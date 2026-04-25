#!/usr/bin/env python3
"""AUXSAYS source-driven patch tracker.

This replaces one-off product workflows with a single updater that loops through
`auxsays/_data/patch_sources.yml`.

What it can safely automate today:
- GitHub release sources: capture official release notes and generate update pages.
- Other official sources: check reachability, compute a cleaned content hash, and
  baseline/change-track the source without inventing unreliable patch records.

The script intentionally does not manufacture public patch pages from generic HTML
pages unless a source-specific parser is added later.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - workflow installs PyYAML
    raise SystemExit("PyYAML is required. Install with: python -m pip install PyYAML") from exc

ROOT = pathlib.Path("auxsays")
DATA_DIR = ROOT / "_data"
SOURCE_PATH = DATA_DIR / "patch_sources.yml"
STATE_PATH = DATA_DIR / "patch_state.json"
NOTIFY_PATH = DATA_DIR / "patch_notifications.json"
OUTPUT_DIR = ROOT / "updates" / "generated"

USER_AGENT = "auxsays-release-intelligence/1.0 (+https://auxsays.com/updates/)"
REQUEST_TIMEOUT = 35
MAX_HTML_BYTES = 1_500_000

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: pathlib.Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: pathlib.Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_yaml(path: pathlib.Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def yaml_frontmatter(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-") or "update"


def request_text(url: str, extra_headers: dict[str, str] | None = None, limit: int | None = None) -> tuple[str, dict[str, str]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        raw = resp.read(limit or -1)
        content_type = resp.headers.get("content-type", "")
        charset_match = re.search(r"charset=([^;]+)", content_type, re.I)
        charset = charset_match.group(1).strip() if charset_match else "utf-8"
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        return text, {k.lower(): v for k, v in resp.headers.items()}


def request_json(url: str) -> Any:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    text, _headers = request_text(url, headers)
    return json.loads(text)


def source_kind(source: dict[str, Any]) -> str:
    explicit = str(source.get("ingestion_strategy") or source.get("source_type") or "").strip().lower()
    if explicit:
        return explicit
    url = str(source.get("source_url") or "")
    if re.search(r"github\.com/[^/]+/[^/]+/releases/?$", url):
        return "github_releases"
    return "official_source_watch"


def github_api_from_releases_url(url: str) -> str | None:
    match = re.search(r"github\.com/([^/]+)/([^/]+)/releases/?$", url)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    return f"https://api.github.com/repos/{owner}/{repo}/releases"


def normalize_html_for_hash(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<!--[\s\S]*?-->", " ", text)
    text = re.sub(r"\b(?:nonce|integrity|crossorigin|data-[\w-]+)=(['\"]).*?\1", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return html.unescape(text).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:20]


def extract_title(text: str) -> str:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if title_match:
        return re.sub(r"\s+", " ", html.unescape(title_match.group(1))).strip()
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S)
    if h1_match:
        clean = re.sub(r"<[^>]+>", " ", h1_match.group(1))
        return re.sub(r"\s+", " ", html.unescape(clean)).strip()
    return "Official source"


def format_asset_size(size_bytes: Any) -> str:
    try:
        size = float(size_bytes or 0)
    except (TypeError, ValueError):
        return ""
    if size <= 0:
        return ""
    units = ["B", "KB", "MB", "GB"]
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    if idx < 2:
        return f"{size:.0f} {units[idx]}"
    return f"{size:.0f} {units[idx]}" if size >= 100 else f"{size:.1f} {units[idx]}"


def primary_asset_size(release: dict[str, Any]) -> tuple[str, str]:
    assets = release.get("assets") or []
    if not assets:
        return "", ""
    preferred = None
    preferred_patterns = [
        r"windows.*(?:installer|setup).*\.(?:exe|msi)$",
        r"win.*(?:x64|64).*\.(?:exe|msi|zip)$",
        r"x64.*\.(?:exe|msi|zip)$",
        r"\.exe$",
        r"\.msi$",
        r"\.zip$",
    ]
    for pattern in preferred_patterns:
        for asset in assets:
            if re.search(pattern, asset.get("name", ""), re.I):
                preferred = asset
                break
        if preferred:
            break
    preferred = preferred or assets[0]
    label = format_asset_size(preferred.get("size"))
    note = f"{preferred.get('name', 'Primary asset')}. Platform assets may vary."
    return label, note


def split_official_sections(body: str) -> tuple[str, str]:
    checksum_match = re.search(r"(^|\n)##\s+Checksums\b", body, re.I)
    if not checksum_match:
        return body.strip(), ""
    start = checksum_match.start()
    before = body[:start].rstrip()
    after = body[start:].strip()
    return before, after


def release_version(release: dict[str, Any]) -> str:
    return str(release.get("tag_name") or release.get("name") or "unknown").lstrip("v")


def release_published(release: dict[str, Any]) -> str:
    return str(release.get("published_at") or release.get("created_at") or utc_now())


def clean_release_body(release: dict[str, Any]) -> str:
    body = (release.get("body") or "No official release body was returned by the GitHub API.").strip()
    return body


def consensus_for_release(release: dict[str, Any], index: int) -> str:
    if release.get("prerelease"):
        return "Insufficient data"
    return "Moderate" if index == 0 else "Insufficient data"


def write_github_release_page(source: dict[str, Any], release: dict[str, Any], index: int, now: str) -> pathlib.Path:
    version = release_version(release)
    version_slug = slugify(version)
    published = release_published(release)
    date_slug = published[:10] if re.match(r"\d{4}-\d{2}-\d{2}", published) else now[:10]
    body, checksums_body = split_official_sections(clean_release_body(release))
    patch_file_size, patch_file_size_note = primary_asset_size(release)
    consensus = consensus_for_release(release, index)
    status = "current" if index == 0 else "archived"
    product_name = source.get("product_name") or source.get("id") or "Software"
    company_name = source.get("company_name") or source.get("update_source_name") or "Official source"
    product_id = source.get("product_id") or source.get("id")
    company_id = source.get("company_id") or slugify(company_name)
    product_url = source.get("product_url") or f"/updates/{company_id}/{product_id}/"
    permalink = product_url.rstrip("/") + f"/{version_slug}/"
    release_url = release.get("html_url") or source.get("source_url")

    front = {
        "layout": "aux-update",
        "title": f"{product_name} {version} official update breakdown",
        "description": f"Published {published[:10]}. {product_name} {version} official release record with AUXSAYS monitoring and upstream release notes preserved below.",
        "permalink": permalink,
        "update_entry": True,
        "company_id": company_id,
        "product_id": product_id,
        "update_brand_id": source.get("source_id") or source.get("id") or product_id,
        "update_product": product_name,
        "update_category": source.get("category_key") or "creator-software",
        "update_type": source.get("category_key") or "creator-software",
        "update_source_name": company_name,
        "update_source_url": release_url,
        "update_download_url": source.get("download_url") or source.get("source_url"),
        "update_version": version,
        "update_logo_text": source.get("badge_text") or str(product_name)[:3].upper(),
        "update_published_at": published,
        "update_last_checked": now,
        "patch_file_size": patch_file_size,
        "patch_file_size_note": patch_file_size_note,
        "update_status": status,
        "update_feed_title": f"{product_name} {version}",
        "update_detail_title": f"{product_name} {version}",
        "update_consensus_label": consensus,
        "update_report_count": 0,
        "update_consensus_confidence": "Low",
        "quick_verdict": f"{product_name} {version} has an initialized AUXSAYS record. Consensus should be updated after public reports are gathered and categorized.",
        "official_summary": f"{company_name} published {product_name} {version}. The official GitHub release notes are preserved below.",
        "consensus_report": "Consensus collection is initialized. Community reports still need to be gathered, categorized, and verified before a stronger recommendation is assigned.",
        "complaint_themes": [],
        "status_events": [
            {"at": published, "label": "Published", "note": f"Official {product_name} release detected from GitHub releases."},
            {"at": now, "label": consensus, "note": "Initial AUXSAYS monitoring record created from official release metadata."},
        ],
        "official_patch_notes_source_type": "github-release",
        "official_patch_notes_capture_status": "captured-from-github-release-body",
        "official_patch_notes_source_url": release_url,
        "official_patch_notes_body": body,
        "official_checksums_body": checksums_body,
        "official_checksums_capture_status": "captured-from-official-release" if checksums_body else "not-present",
    }
    output = OUTPUT_DIR / f"{date_slug}-{slugify(product_name)}-{version_slug}.md"
    output.write_text("---\n" + yaml_frontmatter(front) + "\n---\n", encoding="utf-8")
    return output


def max_release_records_for(source: dict[str, Any]) -> int:
    source_id = source.get("id")
    if source_id == "obs-studio":
        return 2
    return int(source.get("max_release_records") or 1)


def update_github_source(source: dict[str, Any], state: dict[str, Any], notes: list[dict[str, Any]], now: str) -> tuple[int, str]:
    api_url = github_api_from_releases_url(str(source.get("source_url") or ""))
    if not api_url:
        raise ValueError("Could not derive GitHub API URL from source_url")
    releases = request_json(api_url)
    if not isinstance(releases, list):
        raise ValueError("GitHub API response was not a release list")

    stable = [r for r in releases if not r.get("draft") and not r.get("prerelease")]
    selected = stable or [r for r in releases if not r.get("draft")]
    selected = selected[:max_release_records_for(source)]
    if not selected:
        raise ValueError("No usable GitHub releases were returned")

    for idx, release in enumerate(selected):
        write_github_release_page(source, release, idx, now)

    source_id = source["id"]
    latest = selected[0]
    latest_version = release_version(latest)
    prev = state.get(source_id, {}) if isinstance(state.get(source_id), dict) else {}
    previous_version = prev.get("current_version", "")
    status_change_type = "initialized" if not previous_version else ("updated" if previous_version != latest_version else "checked")

    state[source_id] = {
        **prev,
        "source_type": "github_releases",
        "source_status": "ok",
        "source_url": source.get("source_url"),
        "current_version": latest_version,
        "previous_version": previous_version,
        "current_consensus": prev.get("current_consensus") or consensus_for_release(latest, 0),
        "previous_consensus": prev.get("current_consensus", ""),
        "status_changed_at": now if status_change_type != "checked" else prev.get("status_changed_at", now),
        "status_change_type": status_change_type,
        "report_count": prev.get("report_count", 0),
        "last_checked": now,
        "latest_release_url": latest.get("html_url") or source.get("source_url"),
    }

    if previous_version and previous_version != latest_version:
        note_url = (source.get("product_url") or f"/updates/{source.get('company_id')}/{source_id}/").rstrip("/") + f"/{slugify(latest_version)}/"
        notes.insert(0, {
            "product": source.get("product_name", source_id),
            "version": latest_version,
            "change_type": "updated",
            "from": previous_version,
            "to": latest_version,
            "changed_at": now,
            "message": f"{source.get('product_name', source_id)} {latest_version} official release notes were captured from the upstream GitHub release feed.",
            "url": note_url,
            "report_count": 0,
        })

    return len(selected), latest_version


def update_html_watch_source(source: dict[str, Any], state: dict[str, Any], now: str) -> tuple[bool, str]:
    url = str(source.get("source_url") or "")
    if not url:
        raise ValueError("No source_url configured")
    text, headers = request_text(url, limit=MAX_HTML_BYTES)
    normalized = normalize_html_for_hash(text)
    digest = content_hash(normalized)
    source_id = source["id"]
    prev = state.get(source_id, {}) if isinstance(state.get(source_id), dict) else {}
    previous_hash = prev.get("source_hash", "")
    changed = bool(previous_hash and previous_hash != digest)
    title = extract_title(text)
    state[source_id] = {
        **prev,
        "source_type": "official_source_watch",
        "source_status": "ok",
        "source_url": url,
        "source_label": source.get("source_label"),
        "source_title": title,
        "source_hash": digest,
        "previous_source_hash": previous_hash,
        "source_changed_pending_review": changed,
        "status_change_type": "source_changed" if changed else ("initialized" if not previous_hash else "checked"),
        "status_changed_at": now if changed or not previous_hash else prev.get("status_changed_at", now),
        "last_checked": now,
        "http_content_type": headers.get("content-type", ""),
        "monitor_note": "Official source was checked and hash-tracked. No public patch page is generated until a source-specific parser or manual review confirms the change.",
    }
    return changed, title


def main() -> int:
    now = utc_now()
    sources = load_yaml(SOURCE_PATH)
    if not isinstance(sources, list):
        raise SystemExit("patch_sources.yml must be a YAML list")

    only = {item.strip() for item in os.getenv("AUXSAYS_ONLY", "").split(",") if item.strip()}
    if only:
        sources = [s for s in sources if s.get("id") in only]

    state = load_json(STATE_PATH, {})
    notes = load_json(NOTIFY_PATH, [])
    if not isinstance(notes, list):
        notes = []

    ok = 0
    failed = 0
    github_records = 0
    changed_watch_sources = 0

    for source in sources:
        source_id = source.get("id")
        if not source_id:
            continue
        kind = source_kind(source)
        try:
            if kind == "github_releases":
                count, version = update_github_source(source, state, notes, now)
                github_records += count
                print(f"OK github_releases {source_id}: {version} ({count} record(s))")
            else:
                changed, title = update_html_watch_source(source, state, now)
                changed_watch_sources += 1 if changed else 0
                marker = "changed" if changed else "checked"
                print(f"OK official_source_watch {source_id}: {marker} ({title[:80]})")
            ok += 1
        except Exception as exc:  # keep one bad vendor page from killing the whole run
            failed += 1
            prev = state.get(source_id, {}) if isinstance(state.get(source_id), dict) else {}
            state[source_id] = {
                **prev,
                "source_type": kind,
                "source_status": "error",
                "source_url": source.get("source_url"),
                "last_checked": now,
                "last_error": str(exc),
            }
            print(f"ERROR {source_id}: {exc}", file=sys.stderr)

    notes = notes[:25]
    state["_software_update_run"] = {
        "last_checked": now,
        "sources_checked": ok,
        "sources_failed": failed,
        "github_release_records_written": github_records,
        "watch_sources_changed_pending_review": changed_watch_sources,
    }
    save_json(STATE_PATH, state)
    save_json(NOTIFY_PATH, notes)
    print(f"Summary: {ok} source(s) checked, {failed} failed, {github_records} GitHub release record(s) written, {changed_watch_sources} watch source(s) changed.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
