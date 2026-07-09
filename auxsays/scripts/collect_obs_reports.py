#!/usr/bin/env python3
"""Collect version-scoped OBS Studio GitHub Issue evidence.

This collector is intentionally narrow: it only reads GitHub Issues from
obsproject/obs-studio and only counts candidates that explicitly name the
requested OBS version in the issue title or body.

The shared Phase A runner wraps this collector via patch_collectors/obs.py so
OBS participates in the same automated evidence framework as other products
without changing its production behavior.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
GENERATED_DIR = ROOT / "updates" / "generated"
API_ROOT = "https://api.github.com"
REPO = "obsproject/obs-studio"
PRODUCT_ID = "obs-studio"
SOURCE_NAME = "obsproject/obs-studio"
VERSION_RE = re.compile(r"^\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z][0-9A-Za-z.-]*)?$")

# Deterministic "concrete user-facing issue" vocabulary. A candidate that names the
# exact version but contains none of these problem indicators is treated as a generic
# complaint / question / announcement and is NOT counted. Kept as a visible, testable
# keyword list (no AI, no external services); matched against title + scrubbed body only
# (labels are excluded because they can be auto-applied).
CONCRETE_ISSUE_TERMS = (
    "crash", "freeze", "frozen", "freezing", "hang", "hangs", "hanging",
    "black screen", "green screen", "blue screen", "bsod",
    "no audio", "no sound", "no video", "no display", "no signal", "no output",
    "won't start", "wont start", "doesn't start", "does not start", "not starting",
    "won't launch", "wont launch", "fails to launch", "won't open", "can't open", "cannot open",
    "won't install", "can't install", "cannot install", "failed to install", "install fail", "installation fail",
    "won't update", "can't update", "failed to update", "update fail",
    "fails", "failed", "failing", "failure", "fails to",
    "not working", "doesn't work", "does not work", "no longer works", "stopped working", "quit working",
    "broken", "broke", "breaks", "breaking",
    "regression", "regressed",
    "error", "errors", "glitch", "artifact", "artifacts",
    "stutter", "stuttering", "dropped frame", "dropped frames", "drop frames", "frame drop", "skipped frames",
    "corrupt", "corrupted", "corruption", "data loss",
    "lag", "laggy", "slowdown", "slow to", "very slow", "extremely slow",
    "memory leak", "high cpu", "cpu usage", "100% cpu", "gpu usage", "overheat",
    "incompatible", "not compatible", "compatibility issue",
    "vulnerability", "exploit", "security issue", "security flaw",
)

# Word-anchored match: a leading word boundary prevents internal-substring false
# positives (e.g. "changelog" must not match "hang", "terror" must not match "error")
# while allowing plural/tense suffixes (crash -> crashes/crashed/crashing).
CONCRETE_ISSUE_RE = re.compile(r"\b(?:" + "|".join(re.escape(t) for t in CONCRETE_ISSUE_TERMS) + r")", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: Any) -> "datetime.date | None":  # type: ignore[name-defined]
    """Parse an ISO date/datetime string (e.g. '2026-04-02' or '2026-04-02T00:00:00Z')
    into a date. Returns None when the value is missing or not a recognizable date —
    the caller decides how to treat an unknown date (never invents one)."""
    text = str(value or "").strip()
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc).date()
    except ValueError:
        return None


def issue_source_date(issue: dict[str, Any]):
    """The report's own date = the GitHub issue creation date (created_at)."""
    return parse_date(issue.get("created_at"))


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:80].strip("-")


def request_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AUXSAYS-OBS-Report-Beta",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def search_issues(version: str, since: str | None, max_pages: int) -> list[dict[str, Any]]:
    query = f'repo:{REPO} is:issue "{version}"'
    if since:
        query += f" created:>={since}"
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, max(1, max_pages) + 1):
        encoded = urllib.parse.urlencode({"q": query, "per_page": "100", "page": str(page)})
        url = f"{API_ROOT}/search/issues?{encoded}"
        payload = request_json(url)
        items = payload.get("items") or []
        if not items:
            break
        for item in items:
            if item.get("pull_request"):
                continue
            issue_url = str(item.get("url") or "")
            if issue_url and issue_url not in seen:
                seen.add(issue_url)
                results.append(item)
    return results


