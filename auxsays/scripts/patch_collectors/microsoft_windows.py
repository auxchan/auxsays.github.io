"""Windows 11 community-evidence collector (Microsoft Learn Q&A).

Discovers real Windows 11 user reports from Microsoft Learn Q&A (learn.microsoft.com/
answers) via its search-RSS API, driving each search by the *exact current patch
identity* already captured on the generated record (target_kb / target_os_build). It
then applies deterministic acceptance gates so a report counts ONLY when it names the
record's current KB or OS build. It reuses the fail-closed Windows identity gate added
in PR #14, so evidence for an older KB/build can never count after a train rolls over.

Deterministic + repo-owned: no AI, no manual candidate approval. Discovery is
keyword-anchored (search by exact KB/build); acceptance is a fixed ordered rule set.

Safety — NOT wired to the production runner yet. This collector is intentionally NOT
registered in run_patch_evidence_collection.py, because the scheduled "Patch Evidence
Collection" workflow runs that runner in --write mode with no product filter (all
registered collectors). Leaving it unregistered means the default post-merge behavior
cannot write Windows Learn Q&A evidence. Observe it first with the read-only dry-run
below; a later PR can register it behind a default-off gate after dry-run observation.

Read-only local dry-run (never writes evidence or records):
    cd auxsays/scripts && python -m patch_collectors.microsoft_windows [--update-version 24H2] [--since-days 45]
It builds a write=False CollectorContext, so append_evidence_rows / apply_consensus_writeback
are never reached; it only fetches Learn Q&A and prints candidate/acceptance/health JSON.
"""
from __future__ import annotations

import re
from typing import Any

from .base import (
    EVIDENCE_PATH,
    CollectorContext,
    PatchRecord,
    ProductCollector,
    WINDOWS_PRODUCT_ID,
    append_evidence_rows,
    counted_rows,
    date_part,
    exact_version_match,
    generated_records,
    load_front_matter_and_body,
    make_evidence_row,
    method_health_row,
    slug,
    source_url_is_specific,
    text_describes_issue,
    utc_now,
    windows_identity_gate,
)
from . import microsoft_learn_qna_source as learn_qna

PRODUCT_ID = WINDOWS_PRODUCT_ID
METHOD_ID = "learn_qna_search_rss"
SOURCE_TYPE = "microsoft_learn_qna"
SOURCE_NAME = "Microsoft Learn Q&A"

# --- deterministic content classifiers (no AI) -------------------------------
KB_TOKEN_RE = re.compile(r"\bKB\d{6,7}\b", re.I)
BUILD_TOKEN_RE = re.compile(r"\b\d{5}\.\d{3,5}\b")
FEATURE_TOKEN_RE = re.compile(r"\b2\dH[12]\b", re.I)

