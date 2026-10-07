#!/usr/bin/env python3
"""The merge gate is policy, so it is tested like production code.

AUX-013 was closed by a script that refuses to merge a pull request whose required
CI is not green for its current head. A gate like that is only worth the assertions
behind it: a gate that reads a branch instead of a SHA, or that treats a missing
check as a pass, looks identical from the outside and stops nothing.

Section R1 replays the real recorded shape of PR #163 -- the merge this gate exists
to prevent. The rest enumerate the refusals and the single allow path, and R5 pins
the structure, because the demonstrated failure was not a wrong decision. It was a
correct decision with nothing between it and the merge.

Offline: no network, no repo writes.
"""
from __future__ import annotations

import importlib.util
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


# The real head of PR #163 and the real id/conclusion of the run that was already
# red when it merged. Recorded from the API, not invented.
PR163_HEAD = "8ea5ce0dbfa50e3ab91feba122de3fb78c169c56"
PR163_RUN = {"id": 37626793286, "path": ".github/workflows/ci-integrity.yml",
             "event": "pull_request", "status": "completed", "conclusion": "failure",
             "head_sha": PR163_HEAD}

OTHER_SHA = "1111111111111111111111111111111111111111"


def pr(head: str = PR163_HEAD, **over) -> dict:
    """An otherwise perfectly mergeable pull request, so each test varies one thing."""
    base = {"state": "open", "merged": False, "draft": False, "base": {"ref": "main"},
            "head": {"sha": head}, "mergeable": True, "mergeable_state": "clean"}
    base.update(over)
    return base


def run(head: str = PR163_HEAD, conclusion: str = "success", status: str = "completed",
        path: str = ".github/workflows/ci-integrity.yml", rid: int = 1) -> dict:
    return {"id": rid, "path": path, "event": "pull_request", "status": status,
            "conclusion": conclusion, "head_sha": head}


class FakeClient:
    """Records every call. `pr_sequence` lets the head move between the two reads."""

    def __init__(self, pr_sequence, runs):
        self.pr_sequence = list(pr_sequence)
        self.runs = runs
        self.pr_reads = 0
        self.run_queries: list[str] = []
        self.merges: list[dict] = []

    def pull_request(self, number):
        self.pr_reads += 1
        idx = min(self.pr_reads - 1, len(self.pr_sequence) - 1)
        return self.pr_sequence[idx]

    def workflow_runs(self, head_sha):
        self.run_queries.append(head_sha)
        return list(self.runs)

    def merge(self, number, head_sha, method):
        self.merges.append({"number": number, "sha": head_sha, "method": method})
        return {"sha": "merged0000", "merged": True, "message": "Pull Request merged"}


