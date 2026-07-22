#!/usr/bin/env python3
"""Tests for Elgato Help Center official release-note ingestion."""
from __future__ import annotations

import io
import re
import sys
import tempfile
import traceback
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import elgato_help_center as elgato
import patch_ingest


# ---- progressive-backfill harness (Parts B/D/E/F) ---------------------------
# Runs the real patch_ingest.run_source (production-equivalent: seen-gating, the
# per-source scan ledger, atomic promote) against a mocked section + article pages,
# with a request counter, so we can prove the sweep advances across runs.
PROG_SECTION_URL = "https://help.elgato.com/hc/en-us/sections/9000-Elgato-Stream-Deck-Software-Release-Notes"


def prog_source(scan_limit: int = 8) -> dict:
    return {
        "company_id": "elgato", "product_id": "elgato-stream-deck", "company": "Elgato",
        "software": "Stream Deck", "public_category": "Streaming Tools",
        "ingestion": {
            "adapter": "elgato_help_center", "type": "help_center_release_notes",
            "official_url": PROG_SECTION_URL,
            "version_pattern": r"^Elgato Stream Deck (?P<version>[0-9]+(\.[0-9]+)+).*$",
            "scan_limit": scan_limit,
        },
    }


def prog_url(i: int) -> str:
    return f"https://help.elgato.com/hc/en-us/articles/{9000 + i}-item-{i}-Release-Notes"


def _match_html(i: int) -> str:
    return (f'<html><head><title>Elgato Stream Deck 7.{i}.0 Release Notes | Elgato</title></head>'
            f'<body><article><h1>Elgato Stream Deck 7.{i}.0 Release Notes</h1>'
            f'<div class="article-body">Stream Deck 7.{i}.0 notes.</div></article></body></html>')


_NONMATCH_HTML = ('<html><head><title>Help | Elgato</title></head>'
                  '<body><article><h1>How to</h1><div class="article-body">general help</div></article></body></html>')


def prog_responses(url_list: list[str], match_urls: set[str]) -> dict[str, str]:
    section = "<html><body>" + "".join(f'<a href="{u}">a</a>' for u in url_list) + "</body></html>"
    resp = {elgato._clean_url(PROG_SECTION_URL): section}
    for u in url_list:
        idx = int(re.search(r"/articles/(\d+)", u).group(1)) - 9000
        resp[elgato._clean_url(u)] = _match_html(idx) if u in match_urls else _NONMATCH_HTML
    return resp


def prog_run(src: dict, responses: dict, state: dict, output_dir: Path, *,
             fail_url: str | None = None, fail_write_call: int | None = None) -> dict:
    """One production-equivalent run_source with a counting mock. Returns per-run data."""
    reqs: list[str] = []
    original_fetch = elgato.fetch_text
    original_write = patch_ingest.write_record

    def counting_fetch(url, **_kwargs):
        clean = elgato._clean_url(url)
        reqs.append(clean)
        if fail_url and clean == fail_url:
            raise TimeoutError("simulated transport failure")
        if clean not in responses:
            raise KeyError(clean)
        return SimpleNamespace(text=responses[clean])

    if fail_write_call is not None:
        wc = {"n": 0}

        def failing_write(output, record, overwrite_existing=False):
            wc["n"] += 1
            if wc["n"] == fail_write_call:
                raise RuntimeError("simulated write failure")
            return original_write(output, record, overwrite_existing=overwrite_existing)

    args = SimpleNamespace(limit=2, output=output_dir, overwrite_existing=False)
    buf = io.StringIO()
    raised = None
    try:
        elgato.fetch_text = counting_fetch
        if fail_write_call is not None:
            patch_ingest.write_record = failing_write
        with redirect_stderr(buf):
            try:
                result = patch_ingest.run_source(src, args, state)
            except Exception as exc:  # capture write-failure for assertions
                result = None
                raised = exc
    finally:
        elgato.fetch_text = original_fetch
        patch_ingest.write_record = original_write
    detail = [u for u in reqs if "/articles/" in u]
    scan = state.get("sources", {}).get("elgato-stream-deck", {}).get("scan", {})
    return {
        "http": len(reqs), "section_reqs": len(reqs) - len(detail), "detail_reqs": detail,
        "result": result, "raised": raised, "stderr": buf.getvalue(),
        "created": (result or {}).get("created"), "skipped_existing": (result or {}).get("skipped_existing"),
        "deferred": (result or {}).get("deferred_count"),
        "committed_ledger": list(scan.get("inspected", [])),
        "pending_ledger": list(scan.get("pending_inspected", [])),
        "seen": list(state.get("sources", {}).get("elgato-stream-deck", {}).get("seen", [])),
    }


