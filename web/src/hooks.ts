import { useCallback, useEffect, useState } from "react";
import { loadDashboard } from "./lib/data";
import type { Dashboard } from "./lib/types";

export type DashboardState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: Dashboard };

const REFRESH_MS = 5 * 60_000; // pipelinen publicerar varje timme, men en öppen flik ska ändå hålla sig aktuell

export function useDashboard(base: string): { state: DashboardState; reload: () => void } {
  const [state, setState] = useState<DashboardState>({ status: "loading" });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    loadDashboard(base)
      .then((data) => !cancelled && setState({ status: "ready", data }))
      .catch((e: unknown) => {
        // Behåll gammal data på skärmen om en uppdatering misslyckas, och visa fel bara om vi inte har något att visa.
        if (!cancelled) setState((prev) => (prev.status === "ready" ? prev : { status: "error", message: String(e) }));
      });
    return () => {
      cancelled = true;
    };
  }, [base, tick]);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setTick((t) => t + 1);
  }, []);

  return { state, reload };
}
