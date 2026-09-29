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
  * an unimplemented capability is listed beside working methods and reads as operational.

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
