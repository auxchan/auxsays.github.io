#!/usr/bin/env python3
"""Tests for consensus evidence audit severity/category reporting."""
from __future__ import annotations

import json
import io
import sys
import tempfile
import traceback
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import audit_consensus_evidence as audit_mod

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


def yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def record_text(**overrides: Any) -> str:
    fields: dict[str, Any] = {
        "update_entry": True,
        "title": "OBS Studio 32.1.2 official update breakdown",
        "permalink": "/updates/obs-project/obs-studio/32-1-2/",
        "product_id": "obs-studio",
        "update_version": "32.1.2",
        "update_status": "current",
        "update_report_count": 1,
        "confirmed_patch_specific_report_count": 1,
        "evidence_state": "pilot_sample",
        "consensus_collection_status": "pilot_initial_sample",
        "update_last_checked": "2099-01-01T00:00:00Z",
        "evidence_last_checked": "2099-01-01T00:00:00Z",
        "official_patch_notes_body": "Captured official body.",
        "official_checksums_body": "",
    }
    fields.update(overrides)
    front_matter = "\n".join(f"{key}: {yaml_value(value)}" for key, value in fields.items())
    return f"---\n{front_matter}\n---\n"


def evidence_text(*rows: dict[str, Any]) -> str:
    output = ["schema_version: 1", "evidence:"]
    for row in rows:
        output.append(f"- id: {yaml_value(row.get('id', 'evidence-row'))}")
        fields = {
            "product_id": row.get("product_id", "obs-studio"),
            "update_version": row.get("update_version", "32.1.2"),
            "source_url": row.get("source_url", "https://example.test/report"),
            "captured_at": row.get("captured_at", "2099-01-01T00:00:00Z"),
            "patch_version_matched": row.get("patch_version_matched", True),
            "counted": row.get("counted", True),
            "sentiment": row.get("sentiment", "negative"),
            "severity": row.get("severity", "high"),
        }
        for key, value in fields.items():
            output.append(f"  {key}: {yaml_value(value)}")
    return "\n".join(output) + "\n"


@contextmanager
def temporary_case(
    *,
    records: list[tuple[str, str]],
    evidence: str,
    source_state: dict[str, dict[str, str]] | None = None,
) -> Any:
    old_paths = (
        audit_mod.ROOT,
        audit_mod.GENERATED_DIR,
        audit_mod.EVIDENCE_PATH,
        audit_mod.STATE_PATH,
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "auxsays"
        generated_dir = root / "updates" / "generated"
        data_dir = root / "_data"
        generated_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)
        for name, text in records:
            (generated_dir / name).write_text(text, encoding="utf-8")
        evidence_path = data_dir / "consensus_evidence.yml"
        evidence_path.write_text(evidence, encoding="utf-8")
        state_path = data_dir / "patch_ingest_state.json"
        state_path.write_text(json.dumps({"sources": source_state or {}}), encoding="utf-8")

        audit_mod.ROOT = root
        audit_mod.GENERATED_DIR = generated_dir
        audit_mod.EVIDENCE_PATH = evidence_path
        audit_mod.STATE_PATH = state_path
        try:
            yield
        finally:
            (
                audit_mod.ROOT,
                audit_mod.GENERATED_DIR,
                audit_mod.EVIDENCE_PATH,
                audit_mod.STATE_PATH,
            ) = old_paths


