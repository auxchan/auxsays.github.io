#!/usr/bin/env python3
"""Audited withdrawal of the Windows rows the AUX-067 authority now refuses (AUX-072).

AUX-067 taught the Windows acceptance authority that a build-only identity whose TITLE is about some
other update ("I can't install KB2267602", "Excel 2608 (Build 16.0.20326.20100) crashes") is a report
about that other update, not about the build the author quoted in a spec line. Fixing the producer
does not touch a row already stored: the store is append/dedupe oriented and Microsoft Learn Q&A has
no revalidation adapter, so eight rows stayed counted. An audited withdrawal is `counted: false` with
a non-empty `exclusion_reason` and the ROW KEPT, never a deletion (lib/evidence_loss.py).

THE SELECTION IS PINNED, THE VERDICT IS DERIVED. The rows are named in
`audit/windows_identity_not_the_subject_withdrawal.json` by their FULL five-field identity
(product_id, update_version, target_build, id, source_url). Windows needs all five: one Q&A thread
is stored once per build it was matched on, so an id or a URL alone names several rows (5989625 is
also stored on 26200.8973, and the thread of the kept row 51 on three other builds). The Acrobat/OBS
selector (product, version, URL) would refuse or pick the wrong sibling here. Each named row must
match exactly one block, and that block must hash to the manifest's pinned value; the shared
predicate `microsoft_windows.identity_not_the_subject` must refuse it against its record's CURRENT
target identity. Every counted Windows row is also swept with that predicate: a refusal the manifest
does not name is a new candidate that needs its own audit, so the run refuses instead of widening.

FAIL CLOSED, ALL OR NOTHING. Any ambiguous or missing selector, a block whose hash moved, a record
whose target identity moved, a pinned row the authority no longer refuses, a retained row that is
touched or refused, or an edit that changes anything but the three fields refuses the whole run
before a byte is written. A row already withdrawn with this reason (its block hashes to the pinned
after-value) is left alone, so a second run changes nothing.

THE EDIT is block-scoped text, three lines per row: `counted: true -> false`,
`exclusion_reason: null -> identity_not_the_subject`, `evidence_valid_for_current_patch: true ->
false`. Re-serialising the store would normalise every row; an audited withdrawal must read as the
rows it withdraws. The block splitter is imported from the Acrobat withdrawal tool, not copied.

This script only edits the evidence store. The published counts follow from the existing scoped
writers (build_consensus_from_evidence.py --product-id microsoft-windows-11 --reconcile-only, then
apply_consensus_to_records.py --product-id microsoft-windows-11 --write-all --confirm-write).

Run:  python auxsays/scripts/withdraw_windows_identity_not_the_subject_rows.py                  # dry run
      python auxsays/scripts/withdraw_windows_identity_not_the_subject_rows.py --write --confirm-write
      ... --audit PATH --parent-commit SHA                                    # also write the audit
Exit: 0 dry run, written, or nothing left to do; 1 refused (nothing written); 2 usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from lib.patch_identity import patch_key  # noqa: E402
from lib.report_counts import counted_evidence_counts, windows_targets_from_front_matter  # noqa: E402
from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors.base import WINDOWS_PRODUCT_ID, load_front_matter_and_body, row_is_counted  # noqa: E402
from withdraw_acrobat_wrong_edition_rows import (COUNTED_FALSE, COUNTED_TRUE, EOL,  # noqa: E402
                                                 REASON_NULL, _blocks)

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "_data" / "consensus_evidence.yml"
GENERATED = ROOT / "updates" / "generated"
MANIFEST = Path(__file__).resolve().parent / "audit" / "windows_identity_not_the_subject_withdrawal.json"
AUTHORITY_FILE = Path(mw.__file__).resolve()

REASON = "identity_not_the_subject"
SELECTOR = ("product_id", "update_version", "target_build", "id", "source_url")
REASON_SET = EOL + "  exclusion_reason: " + REASON + EOL
VALID_TRUE = EOL + "  evidence_valid_for_current_patch: true" + EOL
VALID_FALSE = EOL + "  evidence_valid_for_current_patch: false" + EOL
EDIT = ((COUNTED_TRUE, COUNTED_FALSE), (REASON_NULL, REASON_SET), (VALID_TRUE, VALID_FALSE))
WITHDRAWN_FIELDS = {"counted": False, "exclusion_reason": REASON, "evidence_valid_for_current_patch": False}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_FRONT_RE = re.compile(r"^product_id:\s*['\"]?" + re.escape(WINDOWS_PRODUCT_ID) + r"['\"]?\s*$", re.M)


class Refusal(Exception):
    """The run cannot proceed safely. Nothing has been written."""


def sha(text: str | bytes) -> str:
    return hashlib.sha256(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()


def identity(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(key) or "") for key in SELECTOR)


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return manifest_entries(json.loads(Path(path).read_text(encoding="utf-8")))


def manifest_entries(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """The pinned entries, refusing a manifest that could select ambiguously."""
    if doc.get("exclusion_reason") != REASON or list(doc.get("selector") or []) != list(SELECTOR):
        raise Refusal("manifest: wrong exclusion_reason or selector")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise Refusal("manifest: no entries")
    seen: set[tuple[str, ...]] = set()
    for entry in entries:
        ident = tuple(str(entry.get(key) or "") for key in SELECTOR)
        if not all(ident):
            raise Refusal(f"manifest: an entry lacks part of the five-field identity: {ident}")
        if ident[0] != WINDOWS_PRODUCT_ID:
            raise Refusal(f"manifest: not a Windows row: {ident}")
        if ident in seen:
            raise Refusal(f"manifest: identity listed twice: {ident}")
        seen.add(ident)
        role = entry.get("role")
        hashes = ["block_sha256_before"] + (["block_sha256_after"] if role == "withdraw" else [])
        if role not in ("withdraw", "retain"):
            raise Refusal(f"manifest: unknown role {role!r}")
        if not all(SHA256_RE.match(str(entry.get(key) or "")) for key in hashes):
            raise Refusal(f"manifest: missing or malformed block hash for {ident[3]}")
        if not entry.get("target_kb") or not entry.get("target_os_build"):
            raise Refusal(f"manifest: no pinned target identity for {ident[3]}")
    return entries


def windows_targets(generated_dir: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Patch key -> the Windows record's CURRENT front matter. Only files whose front matter names
    the Windows product are parsed; `windows_targets_from_front_matter` applies the real filter."""
    records = []
    for path in sorted(Path(generated_dir).glob("*.md")):
        head = path.read_text(encoding="utf-8").split(EOL + "---", 1)[0]
        if WINDOWS_FRONT_RE.search(head):
            data, _body = load_front_matter_and_body(path)
            records.append(data)
    return windows_targets_from_front_matter(records)


