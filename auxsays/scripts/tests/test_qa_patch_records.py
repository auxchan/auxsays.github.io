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
            counts = qa.load_counted_evidence_counts([])
            check(
                "only counted+patch-matched rows are counted (3 of 5 raw rows)",
                counts.get(("obs-studio", "32.1.2", "")) == 3,
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


    # =====================================================================================
    # FIELD-AWARE PUBLIC INTERNAL-TERM GATE
    #
    # Production ingestion was blocked by a false positive: GitHub's own changelog entry
    # "Enterprise managed settings in GitHub Copilot for JetBrains" describes configuring
    # OpenTelemetry "including the collector endpoint, protocol, service name, ...". That
    # vendor prose lands verbatim in `release_summary` (rss_feed -> record["summary"] ->
    # write_update_record), and the gate flattened every public field into one blob before
    # substring-matching the bare term "collector", so a generic English word in a vendor
    # release note read as AUXSAYS implementation leakage and failed the whole run.
    #
    # The gate must stay: "collector" in AUXSAYS-AUTHORED public prose is still a defect.
    # Only the proven vendor-derived field may carry it.
    # =====================================================================================
    def findings_for(data):
        """All public_internal_term findings for a record-like dict."""
        return qa.internal_term_findings(data, "rec.md")

    VENDOR = "Improved garbage collector performance and reduced allocation churn."

    # A. the real-world false positive: vendor prose in release_summary must PASS
    check("A. vendor 'collector' prose in release_summary raises no internal-term error",
          findings_for({"release_summary": VENDOR}) == [],
          f"findings={findings_for({'release_summary': VENDOR})}")

    # B. AUXSAYS-authored quick_verdict must still FAIL
    check("B. 'collector' in AUXSAYS-authored quick_verdict is still an error",
          len(findings_for({"quick_verdict": "Collector execution failed for this update."})) == 1,
          str(findings_for({"quick_verdict": "Collector execution failed for this update."})))

    # C. another AUXSAYS-authored field must still FAIL
    for field in ("update_consensus_summary", "record_note", "update_decision_body",
                  "consensus_report", "community_summary", "practical_recommendations",
                  "evidence_source_limitations", "source_freshness_note", "description"):
        check(f"C. 'collector' in AUXSAYS-authored {field} is still an error",
              len(findings_for({field: "The collector produced these rows."})) == 1,
              f"{field}: {findings_for({field: 'The collector produced these rows.'})}")

    # D. a different banned term inside the exempt field must STILL fail -- the exemption is
    #    per-term, never a blanket pass for the field.
    check("D. 'writeback' inside release_summary is still an error",
          len(findings_for({"release_summary": "Vendor notes mention writeback behaviour."})) == 1,
          str(findings_for({"release_summary": "Vendor notes mention writeback behaviour."})))

    # E. other unambiguous internal terms inside the exempt field still fail
    for term in ("candidate rows", "source_weight", "consensus_evidence.yml",
                 "promoted evidence rows", "deterministically accepted"):
        check(f"E. '{term}' inside release_summary is still an error",
              len(findings_for({"release_summary": f"Upstream text mentioning {term} here."})) == 1,
              f"{term}: {findings_for({'release_summary': f'Upstream text mentioning {term} here.'})}")

    # F. diagnostics name BOTH the offending field and the term
    msg = " ".join(str(m) for m in findings_for({"quick_verdict": "collector failed"}))
    check("F. the finding identifies the offending field and the term",
          "quick_verdict" in msg and "collector" in msg, msg)

    # G. the exemption is scoped to ONE field: collector in official_summary still fails,
    #    because rss_feed does not populate it -- write_update_record substitutes
    #    AUXSAYS-authored fallback prose there.
    check("G. 'collector' in official_summary is still an error (AUXSAYS-authored fallback)",
          len(findings_for({"official_summary": "Collector run for this build."})) == 1,
          str(findings_for({"official_summary": "Collector run for this build."})))

    # H. the real production string, end to end, must pass
    REAL = ("Admins can now configure OpenTelemetry for Copilot in JetBrains IDEs, including "
            "the collector endpoint, protocol, service name, resource attributes and headers.")
    check("H. the exact production GitHub changelog string passes in release_summary",
          findings_for({"release_summary": REAL}) == [], str(findings_for({"release_summary": REAL})))
    check("H2. the same string in quick_verdict still fails",
          len(findings_for({"quick_verdict": REAL})) == 1, str(findings_for({"quick_verdict": REAL})))

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