def prog_ingested(output_dir: Path) -> set:
    got = set()
    for path in output_dir.glob("*.md"):
        match = re.search(r"7\.(\d+)\.0", path.read_text(encoding="utf-8"))
        if match:
            got.add(int(match.group(1)))
    return got

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

    # === Part B: progressive-backfill reproduction — NO fixed-prefix starvation ====
    # 40 links; product-matching, version-valid articles at positions 2,6,9,14,21,33.
    positions = [2, 6, 9, 14, 21, 33]
    urls40 = [prog_url(i) for i in range(40)]
    match40 = {urls40[p] for p in positions}
    resp40 = prog_responses(urls40, match40)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        runs = [prog_run(prog_source(8), resp40, state, out) for _ in range(6)]
        ingested = prog_ingested(out)
        check("Part B: ALL 6 matching positions ingested (not just the first-window 2 and 6)", ingested == set(positions), str(sorted(ingested)))
        check("Part B: previously-starved positions 9/14/21/33 are now reached", {9, 14, 21, 33} <= ingested, str(sorted(ingested)))
        check("Part B: every run is bounded to 1 section + <=8 detail requests", all(r["section_reqs"] == 1 and len(r["detail_reqs"]) <= 8 for r in runs), str([(r["section_reqs"], len(r["detail_reqs"])) for r in runs]))
        check("Part B: run 2 requests DIFFERENT URLs than run 1 (sweep advances; no permanent prefix)", set(runs[0]["detail_reqs"]).isdisjoint(runs[1]["detail_reqs"]), str((sorted(runs[0]["detail_reqs"]), sorted(runs[1]["detail_reqs"]))))
        check("Part B: no eligible article remains unreachable", (set(positions) - ingested) == set(), str(sorted(set(positions) - ingested)))
        check("Part B: converges — a later run once swept creates 0 new records", runs[-1]["created"] == 0, str(runs[-1]["created"]))
        check("Part B: no duplicate generated files", len(list(out.glob("*.md"))) == len(ingested), str(len(list(out.glob("*.md")))))

    # Part F: max requests/run and max successful runs to inspect all 40 links
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        covered: set = set()
        n_runs = 0
        max_http = 0
        while len(covered) < 40 and n_runs < 12:
            r = prog_run(prog_source(8), resp40, state, out)
            n_runs += 1
            covered |= set(r["detail_reqs"])
            max_http = max(max_http, r["http"])
        check("Part F: all 40 links inspected within ceil(40/8)=5 successful runs", n_runs <= 5 and len(covered) == 40, f"runs={n_runs} covered={len(covered)}")
        check("Part F: max HTTP requests per run is 1 section + 8 details = 9", max_http == 9, str(max_http))
        check("Part F: caller limit=200 still cannot bypass the ceiling (<=1+ceiling)", (lambda rr: rr["http"] <= 1 + elgato.ARTICLE_SCAN_CEILING)(prog_run({**prog_source(8), "ingestion": {**prog_source(8)["ingestion"], "scan_limit": 200}}, resp40, {"schema_version": 1, "sources": {}, "seen": {}}, out)), "limit=200 bounded")

    # === Part D: a new front-inserted article is discovered within a bounded #runs ==
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        for _ in range(6):  # sweep the whole 40-link section first
            prog_run(prog_source(8), resp40, state, out)
        before = prog_ingested(out)
        new_url = prog_url(999)  # brand-new matching article -> version 7.999.0
        urls41 = [new_url] + urls40
        resp41 = prog_responses(urls41, set(match40) | {new_url})
        discovered = None
        for k in range(1, 4):
            prog_run(prog_source(8), resp41, state, out)
            if 999 in prog_ingested(out):
                discovered = k
                break
        check("Part D: a new front article is discovered within a bounded number of runs (<=2)", discovered is not None and discovered <= 2, str(discovered))
        check("Part D: older already-ingested candidates remain (no cursor reset replaying the window)", before <= prog_ingested(out), str(sorted(prog_ingested(out))))
        check("Part D: no duplicate files after front insertion", len(list(out.glob("*.md"))) == len(prog_ingested(out)), str(len(list(out.glob("*.md")))))

    # === Part E: failure semantics ==============================================
    # (a) a detail-request (transport) failure does NOT advance the ledger -> retried next run
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        fail = elgato._clean_url(urls40[2])
        r1 = prog_run(prog_source(8), resp40, state, out, fail_url=fail)
        check("Part E(a): a transport-failed URL is NOT recorded in the committed ledger (retryable)", fail not in r1["committed_ledger"], str(fail in r1["committed_ledger"]))
        check("Part E(a): the failed article is not ingested on the failing run", 2 not in prog_ingested(out), str(sorted(prog_ingested(out))))
        prog_run(prog_source(8), resp40, state, out)  # next run, no failure
        check("Part E(a): the failed URL is retried and ingested on the next run", 2 in prog_ingested(out), str(sorted(prog_ingested(out))))

    # (b) a record-write failure does NOT advance successful-ingestion state; deterministic restart
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        r1 = prog_run(prog_source(8), resp40, state, out, fail_write_call=1)  # first record write raises
        check("Part E(b): a record-write failure propagates out of run_source", isinstance(r1["raised"], RuntimeError))
        check("Part E(b): write failure does not advance `seen` ingestion state", r1["seen"] == [], str(r1["seen"]))
        check("Part E(b): write failure does not promote the scan ledger (stays uncommitted)", r1["committed_ledger"] == [], str(r1["committed_ledger"]))
        r2 = prog_run(prog_source(8), resp40, state, out)  # deterministic restart, no failure
        check("Part E(b): restart re-processes the same window and ingests the records (no loss)", {2, 6} <= prog_ingested(out), str(sorted(prog_ingested(out))))
        check("Part E(b): restart creates no duplicate files", len(list(out.glob("*.md"))) == len(prog_ingested(out)), str(len(list(out.glob("*.md")))))

    # (c) section reordering does not create duplicates or permanent starvation
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        prog_run(prog_source(8), resp40, state, out)  # run 1 on original order
        reordered = list(reversed(urls40))            # section fully reordered
        resp_rev = prog_responses(reordered, match40)
        for _ in range(6):
            prog_run(prog_source(8), resp_rev, state, out)
        ing = prog_ingested(out)
        check("Part E(c): reordering still reaches every matching article (URL-keyed, no starvation)", ing == set(positions), str(sorted(ing)))
        check("Part E(c): reordering creates no duplicate files (identity by product+version)", len(list(out.glob("*.md"))) == len(ing), str(len(list(out.glob("*.md")))))

    # === Part F: DENSE-WINDOW convergence hard gate ==============================
    # 6 matching, version-bearing articles inside the FIRST 8 links (positions 0-5),
    # plus later matches at 20 and 30. record_limit=2, scan_limit=8.
    dense_positions = [0, 1, 2, 3, 4, 5, 20, 30]
    dense_window = {0, 1, 2, 3, 4, 5}
    urlsD = [prog_url(i) for i in range(40)]
    matchD = {urlsD[p] for p in dense_positions}
    respD = prog_responses(urlsD, matchD)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        snaps = []
        for _ in range(10):
            r = prog_run(prog_source(8), respD, state, out)
            snaps.append({"created": r["created"], "ingested": prog_ingested(out)})
        ingested = prog_ingested(out)
        converge_run = next((i + 1 for i, s in enumerate(snaps) if s["ingested"] == set(dense_positions)), None)
        check("Part F(1): run 1 writes no more than record_limit(2) new records", snaps[0]["created"] <= 2, str(snaps[0]["created"]))
        check("Part F(2): dense first-window matches (0-5) are NOT permanently lost", dense_window <= ingested, str(sorted(ingested)))
        check("Part F(3): every valid record from the dense window is eventually generated", dense_window <= ingested and converge_run is not None, str((sorted(ingested), converge_run)))
        check("Part F(4): later-in-section matches (20,30) remain reachable", {20, 30} <= ingested, str(sorted(ingested)))
        check("Part F(5): no duplicate generated files", len(list(out.glob("*.md"))) == len(ingested), str(len(list(out.glob("*.md")))))
        check("Part F(6): reaches a no-new-record steady state", snaps[-1]["created"] == 0, str(snaps[-1]["created"]))
        # (7) convergence within the first sweep pass — deferred matches are reconsidered on the
        # NEXT run, not after a full wraparound cycle. 40 links / budget 8 => a sweep is ~5 runs.
        check("Part F(7): converges within a bounded number of runs (<=8)", converge_run is not None and converge_run <= 8, str(converge_run))
        check("Part F(7): a deferred dense-window match (pos 5) is generated quickly, not held to a full sweep (<=4 runs)", any(5 in s["ingested"] for s in snaps[:4]), str([sorted(s["ingested"]) for s in snaps[:4]]))
    # (8) a front insertion DURING dense progression: bounded discovery, older deferred still complete
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        prog_run(prog_source(8), respD, state, out)
        prog_run(prog_source(8), respD, state, out)  # partway through dense progression
        new_url = prog_url(888)
        respDF = prog_responses([new_url] + urlsD, set(matchD) | {new_url})
        found = None
        for k in range(1, 9):
            prog_run(prog_source(8), respDF, state, out)
            if found is None and 888 in prog_ingested(out):
                found = k
        check("Part F(8): a front insertion during dense progression is discovered within bounded runs (<=2)", found is not None and found <= 2, str(found))
        check("Part F(8): older deferred dense-window records still reach completion", set(dense_positions) <= prog_ingested(out), str(sorted(prog_ingested(out))))
        check("Part F(8): no permanent replay/starvation (no duplicate files)", len(list(out.glob("*.md"))) == len(prog_ingested(out)), str(len(list(out.glob("*.md")))))

    # === Part G: DISCOVERY-CEILING truncation hard gate ==========================
    cap = elgato.MAX_DISCOVERED_LINKS
    big_urls = [prog_url(i) for i in range(cap + 50)]  # 250 valid same-domain links
    beyond = big_urls[cap + 10]
    section_html = "<html><body>" + "".join(f'<a href="{u}">a</a>' for u in big_urls) + "</body></html>"
    retained, total = elgato._discover_article_links(PROG_SECTION_URL, section_html, cap)
    check("Part G: discovery counts ALL valid links but retains only the cap", total == cap + 50 and len(retained) == cap, str((total, len(retained))))
    check("Part G: a link beyond the cap is not retained (visibly unreachable, not silently dropped)", beyond not in retained)
    # reset guard (unit): a truncated section must NOT fake a complete sweep
    sel_t, wrapped_t, _pt = elgato._select_uninspected(retained, retained, 8, discovery_truncated=True)
    check("Part G: truncated + all-inspected does NOT reset the ledger (idles)", wrapped_t is False and sel_t == [], str((wrapped_t, len(sel_t))))
    sel_f, wrapped_f, _pf = elgato._select_uninspected(retained, retained, 8, discovery_truncated=False)
    check("Part G: non-truncated + all-inspected legitimately resets for re-verify", wrapped_f is True and len(sel_f) == 8, str((wrapped_f, len(sel_f))))
    # integration: a real run surfaces the truncation fields and stays request-bounded
    respBig = prog_responses(big_urls, {big_urls[5], beyond})
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir(parents=True)
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        rb = prog_run(prog_source(8), respBig, state, out)
        d = rb["stderr"]
        check("Part G: diagnostics expose discovery_truncated=True (never silent)", "discovery_truncated=True" in d, d[:180])
        check("Part G: diagnostics expose total_discovered and retained_count", f"total_discovered={cap + 50}" in d and f"retained_count={cap}" in d, d[:180])
        check("Part G: 250 links still cost only 1 section + <=ceiling detail requests", rb["section_reqs"] == 1 and len(rb["detail_reqs"]) <= elgato.ARTICLE_SCAN_CEILING, str((rb["section_reqs"], len(rb["detail_reqs"]))))
        check("Part G: no record is fabricated for the beyond-cap link (never fetched)", (cap + 10) not in prog_ingested(out), str(sorted(prog_ingested(out))))

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
