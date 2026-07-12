"""Microsoft Windows release-health official-ingestion adapter.

Official ingestion only for Windows 11 servicing versions from
learn.microsoft.com/windows/release-health. This sprint parses the
"windows11-release-information" page's *current versions by servicing option*
summary table into one official-only record per current General Availability
Channel servicing version (e.g. 24H2, 25H2), capturing the Windows feature
version, latest OS build, latest revision date, and — only when deterministically
matched — the KB article for that build.

Design rules:
- Official ingestion only. Never emits consensus/report fields; records stay
  official_only (report_count is left unset, so write_update_record derives
  evidence_state=official_only).
- Deterministic + conservative: only the current-versions summary table is parsed;
  Long-Term Servicing Channel (LTSC) and per-build history tables are skipped. The
  KB is included only when a single KB maps to that exact latest build; otherwise it
  is omitted (never guessed).
- Returns [] on any DOM mismatch so a page change never yields a fabricated record.
- Known-issues / safeguard-hold / resolved-issue status pages are intentionally NOT
  parsed in this sprint (a documented fast-follow).
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from lib.http import fetch_text
from lib.normalize import strip_tags, first_nonempty

TABLE_RE = re.compile(r"<table\b[^>]*>(?P<table>.*?)</table>", re.I | re.S)
ROW_RE = re.compile(r"<tr\b[^>]*>(?P<row>.*?)</tr>", re.I | re.S)
CELL_RE = re.compile(r"<t[dh]\b[^>]*>(?P<cell>.*?)</t[dh]>", re.I | re.S)
VERSION_RE = re.compile(r"\d{2}H\d")        # e.g. 24H2, 25H2, 26H1 (fullmatch used)
BUILD_RE = re.compile(r"\d{5}\.\d{3,5}")    # e.g. 26100.8737 (fullmatch used)
KB_RE = re.compile(r"KB\d{6,7}")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Rows on non-current servicing channels are skipped so only GA current versions ship.
SKIP_SERVICING_TOKENS = ("ltsc", "long-term")
SUPPORTED_PROFILES = {"windows_release_health", "generic", ""}

# --- Known-issues / resolved-issues / safeguard-hold enrichment ---------------
# Body-only: a deterministic roll-up of each version's official Microsoft Release
# Health status page is appended to that version's record body. No structured
# fields, no known_issues_present flag, no consensus fields (Phase 1).
# A safeguard hold is only recognised when an explicit numeric Safeguard ID sits
# in the issue row, so generic "safeguard" help-footer links never create a hold.
SAFEGUARD_ID_RE = re.compile(r"safeguard\s*(?:hold)?\s*(?:id)?\s*[:#]?\s*(\d{6,9})", re.I)
MAX_ROLLUP_BULLETS = 6
MAX_SUMMARY_CHARS = 220


def _request_options(source: dict[str, Any]) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    request = ingestion.get("request", {}) or {}
    headers = request.get("headers") or {}
    return {
        "timeout": int(request.get("timeout_seconds") or 30),
        "retries": int(request.get("retries") or 1),
        "backoff_seconds": float(request.get("backoff_seconds") or 2.0),
        "max_bytes": int(request.get("max_bytes") or 900000),
        "headers": headers if isinstance(headers, dict) else {},
    }


def _source_candidates(source: dict[str, Any]) -> list[str]:
    ingestion = source.get("ingestion", {}) or {}
    clean: list[str] = []
    # Prefer the parseable release-information table over the landing/hub page.
    for url in (ingestion.get("secondary_official_url"), ingestion.get("official_url")):
        if isinstance(url, str) and url.strip() and url.strip() not in clean:
            clean.append(url.strip())
    return clean


def _row_cells(row_html: str) -> list[str]:
    return [re.sub(r"\s+", " ", strip_tags(c.group("cell"))).strip() for c in CELL_RE.finditer(row_html)]


def _has(header: list[str], needle: str) -> bool:
    return any(needle in h for h in header)


def _col(header: list[str], needle: str) -> int | None:
    for idx, cell in enumerate(header):
        if needle in cell:
            return idx
    return None


def _iso(cell: str) -> str:
    match = ISO_DATE_RE.search(cell or "")
    return f"{match.group(0)}T00:00:00Z" if match else ""


def _build_kb_map(html: str) -> dict[str, str]:
    """OS build -> KB, only for builds that map to exactly one KB (else omitted)."""
    mapping: dict[str, str] = {}
    ambiguous: set[str] = set()
    for row in ROW_RE.finditer(html):
        cells = _row_cells(row.group("row"))
        build = next((c for c in cells if BUILD_RE.fullmatch(c)), "")
        if not build:
            continue
        kb = ""
        for cell in cells:
            found = KB_RE.search(cell)
            if found:
                kb = found.group(0)
                break
        if not kb:
            continue
        if build in mapping and mapping[build] != kb:
            ambiguous.add(build)
        else:
            mapping[build] = kb
    for build in ambiguous:
        mapping.pop(build, None)
    return mapping


def _record(
    source: dict[str, Any],
    source_url: str,
    version: str,
    build: str,
    kb: str,
    published: str,
) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    software = source["software"]
    date_str = published[:10] if published else ""
    digest = hashlib.sha256((source_url + version + build).encode("utf-8")).hexdigest()[:16]
    kb_str = f" ({kb})" if kb else ""

    official_sources = []
    for label, url in (
        ("Windows 11 release information", ingestion.get("secondary_official_url")),
        ("Windows release health", ingestion.get("official_url")),
    ):
        if isinstance(url, str) and url.strip():
            official_sources.append({
                "label": label,
                "url": url.strip(),
                "source_type": "release_health",
                "trust_level": "official",
                "extraction_status": "summary_captured" if url.strip() == source_url else "reference_only",
            })

    body = (
        f"{software} {version} is a current General Availability Channel servicing version. "
        f"Latest OS build {build}{kb_str}."
        + (f" Latest revision date {date_str}." if date_str else "")
        + " This is the official Microsoft Windows release-health entry"
        " (learn.microsoft.com/windows/release-health). Known-issue and safeguard-hold"
        " details are published on the per-version Windows release-health status page."
    )
    official_summary = (
        f"Windows 11 {version} latest OS build is {build}{kb_str}"
        + (f" (revised {date_str})." if date_str else ".")
    )

    return {
        "record_id": f"microsoft:{source['product_id']}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": source["product_id"],
        "company": source["company"],
        "software": software,
        "category": source.get("public_category"),
        "version": version,
        "title": first_nonempty(f"{software} {version}", software),
        "published_at": published,
        "source_url": source_url,
        "official_url": source_url,
        "download_url": "",
        "file_size": "",
        "file_size_status": "not_provided_by_source",
        "file_size_note": (
            "Windows 11 updates are Microsoft-managed via Windows Update; the public release-health "
            "information does not expose standalone package/installer size metadata."
        ),
        "body": body,
        "checksums_body": "",
        "summary": "",
        "source_type": "release_health",
        "official_source_type": "release_health",
        "official_note_status": "official_source_captured",
        "official_note_label": "Official release health",
        "official_sources": official_sources,
        "capture_status": "captured-from-official-windows-release-health",
        "official_summary": official_summary,
        # Structured current-patch identity (promoted from the parsed build/KB/date so
        # consensus counting can gate user reports on the exact current KB/build rather
        # than the shared feature-train version). OS build is the train-specific primary
        # identity; KB is secondary (a KB can be shared across trains) and is left empty
        # when it could not be resolved unambiguously (fail-closed downstream).
        "target_feature_version": version,
        "target_kb": kb,
        "target_os_build": build,
        "target_release_date": published,
    }


def _records_from_windows_release_information(
    source: dict[str, Any],
    source_url: str,
    html: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Pure parser (no network): current-versions summary table -> official-only records.

    Only the "current versions by servicing option" summary table is used (identified
    by its Version + Latest build columns, and by NOT being a per-build history table).
    LTSC rows are skipped. KB is resolved from the release-history build->KB map only
    when unambiguous. Returns [] when no current version row is found.
    """
    html = html or ""
    build_kb = _build_kb_map(html)
    records: list[dict[str, Any]] = []
    seen_versions: set[str] = set()

    for table in TABLE_RE.finditer(html):
        rows = list(ROW_RE.finditer(table.group("table")))
        if not rows:
            continue
        header = [c.lower() for c in _row_cells(rows[0].group("row"))]
        if not header or not (_has(header, "version") and _has(header, "latest build")):
            continue
        # Skip the per-build release-history tables (they carry KB/Update-type columns).
        if _has(header, "kb article") or _has(header, "update type"):
            continue

        idx_version = _col(header, "version")
        idx_build = _col(header, "latest build")
        idx_rev = _col(header, "latest revision")
        idx_serv = _col(header, "servicing")

        for row in rows[1:]:
            cells = _row_cells(row.group("row"))
            if idx_version is None or idx_build is None:
                break
            if idx_version >= len(cells) or idx_build >= len(cells):
                continue

            servicing = cells[idx_serv] if (idx_serv is not None and idx_serv < len(cells)) else ""
            if any(token in servicing.lower() for token in SKIP_SERVICING_TOKENS):
                continue

            version = cells[idx_version]
            build = cells[idx_build]
            if not VERSION_RE.fullmatch(version) or not BUILD_RE.fullmatch(build) or version in seen_versions:
                continue

            rev_cell = cells[idx_rev] if (idx_rev is not None and idx_rev < len(cells)) else ""
            published = _iso(rev_cell)
            kb = build_kb.get(build, "")

            seen_versions.add(version)
            records.append(_record(source, source_url, version, build, kb, published))
            if len(records) >= max(1, int(limit)):
                return records

        # The current-versions summary table is the first one that yields rows; stop
        # here so a later "end of servicing" table (same columns) can never inject
        # old / out-of-support versions.
        if records:
            return records

    return records