def run_suite() -> int:
    gm = load_gate()

    print("=" * 92)
    print("R1  the demonstrated failure: PR #163 merged 19s after its CI went red")
    print("=" * 92)
    v = gm.decide(pr(), PR163_HEAD, [PR163_RUN])
    check("R1.1 the real #163 head and run are refused", not v.allowed, v.render())
    check("R1.2 the refusal names the CI result, not something incidental",
          v.code == "run_not_success", v.code)
    check("R1.3 the refusal reports the failing conclusion", "failure" in v.detail, v.detail)
    client = FakeClient([pr()], [PR163_RUN])
    verdict, merged = gm.guarded_merge(client, 163, do_merge=True)
    check("R1.4 asking to merge #163 performs no merge", client.merges == [], str(client.merges))
    check("R1.5 and returns no merge result", merged is None)
    check("R1.6 a red run is not rescued by a green one on the same commit",
          not gm.decide(pr(), PR163_HEAD, [PR163_RUN, run(rid=2)]).allowed)
    check("R1.7 that refusal is still the CI refusal",
          gm.decide(pr(), PR163_HEAD, [PR163_RUN, run(rid=2)]).code == "run_not_success")

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
        ("pull request is closed", pr(state="closed"), [run()], "pr_not_open"),
        ("pull request is already merged", pr(state="closed", merged=True), [run()], "pr_not_open"),
        ("pull request is a draft", pr(draft=True), [run()], "pr_is_draft"),
        ("pull request is not mergeable", pr(mergeable=False, mergeable_state="dirty"), [run()],
         "pr_not_mergeable"),
        ("mergeability is not known yet", pr(mergeable=None, mergeable_state="unknown"), [run()],
         "pr_not_mergeable"),
        ("base branch is not main", pr(base={"ref": "gh-pages"}), [run()], "wrong_base"),
        ("head cannot be resolved", pr(), [run()], "no_head_sha"),
    ]
    for i, (label, pull, runs, expected) in enumerate(cases, start=1):
        head = None if expected == "no_head_sha" else PR163_HEAD
        got = gm.decide(pull, head, runs)
        check(f"R2.{i} refuses: {label}", not got.allowed and got.code == expected,
              f"got {got.code}")

    print()
    print("=" * 92)
    print("R3  the one state the gate must allow")
    print("=" * 92)
    ok = gm.decide(pr(), PR163_HEAD, [run()])
    check("R3.1 current head, green required run, mergeable, correct base is allowed",
          ok.allowed, ok.render())
    check("R3.2 the allow names the current head", ok.head_sha == PR163_HEAD)
    check("R3.3 the allow is attributed to CI success for that head",
          ok.code == "required_ci_success_for_current_head", ok.code)
    check("R3.4 a cancelled run alongside a green one does not wedge a good commit",
          gm.decide(pr(), PR163_HEAD, [run(conclusion="cancelled", rid=9), run()]).allowed)
    check("R3.5 an unrelated workflow failing does not block the merge",
          gm.decide(pr(), PR163_HEAD,
                    [run(), run(path=".github/workflows/pages.yml", conclusion="failure", rid=3)]
                    ).allowed)
    # A lone unrecognised conclusion never reaches the unrecognised-conclusion
    # branch: it fails the "no success" test first. Pinning only that case leaves the
    # branch itself unpinned, so a green run has to be present alongside it.
    check("R3.6 a lone unrecognised conclusion is refused for having no success",
          gm.decide(pr(), PR163_HEAD, [run(conclusion="surprise")]).code
          == "run_not_success")
    both = gm.decide(pr(), PR163_HEAD, [run(), run(conclusion="surprise", rid=2)])
    check("R3.7 an unrecognised conclusion beside a green run is still refused",
          not both.allowed and both.code == "run_conclusion_unrecognised", both.code)
    check("R3.8 and the refusal names the conclusion it did not recognise",
          "surprise" in both.detail, both.detail)

    print()
    print("=" * 92)
    print("R4  the window between reading CI and merging")
    print("=" * 92)
    moved = FakeClient([pr(PR163_HEAD), pr(OTHER_SHA)], [run()])
    verdict, merged = gm.guarded_merge(moved, 1, do_merge=True)
    check("R4.1 a head that moves after CI was read refuses the merge",
          not verdict.allowed and verdict.code == "head_moved", verdict.code)
    check("R4.2 and no merge is attempted", moved.merges == [], str(moved.merges))
    check("R4.3 the head is read twice, not once", moved.pr_reads == 2, str(moved.pr_reads))

    good = FakeClient([pr(), pr()], [run()])
    verdict, merged = gm.guarded_merge(good, 42, do_merge=True)
    check("R4.4 a stable green head does merge", verdict.allowed and merged is not None,
          verdict.render())
    check("R4.5 the merge carries the validated SHA as a lease",
          good.merges and good.merges[0]["sha"] == PR163_HEAD, str(good.merges))
    check("R4.6 CI is queried by SHA, never by branch",
          good.run_queries == [PR163_HEAD], str(good.run_queries))
    check("R4.7 the gate re-reads the head before merging", good.pr_reads == 2, str(good.pr_reads))

    # A pull request that goes green, then is closed in the window. The second read
    # has to be re-judged in full, not merely compared for a moved head.
    closed_late = FakeClient([pr(), pr(state="closed")], [run()])
    verdict, merged = gm.guarded_merge(closed_late, 7, do_merge=True)
    check("R4.8 a pull request closed inside the window is refused",
          not verdict.allowed and verdict.code == "pr_not_open", verdict.code)
    check("R4.9 and nothing is merged", closed_late.merges == [])

    report_only = FakeClient([pr(), pr()], [run()])
    verdict, merged = gm.guarded_merge(report_only, 42, do_merge=False)
    check("R4.10 the default path reports and never merges",
          verdict.allowed and merged is None and report_only.merges == [])
    check("R4.11 reporting does not re-read the head", report_only.pr_reads == 1)

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

    broken = Exploding()
    try:
        gm.guarded_merge(broken, 1, do_merge=True)
        raised = False
    except RuntimeError:
        raised = True
    check("R5.5 an unreachable API raises instead of returning an allow", raised)
    check("R5.6 the governed workflow is pinned by path, not by display name",
          gm.GOVERNED_WORKFLOW_PATH == ".github/workflows/ci-integrity.yml")
    check("R5.7 a run for a different SHA is dropped even if the API returned it",
          gm.governed_runs([run(head=OTHER_SHA)], PR163_HEAD, gm.GOVERNED_WORKFLOW_PATH) == [])
    check("R5.8 success is the only conclusion that is not in a refusal set",
          "success" not in (gm.FAILING | gm.INCONCLUSIVE | gm.NON_TERMINAL))
    check("R5.9 the expected base is main", gm.EXPECTED_BASE == "main")

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
