#!/usr/bin/env python3
"""The vendor-onboarding playbook is executable, and each of its steps can fail.

WHAT THIS GUARDS.

  P. THE PLAYBOOK. `onboard_vendor.py` takes one product through nine checked steps and calls it
     STAGED only when all nine hold. A checklist whose steps cannot fail is prose, so every step is
     driven to a failure here by breaking exactly the thing it checks.
  E. THE EXERCISED PRODUCT. Elgato Stream Deck, from Elgato's own public GitHub issue tracker: the
     adapter's identity rules only REMOVE candidates (the application version must be stated as the
     application's, not as a requirement, not as one of several versions whose role is unstated),
     and everything else is the shared acceptance authority.
  N. NOT ACTIVATED. No production path registers the collector, the production maps do not name
     the product, and the collector refuses write mode. Elgato is a per-platform vendor: the
     playbook's last step keeps it CONTAINED until its records carry a platform gate.

Offline and deterministic. The fixture is synthetic (no recorded issue text).
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_vendor_onboarding_playbook.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
import traceback
import urllib.error
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import onboard_vendor as ov  # noqa: E402
import qa_patch_records as qa  # noqa: E402
import run_patch_evidence_collection as runner  # noqa: E402
from lib import collector_ownership as co  # noqa: E402
from lib import method_routing as mr  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import elgato_stream_deck as esd  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []
PID = "elgato-stream-deck"
CFG = ov.ONBOARDING[PID]
FIXTURE = json.loads((_REPO / "auxsays" / "scripts" / CFG["fixture"]).read_text(encoding="utf-8"))
ISSUES = {item["number"]: item for item in FIXTURE["items"]}
RECORDS = {r.update_version: r for r in base.generated_records(PID, None)}
TRACKED = sorted(RECORDS)
NOW = "2026-11-24T00:00:00Z"


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def steps(report: dict) -> dict[int, bool]:
    return {item["step"]: item["ok"] for item in report["steps"]}


def failed(report: dict) -> list[int]:
    return sorted(n for n, ok in steps(report).items() if not ok)


def playbook_checks() -> None:
    print("-- P. the playbook runs for the product, stops where it must, and every step can fail")
    report = quiet(ov.run_playbook, PID)
    check("P1 Elgato Stream Deck passes all nine build steps",
          len(report["steps"]) == 10 and not (set(failed(report)) - {10}),
          str([(i["step"], i["detail"]) for i in report["steps"] if not i["ok"]]))
    check("P2 and is stopped by the tenth: its vendor is under the per-platform containment decision",
          report["state"] == "CONTAINED" and failed(report) == [10]
          and "PLATFORM_UNGATED_COMPANIES" in report["steps"][9]["detail"], str(report["steps"][9]))
    check("P3 the declaration lived in the playbook manifest and was removed again afterwards",
          report["declared_in"].startswith("playbook manifest")
          and PID not in mr.METHOD_PLANS and PID not in co.ALLOWED_METHODS and PID not in co.ALLOWED_SOURCE_TYPES)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = ov.main(["--product-id", PID])
    check("P4 the command exits 2 for CONTAINED and prints what activation would still need",
          rc == 2 and "State: CONTAINED" in out.getvalue() and "Not activated" in out.getvalue())
    unknown = quiet(ov.run_playbook, "figma")
    with contextlib.redirect_stdout(io.StringIO()):
        rc_unknown = ov.main(["--product-id", "figma"])
    check("P5 a product not taken through the playbook is NOT_STARTED and exits 1",
          unknown["state"] == "NOT_STARTED" and rc_unknown == 1)

    saved_onboarding = copy.deepcopy(ov.ONBOARDING)
    saved_collectors = dict(runner.COLLECTORS)
    saved_blocked = qa.PLATFORM_UNGATED_COMPANIES

    def restore() -> None:
        ov.ONBOARDING.clear(); ov.ONBOARDING.update(copy.deepcopy(saved_onboarding))          # noqa: E702
        runner.COLLECTORS.clear(); runner.COLLECTORS.update(saved_collectors)                 # noqa: E702
        qa.PLATFORM_UNGATED_COMPANIES = saved_blocked

    def with_cfg(**changes) -> list[int]:
        ov.ONBOARDING[PID].update(changes)
        try:
            return failed(quiet(ov.run_playbook, PID))
        finally:
            restore()

    try:
        qa.PLATFORM_UNGATED_COMPANIES = frozenset()
        lifted = quiet(ov.run_playbook, PID)
        with contextlib.redirect_stdout(io.StringIO()):
            rc_lifted = ov.main(["--product-id", PID])
        check("P6 with the containment lifted (simulated) the same product is VALIDATED and exits 0",
              lifted["state"] == "VALIDATED" and not failed(lifted) and rc_lifted == 0, str(failed(lifted)))
        restore()

        ov.ONBOARDING["no-such-product"] = dict(saved_onboarding[PID])
        check("P7 step 1 fails for a product with no entry in the product list",
              1 in failed(quiet(ov.run_playbook, "no-such-product")))
        restore()

        broken = with_cfg(plan={})
        check("P8 without a declared plan, steps 2, 3, 4 and 5 fail", {2, 3, 4, 5} <= set(broken), str(broken))
        check("P9 step 2 fails when a planned method is not in the registry",
              2 in with_cfg(plan={"primary": ["not_a_catalogued_method"]}))
        for closed, why in (("reddit_search", "Reddit"), ("learn_qna_search_rss", "Microsoft Learn Q&A"),
                            ("adobe_community_algolia_search", "Adobe")):
            broken = with_cfg(plan={"primary": [closed]})
            check(f"P10 step 3 refuses to start a new product on {why}", 3 in broken, str(broken))
        check("P11 step 4 fails for a plan with no primary", 4 in with_cfg(plan={"primary": [], "disabled": ["web_search"]}))
        check("P12 step 4 fails for a fallback that has no condition and could never run",
              4 in with_cfg(plan={"primary": ["github_issues"], "fallback": ["obs_forum"]}))
        check("P13 step 4 fails for a fallback chain longer than the bound",
              4 in with_cfg(plan={"primary": ["github_issues"], "fallback_when": ["blocked"],
                                  "fallback": ["obs_forum", "stack_exchange_search", "open_web_discovery",
                                               "tech_community_discussions"]}))
        check("P14 step 5 fails with no declared evidence source type", 5 in with_cfg(source_types=[]))
        check("P15 step 8 fails when a planned method is never emitted by the collector",
              8 in with_cfg(plan={"primary": ["github_issues", "obs_forum"]}))
        check("P16 step 6 fails when the collector class does not import",
              6 in with_cfg(collector_class="NoSuchCollector"))

        with tempfile.TemporaryDirectory() as td:
            only_pass = Path(td) / "only_pass.json"
            only_pass.write_text(json.dumps({"synthetic": True, "since": "2026-01-01",
                                             "items": [ISSUES[9001]]}), encoding="utf-8")
            broken = with_cfg(fixture=str(only_pass))       # an absolute path replaces the base
            check("P17 step 8 fails for a fixture that never exercises a rejection", 8 in broken, str(broken))
            recorded = Path(td) / "recorded.json"
            recorded.write_text(json.dumps({"since": "2026-01-01", "items": FIXTURE["items"]}), encoding="utf-8")
            check("P18 step 7 refuses a fixture that is not marked synthetic", 7 in with_cfg(fixture=str(recorded)))
        check("P19 step 7 fails when the product's suite is not governed in CI",
              7 in with_cfg(suite="auxsays/scripts/tests/test_no_such_suite.py"))

        runner.COLLECTORS[PID] = esd.ElgatoStreamDeckCollector
        check("P20 step 9 fails if any production path registers the collector",
              9 in failed(quiet(ov.run_playbook, PID)))
        restore()
    finally:
        restore()
    after = quiet(ov.run_playbook, PID)
    check("P21 the mutations above were all undone (CONTAINED again, production maps untouched)",
          after["state"] == "CONTAINED" and PID not in mr.METHOD_PLANS and PID not in co.ALLOWED_METHODS)


def row(version: str, number: int) -> dict:
    return esd.evaluate_issue(RECORDS[version], ISSUES[number], NOW, TRACKED)


def collector_checks() -> None:
    print("-- E. Elgato Stream Deck: identity rules only remove; the shared gates decide the rest")
    check("E0 the product has the records the fixture is written against",
          {"7.6.1", "7.6"} <= set(RECORDS) and len(RECORDS) >= 50, str(len(RECORDS)))
    a = row("7.6.1", 9001)
    check("E1 'Stream Deck 7.6.1' in prose, after the release, a concrete crash: counted, weight 1",
          a["counted"] is True and a["match_basis"] == "body" and a["source_weight"] == 1
          and a["source_type"] == "github_issue" and a["sentiment"] == "negative", str(a.get("exclusion_reason")))
    b = row("7.6.1", 9002)
    check("E2 the answer under an issue form's 'Stream Deck version' heading states the application version",
          b["counted"] is True and b["match_basis"] == "issue_form_field", str(b.get("exclusion_reason")))
    expected = {
        9003: "version_not_stated_as_stream_deck_app",          # an SDK version is another number
        9004: "version_stated_as_requirement",                   # a floor is not the failing version
        9005: "feature_or_docs_request_not_a_problem_report",    # maintainer label
        9006: "source_date_before_or_unverified_against_release",  # the shared date gate
    }
    for number, reason in expected.items():
        got = row("7.6.1", number)
        check(f"E3 issue {number} is excluded as {reason}",
              got["counted"] is False and got["exclusion_reason"] == reason, str(got.get("exclusion_reason")))
    c = row("7.6", 9010)
    check("E4 a post naming two tracked versions does not count against the one it says worked",
          c["counted"] is False
          and (c["exclusion_reason"] == "several_app_versions_named_role_not_established"
               or str(c["exclusion_reason"]).startswith("version_role_")),
          str(c.get("exclusion_reason")))
    d = row("7.6", 9008)
    check("E5 a report naming 7.6 counts for 7.6", d["counted"] is True)
    check("E6 exact matching: '7.6.1' is never a mention of 7.6, and '7.6' never of 7.6.1",
          not esd.occurrences(esd.issue_text(ISSUES[9001]), "7.6")
          and not esd.occurrences(esd.issue_text(ISSUES[9008]), "7.6.1"))
    for text, version, established in (
            ("Since updating to Stream Deck 7.6.1 the plugin fails to connect.", "7.6.1", True),
            ("StreamDeck app version: 7.6.1 crashes.", "7.6.1", True),
            ("Requires Stream Deck 7.6.1.", "7.6.1", False),
            ("Supported in Stream Deck 7.6.1 and later.", "7.6.1", False),
            ("Works with Stream Deck 7.6.1+ only.", "7.6.1", False),
            ("@elgato/streamdeck@7.6.1 fails to build.", "7.6.1", False),
            ("Node 7.6.1 crashes.", "7.6.1", False),
            ("The plugin version is 7.6.1 and it crashes.", "7.6.1", False),
            ("It crashes on 7.6.1.", "7.6.1", False),
    ):
        got = esd.resolve_identity(text, version)
        check(f"E7 identity {'established' if established else 'refused'}: {text[:44]!r}",
              got["established"] is established, str(got))

    with ov._one_record_scan(), ov.declared(PID, CFG):
        run = quiet(ov.offline_run, PID, CFG)
    results = {r["version"]: r for r in run["results"]}
    health = [h for r in run["results"] for h in r["method_health"]]
    check("E8 one walk serves every record: one transport call, one health row per record",
          len(run["calls"]) == 1 and len(health) == len(RECORDS) and {h["method_id"] for h in health} == {"github_issues"},
          f"{len(run['calls'])} calls, {len(health)} rows")
    check("E9 the pull request in the fixture is never a candidate for any record",
          not any("9007" in url for r in run["results"] for url in r["accepted_urls"])
          and results["7.6.1"]["candidates_reviewed"] == 7, str(results["7.6.1"]["candidates_reviewed"]))
    check("E10 accepted: 9001 and 9002 for 7.6.1, 9008 for 7.6, nothing else anywhere",
          sorted(u.rsplit("/", 1)[-1] for u in results["7.6.1"]["accepted_urls"]) == ["9001", "9002"]
          and [u.rsplit("/", 1)[-1] for u in results["7.6"]["accepted_urls"]] == ["9008"]
          and sum(r["accepted_count"] for r in run["results"]) == 3,
          str({v: r["accepted_urls"] for v, r in results.items() if r["accepted_urls"]}))
    first = results[base.newest_first(list(RECORDS.values()))[0].update_version]["method_health"][0]
    check("E11 the walk's measured cost is on the first record's row; rejection reasons are stored",
          first.get("requests") == 1 and isinstance(first.get("duration_ms"), int)
          and sum(1 for h in health if h.get("requests") == 0) == len(health) - 1
          and results["7.6.1"]["method_health"][0].get("rejection_reasons", {}).get("version_stated_as_requirement") == 1,
          str(first))

    def refused(_url):
        raise urllib.error.HTTPError(_url, 403, "Forbidden", None, None)

    saved = esd.request_json
    esd.request_json = refused
    try:
        with ov._one_record_scan():
            out = quiet(esd.ElgatoStreamDeckCollector().collect,
                        base.CollectorContext(write=False, since="2026-01-01", max_pages=1))
    finally:
        esd.request_json = saved
    statuses = {h["status"] for r in out for h in r["method_health"]}
    check("E12 a refused walk reads as blocked or broken for every record, never as 'nothing found'",
          statuses <= {"blocked", "broken"} and len(statuses) == 1 and sum(r["accepted_count"] for r in out) == 0,
          str(statuses))

    with tempfile.TemporaryDirectory() as td:
        store = Path(td) / "evidence.yml"
        rows = [row("7.6.1", 9001), row("7.6.1", 9004)]
        base.append_evidence_rows(rows, store, method_health=results["7.6.1"]["method_health"])
        written = base.load_evidence(store)
        check("E13 a stored row names its discovery method, and the excluded row is stored uncounted",
              written[0].get("discovery_method_id") == "github_issues" and written[0]["counted"] is True
              and written[1]["counted"] is False and len({r["id"] for r in written}) == 2,
              str([(r["id"], r.get("discovery_method_id")) for r in written]))
        try:
            with ov._one_record_scan(), ov.declared(PID, CFG):
                co.validate_evidence(PID, None, store.read_text(encoding="utf-8"))
            owned_ok = True
        except co.OwnershipViolation:
            owned_ok = False
        check("E14 the rows pass the semantic ownership gate for this product", owned_ok)


def staging_checks() -> None:
    print("-- N. built, not registered, not activated")
    every_flag = {getattr(runner, name): "true" for name in dir(runner) if name.endswith("_ENABLE_ENV")}
    check("N1 no production path registers the collector, with no flag or with every flag set",
          PID not in runner.build_collectors({}) and PID not in runner.build_collectors(every_flag)
          and PID not in runner.COLLECTORS and len(every_flag) >= 5)
    check("N2 the production maps hold no plan, ownership or source type for the product",
          PID not in mr.METHOD_PLANS and PID not in co.ALLOWED_METHODS and PID not in co.ALLOWED_SOURCE_TYPES)
    workflows = "\n".join(p.read_text(encoding="utf-8")
                          for p in sorted((_REPO / ".github" / "workflows").glob("*.yml")))
    check("N3 no workflow names the collector or allow-lists its records",
          "elgato_stream_deck" not in workflows and "*stream-deck*" not in workflows)
    source = (_REPO / "auxsays/scripts/patch_collectors/elgato_stream_deck.py").read_text(encoding="utf-8")
    check("N4 the collector has ONE transport call site, the shared GitHub client, and no write path",
          source.count("github_api.get_json(") == 1 and "urlopen" not in source and "fetch_text" not in source
          and "append_evidence_rows" not in source and "_index_generated_records" not in source)
    refused = False
    try:
        with ov._one_record_scan():
            esd.ElgatoStreamDeckCollector().collect(base.CollectorContext(write=True, since=None, max_pages=1))
    except RuntimeError as exc:
        refused = "not activated" in str(exc)
    check("N5 the collector refuses write mode outright", refused)
    check("N6 the stored evidence holds no Elgato row (nothing was collected by this change)",
          not any(r.get("product_id") == PID for r in base.load_evidence()))
    check("N7 the playbook script itself makes no request and writes no tracked file",
          all(token not in (_REPO / "auxsays/scripts/onboard_vendor.py").read_text(encoding="utf-8")
              for token in ("urlopen", "requests.get", "write_text(", "atomic_write")))


def run() -> int:
    print("=" * 78)
    print("Vendor onboarding playbook (exercised on Elgato Stream Deck; built, contained, not activated)")
    print("=" * 78)
    playbook_checks()
    collector_checks()
    staging_checks()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed:", ", ".join(_ERRORS))
    print("=" * 78)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
