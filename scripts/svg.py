"""SVG drawing helpers for the profile cards.

Every function returns a complete, self-contained SVG string: no JavaScript,
no external fonts or images, so it renders through GitHub's image proxy.
Animations are pure CSS. Each card is produced per colour mode ("dark" /
"light") and the README swaps them with <picture>.
"""

from __future__ import annotations

import html
import math

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "C": "#555555", "C++": "#f34b7d", "HTML": "#e34c26", "CSS": "#663399",
    "Java": "#b07219", "Go": "#00ADD8", "Rust": "#dea584", "Kotlin": "#A97BFF",
    "Dart": "#00B4AB", "Jupyter Notebook": "#DA5B0B", "Vue": "#41b883",
    "Svelte": "#ff3e00", "PHP": "#4F5D95", "Ruby": "#701516", "C#": "#178600",
    "Shell": "#89e051", "Dockerfile": "#384d54", "SCSS": "#c6538c",
}

# Codeforces rank colours, tuned per mode so they stay readable.
CF_RANKS = [
    (0, "newbie", "#9ca3af", "#6b7280"),
    (1200, "pupil", "#4ade80", "#15803d"),
    (1400, "specialist", "#2dd4bf", "#0f766e"),
    (1600, "expert", "#60a5fa", "#1d4ed8"),
    (1900, "candidate master", "#c084fc", "#7e22ce"),
    (2100, "master", "#fb923c", "#c2410c"),
    (2300, "international master", "#fb923c", "#c2410c"),
    (2400, "grandmaster", "#f87171", "#b91c1c"),
]

OCTICON_REPO = (
    "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75"
    "h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05"
    "A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8Z"
    "M5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2"
    "l-1.45-1.087a.25.25 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"
)
OCTICON_STAR = (
    "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279"
    "l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1"
    "-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
)


# ── basics ──────────────────────────────────────────────────────────────────

def esc(s) -> str:
    return html.escape(str(s), quote=True)


def text_width(s: str, size: float, mono: bool = False, bold: bool = False) -> float:
    """Rough width estimate for the system UI font (good enough for layout)."""
    if mono:
        return len(s) * size * 0.61
    w = 0.0
    for ch in s:
        if ch in "il.,:;|!'`ıjtf":
            w += 0.30
        elif ch in "mwMW@%":
            w += 0.86
        elif ch == " ":
            w += 0.29
        elif ch.isupper() or ch.isdigit():
            w += 0.64
        elif ord(ch) > 0x2000:
            w += 0.9
        else:
            w += 0.53
    return w * size * (1.06 if bold else 1.0)


def wrap(s: str, size: float, max_w: float, max_lines: int) -> list[str]:
    """Word-wrap `s`; the last line gets an ellipsis if text was cut."""
    words = s.split()
    lines: list[str] = []
    cur = ""
    used = 0
    for w in words:
        t = f"{cur} {w}".strip()
        if text_width(t, size) <= max_w:
            cur = t
            used += 1
            continue
        if cur:
            lines.append(cur)
        if len(lines) == max_lines:
            cur = ""
            break
        cur = w
        used += 1
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if used < len(words) and lines:
        last = lines[-1]
        while text_width(last + "…", size) > max_w and " " in last:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last.rstrip(" ,.;:·—-") + "…"
    return lines


def truncate(s: str, size: float, max_w: float, bold: bool = False) -> str:
    if text_width(s, size, bold=bold) <= max_w:
        return s
    while s and text_width(s + "…", size, bold=bold) > max_w:
        s = s[:-1]
    return s.rstrip() + "…"


def palette(theme: dict, mode: str) -> dict:
    t = theme.get(mode, {})
    if mode == "dark":
        base = dict(bg="#0d1117", card="#0f141b", card_hi="#151c25", border="#2a3240",
                    text="#e6edf3", muted="#9aa4b2", faint="#6e7681", chip="#1c2430",
                    chip_text="#cdd6e0", grid="#3b4452", accent="#34d399", accent2="#fb3b5a",
                    bg_a="#06140f", bg_b="#0b1016", bg_c="#1a0b12")
    else:
        base = dict(bg="#ffffff", card="#ffffff", card_hi="#f6f8fa", border="#d8dee4",
                    text="#1f2328", muted="#57606a", faint="#8c959f", chip="#eef2f5",
                    chip_text="#24292f", grid="#c9d1d9", accent="#047857", accent2="#e11d48",
                    bg_a="#ecfdf5", bg_b="#ffffff", bg_c="#fff1f2")
    base.update({k: v for k, v in t.items() if v})
    base["mode"] = mode
    return base


