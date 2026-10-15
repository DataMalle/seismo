"""Watchdog: kontrollerar färskhets-SLA utanför pipelinen och returnerar ett utfall som workflowet agerar på.

Körs av GitHub Actions. Ligger medvetet utanför Databricks-jobbet: en pipeline som stannat kan inte larma om sig själv.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

DEFAULT_SLA_MINUTES = 150  # två missade timkörningar plus marginal


@dataclass(frozen=True)
class Verdict:
    ok: bool
    minutes_since_success: float | None
    last_poll_status: str | None
    reasons: list[str]


def _as_utc(value) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def evaluate(health: dict | None, now: datetime, sla_minutes: int = DEFAULT_SLA_MINUTES) -> Verdict:
    """Ren funktion över en rad ur gold_pipeline_health, så att SLA-logiken går att enhetstesta.

    SLA mäts på senaste *lyckade* körning. Ett enstaka misslyckat försök (t.ex. ett kort USGS-avbrott med 502)
    larmar alltså inte: nästa körning tar igen luckan. Larmet går först när lyckade körningar uteblivit så länge
    att SLA:n är bruten (två missade timmar).
    """
    health = health or {}
    success_at = health.get("last_success_at") or health.get("last_poll_at")
    if not success_at:
        return Verdict(False, None, None, ["Ingen lyckad pipelinekörning registrerad"])
    minutes = (now - _as_utc(success_at)).total_seconds() / 60
    status = health.get("last_poll_status")
    reasons = []
    if minutes > sla_minutes:
        reasons.append(f"Senaste lyckade körning var för {minutes:.0f} minuter sedan (SLA {sla_minutes} min)")
        if status and status != "success":
            reasons.append(f"Senaste försöket avslutades med status '{status}'")
    if (health.get("quarantined_rows") or 0) > 0:
        reasons.append(f"{health['quarantined_rows']} rader i karantän")
    return Verdict(not reasons, round(minutes, 1), status, reasons)


def fetch_health() -> dict | None:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState

    catalog = os.environ.get("CATALOG", "workspace")
    prefix = os.environ.get("SCHEMA_PREFIX", "seismo")
    res = WorkspaceClient().statement_execution.execute_statement(
        statement=f"SELECT * FROM {catalog}.{prefix}_gold.gold_pipeline_health",
        warehouse_id=os.environ["DATABRICKS_WAREHOUSE_ID"],
        wait_timeout="50s",
    )
    if res.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(res.status.error.message if res.status.error else str(res.status.state))
    rows = res.result.data_array if res.result and res.result.data_array else []
    if not rows:
        return None
    return dict(zip([c.name for c in res.manifest.schema.columns], rows[0], strict=True))


def main() -> int:
    verdict = evaluate(fetch_health(), datetime.now(UTC), int(os.environ.get("SLA_MINUTES", DEFAULT_SLA_MINUTES)))
    print(json.dumps(asdict(verdict), ensure_ascii=False))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"ok={'true' if verdict.ok else 'false'}\n")
            fh.write(f"reasons={'; '.join(verdict.reasons)}\n")
    return 0  # utfallet förmedlas via GITHUB_OUTPUT, så att workflowet kan öppna eller stänga ett issue


if __name__ == "__main__":
    sys.exit(main())
