#!/usr/bin/env python3
"""Write the `sidebar:` values from profile.yml to your GitHub account.

Opt-in. It does nothing unless PROFILE_TOKEN is set: a classic token with
the `user` scope, saved as an Actions secret. Run build.py first; it
resolves the live placeholders into .cache/sidebar.json.

    python scripts/sync_profile.py --dry-run   # show what would change

Only fields with a value in profile.yml are touched; empty ones are left
alone, so this never wipes something you set by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"


def call(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-builder", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("PROFILE_TOKEN")
    src = ROOT / ".cache" / "sidebar.json"
    if not src.exists():
        print("No .cache/sidebar.json: run scripts/build.py first (and set `sidebar:` in profile.yml).")
        return 0
    want = json.loads(src.read_text())
    if not token:
        print("PROFILE_TOKEN not set: sidebar sync skipped (this is the default).")
        print(f"  bio would be: {want['bio']}")
        return 0

    try:
        me = call("GET", f"{API}/user", token)
    except urllib.error.HTTPError as e:
        sys.exit(f"Token rejected ({e.code}). It needs the `user` scope.")

    patch = {}
    for ours, theirs in (("bio", "bio"), ("company", "company"), ("location", "location"), ("website", "blog")):
        val = (want.get(ours) or "").strip()
        if val and val != (me.get(theirs) or ""):
            patch[theirs] = val
    for k, v in patch.items():
        print(f"  {k}: {me.get(k)!r} → {v!r}")
    if patch and not args.dry_run:
        call("PATCH", f"{API}/user", token, patch)

    changed = bool(patch)
    text = (want.get("status_text") or "").strip()
    if text:
        q = {"query": "query{viewer{status{emoji message}}}"}
        cur = (call("POST", f"{API}/graphql", token, q).get("data") or {}).get("viewer", {}).get("status") or {}
        emoji = want.get("status_emoji") or ""
        # GitHub returns emoji as :shortcode:, so compare the message only.
        if cur.get("message") != text:
            changed = True
            print(f"  status: {cur.get('emoji')} {cur.get('message')!r} → {emoji} {text!r}")
            if not args.dry_run:
                m = ("mutation($e:String,$m:String){changeUserStatus(input:{emoji:$e,message:$m})"
                     "{status{message}}}")
                res = call("POST", f"{API}/graphql", token, {"query": m, "variables": {"e": emoji, "m": text}})
                if res.get("errors"):
                    print(f"  ! status not updated: {res['errors'][0].get('message')}")

    if not changed:
        print("Sidebar already up to date.")
    elif args.dry_run:
        print("(dry run: nothing changed)")
    else:
        print("Sidebar synced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
