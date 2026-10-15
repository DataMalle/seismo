import itertools
import json
from datetime import UTC, datetime, timedelta

import pytest

import seismo_lib as lib

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def feat(event_id: str, updated_ms: int) -> dict:
    return {"id": event_id, "properties": {"updated": updated_ms, "mag": 2.5}, "geometry": {"coordinates": [0, 0, 5]}}


# --- fönsterplanering ---


def test_bootstrap_uses_reliable_daily_windows_plus_best_effort_deletion_checks():
    windows = lib.plan_windows(None, NOW, bootstrap_days=3)
    main = [w for w in windows if not w.best_effort]
    checks = [w for w in windows if w.best_effort]
    assert len(main) == 3 and all(w.by == "event_time" and not w.include_deleted for w in main)
    assert len(checks) == 3 and all(w.include_deleted and w.deleted_only for w in checks)
    assert main[0].start == NOW - timedelta(days=3) and main[-1].end == NOW


def test_incremental_is_one_required_updatedafter_call_plus_one_best_effort_deletion_check():
    wm = NOW - timedelta(minutes=20)
    changes, deletions = lib.plan_windows(wm, NOW)
    assert (changes.by, changes.start, changes.end) == ("updated", wm - lib.OVERLAP, None)
    assert not changes.include_deleted and not changes.best_effort  # huvudhämtningen får aldrig vara flaksig
    assert (
        deletions.by == "event_time" and deletions.include_deleted and deletions.deleted_only and deletions.best_effort
    )
    assert deletions.start == NOW - lib.DELETION_LOOKBACK and deletions.end == NOW


def test_deletion_check_covers_the_whole_gap_after_a_long_outage():
    wm = NOW - timedelta(days=10)
    _, deletions = lib.plan_windows(wm, NOW)
    assert deletions.start == wm - lib.OVERLAP  # bakåt till luckans början, inte bara tre dagar


def test_event_time_windows_are_contiguous():
    windows = lib.event_time_windows(NOW - timedelta(days=5), NOW)
    assert len(windows) == 5
    for earlier, later in itertools.pairwise(windows):
        assert earlier.end == later.start  # inga luckor mellan fönstren
    assert windows[-1].end == NOW


def test_event_time_windows_empty_when_start_is_not_before_end():
    assert lib.event_time_windows(NOW, NOW) == []
    assert lib.event_time_windows(NOW + timedelta(hours=1), NOW) == []


# --- URL ---


def test_changes_url_uses_updatedafter_and_never_the_slow_or_invalid_parameters():
    url = lib.build_url(lib.Window(NOW - timedelta(hours=1)))
    assert "updatedafter=2026-10-15T11%3A00%3A00" in url
    assert "updatedbefore" not in url  # finns inte hos USGS (HTTP 400)
    assert "includedeleted" not in url  # updatedafter + includedeleted är extremt långsamt
    assert "format=geojson" in url and "offset=1" in url


def test_main_event_time_url_never_asks_for_deleted_events():
    url = lib.build_url(lib.event_time_windows(NOW - timedelta(days=1), NOW)[0])
    assert "starttime=2026-10-14T12%3A00%3A00" in url and "endtime=2026-10-15T12%3A00%3A00" in url
    assert "includedeleted" not in url and "updatedafter" not in url  # opålitligt hos USGS (504), se ADR 0003


def test_deletion_check_url_asks_for_deleted_events():
    url = lib.build_url(lib.deletion_windows(NOW - timedelta(days=3), NOW)[0])
    assert "includedeleted=true" in url and "starttime=" in url


# --- paginering och dedupe ---


def test_fetch_window_paginates_until_a_short_page(monkeypatch):
    monkeypatch.setattr(lib, "PAGE_LIMIT", 2)
    pages = {1: [feat("a", 1), feat("b", 2)], 3: [feat("c", 3)]}
    seen_offsets = []

    def fake_fetch(url):
        offset = int(url.split("offset=")[1].split("&")[0])
        seen_offsets.append(offset)
        return {"features": pages[offset]}

    out = lib.fetch_window(lib.Window(NOW - timedelta(days=1)), fetch=fake_fetch)
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


def test_best_effort_windows_use_the_fast_fetch_and_required_ones_do_not(monkeypatch):
    used = []
    monkeypatch.setattr(lib, "fetch_json_fast", lambda url: used.append("fast") or {"features": []})
    monkeypatch.setattr(lib, "fetch_json", lambda url, **kw: used.append("normal") or {"features": []})
    lib.fetch_window(lib.Window(NOW - timedelta(days=1)))
    lib.fetch_window(lib.deletion_windows(NOW - timedelta(days=1), NOW)[0])
    assert used == ["normal", "fast"]


def test_fetch_json_fast_is_a_single_short_attempt(monkeypatch):
    seen = {}
    monkeypatch.setattr(lib, "fetch_json", lambda url, **kw: seen.update(kw) or {"features": []})
    lib.fetch_json_fast("http://x")
    assert seen == {"retries": 1, "timeout": 25}


def test_deleted_only_window_keeps_only_deleted_features():
    window = lib.Window(NOW - timedelta(days=3), NOW, "event_time", include_deleted=True, deleted_only=True)
    gone = feat("gone", 2) | {"properties": {"updated": 2, "status": "deleted"}}
    kept = feat("kept", 1) | {"properties": {"updated": 1, "status": "reviewed"}}
    out = lib.fetch_window(window, fetch=lambda url: {"features": [kept, gone]})
    assert [f["id"] for f in out] == ["gone"]
