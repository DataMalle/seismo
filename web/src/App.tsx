import { Detail } from "./components/Detail";
import { Home } from "./components/Home";
import { Wordmark } from "./components/Wordmark";
import { useDashboard } from "./hooks";
import { resolveDataBase } from "./lib/data";
import { humanizeMinutes, minutesSince, SLA_BREACH_MINUTES } from "./lib/insights";
import { useRoute } from "./lib/routes";

export default function App() {
  const base = resolveDataBase(window.location.search, import.meta.env.BASE_URL, import.meta.env.VITE_DATA_BASE);
  const { state, reload } = useDashboard(base);
  const route = useRoute();
  const publishedAge = state.status === "ready" ? minutesSince(state.data.generatedAt) : null;
  const stale = publishedAge !== null && publishedAge > SLA_BREACH_MINUTES;

  return (
    <div className="page">
      <header className="top">
        <a className="wordmark" href="#/" aria-label="Seismo, home">
          <Wordmark />
        </a>
        <nav aria-label="Main menu">
          <a href="#/platform">Platform</a>
          <a href="https://github.com/DataMalle/seismo" target="_blank" rel="noreferrer">
            Source code
          </a>
        </nav>
      </header>
      <main>
        {state.status === "loading" && (
          <p className="muted" role="status">
            Loading data …
          </p>
        )}
        {state.status === "error" && (
          <div role="alert">
            <h2>Could not load data</h2>
            <p className="muted small">{state.message}</p>
            <button className="button" onClick={reload}>
              Try again
            </button>
          </div>
        )}
        {state.status === "ready" && (
          <>
            {stale && (
              <p className="notice" role="alert">
                The data was published {humanizeMinutes(publishedAge)} and may be out of date. The pipeline may have stopped.
              </p>
            )}
            {route === "home" ? <Home data={state.data} /> : <Detail id={route} data={state.data} />}
          </>
        )}
      </main>
      <footer className="muted small">
        Malvin Portfolio Project. Data: USGS Earthquake Hazards Program. Use official sources for any safety decision.
      </footer>
    </div>
  );
}