# Concrete Windows user-facing symptoms (a real report, not a how-to question).
WINDOWS_ISSUE_RE = re.compile(
    r"\b(?:bsod|blue[\s-]?screen|bug[\s-]?check|stop\s+(?:code|error)|0x[0-9a-f]{6,8}|"
    r"won'?t\s+boot|fails?\s+to\s+boot|boot\s*loop|black\s+screen|"
    r"(?:install(?:ation)?|update|upgrade)\s+(?:fail(?:ed|s|ure|ing)?|error)|"
    r"fails?\s+to\s+install|won'?t\s+install|error\s+0x|rolls?\s+back|rolled\s+back|rollback|"
    r"printer|printing|no\s+(?:audio|sound|network|internet|wi[\s-]?fi|display|signal)|"
    r"driver\s+(?:crash|fail)|crash(?:es|ing|ed)?|freez(?:e|es|ing|en)|hang(?:s|ing|ed)?|"
    r"not\s+working\s+after|broke(?:n)?\s+after|stopped\s+working\s+after)\b",
    re.I,
)
HOW_TO_RE = re.compile(
    r"\b(?:how\s+(?:do|can|would|should)\s+i|how\s+to|where\s+(?:is|do|can)|is\s+it\s+safe\s+to|"
    r"should\s+i\s+(?:install|update|upgrade)|which\s+version|what'?s\s+the\s+best|recommend(?:ation)?)\b",
    re.I,
)
OFFICIAL_NOTE_RE = re.compile(
    r"\b(?:release\s+notes|change\s*log|what'?s\s+new|known\s+issues\s+(?:for|in|list)|"
    r"official\s+(?:documentation|guidance|list))\b",
    re.I,
)
ANNOUNCE_RE = re.compile(
    r"\b(?:now\s+available|is\s+available|announc(?:e|es|ing|ed|ement)|general\s+availability|"
    r"rolling\s+out|is\s+released|has\s+been\s+released|is\s+now\s+released)\b",
    re.I,
)
TENANT_RE = re.compile(
    r"\b(?:tenant|service\s+health|admin\s+center|message\s+center|exchange\s+online|"
    r"sharepoint\s+online|onedrive\s+for\s+business|microsoft\s+365\s+(?:service|admin)|"
    r"service\s+(?:incident|degradation|outage|advisory))\b",
    re.I,
)
ACCOUNT_RE = re.compile(
    r"\b(?:sign[\s-]?in|log[\s-]?in|password\s+reset|account\s+(?:locked|issue|problem)|"
    r"activation\s+(?:error|fail)|licens(?:e|ing)\s+(?:error|issue)|azure\s+ad|entra\s+id|"
    r"\bmfa\b|multi[\s-]?factor|authenticat(?:e|ion)\s+(?:error|fail))\b",
    re.I,
)
LATEST_RE = re.compile(
    r"\b(?:latest|newest|most\s+recent|recent|last)\s+(?:update|patch|cumulative\s+update|build)\b|"
    r"\bthis\s+month'?s\s+(?:update|patch)\b|\brecent\s+windows\s+update\b",
    re.I,
)
PATCH_TUESDAY_RE = re.compile(r"\bpatch\s+tuesday\b", re.I)
MONTH_YEAR_RE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+20\d{2}\b",
    re.I,
)


# --- helpers -----------------------------------------------------------------

def _has_exact(text: str, token: str) -> bool:
    if not token:
        return False
    matched, _matched, _basis = exact_version_match(text, token)
    return bool(matched)


def _other_kbs(text: str, target_kb: str) -> set[str]:
    found = {m.upper() for m in KB_TOKEN_RE.findall(text or "")}
    return found - ({target_kb.upper()} if target_kb else set())


def _other_builds(text: str, target_build: str) -> set[str]:
    found = set(BUILD_TOKEN_RE.findall(text or ""))
    return found - ({target_build} if target_build else set())


def _other_features(text: str, target_feature: str) -> set[str]:
    found = {m.upper() for m in FEATURE_TOKEN_RE.findall(text or "")}
    return found - ({target_feature.upper()} if target_feature else set())


def describes_windows_issue(text: str) -> bool:
    """A concrete user-facing Windows problem, not a how-to/recommendation question."""
    has_issue = text_describes_issue(text) or bool(WINDOWS_ISSUE_RE.search(text or ""))
    if not has_issue:
        return False
    if HOW_TO_RE.search(text or "") and not WINDOWS_ISSUE_RE.search(text or ""):
        return False
    return True


def identity_basis(matched_kb: str, matched_os_build: str, matched_feature: str) -> tuple[bool, str]:
    if matched_os_build:
        return True, "exact_os_build"
    if matched_kb and matched_feature:
        return True, "exact_kb_feature_train"
    return False, "no_exact_windows_identity"


def classify(text: str) -> tuple[str, str, str, str, str]:
    lowered = (text or "").lower()
    if any(t in lowered for t in ("bsod", "blue screen", "blue-screen", "bugcheck", "bug check", "stop code", "stop error")) or re.search(r"0x[0-9a-f]{6,8}", lowered):
        return "BSOD / stop error", "system stability", "windows", "critical", "negative"
    if any(t in lowered for t in ("won't boot", "wont boot", "fails to boot", "boot loop", "black screen", "no boot")):
        return "boot failure", "startup / boot", "windows", "critical", "negative"
    if any(t in lowered for t in ("install", "update fail", "upgrade fail", "rollback", "rolled back", "0x800", "fails to install", "won't install")):
        return "update/install failure", "windows update", "windows", "high", "negative"
    if "printer" in lowered or "printing" in lowered:
        return "printer regression", "printing", "windows", "high", "negative"
    if any(t in lowered for t in ("network", "wifi", "wi-fi", "internet", "ethernet", "vpn")):
        return "network regression", "networking", "windows", "high", "negative"
    if any(t in lowered for t in ("audio", "sound", "microphone")):
        return "audio regression", "audio", "windows", "medium", "negative"
    if any(t in lowered for t in ("display", "monitor", "graphics", "gpu", "resolution", "screen")):
        return "display regression", "display / graphics", "windows", "medium", "negative"
    if any(t in lowered for t in ("slow", "lag", "performance", "high cpu", "memory leak")):
        return "performance regression", "performance", "windows", "medium", "negative"
    if any(t in lowered for t in ("crash", "freeze", "hang")):
        return "crash or hang", "system stability", "windows", "high", "negative"
    return "unspecified Windows issue", "Windows workflow", "windows", "medium", "negative"


