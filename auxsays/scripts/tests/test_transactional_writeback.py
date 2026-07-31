#!/usr/bin/env python3
"""Transactional writeback: validate-before-commit gate (fail-soft collection sprint, Req 2).

A validated writeback must be all-or-nothing at the committed/origin level: the staged tree is
validated BEFORE any commit, so an invalid working tree (e.g. left dirty by a partial/failed
upstream step) can never be committed. On validation failure: no commit, no push, origin + local
HEAD byte-identical. The gate is OPT-IN (``validate_before_commit``) so other workflows (patch
ingestion) are unchanged.

Builds a throwaway bare origin + working clone against real git. No network (pages dispatch off).

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_transactional_writeback.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import automation_writeback as aw  # noqa: E402

PY_OK = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
PY_FAIL = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
ALLOW = ["data/evidence_method_health.yml", "records/*.md"]

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


def g(repo: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if ok and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {p.returncode}: {p.stderr}")
    return p


def write(repo: Path, rel: str, content: str) -> None:
    fp = repo / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")


def head(repo: Path, ref: str = "main") -> str:
    return g(repo, "rev-parse", ref).stdout.strip()


def setup(tmp: Path) -> tuple[Path, Path]:
    origin = tmp / "origin.git"
    g(tmp, "init", "--bare", "-b", "main", str(origin))
    seed = tmp / "seed"
    g(tmp, "clone", str(origin), str(seed))
    g(seed, "config", "user.name", "seed"); g(seed, "config", "user.email", "seed@x")
    write(seed, "data/evidence_method_health.yml", "schema_version: 1\nmethods:\n  - a\n")
    write(seed, "records/rec-obs.md", "obs base\n")
    g(seed, "add", "-A"); g(seed, "commit", "-m", "seed"); g(seed, "push", "origin", "main")
    work = tmp / "work"
    g(tmp, "clone", str(origin), str(work))
    g(work, "config", "user.name", "bot"); g(work, "config", "user.email", "bot@x")
    return origin, work


def cfg(work: Path, **kw) -> aw.WritebackConfig:
    base = dict(repo=work, message="automation writeback", allow=list(ALLOW),
                validate=[PY_OK], branch="main", remote="origin", pages_cmd=None)
    base.update(kw)
    return aw.WritebackConfig(**base)


def run() -> int:
    print("=" * 60)
    print("Transactional writeback (validate-before-commit) tests")
    print("=" * 60)

    # --- A: validate_before_commit + FAILING validate -> no commit, byte-identical -------------
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        origin, work = setup(tmp)
        origin_before, local_before = head(origin), head(work)
        write(work, "records/rec-obs.md", "obs CHANGED by a partial collect\n")  # dirty working tree
        result = aw.run_writeback(cfg(work, validate=[PY_FAIL], validate_before_commit=True))
        check("A: outcome=validation_failed_pre_commit", result.outcome == aw.VALIDATION_FAILED_PRE_COMMIT)
        check("A: nothing pushed", result.pushed is False)
        check("A: result not ok", result.ok is False)
        check("A: ORIGIN head byte-identical (no commit reached origin)", head(origin) == origin_before)
        check("A: LOCAL head byte-identical (no commit created)", head(work) == local_before)
        check("A: index is clean (staged changes were reset)",
              g(work, "diff", "--cached", "--name-only").stdout.strip() == "")

    # --- B: validate_before_commit + PASSING validate -> normal commit + push -----------------
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        origin, work = setup(tmp)
        origin_before = head(origin)
        write(work, "records/rec-obs.md", "obs healthy update\n")
        result = aw.run_writeback(cfg(work, validate=[PY_OK], validate_before_commit=True))
        check("B: pushed a commit", result.pushed is True)
        check("B: ORIGIN advanced", head(origin) != origin_before)
        check("B: committed content is the healthy update",
              g(origin, "show", "main:records/rec-obs.md").stdout == "obs healthy update\n")

    # --- C: gate is OPT-IN -> default (off) + failing validate still commits (other workflows) -
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        origin, work = setup(tmp)
        origin_before = head(origin)
        write(work, "records/rec-obs.md", "obs change without pre-commit gate\n")
        # validate_before_commit defaults False; a failing validate is NOT run before the first commit
        result = aw.run_writeback(cfg(work, validate=[PY_FAIL], validate_before_commit=False))
        check("C: opt-in gate off -> first-attempt commit still pushes (patch-ingest unaffected)",
              result.pushed is True and head(origin) != origin_before)

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
