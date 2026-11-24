"""Live data from GitHub and Codeforces, with a small on-disk cache.

The cache (.cache/, gitignored) keeps local rebuilds fast and within the
unauthenticated GitHub rate limit; in CI the GITHUB_TOKEN raises that limit.
Every fetch returns None on failure so the build can keep the previous asset.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / ".cache"
UA = "profile-readme-builder"


class Fetcher:
    def __init__(self, ttl: int = 6 * 3600, offline: bool = False, refresh: bool = False):
        self.ttl = ttl
        self.offline = offline
        self.refresh = refresh
        self.token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        CACHE.mkdir(exist_ok=True)

    def _path(self, url: str) -> Path:
        return CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")

    def get(self, url: str, raw: bool = False):
        path = self._path(url)
        cached = None
        if path.exists():
            cached = json.loads(path.read_text())
            fresh = time.time() - cached["t"] < self.ttl
            if self.offline or (fresh and not self.refresh):
                return cached["body"]
        if self.offline:
            return None
        headers = {"User-Agent": UA}
        if "api.github.com" in url:
            headers["Accept"] = "application/vnd.github+json"
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                text = r.read().decode("utf-8", "replace")
            body = text if raw else json.loads(text)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            print(f"  ! fetch failed ({e.__class__.__name__}): {url}")
            return cached["body"] if cached else None
        path.write_text(json.dumps({"t": time.time(), "url": url, "body": body}))
        return body


# ── GitHub ──────────────────────────────────────────────────────────────────

def github_repos(f: Fetcher, handle: str) -> list[dict] | None:
    repos = f.get(f"https://api.github.com/users/{handle}/repos?per_page=100&type=owner")
    if not isinstance(repos, list):
        return None
    return [r for r in repos if not r.get("fork") and r["name"].lower() != handle.lower()]


def github_languages(f: Fetcher, handle: str, repos: list[dict], ignore: set[str]) -> list[tuple[str, float]]:
    totals: dict[str, int] = {}
    for r in repos:
        data = f.get(f"https://api.github.com/repos/{handle}/{r['name']}/languages")
        if not isinstance(data, dict) or "message" in data:
            # Rate-limited or missing: fall back to the primary language.
            if r.get("language"):
                totals[r["language"]] = totals.get(r["language"], 0) + 50_000
            continue
        for lang, n in data.items():
            if lang not in ignore:
                totals[lang] = totals.get(lang, 0) + n
    s = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    top = [(k, v * 100 / s) for k, v in ranked[:5]]
    rest = 100 - sum(p for _, p in top)
    if rest >= 0.5:
        top.append(("Other", rest))
    return top


def github_contributions(f: Fetcher, handle: str) -> dict | None:
    """Total + streak from the public contributions calendar."""
    page = f.get(f"https://github.com/users/{handle}/contributions", raw=True)
    if not isinstance(page, str):
        return None
    m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    total = int(m.group(1).replace(",", "")) if m else None
    days = {d: int(l) for d, l in re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*?data-level="(\d)"', page)}
    if not days:
        days = {d: int(l) for l, d in re.findall(r'data-level="(\d)"[^>]*?data-date="(\d{4}-\d{2}-\d{2})"', page)}
    streak = longest = run = 0
    if days:
        for d in sorted(days):
            run = run + 1 if days[d] > 0 else 0
            longest = max(longest, run)
        day = max(days)
        cur = dt.date.fromisoformat(day)
        if days.get(day, 0) == 0:  # today not active yet: count from yesterday
            cur -= dt.timedelta(days=1)
        while days.get(cur.isoformat(), 0) > 0:
            streak += 1
            cur -= dt.timedelta(days=1)
    return {"total": total, "streak": streak, "longest": longest}


# ── Codeforces ──────────────────────────────────────────────────────────────

def _cf(f: Fetcher, method: str):
    data = f.get(f"https://codeforces.com/api/{method}")
    if isinstance(data, dict) and data.get("status") == "OK":
        return data["result"]
    return None


def codeforces(f: Fetcher, handle: str) -> dict | None:
    info = _cf(f, f"user.info?handles={handle}")
    if not info:
        return None
    history = _cf(f, f"user.rating?handle={handle}") or []
    subs = _cf(f, f"user.status?handle={handle}")
    solved = None
    if subs is not None:
        solved = len({(s["problem"].get("contestId"), s["problem"].get("index"))
                      for s in subs if s.get("verdict") == "OK"})
    return {"info": info[0], "history": history, "solved": solved}
