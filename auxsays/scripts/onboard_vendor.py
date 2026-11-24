#!/usr/bin/env python3
"""Vendor onboarding playbook: an EXECUTABLE, validated sequence for adding community collection
to a product, up to -- and deliberately not including -- production activation.

WHY THIS IS A SCRIPT. Onboarding a source used to be knowledge spread over PR bodies: catalogue the
method, declare the plan, register ownership, write fixtures, wire the suite, then measure. Each
step has been forgotten at least once (a production method ran for months with no catalogue entry;
five owned methods never ran). This runs the steps in order and refuses to call a product staged
until every one of them holds.

    python auxsays/scripts/onboard_vendor.py --list
    python auxsays/scripts/onboard_vendor.py --product-id elgato-stream-deck
    python auxsays/scripts/onboard_vendor.py --product-id elgato-stream-deck --json

Exit 0 when every REQUIRED step passes (the product is STAGED), 1 otherwise. It makes no network
request and writes nothing: the offline run drives the product's real collector over its fixture
with the transport replaced.

THE SEQUENCE (each step names the file a failure is fixed in):

   1 product          the product exists and already has official patch records to attach reports to
   2 registry         every planned method is catalogued in lib/acquisition_methods.py
   3 source policy    no planned method is closed by the owner or by its source's terms, and none
                      has unresolved rights: a NEW product never starts on a source in question
   4 method plan      lib/method_routing.METHOD_PLANS declares it: a primary, a bounded fallback chain
   5 health           lib/collector_ownership owns exactly the planned methods and a source type,
                      and every owned method is a declared health reporter
   6 collector        the collector class imports and is bound to this product
   7 fixtures         the recorded-shape fixture and the governed suite exist and are listed in CI
   8 offline run      the REAL collector over the fixture, network replaced: every owned method
                      emits a health row, the rows pass ownership and the health validator, the
                      gates both accept and reject, and no evidence row is malformed
   9 staged, not on   the collector is registered ONLY when its flag is set, and no workflow sets it

ACTIVATION is not a step here. `ACTIVATION_CHECKLIST` prints what a reviewed activation change still
needs; nothing in this script can turn a collector on.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from lib import acquisition_methods as registry  # noqa: E402
from lib import collector_ownership as ownership  # noqa: E402
from lib import method_routing as routing  # noqa: E402
from patch_collectors import base  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent

# One entry per product taken through the playbook. Adding a product starts here.
ONBOARDING: dict[str, dict[str, Any]] = {
    "elgato-stream-deck": {
        "collector_module": "patch_collectors.elgato_stream_deck",
        "collector_class": "ElgatoStreamDeckCollector",
        # The module attribute the offline run replaces: (url) -> (payload, response metadata).
        "transport_seam": "request_json",
        "fixture": "tests/fixtures/elgato_stream_deck/github_issues_search.json",
        "suite": "auxsays/scripts/tests/test_vendor_onboarding_playbook.py",
        "activation_flag": "AUXSAYS_ENABLE_ELGATO_STREAM_DECK_CONSENSUS",
        "source": "github.com/elgatosf/streamdeck issues, GitHub REST API",
        "source_policy": "Elgato's own public repository (MIT); read through the GitHub API with the "
                         "shared client, as OBS and ComfyUI already are. No HTML, no login, no robots question.",
    },
}

ACTIVATION_CHECKLIST = (
    "a dry run from CI egress (a dispatch with dry_run=true) showing the source answers there",
    "the measured yield judged worth a scheduled request budget (see RESULT/PR text for the number)",
    "a product-scoped promotion step in the collection workflow (the ComfyUI shape)",
    "the record glob added to the writeback allow-list of that workflow",
    "the write path driven in tests/test_collector_write_authority.py and a driver in "
    "tests/test_owned_method_lifecycle.py",
    "the flag set on the scheduled step -- by a reviewed change, never by this script",
)


# A scan of the generated records reads every record file in the repository (seconds). The playbook
# asks for one product's records several times -- the product step, the collector, the ownership
# gate -- so for the duration of a run the scan is made once per distinct request and reused.
_RECORD_SCANS: dict[tuple[Any, ...], list[Any]] = {}


@contextlib.contextmanager
def _one_record_scan():
    original = base.generated_records

    def cached(product_id: str, target_versions: set[str] | None = None, *, include_archived: bool = False):
        key = (product_id, frozenset(target_versions) if target_versions else None, include_archived)
        if key not in _RECORD_SCANS:
            _RECORD_SCANS[key] = original(product_id, target_versions, include_archived=include_archived)
        return list(_RECORD_SCANS[key])

    saved_ownership = ownership.generated_records
    base.generated_records = cached
    ownership.generated_records = cached
    try:
        yield
    finally:
        base.generated_records = original
        ownership.generated_records = saved_ownership


class Step:
    def __init__(self, number: int, name: str, fn: Callable[[str, dict[str, Any]], tuple[bool, str]]) -> None:
        self.number, self.name, self.fn = number, name, fn


def _plan_methods(product_id: str) -> list[str]:
    plan = routing.plan_methods(product_id)
    return plan["primary"] + plan["fallback"] + plan["probe_only"] + plan["disabled"]


def step_product(product_id: str, _cfg: dict[str, Any]) -> tuple[bool, str]:
    products = yaml.safe_load((REPO_ROOT / "auxsays/_data/patch_products.yml").read_text(encoding="utf-8")) or []
    known = {str(p.get("id") or "") for p in products if isinstance(p, dict)}
    if product_id not in known:
        return False, f"{product_id} is not in _data/patch_products.yml"
    records = base.generated_records(product_id, None)
    if not records:
        return False, "no official patch record exists; a report needs a release to attach to"
    return True, f"{len(records)} official records; newest {base.newest_first(records)[0].update_version}"


def step_registry(product_id: str, _cfg: dict[str, Any]) -> tuple[bool, str]:
    if product_id not in routing.METHOD_PLANS:
        return False, "no METHOD_PLANS entry yet (step 4), so there is nothing to look up"
    missing = [m for m in _plan_methods(product_id) if registry.by_id(m) is None]
    if missing:
        return False, f"not catalogued in lib/acquisition_methods.py: {missing}"
    inactive = [m for m in routing.plan_methods(product_id)["primary"]
                if registry.by_id(m)["status"] != "active"]
    if inactive:
        return False, f"a primary must be an `active` registry method: {inactive}"
    return True, ", ".join(f"{m} ({registry.by_id(m)['method_family']})" for m in _plan_methods(product_id))


def step_policy(product_id: str, _cfg: dict[str, Any]) -> tuple[bool, str]:
    if product_id not in routing.METHOD_PLANS:
        return False, "no METHOD_PLANS entry yet (step 4)"
    plan = routing.plan_methods(product_id)
    problems = []
    for method_id in plan["primary"] + plan["fallback"]:
        entry = registry.by_id(method_id) or {}
        if entry.get("rights_status"):
            problems.append(f"{method_id}: rights {entry['rights_status']}")
        refusal = registry.reprobe_refusal(method_id)
        if refusal and not refusal.startswith(("no_reprobe_declared", "declared_never", "probe_incomplete")):
            problems.append(f"{method_id}: {refusal}")      # a floor-closed source
    if problems:
        return False, "a new product may not start on a closed or unresolved source: " + "; ".join(problems)
    return True, "no planned method is on a source closed by the owner or by its terms"


def step_plan(product_id: str, _cfg: dict[str, Any]) -> tuple[bool, str]:
    if product_id not in routing.METHOD_PLANS:
        return False, "add the product to lib/method_routing.METHOD_PLANS"
    try:
        plan = routing.plan_methods(product_id)
    except ValueError as exc:
        return False, str(exc)
    if not plan["primary"]:
        return False, "a plan needs at least one primary method"
    if plan["fallback"] and not plan["fallback_when"]:
        return False, "a fallback is declared with no condition, so it could never run"
    return True, f"primary {plan['primary']}, fallback {plan['fallback']} (bound {routing.MAX_FALLBACK_METHODS})"


def step_health(product_id: str, _cfg: dict[str, Any]) -> tuple[bool, str]:
    owned = set(ownership.ALLOWED_METHODS.get(product_id, set())) - set(ownership.MANUAL_ONLY_METHODS)
    planned = set(_plan_methods(product_id)) if product_id in routing.METHOD_PLANS else set()
    if not owned:
        return False, "add the product to lib/collector_ownership.ALLOWED_METHODS"
    if owned != planned:
        return False, f"owned {sorted(owned)} != planned {sorted(planned)}: every owned method must be planned and emitted"
    if not ownership.ALLOWED_SOURCE_TYPES.get(product_id):
        return False, "add the product's evidence source type to ALLOWED_SOURCE_TYPES"
    silent = sorted(owned - registry.HEALTH_REPORTING_METHODS)
    if silent:
        return False, f"owned but not declared a health reporter in the registry: {silent}"
    return True, f"owns {sorted(owned)}; source types {sorted(ownership.ALLOWED_SOURCE_TYPES[product_id])}"


def _collector(cfg: dict[str, Any]):
    module = importlib.import_module(cfg["collector_module"])
    return module, getattr(module, cfg["collector_class"])


def step_collector(product_id: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    try:
        module, cls = _collector(cfg)
    except Exception as exc:  # noqa: BLE001
        return False, f"cannot import {cfg['collector_module']}.{cfg['collector_class']}: {type(exc).__name__}"
    if not issubclass(cls, base.ProductCollector) or getattr(cls, "product_id", "") != product_id:
        return False, "the class must subclass ProductCollector and carry this product_id"
    if not callable(getattr(module, cfg["transport_seam"], None)):
        return False, f"the module has no transport seam `{cfg['transport_seam']}` for an offline run"
    return True, f"{cfg['collector_module']}.{cfg['collector_class']}"


def step_fixtures(_product_id: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    fixture = SCRIPTS / cfg["fixture"]
    if not fixture.is_file():
        return False, f"missing fixture {cfg['fixture']}"
    try:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
    except ValueError:
        return False, "the fixture is not valid JSON"
    if not (isinstance(payload, dict) and payload.get("synthetic") is True):
        return False, "the fixture must be marked synthetic: recorded post text does not belong in the repo"
    suite = REPO_ROOT / cfg["suite"]
    manifest = (SCRIPTS / "ci" / "integrity_suites.txt").read_text(encoding="utf-8")
    if not suite.is_file() or not re.search(rf"^{re.escape(cfg['suite'])} = \d+$", manifest, re.M):
        return False, f"the suite {cfg['suite']} must exist and be governed in ci/integrity_suites.txt"
    return True, f"{cfg['fixture']} ({len(payload.get('items') or [])} synthetic items); suite governed"


def offline_run(product_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Drive the REAL collector over the fixture with its transport replaced. No network, no write.
    Returns {results, calls}; raises if the collector reaches for anything else."""
    module, cls = _collector(cfg)
    payload = json.loads((SCRIPTS / cfg["fixture"]).read_text(encoding="utf-8"))
    calls: list[str] = []

    def transport(url: str):
        calls.append(url)
        return ({"total_count": len(payload["items"]), "incomplete_results": False,
                 "items": payload["items"]}, {})

    saved = getattr(module, cfg["transport_seam"])
    setattr(module, cfg["transport_seam"], transport)
    try:
        context = base.CollectorContext(write=False, since=payload.get("since") or "2020-01-01", max_pages=1)
        results = cls().collect(context)
    finally:
        setattr(module, cfg["transport_seam"], saved)
    return {"results": results, "calls": calls}


