#!/usr/bin/env python3
"""Promote local Playwright candidate captures into structured evidence.

This bridge is deterministic: it reads local capture JSONL, verifies exact
Premiere Pro version/product/issue gates, and writes accepted rows through the
shared AUXSAYS evidence helpers only in explicit --write mode.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PY_YAML_AVAILABLE = True
try:
    import yaml as _yaml  # noqa: F401
except ModuleNotFoundError:
    PY_YAML_AVAILABLE = False

    class _ReadOnlyYamlFallback:
        @staticmethod
        def safe_load(text: str) -> Any:
            return _simple_yaml_load(text)

        @staticmethod
        def safe_dump(*_args: Any, **_kwargs: Any) -> str:
            raise RuntimeError("PyYAML is required for --write mode")

    sys.modules["yaml"] = _ReadOnlyYamlFallback()

from patch_collectors.base import (
    EVIDENCE_PATH,
    METHOD_HEALTH_PATH,
    append_evidence_rows,
    date_part,
    exact_version_match,
    generated_records,
    load_evidence,
    make_evidence_row,
    method_health_row,
    slug,
    source_date_passes,
    upsert_method_health,
    utc_now,
)
from patch_collectors import adobe_premiere as premiere

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = Path(r"D:\AUXSAYS_CAPTURE_PORTABLE\app\outbox\captured-pages.jsonl")
DEFAULT_PRODUCT_ID = "adobe-premiere-pro"
CAPTURE_METHOD = "local_playwright"
METHOD_ID = "local_playwright_capture_promotion"

VERSION_RE = re.compile(r"(?<![A-Za-z0-9.-])(\d+\.\d+(?:\.\d+)?)(?![A-Za-z0-9.])")
RELATIVE_DATE_RE = re.compile(
    r"\b(?:\d+\s+(?:minute|hour|day|week|month|year)s?(?:,\s*\d+\s+(?:minute|hour|day|week|month|year)s?)?\s+ago|yesterday|today)\b",
    re.I,
)
ABSOLUTE_DATE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s+20\d{2}\b",
    re.I,
)
CARD_CATEGORIES = (
    "Bug Reports",
    "Discussions",
    "Questions",
    "Ideas",
    "Feature Requests",
    "Community",
)
ADOBE_LISTING_HOST = "community.adobe.com"
CREATIVE_COW_HOST = "creativecow.net"


@dataclass
class PromotionResult:
    rows_read: int
    pages_parsed: int
    listing_cards_found: int
    accepted: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    unmatched_versions: set[str]
    generated_record_versions: set[str]
    generated_records_updated: list[str]
    evidence_rows_added: int = 0
    method_health_changed: int = 0

    @property
    def accepted_versions_with_records(self) -> set[str]:
        return {str(row.get("update_version") or "") for row in self.accepted} & self.generated_record_versions

    def summary(self, *, write: bool, output_files: Iterable[Path]) -> dict[str, Any]:
        return {
            "mode": "write" if write else "dry-run",
            "rows_read": self.rows_read,
            "pages_parsed": self.pages_parsed,
            "listing_cards_found": self.listing_cards_found,
            "accepted_count": len(self.accepted),
            "rejected_count": len(self.rejected),
            "unmatched_version_count": len(self.unmatched_versions),
            "unmatched_versions": sorted(self.unmatched_versions),
            "generated_records_updated": bool(self.generated_records_updated),
            "generated_record_versions": sorted(self.generated_record_versions),
            "evidence_rows_added": self.evidence_rows_added,
            "method_health_changed": self.method_health_changed,
            "output_files_that_would_change": [str(path) for path in output_files],
            "accepted": compact_rows(self.accepted),
            "rejection_reasons": dict(Counter(str(row.get("exclusion_reason") or "unknown") for row in self.rejected)),
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.product_id != DEFAULT_PRODUCT_ID:
        raise SystemExit("Only --product-id adobe-premiere-pro is supported in this MVP bridge.")
    if args.write and args.dry_run:
        raise SystemExit("Use either --dry-run or --write, not both.")
    write = bool(args.write)
    if write and not PY_YAML_AVAILABLE:
        raise SystemExit("PyYAML is required for --write mode.")
    result = promote(
        input_path=Path(args.input),
        product_id=args.product_id,
        max_rows=args.max_rows,
        write=write,
    )
    output_files = planned_output_files(result, write=write)
    print(json.dumps(result.summary(write=write, output_files=output_files), indent=2, sort_keys=True))
    if result.unmatched_versions:
        for version in sorted(result.unmatched_versions):
            print(
                f"accepted evidence exists for {args.product_id} {version} "
                "but no generated official patch record was found.",
                file=sys.stderr,
            )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--product-id", default=DEFAULT_PRODUCT_ID)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--max-rows", type=int, default=100)
    return parser.parse_args(argv)


def _simple_yaml_load(text: str) -> Any:
    """Small read-only YAML subset for dry-run environments without PyYAML."""
    lines = [line.rstrip("\n") for line in str(text or "").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    root: dict[str, Any] = {}
    current_list: list[dict[str, Any]] | None = None
    current_item: dict[str, Any] | None = None
    saw_list = False
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not raw.startswith(" ") and ":" in stripped and not stripped.startswith("- "):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                current_list = []
                root[key] = current_list
                current_item = None
                saw_list = True
            else:
                root[key] = _simple_yaml_scalar(value)
                current_list = None
                current_item = None
            continue
        if stripped.startswith("- ") and current_list is not None:
            current_item = {}
            current_list.append(current_item)
            saw_list = True
            remainder = stripped[2:].strip()
            if ":" in remainder:
                key, value = remainder.split(":", 1)
                current_item[key.strip()] = _simple_yaml_scalar(value.strip())
            continue
        if current_item is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_item[key.strip()] = _simple_yaml_scalar(value.strip())
    if saw_list or root:
        return root
    return {}


def _simple_yaml_scalar(value: str) -> Any:
    text = value.strip()
    if text in {"", "''", '""'}:
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if (text.startswith("'") and text.endswith("'")) or (text.startswith('"') and text.endswith('"')):
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        return text


def promote(
    *,
    input_path: Path,
    product_id: str,
    max_rows: int,
    write: bool,
    evidence_path: Path = EVIDENCE_PATH,
    method_health_path: Path = METHOD_HEALTH_PATH,
    writeback_func: Any | None = None,
) -> PromotionResult:
    capture_rows = read_capture_jsonl(input_path, max_rows=max_rows)
    record_by_version = {record.update_version: record for record in generated_records(product_id, include_archived=True)}
    existing = load_evidence(evidence_path)
    existing_ids = {str(row.get("id") or "").strip() for row in existing}
    existing_urls = {
        evidence_url_key(row)
        for row in existing
        if str(row.get("match_basis") or "") != "embedded_listing_report_card"
    }

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    listing_cards_found = 0

    for capture in capture_rows:
        if str(capture.get("capture_status") or "") != "success":
            rejected.append(rejection_from_capture(capture, "capture_status_not_success"))
            continue
        page_candidates = candidates_from_capture(capture, product_id=product_id)
        listing_cards_found += sum(1 for candidate in page_candidates if candidate.get("match_basis") == "embedded_listing_report_card")
        if not page_candidates:
            rejected.append(rejection_from_capture(capture, "no_discrete_report_card_or_detail_report"))
            continue
        for candidate in page_candidates:
            row = evaluate_candidate(candidate, record_by_version)
            if duplicate_row(row, existing_ids, existing_urls, accepted):
                row["counted"] = False
                row["exclusion_reason"] = "duplicate_existing_evidence"
            if row.get("counted") is True:
                accepted.append(row)
            else:
                rejected.append(row)

    accepted_versions = {str(row.get("update_version") or "") for row in accepted}
    generated_versions = set(record_by_version)
    unmatched_versions = accepted_versions - generated_versions
    updated_versions: list[str] = []
    evidence_rows_added = 0
    method_health_changed = 0

    if write:
        evidence_rows_added, _total, _rows = append_evidence_rows(accepted, path=evidence_path)
        health_rows = build_method_health_rows(
            product_id=product_id,
            accepted=accepted,
            rejected=rejected,
            generated_versions=generated_versions,
        )
        method_health_changed, _health_total, _health = upsert_method_health(health_rows, path=method_health_path)
        updater = writeback_func or premiere.apply_consensus_writeback
        for version in sorted(accepted_versions & generated_versions):
            if updater(version):
                updated_versions.append(version)

    return PromotionResult(
        rows_read=len(capture_rows),
        pages_parsed=sum(1 for row in capture_rows if row.get("capture_status") == "success"),
        listing_cards_found=listing_cards_found,
        accepted=accepted,
        rejected=rejected,
        unmatched_versions=unmatched_versions,
        generated_record_versions=generated_versions,
        generated_records_updated=updated_versions,
        evidence_rows_added=evidence_rows_added,
        method_health_changed=method_health_changed,
    )


def read_capture_jsonl(path: Path, *, max_rows: int) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"capture JSONL not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if len(rows) >= max_rows:
                break
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def candidates_from_capture(capture: dict[str, Any], *, product_id: str) -> list[dict[str, Any]]:
    source_url = canonical_url(str(capture.get("source_url") or ""))
    source_name = str(capture.get("source_name") or "").strip()
    visible_text = str(capture.get("visible_text") or "").replace("\u00a0", " ").strip()
    page_title = normalize_text(capture.get("page_title"))
    captured_at = str(capture.get("captured_at") or "").strip()
    product_hint = str(capture.get("product_hint") or "").strip()
    text = "\n".join(item for item in (page_title, visible_text) if item)

    if product_hint and product_hint != product_id:
        return []
    if source_is_specific_detail(source_url):
        return [detail_candidate(capture, source_url, source_name, page_title, text)]
    return listing_card_candidates(capture, source_url, source_name, text, captured_at)


def detail_candidate(
    capture: dict[str, Any],
    source_url: str,
    source_name: str,
    page_title: str,
    text: str,
) -> dict[str, Any]:
    source_type = premiere.SOURCE_TYPE if "community.adobe.com" in source_url else premiere.CREATIVE_COW_SOURCE_TYPE
    version = best_version(text)
    return {
        "candidate_kind": "detail",
        "source_type": source_type,
        "source_name": source_name or ("Adobe Community" if source_type == premiere.SOURCE_TYPE else "Creative COW"),
        "source_url": source_url,
        "parent_title": page_title or first_nonempty_line(text),
        "report_title": page_title or first_nonempty_line(text),
        "report_text": text,
        "source_date": premiere.extract_source_date(text),
        "source_date_text": relative_or_absolute_date_text(text),
        "captured_at": str(capture.get("captured_at") or ""),
        "update_version": version,
        "match_basis": "detail_page",
    }


def listing_card_candidates(
    capture: dict[str, Any],
    source_url: str,
    source_name: str,
    text: str,
    captured_at: str,
) -> list[dict[str, Any]]:
    lines = split_lines(text)
    if not lines:
        return []

    candidates: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    consumed_indices: set[int] = set()
    for index, line in enumerate(lines):
        if index in consumed_indices:
            continue
        if not VERSION_RE.search(line):
            continue
        host = urllib.parse.urlsplit(source_url).netloc.lower().removeprefix("www.")
        if host == CREATIVE_COW_HOST:
            window_lines = context_window(lines, index, before=2, after=4)
        else:
            window_lines = context_window(lines, index, before=7, after=9)
        window = " ".join(window_lines)
        category = nearest_category(lines, index)
        date_text = nearest_date_text(lines, index)
        title = line
        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        source_type = "adobe_community_listing_card" if host == ADOBE_LISTING_HOST else "creativecow_listing_card"
        candidates.append({
            "candidate_kind": "listing_card",
            "product_hint": str(capture.get("product_hint") or ""),
            "source_type": source_type,
            "source_name": source_name,
            "source_url": source_url,
            "parent_title": normalize_text(capture.get("page_title")),
            "report_title": title,
            "report_text": window,
            "source_date": "",
            "source_date_text": date_text,
            "captured_at": captured_at,
            "update_version": best_version(window),
            "match_basis": "embedded_listing_report_card",
            "listing_card_title": title,
            "listing_card_category": category,
            "listing_card_date_text": date_text,
        })
        consumed_indices.update(range(max(0, index - 3), min(len(lines), index + 7)))
    return candidates


def evaluate_candidate(candidate: dict[str, Any], record_by_version: dict[str, Any]) -> dict[str, Any]:
    version = str(candidate.get("update_version") or "").strip()
    record = record_by_version.get(version)
    target_release_date = date_part(record.update_published_at) if record else ""
    report_text = " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ])
    matched, matched_version, basis = premiere.premiere_version_match(report_text, version) if version else (False, "", "")
    if candidate.get("match_basis") == "embedded_listing_report_card" and matched:
        basis = "embedded_listing_report_card"
    theme, workflow_area, platform, severity, sentiment = premiere.classify(report_text)

    row = make_evidence_row(
        product_id=DEFAULT_PRODUCT_ID,
        update_version=version,
        source_type=str(candidate.get("source_type") or ""),
        source_name=str(candidate.get("source_name") or ""),
        source_url=str(candidate.get("source_url") or ""),
        parent_title=str(candidate.get("parent_title") or ""),
        report_title=str(candidate.get("report_title") or ""),
        report_text=str(candidate.get("report_text") or ""),
        captured_at=str(candidate.get("captured_at") or utc_now()),
        source_date=str(candidate.get("source_date") or ""),
        target_release_date=target_release_date,
        patch_version_matched=matched,
        matched_version=matched_version,
        match_basis=basis,
        counted=False,
        exclusion_reason=None,
        issue_theme=theme,
        workflow_area=workflow_area,
        platform=platform,
        severity=severity,
        sentiment=sentiment,
        row_id=row_id_for_candidate(candidate, version),
    )
    row["capture_method"] = CAPTURE_METHOD
    row["source_date_text"] = str(candidate.get("source_date_text") or "")
    row["listing_card_title"] = str(candidate.get("listing_card_title") or "")
    row["listing_card_category"] = str(candidate.get("listing_card_category") or "")
    row["listing_card_date_text"] = str(candidate.get("listing_card_date_text") or "")

    reason = exclusion_reason(row, candidate, report_text)
    if reason:
        row["counted"] = False
        row["exclusion_reason"] = reason
    else:
        row["counted"] = True
        row["exclusion_reason"] = None
        row["source_weight"] = 1
    return row


def exclusion_reason(row: dict[str, Any], candidate: dict[str, Any], report_text: str) -> str | None:
    if not row.get("update_version"):
        return "missing_exact_patch_version_match"
    if not row.get("patch_version_matched"):
        return "missing_exact_patch_version_match"
    if not premiere.PREMIERE_PRODUCT_RE.search(report_text) and str(candidate.get("product_hint") or "") != DEFAULT_PRODUCT_ID:
        return "missing_premiere_product_context"
    if premiere.PRE_RELEASE_RE.search(report_text):
        return "prerelease_context_for_stable_record"
    if not premiere.premiere_strong_issue_match(report_text):
        return "not_a_real_issue_report"
    if feature_request_or_how_to_only(candidate, report_text):
        return "not_a_real_issue_report"

    if candidate.get("match_basis") == "embedded_listing_report_card":
        if not str(row.get("source_name") or "").strip():
            return "missing_source_context"
        if not str(row.get("source_url") or "").strip():
            return "missing_source_url"
        if not str(row.get("captured_at") or "").strip():
            return "missing_captured_at"
        if not str(row.get("listing_card_title") or row.get("report_title") or "").strip():
            return "missing_listing_card_title"
        if not str(row.get("report_text_excerpt") or "").strip():
            return "insufficient_concrete_issue_detail"
        if not str(row.get("listing_card_date_text") or row.get("source_date") or row.get("source_date_text") or "").strip():
            return "missing_listing_card_date"
        if not listing_card_has_enough_issue_detail(candidate):
            return "insufficient_concrete_issue_detail"
        row["source_date_pass"] = row.get("source_date_pass") if row.get("source_date") else True
        return None

    if not source_is_specific_detail(str(row.get("source_url") or "")):
        return "source_url_not_specific_report"
    source_date_pass = source_date_passes(str(row.get("source_date") or ""), str(row.get("target_release_date") or ""))
    if source_date_pass is False:
        return "source_date_before_or_unverified_against_release"
    return None


def feature_request_or_how_to_only(candidate: dict[str, Any], report_text: str) -> bool:
    category = str(candidate.get("listing_card_category") or "").lower()
    lowered = report_text.lower()
    if "feature" in category or "idea" in category:
        return True
    if "question" in category and not re.search(r"\b(?:regression|after\s+updat|since\s+updat|freez|crash|broken|bug)\b", lowered):
        return True
    return False


def listing_card_has_enough_issue_detail(candidate: dict[str, Any]) -> bool:
    title = str(candidate.get("listing_card_title") or candidate.get("report_title") or "")
    text = str(candidate.get("report_text") or "")
    if len(text) < len(title) + 20:
        return False
    if not premiere.STRONG_ISSUE_RE.search(text):
        return False
    return True


def duplicate_row(
    row: dict[str, Any],
    existing_ids: set[str],
    existing_urls: set[tuple[str, str, str]],
    accepted: list[dict[str, Any]],
) -> bool:
    row_id = str(row.get("id") or "").strip()
    if row_id and row_id in existing_ids:
        return True
    accepted_ids = {str(item.get("id") or "").strip() for item in accepted}
    if row_id and row_id in accepted_ids:
        return True
    if row.get("match_basis") == "embedded_listing_report_card":
        return False
    key = evidence_url_key(row)
    return key in existing_urls or key in {evidence_url_key(item) for item in accepted}


def build_method_health_rows(
    *,
    product_id: str,
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    generated_versions: set[str],
) -> list[dict[str, Any]]:
    versions = sorted({str(row.get("update_version") or "") for row in [*accepted, *rejected] if row.get("update_version")})
    if not versions:
        versions = [""]
    rows: list[dict[str, Any]] = []
    for version in versions:
        accepted_for_version = [row for row in accepted if str(row.get("update_version") or "") == version]
        rejected_for_version = [row for row in rejected if str(row.get("update_version") or "") == version]
        if accepted_for_version and rejected_for_version:
            status = "partial"
        elif accepted_for_version:
            status = "success" if version in generated_versions else "manual_review_needed"
        elif rejected_for_version:
            status = "no_results"
        else:
            status = "no_results"
        reasons = Counter(str(row.get("exclusion_reason") or "unknown") for row in rejected_for_version)
        notes = "Promotes local Playwright candidate captures through deterministic Premiere Pro evidence gates."
        if version and version not in generated_versions and accepted_for_version:
            notes += " Accepted evidence is pending a matching official generated record."
        if reasons:
            notes += " Rejected candidates: " + ", ".join(f"{reason}={count}" for reason, count in sorted(reasons.items())) + "."
        rows.append(method_health_row(
            product_id=product_id,
            update_version=version,
            method_id=METHOD_ID,
            source_type="local_playwright_capture",
            status=status,
            candidates_found=len(accepted_for_version) + len(rejected_for_version),
            accepted_reports=len(accepted_for_version),
            rejected_reports=len(rejected_for_version),
            blocked_reason="",
            last_run=utc_now(),
            notes=notes,
        ))
    return rows


def planned_output_files(result: PromotionResult, *, write: bool) -> list[Path]:
    if write:
        files = [EVIDENCE_PATH, METHOD_HEALTH_PATH]
        if result.generated_records_updated:
            files.append(ROOT / "updates" / "generated")
        return files
    files: list[Path] = []
    if result.accepted:
        files.extend([EVIDENCE_PATH, METHOD_HEALTH_PATH])
        if result.accepted_versions_with_records:
            files.append(ROOT / "updates" / "generated")
    return files

def rejection_from_capture(capture: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "id": "",
        "product_id": str(capture.get("product_hint") or DEFAULT_PRODUCT_ID),
        "update_version": str(capture.get("version_hint") or ""),
        "source_type": "local_playwright_capture",
        "source_name": str(capture.get("source_name") or ""),
        "source_url": str(capture.get("source_url") or ""),
        "parent_title": str(capture.get("page_title") or ""),
        "report_title": str(capture.get("page_title") or ""),
        "report_text_excerpt": "",
        "captured_at": str(capture.get("captured_at") or ""),
        "source_date": "",
        "target_release_date": "",
        "source_date_pass": None,
        "patch_version_matched": False,
        "matched_version": "",
        "match_basis": "",
        "counted": False,
        "exclusion_reason": reason,
        "issue_theme": "",
        "workflow_area": "",
        "platform": "unknown",
        "severity": "medium",
        "sentiment": "moderate",
        "source_weight": 1,
        "capture_method": CAPTURE_METHOD,
    }


def compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": row.get("id"),
            "product_id": row.get("product_id"),
            "update_version": row.get("update_version"),
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            "report_title": row.get("report_title"),
            "match_basis": row.get("match_basis"),
            "counted": row.get("counted"),
            "exclusion_reason": row.get("exclusion_reason"),
        }
        for row in rows
    ]


def row_id_for_candidate(candidate: dict[str, Any], version: str) -> str:
    basis = str(candidate.get("match_basis") or "")
    title = str(candidate.get("listing_card_title") or candidate.get("report_title") or "")
    if basis == "embedded_listing_report_card":
        return f"{DEFAULT_PRODUCT_ID}-{slug(version)}-{slug(basis)}-{slug(candidate.get('source_url') or '')}-{slug(title)}"
    return f"{DEFAULT_PRODUCT_ID}-{slug(version)}-{slug(candidate.get('source_type') or '')}-{slug(candidate.get('source_url') or '')}"


def evidence_url_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("product_id") or "").strip(),
        str(row.get("update_version") or "").strip(),
        canonical_url(str(row.get("source_url") or "")),
    )


def source_is_specific_detail(url: str) -> bool:
    return premiere.adobe_report_url_is_specific(url) or premiere.creativecow_thread_url_is_specific(url)


def best_version(text: str) -> str:
    versions = VERSION_RE.findall(text or "")
    if not versions:
        return ""
    # Prefer the most specific version mention, so 26.2.2 is not collapsed to 26.2.
    return sorted(set(versions), key=lambda item: (item.count("."), len(item)), reverse=True)[0]


def relative_or_absolute_date_text(text: str) -> str:
    match = RELATIVE_DATE_RE.search(text or "") or ABSOLUTE_DATE_RE.search(text or "")
    return match.group(0) if match else ""


def nearest_category(lines: list[str], index: int) -> str:
    for distance in range(0, 8):
        for pos in (index - distance, index + distance):
            if 0 <= pos < len(lines):
                clean = lines[pos].strip()
                for category in CARD_CATEGORIES:
                    if clean.lower() == category.lower():
                        return category
    return ""


def nearest_date_text(lines: list[str], index: int) -> str:
    for distance in range(0, 10):
        for pos in (index - distance, index + distance):
            if 0 <= pos < len(lines):
                found = relative_or_absolute_date_text(lines[pos])
                if found:
                    return found
    return ""


def context_window(lines: list[str], index: int, *, before: int, after: int) -> list[str]:
    start = max(0, index - before)
    end = min(len(lines), index + after + 1)
    return lines[start:end]


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in re.split(r"[\r\n]+", text or "") if line.strip()]


def first_nonempty_line(text: str) -> str:
    lines = split_lines(text)
    return lines[0] if lines else ""


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    if host == "www.creativecow.net":
        host = "creativecow.net"
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    query = parsed.query if host == ADOBE_LISTING_HOST and "page=" in parsed.query else ""
    return urllib.parse.urlunsplit((parsed.scheme.lower(), host, path, query, ""))


if __name__ == "__main__":
    raise SystemExit(main())