def _svg(w: int, h: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title>{body}</svg>\n"
    )


def chip(x: float, y: float, label: str, p: dict, size: float = 12,
         fill: str | None = None, color: str | None = None, h: float = 24) -> tuple[str, float]:
    w = text_width(label, size) + 22
    svg = (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
        f'fill="{fill or p["chip"]}"/>'
        f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + size * 0.36:.1f}" text-anchor="middle" '
        f'font-size="{size}" fill="{color or p["chip_text"]}" class="f">{esc(label)}</text>'
    )
    return svg, w


BASE_CSS = (
    f".f{{font-family:{FONT}}}.m{{font-family:{MONO}}}"
    "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
)


# ── banner ──────────────────────────────────────────────────────────────────

def _rotation_css(n: int, period: float) -> str:
    if n <= 1:
        return ".tag{opacity:1}"
    slot = 100 / n
    a, b, c = slot * 0.10, slot * 0.86, slot * 0.98
    css = (
        f".tag{{opacity:0;animation:rot {period:.1f}s ease-in-out infinite}}"
        f"@keyframes rot{{0%{{opacity:0;transform:translateY(12px)}}"
        f"{a:.2f}%{{opacity:1;transform:translateY(0)}}"
        f"{b:.2f}%{{opacity:1;transform:translateY(0)}}"
        f"{c:.2f}%{{opacity:0;transform:translateY(-12px)}}"
        f"100%{{opacity:0;transform:translateY(-12px)}}}}"
    )
    css += "".join(f".tag{i}{{animation-delay:{i * period / n:.2f}s}}" for i in range(n))
    return css


def _wave(y: float, amp: float, period: float, width: float) -> str:
    d = f"M0 {y}"
    x = 0.0
    while x < width:
        d += f" q{period / 4} {-amp} {period / 2} 0 t{period / 2} 0"
        x += period
    return d + f" V300 H0 Z"


