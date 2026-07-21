#!/usr/bin/env python3
"""Tests for Elgato Help Center official release-note ingestion."""
from __future__ import annotations

import io
import sys
import traceback
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import elgato_help_center as elgato

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def source(product_id: str = "elgato-stream-deck") -> dict[str, object]:
    source_by_product = {
        "elgato-stream-deck": {
            "software": "Stream Deck",
            "official_url": "https://help.elgato.com/hc/en-us/sections/5162671529357-Elgato-Stream-Deck-Software-Release-Notes",
            "pattern": r"^Elgato Stream Deck (?P<version>[0-9]+(\.[0-9]+)+).*$",
        },
        "elgato-wave-link": {
            "software": "Wave Link",
            "official_url": "https://help.elgato.com/hc/en-us/sections/4913442828941-Wave-Link-Release-Notes",
            "pattern": r"^Elgato Wave Link (?P<version>[0-9]+(\.[0-9]+)+).*$",
        },
    }
    spec = source_by_product[product_id]
    return {
        "company_id": "elgato",
        "product_id": product_id,
        "company": "Elgato",
        "software": spec["software"],
        "public_category": "Streaming Tools",
        "ingestion": {
            "official_url": spec["official_url"],
            "version_pattern": spec["pattern"],
        },
    }


SECTION_URL = "https://help.elgato.com/hc/en-us/sections/5162671529357-Elgato-Stream-Deck-Software-Release-Notes"
ARTICLE_URL = "https://help.elgato.com/hc/en-us/articles/360028242011-Elgato-Stream-Deck-6-9-1-Release-Notes"
WAVE_URL = "https://help.elgato.com/hc/en-us/articles/111111111111-Elgato-Wave-Link-2-0-Release-Notes"

SECTION_HTML = f"""
<html>
  <body>
    <a href="/hc/en-us/articles/360028242011-Elgato-Stream-Deck-6-9-1-Release-Notes">Stream Deck release</a>
    <a href="{ARTICLE_URL}?foo=bar#comments">Duplicate with query</a>
    <a href="{WAVE_URL}">Wave Link release</a>
    <a href="/hc/en-us/search?query=stream">Search page</a>
    <a href="/hc/en-us/sections/1234-Other">Section page</a>
    <a href="https://example.com/hc/en-us/articles/999">External article</a>
    <a href="/hc/en-us/categories/200000000-Support">Category page</a>
    <a href="mailto:support@example.com">Mail</a>
  </body>
</html>
"""

ARTICLE_HTML = """
<html>
  <head>
    <title>Elgato Stream Deck 6.9.1 Release Notes | Elgato</title>
  </head>
  <body>
    <article>
      <h1>Elgato Stream Deck 6.9.1 Release Notes</h1>
      <time datetime="2026-06-18T12:34:56Z">June 18, 2026</time>
      <div class="article-body">
        <p>Elgato Stream Deck 6.9.1 includes fixes for plugin handling and OBS workflow stability.</p>
        <p>This is an official release-note article.</p>
      </div>
    </article>
  </body>
</html>
"""

WAVE_HTML = """
<html>
  <body>
    <h1>Elgato Wave Link 2.0 Release Notes</h1>
    <time datetime="2026-06-17">June 17, 2026</time>
    <div class="article-body">
      <p>Elgato Wave Link 2.0 changes audio routing behavior.</p>
    </div>
  </body>
</html>
"""


