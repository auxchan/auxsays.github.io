#!/usr/bin/env python3
"""Microsoft Teams community evidence: the acceptance contract, and what it refuses.

WHY EACH GATE EXISTS. Every rejection below was observed on a live calibration thread, not invented.
Of the first eight Learn Q&A threads carrying a tracked Teams build, the build belonged to the
person asking for help exactly ONCE. In the others it was a support agent's ("Reports point to it
starting after Teams build X"), a responder's working comparison ("I have tested this in version X
and I am still able to..."), a tenant-wide reference ("the most current version right now in our
tenant is X"), or the thread was about a different product state entirely -- Citrix VDI, a Mac
client, the Insider ring. A collector that read the build from "somewhere on the page" would have
published every one of them as a report against the tracked Windows patch.

THE CONTRACT. A report counts only when the COMPLETE tracked build appears in text its own author
wrote, describing a concrete failure, on or after the release date, at a specific URL, for the
tracked identity (New Teams / Windows / Public cloud), with the build in the role of the failing
version rather than a fix, rollback, comparison or reference.

Offline and deterministic: no network. Run:
    PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_microsoft_teams_community.py
"""
from __future__ import annotations

import fnmatch
import sys
import tempfile
import yaml
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import run_patch_evidence_collection as runner          # noqa: E402
from lib import collector_ownership as ownership
from lib.method_routing import HEALTH_STATUSES
from patch_collectors import base, runtime_budget as rb, techcommunity_source                        # noqa: E402
from patch_collectors import microsoft_teams as teams    # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label + ("  --  " + detail if detail else ""))
        _ERRORS.append(label)


BUILD = "26198.304.4946.9672"
RELEASE = "2026-08-03T00:00:00Z"
SPECIFIC_URL = "https://learn.microsoft.com/en-us/answers/questions/5984300/teams-meeting-crash"

RECORD = base.PatchRecord(
    product_id="microsoft-teams", update_version=BUILD, path=Path("teams.md"),
    update_published_at=RELEASE, update_status="current", update_product="Microsoft Teams")


def judge(text, date="2026-09-01", url=SPECIFIC_URL, title="Teams fails after update"):
    candidate = {
        "source_type": teams.QNA_SOURCE_TYPE, "source_name": teams.QNA_SOURCE_NAME,
        "source_url": url, "parent_title": title, "report_title": title,
        "report_text": text, "source_date": date,
    }
    return teams.evaluate_candidate(RECORD, candidate, "2026-09-29T00:00:00Z")


