import { describe, expect, it, vi } from "vitest";
import { DEFAULT_DATA_BASE, SnapshotError, assertSnapshot, fetchSnapshot, loadDashboard, resolveDataBase } from "../lib/data";
import { SCHEMA_VERSION } from "../lib/types";

const snapshot = (rows: unknown[], generated_at = "2026-10-15T12:00:00Z", schema_version = SCHEMA_VERSION) => ({
  schema_version,
  generated_at,
  rows,
});

function fakeFetch(files: Record<string, unknown>, status = 200) {
  return vi.fn(async (url: string | URL | Request) => {
    const name = String(url).split("/").pop()!.split(".json")[0];
    return new Response(JSON.stringify(files[name] ?? snapshot([])), { status });
  }) as unknown as typeof fetch;
}

describe("resolveDataBase", () => {
  it("läser exempeldata med ?data=sample och annars standardadressen", () => {
    expect(resolveDataBase("?data=sample", "/seismo/", undefined)).toBe("/seismo/sample");
    expect(resolveDataBase("", "/", undefined)).toBe(DEFAULT_DATA_BASE);
  });

  it("låter en miljövariabel åsidosätta standardadressen", () => {
    expect(resolveDataBase("", "/", "https://example.org/data")).toBe("https://example.org/data");
  });
});

describe("assertSnapshot", () => {
  it("godtar rätt format", () => {
    expect(assertSnapshot("x", snapshot([{ a: 1 }])).rows).toHaveLength(1);
  });

  it("avvisar ett filformat med annan version, så att sidan hellre visar fel än fel data", () => {
    expect(() => assertSnapshot("x", snapshot([], "2026-10-15T12:00:00Z", 99))).toThrow(SnapshotError);
  });

  it.each([null, "text", { schema_version: SCHEMA_VERSION }, { schema_version: SCHEMA_VERSION, rows: [] }])("avvisar trasig nyttolast %#", (payload) => {
    expect(() => assertSnapshot("x", payload)).toThrow(SnapshotError);
  });
});

describe("fetchSnapshot", () => {
  it("kastar ett begripligt fel vid HTTP-fel", async () => {
    await expect(fetchSnapshot("http://x", "health", fakeFetch({}, 404))).rejects.toThrow("HTTP 404");
  });

  it("byter cache-nyckel i samma takt som GitHub cachar (5 minuter)", async () => {
    const f = fakeFetch({});
    await fetchSnapshot("http://x", "health", f, 123);
    expect(String((f as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0])).toBe("http://x/health.json?v=123");
  });
});

describe("loadDashboard", () => {
  it("hämtar alla sex filer och använder den äldsta tidsstämpeln som uppsättningens ålder", async () => {
    const files = {
      event_map: snapshot([{ event_id: "a" }], "2026-10-15T12:00:00Z"),
      significant_events: snapshot([], "2026-10-15T11:55:00Z"),
      countries: snapshot([]),
      daily: snapshot([]),
      briefing: snapshot([{ briefing: "hej" }]),
      health: snapshot([{ events_total: 5 }]),
    };
    const f = fakeFetch(files);
    const data = await loadDashboard("http://x", f);
    expect((f as unknown as ReturnType<typeof vi.fn>).mock.calls).toHaveLength(6);
    expect(data.generatedAt).toBe("2026-10-15T11:55:00Z");
    expect(data.eventMap).toHaveLength(1);
    expect(data.briefing?.briefing).toBe("hej");
    expect(data.health?.events_total).toBe(5);
  });

  it("ger null för briefing och hälsa när filerna är tomma", async () => {
    const data = await loadDashboard("http://x", fakeFetch({}));
    expect(data.briefing).toBeNull();
    expect(data.health).toBeNull();
  });
});