def windows_learn_qna_reason(
    target: dict[str, Any],
    source_url: str,
    source_date: str,
    report_text: str,
    matched_kb: str,
    matched_os_build: str,
    matched_feature: str,
) -> str | None:
    """Ordered, deterministic acceptance. Returns an exclusion reason, or None to count."""
    if not source_url_is_specific(source_url):
        return "no_specific_source_url"
    if OFFICIAL_NOTE_RE.search(report_text) and not WINDOWS_ISSUE_RE.search(report_text):
        return "official_note_not_user_report"
    if ANNOUNCE_RE.search(report_text) and not describes_windows_issue(report_text):
        return "release_announcement_not_user_report"
    if not describes_windows_issue(report_text):
        return "generic_support_request"

    has_identity = bool(matched_os_build) or bool(matched_kb and matched_feature)
    if not has_identity:
        if TENANT_RE.search(report_text):
            return "tenant_service_incident_not_client_patch"
        if ACCOUNT_RE.search(report_text):
            return "account_backend_issue_not_patch"
        if matched_kb and not matched_feature and _other_features(report_text, target.get("target_feature_version", "")):
            return "wrong_feature_train_for_kb"
        if _other_kbs(report_text, target.get("target_kb", "")) or _other_builds(report_text, target.get("target_os_build", "")):
            return "wrong_kb_for_current_patch"
        if LATEST_RE.search(report_text):
            return "vague_latest_update"
        if PATCH_TUESDAY_RE.search(report_text) or MONTH_YEAR_RE.search(report_text):
            return "date_only_inference"
        return "missing_kb_or_build"

    # Exact identity present -> confirm against the record's CURRENT patch + date via the
    # shared fail-closed gate (PR #14). This also enforces stale-after-rollover and date.
    gate_row = {
        "matched_kb": matched_kb,
        "matched_os_build": matched_os_build,
        "matched_feature_version": matched_feature,
        "source_date": source_date,
    }
    ok, gate_reason = windows_identity_gate(gate_row, target)
    if not ok:
        if gate_reason == "source_date_before_target_release_date":
            return "date_before_release"
        return gate_reason  # missing_kb_or_build / wrong_feature_train_for_kb / stale_due_to_patch_rollover / windows_record_missing_target_identity
    return None


def row_from_candidate(record: PatchRecord, target: dict[str, Any], candidate: dict[str, Any], captured_at: str) -> dict[str, Any]:
    report_text = " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ]).strip()

    matched_kb = target.get("target_kb", "") if _has_exact(report_text, target.get("target_kb", "")) else ""
    matched_os_build = target.get("target_os_build", "") if _has_exact(report_text, target.get("target_os_build", "")) else ""
    matched_feature = target.get("target_feature_version", "") if _has_exact(report_text, target.get("target_feature_version", "")) else ""
    patch_matched, match_basis = identity_basis(matched_kb, matched_os_build, matched_feature)
    matched_version = matched_os_build or matched_kb or matched_feature or ""

    source_date = date_part(candidate.get("source_date"))
    target_release_date = date_part(target.get("target_release_date") or record.update_published_at)
    theme, workflow_area, platform, severity, sentiment = classify(report_text)

    row = make_evidence_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        source_type=str(candidate.get("source_type") or SOURCE_TYPE),
        source_name=str(candidate.get("source_name") or SOURCE_NAME),
        source_url=str(candidate.get("source_url") or ""),
        parent_title=str(candidate.get("parent_title") or ""),
        report_title=str(candidate.get("report_title") or ""),
        report_text=str(candidate.get("report_text") or ""),
        captured_at=captured_at,
        source_date=source_date,
        target_release_date=target_release_date,
        patch_version_matched=patch_matched,
        matched_version=matched_version,
        match_basis=match_basis,
        counted=False,
        exclusion_reason=None,
        matched_kb=matched_kb,
        matched_os_build=matched_os_build,
        matched_feature_version=matched_feature,
        issue_theme=theme,
        workflow_area=workflow_area,
        platform=platform,
        severity=severity,
        sentiment=sentiment,
        row_id=f"{PRODUCT_ID}-{slug(record.update_version)}-{slug(SOURCE_TYPE)}-{slug(str(candidate.get('source_url') or ''))}",
    )

    reason = windows_learn_qna_reason(target, str(candidate.get("source_url") or ""), source_date, report_text, matched_kb, matched_os_build, matched_feature)
    counted = reason is None
    row["counted"] = counted
    row["exclusion_reason"] = reason
    row["evidence_valid_for_current_patch"] = counted
    row["stale_due_to_patch_rollover"] = reason == "stale_due_to_patch_rollover"
    return row


