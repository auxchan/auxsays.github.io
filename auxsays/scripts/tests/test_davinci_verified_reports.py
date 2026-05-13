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

from patch_collectors.base import PatchRecord
from patch_collectors.davinci import row_from_candidate

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