def _short(text: str, limit: int = MAX_SUMMARY_CHARS) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _known_issues_from_status_page(html: str, version: str) -> list[dict[str, Any]]:
    """Pure parser (no network): a Release Health status page -> known-issue rows.

    Reads only the "Known issues" summary table (header contains Summary + Status);
    footer/help tables that merely mention "safeguard" are never touched. Each issue
    is classified deterministically as active or resolved from its Status cell.
    Returns [] on any DOM mismatch so a page change never fabricates an issue.
    """
    html = html or ""
    issues: list[dict[str, Any]] = []

    for table in TABLE_RE.finditer(html):
        rows = list(ROW_RE.finditer(table.group("table")))
        if not rows:
            continue
        header = [c.lower() for c in _row_cells(rows[0].group("row"))]
        if not header or not (_has(header, "summary") and _has(header, "status")):
            continue

        i_sum = _col(header, "summary")
        i_stat = _col(header, "status")
        i_orig = _col(header, "originating")
        i_upd = _col(header, "last updated")

        for row in rows[1:]:
            cells = _row_cells(row.group("row"))
            if i_sum is None or i_stat is None or i_sum >= len(cells) or i_stat >= len(cells):
                continue
            summary = cells[i_sum]
            status_raw = cells[i_stat]
            if not summary or not status_raw:
                continue

            originating = cells[i_orig] if (i_orig is not None and i_orig < len(cells)) else ""
            last_updated = cells[i_upd] if (i_upd is not None and i_upd < len(cells)) else ""

            resolved = status_raw.strip().lower().startswith("resolved")
            resolving_match = KB_RE.search(status_raw) if resolved else None
            build_match = BUILD_RE.search(originating)
            kb_match = KB_RE.search(originating)
            safeguard_match = SAFEGUARD_ID_RE.search(f"{summary} {status_raw}")

            issues.append({
                "summary": summary,
                "status_raw": status_raw,
                "state": "resolved" if resolved else "active",
                "originating_build": build_match.group(0) if build_match else "",
                "originating_kb": kb_match.group(0) if kb_match else "",
                "resolving_kb": resolving_match.group(0) if resolving_match else "",
                "last_updated": last_updated,
                "safeguard_id": safeguard_match.group(1) if safeguard_match else "",
            })

        # The known-issues summary table is the first Summary+Status table; stop here.
        if issues:
            return issues

    return issues


