"""Ren Python för USGS-extraktion: fönsterplanering, URL:er, dedupe och NDJSON.

Inga Spark-beroenden, så att logiken kan enhetstestas lokalt och återanvändas i notebooks och backfill.

Varför FDSN `updatedafter` och inte live-feeden? Live-feeden (`all_hour`) innehåller händelser efter *händelsetid*.
Om USGS reviderar ett skalv från igår syns ändringen aldrig där. FDSN-frågan `updatedafter` är den riktiga
ändringsfeeden (inklusive revideringar och raderingar), så den används för all inkrementell extraktion.
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

FDSN_BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"
PAGE_LIMIT = 20000  # USGS maxgräns per anrop
OVERLAP = timedelta(minutes=10)  # hämta lite bakåt så att sena uppdateringar inte missas (dedupe tar bort dubbletter)
DEFAULT_CHUNK = timedelta(days=1)  # största fönster per anrop vid längre luckor, håller resultatet under PAGE_LIMIT


@dataclass(frozen=True)
class Window:
    """Ett tidsfönster av *uppdateringstid* som hämtas i ett (eventuellt paginerat) anrop."""

    updated_after: datetime
    updated_before: datetime


def utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def plan_windows(
    watermark: datetime | None,
    now: datetime,
    *,
    bootstrap_days: int = 7,
    chunk: timedelta = DEFAULT_CHUNK,
) -> list[Window]:
    """Delar upp det som saknas i fönster. Ingen watermark betyder första körningen (bootstrap)."""
    start = now - timedelta(days=bootstrap_days) if watermark is None else watermark - OVERLAP
    return list(split_range(start, now, chunk))


def split_range(start: datetime, end: datetime, chunk: timedelta) -> Iterator[Window]:
    if start >= end:
        return
    cursor = start
    while cursor < end:
        upper = min(cursor + chunk, end)
        yield Window(cursor, upper)
        cursor = upper


def build_url(window: Window, *, offset: int = 1, limit: int = PAGE_LIMIT) -> str:
    params = {
        "format": "geojson",
        "updatedafter": window.updated_after.strftime("%Y-%m-%dT%H:%M:%S"),
        "updatedbefore": window.updated_before.strftime("%Y-%m-%dT%H:%M:%S"),
        "includedeleted": "true",  # raderingar propageras som ändringar istället för att tyst försvinna
        "orderby": "time-asc",
        "limit": limit,
        "offset": offset,
    }
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


def fetch_window(window: Window, fetch=fetch_json) -> list[dict]:
    """Alla features i ett fönster, med paginering när resultatet fyller en hel sida."""
    features: list[dict] = []
    offset = 1
    while True:
        page = fetch(build_url(window, offset=offset)).get("features", [])
        features.extend(page)
        if len(page) < PAGE_LIMIT:
            return features
        offset += PAGE_LIMIT


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
