from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from config import ConfigError, load_settings
from insights import (
    DEPTH_BANDS,
    depth_color,
    depth_legend_html,
    humanize_minutes,
    last_24h,
    marker_radius_m,
    minutes_since,
    sla_status,
)

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(0, "ok"), (30, "ok"), (75, "ok"), (76, "warn"), (150, "warn"), (151, "breach"), (None, "breach")],
)
def test_sla_status_thresholds(minutes, expected):
    assert sla_status(minutes) == expected


def test_minutes_since_handles_naive_aware_and_missing():
    assert minutes_since(pd.Timestamp("2026-10-15 11:30:00"), NOW) == 30.0
    assert minutes_since(pd.Timestamp("2026-10-15 13:30:00+02:00"), NOW) == 30.0
    assert minutes_since(None, NOW) is None
    assert minutes_since(pd.NaT, NOW) is None


@pytest.mark.parametrize(
    ("minutes", "text"),
    [(0.2, "nyss"), (12, "12 min sedan"), (180, "3 h sedan"), (3 * 1440, "3 dygn sedan"), (None, "okänt")],
)
def test_humanize_minutes(minutes, text):
    assert humanize_minutes(minutes) == text


def test_last_24h_filters_on_event_time():
    events = pd.DataFrame(
        {"event_id": ["new", "old"], "event_time": [NOW - timedelta(hours=2), NOW - timedelta(hours=30)]}
    )
    assert list(last_24h(events, NOW)["event_id"]) == ["new"]


def test_marker_radius_grows_with_magnitude_and_clamps_negative():
    assert marker_radius_m(6) > marker_radius_m(4) > marker_radius_m(2)
    assert marker_radius_m(-1.5) == marker_radius_m(0)


def test_depth_color_buckets():
    assert depth_color(10)[:3] == [209, 14, 97]
    assert depth_color(150)[:3] == [230, 140, 40]
    assert depth_color(500)[:3] == [21, 123, 147]
    assert depth_color(None)[:3] == [122, 122, 122]


def test_settings_defaults_and_missing():
    s = load_settings({"DATABRICKS_WAREHOUSE_ID": "w"})
    assert s.gold == "workspace.seismo_gold"
    with pytest.raises(ConfigError):
        load_settings({})


def test_legend_colors_are_exactly_the_marker_colors():
    """Legenden och kartmarkörerna ska aldrig kunna glida isär: båda läser DEPTH_BANDS."""
    html = depth_legend_html()
    for _, _, _, (r, g, b) in DEPTH_BANDS:
        assert f"rgb({r},{g},{b})" in html
    for depth in (10, 150, 500):
        assert tuple(depth_color(depth)[:3]) in {rgb for *_, rgb in DEPTH_BANDS}


def test_every_depth_maps_to_a_band_including_boundaries():
    assert depth_color(69.9)[:3] == list(DEPTH_BANDS[0][3])
    assert depth_color(70)[:3] == list(DEPTH_BANDS[1][3])
    assert depth_color(299.9)[:3] == list(DEPTH_BANDS[1][3])
    assert depth_color(300)[:3] == list(DEPTH_BANDS[2][3])
