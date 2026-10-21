#!/usr/bin/env python3
"""Derive the PUBLIC monitoring status from what collection actually did.

WHAT WAS WRONG. `coverage_status_label` is a static editorial string in
`_data/patch_companies.yml`, and the product and company pages rendered it as a monitoring
claim. It tracks nothing. Measured across 47 products: 29 publicly claimed "Monitoring active"
with NO enabled ingestion source -- including several where nothing has ever been collected --
while `netlify` claimed it with a recorded state of `broken`, and `microsoft-windows-11` and
`microsoft-teams` claimed "Source map staged" while enabled, healthy and producing records that
day. The field was not cautious; it was decoupled, and wrong in both directions.

Four products were worse than mislabelled: the Elgato set is ENABLED and had 226, 226, 146 and
102 CONSECUTIVE FAILURES, with last successes between 2026-08-18 and 2026-09-21. A reader
deciding whether to trust an absence of reports was told none of that.

WHAT THIS EMITS, AND WHAT IT DELIBERATELY DOES NOT. A minimal projection: one row per product
carrying a state from a CLOSED vocabulary, a reader-facing label, and two dates. It carries no
error text, no adapter name, no method id, no failure counter and no health note. The richer
`source_health.yml` already exists and its rows hold 24 fields including `last_error`,
`adapter_type`, `consecutive_failures` and `raw_extractable_fields`; rendering that on a product
page would put all of it in template scope. So this is a separate, narrow file rather than a
reuse of that one.

FAIL CLOSED IS THE WHOLE POINT. `healthy` is the only affirmative state and it has to be EARNED:
an enabled source, a healthy recorded status, and a SUCCESS recent enough for its own cadence.
Everything else -- absent state, a status this file does not recognise, a product that cannot be
joined to a source -- resolves to `unverified`. A state that cannot be established is never
rendered as working.

Run:  python auxsays/scripts/build_monitoring_projection.py
      python auxsays/scripts/build_monitoring_projection.py --check   (no write; non-zero if stale)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_PATH = ROOT / "_data" / "patch_products.yml"
SOURCES_PATH = ROOT / "_data" / "patch_ingestion_sources.yml"
STATE_PATH = ROOT / "_data" / "patch_ingest_state.json"
OUTPUT_PATH = ROOT / "_data" / "monitoring_state.yml"
COMPANIES_PATH = ROOT / "_data" / "patch_companies.yml"
COMPANY_OUTPUT_PATH = ROOT / "_data" / "monitoring_company_state.yml"

# The CLOSED public vocabulary. `healthy` is the only affirmative member.
#
# `blocked`, `unreachable` and `broken` are kept apart on purpose: a source that refuses us, a
# source that never answered, and a source we reached but could not read are three different
# facts, and collapsing them would tell a reader something untrue about which one happened.
PUBLIC_STATES = (
    "healthy",       # enabled, recorded healthy, and succeeded recently enough for its cadence
    "stale",         # succeeded once, but not recently enough to call it working
    "blocked",       # the source refused automated checks
    "unreachable",   # the source did not answer
    "broken",        # the source answered, but the response could not be read
    "disabled",      # a source is configured and deliberately not running
    "unconfigured",  # no ingestion source exists for this product at all
    "unverified",    # state absent, unrecognised, or not joinable to a source -- FAIL CLOSED
)

# Reader-facing copy. Deliberately plain: it states what happened, never what it implies about
# the software itself. None of these is evidence about an update.
STATE_LABELS = {
    "healthy": "Monitoring active",
    "stale": "No recent successful check",
    "blocked": "Source is refusing automated checks",
    "unreachable": "Source did not respond",
    "broken": "Source responded but could not be read",
    # Both of these say the same true thing to a reader -- nothing is collecting for this
    # product right now -- and the distinction between "a source exists but is switched off"
    # and "no source exists" is an internal one. "Paused" was rejected: it implies monitoring
    # was once running, and for most of these it never has been.
    "disabled": "Not currently monitored",
    "unconfigured": "Not currently monitored",
    "unverified": "Monitoring status unknown",
}

# A success is "recent" relative to the source's OWN cadence, not a single global number. Four
# missed cycles is an unambiguous signal, and the 48-hour floor keeps the fastest lane (6h) from
# being called stale after a single bad night.
RECENCY_MULTIPLE = 4
RECENCY_FLOOR = timedelta(hours=48)
RECENCY_CEILING = timedelta(days=14)


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def parse_cadence(value: Any) -> timedelta | None:
    """A declared polling frequency as a duration. None when there is no schedule to miss."""
    text = str(value or "").strip().lower()
    if not text or text == "manual":
        return None
    if text.endswith("h") and text[:-1].isdigit():
        return timedelta(hours=int(text[:-1]))
    if text.endswith("d") and text[:-1].isdigit():
        return timedelta(days=int(text[:-1]))
    return None


def recency_window(cadence: timedelta | None, override_hours: Any = None) -> timedelta | None:
    """How old a success may be and still count. None means recency does not apply."""
    if override_hours not in (None, ""):
        try:
            return timedelta(hours=float(override_hours))
        except (TypeError, ValueError):
            pass  # an unparseable override must not silently widen the window
    if cadence is None:
        return None
    window = cadence * RECENCY_MULTIPLE
    if window < RECENCY_FLOOR:
        window = RECENCY_FLOOR
    return min(window, RECENCY_CEILING)


def parse_instant(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def derive_state(source: dict | None, state: dict | None, *, now: datetime) -> str:
    """The public state for one product. Returns a PUBLIC_STATES member, never anything else.

    Order matters. `healthy` is checked LAST and must satisfy every condition; every earlier
    branch is a reason not to claim the source is working.
    """
    if not source:
        return "unconfigured"
    if not source.get("enabled"):
        return "disabled"

    if not isinstance(state, dict) or not state:
        # The source is switched on and we have no record of it ever running.
        return "unverified"

    status = str(state.get("status") or "").strip().lower()
    error_type = str(state.get("last_error_type") or "").strip().lower()

    if status == "broken":
        return "broken"
    if status in ("failing", "failed", "error"):
        if error_type == "blocked":
            return "blocked"
        if error_type == "timeout":
            return "unreachable"
        return "unverified"   # failing for a reason this file does not recognise

    if status != "healthy":
        return "unverified"   # an unrecognised status is never an affirmative claim

    # Recorded healthy. That is necessary and not sufficient: it must have SUCCEEDED recently.
    last_success = parse_instant(state.get("last_success_at"))
    if last_success is None:
        return "unverified"
    ingestion = source.get("ingestion") or {}
    window = recency_window(
        parse_cadence(ingestion.get("polling_frequency") or source.get("polling_frequency")),
        ingestion.get("monitoring_recency_hours") or source.get("monitoring_recency_hours"),
    )
    if window is None:
        # No schedule, so recency cannot be judged. A manual source is not "active monitoring".
        return "disabled"
    if now - last_success > window:
        return "stale"
    return "healthy"


def company_state(child_states: list[str]) -> tuple[str, str]:
    """Aggregate a company's public state from its products'. Fail-closed, like the product one.

    A company is a collection of products with DIFFERENT states, so the honest summary is a
    count, not a single adjective. Before this, 27 companies asserted "Monitoring active" with
    no healthy product at all.
    """
    total = len(child_states)
    if total == 0:
        return "unconfigured", STATE_LABELS["unconfigured"]
    healthy = sum(1 for s in child_states if s == "healthy")
    if healthy == total:
        return "healthy", "Monitoring active"
    if healthy > 0:
        return "partial", f"Monitoring {healthy} of {total}"
    # Nothing healthy. Say WHY, because "not monitored" and "checks failing" are different facts
    # and a reader weighing an absence of reports needs to know which one applies.
    if any(s in ("blocked", "unreachable", "broken") for s in child_states):
        return "failing", "Source checks failing"
    if all(s in ("disabled", "unconfigured") for s in child_states):
        return "disabled", STATE_LABELS["disabled"]
    if any(s == "stale" for s in child_states):
        return "stale", "No recent successful check"
    return "unverified", STATE_LABELS["unverified"]


COMPANY_STATES = ("healthy", "partial", "failing", "stale", "disabled", "unconfigured",
                  "unverified")


def day(value: Any) -> str:
    """A date, never a timestamp: the hour a check ran is operational detail."""
    dt = parse_instant(value)
    return dt.date().isoformat() if dt else ""


def build_rows(*, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    products = load_yaml(PRODUCTS_PATH) or []
    sources = load_yaml(SOURCES_PATH) or []
    raw_state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    state_by_product = raw_state.get("sources") or {}

    source_by_product = {}
    for src in sources:
        if isinstance(src, dict) and src.get("product_id"):
            source_by_product[src["product_id"]] = src

    rows = []
    for product in products:
        if not isinstance(product, dict):
            continue
        pid = product.get("product_id") or product.get("id")
        if not pid:
            continue
        src = source_by_product.get(pid)
        st = state_by_product.get(pid)
        public_state = derive_state(src, st, now=now)
        if public_state not in PUBLIC_STATES:          # belt: derive_state must never do this
            public_state = "unverified"
        row = {
            "product_id": pid,
            "state": public_state,
            "label": STATE_LABELS[public_state],
            # Dates only, and only when they exist. A reader judging an absence of reports needs
            # to know how old that absence is; they do not need the hour or the adapter.
            "last_success": day((st or {}).get("last_success_at")) if st else "",
            "last_checked": day((st or {}).get("last_checked_at")) if st else "",
        }
        rows.append(row)
    rows.sort(key=lambda r: r["product_id"])
    return rows


def build_company_rows(product_rows: list[dict], *, products=None, companies=None) -> list[dict]:
    products = products if products is not None else (load_yaml(PRODUCTS_PATH) or [])
    companies = companies if companies is not None else (load_yaml(COMPANIES_PATH) or [])
    state_by_product = {r["product_id"]: r["state"] for r in product_rows}

    children: dict[str, list[str]] = {}
    for product in products:
        if not isinstance(product, dict):
            continue
        pid = product.get("product_id") or product.get("id")
        cid = product.get("company_id")
        if not pid or not cid:
            continue
        children.setdefault(cid, []).append(state_by_product.get(pid, "unverified"))

    out = []
    for company in companies:
        if not isinstance(company, dict):
            continue
        cid = company.get("id") or company.get("company_id")
        if not cid:
            continue
        state, label = company_state(children.get(cid, []))
        if state not in COMPANY_STATES:
            state, label = "unverified", STATE_LABELS["unverified"]
        out.append({
            "company_id": cid,
            "state": state,
            "label": label,
            "monitored": sum(1 for s in children.get(cid, []) if s == "healthy"),
            "total": len(children.get(cid, [])),
        })
    out.sort(key=lambda r: r["company_id"])
    return out


def render(rows: list[dict]) -> str:
    header = (
        "# GENERATED by auxsays/scripts/build_monitoring_projection.py -- do not edit by hand.\n"
        "#\n"
        "# The PUBLIC monitoring state per product, derived from what collection actually did.\n"
        "# The pages read THIS and never the raw ingest state: that file carries error bodies,\n"
        "# adapter names and failure counters, and nothing here may expose them. `healthy` is the\n"
        "# only affirmative state and it must be earned -- enabled, recorded healthy, and a\n"
        "# success recent enough for the source's own cadence. Anything unestablished is\n"
        "# `unverified`, never a claim that monitoring is working.\n"
    )
    return header + yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=100)


def render_companies(rows: list[dict]) -> str:
    header = """
