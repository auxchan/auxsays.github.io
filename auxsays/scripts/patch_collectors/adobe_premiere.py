"""Adobe Premiere Pro production evidence collector.

This collector discovers public Adobe Community bug-report pages, then applies
the same deterministic evidence gates used by the shared AUXSAYS evidence
pipeline. It never treats Adobe official notes or broad forum/search pages as
community consensus.
"""
from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError

from .base import (
    EVIDENCE_PATH,
    CollectorContext,
    PatchRecord,
    ProductCollector,
    append_evidence_rows,
    apply_acceptance_gates,
    counted_rows,
    date_part,
    exact_version_match,
    generated_records,
    load_evidence,
    load_front_matter_and_body,
    make_evidence_row,
    method_health_row,
    slug,
    utc_now,
)

PRODUCT_ID = "adobe-premiere-pro"
SOURCE_TYPE = "adobe_community_bug_report"
SOURCE_NAME = "Adobe Community Bug Report"
CREATIVE_COW_SOURCE_TYPE = "creativecow_forum_report"
CREATIVE_COW_SOURCE_NAME = "Creative COW Premiere Pro Forum"
ADOBE_SEARCH_URL = "https://community.adobe.com/t5/forums/searchpage/tab/message"
ADOBE_PREMIERE_BUG_TAB_BASE_URL = "https://community.adobe.com/t5/premiere-pro/ct-p/ct-premiere-pro"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
WAYBACK_CDX_URL = "https://web.archive.org/cdx"
WAYBACK_SNAPSHOT_BASE_URL = "https://web.archive.org/web"
CREATIVE_COW_FORUM_URL = "https://creativecow.net/forums/forum/adobe-premiere-pro/"
BRAVE_SEARCH_API_KEY_ENV = "BRAVE_SEARCH_API_KEY"
MAX_BRAVE_QUERIES_PER_RUN = 4
MAX_SEARCH_QUERIES_PER_RUN = 2
MAX_SEARCH_PAGES_PER_QUERY = 1
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "close",
    "User-Agent": "Mozilla/5.0 (compatible; AUXSAYS-Premiere-Evidence-Collector/1.0; +https://auxsays.com/)",
}
PREMIERE_PRODUCT_RE = re.compile(r"\b(?:adobe\s+)?premiere\s+pro\b", flags=re.I)
BUILD_65_RE = re.compile(r"\bbuild\s*65\b", flags=re.I)
PRE_RELEASE_RE = re.compile(
    r"\b(?:public\s+beta|beta|pre[-\s]?release|prerelease)\s+(?:premiere\s+pro\s+)?26\.2(?:\.0)?\b|\b26\.2(?:\.0)?\s+(?:public\s+beta|beta|pre[-\s]?release|prerelease)\b",
    flags=re.I,
)
SPECIFIC_ADOBE_BUG_URL_RE = re.compile(
    r"^/(?:bug-reports-\d+/[^/?#]+-\d+|t5/premiere-pro-bugs/[^/?#]+/(?:idi|td)-p/\d+)/?$",
    flags=re.I,
)
SPECIFIC_CREATIVE_COW_THREAD_RE = re.compile(r"^/forums/thread/[^/?#]+/?$", flags=re.I)
STRONG_ISSUE_RE = re.compile(
    r"\b(?:crash(?:es|ed|ing)?|freez(?:e|es|ing|en)|hang(?:s|ing)?|lag(?:gy)?|slow(?:down)?|sluggish|fail(?:ed|s|ure|ing)?|error|bug|broke|broken|regression|rollback|revert(?:ed|ing)?|export|render|install(?:ation)?|compatib(?:le|ility)|plugin|project\s+(?:open|opening|load|loading)|timeline|media|decode|audio|video|corrupt(?:ed|ion)?|data\s+loss)\b",
    flags=re.I,
)
HOW_TO_RE = re.compile(
    r"\b(?:how\s+do\s+i|how\s+to|can\s+someone\s+explain|where\s+is|feature\s+request|requesting\s+a\s+feature)\b",
    flags=re.I,
)
OFFICIAL_OR_GENERIC_RE = re.compile(
    r"\b(?:release\s+notes|what'?s\s+new|announcement|download|version\s+history|new\s+features)\b",
    flags=re.I,
)


class AdobeCommunityAccessError(RuntimeError):
    def __init__(self, reason: str, *, status: int | None = None, content_type: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.content_type = content_type


class BraveSearchAccessError(RuntimeError):
    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class WaybackAccessError(RuntimeError):
    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class AdobePremiereCollector(ProductCollector):
    product_id = PRODUCT_ID

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        records = generated_records(PRODUCT_ID, context.target_versions, include_archived=bool(context.target_versions))
        results: list[dict[str, Any]] = []
        for record in records:
            accepted, rejected, method_health = collect_for_record(record, context)
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
                "method_health": method_health,
            }
            if context.write:
                added, total, rows = append_evidence_rows(accepted)
                structured_count = len(counted_rows(rows, PRODUCT_ID, record.update_version))
                record_updated = False
                if accepted:
                    record_updated = apply_consensus_writeback(record.update_version)
                result.update({
                    "evidence_rows_added": added,
                    "evidence_rows_total": total,
                    "structured_count_for_version": structured_count,
                    "premiere_record_updated": record_updated,
                })
            results.append(result)
        return results


