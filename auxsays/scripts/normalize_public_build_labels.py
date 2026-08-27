#!/usr/bin/env python3
"""Make a build-aware record's STORED public label state the build the record identifies.

Scope: exactly two front-matter fields, `title` and `description`, on products in
``patch_identity.BUILD_AWARE_PRODUCTS``. Nothing else is read, written, fetched or regenerated.

WHY A STORED REPAIR AND NOT A TEMPLATE ONE. Every AUXSAYS-rendered headline -- the detail H1, both
patch-feed card titles, the home signal card, the detail-page citation -- now derives its build at
render time from the record's own ``target_build`` via ``_includes/patch-public-label.html``, which
needs no stored value and cannot drift from the canonical identity. `title` and `description` are
the two that a layout provably cannot reach: ``_layouts/aux-base.html`` renders ``{% seo %}``, and
jekyll-seo-tag reads ``page.title`` / ``page.description`` straight off the front matter to build
``<title>``, ``og:title``, ``og:description`` and the meta description. A layout cannot override
what that plugin reads, so those two are repaired in the data or not at all -- and leaving them
bare would ship a page whose ``<h1>`` states a build its own ``<title>`` does not.

WHY NOT THE REFRESH PATH. ``write_update_record.refresh_existing_record`` only ever runs for a
record still present in the live vendor source. The 2024 and 2025 PowerPoint records will never
appear on the Current Channel page again, so a self-healing refresh could not reach them: it would
fix the newest records, which the write path already gets right, and none of the ones that are
actually wrong.

DOCTRINE. This repair NEVER manufactures build attribution. It rewrites a field only when

  1. the product is build-aware AND the record already carries a non-empty ``target_build``; and
  2. the stored value is byte-identical to a label this repo's own writer produced for that exact
     record -- the version-only form, or the current build-bearing form.

Anything else -- a missing build, a hand-authored title, an unrecognised wording -- is reported and
left exactly as it is. There is no inference, no vendor lookup and no re-ingestion; the build comes
from the record being repaired, and the target strings are the ones
``write_update_record.build_front_matter`` writes today.

Idempotent: a record already carrying the build-bearing label is a no-op, so this is safe to re-run
and safe to use as a gate.

Usage:
    python auxsays/scripts/normalize_public_build_labels.py            # report only, exits 1 if stale
    python auxsays/scripts/normalize_public_build_labels.py --apply    # rewrite the stale records
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from lib.normalize import atomic_write_text, split_front_matter
from lib.patch_identity import identity_build, is_build_aware

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"

# The two fields jekyll-seo-tag reads off the front matter. Deliberately NOT update_feed_title /
# update_detail_title: those are AUXSAYS presentation fields rendered by our own layouts, where
# patch-public-label.html supplies the build at render time from the canonical identity.
REPAIRED_FIELDS = ("title", "description")


def public_version_label(version: str, build: str) -> str:
    """The version half of a public label. Mirrors write_update_record._public_version_label."""
    return f"{version} (Build {build})" if build else str(version)


def expected_values(front: dict[str, Any], build: str) -> dict[str, str] | None:
    """The build-bearing `title` / `description` this repo's writer produces for this record.

    None when the record does not carry enough of its own identity to state a label without
    inventing one."""
    software = str(front.get("update_product") or "").strip()
    company = str(front.get("update_source_name") or "").strip()
    version = str(front.get("update_version") or "").strip()
    if not (software and company and version):
        return None
    labelled = public_version_label(version, build)
    return {
        "title": f"{software} {labelled} official update breakdown",
        "description": f"Official {software} update record captured from {company} for {labelled}.",
    }


def writer_authored_values(front: dict[str, Any]) -> dict[str, set[str]] | None:
    """Every stored value this repo's own writer has ever produced for these fields.

    A stored value outside these sets was not written by the engine -- it is hand-authored or from a
    wording this repo no longer recognises -- and is left untouched rather than overwritten."""
    software = str(front.get("update_product") or "").strip()
    company = str(front.get("update_source_name") or "").strip()
    version = str(front.get("update_version") or "").strip()
    if not (software and company and version):
        return None
    return {
        # The pre-build writer, and the version-only label form.
        "title": {f"{software} {version} official update breakdown"},
        # Two historical description shapes: the original with no version at all, and the
        # version-only label form the current writer produces for a version-only product.
        "description": {
            f"Official {software} update record captured from {company}.",
            f"Official {software} update record captured from {company} for {version}.",
        },
    }


def _key_line_span(lines: list[str], key: str) -> tuple[int, int] | None:
    """The [start, end) line span of a top-level front-matter key, continuations included."""
    prefix = f"{key}:"
    for index, line in enumerate(lines):
        if not (line == prefix or line.startswith(prefix + " ")):
            continue
        end = index + 1
        while end < len(lines) and lines[end].startswith((" ", "\t")):
            end += 1
        return index, end
    return None


def _render_scalar(key: str, value: str) -> list[str]:
    """`key: value` rendered exactly as write_update_record dumps front matter (width=120)."""
    text = yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True, width=120)
    return text.splitlines()


def rewrite_front_matter_fields(text: str, updates: dict[str, str]) -> str:
    """Replace named top-level scalars in a record's front matter, touching nothing else.

    A surgical line splice rather than a parse/re-dump round trip: re-dumping the whole document
    would rewrap and requote every unrelated field in all 20 records, burying a two-field repair in
    a whole-corpus reformat. The result is verified by reparsing before anything is written."""
    front, body = split_front_matter(text)
    if front is None:
        raise ValueError("record has no readable front matter")
    lines = front.splitlines()
    # Later keys first, so an earlier splice cannot shift a span already computed.
    spans: list[tuple[int, int, str]] = []
    for key, value in updates.items():
        span = _key_line_span(lines, key)
        if span is None:
            raise ValueError(f"front matter has no top-level {key!r} key to repair")
        spans.append((span[0], span[1], key))
    for start, end, key in sorted(spans, reverse=True):
        lines[start:end] = _render_scalar(key, updates[key])
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def _parse(text: str) -> dict[str, Any]:
    front, _body = split_front_matter(text)
    data = yaml.safe_load(front) if front is not None else None
    return data if isinstance(data, dict) else {}


def plan_record(path: Path) -> dict[str, Any]:
    """What this record needs, if anything. Never raises on a record it cannot repair."""
    text = path.read_text(encoding="utf-8")
    front = _parse(text)
    result: dict[str, Any] = {"path": path, "status": "skipped", "changes": {}, "notes": []}
    product_id = str(front.get("product_id") or "").strip()
    if not is_build_aware(product_id):
        return result  # version-only product: its label is already complete without a build
    build = identity_build(front, product_id)
    if not build:
        # FAIL QUIET, NOT FALSE. A build-aware record with no build is a real problem, but it is an
        # identity problem, not a labelling one -- and no label may be invented for it here.
        result.update(status="no_build", notes=["record carries no target_build; label left as-is"])
        return result
    targets = expected_values(front, build)
    authored = writer_authored_values(front)
    if targets is None or authored is None:
        result.update(status="incomplete",
                      notes=["record lacks update_product / update_source_name / update_version"])
        return result
    for field in REPAIRED_FIELDS:
        current = str(front.get(field) or "")
        if current == targets[field]:
            continue
        if current in authored[field]:
            result["changes"][field] = targets[field]
        else:
            result["notes"].append(f"{field} is not an engine-written label; left untouched")
    result["status"] = "stale" if result["changes"] else ("unrecognised" if result["notes"] else "current")
    return result


def apply_plan(path: Path, changes: dict[str, str]) -> None:
    """Write the repaired record, refusing if the splice changed anything but the named fields."""
    original = path.read_text(encoding="utf-8")
    updated = rewrite_front_matter_fields(original, changes)
    before, after = _parse(original), _parse(updated)
    if set(before) != set(after):
        raise ValueError(f"{path.name}: the repair added or removed front-matter keys")
    drifted = sorted(k for k in before if before[k] != after[k] and k not in changes)
    if drifted:
        raise ValueError(f"{path.name}: the repair disturbed unrelated fields {drifted}")
    for field, value in changes.items():
        if after.get(field) != value:
            raise ValueError(f"{path.name}: {field} did not round-trip to the intended value")
    _, original_body = split_front_matter(original)
    _, updated_body = split_front_matter(updated)
    if original_body != updated_body:
        raise ValueError(f"{path.name}: the repair disturbed the record body")
    # Same writer the ingestion path uses: LF-only (the repo is `* text=auto eol=lf`) and atomic,
    # so an exception mid-run never leaves a half-written tracked record.
    atomic_write_text(path, updated)


def run(apply: bool, generated_dir: Path = GENERATED_DIR) -> int:
    plans = [plan_record(path) for path in sorted(generated_dir.glob("*.md"))]
    stale = [p for p in plans if p["status"] == "stale"]
    flagged = [p for p in plans if p["status"] in {"no_build", "incomplete", "unrecognised"}]

    print("=" * 78)
    print("Stored public label -- build-aware records")
    print("=" * 78)
    considered = [p for p in plans if p["status"] != "skipped"]
    print(f"  build-aware records: {len(considered)}   already correct: "
          f"{sum(1 for p in considered if p['status'] == 'current')}   stale: {len(stale)}")

    for plan in stale:
        print(f"\n  {plan['path'].name}")
        for field, value in plan["changes"].items():
            print(f"    {field}: -> {value}")
    for plan in flagged:
        print(f"\n  {plan['path'].name}  [{plan['status']}]")
        for note in plan["notes"]:
            print(f"    {note}")

    if apply:
        for plan in stale:
            apply_plan(plan["path"], plan["changes"])
        print(f"\n  applied to {len(stale)} record(s)")
        return 1 if flagged else 0

    if stale:
        print(f"\n  {len(stale)} record(s) need repair. Re-run with --apply.")
    return 1 if (stale or flagged) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true",
                        help="rewrite stale records (default: report only)")
    parser.add_argument("--generated-dir", type=Path, default=GENERATED_DIR)
    args = parser.parse_args(argv)
    return run(args.apply, args.generated_dir)


if __name__ == "__main__":
    sys.exit(main())
