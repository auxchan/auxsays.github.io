#!/usr/bin/env python3
"""Audited withdrawal of Windows rows confirmed off-topic and of duplicate Learn captures (AUX-079).

Two kinds of stored Windows rows still count against a patch they should not:

  Track B  ten rows that two independent adjudicators, reading the retained text, both judged to be
           about something other than the credited patch: another update or package is the subject,
           the patch is only the state the reporter was updating FROM, or the problem began before
           the patch shipped. No deterministic rule refuses them today, so the selection is the
           adjudication itself, pinned per row in the manifest with both labels and the reason.
  Track C  four later captures of a Microsoft Q&A question already counted on the SAME patch under an
           earlier title slug: one report counted twice. The duplicate is DERIVED here, not listed:
           the kept row and the withdrawn row must share the patch and the question id, both must be
           the question itself (no answer anchor), the kept row must be the earlier capture and must
           still count, and after the withdrawal no patch may count one Learn report twice.

An audited withdrawal is `counted: false` with a non-empty `exclusion_reason` and the ROW KEPT, never a
deletion (lib/evidence_loss.py). The reasons come from the existing vocabulary, one per track:
`identity_not_the_subject` (Track B: the credited identity is not what the report is about, the
reason AUX-072 withdrew with) and `duplicate_existing_evidence` (Track C: the report was already
held, the name the append guard's telemetry and the capture promoters already use for it). The why of
each Track B row stays in the manifest beside it.

THE MECHANISM IS AUX-072's, imported rather than copied: five-field selection (product_id,
update_version, target_build, id, source_url), the block splitter and its row-for-block proof, the
record-target index, the three-line block edit, pinned before/after block hashes, the field-by-field
proof that nothing but the three fields moved, dry run by default, `--write --confirm-write`, all or
nothing, idempotent. Any ambiguous or missing selector, a block whose hash moved, a record whose
target identity moved, a kept row that changed or stopped counting, a Track C pair that no longer
derives, a counted duplicate the manifest does not name, or an edit that changes anything but the
three fields refuses the whole run before a byte is written.

RE-HOMING. The run only edits the selected blocks, so no other stored row can start counting: every
sibling row of the same question (stored on another patch, typically `cross_patch_duplicate`) is left
byte-identical and reported in the audit, including any whose question now counts on no patch. A
stranded sibling is a finding, never re-attributed here.

THE RECORDS follow from the existing scoped writers only. `--regenerate` (with `--write
--confirm-write`, default tree only) runs exactly the lane's two commands after the store step:
build_consensus_from_evidence.py --product-id microsoft-windows-11 --reconcile-only, then
apply_consensus_to_records.py --product-id microsoft-windows-11 --write-all --confirm-write (its JSON
report goes to a discarded temporary file). So one command reproduces the data change on a newer main:

  python auxsays/scripts/withdraw_windows_confirmed_and_duplicate_rows.py                    # dry run
  python auxsays/scripts/withdraw_windows_confirmed_and_duplicate_rows.py --write --confirm-write --regenerate
         ... --audit PATH --parent-commit SHA                                  # also write the audit

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
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib.patch_identity import patch_key  # noqa: E402
from lib.report_counts import counted_evidence_counts, counted_evidence_rows  # noqa: E402
from lib.source_segments import learn_qna_question_id  # noqa: E402
from patch_collectors.base import WINDOWS_PRODUCT_ID  # noqa: E402
from withdraw_acrobat_wrong_edition_rows import COUNTED_FALSE, COUNTED_TRUE, EOL, REASON_NULL  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
STORE = ROOT / "_data" / "consensus_evidence.yml"
GENERATED = ROOT / "updates" / "generated"
MANIFEST = SCRIPTS / "audit" / "windows_confirmed_and_duplicate_withdrawal.json"

SELECTOR = aux072.SELECTOR
TRACK_REASONS = {"B": aux072.REASON, "C": "duplicate_existing_evidence"}
SUB_LABELS = ("B-source", "B-onset", "B-cause")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LEARN_HOST = "learn.microsoft.com"
WRITERS = (
    ("build_consensus_from_evidence.py", "--product-id", WINDOWS_PRODUCT_ID, "--reconcile-only"),
    ("apply_consensus_to_records.py", "--product-id", WINDOWS_PRODUCT_ID, "--write-all", "--confirm-write"),
)


class Refusal(Exception):
    """The run cannot proceed safely. Nothing has been written."""


sha = aux072.sha
identity = aux072.identity


def edit_for(reason: str) -> tuple[tuple[str, str], ...]:
    """The three-line edit, the same three transitions AUX-072 makes, with the track's reason."""
    return ((COUNTED_TRUE, COUNTED_FALSE),
            (REASON_NULL, EOL + "  exclusion_reason: " + reason + EOL),
            (aux072.VALID_TRUE, aux072.VALID_FALSE))


