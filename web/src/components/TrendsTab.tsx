import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dateOnly, formatInt } from "../lib/format";
import type { DailyRow } from "../lib/types";

export const BUCKETS = ["<2", "2-3", "3-4", "4-5", "5+", "unknown"] as const;
export const BUCKET_COLORS: Record<(typeof BUCKETS)[number], string> = {
  "<2": "#3a3a3a",
  "2-3": "#666",
  "3-4": "#6aa8b8",
  "4-5": "#157b93",
  "5+": "#d10e61",
  unknown: "#7a7a7a",
};

type Series = { date: string } & Partial<Record<(typeof BUCKETS)[number], number>>;

/** Gör om rader (dag, klass, antal) till en rad per dag med en kolumn per magnitudklass, som Recharts vill ha dem. */
export function pivotDaily(rows: DailyRow[]): Series[] {
  const byDate = new Map<string, Series>();
  for (const r of rows) {
    const date = dateOnly(r.event_date);
    const entry = byDate.get(date) ?? { date };
    entry[r.magnitude_bucket as (typeof BUCKETS)[number]] = r.events;
    byDate.set(date, entry);
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function TrendsTab({ daily }: { daily: DailyRow[] }) {
  const data = useMemo(() => pivotDaily(daily), [daily]);
  return (
    <section className="card" aria-labelledby="trend-title">
      <h3 id="trend-title">Quakes per day, by magnitude</h3>
      <div style={{ height: 340 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} stroke="#222" />
            <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} stroke="#7a7a7a" fontSize={12} />
            <YAxis tickFormatter={formatInt} stroke="#7a7a7a" fontSize={12} />
            <Tooltip formatter={(value) => formatInt(Number(value))} cursor={{ fill: "#161616" }} />
            <Legend />
            {BUCKETS.map((b) => (
              <Bar key={b} dataKey={b} stackId="a" fill={BUCKET_COLORS[b]} name={b} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="muted small">The first days of the history can be incomplete until the backfill catches up.</p>
    </section>
  );
}
