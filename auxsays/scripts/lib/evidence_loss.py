"""A stored evidence row may not disappear, and may stop being accepted only by an audited withdrawal.

WHAT THIS GUARDS. `_data/consensus_evidence.yml` is the store every accepted user report lives in.
Nothing downstream can tell whether a row that is no longer there was withdrawn or simply lost:
`qa_patch_records` and `audit_consensus_evidence` compare the generated records against the SAME
store, and the scheduled lane's reconcile step rewrites every record count to match whatever the
store now holds. So a purge that removes evidence and regenerates the records coherently is
invisible to all of them by construction. Measured before this module existed: delete 241 of 246
DaVinci rows, run the lane's own `apply_consensus_to_records.py --write-all --confirm-write`, and
QA, audit, and the full governed suite all pass -- and the real `automation_writeback` pushed it.

The only reference a purge cannot also rewrite is the store as it stood BEFORE the change: the git
parent. Every in-tree ledger (method health, the Tier-2 and Level-3 files, a record's
accepted_report_sources) is written by the same lanes in the same run, so it is LOWER than the
store, not higher -- the same trap as a retention store kept in the file it is meant to retain.

THE RULE. For every row in the base store, the candidate must still account for it:

  - A row may not disappear.                                   -> evidence_row_removed
  - An ACCEPTED row may stop being accepted only by staying in
    the store as `counted: false` with a non-empty
    `exclusion_reason`.                                        -> evidence_withdrawal_unaudited

That second shape is not invented here -- it is the house convention, measured over the store's
whole history as of 2ab3314e (261 commits touch it; 243 of them are automated). 55 rows were
withdrawn, every one by flipping `counted` to false with a named reason and keeping the row (#83,
#104, #112, #116, #120); none was ever flipped back and none was ever created as counted:false.
Accepted rows were deleted outright on three occasions: #79 and #82, both human repairs on the night
before #83 began the flip convention and both expressible as flips, and the pull-merge f6774f61,
whose conflict resolution silently dropped four DaVinci rows through its SECOND parent -- the one
genuine silent loss in the history, and invisible to a first-parent diff. Not one of the 243
automated commits would have been refused.

Judged over every parent edge of the full commit graph (`git rev-list --parents`, not a
path-filtered log, which hides merges that are TREESAME to a parent), the rule fires on exactly four
edges: those three, and the second-parent edge of merge b012f345, whose branch forked before #79/#82
and still held the rows they deleted. That fourth is not a production refusal: neither enforcement
point judges a merge's second parent -- the writeback compares its own checkout with its own
candidate, and CI compares against the event's base, which for that merge (its first parent) loses
nothing.

Withdrawn rows are protected as well as accepted ones. Otherwise "flip it, then delete it" is a
two-step silent purge that passes both steps. A withdrawn row is also what stops a false identity
coming back: the append authority dedups against EVERY stored row regardless of `counted`, so a
tombstone blocks re-collection, while a deleted row frees its key.

WHAT THIS DELIBERATELY DOES NOT DO.
  - It does not freeze the store's size. Growth is unrestricted, and an audited withdrawal shrinks
    the counted population legitimately -- which is why no count, floor or percentage appears here.
  - It does not forbid editing a row. Classification edits (issue_theme, severity, ...) and the
    calibration promotions are neither withdrawals nor losses. An "immutable rows" rule would have
    fired on four legitimate automated commits.
  - It does not police re-acceptance (counted false -> true). That is a precision question, not a
    loss, and it belongs to the identity checks that own precision.
  - It is not product-scoped. The failure it catches is a property of the store and the writeback,
    not of DaVinci.

WHAT THIS DOES NOT SEE -- its scope is the STORE'S ROWS, not every way a record's count can move.
A report can leave a record's count with no row disappearing and no row losing acceptance: restamp
its `target_build`, or change the fields the Windows identity gate reads (`matched_os_build`,
`matched_kb`, `matched_feature_version`, `source_date`), and `report_counts` stops attributing it to
that record. That is the same class as the #110 restamps this rule must allow, so a row-presence rule
cannot tell the two apart; closing it would need a field-immutability rule, which is deliberately not
imposed here. The collector lanes run through run_patch_evidence_collection already have one --
`collector_ownership.validate_evidence` rejects any edit to an existing row in a collector
transaction -- but the PowerPoint orchestration graph does not call it. For the same reason, Windows
sibling-build rows are interchangeable to this rule: it sees that an identity still has as many
accounted-for rows as before, not which build's row they are.

IDENTITY. Rows are matched as a multiset on (product_id, update_version, id, source_url). No row has
ever changed those four fields in place (every historical version of the store, as of 2ab3314e). `target_build` is left out on
purpose: #110, #112 and #113 legitimately restamped it in place on 82 rows, and the canonical
(product, version, build, id) key would read each of those as a deletion. Matching as a MULTISET,
not a dict, is what keeps Windows sibling-build rows -- which share all four fields and differ only
by build -- from collapsing into one.

The store is parsed as raw YAML, never through the evidence normalizer: normalizing turns a missing
`counted` into False and drops null keys, which would invent or hide exactly the transitions this
module exists to see.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import yaml

# The PURE-PYTHON loader, deliberately, although the C loader is several times faster. libyaml's
# composer recurses on the C stack, so a store nested a few thousand levels deep overflows it and
# kills the interpreter outright -- no Python exception, so no refusal outcome, and the writeback
# left its index staged. The pure-Python composer raises RecursionError on the same input, which
# parse_store turns into EvidenceStoreUnreadable like any other unreadable store. The cost, measured
# at 1.2k rows, is one to two seconds per parse (hardware-dependent), paid twice per evidence-staging
# writeback. Every other reader of the store already uses the pure-Python loader (yaml.safe_load).
_Loader = yaml.SafeLoader

EVIDENCE_PATH = "auxsays/_data/consensus_evidence.yml"

REMOVED = "evidence_row_removed"
UNAUDITED = "evidence_withdrawal_unaudited"
UNREADABLE = "evidence_store_unreadable"

Key = tuple[str, str, str, str]


class EvidenceStoreUnreadable(ValueError):
    """The store could not be parsed, so no statement about loss can be made. Callers FAIL CLOSED:
    an unreadable store is never evidence that nothing was lost."""


@dataclass(frozen=True)
class EvidenceLoss:
    code: str
    product_id: str
    update_version: str
    row_id: str
    source_url: str
    rows: int          # how many rows under this identity the violation covers
    detail: str

    def public_reason(self) -> str:
        """One bounded line naming the rule and the identity. The id is the store's own slug, so it
        is already public-safe; it is length-capped anyway so a hostile value cannot flood a log."""
        return (f"code={self.code} product={self.product_id[:64] or '-'} "
                f"version={self.update_version[:64] or '-'} rows={self.rows} "
                f"id={self.row_id[:160] or '-'}")


def parse_store(text: str | None) -> list[dict]:
    """Rows of a store document. Empty or absent text is an empty store (a brand-new repository has
    no base to lose). Anything that does not parse, or parses to something that is not a store,
    raises EvidenceStoreUnreadable -- it is not silently read as empty."""
    if text is None or not text.strip():
        return []
    try:
        doc = yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader only
    except Exception as exc:  # noqa: BLE001 - deliberately total; see below
        # Not only yaml.YAMLError: a scalar the constructor cannot build (an unquoted `2026-13-45`,
        # a bad explicit tag) raises a plain ValueError. Anything that goes wrong READING the store
        # means "unreadable" -- never "empty", and never an uncaught crash that leaves the writeback
        # index staged with no refusal outcome recorded.
        raise EvidenceStoreUnreadable(
            f"evidence store could not be parsed: {type(exc).__name__}") from exc
    if doc is None:
        return []
    if not isinstance(doc, dict):
        raise EvidenceStoreUnreadable(f"evidence store top level is {type(doc).__name__}, not a mapping")
    rows = doc.get("evidence")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise EvidenceStoreUnreadable(f"evidence store 'evidence' is {type(rows).__name__}, not a list")
    # A non-mapping entry carries no identity to lose; it is not a row this rule can reason about.
    return [r for r in rows if isinstance(r, dict)]


def is_accepted(row: dict) -> bool:
    """Row-level acceptance, the same predicate `report_counts.counted_evidence_counts` applies
    before its record-relative Windows gate. That gate is left out on purpose: it depends on which
    cumulative update a Windows record currently targets, which legitimately rolls over, so it is
    not a property of the row."""
    return row.get("counted") is not False and row.get("patch_version_matched") is True


def is_audited_withdrawal(row: dict) -> bool:
    reason = row.get("exclusion_reason")
    return row.get("counted") is False and isinstance(reason, str) and reason.strip() != ""


def row_key(row: dict) -> Key:
    return (str(row.get("product_id") or ""), str(row.get("update_version") or ""),
            str(row.get("id") or ""), str(row.get("source_url") or ""))


def _tally(rows: list[dict]) -> tuple[Counter, Counter]:
    """Per identity: how many rows exist, and how many are accounted for (accepted, or withdrawn
    with a reason)."""
    total: Counter = Counter()
    kept: Counter = Counter()
    for row in rows:
        k = row_key(row)
        total[k] += 1
        if is_accepted(row) or is_audited_withdrawal(row):
            kept[k] += 1
    return total, kept


def find_unexplained_losses(base_rows: list[dict], candidate_rows: list[dict]) -> list[EvidenceLoss]:
    """Every way the candidate fails to account for a base row. Empty means nothing was lost.

    Per identity k:
      removed    = rows under k in base that are no longer in the candidate at all;
      unaudited  = accounted-for rows under k that stopped being accounted for WITHOUT being removed
                   -- an accepted row that lost acceptance with no reason, or a withdrawal whose
                   reason was blanked.
    An accepted row turning into an audited withdrawal leaves `kept` unchanged, so it is never
    reported. Growth only ever raises both tallies, so it is never reported either.
    """
    b_total, b_kept = _tally(base_rows)
    c_total, c_kept = _tally(candidate_rows)
    losses: list[EvidenceLoss] = []
    for k in sorted(b_total):
        removed = max(0, b_total[k] - c_total[k])
        unaudited = max(0, (b_kept[k] - c_kept[k]) - removed)
        product_id, version, row_id, url = k
        if removed:
            losses.append(EvidenceLoss(
                REMOVED, product_id, version, row_id, url, removed,
                f"{removed} of {b_total[k]} row(s) under this identity are gone from the store; "
                f"withdraw by setting counted: false with an exclusion_reason instead of deleting"))
        if unaudited:
            losses.append(EvidenceLoss(
                UNAUDITED, product_id, version, row_id, url, unaudited,
                f"{unaudited} row(s) under this identity stopped counting without an "
                f"exclusion_reason"))
    return losses


def losses_between(base_text: str | None, candidate_text: str | None) -> list[EvidenceLoss]:
    """Convenience over two raw store documents. Raises EvidenceStoreUnreadable if either side
    cannot be parsed; callers must treat that as a refusal, not as a pass."""
    return find_unexplained_losses(parse_store(base_text), parse_store(candidate_text))
