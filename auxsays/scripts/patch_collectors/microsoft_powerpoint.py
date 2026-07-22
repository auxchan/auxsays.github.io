"""Microsoft PowerPoint community-evidence collector (Microsoft Learn Q&A).

Discovers real Microsoft PowerPoint user reports from Microsoft Learn Q&A
(learn.microsoft.com/answers) via its search-RSS API, driving each search by the exact
*version identity* already captured on the generated record (``update_version`` /
``target_app_version`` / ``target_build`` / ``target_channel``). It then applies a fixed,
ordered, deterministic acceptance contract so a report counts ONLY when it names PowerPoint,
names the record's exact Version YYMM in context, is channel-consistent with the record
(Current Channel), does not carry a *conflicting* build, is dated on/after release, links to
a specific report URL, and describes a concrete post-install PowerPoint problem.

PowerPoint is NOT Windows: one Version YYMM maps to exactly one Current-Channel build, so
this collector keys on the version (with an *optional* build cross-check) and MUST NOT copy
the Windows KB / OS-build / servicing-train identity gate. The full Click-to-Run build is a
bonus disambiguator, never a prerequisite (repo doctrine — AGENTS.md "Confirmed report rule"
— counts on the exact version/patch, not the build).

Deterministic + repo-owned: no AI, no manual candidate approval. Discovery is keyword-anchored
(search by "PowerPoint <version>" / "Version <version>"); acceptance is a fixed ordered rule set.

Safety — default-off. This collector is NOT part of the always-on runner registry. It is
registered ONLY when ``AUXSAYS_ENABLE_POWERPOINT_CONSENSUS`` is the explicit canonical
``true`` (see run_patch_evidence_collection.build_collectors), and even then a scheduled
``--write`` never enables the flag (the workflow gates it to a manual dry_run only). Observe
it with the read-only dry-run first; it writes no evidence, no method health, and never
changes a PowerPoint record's verdict.

Read-only local dry-run (never writes evidence or records):
    cd auxsays/scripts && python -m patch_collectors.microsoft_powerpoint [--update-version 2605] [--since-days 90]
"""
from __future__ import annotations

import os
import re
from typing import Any

from .base import (
    CollectorContext,
    PatchRecord,
    ProductCollector,
    append_evidence_rows,
    date_part,
    exact_version_match,
    generated_records,
    load_front_matter_and_body,
    make_evidence_row,
    method_health_row,
    slug,
    source_date_passes,
    source_url_is_specific,
    text_describes_issue,
    utc_now,
)
from . import microsoft_learn_qna_source as learn_qna
from . import reddit_source

PRODUCT_ID = "microsoft-powerpoint"

LEARN_QNA_METHOD_ID = "learn_qna_search_rss"
LEARN_QNA_SOURCE_TYPE = "microsoft_learn_qna"
LEARN_QNA_SOURCE_NAME = "Microsoft Learn Q&A"

REDDIT_METHOD_ID = "reddit_community_search"
REDDIT_SOURCE_TYPE = "reddit_community_report"
REDDIT_SOURCE_NAME = "Reddit"
REDDIT_SUBREDDITS = ("powerpoint", "microsoft365", "Office365")
# Reddit is a documented CI-blocked fallback (PR #23). It is attempted ONLY when this flag is
# the explicit canonical "true"; otherwise it is honestly reported as method-health "disabled".
# It is never required for the pilot to pass, and never weakens the acceptance gates.
REDDIT_FALLBACK_ENV = "AUXSAYS_POWERPOINT_REDDIT_FALLBACK"


# --- deterministic content classifiers (no AI) -------------------------------
# Marketing/version identity: an Office Version is YYMM (year 2X, month 01-12), e.g. 2605.
YYMM_RE = re.compile(r"(?<![0-9.])(2\d(?:0[1-9]|1[0-2]))(?![0-9.])")
# Full Click-to-Run build, e.g. 20026.20076 (5 digits . 5 digits). Optional evidence.
BUILD_RE = re.compile(r"(?<![0-9.])(\d{4,6}\.\d{4,6})(?![0-9.])")

