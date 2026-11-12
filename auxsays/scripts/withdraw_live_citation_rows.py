#!/usr/bin/env python3
"""Audited withdrawal of live-page citations credited to the wrong update (AUX-088) and of reports posted twice (AUX-098).

A citation audit of the six live-consensus pages (Windows 11 25H2 26200.7462, .7623, .7840; OBS Studio
32.1.1, 32.1.2, 32.2.2) flagged stored rows that count against an update they are not about. A second
reviewer then labelled the flagged rows and a set of controls BLIND, without seeing the first labels.
A row is withdrawn here only when BOTH said INCORRECT, with the concrete reason in the manifest beside
it: another product, version or KB is the subject; the author withdrew the claim (their own fix, a
setting, a driver, a damaged install); the credited version is the one that WORKS or the one the
author went back to; the post is not an issue report; or it is the same author's cross-post of a
report the same page already counts. Every disagreement stays counted, and so does every row that
reports a problem which began earlier but is experienced on the credited version. No acceptance rule
changes, so the selection is the adjudication itself, pinned per row.

An audited withdrawal is `counted: false` with a non-empty `exclusion_reason` and the ROW KEPT, never a
deletion (lib/evidence_loss.py). Each row takes the reason its two reviews support, and the run accepts
only a closed set of names the store already uses: `identity_not_the_subject` (AUX-072),
`duplicate_existing_evidence` (AUX-079 and the append guard), `version_named_but_working`,
`version_is_rollback_target` (OBS's own role vocabulary) and `not_a_real_issue_report`. None of them is
a reason any resolver or tier can promote back into view.

THE MECHANISM IS AUX-072's AND AUX-079's, imported rather than copied: five-field selection
(product_id, update_version, target_build, id, source_url), the block splitter and its row-for-block
proof, pinned before/after block hashes, the field-by-field proof that nothing but the withdrawal
fields moved, dry run by default, `--write --confirm-write`, all or nothing, idempotent. Scoped to
the two products:

  microsoft-windows-11  build-aware: target_build is part of the identity, the record's CURRENT
                        target KB and OS build must equal the pinned ones, and the edit is AUX-079's
                        three lines (counted, exclusion_reason, evidence_valid_for_current_patch).
  obs-studio            no build contract: target_build is empty, and the edit is the first two of
                        those lines. OBS rows carry no evidence_valid_for_current_patch field, so a
                        withdrawal adds none; a block that carries one is an unexpected shape and
                        refuses.

A same-page duplicate names the row it duplicates (`duplicate_of`, pinned with role `retain`): the
kept row must be on the same patch, still count, be the earlier capture of another report URL, and
stay byte-identical. Any ambiguous or missing selector, a block whose hash moved, a record that is
missing, duplicated or whose identity moved, a kept row that changed or stopped counting, a reason
outside the closed set, a row without two INCORRECT labels, or an edit that changes anything but the
withdrawal fields refuses the whole run before a byte is written.

RE-HOMING. Only the selected blocks are edited, so no other stored row can start counting: a row of
the same report stored on another identity (the same thread credited to two versions) is left
byte-identical and reported in the audit with its counted state. Whether that row is right is its
own question, never answered here.

THE RECORDS follow from the existing scoped writers only. `--regenerate` (with `--write
--confirm-write`, default tree only) runs, after the store step, the reconcile scoped to the two
products and then each product's own promotion, exactly the lane's commands:
build_consensus_from_evidence.py --product-id microsoft-windows-11 --product-id obs-studio
--reconcile-only, apply_consensus_to_records.py --product-id microsoft-windows-11 --write-all
--confirm-write, and the same for obs-studio. Live eligibility is not decided here: the writers ask
the shipped authority (lib/live_eligibility.py), and a page that no longer certifies is written back.

  python auxsays/scripts/withdraw_live_citation_rows.py                                    # dry run
  python auxsays/scripts/withdraw_live_citation_rows.py --write --confirm-write --regenerate
         ... --audit PATH --parent-commit SHA                                    # also write the audit

LATER AUDITED CHANGES. A pinned row may legitimately move after its pin was taken: AUX-090 filled
the day each OBS report was posted into kept rows this manifest pins. The pins are never rewritten to
follow. Instead a versioned supplemental baseline (audit/live_citation_withdrawal_baseline_v2.json)
names, per row, the pinned hash, the hash the later audited change produced and that change, and a
pinned hash is also satisfied by its recorded successor -- for a kept row (before) and an already
withdrawn row (after), never for a row still to withdraw, whose edit must start from the pinned bytes.
A successor that is not recorded against that exact pinned hash still refuses.

DUPLICATES POSTED TWICE (AUX-098). Two independent adjudications of the counted corpus found reports one
person posted twice (a cross-post or a re-post of one incident). The same mechanism withdraws them, with
four surgical additions and no other change:

  scope       a manifest declares one of two product scopes: AUX-088's (Windows, OBS), which its two
              pinned manifests keep, or that scope plus blackmagic-davinci. Every entry must be a row of
              the scope its manifest declares. DaVinci has no build contract (target_build empty) and
              takes the non-Windows two-line edit; a DaVinci block carrying a validity line refuses.
  two labels  besides AUX-088's two INCORRECT labels, a duplicate may carry two `same_report_duplicate`
              labels from two different, named reviewers, and BOTH must name the kept row the entry
              names (`duplicate_of_id` == duplicate_of.id). Agreeing that two rows are one report is not
              enough; the two reviews must agree on which row stays.
  same time   the kept row is normally the EARLIER capture. Rows found in one collection run share a
              capture time, so the retained row is then the earlier POST: the entry must state
              `capture_tie: true` (and must not state it when the captures differ), both labels must be
              `same_report_duplicate`, and the tool itself derives a source-native ordinal from both stored
              URLs in one family -- the Microsoft Learn question number, the Reddit base-36 post id -- and
              the kept row's must be the lower. Any other family, a missing ordinal, or two families
              refuses. `source_date` never decides: it is a thread's last activity.
  writers     `--regenerate` runs the reconcile and one `--product-id` promotion per product of the
              manifest's declared scope, so a DaVinci manifest adds exactly davinci-updates.yml's own
              scoped promotion (`--product-id blackmagic-davinci`); nothing ever runs unscoped.

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

import withdraw_windows_confirmed_and_duplicate_rows as aux079  # noqa: E402
import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib.patch_identity import is_build_aware, key_from, patch_key  # noqa: E402
from lib.report_counts import counted_evidence_counts, windows_targets_from_front_matter  # noqa: E402
from lib.source_segments import report_url_key  # noqa: E402
from patch_collectors.base import WINDOWS_PRODUCT_ID, load_front_matter_and_body  # noqa: E402
from withdraw_acrobat_wrong_edition_rows import EOL  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
STORE = ROOT / "_data" / "consensus_evidence.yml"
GENERATED = ROOT / "updates" / "generated"
MANIFEST = SCRIPTS / "audit" / "live_citation_withdrawal.json"
BASELINE = SCRIPTS / "audit" / "live_citation_withdrawal_baseline_v2.json"

OBS_PRODUCT_ID = "obs-studio"
DAVINCI_PRODUCT_ID = "blackmagic-davinci"
PRODUCTS = (WINDOWS_PRODUCT_ID, OBS_PRODUCT_ID)  # AUX-088's scope; its two manifests pin it
EXTENDED_PRODUCTS = PRODUCTS + (DAVINCI_PRODUCT_ID,)  # AUX-098
SCOPES = {PRODUCTS: "Windows or OBS", EXTENDED_PRODUCTS: "Windows, OBS or DaVinci"}
SELECTOR = aux072.SELECTOR
DUPLICATE_REASON = "duplicate_existing_evidence"
REASONS = frozenset({aux072.REASON, DUPLICATE_REASON, "version_named_but_working",
                     "version_is_rollback_target", "not_a_real_issue_report"})
INCORRECT = "INCORRECT"
DUPLICATE_LABEL = "same_report_duplicate"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FRONT_RE = re.compile(r"^product_id:\s*['\"]?(" + "|".join(re.escape(p) for p in EXTENDED_PRODUCTS)
                      + r")['\"]?\s*$", re.M)
# Source-native post ordinals, for a same-time capture only: (family, URL pattern, base of the id).
ORDINAL_FAMILIES = (
    ("microsoft_learn_question",
     re.compile(r"^https://learn\.microsoft\.com/(?:[a-z]{2}-[a-z]{2}/)?answers/questions/([0-9]+)(?:[/?#]|$)"), 10),
    ("reddit_post", re.compile(r"^https://(?:www\.)?reddit\.com/r/[A-Za-z0-9_]+/comments/([0-9a-z]+)(?:[/?#]|$)"), 36),
)


def writers_for(scope: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """The reconcile scoped to the products, then each product's own scoped promotion. Never unscoped."""
    reconcile = ("build_consensus_from_evidence.py",
                 *(arg for product in scope for arg in ("--product-id", product)), "--reconcile-only")
    return (reconcile,) + tuple(("apply_consensus_to_records.py", "--product-id", product, "--write-all",
                                 "--confirm-write") for product in scope)