def fetch_issue(item: dict[str, Any]) -> dict[str, Any]:
    url = str(item.get("url") or "")
    if not url:
        return item
    try:
        issue = request_json(url)
        return issue if isinstance(issue, dict) else item
    except Exception:
        return item


def exact_version_re(version: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![0-9.]){re.escape(version)}(?![0-9.])")


def match_basis(issue: dict[str, Any], version: str) -> str | None:
    pattern = exact_version_re(version)
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    if pattern.search(title):
        return "title"
    if pattern.search(body):
        return "body"
    return None


def issue_text(issue: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return normalized title/body/labels plus body with template headings removed."""
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    labels = " ".join(str(label.get("name") or "") for label in issue.get("labels") or [] if isinstance(label, dict))
    scrubbed_body = re.sub(
        r"###\s*(OBS Studio Log URL|OBS Studio Crash Log URL|Other OS|Operating System Info|OBS Studio Version(?: \(Other\))?)",
        " ",
        body,
        flags=re.I,
    )
    return title.lower(), body.lower(), labels.lower(), scrubbed_body.lower()


def likely_developer_only(issue: dict[str, Any]) -> bool:
    title, body, labels, scrubbed_body = issue_text(issue)
    combined = f"{title} {scrubbed_body} {labels}"

    developer_terms = (
        "build failure",
        "build fails",
        "fails to build",
        "fails to configure",
        "configure when",
        "compile",
        "compiler",
        "cmake",
        "enable_plugins",
        "github actions",
        "developer",
        "libobs-metal fails",
        "there is no build log",
    )
    end_user_terms = (
        "crashes on quit",
        "crash if",
        "freeze",
        "hang",
        "lag",
        "recording",
        "streaming",
        "audio mixer",
        "web camera",
        "screen capture",
        "black screen",
        "black square",
        "hotkey",
        "pipewire",
        "xcomposite",
        "rescale output",
        "mouse cursor",
    )
    return any(term in combined for term in developer_terms) and not any(term in combined for term in end_user_terms)


def describes_concrete_issue(issue: dict[str, Any]) -> bool:
    """True only when the report names a concrete user-facing problem (crash, install/
    update failure, capture/encoder/audio/hotkey/plugin regression, performance
    regression, workflow breakage, etc.). Generic questions ("anyone having issues?",
    "is this safe?"), generic dislike ("this version sucks"), release announcements, and
    changelog/official-notes text carry no problem indicator and return False."""
    title, body, labels, scrubbed_body = issue_text(issue)
    return bool(CONCRETE_ISSUE_RE.search(f"{title} {scrubbed_body}"))


def release_date_gate(issue: dict[str, Any], release_date) -> str | None:
    """Return a rejection reason when a report must be excluded by the release-date
    gate, else None. A report counts only if its source date is on or after the patch
    release date. When the release date is unknown, the gate is inactive (no date is
    invented). When the release date is known but the report has no parseable source
    date, the report is rejected conservatively (the gate cannot be verified)."""
    if release_date is None:
        return None
    source_date = issue_source_date(issue)
    if source_date is None:
        return "missing_source_date"
    if source_date < release_date:
        return "before_release_date"
    return None


def evaluate_issue(issue: dict[str, Any], version: str, release_date=None) -> tuple[str | None, str | None]:
    """Deterministic acceptance decision for one candidate issue.
    Returns (match_basis, None) when accepted, or (None, rejection_reason) when rejected.
    Order: exact-version -> developer-only -> generic/no-concrete-issue -> release-date."""
    basis = match_basis(issue, version)
    if not basis:
        return None, "missing_exact_version"
    if likely_developer_only(issue):
        return None, "developer_or_build_only"
    if not describes_concrete_issue(issue):
        return None, "generic_or_no_concrete_issue"
    date_reason = release_date_gate(issue, release_date)
    if date_reason:
        return None, date_reason
    return basis, None


def classify(issue: dict[str, Any]) -> tuple[str, str, str, str, str]:
    title, body, labels, scrubbed_body = issue_text(issue)
    combined = f"{title} {scrubbed_body} {labels}"
    platform = "unknown"
    for name in ("windows", "macos", "linux"):
        if name in combined:
            platform = name
            break
    if "crashes on quit" in combined or "crash if" in combined:
        return "crash / stability", "application stability", platform, "high", "negative"
    if "screen capture" in combined or "xcomposite" in combined or "black screen" in combined:
        return "screen capture regression", "screen/window capture", platform, "high", "negative"
    if "black square" in combined or "mouse cursor" in combined:
        return "visual capture artifact", "display capture / HDR workflow", platform, "medium", "negative"
    if "audio mixer" in combined or "audio" in combined:
        return "audio mixer regression", "audio mixer UI", platform, "medium", "negative"
    if "hotkey" in combined:
        return "hotkey regression", "keyboard shortcuts", platform, "medium", "negative"
    if "web camera" in combined or "camera" in combined:
        return "camera/source regression", "camera source workflow", platform, "medium", "negative"
    if "rescale output" in combined:
        return "output configuration regression", "output settings", platform, "medium", "negative"
    if "freeze" in combined or "hang" in combined:
        return "freeze / hang", "application stability", platform, "high", "negative"
    if "plugin" in combined:
        return "plugin compatibility", "plugins", platform, "medium", "negative"
    return "unspecified issue", "general OBS workflow", platform, "medium", "moderate"


def excerpt(text: str, version: str, width: int = 280) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    idx = text.lower().find(version.lower())
    if idx < 0:
        return textwrap.shorten(text, width=width, placeholder="...")
    start = max(0, idx - 90)
    end = min(len(text), idx + width - 90)
    snippet = text[start:end].strip()
    return textwrap.shorten(snippet, width=width, placeholder="...")


def evidence_row(issue: dict[str, Any], version: str, basis: str, captured_at: str) -> dict[str, Any]:
    number = issue.get("number")
    title = str(issue.get("title") or f"GitHub issue {number}").strip()
    body = str(issue.get("body") or "")
    theme, workflow_area, platform, severity, sentiment = classify(issue)
    return {
        "id": f"obs-studio-{slug(version)}-github-issue-{number}",
        "product_id": PRODUCT_ID,
        "update_version": version,
        "source_type": "github_issue",
        "source_name": SOURCE_NAME,
        "source_url": issue.get("html_url") or f"https://github.com/{REPO}/issues/{number}",
        "parent_title": title,
        "report_title": title,
        "report_text_excerpt": excerpt(body or title, version),
        "captured_at": captured_at,
        "patch_version_matched": True,
        "matched_version": version,
        "match_basis": basis,
        "counted": True,
        "exclusion_reason": None,
        "issue_theme": theme,
        "workflow_area": workflow_area,
        "platform": platform,
        "severity": severity,
        "sentiment": sentiment,
        "source_weight": 1,
    }


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    string_fields = {
        "id",
        "product_id",
        "update_version",
        "source_type",
        "source_name",
        "source_url",
        "parent_title",
        "report_title",
        "report_text_excerpt",
        "captured_at",
        "matched_version",
        "match_basis",
        "exclusion_reason",
        "issue_theme",
        "workflow_area",
        "platform",
        "severity",
        "sentiment",
    }
    for field in string_fields:
        value = normalized.get(field)
        if value is not None:
            normalized[field] = str(value)
    if "source_weight" in normalized:
        normalized["source_weight"] = int(normalized["source_weight"] or 1)
    if "counted" in normalized:
        normalized["counted"] = bool(normalized["counted"])
    if "patch_version_matched" in normalized:
        normalized["patch_version_matched"] = bool(normalized["patch_version_matched"])
    return normalized


def parse_existing_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [normalize_row(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        evidence = payload.get("evidence") or []
        if not isinstance(evidence, list):
            raise ValueError(f"{path} field 'evidence' must be a list")
        return [normalize_row(item) for item in evidence if isinstance(item, dict)]
    raise ValueError(f"{path} must contain a YAML list or a mapping with an evidence list")


def write_evidence_file(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = {"schema_version": 1, "evidence": [normalize_row(row) for row in rows]}
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )


def evidence_key(row: dict[str, Any], field: str) -> tuple[str, str, str]:
    return (
        str(row.get("product_id") or "").strip(),
        str(row.get("update_version") or "").strip(),
        str(row.get(field) or "").strip(),
    )


def write_evidence(rows: list[dict[str, Any]]) -> tuple[int, int, list[dict[str, Any]]]:
    existing = parse_existing_rows(EVIDENCE_PATH)
    seen_ids = {evidence_key(row, "id") for row in existing if row.get("id")}
    seen_urls = {evidence_key(row, "source_url") for row in existing if row.get("source_url")}
    added = 0
    for row in rows:
        id_key = evidence_key(row, "id")
        url_key = evidence_key(row, "source_url")
        if id_key in seen_ids or url_key in seen_urls:
            continue
        existing.append(row)
        seen_ids.add(id_key)
        seen_urls.add(url_key)
        added += 1
    if added:
        write_evidence_file(EVIDENCE_PATH, existing)
    return added, len(existing), existing


def counted_evidence_count(rows: list[dict[str, Any]], version: str) -> int:
    return sum(
        1
        for row in rows
        if str(row.get("product_id") or "").strip() == PRODUCT_ID
        and str(row.get("update_version") or "").strip() == version
        and row.get("counted") is not False
    )


def front_matter_parts(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, flags=re.S)
    if not match:
        return {}, text
    data = yaml.safe_load(match.group(1)) or {}
    return (data if isinstance(data, dict) else {}), match.group(2)


def write_front_matter(path: Path, data: dict[str, Any], body: str) -> None:
    front = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000).strip()
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")


def report_count(data: dict[str, Any]) -> int:
    for key in ("confirmed_patch_specific_report_count", "update_report_count"):
        value = data.get(key)
        if value not in (None, ""):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def update_obs_record(record_path: Path, count: int, captured_at: str) -> bool:
    data, body = front_matter_parts(record_path)
    if not data:
        return False
    current_count = report_count(data)
    updates: dict[str, Any] = {
        "update_report_count": count,
        "confirmed_patch_specific_report_count": count,
        "evidence_last_checked": captured_at,
        "record_last_updated": captured_at,
        "evidence_scope": "github_issues_pilot",
    }
    if current_count != count and data.get("legacy_report_count") in (None, ""):
        updates["legacy_report_count"] = current_count
        updates["evidence_backfill_status"] = "legacy_manual_count_pending_source_rows"

    changed = any(data.get(key) != value for key, value in updates.items())
    if not changed:
        return False
    data.update(updates)
    write_front_matter(record_path, data, body)
    return True


def apply_consensus_writeback(version: str) -> bool:
    from apply_consensus_to_records import _apply_record_fields, _index_generated_records, run_dry_run

    records_index = _index_generated_records()
    results = run_dry_run(
        evidence_path=EVIDENCE_PATH,
        product_id_filter=PRODUCT_ID,
        is_candidate_mode=False,
        records_index=records_index,
        write_requested=True,
    )
    matches = [item for item in results if item["update_version"] == version]
    if len(matches) != 1 or not matches[0].get("would_write"):
        return False
    record_key = (PRODUCT_ID, version)
    if record_key not in records_index:
        return False
    result = matches[0]
    record_path = records_index[record_key]["abs_path"]
    fields = dict(result["proposed_fields_if_written"])
    data, _body = front_matter_parts(record_path)
    comparable = {k: v for k, v in fields.items() if k != "status_events_append"}
    if all(data.get(k) == v for k, v in comparable.items()):
        return False
    _apply_record_fields(record_path, fields)
    return True


def valid_update_version(value: Any) -> bool:
    return bool(VERSION_RE.fullmatch(str(value or "").strip()))


def active_obs_records() -> list[tuple[str, Path]]:
    records: list[tuple[str, Path]] = []
    for path in sorted(GENERATED_DIR.glob("*.md")):
        data, _body = front_matter_parts(path)
        version = str(data.get("update_version") or "").strip()
        if data.get("update_entry") is True and data.get("product_id") == PRODUCT_ID and valid_update_version(version):
            records.append((version, path))
    return records


def collect(version: str, since: str | None, max_pages: int, release_date=None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = [fetch_issue(item) for item in search_issues(version, since, max_pages)]
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    captured_at = utc_now()
    for issue in candidates:
        basis, reason = evaluate_issue(issue, version, release_date)
        if reason:
            rejected.append({"source_url": issue.get("html_url"), "reason": reason})
            continue
        accepted.append(evidence_row(issue, version, basis, captured_at))
    return accepted, rejected


def release_date_for_record(record_path: Path | None):
    """Patch release date from the generated record's update_published_at, or None."""
    if not record_path:
        return None
    data, _body = front_matter_parts(record_path)
    return parse_date(data.get("update_published_at"))


def since_from_days(days: int | None) -> str | None:
    if days is None:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=max(0, days))).date().isoformat()