def withdrawn_fields(reason: str) -> dict[str, Any]:
    return {"counted": False, "exclusion_reason": reason, "evidence_valid_for_current_patch": False}


def withdraw_block(block: str, reason: str) -> str:
    """Each old line must occur exactly once in the block."""
    for old, new in edit_for(reason):
        if block.count(old) != 1:
            raise Refusal(f"unexpected block shape: {old.strip()!r} occurs {block.count(old)} times")
        block = block.replace(old, new, 1)
    return block


def learn_report(url: str) -> tuple[str, str] | None:
    """(question id, segment) for a Microsoft Q&A URL, None for any other host or an unparsed URL.
    The segment is the URL fragment (an `#answer-<id>` anchor) or '' for the question itself."""
    parts = urlsplit(str(url or "").strip())
    if parts.hostname != LEARN_HOST:
        return None
    qid = learn_qna_question_id(url)
    return (qid, parts.fragment.lower()) if qid else None


def _ident(entry: dict[str, Any], prefix: str = "") -> tuple[str, ...]:
    source = entry.get(prefix) if prefix else entry
    return tuple(str((source or {}).get(key) or "") for key in SELECTOR)


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return manifest_entries(json.loads(Path(path).read_text(encoding="utf-8")))


def manifest_entries(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """The pinned entries, refusing a manifest that could select ambiguously or relabel a track."""
    if list(doc.get("selector") or []) != list(SELECTOR):
        raise Refusal("manifest: the selector is not the five-field identity")
    if doc.get("exclusion_reasons") != TRACK_REASONS:
        raise Refusal("manifest: the per-track exclusion reasons differ from the tool's vocabulary")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise Refusal("manifest: no entries")
    seen: set[tuple[str, ...]] = set()
    retained_c: set[tuple[str, ...]] = set()
    for entry in entries:
        ident = _ident(entry)
        if not all(ident):
            raise Refusal(f"manifest: an entry lacks part of the five-field identity: {ident}")
        if ident[0] != WINDOWS_PRODUCT_ID:
            raise Refusal(f"manifest: not a Windows row: {ident}")
        if ident in seen:
            raise Refusal(f"manifest: identity listed twice: {ident}")
        seen.add(ident)
        role, track = entry.get("role"), entry.get("track")
        if role not in ("withdraw", "retain") or track not in TRACK_REASONS:
            raise Refusal(f"manifest: unknown role or track {role!r}/{track!r} for {ident[3]}")
        hashes = ["block_sha256_before"] + (["block_sha256_after"] if role == "withdraw" else [])
        if not all(SHA256_RE.match(str(entry.get(key) or "")) for key in hashes):
            raise Refusal(f"manifest: missing or malformed block hash for {ident[3]}")
        if not entry.get("target_kb") or not entry.get("target_os_build"):
            raise Refusal(f"manifest: no pinned target identity for {ident[3]}")
        if role == "retain":
            if track != "C":
                raise Refusal(f"manifest: only Track C pins a kept row: {ident[3]}")
            retained_c.add(ident)
        elif track == "B":
            adj = entry.get("adjudication") or {}
            labels = (adj.get("auditor_label_final"), adj.get("verifier_label"), adj.get("final_label"))
            if labels != ("B", "B", "B") or adj.get("sub_label") not in SUB_LABELS \
                    or not str(adj.get("rationale") or "").strip():
                raise Refusal(f"manifest: Track B row lacks two agreeing B labels and a reason: {ident[3]}")
    for entry in entries:
        if entry["role"] == "withdraw" and entry["track"] == "C" and _ident(entry, "duplicate_of") not in retained_c:
            raise Refusal(f"manifest: Track C row names no pinned kept row: {entry['id']}")
    return entries


def windows_targets(generated_dir: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    return aux072.windows_targets(generated_dir)


def _duplicate_refusal(row: dict[str, Any], kept: dict[str, Any]) -> str:
    """'' when `row` is a later capture of the report `kept` already counts on the same patch."""
    if identity(row)[:3] != identity(kept)[:3]:
        return "the kept row is on another patch"
    mine, theirs = learn_report(row.get("source_url")), learn_report(kept.get("source_url"))
    if mine is None or theirs is None or mine[0] != theirs[0]:
        return "the kept row is not the same Microsoft Q&A question"
    if mine[1] or theirs[1]:
        return "an answer segment is not the question's opening report"
    if str(row.get("source_url") or "").strip().lower() == str(kept.get("source_url") or "").strip().lower():
        return "the two rows have the same URL"
    if not str(kept.get("captured_at") or "") < str(row.get("captured_at") or ""):
        return "the kept row is not the earlier capture"
    if kept.get("counted") is not True:
        return "the kept row does not count"
    return ""


def _counted_windows(rows: list[dict[str, Any]], targets: dict) -> dict[tuple, list[dict[str, Any]]]:
    """The authoritative counted population of Windows, grouped by patch (Windows gate included)."""
    return counted_evidence_rows([r for r in rows if str(r.get("product_id") or "") == WINDOWS_PRODUCT_ID],
                                 windows_targets=targets)


def _counted_learn_duplicates(rows: list[dict[str, Any]], targets: dict) -> list[str]:
    """Patches that COUNT one Learn report more than once, under the authoritative predicate."""
    groups: dict[tuple, int] = {}
    for key, members in _counted_windows(rows, targets).items():
        for row in members:
            report = learn_report(row.get("source_url"))
            if report is not None:
                groups[(key, report)] = groups.get((key, report), 0) + 1
    return [f"{k[0][1]} {k[0][2]} question {k[1][0]}{('#' + k[1][1]) if k[1][1] else ''} x{n}"
            for k, n in sorted(groups.items()) if n > 1]


def _windows_counts(rows: list[dict[str, Any]], targets: dict) -> dict[tuple[str, str, str], int]:
    return counted_evidence_counts([r for r in rows if str(r.get("product_id") or "") == WINDOWS_PRODUCT_ID],
                                   windows_targets=targets)


def plan(text: str, entries: list[dict[str, Any]], targets: dict) -> dict[str, Any]:  # noqa: PLR0912, PLR0915
    """Decide every entry and prove the resulting text, without writing. Raises Refusal."""
    blocks = aux072.store_blocks(text)
    by_identity: dict[tuple[str, ...], list[int]] = {}
    for index, (_lo, _hi, row) in enumerate(blocks):
        by_identity.setdefault(identity(row), []).append(index)

    refusals: list[str] = []
    decided: list[dict[str, Any]] = []
    edits: dict[int, tuple[str, str]] = {}
    located: dict[tuple[str, ...], dict[str, Any]] = {}
    for entry in entries:
        ident = _ident(entry)
        label = f"{entry['track']} {ident[1]} {ident[2]} {ident[3]}"
        hits = by_identity.get(ident, [])
        if len(hits) != 1:
            refusals.append(f"{len(hits)} blocks match the five-field identity of {label}")
            continue
        index = hits[0]
        lo, hi, row = blocks[index]
        located[ident] = row
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
        reason = TRACK_REASONS[entry["track"]]
        item = {"role": entry["role"], "track": entry["track"], **dict(zip(SELECTOR, ident)),
                "block_sha256_before_run": digest, "counted_before_run": row.get("counted")}
        if entry["role"] == "retain":
            if digest != entry["block_sha256_before"]:
                refusals.append(f"kept row changed: {label}")
            elif row.get("counted") is not True:
                refusals.append(f"kept row no longer counts: {label}")
            item["action"] = "kept"
        elif digest == entry["block_sha256_after"]:
            item["action"] = "already_withdrawn"
        elif digest != entry["block_sha256_before"]:
            refusals.append(f"block changed since the manifest was pinned: {label}")
            continue
        else:
            try:
                new_block = withdraw_block(block, reason)
            except Refusal as exc:
                refusals.append(f"{label}: {exc}")
                continue
            if sha(new_block) != entry["block_sha256_after"]:
                refusals.append(f"the edit does not produce the pinned block for {label}")
                continue
            edits[index] = (new_block, reason)
            item["action"] = "withdraw"
            item["exclusion_reason"] = reason
        decided.append(item)

    # Track C is derived, not listed: re-prove each pair against the rows as stored now.
    for entry in entries:
        if entry["role"] != "withdraw" or entry["track"] != "C":
            continue
        row, kept = located.get(_ident(entry)), located.get(_ident(entry, "duplicate_of"))
        if row is None or kept is None:
            continue  # already refused above
        why = _duplicate_refusal(row, kept)
        if why:
            refusals.append(f"C {entry['update_version']} {entry['target_build']} {entry['id']}: {why}")
    if refusals:
        raise Refusal("; ".join(refusals))

    pieces, cursor = [], 0
    for index in sorted(edits):
        lo, hi, _row = blocks[index]
        pieces += [text[cursor:lo], edits[index][0]]
        cursor = hi
    new_text = "".join(pieces) + text[cursor:]

    rows_before = [row for _lo, _hi, row in blocks]
    rows_after = [row for _lo, _hi, row in aux072.store_blocks(new_text)]
    if len(rows_after) != len(rows_before):
        raise Refusal("the edit changed the row count")
    for index, (old, new) in enumerate(zip(rows_before, rows_after)):
        expected = dict(old, **withdrawn_fields(edits[index][1])) if index in edits else old
        if new != expected:
            raise Refusal(f"the edit changed more than decided at row {index} ({old.get('id')})")

    # Sweep: after this run no patch may count one Learn report twice. A duplicate the manifest does
    # not name is a new candidate that needs its own audit, so the run refuses instead of widening.
    leftover = _counted_learn_duplicates(rows_after, targets)
    if leftover:
        raise Refusal("a patch still counts one Learn report more than once: " + "; ".join(leftover))

    before, after = _windows_counts(rows_before, targets), _windows_counts(rows_after, targets)
    counted_before = {identity(r) for r in rows_before if r.get("counted") is True}
    counted_after = {identity(r) for r in rows_after if r.get("counted") is True}
    newly_counted = sorted(" ".join(k[1:4]) for k in counted_after - counted_before)
    if newly_counted:
        raise Refusal("a row would start counting: " + "; ".join(newly_counted))

    withdrawn_reports = {}
    for entry in entries:
        if entry["role"] == "withdraw":
            report = learn_report(entry["source_url"])
            if report is not None:
                withdrawn_reports.setdefault(report[0], []).append(_ident(entry))
    counted_reports_after = {report[0] for members in _counted_windows(rows_after, targets).values()
                             for report in (learn_report(r.get("source_url")) for r in members) if report}
    pinned = {_ident(e) for e in entries}
    siblings = []
    for index, (lo, hi, row) in enumerate(blocks):
        report = learn_report(row.get("source_url"))
        if (str(row.get("product_id") or "") != WINDOWS_PRODUCT_ID or report is None
                or report[0] not in withdrawn_reports or identity(row) in pinned):
            continue
        after_row = rows_after[index]
        siblings.append({
            **dict(zip(SELECTOR[1:3], identity(row)[1:3])), "id": row.get("id"), "question_id": report[0],
            "counted": after_row.get("counted"), "exclusion_reason": after_row.get("exclusion_reason"),
            "unchanged": index not in edits and after_row == row,
            "question_counted_on_any_patch_after": report[0] in counted_reports_after,
        })
    stranded = [s for s in siblings if s["exclusion_reason"] == "cross_patch_duplicate"
                and not s["question_counted_on_any_patch_after"]]
    touched = sorted({patch_key(*identity(blocks[i][2])[:3]) for i in edits}
                     | {patch_key(*_ident(e)[:3]) for e in entries if e["role"] == "withdraw"})
    return {
        "new_text": new_text,
        "entries": decided,
        "withdrawn_now": len(edits),
        "windows_counted_population": [sum(before.values()), sum(after.values())],
        "per_patch": [{"update_version": k[1], "target_build": k[2],
                       "before": before.get(k, 0), "after": after.get(k, 0)} for k in touched],
        "counted_learn_duplicates_after": leftover,
        "newly_counted_rows": newly_counted,
        "same_question_siblings": siblings,
        "stranded_cross_patch_duplicates": stranded,
    }


def run(store: Path, generated_dir: Path, manifest: Path, write: bool) -> dict[str, Any]:
    raw = Path(store).read_bytes()
    text = raw.decode("utf-8")
    result = plan(text, load_manifest(manifest), windows_targets(generated_dir))
    new_text = result.pop("new_text")
    result.update({
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exclusion_reasons": TRACK_REASONS,
        "store_sha256_before": sha(raw),
        "store_sha256_after": sha(new_text),
        "manifest_sha256": sha(Path(manifest).read_bytes()),
        "written": False,
    })
    if write and result["withdrawn_now"]:
        Path(store).write_bytes(new_text.encode("utf-8"))
        result["written"] = True
    return result


def regenerate() -> list[dict[str, Any]]:
    """The lane's two scoped writers, as subprocesses, in order. Stops at the first failure.

    apply_consensus_to_records prints its whole JSON report to stdout unless given --output, so the
    report goes to a discarded temporary file; the flag changes where the report goes, nothing else."""
    done = []
    with tempfile.TemporaryDirectory(prefix="aux079-") as tmp:
        for script, *argv in WRITERS:
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
    ap.add_argument("--write", action="store_true", help="apply the withdrawal in place")
    ap.add_argument("--confirm-write", action="store_true", help="required together with --write")
    ap.add_argument("--regenerate", action="store_true",
                    help="after the store step, run the two scoped Windows writers (default tree only)")
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
        result = run(args.store, args.generated_dir, args.manifest, args.write)
    except Refusal as exc:
        print("REFUSED, nothing written: " + str(exc))
        return 1
    for item in result["entries"]:
        print(f"  [{item['action']:<17}] {item['track']} {item['update_version']} {item['target_build']}  "
              f"{item['source_url']}")
    print(f"rows withdrawn by this run: {result['withdrawn_now']}")
    before, after = result["windows_counted_population"]
    print(f"Windows counted population: {before} -> {after}")
    for patch in result["per_patch"]:
        print(f"  {patch['update_version']} {patch['target_build']}: {patch['before']} -> {patch['after']}")
    print(f"same-question rows on other patches left untouched: {len(result['same_question_siblings'])} "
          f"(stranded cross_patch_duplicate: {len(result['stranded_cross_patch_duplicates'])})")
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
