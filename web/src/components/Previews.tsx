import { useMemo } from "react";
import { depthColor } from "../lib/insights";
import type { ViewId } from "../lib/routes";
import type { Dashboard } from "../lib/types";
import { pivotDaily } from "./TrendsTab";

/**
 * Förhandsvisningar för galleriets rutor. Estetiken är LED- och ljuskonst på svart: lysande punkter, pixelrutor och
 * ljusströmmar i en färg per verk. Allt ritas av riktig data (positioner, magnitud, antal per dag) och animeras med CSS,
 * så rörelsen stängs av vid prefers-reduced-motion.
 */

const CELL = 2.4; // avstånd mellan LED-punkterna i kartan (viewBox-enheter)

function MapPreview({ data }: { data: Dashboard }) {
  const dots = useMemo(() => {
    const seen = new Set<string>();
    const out: { key: string; x: number; y: number; r: number; color: string }[] = [];
    for (const e of data.eventMap) {
      if (e.magnitude === null || e.magnitude < 2.5) continue;
      // Snappa till LED-rutnätet så att punkterna sitter i en matris. Starkast vinner när flera hamnar i samma cell.
      const x = Math.round((((e.longitude + 180) / 360) * 100) / CELL) * CELL;
      const y = 37.5 + Math.round((((90 - e.latitude) / 180) * 50) / CELL) * CELL;
      const key = `${x}:${y}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ key, x, y, r: Math.min(0.5 + (e.magnitude - 2.5) * 0.45, 3), color: depthColor(e.depth_km) });
    }
    return out.slice(0, 350);
  }, [data.eventMap]);
  return (
    <svg viewBox="0 0 100 125" preserveAspectRatio="xMidYMid slice" className="preview" aria-hidden="true">
      <defs>
        <pattern id="led-grid" width={CELL} height={CELL} patternUnits="userSpaceOnUse">
          <circle cx={CELL / 2} cy={CELL / 2} r="0.3" fill="#262626" />
        </pattern>
        <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="0.9" />
        </filter>
      </defs>
      <rect x="0" y="0" width="100" height="125" fill="url(#led-grid)" />
      <g filter="url(#glow)">
        {dots.map((d, i) => (
          <circle key={d.key} cx={d.x} cy={d.y} r={d.r * 1.6} fill={d.color} className="led" style={{ animationDelay: `${(i % 14) * 0.2}s` }} />
        ))}
      </g>
      {dots.map((d) => (
        <circle key={`c${d.key}`} cx={d.x} cy={d.y} r={d.r * 0.55} fill="#fff" opacity="0.85" />
      ))}
    </svg>
  );
}

/** Ljusströmmar: en kolumn per skalv. Längd och fart följer magnitud, som regn av ljus. */
function SignificantPreview({ data }: { data: Dashboard }) {
  const streams = useMemo(() => {
    const mags = (data.significant.length ? data.significant.map((e) => e.magnitude) : data.eventMap.map((e) => e.magnitude ?? 3))
      .filter((m): m is number => typeof m === "number")
      .slice(0, 30);
    const count = 44;
    return Array.from({ length: count }, (_, i) => {
      const m = mags.length ? mags[i % mags.length] : 5;
      const seed = (Math.sin(i * 12.9898) * 43758.5453) % 1;
      const r = Math.abs(seed);
      return {
        left: (i / count) * 100 + 1.2,
        height: 22 + Math.min(Math.max(m - 4, 0) / 4, 1) * 50,
        duration: 3 + r * 4,
        delay: -r * 7,
      };
    });
  }, [data.significant, data.eventMap]);
  return (
    <div className="preview preview-rain" aria-hidden="true">
      {streams.map((s, i) => (
        <span key={i} style={{ left: `${s.left}%`, height: `${s.height}%`, animationDuration: `${s.duration}s`, animationDelay: `${s.delay}s` }} />
      ))}
    </div>
  );
}

const ROWS = 18;

/** Staplar byggda av enskilda lysande pixlar, ungefär som LED-ridåerna i ljusinstallationer. */
function TrendsPreview({ data }: { data: Dashboard }) {
  const columns = useMemo(() => {
    const days = pivotDaily(data.daily).slice(-14);
    const totals = days.map((d) => Object.entries(d).reduce((s, [k, v]) => (k === "date" ? s : s + Number(v)), 0));
    const max = Math.max(...totals, 1);
    return totals.map((t) => Math.max(1, Math.round((t / max) * ROWS)));
  }, [data.daily]);
  const w = 100 / Math.max(columns.length, 1);
  return (
    <svg viewBox="0 0 100 125" preserveAspectRatio="xMidYMax slice" className="preview preview-leds" aria-hidden="true">
      {columns.map((lit, c) =>
        Array.from({ length: lit }, (_, r) => (
          <rect
            key={`${c}-${r}`}
            x={c * w + w * 0.2}
            y={120 - (r + 1) * 5.6}
            width={w * 0.6}
            height="3.6"
            className={r === lit - 1 ? "led-top" : "led-on"}
            style={r === lit - 1 ? { animationDelay: `${c * 0.15}s` } : undefined}
          />
        )),
      )}
    </svg>
  );
}

const NODES: [number, number][] = [
  [14, 30], [38, 18], [62, 34], [86, 22], [86, 58], [62, 74], [38, 62], [14, 86],
];

/** Pipelinen som ett nätverk av pixelblock där en puls vandrar från källa till sida. */
function PlatformPreview() {
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" className="preview preview-net" aria-hidden="true">
      {NODES.slice(1).map(([x, y], i) => (
        <line key={i} x1={NODES[i][0]} y1={NODES[i][1]} x2={x} y2={y} />
      ))}
      {NODES.map(([x, y], i) => (
        <rect key={i} x={x - 4} y={y - 4} width="8" height="8" style={{ animationDelay: `${i * 0.4}s` }} />
      ))}
    </svg>
  );
}

export function Preview({ id, data }: { id: ViewId; data: Dashboard }) {
  switch (id) {
    case "map":
      return <MapPreview data={data} />;
    case "significant":
      return <SignificantPreview data={data} />;
    case "trends":
      return <TrendsPreview data={data} />;
    case "platform":
      return <PlatformPreview />;
  }
}