POWERPOINT_RE = re.compile(r"\b(?:microsoft\s+)?power\s?point\b", re.I)
# Other Office apps — only matters to reject app-only reports that never name PowerPoint.
OTHER_OFFICE_APP_RE = re.compile(r"\b(?:word|excel|outlook|teams|onenote|access|publisher)\b", re.I)

CURRENT_CHANNEL_RE = re.compile(r"\bcurrent\s+channel\b", re.I)
CURRENT_CHANNEL_PREVIEW_RE = re.compile(r"\bcurrent\s+channel\s*\(?\s*preview", re.I)
CONFLICTING_CHANNEL_RE = re.compile(
    r"\b(?:monthly\s+enterprise(?:\s+channel)?|semi[\s-]?annual(?:\s+enterprise)?(?:\s+channel)?|"
    r"beta\s+channel|insider(?:\s+(?:fast|slow|beta|preview))?|dev\s+channel)\b",
    re.I,
)
STORE_RE = re.compile(r"\b(?:microsoft\s+store|windows\s+store|store\s+(?:app|version)|uwp)\b", re.I)

LATEST_RE = re.compile(
    r"\b(?:latest|newest|most\s+recent|recent|last)\s+(?:update|patch|version|build|release)\b|"
    r"\bthis\s+month'?s\s+(?:update|patch)\b|\bafter\s+(?:the\s+)?(?:last|latest|recent)\s+update\b",
    re.I,
)

# Concrete post-install PowerPoint problems (a real regression report, not a how-to/feature ask).
POWERPOINT_ISSUE_RE = re.compile(
    r"\b(?:"
    r"crash(?:es|ing|ed)?|won'?t\s+(?:open|start|launch)|does\s+not\s+open|cannot\s+open|can'?t\s+open|"
    r"fail(?:s|ed|ing)?\s+to\s+(?:open|start|launch|save|export|load|respond)|"
    r"freez(?:e|es|ing|en)|hang(?:s|ing|ed)?|not\s+responding|"
    r"corrupt(?:s|ed|ion)?|damaged\s+(?:file|presentation|deck)|blank\s+(?:slide|presentation|deck)|"
    r"can'?t\s+save|cannot\s+save|save\s+(?:fail\w*|error)|unable\s+to\s+save|lost\s+(?:my\s+)?(?:work|slides|changes)|data\s+loss|"
    r"slide[\s-]?show\s+(?:fail\w*|crash\w*|black|freez\w*|won'?t\s+start|not\s+working)|presenter\s+view\s+(?:broken|not\s+working|black)|"
    r"export\s+(?:fail\w*|error|broken)|can'?t\s+export|animation[s]?\s+(?:broken|not\s+working|glitch\w*|regress\w*|stutter\w*)|"
    r"transition[s]?\s+(?:broken|not\s+working)|render(?:s|ing|ed)?\s+(?:issue|error|broken|wrong|incorrect)|"
    r"add[\s-]?in[s]?\s+(?:broken|not\s+working|crash\w*|incompatib\w*|fail\w*|disabled)|"
    r"(?:very\s+)?slow|lag(?:s|ging|gy)?|performance\s+(?:regress\w*|issue|problem)|high\s+cpu|memory\s+leak|"
    r"install(?:ation)?\s+(?:fail\w*|error|stuck|loop)|update\s+(?:fail\w*|error|broke\w*|stuck)|"
    r"broke\w*\s+after|stopped\s+working\s+after|no\s+longer\s+works?\s+after|not\s+working\s+after|regress\w*|"
    r"bug|glitch|error\s+message"
    r")\b",
    re.I,
)

