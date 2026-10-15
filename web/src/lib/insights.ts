/** Ren logik bakom dashboarden. Motsvarar app/insights.py i Streamlit-versionen, med samma trösklar och färger. */

import type { EventMapRow } from "./types";

export const SLA_OK_MINUTES = 75; // jobbet körs varje timme
export const SLA_BREACH_MINUTES = 150; // två missade körningar

export type SlaStatus = "ok" | "warn" | "breach";

export function minutesSince(timestamp: string | null | undefined, now: Date = new Date()): number | null {
  if (!timestamp) return null;
  const then = Date.parse(timestamp);
  if (Number.isNaN(then)) return null;
  return (now.getTime() - then) / 60_000;
}

export function slaStatus(minutes: number | null): SlaStatus {
  if (minutes === null || minutes > SLA_BREACH_MINUTES) return "breach";
  return minutes <= SLA_OK_MINUTES ? "ok" : "warn";
}

export function humanizeMinutes(minutes: number | null): string {
  if (minutes === null) return "unknown";
  if (minutes < 1) return "just now";
  if (minutes < 120) return `${Math.round(minutes)} min ago`;
  if (minutes < 48 * 60) return `${Math.round(minutes / 60)} h ago`;
  return `${Math.round(minutes / 1440)} days ago`;
}

export interface DepthBand {
  key: "shallow" | "mid" | "deep";
  label: string;
  span: string;
  /** Övre gräns i km (exklusiv). null för sista bandet. */
  upper: number | null;
  color: string;
}

/** En enda källa för djupfärgerna: kartan och legenden läser båda härifrån, så de kan aldrig glida isär. */
export const DEPTH_BANDS: readonly DepthBand[] = [
  { key: "shallow", label: "shallow", span: "<70 km", upper: 70, color: "#d10e61" },
  { key: "mid", label: "mid", span: "70–300 km", upper: 300, color: "#e68c28" },
  { key: "deep", label: "deep", span: ">300 km", upper: null, color: "#157b93" },
];
export const UNKNOWN_DEPTH_COLOR = "#7a7a7a";

export function depthColor(depthKm: number | null | undefined): string {
  if (depthKm === null || depthKm === undefined || Number.isNaN(depthKm)) return UNKNOWN_DEPTH_COLOR;
  const band = DEPTH_BANDS.find((b) => b.upper === null || depthKm < b.upper);
  return (band ?? DEPTH_BANDS[DEPTH_BANDS.length - 1]).color;
}

/** Markörradie i pixlar: växer ungefär geometriskt med magnituden så att stora skalv syns utan att dölja små. */
export function markerRadiusPx(magnitude: number | null | undefined): number {
  const m = Math.max(magnitude ?? 0, 0);
  return Math.min(2 + 1.7 ** (m + 1.5), 48);
}

export type MagnitudeFilter = 0 | 4 | 5 | 6;
export type DepthFilter = "all" | DepthBand["key"];

/** Filter för kartans hashtags: lägsta magnitud och djupband. Skalv utan magnitud eller djup faller bort när filtret är aktivt. */
export function filterEvents(events: EventMapRow[], minMagnitude: MagnitudeFilter, depth: DepthFilter): EventMapRow[] {
  const band = DEPTH_BANDS.find((b) => b.key === depth);
  const lower = band ? (DEPTH_BANDS[DEPTH_BANDS.indexOf(band) - 1]?.upper ?? 0) : null;
  return events.filter((e) => {
    if (minMagnitude > 0 && (e.magnitude === null || e.magnitude < minMagnitude)) return false;
    if (band && lower !== null) {
      if (e.depth_km === null || e.depth_km < lower) return false;
      if (band.upper !== null && e.depth_km >= band.upper) return false;
    }
    return true;
  });
}

export function eventsLast24h(events: EventMapRow[], now: Date = new Date()): EventMapRow[] {
  const cutoff = now.getTime() - 24 * 3_600_000;
  return events.filter((e) => Date.parse(e.event_time) >= cutoff);
}

export function strongest(events: EventMapRow[]): EventMapRow | null {
  return events.reduce<EventMapRow | null>(
    (best, e) => (e.magnitude !== null && (best === null || e.magnitude > (best.magnitude ?? -Infinity)) ? e : best),
    null,
  );
}
