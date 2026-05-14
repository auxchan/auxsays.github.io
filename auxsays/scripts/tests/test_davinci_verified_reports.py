#!/usr/bin/env python3
"""Gate checks for Taylor-verified DaVinci calibration examples.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_verified_reports.py

The fixture is not public consensus evidence. It proves that fetched forum
posts with equivalent title/text/date/version fields pass reusable gates.
"""
from __future__ import annotations

import sys
import traceback
import types
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

# Local development environments may not have PyYAML installed. The DaVinci
# gate functions exercised here do not need YAML I/O, so provide an import shim.
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda *_args, **_kwargs: {}, safe_dump=lambda *_args, **_kwargs: ""))

from patch_collectors.base import CollectorContext, PatchRecord
import patch_collectors.davinci as davinci
from patch_collectors.davinci import (
    blackmagic_access_challenge_reason,
    blackmagic_forum_unusable_reason,
    method_status,
    row_from_candidate,
    version_aliases,
)
from apply_consensus_to_records import _proposed_record_fields

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "davinci_verified_reports.yml"

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


def load_fixture_reports() -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.startswith("  - "):
            if current:
                reports.append(current)
            current = {}
            key, value = line[4:].split(":", 1)
            current[key.strip()] = clean_value(value)
        elif current is not None and line.startswith("    ") and ":" in line:
            key, value = line.strip().split(":", 1)
            current[key.strip()] = clean_value(value)
    if current:
        reports.append(current)
    return reports


def clean_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def candidate_from_fixture(report: dict[str, str]) -> dict[str, str]:
    return {
        "source_type": report["source_type"],
        "source_name": report["source_name"],
        "source_url": report["source_url"],
        "parent_title": report["thread_title"],
        "report_title": report["report_title"],
        "report_text": report["report_text_excerpt"],
        "source_date": report["source_date"],
    }


def record_from_fixture(report: dict[str, str]) -> PatchRecord:
    return PatchRecord(
        product_id=report["product_id"],
        update_version=report["update_version"],
        path=Path("auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md"),
        update_published_at=report["target_release_date"],
        update_status="current",
        update_product="DaVinci Resolve",
    )


