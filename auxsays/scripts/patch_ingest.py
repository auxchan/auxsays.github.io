#!/usr/bin/env python3
"""AUXSAYS official patch ingestion runner.

Default behavior:
- Loads auxsays/_data/patch_ingestion_sources.yml.
- Runs enabled sources only.
- Writes new Markdown records to auxsays/updates/generated.
- Refreshes existing generated records with safe official-source freshness/body fields.
- Tracks dedupe state in auxsays/_data/patch_ingest_state.json.
- Does not overwrite manually curated verdict/report/evidence fields on existing records.

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

from lib.http import fetch_text
from lib.normalize import strip_tags, utc_now
from lib.state import load_state, save_state, is_seen, mark_seen, update_source_success, update_source_error
from lib.write_update_record import refresh_existing_record, write_record

DEFAULT_CONFIG = Path("auxsays/_data/patch_ingestion_sources.yml")
DEFAULT_STATE = Path("auxsays/_data/patch_ingest_state.json")
DEFAULT_OUTPUT = Path("auxsays/updates/generated")

URL_RE = re.compile(r"https?://[^\s\])}>\"']+")
RETRY_CAPTURE_STATUSES = {
    "",
    "partial-existing-record",
    "official-source-linked-body-not-captured",
    "official-source-unreachable",
    "official-source-parser-failed",
    "manual-watch-required",
}


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


def load_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1]) or {}
    return data if isinstance(data, dict) else {}


def body_from_html(html: str) -> str:
    for pattern in [r"<article\b[^>]*>(.*?)</article>", r"<main\b[^>]*>(.*?)</main>"]:
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            body = strip_tags(match.group(1)).strip()
            if len(body) > 300:
                return body[:9000]
    return ""


def body_matches_record(body: str, front: dict[str, Any]) -> bool:
    if len(body.strip()) < 300:
        return False
    haystack = body.lower()
    product = str(front.get("update_product") or "").lower()
    version = str(front.get("update_version") or "").lower()
    return bool((product and product in haystack) or (version and version in haystack))

def should_run(source: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.source and source.get("product_id") not in args.source and source.get("company_id") not in args.source:
        return False
    if args.all:
        return source.get("ingestion", {}).get("adapter") != "manual_watch"
    return bool(source.get("enabled"))


def refresh_linked_official_bodies(sources: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.dry_run or args.no_refresh_linked_bodies:
        return []

    source_by_product = {str(item.get("product_id")): item for item in sources if isinstance(item, dict)}
    results: list[dict[str, Any]] = []
    for path in sorted(args.output.glob("*.md")):
        front = load_front_matter(path)
        if not front.get("update_entry") or str(front.get("official_patch_notes_body") or "").strip():
            continue
        status = str(front.get("official_patch_notes_capture_status") or "").strip()
        if status not in RETRY_CAPTURE_STATUSES:
            continue
        source_url = str(front.get("official_patch_notes_source_url") or front.get("update_source_url") or "").strip()
        if not source_url.startswith(("http://", "https://")):
            continue

        source = source_by_product.get(str(front.get("product_id") or ""))
        ingestion = (source or {}).get("ingestion") or {}
        request = ingestion.get("request") or {}
        checked_at = utc_now()
        record = {
            "company_id": front.get("company_id"),
            "product_id": front.get("product_id"),
            "version": front.get("update_version"),
            "source_url": source_url,
            "official_url": ingestion.get("official_url") or source_url,
            "primary_official_source": source_url,
            "fallback_official_sources": [],
            "source_last_checked": checked_at,
            "_source_checked_at": checked_at,
        }

        try:
            fetched = fetch_text(
                source_url,
                timeout=int(request.get("timeout_seconds") or 30),
                retries=int(request.get("retries") or 0),
                backoff_seconds=float(request.get("backoff_seconds") or 2),
                max_bytes=int(request.get("max_bytes") or 0) or None,
            )
            body = body_from_html(fetched.text)
            if body_matches_record(body, front):
                record["body"] = body
                record["capture_status"] = "captured-from-primary"
            else:
                record["body"] = ""
                record["capture_status"] = "official-source-parser-failed"
        except Exception:
            record["body"] = ""
            record["capture_status"] = "official-source-unreachable"

        refreshed_path, action = refresh_existing_record(path, record)
        results.append({"path": str(refreshed_path), "action": action, "source_url": source_url})
    return results

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
    refreshed = []
    for record in records:
        record_id = record.get("record_id")
        if not record_id:
            record_id = f"{product_id}:{record.get('source_url') or record.get('title') or record.get('version')}"
            record["record_id"] = record_id

        ingestion = source.get("ingestion", {}) or {}
        record["source_last_checked"] = checked_at
        record["_source_checked_at"] = checked_at
        record.setdefault("primary_official_source", ingestion.get("official_url") or record.get("official_url") or record.get("source_url"))
        fallback_sources = [url for url in [ingestion.get("secondary_official_url")] if url]
        record.setdefault("fallback_official_sources", fallback_sources)

        path, action = write_record(args.output, record, overwrite_existing=args.overwrite_existing)
        mark_seen(state, product_id, record_id)
        if action == "created":
            written.append(str(path))
        elif action in {"refreshed", "freshness-updated"}:
            refreshed.append({"record_id": record_id, "action": action, "path": str(path)})
        else:
            reason = "state-seen-unchanged" if is_seen(state, product_id, record_id) else action
            skipped.append({"record_id": record_id, "reason": reason, "path": str(path)})

    duration_ms = int((time.monotonic() - started) * 1000)
    update_source_success(
        state,
        product_id,
        checked_at=checked_at,
        duration_ms=duration_ms,
        adapter=adapter_name,
        fetched=len(records),
        written=len(written) + len(refreshed),
        skipped=len(skipped),
    )

    return {
        "product_id": product_id,
        "adapter": adapter_name,
        "fetched": len(records),
        "written": written,
        "refreshed": refreshed,
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
    parser.add_argument("--no-refresh-linked-bodies", action="store_true", help="Skip exact-URL body retry for linked-only existing records.")
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
                    "would_refresh_existing": True,
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
    linked_body_refreshes = refresh_linked_official_bodies(sources, args)
    if not args.dry_run:
        save_state(args.state, state)

    print(json.dumps({"results": results, "errors": errors, "linked_body_refreshes": linked_body_refreshes}, indent=2))
    if errors and args.strict:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
