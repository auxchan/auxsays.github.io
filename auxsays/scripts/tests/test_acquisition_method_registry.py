#!/usr/bin/env python3
"""The acquisition-method registry stays a registry, not prose that drifted into a dict.

WHAT THIS GUARDS. `lib/acquisition_methods.py` is knowledge capture: what each acquisition method
can do and how it tends to fail. Knowledge files rot in specific ways, and each check below exists
for one of them:

  * a duplicate `method_id` silently shadows an entry (the later one wins in every lookup);
  * a free-text value creeps into a field that is supposed to be an enum, and the vocabulary stops
    meaning anything;
  * a required field disappears in an edit and nothing notices, because nothing reads it at runtime;
  * a vendor name gets used as a METHOD FAMILY, which is the one modelling mistake this registry
    exists to prevent -- `microsoft_learn` describes nobody's mechanics, `rss_search` does;
  * a health status is invented here that the routing module cannot evaluate;
  * `method_routing.py` routes to a method id the registry never heard of, so the catalogue and the
    thing it catalogues disagree;
  * an unimplemented capability is listed beside working methods and reads as operational;
  * a source-rights status is recorded without its basis, or reads as a clearance.

WHAT THIS IS NOT. It does not check that a method still WORKS -- that is runtime health, and it
lives in `_data/evidence_method_health.yml` and the source-health rows. Nothing here makes a network
request.

Offline and deterministic. Run:
    PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_acquisition_method_registry.py
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import acquisition_methods as am           # noqa: E402
from lib import method_routing                       # noqa: E402

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
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


# A family names a MECHANIC. These are the vendor tokens that must never appear in one: seeing them
# there means the registry has started describing who we fetched from instead of how.
VENDOR_TOKENS = (
    "microsoft", "adobe", "github", "reddit", "google", "brave", "mojeek", "duckduckgo",
    "marginalia", "blackmagic", "elgato", "obs", "stack_exchange", "stackexchange",
    "learn", "helpx", "creativecow", "wayback", "techcommunity", "teams", "powerpoint",
    "windows", "premiere", "acrobat", "photoshop", "davinci",
)

ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def run() -> int:
    print("=" * 74)
    print("Acquisition method registry")
    print("=" * 74)

    methods = am.METHODS
    check("R1 the registry is a non-empty list of dicts",
          isinstance(methods, list) and len(methods) > 0
          and all(isinstance(m, dict) for m in methods), str(type(methods)))

    ids = [m.get("method_id") for m in methods]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    check("R2 every method_id is unique", not dupes, str(dupes))
    bad_ids = [i for i in ids if not (isinstance(i, str) and ID_RE.fullmatch(i))]
    check("R3 every method_id is a snake_case slug", not bad_ids, str(bad_ids[:4]))

    # Required fields, checked by ABSENCE-or-emptiness. A field that silently becomes "" is the same
    # loss as a field that disappears, and neither shows up at runtime because nothing reads this.
    missing: list[str] = []
    for m in methods:
        for field in am.REQUIRED_FIELDS:
            value = m.get(field)
            if value is None or (isinstance(value, (str, list)) and len(value) == 0):
                missing.append(f"{m.get('method_id')}.{field}")
    check("R4 no required field is missing or empty", not missing, "; ".join(missing[:5]))

    def enum_violations(field: str, allowed: frozenset, listy: bool) -> list[str]:
        out = []
        for m in methods:
            values = m.get(field) if listy else [m.get(field)]
            for v in (values or []):
                if v not in allowed:
                    out.append(f"{m.get('method_id')}.{field}={v!r}")
        return out

    for field, allowed, listy in (
        ("method_family", am.METHOD_FAMILIES, False),
        ("status", am.STATUSES, False),
        ("fallback_relationship", am.FALLBACK_RELATIONSHIPS, False),
        ("purpose", am.PURPOSES, True),
        ("discovery_model", am.DISCOVERY_MODELS, True),
        ("transport", am.TRANSPORTS, True),
    ):
        bad = enum_violations(field, allowed, listy)
        check(f"R5 {field} uses only declared values", not bad, "; ".join(bad[:4]))

    # The health vocabulary is IMPORTED from method_routing, so this asserts the two agree rather
    # than asserting a copy against itself.
    bad_health = [f"{m.get('method_id')}={s!r}" for m in methods
                  for s in (m.get("health_statuses") or [])
                  if s not in method_routing.HEALTH_STATUSES]
    check("R6 declared health statuses are ones routing can evaluate",
          not bad_health, "; ".join(bad_health[:4]))
    check("R6b the registry re-exports routing's vocabulary rather than restating it",
          am.HEALTH_STATUSES is method_routing.HEALTH_STATUSES)

    # THE MODELLING RULE. A family is a mechanic; a vendor belongs in the implementation.
    vendor_families = sorted({m["method_family"] for m in methods
                              if any(tok in m["method_family"] for tok in VENDOR_TOKENS)})
    check("R7 no method_family is named after a vendor", not vendor_families, str(vendor_families))
    check("R8 every declared family is actually used",
          set(am.METHOD_FAMILIES) == {m["method_family"] for m in methods},
          str(sorted(set(am.METHOD_FAMILIES) ^ {m["method_family"] for m in methods})))

    # Purpose IS the evidence authority. An entry that does not say what its output may count as is
    # the exact confusion this registry was built to prevent.
    no_authority = [m["method_id"] for m in methods if not (m.get("purpose") or [])]
    check("R9 every method states what its result may count as", not no_authority,
          str(no_authority[:4]))
    discovery_only = [m for m in methods
                      if "candidate_discovery" in m.get("purpose", [])
                      and "official_ingestion" in m.get("purpose", [])]
    check("R10 nothing is both candidate-discovery and official ingestion",
          not discovery_only, str([m["method_id"] for m in discovery_only]))

    # CROSS-REFERENCE with the thing that actually routes. The registry does not drive execution,
    # but a routed method the catalogue has never heard of means one of them is wrong.
    routed: set[str] = set()
    for plan in method_routing.METHOD_PLANS.values():
        routed |= set(plan.get("primary", [])) | set(plan.get("fallback", []))
    unknown_routed = sorted(routed - set(ids))
    check(f"R11 every method method_routing routes to ({len(routed)}) is in the registry",
          not unknown_routed, str(unknown_routed))

    # Product references must be real product ids, since the registry claims where a method is proven.
    import yaml                                       # noqa: PLC0415 - test-only
    products = yaml.safe_load((_REPO / "auxsays" / "_data" / "patch_products.yml")
                              .read_text(encoding="utf-8")) or []
    known = {str(p.get("id") or p.get("product_id")) for p in products if isinstance(p, dict)}
    check("R12 the product list loaded (so R13 is not vacuous)", len(known) > 5, str(len(known)))
    # `proven_on` also carries site names, which are not product ids. Only slug-shaped entries that
    # look like a product id are held to the product list.
    unknown_products = sorted({p for m in methods for p in (m.get("proven_on") or [])
                               if isinstance(p, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", p)
                               and "-" in p and p not in known})
    check("R13 proven_on names no unknown product id", not unknown_products,
          str(unknown_products[:6]))

    # FAILED METHODS ARE THE POINT. A registry that only remembers what works re-litigates what does
    # not, which is how the Photoshop blocker was carried for months as the wrong explanation.
    non_active = [m for m in methods if m["status"] != "active"]
    check("R14 methods that do not run are retained, not deleted", len(non_active) >= 5,
          f"{len(non_active)} non-active of {len(methods)}")
    no_reason = [m["method_id"] for m in non_active
                 if not (m.get("measured_notes") or m.get("break_history") or m.get("evidence_rules"))]
    check("R15 every non-active method records why", not no_reason, str(no_reason[:4]))

    # Unimplemented capability must not sit beside working methods.
    future_ids = {f.get("capability") for f in am.FUTURE_CAPABILITIES}
    check("R16 future capabilities are listed separately from METHODS",
          future_ids and not (future_ids & set(ids)), str(sorted(future_ids & set(ids))))
    check("R17 every future capability is marked not_implemented",
          all(f.get("status") == "not_implemented" for f in am.FUTURE_CAPABILITIES))
    check("R18 no future capability's transport is claimed as a live transport",
          not ({"graphql", "json_ld", "browser_dom"} & set(am.TRANSPORTS)),
          str(sorted(am.TRANSPORTS)))

    # Evidence: every entry cites where its facts came from, so a reader can check rather than trust.
    no_evidence = [m["method_id"] for m in methods
                   if not re.search(r"\.(py|yml|yaml|md)\b|:\d+", str(m.get("evidence") or ""))]
    check("R19 every entry cites a file its facts came from", not no_evidence,
          str(no_evidence[:4]))

    # The prose document restates the family table. A generated table that silently stops matching
    # the registry is worse than no table: it reads as authoritative and is wrong.
    doc = (_REPO / "docs" / "DATA_ACQUISITION_METHODS.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| `([a-z_]+)` \|", doc, re.M))
    check("R20 the document's family table lists exactly the registry's families",
          documented == set(am.families()),
          f"only in doc: {sorted(documented - set(am.families()))}; "
          f"only in registry: {sorted(set(am.families()) - documented)}")
    # The per-family counts in that same table had drifted and nothing noticed: R20 compares
    # family NAMES only, so adding a method to an existing family left its row saying 1 when the
    # registry held 2. A table that reads as authoritative and is wrong is worse than no table,
    # which is the stated reason R20 exists -- so the numbers beside the names are checked too.
    import collections as _collections
    registry_counts = _collections.Counter(m["method_family"] for m in methods)
    doc_counts = {name: int(count) for name, count in
                  re.findall(r"^\| `([a-z_]+)` \| (\d+) \|", doc, re.M)}
    drifted = {name: (count, registry_counts.get(name))
               for name, count in doc_counts.items() if registry_counts.get(name) != count}
    # Non-vacuity first: an empty parse would make the comparison below trivially true.
    check("R21b the family table rows parse at all (this check is not vacuous)",
          len(doc_counts) == len(am.families()),
          f"parsed {len(doc_counts)} rows for {len(am.families())} families")
    check("R21c the family table states each family's real method count",
          not drifted, str(drifted))

    check("R21 the document states the counts the registry actually has",
          f"{len(methods)} concrete implementations" in doc
          and f"{len(am.families())} families" in doc,
          "the doc's headline counts drifted from the registry")

    # The shared-gate rule is the registry's most important invariant and is stated ONCE, in the
    # module docstring, rather than repeated on 57 entries. Stating it once makes it editable away
    # without anything noticing, so the one statement is pinned.
    doc_string = am.__doc__ or ""
    check("R22 the registry states that discovery diversity is not acceptance divergence",
          "acceptance" in doc_string.lower() and "same" in doc_string.lower()
          and "discovery" in doc_string.lower(),
          "the shared-gate invariant is no longer stated in the module docstring")

    # Source rights are a different question from reachability, so they are a separate OPTIONAL
    # field. A recorded status must be a declared value and state its basis (a bare "unresolved" is a
    # label without its terms), and no note may call the access authorised. The methods whose requests
    # go to Adobe Community carry it while the owner's decision on Adobe's terms is pending (AUX-113),
    # which also keeps this check from passing on an empty set.
    adobe_community = {"adobe_community_algolia_search", "adobe_community_known_url_recheck",
                       "adobe_community_search", "adobe_community_bug_tab_index",
                       "single_page_prose_extraction", "ordered_official_source_failover"}
    bad_rights = [m["method_id"] for m in methods
                  if ("rights_status" in m or m["method_id"] in adobe_community)
                  and (m.get("rights_status") not in am.RIGHTS_STATUSES
                       or not str(m.get("rights_note") or "").strip()
                       or "authori" in str(m.get("rights_note") or "").lower())]
    check("R23 a recorded rights status is declared, states its basis, and covers Adobe Community",
          not bad_rights and adobe_community <= set(ids), str(bad_rights[:5]))

    # ---- THE JOIN WITH RUNTIME HEALTH ("R12" of the 2026-11 governance audit; numbered R24+ here
    # because R12 was already taken). The registry and the telemetry were two lists nothing compared:
    # DaVinci's only working method reported health for months with no catalogue entry. Both
    # directions are checked against the COMMITTED health file, so either side drifting fails.
    health_rows = (yaml.safe_load((_REPO / "auxsays" / "_data" / "evidence_method_health.yml")
                                  .read_text(encoding="utf-8")) or {}).get("methods") or []
    emitted = {str(r.get("method_id") or "") for r in health_rows if isinstance(r, dict)} - {""}
    check("R24 every method id that reports health is a registry entry",
          len(emitted) >= 15 and not (emitted - set(ids)), str(sorted(emitted - set(ids))))
    manual_writers = {"local_playwright_capture_promotion"}
    join = am.health_join_errors(emitted, manual_writers=manual_writers)
    check("R25 every emitted id is a declared health reporter, and every declared reporter has rows "
          "(or is declared as awaiting its first)", not join, "; ".join(join))
    arrived = sorted(am.HEALTH_REPORTERS_AWAITING_FIRST_ROW & emitted)
    if arrived:
        # A reminder, never a failure: the committed corpus changes under this suite at run time.
        print(f"  NOTE  these methods now have rows and can leave HEALTH_REPORTERS_AWAITING_FIRST_ROW: {arrived}")
    stores: dict[str, str] = {}
    store_errors: list[str] = []
    for m in methods:
        try:
            stores[m["method_id"]] = am.telemetry_store(m["method_id"])
        except (KeyError, ValueError) as exc:
            store_errors.append(f"{m['method_id']}: {exc}")
    silent_active = [mid for mid, store in stores.items()
                     if store == "none" and am.by_id(mid)["status"] == "active"]
    bad_store = [f"{mid}={store}" for mid, store in stores.items()
                 if store.split(":")[0] not in (am.TELEMETRY_STORES | {"parent"})]
    check("R26 every method says where it reports, and no ACTIVE method reports nowhere",
          not store_errors and not silent_active and not bad_store and len(stores) == len(methods),
          "; ".join(store_errors[:3]) + str(silent_active[:3]) + str(bad_store[:3]))
    bad_parent = [f"{child}->{parent}" for child, parent in am.TELEMETRY_PARENTS.items()
                  if child not in ids or parent not in am.HEALTH_REPORTING_METHODS
                  or child in am.HEALTH_REPORTING_METHODS]
    check("R27 a sub-step's parent is a real health reporter, and a sub-step has no row of its own",
          not bad_parent and not (set(am.TELEMETRY_PARENTS) & emitted),
          str(bad_parent) + str(sorted(set(am.TELEMETRY_PARENTS) & emitted)))
    from lib import collector_ownership as ownership   # noqa: PLC0415 - test-only
    owned = set().union(*ownership.ALLOWED_METHODS.values())
    check("R28 the ownership manifest and the registry name the same health reporters",
          owned - set(ownership.MANUAL_ONLY_METHODS) == set(am.HEALTH_REPORTING_METHODS)
          and set(ownership.MANUAL_ONLY_METHODS) == manual_writers,
          f"owned only: {sorted(owned - am.HEALTH_REPORTING_METHODS - manual_writers)}; "
          f"registry only: {sorted(am.HEALTH_REPORTING_METHODS - owned)}")
    all_roles: set[str] = set()
    for plan in method_routing.METHOD_PLANS.values():
        for role in ("primary", "fallback", "probe_only", "disabled"):
            all_roles |= set(plan.get(role, []))
    check("R29 every method a plan names in ANY role, including switched-off ones, is in the registry",
          not (all_roles - set(ids)) and len(all_roles) > len(routed), str(sorted(all_roles - set(ids))))

    # ---- RE-PROBE POLICY. Whether automation may ever re-test a switched-off method is a fact
    # about the source and its terms. Closed is the default; each open door is one declaration.
    off_methods = [m["method_id"] for m in methods if m["status"] in ("blocked", "disabled")]
    undeclared = [mid for mid in off_methods
                  if am.reprobe_refusal(mid) in ("no_reprobe_declared", "probe_incomplete")]
    check("R30 every blocked or disabled method has a recorded re-probe decision",
          not undeclared and len(off_methods) >= 15, str(undeclared))
    no_basis = [mid for mid, spec in am.REPROBE.items()
                if mid not in ids or spec.get("policy") not in ("allowed", "never")
                or len(str(spec.get("basis") or "")) < 40]
    check("R31 every re-probe declaration names a registry method, a policy and its basis",
          not no_basis and len(am.REPROBE) >= 8, str(no_basis))
    with_rights = [m["method_id"] for m in methods if m.get("rights_status")]
    reopened = [mid for mid in with_rights if not am.reprobe_refusal(mid)]
    closed_families = [m["method_id"] for m in methods
                       if any(tok in m["method_id"] for tok in ("reddit", "learn_qna", "adobe", "brave"))]
    reopened += [mid for mid in closed_families if not am.reprobe_refusal(mid)]
    check("R32 no method with unresolved rights, and no Reddit / Learn Q&A / Adobe / paid-search "
          "method, can be re-probed",
          not reopened and len(with_rights) >= 12 and len(closed_families) >= 15,
          f"{reopened} rights={len(with_rights)} closed={len(closed_families)}")
    allowed_specs = {mid: am.reprobe_spec(mid) for mid in ids if am.reprobe_spec(mid)}
    loose = [mid for mid, spec in allowed_specs.items()
             if spec["max_requests"] > am.REPROBE_MAX_REQUESTS_PER_METHOD
             or spec["cooldown_hours"] < am.REPROBE_COOLDOWN_HOURS_DEFAULT
             or not str(spec.get("robots_url", "")).startswith("https://")
             or not spec.get("expect_any")]
    check("R33 every re-probable method is bounded: robots.txt first, two requests, a week at least",
          not loose and 1 <= len(allowed_specs) <= 5, f"{loose} allowed={sorted(allowed_specs)}")
    learn_and_reddit = {"learn_qna_search_rss", "learn_qna_powerpoint_tags", "learn_qna_question_hydration",
                        "learn_qna_segment_context", "learn_qna_thread_reply_harvest",
                        "open_web_provider_qna_search_rss", "reddit_search",
                        "reddit_listing_enumeration", "reddit_feed_fallback"}
    unrecorded = [mid for mid in learn_and_reddit
                  if (am.by_id(mid) or {}).get("rights_status") not in am.RIGHTS_STATUSES
                  or "authori" in str((am.by_id(mid) or {}).get("rights_note") or "").lower()]
    check("R34 the Microsoft Learn Q&A and Reddit methods record their unresolved rights",
          not unrecorded, str(unrecorded))

    # ---- ACTIVATING A NEW METHOD ID, REHEARSED. A declared reporter with no row failed R25, and a
    # row from an undeclared id fails the writeback, so a new id could only be activated by
    # hand-writing a telemetry row first. The activation change now declares the id as a reporter
    # AND as awaiting its first row; the lane's own first run writes that row. Rehearsed here with
    # a made-up id, the real health writer and the real validator, in a temporary file.
    import tempfile                                      # noqa: PLC0415 - test-only
    import contextlib                                    # noqa: PLC0415 - test-only
    import io                                            # noqa: PLC0415 - test-only
    import validate_evidence_method_health as vh         # noqa: PLC0415 - test-only
    from patch_collectors import base                    # noqa: PLC0415 - test-only
    new_id = "rehearsal_new_vendor_forum_listing"
    saved = (am.HEALTH_REPORTING_METHODS, am.HEALTH_REPORTERS_AWAITING_FIRST_ROW)
    with tempfile.TemporaryDirectory() as td:
        first_row_file = Path(td) / "evidence_method_health.yml"
        try:
            am.HEALTH_REPORTING_METHODS = saved[0] | {new_id}
            blocked = am.health_join_errors(emitted, manual_writers=manual_writers)
            am.HEALTH_REPORTERS_AWAITING_FIRST_ROW = saved[1] | {new_id}
            waiting = am.health_join_errors(emitted, manual_writers=manual_writers)
            check("R35 a newly declared reporter with no row fails the join UNLESS the activation change "
                  "lists it as awaiting its first row",
                  len(blocked) == 1 and new_id in blocked[0] and waiting == [], f"{blocked} / {waiting}")
            base.upsert_method_health([base.method_health_row(
                product_id="blackmagic-davinci", update_version="21.2", method_id=new_id,
                source_type="vendor_forum", status="disabled", candidates_found=0, accepted_reports=0,
                rejected_reports=0, blocked_reason="not_run_yet", last_run="2026-11-24T07:00:00Z",
                notes="first row, written by the lane")], first_row_file)
            with contextlib.redirect_stdout(io.StringIO()):
                accepted = vh.validate(first_row_file, check_registry=True)
            check("R36 the lane's own first row for it, a fresh `disabled` row from the health writer, passes "
                  "the validator with the registry join on, and the join stays clean once the row exists",
                  accepted == 0
                  and am.health_join_errors(emitted | {new_id}, manual_writers=manual_writers) == [])
        finally:
            am.HEALTH_REPORTING_METHODS, am.HEALTH_REPORTERS_AWAITING_FIRST_ROW = saved
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            refused = vh.validate(first_row_file, check_registry=True)
        try:
            am.HEALTH_REPORTERS_AWAITING_FIRST_ROW = saved[1] | {new_id}
            stray = am.health_join_errors(emitted, manual_writers=manual_writers)
        finally:
            am.HEALTH_REPORTERS_AWAITING_FIRST_ROW = saved[1]
        check("R37 without the declaration the same row is still refused at the writeback, and an allowance "
              "for an id that is not a declared reporter is itself an error",
              refused == 1 and "is not a health-reporting method" in out.getvalue()
              and len(stray) == 1 and "awaiting a first row" in stray[0], f"{refused} {stray}")

    print()
    print("=" * 74)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    print(f"({len(methods)} methods, {len(am.families())} families, "
          f"{len(non_active)} non-active retained, {len(am.FUTURE_CAPABILITIES)} future capabilities.)")
    if _ERRORS:
        print("Failed:", ", ".join(_ERRORS))
    print("=" * 74)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
