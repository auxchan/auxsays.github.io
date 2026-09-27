#!/usr/bin/env python3
"""Bounded reachability probe for OFFICIAL Adobe Photoshop release-history endpoints.

WHY THIS EXISTS. `patch_ingestion_sources.yml` records Photoshop as `enabled: false` because the
canonical HelpX desktop release-notes page "is not reachable from datacenter / GitHub Actions
egress (connection times out, zero bytes)". That claim decides whether a P1 product can be
ingested at all, and it was measured once. This probe re-measures it -- the same way, from the same
egress -- so the decision is made against a current reading rather than a remembered one.

It probes OFFICIAL Adobe hosts only. Wayback, search caches, unofficial mirrors and hand-curated
per-version URLs are not production authority and are not probed.

Output is one JSON object per endpoint on stdout, so the same script can run locally and inside a
GitHub Actions job and the two results can be compared line for line.

Run: python auxsays/scripts/probe_photoshop_sources.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.http import USER_AGENT, fetch_text  # noqa: E402

# Official Adobe routes only. Each entry says what it is FOR, because a page that merely responds
# is not the same as a page that carries release identity.
CANDIDATES = [
    # The configured canonical source.
    ("canonical-desktop-release-notes",
     "https://helpx.adobe.com/photoshop/desktop/whats-new/photoshop-on-desktop-release-notes.html",
     "release-history"),
    # Same document under Adobe's explicit /en/ locale path.
    ("en-locale-desktop-release-notes",
     "https://helpx.adobe.com/en/photoshop/desktop/whats-new/photoshop-on-desktop-release-notes.html",
     "release-history"),
    # Adobe's older release-note route for the same product.
    ("legacy-release-notes",
     "https://helpx.adobe.com/photoshop/release-note/photoshop-release-notes.html",
     "release-history"),
    ("en-legacy-release-notes",
     "https://helpx.adobe.com/en/photoshop/release-note/photoshop-release-notes.html",
     "release-history"),
    # "What's new" summary, which historically carries the current version and ship date.
    ("whats-new",
     "https://helpx.adobe.com/photoshop/using/whats-new.html",
     "release-history"),
    ("en-whats-new",
     "https://helpx.adobe.com/en/photoshop/using/whats-new.html",
     "release-history"),
    # AEM model endpoint for the canonical page. HelpX runs on AEM, which often serves the same
    # authored content as JSON. If reachable, this is the most parse-stable official route.
    ("aem-model-json",
     "https://helpx.adobe.com/photoshop/desktop/whats-new/photoshop-on-desktop-release-notes.model.json",
     "release-history"),
    # Creative Cloud app release notes, which include Photoshop desktop rows.
    ("cc-release-notes",
     "https://helpx.adobe.com/creative-cloud/release-note/cc-release-notes.html",
     "release-history"),
    # Transport control: a DIFFERENT Adobe host. Distinguishes "Adobe blocks this egress" from
    # "helpx.adobe.com specifically blocks this egress".
    ("control-adobe-www",
     "https://www.adobe.com/products/photoshop.html",
     "transport-control"),
    # Transport control on helpx itself, on a page that is not release history. Distinguishes
    # "helpx is unreachable" from "this document is unreachable".
    ("control-helpx-known-issues",
     "https://helpx.adobe.com/photoshop/kb/known-issues-photoshop.html",
     "transport-control"),
]

# Content markers. A 200 that carries none of these is a challenge page, a redirect landing or a
# shell that renders client-side -- none of which is a release-history document.
VERSION_RE = re.compile(r"\b2[0-9]\.[0-9]+(\.[0-9]+)?\b")
CHALLENGE_RE = re.compile(
    r"captcha|are you a human|access denied|request blocked|akamai|incapsula|"
    r"cf-browser-verification|challenge-platform|unusual traffic",
    re.I,
)


def probe(name: str, url: str, role: str, timeout: int = 30) -> dict:
    started = time.time()
    row = {"name": name, "url": url, "role": role}
    try:
        res = fetch_text(url, timeout=timeout, max_bytes=750_000)
        text = res.text or ""
        low = text.lower()
        row.update({
            "ok": True,
            "status": res.status,
            "final_url": res.final_url,
            "bytes": len(text),
            "elapsed_s": round(time.time() - started, 2),
            "mentions_photoshop": "photoshop" in low,
            "version_tokens": sorted(set(m.group(0) for m in VERSION_RE.finditer(text)))[:8],
            "looks_like_challenge": bool(CHALLENGE_RE.search(text)),
            # A release-history document has to carry BOTH the product and at least one version.
            "carries_release_identity": bool("photoshop" in low and VERSION_RE.search(text)),
        })
    except Exception as exc:                                  # noqa: BLE001 - every failure mode is data
        row.update({
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
            "elapsed_s": round(time.time() - started, 2),
        })
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", dest="out", default="")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--gap", type=float, default=6.0,
                    help="seconds between requests; the host rate-limits bursts")
    args = ap.parse_args()

    where = "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"
    print(f"# egress={where} runner={os.environ.get('RUNNER_OS', 'n/a')} ua={USER_AGENT[:48]}...",
          flush=True)

    # SPACED ON PURPOSE. helpx.adobe.com serves this document to a cold client and then answers
    # 403 to the same request shape after a burst -- measured locally: three variants returned
    # 200/67,998 bytes, and minutes later every variant including those three returned 403/472.
    # The block is reputation-based, not request-shaped, so a probe that hammers the host measures
    # its own rate limit instead of what a 24-hour production poll would see.
    rows = []
    for index, (name, url, role) in enumerate(CANDIDATES):
        if index:
            time.sleep(args.gap)
        row = probe(name, url, role, timeout=args.timeout)
        row["egress"] = where
        rows.append(row)
        print(json.dumps(row), flush=True)

    usable = [r for r in rows if r.get("carries_release_identity")
              and r["role"] == "release-history" and not r.get("looks_like_challenge")]
    print(f"\n# usable release-history endpoints from {where}: {len(usable)}", flush=True)
    for r in usable:
        print(f"#   {r['name']}  {r['bytes']} bytes  versions={r['version_tokens'][:4]}", flush=True)

    if args.out:
        Path(args.out).write_text(json.dumps({"egress": where, "rows": rows}, indent=2),
                                  encoding="utf-8")
    # Exit 0 regardless: a blocked source is a measurement, not a script failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
