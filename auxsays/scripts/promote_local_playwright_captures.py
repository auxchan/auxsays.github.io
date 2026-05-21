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
from datetime import datetime, timedelta, timezone
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
    parse_iso_date,
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
CURRENT_RELEASE_RE = re.compile(
    r"\b(?:latest|current|current\s+build|current\s+release|after\s+(?:the\s+)?(?:latest|current)\s+update|"
    r"after\s+updat(?:e|ing)|since\s+updat(?:e|ing)|premiere\s+pro\s+2026|premiere\s+2026)\b",
    re.I,
)
TITLE_SKIP_RE = re.compile(
    r"^(?:adobe premiere pro|open for voting|needs more info|participant|bug reports|questions|ideas|feature requests|discussions|community)$",
    re.I,
)


@dataclass(frozen=True)
class ReleaseWindow:
    product_id: str
    update_version: str
    start: datetime
    end: datetime | None
    channel: str
    record: Any


@dataclass(frozen=True)
class SourceDateResolution:
    resolved_at: str
    resolved_date: str
    date_text: str
    precision: str
    source: str


@dataclass(frozen=True)
class VersionMatch:
    update_version: str
    matched_version: str
    match_basis: str
    confidence: str
    target_release_date: str
    next_release_date: str
    source_date_resolved: str
    source_date_text: str
    source_date_pass: bool | None
    rejection_reason: str | None = None


