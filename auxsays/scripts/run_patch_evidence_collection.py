#!/usr/bin/env python3
"""Run automated patch evidence collectors through one shared entry point."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from patch_collectors.base import CollectorContext, upsert_method_health  # noqa: E402
from patch_collectors.adobe_premiere import AdobePremiereCollector  # noqa: E402
from patch_collectors.davinci import DavinciCollector  # noqa: E402
from patch_collectors.obs import ObsCollector  # noqa: E402

COLLECTORS = {
    "adobe-premiere-pro": AdobePremiereCollector,
    "obs-studio": ObsCollector,
    "blackmagic-davinci": DavinciCollector,
}

# --- Windows Learn Q&A: default-off activation gate --------------------------
# The scheduled "Patch Evidence Collection" workflow runs this module with --write and NO
# --product-id, so it invokes every REGISTERED collector. To keep the dormant Windows Learn
# Q&A collector from ever being invoked accidentally by that hourly writeback, it is NOT part
# of the static COLLECTORS base; it is registered ONLY when an explicit enable flag is set.
# The default (flag absent) is always "not registered" -> no Windows writeback. No workflow
# sets this flag; enabling it is a deliberate, separate activation step.
WINDOWS_LEARN_QNA_PRODUCT_ID = "microsoft-windows-11"
WINDOWS_LEARN_QNA_ENABLE_ENV = "AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK"


def windows_learn_qna_writeback_enabled(env: dict[str, str] | None = None) -> bool:
    """Deterministic default-off gate for registering the Windows Learn Q&A collector.

    Returns True ONLY when ``AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK`` resolves to the
    exact canonical boolean ``true`` (case-insensitive, surrounding whitespace trimmed).
    Every other value -- absent, empty, ``false``, ``0``, ``1``, ``yes``, ``on``, or any
    other string -- returns False. Explicit true-only: this deliberately avoids the classic
    ``bool(os.getenv(...))`` pitfall where the string ``"false"`` is truthy.
    """
    source = os.environ if env is None else env
    return str(source.get(WINDOWS_LEARN_QNA_ENABLE_ENV, "")).strip().lower() == "true"


# --- Adobe Acrobat community consensus: default-off activation gate -----------
# GitHub Actions dry-runs (2026-07-18, PR #23) proved that BOTH discovery methods are
# blocked from CI for both editions and every current version: Adobe Community search
# returns an HTTP 403 CloudFront block, and Reddit returns HTTP 403/429 across every JSON
# and Atom endpoint. The activation minimum -- at least one method per product completing
# a dry-run as success or no_results from a reachable source -- is therefore NOT met. The
# shared Acrobat collector is fully implemented and tested, but registering it in the
# always-on base would make the hourly scheduled ``--write`` writeback treat Acrobat
# consensus as active while every source is blocked. So, exactly like the Windows Learn Q&A
# collector above, it is registered ONLY when an explicit enable flag is set. The default
# (flag absent) is always "not registered". No workflow sets this flag; turning it on --
# together with proving a reachable source and re-adding the workflow routing -- is a
# deliberate, separate activation step.
ACROBAT_CONSENSUS_PRODUCT_IDS = ("adobe-acrobat-reader", "adobe-acrobat-pro")
ACROBAT_CONSENSUS_ENABLE_ENV = "AUXSAYS_ENABLE_ACROBAT_CONSENSUS"


def acrobat_consensus_enabled(env: dict[str, str] | None = None) -> bool:
    """Deterministic default-off gate for registering the Acrobat consensus collectors.

    Returns True ONLY when ``AUXSAYS_ENABLE_ACROBAT_CONSENSUS`` resolves to the exact
    canonical boolean ``true`` (case-insensitive, surrounding whitespace trimmed). Every
    other value -- absent, empty, ``false``, ``0``, ``1``, ``yes``, ``on`` -- returns False.
    Explicit true-only, avoiding the ``bool(os.getenv(...))`` pitfall where ``"false"`` is
    truthy."""
    source = os.environ if env is None else env
    return str(source.get(ACROBAT_CONSENSUS_ENABLE_ENV, "")).strip().lower() == "true"


# --- PowerPoint community consensus: default-off activation gate --------------
# A default-off community-evidence PILOT. Its Learn Q&A discovery is proven CI-reachable, but
# it deliberately does NOT activate scheduled production consensus: exactly like the gates
# above, the collector is registered ONLY when the explicit enable flag resolves to the
# canonical ``true``. The evidence-collection workflow further gates this flag to a MANUAL
# dry_run dispatch, so a scheduled ``--write`` never registers or writes PowerPoint evidence.
POWERPOINT_CONSENSUS_PRODUCT_ID = "microsoft-powerpoint"
POWERPOINT_CONSENSUS_ENABLE_ENV = "AUXSAYS_ENABLE_POWERPOINT_CONSENSUS"


def powerpoint_consensus_enabled(env: dict[str, str] | None = None) -> bool:
    """Deterministic default-off gate for registering the PowerPoint consensus collector.

    Returns True ONLY when ``AUXSAYS_ENABLE_POWERPOINT_CONSENSUS`` resolves to the exact
    canonical boolean ``true`` (case-insensitive, surrounding whitespace trimmed). Every other
    value -- absent, empty, ``false``, ``0``, ``1``, ``yes``, ``on`` -- returns False.
    Explicit true-only, avoiding the ``bool(os.getenv(...))`` pitfall where ``"false"`` is
    truthy."""
    source = os.environ if env is None else env
    return str(source.get(POWERPOINT_CONSENSUS_ENABLE_ENV, "")).strip().lower() == "true"


def build_collectors(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Return the runtime collector registry: the always-on base plus each default-off
    collector IFF its activation flag is explicitly enabled. This is the single place that
    decides registration, so no scheduled ``--write`` run can reach a gated collector while
    its flag is off. Gated collector classes are imported lazily so they are only pulled in
    when actually enabled.

    - Windows Learn Q&A: ``AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK``.
    - Adobe Acrobat (Reader + Pro) consensus: ``AUXSAYS_ENABLE_ACROBAT_CONSENSUS`` -- held
      off because both discovery methods are currently blocked from CI (see PR #23).
    - Microsoft PowerPoint consensus PILOT: ``AUXSAYS_ENABLE_POWERPOINT_CONSENSUS`` -- default
      off; the workflow only sets it for a manual dry_run, never a scheduled ``--write``."""
    collectors: dict[str, Any] = dict(COLLECTORS)
    if windows_learn_qna_writeback_enabled(env):
        from patch_collectors.microsoft_windows import WindowsLearnQnaCollector
        collectors[WINDOWS_LEARN_QNA_PRODUCT_ID] = WindowsLearnQnaCollector
    if acrobat_consensus_enabled(env):
        # Shared collector, registered once per edition. The runner calls
        # collectors[product_id]() zero-arg, so a factory binds each product_id; writeback
        # is keyed by (product_id, update_version), so Reader/Pro never cross-contaminate.
        from patch_collectors.adobe_acrobat_community import AdobeAcrobatCollector
        for pid in ACROBAT_CONSENSUS_PRODUCT_IDS:
            collectors[pid] = lambda p=pid: AdobeAcrobatCollector(p)
    if powerpoint_consensus_enabled(env):
        from patch_collectors.microsoft_powerpoint import PowerPointLearnQnaCollector
        collectors[POWERPOINT_CONSENSUS_PRODUCT_ID] = PowerPointLearnQnaCollector
    return collectors


