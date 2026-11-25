#!/usr/bin/env python3
"""Build README.md and assets/*.svg from profile.yml plus live data.

    python scripts/build.py            # fetch (cached 6h) and build
    python scripts/build.py --refresh  # ignore the cache
    python scripts/build.py --offline  # cache only, no network
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shots  # noqa: E402
import sources  # noqa: E402
import svg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
MODES = ("dark", "light")

NAV = [("About", "◆", "about-me"), ("Projects", "▣", "featured-projects"),
       ("Activity", "▦", "activity"), ("Stats", "▲", "live-stats"), ("Contact", "✦", "get-in-touch")]

SHOWCASE_VIEWPORT = (452, 244)   # svg.showcase_card browser viewport
GALLERY_VIEWPORT = (300, 148)    # svg.gallery_card browser viewport


def load_shots(f, handle: str, repo: str, paths: list[str], size: tuple[int, int]) -> list[str]:
    out = []
    for path in paths or []:
        if path.startswith("./"):  # a file kept in this profile repo (for repos without screenshots)
            local = ROOT / path[2:]
            data = local.read_bytes() if local.is_file() else None
        else:
            data = f.get_bytes(f"https://raw.githubusercontent.com/{handle}/{repo}/HEAD/{path.lstrip('/')}")
        uri = shots.fit(data, *size) if data else None
        if uri:
            out.append(uri)
        else:
            print(f"  ! screenshot unavailable: {repo}/{path}")
    return out


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def picture(base: str, alt: str, width: str | None = None) -> str:
    """<picture> that swaps dark/light SVGs to match the viewer's theme."""
    w = f' width="{width}"' if width else ""
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{base}-dark.svg">'
            f'<img src="{base}-light.svg" alt="{svg.esc(alt)}"{w}></picture>')


class _Blank(dict):
    def __missing__(self, key):
        return ""


def fill(text: str, ctx: dict) -> str:
    """Fill {placeholders} per " · " segment; segments with an empty value are dropped."""
    parts = []
    for seg in (text or "").split(" · "):
        keys = re.findall(r"\{(\w+)\}", seg)
        if any(str(ctx.get(k, "")).strip() == "" for k in keys):
            continue
        parts.append(seg.format_map(_Blank(ctx)).strip())
    return " · ".join(p for p in parts if p)


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    cut = cut[:cut.rfind(" ")] if " " in cut else cut
    return cut.rstrip(" ·,;:-") + "…"


def build_sidebar(cfg: dict, repos, by_name, cf, contrib, user) -> dict:
    """Resolve the sidebar block (bio placeholders etc.) for preview + sync."""
    sb = cfg.get("sidebar") or {}
    titles = {str(it["repo"]).lower(): it.get("title") for it in cfg.get("featured") or []}
    latest = None
    if repos:
        r = max(repos, key=lambda r: r.get("pushed_at") or "")
        latest = titles.get(r["name"].lower()) or r["name"]
    info = (cf or {}).get("info") or {}
    ctx = {
        "cf_rating": info.get("rating", ""), "cf_rank": info.get("rank", ""),
        "cf_solved": (cf or {}).get("solved") or "",
        "contributions": f'{contrib["total"]:,}' if contrib and contrib.get("total") else "",
        "streak": contrib.get("streak", "") if contrib else "",
        "repos": len(repos) if repos else "", "stars": sum(r.get("stargazers_count", 0) for r in repos or []),
        "latest_repo": latest or "", "now_building": cfg.get("now_building", ""),
    }
    status = sb.get("status") or {}
    return {
        "bio": clip(fill(sb.get("bio", ""), ctx), 160),
        "status_emoji": status.get("emoji", ""),
        "status_text": clip(fill(status.get("text", ""), ctx), 80),
        "company": sb.get("company", ""),
        "location": sb.get("location") or cfg.get("location", ""),
        "website": sb.get("website") or (cfg.get("links") or {}).get("website", ""),
        "timezone": sb.get("timezone", ""),
        "socials": (sb.get("socials") or [])[:4],
        "followers": (user or {}).get("followers"), "following": (user or {}).get("following"),
        "avatar": sb.get("avatar", ""),
    }