def run() -> int:
    print("=" * 78)
    print("Microsoft Teams community evidence contract")
    print("=" * 78)

    accepted = judge("Teams crashes every time I join a meeting since the update. "
                     "I am on Windows 11, Teams version " + BUILD + ".")
    check("A a complete tracked build plus a concrete failure is accepted",
          accepted.get("counted") is True, str(accepted.get("exclusion_reason")))

    def rejected(label, text, expect="", **kw):
        row = judge(text, **kw)
        reason = str(row.get("exclusion_reason") or "")
        ok = row.get("counted") is not True and (not expect or expect in reason)
        check(label, ok, "counted=" + str(row.get("counted")) + " reason=" + reason)

    rejected("B a report dated before the release is rejected",
             "Teams crashes constantly on " + BUILD + ".", "source_date", date="2026-07-01")
    rejected("C 'the latest Teams update' establishes no patch identity",
             "Teams crashes after the latest update.", "missing_exact_patch_version_match")
    rejected("D a partial YYDDD prefix is not a patch identity",
             "Teams build 26198 crashes on launch.", "missing_exact_patch_version_match")
    rejected("E a Mac report is a different product state",
             "On my Mac, Teams " + BUILD + " crashes on launch.", "platform_mac")
    rejected("F a Teams-on-the-web report is a different product state",
             "Teams on the web fails to load, version " + BUILD + ".", "platform_web")
    rejected("G a VDI/Citrix report is a different product state",
             "In our Citrix VDI, Teams " + BUILD + " freezes.", "platform_vdi")
    rejected("H a Government-cloud report is a different product state",
             "In our GCC High tenant Teams " + BUILD + " crashes.", "cloud_government")
    rejected("H2 a Sovereign/Gallatin report is a different product state",
             "On Gallatin, Teams " + BUILD + " crashes.", "cloud_sovereign")
    rejected("I a Classic Teams report is a different edition",
             "Classic Teams " + BUILD + " hangs on start.", "teams_edition_classic")
    rejected("I2 an Insider/preview-ring report is not the stable channel",
             "Teams Insider " + BUILD + " crashes on launch.", "ring_preview")
    rejected("J a build named as WORKING is not evidence against it",
             "No issues on " + BUILD + ", works fine in our tenant.", "working")
    rejected("K a build named as the FIX is not evidence against it",
             "This crash is fixed in Teams " + BUILD + ".", "fix_target")
    rejected("L a build someone ROLLED BACK TO is their fix, not their failure",
             "I rolled back to " + BUILD + " and the crash stopped.", "rollback")
    rejected("L2 a build offered as a current-version reference is not a failure claim",
             "Can our tenant control feature updates? The most current version right now in "
             "our tenant for Teams is: " + BUILD + ".", "reference")
    rejected("N a concrete problem with no exact patch is not consensus evidence",
             "Teams keeps crashing after an update, version unknown.",
             "missing_exact_patch_version_match")
    rejected("O an announcement is not a user report",
             "Teams " + BUILD + " is now rolling out with new features.", "not_a_real_issue_report")
    rejected("Q a search or generic forum URL is not a specific report",
             "Teams crashes on " + BUILD + " every meeting.", "source_url_not_specific_report",
             url="https://learn.microsoft.com/en-us/answers/questions/")

    # KEEP-COUNTABLE counterparts. A veto that also swallows real failure claims is worse than no
    # veto, so each directional cue is paired with the phrasing it must NOT refuse.
    keep = judge("The crash is still not fixed in " + BUILD + " and happens daily.")
    check("L3 'still not fixed in <build>' remains a failure claim about that build",
          keep.get("counted") is True, str(keep.get("exclusion_reason")))
    keep2 = judge("I rolled back from " + BUILD + " because Teams kept crashing on launch.")
    check("L4 'rolled back FROM <build>' remains a failure claim about that build",
          keep2.get("counted") is True, str(keep2.get("exclusion_reason")))

    # Foreign-identity ALIASES. The tracked Windows build is the one identity VDI shares, so the
    # exact-build gate cannot back this veto up -- coverage has to be in the cue itself.
    rejected("G2 a Windows Virtual Desktop report is a different product state",
             "After our image moved to Teams " + BUILD
             + " every Windows Virtual Desktop session host crashes.", "platform_vdi")
    rejected("G3 an RDSH session-host report is a different product state",
             "On our RDSH session hosts Teams " + BUILD + " crashes when sharing.", "platform_vdi")

    # KEEP-COUNTABLE counterparts for the identity veto. A Windows user proves a defect is
    # Windows-specific by NAMING the other platform, so an unscoped identity search refuses
    # exactly the best-evidenced reports. Each cue is paired with the phrasing it must NOT refuse.
    def kept(label, text):
        row = judge(text)
        check(label, row.get("counted") is True, str(row.get("exclusion_reason")))

    kept("G4 an ordinary-English 'on the horizon' is not a VDI identity",
         "A fix is on the horizon but Teams " + BUILD + " still crashes on launch today.")
    kept("G5 'RDS licensing' in a neighbouring sentence is not a VDI identity",
         "Our RDS licensing renewal is unrelated. Teams " + BUILD + " crashes every meeting.")
    kept("E2 naming macOS as the WORKING contrast keeps the Windows failure claim",
         "Windows 11 here. Teams " + BUILD
         + " crashes on join. Works on my Mac but not Windows.")
    kept("G6 a foreign identity the reporter explicitly DENIES is not their identity",
         "To be clear this is NOT a Citrix VDI problem, our physical Windows desktops on Teams "
         + BUILD + " crash.")
    kept("I3 naming Classic as the working contrast keeps the new-Teams failure claim",
         "Classic Teams was fine; new Teams " + BUILD + " crashes on launch.")
    kept("I4 naming mobile as the working contrast keeps the desktop failure claim",
         "The Android app is fine, but Teams " + BUILD + " on my Windows desktop crashes.")

    # M. AUTHORSHIP. A reply's build belongs to the reply's author. The segment parser addresses
    # each author separately, so a support agent's build never becomes the asker's identity.
    ld = (
        '{"@type":"QAPage","mainEntity":{"@type":"Question","id":"q1",'
        '"name":"Teams freezes when opening a chat","dateCreated":"2026-09-01T09:00:00Z",'
        '"text":"Teams freezes whenever I open a particular chat. Any ideas?",'
        '"author":"Asker","authorId":"u-asker",'
        '"suggestedAnswer":[{"@type":"Answer","id":"a1",'
        '"text":"Reports point to it starting after Teams build ' + BUILD + '.",'
        '"author":"Support Agent","authorId":"u-agent",'
        '"url":"https://learn.microsoft.com/answers/a/a1"}]}}'
    )
    thread_html = ('<html><body><script type="application/ld+json">' + ld
                   + '</script></body></html>')
    segs = teams.qna_segment_candidates(
        "https://learn.microsoft.com/en-us/answers/questions/5987310/teams-freezes",
        thread_html, parent_title="Teams freezes when opening a chat")
    question = [s for s in segs if s.get("segment_type") == "question"]
    answer = [s for s in segs if s.get("segment_type") == "answer"]
    check("M1 a thread is split into per-author segments, not one blob",
          len(question) == 1 and len(answer) == 1, str([s.get("segment_type") for s in segs]))
    check("M2 the asker's segment does not carry the responder's build",
          bool(question) and BUILD not in str(question[0].get("report_text") or ""),
          str(question[0].get("report_text"))[:90] if question else "no question segment")
    if question:
        row = teams.evaluate_candidate(RECORD, question[0], "2026-09-29T00:00:00Z")
        check("M3 so the asker is not counted against a build they never named",
              row.get("counted") is not True
              and "missing_exact_patch_version_match" in str(row.get("exclusion_reason")),
              str(row.get("exclusion_reason")))
    if answer:
        check("M4 the responder's segment is addressed by its own anchor URL",
              "#answer-" in str(answer[0].get("source_url") or ""),
              str(answer[0].get("source_url")))

    # The DATE a report carries decides which patch it can be evidence about, and Q&A search RSS
    # re-stamps a thread on every reply. Last activity is always LATER than the post, so taking it
    # makes the release-date gate permissive in exactly the direction that hands an old report to a
    # new build. Measured live: one report written 2026-08-24 arrived stamped 2026-09-01.
    check("M7 a question carries its ORIGINAL post date, not the feed's last-activity stamp",
          question and str(question[0].get("source_date") or "").startswith("2026-09-01"),
          str(question[0].get("source_date")) if question else "no question segment")
    undated = teams.qna_segment_candidates(
        "https://learn.microsoft.com/en-us/answers/questions/5987310/teams-freezes",
        thread_html.replace(',"dateCreated":"2026-09-01T09:00:00Z"', ""),
        parent_title="Teams freezes when opening a chat")
    undated_q = [s for s in undated if s.get("segment_type") == "question"]
    check("M8 an unestablishable post date is left EMPTY rather than back-filled from the feed",
          undated_q and not str(undated_q[0].get("source_date") or ""),
          str(undated_q[0].get("source_date")) if undated_q else "no question segment")
    if undated_q:
        dateless = teams.evaluate_candidate(
            RECORD, dict(undated_q[0], report_text="Teams " + BUILD + " crashes on launch.",
                         segment_type="question", source_url=SPECIFIC_URL),
            "2026-09-29T00:00:00Z")
        check("M9 and the release-date gate then refuses it, rather than counting it undated",
              dateless.get("counted") is not True
              and "source_date" in str(dateless.get("exclusion_reason")),
              str(dateless.get("exclusion_reason")))

    # The SAME rule has to hold for the other family. techcommunity_source.thread_candidate puts the
    # sitemap's lastmod in source_date and falls back to it when the page serves no dateCreated --
    # right for its other consumers, wrong for a release-date gate, and a per-family date rule is a
    # gate with a hole in it. Both the sitemap walk and the page fetch are stubbed: this suite makes
    # no network calls, and a check that silently degrades to "nothing was discovered" would pass
    # with the defect restored.
    TC_THREAD = "https://techcommunity.microsoft.com/discussions/microsoftteams/dropped/1"
    tc_ld = ('{"@type":"QAPage","mainEntity":{"@type":"Question",'
             '"name":"Dropped from meetings","dateCreated":"2026-08-14T08:00:00Z",'
             '"text":"Using Teams v. ' + BUILD + ' on Win 11 the call drops every meeting."}}')
    tc_html = ('<html><body><script type="application/ld+json">' + tc_ld
               + '</script></body></html>')

    class _Ctx:
        write = False
        since = "2026-08-01"
        max_pages = 1

    real_enumerate = techcommunity_source.enumerate_sitemaps
    techcommunity_source.enumerate_sitemaps = (
        lambda *_a, **_k: [{"source_url": TC_THREAD, "date": "2026-09-29"}])
    try:
        tc_errors: list = []
        tc_cands = teams.discover_tech_community(_Ctx(), tc_errors,
                                                 fetch_page=lambda _url: tc_html)
        undated = teams.discover_tech_community(
            _Ctx(), [], fetch_page=lambda _url: tc_html.replace(
                ',"dateCreated":"2026-08-14T08:00:00Z"', ""))
    finally:
        techcommunity_source.enumerate_sitemaps = real_enumerate

    check("M10 the stubbed board yields exactly one candidate to judge",
          len(tc_cands) == 1, str(len(tc_cands)) + " candidates, errors=" + str(tc_errors))
    check("M11 a Tech Community thread is dated by its post, not by the sitemap's lastmod",
          tc_cands and str(tc_cands[0].get("source_date")) == "2026-08-14",
          str(tc_cands[0].get("source_date")) if tc_cands else "no candidate")
    check("M12 and an unestablishable post date is left EMPTY, not back-filled from the listing",
          undated and not str(undated[0].get("source_date") or ""),
          str(undated[0].get("source_date")) if undated else "no candidate")

    # P. One real report is one row, however many methods found it.
    dup = [
        {"source_url": SPECIFIC_URL, "discovery_method": teams.QNA_METHOD_ID, "report_text": "x"},
        {"source_url": SPECIFIC_URL + "/", "discovery_method": teams.TC_METHOD_ID, "report_text": "x"},
    ]
    merged, provenance = teams.dedupe_candidates(dup)
    check("P1 one report found by two methods collapses to one row", len(merged) == 1, str(len(merged)))
    check("P2 and both discovery methods are retained for audit",
          any(len(v) == 2 for v in provenance.values()), str(provenance))

    # R/S/T. Health must distinguish "we looked and found nothing" from "we could not look".
    check("R1 a healthy empty discovery is no_results", teams.method_status([], [], 0) == "no_results")
    check("S1 a 403 is blocked, never 'nothing found'",
          teams.method_status([], [{"reason": "HTTP 403 forbidden"}], 0) == "blocked")
    check("S2 a 429 is blocked", teams.method_status([], [{"reason": "429 rate_limit"}], 0) == "blocked")
    check("S3 a challenge page is blocked",
          teams.method_status([], [{"reason": "captcha challenge"}], 0) == "blocked")
    check("T a parser/schema failure is broken",
          teams.method_status([], [{"reason": "feed_parse_failed schema"}], 0) == "broken")
    check("R2 candidates found but none accepted is still no_results",
          teams.method_status([{"a": 1}], [], 0) == "no_results")
    check("R3 candidates plus errors is partial",
          teams.method_status([{"a": 1}], [{"reason": "timeout"}], 0) == "partial")
    check("R4 a run that accepted a report AND failed to read sources is partial, not success",
          teams.method_status([{"a": 1}], [{"reason": "timeout"}], 3) == "partial",
          teams.method_status([{"a": 1}], [{"reason": "timeout"}], 3))
    check("R5 a clean run that accepted a report is success",
          teams.method_status([{"a": 1}], [], 3) == "success")
    emitted = {teams.method_status(c, e, a)
               for c in ([], [{"a": 1}]) for e in ([], [{"reason": "timeout"}],
                                                   [{"reason": "403 Forbidden"}],
                                                   [{"reason": "feed parse failed"}])
               for a in (0, 2)}
    check("R6 every status this collector can emit is in the canonical vocabulary",
          emitted <= set(HEALTH_STATUSES), str(sorted(emitted - set(HEALTH_STATUSES))))

    # BUDGET. Neither thread fetcher this collector uses is budget-aware -- only the Learn Q&A
    # search feed is -- so a busy week's thread volume would be charged to the shared run budget and
    # the collectors that run AFTER Teams would never start. Checked at every loop boundary, and
    # reported honestly: we stopped looking, the source did not go quiet.
    budget_only = [{"reason": teams.BUDGET_STOP_REASON}]
    check("R7 a budget stop with nothing found is partial, never no_results",
          teams.method_status([], budget_only, 0) == "partial",
          teams.method_status([], budget_only, 0))
    check("R8 a budget stop is not reported as a transport refusal either",
          teams.method_status([], budget_only, 0) != "blocked")
    check("R9 but a run that was BOTH truncated and refused still surfaces the refusal",
          teams.method_status([{"a": 1}], budget_only + [{"reason": "403 Forbidden"}], 0)
          == "blocked")

    class _Budget:
        def __init__(self, expired):
            self._expired = expired

        def collector_finalize_expired(self):
            return self._expired

    real_get = rb.get_run_budget
    fetched: list = []
    rb.get_run_budget = lambda: _Budget(True)
    real_enum = techcommunity_source.enumerate_sitemaps
    techcommunity_source.enumerate_sitemaps = (
        lambda *_a, **_k: [{"source_url": "https://techcommunity.microsoft.com/discussions/x/1",
                            "date": "2026-09-01"}])
    try:
        stop_errors: list = []
        stopped = teams.discover_tech_community(
            _Ctx(), stop_errors,
            fetch_page=lambda url: fetched.append(url) or tc_html)
    finally:
        rb.get_run_budget = real_get
        techcommunity_source.enumerate_sitemaps = real_enum
    check("R10 an expired budget stops the walk BEFORE the next page is fetched",
          not fetched and not stopped, str(fetched))
    check("R11 and the stop is recorded, so the method cannot read as a clean empty source",
          any(str(e.get("reason")) == teams.BUDGET_STOP_REASON for e in stop_errors),
          str(stop_errors))

    # U. No source weighting: every confirmed report counts equally.
    weights = {judge("Teams crashes on " + BUILD + " constantly.").get("source_weight"),
               judge("Teams " + BUILD + " on my Mac crashes.").get("source_weight")}
    check("U source_weight is always 1, accepted or rejected", weights == {1}, str(weights))

    # V. Community collection must never rewrite the official identity.
    row = judge("Teams crashes every meeting on " + BUILD + ".")
    official = {"target_platform", "target_channel", "teams_edition", "update_published_at"}
    check("V1 an evidence row carries no official identity field it could overwrite",
          not (official & set(row.keys())), str(sorted(set(row.keys()) & official)))
    check("V2 and it names the tracked patch it belongs to",
          row.get("product_id") == "microsoft-teams" and row.get("update_version") == BUILD)

    # W. Cross-product containment.
    other = base.PatchRecord(product_id="obs-studio", update_version="32.2.2", path=Path("o.md"),
                             update_published_at=RELEASE, update_status="current",
                             update_product="OBS Studio")
    foreign = teams.evaluate_candidate(other, {
        "source_type": teams.QNA_SOURCE_TYPE, "source_name": teams.QNA_SOURCE_NAME,
        "source_url": SPECIFIC_URL, "parent_title": "t", "report_title": "t",
        "report_text": "Teams crashes on " + BUILD + ".", "source_date": "2026-09-01"},
        "2026-09-29T00:00:00Z")
    check("W1 the Teams authority always writes rows for microsoft-teams",
          foreign.get("product_id") == "microsoft-teams", str(foreign.get("product_id")))
    check("W2 and a foreign record's version is never matched by Teams text",
          foreign.get("counted") is not True, str(foreign.get("exclusion_reason")))

    # X/Y. Registration is default-off, explicit true only.
    check("X the collector is NOT registered by default",
          "microsoft-teams" not in runner.build_collectors({}))
    check("Y1 it registers for the exact string 'true'",
          "microsoft-teams" in runner.build_collectors({"AUXSAYS_ENABLE_TEAMS_CONSENSUS": "true"}))
    traps = {v: ("microsoft-teams" in runner.build_collectors(
        {"AUXSAYS_ENABLE_TEAMS_CONSENSUS": v})) for v in ("false", "0", "1", "yes", "on", "")}
    check("Y2 no truthy-looking value activates it", not any(traps.values()), str(traps))

    # Replies are discovered but never counted in V1: reply text came back carrying page
    # furniture on the live calibration, and one such row was accepted as a report.
    reply_row = teams.evaluate_candidate(RECORD, {
        "source_type": teams.QNA_SOURCE_TYPE, "source_name": teams.QNA_SOURCE_NAME,
        "source_url": SPECIFIC_URL + "#answer-99", "parent_title": "t", "report_title": "",
        "report_text": "I can confirm the same crash on " + BUILD + " here too.",
        "source_date": "2026-09-01", "segment_type": "answer"}, "2026-09-29T00:00:00Z")
    check("M5 a reply is stored for audit but never counted in V1",
          reply_row.get("counted") is not True
          and "reply_segment_not_counted_v1" in str(reply_row.get("exclusion_reason")),
          str(reply_row.get("exclusion_reason")))
    check("M6 and a reply never claims a patch-version match",
          reply_row.get("patch_version_matched") is not True)

    check("Z1 discovery declares two independent source families",
          teams.QNA_SOURCE_TYPE != teams.TC_SOURCE_TYPE
          and teams.QNA_METHOD_ID != teams.TC_METHOD_ID)
    check("Z2 the Tech Community family is one board, not several queries at one corpus",
          len(teams.TC_BOARD_SITEMAPS) == 1, str(teams.TC_BOARD_SITEMAPS))

    # AA. THE TWO COUNTERS MUST AGREE. reconcile_record_counts sets update_report_count from the
    # evidence store; apply_consensus_to_records builds the summary and samples from its OWN
    # inclusion pass, and refuses any row whose sentiment is not in VALID_SENTIMENTS. When they
    # disagree the record publishes a count with no summary, QA raises
    # report_count_without_consensus_summary -- a blocking error -- and because QA precedes the
    # writeback it discards every OTHER product's evidence for that cycle too. Measured: with a
    # blank sentiment reconcile counted 1 and the promotion counted 0. Read-only: the real records
    # are indexed, the evidence lives in a temp file, nothing on disk is written.
    live = [r for r in base.generated_records(teams.TEAMS_PRODUCT_ID, None)]
    check("AA0 the Teams product has tracked patch records to promote onto", bool(live),
          "no microsoft-teams generated records")
    if live:
        target = base.newest_first(live)[-1]
        counted_row = teams.evaluate_candidate(
            base.PatchRecord(product_id="microsoft-teams",
                             update_version=str(target.update_version),
                             path=target.path,
                             update_published_at=str(target.update_published_at),
                             update_status="current", update_product="Microsoft Teams"),
            {"source_type": teams.QNA_SOURCE_TYPE, "source_name": teams.QNA_SOURCE_NAME,
             "source_url": SPECIFIC_URL, "parent_title": "Teams audio cuts out",
             "report_title": "Teams audio cuts out",
             "report_text": ("Teams " + str(target.update_version)
                             + " crashes every time I join a meeting on Windows 11."),
             "source_date": "2026-09-20"}, "2026-09-29T00:00:00Z")
        check("AA1 the fixture row is actually counted", counted_row.get("counted") is True,
              str(counted_row.get("exclusion_reason")))

        from apply_consensus_to_records import (VALID_SENTIMENTS, _index_generated_records,
                                                run_dry_run)
        from lib.report_counts import counted_evidence_counts
        check("AA2 a counted row carries a sentiment the promotion authority accepts",
              str(counted_row.get("sentiment") or "").lower() in VALID_SENTIMENTS,
              str(counted_row.get("sentiment")))

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "consensus_evidence.yml"
            evidence.write_text(
                yaml.safe_dump({"schema_version": 1, "evidence": [dict(counted_row)]},
                               sort_keys=False), encoding="utf-8")
            groups = run_dry_run(evidence_path=evidence,
                                 product_id_filter=teams.TEAMS_PRODUCT_ID,
                                 is_candidate_mode=False,
                                 records_index=_index_generated_records(),
                                 write_requested=True)
        reconciled = counted_evidence_counts([dict(counted_row)], windows_targets={})
        group = next((g for g in groups
                      if str(g.get("update_version")) == str(target.update_version)), None)
        fields = (group or {}).get("proposed_fields_if_written") or {}
        check("AA3 the promotion counts exactly what reconciliation counts",
              group is not None
              and fields.get("update_report_count") == sum(reconciled.values()) == 1,
              f"promotion={fields.get('update_report_count')} reconcile={sum(reconciled.values())} "
              f"rejected={(group or {}).get('rejected_candidate_reasons')}")
        check("AA4 so the record gets the summary and samples QA requires at a non-zero count",
              bool(str(fields.get("update_consensus_summary") or "").strip())
              and len(fields.get("evidence_samples") or []) == 1,
              f"summary={bool(fields.get('update_consensus_summary'))} "
              f"samples={len(fields.get('evidence_samples') or [])}")
        official = [f for f in ("target_platform", "target_channel", "teams_edition",
                                "update_version", "update_published_at", "update_source_url",
                                "quick_verdict") if f in fields]
        check("AA5 and promotion proposes no official identity field of the ingestion lane's",
              not official, str(official))

    # BB. NO MANUAL-REVIEW TRAP. Default-off is a development property; production must reach the
    # collector with nobody pressing anything. The flag is read out of the parsed workflow, not
    # grepped: a comment mentioning the variable would satisfy a grep and activate nothing.
    workflow = yaml.safe_load(
        (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml").read_text(encoding="utf-8"))
    steps = (((workflow.get("jobs") or {}).get("collect") or {}).get("steps") or [])
    collect_step = next((s for s in steps
                         if "run_patch_evidence_collection.py" in str(s.get("run") or "")), None)
    check("BB1 the scheduled collection step exists", collect_step is not None,
          str([s.get("name") for s in steps]))
    env = (collect_step or {}).get("env") or {}
    check("BB2 and it activates the Teams collector with the exact string 'true'",
          env.get(runner.TEAMS_CONSENSUS_ENABLE_ENV) == "true",
          str(env.get(runner.TEAMS_CONSENSUS_ENABLE_ENV)))
    check("BB3 the schedule reaches that job with no human input",
          bool((workflow.get(True) or workflow.get("on") or {}).get("schedule")),
          str(list((workflow.get(True) or workflow.get("on") or {}).keys())))
    orchestrated = str(env.get("AUXSAYS_ORCHESTRATED_PRODUCTS") or "")
    check("BB4 and Teams is not excluded from that runner's registry by the orchestration list",
          teams.TEAMS_PRODUCT_ID not in orchestrated, orchestrated)

    # CC. OWNERSHIP VALIDATION RUNS ONLY IN WRITE MODE, so a clean dry run proves nothing about it.
    # An unlisted product resolves to the EMPTY set in both allow-lists, which is a refusal, not a
    # pass: every evidence row and every method-health row this collector produces would raise an
    # ownership violation in production and the whole collector would roll back. Asserted from the
    # collector's own constants, so renaming a method id here without registering it fails.
    from lib.collector_ownership import allowed_methods, allowed_source_types
    check("CC1 both discovery methods are authorised for this product",
          {teams.QNA_METHOD_ID, teams.TC_METHOD_ID}
          <= allowed_methods(teams.TEAMS_PRODUCT_ID),
          str(sorted(allowed_methods(teams.TEAMS_PRODUCT_ID))))
    check("CC2 both evidence source identities are authorised for this product",
          {teams.QNA_SOURCE_TYPE, teams.TC_SOURCE_TYPE}
          <= allowed_source_types(teams.TEAMS_PRODUCT_ID),
          str(sorted(allowed_source_types(teams.TEAMS_PRODUCT_ID))))
    check("CC3 the two source identities are genuinely two families, not one read two ways",
          len({teams.QNA_SOURCE_TYPE, teams.TC_SOURCE_TYPE}) == 2)
    # And drive the real validators, because membership in a set is not the same as passing the
    # gate: validate_method_health also requires every row's patch identity to RESOLVE to a
    # generated record, and Teams records carry no target_build, so an empty build slot has to be
    # the resolving shape rather than a missing one.
    if live:
        health_row = base.method_health_row(
            product_id=teams.TEAMS_PRODUCT_ID,
            update_version=str(target.update_version),
            method_id=teams.TC_METHOD_ID, source_type=teams.TC_SOURCE_TYPE,
            status="no_results", candidates_found=1, accepted_reports=0, rejected_reports=1,
            blocked_reason="", last_run="2026-09-29T00:00:00Z", notes="n")
        try:
            ownership.validate_method_health(teams.TEAMS_PRODUCT_ID, [health_row])
            mh_error = None
        except Exception as exc:                                   # noqa: BLE001
            mh_error = exc
        check("CC4 a real method-health row passes ownership validation", mh_error is None,
              repr(mh_error))

        before = yaml.safe_dump({"schema_version": 1, "evidence": []}, sort_keys=False)
        after = yaml.safe_dump(
            {"schema_version": 1, "evidence": [dict(counted_row)]}, sort_keys=False)
        try:
            ownership.validate_evidence(teams.TEAMS_PRODUCT_ID, before, after)
            ev_error = None
        except Exception as exc:                                   # noqa: BLE001
            ev_error = exc
        check("CC5 a real appended evidence row passes ownership validation", ev_error is None,
              repr(ev_error))

    # DD. THE WRITEBACK IS A POSITIVE ALLOW-LIST. A record path that matches no --allow entry is not
    # committed, so a promotion that runs correctly still publishes nothing. Parsed out of the
    # step's real shell with the comment lines removed, not grepped: a commented-out entry satisfies
    # a substring search and allows nothing.
    writeback = next((s for s in steps
                      if "automation_writeback.py" in str(s.get("run") or "")), None)
    check("DD1 the transactional writeback step exists", writeback is not None)
    allow_globs: list[str] = []
    for raw_line in str((writeback or {}).get("run") or "").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("#") or "--allow" not in stripped:
            continue
        token = stripped.split("--allow", 1)[1].strip().rstrip("\\").strip()
        allow_globs.append(token.strip("'\""))
    teams_records = [r.path.name for r in live]
    unmatched = [n for n in teams_records
                 if not any(fnmatch.fnmatch("auxsays/updates/generated/" + n, g)
                            for g in allow_globs)]
    check("DD2 every live Teams record is committable by the writeback", not unmatched,
          "unmatched=" + str(unmatched) + " globs=" + str(allow_globs))
    check("DD3 the evidence store and method-health file are committable too",
          {"auxsays/_data/consensus_evidence.yml",
           "auxsays/_data/evidence_method_health.yml"} <= set(allow_globs),
          str(allow_globs))

    print()
    print("=" * 78)
    total = _PASS + _FAIL
    print("Results: " + str(_PASS) + "/" + str(total) + " passed, " + str(_FAIL) + " failed")
    if _ERRORS:
        print("Failed: " + ", ".join(_ERRORS))
    print("=" * 78)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
