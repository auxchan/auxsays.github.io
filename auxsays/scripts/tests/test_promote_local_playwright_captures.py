#!/usr/bin/env python3
"""Tests for local Playwright capture promotion."""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
import types
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

try:
    import yaml  # type: ignore
except Exception:
    yaml = types.SimpleNamespace(safe_load=lambda *_args, **_kwargs: {}, safe_dump=lambda value, **_kwargs: json.dumps(value, indent=2))
    sys.modules["yaml"] = yaml

import promote_local_playwright_captures as bridge
from promote_local_playwright_captures import (
    build_release_windows,
    candidates_from_capture,
    evaluate_candidate,
    main as bridge_main,
    promote,
    read_capture_jsonl,
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


def capture_row(text: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "source_url": "https://community.adobe.com/t5/premiere-pro-discussions/bd-p/premiere-pro?page=1",
        "final_url": "https://community.adobe.com/t5/premiere-pro-discussions/bd-p/premiere-pro?page=1",
        "source_name": "Adobe Community",
        "product_hint": "adobe-premiere-pro",
        "version_hint": "26.2",
        "page_title": "Premiere Pro discussions",
        "visible_text": text,
        "captured_at": "2026-05-21T12:00:00Z",
        "capture_method": "local_playwright",
        "capture_status": "success",
    }
    row.update(overrides)
    return row


def adobe_bug_listing_text() -> str:
    return """
Adobe Premiere Pro
Participant
Bug Reports
Open for Voting
In 26.2.2, the app would freeze whenever I needed to open a drop-down in the menu.
5 hours ago
Using the latest version 26.2.2 of Adobe Premiere Pro, the application freezes whenever I open a drop-down menu while editing.
"""


def feature_request_text() -> str:
    return """
Adobe Premiere Pro
Ideas
Feature Requests
Premiere Pro 26.2.2 should add a new color label option
2 days ago
I would like a feature request for more labels in Adobe Premiere Pro.
"""


def question_text() -> str:
    return """
Adobe Premiere Pro
Questions
How do I use captions in Premiere Pro 26.2.2?
1 day ago
I am learning Adobe Premiere Pro and want to know how to use captions.
"""


def no_version_current_text() -> str:
    return """
Adobe Premiere Pro
Bug Reports
Export freezes after the latest update
3 hours ago
Adobe Premiere Pro freezes on export after updating.
"""


def mask_tool_current_text() -> str:
    return """
Adobe Premiere Pro
Participant
Bug Reports
Mask Tool Issues (Gaussian Blur & Opacity)
5 hours ago
IssueOpacity mask tools (pen, rectangle, ellipse) do not appear in Effect Controls for certain MP4 files in Premiere Pro 2026, even though the files are standard H.264 video clips and effects apply normally. This makes it impossible to mask Gaussian Blur.
"""


def truncated_262_text(date_text: str = "5 hours ago") -> str:
    return f"""
Adobe Premiere Pro
Participant
Bug Reports
Premiere 26.2 freezes during editing
{date_text}
Premiere Pro 26.2 freezes when opening menus after the update.
"""


def conflicting_old_exact_text() -> str:
    return """
Adobe Premiere Pro
Participant
Bug Reports
Premiere Pro 26.0.1 search broken
5 hours ago
Premiere Pro 26.0.1 search is broken after installing the current app.
"""


def beta_report_text() -> str:
    return """
Adobe Premiere Pro
Participant
Bug Reports
Premiere Pro 2026 beta export freezes
5 hours ago
The latest Premiere Pro beta freezes on export after updating.
"""


def official_announcement_text() -> str:
    return """
Adobe Premiere Pro
What's New in Adobe Premiere 26.2.2 - May 2026
May 21, 2026
Adobe says Premiere Pro 26.2.2 fixes a critical stability issue that could cause Premiere Pro to hang.
"""


def generic_listing_text() -> str:
    return """
Adobe Premiere Pro
Welcome to the Premiere Pro community.
Browse discussions, bug reports, and ideas.
"""


def creative_title_only_text() -> str:
    return """
Adobe Premiere Pro
WARNING: PPro Version 26.2.2 (Build 3) gives you more time to watch paint dry...
2 days ago
"""


def creative_concrete_text() -> str:
    return """
Adobe Premiere Pro
WARNING: Premiere Pro Version 26.2.2 export freezes
2 days ago
Adobe Premiere Pro 26.2.2 freezes for several minutes during export and timeline editing after the update.
"""


def detail_capture_row(
    title: str,
    body: str,
    *,
    source_url: str = "https://community.adobe.com/t5/premiere-pro-discussions/premiere-pro-26-2-2-freezes/td-p/1560001",
    source_name: str = "Adobe Community",
    source_type: str = "adobe_community",
    source_date_text: str = "May 21, 2026",
    source_date_resolved: str = "2026-05-21T10:00:00.000Z",
    listing_card_title: str = "",
    captured_at: str = "2026-05-21T12:00:00Z",
) -> dict[str, object]:
    return {
        "source_url": source_url,
        "detail_url": source_url,
        "final_url": source_url,
        "source_name": source_name,
        "source_type": source_type,
        "product_id": "adobe-premiere-pro",
        "product_hint": "adobe-premiere-pro",
        "version_hint": "26.2",
        "page_title": title,
        "title": title,
        "visible_text": f"{title}\n{source_date_text}\n{body}",
        "body_text": body,
        "source_date_text": source_date_text,
        "source_date_resolved": source_date_resolved,
        "listing_card_title": listing_card_title,
        "listing_card_date_text": source_date_text,
        "captured_at": captured_at,
        "capture_method": "local_playwright",
        "capture_status": "success",
        "url_dedupe_key": source_url.rstrip("/"),
    }


def fake_record(version: str = "26.2.2", published_at: str = "2026-05-20T00:00:00Z", product: str = "Premiere Pro") -> object:
    return types.SimpleNamespace(
        product_id="adobe-premiere-pro",
        update_version=version,
        update_published_at=published_at,
        update_status="current",
        update_product=product,
    )


def record_map(*records: object) -> dict[str, object]:
    return {str(record.update_version): record for record in records}


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def run() -> int:
    print("=" * 60)
    print("Local Playwright capture promotion tests")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "captured-pages.jsonl"
        write_jsonl(input_path, [capture_row(adobe_bug_listing_text())])
        loaded = read_capture_jsonl(input_path, max_rows=100)
        check("reads captured-pages.jsonl fixture", len(loaded) == 1 and loaded[0]["source_name"] == "Adobe Community", str(loaded))

    candidates = candidates_from_capture(capture_row(adobe_bug_listing_text()), product_id="adobe-premiere-pro")
    row = evaluate_candidate(candidates[0], {"26.2.2": fake_record("26.2.2")})
    check("accepts Adobe embedded Bug Reports exact 26.2.2 freeze card", row.get("counted") is True, str(row))
    check("exact version uses exact_version basis", row.get("match_basis") == "exact_version" and row.get("version_match_confidence") == "exact", str(row))
    check("26.2.2 stays mapped to 26.2.2", row.get("update_version") == "26.2.2", str(row))

    stable_2622 = fake_record("26.2.2", "2026-05-01T00:00:00Z")
    stable_2623 = fake_record("26.2.3", "2026-05-25T00:00:00Z")
    truncated = evaluate_candidate(
        candidates_from_capture(capture_row(truncated_262_text()), product_id="adobe-premiere-pro")[0],
        record_map(stable_2622, stable_2623),
    )
    check(
        "short version prefix inside active release window counts as truncated_version_in_release_window",
        truncated.get("counted") is True
        and truncated.get("update_version") == "26.2.2"
        and truncated.get("match_basis") == "truncated_version_in_release_window"
        and truncated.get("version_match_confidence") == "inferred_truncated_window",
        str(truncated),
    )

    truncated_before = evaluate_candidate(
        candidates_from_capture(capture_row(truncated_262_text("April 28, 2026")), product_id="adobe-premiere-pro")[0],
        record_map(stable_2622, stable_2623),
    )
    check("short version prefix before patch release is rejected", truncated_before.get("counted") is False, str(truncated_before))

    after_next = evaluate_candidate(
        candidates_from_capture(capture_row(truncated_262_text(), captured_at="2026-05-27T12:00:00Z"), product_id="adobe-premiere-pro")[0],
        record_map(stable_2622, stable_2623),
    )
    check(
        "short version prefix after next patch release maps to newer active patch",
        after_next.get("counted") is True and after_next.get("update_version") == "26.2.3",
        str(after_next),
    )

    current = evaluate_candidate(
        candidates_from_capture(capture_row(no_version_current_text()), product_id="adobe-premiere-pro")[0],
        record_map(stable_2622, stable_2623),
    )
    check(
        "no-version current/latest report inside active window can count as release_window_inferred",
        current.get("counted") is True
        and current.get("update_version") == "26.2.2"
        and current.get("match_basis") == "release_window_inferred"
        and current.get("version_match_confidence") == "inferred_release_window",
        str(current),
    )

    mask_tool = evaluate_candidate(
        candidates_from_capture(capture_row(mask_tool_current_text()), product_id="adobe-premiere-pro")[0],
        record_map(stable_2622, stable_2623),
    )
    check(
        "Mask Tool Issues can count by release-window inference",
        mask_tool.get("counted") is True
        and mask_tool.get("update_version") == "26.2.2"
        and mask_tool.get("match_basis") == "release_window_inferred",
        str(mask_tool),
    )

    no_date_capture = capture_row(no_version_current_text(), captured_at="")
    no_date_candidates = candidates_from_capture(no_date_capture, product_id="adobe-premiere-pro")
    no_date = evaluate_candidate(no_date_candidates[0], record_map(stable_2622))
    check("no-version report with no resolvable date is rejected", no_date.get("counted") is False and no_date.get("exclusion_reason") == "missing_resolvable_source_date_for_inferred_match", str(no_date))

    conflict = evaluate_candidate(
        candidates_from_capture(capture_row(conflicting_old_exact_text()), product_id="adobe-premiere-pro")[0],
        record_map(fake_record("26.0.1", "2026-02-01T00:00:00Z"), stable_2622),
    )
    check("report with conflicting exact older version is rejected", conflict.get("counted") is False and conflict.get("exclusion_reason") == "conflicting_exact_version_for_active_release_window", str(conflict))

    beta_stable_records = record_map(stable_2622, fake_record("26.3 beta", "2026-05-01T00:00:00Z", product="Premiere Pro Beta"))
    beta = evaluate_candidate(candidates_from_capture(capture_row(beta_report_text()), product_id="adobe-premiere-pro")[0], beta_stable_records)
    check("beta/stable channels do not cross-map", beta.get("counted") is False or beta.get("update_version") != "26.2.2", str(beta))

    feature = evaluate_candidate(candidates_from_capture(capture_row(feature_request_text()), product_id="adobe-premiere-pro")[0], {"26.2.2": fake_record()})
    check("rejects Adobe feature request listing card", feature.get("counted") is False and feature.get("exclusion_reason") == "not_a_real_issue_report", str(feature))

    question = evaluate_candidate(candidates_from_capture(capture_row(question_text()), product_id="adobe-premiere-pro")[0], {"26.2.2": fake_record()})
    check("rejects Adobe question/how-to without concrete regression", question.get("counted") is False and question.get("exclusion_reason") == "not_a_real_issue_report", str(question))

    announcement_candidate = candidates_from_capture(
        capture_row(
            official_announcement_text(),
            source_url="https://community.adobe.com/announcements-727/what-s-new-in-adobe-premiere-26-2-2-may-2026-1560755",
            final_url="https://community.adobe.com/announcements-727/what-s-new-in-adobe-premiere-26-2-2-may-2026-1560755",
        ),
        product_id="adobe-premiere-pro",
    )[0]
    announcement = evaluate_candidate(announcement_candidate, {"26.2.2": fake_record("26.2.2", "2026-05-01T00:00:00Z")})
    check("official announcement inside active window is rejected as user evidence", announcement.get("counted") is False and announcement.get("exclusion_reason") == "official_announcement_not_user_evidence", str(announcement))

    no_context_current = evaluate_candidate(
        candidates_from_capture(capture_row(no_version_current_text(), captured_at=""), product_id="adobe-premiere-pro")[0],
        {"26.2.2": fake_record()},
    )
    check("rejects no-version listing card without date", no_context_current.get("counted") is False, str(no_context_current))

    generic_candidates = candidates_from_capture(capture_row(generic_listing_text()), product_id="adobe-premiere-pro")
    check("rejects generic listing page text without discrete card", generic_candidates == [], str(generic_candidates))

    creative_source = "https://creativecow.net/forums/forum/adobe-premiere-pro/"
    creative_title_only = evaluate_candidate(
        candidates_from_capture(capture_row(creative_title_only_text(), source_url=creative_source, final_url=creative_source, source_name="Creative COW"), product_id="adobe-premiere-pro")[0],
        {"26.2.2": fake_record()},
    )
    check(
        "rejects Creative COW title without enough concrete issue detail",
        creative_title_only.get("counted") is False and creative_title_only.get("exclusion_reason") in {"insufficient_concrete_issue_detail", "not_a_real_issue_report"},
        str(creative_title_only),
    )

    creative_concrete = evaluate_candidate(
        candidates_from_capture(capture_row(creative_concrete_text(), source_url=creative_source, final_url=creative_source, source_name="Creative COW"), product_id="adobe-premiere-pro")[0],
        {"26.2.2": fake_record("26.2.2", "2026-05-01T00:00:00Z")},
    )
    check("accepts Creative COW listing fixture with exact version and concrete issue", creative_concrete.get("counted") is True, str(creative_concrete))

    adobe_detail_candidates = candidates_from_capture(
        detail_capture_row(
            "Premiere Pro 26.2.2 freezes when opening menus",
            "Using Adobe Premiere Pro 26.2.2, the application freezes whenever I open a drop-down menu while editing.",
        ),
        product_id="adobe-premiere-pro",
    )
    adobe_detail = evaluate_candidate(adobe_detail_candidates[0], {"26.2.2": fake_record("26.2.2", "2026-05-01T00:00:00Z")})
    check(
        "detail-page rows promote through exact version matching",
        adobe_detail.get("counted") is True
        and adobe_detail.get("match_basis") == "exact_version"
        and adobe_detail.get("source_url", "").endswith("/td-p/1560001"),
        str(adobe_detail),
    )

    inferred_detail = evaluate_candidate(
        candidates_from_capture(detail_capture_row(
            "Export freezes after the latest update",
            "Adobe Premiere Pro freezes during export after the latest update.",
            source_url="https://community.adobe.com/t5/premiere-pro-discussions/export-freezes-latest-update/td-p/1560002",
            listing_card_title="Export freezes after the latest update",
        ), product_id="adobe-premiere-pro")[0],
        record_map(stable_2622, stable_2623),
    )
    check(
        "detail-page rows promote through release-window inference when valid",
        inferred_detail.get("counted") is True
        and inferred_detail.get("update_version") == "26.2.2"
        and inferred_detail.get("match_basis") == "release_window_inferred",
        str(inferred_detail),
    )

    creative_detail_title_only = evaluate_candidate(
        candidates_from_capture(detail_capture_row(
            "WARNING: PPro Version 26.2.2 gives you more time to watch paint dry...",
            "WARNING: PPro Version 26.2.2 gives you more time to watch paint dry...",
            source_url="https://creativecow.net/forums/thread/premiere-pro-262-title-only/",
            source_name="Creative COW",
            source_type="creativecow_forum",
            source_date_text="May 21, 2026",
            source_date_resolved="2026-05-21T10:00:00.000Z",
        ), product_id="adobe-premiere-pro")[0],
        {"26.2.2": fake_record("26.2.2", "2026-05-01T00:00:00Z")},
    )
    check(
        "Creative COW title-only detail page remains rejected without concrete issue text",
        creative_detail_title_only.get("counted") is False
        and creative_detail_title_only.get("exclusion_reason") == "not_a_real_issue_report",
        str(creative_detail_title_only),
    )

    creative_detail = evaluate_candidate(
        candidates_from_capture(detail_capture_row(
            "Premiere Pro 26.2.2 export freezes",
            "Adobe Premiere Pro 26.2.2 freezes for several minutes during export and timeline editing after the update.",
            source_url="https://creativecow.net/forums/thread/premiere-pro-262-export-freezes/",
            source_name="Creative COW",
            source_type="creativecow_forum",
            source_date_text="May 21, 2026",
            source_date_resolved="2026-05-21T10:00:00.000Z",
        ), product_id="adobe-premiere-pro")[0],
        {"26.2.2": fake_record("26.2.2", "2026-05-01T00:00:00Z")},
    )
    check("Creative COW detail page with exact version and concrete issue can count", creative_detail.get("counted") is True, str(creative_detail))

    detail_feature = evaluate_candidate(
        candidates_from_capture(detail_capture_row(
            "Premiere Pro 26.2.2 should add new labels",
            "Feature request: Adobe Premiere Pro 26.2.2 should add a new color label option.",
            source_url="https://community.adobe.com/t5/premiere-pro-discussions/new-labels/td-p/1560003",
        ), product_id="adobe-premiere-pro")[0],
        {"26.2.2": fake_record("26.2.2", "2026-05-01T00:00:00Z")},
    )
    check("feature requests still reject from detail pages", detail_feature.get("counted") is False and detail_feature.get("exclusion_reason") == "not_a_real_issue_report", str(detail_feature))

    detail_announcement = evaluate_candidate(
        candidates_from_capture(detail_capture_row(
            "What's New in Adobe Premiere 26.2.2",
            "Official announcement: Adobe says Premiere Pro 26.2.2 brings a range of improvements and release notes.",
            source_url="https://community.adobe.com/announcements-727/what-s-new-in-adobe-premiere-26-2-2/td-p/1560004",
        ), product_id="adobe-premiere-pro")[0],
        {"26.2.2": fake_record("26.2.2", "2026-05-01T00:00:00Z")},
    )
    check("official announcements still reject from detail pages", detail_announcement.get("counted") is False and detail_announcement.get("exclusion_reason") == "official_announcement_not_user_evidence", str(detail_announcement))

    old_record_row = evaluate_candidate(candidates[0], {"26.2": fake_record("26.2")})
    check("does not map 26.2.2 evidence to 26.2 without family rule", old_record_row.get("update_version") == "26.2.2", str(old_record_row))
    check("26.2.2 can be accepted but unmatched when no 26.2.2 record exists", old_record_row.get("counted") is True, str(old_record_row))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "captured-pages.jsonl"
        write_jsonl(input_path, [capture_row(adobe_bug_listing_text())])
        original_generated = bridge.generated_records
        original_load_evidence = bridge.load_evidence
        try:
            bridge.generated_records = lambda *_args, **_kwargs: []
            bridge.load_evidence = lambda *_args, **_kwargs: []
            result = promote(input_path=input_path, product_id="adobe-premiere-pro", max_rows=100, write=False)
        finally:
            bridge.generated_records = original_generated
            bridge.load_evidence = original_load_evidence
        check("reports unmatched version when no generated 26.2.2 record exists", result.unmatched_versions == {"26.2.2"}, str(result.summary(write=False, output_files=[])))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "captured-pages.jsonl"
        write_jsonl(input_path, [capture_row(adobe_bug_listing_text())])
        existing_id = row["id"]
        original_generated = bridge.generated_records
        original_load_evidence = bridge.load_evidence
        try:
            bridge.generated_records = lambda *_args, **_kwargs: [fake_record("26.2.2")]
            bridge.load_evidence = lambda *_args, **_kwargs: [{"id": existing_id, "product_id": "adobe-premiere-pro", "update_version": "26.2.2", "source_url": "https://example.com"}]
            result = promote(input_path=input_path, product_id="adobe-premiere-pro", max_rows=100, write=False)
        finally:
            bridge.generated_records = original_generated
            bridge.load_evidence = original_load_evidence
        check("dedupes against existing evidence card IDs", len(result.accepted) == 0 and any(item.get("exclusion_reason") == "duplicate_existing_evidence" for item in result.rejected), str(result.rejected))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "captured-pages.jsonl"
        shared_title = "In 26.2.2, the app would freeze whenever I needed to open a drop-down in the menu."
        detail_row = detail_capture_row(
            shared_title,
            "Using Adobe Premiere Pro 26.2.2, the application freezes whenever I open a drop-down menu while editing.",
            listing_card_title=shared_title,
        )
        write_jsonl(input_path, [capture_row(adobe_bug_listing_text()), detail_row])
        original_generated = bridge.generated_records
        original_load_evidence = bridge.load_evidence
        try:
            bridge.generated_records = lambda *_args, **_kwargs: [fake_record("26.2.2", "2026-05-01T00:00:00Z")]
            bridge.load_evidence = lambda *_args, **_kwargs: []
            result = promote(input_path=input_path, product_id="adobe-premiere-pro", max_rows=100, write=False)
        finally:
            bridge.generated_records = original_generated
            bridge.load_evidence = original_load_evidence
        check(
            "listing-card and detail-page version of same report dedupe to one detail evidence row",
            len(result.accepted) == 1
            and result.accepted[0].get("source_url", "").endswith("/td-p/1560001")
            and any(item.get("exclusion_reason") == "duplicate_detail_page_evidence" for item in result.rejected),
            f"accepted={result.accepted} rejected={result.rejected}",
        )

    before = protected_snapshot()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "captured-pages.jsonl"
        write_jsonl(input_path, [capture_row(adobe_bug_listing_text())])
        original_generated = bridge.generated_records
        original_load_evidence = bridge.load_evidence
        try:
            bridge.generated_records = lambda *_args, **_kwargs: []
            bridge.load_evidence = lambda *_args, **_kwargs: []
            promote(input_path=input_path, product_id="adobe-premiere-pro", max_rows=100, write=False)
        finally:
            bridge.generated_records = original_generated
            bridge.load_evidence = original_load_evidence
    check("dry-run does not write consensus/generated/state files", protected_snapshot() == before)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "outbox" / "captured-pages.jsonl"
        input_path.parent.mkdir()
        write_jsonl(input_path, [capture_row(adobe_bug_listing_text()), capture_row(feature_request_text())])
        before_logs = protected_snapshot()
        original_generated = bridge.generated_records
        original_load_evidence = bridge.load_evidence
        try:
            bridge.generated_records = lambda *_args, **_kwargs: [fake_record("26.2.2", "2026-05-01T00:00:00Z")]
            bridge.load_evidence = lambda *_args, **_kwargs: []
            exit_code = bridge_main(["--input", str(input_path), "--product-id", "adobe-premiere-pro", "--dry-run"])
        finally:
            bridge.generated_records = original_generated
            bridge.load_evidence = original_load_evidence
        accepted_log = input_path.parent / "logs" / "promotion-accepted.jsonl"
        rejected_log = input_path.parent / "logs" / "promotion-rejections.jsonl"
        accepted_rows = [json.loads(line) for line in accepted_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        rejected_rows = [json.loads(line) for line in rejected_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        check(
            "dry-run writes accepted/rejected explanation JSONL",
            exit_code == 0
            and accepted_rows
            and rejected_rows
            and accepted_rows[0].get("accepted_reason")
            and rejected_rows[0].get("rejection_reason"),
            f"accepted={accepted_rows} rejected={rejected_rows}",
        )
        check("dry-run explanation JSONL does not modify consensus/generated/state files", protected_snapshot() == before_logs)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "captured-pages.jsonl"
        evidence_path = tmp_path / "consensus_evidence.yml"
        health_path = tmp_path / "evidence_method_health.yml"
        write_jsonl(input_path, [capture_row(adobe_bug_listing_text())])
        original_generated = bridge.generated_records
        original_load_evidence = bridge.load_evidence
        calls: list[str] = []
        try:
            bridge.generated_records = lambda *_args, **_kwargs: [fake_record("26.2.2")]
            bridge.load_evidence = lambda *args, **kwargs: []
            result = promote(
                input_path=input_path,
                product_id="adobe-premiere-pro",
                max_rows=100,
                write=True,
                evidence_path=evidence_path,
                method_health_path=health_path,
                writeback_func=lambda version: calls.append(version) or True,
            )
        finally:
            bridge.generated_records = original_generated
            bridge.load_evidence = original_load_evidence
        check("write mode uses shared evidence helper output", evidence_path.exists() and result.evidence_rows_added == 1, evidence_path.read_text(encoding="utf-8") if evidence_path.exists() else "")
        check("write mode uses method health helper output", health_path.exists() and result.method_health_changed == 1, health_path.read_text(encoding="utf-8") if health_path.exists() else "")
        check("write mode invokes existing writeback path for matched record", calls == ["26.2.2"], str(calls))

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


def protected_snapshot() -> dict[str, tuple[float, int] | None]:
    paths = [
        _REPO / "auxsays" / "_data" / "consensus_evidence.yml",
        _REPO / "auxsays" / "_data" / "evidence_method_health.yml",
        _REPO / "auxsays" / "_data" / "source_health.yml",
        _REPO / "auxsays" / "_data" / "qa_status.json",
        _REPO / "auxsays" / "_data" / "consensus_status.json",
        _REPO / "auxsays" / "_data" / "patch_ingest_state.json",
    ]
    snapshot: dict[str, tuple[float, int] | None] = {}
    for path in paths:
        if not path.exists():
            snapshot[str(path)] = None
            continue
        stat = path.stat()
        snapshot[str(path)] = (stat.st_mtime, stat.st_size)
    generated = _REPO / "auxsays" / "updates" / "generated"
    snapshot["generated_count"] = (0.0, len(list(generated.glob("*.md"))))
    return snapshot


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
