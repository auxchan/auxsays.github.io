#!/usr/bin/env python3
"""Semantic collector ownership + Git fail-closed contract (Part D/E/F hard gates).

Filesystem containment (test_collector_transaction) is necessary but not sufficient: a collector can
stay inside its declared roots yet still mutate ANOTHER product's record, append cross-product /
unauthorized-source evidence, or return foreign method-health. This suite drives adversarial
collectors that return NORMALLY but attempt each ownership breach, and proves every one is rejected,
the whole collector transaction rolls back byte-for-byte, earlier successful collectors survive, later
independent collectors still run, and no debris remains. It also proves Git fail-closed: in a context
that requires Git, an unavailable/failed Git status hard-aborts instead of degrading silently.

Uses throwaway git repos + REAL product identities so the ownership manifest applies. No network.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_collector_ownership.py
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

from lib.collector_txn import CollectorTransaction, UnexpectedMutation, GitUnavailable  # noqa: E402
from lib import collector_ownership as o  # noqa: E402
import patch_collectors.base as base  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

# Real product identities so ALLOWED_METHODS / ALLOWED_SOURCE_TYPES apply.
SELF = "obs-studio"                 # methods {github_issues, known_watchlist}; sources {github_issue, curated_watchlist}
OTHER = "adobe-premiere-pro"        # methods {reddit_search, ...}; sources {adobe_community_bug_report, ...}
SEEDED_VERSIONS = {SELF: {"31.0.3"}, OTHER: {"26.2"}}


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


def _record_text(product_id: str, version: str, permalink: str, body: str = "body") -> str:
    return (
        "---\n"
        f"product_id: {product_id}\n"
        f"update_version: '{version}'\n"
        "update_entry: true\n"
        f"permalink: {permalink}\n"
        f"---\n{body}\n"
    )


SELF_PERMALINK = "/updates/obs-project/obs-studio/31-0-3/"
OTHER_PERMALINK = "/updates/adobe/adobe-premiere-pro/26-2/"


def make_repo(*, git: bool = True) -> tuple[Path, Path, Path]:
    d = Path(tempfile.mkdtemp(prefix="own-"))
    if git:
        g(d, "init", "-b", "main"); g(d, "config", "user.email", "t@t"); g(d, "config", "user.name", "t")
    ev = d / "_data" / "consensus_evidence.yml"
    ev.parent.mkdir(parents=True)
    # one real existing evidence row owned by SELF (for immutability / delete cases)
    ev.write_text(
        "schema_version: 1\n"
        "evidence:\n"
        f"- id: {SELF}-31-0-3-github_issue-seed\n"
        f"  product_id: {SELF}\n"
        "  update_version: '31.0.3'\n"
        "  source_type: github_issue\n"
        "  source_url: https://github.com/obsproject/obs-studio/issues/1\n",
        encoding="utf-8",
    )
    recs = d / "updates" / "generated"
    recs.mkdir(parents=True)
    # a SELF record and an OTHER-product record already present
    (recs / "2026-01-01-obs-studio-31-0-3.md").write_text(_record_text(SELF, "31.0.3", SELF_PERMALINK), encoding="utf-8")
    (recs / "2026-01-01-adobe-premiere-pro-26-2.md").write_text(_record_text(OTHER, "26.2", OTHER_PERMALINK), encoding="utf-8")
    (d / "AGENTS.md").write_text("do not touch\n", encoding="utf-8")
    (d / "some_script.py").write_text("print('real')\n", encoding="utf-8")
    if git:
        g(d, "add", "-A"); g(d, "commit", "-m", "seed")
    return d, ev, recs


def _under(path: Path, base_dir: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(base_dir).resolve())
        return True
    except ValueError:
        return False


def run_owned(repo: Path, ev: Path, recs: Path, product_id: str, body,
              *, method_health=None, require_git: bool = False) -> tuple[bool, str | None]:
    """Mirror the runner: txn.begin -> collect -> undeclared check -> ownership validation ->
    rollback on any violation, commit on success. Returns (ok, failure_type)."""
    try:
        txn = CollectorTransaction(repo, [ev, recs], require_git=require_git)
        txn.begin()  # may raise GitUnavailable (fail closed)
    except GitUnavailable as exc:
        return False, type(exc).__name__
    before_ev = txn.baseline_bytes(ev)
    try:
        body()
        undecl = txn.undeclared_mutations()
        if undecl:
            raise UnexpectedMutation(undecl)
        mutated = {p for p in txn.declared_mutations() if _under(p, recs)}
        o.validate_records(product_id, recs, mutated, txn.baseline_bytes)
        after_ev = ev.read_text(encoding="utf-8") if ev.exists() else None
        o.validate_evidence(product_id, before_ev.decode("utf-8") if before_ev is not None else None, after_ev)
        o.validate_method_health(product_id, method_health or [])
    except Exception as exc:  # noqa: BLE001
        try:
            txn.rollback()
        except Exception:
            return False, "rollback_failed"
        return False, type(exc).__name__
    txn.commit()
    return True, None


def snap_tree(repo: Path) -> dict[str, str]:
    return {p.relative_to(repo).as_posix(): sha(p)
            for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}


def run() -> int:
    global _PASS, _FAIL
    print("=" * 68)
    print("Semantic collector ownership + Git fail-closed contract tests")
    print("=" * 68)

    # Control version resolution deterministically (decouple from the live repo).
    o._existing_versions = lambda pid: set(SEEDED_VERSIONS.get(pid, set()))

    self_rec = "2026-01-01-obs-studio-31-0-3.md"
    other_rec = "2026-01-01-adobe-premiere-pro-26-2.md"

    def valid_self_evidence_row(rid: str) -> dict:
        return {"id": rid, "product_id": SELF, "update_version": "31.0.3",
                "source_type": "github_issue",
                "source_url": f"https://github.com/obsproject/obs-studio/issues/{rid}"}

    # ---- POSITIVE CONTROL: a healthy SELF collector commits (no false-reject) ----
    d, ev, recs = make_repo()
    def healthy():
        base.append_evidence_rows([valid_self_evidence_row("healthy1")], path=ev)
    okH, _ = run_owned(d, ev, recs, SELF, healthy,
                       method_health=[{"product_id": SELF, "method_id": "github_issues",
                                       "update_version": "31.0.3", "status": "success"}])
    check("POSITIVE control: healthy owned collector commits", okH and "healthy1" in ev.read_text())

    # ---- The 14 adversarial ownership cases ----
    cases = []

    # 1. modify another product's generated record
    def c1(recs=None): (recs / other_rec).write_text(_record_text(OTHER, "26.2", OTHER_PERMALINK, "TAMPERED"), encoding="utf-8")
    cases.append(("1 modify other-product record", c1, "OwnershipViolation"))

    # 2. create another product's generated record
    def c2(recs=None): (recs / "2026-05-05-adobe-premiere-pro-26-2-x.md").write_text(_record_text(OTHER, "26.2", OTHER_PERMALINK), encoding="utf-8")
    cases.append(("2 create other-product record", c2, "OwnershipViolation"))

    # 3. delete another product's generated record
    def c3(recs=None): (recs / other_rec).unlink()
    cases.append(("3 delete other-product record", c3, "OwnershipViolation"))

    # 4a. arbitrary (non-record) markdown under generated/
    def c4a(recs=None): (recs / "arbitrary.md").write_text("just some text, no front matter\n", encoding="utf-8")
    cases.append(("4a arbitrary non-record file under generated/", c4a, "OwnershipViolation"))

    # 4b. malformed front matter under generated/
    def c4b(recs=None): (recs / "2026-06-06-obs-studio-broken.md").write_text("---\nproduct_id: obs-studio\n : : bad\n---\nb\n", encoding="utf-8")
    cases.append(("4b malformed record front matter", c4b, "OwnershipViolation"))

    # 4c. same-product record for an UNRESOLVED version (identity mismatch)
    def c4c(recs=None): (recs / "2026-07-07-obs-studio-99-9-9.md").write_text(_record_text(SELF, "99.9.9", "/updates/obs-project/obs-studio/99-9-9/"), encoding="utf-8")
    cases.append(("4c own record with unresolved version", c4c, "OwnershipViolation"))

    # 5. append evidence for another product
    def c5(ev=None): base.append_evidence_rows([{"id": "cross-1", "product_id": OTHER, "update_version": "26.2", "source_type": "adobe_community_bug_report", "source_url": "http://x/1"}], path=ev)
    cases.append(("5 append cross-product evidence", c5, "OwnershipViolation"))

    # 6. append evidence for unauthorized version
    def c6(ev=None): base.append_evidence_rows([{"id": "badver-1", "product_id": SELF, "update_version": "0.0.0", "source_type": "github_issue", "source_url": "http://x/2"}], path=ev)
    cases.append(("6 append evidence unauthorized version", c6, "OwnershipViolation"))

    # 7. append evidence for unauthorized method/source
    def c7(ev=None): base.append_evidence_rows([{"id": "badsrc-1", "product_id": SELF, "update_version": "31.0.3", "source_type": "reddit_community_report", "source_url": "http://x/3"}], path=ev)
    cases.append(("7 append evidence unauthorized source", c7, "OwnershipViolation"))

    # 8. modify an existing evidence row
    def c8(ev=None):
        t = ev.read_text(encoding="utf-8").replace("source_type: github_issue", "source_type: TAMPERED", 1)
        base.atomic_write_text(ev, t)
    cases.append(("8 modify existing evidence row", c8, "OwnershipViolation"))

    # 9. delete an existing evidence row
    def c9(ev=None):
        base.atomic_write_text(ev, "schema_version: 1\nevidence: []\n")
    cases.append(("9 delete existing evidence row", c9, "OwnershipViolation"))

    # 10 + 11 are method-health return values (handled below, not filesystem bodies)

    for label, body, expect in cases:
        d, ev, recs = make_repo()
        base_tree = snap_tree(d)
        kwargs = {}
        # bind the right target into the body via defaults
        if body.__code__.co_varnames[:1] == ("recs",):
            fn = (lambda b=body, r=recs: b(r))
        else:
            fn = (lambda b=body, e=ev: b(e))
        ok, reason = run_owned(d, ev, recs, SELF, fn)
        after_tree = snap_tree(d)
        check(f"case {label}: rejected as {expect}", (not ok) and reason == expect, f"got ok={ok} reason={reason}")
        check(f"case {label}: full rollback (tree byte-identical)", base_tree == after_tree)
        check(f"case {label}: no untracked/debris (git clean)", g(d, "status", "--porcelain").stdout.strip() == "")

    # 10. return method-health for another product
    d, ev, recs = make_repo(); base_tree = snap_tree(d)
    ok, reason = run_owned(d, ev, recs, SELF, lambda: None,
                           method_health=[{"product_id": OTHER, "method_id": "github_issues", "update_version": "26.2", "status": "success"}])
    check("case 10 method-health other product: rejected", (not ok) and reason == "OwnershipViolation", reason or "")
    check("case 10: full rollback", base_tree == snap_tree(d))

    # 11. return method-health for another method
    d, ev, recs = make_repo(); base_tree = snap_tree(d)
    ok, reason = run_owned(d, ev, recs, SELF, lambda: None,
                           method_health=[{"product_id": SELF, "method_id": "reddit_search", "update_version": "31.0.3", "status": "success"}])
    check("case 11 method-health unauthorized method: rejected", (not ok) and reason == "OwnershipViolation", reason or "")
    check("case 11: full rollback", base_tree == snap_tree(d))

    # 12. modify an unrelated tracked script (outside declared roots)
    d, ev, recs = make_repo(); s0 = sha(d / "some_script.py")
    def c12():
        base.append_evidence_rows([valid_self_evidence_row("x12")], path=ev)   # legit in-root write too
        (d / "some_script.py").write_text("print('HIJACKED')\n", encoding="utf-8")
    ok, reason = run_owned(d, ev, recs, SELF, c12)
    check("case 12 modify unrelated script: rejected (UnexpectedMutation)", (not ok) and reason == "UnexpectedMutation", reason or "")
    check("case 12: script restored byte-identical", sha(d / "some_script.py") == s0)
    check("case 12: in-root evidence also rolled back", "x12" not in ev.read_text())

    # 13. create an untracked file outside allowed transaction-temp locations
    d, ev, recs = make_repo()
    def c13(): (d / "sneaky.txt").write_text("x\n", encoding="utf-8")
    ok, reason = run_owned(d, ev, recs, SELF, c13)
    check("case 13 create file outside roots: rejected", (not ok) and reason == "UnexpectedMutation", reason or "")
    check("case 13: stray file cleaned", not (d / "sneaky.txt").exists())
    check("case 13: git clean", g(d, "status", "--porcelain").stdout.strip() == "")

    # 14. run with Git unavailable (require_git) -> hard fail closed, no writeback
    d, ev, recs = make_repo(git=False)   # NOT a git work tree
    base_tree = snap_tree(d)
    ok, reason = run_owned(d, ev, recs, SELF, lambda: base.append_evidence_rows([valid_self_evidence_row("gitless")], path=ev), require_git=True)
    check("case 14 git unavailable + require_git: fail closed (GitUnavailable)", (not ok) and reason == "GitUnavailable", reason or "")
    check("case 14: no writeback occurred (tree byte-identical, no evidence written)",
          base_tree == snap_tree(d) and "gitless" not in ev.read_text())
    # dry-run / not-required context may proceed without git (explicit adapter path)
    d2, ev2, recs2 = make_repo(git=False)
    ok2, _ = run_owned(d2, ev2, recs2, SELF, lambda: base.append_evidence_rows([valid_self_evidence_row("nogit-ok")], path=ev2), require_git=False)
    check("case 14b non-required context proceeds without git", ok2 and "nogit-ok" in ev2.read_text())

    # ---- Sequence: healthy A -> adversarial B rejected -> healthy C still runs ----
    d, ev, recs = make_repo()
    okA, _ = run_owned(d, ev, recs, SELF, lambda: base.append_evidence_rows([valid_self_evidence_row("seqA")], path=ev))
    ev_after_a = sha(ev)
    okB, rB = run_owned(d, ev, recs, SELF, lambda: base.append_evidence_rows([{"id": "seqB", "product_id": OTHER, "update_version": "26.2", "source_type": "adobe_community_bug_report", "source_url": "http://b/1"}], path=ev))
    okC, _ = run_owned(d, ev, recs, SELF, lambda: base.append_evidence_rows([valid_self_evidence_row("seqC")], path=ev))
    check("sequence: A committed", okA and "seqA" in ev.read_text())
    check("sequence: B (cross-product) rejected + rolled back", (not okB) and rB == "OwnershipViolation" and sha(ev) != "ABSENT")
    check("sequence: A survives B's rollback", "seqA" in ev.read_text())
    check("sequence: B contributed nothing", "seqB" not in ev.read_text())
    check("sequence: later independent C still runs", okC and "seqC" in ev.read_text())

    print()
    print("=" * 68)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 68)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
