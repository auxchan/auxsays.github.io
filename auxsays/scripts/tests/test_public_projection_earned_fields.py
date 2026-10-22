#!/usr/bin/env python3
"""A published evidence field may only assert what its row actually establishes.

`apply_consensus_to_records` projected every accepted row into the public `accepted_report_sources`
list and the `evidence_samples` list, and stamped two fields as CONSTANTS on every entry:
`"patch_version_matched": True` and, on samples, `"counted": True`. Every source a reader saw
therefore claimed a confirmed patch match whether or not one was established.

That mattered more than it looks. `_filter_rows` drops unmatched rows (gate 12) and uncounted rows
(gate 13) only when NOT in candidate mode, so in candidate mode a row the evidence itself marked
unmatched could reach the projection and be published as matched. It also made any check that
trusted the projection unfalsifiable -- which is why the live-consensus gate refuses to read it.

Both fields are now derived from the row. In normal mode the population reaching the projection is
already filtered to matched, counted rows, so published bytes do not change; Part B pins that.

Offline: no network, no repo writes.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_consensus_to_records as ac                       # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


PID, VER = "obs-studio", "32.1.2"


def row(**overrides) -> dict:
    base = {
        "id": "r1", "product_id": PID, "update_version": VER, "source_type": "github_issue",
        "source_name": "obsproject/obs-studio",
        "source_url": "https://github.com/obsproject/obs-studio/issues/13000",
        "report_title": "crash on launch", "matched_version": VER,
        "patch_version_matched": True, "counted": True, "severity": "high",
        "issue_theme": "crash", "workflow_area": "application stability",
    }
    base.update(overrides)
    return base


def run_suite() -> int:
    print("=" * 92)
    print("PART A  the published fields are earned from the row, not stamped")
    print("=" * 92)

    item = ac._public_source_item(PID, VER, row())
    check("Part A: a matched row is published as matched",
          item["patch_version_matched"] is True)
    unmatched = ac._public_source_item(PID, VER, row(patch_version_matched=False))
    check("Part A: an UNMATCHED row is published as unmatched, not stamped True",
          unmatched["patch_version_matched"] is False, str(unmatched["patch_version_matched"]))
    missing = ac._public_source_item(PID, VER, row(patch_version_matched=None))
    check("Part A: a row with no match field is not published as matched",
          missing["patch_version_matched"] is False)
    check("Part A: the source builder carries no hardcoded True for the match field",
          '"patch_version_matched": True' not in
          (SCRIPTS / "apply_consensus_to_records.py").read_text(encoding="utf-8"))

    src = (SCRIPTS / "apply_consensus_to_records.py").read_text(encoding="utf-8")
    samples_block = src.split("for row in _representative_rows(pid, rows, limit=5):", 1)[1]
    samples_block = samples_block.split("})", 1)[0]
    check("Part A: the samples builder derives counted from the row",
          '"counted": row.get("counted") is not False' in samples_block)
    check("Part A: and derives patch_version_matched from the row",
          '"patch_version_matched": row.get("patch_version_matched") is True' in samples_block)

    print()
    print("=" * 92)
    print("PART B  normal mode publishes exactly what it did before")
    print("=" * 92)

    # In normal mode gates 12 and 13 drop unmatched and uncounted rows before projection, so every
    # row that reaches the builders is matched and counted -- the derived values are True, which is
    # what the constant said. The change is therefore invisible on today's pages.
    rows = [row(id="a"), row(id="b", patch_version_matched=False),
            row(id="c", counted=False), row(id="d", source_url="https://github.com/x/y/issues/2")]
    kept, _excluded = ac._filter_rows(rows, product_id=PID, version=VER, is_candidate_mode=False)
    kept_ids = {r["id"] for r in kept}
    check("Part B: normal mode drops the unmatched row before projection",
          "b" not in kept_ids, str(sorted(kept_ids)))
    check("Part B: normal mode drops the uncounted row before projection",
          "c" not in kept_ids, str(sorted(kept_ids)))
    check("Part B: so every projected row in normal mode is published as matched",
          all(ac._public_source_item(PID, VER, r)["patch_version_matched"] is True for r in kept))

    print()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