def store_blocks(text: str) -> list[tuple[int, int, dict[str, Any]]]:
    """(start, end, row) for every stored row. Block i IS row i, checked rather than assumed."""
    payload = yaml.safe_load(text)
    rows = payload.get("evidence") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise Refusal("store: no evidence list")
    spans = _blocks(text)
    if len(spans) != len(rows):
        raise Refusal(f"store: {len(spans)} blocks but {len(rows)} rows")
    out = []
    for (lo, hi), row in zip(spans, rows):
        first = text[lo:text.find(EOL, lo)]
        if first.split(":", 1)[1].strip().strip("'\"") != str(row.get("id") or ""):
            raise Refusal(f"store: block at offset {lo} is not row {row.get('id')!r}")
        out.append((lo, hi, row))
    return out


def withdraw_block(block: str) -> str:
    """The three-line edit. Each old line must occur exactly once in the block."""
    for old, new in EDIT:
        if block.count(old) != 1:
            raise Refusal(f"unexpected block shape: {old.strip()!r} occurs {block.count(old)} times")
        block = block.replace(old, new, 1)
    return block


def _refused(target: dict[str, Any], row: dict[str, Any]) -> bool:
    return bool(mw.identity_not_the_subject(target, str(row.get("report_title") or ""),
                                            str(row.get("matched_kb") or ""),
                                            str(row.get("matched_os_build") or "")))


def _windows_counts(rows: list[dict[str, Any]], targets: dict) -> dict[tuple[str, str, str], int]:
    return counted_evidence_counts([r for r in rows if str(r.get("product_id") or "") == WINDOWS_PRODUCT_ID],
                                   windows_targets=targets)


