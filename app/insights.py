"""Ren logik bakom dashboarden (tider, SLA-status, kartstorlekar), skild från Streamlit så att den går att testa."""

from datetime import UTC, datetime, timedelta

import pandas as pd

SLA_OK_MINUTES = 75  # jobbet körs varje timme
SLA_BREACH_MINUTES = 150  # två missade körningar


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
        return "unknown"
    if minutes < 1:
        return "just now"
    if minutes < 120:
        return f"{minutes:.0f} min ago"
    if minutes < 48 * 60:
        return f"{minutes / 60:.0f} h ago"
    return f"{minutes / 1440:.0f} days ago"


def last_24h(events: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    now = now or datetime.now(UTC)
    times = pd.to_datetime(events["event_time"], utc=True)
    return events[times >= pd.Timestamp(now) - timedelta(hours=24)]


def marker_radius_m(magnitude: float) -> float:
    """Radie i meter: ungefär en faktor 1,9 per magnitudsteg, så att stora skalv syns utan att dölja små."""
    return 2500 * 1.9 ** max(magnitude, 0)


# En enda källa för djupfärgerna: kartans markörer och legenden under den läser båda härifrån.
DEPTH_BANDS = (
    ("shallow", "<70 km", 70, (209, 14, 97)),
    ("mid", "70–300 km", 300, (230, 140, 40)),
    ("deep", ">300 km", None, (21, 123, 147)),
)
UNKNOWN_DEPTH_RGB = (122, 122, 122)
MARKER_ALPHA = 170


def depth_color(depth_km: float | None) -> list[int]:
    """RGBA-färg efter djup: grunda skalv (oftast de farligaste) magenta, mellan orange och djupa teal."""
    if depth_km is None or pd.isna(depth_km):
        return [*UNKNOWN_DEPTH_RGB, 150]
    for _, _, upper, rgb in DEPTH_BANDS:
        if upper is None or depth_km < upper:
            return [*rgb, MARKER_ALPHA]
    return [*DEPTH_BANDS[-1][3], MARKER_ALPHA]  # onåbart, men håller funktionen total


def depth_legend_html() -> str:
    """Legend med samma RGB-värden som markörerna, så att färgerna alltid stämmer överens."""
    items = [
        f'<span style="color: rgb({r},{g},{b}); font-size: 1.1em;">●</span> {label} ({span})'
        for label, span, _, (r, g, b) in DEPTH_BANDS
    ]
    return '<div style="color: #aaaaaa; font-size: 0.85rem;">' + "&nbsp;&nbsp;&nbsp;".join(items) + "</div>"
