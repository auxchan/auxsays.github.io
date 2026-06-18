#!/usr/bin/env python3
"""Tests for read-only evidence method-health validation."""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from validate_evidence_method_health import validate

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


def row_yaml(
    *,
    product_id: str = "adobe-premiere-pro",
    update_version: str = "26.2.2",
    method_id: str = "adobe_community_search",
    source_type: str = "adobe_community_bug_report",
    status: str = "success",
    candidates_found: str = "2",
    accepted_candidates: str = "1",
    duplicate_existing_evidence: str = "0",
    evidence_rows_added: str = "1",
    public_counted_reports: str = "1",
    accepted_reports: str = "1",
    rejected_reports: str = "1",
    last_run: str = "'2026-06-18T18:11:43Z'",
    blocked_reason: str = "''",
    notes: str = "Validated telemetry fixture.",
) -> str:
    return f"""- product_id: {product_id}
  update_version: {update_version}
  method_id: {method_id}
  source_type: {source_type}
  status: {status}
  candidates_found: {candidates_found}
  accepted_candidates: {accepted_candidates}
  duplicate_existing_evidence: {duplicate_existing_evidence}
  evidence_rows_added: {evidence_rows_added}
  public_counted_reports: {public_counted_reports}
  accepted_reports: {accepted_reports}
  rejected_reports: {rejected_reports}
  blocked_reason: {blocked_reason}
  last_run: {last_run}
  notes: {notes}
"""


def fixture(*rows: str, schema_version: str = "1") -> str:
    return f"schema_version: {schema_version}\nmethods:\n" + "".join(rows)


def run_validator(path: Path) -> tuple[int, str]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = validate(path)
    return code, output.getvalue()


def write_fixture(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def run() -> int:
    print("=" * 60)
    print("Evidence method-health validator tests")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        valid_path = tmp_path / "valid.yml"
        valid_text = fixture(row_yaml())
        write_fixture(valid_path, valid_text)
        before = valid_path.read_text(encoding="utf-8")
        code, output = run_validator(valid_path)
        after = valid_path.read_text(encoding="utf-8")
        check("valid fixture passes", code == 0, output)
        check("valid fixture prints row count", "1 method rows checked" in output, output)
        check("validator does not mutate fixture file", before == after, output)

        unknown_status_path = tmp_path / "unknown-status.yml"
        write_fixture(unknown_status_path, fixture(row_yaml(status="collector_mystery")))
        code, output = run_validator(unknown_status_path)
        check("unknown status fails", code != 0 and "field status" in output, output)

        missing_identifier_path = tmp_path / "missing-identifier.yml"
        write_fixture(missing_identifier_path, fixture(row_yaml(product_id="''")))
        code, output = run_validator(missing_identifier_path)
        check("missing required identifier fails", code != 0 and "field product_id" in output, output)

        duplicate_path = tmp_path / "duplicate.yml"
        write_fixture(duplicate_path, fixture(row_yaml(), row_yaml()))
        code, output = run_validator(duplicate_path)
        check("duplicate method key fails", code != 0 and "duplicate key" in output, output)

        negative_counter_path = tmp_path / "negative-counter.yml"
        write_fixture(negative_counter_path, fixture(row_yaml(candidates_found="-1")))
        code, output = run_validator(negative_counter_path)
        check("negative counter fails", code != 0 and "field candidates_found" in output, output)

        non_integer_counter_path = tmp_path / "non-integer-counter.yml"
        write_fixture(non_integer_counter_path, fixture(row_yaml(candidates_found="1.5")))
        code, output = run_validator(non_integer_counter_path)
        check("non-integer counter fails", code != 0 and "field candidates_found" in output, output)

        accepted_gt_candidates_path = tmp_path / "accepted-gt-candidates.yml"
        write_fixture(accepted_gt_candidates_path, fixture(row_yaml(candidates_found="1", accepted_candidates="2")))
        code, output = run_validator(accepted_gt_candidates_path)
        check("accepted count greater than candidate count fails", code != 0 and "cannot exceed candidates_found" in output, output)

        telemetry_statuses_path = tmp_path / "telemetry-statuses.yml"
        telemetry_rows = [
            row_yaml(method_id="blocked_method", status="blocked", candidates_found="0", accepted_candidates="0", evidence_rows_added="0", public_counted_reports="0", accepted_reports="0", rejected_reports="0", blocked_reason="rate_limited"),
            row_yaml(method_id="broken_method", status="broken", candidates_found="0", accepted_candidates="0", evidence_rows_added="0", public_counted_reports="0", accepted_reports="0", rejected_reports="0", blocked_reason="http_402_error"),
            row_yaml(method_id="stale_method", status="stale", candidates_found="0", accepted_candidates="0", evidence_rows_added="0", public_counted_reports="0", accepted_reports="0", rejected_reports="0"),
            row_yaml(method_id="low_confidence_method", status="low_confidence", candidates_found="1", accepted_candidates="0", evidence_rows_added="0", public_counted_reports="0", accepted_reports="0", rejected_reports="1"),
            row_yaml(method_id="manual_review_method", status="manual_review_needed", candidates_found="1", accepted_candidates="0", evidence_rows_added="0", public_counted_reports="0", accepted_reports="0", rejected_reports="1"),
        ]
        write_fixture(telemetry_statuses_path, fixture(*telemetry_rows))
        code, output = run_validator(telemetry_statuses_path)
        check("health-only statuses pass as telemetry states", code == 0, output)

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
