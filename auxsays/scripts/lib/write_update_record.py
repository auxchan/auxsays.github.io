"""Write Jekyll Markdown update records from normalized official source data."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

from .normalize import slugify, utc_now, summarize, normalize_release_notes_body

DEFAULT_CONSENSUS = "Insufficient data"


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


def _front_matter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    data = yaml.safe_load(parts[1]) or {}
    return data if isinstance(data, dict) else {}, parts[2]


def _dump_record(front: dict[str, Any], body: str = "") -> str:
    return "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=120) + "---\n" + body


def _matching_existing_path(output_dir: Path, record: dict[str, Any]) -> Path | None:
    expected = output_path(output_dir, record)
    if expected.exists():
        return expected

    product_id = str(record.get("product_id") or "").strip()
    version = str(record.get("version") or record.get("update_version") or "").strip()
    if not product_id or not version:
        return None

    for path in sorted(output_dir.glob("*.md")):
        front, _ = _front_matter(path)
        if str(front.get("product_id") or "").strip() != product_id:
            continue
        if str(front.get("update_version") or "").strip() == version:
            return path
    return None


def _useful_body(value: Any) -> str:
    body = normalize_release_notes_body(value or "").strip()
    lowered = body.lower()
    placeholders = (
        "no official release-note body was captured",
        "no official release body was returned",
        "official source linked, but full patch-note body has not been captured yet",
    )
    if not body or any(marker in lowered for marker in placeholders):
        return ""
    return body


def _capture_status(record: dict[str, Any], *, body: str) -> str:
    if not body:
        return str(record.get("capture_status") or "official-source-linked-body-not-captured")
    if record.get("captured_from_fallback"):
        return "captured-from-fallback"
    return str(record.get("capture_status") or "captured-from-primary")


def _official_source_attempt(record: dict[str, Any], checked_at: str, *, body: str, checksums_body: str) -> dict[str, Any]:
    source_url = record.get("source_url") or record.get("official_patch_notes_source_url") or record.get("official_url") or ""
    return {
        "at": checked_at,
        "url": source_url,
        "status": _capture_status(record, body=body),
        "body_captured": bool(body),
        "checksums_captured": bool(checksums_body),
    }

def build_front_matter(record: dict[str, Any]) -> dict[str, Any]:
    version = record.get("version") or record.get("title") or "Update"
    version_slug = record_slug(record)
    software = record.get("software") or record.get("product_id")
    company = record.get("company") or record.get("company_id")
    published = record.get("published_at") or utc_now()
    checked_at = record.get("source_last_checked") or record.get("_source_checked_at") or utc_now()
    source_url = record.get("source_url") or record.get("official_url")
    body = normalize_release_notes_body(record.get("body") or "No official release-note body was captured.")
    useful_body = _useful_body(body)
    checksums_body = record.get("checksums_body") or ""
    summary = record.get("summary") or summarize(body)
    report_count = int(record.get("report_count") or record.get("update_report_count") or 0)
    consensus_label = record.get("consensus_label") or record.get("update_consensus_label") or DEFAULT_CONSENSUS
    consensus_confidence = record.get("consensus_confidence") or record.get("update_consensus_confidence") or "Low"
    consensus_status = record.get("consensus_collection_status") or ("pilot_initial_sample" if report_count else "deferred_official_only")
    evidence_state = record.get("evidence_state") or ("pilot_sample" if report_count else "official_only")
    evidence_state_label = record.get("evidence_state_label") or ("Verified reports" if report_count else "Official source only")
    intelligence_stage = record.get("intelligence_stage") or ("pilot" if report_count else "official_live")
    official_sources = record.get("official_sources") or []
    official_source_type = record.get("official_source_type") or record.get("source_type") or "official-source"
    official_note_status = record.get("official_note_status") or ("release_notes_captured" if official_source_type in {"release_notes", "fixed_issues", "security_advisory", "changelog"} else "official_source_captured")
    official_note_label = record.get("official_note_label") or ("Official release notes" if official_source_type == "release_notes" else "Official source summary")
    quick_verdict = record.get("quick_verdict") or f"{software} {version} has an official AUXSAYS record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active."
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
        "update_last_checked": checked_at,
        "source_last_checked": checked_at,
        "official_body_last_checked": checked_at,
        "record_last_updated": checked_at,
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
        "evidence_last_checked": record.get("evidence_last_checked") or record.get("consensus_last_checked") or "",
        "known_issues_present": known_issues_present,
        "consensus_collection_status": consensus_status,
        "consensus_match_policy": "confirmed_patch_specific_reports_v1",
        "consensus_match_policy_label": "Confirmed patch-specific reports only",
        "consensus_report_count_label": "confirmed patch-specific reports",
        "consensus_report_weighting": "equal_per_confirmed_report",
        "consensus_low_context_policy": "excluded",
        "complaint_themes": record.get("complaint_themes") or [],
        "status_events": status_events,
        "official_patch_notes_source_type": official_source_type,
        "primary_official_source": record.get("primary_official_source") or record.get("official_url") or source_url,
        "fallback_official_sources": record.get("fallback_official_sources") or [],
        "official_patch_notes_capture_status": _capture_status(record, body=useful_body),
        "official_patch_notes_source_url": record.get("official_patch_notes_source_url") or source_url,
        "official_note_status": official_note_status,
        "official_note_label": official_note_label,
        "official_source_type": official_source_type,
        "official_source_classification_note": record.get("official_source_classification_note") or "Official vendor sources are classified before display so feature summaries, release notes, fixed issues, and vendor announcements are not mislabeled.",
        "official_sources": official_sources,
        "official_source_attempts": [_official_source_attempt(record, checked_at, body=useful_body, checksums_body=checksums_body)],
        "official_patch_notes_body": useful_body,
        "official_checksums_body": checksums_body,
        "official_checksums_capture_status": "captured-from-official-release" if checksums_body else "not-present",
    }


def refresh_existing_record(path: Path, record: dict[str, Any]) -> tuple[Path, str]:
    existing, body_text = _front_matter(path)
    if not existing:
        return path, "skipped-unreadable"

    checked_at = str(record.get("source_last_checked") or record.get("_source_checked_at") or utc_now())
    incoming_body = _useful_body(record.get("body"))
    incoming_checksums = str(record.get("checksums_body") or "").strip()
    incoming_source_url = str(record.get("source_url") or record.get("official_patch_notes_source_url") or "").strip()
    incoming_download_url = str(record.get("download_url") or "").strip()
    original = dict(existing)
    material_changed = False

    existing["source_last_checked"] = checked_at
    existing["official_body_last_checked"] = checked_at
    existing.setdefault("primary_official_source", record.get("primary_official_source") or record.get("official_url") or incoming_source_url)
    existing.setdefault("fallback_official_sources", record.get("fallback_official_sources") or [])

    attempts = existing.get("official_source_attempts")
    if not isinstance(attempts, list):
        attempts = []
    attempts.append(_official_source_attempt(record, checked_at, body=incoming_body, checksums_body=incoming_checksums))
    existing["official_source_attempts"] = attempts[-5:]

    if incoming_source_url:
        if not existing.get("official_patch_notes_source_url"):
            existing["official_patch_notes_source_url"] = incoming_source_url
            material_changed = True
        if not existing.get("update_source_url"):
            existing["update_source_url"] = incoming_source_url
            material_changed = True
    if incoming_download_url and not existing.get("update_download_url"):
        existing["update_download_url"] = incoming_download_url
        material_changed = True

    if incoming_body:
        if str(existing.get("official_patch_notes_body") or "").strip() != incoming_body:
            existing["official_patch_notes_body"] = incoming_body
            existing["official_patch_notes_capture_status"] = _capture_status(record, body=incoming_body)
            material_changed = True
        elif str(existing.get("official_patch_notes_capture_status") or "").strip() in {
            "",
            "partial-existing-record",
            "official-source-linked-body-not-captured",
            "official-source-parser-failed",
            "manual-watch-required",
        }:
            existing["official_patch_notes_capture_status"] = _capture_status(record, body=incoming_body)
            material_changed = True
    else:
        status = str(record.get("capture_status") or existing.get("official_patch_notes_capture_status") or "").strip()
        if status in {"", "partial-existing-record"}:
            existing["official_patch_notes_capture_status"] = "official-source-linked-body-not-captured"
            material_changed = True

    if incoming_checksums and str(existing.get("official_checksums_body") or "").strip() != incoming_checksums:
        existing["official_checksums_body"] = incoming_checksums
        existing["official_checksums_capture_status"] = "captured-from-official-release"
        material_changed = True

    if material_changed:
        existing["record_last_updated"] = checked_at

    if existing == original:
        return path, "unchanged"

    path.write_text(_dump_record(existing, body_text), encoding="utf-8")
    return path, "refreshed" if material_changed else "freshness-updated"


def write_record(output_dir: Path, record: dict[str, Any], overwrite_existing: bool = False) -> tuple[Path, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = _matching_existing_path(output_dir, record) or output_path(output_dir, record)
    if path.exists() and not overwrite_existing:
        return refresh_existing_record(path, record)
    front = build_front_matter(record)
    path.write_text(_dump_record(front), encoding="utf-8")
    return path, "created"
