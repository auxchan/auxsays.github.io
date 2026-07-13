#!/usr/bin/env python3
"""Run automated patch evidence collectors through one shared entry point."""
from __future__ import annotations

import argparse
import json
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


def since_from_days(days: int | None) -> str | None:
    if days is None:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=max(0, days))).date().isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AUXSAYS patch evidence collection.")
    parser.add_argument(
        "--product-id",
        action="append",
        choices=sorted(COLLECTORS),
        help="Product to collect. May be passed more than once. Defaults to all Phase A collectors.",
    )
    parser.add_argument("--update-version", action="append", help="Exact update_version filter. May be passed more than once.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Fetch and report without writing evidence or records.")
    mode.add_argument("--write", action="store_true", help="Write accepted evidence and update matching generated records.")
    parser.add_argument("--since", help="Optional YYYY-MM-DD lower bound for collectors that support it.")
    parser.add_argument("--since-days", type=int, help="Optional lower bound relative to today.")
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args(argv)

    product_ids = args.product_id or sorted(COLLECTORS)
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
        collector = COLLECTORS[product_id]()
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
