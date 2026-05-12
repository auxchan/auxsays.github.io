#!/usr/bin/env python3
"""
Phase 1C — Blackmagic official-source static access probe.

Read-only. Does not write records, state files, or evidence rows.
Saves structured JSON output only.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "probe-output" / "phase1c"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AUXSAYSProbe/1.0; +https://auxsays.com/methodology)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Target URLs for this probe
URLS = {
    "press_release_specific": "https://www.blackmagicdesign.com/media/release/20260414-01",
    "press_release_listing": "https://www.blackmagicdesign.com/media",
    "support_page": "https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion",
    "download_page": "https://www.blackmagicdesign.com/support/download/20260414-01",
    "robots_txt": "https://www.blackmagicdesign.com/robots.txt",
    "sitemap_xml": "https://www.blackmagicdesign.com/sitemap.xml",
    "sitemap_index": "https://www.blackmagicdesign.com/sitemap_index.xml",
}

DAVINCI_VERSION_PATTERNS = [
    re.compile(r"DaVinci Resolve\s+(\d+(?:\.\d+)*(?:\s+(?:Public\s+)?Beta\s+\d+)?)", re.I),
    re.compile(r"Resolve\s+(\d+(?:\.\d+)*(?:\s+(?:Public\s+)?Beta\s+\d+)?)", re.I),
    re.compile(r"\b(\d{2}\.\d+(?:\.\d+)?)\b"),
    re.compile(r"\bVersion\s+(\d+(?:\.\d+)+)\b", re.I),
]

DOWNLOAD_EXTS = re.compile(r"\.(exe|dmg|zip|pkg|msi|deb|rpm)(\?|\"|\b)", re.I)

API_HINT_PATTERNS = [
    re.compile(r"""(fetch|XMLHttpRequest|axios\.get|\.ajax)\s*\(\s*['"`]([^'"`]+)['"`]"""),
    re.compile(r"""api[_/-]?(url|endpoint|path|base)['":\s]+(['"]/[^'"]+['"])""", re.I),
    re.compile(r"""(/api/v\d+/[^\s'"<>]+)"""),
    re.compile(r"""(/graphql[^\s'"<>]*)"""),
    re.compile(r"""(https?://[^'"<>\s]+/(?:api|json|data)/[^'"<>\s]+\.json)"""),
]


class HTMLExtractor(HTMLParser):
    """Lightweight HTML parser: extract tags, links, and inline scripts."""

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self.h1s: list[str] = []
        self._in_h1 = False
        self._h1_buf = ""
        self.links: list[str] = []
        self.meta_tags: list[dict[str, str]] = []
        self.scripts: list[str] = []
        self._in_script = False
        self._script_buf = ""
        self.canonical: str = ""
        self.rss_links: list[str] = []
        self.json_ld_blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
            self._h1_buf = ""
        elif tag == "a" and "href" in attr_dict:
            self.links.append(attr_dict["href"])
        elif tag == "link":
            rel = attr_dict.get("rel", "").lower()
            t = attr_dict.get("type", "").lower()
            href = attr_dict.get("href", "")
            if rel == "canonical":
                self.canonical = href
            if "rss" in t or "atom" in t or "rss" in rel or "alternate" in rel:
                self.rss_links.append(href)
        elif tag == "meta":
            name = attr_dict.get("name", attr_dict.get("property", ""))
            content = attr_dict.get("content", "")
            if name:
                self.meta_tags.append({"name": name, "content": content[:200]})
        elif tag == "script":
            self._in_script = True
            self._script_buf = ""
            if attr_dict.get("type", "").lower() == "application/ld+json":
                self._script_type = "json_ld"
            else:
                self._script_type = "js"

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
            if self._h1_buf.strip():
                self.h1s.append(self._h1_buf.strip())
        elif tag == "script":
            self._in_script = False
            if self._script_buf.strip():
                if self._script_type == "json_ld":
                    self.json_ld_blocks.append(self._script_buf.strip())
                else:
                    self.scripts.append(self._script_buf.strip())
            self._script_buf = ""

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_h1:
            self._h1_buf += data
        if self._in_script:
            self._script_buf += data


def fetch(url: str, timeout: int = 15) -> tuple[int, str, dict[str, str]]:
    """Fetch URL with polite headers. Returns (status, body, response_headers)."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(512 * 1024).decode("utf-8", errors="replace")
            headers = dict(resp.headers)
            return resp.status, body, headers
    except urllib.error.HTTPError as e:
        return e.code, "", {}
    except Exception as e:
        return -1, str(e), {}


def extract_version_strings(text: str) -> list[str]:
    found: list[str] = []
    for pat in DAVINCI_VERSION_PATTERNS:
        for m in pat.finditer(text):
            v = (m.group(1) if m.lastindex else m.group(0)).strip()
            if v not in found:
                found.append(v)
    return found[:20]


def extract_api_hints(scripts: list[str]) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    combined = "\n".join(scripts)
    for pat in API_HINT_PATTERNS:
        for m in pat.finditer(combined):
            endpoint = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)
            endpoint = endpoint.strip("'\"`")
            if endpoint not in [h["endpoint"] for h in hints]:
                hints.append({"pattern": pat.pattern[:60], "endpoint": endpoint})
        if len(hints) > 30:
            break
    return hints[:30]


def probe_url(label: str, url: str, delay: float = 1.0) -> dict[str, Any]:
    print(f"  Probing {label}: {url}")
    time.sleep(delay)
    status, body, resp_headers = fetch(url)
    result: dict[str, Any] = {
        "label": label,
        "url": url,
        "http_status": status,
        "fetch_ok": 200 <= status < 300,
        "response_length_chars": len(body),
        "content_type": resp_headers.get("Content-Type", resp_headers.get("content-type", "")),
    }
    if not result["fetch_ok"] or not body:
        result["error"] = body[:300] if body else "empty"
        return result

    # Plain text results (robots.txt, sitemap)
    if "xml" in result.get("content_type", "").lower() or url.endswith(".xml"):
        result["raw_excerpt"] = body[:2000]
        result["sitemap_urls_found"] = len(re.findall(r"<loc>", body))
        result["media_release_urls"] = re.findall(
            r"<loc>(https?://[^<]*media/release[^<]*)</loc>", body
        )[:10]
        return result
    if url.endswith("robots.txt"):
        result["raw_excerpt"] = body[:2000]
        return result

    # HTML parsing
    parser = HTMLExtractor()
    try:
        parser.feed(body)
    except Exception as e:
        result["parse_error"] = str(e)

    result["page_title"] = parser.title.strip()
    result["h1s"] = parser.h1s[:5]
    result["canonical"] = parser.canonical
    result["rss_links"] = parser.rss_links[:10]
    result["total_links"] = len(parser.links)
    result["meta_og_title"] = next(
        (m["content"] for m in parser.meta_tags if m["name"] in ("og:title", "twitter:title")), ""
    )
    result["meta_description"] = next(
        (m["content"] for m in parser.meta_tags if m["name"] in ("description", "og:description")), ""
    )[:200]

    # Media/release link discovery
    media_release_links = [l for l in parser.links if "/media/release/" in l]
    result["media_release_links_count"] = len(media_release_links)
    result["media_release_links_sample"] = media_release_links[:10]

    # Download link discovery
    download_links = [l for l in parser.links if DOWNLOAD_EXTS.search(l)]
    result["download_links_count"] = len(download_links)
    result["download_links_sample"] = download_links[:5]

    # Version string discovery
    result["version_strings_found"] = extract_version_strings(body)

    # JSON-LD structured data
    result["json_ld_blocks_count"] = len(parser.json_ld_blocks)
    result["json_ld_sample"] = [b[:400] for b in parser.json_ld_blocks[:3]]

    # API endpoint hints from inline JS
    result["inline_scripts_count"] = len(parser.scripts)
    result["api_hints"] = extract_api_hints(parser.scripts)

    # Look for embedded config/data objects in scripts
    combined_scripts = "\n".join(parser.scripts)
    config_patterns = [
        re.compile(r"(window\.__[A-Z_]+\s*=\s*\{[^}]{0,300})"),
        re.compile(r"(dataLayer\.push\([^)]{0,300}\))"),
        re.compile(r"(\"apiUrl\"\s*:\s*\"[^\"]+\")"),
        re.compile(r"(\"endpoint\"\s*:\s*\"[^\"]+\")"),
        re.compile(r"(\"baseUrl\"\s*:\s*\"[^\"]+\")"),
    ]
    config_matches: list[str] = []
    for cpat in config_patterns:
        for m in cpat.finditer(combined_scripts):
            snippet = m.group(1)[:200]
            if snippet not in config_matches:
                config_matches.append(snippet)
    result["embedded_config_snippets"] = config_matches[:10]

    return result


def main() -> None:
    print("Phase 1C — Blackmagic static source access probe")
    print(f"Output dir: {OUTPUT_DIR}")

    results: dict[str, Any] = {
        "probe_type": "blackmagic-static-source-access",
        "phase": "1C",
        "read_only": True,
        "playwright_available": False,
        "playwright_note": (
            "Playwright is not installed in this Replit environment. "
            "Only static (urllib) fetches are possible for this probe. "
            "Headless browser rendering requires separate setup."
        ),
        "probes": {},
    }

    for label, url in URLS.items():
        results["probes"][label] = probe_url(label, url, delay=1.5)

    # Cross-probe analysis
    pr_probe = results["probes"]["press_release_specific"]
    listing_probe = results["probes"]["press_release_listing"]
    support_probe = results["probes"]["support_page"]

    results["analysis"] = {
        "press_release_static_feasible": bool(
            pr_probe.get("version_strings_found")
            or (pr_probe.get("response_length_chars", 0) > 1000
                and pr_probe.get("fetch_ok"))
        ),
        "listing_has_release_links": (listing_probe.get("media_release_links_count", 0) > 0),
        "support_has_download_links": (support_probe.get("download_links_count", 0) > 0),
        "support_has_version_strings": bool(support_probe.get("version_strings_found")),
        "rss_feeds_found": (
            listing_probe.get("rss_links", [])
            + support_probe.get("rss_links", [])
            + pr_probe.get("rss_links", [])
        ),
        "any_api_hints": bool(
            pr_probe.get("api_hints")
            or listing_probe.get("api_hints")
            or support_probe.get("api_hints")
        ),
        "any_json_ld": bool(
            pr_probe.get("json_ld_blocks_count", 0)
            or listing_probe.get("json_ld_blocks_count", 0)
        ),
    }

    out_file = OUTPUT_DIR / "blackmagic-static-fetch-result.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nSaved: {out_file}")
    print("\n=== Summary ===")
    print(f"  Press release ({pr_probe['http_status']}): {pr_probe['response_length_chars']} chars")
    print(f"  Versions found on press release page: {pr_probe.get('version_strings_found', [])}")
    print(f"  Media release links on listing: {listing_probe.get('media_release_links_count', 0)}")
    print(f"  RSS feeds discovered: {results['analysis']['rss_feeds_found']}")
    print(f"  API hints found: {results['analysis']['any_api_hints']}")
    print(f"  JSON-LD blocks found: {results['analysis']['any_json_ld']}")
    robots = results["probes"].get("robots_txt", {})
    print(f"  robots.txt ({robots.get('http_status', '?')}): {robots.get('response_length_chars', 0)} chars")
    sitemap = results["probes"].get("sitemap_xml", {})
    print(f"  sitemap.xml ({sitemap.get('http_status', '?')}): {sitemap.get('response_length_chars', 0)} chars")


if __name__ == "__main__":
    main()
