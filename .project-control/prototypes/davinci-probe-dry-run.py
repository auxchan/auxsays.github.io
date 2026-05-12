#!/usr/bin/env python3
"""DaVinci Resolve official source dry-run probe.

Phase 1A research script. Read-only. Does not write any records, does not
modify state, does not touch consensus_evidence.yml or any generated file.

Purpose:
  - Probe the Blackmagic press release URL that has previously returned
    `official-source-parser-failed`.
  - Attempt the generic html_changelog body extraction path.
  - Attempt a custom div-selector extraction path.
  - Report what each approach extracts (or fails to extract).
  - Probe the /media listing page and report whether link discovery is possible
    via static fetch.
  - Report version string normalization against the current version_pattern.

Usage:
  python3 .project-control/prototypes/davinci-probe-dry-run.py

  Optional: pass a specific press release URL as first argument, e.g.
  python3 .project-control/prototypes/davinci-probe-dry-run.py \
      https://www.blackmagicdesign.com/media/release/20260414-01

  To save output for review:
  python3 .project-control/prototypes/davinci-probe-dry-run.py \
      > .project-control/probe-output/davinci-probe-$(date +%Y%m%d).json

Requirements:
  Run from the repo root. Adds auxsays/scripts to sys.path to reuse lib.http
  and lib.normalize if available; falls back to urllib if not.

Output:
  JSON-formatted probe report printed to stdout.
  Does not write files. Safe to run in any environment.
"""
from __future__ import annotations

import json
import re
import sys
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

# ---------------------------------------------------------------------------
# Path setup — reuse project lib if available, fall back to stdlib only
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
AUXSAYS_SCRIPTS = REPO_ROOT / "auxsays" / "scripts"

_lib_available = False
if AUXSAYS_SCRIPTS.exists() and str(AUXSAYS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AUXSAYS_SCRIPTS))
    try:
        from lib.http import fetch_text  # type: ignore
        from lib.normalize import strip_tags  # type: ignore
        _lib_available = True
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Probe targets
# ---------------------------------------------------------------------------

DEFAULT_PRESS_RELEASE_URL = "https://www.blackmagicdesign.com/media/release/20260414-01"
LISTING_URL = "https://www.blackmagicdesign.com/media"
SUPPORT_URL = "https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion"

# Matches the config version_pattern (current — requires two numeric components)
CURRENT_VERSION_PATTERN = re.compile(r"^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$")
# Proposed relaxed pattern (allows major-only)
RELAXED_VERSION_PATTERN = re.compile(r"^(v)?(?P<version>[0-9]+(\.[0-9]+)*.*)$")

# Generic body selectors (current adapter path)
ARTICLE_RE = re.compile(r"<article\b[^>]*>(.*?)</article>", re.I | re.S)
MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.I | re.S)

# Custom div selectors to probe for Blackmagic press release pages
BLACKMAGIC_DIV_PATTERNS = [
    re.compile(r'<div[^>]+class=["\'][^"\']*(?:press-release|article-body|release-content|content-body|editorial|media-body)[^"\']*["\'][^>]*>(.*?)</div>', re.I | re.S),
    re.compile(r'<div[^>]+class=["\'][^"\']*(?:body|content|main-content|entry-content)[^"\']*["\'][^>]*>(.*?)</div>', re.I | re.S),
    re.compile(r'<section[^>]+class=["\'][^"\']*(?:content|body|main)[^"\']*["\'][^>]*>(.*?)</section>', re.I | re.S),
]

DATE_RE = re.compile(r"([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})")
LINK_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
GENERIC_EXCLUDE_RE = re.compile(r"/(tag|tags|category|categories|author|page|feed|rss|atom)/", re.I)

# Version strings used in recent DaVinci releases — for normalization testing
DAVINCI_VERSION_SAMPLES = [
    "DaVinci Resolve 21 Public Beta 1",
    "DaVinci Resolve 21 Public Beta 2",
    "DaVinci Resolve 21",
    "DaVinci Resolve 21.0.1",
    "DaVinci Resolve 20.0.0",
    "DaVinci Resolve 19.1",
    "v21.0.1",
    "21",
    "21.0.1",
    "21 Public Beta 1",
]

