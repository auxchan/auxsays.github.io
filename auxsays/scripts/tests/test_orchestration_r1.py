#!/usr/bin/env python3
"""Orchestration R1: deterministic control plane over the existing PowerPoint authorities.

Fixtures A-K from the R1 contract. The fake *methods* injected here are transport fakes only:
every acceptance decision still runs through the REAL ``row_from_candidate`` (exact build,
channel, date, URL, concrete-issue gates), evidence persistence through the REAL
``append_evidence_rows`` / ``upsert_method_health``, and reconciliation through the REAL
``reconcile_record_counts``. The graph never re-scores anything.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_orchestration_r1.py
"""
from __future__ import annotations

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
from lib import method_routing as mr  # noqa: E402
from lib import patch_identity as pi  # noqa: E402
from lib.orchestration import (  # noqa: E402
    BLOCKED, DONE, ERROR, JsonCheckpointer, OrchestrationState, StaleCheckpoint,
    UnsafeCheckpointDir,
)
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import PatchRecord, load_evidence, method_health_row  # noqa: E402

PRODUCT = "microsoft-powerpoint"
VERSION = "2603"
BUILD_A = "19822.20182"
BUILD_B = "19822.20168"
RELEASE = "2026-04-14T00:00:00Z"
URL = "https://learn.microsoft.com/en-us/answers/questions/5975101/ppt-crash"

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


