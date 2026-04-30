"""Write Jekyll Markdown update records from normalized official source data."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

from .normalize import slugify, utc_now, summarize, normalize_release_notes_body

DEFAULT_CONSENSUS = "Insufficient data"

EVIDENCE_STATE_ALIASES = {
    "static_sample": "pilot_sample",
    "static_initial_sample": "pilot_initial_sample",
}

CONSENSUS_STATUS_ALIASES = {
    "static_initial_sample": "pilot_initial_sample",
    "live_consensus": "consensus_live",
}


def _normalize_taxonomy(value: Any, aliases: dict[str, str]) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    return aliases.get(normalized, normalized)


def _intelligence_stage(record: dict[str, Any], evidence_state: str, report_count: int, source_url: Any, body: str) -> str:
    explicit = str(record.get("intelligence_stage") or "").strip().lower().replace("-", "_")
    if explicit:
        return explicit
    if evidence_state == "consensus_live":
        return "consensus_live"
    if evidence_state in {"pilot_sample", "pilot_initial_sample"} or report_count > 0:
        return "pilot"
    if evidence_state == "official_only" and (source_url or body):
        return "official_live"
    if evidence_state == "archived":
        return "archived"
    if evidence_state == "insufficient_data":
        return "staged"
    return "staged"


def _file_size_status(record: dict[str, Any]) -> str:
    if record.get("file_size"):
        return "captured"
    if record.get("file_size_status"):
        return str(record.get("file_size_status"))
    if record.get("file_size_note"):
        return "not_provided_by_source"
    return "pending_adapter_support"

def record_slug(record: dict[str, Any]) -> str:
    version = record.get("version") or record.get("title") or record.get("record_id")
    return slugify(version)

def output_path(output_dir: Path, record: dict[str, Any]) -> Path:
    published = str(record.get("published_at") or utc_now())
    date_slug = published[:10] if len(published) >= 10 else utc_now()[:10]
    product_slug = slugify(record.get("software") or record.get("product_id"))
    return output_dir / f"{date_slug}-{product_slug}-{record_slug(record)}.md"

def build_front_matter(record: dict[str, Any]) -> dict[str, Any]:
    version = record.get("version") or record.get("title") or "Update"
    version_slug = record_slug(record)
    software = record.get("software") or record.get("product_id")
    company = record.get("company") or record.get("company_id")
    published = record.get("published_at") or utc_now()
    source_url = record.get("source_url") or record.get("official_url")
    body = normalize_release_notes_body(record.get("body") or "No official release-note body was captured.")
    summary = record.get("summary") or summarize(body)
    report_count = int(record.get("report_count") or record.get("update_report_count") or 0)
    consensus_label = record.get("consensus_label") or record.get("update_consensus_label") or DEFAULT_CONSENSUS
    consensus_confidence = record.get("consensus_confidence") or record.get("update_consensus_confidence") or "Low"
    consensus_status_raw = record.get("consensus_collection_status") or ("pilot_initial_sample" if report_count else "deferred_official_only")
    consensus_status = _normalize_taxonomy(consensus_status_raw, CONSENSUS_STATUS_ALIASES)
    evidence_state_raw = record.get("evidence_state") or ("pilot_sample" if report_count else "official_only")
    evidence_state = _normalize_taxonomy(evidence_state_raw, EVIDENCE_STATE_ALIASES)
    evidence_state_label = record.get("evidence_state_label")
    if not evidence_state_label or str(evidence_state_label).strip().lower() == "static sample":
        evidence_state_label = "Pilot sample" if evidence_state in {"pilot_sample", "pilot_initial_sample"} else "Official only"
    intelligence_stage = _intelligence_stage(record, evidence_state, report_count, source_url, body)
    quick_verdict = record.get("quick_verdict") or f"{software} {version} has an official AUXSAYS record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active."
    if evidence_state in {"pilot_sample", "pilot_initial_sample"}:
        quick_verdict = record.get("quick_verdict") or f"{software} {version} includes a pilot sample of confirmed patch-specific reports. It is not live consensus yet."
    consensus_report = record.get("consensus_report") or "Confirmed patch-specific consensus collection is deferred. This page currently reflects official-source ingestion only."
    known_issues_present = record.get("known_issues_present")
    if known_issues_present is None and record.get("complaint_themes"):
        known_issues_present = True
    status_events = record.get("status_events") or [
        {"at": published, "label": "Published", "note": "Official source entry detected."},
        {"at": utc_now(), "label": consensus_label, "note": "AUXSAYS official-ingestion record initialized."},
    ]
    return {
        "layout": "aux-update",
        "title": f"{software} {version} official update breakdown",
        "description": f"Official {software} update record captured from {company}.",
        "permalink": f"/updates/{record['company_id']}/{record['product_id']}/{version_slug}/",
        "update_entry": True,
        "company_id": record["company_id"],
        "product_id": record["product_id"],
        "update_brand_id": record["product_id"],
        "update_product": software,
        "update_category": record.get("category") or "creator-software",
        "update_type": record.get("update_type") or "official-source",
        "update_source_name": company,
        "update_source_url": source_url,
        "update_download_url": record.get("download_url") or "",
        "update_version": str(version),
        "update_logo_text": record.get("logo_text") or str(software)[:3].upper(),
        "update_published_at": published,
        "update_last_checked": utc_now(),
        "patch_file_size": record.get("file_size") or "",
        "patch_file_size_note": record.get("file_size_note") or "",
        "patch_file_size_status": _file_size_status(record),
        "update_status": "current",
        "update_feed_title": f"{software} {version}",
        "update_detail_title": f"{software} {version}",
        "update_consensus_label": consensus_label,
        "update_report_count": report_count,
        "update_consensus_confidence": consensus_confidence,
        "quick_verdict": quick_verdict,
        "official_summary": record.get("official_summary") or f"{company} published {software} {version}.",
        "release_summary": summary,
        "consensus_report": consensus_report,
        "evidence_state": evidence_state,
        "evidence_state_label": evidence_state_label,
        "intelligence_stage": intelligence_stage,
        "official_source_captured": bool(source_url or body),
        "confirmed_patch_specific_report_count": report_count,
        "known_issues_present": known_issues_present,
        "consensus_collection_status": consensus_status,
        "consensus_match_policy": "confirmed_patch_specific_reports_v1",
        "consensus_match_policy_label": "Confirmed patch-specific reports only",
        "consensus_report_count_label": "confirmed patch-specific reports",
        "consensus_report_weighting": "equal_per_confirmed_report",
        "consensus_low_context_policy": "excluded",
        "complaint_themes": record.get("complaint_themes") or [],
        "status_events": status_events,
        "official_patch_notes_source_type": record.get("source_type") or "official-source",
        "official_patch_notes_capture_status": record.get("capture_status") or "captured-from-official-source",
        "official_patch_notes_source_url": source_url,
        "official_patch_notes_body": body,
        "official_checksums_body": record.get("checksums_body") or "",
        "official_checksums_capture_status": "captured-from-official-release" if record.get("checksums_body") else "not-present",
    }

def write_record(output_dir: Path, record: dict[str, Any], overwrite_existing: bool = False) -> tuple[Path, bool]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_path(output_dir, record)
    if path.exists() and not overwrite_existing:
        return path, False
    front = build_front_matter(record)
    text = "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=120) + "---\n"
    path.write_text(text, encoding="utf-8")
    return path, True
