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


def build_collectors(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Return the runtime collector registry: the always-on base plus the Windows Learn Q&A
    collector IFF its activation flag is explicitly enabled. This is the single place that
    decides Windows registration, so no scheduled ``--write`` run can reach the collector
    while the flag is off. The collector class is imported lazily so it is only pulled in
    when actually enabled."""
    collectors: dict[str, Any] = dict(COLLECTORS)
    if windows_learn_qna_writeback_enabled(env):
        from patch_collectors.microsoft_windows import WindowsLearnQnaCollector
        collectors[WINDOWS_LEARN_QNA_PRODUCT_ID] = WindowsLearnQnaCollector
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
