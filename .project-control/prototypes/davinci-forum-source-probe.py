#!/usr/bin/env python3
"""
Phase 1C — DaVinci user-report source discovery probe.

Read-only. Checks public accessibility of Blackmagic forum and Reddit
r/davinciresolve for DaVinci Resolve user reports.
Saves structured JSON output only. Does not scrape at volume.
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

REDDIT_HEADERS = {
    "User-Agent": "AUXSAYSProbe/1.0 (research probe; +https://auxsays.com/methodology)",
    "Accept": "application/json",
}

# Target sources
SOURCES = {
    "blackmagic_forum_index": "https://forum.blackmagicdesign.com/",
    "blackmagic_forum_davinci": "https://forum.blackmagicdesign.com/viewforum.php?f=21",
    "blackmagic_forum_search": "https://forum.blackmagicdesign.com/search.php?keywords=resolve+21+beta&fid[]=21",
    "reddit_davinciresolve": "https://www.reddit.com/r/davinciresolve/",
    "reddit_davinci_new_json": "https://www.reddit.com/r/davinciresolve/new.json?limit=5",
    "reddit_davinci_search_json": "https://www.reddit.com/r/davinciresolve/search.json?q=resolve+21+beta&restrict_sr=1&sort=new&limit=5",
    "reddit_davinci_rss": "https://www.reddit.com/r/davinciresolve/.rss",
}

THREAD_TITLE_PATTERNS = [
    re.compile(r"DaVinci Resolve\s+\d+", re.I),
    re.compile(r"Resolve\s+\d+\s*(?:Beta|Public Beta|Update|Update\s+\d+)", re.I),
    re.compile(r"(?:bug|crash|freeze|issue|problem|fix|broken|glitch|error).{0,30}resolve", re.I),
    re.compile(r"resolve.{0,30}(?:bug|crash|freeze|issue|problem|fix|broken|glitch|error)", re.I),
]

FORUM_PATTERNS = {
    "thread_links": re.compile(r'href="([^"]*viewtopic[^"]*)"'),
    "post_count": re.compile(r"(\d+)\s+(?:topics?|posts?|replies?)", re.I),
    "login_wall": re.compile(r"(?:login|sign.?in|please.{0,20}register|must.{0,20}logged)", re.I),
    "anti_scrape": re.compile(r"(?:captcha|cloudflare|access.denied|403|blocked)", re.I),
}


class TitleExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self.h1s: list[str] = []
        self._in_h1 = False
        self._h1_buf = ""
        self.h2s: list[str] = []
        self._in_h2 = False
        self._h2_buf = ""
        self.links: list[tuple[str, str]] = []
        self._in_link = False
        self._link_href = ""
        self._link_buf = ""
        self.page_text_sample = ""
        self._text_buf = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
            self._h1_buf = ""
        elif tag == "h2":
            self._in_h2 = True
            self._h2_buf = ""
        elif tag == "a":
            self._in_link = True
            self._link_href = attr_dict.get("href", "")
            self._link_buf = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
            if self._h1_buf.strip():
                self.h1s.append(self._h1_buf.strip())
        elif tag == "h2":
            self._in_h2 = False
            if self._h2_buf.strip():
                self.h2s.append(self._h2_buf.strip())
        elif tag == "a":
            self._in_link = False
            if self._link_href and self._link_buf.strip():
                self.links.append((self._link_href, self._link_buf.strip()))
            self._link_href = ""
            self._link_buf = ""

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_h1:
            self._h1_buf += data
        if self._in_h2:
            self._h2_buf += data
        if self._in_link:
            self._link_buf += data
        if len(self._text_buf) < 3000:
            self._text_buf += data
        self.page_text_sample = self._text_buf


def fetch(url: str, headers: dict | None = None, timeout: int = 15) -> tuple[int, str, str]:
    """Fetch URL. Returns (status, body, content_type)."""
    h = headers or HEADERS
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(256 * 1024).decode("utf-8", errors="replace")
            ct = resp.headers.get("Content-Type", "")
            return resp.status, body, ct
    except urllib.error.HTTPError as e:
        return e.code, "", ""
    except Exception as e:
        return -1, str(e), ""


def probe_source(label: str, url: str, use_reddit_headers: bool = False, delay: float = 2.0) -> dict[str, Any]:
    print(f"  Probing {label}: {url}")
    time.sleep(delay)
    headers = REDDIT_HEADERS if use_reddit_headers else HEADERS
    status, body, content_type = fetch(url, headers=headers)

    result: dict[str, Any] = {
        "label": label,
        "url": url,
        "http_status": status,
        "fetch_ok": 200 <= status < 300,
        "response_length_chars": len(body),
        "content_type": content_type,
        "is_json": "json" in content_type.lower() or url.endswith(".json"),
        "is_rss": "xml" in content_type.lower() or url.endswith(".rss"),
    }

    if not result["fetch_ok"] or not body:
        result["error"] = body[:300] if body else "empty response"
        result["access"] = "denied" if status == 403 else ("not_found" if status == 404 else "error")
        return result

    result["access"] = "public"

    # JSON response (Reddit API)
    if result["is_json"]:
        try:
            data = json.loads(body)
            posts = []
            try:
                children = data["data"]["children"]
                for child in children[:5]:
                    d = child.get("data", {})
                    title = d.get("title", "")
                    matches = any(pat.search(title) for pat in THREAD_TITLE_PATTERNS)
                    posts.append({
                        "title": title[:120],
                        "score": d.get("score"),
                        "created_utc": d.get("created_utc"),
                        "num_comments": d.get("num_comments"),
                        "permalink": d.get("permalink", "")[:80],
                        "matches_davinci_pattern": matches,
                    })
            except (KeyError, TypeError):
                pass
            result["json_post_count"] = len(posts)
            result["posts_sample"] = posts
            result["structured_accessible"] = True
            result["rate_limited"] = ("ratelimit" in body.lower() or status == 429)
        except json.JSONDecodeError as e:
            result["json_parse_error"] = str(e)[:100]
            result["json_excerpt"] = body[:400]
        return result

    # RSS response
    if result["is_rss"]:
        items = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", body)
        titles = [(a or b).strip() for a, b in items if (a or b).strip()]
        result["rss_item_count"] = len(titles)
        result["rss_titles_sample"] = titles[:10]
        result["structured_accessible"] = True
        return result

    # HTML response
    parser = TitleExtractor()
    try:
        parser.feed(body)
    except Exception:
        pass

    result["page_title"] = parser.title.strip()
    result["h1s"] = parser.h1s[:3]
    result["h2s"] = parser.h2s[:5]

    # Login wall / anti-scrape detection
    text_lower = body.lower()
    result["login_wall_detected"] = bool(
        FORUM_PATTERNS["login_wall"].search(text_lower)
        and ("viewtopic" not in body and "davinci" not in text_lower[:5000])
    )
    result["anti_scrape_detected"] = bool(FORUM_PATTERNS["anti_scrape"].search(text_lower))

    # Forum-specific extractions
    thread_links = FORUM_PATTERNS["thread_links"].findall(body)
    result["thread_link_count"] = len(thread_links)
    result["thread_links_sample"] = thread_links[:5]

    # Davinci-matching thread titles from anchor text
    matching_titles: list[str] = []
    for href, text in parser.links:
        if any(pat.search(text) for pat in THREAD_TITLE_PATTERNS):
            matching_titles.append(text[:120])
    result["davinci_matching_titles"] = matching_titles[:10]

    # Check for pagination signals
    result["has_pagination"] = bool(
        re.search(r"(?:page|next|prev|older|newer).{0,30}(?:\d+|page)", body, re.I)
    )

    # Check if search is available
    result["search_form_present"] = bool(
        re.search(r'<input[^>]+(?:search|query|q)[^>]*>', body, re.I)
        or re.search(r'action="[^"]*search[^"]*"', body, re.I)
    )

    # Look for version/date metadata
    result["version_strings_found"] = []
    for pat in [
        re.compile(r"DaVinci Resolve\s+\d+(?:\.\d+)*(?:\s+(?:Public\s+)?Beta\s+\d+)?", re.I),
        re.compile(r"Resolve\s+\d+(?:\.\d+)*", re.I),
    ]:
        for m in pat.finditer(body):
            v = m.group(0).strip()
            if v not in result["version_strings_found"]:
                result["version_strings_found"].append(v)
    result["version_strings_found"] = result["version_strings_found"][:10]

    return result


def main() -> None:
    print("Phase 1C — DaVinci user-report source discovery probe")
    print(f"Output dir: {OUTPUT_DIR}")

    results: dict[str, Any] = {
        "probe_type": "davinci-user-report-source-discovery",
        "phase": "1C",
        "read_only": True,
        "probes": {},
    }

    for label, url in SOURCES.items():
        use_reddit = "reddit" in label
        results["probes"][label] = probe_source(label, url, use_reddit_headers=use_reddit, delay=2.0)

    # Summary analysis
    forum = results["probes"].get("blackmagic_forum_index", {})
    forum_dr = results["probes"].get("blackmagic_forum_davinci", {})
    reddit_html = results["probes"].get("reddit_davinciresolve", {})
    reddit_json = results["probes"].get("reddit_davinci_new_json", {})
    reddit_rss = results["probes"].get("reddit_davinci_rss", {})

    results["summary"] = {
        "blackmagic_forum_accessible": forum.get("access") == "public",
        "blackmagic_forum_davinci_section_accessible": forum_dr.get("access") == "public",
        "blackmagic_forum_login_wall": forum_dr.get("login_wall_detected", True),
        "reddit_html_accessible": reddit_html.get("access") == "public",
        "reddit_json_api_accessible": reddit_json.get("access") == "public",
        "reddit_rss_accessible": reddit_rss.get("access") == "public",
        "reddit_json_structured": reddit_json.get("structured_accessible", False),
        "reddit_rss_structured": reddit_rss.get("structured_accessible", False),
    }

    out_file = OUTPUT_DIR / "davinci-source-matrix.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nSaved: {out_file}")

    print("\n=== Summary ===")
    for k, v in results["summary"].items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