def evaluate_candidates(record: PatchRecord, target: dict[str, Any], candidates: list[dict[str, Any]], captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = learn_qna.canonical_learn_qna_url(str(candidate.get("source_url") or ""))
        key = url.lower()
        if not url or key in seen:
            continue  # run-level duplicate URL dedup
        seen.add(key)
        row = row_from_candidate(record, target, {**candidate, "source_url": url}, captured_at)
        (accepted if row.get("counted") is True else rejected).append(row)
    return accepted, rejected


# --- record target + queries -------------------------------------------------

def record_target(record: PatchRecord) -> dict[str, Any]:
    front, _body = load_front_matter_and_body(record.path)
    return {
        "target_feature_version": str(front.get("target_feature_version") or "").strip(),
        "target_kb": str(front.get("target_kb") or "").strip(),
        "target_os_build": str(front.get("target_os_build") or "").strip(),
        "target_release_date": str(front.get("target_release_date") or "").strip(),
        "update_version": str(front.get("update_version") or record.update_version).strip(),
    }


def search_query_terms(target: dict[str, Any]) -> list[str]:
    """Exact-identity search terms only: KB and OS build. The feature train (24H2) is
    context, never a standalone search — searching it alone would surface the whole train."""
    terms: list[str] = []
    if target.get("target_kb"):
        terms.append(target["target_kb"])
    if target.get("target_os_build"):
        terms.append(target["target_os_build"])
    return terms


# --- method health -----------------------------------------------------------

def learn_qna_method_status(candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if accepted:
        return "partial" if errors else "success"
    if errors and (candidates or rejected):
        return "partial"
    if errors:
        if any(str(e.get("blocked_signature")) == "broken" or "feed_parse_failed" in str(e.get("reason") or "") for e in errors):
            return "broken"
        return "blocked"
    return "no_results"


def rejection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("exclusion_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def format_rejection_counts(rows: list[dict[str, Any]]) -> str:
    return ", ".join(f"{reason}={count}" for reason, count in sorted(rejection_counts(rows).items()))


def blocked_reason_from_errors(errors: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for error in errors:
        reason = str(error.get("reason") or "fetch_failed")
        counts[reason] = counts.get(reason, 0) + 1
    return "; ".join(f"{reason} x{count}" if count > 1 else reason for reason, count in counts.items())


def build_notes(target: dict[str, Any], candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]], query_terms: list[str]) -> str:
    parts = [
        "Microsoft Learn Q&A search RSS (learn.microsoft.com/api/search/rss) for microsoft-windows-11.",
        f"Searched exact terms: {', '.join(query_terms) if query_terms else 'none (record missing target KB/build)'}.",
        f"Exact KB/OS-build search attempted: {bool(query_terms)}.",
        f"Candidates {len(candidates)}, accepted {len(accepted)}, rejected {len(rejected)}.",
    ]
    if rejected:
        parts.append(f"Top rejections: {format_rejection_counts(rejected)}.")
    if errors:
        parts.append(f"Fetch failures: {len(errors)}.")
    parts.append("Candidates require exact KB/OS-build identity for the record's current patch, a concrete issue, a specific question URL, and source date on/after release before counting.")
    return " ".join(parts)


def health_for_method(record: PatchRecord, target: dict[str, Any], captured_at: str, candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]], query_terms: list[str]) -> dict[str, Any]:
    return method_health_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        method_id=METHOD_ID,
        source_type=SOURCE_TYPE,
        status=learn_qna_method_status(candidates, accepted, rejected, errors),
        candidates_found=len(candidates),
        accepted_reports=len(accepted),
        rejected_reports=len(rejected),
        blocked_reason=blocked_reason_from_errors(errors),
        last_run=captured_at,
        notes=build_notes(target, candidates, accepted, rejected, errors, query_terms),
    )


