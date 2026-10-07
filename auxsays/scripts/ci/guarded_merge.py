#!/usr/bin/env python3
"""The merge authority. A pull request may not be merged while its CI is red.

AUX-013 existed because that rule was only ever written down. On 2026-10-07 it was
broken exactly as predicted: ci-integrity run 37626793286 concluded failure at
13:29:27Z for PR #163, and #163 merged nineteen seconds later at 13:29:46Z. The
status was read and the merge was issued as one uninterrupted gesture, so nothing
stood between knowing and doing.

Server-side enforcement was measured and is unavailable here; see AUX-013 in
docs/ENGINEERING_LEDGER.md for the four probes. This script is the repo-owned
substitute, and its whole design is that reading and merging are separated by a
gate the command line cannot route around:

  * the required run is resolved for the EXACT current head SHA, never for a branch
  * each matching run has its own head_sha re-verified, so a filter is not trusted
  * red and green are read asymmetrically: a FAILING run vetoes whatever event
    produced it, while the green must come from this pull request's own
    pull_request run -- otherwise cancelling the real run and dispatching the
    same workflow by hand would mint a pass
  * absence of a run is a refusal, never a pass, and a truncated page is absence
  * the head AND the CI result are both re-read immediately before merging, and the
    merge carries the SHA as a lease so the server refuses it if the head moved

The CLI takes a pull request number and --merge. It deliberately exposes no way to
name a different workflow, base or repository: an adversarial review pointed out
that --workflow turned this script into its own override flag, because every other
workflow in the repo is green on every commit by virtue of never having run.

Known residuals are named in AUX-013. The largest: a green run proves the workflow
file IN THE PULL REQUEST passed, so a pull request that edits ci-integrity.yml
supplies its own verdict. That is true of PR-triggered CI generally.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field

REPO = "auxchan/auxsays.github.io"
GOVERNED_WORKFLOW_PATH = ".github/workflows/ci-integrity.yml"
GOVERNED_EVENT = "pull_request"
EXPECTED_BASE = "main"
MERGE_METHOD = "squash"

# Exit codes. 1 is a refusal (the normal, useful outcome); 2 is this script failing.
ALLOWED = 0
REFUSED = 1
ERROR = 2

# GitHub computes `mergeable` asynchronously and answers null until it has. Null is
# not a refusal to accept at face value, it is a question not yet answered, so the
# gate asks again a bounded number of times before giving up. Without this the first
# invocation on a fresh head usually refuses, which teaches people to use gh instead.
MERGEABILITY_ATTEMPTS = 4
MERGEABILITY_WAIT_SECONDS = 2.0

# A run in any of these states has not decided yet. Merging now would be merging
# into the unknown, so it is a refusal rather than a wait.
NON_TERMINAL = frozenset({"queued", "in_progress", "waiting", "pending", "requested"})

# Conclusions that are a positive red signal for this exact commit. A later run with
# a new id never erases one of these. (A re-run of the SAME run does replace its
# conclusion in place -- GitHub reports only the latest attempt -- so this protects
# against dispatching a second run, not against re-running the first.)
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
        runs = list(page.get("workflow_runs") or [])
        total = page.get("total_count")
        if isinstance(total, int) and total > len(runs):
            # The list is newest-first, so a truncated page drops the OLDEST runs --
            # exactly where an earlier red would be. A partial answer is not an answer.
            raise RuntimeError(
                f"run list truncated for {head_sha[:12]}: {len(runs)} of {total} returned")
        return runs

    def merge(self, number: int, head_sha: str, method: str) -> dict:
        # sha is the lease. GitHub refuses with 409 if the head is no longer this.
        return self._api(f"pulls/{number}/merge", method="PUT",
                         body={"sha": head_sha, "merge_method": method})


def commit_runs(runs: list[dict], head_sha: str,
                workflow_path: str = GOVERNED_WORKFLOW_PATH) -> list[dict]:
    """Every run of the governed workflow for EXACTLY this commit, whatever triggered it.

    Red is read from this wider set and green from the narrower one below. The
    asymmetry is deliberate: a failure is a fact about the commit no matter which
    event produced it, while a pass has to be the pass this pull request earned.
    """
    return [r for r in runs
            if (r.get("path") or "") == workflow_path
            and (r.get("head_sha") or "") == head_sha]


def governed_runs(runs: list[dict], head_sha: str, number: int | None = None,
                  workflow_path: str = GOVERNED_WORKFLOW_PATH) -> list[dict]:
    """The runs of the governed workflow that belong to EXACTLY this commit.

    Each run has its own head_sha compared here even though the API was asked to
    filter by it. A query parameter is a request, not a guarantee, and the one thing
    this gate must never do is accept a verdict earned by a different commit.

    The event must be pull_request. The same workflow dispatched by hand on the same
    commit is a different question being answered, and accepting it would let anyone
    manufacture a green for a head whose pull-request CI never passed.

    A run names the pull requests it belongs to. When that list is populated it must
    contain this one -- two pull requests can share a head branch with different
    bases, and only one of them was actually tested. When it is empty GitHub is not
    telling us, and an empty list is not evidence of a mismatch.
    """
    kept = []
    for r in runs:
        if (r.get("path") or "") != workflow_path:
            continue
        if (r.get("head_sha") or "") != head_sha:
            continue
        if (r.get("event") or "") != GOVERNED_EVENT:
            continue
        attached = [p.get("number") for p in (r.get("pull_requests") or [])]
        if number is not None and attached and number not in attached:
            continue
        kept.append(r)
    return kept


def decide(pr: dict, head_sha: str | None, runs: list[dict], *, number: int | None = None,
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

    merge_state = pr.get("mergeable_state") or "unknown"
    if pr.get("mergeable") is None:
        return Verdict(False, "mergeability_unknown",
                       "GitHub has not finished computing mergeability", head_sha)
    if pr.get("mergeable") is not True:
        return Verdict(False, "pr_not_mergeable",
                       f"mergeable=false mergeable_state={merge_state}", head_sha)

    for_commit = commit_runs(runs, head_sha, workflow_path)
    # A failing run vetoes first, before the gate even asks whether the run it wants
    # exists. Reporting "no required run" for a commit that demonstrably failed would
    # describe the weaker fact.
    red = sorted({(r.get("conclusion") or "").lower() for r in for_commit
                  if (r.get("conclusion") or "").lower() in FAILING})
    if red:
        return Verdict(False, "run_not_success",
                       f"this commit has a failing run: {', '.join(red)}",
                       head_sha, tuple(for_commit))

    mine = governed_runs(runs, head_sha, number, workflow_path)
    if not mine:
        return Verdict(False, "no_required_run",
                       f"no {workflow_path} {GOVERNED_EVENT} run exists for this commit", head_sha)

    pending = [r for r in mine
               if (r.get("status") or "").lower() in NON_TERMINAL or not r.get("conclusion")]
    if pending:
        shown = ", ".join(f"{r.get('id')}:{r.get('status')}" for r in pending[:4])
        return Verdict(False, "run_incomplete", f"still deciding: {shown}", head_sha, tuple(mine))

    conclusions = [(r.get("conclusion") or "").lower() for r in mine]
    if "success" not in conclusions:
        seen = ", ".join(sorted(set(conclusions))) or "none"
        return Verdict(False, "run_not_success",
                       f"no successful run; conclusions={seen}", head_sha, tuple(mine))

    unknown = sorted({c for c in conclusions if c != "success" and c not in INCONCLUSIVE})
    if unknown:
        return Verdict(False, "run_conclusion_unrecognised",
                       f"unrecognised conclusion: {', '.join(unknown)}", head_sha, tuple(mine))

    # mergeable_state is reported, not gated. "behind" means the base moved since CI
    # ran, which in this repo is normal: four workflows push to main all day. See the
    # residual in AUX-013 -- refusing it would mean rebasing before every merge.
    return Verdict(True, "required_ci_success_for_current_head",
                   f"{len(mine)} governed run(s) green for this commit; "
                   f"mergeable_state={merge_state}", head_sha, tuple(mine))


def read_pull_request(client, number: int, *, sleep=time.sleep) -> dict:
    """Read the pull request, giving GitHub a bounded chance to compute mergeability."""
    pr = client.pull_request(number)
    for _ in range(MERGEABILITY_ATTEMPTS - 1):
        if pr.get("mergeable") is not None or (pr.get("state") or "").lower() != "open":
            return pr
        sleep(MERGEABILITY_WAIT_SECONDS)
        pr = client.pull_request(number)
    return pr


def guarded_merge(client, number: int, *, base: str = EXPECTED_BASE,
                  workflow_path: str = GOVERNED_WORKFLOW_PATH,
                  method: str = MERGE_METHOD, do_merge: bool = False, sleep=time.sleep):
    """Read, gate, re-read everything, then merge under a lease."""
    pr = read_pull_request(client, number, sleep=sleep)
    head = ((pr.get("head") or {}).get("sha")) or None
    runs = client.workflow_runs(head) if head else []
    verdict = decide(pr, head, runs, number=number, base=base, workflow_path=workflow_path)

    if not verdict.allowed or not do_merge:
        return verdict, None

    # The window between deciding and merging is the one #163 fell through. BOTH
    # halves of the view are re-read: the pull request and the CI result. Re-reading
    # only the head would leave a second window of the same shape, because a run can
    # be re-run to red while its commit stands still.
    fresh = read_pull_request(client, number, sleep=sleep)
    fresh_head = ((fresh.get("head") or {}).get("sha")) or None
    if fresh_head != head:
        moved = f"head changed {str(head)[:12]} to {str(fresh_head)[:12]} after CI was read"
        return Verdict(False, "head_moved", moved, head, verdict.runs), None

    fresh_runs = client.workflow_runs(fresh_head)
    reaffirmed = decide(fresh, fresh_head, fresh_runs, number=number, base=base,
                        workflow_path=workflow_path)
    if not reaffirmed.allowed:
        return reaffirmed, None

    try:
        result = client.merge(number, head_sha=head, method=method)
    except RuntimeError as exc:
        # The server declined the lease, or the merge otherwise failed. That is a
        # refusal to merge, not this script malfunctioning, so it exits 1 and says why.
        return Verdict(False, "merge_declined_by_server", str(exc)[:300], head,
                       reaffirmed.runs), None
    return reaffirmed, result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Refuse to merge a pull request whose required CI is not green for its head.")
    ap.add_argument("pr", type=int, help="pull request number")
    ap.add_argument("--merge", action="store_true",
                    help="merge if and only if the gate allows it (default: report the verdict)")
    # Nothing else. --workflow, --base and --repo used to live here for convenience
    # and an adversarial review showed they were an override flag: every other
    # workflow in this repo is green on every commit, having never run on it.
    args = ap.parse_args(argv)

    client = GhClient(REPO)
    try:
        verdict, merged = guarded_merge(client, args.pr, do_merge=args.merge)
    except Exception as exc:  # transport or parse failure is never a pass
        print(f"ERROR  guarded_merge could not reach a verdict: {exc}", file=sys.stderr)
        return ERROR

    print(verdict.render())
    if not verdict.allowed:
        return REFUSED
    if merged is not None:
        print(f"MERGED  {merged.get('sha', '?')}  {merged.get('message', '')}".rstrip())
        return ALLOWED
    if args.merge:
        print("ERROR  gate allowed the merge but no merge was performed", file=sys.stderr)
        return ERROR
    print(f"        NOT MERGED. This was a report. To merge, re-run with --merge.")
    print(f"        Do not chain this into another merge command: reading the status")
    print(f"        and merging as one gesture is exactly how PR #163 went in red.")
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
