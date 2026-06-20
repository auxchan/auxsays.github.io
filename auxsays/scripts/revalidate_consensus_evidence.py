#!/usr/bin/env python3
"""Dry-run classification and live revalidation harness for evidence rows.

Without --live-fetch, this script reads structured evidence from an explicit
input path, classifies rows for a product/version, and never fetches URLs. With
--live-fetch, it may fetch supported source URLs. Generated freshness writeback
is available only through an explicit OBS 32.1.1 guard path.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - used in lightweight local shells.
    yaml = None


MODE = "dry_run_fixture_revalidation_no_fetch_no_write"
LIVE_MODE = "dry_run_live_revalidation_no_write"
WRITEBACK_MODE = "live_revalidation_guarded_generated_freshness_writeback"
CLASSIFICATIONS = (
    "pending_source_adapter",
    "unsupported_source_type",
    "missing_url",
    "malformed_row",
    "candidate_for_revalidation",
)
LIVE_CLASSIFICATIONS = (
    "verified",
    "exact_version_failed",
    "fetch_failed",
    "blocked",
    "unsupported_source_type",
    "malformed_row",
)
CORE_FIELDS = ("product_id", "update_version", "source_type")
REVALIDATION_CANDIDATE_SOURCE_TYPES = {
    "github_issue",
}
CREATIVE_COW_SOURCE_TYPES = {
    "creativecow_forum_report",
    "creator_forum_report",
}
PENDING_SOURCE_ADAPTER_TYPES = {
    "adobe_community_bug_report",
    "adobe_community_listing_card",
    "blackmagic_forum",
    "curated_watchlist",
    "reddit_community_report",
}
GITHUB_API_ROOT = "https://api.github.com"
GITHUB_COMMENT_RE = re.compile(r"(?:^|[-_])comment-(\d+)$|issuecomment-(\d+)", flags=re.I)
CREATIVE_COW_THREAD_RE = re.compile(r"^/forums/thread/[^/?#]+/?$", flags=re.I)
EXPECTED_WRITEBACK_PRODUCT = "obs-studio"
EXPECTED_WRITEBACK_VERSION = "32.1.1"
EXPECTED_WRITEBACK_COUNTED_ROWS = 40
EXPECTED_WRITEBACK_GENERATED_FILE = "2026-04-02-obs-studio-32-1-1.md"
EXPECTED_WRITEBACK_EVIDENCE_STATE = "pilot_sample"
EXPECTED_WRITEBACK_CONSENSUS_STATUS = "pilot_initial_sample"


class SourceFetchError(RuntimeError):
    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def simple_evidence_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    saw_evidence_key = any(line.strip() == "evidence:" for line in text.splitlines())
    in_evidence = not saw_evidence_key

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        stripped = raw_line.strip()
        top_level = not raw_line.startswith((" ", "\t"))
        if top_level and stripped == "evidence:":
            in_evidence = True
            continue
        if top_level and saw_evidence_key and not stripped.startswith("- ") and stripped.endswith(":"):
            in_evidence = stripped == "evidence:"
            continue
        if stripped.startswith("- ") and in_evidence:
            if current:
                rows.append(current)
            current = {}
            remainder = stripped[2:]
            if ":" in remainder:
                key, value = remainder.split(":", 1)
                current[key.strip()] = parse_scalar(value)
            continue
        if current is not None and in_evidence and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = parse_scalar(value)
    if current:
        rows.append(current)
    return rows


def load_evidence_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        payload = yaml.safe_load(text) or {}
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            evidence = payload.get("evidence") or []
            return [item for item in evidence if isinstance(item, dict)]
        return []
    return simple_evidence_rows(text)


def simple_front_matter_mapping(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("generated record is missing YAML front matter")
    for raw_line in lines[1:]:
        if raw_line.strip() == "---":
            return data
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")) or raw_line.lstrip().startswith("- "):
            continue
        stripped = raw_line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    raise ValueError("generated record front matter is not closed")


def load_generated_record_metadata(path: Path) -> dict[str, Any]:
    return simple_front_matter_mapping(path.read_text(encoding="utf-8"))


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def replace_evidence_last_checked(path: Path, timestamp: str) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    in_front_matter = False
    for index, line in enumerate(lines):
        if index == 0 and line.strip() == "---":
            in_front_matter = True
            continue
        if in_front_matter and line.strip() == "---":
            break
        if in_front_matter and re.match(r"^evidence_last_checked\s*:", line):
            before = parse_scalar(line.split(":", 1)[1])
            newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            lines[index] = f"evidence_last_checked: '{timestamp}'{newline}"
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write("".join(lines))
            return str(before or "")
    raise ValueError("generated record is missing evidence_last_checked")


def is_counted(row: dict[str, Any]) -> bool:
    return row.get("counted") is True


def selected_rows(rows: list[dict[str, Any]], product_id: str, update_version: str) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("product_id") or "").strip() == product_id
        and str(row.get("update_version") or "").strip() == update_version
        and is_counted(row)
    ]


def exact_version_re(version: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![0-9.]){re.escape(version)}(?!\.\d|[0-9])")


def github_api_token() -> str:
    github_token = os.getenv("GITHUB_TOKEN", "").strip()
    if github_token:
        return github_token
    return os.getenv("GH_TOKEN", "").strip()


def github_http_error_reason(exc: HTTPError) -> str:
    if exc.code in {403, 429}:
        remaining = str(exc.headers.get("x-ratelimit-remaining") or "").strip()
        reset = str(exc.headers.get("x-ratelimit-reset") or "").strip()
        if remaining == "0":
            suffix = f"_until_{reset}" if reset else ""
            return f"github_rate_limited{suffix}"
        return f"github_api_blocked_http_{exc.code}"
    return f"http_{exc.code}"


def request_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AUXSAYS-Evidence-Revalidation-Dry-Run",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = github_api_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SourceFetchError(github_http_error_reason(exc), status=exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise SourceFetchError(type(exc).__name__) from exc
    except json.JSONDecodeError as exc:
        raise SourceFetchError("invalid_json_response") from exc


def request_text(url: str) -> str:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        "User-Agent": "AUXSAYS-Evidence-Revalidation-Dry-Run",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, "replace")
    except HTTPError as exc:
        raise SourceFetchError(f"http_{exc.code}", status=exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise SourceFetchError(type(exc).__name__) from exc


def blocked_fetch_error(exc: SourceFetchError) -> bool:
    reason = exc.reason.lower()
    return exc.status in {403, 429} or "rate" in reason or "blocked" in reason


def clean_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", text or "")
    text = re.sub(r"(?is)<br\s*/?>", " ", text)
    text = re.sub(r"(?is)</p\s*>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def html_title(text: str) -> str:
    for pattern in (
        r"""<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']""",
        r"""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:title["']""",
        r"""<title[^>]*>(.*?)</title>""",
    ):
        match = re.search(pattern, text or "", flags=re.I | re.S)
        if match:
            return clean_html(match.group(1))
    return ""


