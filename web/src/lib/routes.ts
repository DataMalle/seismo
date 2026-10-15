import { useSyncExternalStore } from "react";

export const VIEW_IDS = ["map", "significant", "trends", "platform"] as const;
export type ViewId = (typeof VIEW_IDS)[number];
export type RouteId = "home" | ViewId;

/** `#/map` -> "map". Allt okänt ger startsidan, så en gammal eller trasig länk aldrig ger en tom sida. */
export function parseHash(hash: string): RouteId {
  const id = hash.replace(/^#\/?/, "");
  return (VIEW_IDS as readonly string[]).includes(id) ? (id as ViewId) : "home";
}

const subscribe = (callback: () => void) => {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
};

/** Hash-routing: fungerar på GitHub Pages utan serverkonfiguration, och webbläsarens bakåtknapp fungerar som väntat. */
export function useRoute(): RouteId {
  return parseHash(useSyncExternalStore(subscribe, () => window.location.hash));
}

export interface TileDef {
  id: ViewId;
  title: string;
  descriptor: string;
  tags: readonly string[];
  /** Verkets egen accentfärg, som på ett galleri där varje verk har sin egen färgvärld. */
  accent: string;
}

export const TILES: readonly TileDef[] = [
  { id: "map", title: "MAP", descriptor: "live map of earthquakes", tags: ["map", "data"], accent: "#ff2a45" },
  { id: "significant", title: "SIGNIFICANT QUAKES", descriptor: "M 4.5+ with an AI summary", tags: ["data", "ai"], accent: "#19ff3c" },
  { id: "trends", title: "TRENDS", descriptor: "quakes per day and magnitude", tags: ["data"], accent: "#2f7bff" },
  { id: "platform", title: "PLATFORM", descriptor: "pipeline and data quality", tags: ["ops", "ai"], accent: "#c13cff" },
];

export const FILTER_TAGS = ["all", "map", "data", "ops", "ai"] as const;
export type FilterTag = (typeof FILTER_TAGS)[number];

export function filterTiles(tag: FilterTag): readonly TileDef[] {
  return tag === "all" ? TILES : TILES.filter((t) => t.tags.includes(tag));
}
