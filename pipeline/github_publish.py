"""Publicerar filer till en gren på GitHub med Git Data API: ett enda commit per publicering, utan historik.

Varför Git Data API och inte Contents API: Contents API gör ett commit per fil (sex commits per timme). Här skapas
alla filer som *ett* commit utan förälder och grenen skrivs över med force. Då förblir repot litet (en gren med ett
enda commit) och React-sidan ser alltid en konsistent uppsättning filer, aldrig hälften nytt och hälften gammalt.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from collections.abc import Callable

API = "https://api.github.com"
Http = Callable[[str, str, dict | None], dict]


def github_request(token: str) -> Http:
    """HTTP-klient mot GitHub API. Returnerar tolkad JSON och kastar HTTPError vid fel."""

    def call(method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            f"{API}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "seismo-publisher/1.0",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"{}")

    return call


def publish(
    files: dict[str, bytes],
    *,
    repo: str,
    branch: str,
    message: str,
    http: Http,
    directory: str = "snapshots",
) -> str:
    """Skriver alla filer som ett enda commit på `branch` och returnerar commitets sha."""
    tree = []
    for name, content in sorted(files.items()):
        blob = http(
            "POST", f"/repos/{repo}/git/blobs", {"content": base64.b64encode(content).decode(), "encoding": "base64"}
        )
        tree.append({"path": f"{directory}/{name}", "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = http(
        "POST", f"/repos/{repo}/git/trees", {"tree": tree}
    )  # utan base_tree: bara dessa filer finns på grenen
    commit = http("POST", f"/repos/{repo}/git/commits", {"message": message, "tree": new_tree["sha"], "parents": []})
    try:
        http("PATCH", f"/repos/{repo}/git/refs/heads/{branch}", {"sha": commit["sha"], "force": True})
    except urllib.error.HTTPError as e:
        if e.code not in (404, 422):  # grenen finns inte än: skapa den
            raise
        http("POST", f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
    return commit["sha"]
