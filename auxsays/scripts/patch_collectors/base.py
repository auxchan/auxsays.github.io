"""Shared evidence collection helpers for AUXSAYS patch intelligence.

The product collectors are intentionally small. This module owns the durable
evidence schema, generated-record discovery, duplicate detection, and the
deterministic gates that must pass before a row can count.
"""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
METHOD_HEALTH_PATH = ROOT / "_data" / "evidence_method_health.yml"
GENERATED_DIR = ROOT / "updates" / "generated"

EVIDENCE_FIELDS = (
    "id",
    "product_id",
    "update_version",
    "source_type",
    "source_name",
    "source_url",
    "archive_url",
    "parent_title",
    "report_title",
    "report_text_excerpt",
    "captured_at",
    "source_date",
    "target_release_date",
    "source_date_pass",
    "patch_version_matched",
    "matched_version",
    "match_basis",
    "counted",
    "exclusion_reason",
    "issue_theme",
    "workflow_area",
    "platform",
    "severity",
    "sentiment",
    "source_weight",
)

METHOD_HEALTH_FIELDS = (
    "product_id",
    "update_version",
    "method_id",
    "source_type",
    "status",
    "candidates_found",
    "accepted_reports",
    "rejected_reports",
    "blocked_reason",
    "last_run",
    "notes",
)

VALID_METHOD_HEALTH_STATUSES = {
    "success",
    "partial",
    "no_results",
    "blocked",
    "stale",
    "broken",
    "low_confidence",
    "disabled",
    "manual_review_needed",
}

ISSUE_TERMS = (
    "crash",
    "crashes",
    "crashed",
    "freeze",
    "freezes",
    "frozen",
    "hang",
    "hangs",
    "failed",
    "failure",
    "bug",
    "broken",
    "corrupt",
    "corrupted",
    "corruption",
    "regression",
    "slow",
    "lag",
    "performance",
    "install",
    "won't open",
    "does not open",
    "can't open",
    "cannot open",
    "decode",
    "render",
    "export",
    "compatibility",
    "plugin",
    "workflow",
)

NON_REPORT_TERMS = (
    "release notes",
    "changelog",
    "what's new",
    "whats new",
    "announcement",
    "download",
    "version history",
    "new features",
)


@dataclass(frozen=True)
class PatchRecord:
    product_id: str
    update_version: str
    path: Path
    update_published_at: str
    update_status: str
    update_product: str


@dataclass(frozen=True)
class CollectorContext:
    write: bool
    since: str | None
    max_pages: int
    target_versions: set[str] | None = None


class ProductCollector:
    product_id: str

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        raise NotImplementedError


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:96].strip("-")


def excerpt(text: str, width: int = 280) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return textwrap.shorten(text, width=width, placeholder="...") if text else ""


def parse_iso_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip().strip("'\"")
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def date_part(value: Any) -> str:
    parsed = parse_iso_date(value)
    return parsed.date().isoformat() if parsed else ""


def load_front_matter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    data = yaml.safe_load(parts[1]) or {}
    return (data if isinstance(data, dict) else {}, parts[2])


def write_front_matter_and_body(path: Path, data: dict[str, Any], body: str) -> None:
    front = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000).strip()
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")


def generated_records(product_id: str, target_versions: set[str] | None = None, *, include_archived: bool = False) -> list[PatchRecord]:
    records: list[PatchRecord] = []
    for path in sorted(GENERATED_DIR.glob("*.md")):
        data, _body = load_front_matter_and_body(path)
        if data.get("update_entry") is not True:
            continue
        if str(data.get("product_id") or "").strip() != product_id:
            continue
        status = str(data.get("update_status") or "").strip()
        if status == "archived" and not include_archived:
            continue
        version = str(data.get("update_version") or "").strip()
        if not version:
            continue
        if target_versions and version not in target_versions:
            continue
        records.append(PatchRecord(
            product_id=product_id,
            update_version=version,
            path=path,
            update_published_at=str(data.get("update_published_at") or "").strip(),
            update_status=status,
            update_product=str(data.get("update_product") or product_id).strip(),
        ))
    return records


