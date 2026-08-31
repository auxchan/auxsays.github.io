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
    evidence_key,
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
    "microsoft-powerpoint": {"learn_qna_search_rss", "learn_qna_powerpoint_tags", "reddit_search",
                             "stack_exchange_search", "github_officedev_issues",
                             "tech_community_discussions", "open_web_discovery"},
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
    # learn_qna_powerpoint_tags deliberately shares the microsoft_learn_qna source_type: it is the
    # same community, discovered a different way, and one report must not become two identities.
    "microsoft-powerpoint": {"microsoft_learn_qna", "reddit_community_report", "stack_exchange_question",
                             "github_officedev_issue", "microsoft_tech_community"},
}

# Per-product allowed permalink route slug(s). A record's public permalink is the canonical shape
# /updates/<company>/<product-slug>/<version-slug>/; the product-slug USUALLY equals product_id, but a
# few products legitimately publish under more than one established route slug (DaVinci Resolve's
# records live under BOTH /blackmagic-davinci/ and /davinci-resolve/). This is the single explicit
# authority for those exceptions -- any product not listed permits EXACTLY its own product_id. There is
# no substring, alias, or display-name inference: validation compares the exact parsed product-slug
# path segment (see _permalink_product_slug) against this allowlist.
ALLOWED_PERMALINK_SLUGS: dict[str, set[str]] = {
    "blackmagic-davinci": {"blackmagic-davinci", "davinci-resolve"},
}


def allowed_permalink_slugs(product_id: str) -> set[str]:
    return ALLOWED_PERMALINK_SLUGS.get(product_id, {product_id})


def _permalink_segments(permalink: str) -> list[str] | None:
    """Return the parsed segments of a canonical update permalink, or None when `permalink` is not
    EXACTLY /updates/<company>/<product>/<version>/ or /updates/<company>/<product>/<version>/<build>/
    -- a leading slash, then four (or, for a build-aware product, five) non-empty path segments, and
    at most a single trailing slash. The shape is validated strictly, never repaired: a missing or
    extra segment, an empty segment from a repeated slash (//), a non-'updates' root, a traversal
    ('..'), or an encoded-slash / encoded-traversal / query / fragment artifact all fail.

    The optional fifth segment is NOT a general relaxation: `validate_records` requires exactly five
    segments for a build-aware product and exactly four for every other product, and additionally
    requires the fifth to equal that record's own target_build. So the accepted shape per product is
    still exactly one, and segment-position spoofing gains nothing."""
    p = str(permalink or "")
    if not p.startswith("/updates/"):
        return None
    body = p[1:]
    if body.endswith("/"):
        body = body[:-1]
    segments = body.split("/")
    if len(segments) not in (4, 5) or any(seg == "" for seg in segments) or segments[0] != "updates":
        return None
    # A query or fragment artifact used to be rejected implicitly, because '/updates/a/b/c/?x=1'
    # split into FIVE segments and only four were allowed. Now that a fifth (build) segment is a
    # legitimate shape for build-aware products, that implicit rejection is gone and these must be
    # refused explicitly -- a canonical record permalink is a pure path, never a URL with a query
    # string, fragment, or percent-encoding.
    if ".." in segments or any(("%" in seg) or ("?" in seg) or ("#" in seg) for seg in segments):
        return None
    return segments


def _permalink_product_slug(permalink: str) -> str | None:
    """Return the product-slug segment of a canonical update permalink, or None if `permalink` is not
    a well-formed canonical path. The shape is validated strictly, never repaired:
    a missing or extra segment, an empty segment from a repeated slash (//), a non-'updates' root, a
    traversal ('..'), or an encoded-slash / encoded-traversal / query / fragment artifact all fail to
    yield a product slug. Combined with the exact-set membership check in validate_records, this makes
    segment-position spoofing and substring look-alikes (davinci-resolve-fake, blackmagic-davinci-extra)
    impossible to smuggle through -- the product slug is only ever the literal 3rd segment of a
    well-formed canonical path."""
    segments = _permalink_segments(permalink)
    return segments[2] if segments else None


def _permalink_build_segment(permalink: str) -> str:
    """The exact-build segment of a build-aware permalink, or '' when the path carries none.

    Delegates to the identity authority so the official-ingest write path and this validator read
    the build out of a permalink the same way. The stricter shape/ownership parsing above still
    runs first, so a hostile permalink is rejected before this is ever consulted."""
    segments = _permalink_segments(permalink)
    if not segments or len(segments) != 5:
        return ""
    return _identity_permalink_build_segment(permalink)


