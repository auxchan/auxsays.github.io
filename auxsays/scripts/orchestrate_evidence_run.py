#!/usr/bin/env python3
"""AUXSAYS orchestration R1 pilot: PowerPoint evidence run as an explicit, resumable graph.

CONTROL PLANE ONLY. Every decision-bearing step calls an existing deterministic authority --
the PowerPoint collector's own method functions, ``normalize_evidence_row`` /
``append_evidence_rows`` / ``upsert_method_health``, ``reconcile_record_counts``,
``apply_consensus_to_records``, ``qa_patch_records``, ``audit_consensus_evidence`` and
``lib.automation_writeback`` -- and records the structured result into the run state. Nothing
here re-implements acceptance, counting, promotion, validation or writeback logic, and nothing
here requires AI: the module imports only the standard library plus repo-owned code.

This pilot is NOT wired into the production workflow in R1. The production evidence lane keeps
its proven step sequence; this layer exists so multi-method discovery, fallback justification and
pipeline state are explicit, checkpointable and diagnosable before any workflow adoption.

Lifecycle (linear, with one bounded fallback loop and explicit BLOCKED/ERROR terminals):

  VERIFY_REPO_STATE -> DISCOVER_PATCH_TARGETS -> PLAN_METHODS -> RUN_PRIMARY_METHODS
    -> NORMALIZE_CANDIDATES -> VERIFY_CANDIDATES -> CHECK_ACCEPTED_EVIDENCE
    -> [RUN_FALLBACK_METHODS -> NORMALIZE -> VERIFY -> CHECK]   (at most once)
    -> FINALIZE_EVIDENCE -> RECONCILE_COUNTS -> PROMOTE -> QA -> AUDIT
    -> PREPARE_WRITEBACK -> WRITEBACK -> DEPLOY -> RECEIPT -> DONE
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.orchestration import (  # noqa: E402
    BLOCKED, DONE, Graph, JsonCheckpointer, OrchestrationState, inputs_identity,
    run_summary, utc_now,
)
from lib.method_routing import fallback_justified, plan_methods  # noqa: E402
from lib.patch_identity import is_build_aware, patch_key, require_build  # noqa: E402
from lib.report_counts import reconcile_record_counts  # noqa: E402
from patch_collectors.base import (  # noqa: E402
    CollectorContext, append_evidence_rows, generated_records, load_evidence,
    normalize_evidence_row, upsert_method_health,
)


# ---------------------------------------------------------------------------
# Default authority bindings. Tests inject substitutes with identical signatures; production
# uses these, which call the same scripts the workflow runs.
# ---------------------------------------------------------------------------

def _script(repo_root: Path, name: str, *args: str) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, str(repo_root / "auxsays" / "scripts" / name), *args],
                          cwd=str(repo_root), capture_output=True, text=True)
    return {"rc": proc.returncode, "tail": (proc.stdout or "").strip().splitlines()[-3:]}


def default_authorities(repo_root: Path, product_id: str, write: bool) -> dict[str, Callable[..., dict[str, Any]]]:
    def promote() -> dict[str, Any]:
        mode = ["--write-all", "--confirm-write"] if write else ["--dry-run"]
        return _script(repo_root, "apply_consensus_to_records.py", "--product-id", product_id, *mode)

    return {
        "promote": promote,
        "qa": lambda: _script(repo_root, "qa_patch_records.py"),
        "audit": lambda: _script(repo_root, "audit_consensus_evidence.py"),
    }


def default_powerpoint_methods() -> dict[str, Callable[..., tuple]]:
    """Bind the collector's OWN extracted method functions -- the production code path."""
    from patch_collectors import microsoft_powerpoint as ppt  # noqa: PLC0415

    def primary(record, target, context, seen, run_urls, captured_at, attempted=True):
        return ppt.run_primary_method(record, target, context, seen, run_urls, captured_at)

    def fallback(record, target, context, seen, run_urls, captured_at, attempted=False):
        return ppt.run_fallback_method(record, target, context, seen, run_urls, captured_at, attempted)

    return {"learn_qna_search_rss": primary, "reddit_search": fallback}


