"""Utvecklingsverktyg: skriver riktiga snapshots (samma format som i produktionen) till en mapp.

Exempel: web/public/sample. Läser gold via SQL warehouse med den inloggning som Databricks-SDK:t hittar
(CLI-profil eller miljövariabler). Produktionen publicerar *inte* så här: där läser jobbet Delta med Spark
och pushar till GitHub (pipeline/03_publish_snapshots.py).

Användning:  python ops/dump_sample.py web/public/sample [prefix]
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from databricks.sdk import WorkspaceClient

import seismo_snapshots as snap
from warehouse import Warehouse


def main(out_dir: str, prefix: str = "seismo") -> None:
    catalog = os.environ.get("CATALOG", "workspace")
    gold = f"{catalog}.{prefix}_gold"
    warehouse = Warehouse(WorkspaceClient(), os.environ["DATABRICKS_WAREHOUSE_ID"], catalog, f"{prefix}_gold")
    frames: dict[str, list[dict]] = {}
    for name, (table, order, limit) in snap.SNAPSHOTS.items():
        sql = (
            f"SELECT * FROM {gold}.{table}"
            + (f" ORDER BY {order}" if order else "")
            + (f" LIMIT {limit}" if limit else "")
        )
        df = warehouse.query(sql)
        for column in ("event_date", "briefing_date"):  # DATE i Delta ska bli ren datumsträng, som i produktionen
            if column in df:
                df[column] = df[column].dt.date
        frames[name] = df.astype(object).where(df.notna(), None).to_dict("records")
        print(f"{name}: {len(frames[name])} rader")
    files = snap.build_files(frames, datetime.now(UTC))
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (target / name).write_bytes(body)
    print(f"Skrev {len(files)} filer till {target} ({sum(len(b) for b in files.values()) / 1024:.0f} kB)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