def _originating_label(issue: dict[str, Any]) -> str:
    build, kb = issue.get("originating_build"), issue.get("originating_kb")
    if build and kb:
        return f"OS Build {build} {kb}"
    if kb:
        return kb
    if build:
        return f"OS Build {build}"
    return "N/A"


def _issue_counts(issues: list[dict[str, Any]]) -> tuple[int, int, int]:
    """(active, resolved, safeguard-hold) counts. Safeguard requires an explicit ID."""
    active = sum(1 for i in issues if i.get("state") == "active")
    resolved = sum(1 for i in issues if i.get("state") == "resolved")
    safeguards = sum(1 for i in issues if i.get("safeguard_id"))
    return active, resolved, safeguards


def _issue_rollup_text(software: str, version: str, issues: list[dict[str, Any]]) -> str:
    """Deterministic, official-only body roll-up. Returns "" when there are no issues."""
    if not issues:
        return ""

    active, resolved, safeguards = _issue_counts(issues)

    lines = [
        f"Microsoft Release Health status (official) for {software} {version}: "
        f"{active} active known issue(s), {resolved} resolved, {safeguards} safeguard hold(s). "
        "Source: official Microsoft Windows release-health status page. This is vendor-published "
        "operational status, not user reports."
    ]
    for issue in issues[:MAX_ROLLUP_BULLETS]:
        label = "Active" if issue["state"] == "active" else "Resolved"
        parts = [f"status {issue['status_raw']}", f"originating {_originating_label(issue)}"]
        if issue["last_updated"]:
            parts.append(f"last updated {issue['last_updated']}")
        if issue["resolving_kb"]:
            parts.append(f"resolved by {issue['resolving_kb']}")
        if issue["safeguard_id"]:
            parts.append(f"safeguard ID {issue['safeguard_id']}")
        lines.append(f"- {label}: {_short(issue['summary'])} — " + "; ".join(parts) + ".")

    extra = len(issues) - MAX_ROLLUP_BULLETS
    if extra > 0:
        lines.append(f"- …and {extra} more known issue(s) on the official status page.")

    return "\n".join(lines)


