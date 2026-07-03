#!/usr/bin/env python3
"""Focused tests for qa_patch_records.scan_evidence_count_alignment.

Covers the credibility gate that a generated record's report count must equal its
counted structured-evidence rows, and that the mismatch is now a BLOCKING error
(not a warning). Uses temp fixtures only; never reads or writes real repo data
(consensus_evidence.yml, generated records, qa_status.json).
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import qa_patch_records as qa

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

CODE = "generated_report_count_mismatch"


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


def record_md(product_id: str, version: str, report_count: int, evidence_state: str) -> str:
    return (
        "---\n"
        f"product_id: {product_id}\n"
        f"update_version: '{version}'\n"
        f"update_report_count: {report_count}\n"
        f"evidence_state: {evidence_state}\n"
        "---\n\n"
        "Body copy for the test fixture.\n"
    )


def evidence_yaml() -> str:
    # 3 truly counted rows + 1 counted:false + 1 patch_version_matched:false
    # => load_counted_evidence_counts must total 3 for (obs-studio, 32.1.2).
    counted = (
        "  - product_id: obs-studio\n"
        "    update_version: '32.1.2'\n"
        "    counted: true\n"
        "    patch_version_matched: true\n"
    )
    uncounted = (
        "  - product_id: obs-studio\n"
        "    update_version: '32.1.2'\n"
        "    counted: false\n"
        "    patch_version_matched: true\n"
    )
    unmatched = (
        "  - product_id: obs-studio\n"
        "    update_version: '32.1.2'\n"
        "    counted: true\n"
        "    patch_version_matched: false\n"
    )
    return "schema_version: 1\nevidence:\n" + counted * 3 + uncounted + unmatched


def codes(findings: list[dict[str, str]]) -> list[str]:
    return [f["code"] for f in findings]


def run() -> int:
    print("=" * 60)
    print("qa_patch_records evidence-count-alignment blocking tests")
    print("=" * 60)

    original_root = qa.ROOT
    original_evidence_path = qa.EVIDENCE_PATH

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        evidence_path = tmp_path / "consensus_evidence.yml"
        evidence_path.write_text(evidence_yaml(), encoding="utf-8")

        mismatch_file = tmp_path / "mismatch.md"
        mismatch_file.write_text(record_md("obs-studio", "32.1.2", 5, "pilot_sample"), encoding="utf-8")

        matched_file = tmp_path / "matched.md"
        matched_file.write_text(record_md("obs-studio", "32.1.2", 3, "pilot_sample"), encoding="utf-8")

        official_file = tmp_path / "official.md"
        official_file.write_text(record_md("figma", "1.2.3", 0, "official_only"), encoding="utf-8")

        # Point the module at the temp fixtures. qa.ROOT lets add() resolve
        # relative_to() for temp record paths; qa.EVIDENCE_PATH feeds the counter.
        qa.ROOT = tmp_path
        qa.EVIDENCE_PATH = evidence_path
        try:
            # Counted-row filtering: only counted+patch-matched rows count (3 of 5 raw rows).
            counts = qa.load_counted_evidence_counts()
            check(
                "only counted+patch-matched rows are counted (3 of 5 raw rows)",
                counts.get(("obs-studio", "32.1.2")) == 3,
                f"counts={counts}",
            )

            # 1. Mismatched record -> BLOCKING error, not a warning.
            errors, warnings = qa.scan_evidence_count_alignment([mismatch_file])
            check("mismatched record is reported as a blocking error", CODE in codes(errors), f"errors={errors}")
            check("mismatched record is NOT reported as a warning", CODE not in codes(warnings), f"warnings={warnings}")

            # 2. Matched record -> no finding at all.
            errors, warnings = qa.scan_evidence_count_alignment([matched_file])
            check("matched record produces no error", errors == [], f"errors={errors}")
            check("matched record produces no warning", warnings == [], f"warnings={warnings}")

            # 3. Zero-count official_only record (no evidence key) -> no false-fail.
            errors, warnings = qa.scan_evidence_count_alignment([official_file])
            check("zero-count official_only produces no error", errors == [], f"errors={errors}")
            check("zero-count official_only produces no warning", warnings == [], f"warnings={warnings}")

            # 4. Aggregate scan -> exactly one blocking error, no warnings for this code.
            errors, warnings = qa.scan_evidence_count_alignment([mismatch_file, matched_file, official_file])
            check(
                "aggregate scan yields exactly one blocking mismatch error",
                [c for c in codes(errors) if c == CODE] == [CODE],
                f"errors={errors}",
            )
            check(
                "aggregate scan yields no mismatch warning",
                CODE not in codes(warnings),
                f"warnings={warnings}",
            )
        finally:
            qa.ROOT = original_root
            qa.EVIDENCE_PATH = original_evidence_path

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
