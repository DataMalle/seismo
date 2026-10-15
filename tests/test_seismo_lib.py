import itertools
import json
from datetime import UTC, datetime, timedelta

import pytest

import seismo_lib as lib

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def feat(event_id: str, updated_ms: int) -> dict:
    return {"id": event_id, "properties": {"updated": updated_ms, "mag": 2.5}, "geometry": {"coordinates": [0, 0, 5]}}


# --- fönsterplanering ---


def test_bootstrap_without_watermark_covers_bootstrap_days_in_day_chunks():
    windows = lib.plan_windows(None, NOW, bootstrap_days=3)
    assert len(windows) == 3
    assert windows[0].updated_after == NOW - timedelta(days=3)
    assert windows[-1].updated_before == NOW


def test_incremental_starts_at_watermark_minus_overlap():
    wm = NOW - timedelta(minutes=20)
    windows = lib.plan_windows(wm, NOW)
    assert len(windows) == 1
    assert windows[0].updated_after == wm - lib.OVERLAP


def test_long_gap_is_chunked_and_contiguous():
    wm = NOW - timedelta(days=5)
    windows = lib.plan_windows(wm, NOW)
    assert len(windows) >= 5
    for earlier, later in itertools.pairwise(windows):
        assert earlier.updated_before == later.updated_after  # inga luckor mellan fönstren
    assert windows[-1].updated_before == NOW


def test_no_windows_when_watermark_is_in_the_future():
    assert lib.plan_windows(NOW + timedelta(hours=1), NOW) == []


# --- URL ---


def test_build_url_requests_change_feed_with_deletions():
    url = lib.build_url(lib.Window(NOW - timedelta(hours=1), NOW))
    assert "updatedafter=2026-10-15T11%3A00%3A00" in url
    assert "includedeleted=true" in url and "format=geojson" in url and "offset=1" in url


# --- paginering och dedupe ---


def test_fetch_window_paginates_until_a_short_page(monkeypatch):
    monkeypatch.setattr(lib, "PAGE_LIMIT", 2)
    pages = {1: [feat("a", 1), feat("b", 2)], 3: [feat("c", 3)]}
    seen_offsets = []

    def fake_fetch(url):
        offset = int(url.split("offset=")[1].split("&")[0])
        seen_offsets.append(offset)
        return {"features": pages[offset]}

    out = lib.fetch_window(lib.Window(NOW - timedelta(days=1), NOW), fetch=fake_fetch)
    assert [f["id"] for f in out] == ["a", "b", "c"]
    assert seen_offsets == [1, 3]


def test_drop_known_removes_existing_versions_but_keeps_new_revisions():
    known = {("a", 100)}
    incoming = [feat("a", 100), feat("a", 200), feat("b", 150), feat("b", 150)]
    fresh = lib.drop_known(incoming, known)
    assert [(f["id"], f["properties"]["updated"]) for f in fresh] == [("a", 200), ("b", 150)]


def test_max_updated_and_empty():
    assert lib.max_updated([feat("a", 1000), feat("b", 5000)]) == lib.utc(5000)
    assert lib.max_updated([]) is None


# --- NDJSON och filnamn ---


def test_ndjson_is_one_compact_json_object_per_line_and_lossless():
    features = [feat("a", 1), feat("b", 2)]
    text = lib.to_ndjson(features)
    lines = text.splitlines()
    assert len(lines) == 2 and text.endswith("\n")
    assert [json.loads(line) for line in lines] == features


def test_landing_filename_and_schema_prefix():
    assert lib.landing_filename(NOW) == "usgs_fdsn_20261015T120000.ndjson"
    assert lib.schema_prefix("prod") == "seismo"
    assert lib.schema_prefix("dev") == "seismo_dev"


@pytest.mark.parametrize("ms", [0, 1_700_000_000_000])
def test_ms_roundtrip(ms):
    assert lib.to_ms(lib.utc(ms)) == ms