# ---------------------------------------------------------------------------
# Stdlib-only fetch fallback
# ---------------------------------------------------------------------------

def _stdlib_fetch(url: str, timeout: int = 30) -> tuple[str, int]:
    """Fetch URL using urllib only. Returns (text, status_code)."""
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AUXSAYS-probe/1a; research-only)",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([^\s;]+)", ct)
            if m:
                charset = m.group(1)
            body = resp.read(500_000).decode(charset, errors="replace")
            return body, resp.status
    except URLError as e:
        return f"[fetch error: {e}]", 0


def fetch_html(url: str) -> tuple[str, int]:
    if _lib_available:
        try:
            r = fetch_text(url, timeout=30, retries=0)
            return r.text, getattr(r, "status_code", 200)
        except Exception as e:
            return f"[fetch error: {e}]", 0
    return _stdlib_fetch(url)

# ---------------------------------------------------------------------------
# Strip tags (stdlib-only fallback)
# ---------------------------------------------------------------------------

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

def _strip(html: str) -> str:
    if _lib_available:
        return strip_tags(html)
    text = TAG_RE.sub(" ", html)
    return WHITESPACE_RE.sub(" ", text).strip()

# ---------------------------------------------------------------------------
# Probe functions
# ---------------------------------------------------------------------------

def probe_press_release(url: str) -> dict:
    result: dict = {"url": url, "adapter_path": {}, "custom_selectors": {}, "meta": {}}

    html, status = fetch_html(url)
    result["meta"]["http_status"] = status
    result["meta"]["fetch_ok"] = status == 200 and not html.startswith("[fetch error")
    result["meta"]["response_length_chars"] = len(html)

    if not result["meta"]["fetch_ok"]:
        result["meta"]["error"] = html[:200]
        return result

    # --- Current adapter path (article/main) ---
    article_m = ARTICLE_RE.search(html)
    main_m = MAIN_RE.search(html)
    result["adapter_path"]["article_tag_found"] = bool(article_m)
    result["adapter_path"]["main_tag_found"] = bool(main_m)

    for tag, match in [("article", article_m), ("main", main_m)]:
        if match:
            body = _strip(match.group(1))
            result["adapter_path"][f"{tag}_body_length"] = len(body)
            result["adapter_path"][f"{tag}_body_excerpt"] = body[:300]

    # Simulate body_matches_record check (version must appear in body)
    test_version = "21"
    test_product = "davinci resolve"
    for tag, match in [("article", article_m), ("main", main_m)]:
        if match:
            body = _strip(match.group(1)).lower()
            passes = (test_product in body or test_version in body) and len(body.strip()) >= 300
            result["adapter_path"][f"{tag}_passes_body_match_check"] = passes

    # --- Custom div selectors ---
    result["custom_selectors"]["attempts"] = []
    for i, pat in enumerate(BLACKMAGIC_DIV_PATTERNS):
        m = pat.search(html)
        attempt: dict = {"pattern_index": i, "found": bool(m)}
        if m:
            body = _strip(m.group(1))
            attempt["body_length"] = len(body)
            attempt["body_excerpt"] = body[:300]
            attempt["passes_body_match_check"] = (
                (test_product in body.lower() or test_version in body.lower()) and len(body.strip()) >= 300
            )
        result["custom_selectors"]["attempts"].append(attempt)

    # --- H1/title extraction (for title probe) ---
    h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    result["meta"]["h1"] = _strip(h1_m.group(1)) if h1_m else None
    result["meta"]["page_title"] = _strip(title_m.group(1)) if title_m else None

    # --- Date extraction from first 8000 chars ---
    text_sample = _strip(html[:8000])
    date_m = DATE_RE.search(text_sample)
    result["meta"]["date_extracted"] = date_m.group(1) if date_m else None

    # --- Check if URL date prefix is usable ---
    url_date_m = re.search(r"/(\d{8})-\d+/?$", url)
    result["meta"]["url_date_prefix"] = url_date_m.group(1) if url_date_m else None

    return result


