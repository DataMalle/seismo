# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze: strömmande ingest med Auto Loader
# MAGIC Läser nya NDJSON-filer från landing-volymen som en strömmande källa (`availableNow`: bearbeta allt nytt och avsluta,
# MAGIC vilket är det kostnadseffektiva mönstret för micro-batch). Checkpointen gör ingesten exactly-once.
# MAGIC
# MAGIC - **Råpayload bevaras** som text (`payload`), så att nya fält hos USGS aldrig kan bryta ingesten. Typning sker i silver.
# MAGIC - **Karantän:** rader utan `id` eller `updated` hamnar i `usgs_events_quarantine` istället för att stoppa strömmen.
# MAGIC - Tabellen exponeras som **Iceberg** via UniForm, så andra motorer (Trino, Snowflake, DuckDB) kan läsa den.

# COMMAND ----------

from pyspark.sql import functions as F

import seismo_lib as lib

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("env", "prod")
catalog = dbutils.widgets.get("catalog")
prefix = lib.schema_prefix(dbutils.widgets.get("env"))
bronze = f"{catalog}.{prefix}_bronze"
landing = f"/Volumes/{catalog}/{prefix}_bronze/landing/usgs"
checkpoint = f"/Volumes/{catalog}/{prefix}_bronze/landing/_checkpoints/usgs_events"

dbutils.fs.mkdirs(landing)

UNIFORM = "'delta.enableIcebergCompatV2' = 'true', 'delta.universalFormat.enabledFormats' = 'iceberg'"
COLUMNS = """
  event_id STRING COMMENT 'USGS händelse-id',
  updated_ms BIGINT COMMENT 'USGS uppdateringstid (epoch ms). Version av händelsen.',
  payload STRING COMMENT 'Oförändrad GeoJSON-feature som text',
  source_file STRING COMMENT 'Landing-filen raden kom från',
  ingested_at TIMESTAMP COMMENT 'När raden lästes in'
"""
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {bronze}.usgs_events ({COLUMNS})
COMMENT 'Append-only ändringslogg: varje version av varje USGS-händelse, i råformat'
TBLPROPERTIES ({UNIFORM})
""")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {bronze}.usgs_events_quarantine ({COLUMNS})
COMMENT 'Rader som saknar id eller updated. Ska vara tom, och alarmeras av dbt-tester.'
""")

# COMMAND ----------


def write_batch(batch_df, batch_id: int) -> None:
    valid = batch_df.filter("event_id IS NOT NULL AND updated_ms IS NOT NULL")
    invalid = batch_df.filter("event_id IS NULL OR updated_ms IS NULL")
    # txnAppId/txnVersion gör skrivningen idempotent om en micro-batch körs om efter ett fel.
    (
        valid.write.format("delta")
        .mode("append")
        .option("txnAppId", "usgs_bronze_valid")
        .option("txnVersion", batch_id)
        .saveAsTable(f"{bronze}.usgs_events")
    )
    (
        invalid.write.format("delta")
        .mode("append")
        .option("txnAppId", "usgs_bronze_invalid")
        .option("txnVersion", batch_id)
        .saveAsTable(f"{bronze}.usgs_events_quarantine")
    )


stream = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "text")  # en rå JSON-feature per rad
    .load(landing)
    .select(
        F.get_json_object("value", "$.id").alias("event_id"),
        F.get_json_object("value", "$.properties.updated").cast("long").alias("updated_ms"),
        F.col("value").alias("payload"),
        F.col("_metadata.file_path").alias("source_file"),
        F.current_timestamp().alias("ingested_at"),
    )
    .writeStream.foreachBatch(write_batch)
    .option("checkpointLocation", checkpoint)
    .trigger(availableNow=True)
    .start()
)
stream.awaitTermination()

progress = stream.recentProgress
rows = sum(p.get("numInputRows") or 0 for p in progress)  # kan vara None för tomma batchar
print(f"Micro-batchar: {len(progress)}, nya rader: {rows}")
print("bronze.usgs_events:", spark.table(f"{bronze}.usgs_events").count())
print("karantän:", spark.table(f"{bronze}.usgs_events_quarantine").count())