def make_fixture_repo(tmp: Path, builds: list[str]) -> Path:
    """A git repo shaped like the real one: generated records + data files, committed clean."""
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
    # The two data files are deliberately NOT seeded: the append/upsert authorities create them
    # in their own canonical shape on first write (a hand-seeded flow-style empty list would not
    # match the byte-preserving appender's block-list expectation).
    (data / ".gitkeep").write_text("", encoding="utf-8")
    g(repo, "init", "-b", "main")
    g(repo, "config", "user.name", "fixture")
    g(repo, "config", "user.email", "f@x")
    g(repo, "add", "-A")
    g(repo, "commit", "-m", "fixture")
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

    def __init__(self, method_id: str, source_type: str, candidates_by_build: dict[str, list[dict]],
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
        if self.status_override and attempted:
            status = self.status_override
        elif not attempted:
            status = "disabled"
        elif accepted:
            status = "success"
        elif candidates:
            status = "low_confidence" if rejected else "no_results"
        else:
            status = "no_results"
        row = method_health_row(product_id=PRODUCT, update_version=VERSION,
                                target_build=build, method_id=self.method_id,
                                source_type=self.source_type, status=status,
                                candidates_found=len(candidates),
                                accepted_reports=len(accepted), rejected_reports=len(rejected),
                                blocked_reason="blocked" if status == "blocked" else None,
                                last_run=captured_at, notes="fixture")
        return accepted, rejected, row


def make_pipeline(repo: Path, ckpt: Path, *, write: bool, primary: FakeMethod,
                  fallback: FakeMethod, capable: bool = True,
                  authorities: dict | None = None, writeback=None) -> orch.Pipeline:
    auth = authorities or {"promote": lambda: {"rc": 0}, "qa": lambda: {"rc": 0},
                           "audit": lambda: {"rc": 0}}
    return orch.Pipeline(
        repo, [PRODUCT], write=write, checkpoint_dir=ckpt,
        evidence_path=repo / "auxsays" / "_data" / "consensus_evidence.yml",
        health_path=repo / "auxsays" / "_data" / "evidence_method_health.yml",
        generated_dir=repo / "auxsays" / "updates" / "generated",
        methods={"learn_qna_search_rss": primary, "reddit_search": fallback},
        authorities=auth, capability={"reddit_search": capable},
        allow_patterns=["auxsays/_data/*", "auxsays/updates/generated/*powerpoint*.md"],
        writeback=writeback,
        context=SimpleNamespace(write=write, since=None, max_pages=1, target_versions=None))


def run() -> int:  # noqa: PLR0915
    print("=" * 70)
    print("Orchestration R1 -- deterministic control plane fixtures A-K")
    print("=" * 70)

    # ---- A. primary accepted -> fallback not needed ---------------------------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_fixture_repo(tmp, [BUILD_A])
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna",
                             {BUILD_A: [report_candidate(BUILD_A)]})
        fallback = FakeMethod("reddit_search", "reddit_community_report", {})
        p = make_pipeline(repo, tmp / "ckpt", write=False, primary=primary, fallback=fallback)
        state = p.run()
        key = "|".join(pi.patch_key(PRODUCT, VERSION, BUILD_A))
        check("A terminal DONE", state.terminal == DONE, str(state.failures))
        check("A primary accepted one exact-build report", state.accepted_counts.get(key) == 1,
              str(state.accepted_counts))
        check("A fallback was NOT invoked (not justified)",
              not any(r["role"] == "fallback" for r in state.method_results))
        check("A accepted row retains the exact build",
              all(r.get("target_build") == BUILD_A for res in state.method_results
                  for r in res["accepted_rows"]))

    # ---- B. primary no_results -> fallback invoked ----------------------------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_fixture_repo(tmp, [BUILD_A])
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna", {})
        fallback = FakeMethod("reddit_search", "reddit_community_report",
                              {BUILD_A: [report_candidate(BUILD_A, URL + "-rd")]})
        p = make_pipeline(repo, tmp / "ckpt", write=False, primary=primary, fallback=fallback)
        state = p.run()
        fb = [r for r in state.method_results if r["role"] == "fallback"]
        check("B fallback invoked on primary no_results",
              fb and fb[0]["attempted"] and fb[0]["fallback_reason"] == "no_accepted_reports",
              str([(r.get('attempted'), r.get('fallback_reason')) for r in fb]))
        key = "|".join(pi.patch_key(PRODUCT, VERSION, BUILD_A))
        check("B fallback exact-build report accepted", state.accepted_counts.get(key) == 1)

    # ---- C. primary blocked -> fallback invoked -------------------------------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_fixture_repo(tmp, [BUILD_A])
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna", {},
                             status_override="blocked")
        fallback = FakeMethod("reddit_search", "reddit_community_report", {})
        p = make_pipeline(repo, tmp / "ckpt", write=False, primary=primary, fallback=fallback)
        state = p.run()
        fb = [r for r in state.method_results if r["role"] == "fallback"]
        check("C fallback invoked on primary blocked",
              fb and fb[0]["attempted"] and fb[0]["fallback_reason"] in ("blocked", "no_accepted_reports"),
              str([(r.get('attempted'), r.get('fallback_reason')) for r in fb]))

    # ---- D. fallback candidate missing exact build -> remains uncounted --------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_fixture_repo(tmp, [BUILD_A])
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna", {})
        fallback = FakeMethod("reddit_search", "reddit_community_report",
                              {BUILD_A: [report_candidate(None, URL + "-noB")]})
        p = make_pipeline(repo, tmp / "ckpt", write=False, primary=primary, fallback=fallback)
        state = p.run()
        key = "|".join(pi.patch_key(PRODUCT, VERSION, BUILD_A))
        check("D version-only fallback report stays UNCOUNTED", state.accepted_counts.get(key) == 0,
              str(state.accepted_counts))
        check("D rejection reason is missing_exact_build",
              state.rejection_counts.get("missing_exact_build", 0) >= 1, str(state.rejection_counts))
        check("D dry finalize would add zero rows",
              state.evidence_changes.get("would_add") == 0, str(state.evidence_changes))

    # ---- E. fallback explicit exact build -> accepted; F. wrong build -> rejected ----------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_fixture_repo(tmp, [BUILD_A, BUILD_B])
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna", {})
        fallback = FakeMethod("reddit_search", "reddit_community_report", {
            BUILD_A: [report_candidate(BUILD_A, URL + "-eA")],
            BUILD_B: [report_candidate(BUILD_A, URL + "-wB")],   # names A's build for B's record
        })
        p = make_pipeline(repo, tmp / "ckpt", write=True, primary=primary, fallback=fallback)
        state = p.run()
        key_a = "|".join(pi.patch_key(PRODUCT, VERSION, BUILD_A))
        key_b = "|".join(pi.patch_key(PRODUCT, VERSION, BUILD_B))
        check("E terminal DONE", state.terminal == DONE, str(state.failures))
        check("E exact-build fallback report ACCEPTED for build A",
              state.accepted_counts.get(key_a) == 1, str(state.accepted_counts))
        check("F wrong-build report REJECTED for build B",
              state.accepted_counts.get(key_b) == 0
              and state.rejection_counts.get("build_mismatch", 0) >= 1,
              str(state.rejection_counts))
        rows = load_evidence(repo / "auxsays" / "_data" / "consensus_evidence.yml")
        check("E evidence persisted exactly one row with the exact build",
              len(rows) == 1 and rows[0].get("target_build") == BUILD_A,
              str([(r.get('id'), r.get('target_build')) for r in rows]))
        check("E sibling build B record untouched by reconciliation",
              "update_report_count: 0" in next(
                  fp.read_text(encoding="utf-8") for fp in
                  (repo / "auxsays" / "updates" / "generated").glob("*.md")
                  if BUILD_B.replace(".", "-") in fp.name))
        check("E build A record reconciled to its own single report",
              "update_report_count: 1" in next(
                  fp.read_text(encoding="utf-8") for fp in
                  (repo / "auxsays" / "updates" / "generated").glob("*.md")
                  if BUILD_A.replace(".", "-") in fp.name))
        check("E health rows carry the exact build per method",
              state.health_changes.get("changed", 0) >= 2, str(state.health_changes))

    # ---- G/H. restart: no duplicate collection, no duplicate evidence ----------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_fixture_repo(tmp, [BUILD_A])
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna",
                             {BUILD_A: [report_candidate(BUILD_A)]})
        fallback = FakeMethod("reddit_search", "reddit_community_report", {})
        crash = {"armed": True}

        def promote_crash_once():
            if crash["armed"]:
                crash["armed"] = False
                raise RuntimeError("simulated crash after evidence persistence")
            return {"rc": 0}

        auth = {"promote": promote_crash_once, "qa": lambda: {"rc": 0}, "audit": lambda: {"rc": 0}}
        p = make_pipeline(repo, tmp / "ckpt", write=True, primary=primary, fallback=fallback,
                          authorities=auth)
        state1 = p.run()
        check("G/H first run crashes at PROMOTE (ERROR terminal)", state1.terminal == ERROR)
        check("G/H evidence was persisted before the crash",
              len(load_evidence(repo / "auxsays" / "_data" / "consensus_evidence.yml")) == 1)
        state2 = p.run(resume_run_id=state1.run_id)
        check("G restart does NOT repeat collection (primary fetched exactly once)",
              primary.calls == 1, f"calls={primary.calls}")
        check("H restart does NOT duplicate evidence (still exactly one row)",
              len(load_evidence(repo / "auxsays" / "_data" / "consensus_evidence.yml")) == 1)
        check("G/H resumed run completes DONE", state2.terminal == DONE, str(state2.failures))

    # ---- I. restart before writeback -> one commit maximum --------------------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_fixture_repo(tmp, [BUILD_A])
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna",
                             {BUILD_A: [report_candidate(BUILD_A)]})
        fallback = FakeMethod("reddit_search", "reddit_community_report", {})
        commits = {"n": 0, "armed": True}

        def writeback_crash_once():
            if commits["armed"]:
                commits["armed"] = False
                raise RuntimeError("simulated crash at writeback")
            commits["n"] += 1
            return {"outcome": "push_success_first_attempt", "pages_dispatched": True}

        p = make_pipeline(repo, tmp / "ckpt", write=True, primary=primary, fallback=fallback,
                          writeback=writeback_crash_once)
        state1 = p.run()
        check("I first run crashes at WRITEBACK", state1.terminal == ERROR)
        state2 = p.run(resume_run_id=state1.run_id)
        check("I resumed run commits exactly once", commits["n"] == 1, f"commits={commits['n']}")
        check("I resumed run completes DONE with deploy surfaced",
              state2.terminal == DONE and state2.deploy_result.get("pages_dispatched") is True,
              str(state2.deploy_result))

    # ---- stale checkpoint + unsafe checkpoint dir (checkpoint strategy guarantees) ---------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = make_fixture_repo(tmp, [BUILD_A])
        primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna", {})
        fallback = FakeMethod("reddit_search", "reddit_community_report", {})
        p = make_pipeline(repo, tmp / "ckpt", write=False, primary=primary, fallback=fallback)
        state = p.run()
        (repo / "advance.txt").write_text("x", encoding="utf-8")
        g(repo, "add", "-A")
        g(repo, "commit", "-m", "advance")
        raised = False
        try:
            p.run(resume_run_id=state.run_id)
        except StaleCheckpoint:
            raised = True
        check("stale checkpoint cannot resume onto a fresher base", raised)
        raised = False
        try:
            JsonCheckpointer(repo / "ckpt-inside", repo_root=repo)
        except UnsafeCheckpointDir:
            raised = True
        check("checkpoint dir inside the repo (not ignored) is REFUSED", raised)

    # ---- J. non-PowerPoint products unchanged ---------------------------------------------
    plan = mr.plan_methods("obs-studio")
    check("J non-PowerPoint products get the empty default plan (no orchestrated fallback)",
          plan == {"primary": [], "fallback": [], "fallback_when": []}, str(plan))
    runner_src = (_REPO / "auxsays" / "scripts" / "run_patch_evidence_collection.py").read_text(encoding="utf-8")
    check("J production runner does NOT import the orchestration layer",
          "orchestration" not in runner_src and "method_routing" not in runner_src)
    check("J collect_for_record keeps its production signature (composition refactor only)",
          callable(getattr(ppt, "collect_for_record", None))
          and callable(getattr(ppt, "run_primary_method", None))
          and callable(getattr(ppt, "run_fallback_method", None)))

    # ---- K. no AI credentials / environment -> production graph completes -----------------
    ai_vars = [k for k in os.environ
               if any(t in k.upper() for t in ("OPENAI", "ANTHROPIC", "LANGCHAIN", "LANGSMITH",
                                               "GEMINI", "MISTRAL", "COHERE"))]
    saved = {k: os.environ.pop(k) for k in ai_vars}
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = make_fixture_repo(tmp, [BUILD_A])
            primary = FakeMethod("learn_qna_search_rss", "microsoft_learn_qna",
                                 {BUILD_A: [report_candidate(BUILD_A)]})
            fallback = FakeMethod("reddit_search", "reddit_community_report", {})
            p = make_pipeline(repo, tmp / "ckpt", write=True, primary=primary, fallback=fallback,
                              writeback=lambda: {"outcome": "push_success_first_attempt",
                                                 "pages_dispatched": True})
            state = p.run()
            check("K graph completes DONE with zero AI environment", state.terminal == DONE,
                  str(state.failures))
    finally:
        os.environ.update(saved)
    for module in ("lib/orchestration.py", "lib/method_routing.py", "orchestrate_evidence_run.py"):
        src = (_REPO / "auxsays" / "scripts" / module).read_text(encoding="utf-8")
        bad = [ln.strip() for ln in src.splitlines()
               if ln.strip().startswith(("import ", "from "))
               and any(t in ln for t in ("langchain", "langgraph", "openai", "anthropic"))]
        check(f"K {module} imports no AI/provider packages", not bad, str(bad))

    print()
    print("=" * 70)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 70)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
