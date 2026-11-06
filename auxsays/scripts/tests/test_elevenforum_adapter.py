#!/usr/bin/env python3
"""Windows 11 Forum (elevenforum.com) discovery adapter: shipped DISABLED.

Offline and deterministic. Every page comes from tests/fixtures/elevenforum/ or from an inline synthetic
page. The fixture files are SYNTHETIC: titles and opening posts written by AUXSAYS, each modelled on a
page recorded 2026-11-04. They keep that page's structure, scenario, thread id, dates, version
identifiers, error codes and commands; apart from those identifiers, no run of five or more consecutive
words of the recorded text remains. The network is replaced by an injected transport, and the one test
that runs the whole collector asserts that no request is made.
Nothing here writes `_data`, a record or the evidence store.

    A  URL policy              only the three approved listings and /t/ threads can be requested;
                               /search/, /members/, /whats-new/, page 4 and other hosts cannot
    B  response classification 403, challenge pages (including a 200 one) and 429 are `blocked`
    C  listing parser          sticky flag, last-activity time and the title prefilter
    D  opening-post parser     JSON-LD datePublished is the post date; replies are never read; no
                               valid date or text means no candidate, with no fallback
    E  request budget          9 listing pages, 40 hydrations, 49 requests, >= 1.5 s apart, enforced
                               in the one function every request goes through
    F  discovery behaviour     ordering, window, early stop, abort on a block, isolated failures
    G  health vocabulary       blocked / partial / no_results / success; the cap is not degradation
    H  disabled means disabled no flag -> no request, no pool, no health row, no ownership entry
    I  AUX-063 RESOLVED        thread 50506 was attributed to the wrong patch by the pre-AUX-067
                               authority; it is now rejected as identity_not_the_subject
    J  duplicates              similarity is an annotation, never a reason to drop a row
    K  registry, ledger, dry run

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_elevenforum_adapter.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import traceback
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from patch_collectors import elevenforum_source as ef  # noqa: E402
from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors.base import CollectorContext, PatchRecord, WINDOWS_PRODUCT_ID  # noqa: E402
from lib import acquisition_methods as am  # noqa: E402
from lib import collector_ownership as co  # noqa: E402

FIX = _SCRIPTS / "tests" / "fixtures" / "elevenforum"
NEWLINE = chr(10)
TODAY = "2026-11-04"
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
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class Clock:
    """Fake time: sleeping only advances it, so pacing is asserted without waiting."""
    def __init__(self) -> None:
        self.now = 1000.0
    def time(self) -> float:
        return self.now
    def sleep(self, seconds: float) -> None:
        self.now += seconds


def fixture_transport(url: str) -> tuple[int, str]:
    kind = ef.classify_url(url)
    if kind == "listing":
        path = url.split("/questions/", 1)[1].strip("/")
        cat, _, page = path.partition("/page-")
        name = f"listing_{cat}_p{page or 1}.html"
    else:
        name = f"thread_{ef.thread_id_of(url)}.html"
    if (FIX / name).is_file():
        return 200, fixture(name)
    if kind == "listing":
        return 200, '<html id="XF"><head><title>x</title></head><body></body></html>'
    return 404, ""


# --- synthetic pages ---------------------------------------------------------------------------

def thread_page(tid: int | str, title: str, text: str, date: str | None = "2026-10-30T10:00:00+00:00",
                *, extra_main: dict | None = None, node_type: str = "WebPage",
                main_type: str = "DiscussionForumPosting", body_extra: str = "") -> str:
    url = f"https://www.elevenforum.com/t/some-thread.{tid}/"
    main: dict = {"@type": main_type, "@id": url, "headline": title, "url": url, "text": text}
    if date is not None:
        main["datePublished"] = date
    main.update(extra_main or {})
    blob = json.dumps({"@context": "https://schema.org", "@type": node_type, "url": url,
                       "mainEntity": main}).replace("</", "<\\/")
    return (f'<!DOCTYPE html><html id="XF"><head><title>{title} | Windows 11 Forum</title>'
            f'<script type="application/ld+json">{blob}</script></head><body>{body_extra}</body></html>')


def listing_page(rows: list[tuple[int, str, str, bool]]) -> str:
    items = []
    for tid, title, last, sticky in rows:
        status = ('<ul class="structItem-statuses"><li><i class="structItem-status structItem-status--sticky">'
                  '</i></li></ul>' if sticky else '<ul class="structItem-statuses"></ul>')
        items.append(
            f'<div class="structItem structItem--thread js-threadListItem-{tid}">'
            f'<div class="structItem-cell structItem-cell--main">{status}'
            f'<div class="structItem-title"><a href="/t/some-thread.{tid}/">{title}</a></div></div>'
            f'<div class="structItem-cell structItem-cell--latest"><a href="/t/some-thread.{tid}/latest">'
            f'<time class="structItem-latestDate u-dt" datetime="{last}T12:00:00-0500">x</time></a></div></div>')
    return '<!DOCTYPE html><html id="XF"><head><title>L</title></head><body>' + "".join(items) + "</body></html>"


class InfiniteForum:
    """A forum that always has 15 fresh, patch-titled threads on every page of every category."""
    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, url: str) -> tuple[int, str]:
        self.seen.append(url)
        kind = ef.classify_url(url)
        if kind == "listing":
            cat = url.split("/questions/", 1)[1].split("/")[0]
            page = int(url.rsplit("page-", 1)[1]) if "page-" in url else 1
            base = (ef.APPROVED_LISTINGS.index(cat) + 1) * 100000 + page * 100
            rows = [(base + i, f"KB5127648 update problem {i}", "2026-11-03", False) for i in range(15)]
            return 200, listing_page(rows)
        tid = ef.thread_id_of(url)
        return 200, thread_page(tid, f"KB5127648 update problem {tid}", "KB5127648 fails to install on 26H2.")


def run_discover(transport, **kw) -> tuple[ef.Discovery, ef.Session]:
    clock = Clock()
    session = ef.Session(transport, clock=clock.time, sleep=clock.sleep)
    return ef.discover(session, since=kw.pop("since", "2026-10-01"), today=TODAY, **kw), session


# --- Windows authority harness (synthetic targets: stable as the real records roll over) -------

TARGET_26H2 = {"target_feature_version": "26H2", "target_kb": "KB5127648", "target_os_build": "26300.9711",
               "target_release_date": "2026-10-13T00:00:00Z", "update_version": "26H2"}
TARGET_25H2 = {"target_feature_version": "25H2", "target_kb": "KB5127648", "target_os_build": "26200.9711",
               "target_release_date": "2026-10-13T00:00:00Z", "update_version": "25H2"}
REC_26H2 = PatchRecord(WINDOWS_PRODUCT_ID, "26H2", Path("synthetic-26h2.md"), "2026-10-13T00:00:00Z",
                       "current", "Windows 11", "26300.9711")
REC_25H2 = PatchRecord(WINDOWS_PRODUCT_ID, "25H2", Path("synthetic-25h2.md"), "2026-10-13T00:00:00Z",
                       "current", "Windows 11", "26200.9711")
CAPTURED = "2026-11-04T00:00:00Z"


def evaluate_all(candidates: list[dict]) -> dict[str, list[tuple[str, dict]]]:
    """url -> [(patch, row)] of ACCEPTED rows, newest-first with a shared claims map like production."""
    claims: dict = {}
    out: dict[str, list[tuple[str, dict]]] = {}
    for rec, target in ((REC_26H2, TARGET_26H2), (REC_25H2, TARGET_25H2)):
        accepted, _rejected = mw.evaluate_candidates(rec, target, candidates, CAPTURED, claims)
        for row in accepted:
            out.setdefault(row["source_url"], []).append((f"{rec.update_version} {rec.target_build}", row))
    return out


def tree_digest(*roots: Path) -> str:
    h = hashlib.sha256()
    for root in roots:
        for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            h.update(str(path.relative_to(root)).encode())
            h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Windows 11 Forum discovery adapter (disabled by default)")
    print("=" * 78)

    # ---------------------------------------------------------------- A. URL policy
    L = "https://www.elevenforum.com/questions/"
    check("A1 the approved listing pages 1..3 are requestable",
          all(ef.classify_url(u) == "listing" for u in (
              L + "install-update-activate/", L + "general-support/", L + "bsod/",
              L + "bsod/page-2", L + "general-support/page-3")))
    check("A2 a thread permalink is requestable",
          ef.classify_url("https://www.elevenforum.com/t/security-update-keeps-failing-to-install.50447/") == "thread")
    check("A3 /search/, /members/ and /whats-new/ are refused (robots.txt Disallow)",
          not any(ef.classify_url(u) for u in (
              "https://www.elevenforum.com/search/", "https://www.elevenforum.com/search/1/?q=KB5127648",
              "https://www.elevenforum.com/members/birk.123/", "https://www.elevenforum.com/whats-new/posts/")))
    check("A4 page 4 of an approved listing is refused", ef.classify_url(L + "bsod/page-4") == "")
    check("A5 a category outside the three approved is refused",
          ef.classify_url(L + "-/") == "" and ef.classify_url(L + "hardware/") == ""
          and ef.classify_url("https://www.elevenforum.com/news/") == "")
    check("A6 another host, plain http, a query string and a fragment are refused",
          ef.classify_url("https://windowsforum.com/t/x.1/") == ""
          and ef.classify_url("http://www.elevenforum.com/t/x.1/") == ""
          and ef.classify_url("https://www.elevenforum.com/t/x.1/?foo=1") == ""
          and ef.classify_url("https://www.elevenforum.com/t/x.1/#post-2") == "")
    check("A7 the RSS endpoint is not on the allow-list (one approach, not two)",
          ef.classify_url(L + "bsod/index.rss") == "")
    check("A8 listing_url builds page 1 without a suffix and refuses page 0 and 4",
          ef.listing_url("bsod", 1) == L + "bsod/" and ef.listing_url("bsod", 3) == L + "bsod/page-3"
          and all(_raises(lambda p=p: ef.listing_url("bsod", p)) for p in (0, 4)))
    check("A9 canonical_thread_url strips the trailing slash and refuses non-threads",
          ef.canonical_thread_url("https://www.elevenforum.com/t/security-update-keeps-failing-to-install.50447/")
          == "https://www.elevenforum.com/t/security-update-keeps-failing-to-install.50447"
          and ef.canonical_thread_url(L + "bsod/") == ""
          and ef.canonical_thread_url("https://example.com/t/x.1/") == "")

    # ---------------------------------------------------------------- B. response classification
    xf = '<!DOCTYPE html><html id="XF"><head><title>Thread</title></head><body>hello</body></html>'
    challenge = '<html><head><title>Just a moment...</title></head><body>Checking your browser</body></html>'
    check("B1 a plain 200 XenForo page is usable", ef.classify_response(200, xf) is None)
    check("B2 HTTP 403 is blocked", ef.classify_response(403, "Forbidden") == "http_403_blocked")
    check("B3 a 403 carrying a challenge body is classified as a challenge",
          ef.classify_response(403, challenge) == "challenge_page")
    check("B4 a 200 whose <title> is a bot check is a challenge, not a page",
          ef.classify_response(200, challenge) == "challenge_page")
    check("B5 a non-XenForo 200 with a bot-check body is a challenge",
          ef.classify_response(200, "<html><body>Checking your browser before accessing</body></html>")
          == "challenge_page")
    check("B6 a real thread whose POST says 'just a moment' is NOT a challenge",
          ef.classify_response(200, '<html id="XF"><head><title>My PC</title></head><body>'
                               'just a moment, checking your browser settings</body></html>') is None)
    check("B7 429 and 503 are rate_limited; 401 is blocked; 404 and 500 are plain errors",
          ef.classify_response(429, "") == "rate_limited" and ef.classify_response(503, "") == "rate_limited"
          and ef.classify_response(401, "") == "http_401_blocked"
          and ef.classify_response(404, "") == "http_404_error"
          and ef.classify_response(500, "") == "http_500_error")
    check("B8 every blocked token is in the set discovery stops on",
          {"http_403_blocked", "challenge_page", "rate_limited", "http_401_blocked"} <= ef.BLOCKED_REASONS
          and "http_404_error" not in ef.BLOCKED_REASONS)

    # ---------------------------------------------------------------- C. listing parser
    page1 = ef.parse_listing(fixture("listing_install-update-activate_p1.html"))
    by_id = {r["thread_id"]: r for r in page1}
    check("C1 the recorded listing parses all 21 threads", len(page1) == 21, str(len(page1)))
    check("C2 pinned threads are flagged sticky (6 on page 1) and others are not",
          sum(r["sticky"] for r in page1) == 6 and not by_id["50594"]["sticky"])
    check("C3 last activity is read as a date and is NOT the post date",
          by_id["50594"]["last_activity"] == "2026-11-04")
    check("C4 titles are unescaped and canonical urls built",
          by_id["50594"]["title"] == "KB5127936 & Ctrl-Alt-Del: restart hangs, any fix?"
          and by_id["50594"]["source_url"].endswith("/t/kb5127936-ctrl-alt-del-restart-hangs-any-fix.50594"))
    check("C5 the title prefilter admits a KB, an OS build, a feature train, 'update' and 'patch'",
          all(ef.title_has_patch_cue(t) for t in (
              "KB5127936 broke it", "Build 26200.9711 crash", "How to move to 24H2",
              "Windows Update stuck", "Patch Tuesday problem")))
    check("C6 the prefilter refuses titles with no patch cue",
          not any(ef.title_has_patch_cue(t) for t in ("Random BSOD", "Icons disappeared", "Windows 11 Won't sleep")))
    check("C7 an empty or malformed listing parses to nothing, not an exception",
          ef.parse_listing("") == [] and ef.parse_listing("<html>no threads</html>") == [])

    # ---------------------------------------------------------------- D. opening-post parser
    cand, why = ef.parse_thread("https://www.elevenforum.com/t/security-update-keeps-failing-to-install.50447/",
                                fixture("thread_50447.html"), today=TODAY)
    check("D1 a fixture thread yields one candidate", cand is not None and why == "", why)
    assert cand is not None
    check("D2 the post date is the JSON-LD datePublished", cand["source_date"] == "2026-10-28"
          and cand["original_post_date"] == "2026-10-28")
    stale, _ = ef.parse_thread("https://www.elevenforum.com/t/restart-request-shows-up-midway-through-a-running-update.44141/",
                               fixture("thread_44141.html"), today=TODAY)
    last_activity = {r["thread_id"]: r["last_activity"] for r in page1}
    check("D3 an old thread bumped by a reply keeps its ORIGINAL date, not its last-activity time",
          stale is not None and stale["source_date"] == "2026-01-28" and last_activity["44141"] >= "2026-10-31",
          f"{stale and stale['source_date']} vs listing {last_activity.get('44141')}")
    check("D4 the candidate carries the url, source identity and an excerpt-sized text",
          cand["source_url"] == "https://www.elevenforum.com/t/security-update-keeps-failing-to-install.50447"
          and cand["source_type"] == ef.DEFAULT_SOURCE_TYPE and 0 < len(cand["report_text"]) <= ef.EXCERPT_CHARS)
    long_text = "KB5127648 fails to install. " * 400
    capped, _ = ef.parse_thread("https://www.elevenforum.com/t/some-thread.1/",
                                thread_page(1, "KB5127648 problem", long_text), today=TODAY)
    check("D5 the stored text is capped at the excerpt size", capped is not None
          and len(capped["report_text"]) == ef.EXCERPT_CHARS)
    reply_bait = thread_page(
        2, "Update failing", "My update fails to install, error 0x80070017.",
        extra_main={"comment": [{"@type": "Comment", "text": "Same on KB5127648 build 26300.9711 here"}]},
        body_extra='<article class="message">Reply: I am on KB5127648 26300.9711 and it works</article>')
    bait, _ = ef.parse_thread("https://www.elevenforum.com/t/some-thread.2/", reply_bait, today=TODAY)
    check("D6 REPLIES ARE NEVER READ: a reply's KB and build do not enter the candidate",
          bait is not None and "KB5127648" not in bait["report_text"] and "26300" not in bait["report_text"])
    nodate, why_nodate = ef.parse_thread("https://www.elevenforum.com/t/some-thread.3/",
                                         thread_page(3, "KB5127648 update fails", "It fails.", date=None), today=TODAY)
    check("D7 no datePublished means NO candidate (no fallback to a listing time)",
          nodate is None and why_nodate == "no_valid_date_published", why_nodate)
    check("D8 a malformed, a future and a pre-forum date are all refused",
          all(ef.parse_thread("https://www.elevenforum.com/t/some-thread.4/",
                              thread_page(4, "KB5127648 update fails", "It fails.", date=d), today=TODAY)[1]
              == "no_valid_date_published"
              for d in ("yesterday", "2026-13-45T00:00:00Z", "2027-03-01T00:00:00+00:00", "2019-05-01T00:00:00+00:00")))
    check("D9 a date-only datePublished is accepted",
          ef.parse_thread("https://www.elevenforum.com/t/some-thread.5/",
                          thread_page(5, "KB5127648 update fails", "It fails.", date="2026-10-30"), today=TODAY)[0] is not None)
    check("D10 an opening post with no text is not a report (a title is a headline)",
          ef.parse_thread("https://www.elevenforum.com/t/some-thread.6/",
                          thread_page(6, "KB5127648 update fails", "   "), today=TODAY)[1] == "no_opening_post_text")
    check("D11 JSON-LD describing a DIFFERENT thread is refused",
          ef.parse_thread("https://www.elevenforum.com/t/some-thread.7/",
                          thread_page(8, "KB5127648 update fails", "It fails."), today=TODAY)[1] == "thread_url_mismatch")
    check("D12 a page with no JSON-LD, and a WebPage with no posting, yield no candidate",
          ef.parse_thread("https://www.elevenforum.com/t/some-thread.9/", "<html></html>", today=TODAY)[1] == "no_json_ld"
          and ef.parse_thread("https://www.elevenforum.com/t/some-thread.9/",
                              '<script type="application/ld+json">{"@type":"WebPage"}</script>', today=TODAY)[1]
          == "no_opening_post_node")
    check("D13 a QAPage wrapper around a Question is accepted too (the hand-off's wording)",
          ef.parse_thread("https://www.elevenforum.com/t/some-thread.10/",
                          thread_page(10, "KB5127648 update fails", "It fails.", node_type="QAPage",
                                      main_type="Question"), today=TODAY)[0] is not None)
    check("D14 HTML in the post text is stripped",
          "<b>" not in (ef.parse_thread("https://www.elevenforum.com/t/some-thread.11/",
                                        thread_page(11, "KB5127648 update fails", "It <b>fails</b> &amp; reboots."),
                                        today=TODAY)[0] or {"report_text": "<b>"})["report_text"])
    check("D15 a malformed JSON-LD block is skipped rather than raised",
          ef.parse_thread("https://www.elevenforum.com/t/some-thread.12/",
                          '<script type="application/ld+json">{not json</script>', today=TODAY)[1] == "no_json_ld")

    # ---------------------------------------------------------------- E. request budget
    check("E1 the approved constants are exactly the decision's",
          ef.APPROVED_LISTINGS == ("install-update-activate", "general-support", "bsod")
          and ef.MAX_LISTING_PAGES == 3 and ef.MAX_HYDRATIONS == 40 and ef.MIN_REQUEST_INTERVAL == 1.5
          and ef.MAX_LISTING_REQUESTS == 9 and ef.MAX_REQUESTS_PER_CYCLE == 49)
    forum = InfiniteForum()
    result, session = run_discover(forum)
    check("E2 BUDGET: at most 9 listing requests", session.counts["listing"] <= 9 and session.counts["listing"] == 9,
          str(session.counts))
    check("E3 BUDGET: at most 40 hydrations, and exactly 40 when more are eligible",
          session.counts["thread"] == 40 and result.telemetry["hydration_requests"] == 40, str(session.counts))
    check("E4 BUDGET: at most 49 requests in the cycle", session.total_requests == 49 == len(forum.seen),
          f"{session.total_requests} / {len(forum.seen)}")
    check("E5 BUDGET: every consecutive pair is at least 1.5 s apart",
          len(session.gaps) == 48 and min(session.gaps) >= 1.5, f"{len(session.gaps)} gaps, min {min(session.gaps)}")
    check("E6 only approved listings and /t/ threads were requested; page 4 never",
          all(ef.classify_url(u) for u in forum.seen) and not any("page-4" in u for u in forum.seen)
          and {u.split("/questions/")[1].split("/")[0] for u in forum.seen if "/questions/" in u}
          == set(ef.APPROVED_LISTINGS))
    check("E7 no disallowed path was ever requested",
          not any(p in u for u in forum.seen for p in ("/search/", "/members/", "/whats-new/", "index.rss")))
    check("E8 the cap is reported as capped, not as degradation", result.telemetry["capped"] is True
          and result.telemetry["aborted"] is False and result.telemetry["eligible"] > 40)
    s2 = ef.Session(lambda u: (200, xf), clock=Clock().time, sleep=Clock().sleep)
    for i in range(9):
        s2.get(ef.listing_url(ef.APPROVED_LISTINGS[i // 3], i % 3 + 1))
    check("E9 the 10th listing request is refused by the session itself",
          _reason(lambda: s2.get(ef.listing_url("bsod", 1))) == "request_budget_exhausted")
    s3 = ef.Session(lambda u: (200, xf), clock=Clock().time, sleep=Clock().sleep)
    for i in range(40):
        s3.get(f"https://www.elevenforum.com/t/some-thread.{i + 1}/")
    check("E10 the 41st hydration is refused by the session itself, whatever the caller does",
          _reason(lambda: s3.get("https://www.elevenforum.com/t/some-thread.99/")) == "request_budget_exhausted"
          and s3.counts["thread"] == 40)
    s4 = ef.Session(lambda u: (200, xf), clock=Clock().time, sleep=Clock().sleep)
    check("E11 a disallowed URL is refused before it counts or reaches the transport",
          _reason(lambda: s4.get("https://www.elevenforum.com/search/1/?q=KB5127648")) == "url_not_allowed"
          and s4.total_requests == 0)
    waits: list[float] = []
    c5 = Clock()
    s5 = ef.Session(lambda u: (200, xf), clock=c5.time, sleep=lambda s: (waits.append(s), c5.sleep(s)))
    s5.get(ef.listing_url("bsod", 1))
    s5.get(ef.listing_url("bsod", 2))
    check("E12 the first request does not wait and the second waits the full interval",
          len(waits) == 1 and abs(waits[0] - 1.5) < 1e-9, str(waits))

    # ---------------------------------------------------------------- F. discovery behaviour
    result, session = run_discover(fixture_transport, since="2026-10-18")
    t = result.telemetry
    check("F1 fixture replay: 20 threads hydrated, 20 candidates, none unparseable",
          t["hydrated"] == 20 and len(result.candidates) == 20 and t["unparseable"] == 0, str(t))
    check("F2 stickies and out-of-window and cue-less threads are skipped and never requested",
          t["skipped"]["sticky"] == 10 and t["skipped"]["outside_window"] == 6
          and t["skipped"]["no_title_cue"] == 31 and t["hydration_requests"] == 20, str(t["skipped"]))
    check("F3 fixture replay stays inside the budget",
          session.total_requests <= 49 and min(session.gaps) >= 1.5 and t["capped"] is False)
    served = [u for u in session.requested if "/t/" in u]
    check("F4 threads are hydrated newest-activity first",
          served[0].endswith(".50607/") or ".50607" in served[0], served[0])

    def listing_then_stop(url: str):
        if "/questions/" in url:
            return 200, listing_page([(1, "KB5127648 update old", "2025-01-01", False)])
        return 200, thread_page(1, "x", "y")
    result, session = run_discover(listing_then_stop, since="2026-10-18")
    check("F5 a page whose unpinned threads all went quiet before the window ends that category's walk",
          session.counts["listing"] == 3 and session.counts["thread"] == 0, str(session.counts))

    calls = {"n": 0}
    def blocked_listing(url: str):
        calls["n"] += 1
        return 403, "Forbidden"
    result, session = run_discover(blocked_listing)
    check("F6 a blocked first listing STOPS discovery: one request, no retry, no other host",
          session.total_requests == 1 and result.telemetry["blocked"] is True
          and result.errors[0]["reason"] == "http_403_blocked" and result.candidates == [], str(session.counts))

    def challenge_after_listing(url: str):
        if "/questions/" in url:
            return 200, listing_page([(i, f"KB5127648 update {i}", "2026-11-03", False) for i in range(1, 9)])
        return 200, challenge
    result, session = run_discover(challenge_after_listing)
    check("F7 three consecutive challenge pages on hydration stop the walk (3 requests, not 8)",
          session.counts["thread"] == 3 and result.telemetry["blocked"] is True
          and result.telemetry["abort_reason"] == "challenge_page", str(session.counts))

    def one_refusal(url: str):
        if "/questions/" in url:
            return 200, listing_page([(i, f"KB5127648 update {i}", "2026-11-03", False) for i in range(1, 7)])
        if ef.thread_id_of(url) == "3":
            return 403, "Forbidden"
        return 200, thread_page(ef.thread_id_of(url), "KB5127648 update fails", "It fails to install.")
    result, session = run_discover(one_refusal)
    check("F8 an isolated refused thread is recorded and the walk goes on",
          result.telemetry["hydration_errors"] == 1 and result.telemetry["hydrated"] > 1
          and result.telemetry["blocked"] is False, str(result.telemetry))

    def flaky(url: str):
        if "/questions/" in url:
            return 200, listing_page([(i, f"KB5127648 update {i}", "2026-11-03", False) for i in range(1, 5)])
        raise ef.ElevenForumError("network_unreachable")
    result, session = run_discover(flaky)
    check("F9 non-block transport failures never trigger the block abort",
          result.telemetry["hydration_errors"] == 4 and result.telemetry["blocked"] is False)

    stop = {"after": 2, "n": 0}
    def should_stop() -> bool:
        stop["n"] += 1
        return stop["n"] > stop["after"]
    result, session = run_discover(InfiniteForum(), should_stop=should_stop)
    check("F10 a run-budget stop ends hydration early and is reported as aborted",
          session.counts["thread"] == 2 and result.telemetry["aborted"] is True
          and result.telemetry["abort_reason"] == "run_budget_expired")

    def duplicate_across_categories(url: str):
        if "/questions/" in url:
            return 200, listing_page([(77, "KB5127648 update fails", "2026-11-03", False)])
        return 200, thread_page(77, "KB5127648 update fails", "It fails to install.")
    result, session = run_discover(duplicate_across_categories)
    check("F11 a thread listed in two categories is hydrated once",
          session.counts["thread"] == 1 and len(result.candidates) == 1)

    # ---------------------------------------------------------------- G. health vocabulary
    def pool(**tele) -> mw.ElevenForumPool:
        base = {"listing_ok": 9, "listing_errors": 0, "attempted": 10, "hydration_errors": 0,
                "blocked": False, "aborted": False, "capped": False}
        base.update(tele)
        return mw.ElevenForumPool(candidates=[{"x": 1}] * 5, telemetry=base, errors=[], unparseable=[])
    acc, rej = [{"counted": True}], [{"counted": False}]
    check("G1 clean walk + accepted -> success", mw.elevenforum_method_status(pool(), acc, rej) == "success")
    check("G2 clean walk, nothing accepted -> no_results", mw.elevenforum_method_status(pool(), [], rej) == "no_results")
    check("G3 hitting the 40 cap is NOT degradation",
          mw.elevenforum_method_status(pool(capped=True), acc, rej) == "success")
    check("G4 a failed listing page -> partial", mw.elevenforum_method_status(pool(listing_errors=1), acc, rej) == "partial")
    check("G5 one hydration in five failing -> partial",
          mw.elevenforum_method_status(pool(hydration_errors=2), acc, rej) == "partial")
    check("G6 every hydration refused -> blocked",
          mw.elevenforum_method_status(pool(hydration_errors=10), [], rej) == "blocked")
    check("G7 blocked with nothing read -> blocked; blocked after some reads -> partial",
          mw.elevenforum_method_status(mw.ElevenForumPool([], {"listing_ok": 0, "listing_errors": 1, "blocked": True},
                                                          [], []), [], []) == "blocked"
          and mw.elevenforum_method_status(pool(blocked=True, aborted=True), [], rej) == "partial")
    check("G8 no listing page read at all -> blocked, never no_results",
          mw.elevenforum_method_status(mw.ElevenForumPool([], {"listing_ok": 0, "listing_errors": 0},
                                                          [], []), [], []) == "blocked")
    row = mw.elevenforum_health(REC_25H2, CAPTURED, pool(), acc, rej)
    check("G9 the health row names its own method, source type and exact build",
          row["method_id"] == mw.ELEVENFORUM_METHOD_ID and row["source_type"] == ef.DEFAULT_SOURCE_TYPE
          and row["target_build"] == "26200.9711" and row["status"] == "success")
    check("G10 every status the method can emit is canonical vocabulary",
          {"blocked", "partial", "no_results", "success"} <= set(am.HEALTH_STATUSES))

    # ---------------------------------------------------------------- H. disabled means disabled
    flag = mw.ELEVENFORUM_ENABLE_ENV
    check("H1 the flag is true-only: absent/empty/false/0/1/yes/on/TRUE-with-space behave as documented",
          not any(mw.elevenforum_discovery_enabled({flag: v}) for v in ("", "false", "0", "1", "yes", "on", "enabled"))
          and not mw.elevenforum_discovery_enabled({})
          and mw.elevenforum_discovery_enabled({flag: "true"}) and mw.elevenforum_discovery_enabled({flag: " TRUE "}))

    results_by_flag = {}
    saved_env = os.environ.get(flag)
    real = {
        "urlopen": urllib.request.urlopen,
        "learn": mw.learn_qna.collect_learn_qna_candidates,
        "enum": mw.techcommunity.enumerate_sitemaps,
        "pool": mw.build_elevenforum_pool,
        "now": mw.utc_now,
    }
    network = {"calls": 0}
    pool_calls = {"n": 0}

    def no_network(*a, **k):
        network["calls"] += 1
        raise AssertionError("a network request was made")

    def stub_pool(context, session=None):
        pool_calls["n"] += 1
        return mw.ElevenForumPool(candidates=[], telemetry={"listing_ok": 1, "listing_errors": 0, "attempted": 0,
                                                            "hydration_errors": 0}, errors=[], unparseable=[])
    try:
        urllib.request.urlopen = no_network
        mw.learn_qna.collect_learn_qna_candidates = lambda **kw: []
        mw.techcommunity.enumerate_sitemaps = lambda *a, **k: []
        mw.utc_now = lambda: CAPTURED
        mw.build_elevenforum_pool = stub_pool
        ctx = CollectorContext(write=False, since="2026-10-01", max_pages=1, target_versions={"26H2"})
        for label, value in (("unset", None), ("false", "false"), ("one", "1"), ("yes", "yes")):
            if value is None:
                os.environ.pop(flag, None)
            else:
                os.environ[flag] = value
            results_by_flag[label] = mw.WindowsLearnQnaCollector().collect(ctx)
        os.environ[flag] = "true"
        results_by_flag["true"] = mw.WindowsLearnQnaCollector().collect(ctx)
    finally:
        urllib.request.urlopen = real["urlopen"]
        mw.learn_qna.collect_learn_qna_candidates = real["learn"]
        mw.techcommunity.enumerate_sitemaps = real["enum"]
        mw.build_elevenforum_pool = real["pool"]
        mw.utc_now = real["now"]
        if saved_env is None:
            os.environ.pop(flag, None)
        else:
            os.environ[flag] = saved_env

    dumps = {k: json.dumps(v, sort_keys=True, default=str) for k, v in results_by_flag.items()}
    disabled_labels = ("unset", "false", "one", "yes")
    check("H2 the lane produced real output to compare (this check is not vacuous)",
          len(results_by_flag["unset"]) >= 1 and "learn_qna_search_rss" in dumps["unset"])
    check("H3 flag absent/false/1/yes: the pool builder is never called and no request is made",
          pool_calls["n"] == 1 and network["calls"] == 0, f"pool calls {pool_calls['n']}, network {network['calls']}")
    check("H4 flag absent/false/1/yes: no elevenforum health row and no trace in the output",
          all("elevenforum" not in dumps[k].lower() for k in disabled_labels))
    check("H5 the four disabled spellings produce byte-identical output",
          len({dumps[k] for k in disabled_labels}) == 1)
    check("H6 with the flag the SAME lane gains exactly the third method's health row",
          "elevenforum" in dumps["true"].lower() and mw.ELEVENFORUM_METHOD_ID in dumps["true"]
          and json.dumps([r for r in results_by_flag["true"]], default=str).count(mw.ELEVENFORUM_METHOD_ID)
          == len(results_by_flag["true"]))
    check("H7 SECOND LOCK: the ownership manifest does not list the method id or the source type",
          mw.ELEVENFORUM_METHOD_ID not in co.ALLOWED_METHODS.get(WINDOWS_PRODUCT_ID, set())
          and ef.DEFAULT_SOURCE_TYPE not in co.ALLOWED_SOURCE_TYPES.get(WINDOWS_PRODUCT_ID, set()))
    wf_text = "".join(p.read_text(encoding="utf-8") for p in (_REPO / ".github" / "workflows").glob("*.yml"))
    runner_text = (_SCRIPTS / "run_patch_evidence_collection.py").read_text(encoding="utf-8")
    check("H8 no workflow and not the runner sets or mentions the flag",
          "ELEVENFORUM" not in wf_text.upper() and "ELEVENFORUM" not in runner_text.upper())
    ef_source = (_SCRIPTS / "patch_collectors" / "elevenforum_source.py").read_text(encoding="utf-8")
    import_lines = [ln for ln in ef_source.splitlines() if re.match(r"^\s*(from|import)\s", ln)]
    check("H9 the adapter imports no part of the acceptance authority or the evidence base",
          bool(import_lines) and not any(re.search(r"microsoft_windows|\bbase\b|collector_ownership", ln)
                                         for ln in import_lines), "; ".join(import_lines))
    check("H10 the adapter has no write path: no evidence, health or record writer is referenced",
          not re.search(r"append_evidence_rows|write_text\(|write_bytes\(|(?<![\w.])open\(|yaml\.dump|"
                        r"apply_collector_record_fields|method_health_row", ef_source))

    # ---------------------------------------------------------------- I. KNOWN AUTHORITY WEAKNESS
    threads = {}
    for tid in ("50447", "50506"):
        c, why = ef.parse_thread(f"https://www.elevenforum.com/t/x.{tid}/", fixture(f"thread_{tid}.html"), today=TODAY)
        threads[tid] = c
    check("I1 both fixture threads parse (the demonstration below is not vacuous)",
          all(threads.values()))
    accepted_map = evaluate_all([c for c in threads.values() if c])
    u50447 = "https://www.elevenforum.com/t/security-update-keeps-failing-to-install.50447"
    u50506 = [u for u in accepted_map if u.endswith(".50506")]
    check("I2 CLEAN CASE: thread 50447 (KB5127648 on 26H2) is accepted once, on 26H2 26300.9711, by KB + train",
          [p for p, _ in accepted_map.get(u50447, [])] == ["26H2 26300.9711"]
          and accepted_map[u50447][0][1]["match_basis"] == "exact_kb_feature_train")
    title_50506 = threads["50506"]["report_title"]
    check("I3 thread 50506's own TITLE puts the defect on 26H2 (KB5121794) and never names the 25H2 build",
          "26H2" in title_50506 and "KB5121794" in title_50506 and "26200" not in title_50506, title_50506)
    rejected_50506 = {}
    claims_i: dict = {}
    for rec_i, target_i in ((REC_26H2, TARGET_26H2), (REC_25H2, TARGET_25H2)):
        _acc, rej_i = mw.evaluate_candidates(rec_i, target_i, [c for c in threads.values() if c], CAPTURED, claims_i)
        for row_i in rej_i:
            if row_i["source_url"].endswith(".50506"):
                rejected_50506[rec_i.update_version] = row_i
    check("I4 [AUX-063 RESOLVED by AUX-067] the authority REJECTS 50506 on 25H2 26200.9711 as identity_not_the_subject",
          not u50506 and rejected_50506.get("25H2", {}).get("exclusion_reason") == "identity_not_the_subject"
          and rejected_50506["25H2"].get("counted") is False,
          str({k: v.get("exclusion_reason") for k, v in rejected_50506.items()}))
    row_50506 = rejected_50506.get("25H2", {})
    body_50506 = threads["50506"]["report_text"]
    check("I5 the matched build is the reporter's CURRENT BASELINE in a system-spec line, not the build with the defect",
          row_50506.get("match_basis") == "exact_os_build" and "25H2 26200.9711 (current)" in body_50506
          and "Issue on 26H2" in body_50506)
    check("I6 the 26H2 record the report is actually about does NOT receive it either (no identity of that record is named)",
          "26H2" in rejected_50506 and rejected_50506["26H2"].get("counted") is False)
    check("I7 this is the shared authority's behaviour, not the adapter's: the adapter's candidate carries no identity",
          not any(k in threads["50506"] for k in ("matched_kb", "matched_os_build", "matched_feature_version",
                                                  "target_build", "counted")))
    ledger = (_REPO / "docs" / "ENGINEERING_LEDGER.md").read_text(encoding="utf-8")
    check("I8 the weakness is ledgered AUX-063 Resolved by AUX-067, which records the residual it does not close",
          "| AUX-063 | Resolved |" in ledger and "### AUX-063" in ledger and "AUX-067" in ledger.split("### AUX-063", 1)[1]
          and "### AUX-067" in ledger and "residual" in ledger.split("### AUX-067", 1)[1].lower())

    # ---------------------------------------------------------------- J. duplicates are candidates only
    base_text = "KB5127648 fails to install on my 26H2 laptop with error 0x80070017 every time I try."
    c1 = {"source_url": "https://www.elevenforum.com/t/a.1", "report_text": base_text}
    refs = [{"source_url": "https://other.example/q/1", "text": base_text + " Thanks!"},
            {"source_url": "https://other.example/q/2", "text": "Completely different question about printers."}]
    flagged = ef.duplicate_candidates([c1], refs)
    check("J1 near-identical text from another source is reported as a duplicate CANDIDATE",
          len(flagged) == 1 and flagged[0]["similar_to"] == "https://other.example/q/1"
          and flagged[0]["conclusive"] is False)
    check("J2 the annotation never removes or alters the candidate", c1["report_text"] == base_text)
    check("J3 dissimilar text is not flagged", ef.duplicate_candidates([c1], refs[1:]) == [])
    twin_a = {"source_type": "x", "source_name": "x", "source_url": "https://www.elevenforum.com/t/a.1",
              "parent_title": "KB5127648 fails", "report_title": "KB5127648 fails", "report_text": base_text,
              "source_date": "2026-10-30"}
    twin_b = {**twin_a, "source_url": "https://www.elevenforum.com/t/b.2"}
    acc_twins, _rej = mw.evaluate_candidates(REC_26H2, TARGET_26H2, [twin_a, twin_b], CAPTURED)
    check("J4 identical text under two distinct URLs is NOT collapsed by the authority (URL claims are the key)",
          len(acc_twins) == 2)

    # ---------------------------------------------------------------- K. registry, fixtures, dry run
    entry = next((m for m in am.METHODS if m["method_id"] == mw.ELEVENFORUM_METHOD_ID), None)
    check("K1 the method is registered, status disabled, in the paginated-listing family",
          bool(entry) and entry["status"] == "disabled" and entry["method_family"] == "paginated_listing_enumeration")
    check("K2 the registry records the activation blocker and the challenge failure mode",
          bool(entry) and "AUX-063" in json.dumps(entry) and "challenge_page" in json.dumps(entry))
    check("K3 the registry names the flag that would enable it",
          bool(entry) and mw.ELEVENFORUM_ENABLE_ENV in json.dumps(entry))
    fixture_files = sorted(FIX.glob("*.html"))
    check("K4 the fixture set is complete (4 listings, 20 threads) and every file is marked SYNTHETIC",
          len(list(FIX.glob("listing_*.html"))) == 4 and len(list(FIX.glob("thread_*.html"))) == 20
          and len(fixture_files) == 24
          and all("fixture: SYNTHETIC" in p.read_text(encoding="utf-8") for p in fixture_files),
          str([p.name for p in fixture_files if "fixture: SYNTHETIC" not in p.read_text(encoding="utf-8")]))

    surfaces = (_REPO / "auxsays" / "_data", _REPO / "auxsays" / "updates" / "generated")
    before = tree_digest(*surfaces)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop(flag, None)
    proc = subprocess.run([sys.executable, str(_SCRIPTS / "dry_run_elevenforum_adapter.py")],
                          capture_output=True, text=True, cwd=str(_SCRIPTS), env=env, timeout=120)
    after = tree_digest(*surfaces)
    report = {}
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        pass
    check("K5 DRY RUN: exits 0 and prints a JSON report", proc.returncode == 0 and bool(report), proc.stderr[-300:])
    check("K6 DRY RUN: zero writes, proven twice (the script's own digest and this suite's)",
          report.get("write_surfaces_unchanged") is True and before == after and report.get("write") is False)
    check("K7 DRY RUN: inside the request budget with real spacing",
          report.get("requests", {}).get("total", 99) <= 49 and report.get("requests", {}).get("min_gap_seconds", 0) >= 1.5)
    check("K8 DRY RUN: accepts exactly thread 50447, and 50506 is no longer accepted (AUX-063 resolved by AUX-067)",
          sorted(a["source_url"].rsplit(".", 1)[-1] for a in report.get("accepted", [])) == ["50447"]
          and not any(a.get("known_misattribution") for a in report.get("accepted", [])))
    check("K9 DRY RUN: rejects the other 19 hydrated threads, each with a reason, 50506 among them",
          len(report.get("rejected", [])) == 19 and all(r.get("reason") for r in report.get("rejected", []))
          and any(r["source_url"].endswith(".50506") and r["reason"] == "identity_not_the_subject"
                  for r in report.get("rejected", [])))
    check("K10 DRY RUN: names the listing pages it had to serve empty rather than implying the forum had none",
          len(report.get("unrecorded_listing_pages_served_empty", [])) == 3)

    print()
    print("=" * 78)
    for e in _ERRORS:
        print(f"  - {e}")
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:  # noqa: BLE001
        return True
    return False


def _reason(fn) -> str:
    try:
        fn()
    except ef.ElevenForumError as exc:
        return exc.reason
    return ""

if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
