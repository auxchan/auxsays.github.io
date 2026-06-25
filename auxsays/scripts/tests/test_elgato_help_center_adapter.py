#!/usr/bin/env python3
"""Tests for Elgato Help Center official release-note ingestion."""
from __future__ import annotations

import sys
import traceback
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