def blocked_html_reason(text: str) -> str:
    lowered = clean_html(text).lower()
    challenge_markers = (
        "access denied",
        "browser challenge",
        "checking your browser",
        "enable javascript and cookies",
        "rate limit",
        "too many requests",
        "unusual traffic",
        "verify you are human",
    )
    for marker in challenge_markers:
        if marker in lowered:
            return marker.replace(" ", "_")
    return ""


def github_comment_id(fragment: str) -> str:
    match = GITHUB_COMMENT_RE.search(fragment or "")
    if not match:
        return ""
    return str(match.group(1) or match.group(2) or "").strip()


def parse_github_reference(source_url: str) -> tuple[dict[str, str] | None, str]:
    parsed = urllib.parse.urlsplit(source_url)
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host == "github.com" and len(parts) >= 4 and parts[2] == "issues":
        issue_number = parts[3]
        if not issue_number.isdigit():
            return None, "github issue URL has a non-numeric issue number"
        return ({
            "owner": parts[0],
            "repo": parts[1],
            "issue_number": issue_number,
            "comment_id": github_comment_id(parsed.fragment),
        }, "")
    if host == "api.github.com" and len(parts) >= 5 and parts[0] == "repos" and parts[3] == "issues":
        if parts[4] == "comments" and len(parts) >= 6 and parts[5].isdigit():
            return None, "api.github.com issue-comment URLs need a github.com parent issue URL"
        if parts[4].isdigit():
            return ({
                "owner": parts[1],
                "repo": parts[2],
                "issue_number": parts[4],
                "comment_id": "",
            }, "")
    return None, "source_url is not a supported GitHub issue URL"


