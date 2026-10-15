import { formatInt, formatPercent } from "../lib/format";
import { humanizeMinutes, minutesSince, slaStatus } from "../lib/insights";
import type { HealthRow } from "../lib/types";

const SLA_LABEL = { ok: "✅ Within SLA", warn: "⚠️ Close to the limit", breach: "🔴 SLA missed" } as const;

const REPO_URL = "https://github.com/DataMalle/seismo";

const PIPELINE = [
  { name: "USGS", detail: "change feed (CDC)" },
  { name: "Landing", detail: "raw NDJSON" },
  { name: "Bronze", detail: "Auto Loader, change log" },
  { name: "Silver", detail: "dbt: MERGE + SCD2" },
  { name: "AI enrichment", detail: "ai_query, cached", accent: true },
  { name: "Gold", detail: "dbt: contracts + tests" },
  { name: "Snapshots", detail: "JSON on GitHub" },
  { name: "This page", detail: "React, no backend", done: true },
];

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

export function PlatformTab({ health }: { health: HealthRow | null }) {
  if (!health) return <p className="muted">No health data yet.</p>;
  const minutes = minutesSince(health.last_success_at);
  const status = slaStatus(minutes);
  return (
    <div className="stack">
      {health.last_poll_status !== "success" && (
        <p className="notice" role="status">
          The last fetch failed, probably a short USGS outage. The next run picks up whatever was missed.
        </p>
      )}
      <div className="stats">
        <Metric label="Last successful run" value={humanizeMinutes(minutes)} />
        <Metric label="Freshness SLA (150 min)" value={SLA_LABEL[status]} />
        <Metric label="Events changed, 24 h" value={formatInt(health.updates_24h)} />
        <Metric label="Revisions, 24 h" value={formatInt(health.revisions_24h)} />
        <Metric label="Events in total" value={formatInt(health.events_total)} />
        <Metric label="Deleted by USGS" value={formatInt(health.events_deleted)} />
        <Metric label="Rows in quarantine" value={formatInt(health.quarantined_rows)} />
        <Metric label="Valid LLM answers" value={formatPercent(health.llm_valid_ratio)} />
      </div>
      <section className="card" aria-labelledby="arch-title">
        <h3 id="arch-title">How it works</h3>
        <ol className="pipeline">
          {PIPELINE.map((step) => (
            <li key={step.name} className={step.accent ? "accent" : step.done ? "done" : ""}>
              <strong>{step.name}</strong>
              <span>{step.detail}</span>
            </li>
          ))}
        </ol>
        <p>
          Source code, architecture decisions (ADR), runbook and cost analysis:{" "}
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            {REPO_URL}
          </a>
          . This page reads static JSON files that the pipeline publishes after each successful run. The LLM runs inside the pipeline, never when someone opens the page.
        </p>
      </section>
    </div>
  );
}