def probe_listing_page() -> dict:
    result: dict = {"url": LISTING_URL, "link_discovery": {}}

    html, status = fetch_html(LISTING_URL)
    result["http_status"] = status
    result["fetch_ok"] = status == 200 and not html.startswith("[fetch error")
    result["response_length_chars"] = len(html)

    if not result["fetch_ok"]:
        result["error"] = html[:200]
        return result

    # Count all <a> tags
    all_links = LINK_RE.findall(html)
    result["link_discovery"]["total_anchor_tags"] = len(all_links)

    # Apply generic changelog filter
    candidate_links = []
    for href, text in all_links:
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        absolute = urljoin(LISTING_URL, href)
        path = urlparse(absolute).path
        if GENERIC_EXCLUDE_RE.search(path):
            continue
        haystack = (path + " " + _strip(text)).lower()
        if any(token in haystack for token in ["/changelog/", "/release-notes/", "/releases/"]):
            candidate_links.append(absolute)
    result["link_discovery"]["generic_filter_candidates"] = len(candidate_links)
    result["link_discovery"]["generic_filter_sample"] = candidate_links[:5]

    # Check for /media/release/ pattern links (DaVinci-specific)
    release_links = []
    for href, text in all_links:
        if not href:
            continue
        absolute = urljoin(LISTING_URL, href)
        if re.search(r"/media/release/\d{8}", absolute):
            release_links.append(absolute)
    result["link_discovery"]["blackmagic_release_links"] = len(release_links)
    result["link_discovery"]["blackmagic_release_sample"] = list(dict.fromkeys(release_links))[:10]

    # Check for JS rendering indicators
    result["link_discovery"]["likely_js_rendered"] = (
        len(all_links) < 10 or len(html) < 5000
    )
    result["link_discovery"]["note"] = (
        "If likely_js_rendered=true, the listing page is a JavaScript shell and "
        "static fetch will not discover release links. URL construction strategy required."
    )

    return result


def probe_version_normalization() -> dict:
    results = []
    for sample in DAVINCI_VERSION_SAMPLES:
        current_match = CURRENT_VERSION_PATTERN.match(sample)
        relaxed_match = RELAXED_VERSION_PATTERN.match(sample)
        results.append({
            "input": sample,
            "current_pattern_matches": bool(current_match),
            "current_version_extracted": current_match.group("version") if current_match else None,
            "relaxed_pattern_matches": bool(relaxed_match),
            "relaxed_version_extracted": relaxed_match.group("version") if relaxed_match else None,
        })
    return {"samples": results}


def probe_support_page() -> dict:
    result: dict = {"url": SUPPORT_URL}
    html, status = fetch_html(SUPPORT_URL)
    result["http_status"] = status
    result["fetch_ok"] = status == 200 and not html.startswith("[fetch error")
    result["response_length_chars"] = len(html)

    if not result["fetch_ok"]:
        result["error"] = html[:200]
        return result

    # Look for version strings in page text
    text = _strip(html[:20000])
    version_mentions = re.findall(r"DaVinci Resolve\s+[\d\.]+(?:\s+Public\s+Beta\s+\d+)?", text)
    result["version_strings_found"] = list(dict.fromkeys(version_mentions))[:10]

    # Look for download links
    all_links = LINK_RE.findall(html)
    download_links = [urljoin(SUPPORT_URL, h) for h, t in all_links
                      if re.search(r"\.(zip|dmg|exe|pkg|AppImage|run)", h, re.I)]
    result["download_links_found"] = len(download_links)
    result["download_link_sample"] = download_links[:5]

    return result

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    press_release_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PRESS_RELEASE_URL

    print("[AUXSAYS Phase 1A] DaVinci official source dry-run probe", file=sys.stderr)
    print(f"  Press release URL: {press_release_url}", file=sys.stderr)
    print(f"  Listing URL: {LISTING_URL}", file=sys.stderr)
    print(f"  Lib available: {_lib_available}", file=sys.stderr)
    print("", file=sys.stderr)

    report = {
        "probe_type": "davinci-official-source-dry-run",
        "phase": "1A",
        "read_only": True,
        "writes_records": False,
        "lib_available": _lib_available,
        "press_release_probe": probe_press_release(press_release_url),
        "listing_page_probe": probe_listing_page(),
        "version_normalization": probe_version_normalization(),
        "support_page_probe": probe_support_page(),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