def run() -> int:
    print("=" * 60)
    print("DaVinci verified report gate fixture tests")
    print("=" * 60)

    reports = load_fixture_reports()
    check("five Taylor-verified calibration reports loaded", len(reports) == 5, f"got: {len(reports)}")
    check(
        "Blackmagic AWS WAF challenge is classified as blocked access",
        blackmagic_access_challenge_reason("<html><script>window.gokuProps = {}</script></html>") == "http_202_aws_waf_challenge",
    )
    check(
        "non-forum Blackmagic response is classified as non-forum content",
        blackmagic_forum_unusable_reason("<html><title>Blackmagic Design</title><main>Products</main></html>") == "source_returned_non_forum_content",
    )
    check(
        "usable Blackmagic forum no-results page is not classified unusable",
        blackmagic_forum_unusable_reason("<html><title>Search</title><body>forum.blackmagicdesign.com No suitable matches were found</body></html>") == "",
    )
    check(
        "vendor forum unusable errors produce low-confidence method health",
        method_status([], [], [], [{"reason": "vendor_forum_search_unusable:source_returned_non_forum_content"}]) == "low_confidence",
    )
    check(
        "vendor forum challenge errors produce blocked method health",
        method_status([], [], [], [{"reason": "vendor_forum_search_blocked_or_failed:http_202_aws_waf_challenge"}]) == "blocked",
    )
    original_request_text = davinci.request_text
    try:
        davinci.request_text = lambda _url: "<html><title>Blackmagic Design</title><main>Products</main></html>"
        forum_errors: list[dict[str, str]] = []
        forum_candidates = davinci.vendor_forum_search_candidates(
            record_from_fixture(reports[0]),
            CollectorContext(write=False, since=None, max_pages=1),
            forum_errors,
        )
    finally:
        davinci.request_text = original_request_text
    check(
        "vendor forum non-forum response yields no candidates",
        forum_candidates == [],
        f"candidates={forum_candidates!r}",
    )
    check(
        "vendor forum non-forum response records unusable source health",
        len(forum_errors) == 1
        and forum_errors[0].get("reason") == "vendor_forum_search_unusable:source_returned_non_forum_content",
        f"errors={forum_errors!r}",
    )

    for report in reports:
        row = row_from_candidate(record_from_fixture(report), candidate_from_fixture(report), "2026-05-13T00:00:00Z")
        label = report["id"]
        check(f"{label} counted", row.get("counted") is True, f"reason={row.get('exclusion_reason')!r}")
        check(f"{label} exact version matched", row.get("patch_version_matched") is True, f"matched={row.get('matched_version')!r}")
        check(f"{label} date gate passed", row.get("source_date_pass") is True, f"source_date={row.get('source_date')!r}")
        check(f"{label} equal source weight", row.get("source_weight") == 1, f"weight={row.get('source_weight')!r}")
        check(f"{label} specific Blackmagic forum URL", "viewtopic.php" in row.get("source_url", ""), row.get("source_url", ""))

    control = reports[0]
    record = record_from_fixture(control)
    candidate = candidate_from_fixture(control)

    no_product = dict(candidate)
    no_product.update({
        "parent_title": "21 Public Beta 1 crash report",
        "report_title": "21 Public Beta 1 crash",
        "report_text": "21 Public Beta 1 crashed during export.",
    })
    no_product_row = row_from_candidate(record, no_product, "2026-05-13T00:00:00Z")
    check(
        "negative control rejects missing DaVinci product context",
        no_product_row.get("counted") is False and no_product_row.get("exclusion_reason") == "missing_davinci_product_context",
        f"reason={no_product_row.get('exclusion_reason')!r}",
    )

    early_date = dict(candidate)
    early_date["source_date"] = "2026-04-13"
    early_date_row = row_from_candidate(record, early_date, "2026-05-13T00:00:00Z")
    check(
        "negative control rejects pre-release report date",
        early_date_row.get("counted") is False and early_date_row.get("exclusion_reason") == "source_date_before_or_unverified_against_release",
        f"reason={early_date_row.get('exclusion_reason')!r}",
    )

    generic_url = dict(candidate)
    generic_url["source_url"] = "https://forum.blackmagicdesign.com/search.php?keywords=DaVinci+Resolve+21"
    generic_url_row = row_from_candidate(record, generic_url, "2026-05-13T00:00:00Z")
    check(
        "negative control rejects generic forum search URL",
        generic_url_row.get("counted") is False and generic_url_row.get("exclusion_reason") == "source_url_not_specific_report",
        f"reason={generic_url_row.get('exclusion_reason')!r}",
    )

    stable_record = PatchRecord(
        product_id="blackmagic-davinci",
        update_version="21",
        path=Path("auxsays/updates/generated/2026-04-14-davinci-resolve-21.md"),
        update_published_at="2026-04-14",
        update_status="current",
        update_product="DaVinci Resolve",
    )
    beta_for_stable = {
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235117",
        "parent_title": "DaVinci Resolve 21 Public Beta 1 crash report",
        "report_title": "Resolve Studio 21.0B Build 20 crash",
        "report_text": "DaVinci Resolve Studio 21.0B Build 20 crashed during export.",
        "source_date": "2026-04-14",
    }
    beta_for_stable_row = row_from_candidate(stable_record, beta_for_stable, "2026-05-13T00:00:00Z")
    check(
        "stable 21 rejects Beta 1 context",
        beta_for_stable_row.get("counted") is False and beta_for_stable_row.get("exclusion_reason") == "beta_context_for_stable_record",
        f"reason={beta_for_stable_row.get('exclusion_reason')!r}",
    )

    beta_record = record_from_fixture(control)
    stable_for_beta = {
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=240001",
        "parent_title": "DaVinci Resolve 21 render crash report",
        "report_title": "Resolve Studio 21 render crash",
        "report_text": "DaVinci Resolve 21 crashed while rendering a timeline.",
        "source_date": "2026-04-14",
    }
    stable_for_beta_row = row_from_candidate(beta_record, stable_for_beta, "2026-05-13T00:00:00Z")
    check(
        "Beta 1 rejects stable 21 wording",
        stable_for_beta_row.get("counted") is False and stable_for_beta_row.get("exclusion_reason") == "missing_exact_patch_version_match",
        f"reason={stable_for_beta_row.get('exclusion_reason')!r}",
    )

    rss_public_beta_21 = {
        "source_type": "reddit_community_report",
        "source_name": "r/davinciresolve",
        "source_url": "https://www.reddit.com/r/davinciresolve/comments/rss001/example/",
        "parent_title": "DaVinci Resolve public beta 21 crashes during render",
        "report_title": "DaVinci Resolve public beta 21 crashes during render",
        "report_text": "DaVinci Resolve public beta 21 crashed while rendering a timeline.",
        "source_date": "2026-04-15",
    }
    rss_public_beta_21_row = row_from_candidate(beta_record, rss_public_beta_21, "2026-05-13T00:00:00Z")
    check(
        "RSS-style public beta 21 with DaVinci context matches Beta 1",
        rss_public_beta_21_row.get("counted") is True
        and rss_public_beta_21_row.get("patch_version_matched") is True
        and rss_public_beta_21_row.get("matched_version") in {"DaVinci Resolve public beta 21", "public beta 21"},
        f"reason={rss_public_beta_21_row.get('exclusion_reason')!r}, matched={rss_public_beta_21_row.get('matched_version')!r}",
    )

    rss_resolve_21_beta = dict(rss_public_beta_21)
    rss_resolve_21_beta.update({
        "source_url": "https://www.reddit.com/r/davinciresolve/comments/rss002/example/",
        "parent_title": "Resolve 21 beta export crash",
        "report_title": "Resolve 21 beta export crash",
        "report_text": "Resolve 21 beta crashed when exporting a project.",
    })
    rss_resolve_21_beta_row = row_from_candidate(beta_record, rss_resolve_21_beta, "2026-05-13T00:00:00Z")
    check(
        "RSS-style Resolve 21 beta with issue context matches Beta 1",
        rss_resolve_21_beta_row.get("counted") is True
        and rss_resolve_21_beta_row.get("matched_version") == "Resolve 21 beta",
        f"reason={rss_resolve_21_beta_row.get('exclusion_reason')!r}, matched={rss_resolve_21_beta_row.get('matched_version')!r}",
    )

    rss_generic_resolve = dict(rss_public_beta_21)
    rss_generic_resolve.update({
        "source_url": "https://www.reddit.com/r/davinciresolve/comments/rss003/example/",
        "parent_title": "Resolve crash during render",
        "report_title": "Resolve crash during render",
        "report_text": "Resolve crashed while rendering a timeline.",
    })
    rss_generic_resolve_row = row_from_candidate(beta_record, rss_generic_resolve, "2026-05-13T00:00:00Z")
    check(
        "RSS-style generic Resolve crash does not match Beta 1",
        rss_generic_resolve_row.get("counted") is False
        and rss_generic_resolve_row.get("exclusion_reason") == "missing_exact_patch_version_match",
        f"reason={rss_generic_resolve_row.get('exclusion_reason')!r}",
    )

    rss_public_beta_no_product = dict(rss_public_beta_21)
    rss_public_beta_no_product.update({
        "source_url": "https://www.reddit.com/r/davinciresolve/comments/rss004/example/",
        "parent_title": "public beta crash during render",
        "report_title": "public beta crash during render",
        "report_text": "public beta crashed while rendering a timeline.",
    })
    rss_public_beta_no_product_row = row_from_candidate(beta_record, rss_public_beta_no_product, "2026-05-13T00:00:00Z")
    check(
        "broad public beta without product context does not match Beta 1",
        rss_public_beta_no_product_row.get("counted") is False
        and rss_public_beta_no_product_row.get("exclusion_reason") == "missing_exact_patch_version_match",
        f"reason={rss_public_beta_no_product_row.get('exclusion_reason')!r}, matched={rss_public_beta_no_product_row.get('matched_version')!r}",
    )

    generic_no_version = dict(stable_for_beta)
    generic_no_version.update({
        "parent_title": "Resolve crashes during render",
        "report_title": "Resolve render crash",
        "report_text": "Resolve crashed while rendering a timeline.",
    })
    generic_no_version_row = row_from_candidate(stable_record, generic_no_version, "2026-05-13T00:00:00Z")
    check(
        "generic Resolve crash without version does not count",
        generic_no_version_row.get("counted") is False and generic_no_version_row.get("exclusion_reason") == "missing_exact_patch_version_match",
        f"reason={generic_no_version_row.get('exclusion_reason')!r}",
    )

    valid_stable = dict(stable_for_beta)
    valid_stable["source_url"] = "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=240002"
    valid_stable_row = row_from_candidate(stable_record, valid_stable, "2026-05-13T00:00:00Z")
    check(
        "exact stable 21 report with issue/date/specific URL passes",
        valid_stable_row.get("counted") is True,
        f"reason={valid_stable_row.get('exclusion_reason')!r}",
    )

    stable_aliases = version_aliases("21")
    for alias in (
        "DaVinci Resolve Studio 21",
        "Resolve Studio 21",
        "DaVinci 21",
        "21.0",
        "DaVinci Resolve 21.0",
        "DaVinci Resolve Studio 21.0",
        "Resolve 21.0",
        "Resolve Studio 21.0",
        "version 21",
        "version 21.0",
    ):
        check(
            f"stable 21 aliases include {alias}",
            alias in stable_aliases,
            f"aliases={stable_aliases}",
        )

    stable_alias_cases = [
        ("stable Studio full product alias passes", "DaVinci Resolve Studio 21 crashed during export."),
        ("stable Resolve Studio alias passes", "Resolve Studio 21 crashed during export."),
        ("stable DaVinci shorthand alias passes", "DaVinci 21 crashed during export."),
        ("stable 21.0 alias passes", "DaVinci Resolve Studio 21.0 crashed during export."),
        ("stable version 21 alias passes with product context", "DaVinci Resolve version 21 crashed during export."),
    ]
    for index, (label, text) in enumerate(stable_alias_cases, start=1):
        stable_alias_candidate = dict(stable_for_beta)
        stable_alias_candidate.update({
            "source_url": f"https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=24100{index}",
            "parent_title": text,
            "report_title": text,
            "report_text": text,
        })
        stable_alias_row = row_from_candidate(stable_record, stable_alias_candidate, "2026-05-13T00:00:00Z")
        check(
            label,
            stable_alias_row.get("counted") is True,
            f"reason={stable_alias_row.get('exclusion_reason')!r}, matched={stable_alias_row.get('matched_version')!r}",
        )

    version_only_stable = dict(stable_for_beta)
    version_only_stable.update({
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=241020",
        "parent_title": "version 21 crash during export",
        "report_title": "version 21 crash during export",
        "report_text": "version 21 crashed during export.",
    })
    version_only_stable_row = row_from_candidate(stable_record, version_only_stable, "2026-05-13T00:00:00Z")
    check(
        "stable version 21 without product context does not count",
        version_only_stable_row.get("counted") is False
        and version_only_stable_row.get("exclusion_reason") == "missing_davinci_product_context",
        f"reason={version_only_stable_row.get('exclusion_reason')!r}",
    )

    support_question_stable = dict(stable_for_beta)
    support_question_stable.update({
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=241023",
        "parent_title": "Is there a way to lock a color page palette to a node?",
        "report_title": "Is there a way to lock a color page palette to a node?",
        "report_text": "Resolve version: DaVinci Resolve 21 Studio. OS: Windows 11. I am trying to learn Resolve for a workflow question.",
    })
    support_question_stable_row = row_from_candidate(stable_record, support_question_stable, "2026-05-13T00:00:00Z")
    check(
        "stable version metadata in a support question does not count",
        support_question_stable_row.get("counted") is False
        and support_question_stable_row.get("exclusion_reason") == "not_a_real_issue_report",
        f"reason={support_question_stable_row.get('exclusion_reason')!r}",
    )

    conflicting_version_stable = dict(stable_for_beta)
    conflicting_version_stable.update({
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=241024",
        "parent_title": "DaVinci Resolve free version 20 crash on launch",
        "report_title": "DaVinci Resolve free version 20 crash on launch",
        "report_text": "DaVinci Resolve free version 20 crashed on launch. I also tried version 21 while debugging.",
    })
    conflicting_version_stable_row = row_from_candidate(stable_record, conflicting_version_stable, "2026-05-13T00:00:00Z")
    check(
        "stable 21 rejects conflicting DaVinci version context",
        conflicting_version_stable_row.get("counted") is False
        and conflicting_version_stable_row.get("exclusion_reason") == "conflicting_davinci_version_context",
        f"reason={conflicting_version_stable_row.get('exclusion_reason')!r}",
    )

    public_beta_for_stable = dict(beta_for_stable)
    public_beta_for_stable.update({
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=241021",
        "parent_title": "DaVinci Resolve 21.0 Public Beta 1 render crash",
        "report_title": "DaVinci Resolve 21.0 Public Beta 1 render crash",
        "report_text": "DaVinci Resolve 21.0 Public Beta 1 crashed during render.",
    })
    public_beta_for_stable_row = row_from_candidate(stable_record, public_beta_for_stable, "2026-05-13T00:00:00Z")
    check(
        "stable 21 rejects Public Beta 1 context even with 21.0 alias",
        public_beta_for_stable_row.get("counted") is False
        and public_beta_for_stable_row.get("exclusion_reason") == "beta_context_for_stable_record",
        f"reason={public_beta_for_stable_row.get('exclusion_reason')!r}",
    )

    point_zero_for_beta = dict(stable_for_beta)
    point_zero_for_beta.update({
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=241022",
        "parent_title": "DaVinci Resolve Studio 21.0 render crash",
        "report_title": "DaVinci Resolve Studio 21.0 render crash",
        "report_text": "DaVinci Resolve Studio 21.0 crashed during render.",
    })
    point_zero_for_beta_row = row_from_candidate(beta_record, point_zero_for_beta, "2026-05-13T00:00:00Z")
    check(
        "Beta 1 rejects stable 21.0 wording",
        point_zero_for_beta_row.get("counted") is False
        and point_zero_for_beta_row.get("exclusion_reason") == "missing_exact_patch_version_match",
        f"reason={point_zero_for_beta_row.get('exclusion_reason')!r}",
    )

    coherence_rows = [
        row_from_candidate(stable_record, valid_stable, "2026-05-13T00:00:00Z"),
        row_from_candidate(stable_record, stable_alias_candidate, "2026-05-13T00:00:00Z"),
    ]
    archived_stable_record = {
        "update_product": "DaVinci Resolve",
        "update_status": "archived",
    }
    stable_fields = _proposed_record_fields(
        "blackmagic-davinci",
        "21",
        coherence_rows,
        archived_stable_record,
        "2026-05-13T00:00:00Z",
    )
    check(
        "stable evidence promotes archived DaVinci 21 to current",
        stable_fields.get("update_status") == "current" and stable_fields.get("feed_hidden") is False,
        f"status={stable_fields.get('update_status')!r}, feed_hidden={stable_fields.get('feed_hidden')!r}",
    )
    check(
        "stable writeback removes archived-only beta wording",
        "archived" not in str(stable_fields.get("record_note") or "").lower()
        and "primary public record" not in str(stable_fields.get("record_note") or "").lower()
        and "stable/Studio" in str(stable_fields.get("record_note") or ""),
        f"record_note={stable_fields.get('record_note')!r}",
    )
    active_stable_fields = _proposed_record_fields(
        "blackmagic-davinci",
        "21",
        coherence_rows,
        {"update_product": "DaVinci Resolve", "update_status": "current"},
        "2026-05-13T00:00:00Z",
    )
    check(
        "active stable DaVinci 21 keeps coherence wording managed",
        "low-confidence Verified reports set" in str(active_stable_fields.get("update_decision_body") or ""),
        f"decision_body={active_stable_fields.get('update_decision_body')!r}",
    )

    beta_fields = _proposed_record_fields(
        "blackmagic-davinci",
        "21 Public Beta 1",
        [row_from_candidate(beta_record, candidate_from_fixture(control), "2026-05-13T00:00:00Z")],
        {"update_product": "DaVinci Resolve", "update_status": "archived"},
        "2026-05-13T00:00:00Z",
    )
    check(
        "Beta writeback does not use stable activation fields",
        "update_status" not in beta_fields and "record_note" not in beta_fields,
        f"fields={sorted(beta_fields)}",
    )

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