def render_template(tmpl: str, values: dict[str, str]) -> str:
    def section(m):
        return m.group(2) if values.get(m.group(1), "").strip() else ""
    out = re.sub(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", section, tmpl, flags=re.S)
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), ""), out)
    return re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use cached data only")
    ap.add_argument("--refresh", action="store_true", help="ignore cache freshness")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "profile.yml").read_text()) or {}
    handle = cfg.get("handle") or os.environ.get("GITHUB_REPOSITORY_OWNER")
    if not handle:
        sys.exit("profile.yml needs `handle:` (your GitHub username)")
    cfg["handle"] = handle
    theme = cfg.get("theme") or {}
    pal = {m: svg.palette(theme, m) for m in MODES}
    f = sources.Fetcher(offline=args.offline, refresh=args.refresh)
    gh = f"https://github.com/{handle}"
    print(f"Building profile for {handle}")

    # ── data ──
    repos = sources.github_repos(f, handle)
    if repos is None:
        print("  ! no repo data; featured cards and project list keep their last version")
    by_name = {r["name"].lower(): r for r in (repos or [])}
    for name, desc in (cfg.get("descriptions") or {}).items():
        r = by_name.get(name.lower())
        if r and not r.get("description"):
            r["description"] = desc

    cf = sources.codeforces(f, cfg["codeforces"]) if cfg.get("codeforces") else None
    contrib = sources.github_contributions(f, handle)
    langs = sources.github_languages(f, handle, repos or [], set(cfg.get("languages_ignore") or []))
    events = sources.github_events(f, handle) if cfg.get("activity") else None
    user = f.get(f"https://api.github.com/users/{handle}")
    featured_names = [r["name"] for it in cfg.get("featured") or []
                      if (r := by_name.get(str(it["repo"]).lower()))]
    traffic = sources.repo_traffic(handle, featured_names, ROOT / "data" / "traffic.json")

    v: dict[str, str] = {}

    # ── banner ──
    chips = [c for c in [cfg.get("headline"), cfg.get("location")] if c]
    if cf and cf["info"].get("rating"):
        chips.append(f"Codeforces {cf['info']['rating']}")
    for m in MODES:
        write(ASSETS / f"banner-{m}.svg", svg.banner(cfg, pal[m], chips))
    v["banner"] = f'<p align="center">{picture("assets/banner", cfg.get("name") or handle, "100%")}</p>'

    # ── nav ──
    sections_present = {"featured-projects": bool(cfg.get("featured")),
                        "get-in-touch": any((cfg.get("links") or {}).values()),
                        "about-me": bool(cfg.get("about")),
                        "activity": bool(cfg.get("activity"))}
    nav = []
    for label, glyph, anchor in NAV:
        if not sections_present.get(anchor, True):
            continue
        for m in MODES:
            write(ASSETS / "nav" / f"{slug(label)}-{m}.svg", svg.pill(label, glyph, pal[m]))
        nav.append(f'<a href="#{anchor}">{picture(f"assets/nav/{slug(label)}", label)}</a>')
    v["nav"] = '<p align="center">\n' + "&nbsp;\n".join(nav) + "\n</p>"

    # ── live badges (count on every page load, so they can't be pre-drawn) ──
    badges = []
    acc = pal["dark"]["accent"].lstrip("#")
    acc2 = pal["dark"]["accent2"].lstrip("#")
    if cfg.get("views_counter"):
        badges.append(f'<img src="https://komarev.com/ghpvc/?username={handle}&label=Profile%20views&color={acc}&style=flat-square" alt="Profile views">')
    badges.append(f'<a href="{gh}?tab=followers"><img src="https://img.shields.io/github/followers/{handle}?label=Followers&style=flat-square&color={acc2}" alt="Followers"></a>')
    badges.append(f'<a href="{gh}?tab=repositories"><img src="https://img.shields.io/github/stars/{handle}?affiliations=OWNER&label=Stars&style=flat-square&color={acc}" alt="Stars"></a>')
    if cfg.get("codeforces"):
        badges.append(f'<a href="https://codeforces.com/profile/{cfg["codeforces"]}"><img src="https://img.shields.io/badge/Codeforces-{cfg["codeforces"]}-{acc2}?style=flat-square" alt="Codeforces"></a>')
    v["badges"] = '<p align="center">\n' + "\n".join(badges) + "\n</p>"

    # ── about ──
    about = list(cfg.get("about") or [])
    meta = []
    if cfg.get("now_building"):
        meta.append(f"🔨 **Now building:** {cfg['now_building']}")
    if cfg.get("location"):
        meta.append(f"📍 {cfg['location']}")
    v["about"] = "\n\n".join(about + ([" &nbsp;·&nbsp; ".join(meta)] if meta else []))

    # ── start here ──
    rows = []
    for s in cfg.get("start_here") or []:
        r = by_name.get(str(s.get("repo", "")).lower())
        name = r["name"] if r else s.get("repo")
        rows.append(f'<tr><td>If you like <b>{svg.esc(s.get("like", ""))}</b></td>'
                    f'<td><a href="{gh}/{name}"><b>{svg.esc(name)}</b></a></td>'
                    f'<td>{svg.esc(s.get("why", ""))}</td></tr>')
    if rows:
        v["start_here"] = "<table>\n" + "\n".join(rows) + "\n</table>"

    # ── featured cards ──
    cards = []
    for i, item in enumerate(cfg.get("featured") or []):
        r = by_name.get(str(item["repo"]).lower())
        base = f"assets/projects/{slug(item['repo'])}"
        if r:
            imgs = load_shots(f, handle, r["name"], item.get("shots"), SHOWCASE_VIEWPORT)
            views = (traffic.get(r["name"]) or {}).get("total")
            for m in MODES:
                card = (svg.showcase_card(r, item, imgs, pal[m], handle, i, views) if imgs
                        else svg.project_card(r, item, pal[m], i))
                write(ROOT / f"{base}-{m}.svg", card)
        elif not (ROOT / f"{base}-dark.svg").exists():
            print(f"  ! featured repo not found: {item['repo']}")
            continue
        name = r["name"] if r else item["repo"]
        cards.append(f'<a href="{gh}/{name}">{picture(base, item.get("title") or name, "49%")}</a>')
    if cards:
        v["featured"] = "\n\n".join(f'<p align="center">\n{cards[i]}\n{cards[i + 1] if i + 1 < len(cards) else ""}\n</p>'
                                     for i in range(0, len(cards), 2))

    # ── gallery ──
    thumbs = []
    for item in cfg.get("gallery") or []:
        r = by_name.get(str(item["repo"]).lower())
        if not r:
            continue
        imgs = load_shots(f, handle, r["name"], item.get("shots"), GALLERY_VIEWPORT)
        if not imgs:
            continue
        base = f"assets/gallery/{slug(r['name'])}"
        if any(t.startswith(f'<a href="{gh}/{r["name"]}"') for t in thumbs):
            base += "-2"
        for m in MODES:
            write(ROOT / f"{base}-{m}.svg", svg.gallery_card(r, imgs, pal[m], handle, item.get("caption", "")))
        thumbs.append(f'<a href="{gh}/{r["name"]}">{picture(base, r["name"], "32%")}</a>')
    if thumbs:
        v["gallery"] = "\n\n".join('<p align="center">\n' + "\n".join(thumbs[i:i + 3]) + "\n</p>"
                                    for i in range(0, len(thumbs), 3))

    # ── activity ──
    if cfg.get("activity") and contrib and contrib.get("days"):
        for m in MODES:
            write(ASSETS / f"heatmap-{m}.svg", svg.heatmap_card(contrib, pal[m]))
            write(ASSETS / f"rhythm-{m}.svg", svg.rhythm_card(contrib, pal[m]))
            if events is not None:
                write(ASSETS / f"activity-{m}.svg", svg.activity_card(events, pal[m]))
        pair = [f'<a href="{gh}?tab=overview">{picture("assets/activity", "Recent activity", "49%")}</a>']
        if not (ASSETS / "activity-dark.svg").exists():
            pair = []
        pair.append(picture("assets/rhythm", "Coding rhythm by weekday", "49%"))
        v["activity"] = (f'<p align="center"><a href="{gh}">{picture("assets/heatmap", "Contribution heatmap", "98%")}</a></p>\n\n'
                         '<p align="center">\n' + "\n".join(pair) + "\n</p>")

    # ── all projects ──
    if repos:
        cats = cfg.get("categories") or {}
        seen, blocks = set(), []
        groups = []
        for cat, names in cats.items():
            rs = [by_name[n.lower()] for n in names or [] if n.lower() in by_name]
            seen |= {r["name"].lower() for r in rs}
            groups.append((cat, rs))
        rest = sorted((r for r in repos if r["name"].lower() not in seen),
                      key=lambda r: r.get("pushed_at") or "", reverse=True)
        if rest:
            groups.append(("More", rest))
        for cat, rs in groups:
            if not rs:
                continue
            trs = "\n".join(
                f'<tr><td><a href="{r["html_url"]}"><b>{svg.esc(r["name"])}</b></a></td>'
                f'<td>{svg.esc(r.get("description") or "—")}</td>'
                f'<td><code>{svg.esc(r.get("language") or "—")}</code></td>'
                f'<td align="right">{"⭐ " + str(r["stargazers_count"]) if r.get("stargazers_count") else ""}</td></tr>'
                for r in rs)
            blocks.append(f"<details>\n<summary><b>{svg.esc(cat)}</b> &nbsp;<sub>{len(rs)} repos</sub></summary>\n<br>\n"
                          f"<table>\n{trs}\n</table>\n</details>")
        v["all_projects"] = "\n\n".join(blocks)

    # ── skills ──
    if cfg.get("skills"):
        ids = ",".join(cfg["skills"])
        v["skills"] = (f'<p align="center"><a href="https://skillicons.dev">'
                       f'<img src="https://skillicons.dev/icons?i={ids}&perline=8" alt="{svg.esc(", ".join(cfg["skills"]))}">'
                       f"</a></p>")

    # ── stats ──
    stats = {"handle": handle,
             "contributions": contrib and contrib["total"],
             "streak": contrib and contrib["streak"],
             "repos": len(repos) if repos is not None else None,
             "stars": sum(r.get("stargazers_count", 0) for r in repos) if repos is not None else None}
    if traffic:
        stats["views"] = sum(t["total"] for t in traffic.values())
        stats["views_since"] = min((t["since"] for t in traffic.values() if t["since"]), default=None)
    if repos is not None or not (ASSETS / "stats-dark.svg").exists():
        for m in MODES:
            write(ASSETS / f"stats-{m}.svg", svg.stats_card(stats, langs, pal[m]))
    stat_imgs = [f'<a href="{gh}?tab=repositories">{picture("assets/stats", "GitHub stats", "49%")}</a>']
    if cfg.get("codeforces"):
        if cf:
            for m in MODES:
                write(ASSETS / f"codeforces-{m}.svg", svg.cf_card(cf["info"], cf["history"], cf["solved"], pal[m]))
        if (ASSETS / "codeforces-dark.svg").exists():
            stat_imgs.append(f'<a href="https://codeforces.com/profile/{cfg["codeforces"]}">'
                             f'{picture("assets/codeforces", "Codeforces rating", "49%")}</a>')
    v["stats"] = '<p align="center">\n' + "\n".join(stat_imgs) + "\n</p>"

    # ── snake (drawn by .github/workflows/snake.yml onto the `output` branch) ──
    raw = f"https://raw.githubusercontent.com/{handle}/{handle}/output"
    v["snake"] = (f'<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="{raw}/snake-dark.svg">'
                  f'<img src="{raw}/snake-light.svg" alt="Snake eating my contribution graph" width="100%"></picture></p>')

    # ── contact ──
    links = cfg.get("links") or {}
    contact = []
    spec = [("linkedin", "LinkedIn", "in", lambda u: u),
            ("email", "Email", "@", lambda u: f"mailto:{u}"),
            ("website", "Website", "↗", lambda u: u)]
    for key, label, glyph, href in spec:
        if links.get(key):
            for m in MODES:
                write(ASSETS / "nav" / f"{key}-{m}.svg", svg.pill(label, glyph, pal[m]))
            contact.append(f'<a href="{svg.esc(href(links[key]))}">{picture(f"assets/nav/{key}", label)}</a>')
    if contact and cfg.get("codeforces"):
        for m in MODES:
            write(ASSETS / "nav" / f"codeforces-{m}.svg", svg.pill("Codeforces", "◢", pal[m]))
        contact.append(f'<a href="https://codeforces.com/profile/{cfg["codeforces"]}">'
                       f'{picture("assets/nav/codeforces", "Codeforces")}</a>')
    if contact:
        v["contact"] = '<p align="center">\n' + "&nbsp;\n".join(contact) + "\n</p>"

    # ── footer ──
    src = cfg.get("template_source") or f"{handle}/{handle}"
    today = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y")
    v["footer"] = (
        '<p align="center"><sub>\n'
        f'✨ Like this profile? It\'s a template. Open <a href="https://github.com/{src}"><b>{src}</b></a>, '
        "click <b>Use this template</b>, edit <code>profile.yml</code>, and the daily Action builds yours.\n"
        f"<br>Cards are drawn from live GitHub &amp; Codeforces data · last refreshed {today}\n"
        "</sub></p>")

    # ── sidebar (not part of the README: read by preview.py and sync_profile.py) ──
    if cfg.get("sidebar"):
        sidebar = build_sidebar(cfg, repos, by_name, cf, contrib, user if isinstance(user, dict) else None)
        (sources.CACHE / "sidebar.json").write_text(json.dumps(sidebar, ensure_ascii=False, indent=1))
        print(f"  ✓ bio ({len(sidebar['bio'])}/160): {sidebar['bio']}")

    tmpl = (ROOT / "templates" / "README.md.tmpl").read_text()
    write(ROOT / "README.md", render_template(tmpl, v))
    print(f"  ✓ README.md + {sum(1 for _ in ASSETS.rglob('*.svg'))} SVGs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