def banner(cfg: dict, p: dict, chips: list[str]) -> str:
    W, H = 1000, 290
    taglines = cfg.get("taglines") or []
    n = len(taglines)
    period = max(3.6 * n, 4)
    dark = p["mode"] == "dark"

    css = BASE_CSS + _rotation_css(n, period) + (
        ".sun{transform-origin:812px 128px;animation:pulse 7s ease-in-out infinite}"
        "@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}"
        ".halo{transform-origin:812px 128px;animation:halo 7s ease-in-out infinite}"
        "@keyframes halo{0%,100%{opacity:.55;transform:scale(1)}50%{opacity:.9;transform:scale(1.12)}}"
        ".w1{animation:flow 14s linear infinite}.w2{animation:flow 22s linear infinite}"
        ".w3{animation:flow 9s linear infinite}"
        "@keyframes flow{to{transform:translateX(-400px)}}"
        ".sweep{stroke-dasharray:520;stroke-dashoffset:520;animation:draw 1.8s cubic-bezier(.2,.8,.2,1) .4s forwards}"
        "@keyframes draw{to{stroke-dashoffset:0}}"
        ".cur{animation:blink 1.1s step-end infinite}@keyframes blink{50%{opacity:0}}"
        ".in{opacity:0;animation:in .9s ease-out forwards}"
        "@keyframes in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}"
        ".d1{animation-delay:.15s}.d2{animation-delay:.35s}.d3{animation-delay:.9s}"
        ".tw{animation:tw 3s ease-in-out infinite}@keyframes tw{50%{opacity:.15}}"
    )

    stars = ""
    if dark:
        pts = [(612, 42), (690, 70), (944, 52), (968, 160), (900, 34), (652, 132), (735, 26), (975, 98)]
        stars = "".join(
            f'<circle class="tw" style="animation-delay:{i * .4:.1f}s" cx="{x}" cy="{y}" r="1.4" fill="{p["text"]}" opacity=".6"/>'
            for i, (x, y) in enumerate(pts)
        )

    tags = "".join(
        f'<text class="f tag tag{i}" x="60" y="206" font-size="22" fill="{p["muted"]}">'
        f'<tspan fill="{p["accent"]}" font-weight="700">▸ </tspan>{esc(t)}</text>'
        for i, t in enumerate(taglines)
    )

    chip_svg, x = "", 60.0
    for c in chips:
        s, w = chip(x, 232, c, p, size=12.5, h=26,
                    fill=p["card_hi"] if dark else "#ffffff", color=p["text"])
        chip_svg += s
        x += w + 10

    name = cfg.get("name") or cfg.get("handle", "")
    name_size = 58 if len(name) <= 16 else 44
    prompt = f"~/{(cfg.get('location') or 'home').split(',')[0].strip().lower()} $ whoami"

    body = f"""<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p['bg_a']}"/><stop offset=".55" stop-color="{p['bg_b']}"/><stop offset="1" stop-color="{p['bg_c']}"/></linearGradient>
<radialGradient id="glow"><stop offset="0" stop-color="{p['accent2']}" stop-opacity=".55"/><stop offset="1" stop-color="{p['accent2']}" stop-opacity="0"/></radialGradient>
<linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="{p['accent']}"/><stop offset="1" stop-color="{p['accent2']}"/></linearGradient>
<linearGradient id="wv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p['accent']}" stop-opacity=".22"/><stop offset="1" stop-color="{p['accent']}" stop-opacity="0"/></linearGradient>
<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="{p['grid']}" opacity="{'.35' if dark else '.6'}"/></pattern>
<clipPath id="clip"><rect width="{W}" height="{H}" rx="20"/></clipPath>
</defs>
<style>{css}</style>
<g clip-path="url(#clip)">
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<rect width="{W}" height="{H}" fill="url(#dots)"/>
{stars}
<circle class="halo" cx="812" cy="128" r="150" fill="url(#glow)"/>
<circle class="sun" cx="812" cy="128" r="66" fill="{p['accent2']}"/>
<path class="w2" d="{_wave(238, 10, 400, 1500)}" fill="url(#wv)" opacity=".7"/>
<path class="w1" d="{_wave(252, 12, 400, 1500)}" fill="url(#wv)"/>
<path class="w3" d="{_wave(268, 7, 400, 1500)}" fill="{p['accent']}" opacity=".12"/>
<text class="m in" x="60" y="72" font-size="16" fill="{p['accent']}">{esc(prompt)}<tspan class="cur" fill="{p['text']}"> ▍</tspan></text>
<text class="f in d1" x="58" y="142" font-size="{name_size}" font-weight="800" letter-spacing="-1" fill="{p['text']}">{esc(name)}</text>
<path class="sweep" d="M60 162 H{min(60 + text_width(name, name_size, bold=True), 560):.0f}" stroke="url(#ln)" stroke-width="5" stroke-linecap="round" fill="none"/>
{tags}
<g class="in d3">{chip_svg}</g>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="none" stroke="{p['border']}"/>"""
    return _svg(W, H, body, f"{name}: " + " · ".join(taglines))


# ── project card ────────────────────────────────────────────────────────────

