"""Kontraktstester mot det RIKTIGA USGS-API:et. Fångar att API:et ändrar beteende eller att vi bygger ogiltiga frågor.

Enhetstesterna med mockad fetch hade aldrig hittat att `updatedbefore` inte finns eller att `updatedafter` +
`includedeleted` är extremt långsamt. Det gjorde bara ett riktigt anrop. Körs med `pytest -m live` (och nattligen i CI).
"""

import time
from datetime import UTC, datetime, timedelta

import pytest

import seismo_lib as lib

pytestmark = pytest.mark.live

NOW = datetime.now(UTC)


def assert_feature_contract(feature: dict) -> None:
    """Fälten som bronze och staging förlitar sig på."""
    assert isinstance(feature["id"], str)
    props = feature["properties"]
    assert isinstance(props["updated"], int)
    assert "time" in props and "mag" in props and "place" in props
    assert len(feature["geometry"]["coordinates"]) == 3  # lon, lat, djup


def test_change_feed_accepts_our_query_and_is_fast():
    started = time.monotonic()
    features = lib.fetch_window(lib.Window(NOW - timedelta(hours=6)))
    assert time.monotonic() - started < 20, "updatedafter har blivit långsam"
    assert features, "förväntade minst en ändring senaste 6 timmarna"
    for feature in features[:20]:
        assert_feature_contract(feature)


def test_event_time_window_without_deletions_is_accepted_and_fast():
    started = time.monotonic()
    features = lib.fetch_window(lib.event_time_windows(NOW - timedelta(days=1), NOW)[0])
    assert time.monotonic() - started < 20, "event-tidsfönster har blivit långsamt"
    assert features
    assert_feature_contract(features[0])


def test_deletion_check_is_accepted_when_usgs_answers():
    """includedeleted är sporadiskt långsamt hos USGS (504 för vissa dagar), därför best effort i pipelinen.

    Testet bevisar att frågan är giltig när USGS svarar, men hoppar över när USGS är långsamt istället för att larma
    i onödan.
    """
    window = lib.plan_windows(NOW - timedelta(minutes=30), NOW)[1]
    assert window.best_effort
    try:
        assert isinstance(lib.fetch_window(window), list)
    except RuntimeError as e:
        pytest.skip(f"USGS includedeleted var långsam eller otillgänglig (känt, se ADR 0003): {str(e)[:80]}")
