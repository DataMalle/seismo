"""Ren logik bakom dashboarden (tider, SLA-status, kartstorlekar), skild från Streamlit så att den går att testa."""

from datetime import UTC, datetime, timedelta

import pandas as pd

SLA_OK_MINUTES = 45  # jobbet körs var 30:e minut
SLA_BREACH_MINUTES = 90


def minutes_since(ts: pd.Timestamp | datetime | None, now: datetime | None = None) -> float | None:
    if ts is None or pd.isna(ts):
        return None
    now = now or datetime.now(UTC)
    stamp = pd.Timestamp(ts)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return (pd.Timestamp(now) - stamp).total_seconds() / 60


def sla_status(minutes: float | None) -> str:
    """ok / warn / breach utifrån hur länge sedan pipelinen senast körde."""
    if minutes is None or minutes > SLA_BREACH_MINUTES:
        return "breach"
    return "ok" if minutes <= SLA_OK_MINUTES else "warn"


def humanize_minutes(minutes: float | None) -> str:
    if minutes is None:
        return "okänt"
    if minutes < 1:
        return "nyss"
    if minutes < 120:
        return f"{minutes:.0f} min sedan"
    if minutes < 48 * 60:
        return f"{minutes / 60:.0f} h sedan"
    return f"{minutes / 1440:.0f} dygn sedan"


def last_24h(events: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    now = now or datetime.now(UTC)
    times = pd.to_datetime(events["event_time"], utc=True)
    return events[times >= pd.Timestamp(now) - timedelta(hours=24)]


def marker_radius_m(magnitude: float) -> float:
    """Radie i meter: ungefär en faktor 1,9 per magnitudsteg, så att stora skalv syns utan att dölja små."""
    return 2500 * 1.9 ** max(magnitude, 0)


def depth_color(depth_km: float | None) -> list[int]:
    """Grund (röd/magenta) till djup (teal). Grunda skalv är oftast de farligaste."""
    if depth_km is None or pd.isna(depth_km):
        return [122, 122, 122, 150]
    if depth_km < 70:
        return [209, 14, 97, 170]
    if depth_km < 300:
        return [230, 140, 40, 170]
    return [21, 123, 147, 170]
