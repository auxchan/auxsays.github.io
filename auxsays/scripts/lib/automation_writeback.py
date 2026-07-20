#!/usr/bin/env python3
"""Shared, deterministic, conflict-safe writeback for AUXSAYS automation workflows.

Every workflow that commits generated outputs to ``main`` (patch evidence collection,
patch ingestion, the DaVinci writers, ...) previously did a plain ``git add`` /
``git commit`` / ``git push``. Because a *separate* workflow (e.g. patch-ingest) can push
to ``main`` between another workflow's checkout and its push, the plain push hits a
non-fast-forward rejection, the run fails, and publication is delayed until a later
scheduled retry. The shared concurrency group ``auxsays-main-writeback`` reduces but does
NOT eliminate this: a queued run may already hold an older checkout, and not every pusher
is guaranteed to sit in the group. So a pre-push fetch/rebase/retry mechanism is mandatory.

This module performs, against an ALREADY-checked-out repo whose working tree already holds
the freshly generated changes:

  1. stage ONLY explicitly permitted paths (git pathspecs)
  2. reject any staged path that is unexpected (blocklist) -> unexpected_changed_path
  3. if the staged diff is empty: no_changes -> no commit, no push, no Pages, exit 0
  4. create the local automation commit
  5. record checkout SHA, local commit SHA, and origin/<branch> SHA
  6. fetch origin/<branch> immediately before each push
  7. if origin/<branch> advanced: rebase the single bot commit onto it
       - a git rebase conflict, OR a clean rebase that shares any modified path with the
         upstream commit, is a conflict -> abort/reset, do NOT push, fail visibly
  8. after a successful rebase, rerun the required validation commands, and re-verify the
     rebased commit still touches only allowed paths
  9. push; on a fresh non-fast-forward rejection, retry up to a bounded limit
 10. dispatch the Pages workflow ONLY after a confirmed successful material push whose
     changed files affect the site

It never force-pushes, never uses ``--ours``/``--theirs`` or ``-X ours``/``-X theirs``, and
never silently resolves a conflict on a shared generated/evidence/state/catalog file.

Deterministic outcome tokens (one per line, prefixed ``WRITEBACK_OUTCOME:``) plus a final
``WRITEBACK_SUMMARY:`` JSON line are emitted for parseable diagnostics, and, when run inside
GitHub Actions, ``outcome`` / ``changed`` / ``deploy_changed`` / ``pushed_sha`` are written to
``$GITHUB_OUTPUT``.

CLI (used by the workflows) and importable ``run_writeback(config)`` (used by tests).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Paths that must NEVER be committed by automation, regardless of the allow-list. Belt-and-
# suspenders on top of the allow-list: a mis-specified allow pathspec that happens to match one
# of these is still refused. (Note: patch_ingest_state.json is intentionally NOT here -- the
# patch-ingest workflow legitimately commits it via its own allow-list.)
FORBIDDEN_PATH_SUBSTRINGS = (
    "/_site/", "_site/",
    "node_modules/",
    ".jekyll-cache/",
    "__pycache__/",
)
FORBIDDEN_PATH_GLOBS = (
    "*.pyc",
    "*.tmp",
    "AGENTS.md",
    "CLAUDE.md",
    "**/AGENTS.md",
    "**/CLAUDE.md",
)


# --- outcome tokens ----------------------------------------------------------
NO_CHANGES = "no_changes"
PUSH_SUCCESS_FIRST_ATTEMPT = "push_success_first_attempt"
UPSTREAM_ADVANCED = "upstream_advanced"
REBASE_SUCCESS = "rebase_success"
VALIDATION_SUCCESS_AFTER_REBASE = "validation_success_after_rebase"
PUSH_SUCCESS_AFTER_RETRY = "push_success_after_retry"
REBASE_CONFLICT = "rebase_conflict"
UNEXPECTED_CHANGED_PATH = "unexpected_changed_path"
VALIDATION_FAILED_AFTER_REBASE = "validation_failed_after_rebase"
RETRY_EXHAUSTED = "retry_exhausted"
PAGES_DISPATCH_SUCCESS = "pages_dispatch_success"
PAGES_DISPATCH_SKIPPED_NO_CHANGES = "pages_dispatch_skipped_no_changes"
PAGES_DISPATCH_SKIPPED_PUSH_FAILURE = "pages_dispatch_skipped_push_failure"

SUCCESS_TOKENS = {NO_CHANGES, PUSH_SUCCESS_FIRST_ATTEMPT, PUSH_SUCCESS_AFTER_RETRY}


@dataclass
class WritebackConfig:
    repo: Path
    message: str
    allow: list[str]
    validate: list[str] = field(default_factory=list)
    site_paths: list[str] = field(default_factory=list)  # subset of allow that affects the site
    max_retries: int = 5
    branch: str = "main"
    remote: str = "origin"
    pages_cmd: str | None = None
    author_name: str = "github-actions[bot]"
    author_email: str = "41898282+github-actions[bot]@users.noreply.github.com"
    # test-only injection: run before the first N push attempts to simulate a concurrent push
    test_hook_before_push: str | None = None
    test_hook_fires: int = 0


@dataclass
class WritebackResult:
    outcome: str
    outcomes: list[str] = field(default_factory=list)
    changed: bool = False
    deploy_changed: bool = False
    checkout_sha: str = ""
    origin_sha_initial: str = ""
    origin_sha_latest: str = ""
    local_commit_sha: str = ""
    rebased_commit_sha: str = ""
    pushed_sha: str = ""
    retry_number: int = 0
    conflicting_paths: list[str] = field(default_factory=list)
    validation: list[dict] = field(default_factory=list)  # {cmd, exit_code}
    pages_dispatched: bool = False
    ok: bool = False

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "outcomes": self.outcomes,
            "changed": self.changed,
            "deploy_changed": self.deploy_changed,
            "checkout_sha": self.checkout_sha,
            "origin_sha_initial": self.origin_sha_initial,
            "origin_sha_latest": self.origin_sha_latest,
            "local_commit_sha": self.local_commit_sha,
            "rebased_commit_sha": self.rebased_commit_sha,
            "pushed_sha": self.pushed_sha,
            "retry_number": self.retry_number,
            "conflicting_paths": self.conflicting_paths,
            "validation": self.validation,
            "pages_dispatched": self.pages_dispatched,
            "ok": self.ok,
        }


class WritebackError(RuntimeError):
    def __init__(self, outcome: str, detail: str = "") -> None:
        super().__init__(f"{outcome}: {detail}" if detail else outcome)
        self.outcome = outcome
        self.detail = detail


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise WritebackError("git_error", f"git {' '.join(args)} -> rc={proc.returncode}: {proc.stderr.strip()}")
    return proc


def _sha(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _is_forbidden(path: str) -> bool:
    p = path.replace("\\", "/")
    if any(sub in f"/{p}" or p.startswith(sub) or f"/{sub}" in f"/{p}" for sub in FORBIDDEN_PATH_SUBSTRINGS):
        return True
    base = p.split("/")[-1]
    return any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch(base, g) for g in FORBIDDEN_PATH_GLOBS)


def _matches_any(path: str, patterns: list[str]) -> bool:
    p = path.replace("\\", "/")
    for pat in patterns:
        pat = pat.replace("\\", "/")
        # git pathspec semantics: an exact dir/prefix matches everything under it, and a
        # trailing/embedded glob matches by fnmatch. Support both a plain prefix and globs.
        if p == pat or p.startswith(pat.rstrip("/") + "/"):
            return True
        if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(p, pat.rstrip("/") + "/*"):
            return True
    return False


def _emit(result: WritebackResult, token: str) -> None:
    result.outcomes.append(token)
    print(f"WRITEBACK_OUTCOME: {token}", flush=True)


def _staged_paths(repo: Path) -> list[str]:
    out = _git(repo, "diff", "--cached", "--name-only").stdout
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _commit_paths(repo: Path, commit: str) -> list[str]:
    out = _git(repo, "show", "--name-only", "--pretty=format:", commit).stdout
    return sorted({ln.strip() for ln in out.splitlines() if ln.strip()})


def _run_validation(repo: Path, commands: list[str], result: WritebackResult) -> bool:
    ok = True
    for cmd in commands:
        proc = subprocess.run(cmd, shell=True, cwd=str(repo), capture_output=True, text=True)
        result.validation.append({"cmd": cmd, "exit_code": proc.returncode})
        print(f"WRITEBACK_VALIDATE: rc={proc.returncode} cmd={cmd}", flush=True)
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout[-2000:] + "\n" + proc.stderr[-2000:] + "\n")
            ok = False
            break
    return ok


def _dispatch_pages(cfg: WritebackConfig, result: WritebackResult) -> None:
    if not cfg.pages_cmd:
        return
    if not result.deploy_changed:
        _emit(result, PAGES_DISPATCH_SKIPPED_NO_CHANGES)
        return
    proc = subprocess.run(cfg.pages_cmd, shell=True, cwd=str(cfg.repo), capture_output=True, text=True)
    if proc.returncode == 0:
        result.pages_dispatched = True
        _emit(result, PAGES_DISPATCH_SUCCESS)
    else:
        # A Pages-dispatch failure does not undo the successful content push; surface it.
        sys.stderr.write(f"pages dispatch failed rc={proc.returncode}: {proc.stderr.strip()}\n")
        _emit(result, PAGES_DISPATCH_SKIPPED_PUSH_FAILURE)


def run_writeback(cfg: WritebackConfig) -> WritebackResult:
    repo = cfg.repo
    result = WritebackResult(outcome="")
    result.checkout_sha = _sha(repo, "HEAD")

    # 1. configure identity + stage ONLY allowed pathspecs
    _git(repo, "config", "user.name", cfg.author_name)
    _git(repo, "config", "user.email", cfg.author_email)
    _git(repo, "add", "--", *cfg.allow)

    staged = _staged_paths(repo)

    # 2. reject unexpected / forbidden staged paths
    bad = [p for p in staged if _is_forbidden(p) or not _matches_any(p, cfg.allow)]
    if bad:
        _git(repo, "reset", "-q")
        result.conflicting_paths = sorted(bad)
        _emit(result, UNEXPECTED_CHANGED_PATH)
        result.outcome = UNEXPECTED_CHANGED_PATH
        return result

    # 3. no material change -> success without commit/push/pages
    if not staged:
        _emit(result, NO_CHANGES)
        _emit(result, PAGES_DISPATCH_SKIPPED_NO_CHANGES)
        result.outcome = NO_CHANGES
        result.ok = True
        return result

    result.changed = True
    result.deploy_changed = any(
        _matches_any(p, cfg.site_paths) for p in staged
    ) if cfg.site_paths else True

    # 4-5. create the local automation commit; record SHAs
    _git(repo, "commit", "-m", cfg.message)
    result.local_commit_sha = _sha(repo, "HEAD")
    original_commit_files = _commit_paths(repo, "HEAD")
    result.origin_sha_initial = _sha(repo, f"{cfg.remote}/{cfg.branch}") if _ref_exists(repo, f"{cfg.remote}/{cfg.branch}") else ""

    fires = 0
    attempt = 0
    rebased = False
    while True:
        # 8. fetch immediately before push
        _git(repo, "fetch", cfg.remote, cfg.branch)
        upstream = f"{cfg.remote}/{cfg.branch}"
        result.origin_sha_latest = _sha(repo, upstream)

        # 9/10. rebase iff origin advanced beyond what HEAD already contains
        contains = _git(repo, "merge-base", "--is-ancestor", upstream, "HEAD", check=False).returncode == 0
        if not contains:
            _emit(result, UPSTREAM_ADVANCED)
            if not _rebase(cfg, result):
                return result  # rebase_conflict already emitted + repo restored
            rebased = True
            result.rebased_commit_sha = _sha(repo, "HEAD")
            # 11. rerun required validation after a successful rebase
            if cfg.validate:
                if not _run_validation(repo, cfg.validate, result):
                    _git(repo, "reset", "--hard", result.local_commit_sha, check=False)
                    _emit(result, VALIDATION_FAILED_AFTER_REBASE)
                    result.outcome = VALIDATION_FAILED_AFTER_REBASE
                    return result
                _emit(result, VALIDATION_SUCCESS_AFTER_REBASE)
            # re-verify the rebased commit still touches only allowed paths
            rebased_files = _commit_paths(repo, "HEAD")
            bad = [p for p in rebased_files if _is_forbidden(p) or not _matches_any(p, cfg.allow)]
            if bad:
                _git(repo, "reset", "--hard", result.local_commit_sha, check=False)
                result.conflicting_paths = sorted(bad)
                _emit(result, UNEXPECTED_CHANGED_PATH)
                result.outcome = UNEXPECTED_CHANGED_PATH
                return result

        # test-only: simulate a concurrent push landing right before ours
        if cfg.test_hook_before_push and fires < cfg.test_hook_fires:
            fires += 1
            subprocess.run(cfg.test_hook_before_push, shell=True, cwd=str(repo))

        push = _git(repo, "push", cfg.remote, f"HEAD:{cfg.branch}", check=False)
        if push.returncode == 0:
            result.pushed_sha = _sha(repo, "HEAD")
            result.retry_number = attempt
            token = PUSH_SUCCESS_AFTER_RETRY if (rebased or attempt > 0) else PUSH_SUCCESS_FIRST_ATTEMPT
            _emit(result, token)
            result.outcome = token
            result.ok = True
            _dispatch_pages(cfg, result)
            return result

        # non-fast-forward rejection: bounded retry
        attempt += 1
        if attempt > cfg.max_retries:
            _emit(result, RETRY_EXHAUSTED)
            _emit(result, PAGES_DISPATCH_SKIPPED_PUSH_FAILURE)
            result.retry_number = attempt
            result.outcome = RETRY_EXHAUSTED
            return result
        # loop: fetch, rebase onto the newly advanced upstream, validate, retry


def _ref_exists(repo: Path, ref: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0


def _rebase(cfg: WritebackConfig, result: WritebackResult) -> bool:
    """Rebase the single bot commit onto the advanced upstream. Returns True on a clean,
    policy-safe rebase; on any conflict emits rebase_conflict, restores the repo, returns False.

    Two things count as a conflict:
      * a real git rebase conflict (overlapping edits), and
      * a git-clean rebase whose replayed commit shares ANY modified path with the upstream
        commit(s) -- two jobs touched the same generated/evidence/state/catalog file. Per the
        conflict policy such shared files are never silently merged; we fail and let the next
        deterministic scheduled run recalculate against current main.
    """
    repo = cfg.repo
    upstream = f"{cfg.remote}/{cfg.branch}"
    base = result.checkout_sha
    my_files = set(_commit_paths(repo, result.local_commit_sha))
    upstream_files = {
        ln.strip() for ln in _git(repo, "diff", "--name-only", base, upstream).stdout.splitlines() if ln.strip()
    }

    proc = _git(repo, "rebase", upstream, check=False)
    if proc.returncode != 0:
        conflicts = sorted({
            ln.strip() for ln in _git(repo, "diff", "--name-only", "--diff-filter=U").stdout.splitlines() if ln.strip()
        })
        _git(repo, "rebase", "--abort", check=False)
        _git(repo, "reset", "--hard", result.local_commit_sha, check=False)
        result.conflicting_paths = conflicts or sorted(my_files & upstream_files)
        _emit(result, REBASE_CONFLICT)
        result.outcome = REBASE_CONFLICT
        return False

    shared = sorted(my_files & upstream_files)
    if shared:
        # clean auto-merge but two jobs modified the same protected file -> do NOT silently keep it
        _git(repo, "reset", "--hard", result.local_commit_sha, check=False)
        result.conflicting_paths = shared
        _emit(result, REBASE_CONFLICT)
        result.outcome = REBASE_CONFLICT
        return False

    _emit(result, REBASE_SUCCESS)
    return True


def _write_github_output(result: WritebackResult) -> None:
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        return
    try:
        with open(out_path, "a", encoding="utf-8") as handle:
            handle.write(f"outcome={result.outcome}\n")
            handle.write(f"changed={'true' if result.changed else 'false'}\n")
            handle.write(f"deploy_changed={'true' if result.deploy_changed else 'false'}\n")
            handle.write(f"pushed_sha={result.pushed_sha}\n")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Conflict-safe automation writeback to a branch.")
    parser.add_argument("--repo", default=".", help="Repository root (default: cwd).")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--message", required=True)
    parser.add_argument("--allow", action="append", default=[], help="git pathspec to stage (repeatable).")
    parser.add_argument("--site-path", action="append", default=[], dest="site_paths",
                        help="allowed subset that affects the site; Pages dispatched only when one changes. "
                             "Default (none given): any material push dispatches Pages.")
    parser.add_argument("--validate", action="append", default=[], help="command to rerun after a rebase (repeatable).")
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--pages-cmd", default=None, help="command dispatched after a confirmed site-affecting push.")
    parser.add_argument("--author-name", default="github-actions[bot]")
    parser.add_argument("--author-email", default="41898282+github-actions[bot]@users.noreply.github.com")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--test-hook-before-push", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--test-hook-fires", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if not args.allow:
        parser.error("at least one --allow pathspec is required")

    cfg = WritebackConfig(
        repo=Path(args.repo).resolve(),
        message=args.message,
        allow=args.allow,
        validate=args.validate,
        site_paths=args.site_paths,
        max_retries=args.max_retries,
        branch=args.branch,
        remote=args.remote,
        pages_cmd=args.pages_cmd,
        author_name=args.author_name,
        author_email=args.author_email,
        test_hook_before_push=args.test_hook_before_push,
        test_hook_fires=args.test_hook_fires,
    )
    try:
        result = run_writeback(cfg)
    except WritebackError as exc:
        print(f"WRITEBACK_OUTCOME: error", flush=True)
        sys.stderr.write(str(exc) + "\n")
        return 3

    print("WRITEBACK_SUMMARY: " + json.dumps(result.as_dict(), ensure_ascii=False), flush=True)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
    _write_github_output(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
