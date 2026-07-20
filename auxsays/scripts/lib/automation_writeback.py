#!/usr/bin/env python3
"""Shared, deterministic, conflict-safe writeback for AUXSAYS automation workflows.

Every workflow that commits generated outputs to ``main`` (patch evidence collection,
patch ingestion, the DaVinci writers, ...) previously did a plain ``git add`` /
``git commit`` / ``git push`` followed by a single ``gh workflow run pages.yml``. Two gaps:

  1. RACE: a *separate* workflow (patch-ingest) can push to ``main`` between another
     workflow's checkout and its push -> non-fast-forward rejection -> failed run ->
     delayed publication. The shared concurrency group reduces but cannot eliminate this,
     so a pre-push fetch/rebase/retry mechanism is mandatory.
  2. UNDEPLOYED COMMIT: the content push can succeed while the single Pages dispatch fails.
     The pushed revision then stays undeployed, and later no-change runs (which see no file
     changes) never redeploy it. This is repaired here with bounded Pages-dispatch retries
     plus a deterministic no-change deployment-recovery path that re-dispatches Pages when
     the exact current ``origin/main`` SHA is not already a completed+success ``pages.yml``
     deployment -- WITHOUT repeating the push or creating an empty commit.

This module performs, against an ALREADY-checked-out repo whose working tree already holds
the freshly generated changes:

  * stage ONLY explicitly permitted pathspecs; reject any unexpected/forbidden staged path
  * empty staged diff -> no_changes; then, IFF deploy-recovery is enabled for this workflow,
    verify the current main SHA is deployed and re-dispatch Pages if not (never on every run)
  * create the bot commit; fetch origin/<branch> immediately before each push; rebase the
    single bot commit when origin advanced; rerun validation + re-verify allowed paths;
    push with a bounded retry limit
  * after a confirmed successful material push, dispatch Pages with bounded retries and
    deterministic backoff; on final dispatch failure set deployment_pending and fail visibly
    while preserving pushed / pushed_sha (a deployment-dispatch failure is NOT a push failure)

It never force-pushes, never uses ``--ours``/``--theirs`` or ``-X ours``/``-X theirs``, and
never silently resolves a conflict on a shared generated/evidence/state/catalog file.

Outcome tokens are emitted one-per-line (``WRITEBACK_OUTCOME:``) plus a final
``WRITEBACK_SUMMARY:`` JSON line; inside GitHub Actions, outputs (outcome / changed /
deploy_changed / pushed / pushed_sha / deployment_pending) are written to ``$GITHUB_OUTPUT``
and a pending-deployment note to ``$GITHUB_STEP_SUMMARY``.

CLI (workflows) and importable ``run_writeback(config)`` (tests). Pages status queries and
sleeps are injectable so tests are deterministic and never sleep or hit the network.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

FORBIDDEN_PATH_SUBSTRINGS = (
    "/_site/", "_site/", "node_modules/", ".jekyll-cache/", "__pycache__/",
)
FORBIDDEN_PATH_GLOBS = (
    "*.pyc", "*.tmp", "AGENTS.md", "CLAUDE.md", "**/AGENTS.md", "**/CLAUDE.md",
)

DEFAULT_PAGES_STATUS_CMD = (
    "gh run list --workflow pages.yml --branch main --limit 30 "
    "--json databaseId,headSha,headBranch,status,conclusion"
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
PAGES_DISPATCH_ATTEMPT = "pages_dispatch_attempt"
PAGES_DISPATCH_RETRY = "pages_dispatch_retry"
PAGES_DISPATCH_SUCCESS = "pages_dispatch_success"
PAGES_DISPATCH_FAILED = "pages_dispatch_failed"
PAGES_DISPATCH_SKIPPED_NO_CHANGES = "pages_dispatch_skipped_no_changes"
PAGES_DISPATCH_SKIPPED_PUSH_FAILURE = "pages_dispatch_skipped_push_failure"
DEPLOYMENT_CURRENT = "deployment_current"
DEPLOYMENT_MISSING = "deployment_missing"


@dataclass
class WritebackConfig:
    repo: Path
    message: str
    allow: list[str]
    validate: list[str] = field(default_factory=list)
    site_paths: list[str] = field(default_factory=list)      # subset of allow that affects the site
    max_retries: int = 5
    branch: str = "main"
    remote: str = "origin"
    pages_cmd: str | None = None
    pages_workflow: str = "pages.yml"
    pages_ref: str = "main"
    pages_max_attempts: int = 3
    pages_backoff: list[int] = field(default_factory=lambda: [5, 15])  # delay after attempts 1,2
    author_name: str = "github-actions[bot]"
    author_email: str = "41898282+github-actions[bot]@users.noreply.github.com"
    # no-change deployment recovery
    deploy_recovery: bool = False
    recovery_site_paths: list[str] = field(default_factory=list)   # main HEAD must touch one of these
    recovery_commit_grep: str | None = None                        # ... and its message must contain this
    pages_status_cmd: str = DEFAULT_PAGES_STATUS_CMD
    # injectables (tests)
    sleep_fn: Callable[[float], None] = time.sleep
    test_hook_before_push: str | None = None
    test_hook_fires: int = 0


@dataclass
class WritebackResult:
    outcome: str
    outcomes: list[str] = field(default_factory=list)
    changed: bool = False
    deploy_changed: bool = False
    pushed: bool = False
    deployment_pending: bool = False
    checkout_sha: str = ""
    origin_sha_initial: str = ""
    origin_sha_latest: str = ""
    local_commit_sha: str = ""
    rebased_commit_sha: str = ""
    pushed_sha: str = ""
    retry_number: int = 0
    conflicting_paths: list[str] = field(default_factory=list)
    validation: list[dict] = field(default_factory=list)
    pages_attempts: int = 0
    pages_backoff_applied: list[int] = field(default_factory=list)
    pages_dispatched: bool = False
    ok: bool = False

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "outcome", "outcomes", "changed", "deploy_changed", "pushed", "deployment_pending",
            "checkout_sha", "origin_sha_initial", "origin_sha_latest", "local_commit_sha",
            "rebased_commit_sha", "pushed_sha", "retry_number", "conflicting_paths", "validation",
            "pages_attempts", "pages_backoff_applied", "pages_dispatched", "ok",
        )}


class WritebackError(RuntimeError):
    def __init__(self, outcome: str, detail: str = "") -> None:
        super().__init__(f"{outcome}: {detail}" if detail else outcome)
        self.outcome = outcome
        self.detail = detail


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise WritebackError("git_error", f"git {' '.join(args)} -> rc={proc.returncode}: {proc.stderr.strip()}")
    return proc


def _sha(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _ref_exists(repo: Path, ref: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0


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
    for cmd in commands:
        proc = subprocess.run(cmd, shell=True, cwd=str(repo), capture_output=True, text=True)
        result.validation.append({"cmd": cmd, "exit_code": proc.returncode})
        print(f"WRITEBACK_VALIDATE: rc={proc.returncode} cmd={cmd}", flush=True)
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout[-2000:] + "\n" + proc.stderr[-2000:] + "\n")
            return False
    return True


# --- Pages status query + bounded dispatch -----------------------------------

def _pages_runs(cfg: WritebackConfig) -> tuple[list[dict], bool]:
    """Return (runs, query_ok). query_ok is False when the status command itself failed
    (e.g. missing token) -- callers must NOT treat that as 'deployed'."""
    if not cfg.pages_status_cmd:
        return [], False
    proc = subprocess.run(cfg.pages_status_cmd, shell=True, cwd=str(cfg.repo), capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(f"pages status query failed rc={proc.returncode}: {proc.stderr.strip()}\n")
        return [], False
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return [], False
    return (data, True) if isinstance(data, list) else ([], True)


def _sha_deployed(cfg: WritebackConfig, sha: str) -> bool:
    """True ONLY when a pages.yml run for exactly this SHA on the target branch is completed
    with conclusion success. Older SHAs, other branches, queued/in-progress, and
    failed/cancelled/skipped/timed-out runs are all insufficient. The status command already
    scopes to `--workflow pages.yml --branch main`; we re-verify branch + exact SHA + terminal
    success here so a mis-scoped command can never yield a false positive."""
    runs, ok = _pages_runs(cfg)
    if not ok:
        return False
    for run in runs:
        if (str(run.get("headSha")) == sha
                and str(run.get("headBranch")) == cfg.pages_ref
                and str(run.get("status")) == "completed"
                and str(run.get("conclusion")) == "success"):
            return True
    return False


def _dispatch_pages_bounded(cfg: WritebackConfig, result: WritebackResult, pushed_sha: str) -> bool:
    """Dispatch Pages with bounded retries and deterministic backoff. Returns True on a
    confirmed dispatch; on final failure sets deployment_pending, records the pending
    deployment to the step summary, and returns False. Never repeats the git push, never
    creates a commit, never force-pushes."""
    origin_sha = _sha(cfg.repo, f"{cfg.remote}/{cfg.branch}") if _ref_exists(cfg.repo, f"{cfg.remote}/{cfg.branch}") else pushed_sha
    for attempt in range(1, cfg.pages_max_attempts + 1):
        result.pages_attempts = attempt
        proc = subprocess.run(cfg.pages_cmd, shell=True, cwd=str(cfg.repo), capture_output=True, text=True)
        print(f"WRITEBACK_PAGES: {PAGES_DISPATCH_ATTEMPT} attempt={attempt} rc={proc.returncode} "
              f"workflow={cfg.pages_workflow} ref={cfg.pages_ref} pushed_sha={pushed_sha} origin_main={origin_sha}", flush=True)
        _emit(result, PAGES_DISPATCH_ATTEMPT)
        if proc.returncode == 0:
            result.pages_dispatched = True
            _emit(result, PAGES_DISPATCH_SUCCESS)
            return True
        sys.stderr.write(f"pages dispatch attempt {attempt} failed rc={proc.returncode}: {proc.stderr.strip()}\n")
        if attempt < cfg.pages_max_attempts:
            delay = cfg.pages_backoff[attempt - 1] if attempt - 1 < len(cfg.pages_backoff) else (cfg.pages_backoff[-1] if cfg.pages_backoff else 0)
            result.pages_backoff_applied.append(delay)
            _emit(result, PAGES_DISPATCH_RETRY)
            if delay:
                cfg.sleep_fn(delay)
    _emit(result, PAGES_DISPATCH_FAILED)
    result.deployment_pending = True
    _write_step_summary(cfg, pushed_sha, origin_sha)
    return False


def _write_step_summary(cfg: WritebackConfig, pushed_sha: str, origin_sha: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as h:
            h.write("### ⚠️ Deployment pending\n\n")
            h.write("The content push SUCCEEDED but the Pages deployment dispatch failed after "
                    f"{cfg.pages_max_attempts} attempts. The pushed revision is on `{cfg.branch}` but not deployed.\n\n")
            h.write(f"- pushed_sha: `{pushed_sha}`\n- origin/{cfg.branch}: `{origin_sha}`\n"
                    f"- workflow: `{cfg.pages_workflow}` ref `{cfg.pages_ref}`\n")
            h.write(f"- recover: `gh workflow run {cfg.pages_workflow} --ref {cfg.pages_ref}` "
                    "(or the next scheduled recovery run will redeploy it automatically).\n")
    except OSError:
        pass


# --- rebase ------------------------------------------------------------------

def _rebase(cfg: WritebackConfig, result: WritebackResult) -> bool:
    """Rebase the single bot commit onto the advanced upstream. True on a clean, policy-safe
    rebase; on any conflict emits rebase_conflict, restores the repo, returns False. A conflict
    is EITHER a real git rebase conflict OR a git-clean rebase whose replayed commit shares any
    modified path with the upstream commits added AFTER this workflow's original base SHA (two
    jobs touched the same generated/evidence/state/catalog file -> never silently merged)."""
    repo = cfg.repo
    upstream = f"{cfg.remote}/{cfg.branch}"
    base = result.checkout_sha
    my_files = set(_commit_paths(repo, result.local_commit_sha))
    # compare only changes AFTER the original base SHA, not all history of those paths
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
        _git(repo, "reset", "--hard", result.local_commit_sha, check=False)
        result.conflicting_paths = shared
        _emit(result, REBASE_CONFLICT)
        result.outcome = REBASE_CONFLICT
        return False

    _emit(result, REBASE_SUCCESS)
    return True


# --- main flow ---------------------------------------------------------------

def _no_change_recovery(cfg: WritebackConfig, result: WritebackResult) -> None:
    """No material change: optionally ensure the exact current main SHA is deployed. Only runs
    for a workflow with configured deploy-recovery responsibility, and only dispatches when the
    current main HEAD is a not-yet-deployed, site-affecting (and, when configured, owned) commit.
    Never dispatches on every no-change run."""
    if not (cfg.deploy_recovery and cfg.pages_cmd):
        _emit(result, PAGES_DISPATCH_SKIPPED_NO_CHANGES)
        return
    _git(cfg.repo, "fetch", cfg.remote, cfg.branch)
    main_sha = _sha(cfg.repo, f"{cfg.remote}/{cfg.branch}")
    result.origin_sha_latest = main_sha
    if _sha_deployed(cfg, main_sha):
        _emit(result, DEPLOYMENT_CURRENT)
        return
    if not _main_head_recoverable(cfg, main_sha):
        # not deployed, but not this workflow's site-deployment responsibility -> abstain
        _emit(result, DEPLOYMENT_CURRENT)
        return
    _emit(result, DEPLOYMENT_MISSING)
    result.deploy_changed = True
    if not _dispatch_pages_bounded(cfg, result, main_sha):
        result.ok = False  # deployment_pending -> fail visibly (push was never the problem here)


def _main_head_recoverable(cfg: WritebackConfig, main_sha: str) -> bool:
    if cfg.recovery_site_paths:
        files = _commit_paths(cfg.repo, main_sha)
        if not any(_matches_any(f, cfg.recovery_site_paths) for f in files):
            return False
    if cfg.recovery_commit_grep:
        msg = _git(cfg.repo, "log", "-1", "--format=%B", main_sha).stdout
        if cfg.recovery_commit_grep not in msg:
            return False
    return True


def run_writeback(cfg: WritebackConfig) -> WritebackResult:
    repo = cfg.repo
    result = WritebackResult(outcome="")
    result.checkout_sha = _sha(repo, "HEAD")

    _git(repo, "config", "user.name", cfg.author_name)
    _git(repo, "config", "user.email", cfg.author_email)
    _git(repo, "add", "--", *cfg.allow)
    staged = _staged_paths(repo)

    bad = [p for p in staged if _is_forbidden(p) or not _matches_any(p, cfg.allow)]
    if bad:
        _git(repo, "reset", "-q")
        result.conflicting_paths = sorted(bad)
        _emit(result, UNEXPECTED_CHANGED_PATH)
        result.outcome = UNEXPECTED_CHANGED_PATH
        return result

    if not staged:
        _emit(result, NO_CHANGES)
        result.outcome = NO_CHANGES
        result.ok = True
        _no_change_recovery(cfg, result)
        return result

    result.changed = True
    result.deploy_changed = any(_matches_any(p, cfg.site_paths) for p in staged) if cfg.site_paths else True

    _git(repo, "commit", "-m", cfg.message)
    result.local_commit_sha = _sha(repo, "HEAD")
    result.origin_sha_initial = _sha(repo, f"{cfg.remote}/{cfg.branch}") if _ref_exists(repo, f"{cfg.remote}/{cfg.branch}") else ""

    fires = 0
    attempt = 0
    rebased = False
    while True:
        _git(repo, "fetch", cfg.remote, cfg.branch)
        upstream = f"{cfg.remote}/{cfg.branch}"
        result.origin_sha_latest = _sha(repo, upstream)

        contains = _git(repo, "merge-base", "--is-ancestor", upstream, "HEAD", check=False).returncode == 0
        if not contains:
            _emit(result, UPSTREAM_ADVANCED)
            if not _rebase(cfg, result):
                return result
            rebased = True
            result.rebased_commit_sha = _sha(repo, "HEAD")
            if cfg.validate:
                if not _run_validation(repo, cfg.validate, result):
                    _git(repo, "reset", "--hard", result.local_commit_sha, check=False)
                    _emit(result, VALIDATION_FAILED_AFTER_REBASE)
                    result.outcome = VALIDATION_FAILED_AFTER_REBASE
                    return result
                _emit(result, VALIDATION_SUCCESS_AFTER_REBASE)
            rebased_files = _commit_paths(repo, "HEAD")
            bad = [p for p in rebased_files if _is_forbidden(p) or not _matches_any(p, cfg.allow)]
            if bad:
                _git(repo, "reset", "--hard", result.local_commit_sha, check=False)
                result.conflicting_paths = sorted(bad)
                _emit(result, UNEXPECTED_CHANGED_PATH)
                result.outcome = UNEXPECTED_CHANGED_PATH
                return result

        if cfg.test_hook_before_push and fires < cfg.test_hook_fires:
            fires += 1
            subprocess.run(cfg.test_hook_before_push, shell=True, cwd=str(repo))

        push = _git(repo, "push", cfg.remote, f"HEAD:{cfg.branch}", check=False)
        if push.returncode == 0:
            result.pushed = True
            result.pushed_sha = _sha(repo, "HEAD")
            result.retry_number = attempt
            token = PUSH_SUCCESS_AFTER_RETRY if (rebased or attempt > 0) else PUSH_SUCCESS_FIRST_ATTEMPT
            _emit(result, token)
            result.outcome = token
            result.ok = True
            # dispatch Pages ONLY after a confirmed site-affecting push
            if cfg.pages_cmd and result.deploy_changed:
                if not _dispatch_pages_bounded(cfg, result, result.pushed_sha):
                    result.ok = False  # pushed, but deployment pending -> fail visibly
            elif cfg.pages_cmd:
                _emit(result, PAGES_DISPATCH_SKIPPED_NO_CHANGES)
            return result

        attempt += 1
        if attempt > cfg.max_retries:
            _emit(result, RETRY_EXHAUSTED)
            _emit(result, PAGES_DISPATCH_SKIPPED_PUSH_FAILURE)
            result.retry_number = attempt
            result.outcome = RETRY_EXHAUSTED
            return result


def _write_github_output(result: WritebackResult) -> None:
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        return
    try:
        with open(out_path, "a", encoding="utf-8") as handle:
            handle.write(f"outcome={result.outcome}\n")
            handle.write(f"changed={'true' if result.changed else 'false'}\n")
            handle.write(f"deploy_changed={'true' if result.deploy_changed else 'false'}\n")
            handle.write(f"pushed={'true' if result.pushed else 'false'}\n")
            handle.write(f"pushed_sha={result.pushed_sha}\n")
            handle.write(f"deployment_pending={'true' if result.deployment_pending else 'false'}\n")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Conflict-safe automation writeback + deployment recovery.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--message", required=True)
    parser.add_argument("--allow", action="append", default=[])
    parser.add_argument("--site-path", action="append", default=[], dest="site_paths")
    parser.add_argument("--validate", action="append", default=[])
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--pages-cmd", default=None)
    parser.add_argument("--pages-workflow", default="pages.yml")
    parser.add_argument("--pages-ref", default="main")
    parser.add_argument("--pages-max-attempts", type=int, default=3)
    parser.add_argument("--pages-backoff", default="5,15", help="comma-separated seconds after attempts 1,2,...")
    parser.add_argument("--deploy-recovery", action="store_true")
    parser.add_argument("--recovery-site-path", action="append", default=[], dest="recovery_site_paths")
    parser.add_argument("--recovery-commit-grep", default=None)
    parser.add_argument("--pages-status-cmd", default=DEFAULT_PAGES_STATUS_CMD)
    parser.add_argument("--author-name", default="github-actions[bot]")
    parser.add_argument("--author-email", default="41898282+github-actions[bot]@users.noreply.github.com")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--test-hook-before-push", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--test-hook-fires", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.allow:
        parser.error("at least one --allow pathspec is required")

    backoff = [int(x) for x in str(args.pages_backoff).split(",") if x.strip()]
    cfg = WritebackConfig(
        repo=Path(args.repo).resolve(), message=args.message, allow=args.allow, validate=args.validate,
        site_paths=args.site_paths, max_retries=args.max_retries, branch=args.branch, remote=args.remote,
        pages_cmd=args.pages_cmd, pages_workflow=args.pages_workflow, pages_ref=args.pages_ref,
        pages_max_attempts=args.pages_max_attempts, pages_backoff=backoff or [5, 15],
        deploy_recovery=args.deploy_recovery, recovery_site_paths=args.recovery_site_paths,
        recovery_commit_grep=args.recovery_commit_grep, pages_status_cmd=args.pages_status_cmd,
        author_name=args.author_name, author_email=args.author_email,
        test_hook_before_push=args.test_hook_before_push, test_hook_fires=args.test_hook_fires,
    )
    try:
        result = run_writeback(cfg)
    except WritebackError as exc:
        print("WRITEBACK_OUTCOME: error", flush=True)
        sys.stderr.write(str(exc) + "\n")
        return 3

    print("WRITEBACK_SUMMARY: " + json.dumps(result.as_dict(), ensure_ascii=False), flush=True)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
    _write_github_output(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
