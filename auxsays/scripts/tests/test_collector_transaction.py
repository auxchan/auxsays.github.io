#!/usr/bin/env python3
"""Per-collector filesystem transaction contract (fail-soft remediation, Part D/E).

Proves that a collector which writes tracked output and then raises (or writes outside its declared
mutable surface) leaves ZERO current-run output in tracked files, while earlier successful collectors'
output survives -- the isolation that exception-catching alone cannot provide. Uses a throwaway git
repo (the transaction detects undeclared mutations and restores via git). No network.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_collector_transaction.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib.collector_txn import CollectorTransaction, UnexpectedMutation  # noqa: E402
import patch_collectors.base as base  # noqa: E402

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


def g(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "ABSENT"


def make_repo() -> tuple[Path, Path, Path]:
    d = Path(tempfile.mkdtemp(prefix="txn-"))
    g(d, "init", "-b", "main"); g(d, "config", "user.email", "t@t"); g(d, "config", "user.name", "t")
    ev = d / "_data" / "consensus_evidence.yml"
    ev.parent.mkdir(parents=True)
    ev.write_text("schema_version: 1\nevidence:\n- id: seed-1\n  product_id: p0\n", encoding="utf-8")
    recs = d / "updates" / "generated"
    recs.mkdir(parents=True)
    (recs / "2026-01-01-p0-1.md").write_text("---\nproduct_id: p0\nupdate_version: '1'\n---\nbody\n", encoding="utf-8")
    (d / "AGENTS.md").write_text("do not touch\n", encoding="utf-8")
    g(d, "add", "-A"); g(d, "commit", "-m", "seed")
    return d, ev, recs


def run_collector(repo: Path, roots: list[Path], body) -> tuple[bool, str | None]:
    """Mirror the runner's per-collector transaction handling."""
    txn = CollectorTransaction(repo, roots)
    txn.begin()
    try:
        body()
        undecl = txn.undeclared_mutations()
        if undecl:
            raise UnexpectedMutation(undecl)
    except Exception as exc:  # noqa: BLE001
        try:
            txn.rollback()
        except Exception:
            return False, "rollback_failed"
        return False, type(exc).__name__
    txn.commit()
    return True, None


