#!/usr/bin/env python3
"""AUXSAYS official patch ingestion runner.

Default behavior:
- Loads auxsays/_data/patch_ingestion_sources.yml.
- Runs enabled sources only.
- Writes new Markdown records to auxsays/updates/generated.
- Tracks dedupe state in auxsays/_data/patch_ingest_state.json.
- Does not overwrite existing hand-authored or previously generated records.

This is official-source ingestion only. Confirmed patch-specific consensus is intentionally deferred.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any
import re

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.normalize import utc_now
from lib.state import load_state, save_state, is_seen, mark_seen, update_source_success, update_source_error
from lib.write_update_record import write_record

DEFAULT_CONFIG = Path("auxsays/_data/patch_ingestion_sources.yml")
DEFAULT_STATE = Path("auxsays/_data/patch_ingest_state.json")
DEFAULT_OUTPUT = Path("auxsays/updates/generated")

URL_RE = re.compile(r"https?://[^\s\])}>\"']+")


def sanitize_error_message(message: object) -> str:
    """Keep Action headlines readable while preserving URLs in source config/state.

    GitHub Actions auto-links URLs in log output. For fetch failures, that makes
    the URL dominate the error and has repeatedly made punctuation look like
    part of the URL. The source URL remains auditable in configuration and source
    health metadata; the top-level error should explain the failure.
    """
    text = str(message)
    return URL_RE.sub("[source URL]", text)

def load_sources(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing ingestion config: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a YAML list")
    return payload

def adapter_module(adapter_name: str):
    safe_name = adapter_name.replace("-", "_")
    return importlib.import_module(f"adapters.{safe_name}")

def should_run(source: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.source and source.get("product_id") not in args.source and source.get("company_id") not in args.source:
        return False
    if args.all:
        return source.get("ingestion", {}).get("adapter") != "manual_watch"
    return bool(source.get("enabled"))

def run_source(source: dict[str, Any], args: argparse.Namespace, state: dict[str, Any]) -> dict[str, Any]:
    product_id = source["product_id"]
    adapter_name = source.get("ingestion", {}).get("adapter") or source.get("ingestion", {}).get("type")
    if not adapter_name:
        raise RuntimeError(f"{product_id} is missing ingestion.adapter")

    started = time.monotonic()
    checked_at = utc_now()
    module = adapter_module(adapter_name)
    records = module.fetch(source, limit=args.limit)
    written = []
    skipped = []
    for record in records:
        record_id = record.get("record_id")
        if not record_id:
            record_id = f"{product_id}:{record.get('source_url') or record.get('title') or record.get('version')}"
            record["record_id"] = record_id

        if is_seen(state, product_id, record_id) and not args.overwrite_existing:
            skipped.append({"record_id": record_id, "reason": "state-seen"})
            continue

        path, created = write_record(args.output, record, overwrite_existing=args.overwrite_existing)
        mark_seen(state, product_id, record_id)
        if created:
            written.append(str(path))
        else:
            skipped.append({"record_id": record_id, "reason": "file-exists", "path": str(path)})

    duration_ms = int((time.monotonic() - started) * 1000)
    update_source_success(
        state,
        product_id,
        checked_at=checked_at,
        duration_ms=duration_ms,
        adapter=adapter_name,
        fetched=len(records),
        written=len(written),
        skipped=len(skipped),
    )

    return {
        "product_id": product_id,
        "adapter": adapter_name,
        "fetched": len(records),
        "written": written,
        "skipped": skipped,
        "status": "success",
        "duration_ms": duration_ms,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Run AUXSAYS official patch ingestion.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source", action="append", help="Run a specific product_id or company_id. May be used multiple times.")
    parser.add_argument("--all", action="store_true", help="Run all non-manual sources, including P2/P3 experimental sources.")
    parser.add_argument("--limit", type=int, default=2, help="Max records per source.")
    parser.add_argument("--overwrite-existing", action="store_true", help="Overwrite existing generated Markdown records.")
    parser.add_argument("--strict", action="store_true", help="Fail the run if any enabled source errors.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report records but do not write state or Markdown.")
    args = parser.parse_args()

    sources = load_sources(args.config)
    state = load_state(args.state)
    state["last_run_started_at"] = utc_now()

    results = []
    errors = []
    for source in sources:
        if not should_run(source, args):
            continue
        try:
            if args.dry_run:
                adapter_name = source.get("ingestion", {}).get("adapter") or source.get("ingestion", {}).get("type")
                records = adapter_module(adapter_name).fetch(source, limit=args.limit)
                results.append({
                    "product_id": source["product_id"],
                    "adapter": adapter_name,
                    "fetched": len(records),
                    "sample_titles": [r.get("title") or r.get("version") for r in records],
                })
            else:
                results.append(run_source(source, args, state))
        except Exception as exc:
            product_id = source.get("product_id")
            adapter_name = source.get("ingestion", {}).get("adapter") or source.get("ingestion", {}).get("type") or "unknown"
            error = {"product_id": product_id, "adapter": adapter_name, "error": sanitize_error_message(exc)}
            errors.append(error)
            if not args.dry_run and product_id:
                update_source_error(
                    state,
                    product_id,
                    checked_at=utc_now(),
                    duration_ms=0,
                    adapter=adapter_name,
                    error=sanitize_error_message(exc),
                )
            print(f"[ERROR] {error['product_id']}: {error['error']}", file=sys.stderr)
            if args.strict:
                break

    state["last_run_finished_at"] = utc_now()
    state["last_results"] = results
    state["last_errors"] = errors
    if not args.dry_run:
        save_state(args.state, state)

    print(json.dumps({"results": results, "errors": errors}, indent=2))
    if errors and args.strict:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
