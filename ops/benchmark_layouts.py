# Databricks notebook source
# MAGIC %md
# MAGIC # Benchmark: tabellayout och småfiler
# MAGIC Jämför fysiska layouter för en händelsetabell med samma schema som `silver.events`, på **syntetisk** data (riktiga
# MAGIC USGS-volymer är för små för att skilja layouterna åt). Mäter dessutom effekten av småfilsproblemet som uppstår av
# MAGIC 30-minuters micro-batchar, och av `OPTIMIZE`.
# MAGIC
# MAGIC Resultaten sparas i `seismo_ops.benchmark_results` och skrivs ut. Körs manuellt, aldrig schemalagt.
# MAGIC Alla tider är medianen av flera körningar efter en uppvärmningskörning.

# COMMAND ----------

import json
import statistics
import time

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("rows", "10000000")
dbutils.widgets.text("small_batches", "400")  # antal micro-batchar i småfilsexperimentet
dbutils.widgets.text("rows_per_batch", "5000")

catalog = dbutils.widgets.get("catalog")
rows = int(dbutils.widgets.get("rows"))
small_batches = int(dbutils.widgets.get("small_batches"))
rows_per_batch = int(dbutils.widgets.get("rows_per_batch"))
schema = f"{catalog}.seismo_bench"
ops = f"{catalog}.seismo_ops"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {ops}")
results: list[dict] = []

# COMMAND ----------


def synthetic(n: int, id_offset: int = 0):
    """n händelser spridda över tre år, med magnitud som ger många små och få stora skalv (som verkligheten)."""
    return (
        spark.range(id_offset, id_offset + n)
        .withColumn("event_id", F.concat(F.lit("ev"), F.col("id").cast("string")))
        .withColumn(
            "event_time",
            F.expr("timestampadd(SECOND, cast(rand(1) * 94608000 as int), timestamp'2023-10-01 00:00:00')"),
        )
        .withColumn("magnitude", F.round(F.lit(0.5) + (-F.log(F.rand(2)) / F.lit(2.3)), 1))
        .withColumn("depth_km", F.round(F.rand(3) * 300, 1))
        .withColumn("latitude", F.round(F.rand(4) * 180 - 90, 3))
        .withColumn("longitude", F.round(F.rand(5) * 360 - 180, 3))
        .withColumn("country", F.concat(F.lit("C"), (F.rand(6) * 200).cast("int").cast("string")))
        .drop("id")
    )


def timed(sql: str, runs: int = 5) -> float:
    spark.sql(sql).collect()  # uppvärmning
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        spark.sql(sql).collect()
        samples.append(time.perf_counter() - t0)
    return round(statistics.median(samples), 3)


def table_stats(name: str) -> dict:
    d = spark.sql(f"DESCRIBE DETAIL {name}").first()
    return {"files": d["numFiles"], "size_mb": round(d["sizeInBytes"] / 1e6, 1)}


QUERIES = {
    "q1_last_7_days_count": "SELECT count(*) FROM {t} WHERE event_time >= timestamp'2026-09-24' AND event_time < timestamp'2026-10-01'",
    "q2_point_lookup": "SELECT * FROM {t} WHERE event_id = 'ev4242424'",
    "q3_country_month_agg": "SELECT country, date_trunc('month', event_time) m, count(*) c, max(magnitude) FROM {t} GROUP BY 1, 2",
}


def record(layout: str, table: str, note: str = "") -> None:
    stats = table_stats(table)
    for qname, tmpl in QUERIES.items():
        results.append(
            {
                "experiment": "layout",
                "layout": layout,
                "query": qname,
                "seconds": timed(tmpl.format(t=table)),
                **stats,
                "note": note,
            }
        )
    print(layout, stats)


# COMMAND ----------
# MAGIC %md
# MAGIC ## Experiment 1: tre layouter för samma data

# COMMAND ----------

base = synthetic(rows)

# a) Ingen layout: slumpmässig ordning, inga partitioner
spark.sql(f"DROP TABLE IF EXISTS {schema}.events_plain")
base.write.format("delta").saveAsTable(f"{schema}.events_plain")
record("a_unclustered", f"{schema}.events_plain")

# b) Partitionerad per dag (det klassiska valet): ~1 095 partitioner för tre år
spark.sql(f"DROP TABLE IF EXISTS {schema}.events_partitioned")
base.withColumn("event_date", F.to_date("event_time")).write.format("delta").partitionBy("event_date").saveAsTable(
    f"{schema}.events_partitioned"
)
record("b_partitioned_by_day", f"{schema}.events_partitioned", "~1095 partitioner")

# c) Liquid clustering på event_time (valet i Seismo)
spark.sql(f"DROP TABLE IF EXISTS {schema}.events_clustered")
spark.sql(f"CREATE TABLE {schema}.events_clustered CLUSTER BY (event_time) AS SELECT * FROM {schema}.events_plain")
spark.sql(f"OPTIMIZE {schema}.events_clustered")
record("c_liquid_clustered", f"{schema}.events_clustered")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Experiment 2: småfilsproblemet från micro-batchar, före och efter OPTIMIZE

# COMMAND ----------


def microbatch_experiment() -> None:
    spark.sql(f"DROP TABLE IF EXISTS {schema}.events_microbatch")
    spark.sql(
        f"CREATE TABLE {schema}.events_microbatch CLUSTER BY (event_time) AS SELECT * FROM {schema}.events_plain WHERE 1 = 0"
    )
    t0 = time.perf_counter()
    for i in range(small_batches):
        synthetic(rows_per_batch, id_offset=i * rows_per_batch).write.format("delta").mode("append").saveAsTable(
            f"{schema}.events_microbatch"
        )
    ingest_s = round(time.perf_counter() - t0, 1)
    before = table_stats(f"{schema}.events_microbatch")
    print(f"{small_batches} micro-batchar à {rows_per_batch} rader skrevs på {ingest_s}s: {before}")

    for qname, tmpl in QUERIES.items():
        results.append(
            {
                "experiment": "microbatch",
                "layout": "before_optimize",
                "query": qname,
                "seconds": timed(tmpl.format(t=f"{schema}.events_microbatch")),
                **before,
                "note": f"ingest {ingest_s}s",
            }
        )

    t0 = time.perf_counter()
    spark.sql(f"OPTIMIZE {schema}.events_microbatch")
    optimize_s = round(time.perf_counter() - t0, 1)
    after = table_stats(f"{schema}.events_microbatch")
    print(f"OPTIMIZE tog {optimize_s}s: {after}")
    for qname, tmpl in QUERIES.items():
        results.append(
            {
                "experiment": "microbatch",
                "layout": "after_optimize",
                "query": qname,
                "seconds": timed(tmpl.format(t=f"{schema}.events_microbatch")),
                **after,
                "note": f"optimize {optimize_s}s",
            }
        )

    # COMMAND ----------


if small_batches > 0:
    microbatch_experiment()
else:
    print("small_batches = 0: hoppar över småfilsexperimentet")

out = spark.createDataFrame(results).withColumn("run_at", F.current_timestamp()).withColumn("rows", F.lit(rows))
out.write.mode("append").saveAsTable(f"{ops}.benchmark_results")
display(out.orderBy("experiment", "query", "layout"))
dbutils.notebook.exit(json.dumps(results))
