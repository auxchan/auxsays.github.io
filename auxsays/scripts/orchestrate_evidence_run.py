#!/usr/bin/env python3
"""AUXSAYS orchestration R1 pilot: PowerPoint evidence run as an explicit, resumable graph.

CONTROL PLANE ONLY. Every decision-bearing step calls an existing deterministic authority --
the PowerPoint collector's own method functions, ``normalize_evidence_row`` /
``append_evidence_rows`` / ``upsert_method_health``, ``reconcile_record_counts``,
``apply_consensus_to_records``, ``qa_patch_records``, ``audit_consensus_evidence`` and
``lib.automation_writeback`` -- and records the structured result into the run state. Nothing
here re-implements acceptance, counting, promotion, validation or writeback logic, and nothing
here requires AI: the module imports only the standard library plus repo-owned code.

PRODUCTION ADOPTION (R2). This is now the authoritative execution path for the PowerPoint lane.
The legacy multi-product runner REFUSES to register any product named in
``AUXSAYS_ORCHESTRATED_PRODUCTS``, so one product can never be collected by both paths in one run
-- the guarantee lives in the collector registry, not in workflow discipline. A write-enabled run
binds the REAL ``lib.automation_writeback`` authority (there is no second writeback
implementation) with this lane's own allow surface, and the validation ordering the production
workflow proved is preserved node-for-node: collect -> reconcile -> promote -> QA -> audit ->
transactional writeback -> deploy, with the writeback authority re-validating the STAGED tree
before it commits, so no state can be committed that was not the state validated.

Lifecycle (linear, with one bounded fallback loop and explicit BLOCKED/ERROR terminals):

  VERIFY_REPO_STATE -> DISCOVER_PATCH_TARGETS -> PLAN_METHODS -> RUN_PRIMARY_METHODS
    -> NORMALIZE_CANDIDATES -> VERIFY_CANDIDATES -> CHECK_ACCEPTED_EVIDENCE
    -> [RESOLVE_CONTEXT -> NORMALIZE -> VERIFY -> CHECK]        (only for missing_exact_build)
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.orchestration import (  # noqa: E402
    BLOCKED, DONE, Graph, JsonCheckpointer, OrchestrationState, inputs_identity,
    run_summary, utc_now,
)
from lib import context_resolution as cr  # noqa: E402
# The resolution budget is ordered with the authority's OWN concreteness predicate, never a local
# re-implementation: prioritisation must not be able to disagree with acceptance.
from patch_collectors.microsoft_powerpoint import concrete_issue as ppt_concrete_issue  # noqa: E402
from lib.method_routing import fallback_justified, plan_methods  # noqa: E402
from lib.patch_identity import is_build_aware, patch_key, require_build  # noqa: E402
from lib.report_counts import reconcile_record_counts  # noqa: E402
from patch_collectors.base import (  # noqa: E402
    CollectorContext, append_evidence_rows, generated_records, load_evidence,
    method_health_row, normalize_evidence_row, upsert_method_health,
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


# The PowerPoint lane's own commit surface and validation commands -- the SAME strings the proven
# production workflow passes to the writeback authority, kept in one place so the orchestrated lane
# and the workflow cannot drift apart.
POWERPOINT_ALLOW = [
    "auxsays/_data/consensus_evidence.yml",
    "auxsays/_data/evidence_method_health.yml",
    "auxsays/updates/generated/*powerpoint*.md",
]
PRODUCTION_VALIDATE = [
    "python auxsays/scripts/qa_patch_records.py",
    "python auxsays/scripts/audit_consensus_evidence.py",
    "python auxsays/scripts/validate_evidence_method_health.py",
]


def default_writeback(repo_root: Path, allow: list[str], *, message: str,
                      pages_cmd: str | None = "gh workflow run pages.yml --ref main",
                      max_retries: int = 5) -> Callable[[], dict[str, Any]]:
    """Bind the REAL ``lib.automation_writeback`` authority. There is no second implementation.

    ``run_writeback`` owns staging against the allow list, the PR #57 equivalence gate (the tree it
    validated is byte-identical to the tree it commits), rebase-on-conflict, push to main and the
    bounded Pages dispatch. This function only supplies configuration; it decides nothing."""
    from lib import automation_writeback as awb  # noqa: PLC0415

    def _writeback() -> dict[str, Any]:
        cfg = awb.WritebackConfig(
            repo=Path(repo_root), message=message, allow=list(allow),
            validate=list(PRODUCTION_VALIDATE), validate_before_commit=True,
            site_paths=list(allow), max_retries=max_retries, pages_cmd=pages_cmd,
            deploy_recovery=True, recovery_site_paths=list(allow),
        )
        return awb.run_writeback(cfg).as_dict()

    return _writeback


def default_context_fetch() -> Callable[[str], tuple[str, str]]:
    """Bind the shared Learn Q&A transport for same-thread context resolution.

    Returns RAW HTML: the segment model reads the page's schema.org structured data, which is how
    a build is attributed to the author who actually stated it."""
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    from patch_collectors import microsoft_learn_qna_source as learn  # noqa: PLC0415

    def _fetch(url: str) -> tuple[str, str]:
        req = urllib.request.Request(url, headers={
            "User-Agent": learn.LEARN_QNA_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read(1_500_000).decode("utf-8", errors="replace")
                if resp.status != 200:
                    return "", "broken"
                low = body.lower()
                if "captcha" in low or "access denied" in low or "request blocked" in low:
                    return "", "blocked"
                return body, "ok"
        except urllib.error.HTTPError as exc:
            return "", "blocked" if exc.code in (401, 403, 429) else "broken"
        except Exception:  # noqa: BLE001 -- transport failure is telemetry, not a crash
            return "", "broken"

    return _fetch


def default_powerpoint_methods() -> dict[str, Callable[..., tuple]]:
    """Bind the collector's OWN extracted method functions -- the production code path."""
    from patch_collectors import microsoft_powerpoint as ppt  # noqa: PLC0415

    def primary(record, target, context, seen, run_urls, captured_at, attempted=True):
        return ppt.run_primary_method(record, target, context, seen, run_urls, captured_at)

    def fallback(record, target, context, seen, run_urls, captured_at, attempted=False):
        return ppt.run_fallback_method(record, target, context, seen, run_urls, captured_at, attempted)

    def stack_exchange(record, target, context, seen, run_urls, captured_at, attempted=True):
        return ppt.run_stack_exchange_method(record, target, context, seen, run_urls, captured_at)

    def github_officedev(record, target, context, seen, run_urls, captured_at, attempted=True):
        return ppt.run_github_method(record, target, context, seen, run_urls, captured_at)

    # Stack Exchange and OfficeDev are PRIMARY, not fallbacks. They discover different populations
    # from Q&A -- a Super User question and a GitHub issue are not the same corpus -- so gating them
    # on Q&A failing would hide reports precisely when Q&A is healthy. Each is a handful of requests.
    return {"learn_qna_search_rss": primary, "reddit_search": fallback,
            "stack_exchange_search": stack_exchange, "github_officedev_issues": github_officedev}