WRITERS = writers_for(PRODUCTS)


class Refusal(Exception):
    """The run cannot proceed safely. Nothing has been written."""


sha = aux072.sha
identity = aux072.identity


def edit_for(product_id: str, reason: str) -> tuple[tuple[str, str], ...]:
    """AUX-079's three transitions for Windows; the first two (counted, exclusion_reason) for OBS."""
    lines = aux079.edit_for(reason)
    return lines if product_id == WINDOWS_PRODUCT_ID else lines[:2]


def withdrawn_fields(product_id: str, reason: str) -> dict[str, Any]:
    fields: dict[str, Any] = {"counted": False, "exclusion_reason": reason}
    if product_id == WINDOWS_PRODUCT_ID:
        fields["evidence_valid_for_current_patch"] = False
    return fields


def withdraw_block(block: str, product_id: str, reason: str) -> str:
    """Each old line must occur exactly once in the block; a non-Windows block must carry no validity line."""
    if product_id != WINDOWS_PRODUCT_ID and (aux072.VALID_TRUE in block or aux072.VALID_FALSE in block):
        raise Refusal("unexpected block shape: a non-Windows row carrying evidence_valid_for_current_patch")
    for old, new in edit_for(product_id, reason):
        if block.count(old) != 1:
            raise Refusal(f"unexpected block shape: {old.strip()!r} occurs {block.count(old)} times")
        block = block.replace(old, new, 1)
    return block