def _status_url_for(source: dict[str, Any], version: str) -> str:
    ingestion = source.get("ingestion", {}) or {}
    template = ingestion.get("status_url_template")
    if not isinstance(template, str) or "{version_slug}" not in template or not version:
        return ""
    return template.replace("{version_slug}", version.lower())


def _enrich_records_with_status(source: dict[str, Any], records: list[dict[str, Any]], options: dict[str, Any]) -> None:
    """Best-effort, body-only: append each version's Release Health issue roll-up.

    Fetch/parse failures are swallowed per version so the base official record is
    never dropped or mutated beyond its body. Only record["body"] is touched; no
    structured/consensus/known_issues fields are added (Phase 1 scope).
    """
    ingestion = source.get("ingestion", {}) or {}
    if not ingestion.get("known_issues_capture"):
        return
    software = source.get("software") or ""

    for record in records:
        version = str(record.get("version") or "")
        url = _status_url_for(source, version)
        if not url:
            continue
        try:
            result = fetch_text(url, **options)
            html = result.text or ""
        except Exception:  # noqa: BLE001 - best-effort: keep the base record intact
            continue
        if not html.strip():
            continue
        issues = _known_issues_from_status_page(html, version)
        if not issues:
            continue
        active, resolved, safeguards = _issue_counts(issues)
        # Official-source signal fields (deterministic counts) — surfaced by the UI as
        # official Microsoft status, kept separate from consensus/report fields.
        record["official_active_issue_count"] = active
        record["official_resolved_issue_count"] = resolved
        record["official_safeguard_hold_count"] = safeguards
        record["official_known_issues_present"] = bool(active or safeguards)
        record["body"] = (str(record.get("body") or "").rstrip() + "\n\n" + _issue_rollup_text(software, version, issues)).strip()


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    ingestion = source.get("ingestion", {}) or {}
    profile = str(ingestion.get("parser_profile") or "").strip()
    if profile not in SUPPORTED_PROFILES:
        return []

    options = _request_options(source)
    candidates = _source_candidates(source)
    fetch_errors: list[str] = []

    for url in candidates:
        try:
            result = fetch_text(url, **options)
        except Exception as exc:  # noqa: BLE001 - surface transport failures below
            fetch_errors.append(f"{url}: {exc}")
            continue
        html = result.text or ""
        if not html.strip():
            fetch_errors.append(f"{url}: empty response")
            continue
        records = _records_from_windows_release_information(source, result.final_url or url, html, limit)
        if records:
            # Best-effort body enrichment; never drops or blocks the base records.
            _enrich_records_with_status(source, records, options)
            return records
        # Fetched OK but no current-version row matched (e.g. the landing/hub page):
        # try the next official URL rather than emitting a snapshot/bad record.

    # Every candidate URL failed to fetch -> surface as a transport error so source
    # health reflects it. Fetched-but-unparseable pages return [] (graceful).
    if candidates and len(fetch_errors) == len(candidates):
        raise RuntimeError("; ".join(fetch_errors[-2:]) or "windows release health fetch failed")
    return []
