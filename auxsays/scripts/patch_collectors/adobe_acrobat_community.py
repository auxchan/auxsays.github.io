"""Shared Adobe Acrobat (Reader + Acrobat Pro) COMMUNITY-EVIDENCE collector.

One config-driven `ProductCollector` serves BOTH editions. It is registered per edition
(`AdobeAcrobatCollector(READER_ID)` and `(PRO_ID)`), so each instance discovers, filters,
and writes evidence for exactly one `product_id`. Because consensus writeback is keyed by
`(product_id, update_version)`, Reader and Pro (which share the same DC build number) can
NEVER cross-contaminate.

Doctrine (fail-closed, deterministic, no AI/manual dependency):
- Multi-method discovery: Adobe Community search (HTML) + Reddit (shared `reddit_source`).
  Each method emits diagnosable method health; a blocked method degrades and the run
  continues.
- A community report counts ONLY when it passes, in order: exact-edition attribution →
  exact current DC-build version match → specific thread/post URL → source date on/after
  the official release date → a concrete post-install user-facing issue → not an official
  announcement/release-note. Every gate failure records a precise `exclusion_reason`.
- Edition attribution never guesses: bare "Acrobat"/"Adobe Acrobat"/"PDF app"/bare "Reader"
  fail closed; the opposite edition is `wrong_product`; only an explicit both-editions report
  counts for both (with explicit `applicability`).
- Official ingestion / release notes are NEVER counted as community evidence.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError

from . import reddit_source
from .base import (
    CollectorContext,
    EVIDENCE_PATH,
    PatchRecord,
    ProductCollector,
    append_evidence_rows,
    counted_rows,
    date_part,
    exact_version_match,
    generated_records,
    make_evidence_row,
    method_health_row,
    slug,
    source_url_is_specific,
    utc_now,
)

READER_ID = "adobe-acrobat-reader"
PRO_ID = "adobe-acrobat-pro"
ACROBAT_PRODUCT_IDS = (READER_ID, PRO_ID)

ADOBE_COMMUNITY_SOURCE_TYPE = "adobe_community_bug_report"
REDDIT_SOURCE_TYPE = "reddit_community_report"

ADOBE_SEARCH_URL = (
    "https://community.adobe.com/t5/forums/searchpage/tab/message"
    "?advanced=false&allow_punctuation=false&q={query}&page={page}"
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AUXSAYS-patch-intelligence/1.0; +https://auxsays.com)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}
MAX_SEARCH_QUERIES = 3
MAX_SEARCH_PAGES = 1

# --- edition attribution (never inferred) ------------------------------------
READER_RE = re.compile(r"\b(?:adobe\s+)?acrobat\s+reader(?:\s+dc)?\b|\badobe\s+reader\b|\breader\s+dc\b", re.I)
PRO_RE = re.compile(r"\b(?:adobe\s+)?acrobat\s+pro(?:\s+dc)?\b|\badobe\s+acrobat\s+dc\s+pro\b", re.I)
ACROBAT_BARE_RE = re.compile(r"\b(?:adobe\s+)?acrobat\b", re.I)

EDITION_CONFIG: dict[str, dict[str, Any]] = {
    READER_ID: {
        "software": "Adobe Acrobat Reader",
        "subreddits": ("Acrobat", "Adobe", "pdf"),
        "query_products": ("Acrobat Reader", "Adobe Acrobat Reader"),
    },
    PRO_ID: {
        "software": "Adobe Acrobat Pro",
        "subreddits": ("Acrobat", "Adobe", "pdf"),
        "query_products": ("Acrobat Pro", "Adobe Acrobat Pro"),
    },
}

# --- concrete post-install issue (Acrobat-specific) --------------------------
# Terminal "failure" verbs allowing common suffixes (fails/failed/failure/errors/...).
_F = r"(?:fail(?:s|ed|ure)?|error(?:s|ed)?|broke|broken|invalid|problem|issue)"
ACROBAT_STRONG_ISSUE_RE = re.compile(
    r"\b(?:crash(?:e[sd])?"
    r"|won'?t\s+(?:open|launch|install|start|print)"
    r"|(?:fail(?:s|ed|ure)?|unable)\s+to\s+(?:install|update|open|launch|print|sign|save|load|activate)"
    rf"|install(?:ation)?\s+{_F}"
    rf"|update\s+{_F}"
    rf"|print(?:ing)?\s+(?:{_F}|regression|blank)"
    r"|(?:pdf|render(?:ing)?|display)\s+(?:blank|broken|garbled|corrupt|wrong|not\s+render)"
    r"|form(?:s|\s+field)?\s+(?:broke|broken|not\s+work|fail(?:s|ed|ure)?|blank)"
    rf"|(?:signature|signing|certificate)\s+{_F}"
    r"|freeze[sd]?|frozen|hang(?:s|ing)?|not\s+responding|high\s+(?:cpu|memory)|memory\s+leak"
    r"|corrupt(?:ed|ion)?|data\s+loss"
    rf"|deploy(?:ment)?\s+{_F}|licens(?:e|ing)\s+{_F}|activation\s+{_F}"
    r"|(?:plugin|add-?in|extension)\s+(?:broke|broken|not\s+work|crash(?:e[sd])?|incompat\w*)"
    r"|regression|broke\s+after|broken\s+after|stopped\s+working\s+after|no\s+longer\s+works)\b",
    re.I,
)
ACROBAT_NON_REPORT_RE = re.compile(
    r"\b(release\s+notes|what'?s\s+new|announcing|announcement|new\s+feature|feature\s+request|"
    r"please\s+add|would\s+be\s+nice|pric(?:e|ing)|subscription\s+cost|too\s+expensive|refund|"
    r"how\s+do\s+i|how\s+to)\b",
    re.I,
)
_GENUINE_FAILURE_RE = re.compile(r"\b(crash|fail|broke|broken|error|corrupt|freeze|hang|regression|not\s+responding)\b", re.I)

# --- specific Adobe Community thread/message URL -----------------------------
_ADOBE_THREAD_RE = re.compile(r"/t5/[^/]+/[^/]+/(?:td-p|m-p|idi-p)/\d+", re.I)
_ADOBE_BUG_RE = re.compile(r"/bug-reports?[-\w]*/[\w%-]+/\d+", re.I)
_HREF_RE = re.compile(r'href=["\'](https?://community\.adobe\.com[^"\']+)["\']', re.I)
_TAG_RE = re.compile(r"(?is)<(script|style|noscript).*?</\1>|<[^>]+>")
_OG_TITLE_RE = re.compile(r"""<meta\s+property=["']og:title["']\s+content=["']([^"']+)["']""", re.I)
_H1_RE = re.compile(r"(?is)<h1[^>]*>(.*?)</h1>")
_TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")


class AcrobatCommunityAccessError(RuntimeError):
    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


def acrobat_edition_attribution(text: str, product_id: str) -> tuple[bool, str, str, str | None]:
    """Deterministic, non-inferred edition attribution.

    Returns (attributed, matched_alias, applicability_csv, exclusion_reason). A report counts
    for an edition only when that edition is explicitly named; an explicit both-editions report
    counts for both; bare Acrobat / bare Reader / opposite edition fail closed.
    """
    has_reader = bool(READER_RE.search(text or ""))
    has_pro = bool(PRO_RE.search(text or ""))
    if has_reader and has_pro:
        return True, "acrobat reader + acrobat pro", f"{READER_ID},{PRO_ID}", None
    if product_id == READER_ID:
        if has_reader:
            return True, "acrobat reader", READER_ID, None
        if has_pro:
            return False, "", "", "wrong_product"
    if product_id == PRO_ID:
        if has_pro:
            return True, "acrobat pro", PRO_ID, None
        if has_reader:
            return False, "", "", "wrong_product"
    if ACROBAT_BARE_RE.search(text or ""):
        return False, "", "", "generic_acrobat_without_edition"
    return False, "", "", "missing_product_attribution"


def acrobat_strong_issue_match(text: str) -> bool:
    lowered = (text or "").lower()
    if not ACROBAT_STRONG_ISSUE_RE.search(lowered):
        return False
    if ACROBAT_NON_REPORT_RE.search(lowered) and not _GENUINE_FAILURE_RE.search(lowered):
        return False
    return True


def acrobat_url_is_specific(url: str) -> bool:
    parsed = urllib.parse.urlparse(url or "")
    if "community.adobe.com" not in parsed.netloc.lower():
        return False
    path = parsed.path.lower()
    if "/announcement" in path or path.rstrip("/").endswith(("/search", "/searchpage")):
        return False
    return bool(_ADOBE_THREAD_RE.search(path) or _ADOBE_BUG_RE.search(path))


def _url_specific(url: str, source_type: str) -> bool:
    """Adobe Community requires a specific thread/message/bug URL (stricter than base's
    generic community.adobe.com fallback); Reddit and other hosts use the shared gate."""
    if source_type == ADOBE_COMMUNITY_SOURCE_TYPE:
        return acrobat_url_is_specific(url)
    return source_url_is_specific(url)


def acrobat_classify(text: str) -> tuple[str, str, str, str, str]:
    lowered = (text or "").lower()
    platform = "unknown"
    for token, label in (("windows", "windows"), ("macos", "macos"), ("mac os", "macos"), ("mac ", "macos")):
        if token in lowered:
            platform = label
            break
    if "print" in lowered:
        return "printing regression", "printing", platform, "high", "negative"
    if "sign" in lowered or "certificate" in lowered:
        return "signing/certificate failure", "e-signatures", platform, "high", "negative"
    if "form" in lowered:
        return "form behavior regression", "forms", platform, "high", "negative"
    if "install" in lowered or "update" in lowered or "deploy" in lowered:
        return "install/update failure", "deployment", platform, "high", "negative"
    if "render" in lowered or "display" in lowered or "blank" in lowered:
        return "PDF rendering regression", "PDF rendering", platform, "high", "negative"
    if "browser" in lowered or "plugin" in lowered or "add-in" in lowered or "extension" in lowered:
        return "browser/plugin handoff failure", "browser integration", platform, "medium", "negative"
    if "cpu" in lowered or "memory" in lowered or "slow" in lowered or "performance" in lowered:
        return "performance regression", "performance", platform, "medium", "negative"
    if "crash" in lowered or "freeze" in lowered or "hang" in lowered:
        return "crash or launch failure", "application stability", platform, "high", "negative"
    return "unspecified Acrobat issue", "Acrobat workflow", platform, "medium", "negative"


# --- HTTP (Adobe Community) ---------------------------------------------------

def _request_text(url: str, timeout: int = 30, max_bytes: int = 800000) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", None)
            content_type = response.headers.get("Content-Type", "")
            body = response.read(max_bytes).decode("utf-8", errors="replace")
    except HTTPError as exc:
        try:
            body = exc.read(8000).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        raise AcrobatCommunityAccessError(_blocked_signature(body, status=exc.code), status=exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AcrobatCommunityAccessError(f"network_{type(exc).__name__}") from exc
    signature = _blocked_signature(body, status=status, content_type=content_type)
    if signature != "none":
        raise AcrobatCommunityAccessError(signature, status=status)
    return body


def _blocked_signature(text: str, *, status: int | None = None, content_type: str = "") -> str:
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
    return "none"


def _error_is_blocked(exc: Exception) -> bool:
    reason = getattr(exc, "reason", type(exc).__name__).lower()
    return any(token in reason for token in ("blocked", "challenge", "captcha", "rate_limited", "http_401", "http_403", "http_429"))


def _clean_html(html_text: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", html_text or ""))).strip()


def _extract_title(html_text: str) -> str:
    for pattern in (_OG_TITLE_RE, _H1_RE, _TITLE_RE):
        match = pattern.search(html_text or "")
        if match:
            title = unescape(_TAG_RE.sub(" ", match.group(1))).strip()
            title = re.sub(r"\s*[-|]\s*Adobe (?:Community|Support Community).*$", "", title).strip()
            if title:
                return title
    return ""


def _canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunsplit(("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


# --- discovery methods --------------------------------------------------------

def _search_queries(edition: dict[str, Any], version: str) -> list[str]:
    queries: list[str] = []
    for product in edition["query_products"]:
        queries.append(f'"{product} {version}"')
    return queries[:MAX_SEARCH_QUERIES]


def adobe_community_search_candidates(
    edition: dict[str, Any], record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in _search_queries(edition, record.update_version):
        for page in range(1, min(MAX_SEARCH_PAGES, max(1, context.max_pages)) + 1):
            url = ADOBE_SEARCH_URL.format(query=urllib.parse.quote(query), page=page)
            try:
                html_text = _request_text(url)
            except Exception as exc:  # noqa: BLE001
                errors.append({"source_url": url, "reason": f"adobe_community_search_fetch_failed:{getattr(exc, 'reason', type(exc).__name__)}"})
                if _error_is_blocked(exc):
                    return candidates
                break
            for link in _HREF_RE.findall(html_text):
                canonical = _canonical_url(link)
                if not canonical or not acrobat_url_is_specific(canonical) or canonical.lower() in seen:
                    continue
                seen.add(canonical.lower())
                try:
                    thread_html = _request_text(canonical)
                except Exception as exc:  # noqa: BLE001
                    errors.append({"source_url": canonical, "reason": f"adobe_community_thread_fetch_failed:{getattr(exc, 'reason', type(exc).__name__)}"})
                    if _error_is_blocked(exc):
                        return candidates
                    continue
                title = _extract_title(thread_html)
                text = _clean_html(thread_html)[:6000]
                candidates.append({
                    "source_type": ADOBE_COMMUNITY_SOURCE_TYPE,
                    "source_name": "Adobe Community",
                    "source_url": canonical,
                    "parent_title": title,
                    "report_title": title,
                    "report_text": text,
                    "source_date": "",
                })
    return candidates


def reddit_search_candidates(
    edition: dict[str, Any], record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    queries: list[str] = []
    for product in edition["query_products"]:
        queries.append(f'{product} {record.update_version}')
    return reddit_source.collect_reddit_candidates(
        subreddits=edition["subreddits"],
        queries=queries,
        context=context,
        errors=errors,
        source_type=REDDIT_SOURCE_TYPE,
        version_hints=[record.update_version],
    )


# --- acceptance ---------------------------------------------------------------

def row_from_candidate(product_id: str, record: PatchRecord, candidate: dict[str, Any], captured_at: str) -> dict[str, Any]:
    report_text = " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ])
    matched, matched_version, basis = exact_version_match(report_text, record.update_version)
    attributed, alias, applicability, edition_reason = acrobat_edition_attribution(report_text, product_id)
    theme, workflow_area, platform, severity, sentiment = acrobat_classify(report_text)
    source_date = date_part(candidate.get("source_date"))
    source_type = str(candidate.get("source_type") or ADOBE_COMMUNITY_SOURCE_TYPE)

    row = make_evidence_row(
        product_id=product_id,
        update_version=record.update_version,
        source_type=source_type,
        source_name=str(candidate.get("source_name") or "Adobe Community"),
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
        matched_product_alias=alias,
        applicability=applicability,
        counted=False,
        exclusion_reason=None,
        issue_theme=theme,
        workflow_area=workflow_area,
        platform=platform,
        severity=severity,
        sentiment=sentiment,
        row_id=f"{product_id}-{slug(record.update_version)}-{slug(source_type)}-{slug(str(candidate.get('source_url') or ''))}",
    )
    source_date_pass = row.get("source_date_pass")
    if not source_date:
        row["source_date_pass"] = None
        source_date_pass = None

    # Fail-closed gate order (Part C): 1 exact-edition attribution -> 2 exact current
    # DC-build version -> 3 specific thread/post URL -> 4 source date >= release date ->
    # 5 concrete post-install issue. The FIRST failing gate sets the exclusion reason, so an
    # ambiguous / wrong-edition report is never masked by a later reason.
    reason: str | None = None
    if not attributed:
        reason = edition_reason or "missing_product_attribution"
    elif not matched:
        reason = "missing_exact_patch_version_match"
    elif not _url_specific(str(row.get("source_url") or ""), source_type):
        reason = "source_url_not_specific_report"
    elif source_date_pass is False:
        reason = "source_date_before_or_unverified_against_release"
    elif not acrobat_strong_issue_match(report_text):
        reason = "not_a_real_issue_report"

    row["counted"] = reason is None
    row["exclusion_reason"] = reason
    row["source_weight"] = 1
    return row


def evaluate_candidates(product_id: str, record: PatchRecord, candidates: list[dict[str, Any]], captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = _canonical_url(str(candidate.get("source_url") or ""))
        if not url or url.lower() in seen:
            continue
        seen.add(url.lower())
        row = row_from_candidate(product_id, record, {**candidate, "source_url": url}, captured_at)
        (accepted if row.get("counted") is True else rejected).append(row)
    return accepted, rejected


def _method_status(candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if accepted and errors:
        return "partial"
    if accepted:
        return "success"
    if candidates and errors:
        return "partial"
    if candidates:
        return "no_results"
    if errors:
        reasons = " ".join(str(e.get("reason") or "") for e in errors).lower()
        if any(token in reasons for token in ("blocked", "challenge", "captcha", "rate_limited", "http_401", "http_403", "http_429")):
            return "blocked"
        return "broken"
    return "no_results"


def _blocked_reason(errors: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for error in errors:
        reason = str(error.get("reason") or "fetch_failed")
        counts[reason] = counts.get(reason, 0) + 1
    return "; ".join(f"{reason} x{count}" if count > 1 else reason for reason, count in counts.items())


def apply_consensus_writeback(product_id: str, update_version: str) -> bool:
    from apply_consensus_to_records import _apply_record_fields, _index_generated_records, run_dry_run
    from patch_collectors.base import load_front_matter_and_body

    records_index = _index_generated_records()
    results = run_dry_run(
        evidence_path=EVIDENCE_PATH,
        product_id_filter=product_id,
        is_candidate_mode=False,
        records_index=records_index,
        write_requested=True,
    )
    matches = [item for item in results if item["update_version"] == update_version]
    if len(matches) != 1 or not matches[0].get("would_write"):
        return False
    result = matches[0]
    key = (product_id, update_version)
    if key not in records_index:
        return False
    record_path = records_index[key]["abs_path"]
    fields = dict(result["proposed_fields_if_written"])
    data, _body = load_front_matter_and_body(record_path)
    comparable = {k: v for k, v in fields.items() if k != "status_events_append"}
    if all(data.get(k) == v for k, v in comparable.items()):
        return False
    _apply_record_fields(record_path, fields)
    return True


class AdobeAcrobatCollector(ProductCollector):
    """Community-evidence collector for one Acrobat edition (Reader or Pro)."""

    def __init__(self, product_id: str) -> None:
        if product_id not in EDITION_CONFIG:
            raise ValueError(f"unsupported acrobat product_id: {product_id}")
        self.product_id = product_id
        self.edition = EDITION_CONFIG[product_id]

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        captured_at = utc_now()
        results: list[dict[str, Any]] = []
        records = generated_records(self.product_id, context.target_versions, include_archived=bool(context.target_versions))
        for record in records:
            accepted, rejected, method_health = self.collect_for_record(record, context, captured_at)
            result: dict[str, Any] = {
                "product_id": self.product_id,
                "version": record.update_version,
                "mode": "write" if context.write else "dry-run",
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [row["source_url"] for row in accepted],
                "rejection_reasons": _rejection_counts(rejected),
                "method_health": method_health,
            }
            if context.write:
                added, total, rows = append_evidence_rows(accepted)
                structured = len(counted_rows(rows, self.product_id, record.update_version))
                record_updated = apply_consensus_writeback(self.product_id, record.update_version) if accepted else False
                result.update({
                    "evidence_rows_added": added,
                    "evidence_rows_total": total,
                    "counted_for_version": structured,
                    "record_updated": record_updated,
                })
            results.append(result)
        return results

    def collect_for_record(self, record: PatchRecord, context: CollectorContext, captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        methods = (
            ("adobe_community_search", ADOBE_COMMUNITY_SOURCE_TYPE, adobe_community_search_candidates),
            ("reddit_search", REDDIT_SOURCE_TYPE, reddit_search_candidates),
        )
        all_accepted: list[dict[str, Any]] = []
        all_rejected: list[dict[str, Any]] = []
        method_health: list[dict[str, Any]] = []
        accepted_urls: set[str] = set()
        for method_id, source_type, fn in methods:
            errors: list[dict[str, Any]] = []
            candidates = fn(self.edition, record, context, errors)
            accepted, rejected = evaluate_candidates(self.product_id, record, candidates, captured_at)
            for row in accepted:
                url = str(row.get("source_url") or "").lower()
                if url in accepted_urls:
                    continue
                accepted_urls.add(url)
                all_accepted.append(row)
            all_rejected.extend(rejected)
            method_health.append(method_health_row(
                product_id=self.product_id,
                update_version=record.update_version,
                method_id=method_id,
                source_type=source_type,
                status=_method_status(candidates, accepted, rejected, errors),
                candidates_found=len(candidates),
                accepted_reports=len(accepted),
                rejected_reports=len(rejected),
                blocked_reason=_blocked_reason(errors) or None,
                last_run=captured_at,
                notes=f"acrobat community collector; edition={self.product_id}",
            ))
        return all_accepted, all_rejected, method_health


def _rejection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("exclusion_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts
