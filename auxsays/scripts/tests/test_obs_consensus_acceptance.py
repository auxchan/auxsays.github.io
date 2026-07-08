#!/usr/bin/env python3
"""Tests for the hardened OBS consensus acceptance rules (collect_obs_reports).

Offline only: synthetic GitHub-issue dicts are fed to the pure acceptance functions
(evaluate_issue / describes_concrete_issue / release_date_gate / match_basis /
likely_developer_only) and to write_evidence with a temp evidence path. No network,
no writes to the live consensus_evidence.yml.

Covers: exact-version matching, developer-only exclusion, the new generic-complaint
filter, the new release-date gate (before/on/after/undated), official-notes/announcement
rejection, and duplicate exclusion.
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import collect_obs_reports as obs

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


def issue(title="", body="", created_at=None, labels=None, number=1):
    return {
        "title": title,
        "body": body,
        "created_at": created_at,
        "labels": [{"name": n} for n in (labels or [])],
        "number": number,
        "html_url": f"https://github.com/obsproject/obs-studio/issues/{number}",
        "url": f"https://api.github.com/repos/obsproject/obs-studio/issues/{number}",
    }


VER = "32.1.1"
RELEASE = obs.parse_date("2026-04-02")  # patch release date


def run() -> int:
    print("=" * 60)
    print("OBS consensus acceptance rule tests")
    print("=" * 60)

    # --- exact-version matching (preserved) ---------------------------------
    check("exact version in title accepted as basis", obs.match_basis(issue(title="OBS 32.1.1 crash"), VER) == "title")
    check("exact version in body accepted as basis", obs.match_basis(issue(body="seen on 32.1.1 here"), VER) == "body")
    check("adjacent-digit version does NOT match (32.1.10 != 32.1.1)", obs.match_basis(issue(title="OBS 32.1.10 crash"), VER) is None)

    # --- developer-only exclusion (preserved) -------------------------------
    dev = issue(title="cmake build failure configuring 32.1.1", created_at="2026-04-05T00:00:00Z")
    check("developer/build-only issue rejected", obs.evaluate_issue(dev, VER, RELEASE) == (None, "developer_or_build_only"))

    # --- parse_date / release_date_gate primitives --------------------------
    check("parse_date reads ISO datetime", obs.parse_date("2026-04-02T00:00:00Z") == RELEASE)
    check("parse_date reads plain date", obs.parse_date("2026-04-02") == RELEASE)
    check("parse_date returns None for empty/garbage", obs.parse_date("") is None and obs.parse_date("n/a") is None)
    check("release_date_gate inactive when release date unknown", obs.release_date_gate(issue(created_at="2020-01-01T00:00:00Z"), None) is None)

    # 1. dated BEFORE release -> rejected
    before = issue(title="OBS 32.1.1 crashes on startup", created_at="2026-03-30T10:00:00Z")
    check("1. concrete report dated before release -> before_release_date", obs.evaluate_issue(before, VER, RELEASE) == (None, "before_release_date"))

    # 2. dated ON release date -> accepted
    on = issue(title="OBS 32.1.1 crashes on startup", created_at="2026-04-02T08:00:00Z")
    check("2. concrete report dated on release date -> accepted", obs.evaluate_issue(on, VER, RELEASE) == ("title", None))

    # 3. dated AFTER release date -> accepted
    after = issue(title="OBS 32.1.1 crashes on startup", created_at="2026-04-10T08:00:00Z")
    check("3. concrete report dated after release date -> accepted", obs.evaluate_issue(after, VER, RELEASE) == ("title", None))

    # 4. undated behavior is deterministic
    undated = issue(title="OBS 32.1.1 crashes on startup", created_at=None)
    check("4a. undated report rejected when release date is known", obs.evaluate_issue(undated, VER, RELEASE) == (None, "missing_source_date"))
    check("4b. undated report accepted when release date is unknown (gate inactive)", obs.evaluate_issue(undated, VER, None) == ("title", None))

    # 5. generic complaints -> rejected
    for t in ("Is OBS 32.1.1 safe to update?", "Anyone having issues with 32.1.1?", "Should I update to 32.1.1?", "OBS 32.1.1 sucks"):
        i = issue(title=t, created_at="2026-04-05T00:00:00Z")
        check(f"5. generic complaint rejected: {t!r}", obs.evaluate_issue(i, VER, RELEASE) == (None, "generic_or_no_concrete_issue"))

    # 6. concrete crash / install failure / regression -> accepted
    concrete_cases = {
        "crash": issue(title="OBS 32.1.1 crashes when I start recording", created_at="2026-04-05T00:00:00Z"),
        "install failure": issue(title="32.1.1 fails to install on Windows", created_at="2026-04-05T00:00:00Z"),
        "capture regression": issue(title="screen capture regression in 32.1.1", created_at="2026-04-05T00:00:00Z"),
        "audio no-sound": issue(title="No audio after updating to 32.1.1", created_at="2026-04-05T00:00:00Z"),
    }
    for name, i in concrete_cases.items():
        basis, reason = obs.evaluate_issue(i, VER, RELEASE)
        check(f"6. concrete {name} accepted", reason is None and basis == "title", f"got {(basis, reason)}")

    # 7. official/announcement/changelog text -> rejected (no concrete issue)
    ann = issue(title="OBS 32.1.1 released — changelog and download links", body="Release notes: new features and improvements.", created_at="2026-04-05T00:00:00Z")
    check("7. release announcement / changelog rejected", obs.evaluate_issue(ann, VER, RELEASE) == (None, "generic_or_no_concrete_issue"))

    # describes_concrete_issue direct
    check("describes_concrete_issue True for crash", obs.describes_concrete_issue(issue(title="crash on 32.1.1")) is True)
    check("describes_concrete_issue False for generic question", obs.describes_concrete_issue(issue(title="is 32.1.1 any good?")) is False)

    # 8. duplicate exclusion via write_evidence (temp evidence file; live file untouched)
    orig_path = obs.EVIDENCE_PATH
    with tempfile.TemporaryDirectory() as d:
        obs.EVIDENCE_PATH = Path(d) / "evidence.yml"
        try:
            row = obs.evidence_row(on, VER, "title", "2026-04-05T00:00:00Z")
            added1, total1, _ = obs.write_evidence([row])
            added2, total2, _ = obs.write_evidence([row])  # same id + url
            check("8. first write adds the row", added1 == 1 and total1 == 1, f"added1={added1} total1={total1}")
            check("8. duplicate write is excluded (id/url dedup)", added2 == 0 and total2 == 1, f"added2={added2} total2={total2}")
        finally:
            obs.EVIDENCE_PATH = orig_path
    check("live EVIDENCE_PATH restored after dedup test", obs.EVIDENCE_PATH == orig_path)

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
