#!/usr/bin/env python3
"""Audited re-admission of stored Acrobat Reader rows that the role veto withdrew wrongly (AUX-110).

The Acrobat collector vetoes a report whose text says the record's version WORKS (#104,
`lib.target_outcome.target_is_contradicted`). On two stored Reader rows the veto misread the post:
"18.009.20044 I work ..." is the start of "I work in IT support", and "19.021.20047 All users were
working ok while on 19.012.20040" is the sentence about the OTHER build. Both rows were stored
`counted: false` with `exclusion_reason: version_named_but_working`. Nothing in the repository could
reverse that: the evidence-loss guard does not police re-acceptance, the withdrawal tools only go
true -> false, and the label-only recompute never writes `counted`.

This is the inverse of `withdraw_live_citation_rows.py`, with the same mechanism imported rather than
copied: five-field selection (product_id, update_version, target_build, id, source_url), the block
splitter and its row-for-block proof, pinned before/after block hashes, a field-by-field proof that
only `counted` and `exclusion_reason` moved, dry run by default, `--write --confirm-write`, all or
nothing, idempotent.

THE SELECTION IS HUMAN ADJUDICATION, NOT A PREDICATE. A row is re-admitted only when the manifest
(`audit/acrobat_reader_readmission.json`) names it and records two labels, both CORRECT ("the report
describes a concrete problem attributable to the exact named version"), from two different named
adjudicators who labelled a shuffled, label-free packet from stored text alone, with the packet and
brief hashes. UNSURE, INCORRECT, one label, or two labels from one adjudicator refuse. The shipped veto
still refuses both rows on their stored text; it is not changed here (no blanket contraction fix), so
the manifest is also the exemption list for any future check that replays the veto over stored rows.

SCOPE IS CLOSED.
  product        adobe-acrobat-reader only (no build contract: target_build is empty).
  from-reason    `version_named_but_working` only. Every other reason -- a rollback target, several
                 builds named with this one not blamed, another product or edition, a vendor
                 announcement, a duplicate -- refuses. A reason is added only when a manifest row
                 needs it, with its own adjudication.
  edit           two lines per block: `counted: false -> true`, `exclusion_reason: <reason> -> null`.
                 A block carrying `evidence_valid_for_current_patch` is an unexpected shape and refuses.

FAIL CLOSED. Any ambiguous or missing selector, a block whose hash moved, a stored reason other than
the pinned one, a record that is missing or not the pinned file, a held identity named as an entry, a
row that would not enter the authoritative counted population, a report already counted on the same
patch under another row (that would count one report twice), any row that would stop counting or
start counting besides the named ones, an evidence loss, or a store that differs from
`--expected-store-sha256` refuses the whole run before a byte is written. The write itself goes through
`lib.single_writer.guarded_write` with the fingerprint of the bytes read, so a store that changed
during the run refuses instead of being overwritten.

LATER AUDITED CHANGES. A re-admitted block may legitimately change afterwards through another
audited tool (AUX-110 corrects one row's theme through recompute_evidence_classification.py). The pins
are never rewritten: an entry lists `successors`, each naming the hash it starts from, the hash it
produced, the change and the tool that made it, chained from `block_sha256_after`. A successor only
ever satisfies the already-re-admitted state, never a row still to re-admit.

THE RECORDS follow from the lane's own scoped Reader writers only. `--regenerate` (with `--write
--confirm-write`, default tree only) runs, after the store step:
build_consensus_from_evidence.py --product-id adobe-acrobat-reader --reconcile-only, then
apply_consensus_to_records.py --product-id adobe-acrobat-reader --write-all --confirm-write.
Nothing ever runs unscoped. Generated records are never edited by hand.

OPERATOR SEQUENCE (AUX-110): (1) this tool --write --confirm-write; (2) the label correction,
recompute_evidence_classification.py --correction-manifest audit/acrobat_reader_label_correction.json
--write; (3) this tool --write --confirm-write --regenerate (the store step is then a no-op, and the
writers see both changes).

  python auxsays/scripts/readmit_adjudicated_rows.py                                    # dry run
  python auxsays/scripts/readmit_adjudicated_rows.py --write --confirm-write [--regenerate]
         [--expected-store-sha256 SHA] [--audit PATH --parent-commit SHA]

Exit: 0 dry run, written, or nothing left to do; 1 refused (nothing written); 2 usage error;
3 a scoped writer failed after the store step.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib import evidence_loss  # noqa: E402
from lib.patch_identity import is_build_aware, key_from, patch_key  # noqa: E402
from lib.report_counts import counted_evidence_rows  # noqa: E402
from lib.single_writer import StaleWrite, WriterBusy, guarded_write  # noqa: E402
from lib.source_segments import report_url_key  # noqa: E402
from patch_collectors.base import load_front_matter_and_body  # noqa: E402
from withdraw_acrobat_wrong_edition_rows import COUNTED_FALSE, COUNTED_TRUE, EOL, REASON_NULL  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
STORE = ROOT / "_data" / "consensus_evidence.yml"
GENERATED = ROOT / "updates" / "generated"
MANIFEST = SCRIPTS / "audit" / "acrobat_reader_readmission.json"

PRODUCT = "adobe-acrobat-reader"
SELECTOR = aux072.SELECTOR
FROM_REASONS = frozenset({"version_named_but_working"})
CORRECT = "CORRECT"
VALIDITY_FIELD = "evidence_valid_for_current_patch"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FRONT_RE = re.compile(r"^product_id:\s*['\"]?" + re.escape(PRODUCT) + r"['\"]?\s*$", re.M)
WRITERS = (
    ("build_consensus_from_evidence.py", "--product-id", PRODUCT, "--reconcile-only"),
    ("apply_consensus_to_records.py", "--product-id", PRODUCT, "--write-all", "--confirm-write"),
)

sha = aux072.sha
identity = aux072.identity


class Refusal(Exception):
    """The run cannot proceed safely. Nothing has been written."""


def _ident(entry: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(entry.get(key) or "") for key in SELECTOR)


def reason_line(reason: str) -> str:
    return EOL + "  exclusion_reason: " + reason + EOL


def readmit_block(block: str, reason: str) -> str:
    """The two-line edit. Each old line must occur exactly once in the block."""
    if (EOL + "  " + VALIDITY_FIELD + ":") in block:
        raise Refusal(f"unexpected block shape: a Reader row carrying {VALIDITY_FIELD}")
    for old, new in ((COUNTED_FALSE, COUNTED_TRUE), (reason_line(reason), REASON_NULL)):
        if block.count(old) != 1:
            raise Refusal(f"unexpected block shape: {old.strip()!r} occurs {block.count(old)} times")
        block = block.replace(old, new, 1)
    return block


def _two_correct_labels(entry: dict[str, Any]) -> bool:
    """Exactly two labels, both CORRECT, each with a reason, from two different named adjudicators,
    both on the same packet entry."""
    labels = entry.get("labels")
    if not isinstance(labels, list) or len(labels) != 2 or not all(isinstance(x, dict) for x in labels):
        return False
    by = [str(x.get("by") or "").strip() for x in labels]
    packet_ids = {str(x.get("packet_id") or "").strip() for x in labels}
    return (all(x.get("label") == CORRECT for x in labels)
            and all(str(x.get("reason") or "").strip() for x in labels)
            and all(by) and by[0] != by[1]
            and len(packet_ids) == 1 and "" not in packet_ids)


def _successors(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """The recorded later audited changes, refusing a chain that does not start at the after-pin."""
    chain = entry.get("successors") or []
    if not isinstance(chain, list):
        raise Refusal(f"manifest: successors is not a list for {entry.get('id')}")
    current = entry.get("block_sha256_after")
    for step in chain:
        frm, to = str(step.get("block_sha256_from") or ""), str(step.get("block_sha256_to") or "")
        if not (SHA256_RE.match(frm) and SHA256_RE.match(to)) or frm == to:
            raise Refusal(f"manifest: malformed successor hashes for {entry.get('id')}")
        if frm != current:
            raise Refusal(f"manifest: a successor does not continue the chain from the after-pin: {entry.get('id')}")
        if not isinstance(step.get("change"), dict) or not step["change"] \
                or not str(step.get("changed_by") or "").strip():
            raise Refusal(f"manifest: a successor does not name its change and the tool that made it: {entry.get('id')}")
        current = to
    return chain


def manifest_entries(doc: dict[str, Any]) -> list[dict[str, Any]]:  # noqa: PLR0912
    """The pinned entries, refusing a manifest that could select ambiguously or widen the scope."""
    if list(doc.get("selector") or []) != list(SELECTOR):
        raise Refusal("manifest: the selector is not the five-field identity")
    if list(doc.get("products") or []) != [PRODUCT]:
        raise Refusal("manifest: the product scope differs from the tool's (Acrobat Reader only)")
    if sorted(doc.get("readmit_from_reasons") or []) != sorted(FROM_REASONS):
        raise Refusal("manifest: the from-reasons differ from the tool's closed vocabulary")
    adjudication = doc.get("adjudication")
    if not isinstance(adjudication, dict) or not all(
            SHA256_RE.match(str(adjudication.get(key) or "")) for key in ("packet_sha256", "brief_sha256")) \
            or not str(adjudication.get("basis") or "").strip():
        raise Refusal("manifest: the adjudication does not pin its packet, its brief and its basis")
    held = {tuple(str(h.get(key) or "") for key in SELECTOR) for h in doc.get("held") or []}
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise Refusal("manifest: no entries")
    seen: set[tuple[str, ...]] = set()
    for entry in entries:
        ident = _ident(entry)
        if ident[0] != PRODUCT:
            raise Refusal(f"manifest: not an Acrobat Reader row: {ident}")
        if not all(ident[i] for i in (0, 1, 3, 4)) or ident[2] or is_build_aware(ident[0]):
            raise Refusal(f"manifest: an entry lacks part of the five-field identity: {ident}")
        if ident in seen:
            raise Refusal(f"manifest: identity listed twice: {ident}")
        seen.add(ident)
        if ident in held:
            raise Refusal(f"manifest: a held row is named as an entry: {ident[3]}")
        if entry.get("exclusion_reason_before") not in FROM_REASONS:
            raise Refusal(f"manifest: reason {entry.get('exclusion_reason_before')!r} is outside the closed "
                          f"from-vocabulary: {ident[3]}")
        if not all(SHA256_RE.match(str(entry.get(key) or "")) for key in ("block_sha256_before", "block_sha256_after")):
            raise Refusal(f"manifest: missing or malformed block hash for {ident[3]}")
        if not str(entry.get("record_file") or "").endswith(".md"):
            raise Refusal(f"manifest: no pinned record for {ident[3]}")
        if not _two_correct_labels(entry):
            raise Refusal(f"manifest: row lacks two CORRECT labels with reasons from two different named "
                          f"adjudicators on one packet entry: {ident[3]}")
        _successors(entry)
    return entries


def patch_records(generated_dir: Path) -> dict[tuple[str, str, str], list[str]]:
    """Canonical patch key -> [file name] for every Acrobat Reader update record."""
    out: dict[tuple[str, str, str], list[str]] = {}
    for path in sorted(Path(generated_dir).glob("*.md")):
        head = path.read_text(encoding="utf-8").split(EOL + "---", 1)[0]
        if not FRONT_RE.search(head):
            continue
        data, _body = load_front_matter_and_body(path)
        if isinstance(data, dict) and data.get("update_entry") is True:
            out.setdefault(key_from(data), []).append(path.name)
    return out


def _population(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    """The authoritative counted population of Acrobat Reader rows, per patch."""
    return counted_evidence_rows([r for r in rows if str(r.get("product_id") or "") == PRODUCT],
                                 windows_targets={})


def plan(text: str, entries: list[dict[str, Any]], records: dict) -> dict[str, Any]:  # noqa: PLR0912, PLR0915
    """Decide every entry and prove the resulting text, without writing. Raises Refusal."""
    blocks = aux072.store_blocks(text)
    by_identity: dict[tuple[str, ...], list[int]] = {}
    for index, (_lo, _hi, row) in enumerate(blocks):
        by_identity.setdefault(identity(row), []).append(index)

    refusals: list[str] = []
    decided: list[dict[str, Any]] = []
    edits: dict[int, str] = {}
    for entry in entries:
        ident = _ident(entry)
        label = f"{ident[1]} {ident[3]}"
        hits = by_identity.get(ident, [])
        if len(hits) != 1:
            refusals.append(f"{len(hits)} blocks match the five-field identity of {label}")
            continue
        index = hits[0]
        lo, hi, row = blocks[index]
        block = text[lo:hi]
        digest = sha(block)
        found = records.get(patch_key(ident[0], ident[1], ident[2]), [])
        if len(found) != 1 or found[0] != Path(entry["record_file"]).name:
            refusals.append(f"the record for {ident[1]} is {found}, not the pinned {entry['record_file']}")
            continue
        item = {**dict(zip(SELECTOR, ident)), "block_sha256_before_run": digest,
                "counted_before_run": row.get("counted"), "exclusion_reason_before": entry["exclusion_reason_before"],
                "labels": [{k: label_.get(k) for k in ("by", "packet_id", "label")} for label_ in entry["labels"]]}
        accepted = [entry["block_sha256_after"]] + [s["block_sha256_to"] for s in _successors(entry)]
        if digest in accepted:
            if row.get("counted") is not True or row.get("exclusion_reason") is not None:
                refusals.append(f"pinned as re-admitted but not counted: {label}")
                continue
            item["action"] = "already_readmitted"
            item["via_successor"] = digest != entry["block_sha256_after"]
        elif digest != entry["block_sha256_before"]:
            refusals.append(f"block changed since the manifest was pinned: {label}")
            continue
        elif row.get("counted") is not False or row.get("exclusion_reason") != entry["exclusion_reason_before"]:
            refusals.append(f"stored state is not the pinned withdrawal ({row.get('counted')!r}, "
                            f"{row.get('exclusion_reason')!r}): {label}")
            continue
        else:
            try:
                new_block = readmit_block(block, entry["exclusion_reason_before"])
            except Refusal as exc:
                refusals.append(f"{label}: {exc}")
                continue
            if sha(new_block) != entry["block_sha256_after"]:
                refusals.append(f"the edit does not produce the pinned block for {label}")
                continue
            edits[index] = new_block
            item["action"] = "readmit"
        decided.append(item)
    if refusals:
        raise Refusal("; ".join(refusals))

    pieces, cursor = [], 0
    for index in sorted(edits):
        lo, hi, _row = blocks[index]
        pieces += [text[cursor:lo], edits[index]]
        cursor = hi
    new_text = "".join(pieces) + text[cursor:]

    rows_before = [row for _lo, _hi, row in blocks]
    rows_after = [row for _lo, _hi, row in aux072.store_blocks(new_text)]
    if len(rows_after) != len(rows_before):
        raise Refusal("the edit changed the row count")
    for index, (old, new) in enumerate(zip(rows_before, rows_after)):
        expected = dict(old, counted=True, exclusion_reason=None) if index in edits else old
        if new != expected:
            raise Refusal(f"the edit changed more than decided at row {index} ({old.get('id')})")

    # Exactly the named rows start counting, none stops, and each enters the authoritative population.
    readmitted = {identity(blocks[i][2]) for i in edits}
    counted_before = {identity(r) for r in rows_before if r.get("counted") is True}
    counted_after = {identity(r) for r in rows_after if r.get("counted") is True}
    if counted_before - counted_after:
        raise Refusal("a row would stop counting")
    if counted_after - counted_before != readmitted:
        raise Refusal("a row other than the named ones would start counting")
    before, after = _population(rows_before), _population(rows_after)
    members = {identity(r) for items in after.values() for r in items}
    for ident in sorted(readmitted):
        if ident not in members:
            raise Refusal(f"a re-admitted row would not enter the counted population: {ident[1]} {ident[3]}")
        # One report counts once per patch: a re-admitted row must not repeat a report already counted.
        key = patch_key(*ident[:3])
        url = report_url_key(ident[4])
        twins = [r for r in after.get(key, []) if identity(r) != ident and report_url_key(str(r.get("source_url") or "")) == url]
        if twins:
            raise Refusal(f"the report is already counted on {ident[1]} by {twins[0].get('id')}")
    losses = evidence_loss.losses_between(text, new_text) if edits else []
    if losses:
        raise Refusal("the edit would lose evidence: " + "; ".join(str(x) for x in losses))

    touched = sorted({patch_key(*_ident(e)[:3]) for e in entries})
    pinned = {_ident(e) for e in entries}
    reports = {report_url_key(e["source_url"]) for e in entries}
    siblings = []
    for index, (_lo, _hi, row) in enumerate(blocks):
        if identity(row) in pinned or report_url_key(str(row.get("source_url") or "")) not in reports:
            continue
        after_row = rows_after[index]
        siblings.append({**dict(zip(SELECTOR, identity(row))), "counted": after_row.get("counted"),
                         "exclusion_reason": after_row.get("exclusion_reason"),
                         "unchanged": index not in edits and after_row == row})
    return {
        "new_text": new_text,
        "entries": decided,
        "readmitted_now": len(edits),
        "counted_population": [sum(len(v) for v in before.values()), sum(len(v) for v in after.values())],
        "per_patch": [{"product_id": k[0], "update_version": k[1], "target_build": k[2],
                       "before": len(before.get(k, [])), "after": len(after.get(k, []))} for k in touched],
        "newly_counted_rows": sorted(" ".join(k[:4]) for k in readmitted),
        "evidence_losses": [],
        "same_report_rows_on_other_identities": siblings,
    }


def run(store: Path, generated_dir: Path, manifest: Path, write: bool,
        expected_store_sha256: str = "") -> dict[str, Any]:
    raw = Path(store).read_bytes()
    digest = sha(raw)
    if expected_store_sha256 and digest != expected_store_sha256:
        raise Refusal(f"the store is not the expected one (expected {expected_store_sha256[:12]}, "
                      f"read {digest[:12]}): re-pin against the current main")
    text = raw.decode("utf-8")
    doc = json.loads(Path(manifest).read_text(encoding="utf-8"))
    result = plan(text, manifest_entries(doc), patch_records(generated_dir))
    new_text = result.pop("new_text")
    result.update({
        "product_scope": [PRODUCT],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "readmit_from_reasons": sorted(FROM_REASONS),
        "adjudication": {k: doc["adjudication"].get(k) for k in ("packet_sha256", "brief_sha256", "basis")},
        "store_sha256_before": digest,
        "store_sha256_after": sha(new_text),
        "manifest_sha256": sha(Path(manifest).read_bytes()),
        "written": False,
    })
    if write and result["readmitted_now"]:
        try:
            guarded_write(store, new_text.encode("utf-8"), expected=digest)
        except (StaleWrite, WriterBusy) as exc:
            raise Refusal(f"the store changed or is being written: {exc}") from exc
        result["written"] = True
    return result


def regenerate(writers: tuple = WRITERS) -> list[dict[str, Any]]:
    """The lane's scoped Reader writers, as subprocesses, in order. Stops at the first failure.
    apply_consensus_to_records' JSON report goes to a discarded temporary file (--output)."""
    done = []
    with tempfile.TemporaryDirectory(prefix="aux110-") as tmp:
        for script, *argv in writers:
            extra = ["--output", str(Path(tmp) / "apply.json")] if script.startswith("apply_") else []
            proc = subprocess.run([sys.executable, str(SCRIPTS / script), *argv, *extra], cwd=str(SCRIPTS),
                                  capture_output=True, text=True, encoding="utf-8")
            lines = [line for line in (proc.stdout + proc.stderr).splitlines()
                     if line.strip() and not line.startswith("Output written to:")]
            done.append({"command": " ".join([script, *argv]), "returncode": proc.returncode,
                         "output": lines[-40:]})
            if proc.returncode != 0:
                break
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--generated-dir", type=Path, default=GENERATED)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--write", action="store_true", help="apply the re-admission in place")
    ap.add_argument("--confirm-write", action="store_true", help="required together with --write")
    ap.add_argument("--regenerate", action="store_true",
                    help="after the store step, run the scoped Acrobat Reader writers (default tree only)")
    ap.add_argument("--expected-store-sha256", default="",
                    help="refuse unless the store read is exactly this one (re-pin at merge time)")
    ap.add_argument("--audit", type=Path, help="also write the run's audit JSON here")
    ap.add_argument("--parent-commit", default="", help="commit the store was read at (audit only)")
    args = ap.parse_args(argv)
    if args.write != args.confirm_write:
        print("refusing: --write and --confirm-write must be given together")
        return 2
    if args.regenerate and not args.write:
        print("refusing: --regenerate needs --write --confirm-write")
        return 2
    if args.regenerate and (Path(args.store).resolve() != STORE.resolve()
                            or Path(args.generated_dir).resolve() != GENERATED.resolve()):
        print("refusing: --regenerate runs the writers over the default tree, so --store and "
              "--generated-dir must be the defaults")
        return 2
    try:
        result = run(args.store, args.generated_dir, args.manifest, args.write, args.expected_store_sha256)
    except Refusal as exc:
        print("REFUSED, nothing written: " + str(exc))
        return 1
    for item in result["entries"]:
        print(f"  [{item['action']:<18}] {item['product_id']} {item['update_version']}  "
              f"{item['exclusion_reason_before']} -> counted  {item['source_url']}")
    print(f"rows re-admitted by this run: {result['readmitted_now']}")
    before, after = result["counted_population"]
    print(f"{PRODUCT} counted population: {before} -> {after}")
    for patch in result["per_patch"]:
        print(f"  {patch['product_id']} {patch['update_version']}: {patch['before']} -> {patch['after']}")
    siblings = result["same_report_rows_on_other_identities"]
    print(f"same-report rows on other identities left untouched: {len(siblings)} "
          f"(still counted: {sum(1 for s in siblings if s['counted'] is True)})")
    status = 0
    if args.regenerate:
        result["writers"] = regenerate()
        for step in result["writers"]:
            print(f"writer rc={step['returncode']}: {step['command']}")
        if any(step["returncode"] != 0 for step in result["writers"]):
            print("a scoped writer failed after the store step; see the audit")
            status = 3
    if args.audit:
        audit = dict(result, parent_commit=args.parent_commit)
        args.audit.write_bytes((json.dumps(audit, indent=1, ensure_ascii=False) + EOL).encode("utf-8"))
    if result["written"]:
        print(f"WROTE {args.store}")
    elif args.write:
        print("nothing to write (idempotent)")
    else:
        print("dry run: pass --write --confirm-write to apply")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
