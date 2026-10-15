# Databricks notebook source
# MAGIC %md
# MAGIC # Publicera snapshots till React-sidan
# MAGIC Läser gold-tabellerna med **Spark på jobbcompute** (inte via SQL warehouse, så att publiceringen inte väcker warehouse en gång till
# MAGIC per timme, se `docs/cost-and-performance.md`) och publicerar dem som JSON till grenen `data` på GitHub, som ett enda commit.
# MAGIC React-sidan hämtar filerna därifrån, så nytt data syns utan att sidan behöver byggas om.
# MAGIC
# MAGIC Körs efter dbt och bara om dbt lyckats: ett trasigt bygge publiceras aldrig. Kräver en GitHub-token i secret-scopet `seismo`.
# MAGIC Saknas den hoppas steget över med en varning, så att en valfri integration aldrig fäller pipelinen.

# COMMAND ----------

from datetime import UTC, datetime

import github_publish as gh
import seismo_lib as lib
import seismo_snapshots as snap

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("env", "prod")
dbutils.widgets.text("snapshot_repo", "DataMalle/seismo")
dbutils.widgets.text("snapshot_branch", "data")

catalog = dbutils.widgets.get("catalog")
gold = f"{catalog}.{lib.schema_prefix(dbutils.widgets.get('env'))}_gold"
repo = dbutils.widgets.get("snapshot_repo")
branch = dbutils.widgets.get("snapshot_branch")

# COMMAND ----------

try:
    token = dbutils.secrets.get(scope="seismo", key="github_token")
except Exception as e:
    token = None
    print(f"VARNING: ingen GitHub-token ({str(e)[:120]}). Hoppar över publiceringen.")

# COMMAND ----------

if token:
    frames: dict[str, list[dict]] = {}
    for name, (table, order, limit) in snap.SNAPSHOTS.items():
        sql = (
            f"SELECT * FROM {gold}.{table}"
            + (f" ORDER BY {order}" if order else "")
            + (f" LIMIT {limit}" if limit else "")
        )
        frames[name] = [row.asDict(recursive=True) for row in spark.sql(sql).collect()]
        print(f"{name}: {len(frames[name])} rader")

    generated_at = datetime.now(UTC)
    files = snap.build_files(frames, generated_at)
    sha = gh.publish(
        files,
        repo=repo,
        branch=branch,
        message=f"Snapshots {generated_at:%Y-%m-%d %H:%M} UTC",
        http=gh.github_request(token),
    )
    print(
        f"Publicerade {len(files)} filer ({sum(len(b) for b in files.values()) / 1024:.0f} kB) till {repo}@{branch}: {sha[:10]}"
    )