def since_from_days(days: int | None) -> str | None:
    if days is None:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=max(0, days))).date().isoformat()


def main(argv: list[str] | None = None) -> int:
    collectors = build_collectors()
    parser = argparse.ArgumentParser(description="Run AUXSAYS patch evidence collection.")
    parser.add_argument(
        "--product-id",
        action="append",
        choices=sorted(collectors),
        help="Product to collect. May be passed more than once. Defaults to all registered collectors.",
    )
    parser.add_argument("--update-version", action="append", help="Exact update_version filter. May be passed more than once.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Fetch and report without writing evidence or records.")
    mode.add_argument("--write", action="store_true", help="Write accepted evidence and update matching generated records.")
    parser.add_argument("--since", help="Optional YYYY-MM-DD lower bound for collectors that support it.")
    parser.add_argument("--since-days", type=int, help="Optional lower bound relative to today.")
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args(argv)

    product_ids = args.product_id or sorted(collectors)
    context = CollectorContext(
        write=bool(args.write),
        since=args.since or since_from_days(args.since_days),
        max_pages=args.max_pages,
        target_versions=set(args.update_version) if args.update_version else None,
    )

    status = 0
    product_results: list[dict[str, Any]] = []
    method_health: list[dict[str, Any]] = []
    for product_id in product_ids:
        collector = collectors[product_id]()
        try:
            results = collector.collect(context)
        except Exception as exc:
            status = 1
            results = [{
                "product_id": product_id,
                "mode": "write" if context.write else "dry-run",
                "status": "collector_failed",
                "error": str(exc),
                "accepted_count": 0,
                "rejected_count": 0,
                "method_health": [],
            }]
        product_results.append({
            "product_id": product_id,
            "result_count": len(results),
            "accepted_count": sum(int(item.get("accepted_count") or 0) for item in results),
            "rejected_count": sum(int(item.get("rejected_count") or 0) for item in results),
            "results": results,
        })
        for result in results:
            for row in result.get("method_health") or []:
                if isinstance(row, dict):
                    method_health.append(row)

    method_health_changed = 0
    method_health_total = 0
    if context.write and method_health:
        method_health_changed, method_health_total, _rows = upsert_method_health(method_health)

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": "write" if context.write else "dry-run",
        "since": context.since,
        "max_pages": context.max_pages,
        "product_ids": product_ids,
        "target_versions": sorted(context.target_versions) if context.target_versions else None,
        "products": product_results,
        "accepted_count": sum(item["accepted_count"] for item in product_results),
        "rejected_count": sum(item["rejected_count"] for item in product_results),
        "method_health_rows": len(method_health),
        "method_health_rows_changed": method_health_changed,
        "method_health_rows_total": method_health_total,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