HOW_TO_OR_FEATURE_RE = re.compile(
    r"\b(?:how\s+(?:do|to|can|would|should)\b|where\s+(?:is|do|can)\b|is\s+it\s+safe\s+to\b|"
    r"should\s+i\s+(?:install|update|upgrade)\b|which\s+version\b|what'?s\s+the\s+best\b|"
    r"feature\s+request|please\s+add|can\s+you\s+add|would\s+like\s+(?:to\s+see|a\s+feature|the\s+ability)|"
    r"is\s+there\s+a\s+way\s+to|how\s+about\s+adding)\b",
    re.I,
)
ANNOUNCE_OR_NOTE_RE = re.compile(
    r"\b(?:now\s+available|is\s+available|announc(?:e|es|ing|ed|ement)|general\s+availability|"
    r"rolling\s+out|is\s+released|has\s+been\s+released|release\s+notes|what'?s\s+new|change\s*log|"
    r"new\s+features|version\s+history)\b",
    re.I,
)


# --- version-in-context / drift -------------------------------------------------

def version_in_context(text: str, version: str) -> bool:
    """True when ``version`` (a Version YYMM) appears with an explicit version/product context,
    e.g. 'Version 2605', 'PowerPoint 2605', 'Microsoft PowerPoint Version 2605', or
    '2605 (Build ...)'. A bare four-digit number with no such context never qualifies."""
    v = re.escape(str(version or "").strip())
    if not v:
        return False
    return bool(
        re.search(rf"\b(?:version|ver\.?|build\s+version)\s+(?:no\.?\s*)?{v}\b", text, re.I)
        or re.search(rf"\bpower\s?point\s+(?:version\s+)?{v}\b", text, re.I)
        or re.search(rf"\bmicrosoft\s+365\s+(?:apps\s+)?(?:version\s+)?{v}\b", text, re.I)
        or re.search(rf"\bcurrent\s+channel\b[^\n]{{0,25}}\b{v}\b", text, re.I)
        or re.search(rf"(?<![0-9.]){v}(?![0-9.])\s*\(\s*build", text, re.I)
    )


def versions_in_context(text: str) -> set[str]:
    """Every Version YYMM that appears *in context* anywhere in ``text``."""
    found: set[str] = set()
    for match in YYMM_RE.finditer(text or ""):
        candidate = match.group(1)
        if version_in_context(text, candidate):
            found.add(candidate)
    return found


def _bare_version_present(text: str, version: str) -> bool:
    matched, _matched, _basis = exact_version_match(text or "", version)
    return bool(matched)


# --- channel / build / issue gates ---------------------------------------------

def channel_reason(text: str) -> str | None:
    """Reject reports explicitly tied to a channel that conflicts with the record's Current
    Channel identity. A Current-Channel mention or no channel mention passes. (All current
    PowerPoint records are Current Channel, and one Version YYMM maps to one Current-Channel
    build, so a bare version is not channel-ambiguous.)"""
    if CURRENT_CHANNEL_PREVIEW_RE.search(text or ""):
        return "channel_conflict"  # Current Channel (Preview) is a distinct channel
    current = bool(CURRENT_CHANNEL_RE.search(text or ""))
    if CONFLICTING_CHANNEL_RE.search(text or "") and not current:
        return "channel_conflict"
    if STORE_RE.search(text or "") and not current:
        return "store_identity_unmapped"
    return None


def build_check(text: str, target_build: str) -> tuple[str | None, bool]:
    """Optional full-build cross-check. Returns (exclusion_reason_or_None, build_matched).
    A build is never required; but if one or more full builds are named and the record's
    exact build is not among them, the report is rejected (it describes a different patch)."""
    builds = set(BUILD_RE.findall(text or ""))
    if not builds:
        return None, False
    target = str(target_build or "").strip()
    if target and target in builds:
        return None, True
    return "build_mismatch", False


def concrete_issue(text: str) -> bool:
    """A concrete post-install PowerPoint problem, not a how-to/feature/announcement."""
    strong = bool(POWERPOINT_ISSUE_RE.search(text or ""))
    if not (strong or text_describes_issue(text)):
        return False
    if HOW_TO_OR_FEATURE_RE.search(text or "") and not strong:
        return False
    return True


# --- theme classification (deterministic; no AI) -------------------------------