def load_evidence(path: Path = EVIDENCE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [normalize_evidence_row(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        evidence = payload.get("evidence") or []
        if not isinstance(evidence, list):
            raise ValueError(f"{path} field 'evidence' must be a list")
        return [normalize_evidence_row(item) for item in evidence if isinstance(item, dict)]
    raise ValueError(f"{path} must contain a YAML list or a mapping with an evidence list")


def write_evidence_file(rows: list[dict[str, Any]], path: Path = EVIDENCE_PATH) -> None:
    payload = {"schema_version": 1, "evidence": [normalize_evidence_row(row) for row in rows]}
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")


def normalize_method_health_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: row.get(field) for field in METHOD_HEALTH_FIELDS}
    for field in ("candidates_found", "accepted_reports", "rejected_reports"):
        normalized[field] = int(normalized.get(field) or 0)
    for field in METHOD_HEALTH_FIELDS:
        if field in {"candidates_found", "accepted_reports", "rejected_reports"}:
            continue
        if normalized[field] is None:
            normalized[field] = ""
        else:
            normalized[field] = str(normalized[field])
    if normalized["status"] not in VALID_METHOD_HEALTH_STATUSES:
        normalized["status"] = "broken"
    return normalized


def load_method_health(path: Path = METHOD_HEALTH_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [normalize_method_health_row(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        methods = payload.get("methods") or []
        if not isinstance(methods, list):
            raise ValueError(f"{path} field 'methods' must be a list")
        return [normalize_method_health_row(item) for item in methods if isinstance(item, dict)]
    raise ValueError(f"{path} must contain a YAML list or a mapping with a methods list")


def write_method_health_file(rows: list[dict[str, Any]], path: Path = METHOD_HEALTH_PATH) -> None:
    payload = {"schema_version": 1, "methods": [normalize_method_health_row(row) for row in rows]}
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")


def method_health_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("product_id") or "").strip(),
        str(row.get("update_version") or "").strip(),
        str(row.get("method_id") or "").strip(),
    )


def upsert_method_health(rows: list[dict[str, Any]], path: Path = METHOD_HEALTH_PATH) -> tuple[int, int, list[dict[str, Any]]]:
    existing = load_method_health(path)
    index = {method_health_key(row): idx for idx, row in enumerate(existing)}
    changed = 0
    for row in rows:
        normalized = normalize_method_health_row(row)
        key = method_health_key(normalized)
        if not all(key):
            continue
        current_idx = index.get(key)
        if current_idx is None:
            index[key] = len(existing)
            existing.append(normalized)
            changed += 1
        elif existing[current_idx] != normalized:
            existing[current_idx] = normalized
            changed += 1
    if changed:
        write_method_health_file(existing, path)
    return changed, len(existing), existing


def method_health_row(
    *,
    product_id: str,
    update_version: str,
    method_id: str,
    source_type: str,
    status: str,
    candidates_found: int,
    accepted_reports: int,
    rejected_reports: int,
    blocked_reason: str | None,
    last_run: str,
    notes: str,
) -> dict[str, Any]:
    return normalize_method_health_row({
        "product_id": product_id,
        "update_version": update_version,
        "method_id": method_id,
        "source_type": source_type,
        "status": status,
        "candidates_found": candidates_found,
        "accepted_reports": accepted_reports,
        "rejected_reports": rejected_reports,
        "blocked_reason": blocked_reason or "",
        "last_run": last_run,
        "notes": notes,
    })


def normalize_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: row.get(field) for field in EVIDENCE_FIELDS}
    normalized["source_weight"] = int(normalized.get("source_weight") or 1)
    normalized["counted"] = bool(normalized.get("counted"))
    normalized["patch_version_matched"] = bool(normalized.get("patch_version_matched"))
    if normalized.get("source_date_pass") not in (True, False, None):
        normalized["source_date_pass"] = bool(normalized.get("source_date_pass"))
    for field in EVIDENCE_FIELDS:
        if field in {"source_weight", "counted", "patch_version_matched", "source_date_pass"}:
            continue
        if normalized[field] is not None:
            normalized[field] = str(normalized[field])
    return normalized


def evidence_key(row: dict[str, Any], key_field: str) -> tuple[str, str, str]:
    return (
        str(row.get("product_id") or "").strip(),
        str(row.get("update_version") or "").strip(),
        normalize_url(str(row.get(key_field) or "")),
    )


def append_evidence_rows(rows: list[dict[str, Any]], path: Path = EVIDENCE_PATH) -> tuple[int, int, list[dict[str, Any]]]:
    existing = load_evidence(path)
    seen_ids = {evidence_key(row, "id") for row in existing if row.get("id")}
    seen_urls = {evidence_key(row, "source_url") for row in existing if row.get("source_url")}
    added = 0
    for row in rows:
        normalized = normalize_evidence_row(row)
        id_key = evidence_key(normalized, "id")
        url_key = evidence_key(normalized, "source_url")
        if id_key in seen_ids or url_key in seen_urls:
            continue
        existing.append(normalized)
        seen_ids.add(id_key)
        seen_urls.add(url_key)
        added += 1
    if added:
        write_evidence_file(existing, path)
    return added, len(existing), existing


def counted_rows(rows: Iterable[dict[str, Any]], product_id: str, update_version: str) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("product_id") or "").strip() == product_id
        and str(row.get("update_version") or "").strip() == update_version
        and row.get("counted") is not False
    ]


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def exact_version_match(text: str, version: str, aliases: Iterable[str] = ()) -> tuple[bool, str, str]:
    for candidate in [version, *aliases]:
        candidate = str(candidate or "").strip()
        if not candidate:
            continue
        pattern = re.compile(rf"(?<![A-Za-z0-9.]){re.escape(candidate)}(?![A-Za-z0-9.])", flags=re.I)
        if pattern.search(text or ""):
            return True, candidate, "exact_version_text" if candidate == version else "exact_version_alias"
    return False, "", ""


