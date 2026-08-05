"""Semantic collector ownership manifest + validation (Part D hard gate).

Filesystem-root containment (collector_txn) is necessary but not sufficient: a collector could
still mutate ANOTHER product's record or append cross-product evidence while staying inside the
declared roots. This module enforces IDENTITY ownership: a collector may only create/modify its own
product's records, append evidence for its own product + an existing patch version, and return
method-health only for its own product and declared methods. Any violation raises OwnershipViolation,
which the runner treats as a collector failure -> full transaction rollback.

The authoritative ownership key is product_id (a collector's identity). ALLOWED_METHODS is the
per-product method allowlist derived from committed telemetry + collector code; it is the deliberate
control point -- adding a genuinely new method to a collector requires updating this manifest.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# A product_id / version rendered into a public diagnostic is either a clean slug or nothing. Product
# ids and versions are deterministic slugs (obs-studio, 31.0.3); anything else -- a value carrying a
# newline, control char, url, absolute path, whitespace, or a token -- is NOT emitted at all (replaced
# by a fixed marker), so no fragment of a hostile source value can leak through the diagnostic line.
_SLUG = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,47}\Z")


def _safe_token(value: Any) -> str:
    s = str(value)
    return s if _SLUG.fullmatch(s) else ("-" if s == "" else "invalid")

from patch_collectors.base import (
    VALID_METHOD_HEALTH_STATUSES,
    split_front_matter,
    generated_records,
)

# Per-product allowed method IDs (EMH ground truth + collector code). See audit notes.
ALLOWED_METHODS: dict[str, set[str]] = {
    "blackmagic-davinci": {
        "known_watchlist", "reddit_search", "creative_cow_forum_search",
        "vendor_forum_search", "web_search",
    },
    "adobe-premiere-pro": {
        "reddit_search", "adobe_community_search", "adobe_community_bug_tab_index",
        "adobe_community_known_url_recheck", "brave_search_api", "wayback_snapshot_recheck",
        "creativecow_forum_index", "creativecow_brave_search", "known_watchlist",
    },
    "adobe-acrobat-reader": {
        "adobe_community_algolia_search", "adobe_community_search", "reddit_search",
        "adobe_community_bug_tab_index", "adobe_community_known_url_recheck",
    },
    "adobe-acrobat-pro": {
        "adobe_community_algolia_search", "adobe_community_search", "reddit_search",
        "adobe_community_bug_tab_index", "adobe_community_known_url_recheck",
    },
    "obs-studio": {"github_issues", "known_watchlist"},
    "microsoft-windows-11": {"learn_qna_search_rss"},
    "microsoft-powerpoint": {"learn_qna_search_rss", "reddit_search"},
}

# Per-product allowed evidence source_type identities. Evidence rows carry ``source_type`` (not a
# method_id); this is the "allowed method/source identity" control point for appended evidence.
# Derived from collector source constants (davinci/obs/premiere/acrobat/windows/powerpoint) UNION the
# source_types already present in committed consensus_evidence.yml, so legitimate rows are never
# rejected. A genuinely new source_type requires updating this manifest -- the deliberate gate.
ALLOWED_SOURCE_TYPES: dict[str, set[str]] = {
    "blackmagic-davinci": {
        "blackmagic_forum", "reddit_community_report", "creator_forum_report", "community_report",
    },
    "adobe-premiere-pro": {
        "adobe_community_bug_report", "creativecow_forum_report", "reddit_community_report",
        "adobe_community_listing_card",
    },
    "adobe-acrobat-reader": {"adobe_community_bug_report", "reddit_community_report"},
    "adobe-acrobat-pro": {"adobe_community_bug_report", "reddit_community_report"},
    "obs-studio": {"github_issue", "curated_watchlist"},
    "microsoft-windows-11": {"microsoft_learn_qna"},
    "microsoft-powerpoint": {"microsoft_learn_qna", "reddit_community_report"},
}


class OwnershipViolation(Exception):
    """A collector produced a record, evidence row, or method-health row it does not own.

    Carries a PUBLIC-SAFE structured reason so a production run can report WHICH rule failed for WHICH
    collector without leaking anything sensitive. ``code`` is a fixed slug (e.g. record_version_
    unresolved); ``surface`` is record|evidence|method_health; ``product_id``/``version`` are the
    collector identity + normalized target version. The free-text ``args[0]`` message may still name a
    record basename / evidence id for local tests, but the runner surfaces ONLY (code, surface,
    product_id, version) -- never a raw path, url, token, header, or stack trace."""

    def __init__(self, message: str, *, code: str = "unspecified", surface: str = "",
                 product_id: str = "", version: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.surface = surface
        self.product_id = product_id
        self.version = version

    def public_reason(self) -> str:
        """Bounded, public-safe one-liner for logs/summaries. Every field is reduced to a slug-safe,
        length-capped token, so no path/url/token/newline/control-char/exception text can leak even
        if a hostile source injected one into a product_id or version."""
        parts = [f"code={_safe_token(self.code)}", f"surface={_safe_token(self.surface) if self.surface else '-'}"]
        if self.product_id:
            parts.append(f"product={_safe_token(self.product_id)}")
        if self.version:
            parts.append(f"version={_safe_token(self.version)}")
        return " ".join(parts)


def _violation(code: str, message: str, *, surface: str, product_id: str = "", version: str = "") -> "OwnershipViolation":
    return OwnershipViolation(message, code=code, surface=surface, product_id=product_id, version=version)


def allowed_methods(product_id: str) -> set[str]:
    return ALLOWED_METHODS.get(product_id, set())


def allowed_source_types(product_id: str) -> set[str]:
    return ALLOWED_SOURCE_TYPES.get(product_id, set())


def _parse_evidence(text: str | None) -> list[dict[str, Any]]:
    if not text:
        return []
    data = yaml.safe_load(text)
    rows = data.get("evidence") if isinstance(data, dict) else (data if isinstance(data, list) else [])
    return [r for r in (rows or []) if isinstance(r, dict)]


def _evidence_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("id")): r for r in rows if r.get("id")}


def _existing_versions(product_id: str) -> set[str]:
    # str-normalize: YAML may parse a version as float (26.2) in one place and string ('26.2') in
    # another; comparing normalized strings on BOTH sides avoids false-rejecting legitimate rows.
    return {str(r.update_version).strip() for r in generated_records(product_id, include_archived=True)}


# --- generated records ---------------------------------------------------------
def validate_records(product_id: str, generated_dir: Path, mutated: set[Path],
                     baseline_bytes) -> None:
    """`mutated` are paths under updates/generated/ this collector changed. baseline_bytes(path)
    returns the pre-collector bytes (None if the path did not exist)."""
    existing_versions = _existing_versions(product_id)
    for path in mutated:
        exists_now = path.exists()
        if not exists_now:
            # Deletion: collectors REFRESH records, they never delete. Any deletion is a violation.
            raise _violation("undeclared_deletion", f"collector '{product_id}' deleted a generated record: {path.name}",
                             surface="record", product_id=product_id)
        text = path.read_text(encoding="utf-8", errors="replace")
        front, _body = split_front_matter(text)
        if front is None:
            raise _violation("record_non_record_file", f"collector '{product_id}' wrote a non-record file under generated/: {path.name}",
                             surface="record", product_id=product_id)
        try:
            data = yaml.safe_load(front) or {}
        except yaml.YAMLError:
            raise _violation("record_malformed_front_matter", f"collector '{product_id}' wrote malformed record front matter: {path.name}",
                             surface="record", product_id=product_id)
        if not isinstance(data, dict) or data.get("update_entry") is not True:
            raise _violation("record_non_update", f"collector '{product_id}' wrote a non-update record under generated/: {path.name}",
                             surface="record", product_id=product_id)
        rec_pid = str(data.get("product_id") or "").strip()
        if rec_pid != product_id:
            raise _violation("record_product_mismatch", f"collector '{product_id}' mutated a '{rec_pid or 'unknown'}'-owned record: {path.name}",
                             surface="record", product_id=product_id)
        version = str(data.get("update_version") or "").strip()
        if not version:
            raise _violation("record_version_missing", f"collector '{product_id}' record has no update_version: {path.name}",
                             surface="record", product_id=product_id)
        # Identity must match the deterministic writer's permalink shape /updates/<company>/<product>/<slug>/
        permalink = str(data.get("permalink") or "")
        if f"/{product_id}/" not in permalink:
            raise _violation("record_permalink_mismatch", f"collector '{product_id}' record permalink identity mismatch: {permalink!r} ({path.name})",
                             surface="record", product_id=product_id, version=version)
        # A collector refreshes existing records; a version with no pre-existing record is suspect.
        if version not in existing_versions:
            raise _violation("record_version_unresolved", f"collector '{product_id}' record version {version} does not resolve to an existing patch record",
                             surface="record", product_id=product_id, version=version)


# --- consensus evidence --------------------------------------------------------
def validate_evidence(product_id: str, before_text: str | None, after_text: str | None) -> None:
    before = _parse_evidence(before_text)
    after = _parse_evidence(after_text)
    before_ids = _evidence_by_id(before)
    after_ids = _evidence_by_id(after)

    # Existing rows are immutable: present, identical, never deleted.
    for bid, brow in before_ids.items():
        if bid not in after_ids:
            raise _violation("evidence_existing_row_deleted", f"collector '{product_id}' deleted existing evidence row {bid}",
                             surface="evidence", product_id=product_id)
        if after_ids[bid] != brow:
            raise _violation("evidence_existing_row_modified", f"collector '{product_id}' modified existing evidence row {bid}",
                             surface="evidence", product_id=product_id)
    if len(after) < len(before):
        raise _violation("evidence_rows_removed", f"collector '{product_id}' removed evidence rows", surface="evidence", product_id=product_id)

    existing_versions = _existing_versions(product_id)
    permitted_sources = allowed_source_types(product_id)
    # Dedup universe = existing ids/urls; each added row must be unique and owned.
    seen_ids = set(before_ids)
    seen_urls = {str(r.get("source_url") or "") for r in before if r.get("source_url")}
    for row in after:
        rid = str(row.get("id") or "")
        if rid in before_ids:
            continue  # unchanged existing row
        pid = str(row.get("product_id") or "").strip()
        if pid != product_id:
            raise _violation("evidence_product_mismatch", f"collector '{product_id}' appended cross-product evidence for '{pid}'",
                             surface="evidence", product_id=product_id)
        version = str(row.get("update_version") or "").strip()
        if version not in existing_versions:
            raise _violation("evidence_version_unresolved", f"collector '{product_id}' appended evidence for unresolved version {version}",
                             surface="evidence", product_id=product_id, version=version)
        source_type = str(row.get("source_type") or "").strip()
        if not source_type:
            raise _violation("evidence_missing_source", f"collector '{product_id}' appended evidence with no source identity (id={rid})",
                             surface="evidence", product_id=product_id, version=version)
        if source_type not in permitted_sources:
            raise _violation("evidence_unauthorized_source", f"collector '{product_id}' appended evidence with unauthorized source '{source_type}' (id={rid})",
                             surface="evidence", product_id=product_id, version=version)
        if not rid:
            raise _violation("evidence_missing_id", f"collector '{product_id}' appended an evidence row with no id", surface="evidence", product_id=product_id, version=version)
        if rid in seen_ids:
            raise _violation("evidence_duplicate_id", f"collector '{product_id}' appended a duplicate evidence id {rid}",
                             surface="evidence", product_id=product_id, version=version)
        url = str(row.get("source_url") or "")
        if url and url in seen_urls and row.get("match_basis") != "embedded_listing_report_card":
            raise _violation("evidence_duplicate_url", f"collector '{product_id}' appended a duplicate evidence url {url}",
                             surface="evidence", product_id=product_id, version=version)
        seen_ids.add(rid)
        if url:
            seen_urls.add(url)


# --- method health -------------------------------------------------------------
def validate_method_health(product_id: str, rows: list[dict[str, Any]]) -> None:
    permitted = allowed_methods(product_id)
    existing_versions = _existing_versions(product_id)
    for row in rows:
        if not isinstance(row, dict):
            raise _violation("method_health_non_dict", f"collector '{product_id}' returned a non-dict method-health row",
                             surface="method_health", product_id=product_id)
        pid = str(row.get("product_id") or "").strip()
        if pid != product_id:
            raise _violation("method_health_product_mismatch", f"collector '{product_id}' returned method-health for '{pid}'",
                             surface="method_health", product_id=product_id)
        method = str(row.get("method_id") or "").strip()
        if method not in permitted:
            raise _violation("method_not_allowed", f"collector '{product_id}' returned unauthorized method_id '{method}'",
                             surface="method_health", product_id=product_id)
        version = str(row.get("update_version") or "").strip()
        if version not in existing_versions:
            raise _violation("method_health_version_unresolved", f"collector '{product_id}' returned method-health for unresolved version {version}",
                             surface="method_health", product_id=product_id, version=version)
        status = str(row.get("status") or "").strip()
        if status not in VALID_METHOD_HEALTH_STATUSES:
            raise _violation("method_health_noncanonical_status", f"collector '{product_id}' returned non-canonical status '{status}'",
                             surface="method_health", product_id=product_id, version=version)
