import { SCHEMA_VERSION, type Dashboard, type Snapshot } from "./types";
import type {
  BriefingRow,
  CountryRow,
  DailyRow,
  EventMapRow,
  HealthRow,
  SignificantEvent,
} from "./types";

/** Pipelinen publicerar snapshots som ett enda commit på grenen `data`. Filerna serveras direkt därifrån. */
export const DEFAULT_DATA_BASE = "https://raw.githubusercontent.com/DataMalle/seismo/data/snapshots";

type FetchFn = typeof fetch;

/** `?data=sample` läser medföljande exempeldata (för utveckling och demo utan nätverk). */
export function resolveDataBase(search: string, baseUrl: string, envBase?: string): string {
  if (new URLSearchParams(search).get("data") === "sample") return `${baseUrl}sample`;
  return envBase || DEFAULT_DATA_BASE;
}

export class SnapshotError extends Error {}

export function assertSnapshot<Row>(name: string, payload: unknown): Snapshot<Row> {
  const p = payload as Partial<Snapshot<Row>> | null;
  if (!p || typeof p !== "object") throw new SnapshotError(`${name}: invalid response`);
  if (p.schema_version !== SCHEMA_VERSION) {
    throw new SnapshotError(
      `${name}: file format is version ${String(p.schema_version)} but this page expects ${SCHEMA_VERSION}`,
    );
  }
  if (!Array.isArray(p.rows) || typeof p.generated_at !== "string") {
    throw new SnapshotError(`${name}: missing rows or generated_at`);
  }
  return p as Snapshot<Row>;
}

export async function fetchSnapshot<Row>(
  base: string,
  name: string,
  fetchFn: FetchFn = fetch,
  cacheBust = Math.floor(Date.now() / 300_000), // raw.githubusercontent cachar i 5 minuter, så vi byter nyckel i samma takt
): Promise<Snapshot<Row>> {
  const response = await fetchFn(`${base}/${name}.json?v=${cacheBust}`, { cache: "no-cache" });
  if (!response.ok) throw new SnapshotError(`${name}: HTTP ${response.status}`);
  return assertSnapshot<Row>(name, await response.json());
}

export async function loadDashboard(base: string, fetchFn: FetchFn = fetch): Promise<Dashboard> {
  const get = <Row>(name: string) => fetchSnapshot<Row>(base, name, fetchFn);
  const [map, significant, countries, daily, briefing, health] = await Promise.all([
    get<EventMapRow>("event_map"),
    get<SignificantEvent>("significant_events"),
    get<CountryRow>("countries"),
    get<DailyRow>("daily"),
    get<BriefingRow>("briefing"),
    get<HealthRow>("health"),
  ]);
  // Alla filer kommer från samma publicering, så äldsta tidsstämpeln är hela uppsättningens ålder.
  const generatedAt = [map, significant, countries, daily, briefing, health]
    .map((s) => s.generated_at)
    .sort()[0];
  return {
    generatedAt,
    eventMap: map.rows,
    significant: significant.rows,
    countries: countries.rows,
    daily: daily.rows,
    briefing: briefing.rows[0] ?? null,
    health: health.rows[0] ?? null,
  };
}
