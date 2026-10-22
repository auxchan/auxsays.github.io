#!/usr/bin/env python3
"""AUXSAYS orchestration R1: a deterministic, repo-owned graph runner (control plane).

WHY NOT LANGGRAPH (R1 decision, revisit only on evidence). The production dependency surface of
this repo is exactly one package (PyYAML). The pipeline this layer coordinates is a static,
~18-node lifecycle with one conditional branch and bounded loops; LangGraph would add an
order-of-magnitude dependency weight (langgraph, langchain-core, serialization/checkpoint
packages) to GitHub Actions installs for semantics a few hundred audited lines provide
deterministically. The INTERFACE here is deliberately LangGraph-shaped -- nodes are
``state -> state`` callables registered by name, routing is a ``state -> next node name``
function, and checkpointing is a pluggable object -- so adopting LangGraph later is a mechanical
swap if bounded evidence ever justifies it. Production must run with ZERO AI/provider packages;
this module imports only the standard library.

DOCTRINE. The graph is a CONTROL PLANE. Existing deterministic scripts (collectors, QA, audit,
promotion, automation_writeback) remain the DATA/DECISION AUTHORITIES: a node calls an authority,
records its structured result into the run state, and the router chooses the next node. A node
never reimplements authority logic.

Borrowed orchestration principles (adapted, not copied, from prior internal tooling):
  * workflow STATE is authority, not any conversational or ambient context
  * explicit lifecycle nodes with explicit ERROR / BLOCKED terminals
  * bounded execution (max steps, per-node attempt counts)
  * receipts for side effects; a restarted run must not duplicate a receipted side effect
  * stale-checkpoint rejection: a checkpoint taken against an older repo base cannot resume
    onto a fresher main
  * deterministic schemas; no hidden failures
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

CHECKPOINT_VERSION = 1

# Terminal node names. DONE is the only success terminal; ERROR and BLOCKED are explicit,
# distinguishable failure terminals (ERROR = something raised / failed; BLOCKED = a fail-closed
# gate refused to proceed -- nothing is wrong with the run itself).
DONE = "DONE"
ERROR = "ERROR"
BLOCKED = "BLOCKED"
TERMINALS = frozenset({DONE, ERROR, BLOCKED})


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def inputs_identity(payload: Any) -> str:
    """Deterministic identity hash for a node's inputs, used for receipt matching on resume.

    A resumed run may skip a receipted side-effecting node ONLY when the inputs that produced the
    receipt are identical; if upstream state changed, the node must run again (and the authority's
    own idempotency -- evidence dedup, keyed health upsert, no-change writeback -- is the second
    line of defence)."""
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


@dataclass
class OrchestrationState:
    """The single authority for a run. Everything a router decision needs lives here.

    ``patch_targets`` carry CANONICAL patch identity as (product_id, update_version,
    target_build) triples -- target_build is "" for products without a build contract and is
    NEVER inferred. ``receipts`` is keyed by node name; the presence of a receipt with a matching
    inputs identity is what makes restart side-effect-safe."""

    run_id: str = ""
    trigger: str = ""                       # schedule | dispatch | test
    base_main_sha: str = ""                 # repo HEAD at VERIFY_REPO_STATE; stale-resume guard
    product_ids: list[str] = field(default_factory=list)
    patch_targets: list[dict[str, Any]] = field(default_factory=list)
    method_plan: dict[str, Any] = field(default_factory=dict)
    method_results: list[dict[str, Any]] = field(default_factory=list)
    candidate_counts: dict[str, int] = field(default_factory=dict)
    accepted_counts: dict[str, int] = field(default_factory=dict)
    rejection_counts: dict[str, int] = field(default_factory=dict)
    evidence_changes: dict[str, Any] = field(default_factory=dict)
    health_changes: dict[str, Any] = field(default_factory=dict)
    tier2_changes: dict[str, Any] = field(default_factory=dict)
    recent_changes: dict[str, Any] = field(default_factory=dict)
    promotion_changes: dict[str, Any] = field(default_factory=dict)
    qa_result: dict[str, Any] = field(default_factory=dict)
    audit_result: dict[str, Any] = field(default_factory=dict)
    writeback_result: dict[str, Any] = field(default_factory=dict)
    deploy_result: dict[str, Any] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    receipts: dict[str, dict[str, Any]] = field(default_factory=dict)
    attempt_counts: dict[str, int] = field(default_factory=dict)
    node_events: list[dict[str, Any]] = field(default_factory=list)
    # Durable discovery-dedup state. These exist because the collector's acceptance authority
    # depends on them: ``seen_urls_by_patch`` is the per-record cross-METHOD canonical-URL dedup
    # set, and ``accepted_url_owners`` is the run-wide canonical-URL -> patch-identity map that
    # enforces cross-PATCH exclusivity. Held only in memory they would reset on resume, so a
    # resumed run could process a URL twice or attach one report to two patches -- i.e. resumed
    # execution would not be semantically identical to uninterrupted execution. Persisted as
    # sorted lists / plain maps: deterministic, minimal, no transport internals.
    seen_urls_by_patch: dict[str, list[str]] = field(default_factory=dict)
    accepted_url_owners: dict[str, str] = field(default_factory=dict)
    terminal: str = ""                      # set to DONE / ERROR / BLOCKED when the run ends
    checkpoint_version: int = CHECKPOINT_VERSION

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, default=str, indent=1)

    @classmethod
    def from_json(cls, text: str) -> "OrchestrationState":
        data = json.loads(text)
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    def fail(self, node: str, reason: str, detail: str = "") -> None:
        self.failures.append({"node": node, "reason": reason, "detail": detail,
                              "at": utc_now()})

    def receipt(self, node: str, identity: str, summary: dict[str, Any]) -> None:
        """Record a completed side effect. Presence + identity match => resume skips the node."""
        self.receipts[node] = {"inputs_identity": identity, "summary": summary,
                               "at": utc_now()}

    def has_receipt(self, node: str, identity: str) -> bool:
        rec = self.receipts.get(node)
        return bool(rec) and rec.get("inputs_identity") == identity


class StaleCheckpoint(Exception):
    """The checkpoint was taken against an older repo base than the current one."""


class UnsafeCheckpointDir(Exception):
    """The checkpoint directory sits inside the repo working tree without being git-ignored.

    A non-ignored file written into the tree during a write run would be residual material the
    writeback equivalence gate (PR #57) rightly refuses -- so the orchestrator refuses to create
    it in the first place."""


class JsonCheckpointer:
    """One JSON checkpoint file per run, rewritten after every completed node.

    Storage is deliberately file-based and caller-located: no database, no service. Production
    callers point this OUTSIDE the repo working tree (e.g. the Actions runner temp dir)."""

    def __init__(self, directory: Path, repo_root: Path | None = None) -> None:
        self.directory = Path(directory)
        if repo_root is not None:
            self._refuse_unsafe_location(Path(repo_root))
        self.directory.mkdir(parents=True, exist_ok=True)

    def _refuse_unsafe_location(self, repo_root: Path) -> None:
        try:
            rel = self.directory.resolve().relative_to(repo_root.resolve())
        except ValueError:
            return  # outside the repo: always safe
        probe = str(rel / "probe.json")
        rc = subprocess.run(["git", "-C", str(repo_root), "check-ignore", "-q", probe],
                            capture_output=True).returncode
        if rc != 0:
            raise UnsafeCheckpointDir(
                f"checkpoint dir {self.directory} is inside the repo and not git-ignored; "
                "it would appear as residual material to the writeback equivalence gate")

    def path_for(self, run_id: str) -> Path:
        return self.directory / f"orchestration-{run_id}.json"

    def save(self, state: OrchestrationState) -> Path:
        path = self.path_for(state.run_id)
        path.write_text(state.to_json(), encoding="utf-8")
        return path

    def load(self, run_id: str, current_base_sha: str | None = None) -> OrchestrationState | None:
        path = self.path_for(run_id)
        if not path.exists():
            return None
        state = OrchestrationState.from_json(path.read_text(encoding="utf-8"))
        if state.checkpoint_version != CHECKPOINT_VERSION:
            raise StaleCheckpoint(f"checkpoint version {state.checkpoint_version} != {CHECKPOINT_VERSION}")
        if current_base_sha and state.base_main_sha and state.base_main_sha != current_base_sha:
            # Fail closed: resuming a run planned against an older base onto a fresher main could
            # replay decisions that no longer hold. The caller starts a fresh run instead.
            raise StaleCheckpoint(
                f"checkpoint base {state.base_main_sha[:12]} != current {current_base_sha[:12]}")
        return state


NodeFn = Callable[[OrchestrationState], OrchestrationState]
RouterFn = Callable[[str, OrchestrationState], str]


class Graph:
    """Minimal deterministic graph runner: named nodes, one router, bounded steps.

    Each step: run the node (recording a structured event), checkpoint, ask the router for the
    next node name. A node that raises routes to ERROR with the failure recorded -- no hidden
    failures. ``max_attempts_per_node`` bounds loops structurally even if a router misroutes."""

    def __init__(self, nodes: dict[str, NodeFn], router: RouterFn,
                 checkpointer: JsonCheckpointer | None = None,
                 max_steps: int = 64, max_attempts_per_node: int = 2) -> None:
        self.nodes = dict(nodes)
        self.router = router
        self.checkpointer = checkpointer
        self.max_steps = max_steps
        self.max_attempts_per_node = max_attempts_per_node

    def run(self, state: OrchestrationState, start: str) -> OrchestrationState:
        current = start
        for _step in range(self.max_steps):
            if current in TERMINALS:
                state.terminal = current
                if self.checkpointer:
                    self.checkpointer.save(state)
                return state
            node_fn = self.nodes.get(current)
            if node_fn is None:
                state.fail(current, "unknown_node")
                state.terminal = ERROR
                return state
            attempts = state.attempt_counts.get(current, 0) + 1
            state.attempt_counts[current] = attempts
            if attempts > self.max_attempts_per_node:
                state.fail(current, "attempt_bound_exceeded", f"attempts={attempts}")
                state.terminal = ERROR
                return state
            event: dict[str, Any] = {"node": current, "started_at": utc_now(),
                                     "attempt": attempts}
            t0 = time.monotonic()
            try:
                state = node_fn(state)
                event["status"] = "ok"
            except Exception as exc:  # noqa: BLE001 -- convert to an explicit ERROR terminal
                event["status"] = "error"
                event["failure_reason"] = f"{type(exc).__name__}: {exc}"
                state.fail(current, type(exc).__name__, str(exc))
            event["completed_at"] = utc_now()
            event["elapsed_s"] = round(time.monotonic() - t0, 3)
            state.node_events.append(event)
            if self.checkpointer:
                self.checkpointer.save(state)
            if event["status"] == "error":
                state.terminal = ERROR
                if self.checkpointer:
                    self.checkpointer.save(state)
                return state
            current = self.router(current, state)
        state.fail(current, "max_steps_exceeded", f"max_steps={self.max_steps}")
        state.terminal = ERROR
        if self.checkpointer:
            self.checkpointer.save(state)
        return state


def run_summary(state: OrchestrationState) -> dict[str, Any]:
    """The single structured answer to 'what did this run do'."""
    methods_run = sorted({str(r.get("method_id")) for r in state.method_results if r.get("attempted")})
    methods_failed = sorted({str(r.get("method_id")) for r in state.method_results
                             if r.get("status") in {"blocked", "broken"}})
    fallbacks = sorted({str(r.get("method_id")) for r in state.method_results
                        if r.get("role") == "fallback" and r.get("attempted")})
    return {
        "run_id": state.run_id,
        "trigger": state.trigger,
        "terminal": state.terminal,
        "base_main_sha": state.base_main_sha,
        "products": state.product_ids,
        "patches": [t.get("patch_key") for t in state.patch_targets],
        "methods_run": methods_run,
        "methods_failed": methods_failed,
        "fallbacks_invoked": fallbacks,
        "candidate_counts": state.candidate_counts,
        "accepted_counts": state.accepted_counts,
        "rejection_counts": state.rejection_counts,
        "evidence_changes": state.evidence_changes,
        "health_changes": state.health_changes,
        "promotion_changes": state.promotion_changes,
        "qa_result": state.qa_result,
        "audit_result": state.audit_result,
        "writeback_result": state.writeback_result,
        "deploy_result": state.deploy_result,
        "failures": state.failures,
        "receipts": {k: v.get("summary") for k, v in state.receipts.items()},
    }
