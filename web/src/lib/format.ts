const nf = new Intl.NumberFormat("en-US");

export const formatInt = (n: number | null | undefined): string => (n === null || n === undefined ? "–" : nf.format(n));

export const formatMagnitude = (m: number | null | undefined): string =>
  m === null || m === undefined ? "–" : m.toFixed(1);

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "–";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
}

/** Tål både ren datumsträng (2026-10-15) och tidsstämpel (2026-10-15T00:00:00Z). */
export const dateOnly = (value: string): string => value.slice(0, 10);

export const formatPercent = (ratio: number | null | undefined): string =>
  ratio === null || ratio === undefined ? "–" : `${Math.round(ratio * 100)}%`;
