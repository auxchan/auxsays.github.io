#!/usr/bin/env python3
"""Plan the deploy's IndexNow ping: the pages whose records changed in this deploy (P8).

WHAT IT SENDS, AND WHEN. pages.yml runs this in the build job, on the exact site about to be uploaded,
and hands the result to ONE step at the end of the deploy job, which POSTs it to api.indexnow.org only
after the deploy succeeded. IndexNow reaches Bing and the engines that share it; Google does not take it
(for Google the lever is the sitemap's lastmod dates). No account and no secret: the key is public by
design and is served at the site root as <key>.txt, which is how the engine checks the sender owns the
host.

WHICH URLS CHANGED. The built sitemap against the LIVE one, fetched just before the deploy replaces it.
Since #279 a patch page's <lastmod> is its record_last_updated, and a tracker's is the newest record it
lists, so a URL is "changed" exactly when it is new in this build or its stored date moved. Comparing with
what is live, not with the previous commit, is what keeps a cancelled or failed deploy from losing its
changes: they are still different from the live site at the next deploy that succeeds.

BOUNDS.
  - at most MAX_URLS (500) per deploy, newest stored date first; the rest are named as dropped in the
    log. The protocol answers 429 to excess submissions, so a deploy never sends the whole site.
  - nothing changed, the live sitemap unreadable or empty, no key file, or any error: no payload, so the
    ping step sends nothing. An unreadable live sitemap is never read as "everything changed".
  - only https://auxsays.com/ URLs, the host the key file is served from.
FAIL SOFT. It always exits 0; every refusal is a ::warning:: in the log. The deploy never waits on it.

Run:  python auxsays/scripts/ci/indexnow_plan.py --site auxsays/_site [--live-sitemap URL | --live-file F]
                                                   [--github-output FILE]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

HOST = "auxsays.com"
ORIGIN = f"https://{HOST}/"
LIVE_SITEMAP = f"{ORIGIN}sitemap.xml"
ENDPOINT = "https://api.indexnow.org/indexnow"
MAX_URLS = 500
KEY_NAME = re.compile(r"\A([0-9a-f]{32})\.txt\Z")
_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
USER_AGENT = "auxsays-deploy/1.0 (+https://auxsays.com/)"


def warn(message: str) -> None:
    print(f"::warning::IndexNow: {message}")


def parse_sitemap(text: str) -> dict[str, str | None]:
    """{loc: lastmod or None}. Raises on XML that does not parse."""
    root = ElementTree.fromstring(text)
    out: dict[str, str | None] = {}
    for url in root.iter(f"{_NS}url"):
        loc = (url.findtext(f"{_NS}loc") or "").strip()
        if not loc:
            continue
        mod = url.findtext(f"{_NS}lastmod")
        out[loc] = mod.strip() if mod and mod.strip() else None
    return out


def find_key(site: Path) -> str | None:
    """The one <key>.txt at the site root whose content is its own name, else None."""
    keys = []
    for path in sorted(site.glob("*.txt")):
        m = KEY_NAME.match(path.name)
        if m and path.read_text(encoding="utf-8").strip() == m.group(1):
            keys.append(m.group(1))
    return keys[0] if len(keys) == 1 else None


def changed_urls(built: dict[str, str | None], live: dict[str, str | None]) -> list[str]:
    """URLs new in this build or whose stored date moved, newest date first, on this host only."""
    changed = [(loc, mod) for loc, mod in built.items()
               if loc.startswith(ORIGIN) and (loc not in live or live[loc] != mod)]
    dated = sorted((c for c in changed if c[1]), key=lambda c: (c[1], c[0]), reverse=True)
    undated = sorted(c for c in changed if not c[1])
    return [loc for loc, _ in dated + undated]


def plan(site: Path, live_text: str | None) -> tuple[dict | None, str]:
    """(payload or None, one-line reason). Never raises."""
    try:
        key = find_key(site)
        if not key:
            return None, "no single <key>.txt at the site root; nothing will be sent"
        built = parse_sitemap((site / "sitemap.xml").read_text(encoding="utf-8"))
        if live_text is None:
            return None, "the live sitemap could not be read; nothing will be sent"
        live = parse_sitemap(live_text)
        if not live:
            return None, "the live sitemap lists no URL; nothing will be sent rather than the whole site"
        urls = changed_urls(built, live)
        if not urls:
            return None, "no page changed in this deploy; nothing will be sent"
        dropped = max(0, len(urls) - MAX_URLS)
        urls = urls[:MAX_URLS]
        payload = {"host": HOST, "key": key, "keyLocation": f"{ORIGIN}{key}.txt", "urlList": urls}
        note = f"{len(urls)} changed URL(s) planned" + (f"; {dropped} more over the {MAX_URLS} cap not sent" if dropped else "")
        return payload, note
    except Exception as exc:  # noqa: BLE001 -- fail soft: a planning error sends nothing
        return None, f"planning failed ({type(exc).__name__}: {exc}); nothing will be sent"


def fetch(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml"})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 -- fixed https URL
            return resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        warn(f"could not read {url} ({type(exc).__name__}: {exc})")
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--live-sitemap", default=LIVE_SITEMAP)
    ap.add_argument("--live-file", type=Path, default=None, help="read the live sitemap from a file (tests)")
    ap.add_argument("--github-output", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.live_file is not None:
        try:
            live_text = args.live_file.read_text(encoding="utf-8")
        except OSError as exc:
            warn(f"could not read {args.live_file} ({exc})")
            live_text = None
    else:
        live_text = fetch(args.live_sitemap)
    payload, note = plan(args.site, live_text)
    if payload is None:
        if "no page changed" in note:
            print(f"IndexNow: {note}")
        else:
            warn(note)
    else:
        print(f"IndexNow: {note}")
        for url in payload["urlList"][:20]:
            print(f"  {url}")
    line = json.dumps(payload, separators=(",", ":")) if payload else ""
    if args.github_output is not None:
        try:
            with args.github_output.open("a", encoding="utf-8") as fh:
                fh.write(f"payload={line}\n")
                fh.write(f"count={len(payload['urlList']) if payload else 0}\n")
        except OSError as exc:
            warn(f"could not write the step output ({exc}); nothing will be sent")
    return 0


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:  # noqa: BLE001 -- fail soft, even on an argument error
        if not (isinstance(exc, SystemExit) and exc.code in (0, None)):
            warn(f"planner stopped ({type(exc).__name__}); nothing will be sent")
    raise SystemExit(0)
