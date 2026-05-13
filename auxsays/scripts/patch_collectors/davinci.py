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
import urllib.parse
import urllib.request
from urllib.error import HTTPError
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
REDDIT_SEARCH = "https://www.reddit.com/r/davinciresolve/search.json"
FORUM_SEARCH = "https://forum.blackmagicdesign.com/search.php"
TEXT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (compatible; AUXSAYS-DaVinci-Evidence-Collector/1.0; +https://auxsays.com/)",
}
JSON_HEADERS = {
    "Accept": "application/json,text/plain;q=0.8,*/*;q=0.5",
    "User-Agent": "Mozilla/5.0 (compatible; AUXSAYS-DaVinci-Evidence-Collector/1.0; +https://auxsays.com/)",
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
BETA_CONTEXT_RE = re.compile(r"\b(?:public\s+beta|beta\s*\d*|21\.0b\d*|21b\d+|21\.0b\s+build\s+20|build\s+20)\b", flags=re.I)


class SourceAccessError(RuntimeError):
    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status

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
        records = generated_records(PRODUCT_ID, context.target_versions, include_archived=False)
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
                if accepted and (added > 0 or record_needs_count_update(record, structured_count)):
                    record_updated = apply_consensus_writeback(record.update_version)
                result.update({
                    "evidence_rows_added": added,
                    "evidence_rows_total": total,
                    "structured_count_for_version": structured_count,
                    "davinci_record_updated": record_updated,
                })
            results.append(result)
        return results


def request_json(url: str) -> Any:
    headers = dict(JSON_HEADERS)
    token = os.getenv("REDDIT_BEARER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SourceAccessError(f"http_{exc.code}_{exc.reason}", status=exc.code) from exc


def request_text(url: str) -> str:
    request = urllib.request.Request(url, headers=TEXT_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(500_000)
            content_type = response.headers.get("content-type", "")
            status = response.status
    except HTTPError as exc:
        raise SourceAccessError(f"http_{exc.code}_{exc.reason}", status=exc.code) from exc
    charset = "utf-8"
    match = re.search(r"charset=([A-Za-z0-9_\-]+)", content_type)
    if match:
        charset = match.group(1)
    text = raw.decode(charset, errors="replace")
    if status == 202 and blackmagic_access_challenge(text):
        raise SourceAccessError("http_202_access_challenge", status=202)
    return text


def blackmagic_access_challenge(text: str) -> bool:
    lowered = text.lower()
    return "<title></title>" in lowered and "please enable javascript" in lowered or "checking your browser" in lowered


def version_aliases(version: str) -> list[str]:
    normalized = normalize_davinci_version(version)
    aliases = [
        f"DaVinci Resolve {version}",
        f"Resolve {version}",
        f"DaVinci Resolve Studio {version}",
    ]
    if normalized.get("is_beta") and int(normalized.get("beta_number") or 0) == 1:
        aliases.extend([
            "DaVinci Resolve 21.0 Public Beta 1",
            "DaVinci Resolve Studio 21.0 Public Beta 1",
            "Resolve 21.0 Public Beta 1",
            "Resolve Studio 21.0B Build 20",
            "DaVinci Resolve Studio 21.0B Build 20",
            "DaVinci Resolve 21.0b1",
            "Resolve 21.0b1",
            "DR 21 Public Beta 1",
            "DR 21 Beta 1",
            "DR 21b1",
        ])
    return aliases


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
        blocked_reason = "; ".join(str(error.get("reason") or "fetch_failed") for error in errors)
        notes = method_notes(method_id)
        if fetch_failure_count:
            notes = f"{notes} Fetch failures: {fetch_failure_count}."
        status = "disabled" if method_id == "web_search" else method_status(candidates, method_accepted, method_rejected, errors)
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
            url = f"{REDDIT_SEARCH}?{urllib.parse.urlencode(params)}"
            try:
                payload = request_json(url)
            except Exception as exc:
                errors.append({"query": query, "source_url": url, "reason": f"reddit_search_fetch_failed:{error_reason(exc)}"})
                break
            children = (((payload or {}).get("data") or {}).get("children") or [])
            for child in children:
                data = child.get("data") if isinstance(child, dict) else None
                if isinstance(data, dict):
                    candidates.append(reddit_candidate(data))
            after = ((payload or {}).get("data") or {}).get("after")
            if not after:
                break
    return candidates


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
            continue
        links.extend(re.findall(r"href=\"(viewtopic\.php\?[^\"#]+t=\d+[^\"#]*)", text, flags=re.I))
    candidates: list[dict[str, Any]] = []
    for link in sorted(set(links))[:25]:
        source_url = urllib.parse.urljoin("https://forum.blackmagicdesign.com/", html.unescape(link))
        try:
            page = request_text(source_url)
        except Exception as exc:
            errors.append({"source_url": source_url, "reason": f"vendor_forum_thread_fetch_failed:{error_reason(exc)}"})
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


def reddit_post_candidate(url: str, source_name: str) -> dict[str, Any]:
    json_url = url.rstrip("/") + "/.json"
    payload = request_json(json_url)
    post = (((payload or [{}])[0].get("data") or {}).get("children") or [{}])[0].get("data") or {}
    candidate = reddit_candidate(post)
    candidate["source_name"] = source_name or SOURCE_NAME_REDDIT
    candidate["source_url"] = url
    return candidate


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
        return "blocked" if "blocked" in reasons else "broken"
    return "no_results"


def method_notes(method_id: str) -> str:
    notes = {
        "known_watchlist": "Temporary seed/calibration fallback. Specific known report URLs are fetched and passed through the same deterministic evidence gates, but this must not be the primary long-term DaVinci discovery method.",
        "reddit_search": "Subreddit search discovers candidate posts; accepted rows still require exact version/date/report gates.",
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
    return gated


def davinci_product_match(text: str) -> bool:
    return bool(PRODUCT_CONTEXT_RE.search(text or ""))


def is_stable_record(version: str) -> bool:
    normalized = normalize_davinci_version(version)
    return bool(normalized.get("major_version")) and normalized.get("is_beta") is False


def beta_context_present(text: str) -> bool:
    return bool(BETA_CONTEXT_RE.search(text or ""))


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
