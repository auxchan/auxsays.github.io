#!/usr/bin/env python3
"""Coverage truth: what AUXSAYS actually monitors for each catalog product (AUX-102).

WHAT WAS WRONG. Putting a product in the catalog was decoupled from collecting anything for it.
`_data/patch_products.yml` carried a hand-written `coverage_state: active_watch` and
`coverage_status_label: Monitoring active` for products whose ingestion source was switched off,
and nothing checked the two against each other. Measured on main d6e691cc: 47 catalog products, 17
with an enabled official lane, 30 without, 18 of those 30 Core (NVIDIA among them), and 29 of the 30
labelled "Monitoring active" in the catalog. The company page told readers "NVIDIA is tracked by
AUXSAYS" while nothing could have produced a record for GeForce 621.14 (2026-11-04) or 621.24
(2026-11-12), and nothing reported that either. The official-update pill was already derived
(`build_monitoring_projection.py`, AUX-039); the prose around it, the catalog fields and the
community side were not.

FOUR CAPABILITIES, NOT ONE LABEL. A product can have any combination of:
  * official release detection  -- `build_monitoring_projection.derive_state`, unchanged and reused;
  * community report discovery   -- derived here from `_data/evidence_method_health.yml`;
  * patch consensus              -- per patch, owned by `lib/maturity.py` and the live projection;
  * product-level issue signals  -- not built for any product (see
                                    docs/PRODUCT_LEVEL_SIGNALS_CONTRACT.md).
This file derives the first two per product and ONE plain-language coverage label from them. The
label describes coverage only. It is never a verdict, an evidence state or a statement about the
software.

FAIL CLOSED. "Official updates monitored" is earned only by an official lane the monitoring
projection calls `healthy`. A configured URL, a catalog entry, a product page, a queued backfill or a
green workflow run that contains other products is never monitoring. An enabled lane that is not
healthy is impaired, never current. A switched-off lane is "Not currently monitored" -- not broken,
because a source that was never monitored is not a collector that broke -- unless the reviewed
coverage debt file (`_data/coverage_debt.yml`) records a plan, in which case it is "Monitoring
planned; not active". A plan never makes anything affirmative.

GENERATED AT DEPLOY, NEVER COMMITTED. `pages.yml` runs this before `jekyll build`, like the monitoring
and live-eligibility projections, because its answer moves with the clock and with files every lane
rewrites. The output is git-ignored. Where it is absent (a local render), the layouts read "Coverage
status unknown", which `ci/verify_coverage_claims.py` refuses on a deploy build.

Run:  python auxsays/scripts/build_coverage_projection.py
      python auxsays/scripts/build_coverage_projection.py --output PATH   (write elsewhere)
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

# Run as a bare script by pages.yml: the sibling modules live beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

import build_monitoring_projection as official  # noqa: E402
from lib.monitoring_health import DISABLED, HEALTHY_STATUSES, load_thresholds  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_PATH = ROOT / "_data" / "patch_products.yml"
COMPANIES_PATH = ROOT / "_data" / "patch_companies.yml"
METHOD_HEALTH_PATH = ROOT / "_data" / "evidence_method_health.yml"
DEBT_PATH = ROOT / "_data" / "coverage_debt.yml"
CONFIG_PATH = ROOT / "_config.yml"
OUTPUT_PATH = ROOT / "_data" / "coverage_state.yml"

# The CLOSED coverage vocabulary, and the only words a page may use to describe it.
COVERAGE_LABELS = {
    "full": "Official updates monitored",
    "official_only": "Official updates monitored; community reports not monitored",
    "impaired": "Monitoring temporarily impaired",
    "planned": "Monitoring planned; not active",
    "not_monitored": "Not currently monitored",
}
COVERAGE_STATES = tuple(COVERAGE_LABELS)
# A company holds products in different states; a mixed company is described by counts.
COMPANY_STATES = COVERAGE_STATES + ("mixed",)
# What a page renders when the projection is ABSENT. Never emitted by this file, and refused on a
# deploy build by ci/verify_coverage_claims.py -- so it can only ever appear on a local render.
UNKNOWN_STATE = "unknown"
UNKNOWN_LABEL = "Coverage status unknown"
# States in which at least one capability is actually operating.
OPERATING_STATES = ("full", "official_only")

COMMUNITY_STATES = ("operating", "impaired", "absent")
COMMUNITY_LABELS = {
    "operating": "Community reports monitored",
    "impaired": "Community report collection impaired",
    "absent": "Community reports not monitored",
}

# Official states that mean "switched off by configuration" (including a manual-only source, which
# derive_state reports as disabled). Everything else that is not `healthy` is a RUNTIME failure of an
# enabled lane: it changes the label and never blocks a deploy.
OFFICIAL_OFF = ("disabled", "unconfigured")

PLAN_VALUES = ("planned", "not_planned")
BLOCKING_REASONS = {
    "vendor_terms_unresolved": "the vendor's terms restrict automated access; an owner rights decision is pending",
    "source_blocks_automation": "the official source refuses automated requests from the collection runners",
    "adapter_not_built": "an official source is mapped, but no adapter for it has been built and validated",
    "no_machine_readable_source": "no official release source suitable for automated detection is mapped",
}
PRIORITIES = ("P1", "P2", "P3")


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def parse_instant(value: Any) -> datetime | None:
    return official.parse_instant(value)


# ---------------------------------------------------------------------------------------------
# Community report discovery
# ---------------------------------------------------------------------------------------------

def community_state(rows: Iterable[Mapping[str, Any]], *, now: datetime, max_age_days: int) -> str:
    """Whether community report discovery is operating for ONE product's method-health rows.

    The newest row per method decides that method's status. `disabled` methods are switched off and
    say nothing. A product is `operating` only when at least one active method's newest row is a
    healthy status (the per-patch authority's own set: success / no_results) AND ran within the
    published freshness window (`monitoring_max_age_days`) and not in the future. Active methods with
    none of that are `impaired`; no active method at all is `absent`.
    """
    newest: dict[str, Mapping[str, Any]] = {}
    newest_at: dict[str, datetime] = {}
    for row in rows:
        method = str(row.get("method_id") or "").strip()
        if not method:
            continue
        at = parse_instant(row.get("last_run")) or datetime.min.replace(tzinfo=timezone.utc)
        if method not in newest or at > newest_at[method]:
            newest[method], newest_at[method] = row, at
    active = {m: r for m, r in newest.items()
              if str(r.get("status") or "").strip().lower() != DISABLED}
    if not active:
        return "absent"
    window = timedelta(days=max_age_days)
    for method, row in active.items():
        status = str(row.get("status") or "").strip().lower()
        at = parse_instant(row.get("last_run"))
        if status in HEALTHY_STATUSES and at is not None and at <= now and now - at <= window:
            return "operating"
    return "impaired"


# ---------------------------------------------------------------------------------------------
# The coverage label
# ---------------------------------------------------------------------------------------------

def derive_coverage(official_state: str, community: str, *, planned: bool) -> str:
    """One COVERAGE_STATES member from the official state, the community state and the plan.

    `healthy` is checked first and is the only path to an affirmative state. An official lane that is
    switched off is never "monitored" whatever else is configured; it is impaired only when community
    discovery still operates for it (partial coverage is not none).
    """
    if official_state == "healthy":
        if community == "operating":
            return "full"
        if community == "absent":
            return "official_only"
        return "impaired"            # community methods exist and none is working
    if official_state in OFFICIAL_OFF:
        if community == "operating":
            return "impaired"
        return "planned" if planned else "not_monitored"
    # stale, blocked, unreachable, broken, unverified -- or anything this file does not recognise:
    # an enabled lane that is not working is never current.
    return "impaired"


def company_coverage(children: list[tuple[str, str]]) -> tuple[str, str]:
    """(state, label) for a company from its products' (coverage state, official state) pairs."""
    total = len(children)
    if total == 0:
        return "not_monitored", COVERAGE_LABELS["not_monitored"]
    states = [s for s, _o in children]
    if len(set(states)) == 1:
        return states[0], COVERAGE_LABELS.get(states[0], UNKNOWN_LABEL)
    official_ok = sum(1 for s in states if s in OPERATING_STATES)
    community_ok = sum(1 for s in states if s == "full")
    if official_ok == total:
        return "mixed", (f"Official updates monitored; community reports monitored for "
                         f"{community_ok} of {total} products")
    if official_ok:
        return "mixed", f"Official updates monitored for {official_ok} of {total} products"
    for state in ("impaired", "planned"):
        if state in states:
            return state, COVERAGE_LABELS[state]
    return "not_monitored", COVERAGE_LABELS["not_monitored"]


# ---------------------------------------------------------------------------------------------
# The reviewed coverage debt
# ---------------------------------------------------------------------------------------------

def load_debt(path: Path = DEBT_PATH) -> list[dict]:
    """The debt entries, or [] when the file is absent. A malformed file raises ValueError."""
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return []
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError(f"{path}: expected a mapping with an `entries` list")
    entries = payload["entries"]
    bad = [i for i, e in enumerate(entries) if not isinstance(e, dict)]
    if bad:
        raise ValueError(f"{path}: entry {bad[0]} is not a mapping")
    return entries


def debt_errors(entries: list[dict], catalog_ids: set[str]) -> list[str]:
    """Structural problems with the debt file. Each is a reason to refuse it."""
    errors = []
    seen: set[str] = set()
    for i, entry in enumerate(entries):
        pid = str(entry.get("product_id") or "").strip()
        where = f"coverage debt entry {i} ({pid or 'no product_id'})"
        if not pid:
            errors.append(f"{where}: missing product_id")
            continue
        if pid in seen:
            errors.append(f"{where}: product listed twice")
        seen.add(pid)
        if pid not in catalog_ids:
            errors.append(f"{where}: not a catalog product")
        if entry.get("remediation_priority") not in PRIORITIES:
            errors.append(f"{where}: remediation_priority must be one of {list(PRIORITIES)}")
        if entry.get("blocking_reason") not in BLOCKING_REASONS:
            errors.append(f"{where}: blocking_reason must be one of {sorted(BLOCKING_REASONS)}")
        if not str(entry.get("next_action") or "").strip():
            errors.append(f"{where}: next_action is empty")
        if entry.get("plan") not in PLAN_VALUES:
            errors.append(f"{where}: plan must be one of {list(PLAN_VALUES)}")
        if parse_instant(entry.get("review_by")) is None:
            errors.append(f"{where}: review_by must be a date")
        for j, rel in enumerate(entry.get("observed_official_releases") or []):
            if not isinstance(rel, dict) or not str(rel.get("version") or "").strip() \
                    or not str(rel.get("reference") or "").strip():
                errors.append(f"{where}: observed_official_releases[{j}] needs a version and a reference")
    return errors


# ---------------------------------------------------------------------------------------------
# Building the projection
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Inputs:
    products: list[dict]
    companies: list[dict]
    sources: list[dict]
    official_rows: list[dict]      # build_monitoring_projection.build_rows output
    method_rows: list[dict] | None  # None when the method-health file could not be read
    debt: list[dict]
    max_age_days: int


def load_inputs(*, now: datetime) -> Inputs:
    products = [p for p in (load_yaml(PRODUCTS_PATH) or []) if isinstance(p, dict)]
    companies = [c for c in (load_yaml(COMPANIES_PATH) or []) if isinstance(c, dict)]
    sources = [s for s in (load_yaml(official.SOURCES_PATH) or []) if isinstance(s, dict)]
    official_rows = official.build_rows(now=now)
    try:
        payload = load_yaml(METHOD_HEALTH_PATH) or {}
        rows = payload.get("methods") if isinstance(payload, dict) else payload
        method_rows = [r for r in rows or [] if isinstance(r, dict)]
    except Exception as exc:  # noqa: BLE001 -- unreadable telemetry fails closed, never as "absent"
        print(f"WARNING: method health unreadable, community discovery reads impaired: {exc!r}"[:300])
        method_rows = None
    thresholds = load_thresholds(CONFIG_PATH)
    return Inputs(products, companies, sources, official_rows, method_rows, load_debt(),
                  thresholds.max_age_days)


def product_id_of(product: Mapping[str, Any]) -> str:
    return str(product.get("product_id") or product.get("id") or "").strip()


def build(inputs: Inputs, *, now: datetime) -> tuple[list[dict], list[dict]]:
    """-> (product rows, company rows), both sorted, both from closed vocabularies."""
    official_by_pid = {r["product_id"]: r["state"] for r in inputs.official_rows}
    rows_by_pid: dict[str, list[dict]] = {}
    for row in inputs.method_rows or []:
        rows_by_pid.setdefault(str(row.get("product_id") or ""), []).append(row)
    planned = {str(e.get("product_id")) for e in inputs.debt if e.get("plan") == "planned"}

    product_rows = []
    children: dict[str, list[tuple[str, str]]] = {}
    for product in inputs.products:
        pid = product_id_of(product)
        if not pid:
            continue
        off = official_by_pid.get(pid, "unverified")
        if inputs.method_rows is None:
            comm = "impaired"
        else:
            comm = community_state(rows_by_pid.get(pid, []), now=now,
                                   max_age_days=inputs.max_age_days)
        state = derive_coverage(off, comm, planned=pid in planned)
        if state not in COVERAGE_STATES:      # belt: derive_coverage must never do this
            state = "impaired"
        product_rows.append({"product_id": pid, "state": state, "label": COVERAGE_LABELS[state],
                             "official": off, "community": comm})
        cid = str(product.get("company_id") or "").strip()
        if cid:
            children.setdefault(cid, []).append((state, off))
    product_rows.sort(key=lambda r: r["product_id"])

    company_rows = []
    for company in inputs.companies:
        cid = str(company.get("id") or company.get("company_id") or "").strip()
        if not cid:
            continue
        kids = children.get(cid, [])
        state, label = company_coverage(kids)
        company_rows.append({"company_id": cid, "state": state, "label": label,
                             "official_monitored": sum(1 for s, _o in kids if s in OPERATING_STATES),
                             "total": len(kids)})
    company_rows.sort(key=lambda r: r["company_id"])
    return product_rows, company_rows


HEADER = (
    "# GENERATED by auxsays/scripts/build_coverage_projection.py -- do not edit by hand.\n"
    "#\n"
    "# What AUXSAYS actually monitors, per catalog product and company, derived at deploy time from\n"
    "# the ingestion sources, the recorded ingest state and the community method health. The pages\n"
    "# read their coverage labels from THIS file only. Never committed (git-ignored).\n"
)


def render(product_rows: list[dict], company_rows: list[dict]) -> str:
    body = yaml.safe_dump({"products": product_rows, "companies": company_rows},
                          sort_keys=False, allow_unicode=True, width=100)
    return HEADER + body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    inputs = load_inputs(now=now)
    catalog = {product_id_of(p) for p in inputs.products}
    problems = debt_errors(inputs.debt, catalog)
    if problems:
        for p in problems:
            print(f"ERROR: {p}")
        return 1
    product_rows, company_rows = build(inputs, now=now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as fh:
        fh.write(render(product_rows, company_rows))
    counts: dict[str, int] = {}
    for r in product_rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    print(f"Wrote {len(product_rows)} product and {len(company_rows)} company coverage rows to "
          f"{args.output} ({', '.join(f'{k} {v}' for k, v in sorted(counts.items()))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
