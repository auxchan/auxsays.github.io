#!/usr/bin/env python3
"""Tests for Blackmagic support-download official ingestion.

Run with: python auxsays/scripts/tests/test_blackmagic_support_downloads.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import adapters.blackmagic_support_downloads as adapter

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def source(include_prereleases: bool = False) -> dict:
    return {
        "company_id": "blackmagic-design",
        "product_id": "blackmagic-davinci",
        "company": "Blackmagic Design",
        "software": "DaVinci Resolve",
        "public_category": "Video / Production",
        "ingestion": {
            "official_url": "https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion",
            "api_url": "https://www.blackmagicdesign.com/api/support/us/downloads.json",
            "include_prereleases": include_prereleases,
        },
    }


def fake_payload() -> dict:
    return {
        "downloads": [
            {
                "id": "beta-2",
                "typeDisplay": "Software Update",
                "platforms": ["Mac OS X", "Windows", "Linux"],
                "urls": {
                    "Windows": [{
                        "downloadTitle": "DaVinci Resolve 21 Beta 2",
                        "product": "davinci-resolve",
                        "major": 21,
                        "minor": 0,
                        "releaseNum": 0,
                        "buildNum": 28,
                        "beta": 2,
                    }]
                },
                "date": "28 Apr 2026",
                "relatedFamilies": ["davinci-resolve-and-fusion"],
                "name": "DaVinci Resolve 21 Public Beta 2",
                "desc": "Public beta improvements and bug fixes.",
                "releaseNotesTitle": "DaVinci Resolve 21 Beta 2",
                "numericDate": 1777359610000,
            },
            {
                "id": "stable-20-3-2",
                "typeDisplay": "Software Update",
                "platforms": ["Mac OS X", "Windows", "Linux", "Windows ARM"],
                "urls": {
                    "Windows": [{
                        "downloadTitle": "DaVinci Resolve 20.3.2",
                        "product": "davinci-resolve",
                        "major": 20,
                        "minor": 3,
                        "releaseNum": 2,
                        "buildNum": 9,
                        "beta": 255,
                    }]
                },
                "date": "12 Feb 2026",
                "relatedFamilies": ["davinci-resolve-and-fusion"],
                "name": "DaVinci Resolve 20.3.2",
                "desc": "Stable update with editing, subtitles, camera metadata, and technical monitoring improvements.",
                "releaseNotesTitle": "DaVinci Resolve 20.3.2",
                "numericDate": 1770883210000,
            },
            {
                "id": "fusion",
                "typeDisplay": "Software Update",
                "platforms": ["Mac OS X"],
                "urls": {},
                "date": "28 Apr 2026",
                "relatedFamilies": ["davinci-resolve-and-fusion"],
                "name": "Fusion Studio 21 Public Beta 2",
                "desc": "Fusion-only update.",
                "releaseNotesTitle": "Fusion Studio 21 Beta 2",
                "numericDate": 1777359610000,
            },
        ]
    }


def run() -> int:
    print("=" * 60)
    print("Blackmagic support-download ingestion tests")
    print("=" * 60)

    original_fetch_json = adapter._fetch_json
    try:
        adapter._fetch_json = lambda _url, timeout=30: fake_payload()

        stable_records = adapter.fetch(source(False), limit=3)
        check("stable-only mode emits one record", len(stable_records) == 1, f"records={stable_records!r}")
        check("stable-only mode skips Public Beta 2", stable_records[0]["version"] == "20.3.2", stable_records[0].get("version", ""))
        check("stable record uses official support-download capture status", stable_records[0]["capture_status"] == "captured-from-official-blackmagic-support-api")
        check("stable record classifies source as download portal", stable_records[0]["official_source_type"] == "download_portal")
        check("stable record body names official metadata endpoint", "Official metadata endpoint:" in stable_records[0]["body"])
        check("stable record does not expose blank file size", stable_records[0]["file_size_status"] == "not_provided_by_source")

        prerelease_records = adapter.fetch(source(True), limit=3)
        versions = [record["version"] for record in prerelease_records]
        check("prerelease mode preserves beta canonical version", "21 Public Beta 2" in versions, f"versions={versions!r}")
        check("prerelease mode also keeps stable record separate", "20.3.2" in versions, f"versions={versions!r}")
        beta = next(record for record in prerelease_records if record["version"] == "21 Public Beta 2")
        check("beta channel label stays public beta", beta["release_channel_label"] == "Public beta", beta.get("release_channel_label", ""))
        check("Fusion sibling downloads are ignored", all("Fusion" not in record["title"] for record in prerelease_records))
    finally:
        adapter._fetch_json = original_fetch_json

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)

    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