def _ident(entry: dict[str, Any], prefix: str = "") -> tuple[str, ...]:
    source = entry.get(prefix) if prefix else entry
    return tuple(str((source or {}).get(key) or "") for key in SELECTOR)


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return manifest_entries(json.loads(Path(path).read_text(encoding="utf-8")))


def _labels(entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    adj = entry.get("adjudication") or {}
    return adj.get("first_audit") or {}, adj.get("second_blind") or {}


def _two_labels(entry: dict[str, Any]) -> bool:
    """Two agreeing labels with reasons: both INCORRECT (AUX-088), or both `same_report_duplicate` from two
    different named reviewers that each name the kept row this entry names (AUX-098)."""
    first, blind = _labels(entry)
    reasons = bool(str(first.get("reason") or "").strip()) and bool(str(blind.get("reason_class") or "").strip())
    if first.get("label") == INCORRECT and blind.get("label") == INCORRECT:
        return reasons
    if first.get("label") == DUPLICATE_LABEL and blind.get("label") == DUPLICATE_LABEL:
        kept = str((entry.get("duplicate_of") or {}).get("id") or "")
        by = (str(first.get("by") or "").strip(), str(blind.get("by") or "").strip())
        return (reasons and first.get("duplicate_of_id") == kept and blind.get("duplicate_of_id") == kept
                and all(by) and by[0] != by[1])
    return False


def manifest_scope(doc: dict[str, Any]) -> tuple[str, ...]:
    """The product scope the manifest declares: AUX-088's (Windows, OBS) or that plus DaVinci, exactly."""
    scope = tuple(doc.get("products") or ())
    if scope not in SCOPES:
        raise Refusal("manifest: the product scope differs from the tool's (Windows and OBS, or Windows, OBS "
                      "and DaVinci)")
    return scope


def manifest_entries(doc: dict[str, Any]) -> list[dict[str, Any]]:  # noqa: PLR0912
    """The pinned entries, refusing a manifest that could select ambiguously or widen the vocabulary."""
    if list(doc.get("selector") or []) != list(SELECTOR):
        raise Refusal("manifest: the selector is not the five-field identity")
    if sorted(doc.get("exclusion_reasons") or []) != sorted(REASONS):
        raise Refusal("manifest: the exclusion reasons differ from the tool's closed vocabulary")
    scope = manifest_scope(doc)
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise Refusal("manifest: no entries")
    seen: set[tuple[str, ...]] = set()
    retained: set[tuple[str, ...]] = set()
    for entry in entries:
        ident = _ident(entry)
        product = ident[0]
        if product not in scope:
            raise Refusal(f"manifest: not a {SCOPES[scope]} row: {ident}")
        required = [ident[i] for i in (0, 1, 3, 4)]
        if not all(required):
            raise Refusal(f"manifest: an entry lacks part of the five-field identity: {ident}")
        if bool(ident[2]) != is_build_aware(product):
            raise Refusal(f"manifest: target_build must be set exactly for a build-aware product: {ident}")
        if ident in seen:
            raise Refusal(f"manifest: identity listed twice: {ident}")
        seen.add(ident)
        role = entry.get("role")
        if role not in ("withdraw", "retain"):
            raise Refusal(f"manifest: unknown role {role!r} for {ident[3]}")
        hashes = ["block_sha256_before"] + (["block_sha256_after"] if role == "withdraw" else [])
        if not all(SHA256_RE.match(str(entry.get(key) or "")) for key in hashes):
            raise Refusal(f"manifest: missing or malformed block hash for {ident[3]}")
        if not str(entry.get("record_file") or "").endswith(".md"):
            raise Refusal(f"manifest: no pinned record for {ident[3]}")
        if product == WINDOWS_PRODUCT_ID and not (entry.get("target_kb") and entry.get("target_os_build")):
            raise Refusal(f"manifest: no pinned target identity for {ident[3]}")
        if role == "retain":
            retained.add(ident)
            continue
        if entry.get("exclusion_reason") not in REASONS:
            raise Refusal(f"manifest: reason {entry.get('exclusion_reason')!r} is outside the closed vocabulary: {ident[3]}")
        if not _two_labels(entry) or not str(entry.get("basis") or "").strip():
            raise Refusal(f"manifest: row lacks two INCORRECT labels (or two same_report_duplicate labels from "
                          f"two reviewers naming its kept row) with reasons and a stated basis: {ident[3]}")
    referenced: set[tuple[str, ...]] = set()
    for entry in entries:
        if entry["role"] != "withdraw":
            continue
        dup = _ident(entry, "duplicate_of") if entry.get("duplicate_of") else None
        if (entry["exclusion_reason"] == DUPLICATE_REASON) != (dup is not None):
            raise Refusal(f"manifest: a duplicate must name its kept row, and only a duplicate may: {entry['id']}")
        if dup is not None:
            if dup not in retained:
                raise Refusal(f"manifest: duplicate names no pinned kept row: {entry['id']}")
            referenced.add(dup)
    if retained - referenced:
        raise Refusal("manifest: a kept row is pinned that no duplicate names")
    return entries


def load_baseline(path: Path | None) -> dict[tuple[str, ...], dict[str, str]]:
    """Five-field identity -> {pinned hash: successor hash}, from the supplemental baseline.

    An absent file is an empty baseline (every pin must then match exactly). A present file that does
    not have the expected shape refuses: a malformed baseline must never read as "nothing changed"."""
    if path is None or not Path(path).exists():
        return {}
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if list(doc.get("selector") or []) != list(SELECTOR) or not isinstance(doc.get("version"), int):
        raise Refusal("baseline: not a versioned five-field baseline")
    entries = doc.get("entries")
    if not isinstance(entries, list):
        raise Refusal("baseline: no entry list")
    out: dict[tuple[str, ...], dict[str, str]] = {}
    for entry in entries:
        ident = _ident(entry)
        pinned, now = str(entry.get("block_sha256_pinned") or ""), str(entry.get("block_sha256_now") or "")
        change = entry.get("change")
        if not (SHA256_RE.match(pinned) and SHA256_RE.match(now)) or pinned == now:
            raise Refusal(f"baseline: malformed hashes for {ident[3]}")
        if not isinstance(change, dict) or not change or not str(entry.get("changed_by") or "").strip():
            raise Refusal(f"baseline: the change or its audit is not named for {ident[3]}")
        if pinned in out.get(ident, {}):
            raise Refusal(f"baseline: pinned hash listed twice for {ident[3]}")
        out.setdefault(ident, {})[pinned] = now
    return out


def _pin_holds(entry: dict[str, Any], key: str, digest: str, baseline: dict) -> bool:
    """The block still is what was pinned, or what a recorded later audited change made of it."""
    pinned = entry[key]
    return digest == pinned or (baseline or {}).get(_ident(entry), {}).get(pinned) == digest


def patch_records(generated_dir: Path) -> dict[tuple[str, str, str], list[tuple[str, dict[str, Any]]]]:
    """Canonical patch key -> [(file name, front matter)] for every Windows, OBS and DaVinci update record.
    Only files whose front matter names one of the three products are parsed."""
    out: dict[tuple[str, str, str], list[tuple[str, dict[str, Any]]]] = {}
    for path in sorted(Path(generated_dir).glob("*.md")):
        head = path.read_text(encoding="utf-8").split(EOL + "---", 1)[0]
        if not FRONT_RE.search(head):
            continue
        data, _body = load_front_matter_and_body(path)
        if isinstance(data, dict) and data.get("update_entry") is True:
            out.setdefault(key_from(data), []).append((path.name, data))
    return out


def _targets(records: dict) -> dict[tuple[str, str, str], dict[str, Any]]:
    return windows_targets_from_front_matter(data for found in records.values() for _name, data in found)


def _counts(rows: list[dict[str, Any]], targets: dict,
            scope: tuple[str, ...] = PRODUCTS) -> dict[tuple[str, str, str], int]:
    """The authoritative counted population of the scope's products, per patch (Windows gate included)."""
    return counted_evidence_counts([r for r in rows if str(r.get("product_id") or "") in scope],
                                   windows_targets=targets)


def _record_refusal(entry: dict[str, Any], records: dict) -> str:
    ident = _ident(entry)
    found = records.get(patch_key(ident[0], ident[1], ident[2]), [])
    if len(found) != 1:
        return f"{len(found)} records carry the identity {ident[0]} {ident[1]} {ident[2]}".rstrip()
    name, data = found[0]
    if name != Path(entry["record_file"]).name:
        return f"the record for {ident[1]} {ident[2]} is {name}, not the pinned {entry['record_file']}"
    if ident[0] == WINDOWS_PRODUCT_ID and (str(data.get("target_kb") or "") != entry["target_kb"]
                                          or str(data.get("target_os_build") or "") != entry["target_os_build"]):
        return f"record target identity moved for {ident[1]} {ident[2]}"
    return ""


def source_ordinal(url: str) -> tuple[str, int] | None:
    """(family, the source's own post number) for a URL of a family with sequential post ids, else None."""
    for family, pattern, base in ORDINAL_FAMILIES:
        match = pattern.match(str(url or ""))
        if match:
            return family, int(match.group(1), base)
    return None


def _tie_refusal(row: dict[str, Any], kept: dict[str, Any], entry: dict[str, Any]) -> str:
    """'' when a same-time capture is decided: two duplicate labels and the kept row the earlier post."""
    first, blind = _labels(entry)
    if not (first.get("label") == DUPLICATE_LABEL and blind.get("label") == DUPLICATE_LABEL):
        return "a same-time capture needs two same_report_duplicate labels naming the kept row"
    mine, theirs = source_ordinal(str(row.get("source_url") or "")), source_ordinal(str(kept.get("source_url") or ""))
    if mine is None or theirs is None:
        return "a same-time capture whose source gives no post number"
    if mine[0] != theirs[0]:
        return "a same-time capture across two source families"
    if not theirs[1] < mine[1]:
        return "the kept row is not the earlier post"
    return ""


def _duplicate_refusal(row: dict[str, Any], kept: dict[str, Any], entry: dict[str, Any] | None = None) -> str:
    """'' when `kept` still counts, on the same patch, as the earlier capture of another report URL -- or,
    captured at the same instant and stated as such, as the earlier post (AUX-098)."""
    if key_from(row) != key_from(kept):
        return "the kept row is on another patch"
    if report_url_key(str(row.get("source_url") or "")) == report_url_key(str(kept.get("source_url") or "")):
        return "the kept row is the same report URL"
    row_at, kept_at = str(row.get("captured_at") or ""), str(kept.get("captured_at") or "")
    tie = (entry or {}).get("capture_tie") is True
    if row_at and kept_at == row_at:
        if not tie:
            return "the kept row is not the earlier capture"
        why = _tie_refusal(row, kept, entry or {})
        if why:
            return why
    elif not kept_at < row_at:
        return "the kept row is not the earlier capture"
    elif tie:
        return "capture_tie is stated but the kept row is the earlier capture"
    if kept.get("counted") is not True:
        return "the kept row does not count"
    return ""


def plan(text: str, entries: list[dict[str, Any]], records: dict,  # noqa: PLR0912, PLR0915
         baseline: dict | None = None, scope: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Decide every entry and prove the resulting text, without writing. Raises Refusal.
    `scope` is the manifest's declared product scope (AUX-088's when every entry is a Windows or OBS row)."""
    if scope is None:
        scope = PRODUCTS if all(e.get("product_id") in PRODUCTS for e in entries) else EXTENDED_PRODUCTS
    blocks = aux072.store_blocks(text)
    by_identity: dict[tuple[str, ...], list[int]] = {}
    for index, (_lo, _hi, row) in enumerate(blocks):
        by_identity.setdefault(identity(row), []).append(index)

    refusals: list[str] = []
    decided: list[dict[str, Any]] = []
    edits: dict[int, tuple[str, dict[str, Any]]] = {}
    located: dict[tuple[str, ...], dict[str, Any]] = {}
    for entry in entries:
        ident = _ident(entry)
        label = f"{ident[0]} {ident[1]} {ident[2]} {ident[3]}".replace("  ", " ")
        hits = by_identity.get(ident, [])
        if len(hits) != 1:
            refusals.append(f"{len(hits)} blocks match the five-field identity of {label}")
            continue
        index = hits[0]
        lo, hi, row = blocks[index]
        located[ident] = row
        block = text[lo:hi]
        digest = sha(block)
        why = _record_refusal(entry, records)
        if why:
            refusals.append(why)
            continue
        item = {"role": entry["role"], **dict(zip(SELECTOR, ident)),
                "block_sha256_before_run": digest, "counted_before_run": row.get("counted")}
        if entry["role"] == "retain":
            if not _pin_holds(entry, "block_sha256_before", digest, baseline):
                refusals.append(f"kept row changed: {label}")
            elif row.get("counted") is not True:
                refusals.append(f"kept row no longer counts: {label}")
            item["action"] = "kept"
        elif _pin_holds(entry, "block_sha256_after", digest, baseline):
            item["action"] = "already_withdrawn"
            item["exclusion_reason"] = entry["exclusion_reason"]
        elif digest != entry["block_sha256_before"]:
            refusals.append(f"block changed since the manifest was pinned: {label}")
            continue
        else:
            reason = entry["exclusion_reason"]
            try:
                new_block = withdraw_block(block, ident[0], reason)
            except Refusal as exc:
                refusals.append(f"{label}: {exc}")
                continue
            if sha(new_block) != entry["block_sha256_after"]:
                refusals.append(f"the edit does not produce the pinned block for {label}")
                continue
            edits[index] = (new_block, withdrawn_fields(ident[0], reason))
            item["action"] = "withdraw"
            item["exclusion_reason"] = reason
        decided.append(item)

    for entry in entries:
        if entry["role"] != "withdraw" or not entry.get("duplicate_of"):
            continue
        row, kept = located.get(_ident(entry)), located.get(_ident(entry, "duplicate_of"))
        if row is None or kept is None:
            continue  # already refused above
        why = _duplicate_refusal(row, kept, entry)
        if why:
            refusals.append(f"duplicate {entry['update_version']} {entry['id']}: {why}")
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
        expected = dict(old, **edits[index][1]) if index in edits else old
        if new != expected:
            raise Refusal(f"the edit changed more than decided at row {index} ({old.get('id')})")

    counted_before = {identity(r) for r in rows_before if r.get("counted") is True}
    counted_after = {identity(r) for r in rows_after if r.get("counted") is True}
    newly_counted = sorted(" ".join(k[:4]) for k in counted_after - counted_before)
    if newly_counted:
        raise Refusal("a row would start counting: " + "; ".join(newly_counted))

    targets = _targets(records)
    before, after = _counts(rows_before, targets, scope), _counts(rows_after, targets, scope)
    withdrawn = {_ident(e) for e in entries if e["role"] == "withdraw"}
    pinned = {_ident(e) for e in entries}
    reports = {report_url_key(e["source_url"]) for e in entries if e["role"] == "withdraw"}
    siblings = []
    for index, (_lo, _hi, row) in enumerate(blocks):
        if identity(row) in pinned or report_url_key(str(row.get("source_url") or "")) not in reports:
            continue
        after_row = rows_after[index]
        siblings.append({**dict(zip(SELECTOR, identity(row))), "counted": after_row.get("counted"),
                         "exclusion_reason": after_row.get("exclusion_reason"),
                         "unchanged": index not in edits and after_row == row})
    touched = sorted({patch_key(*k[:3]) for k in withdrawn})
    population = {product: [sum(n for k, n in before.items() if k[0] == product),
                            sum(n for k, n in after.items() if k[0] == product)] for product in scope}
    return {
        "new_text": new_text,
        "entries": decided,
        "withdrawn_now": len(edits),
        "counted_population": population,
        "per_patch": [{"product_id": k[0], "update_version": k[1], "target_build": k[2],
                       "before": before.get(k, 0), "after": after.get(k, 0)} for k in touched],
        "newly_counted_rows": newly_counted,
        "same_report_rows_on_other_identities": siblings,
    }


def run(store: Path, generated_dir: Path, manifest: Path, write: bool,
        baseline: Path | None = BASELINE) -> dict[str, Any]:
    raw = Path(store).read_bytes()
    text = raw.decode("utf-8")
    doc = json.loads(Path(manifest).read_text(encoding="utf-8"))
    scope = manifest_scope(doc)
    result = plan(text, manifest_entries(doc), patch_records(generated_dir), load_baseline(baseline), scope)
    new_text = result.pop("new_text")
    result.update({
        "product_scope": list(scope),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exclusion_reasons": sorted(REASONS),
        "store_sha256_before": sha(raw),
        "store_sha256_after": sha(new_text),
        "manifest_sha256": sha(Path(manifest).read_bytes()),
        "baseline_sha256": sha(Path(baseline).read_bytes()) if baseline and Path(baseline).exists() else "",
        "written": False,
    })
    if write and result["withdrawn_now"]:
        Path(store).write_bytes(new_text.encode("utf-8"))
        result["written"] = True
    return result


def regenerate(writers: tuple = WRITERS) -> list[dict[str, Any]]:
    """The lane's scoped writers, as subprocesses, in order. Stops at the first failure.
    apply_consensus_to_records' JSON report goes to a discarded temporary file (--output)."""
    done = []
    with tempfile.TemporaryDirectory(prefix="aux088-") as tmp:
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
    ap.add_argument("--baseline", type=Path, default=BASELINE,
                    help="supplemental baseline of later audited changes to pinned rows")
    ap.add_argument("--write", action="store_true", help="apply the withdrawal in place")
    ap.add_argument("--confirm-write", action="store_true", help="required together with --write")
    ap.add_argument("--regenerate", action="store_true",
                    help="after the store step, run the writers scoped to the manifest's products (default tree only)")
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
        result = run(args.store, args.generated_dir, args.manifest, args.write, args.baseline)
    except Refusal as exc:
        print("REFUSED, nothing written: " + str(exc))
        return 1
    for item in result["entries"]:
        where = " ".join(x for x in (item["product_id"], item["update_version"], item["target_build"]) if x)
        print(f"  [{item['action']:<17}] {where}  {item.get('exclusion_reason') or '-'}  {item['source_url']}")
    print(f"rows withdrawn by this run: {result['withdrawn_now']}")
    for product, (before, after) in result["counted_population"].items():
        print(f"{product} counted population: {before} -> {after}")
    for patch in result["per_patch"]:
        where = " ".join(x for x in (patch["product_id"], patch["update_version"], patch["target_build"]) if x)
        print(f"  {where}: {patch['before']} -> {patch['after']}")
    siblings = result["same_report_rows_on_other_identities"]
    print(f"same-report rows on other identities left untouched: {len(siblings)} "
          f"(still counted: {sum(1 for s in siblings if s['counted'] is True)})")
    status = 0
    if args.regenerate:
        result["writers"] = regenerate(writers_for(tuple(result["product_scope"])))
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