def write_case(
    *,
    records: list[tuple[str, str]],
    evidence: str,
    source_state: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    with temporary_case(records=records, evidence=evidence, source_state=source_state):
        return audit_mod.audit(stale_days=7)


def run_cli_case(
    args: list[str],
    *,
    records: list[tuple[str, str]],
    evidence: str,
    source_state: dict[str, dict[str, str]] | None = None,
) -> tuple[int, str]:
    old_argv = sys.argv[:]
    output = io.StringIO()
    with temporary_case(records=records, evidence=evidence, source_state=source_state):
        sys.argv = ["audit_consensus_evidence.py", *args]
        try:
            with redirect_stdout(output):
                exit_code = audit_mod.main()
        finally:
            sys.argv = old_argv
    return exit_code, output.getvalue()


def finding_names(result: dict[str, Any], category: str) -> set[str]:
    return {str(item.get("finding")) for item in result.get(category, [])}


def run() -> int:
    print("=" * 60)
    print("Consensus evidence audit severity tests")
    print("=" * 60)

    result = write_case(
        records=[("2026-04-21-obs-studio-32-1-2.md", record_text())],
        evidence=evidence_text({"id": "obs-32-1-2-report"}),
        source_state={"obs-studio": {"last_checked_at": "2099-01-02T00:00:00Z"}},
    )
    check("source freshness drift is advisory-only", result["category_counts"]["source_freshness_advisories"] == 1, json.dumps(result["category_counts"]))
    check("source freshness drift has no integrity errors", result["category_counts"]["integrity_errors"] == 0, json.dumps(result.get("integrity_errors")))
    check("source freshness drift does not fail strict policy", not audit_mod.strict_has_failures(result), json.dumps(result["strict_failure_categories"]))

    summary_output = io.StringIO()
    with redirect_stdout(summary_output):
        audit_mod.print_summary(result)
    summary = summary_output.getvalue()
    check("summary prints category counts", all(text in summary for text in (
        "Records scanned: 1",
        "Records with reports: 1",
        "Structured evidence groups: 1",
        "Structured evidence rows: 1",
        "Integrity errors: 0",
        "Evidence freshness errors: 0",
        "Record freshness warnings: 0",
        "Source freshness advisories: 1",
        "Strict failure categories:",
        "Affected report-bearing records with evidence freshness errors:",
        "- None",
    )), summary)

    result = write_case(
        records=[("2026-04-21-obs-studio-32-1-2.md", record_text(update_report_count=2, confirmed_patch_specific_report_count=2))],
        evidence=evidence_text({"id": "obs-32-1-2-report"}),
    )
    check("count mismatch is an integrity error", "generated_report_count_differs_from_structured_evidence" in finding_names(result, "integrity_errors"), json.dumps(result.get("integrity_errors")))
    check("count mismatch fails strict policy", audit_mod.strict_has_failures(result), json.dumps(result["strict_failure_categories"]))

    result = write_case(
        records=[],
        evidence=evidence_text({"id": "obs-32-1-2-report"}),
    )
    check("orphan structured evidence is an integrity error", "structured_evidence_without_matching_generated_record" in finding_names(result, "integrity_errors"), json.dumps(result.get("integrity_errors")))
    check("orphan structured evidence fails strict policy", audit_mod.strict_has_failures(result), json.dumps(result["strict_failure_categories"]))

    result = write_case(
        records=[("2026-04-21-obs-studio-32-1-2.md", record_text(evidence_last_checked="2000-01-01T00:00:00Z"))],
        evidence=evidence_text({"id": "obs-32-1-2-report"}),
    )
    check("stale report evidence freshness is evidence freshness error", "stale_evidence_last_checked" in finding_names(result, "evidence_freshness_errors"), json.dumps(result.get("evidence_freshness_errors")))
    check("stale report evidence freshness fails strict policy", audit_mod.strict_has_failures(result), json.dumps(result["strict_failure_categories"]))

    exit_code, summary = run_cli_case(
        ["--summary", "--strict"],
        records=[("2026-04-21-obs-studio-32-1-2.md", record_text(evidence_last_checked="2000-01-01T00:00:00Z"))],
        evidence=evidence_text({"id": "obs-32-1-2-report"}),
    )
    check("summary strict exits nonzero for evidence freshness errors", exit_code == 1, summary)
    check("summary strict lists affected freshness failures", "2026-04-21-obs-studio-32-1-2.md" in summary and "stale_evidence_last_checked" in summary, summary)

    result = write_case(
        records=[
            (
                "2026-04-17-comfyui-0-19-3.md",
                record_text(
                    title="ComfyUI 0.19.3 official update breakdown",
                    permalink="/updates/comfyui/comfyui/0-19-3/",
                    product_id="comfyui",
                    update_version="0.19.3",
                    update_report_count=0,
                    confirmed_patch_specific_report_count=0,
                    evidence_state="official_only",
                    consensus_collection_status="deferred_official_only",
                ),
            )
        ],
        evidence=evidence_text(),
        source_state={"comfyui": {"last_checked_at": "2099-01-02T00:00:00Z"}},
    )
    check("official-only source drift is advisory", result["category_counts"]["source_freshness_advisories"] == 1, json.dumps(result["category_counts"]))
    check("official-only source drift is not count-integrity failure", result["category_counts"]["integrity_errors"] == 0, json.dumps(result.get("integrity_errors")))

    exit_code, summary = run_cli_case(
        ["--summary", "--strict"],
        records=[
            (
                "2026-04-17-comfyui-0-19-3.md",
                record_text(
                    title="ComfyUI 0.19.3 official update breakdown",
                    permalink="/updates/comfyui/comfyui/0-19-3/",
                    product_id="comfyui",
                    update_version="0.19.3",
                    update_report_count=0,
                    confirmed_patch_specific_report_count=0,
                    evidence_state="official_only",
                    consensus_collection_status="deferred_official_only",
                ),
            )
        ],
        evidence=evidence_text(),
        source_state={"comfyui": {"last_checked_at": "2099-01-02T00:00:00Z"}},
    )
    check("summary strict does not fail source advisories only", exit_code == 0, summary)

    exit_code, json_output = run_cli_case(
        ["--json"],
        records=[("2026-04-21-obs-studio-32-1-2.md", record_text())],
        evidence=evidence_text({"id": "obs-32-1-2-report"}),
    )
    payload = json.loads(json_output)
    check("JSON CLI exits zero", exit_code == 0, json_output)
    check("JSON output includes category counts", "category_counts" in payload and "source_freshness_advisories" in payload["category_counts"], json.dumps(payload))
    check("JSON output includes strict failure categories", "strict_failure_categories" in payload and "integrity_errors" in payload["strict_failure_categories"], json.dumps(payload))

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
