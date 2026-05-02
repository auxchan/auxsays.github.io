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
UPDATE_LAYOUT_PATH = ROOT / "_layouts" / "aux-update.html"

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


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def has_structured_evidence(data: dict[str, Any]) -> bool:
    evidence = data.get("consensus_evidence") or data.get("structured_evidence") or data.get("evidence_objects")
    return isinstance(evidence, list) and len(evidence) > 0 and all(isinstance(item, dict) for item in evidence)


def contains_public_static_sample(value: Any) -> bool:
    if isinstance(value, str):
        return ("static" + " sample") in value.lower()
    if isinstance(value, list):
        return any(contains_public_static_sample(item) for item in value)
    if isinstance(value, dict):
        return any(contains_public_static_sample(item) for item in value.values())
    return False


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    return ""


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
    if contains_public_static_sample(data):
        add(errors, path, "public_static_sample_wording", "Public-facing generated record data still contains obsolete sample wording. Use 'Verified reports' for confirmed report samples.")
    public_text = flatten_text(data)
    if ("Pilot" + " sample") in public_text or ("pilot" + " sample") in public_text:
        add(errors, path, "public_pilot_sample_wording", "Public-facing generated record data still contains obsolete verified-report wording. Use 'Verified reports'.")

    evidence_samples = data.get("evidence_samples")
    if evidence_samples is not None:
        if not isinstance(evidence_samples, list):
            add(errors, path, "evidence_samples_not_list", "evidence_samples must be a list of source objects.")
        else:
            for idx, item in enumerate(evidence_samples):
                if not isinstance(item, dict):
                    add(errors, path, "evidence_sample_item_not_object", f"evidence_samples[{idx}] must be an object.")
                    continue
                if not looks_like_url(item.get("source_url")):
                    add(errors, path, "evidence_sample_missing_source_url", f"evidence_samples[{idx}] is missing a valid source_url.")
                if item.get("counted") is True and item.get("patch_version_matched") is not True:
                    add(errors, path, "counted_evidence_without_patch_match", f"evidence_samples[{idx}] is counted but patch_version_matched is not true.")

    stage = str(data.get("intelligence_stage") or "").strip()
    if stage and stage not in VALID_INTELLIGENCE_STAGES:
        add(warnings, path, "unknown_intelligence_stage", f"Intelligence stage '{stage}' is not recognized.")

    for key in ("update_source_url", "official_patch_notes_source_url", "update_download_url"):
        value = data.get(key)
        if value not in (None, "") and not looks_like_url(value):
            add(warnings, path, "malformed_url", f"{key} does not look like a valid HTTP(S) URL.")

    if is_blank(data.get("patch_file_size")) and is_blank(data.get("patch_file_size_status")):
        add(warnings, path, "blank_file_size_without_status", "patch_file_size is blank and no patch_file_size_status explains why.")
    if is_blank(data.get("patch_file_size")) and not is_blank(data.get("patch_file_size_status")):
        valid_file_size_statuses = {"not_provided_by_source", "creative_cloud_managed", "pending_adapter_support"}
        if str(data.get("patch_file_size_status") or "").strip() not in valid_file_size_statuses:
            add(warnings, path, "unknown_file_size_status", "patch_file_size_status is present but not in the normalized status list.")
    if evidence_state == "official_only" and report_count == 0:
        if data.get("known_issues_present") is True:
            add(warnings, path, "official_only_zero_reports_known_issues_yes", "official_only record has 0 reports but known_issues_present is true; the UI may imply patch-specific user reports exist.")
        if data.get("complaint_themes"):
            add(warnings, path, "official_only_zero_reports_complaint_themes", "official_only record has 0 reports but complaint_themes are present; this can imply counted patch-specific user reports.")
        recommendation_text = " ".join(
            [
                str(data.get("quick_verdict") or ""),
                str(data.get("update_decision_label") or ""),
                str(data.get("update_decision_body") or ""),
                flatten_text(data.get("practical_recommendations")),
            ]
        ).lower()
        blocked_recommendation_terms = (
            "wait",
            "avoid",
            "safe enough",
            "production-stable",
            "production systems",
            "install guidance",
            "manual watch",
            "manual-watch",
        )
        if any(term in recommendation_text for term in blocked_recommendation_terms):
            add(warnings, path, "official_only_zero_reports_recommendation_language", "official_only record has 0 reports but still stores install-verdict recommendation language.")
    if str(data.get("official_checksums_capture_status") or "").strip() in {"captured", "present"} and is_blank(data.get("official_checksums_body")):
        add(errors, path, "checksum_status_without_body", "Checksum capture status says checksums are present but official_checksums_body is blank.")
    if is_blank(data.get("official_checksums_body")) and (data.get("show_checksum_section") is True or data.get("checksum_nav_enabled") is True):
        add(errors, path, "checksum_display_without_body", "Record enables checksum display but official_checksums_body is blank.")

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


def scan_update_layout_public_copy() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not UPDATE_LAYOUT_PATH.exists():
        add(errors, UPDATE_LAYOUT_PATH, "missing_update_layout", "aux-update.html is missing.")
        return errors, warnings

    text = UPDATE_LAYOUT_PATH.read_text(encoding="utf-8")
    forbidden_public_copy = {
        "Practical recommendation": "Use public heading 'Recommendation' instead.",
        "Evidence methodology details": "Use 'Consensus Report' for report-bearing pages and hide the large section for 0-report pages.",
        "Static" + " sample": "Public-facing wording must use Verified reports.",
        "Pilot" + " sample": "Public-facing wording must use Verified reports.",
        "pilot" + " sample": "Public-facing wording must use Verified reports.",
        "Intel" + " Status": "Public-facing wording must use Evidence Status.",
        "Official sources are listed first": "Sources should render as concise citations without filler intro copy.",
        "Community bug reports are shown": "Sources should not repeat methodology filler.",
        "AUXSAYS counts a report only when": "Methodology details belong on the methodology page, not patch bodies.",
        "Official source content has not been captured into this AUXSAYS record yet": "Do not force a blank Official Source Summary block.",
    }
    for phrase, message in forbidden_public_copy.items():
        if phrase in text:
            add(errors, UPDATE_LAYOUT_PATH, "layout_public_copy_regression", message)

    if "checksum_body_clean" not in text or "{% if checksum_present %}<a href=\"#checksum\">Checksum</a>{% endif %}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "checksum_nav_not_guarded", "Checksum nav must require stripped non-empty checksum content.")
    if "{{ checksum_body_clean | markdownify }}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "checksum_body_render_path_missing", "Checksum section should render stripped checksum content when present.")
    if "official_body_clean" not in text:
        add(warnings, UPDATE_LAYOUT_PATH, "official_summary_blank_guard_missing", "Official source summary should be guarded by stripped non-empty body content.")

    return errors, warnings


def scan_required_record_paths() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    obs_path = GENERATED_DIR / "2026-04-21-obs-studio-32-1-2.md"
    if obs_path.exists():
        data = front_matter(obs_path)
        if is_blank(data.get("official_checksums_body")):
            add(errors, obs_path, "obs_32_1_2_checksum_missing", "OBS Studio 32.1.2 should retain official_checksums_body content.")
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
    e, w = scan_update_layout_public_copy()
    errors.extend(e)
    warnings.extend(w)
    e, w = scan_required_record_paths()
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