def step_offline_run(product_id: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    try:
        run = offline_run(product_id, cfg)
    except Exception as exc:  # noqa: BLE001
        return False, f"the collector raised over its fixture: {type(exc).__name__}: {str(exc)[:120]}"
    results = run["results"]
    health = [row for result in results for row in result.get("method_health") or []]
    owned = set(ownership.ALLOWED_METHODS.get(product_id, set())) - set(ownership.MANUAL_ONLY_METHODS)
    emitted = {str(row.get("method_id")) for row in health}
    if emitted != owned:
        return False, f"owned {sorted(owned)} != emitted {sorted(emitted)}"
    try:
        ownership.validate_method_health(product_id, health)
    except ownership.OwnershipViolation as exc:
        return False, f"ownership refused a health row: {exc.public_reason() if hasattr(exc, 'public_reason') else exc}"
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "health.yml"
        base.upsert_method_health([dict(row) for row in health], path)
        import validate_evidence_method_health as validator  # noqa: PLC0415
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = validator.validate(path, check_registry=True)
        if code != 0:
            return False, "the health validator refused the rows: " + out.getvalue().strip().splitlines()[-1][:160]
    accepted = sum(int(r.get("accepted_count") or 0) for r in results)
    rejected = sum(int(r.get("rejected_count") or 0) for r in results)
    if not accepted or not rejected:
        return False, (f"the fixture must exercise the gates both ways (accepted {accepted}, rejected {rejected}); "
                       "a fixture that only passes proves nothing about refusal")
    unmeasured = [row["method_id"] for row in health
                  if str(row.get("status")) != "disabled" and "duration_ms" not in row]
    if unmeasured:
        return False, f"attempted rows carry no measured cost: {sorted(set(unmeasured))}"
    return True, (f"{len(results)} records, {len(health)} health rows, accepted {accepted}, rejected {rejected}, "
                  f"{len(run['calls'])} transport calls")


def step_staged(product_id: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    import run_patch_evidence_collection as runner  # noqa: PLC0415
    flag = cfg["activation_flag"]
    if product_id in runner.build_collectors({}):
        return False, "the collector is registered with no flag set: it would run in production today"
    if product_id not in runner.build_collectors({flag: "true"}):
        return False, f"setting {flag}=true does not register the collector"
    setters = [wf.name for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
               if flag in wf.read_text(encoding="utf-8")]
    if setters:
        return False, f"a workflow already names the activation flag: {setters}. Activation is a separate change."
    return True, f"registered only when {flag}=true; no workflow sets it"


STEPS = (
    Step(1, "product", step_product), Step(2, "registry", step_registry),
    Step(3, "source policy", step_policy), Step(4, "method plan", step_plan),
    Step(5, "health registration", step_health), Step(6, "collector", step_collector),
    Step(7, "fixtures and suite", step_fixtures), Step(8, "offline run", step_offline_run),
    Step(9, "staged, not activated", step_staged),
)


def run_playbook(product_id: str) -> dict[str, Any]:
    cfg = ONBOARDING.get(product_id)
    if cfg is None:
        return {"product_id": product_id, "state": "NOT_STARTED", "steps": [],
                "detail": "add the product to onboard_vendor.ONBOARDING to begin"}
    outcomes = []
    with _one_record_scan():
        for step in STEPS:
            try:
                ok, detail = step.fn(product_id, cfg)
            except Exception as exc:  # noqa: BLE001 -- a step that cannot run has not passed
                ok, detail = False, f"{type(exc).__name__}: {str(exc)[:160]}"
            outcomes.append({"step": step.number, "name": step.name, "ok": bool(ok), "detail": detail})
    passed = all(item["ok"] for item in outcomes)
    return {"product_id": product_id, "source": cfg["source"], "source_policy": cfg["source_policy"],
            "state": "STAGED" if passed else "INCOMPLETE", "steps": outcomes,
            "activation_still_needs": list(ACTIVATION_CHECKLIST)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vendor onboarding playbook (stops before activation).")
    parser.add_argument("--product-id")
    parser.add_argument("--list", action="store_true", help="List the products taken through the playbook.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.list or not args.product_id:
        for product_id, cfg in sorted(ONBOARDING.items()):
            print(f"{product_id}: {cfg['source']}")
        return 0
    report = run_playbook(args.product_id)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Vendor onboarding playbook: {report['product_id']}")
        for item in report["steps"]:
            print(f"  {'PASS' if item['ok'] else 'FAIL'}  {item['step']} {item['name']}: {item['detail']}")
        print(f"State: {report['state']}" + ("" if report["steps"] else f" ({report.get('detail')})"))
        if report["state"] == "STAGED":
            print("Not activated. A reviewed activation change still needs:")
            for line in report["activation_still_needs"]:
                print(f"  - {line}")
    return 0 if report["state"] == "STAGED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
