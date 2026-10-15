"""Ren Python för USGS-extraktion: fönsterplanering, URL:er, dedupe och NDJSON.

Inga Spark-beroenden, så att logiken kan enhetstestas lokalt och återanvändas i notebooks och backfill.

Hur USGS-API:et faktiskt beter sig (verifierat mot live-API:et, se ADR 0003):
- Live-feeden (`all_hour`) innehåller händelser efter *händelsetid*. Revideras ett skalv från igår syns det aldrig där.
  FDSN `updatedafter` är den riktiga ändringsfeeden och används därför för inkrementell extraktion.
- `updatedbefore` finns inte (HTTP 400), så fönster av uppdateringstid kan inte avgränsas uppåt.
- `includedeleted=true` är opålitligt: med `updatedafter` alltid extremt långsamt (54 s till timeout), med
  `starttime`/`endtime` sporadiskt långsamt (504 efter 60 s för vissa dagar, 1 s för andra). Huvudhämtningen använder
  det därför aldrig. Raderingar stäms av i ett separat *best effort*-anrop med kort timeout, vars fel loggas
  men inte fäller körningen.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

FDSN_BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"
PAGE_LIMIT = 20000  # USGS maxgräns per anrop
OVERLAP = timedelta(minutes=10)  # hämta lite bakåt så att sena uppdateringar inte missas (dedupe tar bort dubbletter)
DEFAULT_CHUNK = timedelta(days=1)  # största fönster per anrop vid längre luckor, håller resultatet under PAGE_LIMIT


DELETION_LOOKBACK = timedelta(days=3)  # så långt bakåt avstäms raderingar vid varje körning
DELETION_CHUNK = timedelta(days=3650)  # ett enda anrop för hela avstämningsintervallet i den inkrementella körningen


@dataclass(frozen=True)
class Window:
    """Ett anrop mot USGS. `by` avgör om start/end avser uppdateringstid eller händelsetid."""

    start: datetime
    end: datetime | None = None  # None = öppet slut (bara tillåtet för updated)
    by: Literal["updated", "event_time"] = "updated"
    include_deleted: bool = False
    deleted_only: bool = False  # behåll bara raderade features (avstämning av raderingar)
    best_effort: bool = False  # kort timeout, ett försök, och fel fäller inte körningen


def utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def event_time_windows(start: datetime, end: datetime, chunk: timedelta = DEFAULT_CHUNK) -> list[Window]:
    """Dagsfönster av händelsetid utan includedeleted. Snabba och pålitliga, och används vid bootstrap och backfill."""
    return [Window(w_start, w_end, "event_time") for w_start, w_end in split_range(start, end, chunk)]


def deletion_windows(start: datetime, end: datetime, chunk: timedelta = DELETION_CHUNK) -> list[Window]:
    """Best effort-avstämning av raderingar: bara features med status deleted behålls."""
    return [
        Window(w_start, w_end, "event_time", include_deleted=True, deleted_only=True, best_effort=True)
        for w_start, w_end in split_range(start, end, chunk)
    ]


def plan_windows(
    watermark: datetime | None,
    now: datetime,
    *,
    bootstrap_days: int = 7,
    deletion_lookback: timedelta = DELETION_LOOKBACK,
) -> list[Window]:
    """Vad som ska hämtas nu.

    Första körningen (ingen watermark): dagsfönster bakåt i tiden, plus best effort-avstämning av raderingar per dag.
    Därefter ett enda `updatedafter`-anrop från watermark (nya och reviderade händelser) och ett best effort-fönster
    för raderingar.
    """
    if watermark is None:
        start = now - timedelta(days=bootstrap_days)
        return [*event_time_windows(start, now), *deletion_windows(start, now, DEFAULT_CHUNK)]
    since = watermark - OVERLAP
    return [Window(since, None, "updated"), *deletion_windows(min(now - deletion_lookback, since), now)]


def split_range(start: datetime, end: datetime, chunk: timedelta) -> Iterator[tuple[datetime, datetime]]:
    cursor = start
    while cursor < end:
        upper = min(cursor + chunk, end)
        yield cursor, upper
        cursor = upper


def build_url(window: Window, *, offset: int = 1, limit: int = PAGE_LIMIT) -> str:
    params: dict[str, str | int] = {"format": "geojson"}
    fmt = "%Y-%m-%dT%H:%M:%S"
    if window.by == "updated":
        params["updatedafter"] = window.start.strftime(fmt)
    else:
        params["starttime"] = window.start.strftime(fmt)
        if window.end is not None:
            params["endtime"] = window.end.strftime(fmt)
    if window.include_deleted:
        params["includedeleted"] = "true"  # raderingar propageras som ändringar istället för att tyst försvinna
    params.update({"orderby": "time-asc", "limit": limit, "offset": offset})
    return f"{FDSN_BASE}?{urllib.parse.urlencode(params)}"


def fetch_json(url: str, *, retries: int = 3, timeout: int = 60) -> dict:
    """Hämtar JSON med exponentiell backoff. 204 (inga resultat) tolkas som tom FeatureCollection."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "seismo-portfolio/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return json.loads(body) if body else {"features": []}
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return {"features": []}
            last = e
        except Exception as e:
            last = e
        time.sleep(2**attempt)
    raise RuntimeError(f"Kunde inte hämta {url}: {last}")


def fetch_json_fast(url: str) -> dict:
    """För best effort-anrop: ett försök och kort timeout, så att ett flaksigt USGS-svar aldrig tar minuter."""
    return fetch_json(url, retries=1, timeout=25)


def fetch_window(window: Window, fetch=None) -> list[dict]:
    """Alla features i ett fönster, med paginering när resultatet fyller en hel sida."""
    fetch = fetch or (fetch_json_fast if window.best_effort else fetch_json)
    features: list[dict] = []
    offset = 1
    while True:
        page = fetch(build_url(window, offset=offset)).get("features", [])
        features.extend(page)
        if len(page) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
    if window.deleted_only:
        features = [f for f in features if f.get("properties", {}).get("status") == "deleted"]
    return features


def feature_key(feature: dict) -> tuple[str, int]:
    return feature["id"], int(feature["properties"]["updated"])


def drop_known(features: Iterable[dict], known: set[tuple[str, int]]) -> list[dict]:
    """Tar bort versioner som redan finns i bronze, så att omkörningar inte skriver dubbletter."""
    seen: set[tuple[str, int]] = set()
    fresh = []
    for f in features:
        key = feature_key(f)
        if key in known or key in seen:
            continue
        seen.add(key)
        fresh.append(f)
    return fresh


def max_updated(features: Iterable[dict]) -> datetime | None:
    values = [int(f["properties"]["updated"]) for f in features]
    return utc(max(values)) if values else None


def to_ndjson(features: Iterable[dict]) -> str:
    """En feature per rad. Råpayloaden bevaras oförändrad (schema-on-read i silver)."""
    return "".join(json.dumps(f, separators=(",", ":"), ensure_ascii=False) + "\n" for f in features)


def landing_filename(now: datetime, kind: str = "fdsn") -> str:
    return f"usgs_{kind}_{now:%Y%m%dT%H%M%S}.ndjson"


def schema_prefix(env: str) -> str:
    """prod -> seismo, annars seismo_<env>. Samma konvention som dbt-projektet."""
    return "seismo" if env == "prod" else f"seismo_{env}"
