#!/usr/bin/env python3
"""Tests for the shared Adobe Acrobat (Reader + Pro) community-evidence collector.

Offline only: canned candidate dicts are fed to the pure attribution/version/issue gates and
to row_from_candidate; no network, no repo writes. Proves fail-closed edition attribution,
exact DC-build version identity, the concrete-issue gate, URL specificity, dedup, per-method
health, and that Reader/Pro evidence never cross-contaminates.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_adobe_acrobat_community_collector.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from patch_collectors import adobe_acrobat_community as ac
from patch_collectors.base import PatchRecord

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

R, P = ac.READER_ID, ac.PRO_ID
VER = "26.001.21563"
REC_R = PatchRecord(R, VER, Path(f"2026-05-18-{R}-26-001-21563.md"), "2026-05-18T00:00:00Z", "current", "Adobe Acrobat Reader")
REC_P = PatchRecord(P, VER, Path(f"2026-05-18-{P}-26-001-21563.md"), "2026-05-18T00:00:00Z", "current", "Adobe Acrobat Pro")
CAPTURED = "2026-07-17T00:00:00Z"
THREAD = "https://community.adobe.com/t5/acrobat-reader-discussions/x/td-p/12345678"
REDDIT = "https://www.reddit.com/r/Acrobat/comments/abc123/reader_crash/"


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


def cand(title, body, url=THREAD, date="2026-06-01", st=ac.ADOBE_COMMUNITY_SOURCE_TYPE):
    return {"source_type": st, "source_name": "Adobe Community", "source_url": url,
            "parent_title": title, "report_title": title, "report_text": body, "source_date": date}


def outcome(rec, pid, c):
    row = ac.row_from_candidate(pid, rec, c, CAPTURED)
    return row.get("counted"), row.get("exclusion_reason"), row.get("applicability")


def run() -> int:
    print("=" * 60)
    print("Adobe Acrobat community-evidence collector tests")
    print("=" * 60)

    # --- product attribution ------------------------------------------------
    check("Reader explicit -> accepted for Reader only",
          outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes on launch after update."))[0] is True)
    check("Pro explicit -> accepted for Pro only",
          outcome(REC_P, P, cand("Acrobat Pro 26.001.21563", f"Adobe Acrobat Pro {VER} signing fails after update."))[0] is True)
    both = cand("Acrobat Reader and Pro 26.001.21563", f"Both Adobe Acrobat Reader and Acrobat Pro {VER} fail to install.")
    cr, _, appl_r = outcome(REC_R, R, both)
    cp, _, appl_p = outcome(REC_P, P, both)
    check("explicit Reader+Pro report applies to BOTH", cr is True and cp is True and appl_r == f"{R},{P}" and appl_p == f"{R},{P}", f"r={appl_r} p={appl_p}")
    check("bare 'Acrobat' rejected (generic_acrobat_without_edition)",
          outcome(REC_R, R, cand("Acrobat crash", f"Acrobat {VER} keeps crashing."))[1] == "generic_acrobat_without_edition")
    check("bare 'Adobe Acrobat' rejected (generic)",
          outcome(REC_P, P, cand("Adobe Acrobat crash", f"Adobe Acrobat {VER} crashes."))[1] == "generic_acrobat_without_edition")
    check("bare 'Reader' without Adobe context rejected (missing_product_attribution)",
          outcome(REC_R, R, cand("Reader crash", f"Reader {VER} keeps freezing."))[1] == "missing_product_attribution")
    check("wrong Adobe product rejected",
          outcome(REC_R, R, cand("Premiere crash", f"Adobe Premiere Pro {VER} export fails."))[1] in {"missing_product_attribution", "wrong_product"})
    check("Pro-only report on Reader instance -> wrong_product",
          outcome(REC_R, R, cand("Acrobat Pro 26.001.21563", f"Adobe Acrobat Pro {VER} crashes."))[1] == "wrong_product")
    check("Reader-only report on Pro instance -> wrong_product",
          outcome(REC_P, P, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes."))[1] == "wrong_product")

    # --- patch identity -----------------------------------------------------
    check("exact current version accepted",
          outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes after update."))[0] is True)
    check("earlier version rejected", outcome(REC_R, R, cand("Acrobat Reader old", "Adobe Acrobat Reader 26.001.21529 crashes."))[1] == "missing_exact_patch_version_match")
    check("later version rejected", outcome(REC_R, R, cand("Acrobat Reader new", "Adobe Acrobat Reader 26.001.99999 crashes."))[1] == "missing_exact_patch_version_match")
    check("partial version (major only) rejected", outcome(REC_R, R, cand("Acrobat Reader 26", "Adobe Acrobat Reader 26.001 crashes."))[1] == "missing_exact_patch_version_match")
    check("version only in unrelated build string rejected", outcome(REC_R, R, cand("Acrobat Reader signature", "Adobe Acrobat Reader crashes. My build is 26.001.215639 nightly."))[1] == "missing_exact_patch_version_match")
    check("report before release date rejected", outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes.", date="2026-05-01"))[1] == "source_date_before_or_unverified_against_release")

    # --- issue attribution --------------------------------------------------
    for label, body, want in (
        ("crash accepted", f"Adobe Acrobat Reader {VER} crashes on launch after update.", True),
        ("install failure accepted", f"Adobe Acrobat Reader {VER} failed to install.", True),
        ("printing regression accepted", f"Adobe Acrobat Reader {VER} printing regression after update.", True),
        ("signing failure accepted", f"Adobe Acrobat Reader {VER} signing fails after update.", True),
        ("generic question rejected", f"How do I use Adobe Acrobat Reader {VER} to sign a form?", False),
        ("feature request rejected", f"Please add dark mode to Adobe Acrobat Reader {VER}.", False),
        ("pricing complaint rejected", f"Adobe Acrobat Reader {VER} subscription cost is too expensive.", False),
        ("announcement rejected", f"Adobe Acrobat Reader {VER} release notes and what's new.", False),
    ):
        counted, reason, _ = outcome(REC_R, R, cand("t", body))
        check(f"issue: {label}", (counted is True) == want, f"counted={counted} reason={reason}")

    # --- URL specificity ----------------------------------------------------
    check("Adobe board/search URL rejected (not specific)",
          outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes.", url="https://community.adobe.com/t5/acrobat-reader-discussions/bd-p/x"))[1] == "source_url_not_specific_report")
    check("Reddit /comments/ thread accepted",
          outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes after update.", url=REDDIT, st=ac.REDDIT_SOURCE_TYPE))[0] is True)
    check("acrobat_url_is_specific: td-p thread true", ac.acrobat_url_is_specific(THREAD) is True)
    check("acrobat_url_is_specific: announcements false", ac.acrobat_url_is_specific("https://community.adobe.com/t5/announcements/x/td-p/9") is False)

    # --- structured evidence / official-only invariants ---------------------
    row = ac.row_from_candidate(R, REC_R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes after update."), CAPTURED)
    check("accepted row carries product_id=reader, exact matched_version, applicability, weight 1",
          row["product_id"] == R and row["matched_version"] == VER and row["applicability"] == R and row["source_weight"] == 1,
          str({k: row.get(k) for k in ("product_id", "matched_version", "applicability", "source_weight")}))
    check("accepted row is a community source, not an official release note", row["source_type"] in {ac.ADOBE_COMMUNITY_SOURCE_TYPE, ac.REDDIT_SOURCE_TYPE})
    check("matched_product_alias recorded", row["matched_product_alias"] == "acrobat reader")

    # --- dedup / no cross-contamination -------------------------------------
    dup = [cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes after update."),
           cand("Acrobat Reader 26.001.21563 (repost)", f"Adobe Acrobat Reader {VER} crashes after update.")]  # same URL
    acc, rej = ac.evaluate_candidates(R, REC_R, dup, CAPTURED)
    check("duplicate URL counted once within a method", len(acc) == 1, f"accepted={len(acc)}")
    # Reader evidence row never carries Pro product_id (edition isolation at the row level).
    check("Reader rows are product_id=reader only", all(r["product_id"] == R for r in acc))
    accp, _ = ac.evaluate_candidates(P, REC_P, [cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes.")], CAPTURED)
    check("a Reader-only report yields NO Pro rows (no cross-contamination)", len(accp) == 0, f"pro_accepted={len(accp)}")

    # --- method health ------------------------------------------------------
    check("method_status: accepted -> success", ac._method_status([1], [1], [], []) == "success")
    check("method_status: candidates only -> no_results", ac._method_status([1], [], [1], []) == "no_results")
    check("method_status: accepted + errors -> partial", ac._method_status([1], [1], [], [{"reason": "x"}]) == "partial")
    check("method_status: blocked error -> blocked", ac._method_status([], [], [], [{"reason": "adobe_community_search_fetch_failed:rate_limited"}]) == "blocked")
    check("method_status: non-blocked error -> broken", ac._method_status([], [], [], [{"reason": "network_TimeoutError"}]) == "broken")
    check("method_status: nothing -> no_results", ac._method_status([], [], [], []) == "no_results")

    # --- collect_for_record emits one health row per method (offline, no candidates) ----
    class _NoNet:
        max_pages = 1
        since = None
        target_versions = None
    coll = ac.AdobeAcrobatCollector(R)
    # monkeypatch ALL THREE discovery methods to return [] (no network)
    orig_algolia = ac.adobe_community_algolia_search_candidates
    orig_adobe = ac.adobe_community_search_candidates
    orig_reddit = ac.reddit_search_candidates
    try:
        ac.adobe_community_algolia_search_candidates = lambda *a, **k: []
        ac.adobe_community_search_candidates = lambda *a, **k: []
        ac.reddit_search_candidates = lambda *a, **k: []
        accepted, rejected, health = coll.collect_for_record(REC_R, _NoNet(), CAPTURED)
        method_ids = sorted(h["method_id"] for h in health)
        # Only the productive method runs by default. Measured over the whole recorded history,
        # 143 runs each: algolia 0 blocked / 128 accepted reports; adobe_community_search 143
        # blocked (100%) / 0 accepted; reddit_search 142 blocked / 0 accepted. Keeping the two dead
        # transports was not free -- this collector stops mid-corpus on a wall-clock budget, so the
        # time they spent failing was a RECENT record never reached at all.
        check("collect_for_record runs only the method that produces evidence",
              method_ids == ["adobe_community_algolia_search"], str(method_ids))
        check("the retired transports are recoverable for a deliberate reachability probe",
              ac._retired_methods_enabled() is False
              and "AUXSAYS_ACROBAT_RETIRED_METHODS" in
              (_REPO / "auxsays" / "scripts" / "patch_collectors"
               / "adobe_acrobat_community.py").read_text(encoding="utf-8"))
        check("zero candidates -> zero accepted, honest no_results health", accepted == [] and all(h["status"] == "no_results" for h in health))
        check("health rows carry the collector product_id", all(h["product_id"] == R for h in health))
    finally:
        ac.adobe_community_algolia_search_candidates = orig_algolia
        ac.adobe_community_search_candidates = orig_adobe
        ac.reddit_search_candidates = orig_reddit

    # === Algolia search-index discovery method (Part F) =====================
    # Query construction: exact-version + product-constrained, quoted phrases.
    rq = ac._algolia_search_queries(ac.EDITION_CONFIG[P], VER)
    check("algolia queries are exact-version + product constrained (quoted)",
          f'"{VER}" "Acrobat Pro"' in rq and f'"{VER}" "Adobe Acrobat Pro"' in rq and f'"{VER}"' in rq, str(rq))
    check("algolia query count is capped", len(rq) <= ac.MAX_ALGOLIA_QUERIES)

    # New inSided /questions-{board}/{slug}-{id} thread URLs are accepted as specific.
    Q_URL = "https://community.adobe.com/questions-9/e-sign-acrobat-pro-desktop-crashes-every-time-i-try-to-add-a-signature-field-1561796"
    check("new /questions-N/ thread URL is specific", ac.acrobat_url_is_specific(Q_URL) is True)
    check("legacy /t5/ td-p thread URL still specific", ac.acrobat_url_is_specific(THREAD) is True)
    check("board root /questions-9 rejected (not a thread)", ac.acrobat_url_is_specific("https://community.adobe.com/questions-9") is False)
    check("category /acrobat-7 rejected (not a thread)", ac.acrobat_url_is_specific("https://community.adobe.com/acrobat-7") is False)
    check("topic/show redirect URL rejected (not specific)", ac.acrobat_url_is_specific("https://community.adobe.com/topic/show?tid=1561796&fid=9") is False)

    # Bundle-id edition attribution (com.adobe.Acrobat.Pro == Pro; com.adobe.Reader == Reader).
    pro_bundle = cand("Adobe Crashing when using the Fill & Sign Option",
                      f"Every time I select the tab it crashes. I am on Acrobat {VER} and the crash log names com.adobe.Acrobat.Pro as the faulting process. It is up to date.",
                      url="https://community.adobe.com/questions-9/adobe-crashing-fill-sign-1561211")
    counted_pb, reason_pb, appl_pb = outcome(REC_P, P, pro_bundle)
    check("Pro accepted via com.adobe.Acrobat.Pro bundle id (real Pro #1 shape)",
          counted_pb is True and appl_pb == P, f"counted={counted_pb} reason={reason_pb}")
    check("same com.adobe.Acrobat.Pro report is NOT counted for Reader (wrong_product)",
          outcome(REC_R, R, pro_bundle)[1] == "wrong_product")
    reader_bundle = cand("Reader crash after update",
                         f"Adobe Acrobat Reader {VER} crashes. Faulting application com.adobe.Reader after the update.",
                         url="https://community.adobe.com/questions-9/reader-crash-1562000")
    check("Reader accepted via explicit Acrobat Reader + com.adobe.Reader",
          outcome(REC_R, R, reader_bundle)[0] is True)

    # A concrete Pro report (title carries edition) accepted (real Pro #2 shape).
    pro2 = cand("E-Sign / Acrobat Pro Desktop crashes every time I try to add a signature field",
                f"I use Adobe Pro desktop, version {VER} specifically. When I add a signature field the software freezes then crashes.",
                url=Q_URL)
    check("Pro accepted via title 'Acrobat Pro' + crash (real Pro #2 shape)", outcome(REC_P, P, pro2)[0] is True)

    # Ambiguous 'Acrobat DC' with the exact version still fails closed.
    dc = cand("Acrobat DC (26.001.21529) crashing with eSignatures",
              f"Acrobat DC {VER} crashes when setting up eSignature and initials fields.",
              url="https://community.adobe.com/questions-9/acrobat-dc-crashing-esign-1560885")
    check("ambiguous 'Acrobat DC' exact-version report rejected (generic)",
          outcome(REC_P, P, dc)[1] == "generic_acrobat_without_edition")

    # A hit with a title but empty body/URL yields no candidate (insufficient content).
    check("topic with no canonical url -> no candidate", ac._topic_to_candidate({"title": "x", "firstPost": {"content": "<p>y</p>"}}) is None)
    empty_topic = {"url": Q_URL, "title": "", "firstPost": {"content": ""}}
    check("topic with url but empty title+body -> no candidate", ac._topic_to_candidate(empty_topic) is None)

    # Duplicate thread (same URL from two getTopics rows) counted once.
    dupe_topic = {"url": Q_URL, "title": pro2["report_title"], "firstPost": {"content": f"<p>Acrobat Pro {VER} crashes adding a signature field.</p>", "creationDate": "2026-05-20T00:00:00Z"}}
    orig_creds = ac._algolia_credentials
    orig_search = ac._algolia_search
    orig_get = ac._get_topics
    try:
        ac._algolia_credentials = lambda errors: {"app_id": "APP", "key": "K", "index": "idx"}
        ac._algolia_search = lambda creds, query, errors: [{"id": 1561796}]
        ac._get_topics = lambda ids, errors: [dupe_topic, dupe_topic]
        cands = ac.adobe_community_algolia_search_candidates(ac.EDITION_CONFIG[P], REC_P, _NoNet(), [])
        check("duplicate getTopics rows collapse to one candidate", len(cands) == 1, f"n={len(cands)}")
    finally:
        ac._algolia_credentials = orig_creds
        ac._algolia_search = orig_search
        ac._get_topics = orig_get

    # Search-index blocked -> method 'blocked' (searchToken 403). All methods blocked -> the
    # collector produces zero accepted with only blocked/broken health (collector_blocked shape).
    def _boom_token(errors):
        errors.append({"source_url": ac.ADOBE_SEARCH_TOKEN_URL, "reason": "adobe_search_token_fetch_failed:blocked"})
        return None
    try:
        ac._algolia_credentials = _boom_token
        ac.adobe_community_search_candidates = lambda *a, **k: []
        ac.reddit_search_candidates = lambda *a, **k: []
        # feed the blocked-token error through the real candidates fn to exercise _method_status
        errs: list = []
        cands = ac.adobe_community_algolia_search_candidates(ac.EDITION_CONFIG[P], REC_P, _NoNet(), errs)
        check("searchToken blocked -> algolia yields no candidates + blocked error",
              cands == [] and any("blocked" in str(e.get("reason", "")) for e in errs))
        check("algolia _method_status blocked when only a blocked error present",
              ac._method_status([], [], [], errs) == "blocked", ac._method_status([], [], [], errs))
    finally:
        ac._algolia_credentials = orig_creds
        ac.adobe_community_search_candidates = orig_adobe
        ac.reddit_search_candidates = orig_reddit

    # === Part A: exact-patch discovery window uses the release date, not --since-days =========
    class _Ctx:
        def __init__(self, since=None, max_pages=5):
            self.since = since
            self.max_pages = max_pages
            self.target_versions = None

    def _mk_topic(tid, url, title, body, date):
        return {"id": tid, "url": url, "title": title, "firstPost": {"content": f"<p>{body}</p>", "creationDate": date}}

    def _run_algolia(record, topics, since=None):
        oc, os_, og = ac._algolia_credentials, ac._algolia_search, ac._get_topics
        try:
            ac._algolia_credentials = lambda errors: {"app_id": "A", "key": "K", "index": "i"}
            ac._algolia_search = lambda creds, q, errors: [{"id": t["id"]} for t in topics]
            ac._get_topics = lambda ids, errors: list(topics)
            return ac.adobe_community_algolia_search_candidates(ac.EDITION_CONFIG[record.product_id], record, _Ctx(since=since), [])
        finally:
            ac._algolia_credentials, ac._algolia_search, ac._get_topics = oc, os_, og

    # REC_P release = 2026-05-18. A post-release report ~60 days old survives even when the
    # runner's since window (2026-07-01) would hide it.
    old_url = "https://community.adobe.com/questions-9/acrobat-pro-crash-after-signature-1560999"
    post_release = _mk_topic(1560999, old_url, "Acrobat Pro crash", f"Adobe Acrobat Pro {VER} crashes on launch after the update.", "2026-05-20T00:00:00Z")
    cands = _run_algolia(REC_P, [post_release], since="2026-07-01")
    check("Part A: post-release report >45d old is still DISCOVERED (since window ignored)", len(cands) == 1, f"n={len(cands)}")
    acc, _ = ac.evaluate_candidates(P, REC_P, cands, CAPTURED)
    check("Part A: that discovered post-release report is ACCEPTED end-to-end", len(acc) == 1)
    check("Part A: workflow's 45-day arg cannot hide a valid exact-patch report",
          len(_run_algolia(REC_P, [post_release], since="2026-07-15")) == 1)

    pre_release = _mk_topic(1560001, "https://community.adobe.com/questions-9/pre-release-crash-1560001", "x", f"Adobe Acrobat Pro {VER} crashes.", "2026-05-10T00:00:00Z")
    check("Part A: report dated BEFORE the release date is dropped at discovery", _run_algolia(REC_P, [pre_release]) == [])

    dupe_ids = [_mk_topic(1561796, Q_URL, pro2["report_title"], f"Acrobat Pro {VER} crashes adding a signature field.", "2026-05-20T00:00:00Z")]
    oc2, os2, og2 = ac._algolia_credentials, ac._algolia_search, ac._get_topics
    try:
        ac._algolia_credentials = lambda errors: {"app_id": "A", "key": "K", "index": "i"}
        ac._algolia_search = lambda creds, q, errors: [{"id": 1561796}, {"id": 1561796}]  # same id twice per query
        ac._get_topics = lambda ids, errors: dupe_ids
        check("Part A: duplicate topic ids collapse (one topic fetched)",
              len(ac.adobe_community_algolia_search_candidates(ac.EDITION_CONFIG[P], REC_P, _Ctx(), [])) == 1)
        big = [_mk_topic(2000000 + i, f"https://community.adobe.com/questions-9/t-{2000000+i}", "t", f"Adobe Acrobat Pro {VER} crashes.", "2026-05-20T00:00:00Z") for i in range(ac.MAX_TOPICS_PER_RECORD + 8)]
        ac._algolia_search = lambda creds, q, errors: [{"id": t["id"]} for t in big]
        ac._get_topics = lambda ids, errors: [t for t in big if t["id"] in set(ids)]
        capped = ac.adobe_community_algolia_search_candidates(ac.EDITION_CONFIG[P], REC_P, _Ctx(), [])
        check("Part A: result limit is deterministic (<= MAX_TOPICS_PER_RECORD)", len(capped) <= ac.MAX_TOPICS_PER_RECORD)
    finally:
        ac._algolia_credentials, ac._algolia_search, ac._get_topics = oc2, os2, og2

    check("Part A: exact-version queries never widen to unrelated versions",
          all(VER in q and "26.001.21529" not in q for q in ac._algolia_search_queries(ac.EDITION_CONFIG[P], VER)))
    check("Part A: empty exact-version results -> honest no_results",
          ac._method_status([], [], [], []) == "no_results")

    # === Part B: 1627235-shaped classification + shared canonical identity ===================
    reader_then_pro_license = cand(
        "Acrobat fails to launch after silent Reader update when user license switches to Pro/Std",
        (f"We perform a silent update of Adobe Acrobat Reader 64-bit {VER} to all machines. The user then signs in "
         f"with an Acrobat Pro or Acrobat Standard license and Reader switches to licensed Acrobat mode. After a "
         f"later silent Reader update, Acrobat fails to launch with method not implemented."),
        url="https://community.adobe.com/questions-9/acrobat-fails-to-launch-silent-reader-update-1627235")
    rc, rr, ra = outcome(REC_R, R, reader_then_pro_license)
    check("Part B: Reader update + later Pro LICENSE transition is Reader-only (accepted for Reader)",
          rc is True and ra == R, f"counted={rc} reason={rr} appl={ra}")
    check("Part B: the same thread is NOT Pro evidence (wrong_product)",
          outcome(REC_P, P, reader_then_pro_license)[1] == "wrong_product")

    shared = cand("Both editions crash on launch after update",
                  f"Adobe Acrobat Reader {VER} crashes on launch after the update, and Adobe Acrobat Pro {VER} crashes on launch too.",
                  url="https://community.adobe.com/questions-9/both-reader-and-pro-crash-1563100")
    sr = ac.row_from_candidate(R, REC_R, {**shared, "source_url": ac._canonical_url(shared["source_url"])}, CAPTURED)
    sp = ac.row_from_candidate(P, REC_P, {**shared, "source_url": ac._canonical_url(shared["source_url"])}, CAPTURED)
    check("Part B: explicit shared failure accepted for BOTH", sr["counted"] is True and sp["counted"] is True)
    check("Part B: shared applicability lists both editions on both paths",
          sr["applicability"] == f"{R},{P}" and sp["applicability"] == f"{R},{P}")
    check("Part B: shared evidence has IDENTICAL canonical URL on both product paths", sr["source_url"] == sp["source_url"])
    check("Part B: shared evidence has IDENTICAL canonical evidence id on both product paths", sr["id"] == sp["id"], f"{sr['id']} vs {sp['id']}")
    check("Part B: the two shared rows are still per-product (product_id differs, no cross-contamination)",
          sr["product_id"] == R and sp["product_id"] == P)

    pro_reader_license = cand("Acrobat Pro keeps crashing on launch after opening PDFs",
                              f"Adobe Acrobat Pro {VER} crashes on launch every time I open a PDF and I lose my work. For context, this account was upgraded from an Adobe Reader entitlement license months ago.",
                              url="https://community.adobe.com/questions-9/pro-crash-license-1563200")
    check("Part B: incidental/license-only Reader mention does NOT create Reader evidence",
          outcome(REC_R, R, pro_reader_license)[1] == "wrong_product")
    check("Part B: that same report IS valid Pro evidence", outcome(REC_P, P, pro_reader_license)[0] is True)

    # Per-product writeback cannot duplicate the same shared report as unrelated evidence:
    # within one product the same URL collapses to one row.
    acc_r, _ = ac.evaluate_candidates(R, REC_R, [shared, {**shared, "report_title": shared["report_title"] + " (repost)"}], CAPTURED)
    check("Part B: same shared report counts ONCE per product (URL dedup)", len(acc_r) == 1)
    check("Part B: ambiguous bare 'Acrobat' remains fail-closed",
          outcome(REC_P, P, cand("Acrobat crash", f"Acrobat {VER} keeps crashing.", url="https://community.adobe.com/questions-9/acrobat-crash-1563300"))[1] == "generic_acrobat_without_edition")

    # === Part D: dynamic searchToken handling + no credential leakage =======================
    good_token = {"client_id": "APPID123", "token": "SECURED-TOKEN-XYZ", "availableIndexes": ["adobedme-en-unified"]}
    def _patch_json(fn):
        o = ac._request_json
        ac._request_json = fn
        return o
    orig_json = ac._request_json
    try:
        ac._request_json = lambda url, **k: dict(good_token)
        creds = ac._algolia_credentials([])
        check("Part D: token fetched dynamically at runtime -> app id + key + index",
              creds == {"app_id": "APPID123", "key": "SECURED-TOKEN-XYZ", "index": "adobedme-en-unified"}, str(creds))
        for label, payload in (("missing app id", {"token": "T", "availableIndexes": ["i"]}),
                               ("missing token", {"client_id": "A", "availableIndexes": ["i"]}),
                               ("missing index", {"client_id": "A", "token": "T"}),
                               ("empty indexes", {"client_id": "A", "token": "T", "availableIndexes": []})):
            ac._request_json = lambda url, _p=payload, **k: dict(_p)
            e = []
            check(f"Part D: {label} -> no creds + recorded error", ac._algolia_credentials(e) is None and len(e) == 1)
        ac._request_json = lambda url, **k: ["not", "a", "dict"]  # malformed token response
        e = []
        check("Part D: malformed token response -> no creds + error (not silent)", ac._algolia_credentials(e) is None and len(e) == 1)
        # malformed Algolia response (not a dict) -> no hits, error recorded
        ac._request_json = lambda url, **k: ["unexpected"]
        e = []
        check("Part D: malformed Algolia response -> no hits", ac._algolia_search({"app_id": "A", "key": "K", "index": "i"}, "q", e) == [])
        # malformed getTopics response (not a list) -> empty, no crash
        ac._request_json = lambda url, **k: {"unexpected": True}
        check("Part D: malformed getTopics response -> empty list", ac._get_topics([1], []) == [])
        # transport error -> broken/blocked signal, never silent zero without an error row
        def _raise(url, **k):
            raise ac.AcrobatCommunityAccessError("network_TimeoutError")
        ac._request_json = _raise
        e = []
        ac._algolia_credentials(e)
        check("Part D: token transport failure records an error (visible, not silent)", len(e) == 1 and "search_token" in str(e[0]["reason"]))
    finally:
        ac._request_json = orig_json

    # canonical URL preserved from the authoritative topic endpoint
    canon = ac._topic_to_candidate({"url": "https://community.adobe.com/questions-9/acrobat-pro-crash-1561796", "title": "t",
                                    "firstPost": {"content": "<p>crash</p>", "creationDate": "2026-05-20T00:00:00Z"}})
    check("Part D: canonical thread URL preserved from getTopics", canon["source_url"] == "https://community.adobe.com/questions-9/acrobat-pro-crash-1561796")
    # no secured token leaks into an evidence row
    leak_row = ac.row_from_candidate(P, REC_P, {**pro2, "source_url": ac._canonical_url(pro2["source_url"])}, CAPTURED)
    check("Part D: no secured token leaks into evidence row values",
          not any("SECURED-TOKEN" in str(v) for v in leak_row.values()))

    print()
    print("=" * 60)
    print("Part E: shared DC build, and the veto that has to come with it")
    print("=" * 60)
    # Adobe ships ONE DC build to Reader and to Pro. Requiring the words "Reader" or "Pro" refused
    # 73 of 98 recent candidates -- reports that named the exact build and described a concrete
    # post-install failure -- because Adobe's own forum and UI call the product "Acrobat".
    # The relaxation is not an inference: every Acrobat record states its own `applicability`,
    # derived by the adapter from the release note, and the collector reads THAT.
    from patch_collectors.base import generated_records  # noqa: PLC0415
    real = {(r.product_id, r.update_version): r
            for pid in (R, P) for r in generated_records(pid)}
    live = real.get((P, "26.001.21745"))
    check("Part E: a real Acrobat record declares its shared applicability",
          live is not None and ac.record_applicability(live) == (R, P),
          str(ac.record_applicability(live)) if live else "record missing")

    if live is not None:
        def verdict(text, pid=P, rec=None):
            row = ac.row_from_candidate(pid, rec or live, cand(
                text, text, url="https://community.adobe.com/questions-9/x-1234567",
                date="2026-08-01"), CAPTURED)
            return row.get("counted"), row.get("exclusion_reason")

        counted, reason = verdict("Acrobat 26.001.21745 crashes when opening a signed PDF")
        check("Part E: bare 'Acrobat' + exact build now counts on a shared-build record",
              counted is True, str(reason))
        counted_dc, reason_dc = verdict("Acrobat DC (26.001.21745) crashing with eSignatures")
        check("Part E: 'Acrobat DC' counts too, and 'crashing' is a failure word",
              counted_dc is True, str(reason_dc))
        # Precision the relaxation must NOT cost.
        _, wrong = verdict("Adobe Acrobat Reader 26.001.21745 crashes")
        check("Part E: naming the OTHER edition is still wrong_product",
              wrong == "wrong_product", str(wrong))
        _, nover = verdict("Acrobat crashes all the time")
        check("Part E: bare Acrobat with no build still fails the identity gate",
              nover == "missing_exact_patch_version_match", str(nover))
        _, noappl = verdict("Acrobat 26.001.21563 crashes", pid=R, rec=REC_R)
        check("Part E: a record that declares NO applicability gets no relaxation",
              noappl == "generic_acrobat_without_edition", str(noappl))

        # Naming the build is not blaming it. The shared-build relaxation widens what reaches this
        # gate, so the veto ships WITH it -- this is the defect PR #79 fixed for OBS and DaVinci.
        _, works = verdict("Acrobat 26.001.21745 works fine, it is 26.001.21789 that crashes")
        check("Part E: a build named as WORKING is never counted as failing",
              works == "version_named_but_working", str(works))
        _, rolled = verdict("Acrobat crashes on 26.001.21789 so I rolled back to 26.001.21745")
        check("Part E: a build named as the ROLLBACK target is not counted as failing",
              rolled == "version_named_but_rollback_target", str(rolled))
        affected, _ = verdict("Acrobat has crashed on every launch since 26.001.21745")
        check("Part E: an affirmative failure statement still counts", affected is True)
        # Every Adobe candidate carries the SAME string as parent_title and report_title, so the
        # naive join repeated it -- and repetition is not harmless for any rule that reads word
        # order. A second copy beginning "Acrobat crashes" lands beside the build the reporter
        # rolled back TO, and the outcome classifier reads it as affected.
        dup = ac.row_from_candidate(P, live, {
            "source_type": ac.ADOBE_COMMUNITY_SOURCE_TYPE, "source_name": "Adobe Community",
            "source_url": "https://community.adobe.com/questions-9/x-1234567",
            "parent_title": "Acrobat crashes on 26.001.21789 so I rolled back to 26.001.21745",
            "report_title": "Acrobat crashes on 26.001.21789 so I rolled back to 26.001.21745",
            "report_text": "Acrobat crashes on 26.001.21789 so I rolled back to 26.001.21745",
            "source_date": "2026-08-01"}, CAPTURED)
        check("Part E: a repeated title cannot turn a rollback into a failure",
              dup.get("exclusion_reason") == "version_named_but_rollback_target",
              str(dup.get("exclusion_reason")))

        # Adobe's own Help > About shows the year-prefixed spelling, which admins paste verbatim.
        year, yreason = verdict("Help > About shows 2026.001.21745 and Acrobat will not print")
        check("Part E: the year-prefixed build spelling is the same build",
              year is True, str(yreason))
        check("Part E: the alias is a spelling, not a loosening",
              ac.acrobat_version_aliases("26.001.21745") == ("2026.001.21745",)
              and ac.acrobat_version_aliases("garbage") == ())
        _, other = verdict("Help > About shows 2026.001.21789 and Acrobat will not print")
        check("Part E: a DIFFERENT build in year form is still refused",
              other == "missing_exact_patch_version_match", str(other))

    # The walk order is the reach fix: oldest-first plus a wall-clock budget meant 44 of the 48
    # records released since 2025-12-01 had never been attempted by any method.
    ordered = ac._newest_first(generated_records(R))
    check("Part E: the record walk starts at the most recent patch",
          bool(ordered) and ordered[0].update_published_at >= ordered[-1].update_published_at
          and ordered[0].update_published_at[:4] >= "2026", str(ordered[0].update_published_at))
    check("Part E: and it is deterministic",
          [r.update_version for r in ac._newest_first(generated_records(R))]
          == [r.update_version for r in ordered])

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
