import base64
import json
import urllib.error
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

import github_publish as gh
import seismo_snapshots as snap

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


# --- jsonable och build_files ---


def test_jsonable_converts_spark_types_to_json_safe_values():
    assert snap.jsonable(datetime(2026, 10, 15, 12, 0, 5)) == "2026-10-15T12:00:05Z"  # naiv tid tolkas som UTC
    assert snap.jsonable(datetime(2026, 10, 15, 14, 0, tzinfo=timezone(timedelta(hours=2)))) == "2026-10-15T12:00:00Z"
    assert snap.jsonable(date(2026, 10, 15)) == "2026-10-15"
    assert snap.jsonable(Decimal("1.50")) == 1.5
    assert snap.jsonable(float("nan")) is None and snap.jsonable(float("inf")) is None
    assert snap.jsonable(None) is None and snap.jsonable("x") == "x" and snap.jsonable(3) == 3


def test_build_files_has_one_file_per_snapshot_plus_a_manifest_with_hashes():
    frames = {"countries": [{"country": "Chile", "events_30d": 12}], "daily": []}
    files = snap.build_files(frames, NOW)
    assert set(files) == {"countries.json", "daily.json", "manifest.json"}
    payload = json.loads(files["countries.json"])
    assert payload == {
        "schema_version": snap.SCHEMA_VERSION,
        "generated_at": "2026-10-15T12:00:00Z",
        "rows": [{"country": "Chile", "events_30d": 12}],
    }
    manifest = json.loads(files["manifest.json"])
    assert manifest["files"]["countries.json"]["rows"] == 1 and manifest["files"]["daily.json"]["rows"] == 0
    import hashlib

    assert manifest["files"]["countries.json"]["sha256"] == hashlib.sha256(files["countries.json"]).hexdigest()


def test_swedish_characters_survive_unescaped():
    files = snap.build_files({"briefing": [{"briefing": "Jordbävning i Nya Zeeland"}]}, NOW)
    assert "Jordbävning".encode() in files["briefing.json"]


def test_every_gold_snapshot_has_a_table_and_a_valid_ordering():
    assert set(snap.SNAPSHOTS) == {"event_map", "significant_events", "countries", "daily", "briefing", "health"}
    assert all(table.startswith("gold_") for table, _, _ in snap.SNAPSHOTS.values())


# --- GitHub-publicering ---


class FakeHttp:
    def __init__(self, patch_error: int | None = None):
        self.calls: list[tuple[str, str, dict | None]] = []
        self.patch_error = patch_error

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith("/git/blobs"):
            return {"sha": f"blob{len(self.calls)}"}
        if path.endswith("/git/trees"):
            return {"sha": "tree1"}
        if path.endswith("/git/commits"):
            return {"sha": "commit1"}
        if method == "PATCH" and self.patch_error:
            raise urllib.error.HTTPError("u", self.patch_error, "err", {}, None)
        return {}


def test_publish_creates_one_parentless_commit_and_force_updates_the_branch():
    http = FakeHttp()
    sha = gh.publish({"a.json": b"[1]", "b.json": b"[2]"}, repo="o/r", branch="data", message="m", http=http)
    assert sha == "commit1"
    methods_paths = [(m, p) for m, p, _ in http.calls]
    assert methods_paths == [
        ("POST", "/repos/o/r/git/blobs"),
        ("POST", "/repos/o/r/git/blobs"),
        ("POST", "/repos/o/r/git/trees"),
        ("POST", "/repos/o/r/git/commits"),
        ("PATCH", "/repos/o/r/git/refs/heads/data"),
    ]
    commit_body = next(b for m, p, b in http.calls if p.endswith("/git/commits"))
    assert commit_body["parents"] == []  # ingen historik: grenen innehåller alltid ett enda commit
    assert http.calls[-1][2] == {"sha": "commit1", "force": True}


def test_publish_encodes_content_as_base64_and_places_files_in_the_directory():
    http = FakeHttp()
    gh.publish({"x.json": "åäö".encode()}, repo="o/r", branch="data", message="m", http=http, directory="snapshots")
    blob_body = http.calls[0][2]
    assert base64.b64decode(blob_body["content"]).decode() == "åäö" and blob_body["encoding"] == "base64"
    tree_body = next(b for m, p, b in http.calls if p.endswith("/git/trees"))
    assert tree_body["tree"][0]["path"] == "snapshots/x.json"
    assert "base_tree" not in tree_body  # annars skulle gamla filer följa med


@pytest.mark.parametrize("code", [404, 422])
def test_publish_creates_the_branch_when_it_does_not_exist_yet(code):
    http = FakeHttp(patch_error=code)
    gh.publish({"a.json": b"1"}, repo="o/r", branch="data", message="m", http=http)
    assert http.calls[-1] == ("POST", "/repos/o/r/git/refs", {"ref": "refs/heads/data", "sha": "commit1"})


def test_publish_does_not_swallow_other_errors():
    http = FakeHttp(patch_error=403)
    with pytest.raises(urllib.error.HTTPError):
        gh.publish({"a.json": b"1"}, repo="o/r", branch="data", message="m", http=http)
