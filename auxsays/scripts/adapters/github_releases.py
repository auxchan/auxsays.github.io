"""GitHub releases adapter."""
from __future__ import annotations

from typing import Any

from lib.http import fetch_json
from lib.normalize import format_asset_size, first_nonempty, normalize_date

def _asset_url(asset: dict[str, Any]) -> str:
    return first_nonempty(asset.get("browser_download_url"), asset.get("url"))

def _preferred_asset(assets: list[dict[str, Any]], product_id: str) -> dict[str, Any] | None:
    if not assets:
        return None
    names = []
    if product_id == "obs-studio":
        names = ["Windows-x64-Installer.exe", "Windows-x64", ".exe"]
    elif product_id == "comfyui":
        names = [".zip", ".7z", ".exe"]
    for needle in names:
        for asset in assets:
            if needle.lower() in str(asset.get("name", "")).lower():
                return asset
    return assets[0]

def _split_checksums(body: str, selector: str | None = "## Checksums") -> tuple[str, str]:
    body = body or ""
    if selector and selector in body:
        before, after = body.split(selector, 1)
        return before.rstrip(), (selector + "\n\n" + after.strip()).strip()
    return body.strip(), ""

def fetch(source: dict[str, Any], limit: int = 2) -> list[dict[str, Any]]:
    ingestion = source.get("ingestion", {})
    api_url = ingestion.get("api_url")
    if not api_url:
        raise RuntimeError(f"{source['product_id']} is missing ingestion.api_url")
    releases = fetch_json(api_url)
    include_prereleases = bool(ingestion.get("include_prereleases"))
    records = []
    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_prereleases:
            continue
        version = first_nonempty(release.get("tag_name"), release.get("name")).lstrip("v")
        body, checksums = _split_checksums(release.get("body") or "", ingestion.get("checksum_selector"))
        asset = _preferred_asset(release.get("assets") or [], source["product_id"])
        file_size = format_asset_size(asset.get("size")) if asset else ""
        file_note = f"{asset.get('name')}. Platform assets vary." if asset else ""
        records.append({
            "record_id": f"github:{source['product_id']}:{release.get('id') or version}",
            "company_id": source["company_id"],
            "product_id": source["product_id"],
            "company": source["company"],
            "software": source["software"],
            "category": source.get("public_category"),
            "version": version,
            "title": first_nonempty(release.get("name"), version),
            "published_at": normalize_date(first_nonempty(release.get("published_at"), release.get("created_at"))),
            "source_url": first_nonempty(release.get("html_url"), ingestion.get("official_url")),
            "official_url": ingestion.get("official_url"),
            "download_url": _asset_url(asset) if asset else first_nonempty(ingestion.get("secondary_official_url"), ingestion.get("official_url")),
            "file_size": file_size,
            "file_size_note": file_note,
            "body": body or "No official release body was returned by the GitHub Releases API.",
            "checksums_body": checksums,
            "summary": "",
            "source_type": "github-release",
            "capture_status": "captured-from-github-release-body",
        })
        if len(records) >= limit:
            break
    return records
