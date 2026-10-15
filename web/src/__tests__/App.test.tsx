import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { pivotDaily } from "../components/TrendsTab";
import { SCHEMA_VERSION } from "../lib/types";

// MapLibre kräver WebGL, som jsdom saknar. Kartan verifieras i riktig webbläsare, inte här.
vi.mock("../components/MapView", () => ({
  MapView: ({ events }: { events: unknown[] }) => <div data-testid="map">{events.length} markers</div>,
  DepthLegend: () => <ul aria-label="legend" />,
}));

const now = Date.now();
const iso = (minutesAgo: number) => new Date(now - minutesAgo * 60_000).toISOString().replace(/\.\d+Z$/, "Z");
const snap = (rows: unknown[], generated = iso(5)) => ({ schema_version: SCHEMA_VERSION, generated_at: generated, rows });

const FILES: Record<string, unknown> = {
  event_map: snap([
    { event_id: "a", event_time: iso(60), magnitude: 4.2, place: "10 km N of Town", latitude: 1, longitude: 2, depth_km: 12 },
    { event_id: "b", event_time: iso(3000), magnitude: 7.7, place: "Off coast of Panama", latitude: 3, longitude: 4, depth_km: 30 },
  ]),
  significant_events: snap([
    { event_id: "b", event_time: iso(3000), magnitude: 7.7, place: "Off coast of Panama", country: "Panama", region: null, depth_km: 30, latitude: 3, longitude: 4, tsunami_flag: true, significance: 900, felt_reports: 5, revisions: 2, url: "https://example.org/b" },
  ]),
  countries: snap([{ country: "Panama", events_30d: 78, max_magnitude: 7.7, strong_events_30d: 65, last_event_time: iso(3000) }]),
  daily: snap([{ event_date: "2026-10-14", magnitude_bucket: "4-5", events: 10, max_magnitude: 4.9, avg_depth_km: 20 }]),
  briefing: snap([{ briefing_date: "2026-10-15", events_today: 81, strong_events_today: 3, max_magnitude_text: "5.3", max_magnitude_where: "NZ", briefing: "Det har inträffat 81 jordbävningar.", llm_endpoint: "llama", generated_at: iso(5) }]),
  health: snap([{ computed_at: iso(5), last_poll_at: iso(20), last_poll_status: "success", last_success_at: iso(20), latest_event_time: iso(2), latest_update_time: iso(2), events_total: 1987, events_deleted: 18, updates_24h: 339, revisions_24h: 6, quarantined_rows: 0, llm_valid_ratio: 1, polls_24h: 10, failed_polls_24h: 4 }]),
};

function mockFetch(files: Record<string, unknown>, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (!ok) return new Response("nej", { status: 500 });
      const name = String(url).split("/").pop()!.split(".json")[0];
      return new Response(JSON.stringify(files[name]));
    }),
  );
}

beforeEach(() => {
  window.location.hash = "";
});

describe("App", () => {
  it("shows the gallery with one tile per work and a summary of the live data", async () => {
    mockFetch(FILES);
    render(<App />);
    expect(await screen.findByText(/1 quakes in the last 24 hours/)).toBeInTheDocument();
    expect(screen.getByText(/strongest this week was M 7\.7/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /MAP|SIGNIFICANT|TRENDS|PLATFORM/ })).toHaveLength(4);
  });

  it("hashtag filters hide tiles without the tag", async () => {
    mockFetch(FILES);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/quakes in the last 24 hours/);
    await user.click(screen.getByRole("button", { name: "#ops" }));
    expect(screen.getByRole("button", { name: "#ops" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("link", { name: /MAP/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /PLATFORM/ })).toBeInTheDocument();
  });

  it("opens a detail view from the hash, moves focus to the heading and shows the summary", async () => {
    mockFetch(FILES);
    window.location.hash = "#/significant";
    render(<App />);
    const heading = await screen.findByRole("heading", { name: "SIGNIFICANT QUAKES" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(await screen.findByText(/Det har inträffat 81 jordbävningar/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Off coast of Panama" })).toHaveAttribute("href", "https://example.org/b");
  });

  it("the map magnitude filter reduces the number of markers", async () => {
    mockFetch(FILES);
    window.location.hash = "#/map";
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByTestId("map")).toHaveTextContent("2 markers");
    await user.click(screen.getByRole("button", { name: "#M5+" }));
    expect(screen.getByTestId("map")).toHaveTextContent("1 markers");
  });

  it("shows the platform view with the SLA", async () => {
    mockFetch(FILES);
    window.location.hash = "#/platform";
    render(<App />);
    expect(await screen.findByText("Freshness SLA (150 min)")).toBeInTheDocument();
  });

  it("warns when the data is older than the SLA", async () => {
    mockFetch({ ...FILES, event_map: snap((FILES.event_map as { rows: unknown[] }).rows, iso(400)) });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("may be out of date");
  });

  it("shows an error with a retry button when loading fails", async () => {
    mockFetch({}, false);
    render(<App />);
    expect(await screen.findByText("Couldn't load the data")).toBeInTheDocument();
    mockFetch(FILES);
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByText(/quakes in the last 24 hours/)).toBeInTheDocument());
  });
});

describe("pivotDaily", () => {
  it("gives one row per day with a column per magnitude class, sorted by date", () => {
    const rows = [
      { event_date: "2026-10-15", magnitude_bucket: "2-3", events: 4, max_magnitude: 2.9, avg_depth_km: 5 },
      { event_date: "2026-10-14", magnitude_bucket: "2-3", events: 7, max_magnitude: 2.8, avg_depth_km: 5 },
      { event_date: "2026-10-14", magnitude_bucket: "5+", events: 1, max_magnitude: 6.1, avg_depth_km: 40 },
    ];
    expect(pivotDaily(rows)).toEqual([
      { date: "2026-10-14", "2-3": 7, "5+": 1 },
      { date: "2026-10-15", "2-3": 4 },
    ]);
  });
});