def summarize(version: str, mode: str, accepted: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "version": version,
        "mode": mode,
        "candidates_reviewed": len(accepted) + len(rejected),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "rejection_reasons": {},
        "accepted_urls": [row["source_url"] for row in accepted],
    }
    for item in rejected:
        reason = item["reason"]
        result["rejection_reasons"][reason] = result["rejection_reasons"].get(reason, 0) + 1
    return result


def collect_one(
    version: str,
    record_path: Path | None,
    since: str | None,
    max_pages: int,
    write: bool,
) -> tuple[int, dict[str, Any]]:
    release_date = release_date_for_record(record_path)
    try:
        accepted, rejected = collect(version, since, max_pages, release_date)
    except Exception as exc:
        return 1, {
            "version": version,
            "mode": "write" if write else "dry-run",
            "status": "fetch_failed",
            "error": str(exc),
            "candidates_reviewed": 0,
            "accepted_count": 0,
            "rejected_count": 0,
        }

    result = summarize(version, "write" if write else "dry-run", accepted, rejected)
    if write:
        added, total, rows = write_evidence(accepted)
        structured_count = counted_evidence_count(rows, version)
        record_updated = False
        if record_path:
            record_updated = apply_consensus_writeback(version)
            if not record_updated and record_needs_count_update(record_path, structured_count):
                record_updated = update_obs_record(record_path, structured_count, utc_now())
        result["evidence_rows_added"] = added
        result["evidence_rows_total"] = total
        result["structured_count_for_version"] = structured_count
        result["obs_record_updated"] = record_updated
    return 0, result


