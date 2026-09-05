#!/usr/bin/env python3
"""Windows 11 evidence recovery: historical replay, a second source family, and two precision fixes.

Windows had ONE discovery method against a monitoring floor of two, and 52 of its 71 patch pages
carried no accepted report. This suite pins what closed that, and -- as important -- what was
measured and deliberately NOT done.

    A  foreign-product subject veto     a separately-updated product's own failure is not this
                                        cumulative update's defect
    B  gate ORDER                       the veto runs before attribution, because generic install
                                        vocabulary in the body is exactly what it must not trust
    C  stop-error classification        a bare hex token is not a bugcheck
    D  cross-post identity              one report is one row across Tech Community spaces
    E  method health vocabulary         canonical statuses only; a zero-value method is never
                                        `success`; an isolated dead thread is not degradation
    F  source FAMILY independence       coverage counts source_type, so the second method must be
                                        a different community, not a second route into the same one
    G  run-scoped discovery             the sitemap pool is enumerated once per run, not per record
    H  stored-evidence repair           idempotent, keeps target_build on retracted rows, and only
                                        reclassifies where the PUBLISHED text lacks stop-error words
    I  live corpus                      the two fixes hold over the evidence actually committed
    J  historical replay is bounded     `--since` is dispatch-only; routine monitoring stays 45 days
    K  date authority                   Tech Community rows date from the ORIGINAL post

Offline and deterministic: no network, no fixtures outside a temporary directory, and the only
repository state read is the committed evidence file and workflow (section I/J), read-only.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_windows_evidence_recovery.py
"""
from __future__ import annotations

import re
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors import techcommunity_source as tc  # noqa: E402
import repair_windows_evidence_attribution as repair  # noqa: E402

NEWLINE = chr(10)
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