def source_url_is_specific(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parse_qs(parsed.query)
    if "reddit.com" in host:
        return "/comments/" in path and len(path.strip("/").split("/")) >= 4
    if "github.com" in host:
        return bool(re.search(r"/issues/\d+/?$", path))
    if "forum.blackmagicdesign.com" in host:
        return path.endswith("viewtopic.php") and bool(query.get("t"))
    if "creativecow.net" in host:
        return bool(re.fullmatch(r"/forums/thread/[^/]+/?", path))
    return not path.rstrip("/").endswith(("/search", "/forums", "/forum")) and path.strip("/") not in {"", "forums", "forum"}


def source_date_passes(source_date: str, target_release_date: str) -> bool | None:
    if not target_release_date:
        return None
    if not source_date:
        return False
    source = parse_iso_date(source_date)
    target = parse_iso_date(target_release_date)
    if not source or not target:
        return False
    return source.date() >= target.date()


def text_describes_issue(text: str) -> bool:
    lowered = (text or "").lower()
    if not any(term in lowered for term in ISSUE_TERMS):
        return False
    if any(term in lowered for term in NON_REPORT_TERMS) and not any(term in lowered for term in ("crash", "bug", "broken", "failed", "regression")):
        return False
    return True


def make_evidence_row(
    *,
    product_id: str,
    update_version: str,
    source_type: str,
    source_name: str,
    source_url: str,
    parent_title: str,
    report_title: str,
    report_text: str,
    captured_at: str,
    source_date: str,
    target_release_date: str,
    patch_version_matched: bool,
    matched_version: str,
    match_basis: str,
    counted: bool,
    exclusion_reason: str | None,
    issue_theme: str,
    workflow_area: str,
    platform: str,
    severity: str,
    sentiment: str,
    row_id: str | None = None,
) -> dict[str, Any]:
    return normalize_evidence_row({
        "id": row_id or f"{product_id}-{slug(update_version)}-{slug(source_type)}-{slug(source_url)}",
        "product_id": product_id,
        "update_version": update_version,
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "parent_title": parent_title,
        "report_title": report_title,
        "report_text_excerpt": excerpt(report_text),
        "captured_at": captured_at,
        "source_date": source_date,
        "target_release_date": target_release_date,
        "source_date_pass": source_date_passes(source_date, target_release_date),
        "patch_version_matched": patch_version_matched,
        "matched_version": matched_version,
        "match_basis": match_basis,
        "counted": counted,
        "exclusion_reason": exclusion_reason,
        "issue_theme": issue_theme,
        "workflow_area": workflow_area,
        "platform": platform,
        "severity": severity,
        "sentiment": sentiment,
        "source_weight": 1,
    })


def apply_acceptance_gates(row: dict[str, Any], *, report_text: str) -> dict[str, Any]:
    gated = dict(row)
    reason: str | None = None
    if not gated.get("patch_version_matched"):
        reason = "missing_exact_patch_version_match"
    elif not source_url_is_specific(str(gated.get("source_url") or "")):
        reason = "source_url_not_specific_report"
    elif gated.get("source_date_pass") is False:
        reason = "source_date_before_or_unverified_against_release"
    elif not text_describes_issue(report_text):
        reason = "not_a_real_issue_report"

    if reason:
        gated["counted"] = False
        gated["exclusion_reason"] = reason
    else:
        gated["counted"] = True
        gated["exclusion_reason"] = None
    gated["source_weight"] = 1
    return normalize_evidence_row(gated)