def classify(text: str) -> tuple[str, str, str, str, str]:
    lowered = (text or "").lower()
    if any(t in lowered for t in ("corrupt", "damaged", "data loss", "lost my work", "lost slides", "lost changes")):
        return "file corruption / data loss", "file integrity", "windows", "critical", "negative"
    if "can't save" in lowered or "cannot save" in lowered or "save fail" in lowered or "unable to save" in lowered:
        return "save failure", "save / storage", "windows", "high", "negative"
    if any(t in lowered for t in ("won't open", "wont open", "cannot open", "can't open", "fails to open", "won't launch", "won't start", "fails to launch")):
        return "launch / open failure", "startup", "windows", "high", "negative"
    if "slideshow" in lowered or "slide show" in lowered or "presenter view" in lowered:
        return "slideshow failure", "presenting", "windows", "high", "negative"
    if "export" in lowered:
        return "export failure", "export", "windows", "high", "negative"
    if "animation" in lowered or "transition" in lowered:
        return "animation / transition regression", "animation", "windows", "medium", "negative"
    if "add-in" in lowered or "add in" in lowered or "addin" in lowered:
        return "add-in incompatibility", "add-ins", "windows", "medium", "negative"
    if "render" in lowered or "display" in lowered or "blank slide" in lowered:
        return "rendering regression", "rendering", "windows", "medium", "negative"
    if any(t in lowered for t in ("slow", "lag", "performance", "high cpu", "memory leak")):
        return "performance regression", "performance", "windows", "medium", "negative"
    if "install" in lowered or "update fail" in lowered:
        return "install/update failure", "update", "windows", "high", "negative"
    if any(t in lowered for t in ("crash", "freeze", "hang", "not responding")):
        return "crash or hang", "system stability", "windows", "high", "negative"
    return "unspecified PowerPoint issue", "PowerPoint workflow", "windows", "medium", "negative"


# --- ordered, deterministic acceptance -----------------------------------------

def powerpoint_reason(target: dict[str, Any], source_url: str, source_date: str, parent_title: str, report_title: str, report_body: str) -> tuple[str | None, str, bool]:
    """Ordered acceptance for a PowerPoint candidate. Returns
    (exclusion_reason_or_None, match_basis, build_matched).

    ``target`` = the record identity (update_version / target_build / target_channel /
    target_release_date). ``parent_title``/``report_title`` are the thread title (used for
    reply-inheritance); ``report_body`` is the reply/description text (used for drift)."""
    version = str(target.get("update_version") or "").strip()
    target_build = str(target.get("target_build") or "").strip()
    target_release_date = str(target.get("target_release_date") or "").strip()
    title_text = f"{parent_title} {report_title}".strip()
    combined = f"{title_text}\n{report_body}".strip()

    match_basis = "no_exact_version"
    build_matched = False

    # 1. Specific report URL (search/category/landing pages are rejected).
    if not source_url_is_specific(source_url):
        return "no_specific_source_url", match_basis, build_matched
    # 2. Product attribution — PowerPoint must be named (report or parent thread).
    if not POWERPOINT_RE.search(combined):
        return "product_not_powerpoint", match_basis, build_matched
    # 3. Official announcement / release note (not a user report).
    if ANNOUNCE_OR_NOTE_RE.search(combined) and not concrete_issue(combined):
        return "official_announcement_not_user_report", match_basis, build_matched

    # 4. Exact version attribution (with reply-inheritance and drift guard).
    target_in_context = version_in_context(combined, version)
    target_in_title = version_in_context(title_text, version)
    target_in_body = version_in_context(report_body, version)
    other_versions = versions_in_context(combined) - {version}
    other_in_body = versions_in_context(report_body) - {version}
    if not target_in_context:
        if other_versions:
            return "different_version_not_target", match_basis, build_matched
        if _bare_version_present(combined, version):
            return "bare_version_no_context", match_basis, build_matched
        if LATEST_RE.search(combined):
            return "vague_latest_update", match_basis, build_matched
        return "missing_powerpoint_version", match_basis, build_matched
    # Drift: the target version is only inherited from the thread title, but the reply body
    # clearly names a *different* version in context -> the reply shifted patches.
    if other_in_body and not target_in_body and target_in_title:
        return "reply_drifted_to_other_version", match_basis, build_matched
    match_basis = "exact_version_current_channel"

    # 5. Channel consistency.
    channel = channel_reason(combined)
    if channel:
        return channel, match_basis, build_matched
    # 6. Optional full-build cross-check (bonus disambiguator, never required).
    build_reason, build_matched = build_check(combined, target_build)
    if build_reason:
        return build_reason, match_basis, build_matched
    if build_matched:
        match_basis = "exact_version_channel_build"
    # 7. Date gate — on/after release; pre-release/undated rejected.
    if source_date_passes(source_date, target_release_date) is False:
        return "date_before_release_or_undated", match_basis, build_matched
    # 8. Concrete post-install issue.
    if not concrete_issue(combined):
        return "not_a_concrete_powerpoint_issue", match_basis, build_matched
    return None, match_basis, build_matched