# --- collection --------------------------------------------------------------

def collect_for_record(record: PatchRecord, context: CollectorContext) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    captured_at = utc_now()
    target = record_target(record)
    query_terms = search_query_terms(target)
    errors: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    if query_terms:
        candidates = learn_qna.collect_learn_qna_candidates(
            queries=query_terms,
            context=context,
            errors=errors,
            source_type=SOURCE_TYPE,
            source_name=SOURCE_NAME,
        )
    accepted, rejected = evaluate_candidates(record, target, candidates, captured_at)
    health = [health_for_method(record, target, captured_at, candidates, accepted, rejected, errors, query_terms)]
    return accepted, rejected, health


class WindowsLearnQnaCollector(ProductCollector):
    product_id = PRODUCT_ID

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        records = generated_records(PRODUCT_ID, context.target_versions)
        results: list[dict[str, Any]] = []
        for record in records:
            accepted, rejected, health = collect_for_record(record, context)
            result: dict[str, Any] = {
                "product_id": PRODUCT_ID,
                "version": record.update_version,
                "mode": "write" if context.write else "dry-run",
                "record_path": str(record.path.relative_to(record.path.parents[2])),
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [row["source_url"] for row in accepted],
                "rejection_reasons": rejection_counts(rejected),
                "method_health": health,
            }
            if context.write:
                added, total, rows = append_evidence_rows(accepted)
                structured_count = len(counted_rows(rows, PRODUCT_ID, record.update_version))
                record_updated = apply_consensus_writeback(record.update_version) if accepted else False
                result.update({
                    "evidence_rows_added": added,
                    "evidence_rows_total": total,
                    "structured_count_for_version": structured_count,
                    "windows_record_updated": record_updated,
                })
            results.append(result)
        return results


def apply_consensus_writeback(update_version: str) -> bool:
    """Run the deterministic consensus writeback for one Windows version (used only in
    --write mode). The Windows identity gate in apply_consensus re-verifies every row
    against the record's current target_* before counting."""
    from apply_consensus_to_records import _apply_record_fields, _index_generated_records, run_dry_run

    records_index = _index_generated_records()
    results = run_dry_run(
        evidence_path=EVIDENCE_PATH,
        product_id_filter=PRODUCT_ID,
        is_candidate_mode=False,
        records_index=records_index,
        write_requested=True,
    )
    matches = [item for item in results if item["update_version"] == update_version]
    if len(matches) != 1 or not matches[0].get("would_write"):
        return False
    result = matches[0]
    record_path = records_index[(PRODUCT_ID, update_version)]["abs_path"]
    fields = dict(result["proposed_fields_if_written"])
    data, _body = load_front_matter_and_body(record_path)
    comparable = {key: value for key, value in fields.items() if key != "status_events_append"}
    if all(data.get(key) == value for key, value in comparable.items()):
        return False
    _apply_record_fields(record_path, fields)
    return True


def _dry_run_main(argv: list[str] | None = None) -> int:
    """Read-only local dry-run entry point. Hardcodes write=False, so this can NEVER write
    evidence or generated records — it only fetches Learn Q&A and prints diagnostics."""
    import argparse
    import json
    from datetime import datetime, timedelta, timezone

    parser = argparse.ArgumentParser(description="Windows Learn Q&A collector — read-only dry-run (no writeback).")
    parser.add_argument("--update-version", action="append", help="Exact Windows update_version filter (e.g. 24H2). Repeatable.")
    parser.add_argument("--since-days", type=int, help="Optional source-date lower bound relative to today.")
    parser.add_argument("--max-pages", type=int, default=1)
    args = parser.parse_args(argv)

    since = None
    if args.since_days is not None:
        since = (datetime.now(timezone.utc) - timedelta(days=max(0, args.since_days))).date().isoformat()
    context = CollectorContext(
        write=False,  # hardcoded: this entry point can never write
        since=since,
        max_pages=args.max_pages,
        target_versions=set(args.update_version) if args.update_version else None,
    )
    results = WindowsLearnQnaCollector().collect(context)
    print(json.dumps({"mode": "dry-run", "write": False, "products": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_dry_run_main())