def collect_for_record(record: PatchRecord, context: CollectorContext) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    captured_at = utc_now()
    method_results: list[dict[str, Any]] = []

    for method_id, collector in (
        ("adobe_community_search", adobe_community_search_candidates),
        ("adobe_community_bug_tab_index", adobe_community_bug_tab_candidates),
        ("adobe_community_known_url_recheck", adobe_community_known_url_candidates),
        ("brave_search_api", brave_search_api_candidates),
        ("wayback_snapshot_recheck", wayback_snapshot_recheck_candidates),
        ("creativecow_forum_index", creativecow_forum_index_candidates),
        ("creativecow_brave_search", creativecow_brave_search_candidates),
    ):
        errors: list[dict[str, Any]] = []
        candidates = collector(record, context, errors)
        accepted, rejected = evaluate_candidates(record, candidates, captured_at)
        method_results.append({
            "method_id": method_id,
            "candidates": candidates,
            "accepted": accepted,
            "rejected": rejected,
            "errors": errors,
        })

    accepted = merge_rows_by_url([row for result in method_results for row in result["accepted"]])
    rejected = merge_rows_by_url([row for result in method_results for row in result["rejected"] if not row_is_accepted_url(row, accepted)])
    health = [health_for_method(record, captured_at, result) for result in method_results]
    return accepted, rejected, health


def adobe_community_search_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    max_queries = min(MAX_SEARCH_QUERIES_PER_RUN, max(1, context.max_pages), len(search_queries(record)))
    max_pages = min(MAX_SEARCH_PAGES_PER_QUERY, max(1, context.max_pages))
    for query in search_queries(record)[:max_queries]:
        for page in range(1, max_pages + 1):
            url = search_url(query, page)
            try:
                html_text = request_text(url)
            except Exception as exc:
                errors.append({"source_url": url, "reason": f"adobe_community_search_fetch_failed:{error_reason(exc)}"})
                if error_is_blocked(exc):
                    return candidates
                break
            links = extract_report_links(html_text)
            if not links:
                break
            candidates.extend(candidates_from_report_links(links, context, errors, seen_urls, "adobe_community_search"))
    return candidates


def adobe_community_bug_tab_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for page in range(1, max(1, context.max_pages) + 1):
        url = bug_tab_url(page)
        try:
            html_text = request_text(url)
        except Exception as exc:
            errors.append({"source_url": url, "reason": f"adobe_community_bug_tab_fetch_failed:{error_reason(exc)}"})
            if error_is_blocked(exc):
                break
            continue
        links = extract_report_links(html_text)
        if not links:
            if page == 1:
                continue
            break
        before = len(candidates)
        candidates.extend(candidates_from_report_links(links, context, errors, seen_urls, "adobe_community_bug_tab_index"))
        if len(candidates) == before and page > 1:
            break
    return candidates


def adobe_community_known_url_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    urls = known_candidate_urls(record)
    seen_urls: set[str] = set()
    return candidates_from_report_links(urls, context, errors, seen_urls, "adobe_community_known_url_recheck")


def brave_search_api_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = os.environ.get(BRAVE_SEARCH_API_KEY_ENV, "").strip()
    if not api_key:
        errors.append({"source_url": BRAVE_SEARCH_URL, "reason": f"missing_{BRAVE_SEARCH_API_KEY_ENV}"})
        return []

    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for link in brave_discovered_report_links(record, context, errors, "brave_search_fetch_failed"):
        candidates.extend(candidates_from_report_links([link], context, errors, seen_urls, "brave_search_api"))
    return candidates


def wayback_snapshot_recheck_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    links = known_candidate_urls(record)

    brave_errors: list[dict[str, Any]] = []
    brave_links = brave_discovered_report_links(record, context, brave_errors, "wayback_brave_search_fetch_failed")
    if brave_links:
        links.extend(brave_links)
    elif not links:
        errors.extend(brave_errors)

    for link in dedupe(links):
        canonical = canonical_adobe_url(link)
        if not canonical or canonical.lower() in seen_urls or not adobe_report_url_is_specific(canonical):
            continue
        seen_urls.add(canonical.lower())
        snapshot_url = latest_wayback_snapshot_url(canonical, errors)
        if not snapshot_url:
            continue
        try:
            page_html = request_text(snapshot_url)
            candidate = adobe_bug_report_candidate(
                canonical,
                page_html,
                source_name="Adobe Community Bug Report via Wayback",
                archive_url=snapshot_url,
            )
        except Exception as exc:
            errors.append({"source_url": snapshot_url, "reason": f"wayback_snapshot_fetch_failed:{error_reason(exc)}"})
            continue
        if not candidate:
            continue
        if context.since and candidate.get("source_date") and date_part(candidate["source_date"]) < context.since:
            continue
        candidates.append(candidate)
    return candidates


