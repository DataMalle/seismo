from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from config import ConfigError, load_settings
from insights import depth_color, humanize_minutes, last_24h, marker_radius_m, minutes_since, sla_status

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(0, "ok"), (30, "ok"), (45, "ok"), (46, "warn"), (90, "warn"), (91, "breach"), (None, "breach")],
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
