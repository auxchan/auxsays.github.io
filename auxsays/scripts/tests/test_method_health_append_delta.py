#!/usr/bin/env python3
"""`evidence_rows_added` means rows PERSISTED, not candidates accepted.

THE DEFECT. `method_health_row` defaulted `evidence_rows_added` to `accepted_reports`, and no
collector ever passed the argument. The field was therefore a second name for `accepted_candidates`
-- literally so: in all 1484 committed rows the two were equal, and `duplicate_existing_evidence`,
the schema field that exists to carry the remainder, was zero in every one of them.

That is not a cosmetic mislabel, because a collector re-finds the same threads every run and
re-accepts them (a URL already stored for THIS patch passes the claims map, stays counted, and lands
in `accepted`); `append_evidence_rows` then refuses each one as a duplicate. So a run could accept
80 rows, store 0, and publish "80 added" on the public methodology table. Measured over the git
history of that table: 336 claimed against 48 actually stored, with 137 of 159 non-zero rows
overstating.

THE CONTRACT THIS PINS:
    candidates_found            what discovery returned
    accepted_candidates         what the authority accepted
    evidence_rows_added         what the append actually stored, this run
    duplicate_existing_evidence what the append refused because the store already held it
Four separate numbers. None of them is allowed to stand in for another.

Offline and deterministic: every case runs against a temporary evidence file. The repository's own
data files are read only to assert the shipped shape, never written.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_method_health_append_delta.py
"""
from __future__ import annotations

import re
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

from patch_collectors import base  # noqa: E402

NEWLINE = chr(10)
SRC = "microsoft_learn_qna"
BUILD_AWARE_PID = "microsoft-windows-11"
PLAIN_PID = "obs-studio"

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
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


def row(i: int, *, pid: str = BUILD_AWARE_PID, build: str = "26200.1000",
        source_type: str = SRC) -> dict:
    return {"id": f"row-{i}", "product_id": pid, "update_version": "25H2",
            "target_build": build, "source_type": source_type,
            "source_url": f"https://example.invalid/{i}", "counted": True}


def health(accepted: int, *, pid: str = BUILD_AWARE_PID, build: str = "26200.1000",
           source_type: str = SRC, method_id: str = "m1") -> list[dict]:
    return [base.method_health_row(
        product_id=pid, update_version="25H2", target_build=build, method_id=method_id,
        source_type=source_type, status="success", candidates_found=accepted,
        accepted_reports=accepted, rejected_reports=0, blocked_reason="",
        last_run="2026-01-01T00:00:00Z", notes="fixture")]