def row_from_candidate(record: PatchRecord, target: dict[str, Any], candidate: dict[str, Any], captured_at: str) -> dict[str, Any]:
    parent_title = str(candidate.get("parent_title") or "")
    report_title = str(candidate.get("report_title") or "")
    report_body = str(candidate.get("report_text") or "")
    combined = f"{parent_title} {report_title}\n{report_body}".strip()
    source_url = str(candidate.get("source_url") or "")
    source_date = date_part(candidate.get("source_date"))
    target_release_date = date_part(target.get("target_release_date") or record.update_published_at)
    version = str(target.get("update_version") or record.update_version).strip()

    reason, match_basis, build_matched = powerpoint_reason(
        target, source_url, source_date, parent_title, report_title, report_body,
    )
    version_matched = version_in_context(combined, version)
    matched_version = version if version_matched else ""
    theme, workflow_area, platform, severity, sentiment = classify(combined)

    row = make_evidence_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        source_type=str(candidate.get("source_type") or LEARN_QNA_SOURCE_TYPE),
        source_name=str(candidate.get("source_name") or LEARN_QNA_SOURCE_NAME),
        source_url=source_url,
        parent_title=parent_title,
        report_title=str(candidate.get("report_title") or ""),
        report_text=str(candidate.get("report_text") or ""),
        captured_at=captured_at,
        source_date=source_date,
        target_release_date=target_release_date,
        patch_version_matched=version_matched,
        matched_version=matched_version,
        match_basis=match_basis,
        counted=False,
        exclusion_reason=None,
        applicability="microsoft-powerpoint",
        issue_theme=theme,
        workflow_area=workflow_area,
        platform=platform,
        severity=severity,
        sentiment=sentiment,
        row_id=f"{PRODUCT_ID}-{slug(record.update_version)}-{slug(str(candidate.get('source_type') or LEARN_QNA_SOURCE_TYPE))}-{slug(source_url)}",
    )
    row["counted"] = reason is None
    row["exclusion_reason"] = reason
    return row