@dataclass
class PromotionResult:
    rows_read: int
    pages_parsed: int
    listing_cards_found: int
    detail_pages_found: int
    candidates_found: int
    accepted: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    unmatched_versions: set[str]
    generated_record_versions: set[str]
    generated_records_updated: list[str]
    evidence_rows_added: int = 0
    method_health_changed: int = 0
    duplicate_existing_evidence: int = 0

    @property
    def accepted_versions_with_records(self) -> set[str]:
        return {str(row.get("update_version") or "") for row in self.accepted} & self.generated_record_versions

    def summary(self, *, write: bool, output_files: Iterable[Path]) -> dict[str, Any]:
        return {
            "mode": "write" if write else "dry-run",
            "rows_read": self.rows_read,
            "pages_parsed": self.pages_parsed,
            "listing_cards_found": self.listing_cards_found,
            "detail_pages_found": self.detail_pages_found,
            "candidates_found": self.candidates_found,
            "accepted_count": len(self.accepted),
            "rejected_count": len(self.rejected),
            "duplicate_existing_evidence": self.duplicate_existing_evidence,
            "unmatched_version_count": len(self.unmatched_versions),
            "unmatched_versions": sorted(self.unmatched_versions),
            "generated_records_updated": bool(self.generated_records_updated),
            "generated_record_versions": sorted(self.generated_record_versions),
            "evidence_rows_added": self.evidence_rows_added,
            "public_counted_reports": self.evidence_rows_added if write else len(self.accepted),
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
    explanation_paths = write_explanation_logs(result, Path(args.input))
    output_files = planned_output_files(result, write=write)
    summary = result.summary(write=write, output_files=output_files)
    summary["explanation_files"] = {key: str(value) for key, value in explanation_paths.items()}
    print(json.dumps(summary, indent=2, sort_keys=True))
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
    records = generated_records(product_id, include_archived=True)
    record_by_version = {record.update_version: record for record in records}
    release_windows = build_release_windows(records)
    existing = load_evidence(evidence_path)
    existing_ids = {str(row.get("id") or "").strip() for row in existing}
    existing_listing_keys = {listing_card_key(row) for row in existing if listing_card_key(row)}
    existing_urls = {
        evidence_url_key(row)
        for row in existing
        if str(row.get("match_basis") or "") != "embedded_listing_report_card"
    }

    accepted_pending: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    duplicate_existing: list[dict[str, Any]] = []
    listing_cards_found = 0
    detail_pages_found = 0
    candidates_found = 0

    for capture in capture_rows:
        if str(capture.get("capture_status") or "") != "success":
            rejected.append(rejection_from_capture(capture, "capture_status_not_success"))
            continue
        page_candidates = candidates_from_capture(capture, product_id=product_id)
        listing_cards_found += sum(1 for candidate in page_candidates if candidate.get("match_basis") == "embedded_listing_report_card")
        detail_pages_found += sum(1 for candidate in page_candidates if candidate.get("candidate_kind") == "detail")
        candidates_found += len(page_candidates)
        if not page_candidates:
            rejected.append(rejection_from_capture(capture, "no_discrete_report_card_or_detail_report"))
            continue
        for candidate in page_candidates:
            row = evaluate_candidate(candidate, record_by_version, release_windows)
            if row.get("counted") is True:
                accepted_pending.append(row)
            else:
                rejected.append(row)

    accepted_preferred, detail_duplicate_rejections = prefer_detail_evidence(accepted_pending)
    rejected.extend(detail_duplicate_rejections)
    for row in accepted_preferred:
        if duplicate_row(row, existing_ids, existing_listing_keys, existing_urls, accepted):
            row["counted"] = False
            row["exclusion_reason"] = "duplicate_existing_evidence"
            duplicate_existing.append(row)
            rejected.append(row)
        else:
            accepted.append(row)

    accepted_versions = {str(row.get("update_version") or "") for row in accepted}
    duplicate_existing_versions = {str(row.get("update_version") or "") for row in duplicate_existing}
    generated_versions = set(record_by_version)
    unmatched_versions = accepted_versions - generated_versions
    updated_versions: list[str] = []
    evidence_rows_added = 0
    method_health_changed = 0

    if write:
        evidence_rows_added, _total, _rows = append_evidence_rows(accepted, path=evidence_path)
        health_rows = build_method_health_rows(
            product_id=product_id,
            accepted=[*accepted, *duplicate_existing],
            rejected=rejected,
            generated_versions=generated_versions,
        )
        method_health_changed, _health_total, _health = upsert_method_health(health_rows, path=method_health_path)
        updater = writeback_func or premiere.apply_consensus_writeback
        for version in sorted((accepted_versions | duplicate_existing_versions) & generated_versions):
            if updater(version):
                updated_versions.append(version)

    return PromotionResult(
        rows_read=len(capture_rows),
        pages_parsed=sum(1 for row in capture_rows if row.get("capture_status") == "success"),
        listing_cards_found=listing_cards_found,
        detail_pages_found=detail_pages_found,
        candidates_found=candidates_found,
        accepted=accepted,
        rejected=rejected,
        unmatched_versions=unmatched_versions,
        generated_record_versions=generated_versions,
        generated_records_updated=updated_versions,
        evidence_rows_added=evidence_rows_added,
        method_health_changed=method_health_changed,
        duplicate_existing_evidence=len(duplicate_existing),
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


def build_release_windows(records: list[Any]) -> list[ReleaseWindow]:
    grouped: dict[tuple[str, str], list[tuple[Any, datetime]]] = defaultdict(list)
    for record in records:
        start = parse_iso_date(getattr(record, "update_published_at", ""))
        if not start:
            continue
        channel = release_channel_for_record(record)
        grouped[(getattr(record, "product_id", ""), channel)].append((record, start))

    windows: list[ReleaseWindow] = []
    for (product_id, channel), items in grouped.items():
        ordered = sorted(items, key=lambda item: (item[1], version_sort_key(str(getattr(item[0], "update_version", "")))))
        for index, (record, start) in enumerate(ordered):
            end = ordered[index + 1][1] if index + 1 < len(ordered) else None
            windows.append(ReleaseWindow(
                product_id=str(product_id),
                update_version=str(getattr(record, "update_version", "")),
                start=start,
                end=end,
                channel=channel,
                record=record,
            ))
    return windows


def release_channel_for_record(record: Any) -> str:
    text_parts = [
        str(getattr(record, "update_version", "")),
        str(getattr(record, "update_product", "")),
        str(getattr(record, "update_status", "")),
    ]
    path = getattr(record, "path", None)
    if path:
        try:
            from patch_collectors.base import load_front_matter_and_body

            data, _body = load_front_matter_and_body(Path(path))
            text_parts.extend(str(data.get(field) or "") for field in (
                "title",
                "update_type",
                "update_channel_label",
                "update_release_channel",
                "release_channel",
            ))
        except Exception:
            pass
    text = " ".join(text_parts)
    return "beta" if re.search(r"\b(?:beta|public\s+beta|preview|pre[- ]?release|rc)\b", text, flags=re.I) else "stable"


def release_channel_for_report(text: str) -> str:
    return "beta" if re.search(r"\b(?:public\s+beta|beta|pre[-\s]?release|prerelease|preview|release\s+candidate|rc)\b", text or "", flags=re.I) else "stable"


def version_sort_key(version: str) -> tuple[int, ...]:
    parts = []
    for part in str(version or "").split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def candidates_from_capture(capture: dict[str, Any], *, product_id: str) -> list[dict[str, Any]]:
    source_url = canonical_url(str(capture.get("detail_url") or capture.get("source_url") or ""))
    source_name = str(capture.get("source_name") or "").strip()
    structured_title = normalize_text(capture.get("title") or capture.get("page_title"))
    structured_body = str(capture.get("body_text") or capture.get("excerpt") or capture.get("visible_text") or "").replace("\u00a0", " ").strip()
    visible_text = structured_body
    page_title = structured_title
    captured_at = str(capture.get("captured_at") or "").strip()
    product_hint = str(capture.get("product_id") or capture.get("product_hint") or "").strip()
    text = "\n".join(item for item in (page_title, visible_text) if item)

    if product_hint and product_hint != product_id:
        return []
    if capture.get("detail_url") or source_is_specific_detail(source_url):
        return [detail_candidate(capture, source_url, source_name, page_title, text)]
    return listing_card_candidates(capture, source_url, source_name, text, captured_at)


def detail_candidate(
    capture: dict[str, Any],
    source_url: str,
    source_name: str,
    page_title: str,
    text: str,
) -> dict[str, Any]:
    configured_source_type = str(capture.get("source_type") or "").strip()
    source_type = configured_source_type or (premiere.SOURCE_TYPE if "community.adobe.com" in source_url else premiere.CREATIVE_COW_SOURCE_TYPE)
    version = best_version(text)
    title = normalize_text(capture.get("title") or page_title or first_nonempty_line(text))
    date_text = str(capture.get("source_date_text") or relative_or_absolute_date_text(text) or capture.get("listing_card_date_text") or "")
    source_date = str(capture.get("source_date_resolved") or capture.get("source_date") or premiere.extract_source_date(text) or "")
    return {
        "candidate_kind": "detail",
        "product_hint": str(capture.get("product_id") or capture.get("product_hint") or ""),
        "source_type": source_type,
        "source_name": source_name or ("Adobe Community" if source_type == premiere.SOURCE_TYPE else "Creative COW"),
        "source_url": source_url,
        "parent_title": title,
        "report_title": title,
        "report_text": text,
        "source_date": source_date,
        "source_date_text": date_text,
        "captured_at": str(capture.get("captured_at") or ""),
        "update_version": version,
        "match_basis": "detail_page",
        "listing_card_title": str(capture.get("listing_card_title") or ""),
        "listing_card_date_text": str(capture.get("listing_card_date_text") or ""),
        "url_dedupe_key": str(capture.get("url_dedupe_key") or canonical_url(source_url)),
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
        if not line_is_candidate_title(line, lines, index):
            continue
        host = urllib.parse.urlsplit(source_url).netloc.lower().removeprefix("www.")
        if host == CREATIVE_COW_HOST:
            window_lines = context_window(lines, index, before=2, after=4)
        else:
            window_lines = context_window(lines, index, before=2, after=8)
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
            "metadata_date": str(capture.get("source_date") or capture.get("metadata_date") or ""),
            "captured_at": captured_at,
            "update_version": best_version(window),
            "match_basis": "embedded_listing_report_card",
            "listing_card_title": title,
            "listing_card_category": category,
            "listing_card_date_text": date_text,
        })
        consumed_indices.update(range(max(0, index - 3), min(len(lines), index + 7)))
    return candidates


def evaluate_candidate(candidate: dict[str, Any], record_by_version: dict[str, Any], release_windows: list[ReleaseWindow] | None = None) -> dict[str, Any]:
    report_text = " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ])
    release_windows = release_windows or build_release_windows(list(record_by_version.values()))
    version_match = resolve_version_match(report_text, candidate, record_by_version, release_windows)
    version = version_match.update_version
    matched = not version_match.rejection_reason and bool(version_match.update_version)
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
        source_date=version_match.source_date_resolved[:10] if version_match.source_date_resolved else str(candidate.get("source_date") or ""),
        target_release_date=version_match.target_release_date,
        patch_version_matched=matched,
        matched_version=version_match.matched_version,
        match_basis=version_match.match_basis,
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
    row["source_date_text"] = version_match.source_date_text or str(candidate.get("source_date_text") or "")
    row["source_date_resolved"] = version_match.source_date_resolved
    row["next_release_date"] = version_match.next_release_date
    row["source_date_pass"] = version_match.source_date_pass
    row["version_match_confidence"] = version_match.confidence
    row["listing_card_title"] = str(candidate.get("listing_card_title") or "")
    row["listing_card_category"] = str(candidate.get("listing_card_category") or "")
    row["listing_card_date_text"] = str(candidate.get("listing_card_date_text") or "")
    row["capture_candidate_kind"] = str(candidate.get("candidate_kind") or "")
    row["url_dedupe_key"] = str(candidate.get("url_dedupe_key") or "")
    row["accepted_reason"] = ""

    reason = version_match.rejection_reason or exclusion_reason(row, candidate, report_text)
    if reason:
        row["counted"] = False
        row["exclusion_reason"] = reason
    else:
        row["counted"] = True
        row["exclusion_reason"] = None
        row["source_weight"] = 1
        row["accepted_reason"] = f"{version_match.match_basis}:{version_match.confidence}"
    return row


def resolve_version_match(
    report_text: str,
    candidate: dict[str, Any],
    record_by_version: dict[str, Any],
    release_windows: list[ReleaseWindow],
) -> VersionMatch:
    date_resolution = resolve_source_date(candidate)
    mentions = VERSION_RE.findall(report_text or "")
    full_mentions = [version for version in mentions if version.count(".") >= 2]
    short_mentions = [version for version in mentions if version.count(".") == 1]
    report_channel = release_channel_for_report(report_text)

    if full_mentions:
        unique_full = sorted(set(full_mentions), key=lambda item: (-item.count("."), item))
        version = unique_full[0]
        if len(set(unique_full)) > 1:
            return empty_version_match(date_resolution, "conflicting_exact_version_mentions")
        if date_resolution:
            active_window = active_window_for_date(release_windows, date_resolution, report_channel)
            if active_window and version != active_window.update_version and not version.startswith(active_window.update_version + "."):
                return empty_version_match(date_resolution, "conflicting_exact_version_for_active_release_window")
        record = record_by_version.get(version)
        window = window_for_version(release_windows, version, report_channel)
        return VersionMatch(
            update_version=version,
            matched_version=version,
            match_basis="exact_version",
            confidence="exact",
            target_release_date=date_part(getattr(record, "update_published_at", "")) if record else (window.start.date().isoformat() if window else ""),
            next_release_date=window.end.date().isoformat() if window and window.end else "",
            source_date_resolved=date_resolution.resolved_at if date_resolution else "",
            source_date_text=(date_resolution.date_text if date_resolution else str(candidate.get("source_date_text") or "")),
            source_date_pass=source_date_passes(date_resolution.resolved_date if date_resolution else "", date_part(getattr(record, "update_published_at", "")) if record else ""),
        )

    if short_mentions:
        if not date_resolution:
            return empty_version_match(None, "missing_resolvable_source_date_for_inferred_match")
        active_window = active_window_for_date(release_windows, date_resolution, report_channel)
        if not active_window:
            return empty_version_match(date_resolution, "source_date_outside_release_windows")
        matching_short = [version for version in sorted(set(short_mentions)) if short_version_matches_window(version, active_window)]
        if not matching_short:
            return empty_version_match(date_resolution, "truncated_version_outside_active_release_window")
        if coarse_date_too_close_to_boundary(date_resolution, active_window):
            return empty_version_match(date_resolution, "source_date_too_coarse_near_release_boundary")
        basis = "exact_version" if active_window.update_version in matching_short else "truncated_version_in_release_window"
        confidence = "exact" if basis == "exact_version" else "inferred_truncated_window"
        return VersionMatch(
            update_version=active_window.update_version,
            matched_version=active_window.update_version,
            match_basis=basis,
            confidence=confidence,
            target_release_date=active_window.start.date().isoformat(),
            next_release_date=active_window.end.date().isoformat() if active_window.end else "",
            source_date_resolved=date_resolution.resolved_at,
            source_date_text=date_resolution.date_text,
            source_date_pass=True,
        )

    if not CURRENT_RELEASE_RE.search(report_text or ""):
        return empty_version_match(date_resolution, "missing_exact_patch_version_match")
    if not date_resolution:
        return empty_version_match(None, "missing_resolvable_source_date_for_inferred_match")
    active_window = active_window_for_date(release_windows, date_resolution, report_channel)
    if not active_window:
        return empty_version_match(date_resolution, "source_date_outside_release_windows")
    if coarse_date_too_close_to_boundary(date_resolution, active_window):
        return empty_version_match(date_resolution, "source_date_too_coarse_near_release_boundary")
    return VersionMatch(
        update_version=active_window.update_version,
        matched_version=active_window.update_version,
        match_basis="release_window_inferred",
        confidence="inferred_release_window",
        target_release_date=active_window.start.date().isoformat(),
        next_release_date=active_window.end.date().isoformat() if active_window.end else "",
        source_date_resolved=date_resolution.resolved_at,
        source_date_text=date_resolution.date_text,
        source_date_pass=True,
    )


def empty_version_match(date_resolution: SourceDateResolution | None, reason: str) -> VersionMatch:
    return VersionMatch(
        update_version="",
        matched_version="",
        match_basis="",
        confidence="",
        target_release_date="",
        next_release_date="",
        source_date_resolved=date_resolution.resolved_at if date_resolution else "",
        source_date_text=date_resolution.date_text if date_resolution else "",
        source_date_pass=False if date_resolution else None,
        rejection_reason=reason,
    )


def window_for_version(windows: list[ReleaseWindow], version: str, channel: str) -> ReleaseWindow | None:
    for window in windows:
        if window.update_version == version and window.channel == channel:
            return window
    for window in windows:
        if window.update_version == version:
            return window
    return None


def active_window_for_date(
    windows: list[ReleaseWindow],
    date_resolution: SourceDateResolution,
    channel: str,
) -> ReleaseWindow | None:
    parsed = parse_iso_date(date_resolution.resolved_at)
    if not parsed:
        return None
    candidates = [window for window in windows if window.channel == channel and parsed >= window.start and (window.end is None or parsed < window.end)]
    if not candidates:
        return None
    return sorted(candidates, key=lambda window: window.start, reverse=True)[0]


def short_version_matches_window(short_version: str, window: ReleaseWindow) -> bool:
    version = str(window.update_version or "")
    return version == short_version or version.startswith(short_version + ".")


def coarse_date_too_close_to_boundary(date_resolution: SourceDateResolution, window: ReleaseWindow) -> bool:
    if date_resolution.precision not in {"day", "coarse"}:
        return False
    parsed = parse_iso_date(date_resolution.resolved_at)
    if not parsed:
        return True
    boundaries = [window.start]
    if window.end:
        boundaries.append(window.end)
    return any(abs(parsed - boundary) < timedelta(days=1) for boundary in boundaries)


def resolve_source_date(candidate: dict[str, Any]) -> SourceDateResolution | None:
    absolute_candidates = [
        ("detail_source_date", str(candidate.get("source_date") or "")),
        ("listing_card_date_text", str(candidate.get("listing_card_date_text") or "")),
        ("source_date_text", str(candidate.get("source_date_text") or "")),
        ("metadata_date", str(candidate.get("metadata_date") or "")),
    ]
    for source, value in absolute_candidates:
        parsed = parse_absolute_date_text(value)
        if parsed:
            return SourceDateResolution(
                resolved_at=to_utc_iso(parsed),
                resolved_date=parsed.date().isoformat(),
                date_text=value,
                precision="day" if len(value.strip()) <= 12 else "instant",
                source=source,
            )

    relative_text = str(candidate.get("listing_card_date_text") or candidate.get("source_date_text") or "")
    captured_at = parse_iso_date(candidate.get("captured_at"))
    if relative_text and captured_at:
        relative = resolve_relative_date(relative_text, captured_at)
        if relative:
            resolved, precision = relative
            return SourceDateResolution(
                resolved_at=to_utc_iso(resolved),
                resolved_date=resolved.date().isoformat(),
                date_text=relative_text,
                precision=precision,
                source="listing_card_relative_date",
            )
    return None


def parse_absolute_date_text(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = parse_iso_date(text)
    if parsed:
        return parsed
    match = ABSOLUTE_DATE_RE.search(text)
    if not match:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(match.group(0), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def resolve_relative_date(text: str, captured_at: datetime) -> tuple[datetime, str] | None:
    lowered = str(text or "").lower()
    if "today" in lowered:
        return captured_at, "day"
    if "yesterday" in lowered:
        return captured_at - timedelta(days=1), "day"
    match = re.search(r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago", lowered)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "minute":
        return captured_at - timedelta(minutes=amount), "instant"
    if unit == "hour":
        return captured_at - timedelta(hours=amount), "instant"
    if unit == "day":
        return captured_at - timedelta(days=amount), "day"
    if unit == "week":
        return captured_at - timedelta(weeks=amount), "day"
    if unit == "month":
        return captured_at - timedelta(days=30 * amount), "coarse"
    if unit == "year":
        return captured_at - timedelta(days=365 * amount), "coarse"
    return None


def to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def exclusion_reason(row: dict[str, Any], candidate: dict[str, Any], report_text: str) -> str | None:
    if not row.get("update_version"):
        return "missing_exact_patch_version_match"
    if not row.get("patch_version_matched"):
        return "missing_exact_patch_version_match"
    if official_or_announcement_source(str(row.get("source_url") or ""), report_text):
        return "official_announcement_not_user_evidence"
    if not premiere.PREMIERE_PRODUCT_RE.search(report_text) and str(candidate.get("product_hint") or "") != DEFAULT_PRODUCT_ID:
        return "missing_premiere_product_context"
    if premiere.PRE_RELEASE_RE.search(report_text):
        return "prerelease_context_for_stable_record"
    if not concrete_issue_match(report_text):
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
        if row.get("source_date_pass") is False:
            return "source_date_before_or_unverified_against_release"
        if not listing_card_has_enough_issue_detail(candidate):
            return "insufficient_concrete_issue_detail"
        row["source_date_pass"] = row.get("source_date_pass") if row.get("source_date") else True
        return None

    if candidate.get("candidate_kind") != "detail" and not source_is_specific_detail(str(row.get("source_url") or "")):
        return "source_url_not_specific_report"
    source_date_pass = source_date_passes(str(row.get("source_date") or ""), str(row.get("target_release_date") or ""))
    if source_date_pass is False:
        return "source_date_before_or_unverified_against_release"
    return None


def official_or_announcement_source(source_url: str, report_text: str) -> bool:
    url = source_url.lower()
    if "/announcements-" in url or "helpx.adobe.com" in url:
        return True
    normalized = normalize_text(report_text).replace("\u2019", "'").replace("\u2018", "'")
    return bool(re.search(
        r"\b(?:official\s+announcement|release\s+notes|what.?s\s+new|version\s+history|"
        r"we.?ve\s+just\s+released|bringing\s+a\s+range\s+of\s+improvements|new\s+features)\b",
        normalized,
        flags=re.I,
    ))


def concrete_issue_match(report_text: str) -> bool:
    return bool(
        premiere.premiere_strong_issue_match(report_text)
        or re.search(
            r"\b(?:missing|unavailable|not\s+available|do(?:es)?\s+not\s+appear|won.?t\s+appear|"
            r"impossible\s+to|cannot\s+(?:mask|open|export|render|use)|can.?t\s+(?:mask|open|export|render|use))\b",
            report_text or "",
            flags=re.I,
        )
    )


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
    if not concrete_issue_match(text):
        return False
    return True


def duplicate_row(
    row: dict[str, Any],
    existing_ids: set[str],
    existing_listing_keys: set[tuple[str, str, str]],
    existing_urls: set[tuple[str, str, str]],
    accepted: list[dict[str, Any]],
) -> bool:
    row_id = str(row.get("id") or "").strip()
    if row_id and row_id in existing_ids:
        return True
    accepted_ids = {str(item.get("id") or "").strip() for item in accepted}
    if row_id and row_id in accepted_ids:
        return True
    if is_listing_card_row(row):
        key = listing_card_key(row)
        accepted_keys = {listing_card_key(item) for item in accepted if listing_card_key(item)}
        return bool(key and (key in existing_listing_keys or key in accepted_keys))
    key = evidence_url_key(row)
    return key in existing_urls or key in {evidence_url_key(item) for item in accepted}


def prefer_detail_evidence(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    detail_title_keys = {
        report_title_key(row)
        for row in rows
        if is_detail_row(row) and report_title_key(row)[2]
    }
    preferred: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in rows:
        key = report_title_key(row)
        if is_listing_card_row(row) and key[2] and key in detail_title_keys:
            duplicate = dict(row)
            duplicate["counted"] = False
            duplicate["exclusion_reason"] = "duplicate_detail_page_evidence"
            rejected.append(duplicate)
            continue
        preferred.append(row)
    return preferred, rejected


def is_listing_card_row(row: dict[str, Any]) -> bool:
    if str(row.get("capture_candidate_kind") or "") == "detail":
        return False
    return (
        str(row.get("capture_candidate_kind") or "") == "listing_card"
        or bool(str(row.get("listing_card_title") or "").strip() and not source_is_specific_detail(str(row.get("source_url") or "")))
    )


def is_detail_row(row: dict[str, Any]) -> bool:
    return str(row.get("capture_candidate_kind") or "") == "detail" or source_is_specific_detail(str(row.get("source_url") or ""))


def report_title_key(row: dict[str, Any]) -> tuple[str, str, str]:
    title = normalize_text(row.get("listing_card_title") or row.get("report_title") or "").lower()
    return (
        str(row.get("product_id") or "").strip(),
        str(row.get("update_version") or "").strip(),
        title,
    ) if title else ("", "", "")


def build_method_health_rows(
    *,
    product_id: str,
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    generated_versions: set[str],
) -> list[dict[str, Any]]:
    versions = sorted({str(row.get("update_version") or "") for row in accepted if row.get("update_version")})
    if not versions:
        versions = sorted({str(row.get("update_version") or "") for row in rejected if row.get("update_version")}) or [""]
    rows: list[dict[str, Any]] = []
    for version in versions:
        accepted_for_version = [
            row
            for row in accepted
            if str(row.get("update_version") or "") == version
            and row.get("counted") is True
        ]
        duplicate_for_version = [
            row
            for row in accepted
            if str(row.get("update_version") or "") == version
            and str(row.get("exclusion_reason") or "") == "duplicate_existing_evidence"
        ]
        rejected_for_version = [
            row
            for row in rejected
            if str(row.get("update_version") or "") == version
            and str(row.get("exclusion_reason") or "") != "duplicate_existing_evidence"
        ]
        if accepted_for_version and rejected_for_version:
            status = "partial"
        elif accepted_for_version:
            status = "success" if version in generated_versions else "manual_review_needed"
        elif rejected_for_version:
            status = "no_results"
        else:
            status = "no_results"
        reasons = Counter(str(row.get("exclusion_reason") or "unknown") for row in rejected_for_version)
        notes = (
            "Promotes local Playwright candidate captures through deterministic Premiere Pro evidence gates. "
            "accepted_reports means accepted evidence rows, not listing-card candidates."
        )
        if version and version not in generated_versions and accepted_for_version:
            notes += " Accepted evidence is pending a matching official generated record."
        if duplicate_for_version:
            notes += f" Duplicate existing evidence rows skipped: {len(duplicate_for_version)}."
        if reasons:
            notes += " Rejected candidates: " + ", ".join(f"{reason}={count}" for reason, count in sorted(reasons.items())) + "."
        rows.append(method_health_row(
            product_id=product_id,
            update_version=version,
            method_id=METHOD_ID,
            source_type="local_playwright_capture",
            status=status,
            candidates_found=len(accepted_for_version) + len(duplicate_for_version) + len(rejected_for_version),
            accepted_candidates=len(accepted_for_version),
            duplicate_existing_evidence=len(duplicate_for_version),
            evidence_rows_added=len(accepted_for_version),
            public_counted_reports=len(accepted_for_version),
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


def write_explanation_logs(result: PromotionResult, input_path: Path) -> dict[str, Path]:
    log_dir = promotion_log_dir(input_path)
    log_dir.mkdir(parents=True, exist_ok=True)
    accepted_path = log_dir / "promotion-accepted.jsonl"
    rejections_path = log_dir / "promotion-rejections.jsonl"
    write_jsonl_rows(accepted_path, [explanation_row(row, accepted=True) for row in result.accepted])
    write_jsonl_rows(rejections_path, [explanation_row(row, accepted=False) for row in result.rejected])
    return {"accepted": accepted_path, "rejections": rejections_path}


def promotion_log_dir(input_path: Path) -> Path:
    resolved = input_path.resolve()
    parent = resolved.parent
    if parent.name.lower() == "outbox" and parent.parent.name.lower() == "app":
        return parent.parent / "logs"
    return parent / "logs"


def write_jsonl_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def explanation_row(row: dict[str, Any], *, accepted: bool) -> dict[str, Any]:
    return {
        "source_name": row.get("source_name") or "",
        "source_url": row.get("source_url") or "",
        "listing_card_title": row.get("listing_card_title") or row.get("report_title") or "",
        "listing_card_category": row.get("listing_card_category") or "",
        "listing_card_date_text": row.get("listing_card_date_text") or "",
        "source_date_resolved": row.get("source_date_resolved") or row.get("source_date") or "",
        "matched_version": row.get("matched_version") or "",
        "match_basis": row.get("match_basis") or "",
        "version_match_confidence": row.get("version_match_confidence") or "",
        "accepted_reason": row.get("accepted_reason") if accepted else "",
        "rejection_reason": "" if accepted else (row.get("exclusion_reason") or ""),
        "short_excerpt": row.get("report_text_excerpt") or "",
    }


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
        "source_date_resolved": "",
        "target_release_date": "",
        "next_release_date": "",
        "source_date_pass": None,
        "patch_version_matched": False,
        "matched_version": "",
        "match_basis": "",
        "version_match_confidence": "",
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


def listing_card_key(row: dict[str, Any]) -> tuple[str, str, str] | None:
    title = normalize_text(row.get("listing_card_title") or row.get("report_title") or "").lower()
    url = canonical_url(str(row.get("source_url") or ""))
    product_id = str(row.get("product_id") or "").strip()
    if not title or not url or not product_id:
        return None
    return (product_id, url, title)


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
                    if category.lower() in clean.lower():
                        return category
    return ""


def line_is_candidate_title(line: str, lines: list[str], index: int) -> bool:
    clean = normalize_text(line)
    if len(clean) < 8:
        return False
    if TITLE_SKIP_RE.match(clean):
        return False
    if relative_or_absolute_date_text(clean):
        return False
    if VERSION_RE.search(clean):
        return True
    category = nearest_category(lines, index)
    date_text = nearest_date_text(lines, index)
    if not category or not date_text:
        return False
    if "feature" in category.lower() or "idea" in category.lower():
        return True
    return bool(concrete_issue_match(clean) or CURRENT_RELEASE_RE.search(clean) or re.search(r"\b(?:issue|issues|problem|missing|unavailable)\b", clean, flags=re.I))


def nearest_date_text(lines: list[str], index: int) -> str:
    for distance in range(0, 10):
        for pos in (index + distance, index - distance):
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
