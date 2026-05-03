#!/usr/bin/env python3
"""Collect OBS Studio patch-specific GitHub Issue evidence for one pilot patch.

This is a manual pilot collector. It only reads GitHub Issues from
obsproject/obs-studio and only counts candidates that explicitly name the
requested OBS version in the issue title or body.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
OBS_32_1_2_RECORD = ROOT / "updates" / "generated" / "2026-04-21-obs-studio-32-1-2.md"
API_ROOT = "https://api.github.com"
REPO = "obsproject/obs-studio"
PRODUCT_ID = "obs-studio"
SOURCE_NAME = "obsproject/obs-studio"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:80].strip("-")


def request_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AUXSAYS-OBS-Report-Pilot",
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
    """Return normalized title/body/labels plus a body with template headings removed.

    OBS GitHub issue bodies include headings like "OBS Studio Crash Log URL" even
    when the report is not a crash. Classification and developer-only detection
    should not treat those headings as issue substance.
    """
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


def write_evidence_file(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = {"schema_version": 1, "evidence": [normalize_row(row) for row in rows]}
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )


def dump_inline_scalar(value: Any) -> str:
    return yaml.safe_dump(value, default_flow_style=True, allow_unicode=True, width=1000).splitlines()[0]


def replace_or_add_lines(text: str, updates: dict[str, Any]) -> str:
    lines = text.splitlines()
    found: set[str] = set()
    output: list[str] = []
    in_front = False
    for idx, line in enumerate(lines):
        if idx == 0 and line == "---":
            in_front = True
            output.append(line)
            continue
        if in_front and line == "---":
            for key, value in updates.items():
                if key not in found:
                    output.append(f"{key}: {dump_inline_scalar(value)}")
            in_front = False
            output.append(line)
            continue
        if in_front and ":" in line and not line.startswith((" ", "-")):
            key = line.split(":", 1)[0]
            if key in updates:
                output.append(f"{key}: {dump_inline_scalar(updates[key])}")
                found.add(key)
                continue
        output.append(line)
    return "\n".join(output) + "\n"


def update_obs_record(count: int, captured_at: str) -> bool:
    if not OBS_32_1_2_RECORD.exists():
        return False
    text = OBS_32_1_2_RECORD.read_text(encoding="utf-8")
    legacy_match = re.search(r"^update_report_count:\s*(\d+)\s*$", text, flags=re.M)
    legacy_count = int(legacy_match.group(1)) if legacy_match else None
    updates: dict[str, Any] = {
        "update_report_count": count,
        "confirmed_patch_specific_report_count": count,
        "evidence_last_checked": captured_at,
        "record_last_updated": captured_at,
        "evidence_scope": "github_issues_pilot",
    }
    if legacy_count is not None and legacy_count != count:
        updates["legacy_report_count"] = legacy_count
        updates["evidence_backfill_status"] = "legacy_manual_count_pending_source_rows"
    new_text = replace_or_add_lines(text, updates)
    if new_text == text:
        return False
    OBS_32_1_2_RECORD.write_text(new_text, encoding="utf-8")
    return True


def collect(version: str, since: str | None, max_pages: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = [fetch_issue(item) for item in search_issues(version, since, max_pages)]
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    captured_at = utc_now()
    for issue in candidates:
        basis = match_basis(issue, version)
        if not basis:
            rejected.append({"source_url": issue.get("html_url"), "reason": "missing_exact_version"})
            continue
        if likely_developer_only(issue):
            rejected.append({"source_url": issue.get("html_url"), "reason": "developer_or_build_only"})
            continue
        accepted.append(evidence_row(issue, version, basis, captured_at))
    return accepted, rejected


def write_evidence(rows: list[dict[str, Any]]) -> tuple[int, int]:
    existing = parse_existing_rows(EVIDENCE_PATH)
    seen_ids = {str(row.get("id")) for row in existing}
    seen_urls = {str(row.get("source_url")) for row in existing}
    added = 0
    for row in rows:
        if str(row.get("id")) in seen_ids or str(row.get("source_url")) in seen_urls:
            continue
        existing.append(row)
        seen_ids.add(str(row.get("id")))
        seen_urls.add(str(row.get("source_url")))
        added += 1
    write_evidence_file(EVIDENCE_PATH, existing)
    return added, len(existing)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect OBS Studio GitHub Issue evidence for one patch version.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--since", help="Optional YYYY-MM-DD issue creation lower bound.")
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args()

    if args.version != "32.1.2":
        print("This pilot collector is intentionally scoped to OBS Studio 32.1.2.", file=sys.stderr)
        return 2
    if args.dry_run and args.write:
        print("Use either --dry-run or --write, not both.", file=sys.stderr)
        return 2

    try:
        accepted, rejected = collect(args.version, args.since, args.max_pages)
    except Exception as exc:
        print(json.dumps({
            "version": args.version,
            "mode": "write" if args.write else "dry-run",
            "status": "fetch_failed",
            "error": str(exc),
            "candidates_reviewed": 0,
            "accepted_count": 0,
            "rejected_count": 0,
        }, indent=2, ensure_ascii=False))
        return 1
    result = {
        "version": args.version,
        "mode": "write" if args.write else "dry-run",
        "candidates_reviewed": len(accepted) + len(rejected),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "rejection_reasons": {},
        "accepted_urls": [row["source_url"] for row in accepted],
    }
    for item in rejected:
        reason = item["reason"]
        result["rejection_reasons"][reason] = result["rejection_reasons"].get(reason, 0) + 1

    if args.write:
        added, total = write_evidence(accepted)
        changed = update_obs_record(len(accepted), utc_now())
        result["evidence_rows_added"] = added
        result["evidence_rows_total"] = total
        result["obs_record_updated"] = changed

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
