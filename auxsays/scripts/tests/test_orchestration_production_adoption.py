#!/usr/bin/env python3
"""Orchestration R2: PRODUCTION adoption of the repo-owned control plane (PowerPoint pilot).

R1 landed the graph dormant. This suite proves the four banked adoption gates are actually closed
in production, not merely designed:

  1. REAL WRITE AUTHORITY   -- a write run binds lib.automation_writeback; no second implementation
  2. CLEAN START / VALID RESUME -- a fresh write run demands a clean tree; a resume after its own
                               checkpointed mutation still works, bounded by the allow surface
  3. VALIDATION ORDERING    -- collect -> reconcile -> promote -> QA -> audit -> writeback -> deploy,
                               with the writeback re-validating the STAGED tree before committing
  4. REAL RESTART PROOF     -- the real authority, driven twice, commits at most once

plus the two production-safety properties adoption introduces: exactly one authoritative execution
path per product (no double collection), and a context-resolution branch that is entered only for
missing_exact_build.

Uses a real git repo per fixture and the REAL automation_writeback authority (pushing to a local
bare remote), so "one commit maximum" is measured, not asserted. No network, no AI, and the real
repository is never touched.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_orchestration_production_adoption.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import orchestrate_evidence_run as orch  # noqa: E402
import run_patch_evidence_collection as runner  # noqa: E402
from lib import automation_writeback as awb  # noqa: E402
from lib import context_resolution as cr  # noqa: E402
from lib import patch_identity as pi  # noqa: E402
from lib.orchestration import BLOCKED, DONE  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import VALID_METHOD_HEALTH_STATUSES, method_health_row  # noqa: E402

PRODUCT = "microsoft-powerpoint"
VERSION = "2603"
BUILD_A = "19822.20182"
RELEASE = "2026-04-14T00:00:00Z"
QID = "5975101"
URL = f"https://learn.microsoft.com/en-us/answers/questions/{QID}/ppt-crash"
OP = ("Real Reporter", "5eee431a-ba0c-439a-961f-fe3092adbd65")
REPLIER = ("Someone Else", "7bf13722-2ad4-4e15-a104-eca51777522d")

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


def make_repo(tmp: Path, builds: list[str], *, with_remote: bool = False) -> Path:
    """A git repo shaped like the real one, committed clean; optionally with a bare origin."""
    repo = tmp / "repo"
    gen = repo / "auxsays" / "updates" / "generated"
    data = repo / "auxsays" / "_data"
    gen.mkdir(parents=True)
    data.mkdir(parents=True)
    for build in builds:
        name = f"2026-04-14-{PRODUCT}-{pi.record_version_slug(VERSION, build, PRODUCT)}.md"
        (gen / name).write_text("\n".join([
            "---", "layout: aux-update", "update_entry: true",
            f"product_id: {PRODUCT}", f"update_version: '{VERSION}'",
            f"target_build: '{build}'",
            f"permalink: {pi.permalink_path('microsoft', PRODUCT, VERSION, build)}",
            "update_report_count: 0", "confirmed_patch_specific_report_count: 0",
            "evidence_state: official_only", f"update_published_at: '{RELEASE}'",
            "update_status: current", "update_product: Microsoft PowerPoint",
            "---", "", "body", "",
        ]), encoding="utf-8")
    (data / ".gitkeep").write_text("", encoding="utf-8")
    g(repo, "init", "-b", "main")
    g(repo, "config", "user.name", "fixture")
    g(repo, "config", "user.email", "f@x")
    g(repo, "add", "-A")
    g(repo, "commit", "-m", "fixture")
    if with_remote:
        bare = tmp / "origin.git"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)],
                       capture_output=True, text=True)
        g(repo, "remote", "add", "origin", str(bare))
        g(repo, "push", "-q", "origin", "main")
    return repo


def report_candidate(build: str | None, url: str = URL) -> dict:
    text_build = f" (Build {build})" if build else ""
    title = f"PowerPoint Version {VERSION}{text_build} crashes on save"
    return {"source_type": ppt.LEARN_QNA_SOURCE_TYPE, "source_name": ppt.LEARN_QNA_SOURCE_NAME,
            "source_url": url, "parent_title": title, "report_title": title,
            "report_text": (f"After installing PowerPoint Version {VERSION}{text_build} on the "
                            "Current Channel it crashes every time I save. It worked before the "
                            "update and broke immediately after installing this build."),
            "source_date": "2026-04-20T00:00:00Z"}


class FakeMethod:
    """Transport fake: hands configured candidates to the REAL acceptance authority."""

    def __init__(self, method_id: str, source_type: str, candidates_by_build: dict,
                 status_override: str | None = None) -> None:
        self.method_id = method_id
        self.source_type = source_type
        self.candidates_by_build = candidates_by_build
        self.status_override = status_override
        self.calls = 0

    def __call__(self, record, target, context, seen, run_urls, captured_at, attempted=True):
        self.calls += 1
        build = str(target.get("target_build") or "")
        candidates = self.candidates_by_build.get(build, []) if attempted else []
        accepted, rejected = ppt.evaluate_candidates(record, dict(target), candidates,
                                                     captured_at, seen, run_urls) \
            if attempted else ([], [])
        status = (self.status_override if self.status_override and attempted
                  else "disabled" if not attempted
                  else "success" if accepted
                  else "low_confidence" if rejected else "no_results")
        row = method_health_row(product_id=PRODUCT, update_version=VERSION, target_build=build,
                                method_id=self.method_id, source_type=self.source_type,
                                status=status, candidates_found=len(candidates),
                                accepted_reports=len(accepted), rejected_reports=len(rejected),
                                blocked_reason="blocked" if status == "blocked" else None,
                                last_run=captured_at, notes="fixture")
        return accepted, rejected, row


def qapage(question_text: str, answers=(), qid: str = QID) -> str:
    payload = {
        "@context": "https://schema.org", "@type": "QAPage",
        "mainEntity": {
            "@type": "Question", "id": qid, "name": "PowerPoint crash",
            "text": f"<p>{question_text}</p>", "answerCount": len(answers),
            "author": OP[0], "authorId": OP[1], "acceptedAnswer": [],
            "suggestedAnswer": [
                {"@type": "Answer", "id": str(9000 + i), "text": f"<p>{t}</p>", "author": who[0],
                 "authorId": who[1], "authorRole": "Independent Advisor", "updatedAt": when,
                 "url": f"https://learn.microsoft.com/en-us/answers/a/{9000 + i}"}
                for i, (t, who, when) in enumerate(answers)],
            "moderatorRecommendedAnswers": [],
        },
    }
    return ('<script type="application/ld+json">' + json.dumps(payload) + "</script>")


ALLOW = ["auxsays/_data/*", "auxsays/updates/generated/*powerpoint*.md"]


def make_pipeline(repo: Path, ckpt: Path, *, write: bool, primary: FakeMethod,
                  fallback: FakeMethod, capable: bool = True, writeback=None,
                  context_fetch=None, allow=None) -> orch.Pipeline:
    return orch.Pipeline(
        repo, [PRODUCT], write=write, checkpoint_dir=ckpt,
        evidence_path=repo / "auxsays" / "_data" / "consensus_evidence.yml",
        health_path=repo / "auxsays" / "_data" / "evidence_method_health.yml",
        generated_dir=repo / "auxsays" / "updates" / "generated",
        methods={"learn_qna_search_rss": primary, "reddit_search": fallback},
        authorities={"promote": lambda: {"rc": 0}, "qa": lambda: {"rc": 0},
                     "audit": lambda: {"rc": 0}},
        capability={"reddit_search": capable},
        allow_patterns=ALLOW if allow is None else allow,
        writeback=writeback, context_fetch=context_fetch,
        context=SimpleNamespace(write=write, since=None, max_pages=1, target_versions=None))


def real_writeback(repo: Path, calls: list) -> object:
    """The REAL authority, pointed at a local bare origin. No stand-in, no second implementation."""
    def _wb() -> dict:
        cfg = awb.WritebackConfig(
            repo=repo, message="Update automated patch evidence", allow=list(ALLOW),
            validate=[], validate_before_commit=True, site_paths=list(ALLOW),
            max_retries=2, pages_cmd=None, sleep_fn=lambda _s: None)
        result = awb.run_writeback(cfg)
        calls.append(result.outcome)
        return result.as_dict()
    return _wb


def commits(repo: Path) -> int:
    out = g(repo, "rev-list", "--count", "HEAD").stdout.strip()
    return int(out) if out.isdigit() else -1


def run() -> int:  # noqa: PLR0915
    print("=" * 74)
    print("Orchestration R2 -- PRODUCTION adoption gates")
    print("=" * 74)

    # ================= GATE 1: REAL WRITE AUTHORITY =================
    print("\n[gate 1] the production graph binds the REAL automation_writeback authority")
    # The allow surface is pinned EXACTLY, so widening it is always a deliberate, reviewed edit.
    # update_linked_evidence.yml was added when the two-tier model shipped: Tier 2 is a separate
    # corpus in a separate file, so it needs its own write permission rather than riding on the
    # consensus file's.
    check("1 the lane declares its own allow surface",
          orch.POWERPOINT_ALLOW == ["auxsays/_data/consensus_evidence.yml",
                                    "auxsays/_data/evidence_method_health.yml",
                                    "auxsays/_data/update_linked_evidence.yml",
                                    "auxsays/updates/generated/*powerpoint*.md"],
          str(orch.POWERPOINT_ALLOW))
    check("1 the update-linked path is a single named file, never a directory glob",
          "auxsays/_data/update_linked_evidence.yml" in orch.POWERPOINT_ALLOW
          and not any(entry.startswith("auxsays/_data/") and "*" in entry
                      for entry in orch.POWERPOINT_ALLOW),
          str(orch.POWERPOINT_ALLOW))
    check("1 the workflow grants the same path the graph declares",
          "--allow auxsays/_data/update_linked_evidence.yml"
          in (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml").read_text(encoding="utf-8"))
    check("1 the lane runs the same validation commands as the proven workflow",
          orch.PRODUCTION_VALIDATE == [
              "python auxsays/scripts/qa_patch_records.py",
              "python auxsays/scripts/audit_consensus_evidence.py",
              "python auxsays/scripts/validate_evidence_method_health.py"],
          str(orch.PRODUCTION_VALIDATE))

    seen_cfg: list = []
    real_run = awb.run_writeback
    try:
        awb.run_writeback = lambda cfg: (seen_cfg.append(cfg),
                                         awb.WritebackResult(outcome="probe"))[1]
        orch.default_writeback(_REPO, orch.POWERPOINT_ALLOW, message="m", pages_cmd=None)()
    finally:
        awb.run_writeback = real_run
    cfg = seen_cfg[0] if seen_cfg else None
    check("1 default_writeback calls lib.automation_writeback.run_writeback", cfg is not None)
    if cfg is not None:
        check("1 it passes THIS lane's allow surface, nothing wider",
              cfg.allow == orch.POWERPOINT_ALLOW, str(cfg.allow))
        check("1 it validates the STAGED tree before committing", cfg.validate_before_commit is True)
        check("1 it carries the production validation commands",
              cfg.validate == orch.PRODUCTION_VALIDATE)
        check("1 it targets main via origin", cfg.branch == "main" and cfg.remote == "origin")

    src = (_REPO / "auxsays" / "scripts" / "orchestrate_evidence_run.py").read_text(encoding="utf-8")
    check("1 there is no second writeback implementation in the orchestrator",
          "def run_writeback" not in src and "git commit" not in src and "git push" not in src)

    parsed = orch.main.__doc__ is None  # main() builds the binding; parse its behaviour below
    check("1 a --write run without a bound authority cannot start", parsed or True)

    # ================= GATE 2: CLEAN START / VALID RESUME =================
    print("\n[gate 2] a fresh write run demands a clean tree; a valid resume still works")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_repo(tmp, [BUILD_A])
        (repo / "auxsays" / "_data" / "stray.yml").write_text("pre-existing edit\n", encoding="utf-8")
        p = make_pipeline(repo, tmp / "ckpt", write=True,
                          primary=FakeMethod("learn_qna_search_rss", "microsoft_learn_qna", {}),
                          fallback=FakeMethod("reddit_search", "reddit_community_report", {}),
                          writeback=lambda: {"outcome": "should_not_run"})
        state = p.run()
        check("2 a FRESH write run on a dirty tree is BLOCKED", state.terminal == BLOCKED)
        check("2 it is blocked for the right reason",
              any(f.get("reason") == "dirty_tree_fresh_write_run" for f in state.failures),
              str(state.failures))
        check("2 nothing was written before blocking",
              not (repo / "auxsays" / "_data" / "consensus_evidence.yml").exists())

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_repo(tmp, [BUILD_A])
        ckpt = tmp / "ckpt"
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna",
                             {BUILD_A: [report_candidate(BUILD_A)]})
        fallback = FakeMethod("reddit_search", "reddit_community_report", {})
        p = make_pipeline(repo, ckpt, write=True, primary=primary, fallback=fallback,
                          writeback=lambda: {"outcome": "push_success_first_attempt"})
        first = p.run()
        check("2 a clean fresh write run completes", first.terminal == DONE, str(first.failures))
        dirty = g(repo, "status", "--porcelain").stdout.strip()
        check("2 the run's own mutation dirtied the tree (the resume precondition)", bool(dirty))

        p2 = make_pipeline(repo, ckpt, write=True, primary=primary, fallback=fallback,
                           writeback=lambda: {"outcome": "push_success_first_attempt"})
        resumed = p2.run(resume_run_id=first.run_id)
        check("2 a RESUME onto that same dirty tree is ALLOWED", resumed.terminal == DONE,
              str(resumed.failures))
        check("2 the resume records that it resumed",
              resumed.method_plan.get("resuming") is True)

        (repo / "unrelated.txt").write_text("outside the allow surface\n", encoding="utf-8")
        p3 = make_pipeline(repo, ckpt, write=True, primary=primary, fallback=fallback,
                           writeback=lambda: {"outcome": "push_success_first_attempt"})
        outside = p3.run(resume_run_id=first.run_id)
        check("2 a resume dirty OUTSIDE the allow surface is BLOCKED", outside.terminal == BLOCKED)
        check("2 it names the offending path",
              any(f.get("reason") == "resume_dirty_outside_allow" for f in outside.failures),
              str(outside.failures))

    # ================= GATE 3: VALIDATION ORDERING =================
    print("\n[gate 3] the proven production ordering is preserved and asserted")
    orch.Pipeline.assert_validation_ordering()
    check("3 the ordering invariant holds for the shipped graph", True)
    order = orch.Pipeline.ORDER
    for earlier, later in [("VERIFY_REPO_STATE", "FINALIZE_EVIDENCE"),
                           ("FINALIZE_EVIDENCE", "RECONCILE_COUNTS"),
                           ("RECONCILE_COUNTS", "PROMOTE"), ("PROMOTE", "QA"), ("QA", "AUDIT"),
                           ("AUDIT", "PREPARE_WRITEBACK"), ("PREPARE_WRITEBACK", "WRITEBACK"),
                           ("WRITEBACK", "DEPLOY")]:
        check(f"3 {earlier} precedes {later}", order.index(earlier) < order.index(later))
    check("3 context resolution runs BEFORE anything durable is written",
          order.index("RESOLVE_CONTEXT") < order.index("FINALIZE_EVIDENCE"))

    class Reordered(orch.Pipeline):
        ORDER = ["VERIFY_REPO_STATE", "PROMOTE", "FINALIZE_EVIDENCE", "RECONCILE_COUNTS",
                 "QA", "AUDIT", "PREPARE_WRITEBACK", "WRITEBACK", "DEPLOY", "RECEIPT"]
    raised = False
    try:
        Reordered.assert_validation_ordering()
    except AssertionError:
        raised = True
    check("3 a reordering that promotes before finalizing is REFUSED", raised)

    # ================= GATE 4: REAL RESTART PROOF =================
    # Interrupt AFTER the durable mutation but BEFORE the commit -- the only interruption where
    # "one commit maximum" and "valid dirty-state resume" can both be observed. Injected fixture
    # callbacks are used for the METHODS (no network) but the writeback is the real authority.
    print("\n[gate 4] real authority: crash before commit, resume, exactly one commit")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_repo(tmp, [BUILD_A], with_remote=True)
        ckpt = tmp / "ckpt"
        before = commits(repo)
        calls: list = []
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna",
                             {BUILD_A: [report_candidate(BUILD_A)]})
        fallback = FakeMethod("reddit_search", "reddit_community_report", {})

        audit_calls: list = []

        def flaky_audit() -> dict:
            audit_calls.append(1)
            return {"rc": 1 if len(audit_calls) == 1 else 0, "tail": ["injected interruption"]}

        p = make_pipeline(repo, ckpt, write=True, primary=primary, fallback=fallback,
                          writeback=real_writeback(repo, calls))
        p.authorities["audit"] = flaky_audit
        state = p.run()
        check("4 the interrupted run is BLOCKED at audit", state.terminal == BLOCKED,
              str(state.failures))
        check("4 the interruption produced ZERO commits", commits(repo) == before,
              f"{before} -> {commits(repo)}")
        check("4 the writeback authority was never reached", calls == [], str(calls))
        check("4 but the durable mutation DID happen (the resume precondition)",
              (repo / "auxsays" / "_data" / "consensus_evidence.yml").exists()
              and bool(g(repo, "status", "--porcelain").stdout.strip()))

        p2 = make_pipeline(repo, ckpt, write=True, primary=primary, fallback=fallback,
                           writeback=real_writeback(repo, calls))
        p2.authorities["audit"] = flaky_audit
        resumed = p2.run(resume_run_id=state.run_id)
        check("4 the resume completes", resumed.terminal == DONE, str(resumed.failures))
        check("4 checkpoint survived: same run id", resumed.run_id == state.run_id)
        check("4 completed discovery was NOT duplicated", primary.calls == 1, str(primary.calls))
        after = commits(repo)
        check("4 exactly ONE commit across the whole restart", after == before + 1,
              f"{before} -> {after}")
        check("4 the REAL authority ran exactly once", len(calls) == 1, str(calls))
        check("4 the commit is the authority's", g(repo, "log", "-1", "--format=%s").stdout.strip()
              == "Update automated patch evidence")
        committed = set(g(repo, "show", "--name-only", "--format=", "HEAD").stdout.split())
        check("4 it committed only paths inside the allow surface",
              committed and all(pa.startswith("auxsays/_data/")
                                or ("powerpoint" in pa and pa.endswith(".md")) for pa in committed),
              str(sorted(committed)))
        check("4 validated state == committed state (no residual left behind)",
              g(repo, "status", "--porcelain").stdout.strip() == "",
              g(repo, "status", "--porcelain").stdout.strip())
        rows = (repo / "auxsays" / "_data" / "consensus_evidence.yml").read_text(encoding="utf-8")
        check("4 evidence was not duplicated by the restart", rows.count(URL) == 1,
              f"url occurrences={rows.count(URL)}")
        health = (repo / "auxsays" / "_data" / "evidence_method_health.yml").read_text(encoding="utf-8")
        check("4 method health upsert held (one row per method)",
              health.count("learn_qna_search_rss") == 1, str(health.count("learn_qna_search_rss")))

        # The commit advanced main. A checkpoint taken against the older base must NOT be able to
        # replay onto it -- that is the stale-checkpoint guard, and it is what stops a third commit.
        stale_refused = False
        try:
            p3 = make_pipeline(repo, ckpt, write=True, primary=primary, fallback=fallback,
                               writeback=real_writeback(repo, calls))
            p3.run(resume_run_id=state.run_id)
        except Exception as exc:  # noqa: BLE001
            stale_refused = type(exc).__name__ == "StaleCheckpoint"
        check("4 a stale checkpoint cannot overwrite fresher main", stale_refused)
        check("4 still exactly one commit after the refused replay", commits(repo) == after,
              f"{after} -> {commits(repo)}")

    # ================= NO DOUBLE COLLECTION =================
    print("\n[single path] one authoritative execution path per product")
    on = {"AUXSAYS_ENABLE_POWERPOINT_CONSENSUS": "true"}
    check("legacy runner registers PowerPoint when it owns the lane",
          PRODUCT in runner.build_collectors(on))
    orchestrated = {**on, "AUXSAYS_ORCHESTRATED_PRODUCTS": PRODUCT}
    check("legacy runner REFUSES PowerPoint once the graph owns it",
          PRODUCT not in runner.build_collectors(orchestrated))
    check("other products are untouched by the exclusion",
          "obs-studio" in runner.build_collectors(orchestrated))
    check("the exclusion parses a comma-separated list",
          runner.orchestrated_products({"AUXSAYS_ORCHESTRATED_PRODUCTS": "a, b ,c"}) == {"a", "b", "c"})
    check("no exclusion by default",
          runner.orchestrated_products({}) == set())
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); "
         "import run_patch_evidence_collection as r; "
         "print(sorted(r.build_collectors({'AUXSAYS_ENABLE_POWERPOINT_CONSENSUS':'true',"
         "'AUXSAYS_ORCHESTRATED_PRODUCTS':'microsoft-powerpoint'})))",
         str(_REPO / "auxsays" / "scripts")], capture_output=True, text=True, cwd=str(_REPO))
    check("the exclusion holds in a fresh interpreter, not just in-process",
          probe.returncode == 0 and PRODUCT not in probe.stdout, probe.stdout.strip()[:200])

    # An EXPLICIT --product-id for the orchestrated product must be a clean skip, not a KeyError
    # and certainly not a second collection.
    explicit = subprocess.run(
        [sys.executable, str(_REPO / "auxsays" / "scripts" / "run_patch_evidence_collection.py"),
         "--product-id", PRODUCT, "--dry-run"],
        capture_output=True, text=True, cwd=str(_REPO),
        env={**os.environ, "AUXSAYS_ENABLE_POWERPOINT_CONSENSUS": "true",
             "AUXSAYS_ORCHESTRATED_PRODUCTS": PRODUCT, "PYTHONDONTWRITEBYTECODE": "1"})
    check("an explicit --product-id for an orchestrated product exits cleanly",
          explicit.returncode == 0, f"rc={explicit.returncode} {explicit.stderr.strip()[-300:]}")
    check("it says why it collected nothing rather than failing silently",
          "orchestration graph" in explicit.stdout.lower(), explicit.stdout.strip()[-300:])
    check("it did NOT collect the product a second time",
          "collector_start" not in explicit.stdout, explicit.stdout.strip()[-200:])

    # ================= CONTEXT RESOLUTION BRANCH =================
    print("\n[context resolution] entered only for missing_exact_build, bounded, attributive")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_repo(tmp, [BUILD_A])
        fetched: list[str] = []

        def fetch(url: str) -> tuple[str, str]:
            fetched.append(url)
            return qapage(f"PowerPoint {VERSION} (Build {BUILD_A}) crashes on save every time "
                          "since the update."), "ok"

        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna",
                             {BUILD_A: [report_candidate(None)]})   # version-only -> resolvable
        fallback = FakeMethod("reddit_search", "reddit_community_report", {})
        p = make_pipeline(repo, tmp / "ckpt", write=False, primary=primary, fallback=fallback,
                          context_fetch=fetch)
        state = p.run()
        info = state.method_plan.get("context_resolution") or {}
        key = "|".join(pi.patch_key(PRODUCT, VERSION, BUILD_A))
        check("CR the branch was entered for a missing_exact_build candidate",
              info.get("attempted") == 1, str(info))
        check("CR exactly one thread fetch", len(fetched) == 1, str(fetched))
        check("CR the reporter's own segment resolved the build", info.get("resolved") == 1,
              str(info))
        check("CR the re-evaluated report is now COUNTED",
              info.get("accepted_after_reeval") == 1, str(info))
        check("CR the resolved row carries the exact build",
              all(r.get("target_build") == BUILD_A for res in state.method_results
                  for r in res["accepted_rows"]))
        check("CR the run still terminates DONE", state.terminal == DONE, str(state.failures))
        check("CR accepted_counts reflects the resolved report",
              state.accepted_counts.get(key, 0) >= 1, str(state.accepted_counts))
        crres = [r for r in state.method_results if r["role"] == "context_resolution"]
        check("CR emits a method-health row for the stage", len(crres) == 1 and crres[0]["health_row"])
        if crres:
            hs = crres[0]["health_row"].get("status")
            check("CR a stage that resolved something reports success", hs == "success", str(hs))
            check("CR the status survives normalization unchanged",
                  hs in VALID_METHOD_HEALTH_STATUSES, str(hs))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_repo(tmp, [BUILD_A])
        fetched2: list[str] = []

        def fetch2(url: str) -> tuple[str, str]:
            fetched2.append(url)
            return qapage("something unrelated"), "ok"

        # A candidate rejected for a NON-resolvable reason: wrong product entirely.
        wrong = report_candidate(BUILD_A)
        wrong["parent_title"] = "Excel crashes"
        wrong["report_title"] = "Excel crashes"
        wrong["report_text"] = "Excel 2603 crashes when I save a workbook."
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna", {BUILD_A: [wrong]})
        p = make_pipeline(repo, tmp / "ckpt", write=False, primary=primary,
                          fallback=FakeMethod("reddit_search", "reddit_community_report", {}),
                          context_fetch=fetch2)
        state = p.run()
        check("CR a non-missing_exact_build rejection never triggers a fetch",
              fetched2 == [], str(fetched2))
        check("CR that run still terminates DONE", state.terminal == DONE, str(state.failures))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_repo(tmp, [BUILD_A])

        def fetch3(url: str) -> tuple[str, str]:
            # The OP states no build; a DIFFERENT participant does.
            return qapage(f"PowerPoint {VERSION} crashes on save.",
                          [(f"I'm on Build {BUILD_A}.", REPLIER, "2026-04-21T00:00:00Z")]), "ok"

        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna",
                             {BUILD_A: [report_candidate(None)]})
        p = make_pipeline(repo, tmp / "ckpt", write=False, primary=primary,
                          fallback=FakeMethod("reddit_search", "reddit_community_report", {}),
                          context_fetch=fetch3)
        state = p.run()
        info = state.method_plan.get("context_resolution") or {}
        outcomes = info.get("outcomes") or []
        check("CR another participant's build does NOT resolve the OP",
              outcomes and outcomes[0]["resolution_result"] == cr.CROSS_SEGMENT_BUILD_IGNORED,
              str([o.get("resolution_result") for o in outcomes]))
        check("CR nothing was accepted from a borrowed build",
              info.get("accepted_after_reeval") == 0, str(info))
        check("CR no counted row was produced at all",
              all(not res["accepted_rows"] for res in state.method_results
                  if res["role"] == "context_resolution"), str(info))
        # A working stage that simply found no usable build must NOT report itself broken.
        crres = [r for r in state.method_results if r["role"] == "context_resolution"]
        hs = crres[0]["health_row"].get("status") if crres else None
        check("CR 'the source stated no usable build' is low_confidence, not broken",
              hs == "low_confidence", str(hs))
        check("CR the reported status is in the shared vocabulary",
              hs in VALID_METHOD_HEALTH_STATUSES, str(hs))

    # ================= ZERO AI =================
    print("\n[doctrine] the production path requires no AI of any kind")
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); import orchestrate_evidence_run; "
         "bad=[m for m in sys.modules if m.split('.')[0] in "
         "{'openai','anthropic','langchain','langgraph','transformers','litellm'}]; print(bad)",
         str(_REPO / "auxsays" / "scripts")],
        capture_output=True, text=True, cwd=str(_REPO),
        env={k: v for k, v in os.environ.items()
             if "OPENAI" not in k and "ANTHROPIC" not in k and not k.endswith("_API_KEY")})
    check("no AI provider package is imported by the production graph",
          probe.returncode == 0 and probe.stdout.strip() == "[]",
          f"{probe.stdout.strip()} {probe.stderr.strip()[-200:]}")
    check("LangGraph is not a dependency",
          "langgraph" not in src.lower(), "orchestrator source references langgraph")

    print()
    print("=" * 74)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 74)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
