#!/usr/bin/env python3
"""Tests for the reusable Zendesk Help Center official release-note adapter.

Covers the sprint's required surface: pagination + loop protection, section scoping,
exact title/version matching, false-product rejection, malformed responses, 403/429
propagation, duplicate articles, missing version/date, body normalization, bounded
requests, no-results, historical + current fixtures, platform-split version dedup,
and four-product isolation across the Elgato ecosystem.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import traceback
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import zendesk_help_center as zendesk
import patch_ingest

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


HOST = "help.elgato.com"

SECTIONS = {
    "elgato-stream-deck": 5162671529357,
    "elgato-wave-link": 4913442828941,
    "elgato-camera-hub": 4880787756941,
    "elgato-4k-capture-utility": 5126053814029,
}

SOFTWARE = {
    "elgato-stream-deck": ("Stream Deck", r"^Elgato Stream Deck (?P<version>[0-9]+(\.[0-9]+)+).*$", ["stream deck"]),
    "elgato-wave-link": ("Wave Link", r"^Elgato Wave Link (?P<version>[0-9]+(\.[0-9]+)+).*$", ["wave link"]),
    "elgato-camera-hub": ("Camera Hub", r"^Elgato Camera Hub (?P<version>[0-9]+(\.[0-9]+)+).*$", ["camera hub"]),
    "elgato-4k-capture-utility": ("4K Capture Utility", r"^Elgato 4K Capture Utility (?P<version>[0-9]+(\.[0-9]+)+).*$", ["4k capture utility", "4k capture"]),
}


def source(product_id: str = "elgato-stream-deck", **ingestion_overrides) -> dict:
    software, pattern, terms = SOFTWARE[product_id]
    section_id = SECTIONS[product_id]
    ingestion = {
        "adapter": "zendesk_help_center",
        "type": "help_center_release_notes",
        "official_url": f"https://{HOST}/hc/en-us/sections/{section_id}-Release-Notes",
        "version_pattern": pattern,
        "product_terms": terms,
    }
    ingestion.update(ingestion_overrides)
    return {
        "company_id": "elgato",
        "product_id": product_id,
        "company": "Elgato",
        "software": software,
        "public_category": "Streaming Tools",
        "ingestion": ingestion,
    }


def article(section_id: int, article_id: int, title: str, created: str, *,
            body: str = "", draft: bool = False, locale: str = "en-us",
            host: str = HOST) -> dict:
    slug = title.replace(" ", "-").replace(".", "-")
    return {
        "id": article_id,
        "section_id": section_id,
        "title": title,
        "created_at": created,
        "updated_at": created,
        "draft": draft,
        "locale": locale,
        "html_url": f"https://{host}/hc/en-us/articles/{article_id}-{slug}",
        "body": body or f"<p>{title} official changes.</p>",
        "label_names": ["Release Notes"],
    }


def page(articles: list[dict], *, count: int | None = None, next_page: str | None = None) -> str:
    return json.dumps({
        "count": count if count is not None else len(articles),
        "page": 1,
        "page_count": 1,
        "per_page": 100,
        "next_page": next_page,
        "previous_page": None,
        "articles": articles,
    })


def run_fetch(src: dict, responses: dict[str, str], limit: int = 200):
    """Fetch with a request-counting mock. Returns (records_or_exc, requests, stderr)."""
    reqs: list[str] = []
    original = zendesk.fetch_text

    def fake_fetch(url: str, **kwargs):
        reqs.append(url)
        if url not in responses:
            raise KeyError(f"unexpected fetch: {url}")
        payload = responses[url]
        if isinstance(payload, Exception):
            raise payload
        return SimpleNamespace(text=payload, _options=kwargs)

    buf = io.StringIO()
    outcome = None
    raised = None
    try:
        zendesk.fetch_text = fake_fetch
        with redirect_stderr(buf):
            try:
                outcome = zendesk.fetch(src, limit=limit)
            except Exception as exc:  # noqa: BLE001 -- assertions inspect the failure
                raised = exc
    finally:
        zendesk.fetch_text = original
    return outcome, raised, reqs, buf.getvalue()


def default_list_url(product_id: str = "elgato-stream-deck") -> str:
    sid = SECTIONS[product_id]
    return (f"https://{HOST}/api/v2/help_center/en-us/sections/{sid}/articles.json"
            f"?per_page=100&sort_by=created_at&sort_order=desc")


# Real-shaped fixtures captured from the live anonymous Elgato Help Center API.
CURRENT_FIXTURE = {
    "id": 49238316077713,
    "section_id": 5162671529357,
    "title": "Elgato Stream Deck 7.5.1 Release Notes",
    "created_at": "2026-07-28T16:39:48Z",
    "updated_at": "2026-08-11T16:57:42Z",
    "draft": False,
    "locale": "en-us",
    "html_url": "https://help.elgato.com/hc/en-us/articles/49238316077713-Elgato-Stream-Deck-7-5-1-Release-Notes",
    "body": ("<p><strong>Release Date</strong> : 28 July 2026</p>"
             "<p>\U0001f4bb Download Links</p><p>macOS Elgato Stream Deck 7.5.1.pkg</p>"
             "<p>Windows Elgato Stream Deck 7.5.1.msi</p>"
             "<h2>What's new in Stream Deck 7.5.1?</h2>"
             "<p>This update focuses on bug fixes and performance improvements.</p>"),
    "label_names": ["popular-topics-announcement", "Release Notes", "Changelog", "Stream Deck 7.5.1", "7.5.1"],
}
HISTORICAL_FIXTURE = {
    "id": 7113977745293,
    "section_id": 5162671529357,
    "title": "Elgato Stream Deck 5.2.1 Release Notes",
    "created_at": "2022-03-29T23:45:55Z",
    "updated_at": "2022-03-30T00:00:00Z",
    "draft": False,
    "locale": "en-us",
    "html_url": "https://help.elgato.com/hc/en-us/articles/7113977745293-Elgato-Stream-Deck-5-2-1-Release-Notes",
    "body": "<p>Elgato Stream Deck 5.2.1 improves profile handling and plugin stability.</p>",
    "label_names": ["Release Notes"],
}


def run() -> int:
    print("=" * 60)
    print("Zendesk Help Center adapter tests")
    print("=" * 60)

    sd = source()
    sd_section = SECTIONS["elgato-stream-deck"]

    # --- fixtures: current + historical real-shaped articles -------------------------
    records, raised, reqs, diag = run_fetch(sd, {default_list_url(): page([CURRENT_FIXTURE, HISTORICAL_FIXTURE])})
    check("current + historical fixtures both accepted", raised is None and len(records) == 2, str(raised or records))
    if records and len(records) == 2:
        current, historical = records[0], records[1]
        check("current fixture: exact version extracted from title", current["version"] == "7.5.1", str(current["version"]))
        check("current fixture: ISO release date from created_at", current["published_at"] == "2026-07-28T16:39:48Z", str(current["published_at"]))
        check("historical fixture: 2022 article keeps its historical date", historical["published_at"].startswith("2022-03-29"), str(historical["published_at"]))
        check("record identity carries product + version", current["record_id"].startswith("zendesk:elgato-stream-deck:7.5.1:"), current["record_id"])
        check("source_url is the official article page on the configured host", current["source_url"].startswith(f"https://{HOST}/hc/en-us/articles/"), current["source_url"])
        check("official_url is the configured section page", current["official_url"] == sd["ingestion"]["official_url"], current["official_url"])
        check("body is normalized text (tags stripped, whitespace collapsed)", "<p>" not in current["body"] and "What's new in Stream Deck 7.5.1?" in current["body"], current["body"][:200])
        check("capture status marks the Zendesk API lane", current["capture_status"] == "captured-from-zendesk-help-center-api", current["capture_status"])
        check("official summary is vendor-specific", current["official_summary"] == "Elgato published Stream Deck 7.5.1 release notes.", current["official_summary"])
        forbidden = {"report_count", "update_report_count", "consensus_label", "consensus_report", "evidence_state", "complaint_themes"}
        check("no consensus/report fields emitted", not (forbidden & set(current)), str(sorted(forbidden & set(current))))
    check("single-page section costs exactly one HTTP request", len(reqs) == 1, str(reqs))
    check("diagnostics emitted to stderr with the adapter tag", diag.strip().startswith("[zendesk_help_center]"), diag[:120])

    # --- request bounds: byte cap always passed to the transport ---------------------
    reqs_opts: list[dict] = []
    original = zendesk.fetch_text

    def opts_fetch(url, **kwargs):
        reqs_opts.append(kwargs)
        return SimpleNamespace(text=page([CURRENT_FIXTURE]))

    try:
        zendesk.fetch_text = opts_fetch
        with redirect_stderr(io.StringIO()):
            zendesk.fetch(sd, limit=5)
    finally:
        zendesk.fetch_text = original
    check("every list request carries a hard byte cap", reqs_opts and all(o.get("max_bytes") == zendesk.MAX_RESPONSE_BYTES for o in reqs_opts), str(reqs_opts))
    check("every list request carries a bounded timeout", reqs_opts and all(isinstance(o.get("timeout"), int) and o["timeout"] <= 60 for o in reqs_opts), str(reqs_opts))

    # --- pagination: multi-page section is swept in order ---------------------------
    page2_url = default_list_url() + "&page=2"
    a_new = article(sd_section, 101, "Elgato Stream Deck 9.1.0 Release Notes", "2026-08-01T00:00:00Z")
    a_old = article(sd_section, 102, "Elgato Stream Deck 9.0.0 Release Notes", "2026-07-01T00:00:00Z")
    records, raised, reqs, diag = run_fetch(sd, {
        default_list_url(): page([a_new], count=2, next_page=page2_url),
        page2_url: page([a_old], count=2),
    })
    check("pagination follows next_page and merges pages", raised is None and [r["version"] for r in records] == ["9.1.0", "9.0.0"], str(raised or records))
    check("pagination fetched exactly the advertised pages", len(reqs) == 2, str(reqs))
    check("diagnostics report pages_fetched=2", "pages_fetched=2" in diag, diag[:200])

    # --- pagination loop protection: self-pointing next_page terminates --------------
    records, raised, reqs, diag = run_fetch(sd, {
        default_list_url(): page([a_new], count=99, next_page=default_list_url()),
    })
    check("self-pointing next_page terminates after one fetch (no loop)", raised is None and len(reqs) == 1, str(reqs))
    check("loop termination is surfaced as pagination_truncated=True", "pagination_truncated=True" in diag, diag[:200])

    # --- pagination ceiling: an endlessly-advancing paginator is bounded -------------
    endless: dict[str, str] = {}
    first = default_list_url()
    url = first
    for i in range(zendesk.MAX_PAGES + 3):
        nxt = default_list_url() + f"&page={i + 2}"
        endless[url] = page([article(sd_section, 200 + i, f"Elgato Stream Deck 8.{i}.0 Release Notes", f"2026-06-{(i % 27) + 1:02d}T00:00:00Z")], count=999, next_page=nxt)
        url = nxt
    records, raised, reqs, diag = run_fetch(sd, endless)
    check("endless paginator is hard-capped at MAX_PAGES requests", raised is None and len(reqs) == zendesk.MAX_PAGES, str(len(reqs)))
    check("page-ceiling truncation is surfaced (never a silent full sweep)", "pagination_truncated=True" in diag, diag[:200])

    # --- cross-host next_page is never followed --------------------------------------
    records, raised, reqs, diag = run_fetch(sd, {
        default_list_url(): page([a_new], count=2, next_page="https://evil.example.com/api/v2/help_center/en-us/sections/1/articles.json"),
    })
    check("cross-host next_page is never followed", raised is None and len(reqs) == 1, str(reqs))

    # --- section scoping -------------------------------------------------------------
    outside = article(9999999, 301, "Elgato Stream Deck 6.5.0 Release Notes", "2026-05-01T00:00:00Z")
    records, raised, _reqs, diag = run_fetch(sd, {default_list_url(): page([a_new, outside])})
    check("article outside the configured section is rejected", [r["version"] for r in records] == ["9.1.0"], str(records))
    check("outside-section rejection counted honestly", "outside_section=1" in diag, diag[:220])

    # --- false product rejection ------------------------------------------------------
    wave_in_sd = article(sd_section, 302, "Elgato Wave Link 3.0.0 Release Notes", "2026-05-02T00:00:00Z")
    records, raised, _reqs, diag = run_fetch(sd, {default_list_url(): page([a_new, wave_in_sd])})
    check("Wave Link article in the Stream Deck source yields no Stream Deck record", [r["version"] for r in records] == ["9.1.0"], str(records))
    check("false-product drop counted as a title/version miss", "title_version_misses=1" in diag, diag[:220])
    generic = article(sd_section, 303, "Elgato Stream Deck 6.4.9 Release Notes", "2026-05-03T00:00:00Z", body="<p>Notes without the product phrase.</p>")
    hijack = source(product_terms=["wave link"])
    records, raised, _reqs, diag = run_fetch(hijack, {default_list_url(): page([generic])})
    check("configured product_terms gate matches (term absent -> product_misses)", records == [] and "product_misses=1" in diag, diag[:220])

    # --- drafts, locale, wrong-domain -------------------------------------------------
    draft = article(sd_section, 304, "Elgato Stream Deck 9.2.0 Release Notes", "2026-08-02T00:00:00Z", draft=True)
    localized = article(sd_section, 305, "Elgato Stream Deck 9.3.0 Release Notes", "2026-08-03T00:00:00Z", locale="de")
    foreign = article(sd_section, 306, "Elgato Stream Deck 9.4.0 Release Notes", "2026-08-04T00:00:00Z", host="evil.example.com")
    records, raised, _reqs, diag = run_fetch(sd, {default_list_url(): page([draft, localized, foreign, a_new])})
    check("draft articles are skipped", "drafts_skipped=1" in diag and all(r["version"] != "9.2.0" for r in records), diag[:260])
    check("other-locale articles are skipped", "locale_mismatches=1" in diag and all(r["version"] != "9.3.0" for r in records), diag[:260])
    check("wrong-domain article URL is rejected", "wrong_domain=1" in diag and all(r["version"] != "9.4.0" for r in records), diag[:260])

    # --- missing version / missing date ----------------------------------------------
    no_version = article(sd_section, 307, "Elgato Stream Deck Release Notes", "2026-08-05T00:00:00Z")
    no_date = article(sd_section, 308, "Elgato Stream Deck 9.5.0 Release Notes", "")
    records, raised, _reqs, diag = run_fetch(sd, {default_list_url(): page([no_version, no_date, a_new])})
    check("article without an extractable version yields NO record (fail-closed)", all(r["version"] != "" for r in records) and "title_version_misses=1" in diag, diag[:260])
    check("article without created_at yields NO record (date required)", all(r["version"] != "9.5.0" for r in records) and "date_misses=1" in diag, diag[:260])

    # --- duplicate article / platform-split version dedup ----------------------------
    records, raised, _reqs, diag = run_fetch(sd, {default_list_url(): page([a_new, dict(a_new)])})
    check("the same article listed twice yields one record", len(records) == 1 and "version_duplicates=1" in diag, diag[:260])
    wl = source("elgato-wave-link")
    wl_url = default_list_url("elgato-wave-link")
    wl_section = SECTIONS["elgato-wave-link"]
    mac = article(wl_section, 401, "Elgato Wave Link 3.2.2 (macOS) Release Notes", "2026-06-10T12:00:00Z")
    win = article(wl_section, 402, "Elgato Wave Link 3.2.2 (Windows) Release Notes", "2026-06-10T11:00:00Z")
    legacy = article(wl_section, 403, "Elgato Wave Link 1.1.5 Release Notes (macOS)", "2022-03-18T22:12:31Z")
    records, raised, _reqs, diag = run_fetch(wl, {wl_url: page([mac, win, legacy])})
    check("platform-split articles for one version dedupe to ONE record", [r["version"] for r in records] == ["3.2.2", "1.1.5"], str([r.get("version") for r in (records or [])]))
    check("newest platform article wins deterministically", records and records[0]["title"].startswith("Elgato Wave Link 3.2.2 (macOS)"), str(records and records[0]["title"]))
    check("platform dedup counted honestly", "version_duplicates=1" in diag, diag[:260])
    check("both title orders parse (suffix '(macOS)' and 'Release Notes (macOS)')", any(r["version"] == "1.1.5" for r in records), str(records))

    # --- malformed responses ----------------------------------------------------------
    _records, raised, _reqs, _diag = run_fetch(sd, {default_list_url(): "this is not json {"})
    check("invalid JSON raises (source booked failing, never silent)", raised is not None, str(raised))
    _records, raised, _reqs, _diag = run_fetch(sd, {default_list_url(): json.dumps({"count": 1})})
    check("response missing 'articles' raises (never treated as empty success)", raised is not None and "articles" in str(raised), str(raised))

    # --- 403 / 429 propagate as failures ----------------------------------------------
    _records, raised, _reqs, _diag = run_fetch(sd, {default_list_url(): RuntimeError("HTTP 403 while fetching official source — blocked")})
    check("HTTP 403 propagates as a source failure (blocked is visible, not silent)", raised is not None and "403" in str(raised), str(raised))
    _records, raised, _reqs, _diag = run_fetch(sd, {default_list_url(): RuntimeError("HTTP 429 while fetching official source — rate limited")})
    check("HTTP 429 propagates as a source failure", raised is not None and "429" in str(raised), str(raised))

    # --- no results -------------------------------------------------------------------
    records, raised, _reqs, diag = run_fetch(sd, {default_list_url(): page([])})
    check("empty section yields [] without error", raised is None and records == [], str(raised or records))
    check("no-results surfaced in diagnostics", "no_matching_articles=True" in diag, diag[:220])

    # --- limit honored ----------------------------------------------------------------
    many = [article(sd_section, 500 + i, f"Elgato Stream Deck 7.{i}.0 Release Notes", f"2026-07-{27 - i:02d}T00:00:00Z") for i in range(6)]
    records, raised, _reqs, _diag = run_fetch(sd, {default_list_url(): page(many)}, limit=2)
    check("caller limit bounds returned records (newest first)", [r["version"] for r in records] == ["7.0.0", "7.1.0"], str([r.get("version") for r in (records or [])]))

    # --- body normalization cap -------------------------------------------------------
    huge = article(sd_section, 601, "Elgato Stream Deck 6.9.9 Release Notes", "2026-04-01T00:00:00Z", body="<p>" + ("stream deck word " * 2000) + "</p>")
    records, raised, _reqs, _diag = run_fetch(sd, {default_list_url(): page([huge])})
    check("record body is capped", records and len(records[0]["body"]) <= zendesk.MAX_BODY_CHARS, str(records and len(records[0]["body"])))

    # --- config errors fail closed ----------------------------------------------------
    bad = source(official_url="https://help.elgato.com/hc/en-us/categories/123-Support")
    _records, raised, _reqs, _diag = run_fetch(bad, {})
    check("non-section official_url is a config error (fail-closed)", raised is not None and "section URL" in str(raised), str(raised))
    bad_api = source(api_url="https://evil.example.com/api/v2/help_center/en-us/sections/1/articles.json")
    _records, raised, _reqs, _diag = run_fetch(bad_api, {})
    check("api_url on a different host is a config error (fail-closed)", raised is not None and "api_url" in str(raised), str(raised))
    no_pattern = source()
    no_pattern["ingestion"].pop("version_pattern")
    _records, raised, _reqs, _diag = run_fetch(no_pattern, {default_list_url(): page([a_new])})
    check("missing version_pattern is a config error (fail-closed)", raised is not None and "version_pattern" in str(raised), str(raised))

    # --- four-product isolation -------------------------------------------------------
    catalog = {
        default_list_url("elgato-stream-deck"): page([CURRENT_FIXTURE, article(SECTIONS["elgato-stream-deck"], 701, "Elgato Wave Link 9.9.9 Release Notes", "2026-08-01T00:00:00Z")]),
        default_list_url("elgato-wave-link"): page([article(SECTIONS["elgato-wave-link"], 702, "Elgato Wave Link 3.2.10 (Windows) Release Notes", "2026-08-05T17:23:58Z")]),
        default_list_url("elgato-camera-hub"): page([article(SECTIONS["elgato-camera-hub"], 703, "Elgato Camera Hub 2.3 Release Notes", "2026-07-14T17:02:36Z")]),
        default_list_url("elgato-4k-capture-utility"): page([article(SECTIONS["elgato-4k-capture-utility"], 704, "Elgato 4K Capture Utility 1.7.16 Release Notes", "2025-11-26T17:44:03Z")]),
    }
    got = {}
    for pid in SECTIONS:
        records, raised, _reqs, _diag = run_fetch(source(pid), catalog)
        got[pid] = (raised, [(r["product_id"], r["version"]) for r in (records or [])])
    check("stream deck source accepts only its own product", got["elgato-stream-deck"] == (None, [("elgato-stream-deck", "7.5.1")]), str(got["elgato-stream-deck"]))
    check("wave link source accepts only its own product", got["elgato-wave-link"] == (None, [("elgato-wave-link", "3.2.10")]), str(got["elgato-wave-link"]))
    check("camera hub source accepts only its own product", got["elgato-camera-hub"] == (None, [("elgato-camera-hub", "2.3")]), str(got["elgato-camera-hub"]))
    check("4k capture utility source accepts only its own product", got["elgato-4k-capture-utility"] == (None, [("elgato-4k-capture-utility", "1.7.16")]), str(got["elgato-4k-capture-utility"]))

    # --- production-equivalent run_source integration ---------------------------------
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state: dict = {"schema_version": 1, "sources": {}}
        args = SimpleNamespace(limit=2, output=out, overwrite_existing=False)
        five = [article(sd_section, 800 + i, f"Elgato Stream Deck 7.{9 - i}.0 Release Notes", f"2026-07-{20 - i:02d}T00:00:00Z") for i in range(5)]
        responses = {default_list_url(): page(five)}
        original = zendesk.fetch_text

        def fake_fetch(url, **kwargs):
            return SimpleNamespace(text=responses[url])

        try:
            zendesk.fetch_text = fake_fetch
            with redirect_stderr(io.StringIO()):
                r1 = patch_ingest.run_source(source(), args, state)
                r2 = patch_ingest.run_source(source(), args, state)
                r3 = patch_ingest.run_source(source(), args, state)
        finally:
            zendesk.fetch_text = original
        check("run 1 writes record_limit new records and defers the rest", r1["created"] == 2 and r1["deferred_count"] == 3, str((r1["created"], r1["deferred_count"])))
        check("run 2 backfills the next window (progressive, no starvation)", r2["created"] == 2, str(r2["created"]))
        check("run 3 completes the backlog", r3["created"] == 1, str(r3["created"]))
        files = sorted(p.name for p in out.glob("*.md"))
        check("all five versions ingested exactly once across runs", len(files) == 5, str(files))
        text = (out / files[-1]).read_text(encoding="utf-8")
        check("generated record stays official-only (no fabricated consensus)", "evidence_state: official_only" in text and "update_report_count: 0" in text, files[-1])

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
