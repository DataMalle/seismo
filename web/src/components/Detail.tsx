import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { filterEvents, type DepthFilter, type MagnitudeFilter } from "../lib/insights";
import { DEPTH_BANDS } from "../lib/insights";
import { TILES, type ViewId } from "../lib/routes";
import type { Dashboard } from "../lib/types";
import { DepthLegend, MapView } from "./MapView";
import { PlatformTab } from "./PlatformTab";
import { SignificantTab } from "./SignificantTab";
import { TrendsTab } from "./TrendsTab";

const MAGNITUDES: { value: MagnitudeFilter; label: string }[] = [
  { value: 0, label: "#all" },
  { value: 4, label: "#M4+" },
  { value: 5, label: "#M5+" },
  { value: 6, label: "#M6+" },
];

function MapDetail({ data }: { data: Dashboard }) {
  const [mag, setMag] = useState<MagnitudeFilter>(0);
  const [depth, setDepth] = useState<DepthFilter>("all");
  const events = useMemo(() => filterEvents(data.eventMap, mag, depth), [data.eventMap, mag, depth]);
  return (
    <section aria-label="Map">
      <div className="filters" role="group" aria-label="Filter quakes">
        {MAGNITUDES.map((m) => (
          <button key={m.value} type="button" aria-pressed={mag === m.value} onClick={() => setMag(m.value)}>
            {m.label}
          </button>
        ))}
        <span className="filters-sep" aria-hidden="true" />
        <button type="button" aria-pressed={depth === "all"} onClick={() => setDepth("all")}>
          #all depths
        </button>
        {DEPTH_BANDS.map((b) => (
          <button key={b.key} type="button" aria-pressed={depth === b.key} onClick={() => setDepth(b.key)}>
            #{b.label}
          </button>
        ))}
      </div>
      <p className="muted small" role="status">
        {events.length} of {data.eventMap.length} quakes from the last 7 days. Size shows magnitude, color shows depth. Click a quake for details.
      </p>
      <MapView events={events} />
      <DepthLegend />
    </section>
  );
}

function body(id: ViewId, data: Dashboard): ReactNode {
  switch (id) {
    case "map":
      return <MapDetail data={data} />;
    case "significant":
      return <SignificantTab significant={data.significant} countries={data.countries} briefing={data.briefing} />;
    case "trends":
      return <TrendsTab daily={data.daily} />;
    case "platform":
      return <PlatformTab health={data.health} />;
  }
}

export function Detail({ id, data }: { id: ViewId; data: Dashboard }) {
  const tile = TILES.find((t) => t.id === id)!;
  const heading = useRef<HTMLHeadingElement>(null);
  // Fokus flyttas till rubriken vid navigering, så skärmläsare och tangentbord inte blir kvar i galleriet.
  useEffect(() => heading.current?.focus(), [id]);
  return (
    <div className="detail" style={{ "--accent": tile.accent } as React.CSSProperties}>
      <a className="back" href="#/">
        ← Works
      </a>
      <h2 ref={heading} tabIndex={-1}>
        {tile.title}
      </h2>
      <p className="muted small">{tile.descriptor}</p>
      {body(id, data)}
    </div>
  );
}