def evaluate_candidates(record: PatchRecord, target: dict[str, Any], candidates: list[dict[str, Any]], captured_at: str, seen: set[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen = seen if seen is not None else set()
    for candidate in candidates:
        url = str(candidate.get("source_url") or "").strip().rstrip("/")
        key = url.lower()
        if not url or key in seen:
            continue  # run-level canonical-URL dedup (across methods)
        seen.add(key)
        row = row_from_candidate(record, target, candidate, captured_at)
        (accepted if row.get("counted") is True else rejected).append(row)
    return accepted, rejected


# --- record target + queries -------------------------------------------------

def record_target(record: PatchRecord) -> dict[str, Any]:
    front, _body = load_front_matter_and_body(record.path)
    return {
        "update_version": str(front.get("update_version") or record.update_version).strip(),
        "target_app_version": str(front.get("target_app_version") or front.get("update_version") or "").strip(),
        "target_build": str(front.get("target_build") or "").strip(),
        "target_channel": str(front.get("target_channel") or "").strip(),
        "target_release_date": str(front.get("update_published_at") or record.update_published_at or "").strip(),
    }


def search_query_terms(target: dict[str, Any]) -> list[str]:
    """Exact-version discovery terms. The version is searched with product/version context so
    the RSS surfaces PowerPoint threads that name the exact patch; the build is an optional
    extra query (bonus disambiguator), never a prerequisite."""
    version = str(target.get("update_version") or "").strip()
    terms: list[str] = []
    if version:
        terms.append(f"PowerPoint {version}")
        terms.append(f"PowerPoint Version {version}")
    build = str(target.get("target_build") or "").strip()
    if version and build:
        terms.append(f"PowerPoint {build}")
    return terms


# --- method health -----------------------------------------------------------

NEAR_MISS_REASONS = {"bare_version_no_context", "different_version_not_target", "build_mismatch", "channel_conflict", "reply_drifted_to_other_version"}


def rejection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("exclusion_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def format_rejection_counts(rows: list[dict[str, Any]]) -> str:
    return ", ".join(f"{reason}={count}" for reason, count in sorted(rejection_counts(rows).items()))


def learn_qna_method_status(candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if accepted:
        return "partial" if errors else "success"
    if errors and (candidates or rejected):
        return "partial"
    if errors:
        if any("feed_parse_failed" in str(e.get("reason") or "") or str(e.get("blocked_signature")) == "broken" for e in errors):
            return "broken"
        return "blocked"
    # Reachable, nothing accepted. "low_confidence" when relevant-looking PowerPoint threads
    # were found but narrowly missed attribution; plain "no_results" otherwise.
    if rejected and any(str(r.get("exclusion_reason")) in NEAR_MISS_REASONS for r in rejected):
        return "low_confidence"
    return "no_results"


def reddit_method_status(attempted: bool, candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if not attempted:
        return "disabled"
    if accepted:
        return "partial" if errors else "success"
    if errors and not candidates:
        return "blocked"
    if errors:
        return "partial"
    return "no_results"


def blocked_reason_from_errors(errors: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for error in errors:
        reason = str(error.get("reason") or "fetch_failed")
        counts[reason] = counts.get(reason, 0) + 1
    return "; ".join(f"{reason} x{count}" if count > 1 else reason for reason, count in counts.items())


def health_row(record: PatchRecord, method_id: str, source_type: str, status: str, candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]], captured_at: str, notes: str) -> dict[str, Any]:
    return method_health_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        method_id=method_id,
        source_type=source_type,
        status=status,
        candidates_found=len(candidates),
        accepted_reports=len(accepted),
        rejected_reports=len(rejected),
        blocked_reason=blocked_reason_from_errors(errors),
        last_run=captured_at,
        notes=notes,
    )


# --- collection --------------------------------------------------------------

def reddit_fallback_enabled(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(REDDIT_FALLBACK_ENV, "")).strip().lower() == "true"


def collect_for_record(record: PatchRecord, context: CollectorContext, env: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    captured_at = utc_now()
    target = record_target(record)
    query_terms = search_query_terms(target)
    seen: set[str] = set()

    # PRIMARY — Microsoft Learn Q&A (proven CI-reachable, keyless).
    lq_errors: list[dict[str, Any]] = []
    lq_candidates: list[dict[str, Any]] = []
    if query_terms:
        lq_candidates = learn_qna.collect_learn_qna_candidates(
            queries=query_terms,
            context=context,
            errors=lq_errors,
            source_type=LEARN_QNA_SOURCE_TYPE,
            source_name=LEARN_QNA_SOURCE_NAME,
        )
    lq_accepted, lq_rejected = evaluate_candidates(record, target, lq_candidates, captured_at, seen)
    lq_status = learn_qna_method_status(lq_candidates, lq_accepted, lq_rejected, lq_errors)
    lq_notes = (
        "Microsoft Learn Q&A search RSS (learn.microsoft.com/api/search/rss) for microsoft-powerpoint. "
        f"Searched: {', '.join(query_terms) if query_terms else 'none (record missing version)'}. "
        f"Candidates {len(lq_candidates)}, accepted {len(lq_accepted)}, rejected {len(lq_rejected)}. "
        + (f"Top rejections: {format_rejection_counts(lq_rejected)}. " if lq_rejected else "")
        + "Counts only when the report names PowerPoint, the exact Version YYMM in context, is Current-Channel-consistent, "
        "carries no conflicting build, has a specific URL, is dated on/after release, and describes a concrete issue."
    )
    health = [health_row(record, LEARN_QNA_METHOD_ID, LEARN_QNA_SOURCE_TYPE, lq_status, lq_candidates, lq_accepted, lq_rejected, lq_errors, captured_at, lq_notes)]

    # FALLBACK — Reddit (documented CI-blocked, PR #23). Attempted only behind an explicit
    # flag; honestly reported as "disabled" otherwise. Same acceptance gates, never required.
    rd_attempted = reddit_fallback_enabled(env)
    rd_errors: list[dict[str, Any]] = []
    rd_candidates: list[dict[str, Any]] = []
    rd_accepted: list[dict[str, Any]] = []
    rd_rejected: list[dict[str, Any]] = []
    if rd_attempted and query_terms:
        version = str(target.get("update_version") or "").strip()
        rd_candidates = reddit_source.collect_reddit_candidates(
            subreddits=REDDIT_SUBREDDITS,
            queries=[f"PowerPoint {version}", f"Version {version}"],
            context=context,
            errors=rd_errors,
            source_type=REDDIT_SOURCE_TYPE,
            version_hints=[version] if version else None,
        )
        rd_accepted, rd_rejected = evaluate_candidates(record, target, rd_candidates, captured_at, seen)
    rd_status = reddit_method_status(rd_attempted, rd_candidates, rd_accepted, rd_rejected, rd_errors)
    rd_notes = (
        f"Reddit community search across {', '.join('r/' + s for s in REDDIT_SUBREDDITS)}. "
        + ("Fallback disabled by default (documented CI-blocked, PR #23); enable with "
           f"{REDDIT_FALLBACK_ENV}=true. Not required for the pilot." if not rd_attempted
           else f"Candidates {len(rd_candidates)}, accepted {len(rd_accepted)}, rejected {len(rd_rejected)}. Same acceptance gates as Learn Q&A.")
    )
    health.append(health_row(record, REDDIT_METHOD_ID, REDDIT_SOURCE_TYPE, rd_status, rd_candidates, rd_accepted, rd_rejected, rd_errors, captured_at, rd_notes))

    accepted = lq_accepted + rd_accepted
    rejected = lq_rejected + rd_rejected
    return accepted, rejected, health


class PowerPointLearnQnaCollector(ProductCollector):
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
                "record_path": str(record.path.name),
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [row["source_url"] for row in accepted],
                "rejection_reasons": rejection_counts(rejected),
                "method_health": health,
            }
            if context.write:
                # Evidence-only pilot: append accepted rows; NEVER change the PowerPoint
                # record's verdict / consensus fields here (activation is a separate step).
                added, total, _rows = append_evidence_rows(accepted)
                result.update({"evidence_rows_added": added, "evidence_rows_total": total})
            results.append(result)
        return results


def _dry_run_main(argv: list[str] | None = None) -> int:
    """Read-only local dry-run entry point. Hardcodes write=False, so this can NEVER write
    evidence or generated records — it only fetches Learn Q&A and prints diagnostics."""
    import argparse
    import json
    from datetime import datetime, timedelta, timezone

    parser = argparse.ArgumentParser(description="PowerPoint Learn Q&A collector — read-only dry-run (no writeback).")
    parser.add_argument("--update-version", action="append", help="Exact PowerPoint update_version filter (e.g. 2605). Repeatable.")
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
    results = PowerPointLearnQnaCollector().collect(context)
    print(json.dumps({"mode": "dry-run", "write": False, "products": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_dry_run_main())
