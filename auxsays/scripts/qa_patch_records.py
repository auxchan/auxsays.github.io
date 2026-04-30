#!/usr/bin/env python3
"""Warning-first QA for generated AUXSAYS patch intelligence records.

The script intentionally avoids non-stdlib dependencies so it can run before the
Jekyll/Ruby build and in lightweight GitHub Actions environments.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
GENERATED_DIR = ROOT / "auxsays" / "updates" / "generated"
OUT_PATH = ROOT / "auxsays" / "_data" / "qa_status.json"

SCALAR_RE = re.compile(r"^([A-Za-z0-9_\-]+):\s*(.*)$")
URL_KEYS = ("update_source_url", "official_patch_notes_source_url", "update_download_url")
EMPTY_FIELD_SENTINELS = {"", "''", '""', "null", "none", "unknown", "not captured"}
VALID_EVIDENCE = {
    "official_only",
    "pilot_sample",
    "pilot_initial_sample",
    "consensus_live",
    "insufficient_data",
}
VALID_STAGES = {"staged", "official_live", "pilot", "consensus_live", "archived", ""}
ALIASES = {
    "static_sample": "pilot_sample",
    "static_initial_sample": "pilot_initial_sample",
    "live_consensus": "consensus_live",
}


def _raw_norm(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _front_matter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]


def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_scalars(front: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in front.splitlines():
        if raw_line.startswith((" ", "-", "\t")):
            continue
        match = SCALAR_RE.match(raw_line)
        if not match:
            continue
        key, value = match.groups()
        data[key] = _clean(value)
    return data


def _norm(value: str) -> str:
    normalized = _raw_norm(value)
    return ALIASES.get(normalized, normalized)


def _as_int(value: str) -> int:
    try:
        return int(str(value or "0").strip())
    except ValueError:
        return 0


def _has_structured_evidence(front: str) -> bool:
    evidence_keys = (
        "consensus_evidence:",
        "evidence_objects:",
        "structured_evidence:",
        "confirmed_reports:",
    )
    return any(key in front for key in evidence_keys)


def _is_emptyish(value: str) -> bool:
    return str(value or "").strip().lower() in EMPTY_FIELD_SENTINELS


def _url_bad(url: str) -> bool:
    if _is_emptyish(url):
        return False
    parsed = urlparse(url)
    return parsed.scheme not in {"http", "https"} or not parsed.netloc


def _issue(level: str, path: Path, code: str, message: str) -> dict[str, str]:
    return {
        "level": level,
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "code": code,
        "message": message,
    }


def inspect_record(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    front = _front_matter(text)
    data = _parse_scalars(front)
    issues: list[dict[str, str]] = []

    if not front:
        return [_issue("error", path, "missing_front_matter", "Generated update record has no YAML front matter.")]

    title = data.get("title", "")
    detail_title = data.get("update_detail_title", "")
    summary = data.get("release_summary") or data.get("official_summary") or data.get("description", "")
    version = data.get("update_version", "")
    report_count = _as_int(data.get("update_report_count", data.get("confirmed_patch_specific_report_count", "0")))
    evidence_state = _norm(data.get("evidence_state", "insufficient_data"))
    consensus_status = _norm(data.get("consensus_collection_status", ""))
    stage = _norm(data.get("intelligence_stage", ""))
    patch_file_size = data.get("patch_file_size", "")
    patch_file_size_status = data.get("patch_file_size_status", "")

    if _is_emptyish(title):
        issues.append(_issue("error", path, "empty_title", "Generated update record has an empty title."))
    if _is_emptyish(summary):
        issues.append(_issue("error", path, "empty_summary", "Generated update record has no summary/description."))

    if evidence_state not in VALID_EVIDENCE:
        issues.append(_issue("warning", path, "unknown_evidence_state", f"Unknown evidence_state '{data.get('evidence_state')}'."))
    if stage not in VALID_STAGES:
        issues.append(_issue("warning", path, "unknown_intelligence_stage", f"Unknown intelligence_stage '{data.get('intelligence_stage')}'."))

    if report_count > 0 and evidence_state == "official_only":
        issues.append(_issue("error", path, "report_count_with_official_only", "official_only records cannot count confirmed community reports."))

    if (evidence_state == "consensus_live" or consensus_status == "consensus_live") and not _has_structured_evidence(front):
        issues.append(_issue("error", path, "consensus_live_without_evidence_objects", "consensus_live requires structured evidence objects."))

    if _raw_norm(data.get("evidence_state", "")) in {"static_sample", "static_initial_sample"} or _raw_norm(data.get("consensus_collection_status", "")) == "static_initial_sample":
        issues.append(_issue("warning", path, "legacy_static_taxonomy", "Legacy static taxonomy should be migrated to pilot taxonomy."))

    if detail_title and version:
        version_clean = version.strip().strip("'").strip('"')
        duplicate_pattern = re.escape(version_clean) + r"\s+" + re.escape(version_clean) + r"$"
        if re.search(duplicate_pattern, detail_title.strip()):
            issues.append(_issue("warning", path, "duplicated_version_in_title", "Update detail title appears to duplicate the version."))
    if title and version:
        version_clean = version.strip().strip("'").strip('"')
        duplicate_pattern = re.escape(version_clean) + r"\s+" + re.escape(version_clean)
        if re.search(duplicate_pattern, title.strip()):
            issues.append(_issue("warning", path, "duplicated_version_in_page_title", "Page title appears to duplicate the version."))

    for key in URL_KEYS:
        if _url_bad(data.get(key, "")):
            issues.append(_issue("warning", path, "malformed_url", f"{key} is not a valid HTTP/HTTPS URL."))

    if _is_emptyish(patch_file_size) and _is_emptyish(patch_file_size_status):
        issues.append(_issue("warning", path, "blank_file_size_without_status", "patch_file_size is blank and no patch_file_size_status explains why."))
    elif str(patch_file_size).strip() in {"''", '""'}:
        issues.append(_issue("warning", path, "quoted_blank_file_size", "patch_file_size is explicitly blank; prefer a status such as not_provided_by_source or pending_adapter_support."))

    return issues


def main() -> int:
    records = sorted(GENERATED_DIR.glob("*.md"))
    issues: list[dict[str, str]] = []
    for path in records:
        issues.extend(inspect_record(path))

    errors = [item for item in issues if item["level"] == "error"]
    warnings = [item for item in issues if item["level"] == "warning"]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "warning_first",
        "records_scanned": len(records),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": issues,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"QA scanned {len(records)} generated update records: {len(errors)} errors, {len(warnings)} warnings.")
    for item in issues:
        print(f"::{item['level']} file={item['file']},title={item['code']}::{item['message']}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