def parse_creativecow_thread_reference(source_url: str) -> tuple[str | None, str]:
    parsed = urllib.parse.urlsplit(source_url)
    host = parsed.netloc.lower()
    if host not in {"creativecow.net", "www.creativecow.net"}:
        return None, "source_url is not a Creative COW thread URL"
    if not CREATIVE_COW_THREAD_RE.match(parsed.path or ""):
        return None, "source_url is not a specific Creative COW thread URL"
    path = parsed.path.rstrip("/") + "/"
    return urllib.parse.urlunsplit(("https", "creativecow.net", path, "", "")), ""


def issue_api_url(reference: dict[str, str]) -> str:
    owner = urllib.parse.quote(reference["owner"], safe="")
    repo = urllib.parse.quote(reference["repo"], safe="")
    issue_number = urllib.parse.quote(reference["issue_number"], safe="")
    return f"{GITHUB_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}"


def comment_api_url(reference: dict[str, str]) -> str:
    owner = urllib.parse.quote(reference["owner"], safe="")
    repo = urllib.parse.quote(reference["repo"], safe="")
    comment_id = urllib.parse.quote(reference["comment_id"], safe="")
    return f"{GITHUB_API_ROOT}/repos/{owner}/{repo}/issues/comments/{comment_id}"


def fetched_text_context(reference: dict[str, str], fetch_json: Any) -> tuple[dict[str, str], str]:
    issue = fetch_json(issue_api_url(reference))
    if not isinstance(issue, dict):
        raise SourceFetchError("github_issue_payload_not_object")
    context = {
        "issue_title": str(issue.get("title") or ""),
        "issue_body": str(issue.get("body") or ""),
        "comment_body": "",
    }
    if reference.get("comment_id"):
        comment = fetch_json(comment_api_url(reference))
        if not isinstance(comment, dict):
            raise SourceFetchError("github_comment_payload_not_object")
        context["comment_body"] = str(comment.get("body") or "")
        return context, "comment"
    return context, "issue"


def exact_version_basis(context: dict[str, str], source_kind: str, version: str) -> str:
    pattern = exact_version_re(version)
    fields = (
        ("comment_body", context.get("comment_body", "")),
        ("parent_issue_title", context.get("issue_title", "")),
        ("parent_issue_body", context.get("issue_body", "")),
    ) if source_kind == "comment" else (
        ("issue_title", context.get("issue_title", "")),
        ("issue_body", context.get("issue_body", "")),
    )
    for basis, text in fields:
        if pattern.search(text or ""):
            return basis
    return ""


def creativecow_exact_version_basis(raw_html: str, version: str) -> str:
    pattern = exact_version_re(version)
    title = html_title(raw_html)
    if pattern.search(title):
        return "creativecow_thread_title"
    text = clean_html(raw_html)
    if pattern.search(text):
        return "creativecow_thread_text"
    return ""


def classify_row(row: dict[str, Any]) -> tuple[str, str]:
    missing_core = [field for field in CORE_FIELDS if row.get(field) in (None, "")]
    if missing_core:
        return ("malformed_row", "missing core field(s): " + ", ".join(missing_core))
    if row.get("patch_version_matched") is not True:
        return ("malformed_row", "patch_version_matched is not true")
    source_url = str(row.get("source_url") or "").strip()
    if not source_url:
        return ("missing_url", "source_url is missing")
    source_type = str(row.get("source_type") or "").strip()
    if source_type in REVALIDATION_CANDIDATE_SOURCE_TYPES:
        return ("candidate_for_revalidation", "source type has a fixture-safe adapter contract")
    if source_type in CREATIVE_COW_SOURCE_TYPES:
        reference, _ = parse_creativecow_thread_reference(source_url)
        if reference:
            return ("candidate_for_revalidation", "Creative COW thread URL has a dry-run adapter contract")
        return ("pending_source_adapter", "creator forum source is known but this URL is not a supported Creative COW thread")
    if source_type in PENDING_SOURCE_ADAPTER_TYPES:
        return ("pending_source_adapter", "source type is known but has no revalidation adapter in this harness")
    return ("unsupported_source_type", f"unsupported source_type: {source_type}")


