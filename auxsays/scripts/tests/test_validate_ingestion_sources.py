#!/usr/bin/env python3
"""Tests for ingestion-source config validation of the record/scan window contract.

`validate_ingestion_sources._validate_entry` guards `ingestion.scan_limit` (and the
`ingestion.record_limit` it is checked against) so that a misconfigured candidate
scan window fails CI fail-closed rather than silently broadening network activity:
  - scan_limit must be a positive integer,
  - at least record_limit (the per-run write budget it must cover),
  - at most SEEN_RETENTION (so the seen ledger always covers the active window).
No network or filesystem writes: the validator is pure over an in-memory dict, and
the real config is read-only.
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import validate_ingestion_sources as vis

_CONFIG = _REPO / "auxsays" / "_data" / "patch_ingestion_sources.yml"

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


def base(**ingestion_extra: object) -> dict[str, object]:
    ingestion: dict[str, object] = {
        "adapter": "elgato_help_center",
        "type": "help_center_release_notes",
        "official_url": "https://help.elgato.com/hc/en-us/sections/1-Example-Release-Notes",
    }
    ingestion.update(ingestion_extra)
    return {"company_id": "elgato", "product_id": "elgato-example", "enabled": True, "ingestion": ingestion}


def entry_errors(source: dict[str, object]) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    vis._validate_entry(errors, warnings, source)
    return errors


def scan_errors(source: dict[str, object]) -> list[str]:
    return [e for e in entry_errors(source) if "scan_limit" in e]


def record_errors(source: dict[str, object]) -> list[str]:
    return [e for e in entry_errors(source) if "record_limit" in e]


def run() -> int:
    print("=" * 60)
    print("validate_ingestion_sources scan_limit contract tests")
    print("=" * 60)

    retention = vis.SEEN_RETENTION

    # --- baseline: a clean source produces no errors at all ------------------
    check("baseline source (no scan_limit) has no validation errors", entry_errors(base()) == [], str(entry_errors(base())))

    # --- valid scan_limit values ---------------------------------------------
    check("scan_limit absent is valid (default backfill window applies)", scan_errors(base()) == [])
    check("scan_limit=8 is valid", scan_errors(base(scan_limit=8)) == [], str(scan_errors(base(scan_limit=8))))
    check("scan_limit == record_limit is valid", scan_errors(base(scan_limit=2, record_limit=2)) == [], str(scan_errors(base(scan_limit=2, record_limit=2))))
    check("scan_limit == SEEN_RETENTION upper bound is valid", scan_errors(base(scan_limit=retention)) == [], str(scan_errors(base(scan_limit=retention))))

    # --- invalid scan_limit values must be REJECTED (fail-closed) ------------
    check("scan_limit above SEEN_RETENTION is rejected", scan_errors(base(scan_limit=retention + 1)) != [], "expected an error")
    check("scan_limit zero is rejected", scan_errors(base(scan_limit=0)) != [])
    check("scan_limit negative is rejected", scan_errors(base(scan_limit=-4)) != [])
    check("scan_limit non-integer string is rejected", scan_errors(base(scan_limit="lots")) != [])
    check("scan_limit float is rejected (must be an integer)", scan_errors(base(scan_limit=8.5)) != [])
    check("scan_limit boolean is rejected (bool is not an accepted integer)", scan_errors(base(scan_limit=True)) != [])
    check("scan_limit below record_limit is rejected", scan_errors(base(scan_limit=3, record_limit=6)) != [], "3 < 6 must error")

    # --- record_limit sanity (needed for the scan_limit >= record_limit check) ---
    check("record_limit zero is rejected", record_errors(base(record_limit=0)) != [])
    check("record_limit non-integer is rejected", record_errors(base(record_limit="six")) != [])
    check("record_limit boolean is rejected", record_errors(base(record_limit=True)) != [])
    check("valid record_limit alone produces no error", record_errors(base(record_limit=6)) == [], str(record_errors(base(record_limit=6))))

    # --- integration: the real, shipped config still validates cleanly -------
    check("real patch_ingestion_sources.yml passes full validation (exit 0)", vis.validate(_CONFIG) == 0)

    # --- integration: Adobe Photoshop source is correctly wired --------------
    import importlib
    import yaml
    entries = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    ps = next((e for e in entries if e.get("product_id") == "adobe-photoshop"), None)
    check("adobe-photoshop entry exists", ps is not None)
    if ps is not None:
        ing = ps.get("ingestion", {}) or {}
        check("adobe-photoshop uses the dedicated adobe_photoshop adapter (not the Premiere one)",
              ing.get("adapter") == "adobe_photoshop", str(ing.get("adapter")))
        check("adobe-photoshop stays disabled (activation gated on CI source reachability)",
              ps.get("enabled") is False, str(ps.get("enabled")))
        check("adobe-photoshop declares a bounded record_limit/scan_limit within the seen window",
              isinstance(ing.get("record_limit"), int) and isinstance(ing.get("scan_limit"), int)
              and 0 < ing["record_limit"] <= ing["scan_limit"] <= vis.SEEN_RETENTION,
              str({"record_limit": ing.get("record_limit"), "scan_limit": ing.get("scan_limit")}))
        check("adobe-photoshop official_url targets the official Adobe HelpX desktop page",
              str(ing.get("official_url", "")).startswith("https://helpx.adobe.com/photoshop/"),
              str(ing.get("official_url")))
        # The note is the only place the activation blocker is written down, so it has to name the
        # MECHANISM and not just the conclusion. It previously said the page "times out, zero
        # bytes"; re-measurement from CI showed a fast HTTP 403 from an edge filter, on
        # helpx.adobe.com specifically, while www.adobe.com answered 200 in the same job. Someone
        # acting on "times out" would have gone looking for an egress or timeout problem.
        note = str(ps.get("source_health_note", "")).lower()
        check("adobe-photoshop source_health_note records the CI-unreachable / staged state",
              "not reachable" in note, str(ps.get("source_health_note", ""))[:80])
        check("adobe-photoshop source_health_note names the measured failure mechanism",
              "403" in note and "helpx.adobe.com" in note and "timed out" not in note,
              str(ps.get("source_health_note", ""))[:140])
        check("adobe-photoshop source_health_note says how to re-measure the blocker",
              "probe_photoshop_sources.py" in note,
              str(ps.get("source_health_note", ""))[-120:])
        mod = importlib.import_module("adapters.adobe_photoshop")
        check("adobe_photoshop adapter module imports and exposes fetch()",
              callable(getattr(mod, "fetch", None)))
        check("adobe_photoshop adapter is inert for a non-Photoshop product id",
              mod.fetch({"product_id": "obs-studio", "ingestion": {}}, 3) == [])

    # --- integration: Microsoft Teams source is correctly wired (staged) -----
    teams = next((e for e in entries if e.get("product_id") == "microsoft-teams"), None)
    check("microsoft-teams entry exists", teams is not None)
    if teams is not None:
        ting = teams.get("ingestion", {}) or {}
        check("microsoft-teams uses the shared microsoft_office_updates adapter with the Teams profile",
              ting.get("adapter") == "microsoft_office_updates"
              and ting.get("parser_profile") == "microsoft_teams_version_history",
              str((ting.get("adapter"), ting.get("parser_profile"))))
        check("microsoft-teams is ACTIVE (cleanup prerequisite satisfied; see AUX-018)",
              teams.get("enabled") is True, str(teams.get("enabled")))
        # The live Windows/Public table carries the full history -- 63 builds back to 2023-10-12
        # at activation -- and every one satisfies the target identity, so no identity check would
        # stop an unbounded backfill. Only the declared floor does.
        check("microsoft-teams declares a forward-only record_floor_date",
              isinstance(ting.get("record_floor_date"), str)
              and re.fullmatch(r"\d{4}-\d{2}-\d{2}", ting.get("record_floor_date", "")),
              str(ting.get("record_floor_date")))
        check("microsoft-teams official_url targets the official Learn version-history page",
              str(ting.get("official_url", "")).startswith("https://learn.microsoft.com/en-us/officeupdates/teams-app-versioning"),
              str(ting.get("official_url")))
        note = str(teams.get("source_health_note", "")).lower()
        check("microsoft-teams source_health_note records the identity-scoped state",
              "identity-scoped" in note, str(teams.get("source_health_note", ""))[:80])
        # The blocker this note described is gone. Prose that still says activation is gated on a
        # cleanup that already happened sends the next person to redo destructive work.
        check("microsoft-teams source_health_note no longer claims cleanup is pending",
              "gated on a controlled cleanup" not in note and "forward-only" in note,
              str(teams.get("source_health_note", ""))[:120])

    # --- the floor is REQUIRED for this profile, so a key typo cannot remove the guard -------
    # `_validate_entry` is the real per-source validator `validate()` runs; calling it directly
    # keeps this a test of the shipped rule rather than of a copy of it.
    def _teams_like(**ing):
        base = {"adapter": "microsoft_office_updates",
                "parser_profile": "microsoft_teams_version_history",
                "official_url": "https://learn.microsoft.com/en-us/officeupdates/teams-app-versioning",
                "type": "html_release_notes"}
        base.update(ing)
        errs: list = []
        vis._validate_entry(errs, [], {
            "company_id": "microsoft", "product_id": "microsoft-teams", "company": "Microsoft",
            "software": "Microsoft Teams", "public_category": "Workplace Critical",
            "enabled": True, "ingestion": base})
        return [e for e in errs if "record_floor_date" in e]

    check("the Teams profile REQUIRES record_floor_date (absent key rejected)",
          bool(_teams_like()), str(_teams_like())[:100])
    check("a typo in the floor KEY is rejected, not silently ignored",
          bool(_teams_like(record_floor_data="2026-08-01")),
          str(_teams_like(record_floor_data="2026-08-01"))[:100])
    check("a malformed floor VALUE is rejected",
          bool(_teams_like(record_floor_date="2026-8-01")),
          str(_teams_like(record_floor_date="2026-8-01"))[:100])
    check("the correctly spelled, well-formed floor validates",
          not _teams_like(record_floor_date="2026-08-01"),
          str(_teams_like(record_floor_date="2026-08-01"))[:100])

    # --- P. the enabled source is actually selected by the REAL ingestion registry ----------
    # Flipping `enabled` in YAML is only half of activation; `should_run` is what the scheduled
    # lane consults, and it is the function that decides whether Teams is ever fetched.
    import argparse                                                # noqa: PLC0415 - test-only
    import patch_ingest                                            # noqa: PLC0415 - test-only
    scheduled = argparse.Namespace(source=[], all=False)
    check("the scheduled lane selects microsoft-teams now that it is enabled",
          teams is not None and patch_ingest.should_run(teams, scheduled) is True)
    disabled = next((e for e in entries if e.get("enabled") is False), None)
    check("...and still skips a source that is disabled",
          disabled is not None and patch_ingest.should_run(disabled, scheduled) is False,
          str(disabled and disabled.get("product_id")))

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