def run() -> int:
    print("=" * 60)
    print("Elgato Help Center adapter tests")
    print("=" * 60)

    links = elgato._article_links(SECTION_URL, SECTION_HTML, 2)
    check("section page discovers same-domain article links", ARTICLE_URL in links, str(links))
    check("same article is de-duplicated after query/fragment cleanup", links.count(ARTICLE_URL) == 1, str(links))
    check("unrelated same-domain product article remains a candidate before product filtering", WAVE_URL in links, str(links))
    check("external/search/category/section links are rejected", all("example.com" not in item and "/search" not in item and "/categories" not in item and "/sections" not in item for item in links), str(links))

    title = elgato._title_from_html(ARTICLE_HTML)
    body = elgato._body_from_html(ARTICLE_HTML)
    date = elgato._date_from_html(ARTICLE_HTML)
    version = elgato._version_from_pattern(source(), title, body)
    check("article title extracted", title == "Elgato Stream Deck 6.9.1 Release Notes", title)
    check("article body extracted", "OBS workflow stability" in body, body)
    check("article date extracted", date == "2026-06-18T12:34:56Z", date)
    check("version extracted from title", version == "6.9.1", version)

    responses = {
        SECTION_URL: SECTION_HTML,
        ARTICLE_URL: ARTICLE_HTML,
        WAVE_URL: WAVE_HTML,
    }

    original_fetch = elgato.fetch_text

    def fake_fetch(url: str, **_kwargs):
        clean = elgato._clean_url(url)
        return SimpleNamespace(text=responses[clean])

    try:
        elgato.fetch_text = fake_fetch
        records = elgato.fetch(source(), limit=3)
    finally:
        elgato.fetch_text = original_fetch

    check("product-specific acceptance keeps matching Stream Deck article only", len(records) == 1, str(records))
    record = records[0]
    check("matching record uses version", record.get("version") == "6.9.1", str(record))
    check("unrelated Wave Link article rejected for Stream Deck source", "Wave Link" not in record.get("title", ""), str(record))
    check("official source type is set", record.get("source_type") == "help_center_release_notes", str(record))
    check("official capture status is set", record.get("capture_status") == "captured-from-official-elgato-help-center", str(record))
    check("official summary is Elgato-specific", record.get("official_summary") == "Elgato published Stream Deck 6.9.1 release notes.", str(record))
    forbidden = {"report_count", "update_report_count", "consensus_label", "consensus_report", "evidence_state", "complaint_themes"}
    check("no consensus/report fields emitted", not (forbidden & set(record)), str(sorted(forbidden & set(record))))

    # === bounded network cost + honest diagnostics (Parts B / C) =================
    # This adapter issues one HTTP request per discovered article, so its network cost
    # must be bounded independent of the caller's candidate `limit` (which the runner
    # can set as wide as the 200 backfill window).
    def run_fetch(src, limit, section_html, article_map):
        """Fetch with a request-counting mock. Returns (records, total_http, per_url, stderr)."""
        responses = {elgato._clean_url(src["ingestion"]["official_url"]): section_html}
        for url, html in article_map.items():
            responses[elgato._clean_url(url)] = html
        per_url: dict[str, int] = {}

        def counting_fetch(url, **_kwargs):
            clean = elgato._clean_url(url)
            per_url[clean] = per_url.get(clean, 0) + 1
            if clean not in responses:
                raise KeyError(f"unexpected fetch: {clean}")
            return SimpleNamespace(text=responses[clean])

        original = elgato.fetch_text
        buf = io.StringIO()
        try:
            elgato.fetch_text = counting_fetch
            with redirect_stderr(buf):
                recs = elgato.fetch(src, limit=limit)
        finally:
            elgato.fetch_text = original
        return recs, sum(per_url.values()), per_url, buf.getvalue()

    sd = source("elgato-stream-deck")

    def sd_url(i: int) -> str:
        return f"https://help.elgato.com/hc/en-us/articles/{2000 + i}-Elgato-Stream-Deck-6-{i}-0-Release-Notes"

    def sd_html(i: int) -> str:
        return (f'<html><head><title>Elgato Stream Deck 6.{i}.0 Release Notes | Elgato</title></head>'
                f'<body><article><h1>Elgato Stream Deck 6.{i}.0 Release Notes</h1>'
                f'<time datetime="2026-06-{(i % 27) + 1:02d}T00:00:00Z">d</time>'
                f'<div class="article-body">Stream Deck 6.{i}.0 notes.</div></article></body></html>')

    # Section page advertising 30 matching Stream Deck release-note articles.
    many_urls = [sd_url(i) for i in range(30)]
    many_section = "<html><body>" + "".join(f'<a href="{u}">a</a>' for u in many_urls) + "</body></html>"
    many_articles = {u: sd_html(i) for i, u in enumerate(many_urls)}

    # 13. request count is bounded to the caller's small candidate budget
    _r8, total8, per8, _d8 = run_fetch(sd, 8, many_section, many_articles)
    check("limit=8: article fetches bounded to 8 (+1 section page = 9 total)", total8 == 9, str(total8))
    check("limit=8: no article page fetched more than once", all(v == 1 for v in per8.values()), str(per8))

    # 14. a caller passing 200 CANNOT cause unbounded article requests (adapter ceiling)
    r200, total200, _p200, d200 = run_fetch(sd, 200, many_section, many_articles)
    check("limit=200: article fetches HARD-CAPPED at ARTICLE_SCAN_CEILING, not 30", total200 == 1 + elgato.ARTICLE_SCAN_CEILING, str(total200))
    check("limit=200: request count independent of the section's link count (bounded, not exhaustive)", total200 < 1 + len(many_urls) and len(r200) <= elgato.ARTICLE_SCAN_CEILING, str((total200, len(r200))))

    # 15. the configured source cap (the limit the runner passes) is honored
    _r6, total6, _p6, _d6 = run_fetch(sd, 6, many_section, many_articles)
    check("limit=6: at most 6 article fetches (+1 section = 7 total)", total6 == 7, str(total6))

    # 20. ceiling exhaustion is reported honestly in diagnostics
    check("diagnostics report ceiling_reached=True when the ceiling bounds the run", "ceiling_reached=True" in d200, d200)
    check("diagnostics report articles_fetched at the ceiling value", f"articles_fetched={elgato.ARTICLE_SCAN_CEILING}" in d200, d200)
    check("diagnostics go to stderr with the adapter tag (never fabricated into records)", d200.strip().startswith("[elgato_help_center]"), d200)

    # 16. duplicate article links are fetched once
    dup = sd_url(0)
    dup_section = ("<html><body>"
                   f'<a href="{dup}">one</a>'
                   f'<a href="{dup}?utm=x#comments">same again</a>'
                   f'<a href="{sd_url(1)}">two</a>'
                   "</body></html>")
    r_dup, _t, per_dup, _d = run_fetch(sd, 8, dup_section, {sd_url(0): sd_html(0), sd_url(1): sd_html(1)})
    check("duplicate links (after query/fragment cleanup) are fetched exactly once", per_dup.get(elgato._clean_url(dup)) == 1, str(per_dup))
    check("de-duplicated section still yields 2 distinct records", len(r_dup) == 2, str(len(r_dup)))

    # 17. wrong-domain links are ignored (never fetched)
    ext = "https://malicious.example.com/hc/en-us/articles/9999-Elgato-Stream-Deck-9-9-9-Release-Notes"
    wd_section = f'<html><body><a href="{sd_url(0)}">valid</a><a href="{ext}">external</a></body></html>'
    r_wd, _t, per_wd, _d = run_fetch(sd, 8, wd_section, {sd_url(0): sd_html(0), ext: sd_html(99)})
    check("wrong-domain article link is never fetched", elgato._clean_url(ext) not in per_wd, str(per_wd))
    check("only the same-domain article becomes a record", len(r_wd) == 1, str(r_wd))

    # 18. non-matching product articles are fetched but rejected (never fabricated)
    help_url = "https://help.elgato.com/hc/en-us/articles/5555-How-To-Reset-Your-Device"
    help_html = ('<html><head><title>How to reset your device | Elgato</title></head>'
                 '<body><article><h1>How to reset your device</h1>'
                 '<div class="article-body">general help content</div></article></body></html>')
    nm_section = f'<html><body><a href="{help_url}">help</a><a href="{sd_url(0)}">release</a></body></html>'
    r_nm, _t, per_nm, d_nm = run_fetch(sd, 8, nm_section, {help_url: help_html, sd_url(0): sd_html(0)})
    check("non-matching product article is fetched (inspected) but produces no record", elgato._clean_url(help_url) in per_nm and all("Reset" not in (r.get("title") or "") for r in r_nm), str(r_nm))
    check("diagnostics count the non-match honestly (nonmatches=1)", "nonmatches=1" in d_nm, d_nm)

    # 19. a matching article after several non-matches is still reachable within the ceiling
    lead = [f"https://help.elgato.com/hc/en-us/articles/{7000 + i}-How-To-{i}" for i in range(5)]
    late_section = "<html><body>" + "".join(f'<a href="{u}">n</a>' for u in lead) + f'<a href="{sd_url(0)}">m</a></body></html>'
    lead_html = ('<html><head><title>How to | Elgato</title></head>'
                 '<body><article><h1>How to</h1><div class="article-body">x</div></article></body></html>')
    late_articles = {u: lead_html for u in lead}
    late_articles[sd_url(0)] = sd_html(0)
    r_late, _t, _p, _d = run_fetch(sd, 8, late_section, late_articles)
    check("a matching article after 5 non-matches is still reached within the ceiling", len(r_late) == 1 and r_late[0].get("version") == "6.0.0", str(r_late))

    # 21. no fabricated record on parser/DOM miss (missing version, or empty article DOM)
    nover_html = ('<html><head><title>Elgato Stream Deck Release Notes | Elgato</title></head>'
                  '<body><article><h1>Elgato Stream Deck Release Notes</h1>'
                  '<div class="article-body">No version number here.</div></article></body></html>')
    r_nv, _t, _p, d_nv = run_fetch(sd, 8, f'<html><body><a href="{sd_url(0)}">a</a></body></html>', {sd_url(0): nover_html})
    check("article with no extractable version yields NO record (fail-closed)", r_nv == [], str(r_nv))
    check("parser/version miss counted honestly in diagnostics (parser_misses=1)", "parser_misses=1" in d_nv, d_nv)
    r_dom, _t, _p, _d = run_fetch(sd, 8, f'<html><body><a href="{sd_url(0)}">a</a></body></html>', {sd_url(0): "<html><body></body></html>"})
    check("empty/garbage article DOM yields NO fabricated record", r_dom == [], str(r_dom))

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