def stored_text(row: dict) -> str:
    return repair.row_text(row)


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Windows evidence recovery: replay, second source family, precision fixes")
    print("=" * 78)

    # ---------------- A: foreign-product subject ----------------
    print(NEWLINE + "[A] a separately-updated product's failure is not this patch's defect")
    fires = [
        "How do I fix an SQL Server issue - Microsoft Q&A",
        "Java 8 update 491 installation error code1603 on Windows 11 Pro",
        "Can't install Resident Evil 7 from Microsoft store.",
        "Microsoft Outlook 2024 no longer synchronizes imap email from gmail",
        "DirectX End-User Runtime June 2010 installation keeps failing",
        "I got an error during HLK client installation",
        "[Edge short freeze] Win11 pro x64, stable channel",
        "How to set up VS code and use python on new surface laptop?",
    ]
    for title in fires:
        check(f"A veto fires: {title[:52]}",
              mw.foreign_product_subject(title, "", ""), "not vetoed")

    check("A escape 1: the record's own KB in the title is never vetoed",
          not mw.foreign_product_subject("KB5089549 breaks Outlook after install", "KB5089549", ""),
          "vetoed a title naming this patch")
    check("A escape 1: the record's own build in the title is never vetoed",
          not mw.foreign_product_subject("OS Build 26200.8894 Office Errors - Major Headache",
                                         "", "26200.8894"),
          "vetoed a title naming this build")
    check("A escape 2: no foreign product means nothing to veto",
          not mw.foreign_product_subject("Windows 11 keeps failing to install updates", "", ""))
    check("A escape 3: a Windows update named in the title is the subject",
          not mw.foreign_product_subject("2026-05 Preview Update appears to break Excel", "", ""),
          "vetoed a report about the update itself")
    check("A escape 4: a Windows component alongside the app keeps the row",
          not mw.foreign_product_subject(
              "Virtual keyboard/Clipboard history, Start menu Search bar, and Outlook (MS Store)",
              "", ""),
          "vetoed a Windows report listing an app among symptoms")
    check("A a foreign product in the BODY alone never vetoes",
          not mw.foreign_product_subject("Windows 11 update fails to install", "", ""),
          "body-scoped behaviour leaked into the title rule")
    check("A Azure Virtual Desktop is NOT in the lexicon (it is a hosting context)",
          not mw.foreign_product_subject(
              "AVD clipboard redirection broken after 5/12/2026 updates", "", ""),
          "AVD hosting context wrongly treated as a competing product")

    # ---------------- B: gate order ----------------
    print(NEWLINE + "[B] the veto runs BEFORE attribution, not after")
    body = ("Java 8 update 491 installation error code1603 on Windows 11 Pro. "
            "The installation failed repeatedly. My system specs: OS Build: 26200.8246.")
    check("B a foreign-subject post is refused with its own reason",
          mw.windows_intent_reason(body, "Java 8 update 491 installation error code1603",
                                   "", "26200.8246") == "foreign_product_subject_not_windows_patch",
          mw.windows_intent_reason(body, "Java 8 update 491 installation error code1603",
                                   "", "26200.8246") or "accepted")
    check("B the same body with a Windows subject still attributes",
          mw.windows_intent_reason(
              "2026-04 Security Update (KB5083769) (26200.8246) will not install",
              "Windows 11 update 2026-04 security update (kb5083769) (26200.8246)",
              "KB5083769", "26200.8246") is None,
          "a genuine Windows install-failure report was refused")
    src = (_REPO / "auxsays" / "scripts" / "patch_collectors" / "microsoft_windows.py").read_text(encoding="utf-8")
    veto_at = src.find("foreign_product_subject_not_windows_patch")
    attributed_at = src.find("attributed = update_attributed(")
    check("B the veto is positioned before the attribution check in the ordered rule set",
          0 < veto_at < attributed_at, f"veto@{veto_at} attribution@{attributed_at}")

    # ---------------- C: stop-error classification ----------------
    print(NEWLINE + "[C] a hex error code is not a bugcheck")
    for text in ("Update fails with error 0x800f0991 every time",
                 "install error 0x80070306 when installing the update",
                 "download error code 0x80040155"):
        theme, _area, _plat, severity, _sent = mw.classify(text)
        check(f"C install error stays an install failure: {text[:44]}",
              theme == "update/install failure" and severity == "high", f"{theme}/{severity}")
    for text in ("Random BSOD after the update", "blue screen on every boot",
                 "bugcheck DRIVER_IRQL_NOT_LESS_OR_EQUAL 0xD1",
                 "stop code CRITICAL_PROCESS_DIED"):
        theme, _area, _plat, severity, _sent = mw.classify(text)
        check(f"C a real stop error still classifies: {text[:44]}",
              theme == "BSOD / stop error" and severity == "critical", f"{theme}/{severity}")
    check("C the bare-hex cue is gone from the classifier",
          "0x[0-9a-f]{6,8}" not in src.split("def classify(")[1].split("def ")[0],
          "the hex regex is still inside classify()")

    # ---------------- D: cross-post identity ----------------
    print(NEWLINE + "[D] one report is one row, across spaces and across duplicate posts")
    a = "https://techcommunity.microsoft.com/discussions/windows11/how-to-stop-the-loop/4539047"
    b = "https://techcommunity.microsoft.com/discussions/windowsinsiderprogram/how-to-stop-the-loop/4538922"
    c = "https://techcommunity.microsoft.com/discussions/windows11/how-to-fix-kb5086672-breaks-network/4526757"
    d = "https://techcommunity.microsoft.com/discussions/windows11/how-to-fix-kb5086672-breaks-network/4526760"
    e = "https://techcommunity.microsoft.com/discussions/windows11/kb5077181-update-causes-hdmi-port-to-fail/4494548"
    check("D the same thread cross-posted to two spaces collapses",
          mw.techcommunity_slug(a) == mw.techcommunity_slug(b), f"{a} vs {b}")
    check("D the same thread posted twice into one space collapses",
          mw.techcommunity_slug(c) == mw.techcommunity_slug(d))
    check("D two different threads stay distinct",
          mw.techcommunity_slug(a) != mw.techcommunity_slug(e))
    check("D a percent-encoded slug decodes to the same identity",
          mw.techcommunity_slug(
              "https://techcommunity.microsoft.com/discussions/windows11/hang-%e2%86%92-whea/1") ==
          mw.techcommunity_slug(
              "https://techcommunity.microsoft.com/discussions/windowsinsiderprogram/hang-→-whea/2"))
    check("D a malformed url yields no identity rather than a false match",
          mw.techcommunity_slug("https://techcommunity.microsoft.com") == "")

    # ---------------- E: method health vocabulary ----------------
    print(NEWLINE + "[E] canonical source-health statuses, and no free `success`")
    CANONICAL = {"success", "partial", "no_results", "blocked", "stale", "broken",
                 "low_confidence", "disabled", "manual_review_needed"}

    def pool(candidates=1, errors=0, sitemap_errors=0, hydration_errors=0,
             attempted=10, truncated=False):
        return mw.TechCommunityPool(
            candidates=[{"source_url": f"u{i}"} for i in range(candidates)],
            telemetry={"listed": attempted, "unique_slugs": attempted, "hydrated": candidates,
                       "attempted": attempted, "sitemap_errors": sitemap_errors,
                       "hydration_errors": hydration_errors, "truncated": truncated},
            errors=[{"reason": "x"}] * errors)

    row = [{"counted": True}]
    check("E accepted + clean walk is success",
          mw.techcommunity_method_status(pool(), row, []) == "success")
    check("E a record with nothing accepted is no_results, not success",
          mw.techcommunity_method_status(pool(), [], [{"counted": False}]) == "no_results",
          mw.techcommunity_method_status(pool(), [], [{"counted": False}]))
    check("E an empty pool is no_results",
          mw.techcommunity_method_status(pool(candidates=0), [], []) == "no_results")
    check("E a failed sitemap walk with nothing hydrated is blocked",
          mw.techcommunity_method_status(pool(candidates=0, errors=1, sitemap_errors=1), [], []) == "blocked")
    check("E a failed sitemap walk that still hydrated is partial",
          mw.techcommunity_method_status(pool(errors=1, sitemap_errors=1), row, []) == "partial")
    check("E a truncated walk is partial even with accepts",
          mw.techcommunity_method_status(pool(truncated=True), row, []) == "partial")
    check("E ONE dead thread out of ten is not degradation",
          mw.techcommunity_method_status(pool(errors=1, hydration_errors=1), row, []) == "success",
          "an isolated hydration failure marked every patch degraded")
    check("E a fifth of the walk failing IS degradation",
          mw.techcommunity_method_status(pool(errors=2, hydration_errors=2), row, []) == "partial")
    for status in (mw.techcommunity_method_status(pool(), row, []),
                   mw.techcommunity_method_status(pool(), [], []),
                   mw.techcommunity_method_status(pool(candidates=0, errors=1, sitemap_errors=1), [], []),
                   mw.techcommunity_method_status(pool(truncated=True), row, [])):
        check(f"E status '{status}' is canonical", status in CANONICAL)

    # ---------------- F: source FAMILY independence ----------------
    print(NEWLINE + "[F] coverage counts communities, so the second method is a second community")
    check("F the second method declares a different source_type family",
          mw.TECHCOMMUNITY_SOURCE_TYPE != mw.SOURCE_TYPE,
          f"{mw.TECHCOMMUNITY_SOURCE_TYPE} == {mw.SOURCE_TYPE}")
    check("F the second method declares a different method_id",
          mw.TECHCOMMUNITY_METHOD_ID != mw.METHOD_ID)
    include = (_REPO / "auxsays" / "_includes" / "monitoring-status.html").read_text(encoding="utf-8")
    check("F the public coverage counter still keys on source_type, not method_id",
          "m.source_type | default: m.method_id" in include,
          "coverage no longer counts families; a second route into one community would satisfy it")
    check("F only success/no_results count toward coverage",
          "m_status == 'success' or m_status == 'no_results'" in include)

    # ---------------- G: run-scoped discovery ----------------
    print(NEWLINE + "[G] the sitemap pool is enumerated once per run, never per record")
    calls: list[str] = []
    original = tc.enumerate_sitemaps
    try:
        tc.enumerate_sitemaps = lambda *a, **k: calls.append("walk") or []  # type: ignore[assignment]
        empty = mw.TechCommunityPool(candidates=[], telemetry={}, errors=[])
        check("G collect_for_record takes a prebuilt pool and does not walk sitemaps",
              "techcommunity_pool" in mw.collect_for_record.__code__.co_varnames and not calls,
              f"{calls}")
        check("G an empty pool object is usable without a walk", empty.candidates == [])
    finally:
        tc.enumerate_sitemaps = original  # type: ignore[assignment]
    collect_src = src.split("class WindowsLearnQnaCollector")[1]
    check("G the pool is built before the record loop",
          collect_src.find("build_techcommunity_pool") < collect_src.find("for record in records"),
          "the pool is built inside the record loop")

    # ---------------- H: stored-evidence repair ----------------
    print(NEWLINE + "[H] the repair is idempotent, build-preserving and text-supported")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        rows = [
            {"product_id": mw.PRODUCT_ID, "update_version": "25H2", "target_build": "26200.8973",
             "source_url": "https://x/1", "report_title": "SQL Server 2022 Recovery Handle Failed",
             "parent_title": "", "report_text_excerpt": "setup failed", "counted": True,
             "issue_theme": "update/install failure", "severity": "high", "sentiment": "negative",
             "matched_kb": "", "matched_os_build": "26200.8973", "id": "a"},
            {"product_id": mw.PRODUCT_ID, "update_version": "25H2", "target_build": "26200.9168",
             "source_url": "https://x/2", "report_title": "WINDOWS UPDATE not functioning",
             "parent_title": "", "report_text_excerpt": "error 0x800f0991 every attempt",
             "counted": True, "issue_theme": "BSOD / stop error", "severity": "critical",
             "sentiment": "negative", "matched_kb": "KB5121003", "matched_os_build": "", "id": "b"},
            {"product_id": mw.PRODUCT_ID, "update_version": "25H2", "target_build": "26200.9168",
             "source_url": "https://x/3", "report_title": "Random BSOD after KB5121003",
             "parent_title": "", "report_text_excerpt": "blue screen every boot", "counted": True,
             "issue_theme": "BSOD / stop error", "severity": "critical", "sentiment": "negative",
             "matched_kb": "KB5121003", "matched_os_build": "", "id": "c"},
            {"product_id": "obs-studio", "update_version": "32.1.2", "target_build": "",
             "source_url": "https://x/4", "report_title": "Outlook crashes", "parent_title": "",
             "report_text_excerpt": "n/a", "counted": True, "issue_theme": "BSOD / stop error",
             "severity": "critical", "sentiment": "negative", "id": "d"},
        ]
        path.write_text(yaml.safe_dump({"schema_version": 1, "evidence": rows}, sort_keys=False),
                        encoding="utf-8")
        first = repair.run(True, path)
        check("H the foreign-subject row is retracted", first["retracted_foreign_subject"] == 1,
              str(first["retracted_foreign_subject"]))
        check("H the unsupported stop-error claim is reclassified",
              first["reclassified_stop_error"] == 1, str(first["reclassified_stop_error"]))
        after = yaml.safe_load(path.read_text(encoding="utf-8"))["evidence"]
        by_id = {r["id"]: r for r in after}
        check("H the retracted row is uncounted with its own reason",
              by_id["a"]["counted"] is False
              and by_id["a"]["exclusion_reason"] == repair.FOREIGN_REASON)
        check("H the retracted row KEEPS its target_build",
              by_id["a"]["target_build"] == "26200.8973",
              "blanking the build creates a (product, version, '') group no record has")
        check("H the reclassified row drops the unsupported critical severity",
              by_id["b"]["issue_theme"] == "update/install failure"
              and by_id["b"]["severity"] == "high",
              f'{by_id["b"]["issue_theme"]}/{by_id["b"]["severity"]}')
        check("H a stop-error claim the published text SUPPORTS is untouched",
              by_id["c"]["issue_theme"] == "BSOD / stop error"
              and by_id["c"]["severity"] == "critical")
        check("H another product's rows are never touched",
              by_id["d"]["counted"] is True and by_id["d"]["issue_theme"] == "BSOD / stop error")
        second = repair.run(True, path)
        check("H a second run is a no-op",
              second["retracted_foreign_subject"] == 0 and second["reclassified_stop_error"] == 0,
              f'{second["retracted_foreign_subject"]}/{second["reclassified_stop_error"]}')

    # ---------------- I: the live corpus ----------------
    print(NEWLINE + "[I] both fixes hold over the evidence actually committed")
    evidence_path = _REPO / "auxsays" / "_data" / "consensus_evidence.yml"
    evidence = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))["evidence"]
    win = [r for r in evidence if str(r.get("product_id") or "") == mw.PRODUCT_ID]
    counted = [r for r in win if r.get("counted") is True]
    check("I the Windows corpus is non-empty (this section is not vacuous)", len(counted) > 0,
          f"{len(counted)} counted rows")
    offenders = [r for r in counted
                 if mw.foreign_product_subject(str(r.get("report_title") or ""),
                                               str(r.get("matched_kb") or ""),
                                               str(r.get("matched_os_build") or ""))]
    check("I no counted Windows row has a foreign product as its subject",
          not offenders, "; ".join(str(r.get("report_title"))[:60] for r in offenders[:3]))
    unsupported = [r for r in win
                   if str(r.get("issue_theme") or "") == repair.STOP_ERROR_THEME
                   and not any(t in stored_text(r).lower() for t in mw.BSOD_VOCABULARY)]
    check("I no Windows row claims a stop error its own published text does not show",
          not unsupported, "; ".join(str(r.get("report_title"))[:60] for r in unsupported[:3]))
    retracted = [r for r in win if r.get("exclusion_reason") == repair.FOREIGN_REASON]
    check("I the retracted rows are still present as an audit trail", len(retracted) >= 1,
          f"{len(retracted)} retracted rows")
    check("I every retracted row still carries the build that refused it",
          all(str(r.get("target_build") or "").strip() for r in retracted))

    # ---------------- J: historical replay is bounded ----------------
    print(NEWLINE + "[J] replay is dispatch-only; routine monitoring stays recent")
    wf_path = _REPO / ".github" / "workflows" / "obs-evidence-collection.yml"
    wf_text = wf_path.read_text(encoding="utf-8")
    wf = yaml.safe_load(wf_text)
    dispatch = wf[True]["workflow_dispatch"]["inputs"]
    check("J the workflow exposes a `since` input", "since" in dispatch)
    check("J the routine horizon is still 45 days", "args=(--since-days 45 --max-pages 5)" in wf_text)
    check("J the replay bound is format-validated",
          "^[0-9]{4}-[0-9]{2}-[0-9]{2}$" in wf_text, "an unvalidated date reaches the runner")
    check("J the replay bound has a floor", "2025-01-01" in wf_text)
    check("J the schedule passes no inputs, so cron can never reach the replay branch",
          "schedule" in wf[True] and "inputs" not in str(wf[True]["schedule"]))
    runner = (_REPO / "auxsays" / "scripts" / "run_patch_evidence_collection.py").read_text(encoding="utf-8")
    check("J --since already existed in the runner (no new replay framework)",
          '"--since"' in runner and "args.since or since_from_days" in runner)

    # ---------------- K: date authority ----------------
    print(NEWLINE + "[K] a Tech Community row dates from the ORIGINAL post, not last activity")
    page = ('<script type="application/ld+json">'
            '{"@type":"QAPage","mainEntity":{"name":"KB5121003 breaks USB",'
            '"text":"After installing KB5121003 my USB controller fails.",'
            '"dateCreated":"2026-08-12T10:00:00Z"}}</script>')
    candidate = tc.thread_candidate(
        "https://techcommunity.microsoft.com/discussions/windows11/kb5121003-breaks-usb/1",
        date="2026-09-01", page_html=page, source_type=mw.TECHCOMMUNITY_SOURCE_TYPE,
        source_name=mw.TECHCOMMUNITY_SOURCE_NAME)
    check("K the opening post is read, replies are not", candidate is not None
          and "USB controller fails" in candidate["report_text"])
    check("K the original post date is carried alongside the listing date",
          candidate["original_post_date"] == "2026-08-12", str(candidate))
    check("K the collector stamps source_date from the original post date",
          "candidate['original_post_date']" in src or
          'candidate.get("original_post_date")' in src,
          "the sitemap lastmod would reach the date gate")
    check("K discovery admits only identity-bearing slugs",
          bool(mw.WINDOWS_IDENTITY_SLUG_RE.search("/discussions/windows11/kb5121003-breaks-usb/1"))
          and bool(mw.WINDOWS_IDENTITY_SLUG_RE.search("/x/update-kb5079473-26200-8037-issues/2"))
          and not mw.WINDOWS_IDENTITY_SLUG_RE.search("/discussions/windows11/how-do-i-rename-files/3"))
    check("K the hydration ceiling is finite",
          isinstance(mw.TECHCOMMUNITY_MAX_HYDRATIONS, int) and 0 < mw.TECHCOMMUNITY_MAX_HYDRATIONS <= 2000)
    check("K only Windows client spaces are enumerated",
          all(re.search(r"windows", name, re.I) for name in mw.TECHCOMMUNITY_SPACES)
          and not any("server" in name for name in mw.TECHCOMMUNITY_SPACES),
          str(mw.TECHCOMMUNITY_SPACES))

    # ---------------- L: the build named as a remedy is not a defect report ----------------
    print(NEWLINE + "[L] a build named as a future fix is the fixed-in role, not failing evidence")
    snipping = ("I assume that the problem is related to the OS update only. Ther is a new OS "
                "version for my computer: 22631.6936 that may fix this problem, some words around "
                "graphical updates. The current OS version is W11, ver.23H2, 22631.6783.")
    check("L the measured live false positive is vetoed",
          mw.identity_named_as_prospective_fix(snipping, "22631.6936"))
    check("L a report about installing the target is untouched",
          not mw.identity_named_as_prospective_fix(
              "After installing KB5121003 (26200.9168) my USB controller fails. "
              "Rolling back to 26200.8973 fixes it.", "26200.9168"),
          "an affected report was vetoed")
    check("L the rule needs the reporter to be on another build",
          not mw.identity_named_as_prospective_fix("26200.9168 may fix this problem", "26200.9168"),
          "fired without the reporter placing themselves elsewhere")
    check("L a KB named as a remedy is never vetoed (that is a distribution complaint)",
          not mw.identity_named_as_prospective_fix(
              "KB5073455 should fix this but is not offered on 23H2. I am on 22631.6783 and "
              "22631.6936 exists.", ""),
          "a KB-only report was vetoed")
    check("L the gate returns the reason",
          mw.windows_intent_reason(snipping, "Snipping tool freezing my laptop", "", "22631.6936")
          == "identity_named_as_prospective_fix",
          str(mw.windows_intent_reason(snipping, "Snipping tool freezing my laptop", "", "22631.6936")))
    check("L a dot inside a build token is not a sentence boundary",
          "26200.7462" in mw.sentences("the build 26200.7462 broke it. next sentence")[0],
          str(mw.sentences("the build 26200.7462 broke it. next sentence")))
    check("L real punctuation still splits",
          len(mw.sentences("one. two. three")) == 3,
          str(mw.sentences("one. two. three")))
    check("L no counted Windows row names its own build only as a remedy",
          not [r for r in counted
               if mw.identity_named_as_prospective_fix(stored_text(r),
                                                       str(r.get("matched_os_build") or ""))],
          "a live row still names its build as a prospective fix")

    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
