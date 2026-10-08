#!/usr/bin/env python3
"""Premiere discovery routing, and the health semantics that make it honest.

Routing decides WHICH acquisition method runs. It must never decide what counts, and it must never
let a method it declined to call look like a method that failed.

The measurement this protects (current main, both live Premiere records, scheduled shape
--since-days 45 --max-pages 5): the nine-method flat loop took 546.8s over 219 HTTP requests;
wayback_snapshot_recheck was 408.5s and reddit_search 92.3s of that, and both returned zero
candidates. Routed, the same records take 12.1s over 12 requests and accept the same 4 and 18
reports. That is the whole point, and the assertions below are what stops it from being bought with
weaker acceptance or a prettier-looking telemetry file.

Offline: no network, no repo writes.
"""
from __future__ import annotations

import importlib.util
import sys
import traceback
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib import method_routing as mr                      # noqa: E402
from patch_collectors import adobe_premiere as ap         # noqa: E402
from patch_collectors.base import CollectorContext        # noqa: E402

PRODUCT = "adobe-premiere-pro"
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


class Recorder:
    """Swaps every discovery method for a stub that records whether it was called."""

    def __init__(self, yields: dict[str, list[dict]] | None = None,
                 raises: dict[str, Exception] | None = None):
        self.called: list[str] = []
        self.yields = yields or {}
        self.raises = raises or {}
        self._saved: dict = {}

    def __enter__(self):
        self._saved = dict(ap.PREMIERE_METHODS)
        for method_id in list(ap.PREMIERE_METHODS):
            ap.PREMIERE_METHODS[method_id] = self._stub(method_id)
        return self

    def __exit__(self, *exc):
        ap.PREMIERE_METHODS.clear()
        ap.PREMIERE_METHODS.update(self._saved)
        return False

    def _stub(self, method_id: str):
        def stub(record, context, errors):
            self.called.append(method_id)
            if method_id in self.raises:
                errors.append({"source_url": "https://example.invalid",
                               "reason": str(self.raises[method_id])})
                return []
            return list(self.yields.get(method_id, []))
        return stub


def a_record():
    return ap.generated_records(PRODUCT, [], include_archived=False)[0]


def a_context():
    return CollectorContext(write=False, since="2026-01-01", max_pages=5, target_versions=[])


def health_by_method(health: list[dict]) -> dict[str, str]:
    return {str(h["method_id"]): str(h["status"]) for h in health}