def live_classify_creativecow_thread(row: dict[str, Any], update_version: str, fetch_text: Any) -> tuple[str, str, str]:
    source_url = str(row.get("source_url") or "").strip()
    if not source_url:
        return ("malformed_row", "source_url is missing", "")
    reference, parse_error = parse_creativecow_thread_reference(source_url)
    if reference is None:
        return ("malformed_row", parse_error, "")
    try:
        raw_html = fetch_text(reference)
    except SourceFetchError as exc:
        if blocked_fetch_error(exc):
            return ("blocked", exc.reason, "")
        return ("fetch_failed", exc.reason, "")
    if not isinstance(raw_html, str):
        return ("fetch_failed", "creativecow_thread_payload_not_text", "")
    blocked_reason = blocked_html_reason(raw_html)
    if blocked_reason:
        return ("blocked", blocked_reason, "")
    basis = creativecow_exact_version_basis(raw_html, update_version)
    if basis:
        return ("verified", f"exact version matched in {basis}", basis)
    return ("exact_version_failed", "target version was not found in fetched Creative COW thread text", "")


def live_classify_row(row: dict[str, Any], update_version: str, fetch_json: Any, fetch_text: Any) -> tuple[str, str, str]:
    missing_core = [field for field in CORE_FIELDS if row.get(field) in (None, "")]
    if missing_core:
        return ("malformed_row", "missing core field(s): " + ", ".join(missing_core), "")
    if row.get("patch_version_matched") is not True:
        return ("malformed_row", "patch_version_matched is not true", "")
    source_type = str(row.get("source_type") or "").strip()
    if source_type in CREATIVE_COW_SOURCE_TYPES:
        return live_classify_creativecow_thread(row, update_version, fetch_text)
    if source_type != "github_issue":
        return ("unsupported_source_type", f"unsupported source_type for live fetch: {source_type}", "")
    source_url = str(row.get("source_url") or "").strip()
    if not source_url:
        return ("malformed_row", "source_url is missing", "")
    reference, parse_error = parse_github_reference(source_url)
    if reference is None:
        return ("malformed_row", parse_error, "")
    try:
        context, source_kind = fetched_text_context(reference, fetch_json)
    except SourceFetchError as exc:
        if blocked_fetch_error(exc):
            return ("blocked", exc.reason, "")
        return ("fetch_failed", exc.reason, "")
    basis = exact_version_basis(context, source_kind, update_version)
    if basis:
        return ("verified", f"exact version matched in {basis}", basis)
    return ("exact_version_failed", "target version was not found in fetched GitHub issue/comment context", "")


def compact_row(row: dict[str, Any], classification: str, reason: str, index: int, match_basis: str = "") -> dict[str, Any]:
    item = {
        "row_index": index,
        "classification": classification,
        "reason": reason,
        "id": row.get("id"),
        "product_id": row.get("product_id"),
        "update_version": row.get("update_version"),
        "source_type": row.get("source_type"),
        "source_url": row.get("source_url"),
    }
    if match_basis:
        item["live_match_basis"] = match_basis
    return item


def revalidate(
    evidence_file: Path,
    product_id: str,
    update_version: str,
    *,
    live_fetch: bool = False,
    fetch_json: Any | None = None,
    fetch_text: Any | None = None,
) -> dict[str, Any]:
    if fetch_json is None:
        fetch_json = request_json
    if fetch_text is None:
        fetch_text = request_text
    rows = load_evidence_rows(evidence_file)
    selected = selected_rows(rows, product_id, update_version)
    classified: list[dict[str, Any]] = []
    classifications = LIVE_CLASSIFICATIONS if live_fetch else CLASSIFICATIONS
    counts = {name: 0 for name in classifications}
    for index, row in enumerate(selected, start=1):
        if live_fetch:
            classification, reason, match_basis = live_classify_row(row, update_version, fetch_json, fetch_text)
        else:
            classification, reason = classify_row(row)
            match_basis = ""
        counts[classification] += 1
        classified.append(compact_row(row, classification, reason, index, match_basis))

    matching_rows = [
        row for row in rows
        if str(row.get("product_id") or "").strip() == product_id
        and str(row.get("update_version") or "").strip() == update_version
    ]
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": LIVE_MODE if live_fetch else MODE,
        "fetches_urls": bool(live_fetch),
        "writes_files": False,
        "evidence_file": str(evidence_file),
        "product_id": product_id,
        "update_version": update_version,
        "total_rows_loaded": len(rows),
        "matching_rows": len(matching_rows),
        "counted_rows_selected": len(selected),
        "non_counted_rows_skipped": len(matching_rows) - len(selected),
        "classification_counts": counts,
        "classifications": list(classifications),
        "rows": classified,
    }