def project_card(repo: dict, item: dict, p: dict, idx: int = 0) -> str:
    W, H = 480, 210
    lang = repo.get("language") or ""
    lc = LANG_COLORS.get(lang, p["faint"])
    title = item.get("title") or repo["name"]
    desc = repo.get("description") or ""
    tag = (item.get("tag") or "").upper()
    delay = 1.2 + idx * 1.7

    css = BASE_CSS + (
        ".sh{animation:sh 9s ease-in-out infinite}"
        "@keyframes sh{0%{transform:translateX(-260px) skewX(-20deg)}35%,100%{transform:translateX(760px) skewX(-20deg)}}"
        ".in{opacity:0;animation:in .7s ease-out forwards}"
        "@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
    )

    tag_svg, tag_w = "", 0.0
    if tag:
        tag_w = text_width(tag, 10, bold=True) + len(tag) * 1.0 + 18  # +letter-spacing
        tx = W - 22 - tag_w
        tag_svg = (
            f'<rect x="{tx:.1f}" y="20" width="{tag_w:.1f}" height="22" rx="11" fill="none" stroke="{p["accent2"]}" stroke-opacity=".55"/>'
            f'<text class="f" x="{tx + tag_w / 2:.1f}" y="35" text-anchor="middle" font-size="10" '
            f'font-weight="700" letter-spacing="1" fill="{p["accent2"]}">{esc(tag)}</text>'
        )
    title = truncate(title, 19, W - 70 - tag_w - 30, bold=True)

    lines = wrap(desc, 13.5, W - 48, 3) if desc else ["No description yet."]
    desc_svg = "".join(
        f'<text class="f" x="24" y="{80 + i * 21}" font-size="13.5" fill="{p["muted"]}">{esc(l)}</text>'
        for i, l in enumerate(lines)
    )

    chips, x = "", 24.0
    for s in item.get("stack") or []:
        w = text_width(s, 11.5) + 22
        if x + w > W - 24:
            break
        c, w = chip(x, 146, s, p, size=11.5, h=23)
        chips += c
        x += w + 7

    stars = repo.get("stargazers_count", 0)
    foot = ""
    if lang:
        foot += (f'<circle cx="30" cy="186" r="5.5" fill="{lc}"/>'
                 f'<text class="f" x="42" y="190.5" font-size="12.5" fill="{p["muted"]}">{esc(lang)}</text>')
    sx = 42 + (text_width(lang, 12.5) + 18 if lang else -18)
    foot += (f'<path transform="translate({sx:.1f},178)" d="{OCTICON_STAR}" fill="{p["muted"]}"/>'
             f'<text class="f" x="{sx + 22:.1f}" y="190.5" font-size="12.5" fill="{p["muted"]}">{stars}</text>')
    foot += (f'<text class="f" x="{W - 24}" y="190.5" text-anchor="end" font-size="12.5" '
             f'font-weight="600" fill="{p["accent"]}">Open repo →</text>')

    body = f"""<defs>
<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16"/></clipPath>
<radialGradient id="g" cx="1" cy="0" r="1"><stop offset="0" stop-color="{lc}" stop-opacity="{'.22' if p['mode'] == 'dark' else '.12'}"/><stop offset=".6" stop-color="{lc}" stop-opacity="0"/></radialGradient>
<linearGradient id="top" x1="0" x2="1"><stop offset="0" stop-color="{p['accent']}"/><stop offset="1" stop-color="{p['accent2']}"/></linearGradient>
<linearGradient id="s" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity="{'.06' if p['mode'] == 'dark' else '.35'}"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
</defs>
<style>{css}</style>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{p['card']}"/>
<rect width="{W}" height="{H}" fill="url(#g)"/>
<rect width="{W}" height="3" fill="url(#top)"/>
<rect class="sh" style="animation-delay:{delay:.1f}s" x="0" y="0" width="140" height="{H}" fill="url(#s)"/>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="none" stroke="{p['border']}"/>
<g class="in">
<path transform="translate(24,24)" d="{OCTICON_REPO}" fill="{p['muted']}"/>
<text class="f" x="48" y="38" font-size="19" font-weight="700" fill="{p['text']}">{esc(title)}</text>
{tag_svg}
{desc_svg}
{chips}
<line x1="24" y1="168" x2="{W - 24}" y2="168" stroke="{p['border']}" stroke-dasharray="2 4"/>
{foot}
</g>"""
    return _svg(W, H, body, f"{title}: {desc}")


# ── codeforces card ─────────────────────────────────────────────────────────

def cf_rank(rating: int | None, mode: str) -> tuple[str, str]:
    name, color = "unrated", "#9ca3af" if mode == "dark" else "#6b7280"
    if rating is None:
        return name, color
    for floor, n, cd, cl in CF_RANKS:
        if rating >= floor:
            name, color = n, cd if mode == "dark" else cl
    return name, color


def _sparkline(values: list[int], x0, y0, w, h) -> tuple[str, list[tuple[float, float]]]:
    lo, hi = min(values), max(values)
    if hi - lo < 50:
        lo, hi = lo - 25, hi + 25
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        px = x0 + (w * i / (n - 1) if n > 1 else w / 2)
        py = y0 + h - (v - lo) / (hi - lo) * h
        pts.append((px, py))
    d = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    return d, pts


