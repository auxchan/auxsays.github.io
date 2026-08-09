#!/usr/bin/env python3
"""Regression proof for patch_ingest.load_front_matter (official-ingestion restoration).

Scheduled official ingestion (patch-ingest.yml -> patch_ingest.py) failed on every run since
2026-08-06: ``load_front_matter`` still extracted the front-matter block with
``text.split("---\\n", 2)`` -- the fragile substring splitter PR #36 replaced in every other
production reader. A single-quoted ``release_summary`` (an OBS ``> [!IMPORTANT]`` admonition plus
a ``Hotfix Changes ------------------`` hyphen rule) folded by the writer onto a line ending in
``---`` was mistaken for the closing fence, truncating the block mid-scalar ->
``yaml.scanner.ScannerError: found unexpected end of stream``.

This suite drives the EXACT production record plus every adjacent hazard through the fixed
reader (now delegated to ``lib.normalize.split_front_matter``), and pins the rejection policy
(missing fences -> {}, malformed YAML -> still raises, non-mapping -> {}).

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_ingest_front_matter.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import patch_ingest  # noqa: E402
from patch_collectors import base  # noqa: E402

# The exact committed record whose folded release_summary crashed scheduled production
# (runs 31158859151..31290501596, "found unexpected end of stream").
PRODUCTION_RECORD = _REPO / "auxsays" / "updates" / "generated" / "2025-07-28-obs-studio-31-1-2.md"

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def _tmp_record(text: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix="pi-fm-")) / "rec.md"
    path.write_text(text, encoding="utf-8", newline="")
    return path


def run() -> int:  # noqa: PLR0915
    print("=" * 60)
    print("patch_ingest.load_front_matter regression")
    print("=" * 60)

    # 1. The exact production OBS record (unmodified, committed).
    try:
        front = patch_ingest.load_front_matter(PRODUCTION_RECORD)
        check("production OBS 31.1.2 record parses (was ScannerError on main)",
              bool(front) and front.get("product_id") == "obs-studio"
              and front.get("update_version") == "31.1.2",
              f"got {len(front)} keys, product_id={front.get('product_id')!r}")
        summary = str(front.get("release_summary") or "")
        check("production record: release_summary recovered intact (admonition + hyphen rule)",
              summary.startswith("> [!IMPORTANT]") and "Hotfix Changes" in summary,
              f"got {summary[:80]!r}")
    except Exception as exc:  # noqa: BLE001
        check("production OBS 31.1.2 record parses (was ScannerError on main)", False,
              f"raised {type(exc).__name__}: {exc}")
        check("production record: release_summary recovered intact (admonition + hyphen rule)", False)

    # 2. '---' inside a quoted scalar.
    path = _tmp_record("---\nrelease_summary: 'before --- after'\nproduct_id: obs-studio\n---\nBody\n")
    front = patch_ingest.load_front_matter(path)
    check("'---' inside a quoted scalar survives", front.get("release_summary") == "before --- after")

    # 3. A folded continuation line ENDING in a hyphen run (the exact production failure shape:
    #    the line's trailing '---\n' matched the old substring split).
    path = _tmp_record(
        "---\n"
        "release_summary: 'See notes. 31.1.2 Hotfix Changes ---------------------\n"
        "  Fixed a crash on startup.'\n"
        "product_id: obs-studio\n"
        "---\nBody\n"
    )
    front = patch_ingest.load_front_matter(path)
    check("scalar line ending in a hyphen run does not close the fence",
          "Hotfix Changes" in str(front.get("release_summary")) and front.get("product_id") == "obs-studio",
          f"got {front.get('release_summary')!r}")

    # 4. Folded (>) and literal (|) block scalars containing '---'.
    path = _tmp_record("---\nrelease_summary: >\n  folded text\n  --- embedded\nproduct_id: obs-studio\n---\n")
    front = patch_ingest.load_front_matter(path)
    check("folded block scalar with '---' parses", "--- embedded" in str(front.get("release_summary")))
    path = _tmp_record("---\nrelease_summary: |\n  line one\n  ---\n  line three\nproduct_id: obs-studio\n---\n")
    front = patch_ingest.load_front_matter(path)
    check("literal block scalar with a bare '---' line parses",
          str(front.get("release_summary")).splitlines()[1:2] == ["---"])

    # 5. GitHub-flavored Markdown admonition text.
    path = _tmp_record("---\nrelease_summary: '> [!IMPORTANT] > The code signing certificate changed.'\n---\n")
    front = patch_ingest.load_front_matter(path)
    check("'> [!IMPORTANT]' admonition value parses",
          str(front.get("release_summary")).startswith("> [!IMPORTANT]"))

    # 6. Multiline release_summary written through the REAL production writer.
    value = "> [!IMPORTANT] > Cert changed.\n\n----- Hotfix Changes ------------------\nFixed a crash."
    path = Path(tempfile.mkdtemp(prefix="pi-fm-")) / "rec.md"
    base.write_front_matter_and_body(path, {"layout": "aux-update", "release_summary": value,
                                            "product_id": "obs-studio"}, "Body\n")
    front = patch_ingest.load_front_matter(path)
    check("multiline release_summary via the production writer round-trips",
          front.get("release_summary") == value, f"got {front.get('release_summary')!r}")

    # 7. CRLF input (the shared parser strips trailing CR on fence lines).
    path = _tmp_record("---\r\nrelease_summary: 'crlf value'\r\nproduct_id: obs-studio\r\n---\r\nBody\r\n")
    front = patch_ingest.load_front_matter(path)
    check("CRLF front matter parses", front.get("release_summary") == "crlf value")

    # 8. Normal conventional front matter.
    path = _tmp_record("---\nlayout: aux-update\ntitle: OBS Studio 32.2.1\nupdate_version: 32.2.1\n---\nBody\n")
    front = patch_ingest.load_front_matter(path)
    check("conventional front matter parses", front.get("update_version") == "32.2.1")

    # Rejection policy (unchanged from the previous reader's contract).
    path = _tmp_record("no front matter here\njust body\n")
    check("missing opening fence -> {}", patch_ingest.load_front_matter(path) == {})
    path = _tmp_record("---\nopened: 1\nbut never closed\n")
    check("missing closing fence -> {}", patch_ingest.load_front_matter(path) == {})
    path = _tmp_record("---\n---\nBody\n")
    check("empty front matter -> {}", patch_ingest.load_front_matter(path) == {})
    path = _tmp_record("---\n- just\n- a\n- list\n---\nBody\n")
    check("non-mapping front matter -> {}", patch_ingest.load_front_matter(path) == {})
    path = _tmp_record("---\nkey: 'unterminated\n---\nBody\n")
    try:
        patch_ingest.load_front_matter(path)
        check("genuinely malformed YAML still raises (policy unchanged)", False, "no exception raised")
    except yaml.YAMLError:
        check("genuinely malformed YAML still raises (policy unchanged)", True)

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