def default_capability(env: dict[str, str] | None) -> dict[str, bool]:
    """Production capability per fallback method. Declaration in a plan is NOT capability."""
    from patch_collectors import microsoft_powerpoint as ppt  # noqa: PLC0415
    return {"reddit_search": ppt.reddit_fallback_enabled(env)}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def resolution_priority(row: dict[str, Any]) -> tuple[int, str]:
    """Sort key deciding which rejected rows get to spend a resolution fetch.

    Reconsidering `missing_powerpoint_version` took the resolvable population from 15 rows to 2155,
    and a budget of 8 fetches then covered 0.4% of it -- the widening made the right report reachable
    in principle and unreachable in practice. Rows are ranked by how close they already are to
    acceptance, using the authority's OWN concreteness predicate so prioritisation can never disagree
    with acceptance:

      0  missing_exact_build          product, version, concreteness and date have all passed
      1  missing_powerpoint_version   and the text describes a concrete post-install failure
      2  everything else              reached only when the budget outlasts the first two

    The URL tiebreak keeps the ordering reproducible for the same input set.
    """
    reason = str(row.get("exclusion_reason") or "")
    if reason == cr.RESOLVABLE_REASON:
        rank = 0
    else:
        text = " ".join(str(row.get(field) or "")
                        for field in ("parent_title", "report_title", "report_text"))
        rank = 1 if ppt_concrete_issue(text) else 2
    return rank, str(row.get("source_url") or "")


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
                 context: CollectorContext | None = None,
                 context_fetch: Callable[[str], tuple[str, str]] | None = None,
                 context_max_fetches: int = 200) -> None:
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
        self.context_fetch = context_fetch
        self.context_max_fetches = int(context_max_fetches)
        self.checkpointer = JsonCheckpointer(checkpoint_dir, repo_root=self.repo_root)
        # PatchRecord objects are genuinely runtime-only (rebuilt by DISCOVER_PATCH_TARGETS on
        # resume). The URL dedup set and the run-wide ownership map are NOT: they are mirrored
        # into serializable state fields and restored before any remaining discovery runs.
        self._records: dict[str, Any] = {}
        self._run_urls: dict[str, str] = {}
        self._seen: dict[str, set[str]] = {}
        # Whether THIS execution is a resume. A new write run demands a clean tree; a resume may
        # legitimately meet a tree its own checkpointed mutation already dirtied.
        self._resuming = False

    # ---- durable discovery-dedup state -------------------------------------

    def _restore_url_state(self, state: OrchestrationState) -> None:
        """Rehydrate the dedup set / ownership map from checkpointed state."""
        self._seen = {k: set(v) for k, v in (state.seen_urls_by_patch or {}).items()}
        self._run_urls = dict(state.accepted_url_owners or {})

    def _persist_url_state(self, state: OrchestrationState) -> None:
        state.seen_urls_by_patch = {k: sorted(v) for k, v in self._seen.items()}
        state.accepted_url_owners = dict(self._run_urls)

    # ---- nodes -------------------------------------------------------------

    def verify_repo_state(self, state: OrchestrationState) -> OrchestrationState:
        self._restore_url_state(state)   # resume: rehydrate dedup/ownership before any discovery
        head = subprocess.run(["git", "-C", str(self.repo_root), "rev-parse", "HEAD"],
                              capture_output=True, text=True)
        state.base_main_sha = head.stdout.strip() if head.returncode == 0 else "no-git"
        porcelain = subprocess.run(["git", "-C", str(self.repo_root), "status", "--porcelain"],
                                   capture_output=True, text=True).stdout
        # Slice the RAW output: porcelain is 'XY<space>PATH', so the first line's leading status
        # space is significant. Stripping first would eat it and shift that one path by a character.
        dirty_paths = [ln[3:].strip() for ln in porcelain.splitlines() if len(ln) > 3]
        state.method_plan["repo_dirty"] = bool(porcelain.strip())
        state.method_plan["dirty_paths"] = dirty_paths
        state.method_plan["resuming"] = self._resuming

        # GATE 1 -- write mode must be fully configured BEFORE any mutating node. The mutating
        # nodes are FINALIZE_EVIDENCE, RECONCILE_COUNTS and PROMOTE; all of them come after this
        # one, so refusing here guarantees the working tree is untouched. A write run without a
        # transactional writeback authority and an explicit allow surface could mutate durable
        # state and then terminate DONE having committed nothing -- durable mutation with no
        # transaction and no commit permission is exactly what must never happen.
        if self.write:
            missing = []
            if self.writeback is None:
                missing.append("writeback_authority")
            if not self.allow_patterns:
                missing.append("allow_patterns")
            if missing:
                state.method_plan["write_config_missing"] = missing
                state.fail("VERIFY_REPO_STATE", "write_mode_unconfigured", ",".join(missing))

            # GATE 1b -- CLEAN START / VALID RESUME. A NEW write run must begin from a clean
            # worktree: pre-existing edits would be swept into this lane's commit, and the
            # writeback's equivalence gate would then refuse mid-run after durable mutation had
            # already happened. A RESUME is different: its own checkpointed FINALIZE/PROMOTE
            # legitimately dirtied the tree, and aborting there would strand exactly the recovery
            # case checkpoints exist for. So a resume is allowed to proceed dirty -- but only
            # within its declared allow surface, which is the same boundary the commit obeys.
            if dirty_paths:
                if not self._resuming:
                    state.method_plan["dirty_on_fresh_write"] = dirty_paths[:20]
                    state.fail("VERIFY_REPO_STATE", "dirty_tree_fresh_write_run",
                               ",".join(dirty_paths[:5]))
                else:
                    outside = [p for p in dirty_paths
                               if not any(fnmatch.fnmatch(p, pat) for pat in self.allow_patterns)]
                    if outside:
                        state.method_plan["resume_dirty_outside_allow"] = outside[:20]
                        state.fail("VERIFY_REPO_STATE", "resume_dirty_outside_allow",
                                   ",".join(outside[:5]))

        # GATE 2 -- R1 only has a real method adapter for products with a declared plan. Running
        # an empty plan and reporting DONE would claim a product was orchestrated when nothing
        # ran. Fail closed instead; this does not touch production collectors.
        unsupported = [p for p in self.product_ids if not plan_methods(p).get("primary")]
        if unsupported:
            state.method_plan["unsupported_products"] = unsupported
            state.fail("VERIFY_REPO_STATE", "unsupported_product", ",".join(unsupported))
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
        self._persist_url_state(state)
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
                fn = self.methods.get(method_id)
                if fn is None:
                    # A plan may name a method this runner has no binding for -- a fixture that
                    # injects its own method map, or a plan entry added ahead of its implementation.
                    # Skipping is honest and keeps the rest of the plan running; raising would take
                    # every other method down with it. Recorded so the gap is visible, not silent.
                    state.receipt(node, f"{identity}:{method_id}:no_binding",
                                  {"method_id": method_id, "skipped": "no_binding"})
                    continue
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
                    # Retained ONLY for the reason context resolution may act on. A rejected row
                    # is a lossless candidate (it carries parent_title/report_title/report_text/
                    # source_url/source_date), so the resolver never has to re-discover anything.
                    # The SET, not the single constant. A report whose version and build both
                    # arrive in the reporter's later comment dies on the VERSION gate before the
                    # build gate is reached, so filtering on missing_exact_build alone made that
                    # whole class unreachable no matter what the resolver could do.
                    "resolvable_rows": [dict(r) for r in rejected
                                        if r.get("exclusion_reason") in cr.RESOLVABLE_REASONS],
                })
                state.candidate_counts[key] = state.candidate_counts.get(key, 0) \
                    + int(health.get("candidates_found") or 0)
                for r, n in reasons.items():
                    state.rejection_counts[r] = state.rejection_counts.get(r, 0) + n
                # Mirror the authority-mutated dedup/ownership state into the checkpoint after
                # every method, so a crash between methods still resumes with them intact.
                self._persist_url_state(state)
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

    def resolve_context(self, state: OrchestrationState) -> OrchestrationState:
        """Segment-scoped exact-build resolution for candidates rejected missing_exact_build ONLY.

        Reads more of the SAME report -- the thread the candidate's own URL points at -- attributes
        a build strictly to the segment whose author stated it, and re-presents the candidate to the
        UNCHANGED acceptance authority. It never infers, never borrows a build from another
        participant, and never consults an unrelated page. A qualifying reply is evaluated as its
        OWN candidate rather than pasted onto somebody else's report; a machine-generated reply is
        never offered at all."""
        from patch_collectors import microsoft_powerpoint as ppt  # noqa: PLC0415

        pending = [(res, row) for res in state.method_results
                   for row in (res.get("resolvable_rows") or [])]
        identity = inputs_identity({"urls": sorted(str(r.get("source_url")) for _, r in pending)})
        if state.has_receipt("RESOLVE_CONTEXT", identity):
            return state
        if not pending or self.context_fetch is None:
            state.method_plan["context_resolution"] = {
                "attempted": 0, "reason": "no resolvable candidates" if not pending
                else "no context transport bound"}
            # Mark done on EVERY exit path. The router sends CHECK_ACCEPTED_EVIDENCE here whenever
            # resolvable rows exist, and the second pass returns to CHECK; without the flag on the
            # no-op path the graph would revisit this node until max_steps and terminate ERROR.
            state.method_plan["context_resolution_done"] = True
            state.receipt("RESOLVE_CONTEXT", identity, {"attempted": 0})
            return state

        # ORDER THE SPEND. Reconsidering `missing_powerpoint_version` took the resolvable population
        # from 15 rows to 2155, and a budget of 8 fetches then covered 0.4% of it -- the widening
        # made the right report reachable in principle and unreachable in practice. Rows are sorted
        # by how close they already are to acceptance, using the SAME production predicate the
        # authority uses, so this is prioritisation and never a second opinion about acceptance:
        #   0  missing_exact_build          product, version, concreteness and date already passed
        #   1  missing_powerpoint_version   AND the text describes a concrete post-install failure
        #   2  everything else              only reached when the budget outlasts the first two
        pending.sort(key=lambda entry: resolution_priority(entry[1]))
        # The budget counts THREAD FETCHES, and ResolutionBudget already caches one fetch per thread
        # URL, so `attempted` (rows) is the wrong denominator for coverage: the same thread is
        # re-queued once per patch record, which inflated 296 real threads into 2153 rows and made a
        # mis-sized budget look like an impossible one. Report the denominator that governs.
        distinct_threads = {str(row.get("source_url") or "") for _res, row in pending}
        eligible_threads = {str(row.get("source_url") or "") for _res, row in pending
                            if resolution_priority(row)[0] <= 1}
        budget = cr.ResolutionBudget(max_fetches=self.context_max_fetches)
        captured_at = utc_now()
        outcomes: list[dict[str, Any]] = []
        resolved_rows: list[dict[str, Any]] = []
        independent_rows: list[dict[str, Any]] = []

        for result, row in pending:
            key = result["patch_key"]
            record = self._records.get(key)
            if record is None:
                continue
            target = {"update_version": key.split("|")[1], "target_build": key.split("|")[2],
                      "target_release_date": getattr(record, "update_published_at", ""),
                      "version_ambiguous": False}
            candidate = {k: row.get(k) for k in ("source_url", "source_date", "source_type",
                                                 "source_name", "parent_title", "report_title")}
            # A rejected row records the report as `report_text_excerpt`; it has NO `report_text`
            # key. Reading the key that never exists handed the resolver an EMPTY report body, so the
            # re-evaluation failed PRODUCT PRIMACY and returned product_not_powerpoint even when
            # resolution had correctly recovered the exact build from the reporter's own comment.
            # The report was discovered, resolved, and then thrown away on a key name.
            candidate["report_text"] = str(row.get("report_text")
                                           or row.get("report_text_excerpt") or "")
            # Pass the row's OWN rejection reason. Hard-coding one reason here meant a row selected
            # for a different resolvable reason was then re-presented as if it had the other, and
            # the resolver's own gate would have refused it.
            outcome = cr.resolve_candidate(candidate,
                                           str(row.get("exclusion_reason") or cr.RESOLVABLE_REASON),
                                           fetch_thread=self.context_fetch, budget=budget)
            entry = outcome.as_dict()
            entry["patch_key"] = key

            if outcome.resolution_result == cr.RESOLVED_EXACT_BUILD:
                rerun = ppt.row_from_candidate(record, target,
                                               cr.augmented_candidate(candidate, outcome),
                                               captured_at)
                entry["reevaluated_counted"] = rerun.get("counted")
                entry["reevaluated_reason"] = rerun.get("exclusion_reason")
                if rerun.get("counted") is True:
                    resolved_rows.append(rerun)

            # A reply that stands on its own is judged on its own merits, never merged into the
            # original poster's report. No extra fetch: this reads the thread already fetched.
            for report in cr.independent_reports(candidate, budget=budget,
                                                 exclude_segment_key=outcome.segment_key,
                                                 issue_predicate=ppt.concrete_issue):
                url_key = str(report.segment_url).strip().rstrip("/").lower()
                if url_key in self._seen.setdefault(key, set()):
                    continue
                self._seen[key].add(url_key)
                own = ppt.row_from_candidate(record, target, report.candidate, captured_at)
                entry.setdefault("independent_reports", []).append({
                    "segment_url": report.segment_url, "author_id": report.author_id,
                    "explicit_build": report.explicit_build, "counted": own.get("counted"),
                    "reason": own.get("exclusion_reason")})
                if own.get("counted") is True:
                    independent_rows.append(own)
            outcomes.append(entry)

        # ONE method result per PATCH TARGET, never one per run. `pending` is flattened across every
        # target in the run, so stamping the aggregate with pending[0]'s key attributed every
        # resolved row -- and the entire health row, with run-wide counters -- to whichever target
        # happened to sort first. verify_candidates then raises "cross-build leakage" and the lane
        # writes nothing at all. Group by each row's OWN canonical identity so a resolution can only
        # ever land on the build it actually belongs to.
        def _row_key(row: dict[str, Any]) -> str:
            return "|".join(patch_key(row.get("product_id"), row.get("update_version"),
                                      row.get("target_build")))

        for key in sorted({str(o.get("patch_key") or "") for o in outcomes}
                          | {_row_key(r) for r in resolved_rows + independent_rows}):
            key_outcomes = [o for o in outcomes if str(o.get("patch_key") or "") == key]
            key_resolved = [r for r in resolved_rows if _row_key(r) == key]
            key_independent = [r for r in independent_rows if _row_key(r) == key]
            if not key_outcomes and not key_resolved and not key_independent:
                continue
            # Land as a distinct method result so identity, health and provenance stay separable
            # from the primary discovery that produced the original candidates. Health is emitted
            # even when nothing resolved -- an honest zero is the point of the telemetry.
            accepted_rows = key_resolved + key_independent
            blocked = sum(1 for o in key_outcomes if o["resolution_result"] == cr.FETCH_BLOCKED)
            broken = sum(1 for o in key_outcomes if o["resolution_result"] == cr.FETCH_BROKEN)
            # Status must come from the SHARED vocabulary; anything outside it is normalized to
            # "broken", which would report a healthy stage as a failure. "The source stated no
            # usable build" is low_confidence, not broken -- a working method finding nothing.
            if blocked and blocked + broken == len(key_outcomes):
                status = "blocked"
            elif broken and blocked + broken == len(key_outcomes):
                status = "broken"
            elif accepted_rows:
                status = "success"
            elif blocked or broken:
                status = "partial"
            else:
                status = "low_confidence"
            state.method_results.append({
                "method_id": cr.METHOD_ID, "role": "context_resolution",
                "patch_key": key, "attempted": True, "fallback_reason": "",
                "status": status,
                "accepted_rows": accepted_rows,
                "rejected_count": 0, "rejection_reasons": {}, "resolvable_rows": [],
                "health_row": method_health_row(
                    product_id=key.split("|")[0], update_version=key.split("|")[1],
                    target_build=key.split("|")[2], method_id=cr.METHOD_ID,
                    source_type="microsoft_learn_qna", status=status,
                    # An independent reply IS a discovered candidate report -- a distinct author's
                    # report found in the already-fetched thread -- so it counts in BOTH
                    # candidates_found and accepted_candidates. The validator enforces
                    # accepted_candidates <= candidates_found AND evidence_rows_added <=
                    # accepted_candidates (evidence_rows_added/public_counted_reports default to
                    # accepted_reports), so excluding independents from either side violates one of
                    # them; that validator is a --validate gate, and a violation refuses the whole
                    # lane's writeback. Per-key grouping removed the run-wide dilution that used to
                    # hide this, so both counters state it explicitly.
                    candidates_found=len(key_outcomes) + len(key_independent),
                    accepted_candidates=len(accepted_rows),
                    accepted_reports=len(accepted_rows),
                    rejected_reports=max(0, len(key_outcomes) - len(key_resolved)),
                    blocked_reason="context_fetch_blocked" if blocked else None,
                    last_run=captured_at,
                    notes=f"segment-scoped exact-build resolution; fetches={budget.fetched}"),
            })
        # Role-attribution telemetry: enough to tell WHY a candidate resolved or did not, without
        # re-reading the source. No hidden semantic resolution -- every count here is the sum of
        # explicit author claims the classifier recorded per build.
        def _role_total(role: str) -> int:
            return sum((o.get("role_counts") or {}).get(role, 0) for o in outcomes)

        resolved_total = sum(1 for o in outcomes
                             if o["resolution_result"] == cr.RESOLVED_EXACT_BUILD)
        state.method_plan["context_resolution"] = {
            "attempted": len(outcomes), "fetches": budget.fetched,
            "resolved": resolved_total,
            "accepted_after_reeval": len(resolved_rows),
            "independent_accepted": len(independent_rows),
            # role attribution
            "builds_found": sum(len(o.get("build_claims") or []) for o in outcomes),
            "current_failing_claims": _role_total(cr.ROLE_CURRENT_FAILING),
            "rollback_claims": _role_total(cr.ROLE_ROLLBACK_PREVIOUS),
            "ambiguous_claims": _role_total(cr.ROLE_AMBIGUOUS),
            "resolved_by_explicit_role": sum(
                1 for o in outcomes
                if o["resolution_result"] == cr.RESOLVED_EXACT_BUILD
                and str(o.get("resolution_match_basis") or "").startswith("explicit_role_")),
            "rejected_conflicting_role": sum(
                1 for o in outcomes if o["resolution_result"] == cr.CONFLICTING_BUILD),
            "outcomes": outcomes,
        }
        state.method_plan["context_resolution_done"] = True
        self._persist_url_state(state)
        state.receipt("RESOLVE_CONTEXT", identity,
                      {"attempted": len(outcomes),
                       "distinct_threads": len(distinct_threads),
                       "eligible_threads": len(eligible_threads),
                                                    "fetches": budget.fetched})
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
            # Scoped to the products THIS run actually collected for. Without the scope the
            # authority walks every generated record, so a pre-existing mismatch on an unrelated
            # product could be rewritten by a run that never collected it.
            changed, details = reconcile_record_counts(rows, self.generated_dir,
                                                       product_ids=set(self.product_ids))
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
        if not self.write:
            state.writeback_result["outcome"] = "skipped_dry_run"
        elif self.writeback is None:
            # Unreachable: VERIFY_REPO_STATE blocks an unconfigured write run before any mutating
            # node. Kept as a hard assertion so a future refactor cannot reintroduce a write run
            # that mutates durable state and then terminates DONE having committed nothing.
            raise RuntimeError("write mode reached WRITEBACK with no writeback authority configured")
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
             "CHECK_ACCEPTED_EVIDENCE", "RESOLVE_CONTEXT", "RUN_FALLBACK_METHODS",
             "FINALIZE_EVIDENCE", "RECONCILE_COUNTS", "PROMOTE", "QA", "AUDIT",
             "PREPARE_WRITEBACK", "WRITEBACK", "DEPLOY", "RECEIPT"]

    # The production validation ordering the live workflow proved, asserted rather than assumed:
    # nothing durable is written before discovery finishes, promotion never precedes the evidence
    # it promotes, QA and audit always run on the promoted tree, and the transactional writeback is
    # the last thing before deploy. A refactor that reorders these fails the invariant, not a run.
    VALIDATION_ORDER = ["FINALIZE_EVIDENCE", "RECONCILE_COUNTS", "PROMOTE", "QA", "AUDIT",
                        "PREPARE_WRITEBACK", "WRITEBACK", "DEPLOY"]

    @classmethod
    def assert_validation_ordering(cls) -> None:
        positions = [cls.ORDER.index(node) for node in cls.VALIDATION_ORDER]
        if positions != sorted(positions):
            raise AssertionError(f"production validation ordering violated: {cls.VALIDATION_ORDER}")
        mutating = cls.ORDER.index("FINALIZE_EVIDENCE")
        if cls.ORDER.index("VERIFY_REPO_STATE") >= mutating:
            raise AssertionError("preconditions must be verified before any mutating node")

    def router(self, node: str, state: OrchestrationState) -> str:
        if node == "VERIFY_REPO_STATE":
            # Every fail-closed precondition is evaluated in the node; routing to BLOCKED here
            # happens BEFORE DISCOVER_PATCH_TARGETS and therefore before any mutating node.
            if state.method_plan.get("write_config_missing") \
                    or state.method_plan.get("unsupported_products") \
                    or state.method_plan.get("dirty_on_fresh_write") \
                    or state.method_plan.get("resume_dirty_outside_allow"):
                return BLOCKED
            if self.write and state.method_plan.get("repo_dirty") and not self.allow_patterns:
                # A dirty tree in write mode with no declared allow surface would be refused by
                # the writeback equivalence gate anyway; block early and say so.
                state.fail(node, "dirty_tree_write_mode")
                return BLOCKED
        if node == "CHECK_ACCEPTED_EVIDENCE":
            # CONDITIONAL context resolution: entered ONLY when discovery actually produced
            # missing_exact_build rejections, and at most once. Any other rejection reason routes
            # straight past it -- a report refused for product, version, date, URL or
            # non-concrete-issue is never made countable by looking at its page.
            resolvable = any(res.get("resolvable_rows") for res in state.method_results)
            if resolvable and not state.method_plan.get("context_resolution_done"):
                return "RESOLVE_CONTEXT"
            decisions = state.method_plan.get("fallback_decisions") or {}
            ran_fallback = any(r["role"] == "fallback" for r in state.method_results)
            if any(d.get("justified") for d in decisions.values()) and not ran_fallback:
                return "RUN_FALLBACK_METHODS"
            return "FINALIZE_EVIDENCE"
        if node in ("RUN_FALLBACK_METHODS", "RESOLVE_CONTEXT"):
            return "NORMALIZE_CANDIDATES"  # bounded second pass over the new rows
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
            "RESOLVE_CONTEXT": self.resolve_context,
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
        self.assert_validation_ordering()
        return Graph(nodes, self.router, checkpointer=self.checkpointer,
                     max_steps=64, max_attempts_per_node=3)

    def run(self, trigger: str = "dispatch", resume_run_id: str | None = None) -> OrchestrationState:
        # Product-level discovery routes are memoised for the lifetime of ONE run. The graph is the
        # only production PowerPoint path and never calls the CLI collector that used to do this, so
        # without an explicit reset a long-lived process would serve one run's index view to the
        # next. Cheap and unconditional: an empty cache is the correct state at every run start.
        try:
            from patch_collectors import microsoft_powerpoint as _ppt
            _ppt.reset_symptom_cache()
        except Exception:                      # noqa: BLE001 - a missing collector is not a run error
            pass
        head = subprocess.run(["git", "-C", str(self.repo_root), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        if resume_run_id:
            state = self.checkpointer.load(resume_run_id, current_base_sha=head or None)
            if state is None:
                raise FileNotFoundError(f"no checkpoint for run {resume_run_id}")
            state.attempt_counts = {}  # attempt bounds apply per execution, not per lifetime
            self._resuming = True
        else:
            self._resuming = False
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
    parser.add_argument("--message", default="Update automated patch evidence",
                        help="commit message for the writeback authority")
    parser.add_argument("--no-pages", action="store_true", default=False,
                        help="do not dispatch Pages (controlled proofs)")
    parser.add_argument("--no-context-resolution", action="store_true", default=False,
                        help="skip same-thread exact-build context resolution")
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--since-days", type=int, default=45)
    args = parser.parse_args(argv)
    repo_root = SCRIPT_DIR.parents[1]
    product_ids = args.product_id or ["microsoft-powerpoint"]

    # PRODUCTION BINDING. A write run gets the REAL writeback authority and this lane's own allow
    # surface; there is no second writeback implementation and no default that could commit outside
    # the declared surface. A dry run binds neither, and VERIFY_REPO_STATE keeps write mode from
    # ever starting unconfigured.
    allow = list(POWERPOINT_ALLOW) if product_ids == ["microsoft-powerpoint"] else []
    writeback = default_writeback(
        repo_root, allow, message=args.message,
        pages_cmd=None if args.no_pages else "gh workflow run pages.yml --ref main",
    ) if (args.write and allow) else None

    since = (datetime.now(timezone.utc) - timedelta(days=max(0, args.since_days))).date().isoformat()
    pipeline = Pipeline(repo_root, product_ids,
                        write=args.write, checkpoint_dir=Path(args.checkpoint_dir),
                        allow_patterns=allow, writeback=writeback,
                        context=CollectorContext(write=args.write, since=since,
                                                 max_pages=args.max_pages),
                        context_fetch=None if args.no_context_resolution
                        else default_context_fetch())
    state = pipeline.run(resume_run_id=args.resume)
    print(json.dumps(run_summary(state), indent=1, sort_keys=True, default=str))
    return 0 if state.terminal == DONE else 1


if __name__ == "__main__":
    raise SystemExit(main())
