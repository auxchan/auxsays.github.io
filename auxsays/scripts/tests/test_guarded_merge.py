#!/usr/bin/env python3
"""The merge gate is policy, so it is tested like production code.

AUX-013 was closed by a script that refuses to merge a pull request whose required
CI is not green for its current head. A gate like that is only worth the assertions
behind it: a gate that reads a branch instead of a SHA, or that treats a missing
check as a pass, looks identical from the outside and stops nothing.

Section R1 replays the real recorded shape of PR #163 -- the merge this gate exists
to prevent. R2 enumerates the refusals, R3 the single allow path and the cases that
must not wedge a good commit, R4 the window between reading and merging, R5 the
structure. R6 covers what one bounded adversarial review found after the first
version shipped, which was mostly one theme: the gate was asking a narrower question
than it claimed, and its own command line could re-point it at an easier one.

Offline: no network, no repo writes, no sleeping.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "ci" / "guarded_merge.py"

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def load_gate():
    spec = importlib.util.spec_from_file_location("auxsays_guarded_merge", GATE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses resolves its annotations through sys.modules, so a module loaded
    # by path has to be registered before it is executed or @dataclass raises.
    sys.modules["auxsays_guarded_merge"] = mod
    spec.loader.exec_module(mod)
    return mod


# The real head of PR #163 and the real id/event/conclusion of the run that was
# already red when it merged. Recorded from the API, not invented.
PR163 = 163
PR163_HEAD = "8ea5ce0dbfa50e3ab91feba122de3fb78c169c56"
PR163_RUN = {"id": 37626793286, "path": ".github/workflows/ci-integrity.yml",
             "event": "pull_request", "status": "completed", "conclusion": "failure",
             "head_sha": PR163_HEAD, "pull_requests": [{"number": PR163}]}

OTHER_SHA = "1111111111111111111111111111111111111111"
NO_SLEEP = lambda _seconds: None


def pr(head: str = PR163_HEAD, **over) -> dict:
    """An otherwise perfectly mergeable pull request, so each test varies one thing."""
    base = {"state": "open", "merged": False, "draft": False, "base": {"ref": "main"},
            "head": {"sha": head}, "mergeable": True, "mergeable_state": "clean"}
    base.update(over)
    return base


def run(head: str = PR163_HEAD, conclusion: str = "success", status: str = "completed",
        path: str = ".github/workflows/ci-integrity.yml", rid: int = 1,
        event: str = "pull_request", prs=(PR163,)) -> dict:
    return {"id": rid, "path": path, "event": event, "status": status,
            "conclusion": conclusion, "head_sha": head,
            "pull_requests": [{"number": n} for n in prs]}


class FakeClient:
    """Records every call. The sequences let the view change between the two reads."""

    def __init__(self, pr_sequence, runs, runs_sequence=None, merge_error: str = ""):
        self.pr_sequence = list(pr_sequence)
        self.runs = list(runs)
        self.runs_sequence = [list(r) for r in runs_sequence] if runs_sequence else None
        self.merge_error = merge_error
        self.pr_reads = 0
        self.run_queries: list[str] = []
        self.merges: list[dict] = []

    def pull_request(self, number):
        self.pr_reads += 1
        return self.pr_sequence[min(self.pr_reads - 1, len(self.pr_sequence) - 1)]

    def workflow_runs(self, head_sha):
        self.run_queries.append(head_sha)
        if self.runs_sequence is None:
            return list(self.runs)
        i = min(len(self.run_queries) - 1, len(self.runs_sequence) - 1)
        return list(self.runs_sequence[i])

    def merge(self, number, head_sha, method):
        if self.merge_error:
            raise RuntimeError(self.merge_error)
        self.merges.append({"number": number, "sha": head_sha, "method": method})
        return {"sha": "merged0000", "merged": True, "message": "Pull Request merged"}


def run_suite() -> int:
    gm = load_gate()
    GM = dict(number=PR163)

    print("=" * 92)
    print("R1  the demonstrated failure: PR #163 merged 19s after its CI went red")
    print("=" * 92)
    v = gm.decide(pr(), PR163_HEAD, [PR163_RUN], **GM)
    check("R1.1 the real #163 head and run are refused", not v.allowed, v.render())
    check("R1.2 the refusal names the CI result, not something incidental",
          v.code == "run_not_success", v.code)
    check("R1.3 the refusal reports the failing conclusion", "failure" in v.detail, v.detail)
    client = FakeClient([pr()], [PR163_RUN])
    verdict, merged = gm.guarded_merge(client, PR163, do_merge=True, sleep=NO_SLEEP)
    check("R1.4 asking to merge #163 performs no merge", client.merges == [], str(client.merges))
    check("R1.5 and returns no merge result", merged is None)
    check("R1.6 a red run is not rescued by a green one on the same commit",
          not gm.decide(pr(), PR163_HEAD, [PR163_RUN, run(rid=2)], **GM).allowed)
    check("R1.7 that refusal is still the CI refusal",
          gm.decide(pr(), PR163_HEAD, [PR163_RUN, run(rid=2)], **GM).code == "run_not_success")

    print()
    print("=" * 92)
    print("R2  every state the gate must refuse")
    print("=" * 92)
    cases = [
        ("CI failed", pr(), [run(conclusion="failure")], "run_not_success"),
        ("CI timed out", pr(), [run(conclusion="timed_out")], "run_not_success"),
        ("CI was cancelled", pr(), [run(conclusion="cancelled")], "run_not_success"),
        ("CI was skipped", pr(), [run(conclusion="skipped")], "run_not_success"),
        ("CI is queued", pr(), [run(status="queued", conclusion=None)], "run_incomplete"),
        ("CI is in progress", pr(), [run(status="in_progress", conclusion=None)], "run_incomplete"),
        ("no run at all", pr(), [], "no_required_run"),
        ("only another workflow ran", pr(), [run(path=".github/workflows/pages.yml")],
         "no_required_run"),
        ("the only green run is for an older SHA", pr(), [run(head=OTHER_SHA)], "no_required_run"),
        ("the only green run was dispatched by hand", pr(), [run(event="workflow_dispatch")],
         "no_required_run"),
        ("the only green run was a push-event run", pr(), [run(event="push")], "no_required_run"),
        ("the only green run belongs to a sibling pull request", pr(), [run(prs=(999,))],
         "no_required_run"),
        ("pull request is closed", pr(state="closed"), [run()], "pr_not_open"),
        ("pull request is already merged", pr(state="closed", merged=True), [run()], "pr_not_open"),
        ("pull request is a draft", pr(draft=True), [run()], "pr_is_draft"),
        ("pull request is not mergeable", pr(mergeable=False, mergeable_state="dirty"), [run()],
         "pr_not_mergeable"),
        ("mergeability is still unknown", pr(mergeable=None, mergeable_state="unknown"), [run()],
         "mergeability_unknown"),
        ("base branch is not main", pr(base={"ref": "gh-pages"}), [run()], "wrong_base"),
        ("head cannot be resolved", pr(), [run()], "no_head_sha"),
    ]
    for i, (label, pull, runs, expected) in enumerate(cases, start=1):
        head = None if expected == "no_head_sha" else PR163_HEAD
        got = gm.decide(pull, head, runs, **GM)
        check(f"R2.{i} refuses: {label}", not got.allowed and got.code == expected,
              f"got {got.code}")

    print()
    print("=" * 92)
    print("R3  the one state the gate must allow")
    print("=" * 92)
    ok = gm.decide(pr(), PR163_HEAD, [run()], **GM)
    check("R3.1 current head, green required run, mergeable, correct base is allowed",
          ok.allowed, ok.render())
    check("R3.2 the allow names the current head", ok.head_sha == PR163_HEAD)
    check("R3.3 the allow is attributed to CI success for that head",
          ok.code == "required_ci_success_for_current_head", ok.code)
    check("R3.4 a cancelled run alongside a green one does not wedge a good commit",
          gm.decide(pr(), PR163_HEAD, [run(conclusion="cancelled", rid=9), run()], **GM).allowed)
    check("R3.5 an unrelated workflow failing does not block the merge",
          gm.decide(pr(), PR163_HEAD,
                    [run(), run(path=".github/workflows/pages.yml", conclusion="failure", rid=3)],
                    **GM).allowed)
    check("R3.6 a lone unrecognised conclusion is refused for having no success",
          gm.decide(pr(), PR163_HEAD, [run(conclusion="surprise")], **GM).code == "run_not_success")
    both = gm.decide(pr(), PR163_HEAD, [run(), run(conclusion="surprise", rid=2)], **GM)
    check("R3.7 an unrecognised conclusion beside a green run is still refused",
          not both.allowed and both.code == "run_conclusion_unrecognised", both.code)
    check("R3.8 and the refusal names the conclusion it did not recognise",
          "surprise" in both.detail, both.detail)
    check("R3.9 a run that names no pull request is accepted, since GitHub is not telling us",
          gm.decide(pr(), PR163_HEAD, [run(prs=())], **GM).allowed)
    behind = gm.decide(pr(mergeable_state="behind"), PR163_HEAD, [run()], **GM)
    check("R3.10 a pull request behind its base is allowed, as GitHub allows it", behind.allowed)
    check("R3.11 but the allow reports the state rather than hiding it",
          "behind" in behind.detail, behind.detail)

    print()
    print("=" * 92)
    print("R4  the window between reading CI and merging")
    print("=" * 92)
    moved = FakeClient([pr(PR163_HEAD), pr(OTHER_SHA)], [run()])
    verdict, merged = gm.guarded_merge(moved, PR163, do_merge=True, sleep=NO_SLEEP)
    check("R4.1 a head that moves after CI was read refuses the merge",
          not verdict.allowed and verdict.code == "head_moved", verdict.code)
    check("R4.2 and no merge is attempted", moved.merges == [], str(moved.merges))
    check("R4.3 the head is read twice, not once", moved.pr_reads == 2, str(moved.pr_reads))

    good = FakeClient([pr(), pr()], [run()])
    verdict, merged = gm.guarded_merge(good, PR163, do_merge=True, sleep=NO_SLEEP)
    check("R4.4 a stable green head does merge", verdict.allowed and merged is not None,
          verdict.render())
    check("R4.5 the merge carries the validated SHA as a lease",
          good.merges and good.merges[0]["sha"] == PR163_HEAD, str(good.merges))
    check("R4.6 CI is queried by SHA, never by branch",
          good.run_queries == [PR163_HEAD, PR163_HEAD], str(good.run_queries))
    check("R4.7 the gate re-reads the head before merging", good.pr_reads == 2, str(good.pr_reads))

    # The head can stand still while the CI result moves under it: re-running a run
    # replaces its conclusion in place. Re-reading only the head leaves that window.
    reran = FakeClient([pr(), pr()], [], runs_sequence=[[run()], [run(conclusion="failure")]])
    verdict, merged = gm.guarded_merge(reran, PR163, do_merge=True, sleep=NO_SLEEP)
    check("R4.8 CI going red in the window refuses, even with the head unchanged",
          not verdict.allowed and verdict.code == "run_not_success", verdict.code)
    check("R4.9 and nothing is merged", reran.merges == [])
    check("R4.10 CI is re-read before merging, not reused", len(reran.run_queries) == 2,
          str(reran.run_queries))

    closed_late = FakeClient([pr(), pr(state="closed")], [run()])
    verdict, merged = gm.guarded_merge(closed_late, PR163, do_merge=True, sleep=NO_SLEEP)
    check("R4.11 a pull request closed inside the window is refused",
          not verdict.allowed and verdict.code == "pr_not_open", verdict.code)

    declined = FakeClient([pr(), pr()], [run()], merge_error="HTTP 409 Head branch was modified")
    try:
        verdict, merged = gm.guarded_merge(declined, PR163, do_merge=True, sleep=NO_SLEEP)
    except Exception as exc:  # a crash here is the defect, so name it rather than abort
        verdict, merged = gm.Verdict(False, f"raised:{type(exc).__name__}", str(exc)), None
    check("R4.12 a lease the server rejects is a refusal, not a crash",
          not verdict.allowed and verdict.code == "merge_declined_by_server", verdict.code)
    check("R4.13 and the refusal carries the server's reason", "409" in verdict.detail,
          verdict.detail)

    report_only = FakeClient([pr(), pr()], [run()])
    verdict, merged = gm.guarded_merge(report_only, PR163, do_merge=False, sleep=NO_SLEEP)
    check("R4.14 the default path reports and never merges",
          verdict.allowed and merged is None and report_only.merges == [])
    check("R4.15 reporting does not re-read the head", report_only.pr_reads == 1)

    # GitHub answers `mergeable: null` until it has computed the merge, which is the
    # usual answer on a freshly pushed head. Refusing that outright is what sends an
    # impatient operator back to gh pr merge, so the gate asks again.
    waking = FakeClient([pr(mergeable=None, mergeable_state="unknown"), pr()], [run()])
    resolved = gm.read_pull_request(waking, PR163, sleep=NO_SLEEP)
    check("R4.16 an uncomputed mergeability is re-read rather than refused",
          resolved.get("mergeable") is True, str(resolved.get("mergeable")))
    check("R4.17 and that takes more than one read", waking.pr_reads >= 2, str(waking.pr_reads))
    stuck = FakeClient([pr(mergeable=None, mergeable_state="unknown")], [run()])
    verdict, merged = gm.guarded_merge(stuck, PR163, do_merge=True, sleep=NO_SLEEP)
    check("R4.18 mergeability that never resolves still refuses",
          not verdict.allowed and verdict.code == "mergeability_unknown", verdict.code)
    check("R4.19 the re-read is bounded, not a spin",
          stuck.pr_reads == gm.MERGEABILITY_ATTEMPTS, str(stuck.pr_reads))
    gone = FakeClient([pr(state="closed", mergeable=None)], [run()])
    gm.read_pull_request(gone, PR163, sleep=NO_SLEEP)
    check("R4.20 a closed pull request is not waited on", gone.pr_reads == 1, str(gone.pr_reads))

    print()
    print("=" * 92)
    print("R5  structure: the merge must be unreachable without the gate")
    print("=" * 92)
    source = GATE.read_text(encoding="utf-8")
    check("R5.1 the gate exposes no override flag",
          not any(f in source for f in ("--force", "--no-verify", "--skip-ci", "--admin")))
    check("R5.2 client.merge is called from exactly one place in the module",
          source.count("client.merge(") == 1, str(source.count("client.merge(")))
    check("R5.3 refusing exits non-zero", gm.REFUSED == 1 and gm.ALLOWED == 0)
    check("R5.4 a transport error is its own exit code, not a pass", gm.ERROR == 2)

    class Exploding:
        def pull_request(self, number):
            raise RuntimeError("gh api unreachable")

    try:
        gm.guarded_merge(Exploding(), 1, do_merge=True, sleep=NO_SLEEP)
        raised = False
    except RuntimeError:
        raised = True
    check("R5.5 an unreachable API raises instead of returning an allow", raised)
    check("R5.6 the governed workflow is pinned by path, not by display name",
          gm.GOVERNED_WORKFLOW_PATH == ".github/workflows/ci-integrity.yml")
    check("R5.7 a run for a different SHA is dropped even if the API returned it",
          gm.governed_runs([run(head=OTHER_SHA)], PR163_HEAD, PR163) == [])
    check("R5.8 success is the only conclusion that is not in a refusal set",
          "success" not in (gm.FAILING | gm.INCONCLUSIVE | gm.NON_TERMINAL))
    check("R5.9 the expected base is main", gm.EXPECTED_BASE == "main")
    check("R5.10 the repository is pinned", gm.REPO == "auxchan/auxsays.github.io")
    check("R5.11 the governed event is the pull request event",
          gm.GOVERNED_EVENT == "pull_request")

    print()
    print("=" * 92)
    print("R6  what the adversarial review found: the command line was the override")
    print("=" * 92)
    # Every other workflow in this repo is green on every commit, having never run on
    # it. A flag naming the workflow therefore WAS the bypass: point it at pages.yml
    # and the gate reports an ALLOW line byte-identical to an honest one.
    # Read the real help text rather than monkeypatching argparse: subclassing a
    # patched ArgumentParser makes super().__init__ resolve back to the subclass.
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            gm.main(["--help"])
        except SystemExit:
            pass
    helptext = buf.getvalue()
    parser_flags = set(re.findall(r"--[a-z][a-z-]*", helptext)) - {"--help"}
    check("R6.1 the CLI accepts --merge and nothing else", parser_flags == {"--merge"},
          str(sorted(parser_flags)))
    for flag in ("--workflow", "--base", "--repo"):
        check(f"R6.2 {flag} is not a flag the gate accepts", flag not in parser_flags)
    check("R6.3 a truncated run page is an error, not a short list",
          "total_count" in source and "truncated" in source)

    class Truncating:
        def _api(self, *a, **k):
            return {"total_count": 150, "workflow_runs": [run()]}
        pull_request = lambda self, n: pr()
        workflow_runs = gm.GhClient.workflow_runs

    try:
        Truncating().workflow_runs(PR163_HEAD)
        truncation_raised = False
    except RuntimeError:
        truncation_raised = True
    check("R6.4 a truncated run list refuses to be read as complete", truncation_raised)
    check("R6.5 a hand-dispatched run of the governed workflow is not the governed check",
          gm.governed_runs([run(event="workflow_dispatch")], PR163_HEAD, PR163) == [])
    check("R6.6 a run attached only to a sibling pull request is dropped",
          gm.governed_runs([run(prs=(999,))], PR163_HEAD, PR163) == [])
    check("R6.7 a run attached to this pull request among others is kept",
          len(gm.governed_runs([run(prs=(999, PR163))], PR163_HEAD, PR163)) == 1)
    check("R6.8 the gate claims no more than it enforces: it names its residuals",
          "residual" in source.lower() and "ci-integrity.yml" in source)

    # Red and green are read from different sets on purpose. A failure is a fact
    # about the commit whoever triggered the run; a pass has to be the pass this
    # pull request earned. The attack this closes: let the pull-request run go red,
    # cancel it, then dispatch the same workflow by hand to mint a green.
    red_dispatch = gm.decide(pr(), PR163_HEAD,
                             [run(conclusion="failure", event="workflow_dispatch", rid=5), run()],
                             **GM)
    check("R6.9 a failing run vetoes whatever event produced it",
          not red_dispatch.allowed and red_dispatch.code == "run_not_success", red_dispatch.code)
    cancelled_then_dispatched = gm.decide(
        pr(), PR163_HEAD,
        [run(conclusion="cancelled", rid=6), run(conclusion="success", event="workflow_dispatch", rid=7)],
        **GM)
    check("R6.10 a cancelled pull-request run cannot be replaced by a dispatched green",
          not cancelled_then_dispatched.allowed, cancelled_then_dispatched.code)
    check("R6.11 a green still has to come from this pull request's own run",
          not gm.decide(pr(), PR163_HEAD,
                        [run(conclusion="success", event="push", rid=8)], **GM).allowed)
    check("R6.12 red is read from the wider set than green",
          len(gm.commit_runs([run(event="workflow_dispatch")], PR163_HEAD)) == 1
          and gm.governed_runs([run(event="workflow_dispatch")], PR163_HEAD, PR163) == [])

    print()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
