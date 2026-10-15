# Databricks notebook source
# MAGIC %md
# MAGIC # Extraktion: USGS ändringsfeed (CDC) till landing-volymen
# MAGIC Hämtar alla skalv som *uppdaterats* sedan senaste watermark (nya, reviderade och raderade) via FDSN `updatedafter`.
# MAGIC - **Watermark** hämtas ur bronze-tabellen, så det finns inget externt tillstånd att tappa bort.
# MAGIC - **Gap-medveten:** en lång lucka delas upp i dagsfönster, så att inget anrop passerar USGS sidgräns.
# MAGIC - **Idempotent:** versioner som redan finns i bronze skrivs inte igen, och filen skrivs atomiskt.
# MAGIC - **Backfill:** `mode=backfill` hämtar ett explicit intervall, ett fönster per fil, och hoppar över fönster som redan finns.
# MAGIC
# MAGIC Varje körning loggas i `ops.poll_log`, som även fungerar som pipelinens hjärtslag för freshness-kontroller.

# COMMAND ----------

import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import seismo_lib as lib

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("env", "prod")
dbutils.widgets.dropdown("mode", "incremental", ["incremental", "backfill"])
dbutils.widgets.text("bootstrap_days", "7")  # första körningen: hur långt bakåt
dbutils.widgets.text("backfill_start", "")  # YYYY-MM-DD (UTC), används bara i backfill
dbutils.widgets.text("backfill_end", "")

catalog = dbutils.widgets.get("catalog")
prefix = lib.schema_prefix(dbutils.widgets.get("env"))
mode = dbutils.widgets.get("mode")
bronze = f"{catalog}.{prefix}_bronze"
ops = f"{catalog}.{prefix}_ops"
landing = Path(f"/Volumes/{catalog}/{prefix}_bronze/landing/usgs")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {bronze}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {bronze}.landing")  # råfiler: oföränderlig landningszon
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {ops}")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {ops}.poll_log (
  polled_at TIMESTAMP COMMENT 'När körningen startade (UTC)',
  run_id STRING, mode STRING,
  windows INT COMMENT 'Antal tidsfönster som hämtades',
  fetched INT COMMENT 'Features som USGS returnerade',
  new_versions INT COMMENT 'Varav nya versioner som skrevs till landing',
  watermark_before TIMESTAMP, watermark_after TIMESTAMP,
  duration_s DOUBLE, status STRING, error STRING
) COMMENT 'En rad per extraktionskörning. Pipelinens hjärtslag.'
""")

# COMMAND ----------


def current_watermark() -> datetime | None:
    if not spark.catalog.tableExists(f"{bronze}.usgs_events"):
        return None
    ms = spark.sql(f"SELECT MAX(updated_ms) AS m FROM {bronze}.usgs_events").first()["m"]
    return lib.utc(ms) if ms is not None else None


def known_versions(since: datetime) -> set[tuple[str, int]]:
    if not spark.catalog.tableExists(f"{bronze}.usgs_events"):
        return set()
    rows = spark.sql(
        f"SELECT event_id, updated_ms FROM {bronze}.usgs_events WHERE updated_ms >= {lib.to_ms(since)}"
    ).collect()
    return {(r["event_id"], r["updated_ms"]) for r in rows}


def land(features: list[dict], name: str) -> None:
    """Skriver atomiskt: Auto Loader ignorerar filer som börjar med _, så ingen läser en halvskriven fil."""
    landing.mkdir(parents=True, exist_ok=True)
    tmp = landing / f"_tmp_{uuid.uuid4().hex}"
    tmp.write_text(lib.to_ndjson(features), encoding="utf-8")
    os.replace(tmp, landing / name)


# COMMAND ----------

started = time.monotonic()
now = datetime.now(UTC)
run_id = uuid.uuid4().hex[:12]
watermark_before = current_watermark()
fetched = new_total = n_windows = 0
watermark_after = watermark_before
status, error = "success", None

try:
    if mode == "backfill":
        start = datetime.fromisoformat(dbutils.widgets.get("backfill_start")).replace(tzinfo=UTC)
        end = datetime.fromisoformat(dbutils.widgets.get("backfill_end")).replace(tzinfo=UTC)
        windows = list(lib.split_range(start, end, lib.DEFAULT_CHUNK))
    else:
        windows = lib.plan_windows(watermark_before, now, bootstrap_days=int(dbutils.widgets.get("bootstrap_days")))
    n_windows = len(windows)
    known = known_versions((watermark_before or now) - lib.OVERLAP - lib.DEFAULT_CHUNK)
    collected: list[dict] = []

    for window in windows:
        name = lib.landing_filename(window.updated_after, "backfill") if mode == "backfill" else None
        if name and (landing / name).exists():
            print(f"{window.updated_after:%Y-%m-%d}: finns redan, hoppar över")
            continue
        features = lib.fetch_window(window)
        fetched += len(features)
        fresh = lib.drop_known(features, known)
        known |= {lib.feature_key(f) for f in fresh}
        if mode == "backfill":
            if fresh:
                land(fresh, name)
            new_total += len(fresh)
        else:
            collected += fresh

    if mode == "incremental" and collected:
        land(collected, lib.landing_filename(now))
        new_total = len(collected)
    newest = lib.max_updated(collected) if mode == "incremental" else None
    watermark_after = max(filter(None, [watermark_before, newest]), default=None)
    print(f"{n_windows} fönster, {fetched} hämtade, {new_total} nya versioner")
except Exception as e:
    status, error = "failed", str(e)[:500]
    raise
finally:
    spark.createDataFrame(
        [
            (
                now,
                run_id,
                mode,
                n_windows,
                fetched,
                new_total,
                watermark_before,
                watermark_after,
                round(time.monotonic() - started, 2),
                status,
                error,
            )
        ],
        "polled_at timestamp, run_id string, mode string, windows int, fetched int, new_versions int, "
        "watermark_before timestamp, watermark_after timestamp, duration_s double, status string, error string",
    ).write.mode("append").saveAsTable(f"{ops}.poll_log")
