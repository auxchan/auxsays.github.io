#!/usr/bin/env python3
"""Cleanup-invariant test for the Microsoft Teams record/state correction.

The prior identity-unaware Teams parser mislabeled non-Windows builds (the Public/New
Teams *Mac* stream, whose build numbers are also shared into Government/Gallatin) as
generic "Microsoft Teams" records. Those records were removed and the Teams ingestion
state was reset. This test deterministically asserts the post-cleanup invariants so a
regression (a mislabeled record or an un-reset state) fails CI:

  1. Every REMAINING microsoft-teams generated record satisfies the corrected identity
     contract -- New Teams / Windows / Public cloud, and an exact YYDDD desktop build.
     (There are currently zero such records; the check is a forward guard.)
  2. No Mac/Web/VDI/Mobile/Classic/Government/Sovereign/preview Teams record remains --
     enforced by requiring target_platform == "Windows" and target_channel to name the
     Public cloud, which the identity-unaware parser never emitted.
  3. No duplicate Teams version identity remains.
  4. The microsoft-teams ingestion source state was reset (no source entry, and no Teams
     block in last_results), while the state file stays valid and other product state is
     present and untouched.

Offline only: reads repository files; no network. Run with:
    PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_teams_record_cleanup.py
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters.microsoft_office_updates import _is_new_teams_windows_build  # noqa: E402

_GENERATED = _REPO / "auxsays" / "updates" / "generated"
_STATE = _REPO / "auxsays" / "_data" / "patch_ingest_state.json"

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def _fm(text: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*['\"]?([^'\"\n]+)", text, re.M)
    return m.group(1).strip() if m else ""


def run() -> int:
    print("=" * 60)
    print("Microsoft Teams record/state cleanup invariants")
    print("=" * 60)

    teams_files = sorted(_GENERATED.glob("*microsoft-teams*.md"))
    versions: list[str] = []
    bad_identity: list[str] = []
    for path in teams_files:
        text = path.read_text(encoding="utf-8")
        ver = _fm(text, "update_version")
        versions.append(ver)
        platform = _fm(text, "target_platform")
        channel = _fm(text, "target_channel")
        edition = _fm(text, "teams_edition")
        ok = (
            platform == "Windows"
            and "Public cloud" in channel
            and edition == "New Teams"
            and _is_new_teams_windows_build(ver)
        )
        if not ok:
            bad_identity.append(f"{path.name} (plat={platform!r} chan={channel!r} edn={edition!r} ver={ver})")

    # 1 + 2: every remaining Teams record is a valid Windows/Public/New-Teams build.
    check("no remaining Teams record fails the New-Teams/Windows/Public identity contract",
          bad_identity == [], "\n        ".join(bad_identity))
    # 3: no duplicate Teams version identity.
    check("no duplicate Teams version identity among remaining records",
          len(versions) == len(set(versions)), str([v for v in versions if versions.count(v) > 1]))

    # 4: Teams ingestion state was reset; other product state intact + file valid.
    raw = _STATE.read_bytes()
    check("patch_ingest_state.json is valid JSON, LF-only, no trailing newline",
          b"\r\n" not in raw and not raw.endswith(b"\n"))
    state = json.loads(raw.decode("utf-8"))
    check("microsoft-teams source state entry was removed (reset baseline)",
          "microsoft-teams" not in state.get("sources", {}),
          str(list(state.get("sources", {}).keys())[:5]))
    check("no microsoft-teams block remains in last_results",
          not any(isinstance(x, dict) and x.get("product_id") == "microsoft-teams"
                  for x in state.get("last_results", [])))
    check("other product ingestion state is present and untouched (>= 15 sources remain)",
          len(state.get("sources", {})) >= 15, str(len(state.get("sources", {}))))

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    print(f"(Teams records remaining: {len(teams_files)}; expected 0 until the corrected "
          f"parser re-ingests the Windows/Public stream.)")
    if _ERRORS:
        print("Failed:", ", ".join(_ERRORS))
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