def run_suite() -> int:
    plan = mr.plan_methods(PRODUCT)

    print("=" * 92)
    print("A-B  Premiere declares a shared routing plan, with Algolia as the primary")
    print("=" * 92)
    check("A.1 Premiere has a plan in the SHARED router, not a private one",
          PRODUCT in mr.METHOD_PLANS)
    check("A.2 the plan is reached through the shared accessor", bool(plan.get("primary")))
    check("B.1 Algolia is the only primary",
          plan["primary"] == ["adobe_community_algolia_search"], str(plan["primary"]))
    check("B.2 the known-URL recheck is the declared fallback",
          plan["fallback"] == ["adobe_community_known_url_recheck"], str(plan["fallback"]))
    check("B.3 wayback is probe-only",
          plan["probe_only"] == ["wayback_snapshot_recheck"], str(plan["probe_only"]))
    check("B.4 six methods are declared disabled", len(plan["disabled"]) == 6,
          str(plan["disabled"]))
    check("B.5 every one of the nine implemented methods has exactly one declared role",
          sorted(plan["primary"] + plan["fallback"] + plan["probe_only"] + plan["disabled"])
          == sorted(ap.PREMIERE_METHODS))
    check("B.6 every declared condition is one the shared router can evaluate",
          set(plan["fallback_when"]) <= mr.FALLBACK_CONDITIONS, str(plan["fallback_when"]))
    # Declaring a condition Algolia can never report is configuration that can never fire.
    check("B.7 only conditions the primary can actually report are declared",
          set(plan["fallback_when"]) == {"no_accepted_reports", "blocked", "broken"},
          str(plan["fallback_when"]))
    check("B.8 a method declared in two roles is refused", _two_roles_refused())

    print()
    print("=" * 92)
    print("C-D  a healthy primary with accepted evidence runs nothing else")
    print("=" * 92)
    good = [{"source_url": "https://community.adobe.com/t5/premiere-pro-bugs/x/idi-p/1",
             "source_date": "2026-05-01T00:00:00Z", "report_text": "Premiere Pro 26.2 crashes on export",
             "update_version": "26.2"}]
    with Recorder(yields={"adobe_community_algolia_search": good}) as rec:
        record = a_record()
        accepted, rejected, health = ap.collect_for_record(record, a_context())
    statuses = health_by_method(health)
    disabled_ids = set(plan["disabled"])
    check("C.1 no disabled method is called",
          not (disabled_ids & set(rec.called)), str(sorted(disabled_ids & set(rec.called))))
    check("C.2 the probe-only method is not called",
          "wayback_snapshot_recheck" not in rec.called, str(rec.called))
    check("D.1 the fallback is not called when the primary accepted evidence",
          "adobe_community_known_url_recheck" not in rec.called, str(rec.called))
    check("D.2 only the primary ran", rec.called == ["adobe_community_algolia_search"],
          str(rec.called))
    check("O.1 every one of the nine methods still reports a row",
          len(health) == 9 and set(statuses) == set(ap.PREMIERE_METHODS), str(sorted(statuses)))
    check("O.2 a disabled method is reported `disabled`, never a fresh failure",
          all(statuses[m] == "disabled" for m in disabled_ids),
          str({m: statuses[m] for m in disabled_ids}))
    check("P.1 a fallback that did not run does not masquerade as failed",
          statuses["adobe_community_known_url_recheck"] == "disabled",
          statuses["adobe_community_known_url_recheck"])
    check("J.1 probe-only wayback reports disabled rather than a failure",
          statuses["wayback_snapshot_recheck"] == "disabled",
          statuses["wayback_snapshot_recheck"])
    check("O.3 not one not-run row carries a blocked_reason",
          all(not str(h.get("blocked_reason") or "")
              for h in health if str(h["method_id"]) != "adobe_community_algolia_search"))
    check("O.4 every not-run row is stamped with THIS run's timestamp, so none can go stale",
          len({str(h.get("last_run")) for h in health}) == 1)

    print()
    print("=" * 92)
    print("E-G  the declared fallback conditions, and only those, invoke the fallback")
    print("=" * 92)
    # E: primary healthy but accepted nothing.
    with Recorder(yields={"adobe_community_algolia_search": []}) as rec:
        ap.collect_for_record(a_record(), a_context())
    check("E.1 zero accepted evidence invokes the fallback",
          "adobe_community_known_url_recheck" in rec.called, str(rec.called))
    check("E.2 and still runs no disabled method",
          not (disabled_ids & set(rec.called)), str(rec.called))

    blocked = RuntimeError("blocked:http_403")
    with Recorder(raises={"adobe_community_algolia_search": blocked}) as rec:
        _, _, health_blocked = ap.collect_for_record(a_record(), a_context())
    check("F.1 a blocked primary invokes the fallback",
          "adobe_community_known_url_recheck" in rec.called, str(rec.called))
    check("F.2 the blocked primary still reports its REAL status, not disabled",
          health_by_method(health_blocked)["adobe_community_algolia_search"] == "blocked",
          health_by_method(health_blocked)["adobe_community_algolia_search"])

    with Recorder(raises={"adobe_community_algolia_search": RuntimeError("unexpected_parse_error")}) as rec:
        _, _, health_broken = ap.collect_for_record(a_record(), a_context())
    check("G.1 a broken primary invokes the fallback",
          "adobe_community_known_url_recheck" in rec.called, str(rec.called))
    check("G.2 the broken primary reports broken",
          health_by_method(health_broken)["adobe_community_algolia_search"] == "broken",
          health_by_method(health_broken)["adobe_community_algolia_search"])

    # The executed fallback must report REAL health, not the not-run placeholder.
    with Recorder(yields={"adobe_community_algolia_search": [], "adobe_community_known_url_recheck": []}) as rec:
        _, _, health_fb = ap.collect_for_record(a_record(), a_context())
    check("G.3 an executed fallback reports real health, not `disabled`",
          health_by_method(health_fb)["adobe_community_known_url_recheck"] != "disabled",
          health_by_method(health_fb)["adobe_community_known_url_recheck"])

    print()
    print("=" * 92)
    print("H  routing chooses the method; it never touches acceptance")
    print("=" * 92)
    # The same candidate, offered by the primary and then by the fallback, must reach the same
    # verdict -- routing may not become a way to admit a row the primary's gates would refuse.
    probe = [{"source_url": "https://community.adobe.com/t5/premiere-pro-bugs/y/idi-p/2",
              "source_date": "2026-05-02T00:00:00Z",
              "report_text": "Totally unrelated text with no version and no issue."}]
    with Recorder(yields={"adobe_community_algolia_search": probe}) as rec:
        acc_primary, _, _ = ap.collect_for_record(a_record(), a_context())
    with Recorder(yields={"adobe_community_algolia_search": [],
                          "adobe_community_known_url_recheck": probe}) as rec:
        acc_fallback, _, _ = ap.collect_for_record(a_record(), a_context())
    check("H.1 a candidate the primary's gates refuse is refused from the fallback too",
          len(acc_primary) == len(acc_fallback) == 0,
          f"primary={len(acc_primary)} fallback={len(acc_fallback)}")
    src = ap.inspect_source()
    check("H.2 routing code reads no acceptance field and makes no accept/reject decision",
          "evaluate_candidates" in src["run_one"] and "apply_acceptance_gates" not in src["collect"],
          "routing must delegate, not re-decide")
    check("H.3 exactly one place evaluates candidates for every method",
          src["evaluate_calls"] == 1, str(src["evaluate_calls"]))

    print()
    print("=" * 92)
    print("I-K  no routine network work from a method routing declined to call")
    print("=" * 92)
    check("I.1 a disabled method is never even looked up in the dispatch table",
          _no_network_on_success(), "a not-run method must not reach its implementation")
    check("K.1 no probe recovery trigger is declared, so the probe is never automatic",
          "wayback_snapshot_recheck" not in plan["primary"] + plan["fallback"])
    check("K.2 the probe stays implemented and reachable by hand",
          callable(ap.PREMIERE_METHODS["wayback_snapshot_recheck"]))

    print()
    print("=" * 92)
    print("L-N  routing writes no evidence and touches no stored row")
    print("=" * 92)
    before_ev = (ROOT / "_data" / "consensus_evidence.yml").read_bytes()
    before_mh = (ROOT / "_data" / "evidence_method_health.yml").read_bytes()
    with Recorder(yields={"adobe_community_algolia_search": good}):
        ap.collect_for_record(a_record(), a_context())
    check("L.1 a dry collection rewrites no stored evidence",
          (ROOT / "_data" / "consensus_evidence.yml").read_bytes() == before_ev)
    check("L.2 and no stored method health", 
          (ROOT / "_data" / "evidence_method_health.yml").read_bytes() == before_mh)
    check("M.1 withdrawn Premiere rows are still withdrawn, and still carry a reason",
          _withdrawn_rows_intact(), "an audited withdrawal must survive untouched")
    check("N.1 routing code touches no official field",
          not any(t in src["collect"] for t in ("official", "release_notes", "source_captured")))
    check("N.2 routing writes nothing at all: no append, no upsert, no record write",
          not any(t in src["collect"] for t in ("append_evidence_rows", "upsert_method_health",
                                                "apply_consensus_writeback")))

    print()
    print("=" * 92)
    print("Q-R  public monitoring follows the executing route; PowerPoint does not move")
    print("=" * 92)
    check("Q.1 a not-run method is `disabled`, which the monitoring ladder treats as not-usable "
          "rather than as a failure",
          "disabled" in mr.HEALTH_STATUSES)
    # The fail-open this avoids: the collector's own mapper returns `no_results` for a method with
    # no candidates and no errors, and the ladder counts `no_results` as HEALTHY. A not-run method
    # must never travel that path.
    check("Q.2 the status mapper would call an uncalled method healthy, so not-run rows bypass it",
          ap.adobe_community_method_status([], [], [], []) == "no_results")
    check("Q.3 not-run rows are built by their own function, never by the mapper",
          _not_run_bypasses_mapper())
    check("Q.4 the not-run reason is public copy and names no repository path",
          all(not any(t in text for t in ("lib/", ".py", "auxsays/", "method_routing"))
              for text in ap.NOT_RUN_REASONS.values()))
    check("R.1 PowerPoint's plan is byte-identical to its declaration",
          mr.plan_methods("microsoft-powerpoint")["primary"]
          == ["learn_qna_search_rss", "learn_qna_powerpoint_tags", "stack_exchange_search",
              "github_officedev_issues", "tech_community_discussions", "open_web_discovery"])
    check("R.2 PowerPoint gains no probe-only or disabled role",
          mr.plan_methods("microsoft-powerpoint")["probe_only"] == []
          and mr.plan_methods("microsoft-powerpoint")["disabled"] == [])
    check("R.3 PowerPoint's fallback and conditions are unchanged",
          mr.plan_methods("microsoft-powerpoint")["fallback"] == ["reddit_search"]
          and mr.plan_methods("microsoft-powerpoint")["fallback_when"]
          == ["no_accepted_reports", "blocked", "broken", "stale", "low_confidence"])
    check("R.4 a product with no plan still gets the empty default, so nothing else is routed",
          mr.plan_methods("obs-studio") == {"primary": [], "fallback": [], "fallback_when": [],
                                            "probe_only": [], "disabled": []})
    # The orchestrator must not treat Premiere as orchestrable just because it now has a plan: its
    # only method adapters are PowerPoint's, and it would have run them against Premiere records.
    check("R.5 the orchestrator still refuses Premiere, because it has no adapter for it",
          _orchestrator_refuses_premiere())
    check("R.6 and still accepts PowerPoint", _orchestrator_accepts_powerpoint())

    print()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


