"""Bygger JSON-snapshots av gold-tabellerna för den statiska React-sidan. Ren Python utan Spark, så att den kan testas.

Snapshotten är ett *dataprodukt-gränssnitt*: React läser dem som statiska filer, utan backend och utan
hemligheter i drift. Varje fil har samma form: `{"generated_at": ..., "rows": [...]}`. `manifest.json` listar
filerna med radantal och sha256.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from decimal import Decimal

# Namn i snapshotten -> (gold-tabell, ORDER BY, LIMIT). Samma urval som Streamlit-appen använder.
SNAPSHOTS: dict[str, tuple[str, str, int | None]] = {
    "event_map": ("gold_event_map", "event_time DESC", None),
    "significant_events": ("gold_significant_events", "event_time DESC", 500),
    "countries": ("gold_country_summary", "events_30d DESC", None),
    "daily": ("gold_events_daily", "event_date", None),
    "briefing": ("gold_daily_briefing", "briefing_date DESC", 1),
    "health": ("gold_pipeline_health", "", None),
}

SCHEMA_VERSION = 1  # höjs vid brytande ändring av filformatet, så att React kan avvisa ett format den inte förstår


def jsonable(value):
    """Gör ett värde ur en Spark-rad JSON-säkert: tidsstämplar som ISO 8601 i UTC, decimaler som tal, NaN som null."""
    if value is None:
        return None
    if isinstance(value, datetime):
        stamp = value if value.tzinfo else value.replace(tzinfo=UTC)
        return stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def to_records(rows: list[dict]) -> list[dict]:
    return [{key: jsonable(val) for key, val in row.items()} for row in rows]


def _dump(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def build_files(frames: dict[str, list[dict]], generated_at: datetime) -> dict[str, bytes]:
    """Filnamn (relativt snapshots/) -> innehåll, inklusive manifest.json."""
    stamp = jsonable(generated_at)
    files: dict[str, bytes] = {}
    for name, rows in frames.items():
        files[f"{name}.json"] = _dump(
            {"schema_version": SCHEMA_VERSION, "generated_at": stamp, "rows": to_records(rows)}
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": stamp,
        "files": {
            filename: {"rows": len(frames[filename.removesuffix(".json")]), "sha256": hashlib.sha256(body).hexdigest()}
            for filename, body in files.items()
        },
    }
    files["manifest.json"] = _dump(manifest)
    return files
