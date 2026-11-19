#!/usr/bin/env python3
"""One-time, zero-network removal of contributor account handles from stored GitHub release notes.

The GitHub Releases adapter now removes contributor handles from a release body before it is stored
(lib/contributor_credits.py, adapters/github_releases.release_body). That fixes every record written
from now on. It cannot fix the records already written: the official lane refreshes only the newest
releases, and `release_summary` is never refreshed at all. This migration applies the SAME functions
to the stored text, so a migrated record and one later refreshed from GitHub cannot disagree.

Scope, exactly:
    files     updates/generated/*.md whose product's official source uses the github_releases
              adapter (read from _data/patch_ingestion_sources.yml) and whose release notes came
              from a GitHub release (official_patch_notes_source_type: github-release)
    fields    official_patch_notes_body  -> strip_contributor_credits(...)
              release_summary            -> strip_contributor_credits_from_summary(...)
    nothing else: every other key, the record body below the front matter, every evidence store and
    patch_ingest_state.json are untouched, and the rewritten front matter must parse back equal to
    the original apart from those two values, or the file is refused.

Each file is re-serialised with the record writer's own YAML settings, and only when that setting
reproduces the ORIGINAL bytes exactly; otherwise the file is refused rather than reformatted. The
migration makes no network request, is deterministic, and is idempotent: a second run changes 0
files. Dry run by default; `--write` writes.

The public git history keeps the earlier text. This changes what is published from now on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.contributor_credits import (  # noqa: E402
    strip_contributor_credits, strip_contributor_credits_from_summary)
from lib.normalize import split_front_matter  # noqa: E402

ROOT = SCRIPT_DIR.parent
GENERATED_DIR = ROOT / "updates" / "generated"
SOURCES_PATH = ROOT / "_data" / "patch_ingestion_sources.yml"
ADAPTER = "github_releases"
SOURCE_TYPE = "github-release"
FIELDS = ("official_patch_notes_body", "release_summary")
# The widths the record writers use (lib/write_update_record._dump_record: 120;
# apply_consensus_to_records: 110). A file is re-serialised only with the one that reproduces it.
WIDTHS = (120, 110)


def github_release_products(sources_path: Path = SOURCES_PATH) -> set[str]:
    data = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    rows = data.get("sources") if isinstance(data, dict) else data
    out: set[str] = set()
    for row in rows or []:
        ingestion = (row or {}).get("ingestion") or {}
        if ingestion.get("adapter") == ADAPTER or ingestion.get("type") == ADAPTER:
            out.add(str(row.get("product_id") or ""))
    out.discard("")
    return out


def _dump(front: dict[str, Any], body: str, width: int) -> str:
    return "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=width) + "---\n" + body


def migrate_text(text: str) -> tuple[str, list[str], str]:
    """(new text, fields changed, refusal reason or ""). Pure: no I/O."""
    front_text, body = split_front_matter(text)
    if front_text is None:
        return text, [], "no_front_matter"
    front = yaml.safe_load(front_text) or {}
    width = next((w for w in WIDTHS if _dump(front, body, w) == text), None)
    if width is None:
        return text, [], "not_reproducible_by_record_writer"
    changed: list[str] = []
    updated = dict(front)
    body_value = updated.get("official_patch_notes_body")
    if isinstance(body_value, str):
        new_value = strip_contributor_credits(body_value)
        if new_value != body_value:
            updated["official_patch_notes_body"] = new_value
            changed.append("official_patch_notes_body")
    summary_value = updated.get("release_summary")
    if isinstance(summary_value, str):
        new_value = strip_contributor_credits_from_summary(summary_value)
        if new_value != summary_value:
            updated["release_summary"] = new_value
            changed.append("release_summary")
    if not changed:
        return text, [], ""
    new_text = _dump(updated, body, width)
    reparsed_front, reparsed_body = split_front_matter(new_text)
    reparsed = yaml.safe_load(reparsed_front or "") or {}
    others_equal = ({k: v for k, v in reparsed.items() if k not in FIELDS}
                    == {k: v for k, v in front.items() if k not in FIELDS})
    if list(reparsed) != list(front) or not others_equal or reparsed_body != body:
        return text, [], "would_change_other_content"
    return new_text, changed, ""


def selected_files(generated_dir: Path = GENERATED_DIR, sources_path: Path = SOURCES_PATH) -> list[Path]:
    products = github_release_products(sources_path)
    out: list[Path] = []
    for path in sorted(generated_dir.glob("*.md")):
        text = path.read_bytes().decode("utf-8")
        front_text, _body = split_front_matter(text)
        if front_text is None:
            continue
        front = yaml.safe_load(front_text) or {}
        if (str(front.get("product_id") or "") in products
                and front.get("official_patch_notes_source_type") == SOURCE_TYPE):
            out.append(path)
    return out


def run(*, write: bool, generated_dir: Path = GENERATED_DIR,
        sources_path: Path = SOURCES_PATH) -> dict[str, Any]:
    report: dict[str, Any] = {"mode": "write" if write else "dry-run", "products":
                              sorted(github_release_products(sources_path)), "scanned": 0,
                              "changed": [], "refused": [], "unchanged": 0}
    for path in selected_files(generated_dir, sources_path):
        report["scanned"] += 1
        before = path.read_bytes()
        new_text, changed, refusal = migrate_text(before.decode("utf-8"))
        rel = path.name
        if refusal:
            report["refused"].append({"file": rel, "reason": refusal})
            continue
        if not changed:
            report["unchanged"] += 1
            continue
        after = new_text.encode("utf-8")
        report["changed"].append({"file": rel, "fields": changed,
                                  "sha256_before": hashlib.sha256(before).hexdigest(),
                                  "sha256_after": hashlib.sha256(after).hexdigest()})
        if write:
            tmp = path.with_name(f".{path.name}.migrate.tmp")
            tmp.write_bytes(after)
            tmp.replace(path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="write the changes (default: dry run)")
    args = parser.parse_args(argv)
    report = run(write=args.write)
    print(json.dumps({**report, "changed_count": len(report["changed"])}, indent=2))
    return 1 if report["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
