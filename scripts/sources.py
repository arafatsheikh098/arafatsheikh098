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


    def get_bytes(self, url: str) -> bytes | None:
        """Binary download (screenshots), cached forever: same URL, same bytes."""
        path = CACHE / ("img-" + hashlib.sha1(url.encode()).hexdigest()[:16])
        if path.exists() and not self.refresh:
            return path.read_bytes()
        if self.offline:
            return path.read_bytes() if path.exists() else None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"  ! download failed ({e.__class__.__name__}): {url}")
            return path.read_bytes() if path.exists() else None
        path.write_bytes(data)
        return data


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
    """Per-day counts, total and streaks from the public contributions calendar."""
    page = f.get(f"https://github.com/users/{handle}/contributions", raw=True)
    if not isinstance(page, str):
        return None
    m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    total = int(m.group(1).replace(",", "")) if m else None

    cells = {}
    for td in re.findall(r"<td\b[^>]*ContributionCalendar-day[^>]*>", page):
        d = re.search(r'data-date="([\d-]+)"', td)
        lv = re.search(r'data-level="(\d)"', td)
        cid = re.search(r'\bid="([^"]+)"', td)
        if d and lv:
            cells[cid.group(1) if cid else d.group(1)] = (d.group(1), int(lv.group(1)))
    counts = {}
    for cid, text in re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        n = re.match(r"\s*(\d+|No)\s+contribution", text)
        if n:
            counts[cid] = 0 if n.group(1) == "No" else int(n.group(1))
    days = {date: {"level": lv, "count": counts.get(cid, lv)} for cid, (date, lv) in cells.items()}

    streak = longest = run = 0
    if days:
        for d in sorted(days):
            run = run + 1 if days[d]["level"] > 0 else 0
            longest = max(longest, run)
        day = max(days)
        cur = dt.date.fromisoformat(day)
        if days[day]["level"] == 0:  # today not active yet: count from yesterday
            cur -= dt.timedelta(days=1)
        while days.get(cur.isoformat(), {}).get("level", 0) > 0:
            streak += 1
            cur -= dt.timedelta(days=1)
    return {"total": total, "streak": streak, "longest": longest, "days": days}


def github_events(f: Fetcher, handle: str) -> list[dict] | None:
    """Recent public activity, condensed into human-readable lines."""
    events = f.get(f"https://api.github.com/users/{handle}/events/public?per_page=100")
    if not isinstance(events, list):
        return None
    out: list[dict] = []
    for e in events:
        repo = e["repo"]["name"].split("/", 1)[-1]
        day = e["created_at"][:10]
        pl = e.get("payload") or {}
        t = e["type"]
        if t == "PushEvent":
            n = pl.get("size") or len(pl.get("commits") or []) or 1
            last = out[-1] if out else None
            if last and last["kind"] == "push" and last["repo"] == repo and last["day"] == day:
                last["n"] += n
                continue
            out.append({"kind": "push", "repo": repo, "day": day, "n": n})
        elif t == "CreateEvent" and pl.get("ref_type") == "repository":
            out.append({"kind": "create", "repo": repo, "day": day})
        elif t == "CreateEvent" and pl.get("ref_type") == "tag":
            out.append({"kind": "tag", "repo": repo, "day": day, "ref": pl.get("ref")})
        elif t == "ReleaseEvent":
            out.append({"kind": "release", "repo": repo, "day": day,
                        "ref": (pl.get("release") or {}).get("tag_name")})
        elif t == "PullRequestEvent" and pl.get("action") in ("opened", "closed"):
            merged = (pl.get("pull_request") or {}).get("merged")
            kind = "merged" if merged else ("pr" if pl["action"] == "opened" else None)
            if kind:
                out.append({"kind": kind, "repo": repo, "day": day, "num": pl.get("number")})
        elif t == "IssuesEvent" and pl.get("action") == "opened":
            out.append({"kind": "issue", "repo": repo, "day": day, "num": (pl.get("issue") or {}).get("number")})
        elif t == "WatchEvent":
            out.append({"kind": "star", "repo": e["repo"]["name"], "day": day})
        elif t == "PublicEvent":
            out.append({"kind": "public", "repo": repo, "day": day})
    return out


def repo_traffic(handle: str, repos: list[str], store: Path) -> dict[str, dict]:
    """Views per repo, accumulated in `store` beyond GitHub's 14-day window.

    Needs TRAFFIC_TOKEN (a token with push/admin read access to the repos);
    without it, returns whatever was stored before (possibly nothing).
    """
    data = json.loads(store.read_text()) if store.exists() else {}
    token = os.environ.get("TRAFFIC_TOKEN")
    if token:
        for name in repos:
            url = f"https://api.github.com/repos/{handle}/{name}/traffic/views"
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = json.loads(r.read())
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
                print(f"  ! traffic failed for {name}: {e}")
                continue
            daily = data.setdefault(name, {})
            for v in body.get("views", []):
                daily[v["timestamp"][:10]] = {"count": v["count"], "uniques": v["uniques"]}
        store.parent.mkdir(exist_ok=True)
        store.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    result = {}
    cutoff = (dt.date.today() - dt.timedelta(days=14)).isoformat()
    for name, daily in data.items():
        result[name] = {
            "total": sum(d["count"] for d in daily.values()),
            "recent": sum(d["count"] for k, d in daily.items() if k >= cutoff),
            "since": min(daily) if daily else None,
        }
    return result


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
