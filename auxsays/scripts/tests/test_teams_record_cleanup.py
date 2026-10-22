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
  4. Activation stays FORWARD-ONLY: no generated Teams record predates the declared
     ingestion.record_floor_date, and nothing the Teams lane has marked seen is outside the
     Windows desktop build shape. The state file stays valid and other product state is
     present and untouched.

     (Checks 4 previously asserted the RESET baseline -- no microsoft-teams state entry at
     all. Activation ends that baseline by design: the first production run creates the entry.
     What must hold forever is the identity contract and the floor, so those are asserted
     instead. Asserting "the entry is absent" after activation would have gone red on the
     first successful ingest and invited someone to delete real state to make it green.)

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

    # Identity is the record's DECLARED product_id, never its filename. A generated slug falls back
    # to the vendor-authored TITLE (write_update_record.record_slug), so any other product whose
    # title merely mentions Microsoft Teams lands in a "*microsoft-teams*.md" glob. That is not
    # hypothetical: 2026-08-21-github-copilot-shared-agentic-work-with-github-copilot-in-microsoft-
    # teams.md carries `product_id: github`, and globbing made this suite red from 2026-08-22 by
    # holding a GitHub record to the Teams identity contract. Same family as asserting records[0].
    teams_files = sorted(
        path for path in _GENERATED.glob("*.md")
        if _fm(path.read_text(encoding="utf-8"), "product_id") == "microsoft-teams"
    )
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
    # FORWARD-ONLY. The official Windows/Public table carries the full history (63 builds back
    # to 2023-10-12 at activation), and every one of them satisfies the identity contract above
    # -- so the identity checks cannot catch a historical flood. Only the declared floor can.
    import yaml                                                    # noqa: PLC0415 - test-only
    cfg = yaml.safe_load((_REPO / "auxsays" / "_data" / "patch_ingestion_sources.yml")
                         .read_text(encoding="utf-8"))
    teams_cfg = next((e for e in cfg if e.get("product_id") == "microsoft-teams"), {})
    floor = str((teams_cfg.get("ingestion", {}) or {}).get("record_floor_date") or "")
    check("the Teams lane declares a forward-only record_floor_date",
          bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", floor)), repr(floor))
    early = []
    for path in teams_files:
        published = _fm(path.read_text(encoding="utf-8"), "update_published_at")[:10]
        if floor and published and published < floor:
            early.append(f"{path.name}: {published} < {floor}")
    check("no generated Teams record predates the activation floor",
          not early, "; ".join(early[:3]))

    # The seen ledger is what stops re-ingestion, so a malformed identity in it would quietly
    # re-open the door. Every Teams id it holds must still be a Windows desktop build.
    teams_state = (state.get("sources", {}) or {}).get("microsoft-teams", {}) or {}
    seen_ids = [str(x) for x in (teams_state.get("seen") or [])]
    odd = [i for i in seen_ids
           if len(i.split(":")) < 3 or not re.fullmatch(r"\d{5}\.\d+\.\d+\.\d+", i.split(":")[2])]
    check("every identity the Teams lane has marked seen is a Windows desktop build",
          not odd, "; ".join(odd[:3]) or f"{len(seen_ids)} seen id(s)")
    # THE DICT -> DISK BOUNDARY. Everything above reads records that EXIST. With zero Teams
    # records the identity contract above is vacuously green, which is exactly how the missing
    # `teams_edition` survived: the adapter emitted it, `build_front_matter` dropped it because the
    # field was in none of the OPTIONAL_STRUCTURED_FIELDS tuples, and no check compared the two.
    # This runs a Teams-shaped adapter record through the real writer and asserts the identity
    # survives serialisation, so it holds whether or not any record has been ingested yet.
    from lib import write_update_record as wur                     # noqa: PLC0415 - test-only
    written = wur.build_front_matter({
        "product_id": "microsoft-teams", "company_id": "microsoft", "company": "Microsoft",
        "software": "Microsoft Teams", "version": "26246.1604.5133.838",
        "published_at": "2026-09-24T00:00:00Z",
        "source_url": "https://learn.microsoft.com/en-us/officeupdates/teams-app-versioning",
        "body": "Official Microsoft Teams release.",
        "target_platform": "Windows", "target_channel": "Public cloud (Production)",
        "teams_edition": "New Teams",
    })
    missing = [f for f in ("target_platform", "target_channel", "teams_edition")
               if not str(written.get(f) or "").strip()]
    check("the writer carries the full Teams identity onto the record it serialises",
          not missing, f"dropped by build_front_matter: {missing}")
    check("an official Teams record is written with zero community reports",
          int(written.get("update_report_count") or 0) == 0,
          str(written.get("update_report_count")))

    check("other product ingestion state is present and untouched (>= 15 sources remain)",
          len(state.get("sources", {})) >= 15, str(len(state.get("sources", {}))))

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    print(f"(Teams records: {len(teams_files)}; floor {floor}; "
          f"{len(seen_ids)} identity(ies) marked seen.)")
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