from .patch_identity import (
    REASON_BUILD_MISSING, REASON_PERMALINK_BUILD_MISMATCH, REASON_PERMALINK_BUILD_UNEXPECTED,
    build_identity_reason, is_build_aware, normalize_build, patch_key,
)
from .patch_identity import permalink_build_segment as _identity_permalink_build_segment


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


def _evidence_by_id(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    # Row identity is the SAME key the append/dedup authority uses (base.evidence_key): the triple
    # (product_id, exact update_version, id). Keying by the id STRING alone conflated two legitimately
    # distinct rows that share an id string across editions -- Reader and Pro share the DC build number
    # and the acrobat evidence id omits the edition, so the same Adobe post yields the same id string for
    # both. That produced a FALSE evidence_existing_row_modified when the Reader collector appended its
    # row after Pro had committed the same-id-string row (natural run 31234793893). Using the append
    # authority's triple keeps the two rows distinct (Reader's is a new row, not a mutation of Pro's).
    return {evidence_key(r, "id"): r for r in rows if r.get("id")}


def _existing_patch_keys(product_id: str) -> set[tuple[str, str, str]]:
    """The exact canonical patch identities this product actually has records for.

    For a version-only product this is just its versions with an empty build slot, so membership
    is identical to the version-only check this replaced. For a build-aware product it is the
    EXACT (version, build) pairs: a YYMM that exists is no longer sufficient, because a sibling
    build under the same YYMM is a different patch that this row may not belong to."""
    return {
        patch_key(product_id, str(r.update_version).strip(), getattr(r, "target_build", ""))
        for r in generated_records(product_id, include_archived=True)
    }


def _patch_resolves(product_id: str, version: str, target_build: str,
                    existing_keys: set[tuple[str, str, str]]) -> bool:
    """True when (product, version, build) names a patch that exists.

    Build-aware products get NO version-only fallback: a missing build cannot resolve (it does not
    name a patch at all) and a wrong build cannot resolve (it names a patch that does not exist).
    Non-build-aware products are unaffected -- their build slot is always empty on both sides."""
    return patch_key(product_id, version, target_build) in existing_keys


# --- generated records ---------------------------------------------------------
def validate_records(product_id: str, generated_dir: Path, mutated: set[Path],
                     baseline_bytes) -> None:
    """`mutated` are paths under updates/generated/ this collector changed. baseline_bytes(path)
    returns the pre-collector bytes (None if the path did not exist)."""
    existing_keys = _existing_patch_keys(product_id)
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
        # Identity must match the deterministic writer's permalink shape /updates/<company>/<product>/<slug>/.
        # The product-slug segment must be one this product is explicitly allowed to publish under (its
        # own product_id, or an entry in ALLOWED_PERMALINK_SLUGS). Exact parsed-segment match only -- no
        # substring/alias inference -- so another product using this slug, a DaVinci record under an
        # unrelated slug, and deceptive substring paths are all rejected.
        permalink = str(data.get("permalink") or "")
        slug = _permalink_product_slug(permalink)
        if slug is None or slug not in allowed_permalink_slugs(product_id):
            raise _violation("record_permalink_mismatch", f"collector '{product_id}' record permalink identity mismatch: {permalink!r} ({path.name})",
                             surface="record", product_id=product_id, version=version)
        # Exact-build identity. A build-aware product publishes at
        # /updates/<co>/<product>/<version>/<build>/ and the build segment must be THIS record's own
        # target_build -- so a record cannot claim another build's URL, and a missing build fails
        # closed rather than silently falling back to the version-only URL that a sibling build may
        # already own. Every other product must still be exactly four segments.
        record_build = normalize_build(data.get("target_build"))
        permalink_build = _permalink_build_segment(permalink)
        # The rule itself lives in the identity authority; the official-ingest write path applies
        # the SAME function before writing. Only the violation message is lane-specific.
        build_reason = build_identity_reason(product_id, version, record_build, permalink)
        if build_reason == REASON_BUILD_MISSING:
            raise _violation("record_build_missing", f"collector '{product_id}' record has no exact target_build: {path.name}",
                             surface="record", product_id=product_id, version=version)
        if build_reason == REASON_PERMALINK_BUILD_MISMATCH:
            raise _violation("record_permalink_build_mismatch", f"collector '{product_id}' record permalink build {permalink_build!r} does not match target_build {record_build!r} ({path.name})",
                             surface="record", product_id=product_id, version=version)
        if build_reason == REASON_PERMALINK_BUILD_UNEXPECTED:
            raise _violation("record_permalink_build_unexpected", f"collector '{product_id}' is not build-aware but its permalink carries a build segment: {permalink!r} ({path.name})",
                             surface="record", product_id=product_id, version=version)

        # A collector refreshes existing records; a patch with no pre-existing record is suspect.
        # For a build-aware product this resolves the EXACT (version, build), so refreshing a
        # sibling build that has no record of its own is rejected rather than accepted because the
        # YYMM happens to exist.
        if not _patch_resolves(product_id, version, record_build, existing_keys):
            raise _violation("record_version_unresolved", f"collector '{product_id}' record version {version} does not resolve to an existing patch record",
                             surface="record", product_id=product_id, version=version)


# --- consensus evidence --------------------------------------------------------
def validate_evidence(product_id: str, before_text: str | None, after_text: str | None) -> None:
    before = _parse_evidence(before_text)
    after = _parse_evidence(after_text)
    before_ids = _evidence_by_id(before)
    after_ids = _evidence_by_id(after)

    # Existing rows are immutable: present, identical, never deleted. Identity = the append authority's
    # (product_id, version, id) triple, so a genuine change to the SAME row still rejects while a
    # different edition's same-id-string row is correctly treated as a distinct (new) row.
    for bkey, brow in before_ids.items():
        if bkey not in after_ids:
            raise _violation("evidence_existing_row_deleted", f"collector '{product_id}' deleted existing evidence row {brow.get('id')}",
                             surface="evidence", product_id=product_id)
        if after_ids[bkey] != brow:
            raise _violation("evidence_existing_row_modified", f"collector '{product_id}' modified existing evidence row {brow.get('id')}",
                             surface="evidence", product_id=product_id)
    if len(after) < len(before):
        raise _violation("evidence_rows_removed", f"collector '{product_id}' removed evidence rows", surface="evidence", product_id=product_id)

    existing_keys = _existing_patch_keys(product_id)
    permitted_sources = allowed_source_types(product_id)
    # Dedup universe = existing ids/urls; each added row must be unique and owned. The duplicate-URL
    # identity is the SAME key the append/dedup authority uses (base.evidence_key): the triple
    # (product_id, exact update_version, normalize_url(source_url)) -- NOT the url alone. A url-alone
    # key over-rejected legitimately shared source URLs across distinct (product, version) rows
    # (run 31015586517 false positive on obs/acrobat-pro/acrobat-reader). Embedded listing report cards
    # are exempt from the url set exactly as append_evidence_rows exempts them.
    seen_ids = set(before_ids)
    seen_urls = {
        evidence_key(r, "source_url")
        for r in before
        if r.get("source_url") and r.get("match_basis") != "embedded_listing_report_card"
    }
    for row in after:
        rid = str(row.get("id") or "")
        rkey = evidence_key(row, "id")  # (product_id, version, id) -- the append authority's identity
        if rkey in before_ids:
            continue  # unchanged existing row (same product_id + version + id)
        pid = str(row.get("product_id") or "").strip()
        if pid != product_id:
            raise _violation("evidence_product_mismatch", f"collector '{product_id}' appended cross-product evidence for '{pid}'",
                             surface="evidence", product_id=product_id)
        version = str(row.get("update_version") or "").strip()
        if not _patch_resolves(product_id, version, row.get("target_build"), existing_keys):
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
        if rkey in seen_ids:
            raise _violation("evidence_duplicate_id", f"collector '{product_id}' appended a duplicate evidence id {rid}",
                             surface="evidence", product_id=product_id, version=version)
        url = str(row.get("source_url") or "")
        if url and row.get("match_basis") != "embedded_listing_report_card":
            url_key = evidence_key(row, "source_url")
            if url_key in seen_urls:
                raise _violation("evidence_duplicate_url", f"collector '{product_id}' appended a duplicate evidence url {url}",
                                 surface="evidence", product_id=product_id, version=version)
            seen_urls.add(url_key)
        seen_ids.add(rkey)


# --- method health -------------------------------------------------------------
def validate_method_health(product_id: str, rows: list[dict[str, Any]]) -> None:
    permitted = allowed_methods(product_id)
    existing_keys = _existing_patch_keys(product_id)
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
        if not _patch_resolves(product_id, version, row.get("target_build"), existing_keys):
            raise _violation("method_health_version_unresolved", f"collector '{product_id}' returned method-health for unresolved version {version}",
                             surface="method_health", product_id=product_id, version=version)
        status = str(row.get("status") or "").strip()
        if status not in VALID_METHOD_HEALTH_STATUSES:
            raise _violation("method_health_noncanonical_status", f"collector '{product_id}' returned non-canonical status '{status}'",
                             surface="method_health", product_id=product_id, version=version)
