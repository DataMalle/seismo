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
from insights import depth_color, humanize_minutes, last_24h, marker_radius_m, minutes_since, sla_status
from style import TEAL, hero, inject_style
from warehouse import Warehouse

st.set_page_config(page_title="Seismo - Malvin Portfolio Project", page_icon="🌍", layout="wide")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("seismo")

REPO_URL = "https://github.com/DataMalle/seismo"
BUCKETS = ["<2", "2-3", "3-4", "4-5", "5+", "unknown"]
BUCKET_COLORS = ["#d9d9d9", "#bdbdbd", "#8fb8c4", "#157b93", "#d10e61", "#7a7a7a"]


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
    st.caption("Skalv de senaste 7 dagarna. Storlek visar magnitud och färg visar djup. Hovra för detaljer.")
    if events.empty:
        st.info("Inga skalv att visa ännu.")
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
    tooltip = {"html": "<b>M {magnitude}</b><br/>{place}<br/>{when}<br/>Djup {depth_km} km"}
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(latitude=20, longitude=0, zoom=0.8),
            tooltip=tooltip,
            map_style="light",
        ),
        height=520,
    )
    st.caption("🟣 grunda (<70 km)   🟠 mellan (70–300 km)   🔵 djupa (>300 km)")


def tab_significant(significant: pd.DataFrame, countries: pd.DataFrame, briefing: pd.DataFrame) -> None:
    if not briefing.empty:
        row = briefing.iloc[0]
        with st.container(border=True, key="card_briefing"):
            st.markdown(f"**Dagens sammandrag** · {row['briefing_date']:%Y-%m-%d}")
            st.write(row["briefing"])
            st.caption(
                f"Skriven av en LLM ({row['llm_endpoint']}) utifrån siffror som räknats i SQL och verifierats av ett dbt-test."
            )

    left, right = st.columns([3, 2])
    with left, st.container(border=True, key="card_significant"):
        st.subheader("Skalv med magnitud 4,5 eller högre")
        st.caption("Senaste 90 dagarna. Land är extraherat av en LLM ur USGS platsbeskrivning.")
        view = significant.assign(Tid=significant["event_time"].dt.strftime("%Y-%m-%d %H:%M")).rename(
            columns={
                "magnitude": "Magnitud",
                "country": "Land",
                "region": "Region",
                "revisions": "Versioner",
                "place": "Plats",
            }
        )
        st.dataframe(
            view[["Tid", "Magnitud", "Land", "Plats", "Versioner"]].head(200),
            hide_index=True,
            width="stretch",
            column_config={"Magnitud": st.column_config.NumberColumn(format="%.1f")},
        )
    with right, st.container(border=True, key="card_countries"):
        st.subheader("Mest aktiva länder")
        st.caption("Antal skalv senaste 30 dagarna.")
        top = countries.head(12)
        chart = (
            alt.Chart(top)
            .mark_bar(color=TEAL, cornerRadiusEnd=3)
            .encode(
                y=alt.Y("country:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220, labelOverlap=False)),
                x=alt.X("events_30d:Q", title=None),
                tooltip=["country", "events_30d", "max_magnitude", "strong_events_30d"],
            )
            .properties(height=max(220, 28 * len(top)))
        )
        st.altair_chart(chart, width="stretch")


def tab_trends(daily: pd.DataFrame) -> None:
    with st.container(border=True, key="card_daily"):
        st.subheader("Skalv per dag och magnitudklass")
        chart = (
            alt.Chart(daily)
            .mark_bar()
            .encode(
                x=alt.X("event_date:T", title=None, axis=alt.Axis(format="%d %b")),
                y=alt.Y("events:Q", title="Antal skalv"),
                color=alt.Color(
                    "magnitude_bucket:N", scale=alt.Scale(domain=BUCKETS, range=BUCKET_COLORS), title="Magnitud"
                ),
                order=alt.Order("magnitude_bucket:N", sort="ascending"),
                tooltip=["event_date", "magnitude_bucket", "events", "max_magnitude"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, width="stretch")
        st.caption("Dagar nära början av historiken kan vara ofullständiga tills backfillen hunnit ikapp.")


def tab_platform(health: pd.DataFrame) -> None:
    if health.empty:
        st.info("Ingen hälsodata ännu.")
        return
    h = health.iloc[0]
    minutes = minutes_since(h["last_poll_at"])
    status = sla_status(minutes)
    label = {"ok": "✅ Inom SLA", "warn": "⚠️ Nära SLA-gränsen", "breach": "🔴 SLA bruten"}[status]
    a, b, c, d = st.columns(4)
    a.metric("Senaste körning", humanize_minutes(minutes))
    b.metric("Färskhets-SLA (90 min)", label)
    c.metric("Ändrade händelser, 24 h", f"{int(h['updates_24h']):,}".replace(",", " "))
    d.metric("Revideringar, 24 h", f"{int(h['revisions_24h']):,}".replace(",", " "))
    e, f, g, i = st.columns(4)
    e.metric("Händelser totalt", f"{int(h['events_total']):,}".replace(",", " "))
    f.metric("Raderade av USGS", f"{int(h['events_deleted']):,}".replace(",", " "))
    g.metric("Rader i karantän", int(h["quarantined_rows"]))
    ratio = h["llm_valid_ratio"]
    i.metric("Giltiga LLM-svar", "–" if pd.isna(ratio) else f"{ratio:.0%}")

    with st.container(border=True, key="card_arch"):
        st.subheader("Så fungerar plattformen")
        st.graphviz_chart(
            """
            digraph G {
              rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#eef2f3", fontname="Helvetica"];
              usgs [label="USGS FDSN\\nändringsfeed (CDC)"]; land [label="Volume\\nrå NDJSON"];
              bronze [label="bronze\\nAuto Loader (streaming)\\nändringslogg"]; silver [label="silver (dbt)\\nMERGE + SCD2"];
              llm [label="LLM-berikning\\nai_query, cachad", fillcolor="#fff7e6"]; gold [label="gold (dbt)\\nkontrakt + tester"];
              app [label="Streamlit", fillcolor="#e6ffed"]; wd [label="watchdog\\nSLA till GitHub-issue", fillcolor="#ffecec"];
              usgs -> land -> bronze -> silver -> gold -> app; silver -> llm -> gold; gold -> wd;
            }
            """
        )
        st.markdown(
            f"Källkod, arkitekturbeslut (ADR), runbook och kostnadsanalys: [{REPO_URL}]({REPO_URL}). "
            "Appen läser bara gold-tabellerna, och LLM-steget körs i pipelinen, aldrig per besök."
        )


def main() -> None:
    inject_style()
    hero(
        "Seismo",
        "Malvin Portfolio Project · Live lakehouse-plattform över globala jordbävningar (USGS) med CDC, dbt, datakontrakt och AI-berikning.",
        "Live · uppdateras var 30:e minut",
    )
    _load_streamlit_secrets_into_env()
    try:
        services()
    except ConfigError as e:
        st.error(f"Appen saknar konfiguration: {e}. Lägg till den under App settings → Secrets.")
        st.stop()

    try:
        with st.spinner("Hämtar data från Databricks (kan ta upp till någon minut om warehouse sover) …"):
            events = utc(gold("gold_event_map"), "event_time")
            significant = utc(gold("gold_significant_events", "event_time DESC", 500), "event_time")
            countries = gold("gold_country_summary", "events_30d DESC")
            daily = utc(gold("gold_events_daily", "event_date"), "event_date")
            briefing = gold("gold_daily_briefing", "briefing_date DESC", 1)
            health = utc(gold("gold_pipeline_health"), "last_poll_at")
    except Exception as e:
        log.exception("Datahämtning misslyckades")
        st.error("Kunde inte hämta data just nu.")
        with st.expander("Teknisk detalj"):
            st.code(str(e)[:500])
        if st.button("Försök igen"):
            st.cache_data.clear()
            st.rerun()
        st.stop()

    recent = last_24h(events)
    strongest = events.loc[events["magnitude"].idxmax()] if not events.empty else None
    poll_minutes = minutes_since(health.iloc[0]["last_poll_at"]) if not health.empty else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Skalv, senaste 24 h", f"{len(recent):,}".replace(",", " "))
    c2.metric("Starkaste, 7 dagar", "–" if strongest is None else f"M {strongest['magnitude']:.1f}")
    c3.metric("Skalv, 7 dagar", f"{len(events):,}".replace(",", " "))
    c4.metric("Data senast hämtad", humanize_minutes(poll_minutes))
    if strongest is not None:
        st.caption(f"Starkaste skalvet: {strongest['place']}, {strongest['event_time']:%Y-%m-%d %H:%M} UTC.")

    t_map, t_sig, t_trend, t_platform = st.tabs(["🌍 Karta", "🔔 Betydande skalv", "📈 Trender", "🛠️ Plattformen"])
    with t_map:
        tab_map(events)
    with t_sig:
        tab_significant(significant, countries, briefing)
    with t_trend:
        tab_trends(daily)
    with t_platform:
        tab_platform(health)
    st.caption(
        f"Data: USGS Earthquake Hazards Program. Kontrollera alltid officiella källor för säkerhetsbeslut. [Källkod]({REPO_URL})"
    )


main()