def cf_card(info: dict | None, history: list[dict], solved: int | None, p: dict) -> str:
    W, H = 480, 210
    mode = p["mode"]
    handle = (info or {}).get("handle", "")
    rating = (info or {}).get("rating")
    max_rating = (info or {}).get("maxRating")
    rank, rc = cf_rank(rating, mode)
    contests = len(history)
    delta = history[-1]["newRating"] - history[-1]["oldRating"] if history else None

    css = BASE_CSS + (
        ".ln{stroke-dasharray:1200;stroke-dashoffset:1200;animation:draw 2.4s ease-out .3s forwards}"
        "@keyframes draw{to{stroke-dashoffset:0}}"
        ".ar{opacity:0;animation:fade 1s ease-out 1.6s forwards}@keyframes fade{to{opacity:1}}"
        ".pl{transform-box:fill-box;transform-origin:center;animation:pl 2s ease-out 2.4s infinite}"
        "@keyframes pl{0%{transform:scale(1);opacity:.7}100%{transform:scale(3.2);opacity:0}}"
        ".in{opacity:0;animation:fade .8s ease-out forwards}"
    )

    graph = ""
    gx, gy, gw, gh = 236, 52, 220, 96
    if len(history) >= 2:
        vals = [h["newRating"] for h in history][-40:]
        d, pts = _sparkline(vals, gx, gy, gw, gh)
        area = d + f" L{pts[-1][0]:.1f} {gy + gh} L{pts[0][0]:.1f} {gy + gh} Z"
        lx, ly = pts[-1]
        graph = (
            f'<path class="ar" d="{area}" fill="url(#ga)"/>'
            f'<path class="ln" d="{d}" fill="none" stroke="{rc}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle class="pl" cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{rc}"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{rc}" stroke="{p["card"]}" stroke-width="2"/>'
            f'<text class="f" x="{gx}" y="{gy + gh + 16}" font-size="11" fill="{p["faint"]}">rating over last {len(vals)} contests</text>'
        )
    elif history:
        graph = (f'<text class="f" x="{gx + gw / 2}" y="{gy + gh / 2}" text-anchor="middle" font-size="12.5" '
                 f'fill="{p["faint"]}">1 rated contest so far</text>')
    else:
        graph = (f'<text class="f" x="{gx + gw / 2}" y="{gy + gh / 2}" text-anchor="middle" font-size="12.5" '
                 f'fill="{p["faint"]}">No rated contests yet</text>')

    big = str(rating) if rating is not None else "—"
    sub = f"{rank}" + (f" · max {max_rating}" if max_rating else "")

    chips, x = "", 24.0
    items = []
    if solved is not None:
        items.append(f"{solved} solved")
    items.append(f"{contests} contests")
    if delta is not None:
        items.append(f"last {'+' if delta >= 0 else '−'}{abs(delta)}")
    for it in items:
        c, w = chip(x, 168, it, p, size=12, h=24)
        chips += c
        x += w + 8

    body = f"""<defs>
<linearGradient id="ga" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{rc}" stop-opacity=".35"/><stop offset="1" stop-color="{rc}" stop-opacity="0"/></linearGradient>
<linearGradient id="top" x1="0" x2="1"><stop offset="0" stop-color="#f6c343"/><stop offset=".5" stop-color="#3b82f6"/><stop offset="1" stop-color="#ef4444"/></linearGradient>
<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16"/></clipPath>
</defs>
<style>{css}</style>
<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="{p['card']}"/><rect width="{W}" height="3" fill="url(#top)"/></g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="none" stroke="{p['border']}"/>
<g class="in">
<text class="f" x="24" y="34" font-size="11" font-weight="700" letter-spacing="1.6" fill="{p['faint']}">CODEFORCES</text>
<text class="f" x="24" y="58" font-size="17" font-weight="700" fill="{rc}">{esc(handle)}</text>
<text class="f" x="22" y="118" font-size="50" font-weight="800" letter-spacing="-1.5" fill="{p['text']}">{esc(big)}</text>
<text class="f" x="24" y="142" font-size="13.5" fill="{rc}" font-weight="600">{esc(sub)}</text>
{chips}
</g>
{graph}"""
    return _svg(W, H, body, f"Codeforces {handle}: {big} ({rank})")


# ── github stats card ───────────────────────────────────────────────────────

