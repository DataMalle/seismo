import { describe, expect, it } from "vitest";
import {
  DEPTH_BANDS,
  UNKNOWN_DEPTH_COLOR,
  depthColor,
  eventsLast24h,
  humanizeMinutes,
  markerRadiusPx,
  minutesSince,
  slaStatus,
  strongest,
} from "../lib/insights";
import type { EventMapRow } from "../lib/types";

const NOW = new Date("2026-10-15T12:00:00Z");

const ev = (id: string, time: string, magnitude: number | null): EventMapRow => ({
  event_id: id,
  event_time: time,
  magnitude,
  place: null,
  latitude: 0,
  longitude: 0,
  depth_km: 10,
});

describe("slaStatus", () => {
  it.each([
    [0, "ok"],
    [75, "ok"],
    [76, "warn"],
    [150, "warn"],
    [151, "breach"],
    [null, "breach"],
  ] as const)("%s minuter ger %s", (minutes, expected) => {
    expect(slaStatus(minutes)).toBe(expected);
  });
});

describe("minutesSince", () => {
  it("räknar mot en given tidpunkt och tål saknade eller trasiga värden", () => {
    expect(minutesSince("2026-10-15T11:30:00Z", NOW)).toBe(30);
    expect(minutesSince(null, NOW)).toBeNull();
    expect(minutesSince("inte ett datum", NOW)).toBeNull();
  });
});

describe("humanizeMinutes", () => {
  it.each([
    [0.2, "just now"],
    [12, "12 min ago"],
    [180, "3 h ago"],
    [3 * 1440, "3 days ago"],
    [null, "unknown"],
  ] as const)("%s", (minutes, text) => {
    expect(humanizeMinutes(minutes)).toBe(text);
  });
});

describe("depthColor", () => {
  it("följer bandgränserna, inklusive exakt på gränsen", () => {
    expect(depthColor(10)).toBe(DEPTH_BANDS[0].color);
    expect(depthColor(69.9)).toBe(DEPTH_BANDS[0].color);
    expect(depthColor(70)).toBe(DEPTH_BANDS[1].color);
    expect(depthColor(299.9)).toBe(DEPTH_BANDS[1].color);
    expect(depthColor(300)).toBe(DEPTH_BANDS[2].color);
    expect(depthColor(null)).toBe(UNKNOWN_DEPTH_COLOR);
  });

  it("använder samma färger som legenden, så att de aldrig kan glida isär", () => {
    expect(DEPTH_BANDS.map((b) => b.color)).toEqual(["#d10e61", "#e68c28", "#157b93"]);
  });
});

describe("markerRadiusPx", () => {
  it("växer med magnituden, begränsas uppåt och klarar negativa och saknade värden", () => {
    expect(markerRadiusPx(6)).toBeGreaterThan(markerRadiusPx(4));
    expect(markerRadiusPx(4)).toBeGreaterThan(markerRadiusPx(2));
    expect(markerRadiusPx(-1.5)).toBe(markerRadiusPx(0));
    expect(markerRadiusPx(null)).toBe(markerRadiusPx(0));
    expect(markerRadiusPx(10)).toBeLessThanOrEqual(48);
  });
});

describe("eventsLast24h och strongest", () => {
  const events = [ev("ny", "2026-10-15T10:00:00Z", 4.1), ev("gammal", "2026-10-14T08:00:00Z", 6.8), ev("utan", "2026-10-15T09:00:00Z", null)];

  it("filtrerar på händelsetid", () => {
    expect(eventsLast24h(events, NOW).map((e) => e.event_id)).toEqual(["ny", "utan"]);
  });

  it("hittar starkaste skalvet och ignorerar saknade magnituder", () => {
    expect(strongest(events)?.event_id).toBe("gammal");
    expect(strongest([ev("a", "2026-10-15T10:00:00Z", null)])).toBeNull();
    expect(strongest([])).toBeNull();
  });
});
