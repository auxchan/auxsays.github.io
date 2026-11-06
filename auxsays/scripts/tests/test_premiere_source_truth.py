#!/usr/bin/env python3
"""The Premiere Pro official-source lane must report what it can and cannot see.

THE DEFECT (GROWTH-2A, closed SOURCE-BLOCKED on 2026-11-06)
-----------------------------------------------------------
The lane tries Adobe HelpX release notes first and a PINNED Adobe Community announcement of one
release (26.2.2) second. HelpX has refused CI at once with HTTP 403 since 2026-09-08 (run
34252632666; measured 403 from CI in run 36355602551). The pinned page answers every run. Three
things were wrong with how that was reported and recorded:

1. `_fetch_first_available` DISCARDED the HelpX error whenever the fallback answered, so the
   source read `healthy` / "Fetch succeeded." (run 42194448565, 958 ms) while it could see nothing
   newer than May, and the product page said "Official updates monitored".
2. `_record` gave every version without a pinned announcement the 26.2 announcement URL.
3. `_date_from_text` returned the CURRENT time when a page had no date, and the prose path read
   the version and date from anywhere on a forum page (replies, sidebars) instead of the
   announcement's own title.

WHAT IS PINNED HERE
-------------------
A. The adapter, offline, on frozen fixtures: the HelpX 403 is reported through `probe` even when the
   pinned page answers; identity and date come from the page title; an undated or unidentified
   candidate is dropped and reported; an unknown version gets no announcement link.
B. `lib.state`: a primary failure makes the source `partial`, never `healthy` or `no_results`, and
   never "Fetch succeeded."; worse states stay; the primary's last success is kept apart from the
   fallback's.
C. End to end through `patch_ingest.run_source` (temp output dir, stubbed transport): write and dry
   runs both grade the source `partial`, and the run is annotated.
D. The publication surfaces: the monitoring projection publishes the primary's refusal, never
   "Official updates monitored", and never the fallback's date as the last successful check; the
   source-health snapshot never says "Active".

The fixture page is synthetic but reproduces the pinned announcement's identity exactly: its title
string and URL give the production record id adobe:adobe-premiere-pro:26.2.2:c176cc33bba85978.

Run standalone. Deterministic, offline, writes nothing outside a temp dir.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import build_monitoring_projection as proj  # noqa: E402
import patch_ingest  # noqa: E402
import source_health_snapshot as shs  # noqa: E402
from adapters import adobe_release_notes as adobe  # noqa: E402
from lib import ingest_health as H  # noqa: E402
from lib.state import (  # noqa: E402
    DEFAULT_EMPTY_EXTRACTION_TOLERANCE,
    PRIMARY_SOURCE_FIELDS,
    classify_success,
    update_source_success,
)

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


HELPX_URL = "https://helpx.adobe.com/premiere/desktop/whats-new/release-notes.html"
PIN_URL = "https://community.adobe.com/announcements-727/what-s-new-in-adobe-premiere-26-2-2-may-2026-1560755"
URL_262 = "https://community.adobe.com/announcements-727/welcome-to-premiere-26-2-1557825"
PRODUCTION_RECORD_ID = "adobe:adobe-premiere-pro:26.2.2:c176cc33bba85978"

# The error shape lib.http raises for the HelpX edge refusal (frozen from run 36355602551).
HELPX_403 = ("HTTP 403 while fetching official Adobe source — <HTML><HEAD>\n<TITLE>Access Denied"
             "</TITLE>\n</HEAD><BODY>\n<H1>Access Denied</H1>")

# The pinned announcement's shape: no h1-h4 at all (the live page has none), the release in the
# <title>, and forum content below it. The reply carries a full "Month D, YYYY" date and the sidebar
# names a different release; neither is this announcement's identity or date.
PIN_HTML = (
    "<html><head><title>What&#039;s New in Adobe Premiere 26.2.2 – May 2026 | Community</title>"
    "</head><body><div class=\"post\">We've just released Premiere 26.2.2. This update fixes a critical"
    " issue that impacted general stability. Like Reply Subscribe</div>"
    "<div class=\"reply\">Posted November 3, 2026: still crashing for me.</div>"
    "<aside><a href=\"/bug-reports-728/x\">Premiere 26.5.1 export crash</a></aside></body></html>"
)
# A version in the title, and no date anywhere on the page.
DATELESS_HTML = ("<html><head><title>Welcome to Premiere 26.3! | Community</title></head>"
                 "<body><div class=\"post\">We've just released Premiere 26.3.</div></body></html>")
# No version in the title; a user's report in the body names one and dates it.
NO_IDENTITY_HTML = ("<html><head><title>Premiere known issues | Community</title></head><body>"
                    "<div class=\"reply\">Premiere Pro 26.5.1 crashes on export, November 2, 2026.</div>"
                    "</body></html>")
# A date in the title and no version in it; a reply below names a version.
TITLE_DATE_NO_VERSION_HTML = ("<html><head><title>Premiere update – May 2026 | Community</title></head>"
                              "<body><div class=\"post\">Update notes.</div>"
                              "<div class=\"reply\">Still broken on Premiere Pro 26.5.1.</div></body></html>")
# HelpX-style headings: one dated, one with no date anywhere in its section, one unknown version.
HEADINGS_HTML = (
    "<html><body>"
    "<h2>June 2026 (version 26.3)</h2><p>New features.</p>"
    "<h2>Version 26.2.9</h2><p>Stability fixes.</p>"
    "<h2>May 2026 (version 26.2.2)</h2><p>Fixed a critical issue that could cause Premiere to hang.</p>"
    "</body></html>"
)


class _Result:
    def __init__(self, url: str, text: str) -> None:
        self.url = url
        self.final_url = url
        self.text = text


def source() -> dict:
    return {
        "company_id": "adobe",
        "product_id": "adobe-premiere-pro",
        "company": "Adobe",
        "software": "Premiere Pro",
        "public_category": "Video / Production",
        "enabled": True,
        "ingestion": {
            "type": "html_changelog",
            "adapter": "adobe_release_notes",
            "official_url": HELPX_URL,
            "secondary_official_url": PIN_URL,
            "polling_frequency": "24h",
        },
    }


def transport(pages: dict[str, str], refuse: set[str] = frozenset()):
    """A stub for adobe_release_notes.fetch_text: frozen pages, frozen refusals, never the network."""
    def fake(url, **_kw):
        if url in refuse:
            raise RuntimeError(HELPX_403)
        if url not in pages:
            raise RuntimeError(f"unexpected URL in an offline test: {url}")
        return _Result(url, pages[url])
    return fake


def run_fetch(pages, refuse=frozenset(), limit=200):
    original = adobe.fetch_text
    adobe.fetch_text = transport(pages, refuse)
    try:
        probe: dict = {}
        records = adobe.fetch(source(), limit=limit, probe=probe)
        return records, probe
    finally:
        adobe.fetch_text = original


def section_a_adapter() -> None:
    print("\n[A] the adapter reports the primary failure and mints no record without identity and date")
    records, probe = run_fetch({PIN_URL: PIN_HTML}, refuse={HELPX_URL})
    check("A1 HelpX refused and the pinned page answered: exactly one record, 26.2.2",
          [r.get("version") for r in records] == ["26.2.2"], str([r.get("version") for r in records]))
    check("A2 the HelpX refusal is reported through the probe although the fallback answered",
          "HTTP 403" in str(probe.get("primary_source_error") or ""), str(probe))
    check("A3 the frozen pinned page reproduces the production record identity",
          bool(records) and records[0].get("record_id") == PRODUCTION_RECORD_ID,
          str(records[0].get("record_id") if records else None))
    check("A4 the pinned page's date is its title's 'May 2026', not a reply dated November 3, 2026",
          bool(records) and records[0].get("published_at") == "2026-05-01T00:00:00Z",
          str(records[0].get("published_at") if records else None))

    ok_records, ok_probe = run_fetch({HELPX_URL: PIN_HTML, PIN_URL: PIN_HTML})
    check("A5 a primary that answered reports an empty primary error (the adapter has a chain)",
          ok_probe.get("primary_source_error") == "" and len(ok_records) == 1, str(ok_probe))

    dateless, dateless_probe = run_fetch({PIN_URL: DATELESS_HTML}, refuse={HELPX_URL})
    check("A6 a page with no date anywhere yields NO record (it used to be dated today)",
          dateless == [], str([(r.get("version"), r.get("published_at")) for r in dateless]))
    check("A7 that drop is reported as an extraction mismatch over one upstream candidate",
          dateless_probe.get("extraction_mismatch") is True
          and dateless_probe.get("upstream_candidates") == 1, str(dateless_probe))

    no_identity, _ = run_fetch({PIN_URL: NO_IDENTITY_HTML}, refuse={HELPX_URL})
    check("A8 a version named only in a user's reply is not a release identity: no record",
          no_identity == [], str([(r.get("version"), r.get("published_at")) for r in no_identity]))
    no_version, _ = run_fetch({PIN_URL: TITLE_DATE_NO_VERSION_HTML}, refuse={HELPX_URL})
    check("A9 a dated title with no version yields no record (no placeholder, no version from a reply)",
          no_version == [], str([(r.get("version"), r.get("published_at")) for r in no_version]))

    check("A10 _date_from_text returns '' for text with no date",
          adobe._date_from_text("no date in this text") == "", repr(adobe._date_from_text("no date in this text")))
    check("A11 _version_from_text returns '' for text with no version",
          adobe._version_from_text("no version here") == "", repr(adobe._version_from_text("no version here")))

    headings, headings_probe = run_fetch({HELPX_URL: HEADINGS_HTML})
    versions = [r.get("version") for r in headings]
    check("A12 an undated HelpX heading is dropped and the dated ones are kept",
          versions == ["26.3", "26.2.2"], str(versions))
    check("A13 a partial drop reports its candidates without claiming a mismatch",
          headings_probe.get("upstream_candidates") == 3 and headings_probe.get("extraction_mismatch") is False,
          str(headings_probe))
    by_version = {r.get("version"): r for r in headings}
    unknown_urls = [s.get("url") for s in (by_version.get("26.3") or {}).get("official_sources", [])]
    check("A14 an unknown version (26.3) cites no community announcement at all",
          unknown_urls == [HELPX_URL], str(unknown_urls))
    check("A15 the unknown version never inherits the 26.2 announcement URL",
          URL_262 not in json.dumps(by_version.get("26.3") or {}), str(unknown_urls))
    known_urls = [s.get("url") for s in (by_version.get("26.2.2") or {}).get("official_sources", [])]
    check("A16 a pinned version keeps its own announcement link",
          known_urls == [HELPX_URL, PIN_URL], str(known_urls))

    original = adobe.fetch_text
    adobe.fetch_text = transport({}, refuse={HELPX_URL, PIN_URL})
    try:
        adobe.fetch(source(), limit=5, probe={})
        raised = False
    except RuntimeError as exc:
        raised = "HTTP 403" in str(exc)
    finally:
        adobe.fetch_text = original
    check("A17 when every candidate fails the fetch still raises (unchanged failure path)", raised)


def section_b_state() -> None:
    print("\n[B] a primary failure is `partial`, never healthy, and never 'Fetch succeeded.'")
    tol = DEFAULT_EMPTY_EXTRACTION_TOLERANCE
    check("B1 records came back but the primary failed -> partial",
          classify_success(1, 1, 0, primary_failed=True) == "partial")
    check("B2 a quiet check whose primary failed is not quiet -> partial",
          classify_success(0, 0, 0, consecutive_empty=1, primary_failed=True) == "partial")
    check("B3 worse states stay: a long empty streak is stale, not partial",
          classify_success(0, 0, 0, consecutive_empty=tol + 1, ever_extracted=True,
                           primary_failed=True) == "stale")
    check("B4 worse states stay: an extraction mismatch is broken, not partial",
          classify_success(0, 0, 0, extraction_mismatch=True, primary_failed=True) == "broken")
    check("B5 without a primary failure nothing changes (healthy / no_results)",
          classify_success(1, 1, 0) == "healthy" and classify_success(0, 0, 0, consecutive_empty=1) == "no_results")

    state: dict = {}
    update_source_success(state, "p", checked_at="2026-11-06T09:21:47Z", duration_ms=958,
                          adapter="adobe_release_notes", fetched=1, written=1, skipped=0,
                          primary_source_error=HELPX_403)
    b = state["sources"]["p"]
    check("B6 the persisted status is partial", b.get("status") == "partial", str(b.get("status")))
    note = str(b.get("last_health_note") or "")
    check("B7 the note never says 'Fetch succeeded.' and names the primary's refusal",
          "Fetch succeeded" not in note and "primary official source failed" in note and "(blocked)" in note, note)
    check("B8 the primary's error and its type are kept",
          "HTTP 403" in str(b.get("primary_source_error")) and b.get("primary_source_error_type") == "blocked",
          str({k: b.get(k) for k in PRIMARY_SOURCE_FIELDS}))
    check("B9 a fallback success is not the primary's success",
          b.get("primary_last_success_at") == "" and b.get("last_success_at") == "2026-11-06T09:21:47Z",
          str({k: b.get(k) for k in ("primary_last_success_at", "last_success_at")}))
    check("B10 the fallback's record still counts as an extraction",
          b.get("last_extraction_at") == "2026-11-06T09:21:47Z")

    update_source_success(state, "p", checked_at="2026-11-07T00:00:00Z", duration_ms=10,
                          adapter="adobe_release_notes", fetched=2, written=2, skipped=0,
                          primary_source_error="")
    check("B11 when the primary answers again the source is healthy and the error is cleared",
          b.get("status") == "healthy" and b.get("primary_source_error") == ""
          and b.get("primary_source_error_type") == "" and b.get("last_health_note") == "Fetch succeeded.",
          str({k: b.get(k) for k in ("status", "primary_source_error", "last_health_note")}))
    check("B12 and the primary's own success is recorded",
          b.get("primary_last_success_at") == "2026-11-07T00:00:00Z", str(b.get("primary_last_success_at")))

    update_source_success(state, "p", checked_at="2026-11-08T00:00:00Z", duration_ms=10,
                          adapter="html_changelog", fetched=1, written=1, skipped=0)
    check("B13 an adapter with no primary/fallback chain leaves no primary fields behind",
          not any(k in b for k in PRIMARY_SOURCE_FIELDS), str(sorted(b)))
    plain: dict = {}
    update_source_success(plain, "q", checked_at="2026-11-08T00:00:00Z", duration_ms=10,
                          adapter="html_changelog", fetched=1, written=1, skipped=0)
    check("B14 every other source's bucket gains no new field",
          not any(k in plain["sources"]["q"] for k in PRIMARY_SOURCE_FIELDS), str(sorted(plain["sources"]["q"])))


def _run(state: dict, *, write: bool, pages: dict, refuse=frozenset()):
    original = adobe.fetch_text
    adobe.fetch_text = transport(pages, refuse)
    try:
        with tempfile.TemporaryDirectory() as td:
            args = SimpleNamespace(limit=2, output=Path(td) / "generated", overwrite_existing=False,
                                   updates_dir=Path(td))
            return patch_ingest.run_source(source(), args, state, write=write)
    finally:
        adobe.fetch_text = original


def section_c_end_to_end() -> None:
    print("\n[C] end to end: write and dry runs both grade the lane partial, and say so")
    state: dict = {}
    result = _run(state, write=True, pages={PIN_URL: PIN_HTML}, refuse={HELPX_URL})
    bucket = state["sources"]["adobe-premiere-pro"]
    check("C1 a write run persists partial with the primary's refusal",
          bucket.get("status") == "partial" and bucket.get("primary_source_error_type") == "blocked",
          str({k: bucket.get(k) for k in ("status", "primary_source_error_type", "last_health_note")}))
    check("C2 the run result carries the primary's error",
          "HTTP 403" in str(result.get("primary_source_error") or ""), str(result.get("primary_source_error")))
    check("C3 the fallback record was still written (no record is lost)",
          len(result.get("written") or []) == 1, str(result.get("written")))

    rows = H.source_rows(state, [source()], [result], [], already_persisted=True)
    check("C4 the run's health row is partial with the partial note",
          rows[0]["status"] == "partial" and "primary official source failed" in rows[0]["health_note"],
          str(rows[0]))
    check("C5 a run whose only source is partial is degraded, not healthy",
          H.classify_run(rows) == H.RUN_DEGRADED, H.classify_run(rows))
    lines: list[str] = []
    H.annotate(rows, H.classify_run(rows), emit=lines.append)
    check("C6 the run page is annotated with the partial source",
          any(ln.startswith("::warning title=Ingestion source partial::adobe-premiere-pro") for ln in lines),
          str(lines))

    # A dry run against a bucket still carrying yesterday's "healthy / Fetch succeeded.".
    stored = {"sources": {"adobe-premiere-pro": {
        "status": "healthy", "last_health_note": "Fetch succeeded.", "seen": [PRODUCTION_RECORD_ID],
        "last_extraction_at": "2026-11-06T09:21:47Z", "consecutive_empty_extractions": 0}}}
    before = json.dumps(stored, sort_keys=True)
    dry = _run(stored, write=False, pages={PIN_URL: PIN_HTML}, refuse={HELPX_URL})
    drows = H.source_rows(stored, [source()], [dry], [], already_persisted=False)
    check("C7 a dry run grades the lane partial from what it observed, not from the stored healthy",
          drows[0]["status"] == "partial", str(drows[0]["status"]))
    check("C8 and quotes the partial note, not the stored 'Fetch succeeded.'",
          "Fetch succeeded" not in drows[0]["health_note"]
          and "primary official source failed" in drows[0]["health_note"], drows[0]["health_note"])
    check("C9 the dry run wrote no state", json.dumps(stored, sort_keys=True) == before)

    ok_state: dict = {}
    ok = _run(ok_state, write=True, pages={HELPX_URL: PIN_HTML, PIN_URL: PIN_HTML})
    check("C10 when HelpX answers the lane is healthy again",
          ok_state["sources"]["adobe-premiere-pro"].get("status") == "healthy" and ok.get("primary_source_error") == "",
          str(ok_state["sources"]["adobe-premiere-pro"].get("status")))


NOW = proj.datetime(2026, 11, 6, 12, 0, tzinfo=proj.timezone.utc)


def section_d_publication() -> None:
    print("\n[D] the public surfaces never present the fallback as official-update monitoring")
    partial_blocked = {"status": "partial", "last_success_at": "2026-11-06T09:21:47Z",
                       "primary_source_error_type": "blocked", "primary_last_success_at": "",
                       "last_checked_at": "2026-11-06T09:21:47Z"}
    src = source()
    check("D1 partial behind a refusal publishes blocked ('refusing automated checks')",
          proj.derive_state(src, partial_blocked, now=NOW) == "blocked",
          proj.derive_state(src, partial_blocked, now=NOW))
    check("D2 partial behind a timeout publishes unreachable",
          proj.derive_state(src, dict(partial_blocked, primary_source_error_type="timeout"), now=NOW) == "unreachable")
    check("D3 partial for any other reason is unverified, never healthy",
          proj.derive_state(src, dict(partial_blocked, primary_source_error_type="error"), now=NOW) == "unverified")
    check("D4 the reader is not told the fallback's date as the last successful check",
          proj.day(proj._success_field(partial_blocked)) == "", proj.day(proj._success_field(partial_blocked)))
    check("D5 a non-partial source keeps its own last success",
          proj.day(proj._success_field({"status": "healthy", "last_success_at": "2026-11-06T09:21:47Z"})) == "2026-11-06")
    check("D6 the source-health snapshot never says Active for a partial source",
          shs.status_for(src, partial_blocked, "")[0] == "Partial", str(shs.status_for(src, partial_blocked, "")))

    # Before/after over the COMMITTED bucket: apply today's production observation (HelpX 403,
    # pinned page answered with one record) to a copy. Whatever the stored status, the lane must
    # stop publishing "Official updates monitored".
    live = json.loads((_REPO / "auxsays" / "_data" / "patch_ingest_state.json").read_text(encoding="utf-8"))
    sim = {"sources": {"adobe-premiere-pro": copy.deepcopy(live["sources"]["adobe-premiere-pro"])}}
    update_source_success(sim, "adobe-premiere-pro", checked_at="2026-11-06T09:21:47Z", duration_ms=958,
                          adapter="adobe_release_notes", fetched=1, written=1, skipped=0,
                          primary_source_error=HELPX_403)
    after = sim["sources"]["adobe-premiere-pro"]
    check("D7 the live bucket, after today's observation, is partial and publishes blocked",
          after.get("status") == "partial" and proj.derive_state(src, after, now=NOW) == "blocked",
          str({k: after.get(k) for k in ("status", "primary_source_error_type")}))
    check("D8 its public label is the refusal, not 'Official updates monitored'",
          proj.STATE_LABELS[proj.derive_state(src, after, now=NOW)] == "Official source is refusing automated checks")


def run() -> int:
    print("=" * 60)
    print("Premiere Pro official-source truthfulness")
    print("=" * 60)
    section_a_adapter()
    section_b_state()
    section_c_end_to_end()
    section_d_publication()
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
