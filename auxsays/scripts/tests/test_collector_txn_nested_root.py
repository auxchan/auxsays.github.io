#!/usr/bin/env python3
"""Nested-root Git path handling for CollectorTransaction (post-PR-37 UnexpectedMutation fix).

Production runs the pipeline with repo_root = <git-top>/auxsays (a SUBDIRECTORY), but
`git status --porcelain` reports paths relative to the Git TOP LEVEL. The transaction previously
joined those git-root-relative paths onto the nested repo_root, doubling the `auxsays/` segment and
misclassifying every legitimate in-surface write as UnexpectedMutation. These tests reproduce that
exact layout (repo_root is a subdir of the git top level) and prove:

  * legitimate in-surface evidence/record writes are NOT flagged (the false positives are gone),
  * semantic ownership still rejects cross-product / deletion (no permissions were broadened),
  * genuine out-of-surface writes are still UnexpectedMutation and rolled back,
  * Git-unavailable still fails closed,
  * spaces/Unicode paths are handled,
  * the historical repo_root == git-top layout still works.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_collector_txn_nested_root.py
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

SELF = "obs-studio"                 # sources {github_issue, curated_watchlist}; methods {github_issues, known_watchlist}
OTHER = "adobe-premiere-pro"
SEEDED = {SELF: {"31.0.3"}, OTHER: {"26.2"}}
SELF_PERMALINK = "/updates/obs-project/obs-studio/31-0-3/"
OTHER_PERMALINK = "/updates/adobe/adobe-premiere-pro/26-2/"


def check(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
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
    return (f"---\nproduct_id: {product_id}\nupdate_version: '{version}'\n"
            f"update_entry: true\npermalink: {permalink}\n---\n{body}\n")


def _under(path: Path, base_dir: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(base_dir).resolve())
        return True
    except ValueError:
        return False


def make_repo(*, nested: bool = True, git: bool = True):
    """Return (top, app, ev, gen). nested=True -> git top level is the PARENT of the application
    root (the production layout). nested=False -> app root == git top level (historical layout)."""
    top = Path(tempfile.mkdtemp(prefix="nest-"))
    app = (top / "auxsays") if nested else top
    (app / "_data").mkdir(parents=True)
    (app / "updates" / "generated").mkdir(parents=True)
    ev = app / "_data" / "consensus_evidence.yml"
    gen = app / "updates" / "generated"
    ev.write_text(
        "schema_version: 1\nevidence:\n"
        f"- id: {SELF}-31-0-3-github_issue-seed\n  product_id: {SELF}\n"
        "  update_version: '31.0.3'\n  source_type: github_issue\n"
        "  source_url: https://github.com/obsproject/obs-studio/issues/1\n",
        encoding="utf-8",
    )
    (gen / "2026-01-01-obs-studio-31-0-3.md").write_text(_record_text(SELF, "31.0.3", SELF_PERMALINK), encoding="utf-8")
    (gen / "2026-01-01-adobe-premiere-pro-26-2.md").write_text(_record_text(OTHER, "26.2", OTHER_PERMALINK), encoding="utf-8")
    (top / "some_script.py").write_text("print('real')\n", encoding="utf-8")
    if git:
        g(top, "init", "-b", "main"); g(top, "config", "user.email", "t@t"); g(top, "config", "user.name", "t")
        g(top, "config", "core.autocrlf", "false")
        g(top, "add", "-A"); g(top, "commit", "-m", "seed")
    return top, app, ev, gen


def snap_tree(top: Path) -> dict[str, str]:
    return {p.relative_to(top).as_posix(): sha(p)
            for p in top.rglob("*") if p.is_file() and ".git" not in p.parts}


def run_owned(app, ev, gen, product_id, body, *, method_health=None, require_git=True):
    """Mirror the runner: txn.begin -> body -> undeclared check -> ownership -> rollback/commit."""
    o._existing_versions = lambda pid: set(SEEDED.get(pid, set()))
    try:
        txn = CollectorTransaction(app, [ev, gen], require_git=require_git)
        txn.begin()
    except GitUnavailable as exc:
        return False, type(exc).__name__
    before_ev = txn.baseline_bytes(ev)
    try:
        body()
        undecl = txn.undeclared_mutations()
        if undecl:
            raise UnexpectedMutation(undecl)
        mutated = {p for p in txn.declared_mutations() if _under(p, gen)}
        o.validate_records(product_id, gen, mutated, txn.baseline_bytes)
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


def owned_evidence_row(rid: str) -> dict:
    return {"id": rid, "product_id": SELF, "update_version": "31.0.3", "source_type": "github_issue",
            "source_url": f"https://github.com/obsproject/obs-studio/issues/{rid}"}


def run() -> int:
    print("=" * 68)
    print("CollectorTransaction nested-root Git path handling")
    print("=" * 68)
    self_rec = "2026-01-01-obs-studio-31-0-3.md"
    other_rec = "2026-01-01-adobe-premiere-pro-26-2.md"

    # 1. legitimate shared evidence modification -> in-surface, ownership runs, commits
    top, app, ev, gen = make_repo()
    ok, r = run_owned(app, ev, gen, SELF, lambda: base.append_evidence_rows([owned_evidence_row("legit1")], path=ev))
    check("1 legit evidence append: committed", ok and "legit1" in ev.read_text(), f"ok={ok} r={r}")

    # 2. legitimate generated-record modification -> accepted
    top, app, ev, gen = make_repo()
    ok, r = run_owned(app, ev, gen, SELF,
                      lambda: (gen / self_rec).write_text(_record_text(SELF, "31.0.3", SELF_PERMALINK, "refreshed"), encoding="utf-8"))
    check("2 legit record modify: committed", ok and "refreshed" in (gen / self_rec).read_text(), f"ok={ok} r={r}")

    # 3. legitimate evidence + record in one transaction -> accepted
    top, app, ev, gen = make_repo()
    def body3():
        base.append_evidence_rows([owned_evidence_row("legit3")], path=ev)
        (gen / self_rec).write_text(_record_text(SELF, "31.0.3", SELF_PERMALINK, "both"), encoding="utf-8")
    ok, r = run_owned(app, ev, gen, SELF, body3)
    check("3 legit evidence+record: committed", ok and "legit3" in ev.read_text() and "both" in (gen / self_rec).read_text(), f"ok={ok} r={r}")

    # 4. write then raise -> exact rollback to baseline
    top, app, ev, gen = make_repo(); base_tree = snap_tree(top)
    def body4():
        base.append_evidence_rows([owned_evidence_row("boom")], path=ev)
        (gen / self_rec).write_text("TORN\n", encoding="utf-8")
        raise RuntimeError("secret token=xyz boom")
    ok, r = run_owned(app, ev, gen, SELF, body4)
    check("4 write-then-raise: rejected", (not ok) and r == "RuntimeError", r or "")
    check("4 write-then-raise: exact rollback (tree byte-identical)", base_tree == snap_tree(top))

    # 5. cross-product record mutation -> ownership rejection + rollback
    top, app, ev, gen = make_repo(); base_tree = snap_tree(top)
    ok, r = run_owned(app, ev, gen, SELF,
                      lambda: (gen / other_rec).write_text(_record_text(OTHER, "26.2", OTHER_PERMALINK, "TAMPERED"), encoding="utf-8"))
    check("5 cross-product record: OwnershipViolation", (not ok) and r == "OwnershipViolation", r or "")
    check("5 cross-product record: rolled back", base_tree == snap_tree(top))

    # 6. cross-product evidence insertion -> ownership rejection + rollback
    top, app, ev, gen = make_repo(); base_tree = snap_tree(top)
    ok, r = run_owned(app, ev, gen, SELF,
                      lambda: base.append_evidence_rows([{"id": "x-cross", "product_id": OTHER, "update_version": "26.2", "source_type": "adobe_community_bug_report", "source_url": "http://x/1"}], path=ev))
    check("6 cross-product evidence: OwnershipViolation", (not ok) and r == "OwnershipViolation", r or "")
    check("6 cross-product evidence: rolled back", base_tree == snap_tree(top))

    # 7. unrelated tracked file mutation -> UnexpectedMutation + rollback
    top, app, ev, gen = make_repo(); s0 = sha(top / "some_script.py")
    def body7():
        base.append_evidence_rows([owned_evidence_row("x7")], path=ev)  # legit in-surface too
        (top / "some_script.py").write_text("print('HIJACK')\n", encoding="utf-8")
    ok, r = run_owned(app, ev, gen, SELF, body7)
    check("7 unrelated tracked file: UnexpectedMutation", (not ok) and r == "UnexpectedMutation", r or "")
    check("7 unrelated tracked file: restored + in-surface rolled back", sha(top / "some_script.py") == s0 and "x7" not in ev.read_text())

    # 8. untracked file outside surface -> UnexpectedMutation + cleanup
    top, app, ev, gen = make_repo()
    ok, r = run_owned(app, ev, gen, SELF, lambda: (top / "sneaky.txt").write_text("x\n", encoding="utf-8"))
    check("8 untracked outside surface: UnexpectedMutation", (not ok) and r == "UnexpectedMutation", r or "")
    check("8 untracked outside surface: cleaned + git clean", (not (top / "sneaky.txt").exists()) and g(top, "status", "--porcelain").stdout.strip() == "")

    # 9. deleted owned record -> existing ownership policy decides (reject), unchanged by this fix
    top, app, ev, gen = make_repo(); base_tree = snap_tree(top)
    ok, r = run_owned(app, ev, gen, SELF, lambda: (gen / self_rec).unlink())
    check("9 deleted owned record: OwnershipViolation (policy unchanged)", (not ok) and r == "OwnershipViolation", r or "")
    check("9 deleted owned record: restored", base_tree == snap_tree(top))

    # 10. git unavailable + require_git -> fail closed
    top, app, ev, gen = make_repo(git=False)  # not a work tree
    base_tree = snap_tree(top)
    ok, r = run_owned(app, ev, gen, SELF, lambda: base.append_evidence_rows([owned_evidence_row("nogit")], path=ev), require_git=True)
    check("10 git unavailable + require_git: GitUnavailable (fail closed)", (not ok) and r == "GitUnavailable", r or "")
    check("10 git unavailable: no write (writeback_eligible=false semantics)", base_tree == snap_tree(top) and "nogit" not in ev.read_text())

    # 11. nested path with spaces and Unicode (outside surface) -> detected + rolled back
    top, app, ev, gen = make_repo()
    weird = top / "café notes (draft).md"
    ok, r = run_owned(app, ev, gen, SELF, lambda: weird.write_text("hi\n", encoding="utf-8"))
    check("11 spaces+unicode path: UnexpectedMutation (correct -z normalization)", (not ok) and r == "UnexpectedMutation", r or "")
    check("11 spaces+unicode path: cleaned", not weird.exists())

    # 12. historical layout compatibility: repo_root == git top level still works
    top, app, ev, gen = make_repo(nested=False)
    ok, r = run_owned(app, ev, gen, SELF, lambda: base.append_evidence_rows([owned_evidence_row("flat1")], path=ev))
    check("12 top-level-root layout: still commits legit write", ok and "flat1" in ev.read_text(), f"ok={ok} r={r}")

    # 13. exact doubled-prefix regression on _within_roots
    top, app, ev, gen = make_repo()
    txn = CollectorTransaction(app, [ev, gen], require_git=True); txn.begin()
    git_rel = "auxsays/updates/generated/example.md"
    inside = txn._within_roots(git_rel)
    resolved = (txn._git_root / git_rel).resolve()
    doubled = (app / git_rel).resolve()  # the OLD buggy join
    check("13 doubled-prefix regression: git-rel path is within roots", inside is True)
    check("13 doubled-prefix regression: resolves under git top, not doubled",
          str(resolved).replace("\\", "/").endswith("auxsays/updates/generated/example.md")
          and "auxsays/auxsays" not in str(resolved).replace("\\", "/")
          and "auxsays/auxsays" in str(doubled).replace("\\", "/"))

    # VERIFICATION: controlled write-mode simulation in a nested repo -- healthy A -> fail B -> healthy C
    top, app, ev, gen = make_repo()
    okA, _ = run_owned(app, ev, gen, SELF, lambda: base.append_evidence_rows([owned_evidence_row("seqA")], path=ev))
    okB, rB = run_owned(app, ev, gen, SELF,
                        lambda: base.append_evidence_rows([{"id": "seqB", "product_id": OTHER, "update_version": "26.2", "source_type": "adobe_community_bug_report", "source_url": "http://b/1"}], path=ev))
    okC, _ = run_owned(app, ev, gen, SELF, lambda: base.append_evidence_rows([owned_evidence_row("seqC")], path=ev))
    text = ev.read_text()
    check("seq: A committed", okA and "seqA" in text)
    check("seq: B rejected + rolled back", (not okB) and rB == "OwnershipViolation")
    check("seq: A and C survive, B absent", "seqA" in text and "seqC" in text and "seqB" not in text)
    check("seq: no duplicate evidence, clean index vs expected outputs",
          text.count("id: seqA") == 1 and text.count("id: seqC") == 1)

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