def plan(text: str, entries: list[dict[str, Any]], targets: dict) -> dict[str, Any]:
    """Decide every entry and prove the resulting text, without writing. Raises Refusal."""
    blocks = store_blocks(text)
    by_identity: dict[tuple[str, ...], list[int]] = {}
    for index, (_lo, _hi, row) in enumerate(blocks):
        by_identity.setdefault(identity(row), []).append(index)

    refusals: list[str] = []
    decided: list[dict[str, Any]] = []
    edits: dict[int, str] = {}
    pinned = {tuple(str(e[key]) for key in SELECTOR) for e in entries if e["role"] == "withdraw"}
    for entry in entries:
        ident = tuple(str(entry[key]) for key in SELECTOR)
        label = f"{ident[1]} {ident[2]} {ident[3]}"
        hits = by_identity.get(ident, [])
        if len(hits) != 1:
            refusals.append(f"{len(hits)} blocks match the five-field identity of {label}")
            continue
        index = hits[0]
        lo, hi, row = blocks[index]
        block = text[lo:hi]
        digest = sha(block)
        target = targets.get(patch_key(ident[0], ident[1], ident[2]))
        if target is None:
            refusals.append(f"no Windows record for {ident[1]} {ident[2]}")
            continue
        if (str(target.get("target_kb") or "") != entry["target_kb"]
                or str(target.get("target_os_build") or "") != entry["target_os_build"]):
            refusals.append(f"record target identity moved for {label}")
            continue
        refused = _refused(target, row)
        item = {"role": entry["role"], **dict(zip(SELECTOR, ident)), "block_sha256_before_run": digest,
                "counted_before_run": row.get("counted"), "authority_refuses": refused}
        if entry["role"] == "retain":
            if digest != entry["block_sha256_before"]:
                refusals.append(f"retained row changed: {label}")
            elif row.get("counted") is not True or refused:
                refusals.append(f"retained row is not counted or the authority refuses it: {label}")
            item["action"] = "kept"
        elif digest == entry["block_sha256_after"]:
            item["action"] = "already_withdrawn"
        elif digest != entry["block_sha256_before"]:
            refusals.append(f"block changed since the manifest was pinned: {label}")
            continue
        elif not refused:
            refusals.append(f"the authority no longer refuses {label}")
            continue
        else:
            try:
                new_block = withdraw_block(block)
            except Refusal as exc:
                refusals.append(f"{label}: {exc}")
                continue
            if sha(new_block) != entry["block_sha256_after"]:
                refusals.append(f"the edit does not produce the pinned block for {label}")
                continue
            edits[index] = new_block
            item["action"] = "withdraw"
        decided.append(item)

    # Sweep: every counted Windows row the authority refuses must be one the manifest names.
    swept = 0
    for _lo, _hi, row in blocks:
        if str(row.get("product_id") or "") != WINDOWS_PRODUCT_ID or not row_is_counted(row):
            continue
        target = targets.get(patch_key(row.get("product_id"), row.get("update_version"), row.get("target_build")))
        if target is None:
            continue
        swept += 1
        if _refused(target, row) and identity(row) not in pinned:
            refusals.append("the authority refuses a counted row the manifest does not name: "
                            + " ".join(identity(row)[1:4]))
    if refusals:
        raise Refusal("; ".join(refusals))

    pieces, cursor = [], 0
    for index in sorted(edits):
        lo, hi, _row = blocks[index]
        pieces += [text[cursor:lo], edits[index]]
        cursor = hi
    new_text = "".join(pieces) + text[cursor:]

    rows_before = [row for _lo, _hi, row in blocks]
    rows_after = [row for _lo, _hi, row in store_blocks(new_text)]
    if len(rows_after) != len(rows_before):
        raise Refusal("the edit changed the row count")
    for index, (old, new) in enumerate(zip(rows_before, rows_after)):
        expected = dict(old, **WITHDRAWN_FIELDS) if index in edits else old
        if new != expected:
            raise Refusal(f"the edit changed more than decided at row {index} ({old.get('id')})")

    before, after = _windows_counts(rows_before, targets), _windows_counts(rows_after, targets)
    touched = sorted({patch_key(*identity(blocks[i][2])[:3]) for i in edits})
    return {
        "new_text": new_text,
        "entries": decided,
        "withdrawn_now": len(edits),
        "counted_windows_rows_swept": swept,
        "windows_counted_population": [sum(before.values()), sum(after.values())],
        "per_patch": [{"update_version": k[1], "target_build": k[2],
                       "before": before.get(k, 0), "after": after.get(k, 0)} for k in touched],
    }


def run(store: Path, generated_dir: Path, manifest: Path, write: bool) -> dict[str, Any]:
    raw = Path(store).read_bytes()
    text = raw.decode("utf-8")
    result = plan(text, load_manifest(manifest), windows_targets(generated_dir))
    new_text = result.pop("new_text")
    result.update({
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exclusion_reason": REASON,
        "store_sha256_before": sha(raw),
        "store_sha256_after": sha(new_text),
        "authority_sha256": sha(AUTHORITY_FILE.read_bytes()),
        "manifest_sha256": sha(Path(manifest).read_bytes()),
        "written": False,
    })
    if write and result["withdrawn_now"]:
        Path(store).write_bytes(new_text.encode("utf-8"))
        result["written"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--generated-dir", type=Path, default=GENERATED)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--write", action="store_true", help="apply the withdrawal in place")
    ap.add_argument("--confirm-write", action="store_true", help="required together with --write")
    ap.add_argument("--audit", type=Path, help="also write the run's audit JSON here")
    ap.add_argument("--parent-commit", default="", help="commit the store was read at (audit only)")
    args = ap.parse_args(argv)
    if args.write != args.confirm_write:
        print("refusing: --write and --confirm-write must be given together")
        return 2
    try:
        result = run(args.store, args.generated_dir, args.manifest, args.write)
    except Refusal as exc:
        print("REFUSED, nothing written: " + str(exc))
        return 1
    for item in result["entries"]:
        print(f"  [{item['action']:<17}] {item['update_version']} {item['target_build']}  {item['source_url']}")
    print(f"counted Windows rows swept by the authority: {result['counted_windows_rows_swept']}")
    print(f"rows withdrawn by this run: {result['withdrawn_now']}")
    before, after = result["windows_counted_population"]
    print(f"Windows counted population: {before} -> {after}")
    for patch in result["per_patch"]:
        print(f"  {patch['update_version']} {patch['target_build']}: {patch['before']} -> {patch['after']}")
    if args.audit:
        audit = dict(result, parent_commit=args.parent_commit)
        args.audit.write_bytes((json.dumps(audit, indent=1, ensure_ascii=False) + EOL).encode("utf-8"))
    if result["written"]:
        print(f"WROTE {args.store}")
    elif args.write:
        print("nothing to write (idempotent)")
    else:
        print("dry run: pass --write --confirm-write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
