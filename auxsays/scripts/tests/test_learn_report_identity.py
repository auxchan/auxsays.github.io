#!/usr/bin/env python3
"""One canonical Microsoft Learn Q&A report identity at every dedup site (AUX-078).

A Learn Q&A question URL carries a title slug that follows the title. Every dedup key in the Learn
path was the slugged URL, so a report re-found under an edited title passed every guard and was
counted twice on one patch (measured: four Windows identities, +1 each). The question id is the
identity. `lib.source_segments.learn_report_key` derives it from the URL -- question id + an
explicit segment slot -- and `report_url_key` falls back to the historical normalised URL for every
other host, byte for byte. This suite pins:

  A  the key: one question under any slug/locale/scheme/case/query is one key; two questions, a
     question and its reply, two replies stay distinct; `#answer-<id>` is a REPLY (the URL cannot
     tell an answer from a comment); every non-Learn URL keeps its key byte for byte; the key is
     idempotent; and its reconciliation with `SourceSegment.segment_key` on a parsed thread
  B  the durable append guard (`base.evidence_key` / `append_evidence_rows`) and the write-authority
     validator (`collector_ownership.validate_evidence`)
  C  the shared Learn search-RSS run dedup
  D  Windows: the row id, the run-level dedup, the in-run and cross-run one-report-one-patch claims
  E  Teams: one fetch per question, one candidate per report, provenance on the same key
  F  PowerPoint: the per-record seen set and the run-wide exclusivity map
  G  the orchestrator: checkpoint restore re-keys a legacy seen-set, the reply-harvest key, the
     higher-level exclusion set and the in-run Tier 2 / Level 3 dedup
  H  Tier 2 and Level 3: held ids never re-keyed, a new slug merges into the held row, eviction by
     report identity, question vs reply, product scoping, non-Learn rows unchanged
  I  live eligibility: exclusive-URL counting and the duplicate-citation check
  J  QA's live-source distinctness
  K  the WARN-only read-only diagnostic on a frozen fixture store
  L  the bare-script entry points import and run as subprocesses under a network fence
  M  this suite touched no network and no real data

Frozen synthetic fixtures only: question ids in the 74xxxxx range, invented slugs and texts, no
stored row, no live total. Network is refused in-process before any collector is imported, and every
subprocess runs under a sitecustomize fence that refuses non-loopback DNS/TCP and records attempts.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_learn_report_identity.py
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import socket
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]          # auxsays/
SCRIPTS = ROOT / "scripts"
REPO = ROOT.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# ---- network refusal, installed before any collector module is imported --------------------------
ATTEMPTS = [0]


class _NoNetSocket(socket.socket):
    def connect(self, *args, **kwargs):          # noqa: D102
        ATTEMPTS[0] += 1
        raise OSError("network refused by test_learn_report_identity")

    def connect_ex(self, *args, **kwargs):       # noqa: D102
        ATTEMPTS[0] += 1
        raise OSError("network refused by test_learn_report_identity")


def _no_dns(*args, **kwargs):
    ATTEMPTS[0] += 1
    raise OSError("DNS refused by test_learn_report_identity")


socket.socket = _NoNetSocket                     # type: ignore[misc]
socket.getaddrinfo = _no_dns                     # type: ignore[assignment]

import yaml                                                              # noqa: E402

import audit_learn_report_identity as diag                               # noqa: E402
import orchestrate_evidence_run as orch                                  # noqa: E402
import qa_patch_records as qa                                            # noqa: E402
from lib import collector_ownership as co                                # noqa: E402
from lib import live_eligibility as le                                   # noqa: E402
from lib import maturity                                                 # noqa: E402
from lib import monitoring_health as mh                                  # noqa: E402
from lib import recent_reports as l3                                     # noqa: E402
from lib import source_segments as ss                                    # noqa: E402
from lib import tier2_evidence as t2                                     # noqa: E402
from lib.orchestration import OrchestrationState                         # noqa: E402
from lib.patch_identity import patch_key                                 # noqa: E402
from patch_collectors import base                                        # noqa: E402
from patch_collectors import microsoft_learn_qna_source as lq            # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt                 # noqa: E402
from patch_collectors import microsoft_teams as teams                    # noqa: E402
from patch_collectors import microsoft_windows as mw                     # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


# ---- frozen synthetic fixtures -------------------------------------------------------------------
QA_BASE = "https://learn.microsoft.com/en-us/answers/questions"
QID, QID2, QID3 = "7400001", "7400002", "7400003"
SLUG_A = "printer-stops-after-the-june-update"
SLUG_B = "solved-printer-stops-after-the-june-update"
TC_URL = "https://techcommunity.microsoft.com/discussions/windows11/printer-stops/7400099"
SE_URL = "https://superuser.com/questions/7400098/powerpoint-freezes"
QKEY = f"learn:{QID}:question:{QID}"

WIN = "microsoft-windows-11"
PPT = "microsoft-powerpoint"
TEAMS = "microsoft-teams"


def q(qid: str, slug: str = SLUG_A, frag: str = "") -> str:
    return f"{QA_BASE}/{qid}/{slug}" + (f"#{frag}" if frag else "")


def evidence(url: str, *, product: str = WIN, version: str = "25H2", build: str = "26200.1000",
             counted: bool = True, rid: str = "", source_type: str = "microsoft_learn_qna") -> dict:
    return {
        "id": rid or f"{product}-{base.slug(version)}-row-{base.slug(url)}",
        "product_id": product, "update_version": version, "target_build": build,
        "source_type": source_type, "source_name": "synthetic", "source_url": url,
        "parent_title": "synthetic", "report_title": "synthetic",
        "report_text_excerpt": "synthetic report", "captured_at": "2026-08-01T00:00:00Z",
        "source_date": "2026-08-01", "target_release_date": "2026-07-01",
        "patch_version_matched": True, "matched_version": version, "match_basis": "exact_os_build",
        "counted": counted, "exclusion_reason": None if counted else "synthetic_reason",
        "issue_theme": "", "workflow_area": "", "platform": "", "severity": "",
        "sentiment": "negative", "source_weight": 1,
    }


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


NON_LEARN = [
    TC_URL, TC_URL + "/", TC_URL.upper(), SE_URL,
    "https://github.com/OfficeDev/office-js/issues/7400097",
    "https://www.reddit.com/r/PowerPoint/comments/7400096/slides_vanish/",
    "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=7400095",
    "https://learn.microsoft.com/en-us/windows/release-health/status-windows-11-25h2",
    "https://learn.microsoft.com/en-us/answers/a/7400094",
    f"{QA_BASE}/{QID}/{SLUG_A}#comments",
    f"{QA_BASE}/{QID}/{SLUG_A}/extra",
    f"https://learn.microsoft.com:443/en-us/answers/questions/{QID}/{SLUG_A}",
    f"https://learn.microsoft.com.example.test/en-us/answers/questions/{QID}/{SLUG_A}",
    f"ftp://learn.microsoft.com/en-us/answers/questions/{QID}/{SLUG_A}",
    "   ", "",
]

QAPAGE_TEMPLATE = (
    '<html><head><script type="application/ld+json">{{"@context":"https://schema.org",'
    '"@type":"QAPage","mainEntity":{{"@type":"Question","id":"{qid}",'
    '"name":"PowerPoint crash","dateCreated":"2026-08-10T09:00:00Z",'
    '"text":"<p>{qtext}</p>","author":"Asker","authorId":"aaaaaaaa-0000-4000-8000-000000000001",'
    '"suggestedAnswer":[{{"@type":"Answer","id":"11","text":"<p>{atext}</p>",'
    '"author":"Replier","authorId":"bbbbbbbb-0000-4000-8000-000000000002",'
    '"updatedAt":"2026-08-12T09:00:00Z"}}]}}}}</script></head><body>'
    '<ul><li data-test-id="comment-21"><a href="/en-us/users/na/?userid=cccccccc-0000-4000-8000-000000000003">'
    'Commenter</a><p>Same here after the update.</p><time datetime="2026-08-13T09:00:00Z"></time></li></ul>'
    '</body></html>')


def qapage(qid: str = QID, qtext: str = "PowerPoint closes when I open a deck.",
           atext: str = "Same for me.") -> str:
    return QAPAGE_TEMPLATE.format(qid=qid, qtext=qtext, atext=atext)


# ---- A: the key ----------------------------------------------------------------------------------
def part_a() -> None:
    print("A  the canonical key")
    k = ss.learn_report_key
    check("A1 two title slugs of one question are one report", k(q(QID, SLUG_A)) == k(q(QID, SLUG_B)) == QKEY,
          f"{k(q(QID, SLUG_A))} {k(q(QID, SLUG_B))}")
    spellings = [f"http://learn.microsoft.com/en-us/answers/questions/{QID}/{SLUG_A}",
                 f"https://LEARN.MICROSOFT.COM/en-us/answers/questions/{QID}/{SLUG_A}",
                 f"https://learn.microsoft.com/de-de/answers/questions/{QID}/{SLUG_B}",
                 f"https://learn.microsoft.com/answers/questions/{QID}/{SLUG_A}",
                 f"https://learn.microsoft.com/en-us/answers/questions/{QID}/",
                 f"https://learn.microsoft.com/en-us/answers/questions/{QID}",
                 f"  {q(QID, SLUG_A)}/  ",
                 f"{q(QID, SLUG_A)}?orderby=newest"]
    check("A2 scheme, host case, locale, missing slug, trailing slash, whitespace and a query do not "
          "make a second report", {k(u) for u in spellings} == {QKEY}, str({u: k(u) for u in spellings}))
    check("A3 two different questions with the same slug text are two reports",
          k(q(QID, SLUG_A)) != k(q(QID2, SLUG_A)) and k(q(QID2, SLUG_A)) == f"learn:{QID2}:question:{QID2}")
    keys = {k(q(QID)), k(q(QID, frag="answer-11")), k(q(QID, frag="answer-12")),
            k(q(QID, frag="comment-11"))}
    check("A4 the question, two replies and a comment of one thread are four reports",
          len(keys) == 4 and "" not in keys, str(keys))
    check("A5 an #answer- anchor is a REPLY: the URL cannot tell an answer from a comment",
          k(q(QID, SLUG_B, "answer-11")) == f"learn:{QID}:reply:11"
          and ":answer:" not in k(q(QID, SLUG_B, "answer-11")),
          k(q(QID, SLUG_B, "answer-11")))
    check("A6 an anchored reply under two slugs is one reply",
          k(q(QID, SLUG_A, "answer-11")) == k(q(QID, SLUG_B, "ANSWER-11")))
    unknown = [u for u in NON_LEARN if k(u) != ""]
    check("A7 every non-Learn URL, unknown fragment, unknown path shape and foreign host yields no key",
          not unknown, str(unknown))
    drift = [u for u in NON_LEARN if ss.report_url_key(u) != base.normalize_url(u)]
    check("A8 ...and its report_url_key is base.normalize_url byte for byte", not drift, str(drift))
    samples = NON_LEARN + spellings + [q(QID, frag="answer-11"), q(QID, frag="comment-21")]
    check("A9 the key is idempotent, so a persisted key set can be re-keyed safely",
          all(ss.report_url_key(ss.report_url_key(u)) == ss.report_url_key(u) for u in samples))

    page = qapage()
    for slug in (SLUG_A, SLUG_B):
        thread = ss.parse_learn_qna_thread(q(QID, slug), page)
        question = thread.question()
        answers = thread.answers()
        comments = [s for s in thread.segments if s.segment_type == ss.SEGMENT_COMMENT]
        check(f"A10 [{slug[:6]}] the synthetic thread parses into a question, one answer, one comment",
              thread.ok and question is not None and len(answers) == 1 and len(comments) == 1,
              f"{thread.parse_status} {[s.segment_type for s in thread.segments]}")
        if not (question and answers and comments):
            continue
        check(f"A11 [{slug[:6]}] question: the URL key is 'learn:' + segment_key",
              k(question.segment_url) == "learn:" + question.segment_key == QKEY,
              f"{k(question.segment_url)} vs {question.segment_key}")
        check(f"A12 [{slug[:6]}] comment by its #comment- URL: the URL key is 'learn:' + segment_key",
              k(comments[0].segment_url) == "learn:" + comments[0].segment_key
              == f"learn:{QID}:comment:21", k(comments[0].segment_url))
        check(f"A13 [{slug[:6]}] answer: the URL key is the reply slot, never claimed as an answer",
              k(ss.anchor_url(q(QID, slug), answers[0])) == k(answers[0].segment_url)
              == f"learn:{QID}:reply:11" != "learn:" + answers[0].segment_key)
        check(f"A14 [{slug[:6]}] anchor_url writes #answer- for a COMMENT too, so its key is a reply",
              "#answer-21" in ss.anchor_url(q(QID, slug), comments[0])
              and k(ss.anchor_url(q(QID, slug), comments[0])) == f"learn:{QID}:reply:21")


# ---- B: the durable append guard and the write authority -------------------------------------------
def part_b(tmp: Path) -> None:
    print("B  the durable append guard")
    store = tmp / "b_store.yml"
    base.append_evidence_rows([evidence(q(QID, SLUG_A))], path=store)
    before = store.read_bytes()
    added_rows: list = []
    held: list = []
    added, total, _ = base.append_evidence_rows([evidence(q(QID, SLUG_B))], path=store,
                                                out_added=added_rows, out_already_held=held)
    check("B1 a slug variant of a held report on the same patch is refused as already held",
          added == 0 and total == 1 and len(held) == 1 and not added_rows, f"{added} {total} {len(held)}")
    check("B2 ...and the store bytes are unchanged", store.read_bytes() == before)
    stored = base.load_evidence(store)
    check("B3 the held row wins: its source_url and id are the ones first stored",
          len(stored) == 1 and stored[0]["source_url"] == q(QID, SLUG_A)
          and stored[0]["id"] == evidence(q(QID, SLUG_A))["id"], str(stored[0].get("source_url")))
    added, _t, _ = base.append_evidence_rows([evidence(q(QID, SLUG_B), build="26200.2000")], path=store)
    check("B4 the same question on ANOTHER patch is not this guard's to refuse", added == 1)

    fresh = tmp / "b_fresh.yml"
    added, _t, _ = base.append_evidence_rows(
        [evidence(q(QID)), evidence(q(QID, frag="answer-11"), counted=False),
         evidence(q(QID, SLUG_B, "answer-12"), counted=False)], path=fresh)
    check("B5 a question and two anchored replies of one thread stay three rows", added == 3, str(added))
    added, _t, _ = base.append_evidence_rows(
        [evidence(q(QID), product=TEAMS, version="25200.1000.0000.0001", build=""),
         evidence(q(QID, SLUG_B), product=TEAMS, version="25210.1000.0000.0001", build="")], path=fresh)
    check("B6 Teams: one thread stored per Teams version stays one row per version", added == 2, str(added))
    added, _t, _ = base.append_evidence_rows([evidence(q(QID2, SLUG_A))], path=fresh)
    check("B7 a different question with the same slug text is a new row", added == 1)

    batch = tmp / "b_batch.yml"
    held = []
    added, _t, _ = base.append_evidence_rows([evidence(q(QID3, SLUG_A)), evidence(q(QID3, SLUG_B))],
                                             path=batch, out_already_held=held)
    check("B8 two spellings inside ONE batch keep one row, and that is not published as 'already held'",
          added == 1 and not held, f"{added} {len(held)}")

    tc = tmp / "b_tc.yml"
    added, _t, _ = base.append_evidence_rows(
        [evidence(TC_URL, source_type="microsoft_tech_community"),
         evidence(TC_URL.upper() + "/", source_type="microsoft_tech_community"),
         evidence(TC_URL.replace("7400099", "7400100"), source_type="microsoft_tech_community")], path=tc)
    check("B9 Tech Community keeps its historical identity: case/slash collapse, a new thread does not",
          added == 2, str(added))
    row = evidence(TC_URL)
    check("B10 evidence_key for a non-Learn URL is the pre-AUX-078 tuple byte for byte",
          base.evidence_key(row, "source_url") == (WIN, "25H2", "26200.1000", base.normalize_url(TC_URL)))
    check("B11 evidence_key's id slot is never re-keyed",
          base.evidence_key(evidence(q(QID), rid="X-Id/"), "id") == (WIN, "25H2", "26200.1000", "x-id"))

    print("B  the write-authority validator agrees with the guard")
    real_keys = co._existing_patch_keys
    co._existing_patch_keys = lambda _pid: {(WIN, "25H2", "26200.1000")}
    try:
        before_text = yaml.safe_dump({"schema_version": 1, "evidence": [evidence(q(QID, SLUG_A))]})
        dup_text = yaml.safe_dump({"schema_version": 1, "evidence": [
            evidence(q(QID, SLUG_A)), evidence(q(QID, SLUG_B))]})
        ok_text = yaml.safe_dump({"schema_version": 1, "evidence": [
            evidence(q(QID, SLUG_A)), evidence(q(QID2, SLUG_B))]})
        code = ""
        try:
            co.validate_evidence(WIN, before_text, dup_text)
        except co.OwnershipViolation as exc:
            code = str(getattr(exc, "code", "") or exc)
        check("B12 a slug variant appended behind the guard's back is a duplicate URL to the validator",
              "evidence_duplicate_url" in code, code)
        clean = True
        try:
            co.validate_evidence(WIN, before_text, ok_text)
        except co.OwnershipViolation as exc:
            clean = False
            code = str(exc)
        check("B13 ...while a genuinely new question is accepted (non-vacuous control)", clean, code)
    finally:
        co._existing_patch_keys = real_keys


# ---- C: the shared search-RSS run dedup -----------------------------------------------------------
def part_c() -> None:
    print("C  the shared Learn search-RSS run dedup")
    feeds = {"KB0000001": [{"source_url": q(QID, SLUG_A), "source_date": "2026-08-02"}],
             "26200.1000": [{"source_url": q(QID, SLUG_B), "source_date": "2026-08-03"},
                            {"source_url": q(QID2, SLUG_B), "source_date": "2026-08-03"}]}
    real_req, real_sleep = lq.request_learn_qna_feed, lq.learn_qna_sleep
    lq.request_learn_qna_feed = lambda query, **_k: [dict(c) for c in feeds[query]]
    lq.learn_qna_sleep = lambda _s: None
    try:
        got = lq.collect_learn_qna_candidates(queries=list(feeds), context=SimpleNamespace(since=None),
                                              errors=[])
    finally:
        lq.request_learn_qna_feed, lq.learn_qna_sleep = real_req, real_sleep
    urls = [c["source_url"] for c in got]
    check("C1 one question surfaced by two queries under two slugs is one candidate",
          urls == [q(QID, SLUG_A), q(QID2, SLUG_B)], str(urls))


# ---- D: Windows ------------------------------------------------------------------------------------
def _stub_row(record, target, candidate, captured_at):
    return {"source_url": candidate["source_url"], "counted": True, "exclusion_reason": None,
            "target_build": record.target_build, "evidence_valid_for_current_patch": True}


def part_d() -> None:
    print("D  Windows")
    rec1 = base.PatchRecord(WIN, "25H2", Path("w1.md"), "2026-07-14T00:00:00Z", "current", "Windows 11",
                            "26200.1000")
    rec2 = base.PatchRecord(WIN, "25H2", Path("w2.md"), "2026-08-11T00:00:00Z", "current", "Windows 11",
                            "26200.2000")
    target = {"target_feature_version": "25H2", "target_kb": "KB0000001", "target_os_build": "26200.1000",
              "target_release_date": "2026-07-14T00:00:00Z", "update_version": "25H2"}

    def cand(url: str) -> dict:
        return {"source_type": "microsoft_learn_qna", "source_name": "Microsoft Learn Q&A",
                "source_url": url, "parent_title": "Printer stops", "report_title": "Printer stops",
                "report_text": "Printing stops after the update.", "source_date": "2026-07-20"}

    ida = mw.row_from_candidate(rec1, target, cand(q(QID, SLUG_A)), "2026-08-01T00:00:00Z")["id"]
    idb = mw.row_from_candidate(rec1, target, cand(q(QID, SLUG_B)), "2026-08-01T00:00:00Z")["id"]
    check("D1 a Learn row's id is minted from the report identity, so two slugs mint one id",
          ida == idb == f"{WIN}-25h2-microsoft-learn-qna-learn-{QID}-question-{QID}", f"{ida} | {idb}")
    tc_row = mw.row_from_candidate(rec1, target, {**cand(TC_URL), "source_type": "microsoft_tech_community"},
                                   "2026-08-01T00:00:00Z")
    check("D2 a non-Learn row keeps its URL-derived id byte for byte",
          tc_row["id"] == f"{WIN}-{base.slug('25H2')}-{base.slug(mw.SOURCE_TYPE)}-{base.slug(TC_URL)}",
          tc_row["id"])

    real_row, real_load = mw.row_from_candidate, mw.load_evidence
    mw.row_from_candidate = _stub_row
    try:
        acc, rej = mw.evaluate_candidates(rec1, target, [cand(q(QID, SLUG_A)), cand(q(QID, SLUG_B))],
                                          "2026-08-01T00:00:00Z")
        check("D3 two slugs of one question in one candidate list are evaluated once",
              len(acc) + len(rej) == 1, f"{len(acc)} {len(rej)}")
        claims: dict = {}
        a1, _r1 = mw.evaluate_candidates(rec1, target, [cand(q(QID, SLUG_A))], "t", claims)
        a2, r2 = mw.evaluate_candidates(rec2, target, [cand(q(QID, SLUG_B))], "t", claims)
        check("D4 in one run, a later patch meeting the same question under a new slug refuses it",
              len(a1) == 1 and not a2 and r2 and r2[0].get("exclusion_reason") == "cross_patch_duplicate",
              str([r.get("exclusion_reason") for r in r2]))
        mw.load_evidence = lambda *a, **k: [evidence(q(QID, SLUG_A), build="26200.1000"),
                                            evidence(TC_URL, build="26200.1000",
                                                     source_type="microsoft_tech_community")]
        stored = mw.claimed_urls()
        check("D5 cross-run claims are keyed on the report identity for Learn",
              stored.get(QKEY) == (WIN, "25H2", "26200.1000"), str(stored))
        check("D6 ...and on the historical canonical URL for every other host",
              stored.get(lq.canonical_learn_qna_url(TC_URL).lower()) == (WIN, "25H2", "26200.1000"),
              str(stored))
        a3, r3 = mw.evaluate_candidates(rec2, target, [cand(q(QID, SLUG_B))], "t", dict(stored))
        check("D7 across runs, a stored report re-found under a new slug for another patch is refused",
              not a3 and r3 and r3[0].get("exclusion_reason") == "cross_patch_duplicate",
              str([r.get("exclusion_reason") for r in r3]))
        a4, _r4 = mw.evaluate_candidates(rec1, target, [cand(q(QID, SLUG_B))], "t", dict(stored))
        check("D8 the holding patch re-finding its own report under a new slug is not a cross-patch "
              "refusal (the append guard dedups it)", len(a4) == 1)
    finally:
        mw.row_from_candidate, mw.load_evidence = real_row, real_load


# ---- E: Teams --------------------------------------------------------------------------------------
def part_e() -> None:
    print("E  Teams")
    record = base.PatchRecord(TEAMS, "25200.1000.0000.0001", Path("t.md"), "2026-08-01T00:00:00Z",
                              "current", "Microsoft Teams")
    raw = [{"source_url": q(QID, SLUG_A), "parent_title": "Teams crash"},
           {"source_url": q(QID, SLUG_B), "parent_title": "Teams crash"},
           {"source_url": q(QID2, SLUG_A), "parent_title": "Other"}]
    fetched: list[str] = []

    def fetch(url: str) -> str:
        fetched.append(url)
        return qapage(qid=QID2 if f"/{QID2}/" in url else QID)

    real = teams.qna_source.collect_learn_qna_candidates
    teams.qna_source.collect_learn_qna_candidates = lambda **_k: [dict(r) for r in raw]
    try:
        cands = teams.discover_learn_qna(record, SimpleNamespace(since=None), [], fetch_page=fetch)
    finally:
        teams.qna_source.collect_learn_qna_candidates = real
    check("E1 one thread fetch per QUESTION: a second slug of a fetched thread is not refetched",
          len(fetched) == 2 and fetched[0].startswith(q(QID, SLUG_A)), str(fetched))
    check("E2 ...and its segments are offered once",
          sum(1 for c in cands if f"/{QID}/" in c["source_url"]) == 3, str([c["source_url"] for c in cands]))

    pool = [{"source_url": q(QID, SLUG_A), "discovery_method": teams.QNA_METHOD_ID},
            {"source_url": q(QID, SLUG_B), "discovery_method": teams.QNA_METHOD_ID},
            {"source_url": q(QID, SLUG_B, "answer-11"), "discovery_method": teams.QNA_METHOD_ID},
            {"source_url": TC_URL, "discovery_method": teams.TC_METHOD_ID}]
    kept, provenance = teams.dedupe_candidates(pool)
    check("E3 two slugs of one question collapse; its reply and a Tech Community thread stay",
          [c["source_url"] for c in kept] == [q(QID, SLUG_A), q(QID, SLUG_B, "answer-11"), TC_URL],
          str([c["source_url"] for c in kept]))
    check("E4 provenance is keyed on the same identity the per-method accounting reads",
          set(provenance) == {teams.candidate_key(c) for c in kept}, str(sorted(provenance)))
    check("E5 a Tech Community candidate keeps its historical key",
          teams.candidate_key({"source_url": TC_URL + "/"}) == base.normalize_url(TC_URL + "/"))


# ---- F: PowerPoint ---------------------------------------------------------------------------------
def part_f() -> None:
    print("F  PowerPoint")
    rx = base.PatchRecord(PPT, "2608", Path("p1.md"), "2026-08-12T00:00:00Z", "current",
                          "Microsoft PowerPoint", "20000.20100")
    ry = base.PatchRecord(PPT, "2609", Path("p2.md"), "2026-09-09T00:00:00Z", "current",
                          "Microsoft PowerPoint", "20100.20100")
    tx = {"update_version": "2608", "target_build": "20000.20100"}
    ty = {"update_version": "2609", "target_build": "20100.20100"}

    def stub(record, target, candidate, captured_at):
        return {"source_url": candidate["source_url"], "counted": True, "exclusion_reason": None,
                "target_build": target["target_build"]}

    real = ppt.row_from_candidate
    ppt.row_from_candidate = stub
    try:
        seen: set = set()
        acc, rej = ppt.evaluate_candidates(rx, tx, [{"source_url": q(QID, SLUG_A)},
                                                    {"source_url": q(QID, SLUG_B)}], "t", seen, {})
        check("F1 the per-record seen set evaluates one question once, whatever its slug",
              len(acc) + len(rej) == 1 and QKEY in seen, f"{len(acc)} {len(rej)} {sorted(seen)}")
        run_map: dict = {}
        ppt.evaluate_candidates(rx, tx, [{"source_url": q(QID, SLUG_A)}], "t", set(), run_map)
        acc2, rej2 = ppt.evaluate_candidates(ry, ty, [{"source_url": q(QID, SLUG_B)}], "t", set(), run_map)
        check("F2 run-wide exclusivity: another patch meeting the question under a new slug refuses it",
              not acc2 and rej2 and rej2[0].get("exclusion_reason") == "cross_version_duplicate",
              str([r.get("exclusion_reason") for r in rej2]))
        acc3, _ = ppt.evaluate_candidates(rx, tx, [{"source_url": q(QID2)},
                                                   {"source_url": q(QID2, frag="answer-11")}], "t", set(), {})
        check("F3 a question and its anchored reply are two candidates", len(acc3) == 2, str(len(acc3)))
        seen_se: set = set()
        ppt.evaluate_candidates(rx, tx, [{"source_url": SE_URL + "/"}], "t", seen_se, {})
        check("F4 a non-Learn candidate keeps its historical seen key",
              seen_se == {SE_URL.lower()}, str(seen_se))
    finally:
        ppt.row_from_candidate = real


# ---- G: the orchestrator ---------------------------------------------------------------------------
PKEY = f"{PPT}|2608|20000.20100"
PREC = base.PatchRecord(PPT, "2608", Path("x.md"), "2026-08-01", "current", "Microsoft PowerPoint",
                        "20000.20100")
L3_TEXT = "PowerPoint crashes every time I open a presentation that contains a video."
LINKED_TEXT = ("Since the latest PowerPoint update, PowerPoint crashes every time I open a presentation "
               "that contains a video.")


def part_g(tmp: Path) -> None:
    print("G  the orchestrator")
    me = SimpleNamespace()
    legacy = SimpleNamespace(seen_urls_by_patch={PKEY: [q(QID, SLUG_A).lower(), SE_URL.lower()]},
                             accepted_url_owners={q(QID, SLUG_A).lower(): PKEY, SE_URL.lower(): PKEY})
    orch.Pipeline._restore_url_state(me, legacy)
    check("G1 a pre-AUX-078 checkpoint's seen-set is re-keyed to report identities on restore",
          me._seen == {PKEY: {QKEY, SE_URL.lower()}}, str(me._seen))
    check("G2 ...and so is its run-wide ownership map", me._run_urls == {QKEY: PKEY, SE_URL.lower(): PKEY},
          str(me._run_urls))
    current = SimpleNamespace(seen_urls_by_patch={PKEY: sorted(me._seen[PKEY])},
                              accepted_url_owners=dict(me._run_urls))
    again = SimpleNamespace()
    orch.Pipeline._restore_url_state(again, current)
    check("G3 a current checkpoint restores unchanged (the key is idempotent)",
          again._seen == me._seen and again._run_urls == me._run_urls)
    real = ppt.row_from_candidate
    ppt.row_from_candidate = lambda record, target, cand, captured_at: {
        "source_url": cand["source_url"], "counted": True, "exclusion_reason": None,
        "target_build": target["target_build"]}
    try:
        acc, rej = ppt.evaluate_candidates(PREC, {"update_version": "2608", "target_build": "20000.20100"},
                                           [{"source_url": q(QID, SLUG_B)}], "t", me._seen[PKEY],
                                           me._run_urls)
    finally:
        ppt.row_from_candidate = real
    check("G4 so a resumed run does not re-evaluate a report it saw before the checkpoint",
          not acc and not rej, f"{len(acc)} {len(rej)}")

    # The reply harvest: a reply already seen under one slug is not re-harvested under another.
    reply_text = "PowerPoint crashes on open every time since Version 2608 (Build 20000.20100)."

    def drive(seen: set) -> list:
        state = OrchestrationState()
        state.method_results = [{"method_id": "m", "patch_key": PKEY, "accepted_rows": [],
                                 "resolvable_rows": [{
                                     "source_url": q(QID, SLUG_B), "exclusion_reason": "missing_exact_build",
                                     "report_text": "PowerPoint closes when I open a deck.",
                                     "parent_title": "PowerPoint crash", "report_title": "",
                                     "source_date": "2026-08-10", "source_type": "microsoft_learn_qna",
                                     "source_name": "Microsoft Learn Q&A"}]}]
        pipe = SimpleNamespace(_records={PKEY: PREC}, _seen={PKEY: set(seen)},
                               context_fetch=lambda _u: (qapage(atext=reply_text), "ok"),
                               context_max_fetches=4, _persist_url_state=lambda *a, **k: None)
        out = orch.Pipeline.resolve_context(pipe, state)
        outcomes = (out.method_plan.get("context_resolution") or {}).get("outcomes") or []
        return [r for o in outcomes for r in (o.get("independent_reports") or [])]

    control = drive(set())
    check("G5 control: the synthetic reply qualifies as an independent report",
          len(control) == 1, str(control))
    blocked = drive({ss.report_url_key(q(QID, SLUG_A, "answer-11"))})
    check("G6 a reply already seen under the question's earlier slug is not harvested again",
          blocked == [], str(blocked))

    # The higher-level exclusion set and the in-run Tier 2 / Level 3 dedup.
    def rejected(url: str) -> dict:
        return {"product_id": PPT, "update_version": "2608", "source_url": url,
                "source_type": "microsoft_learn_qna", "exclusion_reason": "missing_exact_build",
                "tier2_full_text": L3_TEXT, "parent_title": "PowerPoint crashes opening a video deck",
                "report_title": "", "report_text_excerpt": L3_TEXT, "source_date": "2026-08-20",
                "original_post_date": "2026-08-10"}

    def write_tiers(counted: list, rows: list) -> OrchestrationState:
        state = OrchestrationState()
        state.method_results = [{"tier2_source_rows": rows}]
        pipe = SimpleNamespace(_records={PKEY: PREC}, write=False,
                               evidence_path=tmp / "g_none_evidence.yml",
                               tier2_path=tmp / "g_none_t2.yml", recent_path=tmp / "g_none_l3.yml")
        orch.Pipeline._write_tier2(pipe, state, counted)
        return state

    st = write_tiers([], [rejected(q(QID, SLUG_A))])
    check("G7 control: the synthetic rejection reaches Level 3",
          (st.recent_changes or {}).get("candidates") == 1, str(st.recent_changes))
    st = write_tiers([evidence(q(QID, SLUG_A), product=PPT, version="2608", build="20000.20100")],
                     [rejected(q(QID, SLUG_B))])
    check("G8 a report confirmed under one slug is excluded from Level 3 under another",
          (st.recent_changes or {}).get("candidates") == 0, str(st.recent_changes))
    check("G9 ...and evicted from Tier 2 by the same identity",
          (st.tier2_changes or {}).get("stored") == 0, str(st.tier2_changes))
    st = write_tiers([], [rejected(q(QID, SLUG_A)), rejected(q(QID, SLUG_B))])
    check("G10 two slugs in one run are one Tier 2 candidate", (st.tier2_changes or {}).get("candidates") == 1,
          str(st.tier2_changes))
    check("G11 ...and one Level 3 candidate", (st.recent_changes or {}).get("candidates") == 1,
          str(st.recent_changes))
    linked = dict(rejected(q(QID, SLUG_A)), tier2_full_text=LINKED_TEXT, report_text_excerpt=LINKED_TEXT)
    st = write_tiers([], [linked])
    check("G12 control: the update-linked rejection is stored as an update-linked Tier 2 row",
          (st.tier2_changes or {}).get("stored") == 1, str(st.tier2_changes))
    st = write_tiers([], [linked, rejected(q(QID, SLUG_B))])
    check("G13 a report update-linked under one slug is excluded from Level 3 under another",
          (st.recent_changes or {}).get("candidates") == 0, str(st.recent_changes))


# ---- H: Tier 2 and Level 3 -------------------------------------------------------------------------
def t2row(url: str, product: str = PPT, **extra) -> dict:
    return {"report_id": t2.report_identity(product, url), "product_id": product, "source_url": url,
            "source_report_id": t2._source_report_id(url), "report_date": "2026-08-10",
            "report_title": "synthetic", "classification": t2.TIER_UNRESOLVED, **extra}


def part_h() -> None:
    print("H  Tier 2 and Level 3")
    pinned = hashlib.sha256(f"{PPT}|{q(QID, SLUG_A).lower()}".encode("utf-8")).hexdigest()[:16]
    check("H1 a held report id is never re-keyed: report_identity still hashes the URL",
          t2.report_identity(PPT, q(QID, SLUG_A)) == f"{PPT}:{pinned}")
    held = t2row(q(QID, SLUG_A))
    merged, stats = t2.merge_tier2_rows([held], [t2row(q(QID, SLUG_B), report_title="newer")],
                                        confirmed_urls=set())
    check("H2 Tier 2: a held report re-found under a new slug merges INTO the held row",
          len(merged) == 1 and stats["added"] == 0 and merged[0]["report_id"] == held["report_id"]
          and merged[0]["source_url"] == q(QID, SLUG_A) and merged[0]["report_title"] == "newer",
          f"{len(merged)} {stats} {merged[0].get('source_url')}")
    _m, stats = t2.merge_tier2_rows([held], [], confirmed_urls={q(QID, SLUG_B)})
    check("H3 Tier 2: a confirmation under another slug evicts the held row", stats["promoted_out"] == 1,
          str(stats))
    merged, _s = t2.merge_tier2_rows([held], [t2row(q(QID, SLUG_B, "answer-11"))], confirmed_urls=set())
    check("H4 Tier 2: a reply is not its question", len(merged) == 2)
    merged, _s = t2.merge_tier2_rows([held], [t2row(q(QID, SLUG_B), product=TEAMS)], confirmed_urls=set())
    check("H5 Tier 2: one question under two products stays per product", len(merged) == 2)
    merged, stats = t2.merge_tier2_rows([t2row(SE_URL)], [t2row(SE_URL), t2row(SE_URL + "-other")],
                                        confirmed_urls=set())
    check("H6 Tier 2: non-Learn rows merge on the report id exactly as before",
          len(merged) == 2 and stats["added"] == 1, str(stats))
    merged, _s = t2.merge_tier2_rows([], [t2row(q(QID, SLUG_A)), t2row(q(QID, SLUG_B))], confirmed_urls=set())
    check("H7 Tier 2: two slugs arriving in one batch are one row", len(merged) == 1, str(len(merged)))

    window = t2.ReleaseWindow(product_id=PPT, update_version="2608", target_build="20000.20100",
                              released_on="2026-08-01")
    rej = {"product_id": PPT, "source_url": q(QID, SLUG_A), "source_type": "microsoft_learn_qna",
           "exclusion_reason": "missing_exact_build", "tier2_full_text": L3_TEXT,
           "parent_title": "PowerPoint crashes opening a video deck", "report_text_excerpt": L3_TEXT,
           "original_post_date": "2026-08-10"}

    def build(exclude):
        return l3.recent_report_from_rejection(
            rej, windows=[window], captured_at="t", is_concrete=ppt.concrete_issue,
            states_problem=orch._l3_states_problem, states_target_build=orch._l3_states_target_build,
            exclude_urls=exclude)

    check("H8 control: the synthetic rejection builds a Level 3 card", build(set()) is not None)
    check("H9 Level 3: a report at a higher level under another slug is excluded",
          build({ss.report_url_key(q(QID, SLUG_B))}) is None)
    check("H10 Level 3: a caller passing plain normalised URLs is still honoured",
          build({q(QID, SLUG_A).lower()}) is None)
    card = build(set()).as_dict()
    other = dict(card, report_id=t2.report_identity(PPT, q(QID, SLUG_B)), source_url=q(QID, SLUG_B),
                 report_title="retitled")
    merged, stats = l3.merge_recent_reports([card], [other], promoted_urls=set())
    check("H11 Level 3: a held card re-found under a new slug merges into the held card",
          len(merged) == 1 and merged[0]["report_id"] == card["report_id"]
          and merged[0]["source_url"] == q(QID, SLUG_A) and stats["added"] == 0, f"{len(merged)} {stats}")
    _m, stats = l3.merge_recent_reports([card], [], promoted_urls={q(QID, SLUG_B)})
    check("H12 Level 3: promotion under another slug evicts the held card", stats["promoted_out"] == 1,
          str(stats))
    second = dict(other, report_title="a different headline")
    merged, stats = l3.merge_recent_reports([], [card, second], promoted_urls=set())
    check("H14 Level 3: two slugs arriving in one batch are one card", len(merged) == 1 and stats["added"] == 1,
          f"{len(merged)} {stats}")
    check("H13 the in-run merge key is product-scoped and falls back to the report id off Learn",
          t2.report_merge_key(PPT, q(QID, SLUG_B), "x") == f"{PPT}|{QKEY}"
          and t2.report_merge_key(PPT, SE_URL, "rid-1") == "rid-1")


# ---- I: live eligibility ---------------------------------------------------------------------------
def part_i() -> None:
    print("I  live eligibility")
    k1, k2 = (WIN, "25H2", "26200.1000"), (WIN, "25H2", "26200.2000")
    groups = {k1: [evidence(q(QID, SLUG_A)), evidence(q(QID, SLUG_B)), evidence(q(QID2))]}
    check("I1 two slugs of one question are ONE exclusive report", le.exclusive_url_counts(groups) == {k1: 2},
          str(le.exclusive_url_counts(groups)))
    split = {k1: [evidence(q(QID, SLUG_A))], k2: [evidence(q(QID, SLUG_B), build="26200.2000")]}
    check("I2 one question counted on two identities under two slugs is exclusive to neither",
          le.exclusive_url_counts(split) == {k1: 0, k2: 0}, str(le.exclusive_url_counts(split)))
    tc_groups = {k1: [evidence(TC_URL), evidence(TC_URL.upper() + "/"),
                      evidence(TC_URL.replace("7400099", "7400100"))]}
    check("I3 non-Learn exclusivity is unchanged", le.exclusive_url_counts(tc_groups) == {k1: 2})
    record = {"product_id": WIN, "update_version": "25H2", "target_build": "26200.1000",
              "update_published_at": "2026-07-14"}
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    thresholds = mh.Thresholds(max_age_days=14, min_healthy_families=2)
    dup = le.evaluate(record, {k1: [evidence(q(QID, SLUG_A)), evidence(q(QID, SLUG_B))]}, emh_rows=[],
                      now=now, thresholds=thresholds)
    clean = le.evaluate(record, {k1: [evidence(q(QID, SLUG_A)), evidence(q(QID2, SLUG_B))]}, emh_rows=[],
                        now=now, thresholds=thresholds)
    check("I4 two slugs of one question are a duplicate citation", "duplicate_citation_urls" in dup.reasons,
          str(dup.reasons))
    check("I5 ...two questions are not (non-vacuous control)", "duplicate_citation_urls" not in clean.reasons,
          str(clean.reasons))


# ---- J: QA live-source distinctness -----------------------------------------------------------------
def part_j() -> None:
    print("J  QA live-source distinctness")
    n = qa.LIVE_MIN_ACCEPTED_REPORTS
    key = patch_key(WIN, "25H2", "26200.1000")

    def claim(urls: list) -> set:
        data = {"product_id": WIN, "update_version": "25H2", "target_build": "26200.1000",
                "evidence_state": "consensus_live", "consensus_collection_status": "consensus_live",
                "evidence_state_label": maturity.CONSENSUS_LIVE.evidence_state_label,
                "intelligence_stage": maturity.CONSENSUS_LIVE.intelligence_stage,
                "update_report_count": n, "confirmed_patch_specific_report_count": n,
                "accepted_report_sources": [{"source_url": u, "patch_version_matched": True} for u in urls]}
        errs, _w = qa.scan_live_consensus_claims([(Path("f.md"), data)], {key: n}, None)
        return {e["code"] for e in errs}

    distinct = [q(str(7410000 + i)) for i in range(n)]
    renamed = distinct[:-1] + [q(str(7410000), SLUG_B)]
    check("J1 control: N distinct questions are N distinct reports",
          "live_sources_not_distinct" not in claim(distinct), str(claim(distinct)))
    check("J2 a live claim citing one question under two slugs is not independent corroboration",
          "live_sources_not_distinct" in claim(renamed), str(claim(renamed)))


# ---- K: the diagnostic -----------------------------------------------------------------------------
def fixture_site(tmp: Path) -> Path:
    site = tmp / "site"
    (site / "_data").mkdir(parents=True)
    (site / "updates" / "generated").mkdir(parents=True)
    rows = [
        evidence(q(QID, SLUG_A), product=PPT, version="2608", build="20000.20100"),
        evidence(q(QID, SLUG_B), product=PPT, version="2608", build="20000.20100"),
        evidence(q(QID, frag="answer-11"), product=PPT, version="2608", build="20000.20100"),
        evidence(q(QID, SLUG_B), product=PPT, version="2609", build="20100.20100"),
        evidence(q(QID2, SLUG_A), product=PPT, version="2608", build="20000.20100"),
        evidence(q(QID3, SLUG_A), product=PPT, version="2608", build="", counted=False),
        evidence(q(QID3, SLUG_B), product=PPT, version="2608", build="", counted=False),
        evidence(SE_URL, product=PPT, version="2608", build="20000.20100", source_type="stack_exchange"),
    ]
    base.write_evidence_file(rows, site / "_data" / "consensus_evidence.yml")
    return site


def part_k(tmp: Path) -> None:
    print("K  the WARN-only read-only diagnostic")
    site = fixture_site(tmp)
    store = site / "_data" / "consensus_evidence.yml"
    before = store.read_bytes()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = diag.main(["--root", str(site)])
    text = out.getvalue()
    warns = [ln for ln in text.splitlines() if ln.startswith("WARN class_a")]
    check("K1 the diagnostic exits 0 when it finds a counted duplicate (WARN-only)", rc == 0, str(rc))
    check("K2 it names exactly the one class (a) group: one question counted twice on one patch",
          len(warns) == 1 and f"report={QKEY}" in warns[0] and "store_rows=[0, 1]" in warns[0]
          and "build=20000.20100" in warns[0], str(warns))
    infos = [ln for ln in text.splitlines() if ln.startswith("INFO spelling")]
    check("K3 store-wide it also names the uncounted spelling pair, and nothing else",
          len(infos) == 2 and any(f"learn:{QID3}:" in ln for ln in infos), str(infos))
    check("K4 it prints no title and no slug", SLUG_A not in text and SLUG_B not in text)
    check("K5 it is read-only", store.read_bytes() == before)
    broken = tmp / "broken_site"
    (broken / "_data").mkdir(parents=True)
    with contextlib.redirect_stdout(io.StringIO()):
        rc_missing = diag.main(["--root", str(broken)])
    check("K6 an unreadable store is exit 2, never a silent clean bill", rc_missing == 2, str(rc_missing))


# ---- L: bare-script entry points, fenced -----------------------------------------------------------
FENCE = r'''
import os, socket
_LOG = os.environ.get("AUX_TEST_NETFENCE_LOG", "")
def _note(kind, what):
    if _LOG:
        with open(_LOG, "a", encoding="utf-8") as fh:
            fh.write(kind + "\t" + str(os.getpid()) + "\t" + what + "\n")
def _loop(host):
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    host = str(host).strip().lower().strip("[]")
    return host in ("", "localhost", "::1", "0.0.0.0") or host.startswith("127.")
_oc, _ox, _og = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo
def _guard(sock, address):
    if getattr(sock, "family", None) not in (socket.AF_INET, socket.AF_INET6):
        return
    host = address[0] if isinstance(address, tuple) and address else address
    if not _loop(host):
        _note("ATTEMPT", "connect " + repr(host))
        raise OSError("fenced: non-loopback connect refused")
def _connect(self, address):
    _guard(self, address)
    return _oc(self, address)
def _connect_ex(self, address):
    _guard(self, address)
    return _ox(self, address)
def _gai(host, *a, **k):
    if not _loop(host):
        _note("ATTEMPT", "dns " + repr(host))
        raise socket.gaierror("fenced: DNS refused")
    return _og(host, *a, **k)
socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex
socket.getaddrinfo = _gai
_note("loaded", "fence")
'''


def part_l(tmp: Path) -> None:
    print("L  bare-script entry points run as subprocesses, network-fenced")
    fence_dir = tmp / "fence"
    fence_dir.mkdir()
    (fence_dir / "sitecustomize.py").write_text(FENCE, encoding="utf-8")
    log = tmp / "fence.log"
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}
    env.update({"PYTHONPATH": str(fence_dir), "AUX_TEST_NETFENCE_LOG": str(log),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    site = fixture_site(tmp / "l")
    runs = [
        ("L1 the diagnostic runs as a bare script and finds the fixture group",
         [sys.executable, str(SCRIPTS / "audit_learn_report_identity.py"), "--root", str(site)],
         SCRIPTS.parent, lambda out: f"report={QKEY}" in out),
        ("L2 the orchestrator imports as a bare script",
         [sys.executable, str(SCRIPTS / "orchestrate_evidence_run.py"), "--help"], REPO, None),
        ("L3 the collection runner imports as a bare script",
         [sys.executable, str(SCRIPTS / "run_patch_evidence_collection.py"), "--help"], REPO, None),
        ("L4 the live-eligibility projection imports as a bare script",
         [sys.executable, str(SCRIPTS / "build_live_eligibility_projection.py"), "--help"], REPO, None),
        ("L5 qa_patch_records imports with only the scripts directory on its path",
         [sys.executable, "-c", "import qa_patch_records, patch_collectors.base as b; "
                                "print(b.report_url_key('" + q(QID, SLUG_B) + "'))"],
         SCRIPTS, lambda out: QKEY in out),
    ]
    for label, cmd, cwd, expect in runs:
        try:
            proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=300)
            ok = proc.returncode == 0 and (expect is None or expect(proc.stdout))
            detail = f"rc={proc.returncode} {proc.stderr.strip()[-300:]}"
        except subprocess.TimeoutExpired:
            ok, detail = False, "timeout"
        check(label, ok, detail)
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    loaded = sum(1 for ln in lines if ln.startswith("loaded"))
    attempts = [ln for ln in lines if ln.startswith("ATTEMPT")]
    check("L6 the fence was active in every subprocess", loaded >= len(runs), f"loaded={loaded}")
    check("L7 and no subprocess attempted a non-loopback connection or lookup", not attempts, str(attempts))


def tracked_data_digest() -> str:
    digest = hashlib.sha256()
    for sub in ("_data", "updates"):
        for path in sorted((ROOT / sub).rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
                digest.update(sha(path.read_bytes()).encode("ascii"))
    return digest.hexdigest()


def run() -> int:
    print("=" * 78)
    print("AUX-078  one canonical Microsoft Learn Q&A report identity at every dedup site")
    print("=" * 78)
    data_before = tracked_data_digest()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for part in (part_a, lambda: part_b(tmp), part_c, part_d, part_e, part_f,
                     lambda: part_g(tmp), part_h, part_i, part_j, lambda: part_k(tmp),
                     lambda: part_l(tmp)):
            try:
                part()
            except Exception as exc:  # noqa: BLE001 - a crash is a NAMED failure, never a lost tail
                check(f"part raised {type(exc).__name__}", False, traceback.format_exc()[-600:])
    print("M  this suite changed nothing real")
    check("M1 auxsays/_data and auxsays/updates are byte-identical after the suite",
          tracked_data_digest() == data_before)
    check("M2 no in-process network attempt", ATTEMPTS[0] == 0, str(ATTEMPTS[0]))
    print()
    for label in FAILURES:
        print(f"  failed: {label}")
    print("=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