def stats_card(stats: dict, langs: list[tuple[str, float]], p: dict) -> str:
    W, H = 480, 210
    css = BASE_CSS + (
        ".in{opacity:0;animation:in .7s ease-out forwards}"
        "@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
        ".bar{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow 1.2s cubic-bezier(.2,.8,.2,1) forwards}"
        "@keyframes grow{to{transform:scaleX(1)}}"
    )

    cells = [
        ("contributions", stats.get("contributions"), "in the last year"),
        ("current streak", stats.get("streak"), "days"),
        ("public repos", stats.get("repos"), "and counting"),
        ("stars earned", stats.get("stars"), "across repos"),
    ]
    grid = ""
    for i, (label, val, hint) in enumerate(cells):
        cx = 24 + (i % 2) * 108
        cy = 64 + (i // 2) * 66
        v = "—" if val is None else f"{val:,}"
        grid += (
            f'<g class="in" style="animation-delay:{.1 + i * .12:.2f}s">'
            f'<text class="f" x="{cx}" y="{cy + 18}" font-size="26" font-weight="800" fill="{p["text"]}">{v}</text>'
            f'<text class="f" x="{cx}" y="{cy + 38}" font-size="11.5" fill="{p["muted"]}">{esc(label)}</text>'
            f'<text class="f" x="{cx}" y="{cy + 53}" font-size="10.5" fill="{p["faint"]}">{esc(hint)}</text></g>'
        )

    lx, lw = 262, 194
    lang_svg = (f'<text class="f" x="{lx}" y="64" font-size="11" font-weight="700" letter-spacing="1.2" '
                f'fill="{p["faint"]}">TOP LANGUAGES</text>')
    if langs:
        x = float(lx)
        segs = ""
        for name, pct in langs:
            w = lw * pct / 100
            segs += f'<rect x="{x:.1f}" y="76" width="{max(w, 0):.1f}" height="10" fill="{LANG_COLORS.get(name, p["faint"])}"/>'
            x += w
        lang_svg += (f'<clipPath id="bc"><rect x="{lx}" y="76" width="{lw}" height="10" rx="5"/></clipPath>'
                     f'<g clip-path="url(#bc)"><g class="bar">{segs}</g></g>')
        for i, (name, pct) in enumerate(langs[:5]):
            yy = 110 + i * 19
            lang_svg += (
                f'<g class="in" style="animation-delay:{.5 + i * .1:.2f}s">'
                f'<circle cx="{lx + 5}" cy="{yy - 4}" r="5" fill="{LANG_COLORS.get(name, p["faint"])}"/>'
                f'<text class="f" x="{lx + 16}" y="{yy}" font-size="12.5" fill="{p["text"]}">{esc(name)}</text>'
                f'<text class="f" x="{lx + lw}" y="{yy}" text-anchor="end" font-size="12.5" fill="{p["muted"]}">{pct:.1f}%</text></g>'
            )

    body = f"""<defs>
<linearGradient id="top" x1="0" x2="1"><stop offset="0" stop-color="{p['accent']}"/><stop offset="1" stop-color="{p['accent2']}"/></linearGradient>
<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16"/></clipPath>
</defs>
<style>{css}</style>
<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="{p['card']}"/><rect width="{W}" height="3" fill="url(#top)"/></g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="none" stroke="{p['border']}"/>
<text class="f" x="24" y="34" font-size="11" font-weight="700" letter-spacing="1.6" fill="{p['faint']}">GITHUB</text>
<text class="f" x="{W - 24}" y="34" text-anchor="end" font-size="12" fill="{p['muted']}">@{esc(stats.get('handle', ''))}</text>
<line x1="{lx - 18}" y1="56" x2="{lx - 18}" y2="{H - 24}" stroke="{p['border']}"/>
{grid}
{lang_svg}"""
    return _svg(W, H, body, f"GitHub stats for {stats.get('handle', '')}")


# ── pills (nav + contact) ───────────────────────────────────────────────────

def pill(label: str, glyph: str, p: dict) -> str:
    """A small rounded button. `glyph` is a short symbol shown before the label."""
    size = 14
    w = int(text_width(label, size, bold=True) + (34 if glyph else 0) + 34)
    h = 38
    gx = 18
    body = f"""<defs><linearGradient id="b" x1="0" x2="1"><stop offset="0" stop-color="{p['accent']}" stop-opacity="{'.18' if p['mode'] == 'dark' else '.10'}"/><stop offset="1" stop-color="{p['accent2']}" stop-opacity="{'.18' if p['mode'] == 'dark' else '.10'}"/></linearGradient>
<linearGradient id="s" x1="0" x2="1"><stop offset="0" stop-color="{p['accent']}"/><stop offset="1" stop-color="{p['accent2']}"/></linearGradient></defs>
<style>{BASE_CSS}</style>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{(h - 2) / 2}" fill="{p['card']}"/>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{(h - 2) / 2}" fill="url(#b)" stroke="url(#s)" stroke-width="1.5"/>
{f'<text class="f" x="{gx}" y="{h / 2 + 5}" font-size="15" fill="{p["accent"]}">{esc(glyph)}</text>' if glyph else ''}
<text class="f" x="{gx + (24 if glyph else 0)}" y="{h / 2 + 5}" font-size="{size}" font-weight="700" fill="{p['text']}">{esc(label)}</text>"""
    return _svg(w, h, body, label)
