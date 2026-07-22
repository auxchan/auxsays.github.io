#!/usr/bin/env python3
"""Tests for the Microsoft PowerPoint Learn Q&A community-evidence collector (default-off pilot).

Offline only: synthetic PatchRecords/targets and canned candidate dicts; the Learn Q&A and
Reddit sources are monkeypatched, so no network. No _data writes, no live records. Proves the
deterministic PowerPoint acceptance contract (product attribution, exact Version YYMM in
context with reply inheritance + drift guard, Current-Channel consistency, optional-build
cross-check, date, specific URL, concrete issue), dedup, weight, method health, and that the
collector is NOT registered / writes nothing by default. It deliberately does NOT use any
Windows KB / OS-build identity logic.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_microsoft_powerpoint_collector.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

import yaml

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from patch_collectors.base import PatchRecord
import patch_collectors.microsoft_powerpoint as pp

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


TARGET = {
    "update_version": "2605",
    "target_app_version": "2605",
    "target_build": "20026.20076",
    "target_channel": "Current Channel",
    "target_release_date": "2026-05-20T00:00:00Z",
}
REC = PatchRecord("microsoft-powerpoint", "2605", Path("2026-05-20-microsoft-powerpoint-2605.md"), "2026-05-20T00:00:00Z", "current", "Microsoft PowerPoint")
URL = "https://learn.microsoft.com/en-us/answers/questions/2412345/powerpoint-2605-crash"
CAPTURED = "2026-06-01T00:00:00Z"


def cand(parent: str, body: str, *, url: str = URL, date: str = "2026-06-01T00:00:00Z", stype: str = "microsoft_learn_qna", sname: str = "Microsoft Learn Q&A") -> dict:
    return {
        "source_type": stype, "source_name": sname, "source_url": url,
        "parent_title": parent, "report_title": parent, "report_text": body, "source_date": date,
    }


def row(parent: str, body: str, **kw) -> dict:
    return pp.row_from_candidate(REC, TARGET, cand(parent, body, **kw), CAPTURED)


def verdict(parent: str, body: str, **kw) -> tuple:
    r = row(parent, body, **kw)
    return r.get("counted"), r.get("exclusion_reason")


def run() -> int:
    print("=" * 60)
    print("Microsoft PowerPoint Learn Q&A collector tests")
    print("=" * 60)

    # 1. exact Version 2605 + a concrete PowerPoint issue -> accepted
    c, r = verdict("PowerPoint Version 2605 crashes", "After installing PowerPoint Version 2605 it crashes when I open a deck.")
    check("1  accepted: exact Version 2605 + PowerPoint issue", c is True and r is None, f"{c} {r}")

    # 2. exact version in the patch-specific parent title, concrete reply -> accepted by inheritance
    c, r = verdict("Microsoft PowerPoint Version 2605 problem thread", "The presentation crashes every time I start a slideshow after the update.")
    check("2  accepted: exact version in parent title, concrete reply (inheritance)", c is True and r is None, f"{c} {r}")

    # 3. reply drifts to another version -> rejected
    c, r = verdict("PowerPoint Version 2605 issues", "Actually I'm on PowerPoint Version 2603 and that one corrupts my presentation.")
    check("3  rejected: reply drifts to a different version", c is False and r == "reply_drifted_to_other_version", f"{c} {r}")

    # 3b. the title's subject is a DIFFERENT version (target only mentioned in the body) -> rejected
    c, r = verdict("PowerPoint VBA fails in Microsoft 365 Version 2606", "This started for me on Version 2605 too; PowerPoint crashes on that chart action.")
    check("3b rejected: title subject is a different version (target only in body)", c is False and r == "different_version_in_title", f"{c} {r}")

    # 3c. multiple versions named with no single title subject -> rejected as ambiguous
    c, r = verdict("PowerPoint crashing since the update", "I updated PowerPoint Version 2605 and also saw it on Version 2604; it crashes on open.")
    check("3c rejected: multiple versions named, no single subject -> ambiguous", c is False and r == "ambiguous_multiple_versions", f"{c} {r}")

    # 4. bare 2605 with no version context -> rejected
    c, r = verdict("PowerPoint problem", "The 2605 thing keeps crashing on my machine.")
    check("4  rejected: bare four-digit number, no version context", c is False and r == "bare_version_no_context", f"{c} {r}")

    # 5. generic 'latest update' -> rejected
    c, r = verdict("PowerPoint keeps crashing", "PowerPoint crashes constantly after the latest update; no idea which version.")
    check("5  rejected: generic 'latest update' with no exact version", c is False and r == "vague_latest_update", f"{c} {r}")

    # 6. generic Microsoft 365 complaint -> rejected (PowerPoint not named)
    c, r = verdict("Microsoft 365 is slow", "My whole Microsoft 365 install got slow after the update, super frustrating.")
    check("6  rejected: generic Microsoft 365 complaint (no PowerPoint)", c is False and r == "product_not_powerpoint", f"{c} {r}")

    # 7. Word-only / Excel-only / Outlook-only / Teams-only -> rejected
    for app in ("Word", "Excel", "Outlook", "Teams"):
        c, r = verdict(f"{app} Version 2605 crash", f"Microsoft {app} Version 2605 crashes when I save my file.")
        check(f"7  rejected: {app}-only report (PowerPoint not named)", c is False and r == "product_not_powerpoint", f"{c} {r}")

    # 8. exact Version YYMM + compatible Current Channel context -> accepted
    c, r = verdict("PowerPoint Version 2605 on Current Channel", "Current Channel Version 2605: PowerPoint crashes when opening any file.")
    check("8  accepted: exact version with compatible Current Channel context", c is True and r is None, f"{c} {r}")

    # 9. explicit conflicting channel -> rejected
    c, r = verdict("PowerPoint Version 2605 Monthly Enterprise", "On the Monthly Enterprise Channel, PowerPoint Version 2605 crashes on launch.")
    check("9  rejected: explicit conflicting channel (Monthly Enterprise)", c is False and r == "channel_conflict", f"{c} {r}")

    # 10. matching optional full build -> accepted with build match basis
    rrow = row("PowerPoint Version 2605 (Build 20026.20076)", "PowerPoint Version 2605 (Build 20026.20076) crashes on export.")
    check("10 accepted: matching optional full build (build match basis)", rrow.get("counted") is True and rrow.get("match_basis") == "exact_version_channel_build", str({k: rrow.get(k) for k in ("counted", "match_basis", "exclusion_reason")}))

    # 11. mismatched full build -> rejected
    c, r = verdict("PowerPoint Version 2605 crash", "PowerPoint Version 2605 with build 19999.10000 crashes on save.")
    check("11 rejected: mismatched full build", c is False and r == "build_mismatch", f"{c} {r}")

    # 12. report before official release -> rejected
    c, r = verdict("PowerPoint Version 2605 crash", "PowerPoint Version 2605 crashes on open.", date="2026-05-01T00:00:00Z")
    check("12 rejected: report dated before official release", c is False and r == "date_before_release_or_undated", f"{c} {r}")

    # 13. report on the release date -> accepted
    c, r = verdict("PowerPoint Version 2605 crash", "PowerPoint Version 2605 crashes on open.", date="2026-05-20T00:00:00Z")
    check("13 accepted: report on the release date", c is True and r is None, f"{c} {r}")

    # 14. search / category URL -> rejected
    c, r = verdict("PowerPoint Version 2605 crash", "PowerPoint Version 2605 crashes on open.", url="https://learn.microsoft.com/en-us/answers/search?q=powerpoint%202605")
    check("14 rejected: non-specific search/category URL", c is False and r == "no_specific_source_url", f"{c} {r}")

    # 15. specific Learn Q&A question URL, all gates pass -> accepted
    c, r = verdict("PowerPoint Version 2605 crash", "PowerPoint Version 2605 crashes on open.", url="https://learn.microsoft.com/en-us/answers/questions/9988776/powerpoint-2605")
    check("15 accepted: specific Learn Q&A question URL with all gates passing", c is True and r is None, f"{c} {r}")

    # 16. official Microsoft announcement -> rejected
    c, r = verdict("PowerPoint Version 2605 now available", "Microsoft PowerPoint Version 2605 is now available in Current Channel. See what's new.")
    check("16 rejected: official announcement / release note (not a user report)", c is False and r == "official_announcement_not_user_report", f"{c} {r}")

    # 17. concrete crash / corruption / slideshow / save / export / add-in / performance -> accepted
    concrete = [
        ("crash", "PowerPoint Version 2605 crashes immediately on launch."),
        ("presentation corruption", "PowerPoint Version 2605 corrupts my presentation; the file is damaged and won't open."),
        ("slideshow failure", "PowerPoint Version 2605: slideshow fails to start and shows a black screen."),
        ("save failure", "PowerPoint Version 2605 cannot save; I get a save error and lost my work."),
        ("export problem", "PowerPoint Version 2605 fails to export to PDF, export error every time."),
        ("add-in incompatibility", "PowerPoint Version 2605 broke my add-in; the add-in is not working and crashes."),
        ("performance regression", "PowerPoint Version 2605 is very slow now, huge performance regression."),
    ]
    for label, body in concrete:
        c, r = verdict(f"PowerPoint Version 2605 {label}", body)
        check(f"17 accepted: concrete {label}", c is True and r is None, f"{c} {r}")

    # 18. feature request / general question -> rejected
    c, r = verdict("PowerPoint Version 2605 feature", "In PowerPoint Version 2605, please add a proper dark mode. Feature request.")
    check("18 rejected: feature request / general question (no concrete issue)", c is False and r == "not_a_concrete_powerpoint_issue", f"{c} {r}")

    # 19. duplicate canonical URL -> counted once
    d1 = cand("PowerPoint Version 2605 crash", "PowerPoint Version 2605 crashes on open.", url=URL + "/dup")
    d2 = cand("PowerPoint Version 2605 crash (repost)", "PowerPoint Version 2605 crashes on open again.", url=URL + "/dup")
    acc, rej = pp.evaluate_candidates(REC, TARGET, [d1, d2], CAPTURED)
    check("19 duplicate canonical URL counted once (dedup)", len(acc) == 1, f"accepted={len(acc)} rejected={len(rej)}")

    # 20. two independent replies in a patch-specific thread -> counted separately
    t1 = cand("PowerPoint Version 2605 save crash", "PowerPoint Version 2605 crashes when I save.", url=URL + "/reply-a")
    t2 = cand("PowerPoint Version 2605 export fail", "PowerPoint Version 2605 fails to export to PDF.", url=URL + "/reply-b")
    acc2, rej2 = pp.evaluate_candidates(REC, TARGET, [t1, t2], CAPTURED)
    check("20 two independent concrete reports counted separately", len(acc2) == 2, f"accepted={len(acc2)}")

    # 21. source weight is always 1
    check("21 source_weight is always 1", all(a.get("source_weight") == 1 for a in acc2), str([a.get("source_weight") for a in acc2]))

    # 22. one or two accepted -> pilot volume; the collector NEVER stamps consensus_live / a verdict
    accepted_row = acc2[0]
    forbidden = {"consensus_live", "update_consensus_label", "update_report_count", "quick_verdict", "evidence_state"}
    check("22 accepted evidence carries no consensus_live / verdict fields (stays pilot-only)", not (forbidden & set(accepted_row)) and accepted_row.get("counted") is True, str(sorted(forbidden & set(accepted_row))))

    # 23. collector never modifies a generated record / thresholds (evidence-only)
    check("23 collector defines no record-writeback (evidence-only, verdict unchanged)", not hasattr(pp, "apply_consensus_writeback") and not hasattr(pp, "_apply_record_fields"), "collector must not modify records")

    # 24. Learn Q&A reachable, nothing accepted -> no_results (or low_confidence for near-misses)
    check("24 method status: accepted -> success", pp.learn_qna_method_status([{"x": 1}], [{"c": 1}], [], []) == "success")
    check("24 method status: accepted + errors -> partial", pp.learn_qna_method_status([{"x": 1}], [{"c": 1}], [], [{"reason": "x"}]) == "partial")
    check("24 method status: reachable, plain miss -> no_results", pp.learn_qna_method_status([{"x": 1}], [], [{"exclusion_reason": "product_not_powerpoint"}], []) == "no_results")
    check("24 method status: reachable, near-miss -> low_confidence", pp.learn_qna_method_status([{"x": 1}], [], [{"exclusion_reason": "bare_version_no_context"}], []) == "low_confidence")
    check("24 method status: reachable, empty -> no_results", pp.learn_qna_method_status([], [], [], []) == "no_results")
    check("24 method status: parse error -> broken", pp.learn_qna_method_status([], [], [], [{"reason": "learn_qna_search_fetch_failed:feed_parse_failed:ParseError", "blocked_signature": "broken"}]) == "broken")

    # 25. Reddit blocked -> method health blocked; does not weaken acceptance
    check("25 reddit status: not attempted -> disabled", pp.reddit_method_status(False, [], [], [], []) == "disabled")
    check("25 reddit status: attempted + blocked errors -> blocked", pp.reddit_method_status(True, [], [], [], [{"reason": "reddit_search_fetch_failed:all_reddit_endpoint_attempts_failed"}]) == "blocked")
    check("25 reddit status: attempted, reachable, none -> no_results", pp.reddit_method_status(True, [], [], [], []) == "no_results")

    # === PART D — exact-patch ambiguity (fail-closed when a Version YYMM is not unique) =====
    def ambig(is_ambiguous: bool, body: str, build: str = "20026.20076") -> tuple:
        t = dict(TARGET, target_build=build, version_ambiguous=is_ambiguous)
        c = cand(body, body)
        r = pp.row_from_candidate(REC, t, c, CAPTURED)
        return r.get("counted"), r.get("exclusion_reason")

    # D1: exactly one Current Channel record for 2605 -> version-only accepted
    check("D1 one record for a version: version-only report accepted", ambig(False, "PowerPoint Version 2605 crashes on open.") == (True, None))
    # D2: two Current Channel records for 2605 with different builds -> version-only rejected
    check("D2 two records share the version: version-only rejected as ambiguous", ambig(True, "PowerPoint Version 2605 crashes on open.") == (False, "ambiguous_version_needs_build"))
    # D3: same ambiguous pair, exact matching build present -> accepted
    check("D3 ambiguous + exact matching build -> accepted", ambig(True, "PowerPoint Version 2605 (Build 20026.20076) crashes on export.") == (True, None))
    # D4: same pair, mismatched build -> rejected
    check("D4 ambiguous + mismatched build -> rejected", ambig(True, "PowerPoint Version 2605 build 19999.10000 crashes.") == (False, "build_mismatch"))
    # D5: same version on a conflicting channel -> rejected
    check("D5 ambiguous + conflicting channel -> rejected", ambig(True, "PowerPoint Version 2605 on Monthly Enterprise Channel crashes.") == (False, "channel_conflict"))
    # D6: parent title supplies the version but two builds exist -> rejected unless exact build present
    parent_only = pp.row_from_candidate(REC, dict(TARGET, version_ambiguous=True), cand("PowerPoint Version 2605 thread", "It crashes on open every time after the update."), CAPTURED)
    check("D6 parent-title version + ambiguous, no build -> rejected", parent_only.get("counted") is False and parent_only.get("exclusion_reason") == "ambiguous_version_needs_build", str(parent_only.get("exclusion_reason")))
    parent_build = pp.row_from_candidate(REC, dict(TARGET, version_ambiguous=True), cand("PowerPoint Version 2605 (Build 20026.20076) thread", "It crashes on open every time after the update."), CAPTURED)
    check("D6 parent-title version + ambiguous, with exact build -> accepted", parent_build.get("counted") is True, str(parent_build.get("exclusion_reason")))

    # D7: adding a second tracked build flips a previously accepted version-only candidate to fail-closed.
    def _rec(build: str, date: str) -> PatchRecord:
        import tempfile as _tf
        f = _tf.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        f.write("---\n" + yaml.safe_dump({
            "update_entry": True, "product_id": "microsoft-powerpoint", "update_product": "Microsoft PowerPoint",
            "update_status": "current", "update_version": "2605", "target_app_version": "2605",
            "target_channel": "Current Channel", "target_build": build, "update_published_at": date,
        }, sort_keys=False) + "---\nb\n")
        f.close()
        return PatchRecord("microsoft-powerpoint", "2605", Path(f.name), date, "current", "Microsoft PowerPoint")
    one_rec = [_rec("20026.20076", "2026-05-20T00:00:00Z")]
    two_rec = one_rec + [_rec("20026.99999", "2026-05-25T00:00:00Z")]
    amb_one = pp.compute_ambiguous_identities(one_rec)
    amb_two = pp.compute_ambiguous_identities(two_rec)
    key = ("2605", "current channel")
    check("D7 ambiguity map: one tracked build -> version NOT ambiguous", key not in amb_one, str(amb_one))
    check("D7 ambiguity map: a second tracked build -> version becomes ambiguous", key in amb_two, str(amb_two))
    body = "PowerPoint Version 2605 crashes on open."
    before = pp.row_from_candidate(REC, dict(TARGET, version_ambiguous=(key in amb_one)), cand(body, body), CAPTURED)
    after = pp.row_from_candidate(REC, dict(TARGET, version_ambiguous=(key in amb_two)), cand(body, body), CAPTURED)
    check("D7 same version-only candidate: accepted with one record, fail-closed after a second is added",
          before.get("counted") is True and after.get("counted") is False and after.get("exclusion_reason") == "ambiguous_version_needs_build",
          f"before={before.get('counted')} after={after.get('exclusion_reason')}")
    check("D7 ambiguity uses the ACTUAL tracked record set (not a hardcoded list)", pp.compute_ambiguous_identities([]) == set())

    # === PART F — discovery precision + bounded cost ========================================
    check("F query count is hard-bounded (<= MAX_QUERIES_PER_RECORD)", len(pp.search_query_terms(TARGET)) <= pp.MAX_QUERIES_PER_RECORD and pp.MAX_QUERIES_PER_RECORD <= 3, str(pp.search_query_terms(TARGET)))
    # duplicate canonical URLs across queries collapse to one hydrated/evaluated report
    dupes = [cand("PowerPoint Version 2605 crash", "PowerPoint Version 2605 crashes.", url=URL + "/same"),
             cand("PowerPoint Version 2605 crash (again)", "PowerPoint Version 2605 crashes again.", url=URL + "/same"),
             cand("PowerPoint Version 2605 export", "PowerPoint Version 2605 fails to export.", url=URL + "/other")]
    acc_d, rej_d = pp.evaluate_candidates(REC, TARGET, dupes, CAPTURED)
    check("F duplicate canonical URLs across queries are evaluated once (dedup)", len(acc_d) + len(rej_d) == 2, f"reviewed={len(acc_d)+len(rej_d)}")
    # request bound: exactly one search request per query term; no pagination, no retry multiplier,
    # no per-candidate hydration (the RSS item carries the content).
    with tempfile.TemporaryDirectory() as d:
        rec_path = Path(d) / "2026-05-20-microsoft-powerpoint-2605.md"
        rec_path.write_text("---\n" + yaml.safe_dump({
            "layout": "aux-update", "update_entry": True, "product_id": "microsoft-powerpoint",
            "update_product": "Microsoft PowerPoint", "update_version": "2605", "update_status": "current",
            "update_published_at": "2026-05-20T00:00:00Z", "target_channel": "Current Channel",
            "target_build": "20026.20076", "target_app_version": "2605",
        }, sort_keys=False) + "---\nbody\n", encoding="utf-8")
        record = PatchRecord("microsoft-powerpoint", "2605", rec_path, "2026-05-20T00:00:00Z", "current", "Microsoft PowerPoint")
        fetch_calls = {"n": 0}
        orig_fetch = pp.learn_qna._fetch_feed_text
        try:
            def _counting_fetch(url, **kw):
                fetch_calls["n"] += 1
                return (200, "application/rss+xml", "<rss><channel></channel></rss>")
            pp.learn_qna._fetch_feed_text = _counting_fetch
            pp.collect_for_record(record, SimpleNamespace(write=False, since=None, max_pages=5, target_versions=None))
            n_terms = len(pp.search_query_terms(pp.record_target(record)))
            check("F exactly one Learn Q&A request per query term (no pagination / retry explosion)", fetch_calls["n"] == n_terms and n_terms <= pp.MAX_QUERIES_PER_RECORD, f"fetches={fetch_calls['n']} terms={n_terms}")
        finally:
            pp.learn_qna._fetch_feed_text = orig_fetch
    # no unbounded cross-version explosion: discovery is invoked exactly once per record
    disc_calls = {"n": 0}
    orig_disc = pp.learn_qna.collect_learn_qna_candidates
    orig_recs = pp.generated_records
    try:
        pp.learn_qna.collect_learn_qna_candidates = lambda **k: (disc_calls.__setitem__("n", disc_calls["n"] + 1), [])[1]
        two_recs = [REC, PatchRecord("microsoft-powerpoint", "2603", Path("y.md"), "2026-04-14T00:00:00Z", "current", "Microsoft PowerPoint")]
        # give both records real front matter via a temp dir so record_target works
        import tempfile as _tf2
        with _tf2.TemporaryDirectory() as d2:
            paths = []
            for v, dt in (("2605", "2026-05-20T00:00:00Z"), ("2603", "2026-04-14T00:00:00Z")):
                p = Path(d2) / f"{v}.md"
                p.write_text("---\n" + yaml.safe_dump({"update_entry": True, "product_id": "microsoft-powerpoint", "update_product": "Microsoft PowerPoint", "update_status": "current", "update_version": v, "target_app_version": v, "target_channel": "Current Channel", "target_build": f"200{v}.1", "update_published_at": dt}, sort_keys=False) + "---\nb\n", encoding="utf-8")
                paths.append(PatchRecord("microsoft-powerpoint", v, p, dt, "current", "Microsoft PowerPoint"))
            pp.generated_records = lambda pid, tv=None, **k: paths
            pp.PowerPointLearnQnaCollector().collect(SimpleNamespace(write=False, since=None, max_pages=5, target_versions=None))
            check("F cross-version: discovery invoked exactly once per record (no explosion)", disc_calls["n"] == len(paths), f"disc_calls={disc_calls['n']} records={len(paths)}")
    finally:
        pp.learn_qna.collect_learn_qna_candidates = orig_disc
        pp.generated_records = orig_recs

    # --- search terms + record target ---------------------------------------
    check("search terms are exact-version PowerPoint queries (no standalone bare number)", pp.search_query_terms(TARGET) == ["PowerPoint 2605", "PowerPoint Version 2605", "PowerPoint 20026.20076"], str(pp.search_query_terms(TARGET)))
    check("record with no version searches nothing (fail-closed)", pp.search_query_terms({}) == [])

    # --- collect_for_record end-to-end (sources monkeypatched, no network) ----
    with tempfile.TemporaryDirectory() as d:
        rec_path = Path(d) / "2026-05-20-microsoft-powerpoint-2605.md"
        front = {
            "layout": "aux-update", "update_entry": True, "product_id": "microsoft-powerpoint",
            "update_product": "Microsoft PowerPoint", "update_version": "2605", "update_status": "current",
            "update_published_at": "2026-05-20T00:00:00Z", "target_channel": "Current Channel",
            "target_build": "20026.20076", "target_app_version": "2605",
        }
        rec_path.write_text("---\n" + yaml.safe_dump(front, sort_keys=False) + "---\nbody\n", encoding="utf-8")
        record = PatchRecord("microsoft-powerpoint", "2605", rec_path, "2026-05-20T00:00:00Z", "current", "Microsoft PowerPoint")

        orig_lq = pp.learn_qna.collect_learn_qna_candidates
        orig_rd = pp.reddit_source.collect_reddit_candidates
        try:
            def _lq_ok(*, queries, context, errors, source_type, source_name):
                return [cand("PowerPoint Version 2605 crash", "PowerPoint Version 2605 crashes on open.", url=URL + "/ok"),
                        cand("How do I update PowerPoint 2605?", "How do I update to PowerPoint Version 2605 safely?", url=URL + "/howto")]
            pp.learn_qna.collect_learn_qna_candidates = _lq_ok
            pp.reddit_source.collect_reddit_candidates = lambda **k: []  # not attempted by default anyway
            accepted, rejected, health = pp.collect_for_record(record, SimpleNamespace(write=False, since=None, max_pages=1, target_versions=None))
            lq_health = next(h for h in health if h["method_id"] == pp.LEARN_QNA_METHOD_ID)
            rd_health = next(h for h in health if h["method_id"] == pp.REDDIT_METHOD_ID)
            check("collect_for_record: one accepted, one rejected, learn_qna success", len(accepted) == 1 and len(rejected) == 1 and lq_health["status"] == "success", f"acc={len(accepted)} rej={len(rejected)} lq={lq_health['status']}")
            check("collect_for_record: reddit disabled by default -> method health 'disabled'", rd_health["status"] == "disabled", str(rd_health["status"]))
            check("collect_for_record: accepted row is PowerPoint-attributed at version 2605", accepted and accepted[0].get("matched_version") == "2605" and accepted[0].get("applicability") == "microsoft-powerpoint", str(accepted[0].get("matched_version") if accepted else None))

            def _lq_blocked(*, queries, context, errors, source_type, source_name):
                errors.append({"reason": "learn_qna_search_fetch_failed:blocked:rate_limited", "blocked_signature": "blocked"})
                return []
            pp.learn_qna.collect_learn_qna_candidates = _lq_blocked
            accepted2, _rej2, health2 = pp.collect_for_record(record, SimpleNamespace(write=False, since=None, max_pages=1, target_versions=None))
            lq2 = next(h for h in health2 if h["method_id"] == pp.LEARN_QNA_METHOD_ID)
            check("collect_for_record: blocked learn_qna -> blocked health, no accepted", len(accepted2) == 0 and lq2["status"] == "blocked", f"status={lq2['status']}")

            # reddit fallback ENABLED + blocked -> reddit health blocked (does not weaken gates)
            def _rd_blocked(*, subreddits, queries, context, errors, source_type, version_hints=None):
                errors.append({"reason": "reddit_search_fetch_failed:all_reddit_endpoint_attempts_failed"})
                return []
            pp.learn_qna.collect_learn_qna_candidates = lambda **k: []
            pp.reddit_source.collect_reddit_candidates = _rd_blocked
            _acc3, _rej3, health3 = pp.collect_for_record(record, SimpleNamespace(write=False, since=None, max_pages=1, target_versions=None), env={pp.REDDIT_FALLBACK_ENV: "true"})
            rd3 = next(h for h in health3 if h["method_id"] == pp.REDDIT_METHOD_ID)
            check("collect_for_record: reddit fallback enabled + blocked -> reddit health 'blocked'", rd3["status"] == "blocked", str(rd3["status"]))
        finally:
            pp.learn_qna.collect_learn_qna_candidates = orig_lq
            pp.reddit_source.collect_reddit_candidates = orig_rd

    # --- safety: NOT registered + writes nothing by default -----------------
    import run_patch_evidence_collection as runner
    FLAG = runner.POWERPOINT_CONSENSUS_ENABLE_ENV
    check("activation flag name is AUXSAYS_ENABLE_POWERPOINT_CONSENSUS", FLAG == "AUXSAYS_ENABLE_POWERPOINT_CONSENSUS", FLAG)
    check("static COLLECTORS base never contains PowerPoint", "microsoft-powerpoint" not in runner.COLLECTORS, str(sorted(runner.COLLECTORS)))
    check("default runtime registry has NO PowerPoint (no scheduled writeback)", "microsoft-powerpoint" not in runner.build_collectors({}), str(sorted(runner.build_collectors({}))))
    check("flag=true registers PowerPointLearnQnaCollector", runner.build_collectors({FLAG: "true"}).get("microsoft-powerpoint") is pp.PowerPointLearnQnaCollector)
    check("gate predicate True only for canonical true",
          runner.powerpoint_consensus_enabled({FLAG: "true"}) is True
          and runner.powerpoint_consensus_enabled({FLAG: "TRUE"}) is True
          and runner.powerpoint_consensus_enabled({FLAG: " true "}) is True)
    check("gate predicate False for absent/false/0/empty/1/yes/on",
          runner.powerpoint_consensus_enabled({}) is False
          and runner.powerpoint_consensus_enabled({FLAG: "false"}) is False
          and runner.powerpoint_consensus_enabled({FLAG: "0"}) is False
          and runner.powerpoint_consensus_enabled({FLAG: ""}) is False
          and runner.powerpoint_consensus_enabled({FLAG: "1"}) is False
          and runner.powerpoint_consensus_enabled({FLAG: "yes"}) is False
          and runner.powerpoint_consensus_enabled({FLAG: "on"}) is False)
    # enabling PowerPoint does not remove/alter the base collectors
    reg = runner.build_collectors({FLAG: "true"})
    check("enabling PowerPoint leaves the base collectors intact", all(reg.get(pid) is runner.COLLECTORS[pid] for pid in runner.COLLECTORS))

    # dry-run writes nothing / write path reaches append_evidence_rows only
    with tempfile.TemporaryDirectory() as d:
        rec_path = Path(d) / "2026-05-20-microsoft-powerpoint-2605.md"
        rec_path.write_text("---\n" + yaml.safe_dump({
            "layout": "aux-update", "update_entry": True, "product_id": "microsoft-powerpoint",
            "update_product": "Microsoft PowerPoint", "update_version": "2605", "update_status": "current",
            "update_published_at": "2026-05-20T00:00:00Z", "target_channel": "Current Channel",
            "target_build": "20026.20076", "target_app_version": "2605",
        }, sort_keys=False) + "---\nbody\n", encoding="utf-8")
        synthetic = PatchRecord("microsoft-powerpoint", "2605", rec_path, "2026-05-20T00:00:00Z", "current", "Microsoft PowerPoint")
        orig_records = pp.generated_records
        orig_lq = pp.learn_qna.collect_learn_qna_candidates
        orig_append = pp.append_evidence_rows
        calls = {"append": 0}
        try:
            pp.generated_records = lambda pid, tv=None, **k: [synthetic]
            pp.learn_qna.collect_learn_qna_candidates = lambda **k: []  # no network
            pp.append_evidence_rows = lambda rows, *a, **k: (calls.__setitem__("append", calls["append"] + 1), (0, 0, []))[1]

            calls["append"] = 0
            pp.PowerPointLearnQnaCollector().collect(SimpleNamespace(write=False, since=None, max_pages=1, target_versions=None))
            check("dry-run (write=False) NEVER calls append_evidence_rows", calls["append"] == 0, f"append calls={calls['append']}")

            calls["append"] = 0
            pp.PowerPointLearnQnaCollector().collect(SimpleNamespace(write=True, since=None, max_pages=1, target_versions=None))
            check("write path reaches append_evidence_rows (evidence-only)", calls["append"] == 1, f"append calls={calls['append']}")
        finally:
            pp.generated_records = orig_records
            pp.learn_qna.collect_learn_qna_candidates = orig_lq
            pp.append_evidence_rows = orig_append

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
