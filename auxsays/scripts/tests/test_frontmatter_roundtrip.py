#!/usr/bin/env python3
"""Round-trip regression for front-matter serialization (fail-soft collection sprint, Req 4).

The OBS "Patch Evidence Collection" workflow failed on every run because the shared front-matter
readers extracted the block with ``text.split("---\\n", 2)`` -- which matches ``---\\n`` as a
substring and TRUNCATES any value whose serialized line ends in three or more hyphens (a
``release_summary`` built from OBS notes containing ``----- Hotfix Changes ------------------``),
leaving an unterminated single-quoted scalar -> "found unexpected end of stream".

This drives the EXACT failure shape (and every adjacent hazard) through the real writer and EVERY
shared reader, comparing the parsed value semantically:

    normalized value -> YAML/front-matter serialization -> repository file -> safe parse -> compare

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_frontmatter_roundtrip.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from patch_collectors import base  # noqa: E402
from patch_collectors.base import split_front_matter  # noqa: E402
from lib import write_update_record  # noqa: E402
from lib.normalize import split_front_matter as normalize_split  # noqa: E402
import apply_consensus_to_records as apply_consensus  # noqa: E402
import collect_obs_reports  # noqa: E402
import patch_ingest  # noqa: E402

# Every hazardous shape the requirement calls out.
SHAPES = {
    "admonition_plus_repeated_hyphens": "> [!IMPORTANT] > Signing cert changed.\n\n----- Hotfix Changes ------------------\nFixed a crash.",
    "bare_triple_hyphen_line": "intro\n---\nafter a bare triple-hyphen line",
    "single_and_double_quotes": "It's a \"quoted\" value that won't break",
    "colons_everywhere": "note: value: 3:14 http://x.test/a:b",
    "leading_yaml_delimiter": "--- not really front matter ---",
    "multiline_markdown": "# Heading\n\n- one\n- two\n\n> blockquote\n\n```\ncode: here\n```\n",
    "unicode": "café — 日本語 — ✅ — naïve — €",
    "html": "<script>alert('x')</script> <b>bold</b> & <em>em</em>",
    "trailing_newlines": "content\nmore\n\n\n",
    "hyphen_run_only": "------------------------------",
}

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


# A hazardous body: an internal hyphen rule AND a bare '---' line that must NOT be mistaken for the
# closing fence (only the FIRST '---' after the front matter closes it; the rest stays in the body).
_BODY = "Body paragraph one.\n\n----- Hotfix Changes ------------------\n\n---\n\ntrailing body line\n"


def run() -> int:
    print("=" * 60)
    print("Front-matter round-trip regression")
    print("=" * 60)

    for name, value in SHAPES.items():
        path = Path(tempfile.mkdtemp(prefix="fm-")) / "rec.md"
        front = {
            "layout": "aux-update", "title": "OBS Studio 32.2.1", "product_id": "obs-studio",
            "update_version": "32.2.1", "release_summary": value,
            "description": "Official OBS Studio update record captured from OBS Project.",
        }
        # Write through the REAL shared writer (safe_dump + atomic replace).
        base.write_front_matter_and_body(path, front, _BODY)
        # Every shared reader must recover the EXACT release_summary value AND the exact body.
        readers = {
            "base.load_front_matter_and_body": base.load_front_matter_and_body,
            "write_update_record._front_matter": write_update_record._front_matter,
            "apply_consensus._load_front_matter_and_body": apply_consensus._load_front_matter_and_body,
            "collect_obs_reports.front_matter_parts": collect_obs_reports.front_matter_parts,
        }
        for reader_name, reader in readers.items():
            try:
                data, body = reader(path)
                check(f"[{name}] {reader_name}: value round-trips (semantic compare)",
                      data.get("release_summary") == value, f"got {data.get('release_summary')!r}")
                check(f"[{name}] {reader_name}: body round-trips exactly (internal '---'/rules kept)",
                      body == _BODY, f"got {body[:70]!r}")
            except Exception as exc:  # noqa: BLE001
                check(f"[{name}] {reader_name}: value round-trips (semantic compare)", False,
                      f"raised {type(exc).__name__}: {exc}")
        # Front-only readers (return just the mapping; the body is discarded by design).
        try:
            data = patch_ingest.load_front_matter(path)
            check(f"[{name}] patch_ingest.load_front_matter: value round-trips (semantic compare)",
                  data.get("release_summary") == value, f"got {data.get('release_summary')!r}")
        except Exception as exc:  # noqa: BLE001
            check(f"[{name}] patch_ingest.load_front_matter: value round-trips (semantic compare)", False,
                  f"raised {type(exc).__name__}: {exc}")

    # split_front_matter unit behaviour (both copies must agree and be delimiter-line-exact).
    for splitter_name, splitter in (("base", split_front_matter), ("normalize", normalize_split)):
        f, b = splitter("---\na: 1\nsummary: '----- x ------------------'\n---\nBODY\n---\nafter\n")
        check(f"{splitter_name}: a '-----' value line does not close the fence", f is not None and "summary" in f and b.startswith("BODY"))
        f2, b2 = splitter("no front matter here\n")
        check(f"{splitter_name}: no fence -> (None, text)", f2 is None and b2 == "no front matter here\n")
        f3, b3 = splitter("---\nopened: 1\nbut never closed\n")
        check(f"{splitter_name}: opened-but-unclosed -> (None, text)", f3 is None)
        f4, b4 = splitter("---\nx: 1\n---\n")
        check(f"{splitter_name}: empty body after fence", f4 is not None and b4 == "")

    # Old-bug shape: no production reader may still use the fragile substring splitter.
    import inspect
    src = (inspect.getsource(base.load_front_matter_and_body)
           + inspect.getsource(apply_consensus._load_front_matter_and_body)
           + inspect.getsource(write_update_record._front_matter)
           + inspect.getsource(patch_ingest.load_front_matter))
    check("no reader still uses the fragile text.split('---\\n', 2)", 'split("---\\n"' not in src)

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
