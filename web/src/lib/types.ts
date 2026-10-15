/** Formen på JSON-snapshotten som pipelinen publicerar (se pipeline/seismo_snapshots.py). Tidsstämplar är ISO 8601 i UTC. */

export const SCHEMA_VERSION = 1;

export interface Snapshot<Row> {
  schema_version: number;
  generated_at: string;
  rows: Row[];
}

export interface EventMapRow {
  event_id: string;
  event_time: string;
  magnitude: number | null;
  place: string | null;
  latitude: number;
  longitude: number;
  depth_km: number | null;
}

export interface SignificantEvent {
  event_id: string;
  event_time: string;
  magnitude: number;
  place: string | null;
  country: string;
  region: string | null;
  depth_km: number | null;
  latitude: number | null;
  longitude: number | null;
  /** USGS-flaggan tsunami=1: stor händelse i oceaniskt område. Betyder inte att en tsunami har inträffat. */
  tsunami_flag: boolean;
  significance: number | null;
  felt_reports: number | null;
  revisions: number | null;
  url: string | null;
}

export interface CountryRow {
  country: string;
  events_30d: number;
  max_magnitude: number | null;
  strong_events_30d: number;
  last_event_time: string | null;
}

export interface DailyRow {
  event_date: string;
  magnitude_bucket: string;
  events: number;
  max_magnitude: number | null;
  avg_depth_km: number | null;
}

export interface BriefingRow {
  briefing_date: string;
  events_today: number;
  strong_events_today: number;
  max_magnitude_text: string | null;
  max_magnitude_where: string | null;
  briefing: string | null;
  llm_endpoint: string | null;
  generated_at: string | null;
}

export interface HealthRow {
  computed_at: string;
  last_poll_at: string | null;
  last_poll_status: string | null;
  last_success_at: string | null;
  latest_event_time: string | null;
  latest_update_time: string | null;
  events_total: number;
  events_deleted: number;
  updates_24h: number;
  revisions_24h: number;
  quarantined_rows: number;
  llm_valid_ratio: number | null;
  polls_24h: number;
  failed_polls_24h: number;
}

export interface Dashboard {
  generatedAt: string;
  eventMap: EventMapRow[];
  significant: SignificantEvent[];
  countries: CountryRow[];
  daily: DailyRow[];
  briefing: BriefingRow | null;
  health: HealthRow | null;
}