def scenario(prestore: list[dict], submit: list[dict]) -> tuple[dict, int, int]:
    """Returns (finalized health row, real append delta, corpus size)."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.write_evidence_file([], path)
        if prestore:
            base.append_evidence_rows(prestore, path)
        rows = health(len(submit))
        persisted: list[dict] = []
        held: list[dict] = []
        added, _total, _all = base.append_evidence_rows(
            submit, path, out_added=persisted, out_already_held=held)
        base.finalize_method_health_delta(rows, persisted, held)
        return rows[0], added, len(base.load_evidence(path))


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("evidence_rows_added counts rows persisted, not candidates accepted")
    print("=" * 78)

    ten = [row(i) for i in range(10)]

    # ---------------- the five mandated cases ----------------
    print(NEWLINE + "[1] 10 accepted, 10 genuinely new")
    r, added, corpus = scenario([], ten)
    check("1 the append stored all ten", added == 10 and corpus == 10, f"{added}/{corpus}")
    check("1 telemetry says ten", r["evidence_rows_added"] == 10, str(r["evidence_rows_added"]))
    check("1 no duplicates are claimed", r["duplicate_existing_evidence"] == 0)

    print(NEWLINE + "[2] 10 accepted, all ten already stored")
    r, added, corpus = scenario(ten, ten)
    check("2 the append stored nothing", added == 0 and corpus == 10, f"{added}/{corpus}")
    check("2 telemetry says ZERO, not ten", r["evidence_rows_added"] == 0,
          f"{r['evidence_rows_added']} -- the defect: accepted echoed as added")
    check("2 the ten refusals are reported as duplicates",
          r["duplicate_existing_evidence"] == 10, str(r["duplicate_existing_evidence"]))
    check("2 accepted_candidates is untouched", r["accepted_candidates"] == 10)

    print(NEWLINE + "[3] 10 accepted, 6 duplicates, 4 new")
    r, added, corpus = scenario(ten[:6], ten)
    check("3 the append stored four", added == 4 and corpus == 10, f"{added}/{corpus}")
    check("3 telemetry says four", r["evidence_rows_added"] == 4, str(r["evidence_rows_added"]))
    check("3 six are reported as duplicates", r["duplicate_existing_evidence"] == 6)
    check("3 added + duplicates == accepted",
          r["evidence_rows_added"] + r["duplicate_existing_evidence"] == r["accepted_candidates"])

    print(NEWLINE + "[4] the method accepted nothing")
    r, added, corpus = scenario([], [])
    check("4 nothing stored, nothing claimed",
          added == 0 and r["evidence_rows_added"] == 0 and r["duplicate_existing_evidence"] == 0)

    print(NEWLINE + "[5] the write is refused mid-batch")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.write_evidence_file([], path)
        rows = health(3)
        persisted: list[dict] = []
        refused = False
        try:
            # A counted row with no build for a build-aware product: `require_build` fails closed.
            base.append_evidence_rows([row(1), row(2), dict(row(3), target_build="")],
                                      path, out_added=persisted)
        except Exception:  # noqa: BLE001 - the identity gate, whatever it raises
            refused = True
        base.finalize_method_health_delta(rows, persisted)
        stored = base.load_evidence(path)
        check("5 the batch was refused", refused)
        check("5 nothing reached the store", not stored, f"{len(stored)} rows")
        check("5 telemetry claims no growth", rows[0]["evidence_rows_added"] == 0,
              str(rows[0]["evidence_rows_added"]))

    # ---------------- several methods, ONE source family ----------------
    # The production shape in 173 of the committed groups, and the case the first version of
    # `finalize_method_health_delta` got wrong: it handed the whole family delta to the FIRST row
    # with that key. On the real Premiere method order -- `adobe_community_search` first and usually
    # empty, `brave_search_api` later and productive -- that published `accepted=0, stored=3` for a
    # method that found nothing and `stored=0, already held=3` for the one that had just stored
    # them. `stored > accepted` is refused by validate_evidence_method_health, which runs
    # --validate-before-commit in BOTH write lanes, so the whole run's writeback would have been
    # rejected -- every product, every file, on every retry.
    print(NEWLINE + "[5b] several methods share one source_type")
    PREMIERE, ADOBE_SRC = "adobe-premiere-pro", "adobe_community_bug_report"

    def adobe_row(i: int) -> dict:
        return {"id": f"a{i}", "product_id": PREMIERE, "update_version": "26.2",
                "source_type": ADOBE_SRC, "counted": True,
                "source_url": f"https://community.example.invalid/{i}"}

    def adobe_health(method_id: str, accepted: int) -> dict:
        return base.method_health_row(
            product_id=PREMIERE, update_version="26.2", method_id=method_id,
            source_type=ADOBE_SRC, status="success" if accepted else "no_results",
            candidates_found=accepted, accepted_reports=accepted, rejected_reports=0,
            blocked_reason="", last_run="2026-01-01T00:00:00Z", notes="fixture")

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.write_evidence_file([], path)
        family = [adobe_health("adobe_community_search", 0),
                  adobe_health("adobe_community_bug_tab_index", 0),
                  adobe_health("brave_search_api", 3)]
        persisted, held = [], []
        base.append_evidence_rows([adobe_row(1), adobe_row(2), adobe_row(3)], path,
                                  out_added=persisted, out_already_held=held)
        base.finalize_method_health_delta(family, persisted, held)
        impossible = [r for r in family
                      if int(r["evidence_rows_added"]) > int(r["accepted_candidates"])]
        check("5b no row claims it stored more than it accepted", not impossible,
              "; ".join(f"{r['method_id']} {r['evidence_rows_added']}>{r['accepted_candidates']}"
                        for r in impossible))
        check("5b the method that accepted them is credited with them",
              family[2]["evidence_rows_added"] == 3, str(family[2]["evidence_rows_added"]))
        check("5b a method that accepted nothing is credited with nothing",
              family[0]["evidence_rows_added"] == 0 and family[1]["evidence_rows_added"] == 0,
              f"{family[0]['evidence_rows_added']}/{family[1]['evidence_rows_added']}")
        check("5b the family total is still exact",
              sum(int(r["evidence_rows_added"]) for r in family) == 3)
        check("5b the storer does not also report them as already held",
              family[2]["duplicate_existing_evidence"] == 0,
              str(family[2]["duplicate_existing_evidence"]))
        check("5b the rows validate (added <= accepted is a production commit gate)",
              all(int(r["evidence_rows_added"]) <= int(r["accepted_candidates"]) for r in family))

    # ---------------- duplicates are measured, not derived ----------------
    print(NEWLINE + "[5c] `already held` means the STORE held it, not anything else")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.write_evidence_file([], path)
        rows = health(3)
        persisted, held = [], []
        try:
            base.append_evidence_rows([row(1), row(2), dict(row(3), target_build="")], path,
                                      out_added=persisted, out_already_held=held)
        except Exception:  # noqa: BLE001
            pass
        base.finalize_method_health_delta(rows, persisted, held)
        check("5c a batch the build gate refused holds nothing",
              rows[0]["duplicate_existing_evidence"] == 0,
              f"{rows[0]['duplicate_existing_evidence']} -- the store was empty")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.write_evidence_file([], path)
        rows = health(2)
        twin = dict(row(9))
        twin["id"] = "row-9b"
        persisted, held = [], []
        base.append_evidence_rows([row(9), twin], path, out_added=persisted, out_already_held=held)
        base.finalize_method_health_delta(rows, persisted, held)
        check("5c a duplicate created inside this run is not archive depth",
              rows[0]["evidence_rows_added"] == 1 and rows[0]["duplicate_existing_evidence"] == 0,
              f"stored={rows[0]['evidence_rows_added']} held={rows[0]['duplicate_existing_evidence']}")
    r, added, corpus = scenario(ten, ten)
    check("5c a genuine re-run reports the store's own rows as held",
          r["duplicate_existing_evidence"] == 10 and r["evidence_rows_added"] == 0,
          f"stored={r['evidence_rows_added']} held={r['duplicate_existing_evidence']}")

    # ---------------- attribution ----------------
    print(NEWLINE + "[6] the delta is attributed to the source family that stored it")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.write_evidence_file([], path)
        learn = [row(i) for i in range(3)]
        tc = [row(100 + i, source_type="microsoft_tech_community") for i in range(2)]
        rows = health(3) + health(2, source_type="microsoft_tech_community", method_id="m2")
        persisted: list[dict] = []
        held: list[dict] = []
        base.append_evidence_rows(learn + tc, path, out_added=persisted, out_already_held=held)
        base.finalize_method_health_delta(rows, persisted, held)
        check("6 each family gets its own count",
              rows[0]["evidence_rows_added"] == 3 and rows[1]["evidence_rows_added"] == 2,
              f"{rows[0]['evidence_rows_added']}/{rows[1]['evidence_rows_added']}")
        check("6 a family's rows are not credited to the other family",
              rows[0]["source_type"] == SRC and rows[1]["source_type"] == "microsoft_tech_community")

    print(NEWLINE + "[7] another patch's rows are never credited to this one")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.write_evidence_file([], path)
        mine = [row(i) for i in range(2)]
        sibling = [row(200 + i, build="26200.2000") for i in range(5)]
        rows = health(2)
        persisted: list[dict] = []
        held: list[dict] = []
        base.append_evidence_rows(mine + sibling, path, out_added=persisted, out_already_held=held)
        base.finalize_method_health_delta(rows, persisted, held)
        check("7 only this patch's two rows are counted", rows[0]["evidence_rows_added"] == 2,
              str(rows[0]["evidence_rows_added"]))

    # ---------------- the default, and the store it appends to ----------------
    print(NEWLINE + "[8] the default no longer echoes the accepted count")
    plain = base.method_health_row(
        product_id=PLAIN_PID, update_version="32.1.2", method_id="github_issues",
        source_type="github_issue", status="success", candidates_found=7, accepted_reports=7,
        rejected_reports=0, blocked_reason="", last_run="2026-01-01T00:00:00Z", notes="fixture")
    check("8 an un-passed evidence_rows_added is 0, not the accepted count",
          plain["evidence_rows_added"] == 0, str(plain["evidence_rows_added"]))
    check("8 accepted_candidates still defaults to accepted_reports",
          plain["accepted_candidates"] == 7)
    check("8 an explicit value is still honoured",
          base.method_health_row(
              product_id=PLAIN_PID, update_version="32.1.2", method_id="m", source_type="s",
              status="success", candidates_found=7, accepted_reports=7, rejected_reports=0,
              evidence_rows_added=3, blocked_reason="", last_run="2026-01-01T00:00:00Z",
              notes="f")["evidence_rows_added"] == 3)

    print(NEWLINE + "[9] appending to a store that is present but empty")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.write_evidence_file([], path)
        base.append_evidence_rows([row(1)], path)
        reloaded = base.load_evidence(path)
        check("9 the store is still readable after its first append", len(reloaded) == 1,
              "the byte-append concatenated a bare sequence onto a mapping")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        check("9 it is still a mapping with an evidence list",
              isinstance(payload, dict) and isinstance(payload.get("evidence"), list))

    # ---------------- every collector finalizes ----------------
    print(NEWLINE + "[10] every collector that appends also finalizes")
    collectors = {
        "microsoft_windows.py": True, "microsoft_powerpoint.py": True, "davinci.py": True,
        "adobe_premiere.py": True, "adobe_acrobat_community.py": True,
    }
    for name in collectors:
        src = (_REPO / "auxsays" / "scripts" / "patch_collectors" / name).read_text(encoding="utf-8")
        appends = src.index("append_evidence_rows(")
        check(f"10 {name} finalizes after its append",
              "finalize_method_health_delta(" in src
              and src.index("finalize_method_health_delta(", appends) > appends,
              "the health row would keep the un-measured default")
        check(f"10 {name} captures the persisted rows",
              "out_added=" in src, "no way to attribute the delta")
        check(f"10 {name} captures the rows the store already held",
              "out_already_held=" in src, "duplicates would be derived, not measured")
    orch = (_REPO / "auxsays" / "scripts" / "orchestrate_evidence_run.py").read_text(encoding="utf-8")
    check("10 the orchestration graph finalizes before it upserts health",
          orch.index("finalize_method_health_delta(") < orch.index("upsert_method_health(health"),
          "health is written before the delta is known")
    obs = (_REPO / "auxsays" / "scripts" / "patch_collectors" / "obs.py").read_text(encoding="utf-8")
    check("10 OBS passes the delta its legacy runner reports",
          "evidence_rows_added=rows_added" in obs,
          "OBS appends inside the legacy script; it must forward the reported delta")

    # ---------------- the shipped corpus ----------------
    print(NEWLINE + "[11] the committed telemetry no longer equates the two fields")
    mh = yaml.safe_load(
        (_REPO / "auxsays" / "_data" / "evidence_method_health.yml").read_text(encoding="utf-8"))["methods"]
    check("11 the file is non-empty (this section is not vacuous)", len(mh) > 100, str(len(mh)))
    over = [m for m in mh
            if int(m.get("evidence_rows_added") or 0) > int(m.get("accepted_candidates") or 0)]
    check("11 no row claims more stored than accepted", not over, f"{len(over)} rows")
    check("11 added + duplicates never exceeds accepted",
          not [m for m in mh
               if int(m.get("evidence_rows_added") or 0) + int(m.get("duplicate_existing_evidence") or 0)
               > int(m.get("accepted_candidates") or 0)])

    print(NEWLINE + "[12] the public table no longer says 'added' for a number that is not")
    page = (_REPO / "auxsays" / "updates" / "methodology" / "index.md").read_text(encoding="utf-8")
    emitted = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", page, flags=re.S)
    check("12 the label states what the number is", "newly stored" in emitted,
          "the column still reads 'N added'")
    check("12 duplicates are surfaced next to it", "already held" in emitted)
    check("12 it still renders the real field", "item.evidence_rows_added" in emitted)

    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
