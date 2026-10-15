"""Seismo: live dashboard över globala jordbävningar. Läser enbart gold-tabellerna via en read-only service principal."""

import logging
import os
import threading
from dataclasses import dataclass

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st
from databricks.sdk import WorkspaceClient

from config import ConfigError, Settings, load_settings
from insights import (
    depth_color,
    depth_legend_html,
    humanize_minutes,
    last_24h,
    marker_radius_m,
    minutes_since,
    sla_status,
)
from style import ACCENT_TRENDS, dark_chart, header, inject_style
from warehouse import Warehouse

st.set_page_config(page_title="Seismo - Malvin Portfolio Project", page_icon="🌍", layout="wide")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("seismo")

REPO_URL = "https://github.com/DataMalle/seismo"
BUCKETS = ["<2", "2-3", "3-4", "4-5", "5+", "unknown"]
BUCKET_COLORS = ["#3a3a3a", "#666666", "#6aa8b8", "#157b93", "#d10e61", "#7a7a7a"]


@dataclass(frozen=True)
class Services:
    settings: Settings
    warehouse: Warehouse


def _load_streamlit_secrets_into_env() -> None:
    """Streamlit Community Cloud: lägg secrets i miljön så att Databricks-SDK:t hittar dem."""
    try:
        for key, value in st.secrets.items():
            if isinstance(value, str):
                os.environ.setdefault(key, value)
    except Exception:
        pass


@st.cache_resource
def services() -> Services:
    settings = load_settings()
    warehouse = Warehouse(WorkspaceClient(), settings.warehouse_id, settings.catalog, f"{settings.schema_prefix}_gold")
    # Väck warehouse i bakgrunden medan besökaren läser sidan.
    threading.Thread(target=lambda: _prewarm(warehouse), daemon=True).start()
    return Services(settings, warehouse)


def _prewarm(warehouse: Warehouse) -> None:
    try:
        warehouse.query("SELECT 1", attempts=1)
    except Exception as e:
        log.info("Förvärmning misslyckades (ofarligt): %s", e)


@st.cache_data(ttl=300, show_spinner=False)
def gold(table: str, order_by: str = "", limit: int = 0) -> pd.DataFrame:
    svc = services()
    sql = f"SELECT * FROM {svc.settings.gold}.{table}"
    sql += f" ORDER BY {order_by}" if order_by else ""
    sql += f" LIMIT {limit}" if limit else ""
    return svc.warehouse.query(sql)


def utc(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    for col in cols:
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


# --- Flikar -------------------------------------------------------------------------------------------------------


def tab_map(events: pd.DataFrame) -> None:
    st.caption(
        "Every quake from the past 7 days. Bigger circles are stronger quakes, and color shows depth. Hover for details."
    )
    if events.empty:
        st.info("No quakes to show yet.")
        return
    df = events.assign(
        radius=events["magnitude"].map(marker_radius_m),
        color=events["depth_km"].map(depth_color),
        when=events["event_time"].dt.strftime("%Y-%m-%d %H:%M UTC"),
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df[["longitude", "latitude", "radius", "color", "magnitude", "place", "when", "depth_km"]],
        get_position="[longitude, latitude]",
        get_radius="radius",
        get_fill_color="color",
        pickable=True,
        radius_min_pixels=2,
        radius_max_pixels=60,
    )
    tooltip = {"html": "<b>M {magnitude}</b><br/>{place}<br/>{when}<br/>Depth {depth_km} km"}
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(latitude=20, longitude=0, zoom=0.8),
            tooltip=tooltip,
            map_style="dark",
        ),
        height=520,
    )
    st.markdown(depth_legend_html(), unsafe_allow_html=True)


