import { useMemo, useState } from "react";
import { formatInt, formatMagnitude } from "../lib/format";
import { eventsLast24h, humanizeMinutes, minutesSince, strongest } from "../lib/insights";
import { FILTER_TAGS, filterTiles, type FilterTag } from "../lib/routes";
import type { Dashboard } from "../lib/types";
import { Preview } from "./Previews";

export function Home({ data }: { data: Dashboard }) {
  const [tag, setTag] = useState<FilterTag>("all");
  const tiles = filterTiles(tag);
  const recent = useMemo(() => eventsLast24h(data.eventMap), [data.eventMap]);
  const top = useMemo(() => strongest(data.eventMap), [data.eventMap]);
  const age = minutesSince(data.health?.last_success_at);

  return (
    <>
      <p className="lede">
        Live earthquake data from USGS, run through a lakehouse pipeline. {formatInt(recent.length)} quakes in the last 24 hours
        {top ? `, strongest this week M ${formatMagnitude(top.magnitude)}` : ""}. Data fetched {humanizeMinutes(age)}.
      </p>
      <nav className="filters" aria-label="Filter works">
        {FILTER_TAGS.map((t) => (
          <button key={t} type="button" aria-pressed={tag === t} onClick={() => setTag(t)}>
            #{t}
          </button>
        ))}
      </nav>
      <ul className="grid">
        {tiles.map((tile) => (
          <li key={tile.id} style={{ "--accent": tile.accent } as React.CSSProperties}>
            <a className="tile" href={`#/${tile.id}`} aria-label={`${tile.title}: ${tile.descriptor}`}>
              <div className="tile-art">
                <Preview id={tile.id} data={data} />
              </div>
              <span className="tile-title">{tile.title}</span>
              <span className="tile-desc">{tile.descriptor}</span>
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}
