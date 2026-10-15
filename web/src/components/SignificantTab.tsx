import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dateOnly, formatDateTime, formatInt, formatMagnitude } from "../lib/format";
import type { BriefingRow, CountryRow, SignificantEvent } from "../lib/types";

export function SignificantTab({
  significant,
  countries,
  briefing,
}: {
  significant: SignificantEvent[];
  countries: CountryRow[];
  briefing: BriefingRow | null;
}) {
  const topCountries = countries.slice(0, 12);
  return (
    <div className="stack">
      {briefing?.briefing && (
        <section className="card" aria-labelledby="briefing-title">
          <h3 id="briefing-title">Today's summary · {dateOnly(briefing.briefing_date)}</h3>
          <p>{briefing.briefing}</p>
          <p className="muted small">
            Written by an LLM ({briefing.llm_endpoint ?? "unknown model"}) from figures counted in SQL and checked by a dbt test.
          </p>
        </section>
      )}
      <div className="grid-3-2">
        <section className="card" aria-labelledby="sig-title">
          <h3 id="sig-title">Quakes of magnitude 4.5 and up</h3>
          <p className="muted small">
            Last 90 days. An LLM pulls the country out of the USGS place description. 🌊 is the USGS flag <em>tsunami=1</em>, set for large
            events in ocean areas. It does <strong>not</strong> mean a tsunami happened.
          </p>
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th className="num">Magnitude</th>
                  <th>Country</th>
                  <th>Place</th>
                  <th className="num">Revisions</th>
                </tr>
              </thead>
              <tbody>
                {significant.slice(0, 100).map((e) => (
                  <tr key={e.event_id}>
                    <td>{formatDateTime(e.event_time)}</td>
                    <td className="num">
                      <span className={`mag ${e.magnitude >= 6 ? "mag-high" : ""}`}>{formatMagnitude(e.magnitude)}</span>
                      {e.tsunami_flag && (
                        <span
                          title="USGS flag tsunami=1: a large event in an ocean area. It doesn't mean a tsunami happened or will happen."
                          aria-label="Ocean event according to the USGS tsunami flag"
                        >
                          {" "}
                          🌊
                        </span>
                      )}
                    </td>
                    <td>{e.country}</td>
                    <td>{e.url ? <a href={e.url} target="_blank" rel="noreferrer">{e.place ?? "USGS"}</a> : e.place}</td>
                    <td className="num">{e.revisions ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="card" aria-labelledby="country-title">
          <h3 id="country-title">Most active countries</h3>
          <p className="muted small">Quakes in the last 30 days.</p>
          <div style={{ height: Math.max(220, topCountries.length * 30) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topCountries} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid horizontal={false} stroke="#222" />
                <XAxis type="number" tickFormatter={formatInt} stroke="#7a7a7a" fontSize={12} />
                <YAxis type="category" dataKey="country" width={120} stroke="#7a7a7a" fontSize={12} interval={0} />
                <Tooltip
                  formatter={(value) => formatInt(Number(value))}
                  labelFormatter={(label) => String(label)}
                  cursor={{ fill: "#161616" }}
                />
                <Bar dataKey="events_30d" name="Quakes" fill="#157b93" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>
    </div>
  );
}
