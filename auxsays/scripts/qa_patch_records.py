#!/usr/bin/env python3
"""Warning-first QA for generated AUXSAYS update records and priority source coverage."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"
OUT_PATH = ROOT / "_data" / "qa_status.json"
PRODUCTS_PATH = ROOT / "_data" / "patch_products.yml"
SOURCES_PATH = ROOT / "_data" / "patch_ingestion_sources.yml"

VALID_EVIDENCE_STATES = {"official_only", "pilot_sample", "pilot_initial_sample", "consensus_live", "insufficient_data"}
VALID_INTELLIGENCE_STAGES = {"staged", "official_live", "pilot", "consensus_live", "archived"}
PATCH_NOTE_SOURCE_TYPES = {"release_notes", "fixed_issues", "security_advisory", "changelog"}
NON_PATCH_NOTE_SOURCE_TYPES = {"whats_new", "vendor_blog", "community_official_post", "download_portal"}
OPERATIONAL_SOURCE_TYPES = {"release_health", "known_issues", "help_center_release_notes"}
LEGACY_SOURCE_TYPES = {"official-source", "adobe-official-release-source", "github-release", "rss-feed", "vendor-release-page"}
KNOWN_SOURCE_TYPES = PATCH_NOTE_SOURCE_TYPES | NON_PATCH_NOTE_SOURCE_TYPES | OPERATIONAL_SOURCE_TYPES | LEGACY_SOURCE_TYPES

PRIORITY_PRODUCTS = {
    "obs-studio",
    "blackmagic-davinci",
    "adobe-premiere-pro",
    "adobe-acrobat-reader",
    "microsoft-windows-11",
    "elgato-stream-deck",
    "elgato-wave-link",
    "elgato-camera-hub",
    "elgato-4k-capture-utility",
    "adobe-photoshop",
    "openai-chatgpt",
    "microsoft-powerpoint",
    "microsoft-teams",
    "microsoft-365-apps",
}


def load_yaml(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return fallback if data is None else data


def front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data if isinstance(data, dict) else {}


def add(bucket: list[dict[str, str]], path: Path | str, code: str, message: str) -> None:
    file_value = str(path.relative_to(ROOT)) if isinstance(path, Path) and path.is_absolute() else str(path)
    bucket.append({"file": file_value, "code": code, "message": message})


def looks_like_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def has_structured_evidence(data: dict[str, Any]) -> bool:
    evidence = data.get("consensus_evidence") or data.get("structured_evidence") or data.get("evidence_objects")
    return isinstance(evidence, list) and len(evidence) > 0 and all(isinstance(item, dict) for item in evidence)


def scan_record(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    data = front_matter(path)
    if not data:
        add(errors, path, "missing_front_matter", "Generated record has no readable YAML front matter.")
        return errors, warnings

    title = str(data.get("title") or "").strip()
    summary = str(data.get("release_summary") or data.get("summary") or data.get("description") or "").strip()
    version = str(data.get("update_version") or data.get("version") or "").strip()
    detail_title = str(data.get("update_detail_title") or "").strip()
    evidence_state = str(data.get("evidence_state") or "").strip()
    source_type = str(data.get("official_patch_notes_source_type") or data.get("official_source_type") or "").strip()
    official_body = str(data.get("official_patch_notes_body") or "")
    report_count = int(data.get("update_report_count") or data.get("confirmed_patch_specific_report_count") or 0)

    if not title:
        add(errors, path, "empty_title", "Generated record title is empty.")
    if not summary:
        add(warnings, path, "empty_summary", "Generated record has no useful summary/description.")

    if version and detail_title and len(re.findall(re.escape(version), detail_title, flags=re.I)) > 1:
        add(warnings, path, "duplicated_detail_title_version", f"Detail title appears to repeat version '{version}'.")
    if version and title and len(re.findall(re.escape(version), title, flags=re.I)) > 1:
        add(warnings, path, "duplicated_title_version", f"Title appears to repeat version '{version}'.")

    if evidence_state == "official_only" and report_count > 0:
        add(errors, path, "official_only_with_reports", "Record has report_count > 0 but evidence_state is official_only.")
    if evidence_state == "consensus_live" and not has_structured_evidence(data):
        add(errors, path, "live_without_structured_evidence", "consensus_live requires structured evidence objects.")
    if evidence_state and evidence_state not in VALID_EVIDENCE_STATES:
        add(warnings, path, "unknown_evidence_state", f"Evidence state '{evidence_state}' is not in the normalized taxonomy.")

    stage = str(data.get("intelligence_stage") or "").strip()
    if stage and stage not in VALID_INTELLIGENCE_STAGES:
        add(warnings, path, "unknown_intelligence_stage", f"Intelligence stage '{stage}' is not recognized.")

    for key in ("update_source_url", "official_patch_notes_source_url", "update_download_url"):
        value = data.get(key)
        if value not in (None, "") and not looks_like_url(value):
            add(warnings, path, "malformed_url", f"{key} does not look like a valid HTTP(S) URL.")

    if data.get("patch_file_size") in (None, "") and not data.get("patch_file_size_status"):
        add(warnings, path, "blank_file_size_without_status", "patch_file_size is blank and no patch_file_size_status explains why.")

    official_claim = " ".join([title, detail_title, official_body[:500]]).lower()
    if "patch notes" in official_claim and source_type in NON_PATCH_NOTE_SOURCE_TYPES:
        add(errors, path, "patch_notes_claim_from_non_patch_source", f"Source type '{source_type}' must not be labeled as patch notes.")
    if source_type in NON_PATCH_NOTE_SOURCE_TYPES and data.get("official_note_status") == "release_notes_captured":
        add(errors, path, "release_notes_status_mismatch", "Non-release source is marked release_notes_captured.")
    if source_type and source_type not in KNOWN_SOURCE_TYPES:
        add(warnings, path, "unknown_official_source_type", f"official source type '{source_type}' is not classified.")

    official_sources = data.get("official_sources")
    if official_sources is not None:
        if not isinstance(official_sources, list):
            add(warnings, path, "official_sources_not_list", "official_sources should be a list of source objects.")
        else:
            for idx, item in enumerate(official_sources):
                if not isinstance(item, dict):
                    add(warnings, path, "official_source_item_not_object", f"official_sources[{idx}] is not an object.")
                    continue
                if not looks_like_url(item.get("url")):
                    add(warnings, path, "official_source_item_bad_url", f"official_sources[{idx}] has a malformed URL.")
                if not item.get("source_type"):
                    add(warnings, path, "official_source_item_missing_type", f"official_sources[{idx}] is missing source_type.")

    return errors, warnings


def scan_priority_source_coverage() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    products = load_yaml(PRODUCTS_PATH, [])
    sources = load_yaml(SOURCES_PATH, [])
    product_ids = {str(item.get("product_id") or item.get("id")) for item in products if isinstance(item, dict)}
    source_by_product = {str(item.get("product_id")): item for item in sources if isinstance(item, dict)}

    for product_id in sorted(PRIORITY_PRODUCTS):
        if product_id not in product_ids:
            add(warnings, PRODUCTS_PATH, "priority_product_missing_product_record", f"Priority product '{product_id}' has no patch_products.yml record.")
            continue
        source = source_by_product.get(product_id)
        if not source:
            add(warnings, SOURCES_PATH, "priority_product_missing_source_config", f"Priority product '{product_id}' has no source config entry.")
            continue
        ingestion = source.get("ingestion") if isinstance(source.get("ingestion"), dict) else {}
        official_url = ingestion.get("official_url")
        if not looks_like_url(official_url):
            code = "enabled_source_without_official_url" if source.get("enabled") else "staged_source_without_official_url"
            bucket = errors if source.get("enabled") else warnings
            add(bucket, SOURCES_PATH, code, f"Priority source '{product_id}' does not have a valid official_url.")
        source_type = str(ingestion.get("official_source_type") or ingestion.get("type") or "").strip()
        if source_type and source_type not in KNOWN_SOURCE_TYPES | {"html_release_notes", "github_releases", "help_center_release_notes", "html_changelog", "html_blog"}:
            add(warnings, SOURCES_PATH, "priority_product_unclassified_source_type", f"Priority source '{product_id}' uses unclassified source type '{source_type}'.")

    return errors, warnings


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(GENERATED_DIR.glob("*.md"))
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for path in files:
        e, w = scan_record(path)
        errors.extend(e)
        warnings.extend(w)

    e, w = scan_priority_source_coverage()
    errors.extend(e)
    warnings.extend(w)

    status = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "warning-first",
        "records_scanned": len(files),
        "priority_products_checked": len(PRIORITY_PRODUCTS),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    OUT_PATH.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"QA scanned {len(files)} generated records and {len(PRIORITY_PRODUCTS)} priority products: {len(errors)} errors, {len(warnings)} warnings")
    for item in warnings[:25]:
        print(f"::warning file={item['file']}::{item['code']}: {item['message']}")
    if len(warnings) > 25:
        print(f"::warning::{len(warnings) - 25} additional warnings omitted from log; see auxsays/_data/qa_status.json")
    for item in errors:
        print(f"::error file={item['file']}::{item['code']}: {item['message']}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