def default_capability(env: dict[str, str] | None) -> dict[str, bool]:
    """Production capability per fallback method. Declaration in a plan is NOT capability."""
    from patch_collectors import microsoft_powerpoint as ppt  # noqa: PLC0415
    return {"reddit_search": ppt.reddit_fallback_enabled(env)}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    def __init__(self, repo_root: Path, product_ids: list[str], *, write: bool,
                 checkpoint_dir: Path, evidence_path: Path | None = None,
                 health_path: Path | None = None, generated_dir: Path | None = None,
                 methods: dict[str, Callable] | None = None,
                 authorities: dict[str, Callable] | None = None,
                 capability: dict[str, bool] | None = None,
                 allow_patterns: list[str] | None = None,
                 writeback: Callable[..., dict[str, Any]] | None = None,
                 env: dict[str, str] | None = None,
                 context: CollectorContext | None = None) -> None:
        self.repo_root = Path(repo_root)
        self.product_ids = list(product_ids)
        self.write = bool(write)
        self.evidence_path = evidence_path or (self.repo_root / "auxsays" / "_data" / "consensus_evidence.yml")
        self.health_path = health_path or (self.repo_root / "auxsays" / "_data" / "evidence_method_health.yml")
        self.generated_dir = generated_dir or (self.repo_root / "auxsays" / "updates" / "generated")
        self.methods = methods if methods is not None else default_powerpoint_methods()
        self.authorities = authorities if authorities is not None else default_authorities(
            self.repo_root, self.product_ids[0] if self.product_ids else "", self.write)
        self.capability = capability if capability is not None else default_capability(env)
        self.allow_patterns = allow_patterns or []
        self.writeback = writeback
        self.context = context or CollectorContext(write=self.write, since=None, max_pages=1)
        self.checkpointer = JsonCheckpointer(checkpoint_dir, repo_root=self.repo_root)
        # Runtime-only (never serialized): PatchRecord objects keyed by patch_key string.
        self._records: dict[str, Any] = {}
        self._run_urls: dict[str, str] = {}
        self._seen: dict[str, set[str]] = {}

    # ---- nodes -------------------------------------------------------------

    def verify_repo_state(self, state: OrchestrationState) -> OrchestrationState:
        head = subprocess.run(["git", "-C", str(self.repo_root), "rev-parse", "HEAD"],
                              capture_output=True, text=True)
        state.base_main_sha = head.stdout.strip() if head.returncode == 0 else "no-git"
        porcelain = subprocess.run(["git", "-C", str(self.repo_root), "status", "--porcelain"],
                                   capture_output=True, text=True).stdout.strip()
        state.method_plan["repo_dirty"] = bool(porcelain)
        return state

    def discover_patch_targets(self, state: OrchestrationState) -> OrchestrationState:
        # Call the AUTHORITY's record scanner verbatim, pointed at this pipeline's generated dir
        # (the authority reads a module-level GENERATED_DIR; save/patch/restore keeps its
        # filtering -- update_entry, product match, archived handling -- exactly as production).
        import patch_collectors.base as _base  # noqa: PLC0415
        targets: list[dict[str, Any]] = []
        original_dir = _base.GENERATED_DIR
        _base.GENERATED_DIR = Path(self.generated_dir)
        try:
            discovered = {pid: generated_records(pid) for pid in self.product_ids}
        finally:
            _base.GENERATED_DIR = original_dir
        for product_id in self.product_ids:
            for record in discovered[product_id]:
                build = getattr(record, "target_build", "") or ""
                if is_build_aware(product_id):
                    require_build(product_id, record.update_version, build,
                                  f"patch target {record.path.name}")
                key = "|".join(patch_key(product_id, record.update_version, build))
                targets.append({"patch_key": key, "product_id": product_id,
                                "update_version": record.update_version, "target_build": build})
                self._records[key] = record
                self._seen.setdefault(key, set())
        state.patch_targets = targets
        return state

    def plan_methods_node(self, state: OrchestrationState) -> OrchestrationState:
        plans = {pid: plan_methods(pid) for pid in self.product_ids}
        state.method_plan.update({"plans": plans, "fallback_evaluated": False})
        return state

    def _run_methods(self, state: OrchestrationState, role: str) -> OrchestrationState:
        node = "RUN_PRIMARY_METHODS" if role == "primary" else "RUN_FALLBACK_METHODS"
        # Identity is scoped to THIS role's inputs only: the primary's identity must not include
        # fallback decisions, which do not exist yet when the primary first runs but do exist in
        # a resumed checkpoint -- including them would defeat the receipt skip on restart.
        plans = state.method_plan.get("plans") or {}
        role_inputs: dict[str, Any] = {"role": role,
                                       "targets": [t["patch_key"] for t in state.patch_targets],
                                       "methods": {pid: plans.get(pid, {}).get(role, [])
                                                   for pid in self.product_ids}}
        if role == "fallback":
            role_inputs["decisions"] = state.method_plan.get("fallback_decisions")
        identity = inputs_identity(role_inputs)
        if state.has_receipt(node, identity):
            return state  # restart: discovery already receipted; do not re-fetch
        captured_at = utc_now()
        for target in state.patch_targets:
            key = target["patch_key"]
            record = self._records.get(key)
            plan = state.method_plan["plans"].get(target["product_id"], {})
            for method_id in plan.get(role, []):
                attempted = True
                reason = ""
                if role == "fallback":
                    decision = (state.method_plan.get("fallback_decisions") or {}).get(key, {})
                    justified, reason = decision.get("justified", False), decision.get("reason", "")
                    capable = self.capability.get(method_id, False)
                    attempted = bool(justified and capable)
                fn = self.methods[method_id]
                t = {"update_version": target["update_version"], "target_build": target["target_build"],
                     "target_release_date": getattr(record, "update_published_at", ""),
                     "version_ambiguous": False}
                accepted, rejected, health = fn(record, t, self.context, self._seen[key],
                                               self._run_urls, captured_at, attempted=attempted)
                reasons: dict[str, int] = {}
                for row in rejected:
                    r = str(row.get("exclusion_reason") or "?")
                    reasons[r] = reasons.get(r, 0) + 1
                state.method_results.append({
                    "method_id": method_id, "role": role, "patch_key": key,
                    "attempted": attempted, "fallback_reason": reason,
                    "status": health.get("status"),
                    "accepted_rows": accepted, "rejected_count": len(rejected),
                    "rejection_reasons": reasons, "health_row": health,
                })
                state.candidate_counts[key] = state.candidate_counts.get(key, 0) \
                    + int(health.get("candidates_found") or 0)
                for r, n in reasons.items():
                    state.rejection_counts[r] = state.rejection_counts.get(r, 0) + n
        state.receipt(node, identity, {"methods": len(state.method_results)})
        return state

    def run_primary_methods(self, state: OrchestrationState) -> OrchestrationState:
        return self._run_methods(state, "primary")

    def run_fallback_methods(self, state: OrchestrationState) -> OrchestrationState:
        return self._run_methods(state, "fallback")

    def normalize_candidates(self, state: OrchestrationState) -> OrchestrationState:
        for result in state.method_results:
            if not result.get("normalized"):
                result["accepted_rows"] = [normalize_evidence_row(r) for r in result["accepted_rows"]]
                result["normalized"] = True
        return state

    def verify_candidates(self, state: OrchestrationState) -> OrchestrationState:
        """Invariant assertion, not re-scoring: every counted row for a build-aware product must
        carry ITS OWN patch target's exact build -- cross-build leakage is a hard error."""
        for result in state.method_results:
            target_build = result["patch_key"].split("|")[2]
            product_id = result["patch_key"].split("|")[0]
            for row in result["accepted_rows"]:
                if row.get("counted") is False:
                    continue
                build = require_build(product_id, row.get("update_version"),
                                      row.get("target_build"), "verify_candidates")
                if is_build_aware(product_id) and build != target_build:
                    raise ValueError(f"cross-build leakage: row build {build!r} attached to "
                                     f"target {result['patch_key']!r}")
        return state

    def check_accepted_evidence(self, state: OrchestrationState) -> OrchestrationState:
        counts: dict[str, int] = {}
        for result in state.method_results:
            counts[result["patch_key"]] = counts.get(result["patch_key"], 0) \
                + sum(1 for r in result["accepted_rows"] if r.get("counted") is not False)
        for t in state.patch_targets:
            counts.setdefault(t["patch_key"], 0)
        state.accepted_counts = counts
        if not state.method_plan.get("fallback_evaluated"):
            decisions: dict[str, Any] = {}
            for t in state.patch_targets:
                key = t["patch_key"]
                plan = state.method_plan["plans"].get(t["product_id"], {})
                primary_health = [r["health_row"] for r in state.method_results
                                  if r["patch_key"] == key and r["role"] == "primary"]
                justified, reason = fallback_justified(primary_health, counts.get(key, 0),
                                                       plan.get("fallback_when", []))
                decisions[key] = {"justified": justified, "reason": reason}
            state.method_plan["fallback_decisions"] = decisions
            state.method_plan["fallback_evaluated"] = True
        return state

    def finalize_evidence(self, state: OrchestrationState) -> OrchestrationState:
        counted = [r for res in state.method_results for r in res["accepted_rows"]
                   if r.get("counted") is not False]
        health = [res["health_row"] for res in state.method_results]
        identity = inputs_identity({"rows": sorted(str(r.get("id")) for r in counted),
                                    "health": sorted(str(h.get("method_id")) + str(h.get("update_version"))
                                                     + str(h.get("target_build")) for h in health)})
        if state.has_receipt("FINALIZE_EVIDENCE", identity):
            return state
        if not self.write:
            state.evidence_changes = {"mode": "dry", "would_add": len(counted)}
            state.health_changes = {"mode": "dry", "would_upsert": len(health)}
        else:
            added, dupes, _ = append_evidence_rows(counted, self.evidence_path) if counted \
                else (0, 0, load_evidence(self.evidence_path) if self.evidence_path.exists() else [])
            changed, total, _ = upsert_method_health(health, self.health_path)
            state.evidence_changes = {"mode": "write", "added": added, "duplicates": dupes}
            state.health_changes = {"mode": "write", "changed": changed, "total": total}
        state.receipt("FINALIZE_EVIDENCE", identity,
                      {**state.evidence_changes, **{"health_" + k: v for k, v in state.health_changes.items()}})
        return state

    def reconcile_counts(self, state: OrchestrationState) -> OrchestrationState:
        identity = inputs_identity({"evidence": state.evidence_changes, "targets":
                                    [t["patch_key"] for t in state.patch_targets]})
        if state.has_receipt("RECONCILE_COUNTS", identity):
            return state
        if self.write:
            rows = load_evidence(self.evidence_path) if self.evidence_path.exists() else []
            changed, details = reconcile_record_counts(rows, self.generated_dir)
            state.promotion_changes["reconciled"] = changed
        else:
            state.promotion_changes["reconciled"] = 0
        state.receipt("RECONCILE_COUNTS", identity, {"reconciled": state.promotion_changes["reconciled"]})
        return state

    def promote(self, state: OrchestrationState) -> OrchestrationState:
        identity = inputs_identity({"counts": state.accepted_counts, "write": self.write})
        if state.has_receipt("PROMOTE", identity):
            return state
        state.promotion_changes["promotion"] = self.authorities["promote"]()
        state.receipt("PROMOTE", identity, {"rc": state.promotion_changes["promotion"].get("rc")})
        return state

    def qa(self, state: OrchestrationState) -> OrchestrationState:
        state.qa_result = self.authorities["qa"]()
        return state

    def audit(self, state: OrchestrationState) -> OrchestrationState:
        state.audit_result = self.authorities["audit"]()
        return state

    def prepare_writeback(self, state: OrchestrationState) -> OrchestrationState:
        """Observability + early fail-closed mirror of the writeback authority's own gate."""
        porcelain = subprocess.run(["git", "-C", str(self.repo_root), "status", "--porcelain"],
                                   capture_output=True, text=True).stdout
        changed = [ln[3:].strip() for ln in porcelain.splitlines() if len(ln) > 3]
        state.writeback_result["changed_paths"] = changed
        if self.allow_patterns:
            outside = [p for p in changed
                       if not any(fnmatch.fnmatch(p, pat) for pat in self.allow_patterns)]
            state.writeback_result["paths_outside_allow"] = outside
        return state

    def writeback_node(self, state: OrchestrationState) -> OrchestrationState:
        identity = inputs_identity({"paths": state.writeback_result.get("changed_paths"),
                                    "base": state.base_main_sha})
        if state.has_receipt("WRITEBACK", identity):
            return state
        if not self.write or self.writeback is None:
            state.writeback_result["outcome"] = "skipped_dry_run" if not self.write else "no_writeback_configured"
        else:
            result = self.writeback()
            state.writeback_result.update(result)
        state.receipt("WRITEBACK", identity, {"outcome": state.writeback_result.get("outcome")})
        return state

    def deploy(self, state: OrchestrationState) -> OrchestrationState:
        # The writeback authority owns Pages dispatch; this node only surfaces its result.
        state.deploy_result = {
            "pages_dispatched": state.writeback_result.get("pages_dispatched", False),
            "deployment_pending": state.writeback_result.get("deployment_pending", False),
        }
        return state

    def receipt_node(self, state: OrchestrationState) -> OrchestrationState:
        summary = run_summary(state)
        path = self.checkpointer.directory / f"summary-{state.run_id}.json"
        path.write_text(json.dumps(summary, indent=1, sort_keys=True, default=str), encoding="utf-8")
        state.receipts.setdefault("RECEIPT", {"inputs_identity": "final",
                                              "summary": {"path": str(path)}, "at": utc_now()})
        return state

    # ---- graph -------------------------------------------------------------

    ORDER = ["VERIFY_REPO_STATE", "DISCOVER_PATCH_TARGETS", "PLAN_METHODS",
             "RUN_PRIMARY_METHODS", "NORMALIZE_CANDIDATES", "VERIFY_CANDIDATES",
             "CHECK_ACCEPTED_EVIDENCE", "RUN_FALLBACK_METHODS", "FINALIZE_EVIDENCE",
             "RECONCILE_COUNTS", "PROMOTE", "QA", "AUDIT", "PREPARE_WRITEBACK",
             "WRITEBACK", "DEPLOY", "RECEIPT"]

    def router(self, node: str, state: OrchestrationState) -> str:
        if node == "VERIFY_REPO_STATE" and self.write and state.method_plan.get("repo_dirty") \
                and not self.allow_patterns:
            # Fail closed: a dirty tree in write mode with no declared allow surface would be
            # refused by the writeback equivalence gate anyway; block early and say so.
            state.fail(node, "dirty_tree_write_mode")
            return BLOCKED
        if node == "CHECK_ACCEPTED_EVIDENCE":
            decisions = state.method_plan.get("fallback_decisions") or {}
            ran_fallback = any(r["role"] == "fallback" for r in state.method_results)
            if any(d.get("justified") for d in decisions.values()) and not ran_fallback:
                return "RUN_FALLBACK_METHODS"
            return "FINALIZE_EVIDENCE"
        if node == "RUN_FALLBACK_METHODS":
            return "NORMALIZE_CANDIDATES"  # bounded second pass over fallback rows
        if node == "QA" and state.qa_result.get("rc", 0) != 0:
            state.fail(node, "qa_failed", str(state.qa_result))
            return BLOCKED
        if node == "AUDIT" and state.audit_result.get("rc", 0) != 0:
            state.fail(node, "audit_failed", str(state.audit_result))
            return BLOCKED
        if node == "RECEIPT":
            return DONE
        return self.ORDER[self.ORDER.index(node) + 1]

    def build(self) -> Graph:
        nodes = {
            "VERIFY_REPO_STATE": self.verify_repo_state,
            "DISCOVER_PATCH_TARGETS": self.discover_patch_targets,
            "PLAN_METHODS": self.plan_methods_node,
            "RUN_PRIMARY_METHODS": self.run_primary_methods,
            "NORMALIZE_CANDIDATES": self.normalize_candidates,
            "VERIFY_CANDIDATES": self.verify_candidates,
            "CHECK_ACCEPTED_EVIDENCE": self.check_accepted_evidence,
            "RUN_FALLBACK_METHODS": self.run_fallback_methods,
            "FINALIZE_EVIDENCE": self.finalize_evidence,
            "RECONCILE_COUNTS": self.reconcile_counts,
            "PROMOTE": self.promote,
            "QA": self.qa,
            "AUDIT": self.audit,
            "PREPARE_WRITEBACK": self.prepare_writeback,
            "WRITEBACK": self.writeback_node,
            "DEPLOY": self.deploy,
            "RECEIPT": self.receipt_node,
        }
        return Graph(nodes, self.router, checkpointer=self.checkpointer,
                     max_steps=64, max_attempts_per_node=3)

    def run(self, trigger: str = "dispatch", resume_run_id: str | None = None) -> OrchestrationState:
        head = subprocess.run(["git", "-C", str(self.repo_root), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        if resume_run_id:
            state = self.checkpointer.load(resume_run_id, current_base_sha=head or None)
            if state is None:
                raise FileNotFoundError(f"no checkpoint for run {resume_run_id}")
            state.attempt_counts = {}  # attempt bounds apply per execution, not per lifetime
        else:
            state = OrchestrationState(run_id=uuid.uuid4().hex[:12], trigger=trigger,
                                       product_ids=list(self.product_ids))
        return self.build().run(state, "VERIFY_REPO_STATE")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AUXSAYS orchestration R1 pilot runner.")
    parser.add_argument("--product-id", action="append", default=None)
    parser.add_argument("--write", action="store_true", default=False)
    parser.add_argument("--checkpoint-dir", required=True,
                        help="MUST be outside the repo tree (or git-ignored); refused otherwise.")
    parser.add_argument("--resume", default=None, help="run_id of a checkpoint to resume")
    args = parser.parse_args(argv)
    repo_root = SCRIPT_DIR.parents[1]
    pipeline = Pipeline(repo_root, args.product_id or ["microsoft-powerpoint"],
                        write=args.write, checkpoint_dir=Path(args.checkpoint_dir))
    state = pipeline.run(resume_run_id=args.resume)
    print(json.dumps(run_summary(state), indent=1, sort_keys=True, default=str))
    return 0 if state.terminal == DONE else 1


if __name__ == "__main__":
    raise SystemExit(main())
