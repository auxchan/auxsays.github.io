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
    candidates_from_capture,
    evaluate_candidate,
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


def no_version_text() -> str:
    return """
Adobe Premiere Pro
Bug Reports
Export freezes after the latest update
3 hours ago
Adobe Premiere Pro freezes on export after updating.
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


def fake_record(version: str = "26.2.2") -> object:
    return types.SimpleNamespace(update_version=version, update_published_at="2026-05-20T00:00:00Z")


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
    check("listing card uses embedded match basis", row.get("match_basis") == "embedded_listing_report_card", str(row))
    check("26.2.2 stays mapped to 26.2.2", row.get("update_version") == "26.2.2", str(row))

    feature = evaluate_candidate(candidates_from_capture(capture_row(feature_request_text()), product_id="adobe-premiere-pro")[0], {"26.2.2": fake_record()})
    check("rejects Adobe feature request listing card", feature.get("counted") is False and feature.get("exclusion_reason") == "not_a_real_issue_report", str(feature))

    question = evaluate_candidate(candidates_from_capture(capture_row(question_text()), product_id="adobe-premiere-pro")[0], {"26.2.2": fake_record()})
    check("rejects Adobe question/how-to without concrete regression", question.get("counted") is False and question.get("exclusion_reason") == "not_a_real_issue_report", str(question))

    no_version_candidates = candidates_from_capture(capture_row(no_version_text()), product_id="adobe-premiere-pro")
    check("rejects listing card with no exact version", no_version_candidates == [], str(no_version_candidates))

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
        {"26.2.2": fake_record()},
    )
    check("accepts Creative COW listing fixture with exact version and concrete issue", creative_concrete.get("counted") is True, str(creative_concrete))

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
