"""DaVinci Resolve production evidence collector.

Phase A supports unattended collection from source-specific public report URLs
that can be fetched and checked deterministically. Ambiguous candidates remain
rejected; accepted rows are written only after exact-version/date/report gates.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone
from typing import Any

from lib.normalize_davinci_version import normalize_davinci_version

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
    load_front_matter_and_body,
    make_evidence_row,
    method_health_row,
    slug,
    utc_now,
)

PRODUCT_ID = "blackmagic-davinci"
SOURCE_NAME_REDDIT = "r/davinciresolve"
REDDIT_SUBREDDIT = "davinciresolve"
REDDIT_SEARCH = f"https://www.reddit.com/r/{REDDIT_SUBREDDIT}/search.json"
REDDIT_OLD_SEARCH = f"https://old.reddit.com/r/{REDDIT_SUBREDDIT}/search.json"
REDDIT_LISTING = f"https://www.reddit.com/r/{REDDIT_SUBREDDIT}/new.json"
REDDIT_OLD_LISTING = f"https://old.reddit.com/r/{REDDIT_SUBREDDIT}/new.json"
REDDIT_GLOBAL_SEARCH = "https://www.reddit.com/search.json"
REDDIT_SEARCH_RSS = f"https://www.reddit.com/r/{REDDIT_SUBREDDIT}/search.rss"
REDDIT_OLD_SEARCH_RSS = f"https://old.reddit.com/r/{REDDIT_SUBREDDIT}/search.rss"
REDDIT_NEW_RSS = f"https://www.reddit.com/r/{REDDIT_SUBREDDIT}/new/.rss"
REDDIT_OLD_NEW_RSS = f"https://old.reddit.com/r/{REDDIT_SUBREDDIT}/new/.rss"
REDDIT_HOT_RSS = f"https://www.reddit.com/r/{REDDIT_SUBREDDIT}/.rss"
REDDIT_OLD_HOT_RSS = f"https://old.reddit.com/r/{REDDIT_SUBREDDIT}/.rss"
FORUM_SEARCH = "https://forum.blackmagicdesign.com/search.php"
TEXT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (compatible; AUXSAYS-DaVinci-Evidence-Collector/1.0; +https://auxsays.com/)",
}
REDDIT_USER_AGENT = os.getenv(
    "AUXSAYS_REDDIT_USER_AGENT",
    "script:com.auxsays.patch-intelligence:v1.0 (by /u/auxsays)",
)
JSON_HEADERS = {
    "Accept": "application/json, text/plain;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "close",
    "User-Agent": REDDIT_USER_AGENT,
}
FEED_HEADERS = {
    "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9, text/plain;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "close",
    "User-Agent": REDDIT_USER_AGENT,
}
FORUM_DISCOVERY_ISSUE_TERMS = (
    "crash",
    "corrupt",
    "render",
    "export",
    "gpu",
    "install",
    "bug",
    "magic mask",
)
PRODUCT_CONTEXT_RE = re.compile(r"\b(?:davinci\s+resolve|resolve\s+studio|resolve)\b", flags=re.I)
VERSIONED_DAVINCI_CONTEXT_RE = re.compile(
    r"\bdavinci\s+(?:version\s+)?v?\d{1,2}(?:\.\d+){0,2}\b",
    flags=re.I,
)
BETA_CONTEXT_RE = re.compile(r"\b(?:public\s+beta|beta\s*\d*|21\.0b\d*|21b\d+|21\.0b\s+build\s+20|build\s+20)\b", flags=re.I)
DAVINCI_VERSION_CONTEXT_RE = re.compile(
    r"\b(?:davinci\s+resolve(?:\s+studio)?|resolve(?:\s+studio)?|davinci|version)\s+v?(\d{1,2})(?:\.\d+){0,2}\b",
    flags=re.I,
)
DAVINCI_STRONG_ISSUE_RE = re.compile(
    r"\b(?:crash(?:es|ed|ing)?|freez(?:e|es|ing|en)|hang(?:s|ing)?|fail(?:ed|s|ure|ing)?|error|bug|broke|broken|breaks|corrupt(?:ed|ion)?|regression|slow|lag(?:gy)?|won't\s+open|can't\s+open|cannot\s+open|does\s+not\s+open|decode|install(?:ation)?\s+issue|problem)\b",
    flags=re.I,
)


class SourceAccessError(RuntimeError):
    def __init__(
        self,
        reason: str,
        *,
        status: int | None = None,
        content_type: str = "",
        blocked_signature: str = "",
        endpoint_family: str = "",
        headers_strategy: str = "",
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.content_type = content_type
        self.blocked_signature = blocked_signature
        self.endpoint_family = endpoint_family
        self.headers_strategy = headers_strategy

# Seed/fallback coverage only: these URLs are calibration examples for the
# deterministic gates, not the primary long-term DaVinci evidence mechanism.
# Productive vendor forum / Reddit discovery should reduce reliance on this list.
KNOWN_WATCHLIST = (
    {
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235117",
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
    },
    {
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235536",
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
    },
    {
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235458",
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
    },
    {
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235208",
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
    },
    {
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=234870",
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
    },
    {
        "source_url": "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235179",
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
    },
    {
        "source_url": "https://www.reddit.com/r/davinciresolve/comments/1sn39qf/davinci_resolve_failed_to_decode_video_frame_when/",
        "source_type": "reddit_community_report",
        "source_name": SOURCE_NAME_REDDIT,
    },
)


class DavinciCollector(ProductCollector):
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
                    "davinci_record_updated": record_updated,
                })
            results.append(result)
        return results


def reddit_headers_strategy(headers: dict[str, str]) -> str:
    strategy = "reddit_descriptive_ua_json"
    if headers.get("Authorization"):
        strategy += "+bearer"
    return strategy


def reddit_diagnostics_enabled() -> bool:
    value = os.getenv("AUXSAYS_REDDIT_DIAGNOSTICS")
    if value is not None:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true"


def sanitize_diagnostic_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    sensitive = {"access_token", "token", "client_secret", "authorization", "bearer"}
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    clean_query = urllib.parse.urlencode([
        (key, "[redacted]" if key.lower() in sensitive else value)
        for key, value in query_pairs
    ])
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, clean_query, ""))


def blocked_signature(text: str, *, status: int | None, content_type: str, headers: dict[str, str] | None = None) -> str:
    lowered = (text or "").lower()
    header_text = " ".join(f"{key}:{value}" for key, value in (headers or {}).items()).lower()
    if status == 429 or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "cf-ray" in header_text or "cloudflare" in lowered or "checking your browser" in lowered:
        return "cloudflare_or_browser_challenge"
    if status == 403:
        return "blocked"
    if "blocked" in lowered and "text/html" in content_type.lower():
        return "blocked"
    if "login" in lowered and "reddit" in lowered:
        return "login_or_auth_challenge"
    if "captcha" in lowered:
        return "captcha_challenge"
    if "text/html" in content_type.lower() and "application/json" not in content_type.lower():
        title = extract_title(text)
        return f"html_response:{title[:60]}" if title else "html_response"
    if not text:
        return "empty_body"
    return "none"


def emit_reddit_fetch_diagnostic(
    *,
    url: str,
    endpoint_family: str,
    status: int | None,
    content_type: str,
    signature: str,
    headers_strategy: str,
    parsed_as_feed: bool | None = None,
    candidate_count: int | None = None,
) -> None:
    if not reddit_diagnostics_enabled():
        return
    payload = {
        "event": "reddit_fetch",
        "url": sanitize_diagnostic_url(url),
        "endpoint_family": endpoint_family,
        "http_status": status,
        "content_type": content_type,
        "blocked_signature": signature,
        "headers_strategy": headers_strategy,
    }
    if parsed_as_feed is not None:
        payload["parsed_as_feed"] = parsed_as_feed
    if candidate_count is not None:
        payload["candidate_count"] = candidate_count
    print(f"[auxsays:diagnostic] {json.dumps(payload, sort_keys=True, ensure_ascii=True)}")


def reddit_request_delay() -> float:
    try:
        return max(0.0, float(os.getenv("AUXSAYS_REDDIT_REQUEST_DELAY_SECONDS", "0.35")))
    except ValueError:
        return 0.35


def pace_reddit_request() -> None:
    delay = reddit_request_delay()
    if delay > 0:
        time.sleep(delay)


def with_raw_json(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key == "raw_json" for key, _value in pairs):
        pairs.append(("raw_json", "1"))
    query = urllib.parse.urlencode(pairs)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def request_json(url: str, *, endpoint_family: str = "reddit_json") -> Any:
    headers = dict(JSON_HEADERS)
    token = os.getenv("REDDIT_BEARER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers_strategy = reddit_headers_strategy(headers)
    request_url = with_raw_json(url)
    request = urllib.request.Request(request_url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            content_type = response.headers.get("content-type", "")
            status = int(getattr(response, "status", 200) or 200)
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            signature = blocked_signature(text[:4000], status=status, content_type=content_type, headers=dict(response.headers.items()))
            emit_reddit_fetch_diagnostic(
                url=request_url,
                endpoint_family=endpoint_family,
                status=status,
                content_type=content_type,
                signature=signature,
                headers_strategy=headers_strategy,
            )
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise SourceAccessError(
                    f"json_decode_failed:{type(exc).__name__}",
                    status=status,
                    content_type=content_type,
                    blocked_signature=signature,
                    endpoint_family=endpoint_family,
                    headers_strategy=headers_strategy,
                ) from exc
    except HTTPError as exc:
        body = exc.read(8000).decode("utf-8", errors="replace")
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        signature = blocked_signature(body, status=exc.code, content_type=content_type, headers=dict(exc.headers.items()) if exc.headers else {})
        emit_reddit_fetch_diagnostic(
            url=request_url,
            endpoint_family=endpoint_family,
            status=exc.code,
            content_type=content_type,
            signature=signature,
            headers_strategy=headers_strategy,
        )
        raise SourceAccessError(
            f"http_{exc.code}_{exc.reason}",
            status=exc.code,
            content_type=content_type,
            blocked_signature=signature,
            endpoint_family=endpoint_family,
            headers_strategy=headers_strategy,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        emit_reddit_fetch_diagnostic(
            url=request_url,
            endpoint_family=endpoint_family,
            status=None,
            content_type="",
            signature=type(exc).__name__,
            headers_strategy=headers_strategy,
        )
        raise SourceAccessError(
            f"network_{type(exc).__name__}",
            endpoint_family=endpoint_family,
            blocked_signature=type(exc).__name__,
            headers_strategy=headers_strategy,
        ) from exc


def reddit_failure_summary(failures: list[dict[str, Any]]) -> str:
    pieces: list[str] = []
    for failure in failures:
        family = str(failure.get("endpoint_family") or "reddit_json")
        reason = str(failure.get("reason") or "fetch_failed")
        signature = str(failure.get("blocked_signature") or "")
        piece = f"{family}={reason}"
        if signature and signature != "none":
            piece += f":{signature}"
        pieces.append(piece)
    return "all_reddit_endpoint_attempts_failed[" + ";".join(pieces[:4]) + "]"


def request_reddit_json_with_fallback(attempts: list[tuple[str, str]]) -> Any:
    failures: list[dict[str, Any]] = []
    for endpoint_family, url in attempts:
        try:
            payload = request_json(url, endpoint_family=endpoint_family)
            pace_reddit_request()
            return payload
        except SourceAccessError as exc:
            failures.append({
                "endpoint_family": endpoint_family,
                "reason": exc.reason,
                "status": exc.status,
                "content_type": exc.content_type,
                "blocked_signature": exc.blocked_signature,
            })
            pace_reddit_request()
            continue
    raise SourceAccessError(reddit_failure_summary(failures), status=failures[0].get("status") if failures else None)


def request_reddit_feed(url: str, *, endpoint_family: str) -> list[dict[str, Any]]:
    headers = dict(FEED_HEADERS)
    headers_strategy = "reddit_descriptive_ua_feed"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(1_000_000)
            content_type = response.headers.get("content-type", "")
            status = int(getattr(response, "status", 200) or 200)
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            candidates = reddit_feed_candidates(text)
            signature = blocked_signature(text[:4000], status=status, content_type=content_type, headers=dict(response.headers.items()))
            emit_reddit_fetch_diagnostic(
                url=url,
                endpoint_family=endpoint_family,
                status=status,
                content_type=content_type,
                signature=signature,
                headers_strategy=headers_strategy,
                parsed_as_feed=True,
                candidate_count=len(candidates),
            )
            return candidates
    except HTTPError as exc:
        body = exc.read(8000).decode("utf-8", errors="replace")
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        signature = blocked_signature(body, status=exc.code, content_type=content_type, headers=dict(exc.headers.items()) if exc.headers else {})
        emit_reddit_fetch_diagnostic(
            url=url,
            endpoint_family=endpoint_family,
            status=exc.code,
            content_type=content_type,
            signature=signature,
            headers_strategy=headers_strategy,
            parsed_as_feed=False,
            candidate_count=0,
        )
        raise SourceAccessError(
            f"http_{exc.code}_{exc.reason}",
            status=exc.code,
            content_type=content_type,
            blocked_signature=signature,
            endpoint_family=endpoint_family,
            headers_strategy=headers_strategy,
        ) from exc
    except ET.ParseError as exc:
        emit_reddit_fetch_diagnostic(
            url=url,
            endpoint_family=endpoint_family,
            status=None,
            content_type="",
            signature=f"feed_parse_failed:{type(exc).__name__}",
            headers_strategy=headers_strategy,
            parsed_as_feed=False,
            candidate_count=0,
        )
        raise SourceAccessError(
            f"feed_parse_failed:{type(exc).__name__}",
            endpoint_family=endpoint_family,
            blocked_signature=type(exc).__name__,
            headers_strategy=headers_strategy,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        emit_reddit_fetch_diagnostic(
            url=url,
            endpoint_family=endpoint_family,
            status=None,
            content_type="",
            signature=type(exc).__name__,
            headers_strategy=headers_strategy,
            parsed_as_feed=False,
            candidate_count=0,
        )
        raise SourceAccessError(
            f"network_{type(exc).__name__}",
            endpoint_family=endpoint_family,
            blocked_signature=type(exc).__name__,
            headers_strategy=headers_strategy,
        ) from exc


def request_reddit_feed_with_fallback(attempts: list[tuple[str, str]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for endpoint_family, url in attempts:
        try:
            candidates = request_reddit_feed(url, endpoint_family=endpoint_family)
            pace_reddit_request()
            return candidates
        except SourceAccessError as exc:
            failures.append({
                "endpoint_family": endpoint_family,
                "reason": exc.reason,
                "status": exc.status,
                "content_type": exc.content_type,
                "blocked_signature": exc.blocked_signature,
            })
            pace_reddit_request()
            continue
    raise SourceAccessError(reddit_failure_summary(failures), status=failures[0].get("status") if failures else None)


def request_text(url: str) -> str:
    request = urllib.request.Request(url, headers=TEXT_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(500_000)
            content_type = response.headers.get("content-type", "")
            status = response.status
    except HTTPError as exc:
        body = exc.read(8000).decode("utf-8", errors="replace")
        reason = blackmagic_access_challenge_reason(body) if is_blackmagic_forum_url(url) else ""
        raise SourceAccessError(reason or f"http_{exc.code}_{exc.reason}", status=exc.code) from exc
    charset = "utf-8"
    match = re.search(r"charset=([A-Za-z0-9_\-]+)", content_type)
    if match:
        charset = match.group(1)
    text = raw.decode(charset, errors="replace")
    if is_blackmagic_forum_url(url) and blackmagic_access_challenge(text):
        raise SourceAccessError(blackmagic_access_challenge_reason(text), status=status)
    return text


def is_blackmagic_forum_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(str(url or ""))
    return parsed.netloc.lower() == "forum.blackmagicdesign.com"


def blackmagic_access_challenge(text: str) -> bool:
    return blackmagic_access_challenge_reason(text) != ""


def blackmagic_access_challenge_reason(text: str) -> str:
    lowered = text.lower()
    if "window.gokuprops" in lowered or "awswaf" in lowered:
        return "http_202_aws_waf_challenge"
    if "<title></title>" in lowered and "please enable javascript" in lowered:
        return "http_202_javascript_challenge"
    if "checking your browser" in lowered:
        return "http_202_browser_challenge"
    return ""


def blackmagic_forum_unusable_reason(text: str) -> str:
    access_reason = blackmagic_access_challenge_reason(text)
    if access_reason:
        return access_reason
    lowered = (text or "").lower()
    if not lowered.strip():
        return "source_unusable_response"
    if "captcha" in lowered:
        return "blackmagic_forum_captcha_challenge"
    if "access denied" in lowered or "forbidden" in lowered:
        return "blackmagic_forum_access_denied"
    forum_markers = (
        "forum.blackmagicdesign.com",
        "blackmagic design community forum",
        "viewtopic.php",
        "search.php",
        "phpbb",
        "board index",
        "no suitable matches were found",
    )
    if any(marker in lowered for marker in forum_markers):
        return ""
    return "source_returned_non_forum_content"


def version_aliases(version: str) -> list[str]:
    normalized = normalize_davinci_version(version)
    aliases = [
        f"DaVinci Resolve {version}",
        f"Resolve {version}",
        f"DaVinci Resolve Studio {version}",
    ]
    aliases.extend(str(alias) for alias in normalized.get("normalized_aliases") or [])
    if normalized.get("is_beta") and int(normalized.get("beta_number") or 0) == 1:
        aliases.extend([
            "DaVinci Resolve 21.0 Public Beta 1",
            "DaVinci Resolve Studio 21.0 Public Beta 1",
            "Resolve 21.0 Public Beta 1",
            "Resolve Studio 21.0B Build 20",
            "DaVinci Resolve Studio 21.0B Build 20",
            "DaVinci Resolve 21.0b1",
            "Resolve 21.0b1",
            "DaVinci Resolve public beta 21",
            "Resolve public beta 21",
            "public beta 21",
            "DaVinci Resolve 21 beta",
            "Resolve 21 beta",
            "DaVinci Resolve Studio 21 beta",
            "DR 21 Public Beta 1",
            "DR 21 Beta 1",
            "DR 21b1",
        ])
    elif normalized.get("is_beta") is False and normalized.get("minor_version") is None:
        major = int(normalized.get("major_version") or 0)
        if major:
            aliases.extend([
                f"{major}.0",
                f"DaVinci Resolve {major}.0",
                f"DaVinci Resolve Studio {major}.0",
                f"Resolve {major}.0",
                f"Resolve Studio {major}.0",
                f"DaVinci {major}.0",
                f"version {major}",
                f"version {major}.0",
                f"DaVinci Resolve version {major}",
                f"DaVinci Resolve version {major}.0",
                f"Resolve Studio {major}",
            ])
    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        alias = re.sub(r"\s+", " ", str(alias or "")).strip()
        if alias and alias.lower() not in seen:
            seen.add(alias.lower())
            deduped.append(alias)
    return deduped


def collect_for_record(record: PatchRecord, context: CollectorContext) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    captured_at = utc_now()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    health: list[dict[str, Any]] = []

    method_stack = (
        ("known_watchlist", "curated_watchlist", known_watchlist_candidates),
        ("reddit_search", "reddit_community_report", reddit_search_candidates),
        ("vendor_forum_search", "blackmagic_forum", vendor_forum_search_candidates),
        ("web_search", "web_search", web_search_candidates),
    )

    for method_id, source_type, method in method_stack:
        errors: list[dict[str, Any]] = []
        candidates = method(record, context, errors)
        method_accepted, method_rejected = evaluate_candidates(record, candidates, captured_at, seen_urls)
        accepted.extend(method_accepted)
        rejected.extend(method_rejected)
        fetch_failure_count = len(errors)
        blocked_reason = blocked_reason_from_errors(errors)
        notes = method_notes(method_id)
        if fetch_failure_count:
            notes = f"{notes} Fetch failures: {fetch_failure_count}."
        if method_rejected and not method_accepted:
            notes = f"{notes} Rejected candidates: {format_rejection_counts(method_rejected)}."
        status = "disabled" if method_id == "web_search" else method_status(candidates, method_accepted, method_rejected, errors)
        if method_id == "vendor_forum_search" and status in {"blocked", "low_confidence"}:
            notes = f"Blackmagic forum acquisition did not return usable forum content. No unusable source checks were counted as reports. {blocked_reason}"
        health.append(method_health_row(
            product_id=PRODUCT_ID,
            update_version=record.update_version,
            method_id=method_id,
            source_type=source_type,
            status=status,
            candidates_found=len(candidates),
            accepted_reports=len(method_accepted),
            rejected_reports=len(method_rejected),
            blocked_reason=blocked_reason,
            last_run=captured_at,
            notes=notes,
        ))

    return accepted, rejected, health


def evaluate_candidates(
    record: PatchRecord,
    candidates: list[dict[str, Any]],
    captured_at: str,
    seen_urls: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in candidates:
        url = str(candidate.get("source_url") or "").strip().rstrip("/")
        if not url or url.lower() in seen_urls:
            continue
        seen_urls.add(url.lower())
        row = row_from_candidate(record, candidate, captured_at)
        if row.get("counted") is True:
            accepted.append(row)
        else:
            rejected.append(row)
    return accepted, rejected


def reddit_search_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queries = reddit_search_queries(record)
    candidates: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    consecutive_fetch_failures = 0
    for query in queries:
        if query.lower() in seen_queries:
            continue
        seen_queries.add(query.lower())
        after: str | None = None
        for _page in range(max(1, context.max_pages)):
            params = {
                "q": query,
                "restrict_sr": "1",
                "sort": "new",
                "t": "year",
                "limit": "50",
            }
            if after:
                params["after"] = after
            try:
                payload = request_reddit_json_with_fallback(reddit_search_attempts(query, params))
            except Exception as exc:
                errors.append({
                    "query": query,
                    "source_url": f"{REDDIT_SEARCH}?{urllib.parse.urlencode(params)}",
                    "reason": f"reddit_search_fetch_failed:{error_reason(exc)}",
                })
                consecutive_fetch_failures += 1
                break
            consecutive_fetch_failures = 0
            children = (((payload or {}).get("data") or {}).get("children") or [])
            for child in children:
                data = child.get("data") if isinstance(child, dict) else None
                if isinstance(data, dict):
                    candidates.append(reddit_candidate(data))
            after = ((payload or {}).get("data") or {}).get("after")
            if not after:
                break
        if consecutive_fetch_failures >= 3:
            break
    listing_errors: list[dict[str, Any]] = []
    listing_candidates = reddit_listing_candidates(record, context, listing_errors)
    if listing_candidates:
        candidates.extend(listing_candidates)
    else:
        errors.extend(listing_errors)
    feed_errors: list[dict[str, Any]] = []
    feed_candidates = reddit_feed_discovery_candidates(record, context, feed_errors)
    if feed_candidates:
        candidates.extend(feed_candidates)
    else:
        errors.extend(feed_errors)
    return candidates


def reddit_search_attempts(query: str, params: dict[str, str]) -> list[tuple[str, str]]:
    attempts: list[tuple[str, str]] = []
    encoded = urllib.parse.urlencode(params)
    token = os.getenv("REDDIT_BEARER_TOKEN")
    if token:
        attempts.append((
            "reddit_search_oauth",
            f"https://oauth.reddit.com/r/{REDDIT_SUBREDDIT}/search?{encoded}",
        ))
    attempts.extend([
        ("reddit_search_www_json", f"{REDDIT_SEARCH}?{encoded}"),
        ("reddit_search_old_json", f"{REDDIT_OLD_SEARCH}?{encoded}"),
        ("reddit_search_global_json", f"{REDDIT_GLOBAL_SEARCH}?{urllib.parse.urlencode(global_reddit_search_params(query, params))}"),
    ])
    return attempts


def global_reddit_search_params(query: str, params: dict[str, str]) -> dict[str, str]:
    global_params = dict(params)
    global_params.pop("restrict_sr", None)
    global_params["q"] = f"subreddit:{REDDIT_SUBREDDIT} {query}"
    return global_params


def reddit_listing_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    after: str | None = None
    for _page in range(max(1, context.max_pages)):
        params = {"limit": "100"}
        if after:
            params["after"] = after
        try:
            payload = request_reddit_json_with_fallback(reddit_listing_attempts(params))
        except Exception as exc:
            errors.append({
                "source_url": f"{REDDIT_LISTING}?{urllib.parse.urlencode(params)}",
                "reason": f"reddit_listing_fetch_failed:{error_reason(exc)}",
            })
            break
        children = (((payload or {}).get("data") or {}).get("children") or [])
        for child in children:
            data = child.get("data") if isinstance(child, dict) else None
            if not isinstance(data, dict):
                continue
            candidate = reddit_candidate(data)
            if context.since and candidate.get("source_date") and date_part(candidate.get("source_date")) < context.since:
                continue
            candidates.append(candidate)
        after = ((payload or {}).get("data") or {}).get("after")
        if not after:
            break
    return candidates


def reddit_listing_attempts(params: dict[str, str]) -> list[tuple[str, str]]:
    encoded = urllib.parse.urlencode(params)
    attempts: list[tuple[str, str]] = []
    token = os.getenv("REDDIT_BEARER_TOKEN")
    if token:
        attempts.append((
            "reddit_listing_oauth",
            f"https://oauth.reddit.com/r/{REDDIT_SUBREDDIT}/new?{encoded}",
        ))
    attempts.extend([
        ("reddit_listing_www_json", f"{REDDIT_LISTING}?{encoded}"),
        ("reddit_listing_old_json", f"{REDDIT_OLD_LISTING}?{encoded}"),
    ])
    return attempts


def reddit_feed_discovery_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for query in reddit_feed_search_queries(record):
        for family, url in reddit_search_feed_attempts(query):
            try:
                feed_candidates = request_reddit_feed(url, endpoint_family=family)
            except Exception as exc:
                errors.append({
                    "query": query,
                    "source_url": url,
                    "reason": f"reddit_search_feed_fetch_failed:{error_reason(exc)}",
                })
                continue
            for candidate in feed_candidates:
                candidate_url = str(candidate.get("source_url") or "").strip().rstrip("/").lower()
                if not candidate_url or candidate_url in seen_urls:
                    continue
                if not candidate_has_version_hint(record, candidate):
                    continue
                seen_urls.add(candidate_url)
                candidates.append(candidate)
    for family, url in reddit_listing_feed_attempts():
        try:
            feed_candidates = request_reddit_feed(url, endpoint_family=family)
        except Exception as exc:
            errors.append({
                "source_url": url,
                "reason": f"reddit_listing_feed_fetch_failed:{error_reason(exc)}",
            })
            continue
        for candidate in feed_candidates:
            if context.since and candidate.get("source_date") and date_part(candidate.get("source_date")) < context.since:
                continue
            candidate_url = str(candidate.get("source_url") or "").strip().rstrip("/").lower()
            if not candidate_url or candidate_url in seen_urls:
                continue
            if not candidate_has_version_hint(record, candidate):
                continue
            seen_urls.add(candidate_url)
            candidates.append(candidate)
    return candidates


def reddit_feed_search_queries(record: PatchRecord) -> list[str]:
    normalized = normalize_davinci_version(record.update_version)
    if normalized.get("is_beta") and int(normalized.get("beta_number") or 0) == 1:
        base_queries = [
            '"21 Public Beta 1"',
            '"DaVinci Resolve 21 Public Beta 1"',
            '"Resolve 21 Public Beta 1"',
            '"public beta 21"',
            '"Resolve 21 beta"',
            '"DaVinci Resolve 21 beta"',
            '"21.0B"',
            '"21b1"',
        ]
    else:
        base_queries = [
            f'"DaVinci Resolve {record.update_version}"',
            f'"Resolve {record.update_version}"',
            f'"DaVinci Resolve Studio {record.update_version}"',
        ]
    issue_terms = ("crash", "render", "export", "bug")
    queries = list(base_queries)
    for base in base_queries[:6]:
        for issue_term in issue_terms[:3]:
            queries.append(f"{base} {issue_term}")
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized_query = re.sub(r"\s+", " ", query).strip()
        if normalized_query and normalized_query.lower() not in seen:
            seen.add(normalized_query.lower())
            deduped.append(normalized_query)
    return deduped[:24]


def candidate_has_version_hint(record: PatchRecord, candidate: dict[str, Any]) -> bool:
    text = " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ])
    matched, _matched_version, _basis = exact_version_match(text, record.update_version, version_aliases(record.update_version))
    return matched


def reddit_search_feed_attempts(query: str) -> list[tuple[str, str]]:
    params = {
        "q": query,
        "restrict_sr": "1",
        "sort": "new",
        "t": "year",
    }
    encoded = urllib.parse.urlencode(params)
    return [
        ("reddit_search_www_atom", f"{REDDIT_SEARCH_RSS}?{encoded}"),
        ("reddit_search_old_atom", f"{REDDIT_OLD_SEARCH_RSS}?{encoded}"),
    ]


def reddit_listing_feed_attempts() -> list[tuple[str, str]]:
    return [
        ("reddit_new_www_atom", REDDIT_NEW_RSS),
        ("reddit_new_old_atom", REDDIT_OLD_NEW_RSS),
        ("reddit_hot_www_atom", REDDIT_HOT_RSS),
        ("reddit_hot_old_atom", REDDIT_OLD_HOT_RSS),
    ]


def reddit_search_queries(record: PatchRecord) -> list[str]:
    aliases = [record.update_version, *version_aliases(record.update_version)]
    queries: list[str] = []
    for alias in aliases:
        alias = str(alias or "").strip()
        if alias:
            queries.append(f'"{alias}"')
    normalized = normalize_davinci_version(record.update_version)
    if normalized.get("is_beta"):
        queries.extend([
            '"public beta 21"',
            '"21.0B"',
            '"21b1"',
            "davinci resolve public beta render",
            "davinci resolve public beta crash",
        ])
    else:
        queries.extend([
            '"DaVinci Resolve 21"',
            '"Resolve Studio 21"',
            "davinci resolve 21 crash",
            "davinci resolve 21 render",
        ])
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        if query.lower() not in seen:
            seen.add(query.lower())
            deduped.append(query)
    return deduped


def known_watchlist_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return source_probe_candidates(record, context, errors, KNOWN_WATCHLIST)


def vendor_forum_search_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    links: list[str] = []
    for term in forum_search_terms(record):
        params = urllib.parse.urlencode({"keywords": term, "terms": "all", "author": "", "sc": "1", "sf": "all"})
        url = f"{FORUM_SEARCH}?{params}"
        try:
            text = request_text(url)
        except Exception as exc:
            errors.append({"source_url": url, "reason": f"vendor_forum_search_blocked_or_failed:{error_reason(exc)}"})
            if blackmagic_error_is_access_limited(error_reason(exc)):
                break
            continue
        unusable_reason = blackmagic_forum_unusable_reason(text)
        if unusable_reason:
            errors.append({"source_url": url, "reason": f"vendor_forum_search_unusable:{unusable_reason}"})
            break
        links.extend(re.findall(r"href=\"(viewtopic\.php\?[^\"#]+t=\d+[^\"#]*)", text, flags=re.I))
    candidates: list[dict[str, Any]] = []
    for link in sorted(set(links))[:25]:
        source_url = urllib.parse.urljoin("https://forum.blackmagicdesign.com/", html.unescape(link))
        try:
            page = request_text(source_url)
        except Exception as exc:
            errors.append({"source_url": source_url, "reason": f"vendor_forum_thread_fetch_failed:{error_reason(exc)}"})
            continue
        unusable_reason = blackmagic_forum_unusable_reason(page)
        if unusable_reason:
            errors.append({"source_url": source_url, "reason": f"vendor_forum_thread_unusable:{unusable_reason}"})
            continue
        clean = clean_html(page)
        title = extract_title(page) or source_url
        candidates.append({
            "source_type": "blackmagic_forum",
            "source_name": "Blackmagic Design Community Forum",
            "source_url": source_url,
            "parent_title": title,
            "report_title": title,
            "report_text": clean[:4000],
            "source_date": extract_source_date(clean),
        })
    return candidates


def blackmagic_error_is_access_limited(reason: str) -> bool:
    lowered = str(reason or "").lower()
    return any(token in lowered for token in ("blocked", "challenge", "waf", "captcha", "access_denied", "unusable"))


def forum_search_terms(record: PatchRecord) -> list[str]:
    version_terms: list[str] = []
    seen: set[str] = set()
    for term in [record.update_version, *version_aliases(record.update_version)]:
        term = re.sub(r"\s+", " ", str(term or "")).strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            version_terms.append(term)
    queries = list(version_terms)
    for version_term in version_terms[:6]:
        for issue_term in FORUM_DISCOVERY_ISSUE_TERMS[:4]:
            queries.append(f"{version_term} {issue_term}")
    return queries[:24]


def web_search_candidates(record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors.append({
        "query": f"DaVinci Resolve {record.update_version} issue report",
        "reason": "web_search_adapter_disabled_in_phase_a",
    })
    return []


def reddit_candidate(data: dict[str, Any]) -> dict[str, Any]:
    created = data.get("created_utc")
    source_date = ""
    if isinstance(created, (int, float)):
        source_date = datetime.fromtimestamp(float(created), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    permalink = str(data.get("permalink") or "")
    return {
        "source_type": "reddit_community_report",
        "source_name": SOURCE_NAME_REDDIT,
        "source_url": f"https://www.reddit.com{permalink}" if permalink.startswith("/") else str(data.get("url") or ""),
        "parent_title": str(data.get("title") or ""),
        "report_title": str(data.get("title") or ""),
        "report_text": " ".join([str(data.get("title") or ""), str(data.get("selftext") or "")]).strip(),
        "source_date": source_date,
    }


def reddit_feed_candidates(text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(text)
    candidates: list[dict[str, Any]] = []
    if root.tag.endswith("feed"):
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            candidate = reddit_atom_entry_candidate(entry)
            if candidate:
                candidates.append(candidate)
        return candidates
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            candidate = reddit_rss_item_candidate(item)
            if candidate:
                candidates.append(candidate)
    return candidates


def reddit_atom_entry_candidate(entry: ET.Element) -> dict[str, Any] | None:
    title = xml_child_text(entry, "title")
    url = atom_entry_link(entry)
    if not reddit_source_url_is_usable(url):
        return None
    summary = xml_child_text(entry, "summary") or xml_child_text(entry, "content")
    source_date = xml_child_text(entry, "published") or xml_child_text(entry, "updated")
    text = clean_html(" ".join([title, summary]).strip())
    return {
        "source_type": "reddit_community_report",
        "source_name": SOURCE_NAME_REDDIT,
        "source_url": canonical_reddit_url(url),
        "parent_title": title,
        "report_title": title,
        "report_text": text[:4000],
        "source_date": source_date,
    }


def reddit_rss_item_candidate(item: ET.Element) -> dict[str, Any] | None:
    title = xml_child_text(item, "title")
    url = xml_child_text(item, "link")
    if not reddit_source_url_is_usable(url):
        return None
    description = xml_child_text(item, "description")
    source_date = normalize_feed_date(xml_child_text(item, "pubDate") or xml_child_text(item, "dc:date"))
    text = clean_html(" ".join([title, description]).strip())
    return {
        "source_type": "reddit_community_report",
        "source_name": SOURCE_NAME_REDDIT,
        "source_url": canonical_reddit_url(url),
        "parent_title": title,
        "report_title": title,
        "report_text": text[:4000],
        "source_date": source_date,
    }


def xml_child_text(parent: ET.Element, tag_name: str) -> str:
    if ":" in tag_name:
        tag_name = tag_name.split(":", 1)[1]
    for child in list(parent):
        if child.tag.split("}", 1)[-1] == tag_name:
            return "".join(child.itertext()).strip()
    return ""


def atom_entry_link(entry: ET.Element) -> str:
    fallback = ""
    for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
        href = str(link.attrib.get("href") or "").strip()
        rel = str(link.attrib.get("rel") or "alternate").strip()
        if not href:
            continue
        if rel == "alternate":
            return href
        fallback = fallback or href
    return fallback


def reddit_source_url_is_usable(url: str) -> bool:
    parsed = urllib.parse.urlsplit(str(url or ""))
    return "reddit.com" in parsed.netloc.lower() and "/comments/" in parsed.path.lower()


def canonical_reddit_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    host = "www.reddit.com" if "reddit.com" in parsed.netloc.lower() else parsed.netloc
    return urllib.parse.urlunsplit(("https", host, parsed.path, "", ""))


def normalize_feed_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def reddit_post_candidate(url: str, source_name: str) -> dict[str, Any]:
    try:
        payload = request_reddit_json_with_fallback(reddit_post_attempts(url))
        post = (((payload or [{}])[0].get("data") or {}).get("children") or [{}])[0].get("data") or {}
        candidate = reddit_candidate(post)
    except SourceAccessError:
        feed_candidates = request_reddit_feed_with_fallback(reddit_post_feed_attempts(url))
        if not feed_candidates:
            raise SourceAccessError("reddit_post_feed_empty")
        candidate = feed_candidates[0]
    candidate["source_name"] = source_name or SOURCE_NAME_REDDIT
    candidate["source_url"] = url
    return candidate


def reddit_post_attempts(url: str) -> list[tuple[str, str]]:
    parsed = urllib.parse.urlsplit(url)
    path = parsed.path.rstrip("/")
    if path.endswith(".json"):
        path = path[:-5].rstrip("/")
    json_path = f"{path}/.json"
    attempts: list[tuple[str, str]] = []
    token = os.getenv("REDDIT_BEARER_TOKEN")
    if token:
        oauth_path = path
        attempts.append(("reddit_post_oauth", urllib.parse.urlunsplit(("https", "oauth.reddit.com", oauth_path, "", ""))))
    attempts.extend([
        ("reddit_post_www_json", urllib.parse.urlunsplit(("https", "www.reddit.com", json_path, "", ""))),
        ("reddit_post_old_json", urllib.parse.urlunsplit(("https", "old.reddit.com", json_path, "", ""))),
    ])
    post_id = reddit_post_id(url)
    if post_id:
        compact_path = f"/r/{REDDIT_SUBREDDIT}/comments/{post_id}/.json"
        attempts.extend([
            ("reddit_post_www_comments_json", urllib.parse.urlunsplit(("https", "www.reddit.com", compact_path, "", ""))),
            ("reddit_post_old_comments_json", urllib.parse.urlunsplit(("https", "old.reddit.com", compact_path, "", ""))),
        ])
    return attempts


def reddit_post_feed_attempts(url: str) -> list[tuple[str, str]]:
    parsed = urllib.parse.urlsplit(url)
    path = parsed.path.rstrip("/")
    if path.endswith(".rss"):
        path = path[:-4].rstrip("/")
    attempts = [
        ("reddit_post_www_atom", urllib.parse.urlunsplit(("https", "www.reddit.com", f"{path}/.rss", "", ""))),
        ("reddit_post_old_atom", urllib.parse.urlunsplit(("https", "old.reddit.com", f"{path}/.rss", "", ""))),
        ("reddit_post_www_rss_suffix", urllib.parse.urlunsplit(("https", "www.reddit.com", f"{path}.rss", "", ""))),
        ("reddit_post_old_rss_suffix", urllib.parse.urlunsplit(("https", "old.reddit.com", f"{path}.rss", "", ""))),
    ]
    post_id = reddit_post_id(url)
    if post_id:
        compact_path = f"/r/{REDDIT_SUBREDDIT}/comments/{post_id}"
        attempts.extend([
            ("reddit_post_www_comments_atom", urllib.parse.urlunsplit(("https", "www.reddit.com", f"{compact_path}/.rss", "", ""))),
            ("reddit_post_old_comments_atom", urllib.parse.urlunsplit(("https", "old.reddit.com", f"{compact_path}/.rss", "", ""))),
        ])
    return attempts


def reddit_post_id(url: str) -> str:
    parts = [part for part in urllib.parse.urlsplit(url).path.split("/") if part]
    for idx, part in enumerate(parts):
        if part == "comments" and idx + 1 < len(parts):
            candidate = parts[idx + 1].strip()
            if re.fullmatch(r"[A-Za-z0-9_]+", candidate):
                return candidate
    return ""


def source_probe_candidates(
    record: PatchRecord,
    context: CollectorContext,
    errors: list[dict[str, Any]],
    probes: tuple[dict[str, str], ...],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for probe in probes:
        if "reddit.com" in probe["source_url"]:
            try:
                candidates.append(reddit_post_candidate(probe["source_url"], probe.get("source_name", "")))
            except Exception as exc:
                errors.append({"source_url": probe["source_url"], "reason": f"reddit_post_fetch_failed:{error_reason(exc)}"})
            continue
        try:
            text = request_text(probe["source_url"])
        except Exception as exc:
            errors.append({"source_url": probe["source_url"], "reason": f"probe_fetch_failed:{error_reason(exc)}"})
            continue
        title = extract_title(text) or probe["source_url"]
        clean = clean_html(text)
        candidates.append({
            "source_type": probe["source_type"],
            "source_name": probe["source_name"],
            "source_url": probe["source_url"],
            "parent_title": title,
            "report_title": title,
            "report_text": clean[:4000],
            "source_date": extract_source_date(clean),
        })
    return candidates


def method_status(
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
        if any(token in reasons for token in ("blocked", "challenge", "waf", "captcha", "access_denied")):
            return "blocked"
        if "unusable" in reasons or "source_returned_non_forum_content" in reasons or "source_unusable_response" in reasons:
            return "low_confidence"
        return "broken"
    return "no_results"


def blocked_reason_from_errors(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return ""
    counts: dict[str, int] = {}
    for error in errors:
        reason = str(error.get("reason") or "fetch_failed")
        counts[reason] = counts.get(reason, 0) + 1
    return "; ".join(
        f"{reason} x{count}" if count > 1 else reason
        for reason, count in counts.items()
    )


def method_notes(method_id: str) -> str:
    notes = {
        "known_watchlist": "Temporary seed/calibration fallback. Specific known report URLs are fetched and passed through the same deterministic evidence gates, but this must not be the primary long-term DaVinci discovery method.",
        "reddit_search": "Subreddit search discovers candidate posts; RSS/Atom candidates are prefiltered to exact version hints, and accepted rows still require exact version/date/report gates.",
        "vendor_forum_search": "Blackmagic forum search uses exact version aliases plus issue-language terms to discover candidate threads; accepted rows still require exact version/date/report gates.",
        "web_search": "Reserved fallback discovery method; no adapter is configured in Phase A.",
    }
    return notes.get(method_id, "")


def row_from_candidate(record: PatchRecord, candidate: dict[str, Any], captured_at: str) -> dict[str, Any]:
    report_text = " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ])
    matched, matched_version, basis = exact_version_match(report_text, record.update_version, version_aliases(record.update_version))
    theme, workflow_area, platform, severity, sentiment = classify(report_text)
    row = make_evidence_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        source_type=str(candidate.get("source_type") or "community_report"),
        source_name=str(candidate.get("source_name") or "Community report"),
        source_url=str(candidate.get("source_url") or ""),
        parent_title=str(candidate.get("parent_title") or ""),
        report_title=str(candidate.get("report_title") or ""),
        report_text=str(candidate.get("report_text") or ""),
        captured_at=captured_at,
        source_date=date_part(candidate.get("source_date")),
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
        row_id=f"{PRODUCT_ID}-{slug(record.update_version)}-{slug(str(candidate.get('source_type') or 'source'))}-{slug(str(candidate.get('source_url') or ''))}",
    )
    gated = apply_acceptance_gates(row, report_text=report_text)
    if gated.get("counted") is True and is_stable_record(record.update_version) and beta_context_present(report_text):
        gated["counted"] = False
        gated["exclusion_reason"] = "beta_context_for_stable_record"
    if gated.get("counted") is True and not davinci_product_match(report_text):
        gated["counted"] = False
        gated["exclusion_reason"] = "missing_davinci_product_context"
    if gated.get("counted") is True and is_stable_record(record.update_version) and conflicting_stable_major_context(record.update_version, report_text):
        gated["counted"] = False
        gated["exclusion_reason"] = "conflicting_davinci_version_context"
    if gated.get("counted") is True and not davinci_strong_issue_match(report_text):
        gated["counted"] = False
        gated["exclusion_reason"] = "not_a_real_issue_report"
    return gated


def davinci_product_match(text: str) -> bool:
    return bool(PRODUCT_CONTEXT_RE.search(text or "") or VERSIONED_DAVINCI_CONTEXT_RE.search(text or ""))


def is_stable_record(version: str) -> bool:
    normalized = normalize_davinci_version(version)
    return bool(normalized.get("major_version")) and normalized.get("is_beta") is False


def beta_context_present(text: str) -> bool:
    return bool(BETA_CONTEXT_RE.search(text or ""))


def conflicting_stable_major_context(version: str, text: str) -> bool:
    normalized = normalize_davinci_version(version)
    major = int(normalized.get("major_version") or 0)
    if not major:
        return False
    for match in DAVINCI_VERSION_CONTEXT_RE.finditer(text or ""):
        try:
            matched_major = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if matched_major != major:
            return True
    return False


def davinci_strong_issue_match(text: str) -> bool:
    return bool(DAVINCI_STRONG_ISSUE_RE.search(text or ""))


def error_reason(exc: Exception) -> str:
    if isinstance(exc, SourceAccessError):
        return exc.reason
    return type(exc).__name__


def classify(text: str) -> tuple[str, str, str, str, str]:
    lowered = text.lower()
    platform = "unknown"
    for name in ("windows", "macos", "mac", "linux"):
        if name in lowered:
            platform = "macos" if name == "mac" else name
            break
    if "magic mask" in lowered and "crash" in lowered:
        return "magic mask crash", "color grading / Magic Mask", platform, "high", "negative"
    if "crash" in lowered or "won't open" in lowered or "does not open" in lowered:
        return "startup or application crash", "application stability", platform, "high", "negative"
    if "decode" in lowered or "render" in lowered or "export" in lowered:
        return "render/export failure", "render/export", platform, "medium", "negative"
    if "gpu" in lowered or "performance" in lowered or "lag" in lowered or "slow" in lowered:
        return "performance regression", "timeline / GPU performance", platform, "medium", "negative"
    if "plugin" in lowered or "codec" in lowered:
        return "compatibility issue", "plugins / codecs", platform, "medium", "negative"
    if "install" in lowered:
        return "install issue", "installation", platform, "medium", "negative"
    return "unspecified issue", "general DaVinci Resolve workflow", platform, "medium", "moderate"


def extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    if not match:
        return ""
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()


def clean_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_source_date(text: str) -> str:
    match = re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2}),\s+(20\d{2})", text)
    if not match:
        return ""
    month = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
    }.get(match.group(1))
    if not month:
        return ""
    return datetime(int(match.group(3)), month, int(match.group(2)), tzinfo=timezone.utc).date().isoformat()


def rejection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("exclusion_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def format_rejection_counts(rows: list[dict[str, Any]]) -> str:
    counts = rejection_counts(rows)
    return ", ".join(f"{reason}={count}" for reason, count in sorted(counts.items()))


def record_needs_count_update(record: PatchRecord, count: int) -> bool:
    data, _body = load_front_matter_and_body(record.path)
    for key in ("confirmed_patch_specific_report_count", "update_report_count"):
        value = data.get(key)
        if value not in (None, ""):
            try:
                return int(value) != count
            except (TypeError, ValueError):
                return True
    return count != 0


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
    comparable = {k: v for k, v in fields.items() if k != "status_events_append"}
    if all(data.get(k) == v for k, v in comparable.items()):
        return False
    _apply_record_fields(record_path, fields)
    return True