def record_needs_count_update(record_path: Path, count: int) -> bool:
    data, _body = front_matter_parts(record_path)
    if not data:
        return False
    return report_count(data) != count


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect OBS Studio GitHub Issue evidence for patch versions.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--version", help="OBS Studio update_version to collect.")
    target.add_argument("--all-active-obs", action="store_true", help="Collect all generated OBS update records with valid versions.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--since", help="Optional YYYY-MM-DD issue creation lower bound.")
    parser.add_argument("--since-days", type=int, help="Optional issue creation lower bound relative to today.")
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args()

    write = bool(args.write)
    since = args.since or since_from_days(args.since_days)

    if args.version:
        version = str(args.version).strip()
        if not valid_update_version(version):
            print(f"Invalid OBS update_version: {version}", file=sys.stderr)
            return 2
        matching_records = [item for item in active_obs_records() if item[0] == version]
        record_path = matching_records[0][1] if matching_records else None
        status, result = collect_one(version, record_path, since, args.max_pages, write)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return status

    records = active_obs_records()
    results: list[dict[str, Any]] = []
    status = 0
    for version, record_path in records:
        item_status, result = collect_one(version, record_path, since, args.max_pages, write)
        status = max(status, item_status)
        result["record_path"] = str(record_path.relative_to(ROOT))
        results.append(result)

    print(json.dumps({
        "mode": "write" if write else "dry-run",
        "since": since,
        "max_pages": args.max_pages,
        "records_scanned": len(records),
        "results": results,
    }, indent=2, ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