# GENERATED by auxsays/scripts/build_monitoring_projection.py -- do not edit by hand.
#
# The PUBLIC monitoring state per COMPANY, aggregated from its products' states. The same
# editorial field lied one level up: 27 companies asserted 'Monitoring active' with no healthy
# product at all. A company is a set of products in different states, so the honest summary is
# a count, and when nothing is healthy it says WHY -- 'not monitored' and 'checks failing' are
# different facts, and a reader weighing an absence of reports needs to know which applies.
"""
    return header + yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=100)

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit non-zero if the committed projection is stale")
    args = ap.parse_args(argv)

    rows = build_rows()
    text = render(rows)
    company_rows = build_company_rows(rows)
    company_text = render_companies(company_rows)

    if args.check:
        stale = []
        for path, want in ((OUTPUT_PATH, text), (COMPANY_OUTPUT_PATH, company_text)):
            have = ""
            if path.exists():
                with open(path, encoding="utf-8", newline="") as fh:
                    have = fh.read().replace("\r\n", "\n")
            if have != want:
                stale.append(path.name)
        if stale:
            print("monitoring projection is stale; regenerate it: " + ", ".join(stale),
                  file=sys.stderr)
            return 1
        print(f"monitoring projection current ({len(rows)} products, "
              f"{len(company_rows)} companies)")
        return 0

    # Newlines are pinned so the output is byte-identical on every
    # platform: write_text() would translate them to os.linesep, making the
    # generator platform-dependent and the committed projection churn between
    # a Windows developer machine and the Linux runner.
    # making the generator platform-dependent and the committed projection churn between a
    # Windows developer and the Linux runner.
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    with open(COMPANY_OUTPUT_PATH, "w", encoding="utf-8", newline="") as fh:
        fh.write(company_text)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    cc: dict[str, int] = {}
    for r in company_rows:
        cc[r["state"]] = cc.get(r["state"], 0) + 1
    print(f"Wrote {len(rows)} product rows to {OUTPUT_PATH.relative_to(ROOT)} ({summary})")
    print(f"Wrote {len(company_rows)} company rows to "
          f"{COMPANY_OUTPUT_PATH.relative_to(ROOT)} "
          f"({', '.join(f'{k} {v}' for k, v in sorted(cc.items()))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
