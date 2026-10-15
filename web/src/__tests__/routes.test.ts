import { describe, expect, it } from "vitest";
import { filterEvents } from "../lib/insights";
import { FILTER_TAGS, TILES, filterTiles, parseHash } from "../lib/routes";
import type { EventMapRow } from "../lib/types";

const ev = (id: string, magnitude: number | null, depth: number | null): EventMapRow => ({
  event_id: id,
  event_time: "2026-10-15T10:00:00Z",
  magnitude,
  place: null,
  latitude: 0,
  longitude: 0,
  depth_km: depth,
});

describe("parseHash", () => {
  it.each([
    ["#/map", "map"],
    ["#/significant", "significant"],
    ["#trends", "trends"],
    ["#/platform", "platform"],
    ["", "home"],
    ["#/", "home"],
    ["#/finns-inte", "home"],
  ] as const)("%s -> %s", (hash, expected) => {
    expect(parseHash(hash)).toBe(expected);
  });
});

describe("filterTiles", () => {
  it("visar alla rutor för #alla och annars bara de som har taggen", () => {
    expect(filterTiles("all")).toHaveLength(TILES.length);
    expect(filterTiles("map").map((t) => t.id)).toEqual(["map"]);
    expect(filterTiles("ai").map((t) => t.id)).toEqual(["significant", "platform"]);
  });

  it("varje tagg i filterraden ger minst en ruta, så ingen knapp leder till en tom sida", () => {
    for (const tag of FILTER_TAGS) expect(filterTiles(tag).length).toBeGreaterThan(0);
  });

  it("varje ruta har en unik accentfärg", () => {
    expect(new Set(TILES.map((t) => t.accent)).size).toBe(TILES.length);
  });
});

describe("filterEvents", () => {
  const events = [ev("a", 3.1, 10), ev("b", 5.2, 150), ev("c", 6.4, 500), ev("d", null, null), ev("e", 4.5, 70), ev("f", 6, 300)];
  const ids = (list: EventMapRow[]) => list.map((e) => e.event_id);

  it("utan filter returneras allt, även skalv utan magnitud och djup", () => {
    expect(ids(filterEvents(events, 0, "all"))).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("filtrerar på lägsta magnitud och släpper skalv utan magnitud", () => {
    expect(ids(filterEvents(events, 5, "all"))).toEqual(["b", "c", "f"]);
    expect(ids(filterEvents(events, 6, "all"))).toEqual(["c", "f"]);
  });

  it("djupbanden följer samma gränser som kartfärgerna, inklusive exakt på gränsen", () => {
    expect(ids(filterEvents(events, 0, "shallow"))).toEqual(["a"]);
    expect(ids(filterEvents(events, 0, "mid"))).toEqual(["b", "e"]); // 70 km hör till mellanbandet
    expect(ids(filterEvents(events, 0, "deep"))).toEqual(["c", "f"]); // 300 km hör till det djupa
  });

  it("kombinerar magnitud och djup", () => {
    expect(ids(filterEvents(events, 5, "deep"))).toEqual(["c", "f"]);
    expect(ids(filterEvents(events, 6, "mid"))).toEqual([]);
  });
});