def brave_discovered_report_links(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]], reason_prefix: str) -> list[str]:
    api_key = os.environ.get(BRAVE_SEARCH_API_KEY_ENV, "").strip()
    if not api_key:
        errors.append({"source_url": BRAVE_SEARCH_URL, "reason": f"missing_{BRAVE_SEARCH_API_KEY_ENV}"})
        return []
    links: list[str] = []
    max_queries = min(MAX_BRAVE_QUERIES_PER_RUN, max(1, context.max_pages), len(brave_search_queries(record)))
    for query in brave_search_queries(record)[:max_queries]:
        url = brave_search_url(query)
        try:
            payload = request_json(url, api_key=api_key)
        except Exception as exc:
            errors.append({"source_url": url, "reason": f"{reason_prefix}:{error_reason(exc)}"})
            if error_is_blocked(exc):
                break
            continue
        links.extend(extract_brave_result_links(payload))
    return dedupe(links)


def candidates_from_report_links(
    links: list[str],
    context: CollectorContext,
    errors: list[dict[str, Any]],
    seen_urls: set[str],
    method_id: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for link in links:
        canonical = canonical_adobe_url(link)
        if not canonical or canonical.lower() in seen_urls:
            continue
        seen_urls.add(canonical.lower())
        if not adobe_report_url_is_specific(canonical):
            continue
        try:
            page_html = request_text(canonical)
            candidate = adobe_bug_report_candidate(canonical, page_html)
        except Exception as exc:
            errors.append({"source_url": canonical, "reason": f"{method_id}_report_fetch_failed:{error_reason(exc)}"})
            continue
        if not candidate:
            continue
        if context.since and candidate.get("source_date") and date_part(candidate["source_date"]) < context.since:
            continue
        candidates.append(candidate)
    return candidates


def bug_tab_url(page: int) -> str:
    params = {
        "tabid": "bugs",
        "sort": "latest_replies",
        "filter": "all",
        "lang": "all",
    }
    if page > 1:
        params["page"] = str(page)
    return f"{ADOBE_PREMIERE_BUG_TAB_BASE_URL}?{urllib.parse.urlencode(params)}"


def known_candidate_urls(record: PatchRecord) -> list[str]:
    urls: list[str] = []
    try:
        rows = load_evidence()
    except Exception:
        rows = []
    for row in rows:
        if str(row.get("product_id") or "").strip() != PRODUCT_ID:
            continue
        if str(row.get("update_version") or "").strip() != record.update_version:
            continue
        url = canonical_adobe_url(str(row.get("source_url") or ""))
        if adobe_report_url_is_specific(url):
            urls.append(url)
    return dedupe(urls)



def creativecow_forum_index_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for page in range(1, min(max(1, context.max_pages), 3) + 1):
        url = creativecow_forum_page_url(page)
        try:
            html_text = request_text(url)
        except Exception as exc:
            errors.append({"source_url": url, "reason": f"creativecow_forum_index_fetch_failed:{error_reason(exc)}"})
            if error_is_blocked(exc):
                break
            continue
        links = extract_creativecow_thread_links(html_text)
        if not links:
            break
        before = len(candidates)
        candidates.extend(candidates_from_creativecow_links(links, context, errors, seen_urls, "creativecow_forum_index"))
        if len(candidates) == before and page > 1:
            break
    return candidates


def creativecow_brave_search_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = os.environ.get(BRAVE_SEARCH_API_KEY_ENV, "").strip()
    if not api_key:
        errors.append({"source_url": BRAVE_SEARCH_URL, "reason": f"missing_{BRAVE_SEARCH_API_KEY_ENV}"})
        return []
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    max_queries = min(MAX_BRAVE_QUERIES_PER_RUN, max(1, context.max_pages), len(creativecow_brave_search_queries(record)))
    for query in creativecow_brave_search_queries(record)[:max_queries]:
        url = brave_search_url(query)
        try:
            payload = request_json(url, api_key=api_key)
        except Exception as exc:
            errors.append({"source_url": url, "reason": f"creativecow_brave_search_fetch_failed:{error_reason(exc)}"})
            if error_is_blocked(exc):
                break
            continue
        candidates.extend(candidates_from_creativecow_links(extract_creativecow_brave_result_links(payload), context, errors, seen_urls, "creativecow_brave_search"))
    return candidates


def candidates_from_creativecow_links(
    links: list[str],
    context: CollectorContext,
    errors: list[dict[str, Any]],
    seen_urls: set[str],
    method_id: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for link in links:
        canonical = canonical_creativecow_url(link)
        if not canonical or canonical.lower() in seen_urls:
            continue
        seen_urls.add(canonical.lower())
        if not creativecow_thread_url_is_specific(canonical):
            continue
        try:
            page_html = request_text(canonical)
            candidate = creativecow_thread_candidate(canonical, page_html)
        except Exception as exc:
            errors.append({"source_url": canonical, "reason": f"{method_id}_thread_fetch_failed:{error_reason(exc)}"})
            continue
        if not candidate:
            continue
        if context.since and candidate.get("source_date") and date_part(candidate["source_date"]) < context.since:
            continue
        candidates.append(candidate)
    return candidates

def health_for_method(record: PatchRecord, captured_at: str, result: dict[str, Any]) -> dict[str, Any]:
    method_id = str(result["method_id"])
    candidates = list(result["candidates"])
    accepted = list(result["accepted"])
    rejected = list(result["rejected"])
    errors = list(result["errors"])
    blocked_reason = blocked_reason_from_errors(errors)
    notes = method_notes(method_id, candidates, accepted, rejected, errors)
    return method_health_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        method_id=method_id,
        source_type=method_source_type(method_id),
        status=adobe_community_method_status(candidates, accepted, rejected, errors),
        candidates_found=len(candidates),
        accepted_reports=len(accepted),
        rejected_reports=len(rejected),
        blocked_reason=blocked_reason,
        last_run=captured_at,
        notes=notes,
    )


def method_source_type(method_id: str) -> str:
    if method_id.startswith("creativecow"):
        return CREATIVE_COW_SOURCE_TYPE
    return SOURCE_TYPE


def method_notes(
    method_id: str,
    candidates: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> str:
    labels = {
        "adobe_community_search": "Adobe Community search",
        "adobe_community_bug_tab_index": "Adobe Community Premiere bug-tab listing",
        "adobe_community_known_url_recheck": "Known Adobe Community bug-report URL recheck",
        "brave_search_api": "Brave Search API fallback",
        "wayback_snapshot_recheck": "Wayback snapshot recheck",
        "creativecow_forum_index": "Creative COW Premiere Pro forum index",
        "creativecow_brave_search": "Creative COW Brave Search fallback",
    }
    notes = f"{labels.get(method_id, method_id)} discovers candidate URLs only; accepted rows still require exact product, version, date, URL, and issue gates."
    if method_id == "adobe_community_search":
        notes = f"{notes} Search requests are deliberately capped so rate limiting moves the collector to fallback methods instead of retrying the blocked endpoint repeatedly."
    if method_id == "brave_search_api":
        notes = f"{notes} This method reads {BRAVE_SEARCH_API_KEY_ENV} from the workflow environment, uses it only as an API header, and never logs the token."
    if method_id == "wayback_snapshot_recheck":
        notes = f"{notes} This method verifies blocked Adobe Community report pages through public Wayback snapshots of the same specific report URL when enough archived text is available."
    if method_id in {"creativecow_forum_index", "creativecow_brave_search"}:
        notes = f"{notes} This non-Adobe source is used only for specific Creative COW Premiere Pro forum threads that explicitly match the same patch/version and concrete-issue gates."
    if errors:
        notes = f"{notes} Fetch failures: {len(errors)}."
    if rejected and not accepted:
        notes = f"{notes} Rejected candidates: {format_rejection_counts(rejected)}."
    return notes


def merge_rows_by_url(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        url = canonical_evidence_url(str(row.get("source_url") or ""))
        if not url or url.lower() in seen:
            continue
        seen.add(url.lower())
        merged.append(row)
    return merged


def row_is_accepted_url(row: dict[str, Any], accepted: list[dict[str, Any]]) -> bool:
    url = canonical_evidence_url(str(row.get("source_url") or ""))
    return bool(url) and any(canonical_evidence_url(str(item.get("source_url") or "")).lower() == url.lower() for item in accepted)


def error_is_blocked(exc: Exception) -> bool:
    reason = error_reason(exc).lower()
    return any(token in reason for token in ("blocked", "challenge", "captcha", "rate_limited", "access_denied"))


def search_queries(record: PatchRecord) -> list[str]:
    version = record.update_version
    queries = [
        f'"Premiere Pro {version}" crash',
        f'"Premiere Pro {version}" lag',
        f'"Premiere Pro {version}" freeze',
        f'"Premiere Pro {version}" export',
        f'"Adobe Premiere Pro {version}" bug',
    ]
    if version == "26.2":
        queries.append('"Premiere Pro 26.2.0" "Build 65"')
    return dedupe(queries)


def search_url(query: str, page: int) -> str:
    params = {
        "advanced": "false",
        "allow_punctuation": "false",
        "q": query,
    }
    if page > 1:
        params["page"] = str(page)
    return f"{ADOBE_SEARCH_URL}?{urllib.parse.urlencode(params)}"


def brave_search_queries(record: PatchRecord) -> list[str]:
    version = record.update_version
    queries = [
        f'site:community.adobe.com/bug-reports-728 "Premiere Pro" "{version}"',
        f'site:community.adobe.com/bug-reports-728 "Adobe Premiere Pro {version}"',
    ]
    if re.fullmatch(r"\d+\.\d+", version or ""):
        queries.append(f'site:community.adobe.com/bug-reports-728 "Premiere Pro" "{version}.0"')
    if version == "26.2":
        queries.append('site:community.adobe.com/bug-reports-728 "Build 65" "Premiere Pro"')
    return dedupe(queries)[:MAX_BRAVE_QUERIES_PER_RUN]


def brave_search_url(query: str) -> str:
    params = {
        "q": query,
        "count": "10",
        "safesearch": "moderate",
        "search_lang": "en",
        "country": "us",
        "text_decorations": "false",
    }
    return f"{BRAVE_SEARCH_URL}?{urllib.parse.urlencode(params)}"



def creativecow_forum_page_url(page: int) -> str:
    if page <= 1:
        return CREATIVE_COW_FORUM_URL
    return urllib.parse.urljoin(CREATIVE_COW_FORUM_URL, f"page/{page}/")


def creativecow_brave_search_queries(record: PatchRecord) -> list[str]:
    version = record.update_version
    queries = [
        f'site:creativecow.net/forums/thread "Premiere Pro" "{version}"',
        f'site:creativecow.net/forums/thread "Adobe Premiere Pro {version}"',
        f'site:creativecow.net/forums/thread "PPro" "{version}"',
    ]
    if re.fullmatch(r"\d+\.\d+", version or ""):
        queries.append(f'site:creativecow.net/forums/thread "Premiere Pro" "{version}.0"')
    if version == "26.2":
        queries.append('site:creativecow.net/forums/thread "Build 65" "Premiere Pro"')
    return dedupe(queries)[:MAX_BRAVE_QUERIES_PER_RUN]


def extract_creativecow_thread_links(html_text: str) -> list[str]:
    links: list[str] = []
    for raw in re.findall(r"""href=["']([^"']+)["']""", html_text or "", flags=re.I):
        url = html.unescape(raw)
        if not url.startswith(("http://", "https://")):
            url = urllib.parse.urljoin(CREATIVE_COW_FORUM_URL, url)
        canonical = canonical_creativecow_url(url)
        if creativecow_thread_url_is_specific(canonical):
            links.append(canonical)
    return dedupe(links)


def extract_creativecow_brave_result_links(payload: dict[str, Any]) -> list[str]:
    links: list[str] = []
    web_results = payload.get("web", {}).get("results", []) if isinstance(payload, dict) else []
    if not isinstance(web_results, list):
        return []
    for result in web_results:
        if not isinstance(result, dict):
            continue
        canonical = canonical_creativecow_url(str(result.get("url") or "").strip())
        if creativecow_thread_url_is_specific(canonical):
            links.append(canonical)
    return dedupe(links)


def creativecow_thread_candidate(url: str, html_text: str) -> dict[str, str] | None:
    canonical = canonical_creativecow_url(url)
    if not creativecow_thread_url_is_specific(canonical):
        return None
    title = extract_title(html_text) or canonical
    text = clean_html(html_text)
    if not text:
        return None
    return {
        "source_type": CREATIVE_COW_SOURCE_TYPE,
        "source_name": CREATIVE_COW_SOURCE_NAME,
        "source_url": canonical,
        "parent_title": title,
        "report_title": title,
        "report_text": text[:6000],
        "source_date": extract_source_date(html_text) or extract_source_date(text),
    }

def wayback_cdx_url(original_url: str) -> str:
    params = {
        "url": original_url,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "digest",
        "sort": "reverse",
        "limit": "5",
    }
    return f"{WAYBACK_CDX_URL}?{urllib.parse.urlencode(params, doseq=True)}"


def latest_wayback_snapshot_url(original_url: str, errors: list[dict[str, Any]]) -> str:
    url = wayback_cdx_url(original_url)
    try:
        payload = request_public_json(url)
    except Exception as exc:
        errors.append({"source_url": url, "reason": f"wayback_cdx_fetch_failed:{error_reason(exc)}"})
        return ""
    timestamp = wayback_latest_timestamp(payload)
    if not timestamp:
        errors.append({"source_url": original_url, "reason": "wayback_no_snapshot"})
        return ""
    return f"{WAYBACK_SNAPSHOT_BASE_URL}/{timestamp}id_/{original_url}"


def wayback_latest_timestamp(payload: Any) -> str:
    if not isinstance(payload, list) or len(payload) < 2:
        return ""
    header = payload[0] if isinstance(payload[0], list) else []
    try:
        timestamp_index = header.index("timestamp")
    except ValueError:
        timestamp_index = 0
    for row in payload[1:]:
        if not isinstance(row, list) or len(row) <= timestamp_index:
            continue
        timestamp = str(row[timestamp_index] or "").strip()
        if re.fullmatch(r"\d{14}", timestamp):
            return timestamp
    return ""


def extract_report_links(html_text: str) -> list[str]:
    links: list[str] = []
    for raw in re.findall(r"""href=["']([^"']+)["']""", html_text or "", flags=re.I):
        url = html.unescape(raw)
        if not url.startswith(("http://", "https://")):
            url = urllib.parse.urljoin("https://community.adobe.com/", url)
        canonical = canonical_adobe_url(url)
        if adobe_report_url_is_specific(canonical):
            links.append(canonical)
    return dedupe(links)


def extract_brave_result_links(payload: dict[str, Any]) -> list[str]:
    links: list[str] = []
    web_results = payload.get("web", {}).get("results", []) if isinstance(payload, dict) else []
    if not isinstance(web_results, list):
        return []
    for result in web_results:
        if not isinstance(result, dict):
            continue
        url = str(result.get("url") or "").strip()
        canonical = canonical_adobe_url(url)
        if adobe_report_url_is_specific(canonical):
            links.append(canonical)
    return dedupe(links)


def adobe_bug_report_candidate(url: str, html_text: str, *, source_name: str = SOURCE_NAME, archive_url: str = "") -> dict[str, str] | None:
    canonical = canonical_adobe_url(url)
    if not adobe_report_url_is_specific(canonical):
        return None
    title = extract_title(html_text) or canonical
    text = clean_html(html_text)
    if not text:
        return None
    return {
        "source_type": SOURCE_TYPE,
        "source_name": source_name,
        "source_url": canonical,
        "archive_url": archive_url,
        "parent_title": title,
        "report_title": title,
        "report_text": text[:6000],
        "source_date": extract_source_date(html_text) or extract_source_date(text),
    }


def evaluate_candidates(
    record: PatchRecord,
    candidates: list[dict[str, Any]],
    captured_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for candidate in candidates:
        url = canonical_evidence_url(str(candidate.get("source_url") or ""))
        if not url or url.lower() in seen_urls:
            continue
        seen_urls.add(url.lower())
        row = row_from_candidate(record, {**candidate, "source_url": url}, captured_at)
        if row.get("counted") is True:
            accepted.append(row)
        else:
            rejected.append(row)
    return accepted, rejected


def row_from_candidate(record: PatchRecord, candidate: dict[str, Any], captured_at: str) -> dict[str, Any]:
    report_text = " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ])
    matched, matched_version, basis = premiere_version_match(report_text, record.update_version)
    theme, workflow_area, platform, severity, sentiment = classify(report_text)
    source_date = date_part(candidate.get("source_date"))
    archive_url = str(candidate.get("archive_url") or "").strip()
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
        target_release_date=date_part(record.update_published_at),
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
        row_id=f"{PRODUCT_ID}-{slug(record.update_version)}-{slug(str(candidate.get('source_type') or SOURCE_TYPE))}-{slug(str(candidate.get('source_url') or ''))}",
    )
    if archive_url:
        row["archive_url"] = archive_url
    if not source_date:
        row["source_date_pass"] = None
    gated = apply_acceptance_gates(row, report_text=report_text)
    if archive_url:
        gated["archive_url"] = archive_url
    if gated.get("counted") is True and str(gated.get("source_type") or "") == SOURCE_TYPE and not adobe_report_url_is_specific(str(gated.get("source_url") or "")):
        gated["counted"] = False
        gated["exclusion_reason"] = "source_url_not_specific_report"
    if gated.get("counted") is True and str(gated.get("source_type") or "") == CREATIVE_COW_SOURCE_TYPE and not creativecow_thread_url_is_specific(str(gated.get("source_url") or "")):
        gated["counted"] = False
        gated["exclusion_reason"] = "source_url_not_specific_report"
    if gated.get("counted") is True and not PREMIERE_PRODUCT_RE.search(report_text):
        gated["counted"] = False
        gated["exclusion_reason"] = "missing_premiere_product_context"
    if gated.get("counted") is True and BUILD_65_RE.search(report_text) and not premiere_build_65_context(report_text, record.update_version):
        gated["counted"] = False
        gated["exclusion_reason"] = "build_65_without_premiere_version_context"
    if gated.get("counted") is True and PRE_RELEASE_RE.search(report_text):
        gated["counted"] = False
        gated["exclusion_reason"] = "prerelease_context_for_stable_record"
    if gated.get("counted") is True and not premiere_strong_issue_match(report_text):
        gated["counted"] = False
        gated["exclusion_reason"] = "not_a_real_issue_report"
    return gated


def premiere_version_match(text: str, version: str) -> tuple[bool, str, str]:
    matched, matched_version, basis = exact_version_match(text, version, version_aliases(version))
    if matched:
        return matched, matched_version, basis
    if BUILD_65_RE.search(text or "") and premiere_build_65_context(text, version):
        return True, "Build 65", "build_65_with_premiere_version_context"
    return False, "", ""


def premiere_build_65_context(text: str, version: str) -> bool:
    if not BUILD_65_RE.search(text or ""):
        return False
    version_pattern = re.compile(rf"\b(?:adobe\s+)?premiere\s+pro\s+{re.escape(version)}(?:\.0)?\b", flags=re.I)
    return bool(version_pattern.search(text or ""))


def version_aliases(version: str) -> list[str]:
    aliases = [version]
    if re.fullmatch(r"\d+\.\d+", version or ""):
        aliases.append(f"{version}.0")
    for value in list(aliases):
        aliases.extend([
            f"Premiere Pro {value}",
            f"Adobe Premiere Pro {value}",
        ])
    return dedupe(aliases)


def adobe_report_url_is_specific(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "community.adobe.com" and bool(SPECIFIC_ADOBE_BUG_URL_RE.match(parsed.path))


def canonical_adobe_url(url: str) -> str:
    parsed = urllib.parse.urlsplit((url or "").strip())
    if not parsed.scheme:
        return ""
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def creativecow_thread_url_is_specific(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "creativecow.net" and bool(SPECIFIC_CREATIVE_COW_THREAD_RE.match(parsed.path))


def canonical_creativecow_url(url: str) -> str:
    parsed = urllib.parse.urlsplit((url or "").strip())
    if not parsed.scheme:
        return ""
    if parsed.netloc.lower() not in {"creativecow.net", "www.creativecow.net"}:
        return ""
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    return urllib.parse.urlunsplit(("https", "creativecow.net", path, "", ""))


def canonical_evidence_url(url: str) -> str:
    parsed = urllib.parse.urlsplit((url or "").strip())
    if "community.adobe.com" in parsed.netloc.lower():
        return canonical_adobe_url(url)
    if "creativecow.net" in parsed.netloc.lower():
        return canonical_creativecow_url(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        path = re.sub(r"/+", "/", parsed.path).rstrip("/")
        return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))
    return ""


def request_text(url: str, timeout: int = 30, max_bytes: int = 800000) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", None)
            content_type = response.headers.get("Content-Type", "")
            body = response.read(max_bytes).decode("utf-8", errors="replace")
    except HTTPError as exc:
        try:
            body = exc.read(12000).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        signature = blocked_signature(body, status=exc.code, content_type=exc.headers.get("Content-Type", ""))
        raise AdobeCommunityAccessError(f"http_{exc.code}_{signature}", status=exc.code, content_type=exc.headers.get("Content-Type", "")) from exc
    except URLError as exc:
        raise AdobeCommunityAccessError(f"url_error_{getattr(exc, 'reason', exc)}") from exc
    signature = blocked_signature(body, status=status, content_type=content_type)
    if signature != "none":
        raise AdobeCommunityAccessError(signature, status=status, content_type=content_type)
    return body


def request_json(url: str, *, api_key: str, timeout: int = 30, max_bytes: int = 800000) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
        "User-Agent": HEADERS["User-Agent"],
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", None)
            body = response.read(max_bytes).decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise BraveSearchAccessError(f"http_{exc.code}_{brave_status_reason(exc.code)}", status=exc.code) from exc
    except URLError as exc:
        raise BraveSearchAccessError(f"url_error_{getattr(exc, 'reason', exc)}") from exc
    if status in {401, 403, 429}:
        raise BraveSearchAccessError(f"http_{status}_{brave_status_reason(status)}", status=status)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BraveSearchAccessError("invalid_json") from exc
    if not isinstance(payload, dict):
        raise BraveSearchAccessError("unexpected_json_shape")
    return payload


def request_public_json(url: str, timeout: int = 30, max_bytes: int = 800000) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": HEADERS["User-Agent"],
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", None)
            body = response.read(max_bytes).decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise WaybackAccessError(f"http_{exc.code}_{brave_status_reason(exc.code)}", status=exc.code) from exc
    except URLError as exc:
        raise WaybackAccessError(f"url_error_{getattr(exc, 'reason', exc)}") from exc
    if status in {401, 403, 429}:
        raise WaybackAccessError(f"http_{status}_{brave_status_reason(status)}", status=status)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise WaybackAccessError("invalid_json") from exc


def brave_status_reason(status: int | None) -> str:
    if status == 429:
        return "rate_limited"
    if status in {401, 403}:
        return "blocked"
    return "error"


def blocked_signature(text: str, *, status: int | None, content_type: str) -> str:
    lowered = (text or "").lower()
    if status in {401, 403}:
        return "blocked"
    if status == 429 or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "captcha" in lowered:
        return "captcha_challenge"
    if "access denied" in lowered or "request blocked" in lowered:
        return "blocked"
    if "checking your browser" in lowered or "cloudflare" in lowered:
        return "browser_challenge"
    if not text:
        return "empty_body"
    if content_type and "text/html" not in content_type.lower() and "text/plain" not in content_type.lower():
        return f"unexpected_content_type:{content_type[:40]}"
    return "none"


def error_reason(exc: Exception) -> str:
    if isinstance(exc, (AdobeCommunityAccessError, BraveSearchAccessError, WaybackAccessError)):
        return exc.reason
    return type(exc).__name__


def adobe_community_method_status(
    candidates: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> str:
    if accepted and errors:
        return "partial"
    if accepted:
        return "success"
    if candidates and errors:
        return "partial"
    if candidates and rejected:
        return "no_results"
    if errors:
        reasons = " ".join(str(error.get("reason") or "") for error in errors).lower()
        if "missing_brave_search_api_key" in reasons:
            return "disabled"
        if any(token in reasons for token in ("blocked", "challenge", "captcha", "rate_limited", "access_denied", "http_401", "http_403", "http_429")):
            return "blocked"
        return "broken"
    return "no_results"


def blocked_reason_from_errors(errors: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for error in errors:
        reason = str(error.get("reason") or "fetch_failed")
        counts[reason] = counts.get(reason, 0) + 1
    return "; ".join(f"{reason} x{count}" if count > 1 else reason for reason, count in counts.items())


def classify(text: str) -> tuple[str, str, str, str, str]:
    lowered = (text or "").lower()
    platform = "unknown"
    for token, label in (("windows", "windows"), ("macos", "macos"), ("mac os", "macos"), ("mac", "macos")):
        if token in lowered:
            platform = label
            break
    if "export" in lowered or "render" in lowered:
        return "export/render failure", "export/render", platform, "high", "negative"
    if "project" in lowered and any(token in lowered for token in ("open", "load", "hang", "delay")):
        return "project open/load failure", "project opening", platform, "high", "negative"
    if "timeline" in lowered and any(token in lowered for token in ("crash", "freeze", "hang", "lag")):
        return "timeline crash or hang", "timeline editing", platform, "high", "negative"
    if "ui" in lowered or "interface" in lowered or "lag" in lowered or "slow" in lowered:
        return "interface lag or freezing", "editing interface", platform, "high", "negative"
    if "plugin" in lowered or "compatib" in lowered:
        return "plugin or compatibility issue", "plugins / compatibility", platform, "medium", "negative"
    if "media" in lowered or "decode" in lowered or "audio" in lowered or "video" in lowered:
        return "media decode or audio/video issue", "media playback", platform, "medium", "negative"
    if "install" in lowered:
        return "install issue", "installation", platform, "medium", "negative"
    if "crash" in lowered or "hang" in lowered or "freeze" in lowered:
        return "application crash or hang", "application stability", platform, "high", "negative"
    return "unspecified issue", "Premiere Pro workflow", platform, "medium", "moderate"


def premiere_strong_issue_match(text: str) -> bool:
    lowered = (text or "").lower()
    if HOW_TO_RE.search(lowered):
        return bool(STRONG_ISSUE_RE.search(lowered) and re.search(r"\b(?:after\s+updat|since\s+updat|regression|broke|broken)\b", lowered))
    if OFFICIAL_OR_GENERIC_RE.search(lowered) and not STRONG_ISSUE_RE.search(lowered):
        return False
    return bool(STRONG_ISSUE_RE.search(lowered))


def extract_title(html_text: str) -> str:
    patterns = [
        r"""<meta\s+property=["']og:title["']\s+content=["']([^"']+)["']""",
        r"""<h1[^>]*>(.*?)</h1>""",
        r"""<title[^>]*>(.*?)</title>""",
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text or "", flags=re.I | re.S)
        if match:
            title = clean_html(match.group(1))
            return re.sub(r"\s*-\s*Adobe Community\s*$", "", title, flags=re.I).strip()
    return ""


def clean_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", text or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_source_date(text: str) -> str:
    if not text:
        return ""
    for pattern in [
        r"""<time[^>]+datetime=["']([^"']+)["']""",
        r"""<meta[^>]+(?:property|name)=["'](?:article:published_time|date|dc\.date)["'][^>]+content=["']([^"']+)["']""",
    ]:
        match = re.search(pattern, text, flags=re.I)
        if match:
            parsed = parse_date(match.group(1))
            if parsed:
                return parsed
    match = re.search(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),\s+(20\d{2})\b", clean_html(text), flags=re.I)
    if match:
        month = month_number(match.group(1))
        if month:
            return datetime(int(match.group(3)), month, int(match.group(2)), tzinfo=timezone.utc).date().isoformat()
    return ""


def parse_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


def month_number(value: str) -> int | None:
    key = value[:3].lower()
    return {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }.get(key)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = re.sub(r"\s+", " ", str(value or "")).strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append(clean)
    return result


def rejection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("exclusion_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def format_rejection_counts(rows: list[dict[str, Any]]) -> str:
    return ", ".join(f"{reason}={count}" for reason, count in sorted(rejection_counts(rows).items()))


def apply_consensus_writeback(update_version: str) -> bool:
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
