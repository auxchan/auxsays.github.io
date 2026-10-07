#!/usr/bin/env python3
"""The merge authority. A pull request may not be merged while its CI is red.

AUX-013 existed because that rule was only ever written down. On 2026-10-07 it was
broken exactly as predicted: ci-integrity run 37626793286 concluded failure at
13:29:27Z for PR #163, and #163 merged nineteen seconds later at 13:29:46Z. The
status was read and the merge was issued as one uninterrupted gesture, so nothing
stood between knowing and doing.

Server-side enforcement was measured and is unavailable here; see AUX-013 in
docs/ENGINEERING_LEDGER.md for the three probes. This script is the repo-owned
substitute, and its whole design is that reading and merging are separated by a
gate that no flag can turn off:

  * the required run is resolved for the EXACT current head SHA, never for a branch
  * each matching run has its own head_sha re-verified, so a filter is not trusted
  * a red run for this commit can never be overridden by dispatching a greener one
  * absence of a run is a refusal, never a pass
  * the head is re-read immediately before merging, and the merge itself carries the
    SHA as a lease so the server refuses it if the head moved in between

There is deliberately no override flag. If this script refuses, the answer is to fix
the commit, not to reach past the gate.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field

REPO = "auxchan/auxsays.github.io"
GOVERNED_WORKFLOW_PATH = ".github/workflows/ci-integrity.yml"
EXPECTED_BASE = "main"
MERGE_METHOD = "squash"

# Exit codes. 1 is a refusal (the normal, useful outcome); 2 is this script failing.
ALLOWED = 0
REFUSED = 1
ERROR = 2

# A run in any of these states has not decided yet. Merging now would be merging
# into the unknown, so it is a refusal rather than a wait.
NON_TERMINAL = frozenset({"queued", "in_progress", "waiting", "pending", "requested"})

# Conclusions that are a positive red signal for this exact commit. Once one of
# these exists it is never discarded, because discarding it is what #163 did.
FAILING = frozenset({"failure", "timed_out", "startup_failure", "action_required"})

# Terminal but not evidence of success. Green must be asserted, not inferred from
# the absence of red: a skipped or cancelled run proves nothing was verified.
INCONCLUSIVE = frozenset({"cancelled", "skipped", "neutral", "stale"})


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    code: str
    detail: str = ""
    head_sha: str | None = None
    runs: tuple = field(default=())

    def render(self) -> str:
        word = "ALLOW" if self.allowed else "REFUSE"
        head = (self.head_sha or "?")[:12]
        return f"{word}  {self.code}  head={head}  {self.detail}".rstrip()


class GhClient:
    """Thin gh-api transport. Replaced wholesale by the tests."""

    def __init__(self, repo: str = REPO) -> None:
        self.repo = repo

    def _api(self, path: str, method: str = "GET", body: dict | None = None) -> dict:
        cmd = ["gh", "api", "-X", method, f"repos/{self.repo}/{path}"]
        if body is not None:
            cmd += ["--input", "-"]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace",
                              input=json.dumps(body) if body is not None else None)
        if proc.returncode != 0:
            raise RuntimeError(f"gh api {method} {path} failed: {proc.stderr.strip()[:400]}")
        return json.loads(proc.stdout or "{}")

    def pull_request(self, number: int) -> dict:
        return self._api(f"pulls/{number}")

    def workflow_runs(self, head_sha: str) -> list[dict]:
        # Query BY SHA. There is no branch in this request on purpose: a branch
        # name would happily hand back a green run for a commit nobody is merging.
        page = self._api(f"actions/runs?head_sha={head_sha}&per_page=100")
        return list(page.get("workflow_runs") or [])

    def merge(self, number: int, head_sha: str, method: str) -> dict:
        # sha is the lease. GitHub refuses with 409 if the head is no longer this.
        return self._api(f"pulls/{number}/merge", method="PUT",
                         body={"sha": head_sha, "merge_method": method})


def governed_runs(runs: list[dict], head_sha: str, workflow_path: str) -> list[dict]:
    """The runs of the governed workflow that belong to EXACTLY this commit.

    Each run has its own head_sha compared here even though the API was asked to
    filter by it. A query parameter is a request, not a guarantee, and the one thing
    this gate must never do is accept a verdict earned by a different commit.
    """
    return [r for r in runs
            if (r.get("path") or "") == workflow_path
            and (r.get("head_sha") or "") == head_sha]


def decide(pr: dict, head_sha: str | None, runs: list[dict], *,
           base: str = EXPECTED_BASE, workflow_path: str = GOVERNED_WORKFLOW_PATH) -> Verdict:
    """Pure. Every refusal this gate can issue is decided here and nowhere else."""
    if not head_sha:
        return Verdict(False, "no_head_sha", "the pull request head could not be resolved")

    state = (pr.get("state") or "").lower()
    if state != "open":
        merged = " (already merged)" if pr.get("merged") else ""
        return Verdict(False, "pr_not_open", f"state={state or 'unknown'}{merged}", head_sha)

    if pr.get("draft"):
        return Verdict(False, "pr_is_draft", "a draft pull request is not a merge candidate", head_sha)

    actual_base = ((pr.get("base") or {}).get("ref")) or ""
    if actual_base != base:
        return Verdict(False, "wrong_base", f"base={actual_base or 'unknown'} expected={base}", head_sha)

    # mergeable is computed asynchronously, so None means "not known yet". Unknown
    # is a refusal: this gate never merges on a field it has not actually read.
    if pr.get("mergeable") is not True:
        got = "unknown" if pr.get("mergeable") is None else "false"
        state_word = pr.get("mergeable_state") or "unknown"
        return Verdict(False, "pr_not_mergeable",
                       f"mergeable={got} mergeable_state={state_word}", head_sha)

    mine = governed_runs(runs, head_sha, workflow_path)
    if not mine:
        return Verdict(False, "no_required_run",
                       f"no {workflow_path} run exists for this commit", head_sha)

    pending = [r for r in mine
               if (r.get("status") or "").lower() in NON_TERMINAL or not r.get("conclusion")]
    if pending:
        shown = ", ".join(f"{r.get('id')}:{r.get('status')}" for r in pending[:4])
        return Verdict(False, "run_incomplete", f"still deciding: {shown}", head_sha, tuple(mine))

    conclusions = [(r.get("conclusion") or "").lower() for r in mine]
    red = sorted({c for c in conclusions if c in FAILING})
    if red:
        return Verdict(False, "run_not_success",
                       f"this commit has a failing run: {', '.join(red)}", head_sha, tuple(mine))

    if "success" not in conclusions:
        seen = ", ".join(sorted(set(conclusions))) or "none"
        return Verdict(False, "run_not_success",
                       f"no successful run; conclusions={seen}", head_sha, tuple(mine))

    unknown = sorted({c for c in conclusions if c != "success" and c not in INCONCLUSIVE})
    if unknown:
        return Verdict(False, "run_conclusion_unrecognised",
                       f"unrecognised conclusion: {', '.join(unknown)}", head_sha, tuple(mine))

    return Verdict(True, "required_ci_success_for_current_head",
                   f"{len(mine)} governed run(s) green for this commit", head_sha, tuple(mine))


def guarded_merge(client, number: int, *, base: str = EXPECTED_BASE,
                  workflow_path: str = GOVERNED_WORKFLOW_PATH,
                  method: str = MERGE_METHOD, do_merge: bool = False):
    """Read, gate, re-read, then merge under a lease. Returns (verdict, merge_result)."""
    pr = client.pull_request(number)
    head = ((pr.get("head") or {}).get("sha")) or None
    runs = client.workflow_runs(head) if head else []
    verdict = decide(pr, head, runs, base=base, workflow_path=workflow_path)

    if not verdict.allowed or not do_merge:
        return verdict, None

    # The window between deciding and merging is the one #163 fell through. Re-read
    # the head and re-run the whole gate against the fresh view, then let the server
    # enforce the same SHA a second time.
    fresh = client.pull_request(number)
    fresh_head = ((fresh.get("head") or {}).get("sha")) or None
    if fresh_head != head:
        moved = f"head changed {str(head)[:12]} to {str(fresh_head)[:12]} after CI was read"
        return Verdict(False, "head_moved", moved, head, verdict.runs), None

    reaffirmed = decide(fresh, fresh_head, runs, base=base, workflow_path=workflow_path)
    if not reaffirmed.allowed:
        return reaffirmed, None

    return reaffirmed, client.merge(number, head_sha=head, method=method)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Refuse to merge a pull request whose required CI is not green for its head.")
    ap.add_argument("pr", type=int, help="pull request number")
    ap.add_argument("--merge", action="store_true",
                    help="merge if and only if the gate allows it (default: report the verdict)")
    ap.add_argument("--base", default=EXPECTED_BASE)
    ap.add_argument("--workflow", default=GOVERNED_WORKFLOW_PATH)
    ap.add_argument("--merge-method", default=MERGE_METHOD, choices=("squash", "merge", "rebase"))
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args(argv)

    client = GhClient(args.repo)
    try:
        verdict, merged = guarded_merge(client, args.pr, base=args.base,
                                        workflow_path=args.workflow,
                                        method=args.merge_method, do_merge=args.merge)
    except Exception as exc:  # transport or parse failure is never a pass
        print(f"ERROR  guarded_merge could not reach a verdict: {exc}", file=sys.stderr)
        return ERROR

    print(verdict.render())
    if not verdict.allowed:
        return REFUSED
    if merged is not None:
        print(f"MERGED  {merged.get('sha', '?')}  {merged.get('message', '')}".rstrip())
    elif args.merge:
        print("ERROR  gate allowed the merge but no merge was performed", file=sys.stderr)
        return ERROR
    else:
        print(f"      (report only; re-run with --merge to merge PR #{args.pr})")
    return ALLOWED


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(ERROR)