def run() -> int:
    print("=" * 60)
    print("Collector transaction contract tests")
    print("=" * 60)

    # ---- Case 1 + 8: healthy A -> failing B (write+modify+create+delete then raise) -> healthy C ----
    d, ev, recs = make_repo()
    roots = [ev, recs]
    ev0, rec0 = sha(ev), sha(recs / "2026-01-01-p0-1.md")

    def collector_a():
        base.append_evidence_rows([{"id": "a-1", "product_id": "A", "update_version": "1", "source_url": "http://a/1"}], path=ev)
        (recs / "2026-02-02-A-1.md").write_text("---\nproduct_id: A\nupdate_version: '1'\n---\nA body\n", encoding="utf-8")

    okA, _ = run_collector(d, roots, collector_a)
    ev_after_a = sha(ev)
    check("A committed: evidence changed", okA and ev_after_a != ev0)
    check("A committed: A record created", (recs / "2026-02-02-A-1.md").exists())

    def collector_b():
        base.append_evidence_rows([{"id": "b-1", "product_id": "B", "update_version": "1", "source_url": "http://b/1"}], path=ev)
        (recs / "2026-02-02-A-1.md").write_text("B TAMPERED A's record\n", encoding="utf-8")  # modify existing
        (recs / "2026-03-03-B-1.md").write_text("B created\n", encoding="utf-8")               # create
        (recs / "2026-01-01-p0-1.md").unlink()                                                 # delete existing
        raise RuntimeError("secret token=xyz /home/runner boom")

    okB, reasonB = run_collector(d, roots, collector_b)
    check("B failed", not okB)
    check("B: 8 A's committed output preserved (evidence + record byte-identical)",
          sha(ev) == ev_after_a and (recs / "2026-02-02-A-1.md").read_text() == "---\nproduct_id: A\nupdate_version: '1'\n---\nA body\n")
    check("B: its evidence append rolled back (no b-1)", "b-1" not in ev.read_text())
    check("B: created record removed", not (recs / "2026-03-03-B-1.md").exists())
    check("B: deleted record restored byte-identical", sha(recs / "2026-01-01-p0-1.md") == rec0)

    def collector_c():
        base.append_evidence_rows([{"id": "c-1", "product_id": "C", "update_version": "1", "source_url": "http://c/1"}], path=ev)

    okC, _ = run_collector(d, roots, collector_c)
    check("C committed after B failed (later collectors still run)", okC and "c-1" in ev.read_text())
    check("final evidence has a-1 and c-1 but NOT b-1",
          all(x in ev.read_text() for x in ("a-1", "c-1")) and "b-1" not in ev.read_text())

    # ---- Case 2 + 9: undeclared mutation (returns normally) -> rejected + rolled back ----
    d2, ev2, recs2 = make_repo()
    agents0 = sha(d2 / "AGENTS.md")

    def collector_undeclared():
        base.append_evidence_rows([{"id": "u-1", "product_id": "U", "update_version": "1", "source_url": "http://u/1"}], path=ev2)
        (d2 / "AGENTS.md").write_text("HIJACKED\n", encoding="utf-8")  # tracked path OUTSIDE roots

    okU, reasonU = run_collector(d2, [ev2, recs2], collector_undeclared)
    check("undeclared mutation -> collector classified failed", not okU and reasonU == "UnexpectedMutation")
    check("undeclared out-of-root path restored (AGENTS.md)", sha(d2 / "AGENTS.md") == agents0)
    check("undeclared collector's in-root evidence also rolled back", "u-1" not in ev2.read_text())
    # create + delete OUTSIDE roots also flagged
    d2b, ev2b, recs2b = make_repo()
    def collector_outside_create():
        (d2b / "newfile.txt").write_text("x\n", encoding="utf-8")
    ok_oc, r_oc = run_collector(d2b, [ev2b, recs2b], collector_outside_create)
    check("undeclared CREATE outside roots -> failed + cleaned", (not ok_oc) and not (d2b / "newfile.txt").exists())

    # ---- Case 3 + 10: total failure -> every tracked file byte-identical, working tree clean ----
    d3, ev3, recs3 = make_repo()
    snap = {p.relative_to(d3).as_posix(): sha(p) for p in d3.rglob("*") if p.is_file() and ".git" not in p.parts}
    for name in ("X", "Y"):
        def failing(n=name):
            base.append_evidence_rows([{"id": f"{n}-1", "product_id": n, "update_version": "1", "source_url": f"http://{n}/1"}], path=ev3)
            raise RuntimeError("boom")
        okF, _ = run_collector(d3, [ev3, recs3], failing)
        check(f"total-failure collector {name} failed", not okF)
    after = {p.relative_to(d3).as_posix(): sha(p) for p in d3.rglob("*") if p.is_file() and ".git" not in p.parts}
    check("total failure: every tracked file byte-identical to baseline", snap == after, f"{snap} != {after}")
    check("total failure: working tree clean (no untracked debris, clean index)",
          g(d3, "status", "--porcelain").stdout.strip() == "")

    # ---- Case 4: failed collector had prior committed evidence -> survives, no no_results ----
    d4, ev4, recs4 = make_repo()
    base.append_evidence_rows([{"id": "prior-1", "product_id": "F", "update_version": "1", "source_url": "http://f/prior"}], path=ev4)
    g(d4, "add", "-A"); g(d4, "commit", "-m", "prior F evidence")
    ev4_prior = sha(ev4)
    def failing_with_prior():
        base.append_evidence_rows([{"id": "f-new", "product_id": "F", "update_version": "1", "source_url": "http://f/new"}], path=ev4)
        raise RuntimeError("boom")
    run_collector(d4, [ev4, recs4], failing_with_prior)
    check("failed collector: prior committed evidence survives byte-identical", sha(ev4) == ev4_prior)
    check("failed collector: no no_results / no new row injected", "f-new" not in ev4.read_text() and "prior-1" in ev4.read_text())

    # ---- Case 6: atomic evidence append -- crash at os.replace leaves original byte-identical ----
    d6, ev6, recs6 = make_repo()
    ev6_before = ev6.read_text(encoding="utf-8")
    orig_replace = base.os.replace
    base.os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full at replace"))
    try:
        raised = False
        try:
            base.append_evidence_rows([{"id": "atom-1", "product_id": "Z", "update_version": "1", "source_url": "http://z/1"}], path=ev6)
        except OSError:
            raised = True
    finally:
        base.os.replace = orig_replace
    check("atomic append: os.replace failure raised (no silent partial)", raised)
    check("atomic append: original evidence byte-identical after failed replace", ev6.read_text(encoding="utf-8") == ev6_before)
    check("atomic append: no .tmp debris left behind", not any(p.name.startswith(".") and p.suffix == ".tmp" for p in ev6.parent.iterdir()))

    # ---- Case 7: identical rerun -> no duplicate evidence, deterministic ----
    d7, ev7, recs7 = make_repo()
    rows = [{"id": "dup-1", "product_id": "R", "update_version": "1", "source_url": "http://r/1"}]
    base.append_evidence_rows(rows, path=ev7)
    first = ev7.read_text(encoding="utf-8")
    base.append_evidence_rows(rows, path=ev7)  # identical rerun
    second = ev7.read_text(encoding="utf-8")
    check("identical rerun: no duplicate evidence (dedup) + deterministic", first == second and first.count("id: dup-1") == 1)

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