# --- helpers the sections above rely on ---------------------------------------------------------

def _premiere_source() -> str:
    return (SCRIPTS / "patch_collectors" / "adobe_premiere.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    src = _premiere_source()
    start = src.index(f"def {name}(")
    nxt = src.find("\ndef ", start + 1)
    return src[start:nxt if nxt != -1 else len(src)]


def _inspect_source() -> dict:
    whole = _premiere_source()
    return {
        "collect": _function_source("collect_for_record"),
        "run_one": _function_source("run_one"),
        "evaluate_calls": whole.count("evaluate_candidates(record, candidates"),
    }


ap.inspect_source = _inspect_source  # the suite reads the shipped source, not a production helper


def _two_roles_refused() -> bool:
    saved = dict(mr.METHOD_PLANS)
    try:
        mr.METHOD_PLANS["aux-test-double-role"] = {
            "primary": ["m1"], "fallback": ["m1"], "fallback_when": [],
        }
        try:
            mr.plan_methods("aux-test-double-role")
            return False
        except ValueError:
            return True
    finally:
        mr.METHOD_PLANS.clear()
        mr.METHOD_PLANS.update(saved)


def _no_network_on_success() -> bool:
    """With every implementation replaced by a bomb, a healthy primary must still complete."""
    saved = dict(ap.PREMIERE_METHODS)
    plan = mr.plan_methods(PRODUCT)
    try:
        def bomb(record, context, errors):
            raise AssertionError("a not-run method reached its implementation")
        for method_id in ap.PREMIERE_METHODS:
            ap.PREMIERE_METHODS[method_id] = bomb
        ap.PREMIERE_METHODS["adobe_community_algolia_search"] = lambda r, c, e: [
            {"source_url": "https://community.adobe.com/t5/premiere-pro-bugs/z/idi-p/3",
             "source_date": "2026-05-01T00:00:00Z",
             "report_text": "Premiere Pro 26.2 crashes on export", "update_version": "26.2"}]
        ap.collect_for_record(a_record(), a_context())
        return True
    except AssertionError:
        return False
    finally:
        ap.PREMIERE_METHODS.clear()
        ap.PREMIERE_METHODS.update(saved)


def _not_run_bypasses_mapper() -> bool:
    row = ap.not_run_health_row(a_record(), "2026-10-07T00:00:00Z",
                                "reddit_search", "disabled")
    return str(row.get("status")) == "disabled" and int(row.get("candidates_found") or 0) == 0


def _withdrawn_rows_intact() -> bool:
    rows = ap.load_evidence()
    withdrawn = [r for r in rows
                 if str(r.get("product_id") or "") == PRODUCT and r.get("counted") is False]
    return bool(withdrawn) and all(str(r.get("exclusion_reason") or "").strip() for r in withdrawn)


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "aux_orch_probe", SCRIPTS / "orchestrate_evidence_run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["aux_orch_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def _gate_verdict(product_id: str) -> list[str]:
    """Run the orchestrator's REAL gate predicate for one product.

    Calls `Pipeline.unsupported_products` as an unbound function over a stand-in carrying only
    the two attributes it reads. Constructing a real Pipeline would drag in the checkpointer,
    which validates its directory against the repo; re-deriving the predicate here instead
    would pass with the gate deleted, which is exactly the hole this replaced."""
    mod = _load_orchestrator()
    stand_in = SimpleNamespace(product_ids=[product_id],
                               methods=mod.default_powerpoint_methods())
    return mod.Pipeline.unsupported_products(stand_in)


def _orchestrator_refuses_premiere() -> bool:
    return _gate_verdict(PRODUCT) == [PRODUCT]


def _orchestrator_accepts_powerpoint() -> bool:
    return _gate_verdict("microsoft-powerpoint") == []


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