def tab_significant(significant: pd.DataFrame, countries: pd.DataFrame, briefing: pd.DataFrame) -> None:
    if not briefing.empty:
        row = briefing.iloc[0]
        with st.container(border=True, key="card_briefing"):
            st.markdown(f"**Today's summary** · {row['briefing_date']:%Y-%m-%d}")
            st.write(row["briefing"])
            st.caption(
                f"Written by an LLM ({row['llm_endpoint']}) from figures counted in SQL and checked by a dbt test."
            )

    left, right = st.columns([3, 2])
    with left, st.container(border=True, key="card_significant"):
        st.subheader("Quakes of magnitude 4.5 and up")
        st.caption("Last 90 days. An LLM pulls the country out of the USGS place description.")
        view = significant.assign(Time=significant["event_time"].dt.strftime("%Y-%m-%d %H:%M")).rename(
            columns={
                "magnitude": "Magnitude",
                "country": "Country",
                "region": "Region",
                "revisions": "Revisions",
                "place": "Place",
            }
        )
        st.dataframe(
            view[["Time", "Magnitude", "Country", "Place", "Revisions"]].head(200),
            hide_index=True,
            width="stretch",
            column_config={"Magnitude": st.column_config.NumberColumn(format="%.1f")},
        )
    with right, st.container(border=True, key="card_countries"):
        st.subheader("Most active countries")
        st.caption("Quakes in the last 30 days.")
        top = countries.head(12)
        chart = (
            alt.Chart(top)
            .mark_bar(color=ACCENT_TRENDS)
            .encode(
                y=alt.Y("country:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220, labelOverlap=False)),
                x=alt.X("events_30d:Q", title=None),
                tooltip=["country", "events_30d", "max_magnitude", "strong_events_30d"],
            )
            .properties(height=max(220, 28 * len(top)))
        )
        st.altair_chart(dark_chart(chart), width="stretch")


def tab_trends(daily: pd.DataFrame) -> None:
    with st.container(border=True, key="card_daily"):
        st.subheader("Quakes per day, by magnitude")
        chart = (
            alt.Chart(daily)
            .mark_bar()
            .encode(
                x=alt.X("event_date:T", title=None, axis=alt.Axis(format="%d %b")),
                y=alt.Y("events:Q", title="Quakes"),
                color=alt.Color(
                    "magnitude_bucket:N", scale=alt.Scale(domain=BUCKETS, range=BUCKET_COLORS), title="Magnitude"
                ),
                order=alt.Order("magnitude_bucket:N", sort="ascending"),
                tooltip=["event_date", "magnitude_bucket", "events", "max_magnitude"],
            )
            .properties(height=320)
        )
        st.altair_chart(dark_chart(chart), width="stretch")
        st.caption("The first days of the history can be incomplete until the backfill catches up.")


def tab_platform(health: pd.DataFrame) -> None:
    if health.empty:
        st.info("No health data yet.")
        return
    h = health.iloc[0]
    minutes = minutes_since(h["last_success_at"])
    status = sla_status(minutes)
    label = {"ok": "✅ Within SLA", "warn": "⚠️ Close to the limit", "breach": "🔴 SLA missed"}[status]
    if h["last_poll_status"] != "success":
        st.info("The last fetch failed, probably a short USGS outage. The next run picks up whatever was missed.")
    a, b, c, d = st.columns(4)
    a.metric("Last successful run", humanize_minutes(minutes))
    b.metric("Freshness SLA (150 min)", label)
    c.metric("Events changed, 24 h", f"{int(h['updates_24h']):,}")
    d.metric("Revisions, 24 h", f"{int(h['revisions_24h']):,}")
    e, f, g, i = st.columns(4)
    e.metric("Events in total", f"{int(h['events_total']):,}")
    f.metric("Deleted by USGS", f"{int(h['events_deleted']):,}")
    g.metric("Rows in quarantine", int(h["quarantined_rows"]))
    ratio = h["llm_valid_ratio"]
    i.metric("Valid LLM answers", "–" if pd.isna(ratio) else f"{ratio:.0%}")

    with st.container(border=True, key="card_arch"):
        st.subheader("How it works")
        st.graphviz_chart(
            """
            digraph G {
              rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#111111", color="#c13cff", fontcolor="#e8e8e8", fontname="Helvetica"];
              usgs [label="USGS FDSN\\nchange feed (CDC)"]; land [label="Volume\\nraw NDJSON"];
              bronze [label="bronze\\nAuto Loader (streaming)\\nchange log"]; silver [label="silver (dbt)\\nMERGE + SCD2"];
              llm [label="LLM enrichment\\nai_query, cached", fillcolor="#1a1308", color="#e68c28"]; gold [label="gold (dbt)\\ncontracts + tests"];
              app [label="Streamlit", fillcolor="#0a1a0d", color="#19ff3c"]; wd [label="watchdog\\nSLA alerts as GitHub issues", fillcolor="#1a0a0a", color="#ff2a45"];
              edge [color="#666666"]; usgs -> land -> bronze -> silver -> gold -> app; silver -> llm -> gold; gold -> wd;
            }
            """
        )
        st.markdown(
            f"Source code, architecture decisions (ADRs), runbook and cost analysis: [{REPO_URL}]({REPO_URL}). "
            "The app only reads the gold tables. The LLM runs inside the pipeline, never when someone opens the page."
        )


def main() -> None:
    inject_style()
    header(
        "Malvin Portfolio Project. A pipeline that pulls earthquake data from USGS every hour and turns it into this dashboard, built with CDC, dbt, data contracts and AI summaries.",
        "Live · updates every hour",
    )
    _load_streamlit_secrets_into_env()
    try:
        services()
    except ConfigError as e:
        st.error(f"The app is missing configuration: {e}. Add it under App settings → Secrets.")
        st.stop()

    try:
        with st.spinner("Loading data from Databricks. This can take up to a minute if the warehouse was asleep …"):
            events = utc(gold("gold_event_map"), "event_time")
            significant = utc(gold("gold_significant_events", "event_time DESC", 500), "event_time")
            countries = gold("gold_country_summary", "events_30d DESC")
            daily = utc(gold("gold_events_daily", "event_date"), "event_date")
            briefing = gold("gold_daily_briefing", "briefing_date DESC", 1)
            health = utc(gold("gold_pipeline_health"), "last_poll_at", "last_success_at")
    except Exception as e:
        log.exception("Datahämtning misslyckades")
        st.error("Couldn't load the data right now.")
        with st.expander("Technical details"):
            st.code(str(e)[:500])
        if st.button("Try again"):
            st.cache_data.clear()
            st.rerun()
        st.stop()

    recent = last_24h(events)
    strongest = events.loc[events["magnitude"].idxmax()] if not events.empty else None
    poll_minutes = minutes_since(health.iloc[0]["last_success_at"]) if not health.empty else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Quakes, last 24 h", f"{len(recent):,}")
    c2.metric("Strongest, 7 days", "–" if strongest is None else f"M {strongest['magnitude']:.1f}")
    c3.metric("Quakes, 7 days", f"{len(events):,}")
    c4.metric("Data last fetched", humanize_minutes(poll_minutes))
    if strongest is not None:
        st.caption(f"Strongest quake: {strongest['place']}, {strongest['event_time']:%Y-%m-%d %H:%M} UTC.")

    t_map, t_sig, t_trend, t_platform = st.tabs(["Map", "Significant quakes", "Trends", "Platform"])
    with t_map:
        tab_map(events)
    with t_sig:
        tab_significant(significant, countries, briefing)
    with t_trend:
        tab_trends(daily)
    with t_platform:
        tab_platform(health)
    st.caption(
        f"Data: USGS Earthquake Hazards Program. Check official sources before making any safety decision. [Source code]({REPO_URL})"
    )


main()