def guarded_generated_freshness_writeback(
    result: dict[str, Any],
    *,
    generated_dir: Path | None,
    confirm_product: str | None,
    confirm_version: str | None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    writeback: dict[str, Any] = {
        "attempted": True,
        "success": False,
        "guard_failures": failures,
        "expected_product": EXPECTED_WRITEBACK_PRODUCT,
        "expected_version": EXPECTED_WRITEBACK_VERSION,
        "expected_counted_rows": EXPECTED_WRITEBACK_COUNTED_ROWS,
        "expected_generated_file": EXPECTED_WRITEBACK_GENERATED_FILE,
    }

    if result.get("product_id") != EXPECTED_WRITEBACK_PRODUCT:
        failures.append(f"product must be exactly {EXPECTED_WRITEBACK_PRODUCT}")
    if result.get("update_version") != EXPECTED_WRITEBACK_VERSION:
        failures.append(f"version must be exactly {EXPECTED_WRITEBACK_VERSION}")
    if confirm_product != EXPECTED_WRITEBACK_PRODUCT:
        failures.append(f"--confirm-product must be exactly {EXPECTED_WRITEBACK_PRODUCT}")
    if confirm_version != EXPECTED_WRITEBACK_VERSION:
        failures.append(f"--confirm-version must be exactly {EXPECTED_WRITEBACK_VERSION}")
    if result.get("counted_rows_selected") != EXPECTED_WRITEBACK_COUNTED_ROWS:
        failures.append(
            f"selected counted rows must total exactly {EXPECTED_WRITEBACK_COUNTED_ROWS}; "
            f"found {result.get('counted_rows_selected')}"
        )
    if not result.get("fetches_urls"):
        failures.append("--live-fetch is required in the same command")

    counts = result.get("classification_counts") or {}
    verified = counts.get("verified", 0)
    if verified != EXPECTED_WRITEBACK_COUNTED_ROWS:
        failures.append(
            f"all selected rows must verify live; verified={verified}, "
            f"expected={EXPECTED_WRITEBACK_COUNTED_ROWS}"
        )
    for name in LIVE_CLASSIFICATIONS:
        if name == "verified":
            continue
        value = counts.get(name, 0)
        if value:
            failures.append(f"all selected rows must verify live; {name}={value}")

    record_path: Path | None = None
    if generated_dir is None:
        failures.append("--generated-dir is required for generated freshness writeback")
    else:
        generated_root = generated_dir.resolve()
        record_path = (generated_root / EXPECTED_WRITEBACK_GENERATED_FILE).resolve()
        writeback["generated_record"] = str(record_path)
        if record_path.name != EXPECTED_WRITEBACK_GENERATED_FILE or record_path.parent != generated_root:
            failures.append(f"generated record path must resolve to {EXPECTED_WRITEBACK_GENERATED_FILE}")
        elif not record_path.exists():
            failures.append(f"expected generated record does not exist: {record_path}")
        elif not record_path.is_file():
            failures.append(f"expected generated record is not a file: {record_path}")
        else:
            try:
                metadata = load_generated_record_metadata(record_path)
            except (OSError, ValueError) as exc:
                failures.append(f"could not read generated record front matter: {exc}")
            else:
                writeback["current_evidence_last_checked"] = metadata.get("evidence_last_checked")
                if metadata.get("product_id") != EXPECTED_WRITEBACK_PRODUCT:
                    failures.append(f"generated record product_id must be {EXPECTED_WRITEBACK_PRODUCT}")
                if metadata.get("update_version") != EXPECTED_WRITEBACK_VERSION:
                    failures.append(f"generated record update_version must be {EXPECTED_WRITEBACK_VERSION}")
                update_report_count = metadata.get("update_report_count")
                confirmed_report_count = metadata.get("confirmed_patch_specific_report_count")
                if update_report_count != EXPECTED_WRITEBACK_COUNTED_ROWS or confirmed_report_count != EXPECTED_WRITEBACK_COUNTED_ROWS:
                    failures.append(
                        "generated record report counts must still be 40; "
                        f"update_report_count={update_report_count}, "
                        f"confirmed_patch_specific_report_count={confirmed_report_count}"
                    )
                if metadata.get("evidence_state") != EXPECTED_WRITEBACK_EVIDENCE_STATE:
                    failures.append(f"generated record evidence_state must remain {EXPECTED_WRITEBACK_EVIDENCE_STATE}")
                if metadata.get("consensus_collection_status") != EXPECTED_WRITEBACK_CONSENSUS_STATUS:
                    failures.append(
                        "generated record consensus_collection_status must remain "
                        f"{EXPECTED_WRITEBACK_CONSENSUS_STATUS}"
                    )

    if failures:
        return writeback

    assert record_path is not None
    after_timestamp = timestamp or utc_timestamp()
    before_timestamp = replace_evidence_last_checked(record_path, after_timestamp)
    writeback.update({
        "success": True,
        "guard_failures": [],
        "generated_record": str(record_path),
        "evidence_last_checked_before": before_timestamp,
        "evidence_last_checked_after": after_timestamp,
    })
    result["writes_files"] = True
    result["mode"] = WRITEBACK_MODE
    return writeback


def print_summary(result: dict[str, Any]) -> None:
    print("AUXSAYS consensus evidence revalidation dry run")
    print(f"Mode: {result['mode']}")
    print(f"Evidence file: {result['evidence_file']}")
    print(f"Product/version: {result['product_id']} {result['update_version']}")
    print(f"Rows loaded: {result['total_rows_loaded']}")
    print(f"Matching rows: {result['matching_rows']}")
    print(f"Counted rows selected: {result['counted_rows_selected']}")
    print(f"Non-counted rows skipped: {result['non_counted_rows_skipped']}")
    print("Classification counts:")
    for name in result.get("classifications") or CLASSIFICATIONS:
        label = name.replace("_", " ")
        print(f"- {label}: {result['classification_counts'].get(name, 0)}")
    writeback = result.get("writeback") or {}
    if writeback.get("attempted"):
        print("Generated freshness writeback:")
        if writeback.get("success"):
            print("- status: success")
            print(f"- file changed: {writeback.get('generated_record')}")
            print(f"- evidence_last_checked before: {writeback.get('evidence_last_checked_before')}")
            print(f"- evidence_last_checked after: {writeback.get('evidence_last_checked_after')}")
        else:
            print("- status: blocked")
            for failure in writeback.get("guard_failures") or []:
                print(f"- guard failure: {failure}")
    if result.get("writes_files"):
        print("Files written: guarded generated freshness update only.")
    elif result.get("fetches_urls"):
        print("Live fetch enabled. No files written.")
    else:
        print("No URLs fetched. No files written.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify fixture evidence rows for future revalidation.")
    parser.add_argument("--evidence-file", required=True, help="Fixture/input evidence YAML file.")
    parser.add_argument("--product", required=True, help="Product ID to select.")
    parser.add_argument("--version", required=True, help="Update version to select.")
    parser.add_argument("--live-fetch", action="store_true", help="Fetch supported source URLs and revalidate in dry-run mode.")
    parser.add_argument(
        "--write-generated-freshness",
        action="store_true",
        help="Guarded OBS 32.1.1 generated-record evidence freshness writeback.",
    )
    parser.add_argument("--generated-dir", help="Generated record directory for guarded freshness writeback.")
    parser.add_argument("--confirm-product", help="Required product confirmation for guarded freshness writeback.")
    parser.add_argument("--confirm-version", help="Required version confirmation for guarded freshness writeback.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--summary", action="store_true", help="Print concise human-readable output.")
    output.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args(argv)

    result = revalidate(Path(args.evidence_file), args.product, args.version, live_fetch=args.live_fetch)
    exit_code = 0
    if args.write_generated_freshness:
        writeback = guarded_generated_freshness_writeback(
            result,
            generated_dir=Path(args.generated_dir) if args.generated_dir else None,
            confirm_product=args.confirm_product,
            confirm_version=args.confirm_version,
        )
        result["writeback"] = writeback
        if not writeback.get("success"):
            exit_code = 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_summary(result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
