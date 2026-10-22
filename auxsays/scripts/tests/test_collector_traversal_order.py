#!/usr/bin/env python3
"""Budget-bounded collectors must walk the corpus NEWEST-FIRST.

THE DEFECT THIS PINS
--------------------
`base.generated_records` returns records in FILENAME order. Every generated filename is
date-prefixed, so that order is oldest-first: 2014 before 2026. Each collector is bounded by
`AUXSAYS_COLLECTOR_DEADLINE_SECONDS` (1200 s) and simply `break`s when it expires. An oldest-first
walk therefore spends its entire budget on the historical head of the corpus and never reaches the
patches a reader is looking at.

Measured on DaVinci, scheduled run 34377762747, BEFORE the fix:

    versions processed        10.1.5 .. 15.0.1   (published 2014-05-09 .. 2018-09-03)
    candidates rejected       77 of 77, all `missing_exact_patch_version_match`
    records never reached     87 of 120
    newest release 21.1       zero method-health rows -- never searched once by any method
    site monitoring axis      MONITORING ACTIVE on 0 of 120 pages

and the high-water mark was RECEDING run over run, because each newly ingested record lengthens the
corpus ahead of the recent tail. Acrobat (PRs #102-#105) and Windows already walked newest-first;
DaVinci was the collector that never got it.

WHY THIS TEST IS STRUCTURAL, NOT TEXTUAL
----------------------------------------
An earlier suite in this repo asserted a workflow's safety guards by searching the file for tokens,
and stayed green after three of the guards were deleted, because the tokens survived in the comments
describing them. So the wiring check here parses the collector with `ast` and asserts the actual call
graph -- `newest_first(generated_records(...))` -- rather than looking for a substring. The ordering
itself is asserted behaviourally, and a budget simulation over the REAL corpus proves the fix changes
which records get reached.

Run standalone. Deterministic, offline, writes nothing.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "auxsays" / "scripts"))

from patch_collectors.base import PatchRecord, generated_records, newest_first  # noqa: E402

NEWLINE = "\n"
_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))


def rec(version: str, published: str) -> PatchRecord:
    return PatchRecord(product_id="p", update_version=version, path=Path(f"{published}-{version}.md"),
                       update_published_at=published, update_status="", update_product="p",
                       target_build="")


# Which collectors are budget-bounded enough for traversal order to matter. A collector whose whole
# corpus fits inside one budget cannot starve, so requiring the helper there would be cargo cult.
BUDGET_BOUND = {"davinci.py": "blackmagic-davinci"}
# These carry their own private, older copy of the same helper. They are FROZEN products; the
# duplication is deliberate and documented in base.newest_first.
HAS_PRIVATE_COPY = {"adobe_acrobat_community.py", "microsoft_windows.py"}


def collect_assignment_calls(path: Path, class_name: str, method: str) -> list[str]:
    """The call chain assigned to `records` inside <class_name>.<method>, from the AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue
        for sub in node.body:
            if not (isinstance(sub, ast.FunctionDef) and sub.name == method):
                continue
            for stmt in ast.walk(sub):
                if not isinstance(stmt, ast.Assign):
                    continue
                if not any(isinstance(t, ast.Name) and t.id == "records" for t in stmt.targets):
                    continue
                names = []
                for c in ast.walk(stmt.value):
                    if isinstance(c, ast.Call):
                        f = c.func
                        names.append(f.id if isinstance(f, ast.Name)
                                     else getattr(f, "attr", "?"))
                return names
    return []


def main() -> int:
    print(NEWLINE + "[1] the ordering primitive itself")
    rs = [rec("10.1.5", "2014-05-09"), rec("21.1", "2026-09-08"), rec("15.0.1", "2018-09-03")]
    out = [r.update_version for r in newest_first(rs)]
    check("1a newest release first, oldest last", out == ["21.1", "15.0.1", "10.1.5"], str(out))
    check("1b it does not mutate its input",
          [r.update_version for r in rs] == ["10.1.5", "21.1", "15.0.1"])
    tie = newest_first([rec("21.0", "2026-06-03"), rec("21.1", "2026-06-03")])
    check("1c ties break on version, so two runs walk the same order",
          [r.update_version for r in tie] == ["21.1", "21.0"], str([r.update_version for r in tie]))
    check("1d a record with no publish date sorts last rather than raising",
          [r.update_version for r in newest_first([rec("x", ""), rec("y", "2020-01-01")])]
          == ["y", "x"])
    check("1e empty input is fine", newest_first([]) == [])

    print(NEWLINE + "[2] the wiring, read from the AST rather than the text")
    for filename, product in sorted(BUDGET_BOUND.items()):
        path = REPO / "auxsays" / "scripts" / "patch_collectors" / filename
        cls = {"davinci.py": ("DavinciCollector", "collect")}[filename]
        calls = collect_assignment_calls(path, *cls)
        check(f"2a {filename}: the record walk is assigned from generated_records",
              "generated_records" in calls, f"calls={calls}")
        check(f"2b {filename}: and that result is wrapped in newest_first",
              "newest_first" in calls,
              f"calls={calls} -- an oldest-first walk starves the newest patches")

    print(NEWLINE + "[3] the frozen collectors keep their own copy, and still walk newest-first")
    for filename in sorted(HAS_PRIVATE_COPY):
        src = (REPO / "auxsays" / "scripts" / "patch_collectors" / filename).read_text(encoding="utf-8")
        tree = ast.parse(src)
        defines = any(isinstance(n, ast.FunctionDef) and n.name == "_newest_first"
                      for n in ast.walk(tree))
        uses = any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_newest_first"
                   for n in ast.walk(tree))
        check(f"3a {filename} still defines its private _newest_first", defines)
        check(f"3b {filename} still calls it", uses)

    print(NEWLINE + "[4] budget simulation over the REAL corpus")
    real = generated_records("blackmagic-davinci")
    check("4a the corpus is large enough for traversal order to matter",
          len(real) > 40, f"{len(real)} records")
    if real:
        # Run 34377762747 reached 33 records before its budget expired. Use that measured number.
        BUDGET = 33
        newest = [r.update_version for r in newest_first(real)[:BUDGET]]
        oldest = [r.update_version for r in real[:BUDGET]]
        top = max(real, key=lambda r: (str(r.update_published_at), str(r.update_version)))
        check("4b with a 33-record budget the NEWEST release is now reached",
              top.update_version in newest, f"newest={newest[:4]}")
        # NON-VACUITY: the same budget on the unfixed order must MISS it, or this proves nothing.
        check("4c and the pre-fix order provably missed it",
              top.update_version not in oldest,
              "if the old order also reached it, this suite is not measuring the defect")
        check("4d the pre-fix order spent its budget on the historical head",
              all(str(r.update_published_at) < "2020-01-01" for r in real[:BUDGET]),
              f"pre-fix window: {real[0].update_published_at[:10]} .. {real[BUDGET-1].update_published_at[:10]}")
        reached_after = {r.update_version for r in newest_first(real)[:BUDGET]}
        reached_before = {r.update_version for r in real[:BUDGET]}
        check("4e the fix changes which records are reached at all",
              len(reached_after - reached_before) > 20,
              f"newly reachable: {len(reached_after - reached_before)}")

    print(NEWLINE + "=" * 74)
    print(f"Results: {_passed}/{_passed + _failed} passed, {_failed} failed")
    print("=" * 74)
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
