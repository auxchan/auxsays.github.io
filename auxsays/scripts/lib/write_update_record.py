"""Write Jekyll Markdown update records from normalized official source data."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

from .normalize import slugify, utc_now, summarize

DEFAULT_CONSENSUS = "Insufficient data"

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
    body = record.get("body") or "No official release-note body was captured."
    summary = record.get("summary") or summarize(body)
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
        "update_status": "current",
        "update_feed_title": f"{software} {version}",
        "update_detail_title": f"{software} {version}",
        "update_consensus_label": DEFAULT_CONSENSUS,
        "update_report_count": 0,
        "update_consensus_confidence": "Low",
        "quick_verdict": f"{software} {version} has an official AUXSAYS record. Community consensus is deferred until official ingestion is stable.",
        "official_summary": record.get("official_summary") or f"{company} published {software} {version}.",
        "release_summary": summary,
        "consensus_report": "Consensus collection is deferred. This page currently reflects official-source ingestion only.",
        "complaint_themes": [],
        "status_events": [
            {"at": published, "label": "Published", "note": "Official source entry detected."},
            {"at": utc_now(), "label": DEFAULT_CONSENSUS, "note": "AUXSAYS official-ingestion record initialized."},
        ],
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
