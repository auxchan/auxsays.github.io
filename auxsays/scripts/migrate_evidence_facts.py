#!/usr/bin/env python3
"""Zero-network backfill of the structured evidence facts on every stored Tier 1 row (G68).

From G68 on, every row a collector persists carries four public, derived facts, computed from its own
text when it is written (`lib.evidence_facts`): `excerpt_norm_sha256`, `title_dedup_sha256`,
`issue_bucket` and `facts_rule_version`. Rows written earlier carry none. This script adds them, from
the text each row already holds. It makes no network request, runs no collector, and writes exactly
one file: `auxsays/_data/consensus_evidence.yml`.

The same script carries a future rule change. When a version in `lib.evidence_facts.RULE_SETS` names
a new rule for a fact, `--write` rewrites that fact on every row, in place, and nothing else.

Scope, exactly:
    a row with no facts      gains the four lines at the END of its own text block;
    a row with complete facts that are outdated, malformed or do not match its own text
                             has exactly those lines rewritten in place;
    a row with current, correct facts
                             keeps every byte;
    a row with a PARTIAL set refuses the whole run, and nothing is written.

Nothing is re-serialised: every other byte of the store stays as it is. The script PROVES that before
it writes, and refuses otherwise:
    * the edited store parses to the same rows, each equal to its old self plus the current facts;
    * every old key keeps its position, and the facts are the row's last keys;
    * on a backfill, removing every fact line gives back the old bytes exactly (`sha256` printed);
    * a second pass over the result changes nothing (idempotent).

Run:  python auxsays/scripts/migrate_evidence_facts.py            (report only, JSON on stdout)
      python auxsays/scripts/migrate_evidence_facts.py --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from lib import evidence_facts as ef  # noqa: E402
from lib.normalize import atomic_write_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "_data" / "consensus_evidence.yml"


class ProofFailed(RuntimeError):
    """The edited store is not exactly the old store plus the facts; nothing is written."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rows(text: str) -> list[dict[str, Any]]:
    return yaml.load(text, Loader=yaml.SafeLoader)["evidence"]


def prove(before_text: str, after_text: str, stats: dict[str, Any]) -> dict[str, Any]:
    """Check the edit is the facts and nothing else. Raises ProofFailed."""
    before, after = _rows(before_text), _rows(after_text)
    if len(before) != len(after):
        raise ProofFailed(f"row count changed: {len(before)} -> {len(after)}")
    for index, (old, new) in enumerate(zip(before, after)):
        kept_old = [k for k in old if k not in ef.STORED_FIELDS]
        keys_new = list(new)
        if keys_new != kept_old + list(ef.STORED_FIELDS) and keys_new != list(old):
            raise ProofFailed(f"row {index} ({old.get('id')}): key order changed")
        if {k: v for k, v in new.items() if k not in ef.STORED_FIELDS} != \
                {k: v for k, v in old.items() if k not in ef.STORED_FIELDS}:
            raise ProofFailed(f"row {index} ({old.get('id')}): a field other than the facts changed")
        if {k: new.get(k) for k in ef.STORED_FIELDS} != ef.compute_facts(old):
            raise ProofFailed(f"row {index} ({old.get('id')}): the stored facts are not the computed ones")
    proof: dict[str, Any] = {"rows_equal_old_plus_facts": True}
    if stats["refreshed"] == 0:
        # A pure backfill: every byte outside the added lines is the old store's.
        stripped = ef.strip_fact_lines(after_text)
        if stripped != ef.strip_fact_lines(before_text):
            raise ProofFailed("removing the fact lines does not give back the old store")
        proof["sha256_after_without_fact_lines"] = _sha(stripped)
        proof["sha256_before_without_fact_lines"] = _sha(ef.strip_fact_lines(before_text))
    again, again_stats = ef.backfill_store_text(after_text)
    if again != after_text:
        raise ProofFailed("a second pass changes the store (not idempotent)")
    proof["second_pass_changes"] = again_stats["backfilled"] + again_stats["refreshed"]
    return proof


def run(store: Path, write: bool) -> dict[str, Any]:
    before = store.read_bytes().decode("utf-8")
    after, stats = ef.backfill_store_text(before)
    report: dict[str, Any] = {
        "store": str(store.name),
        "rule_version": ef.CURRENT_VERSION,
        "rules": ef.RULE_SETS[ef.CURRENT_VERSION],
        **{k: v for k, v in stats.items()},
        "sha256_before": _sha(before),
        "sha256_after": _sha(after),
        "written": False,
    }
    if after == before:
        report["proof"] = {"no_change": True}
        return report
    report["proof"] = prove(before, after, stats)
    if write:
        atomic_write_text(store, after)
        report["written"] = True
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill the structured evidence facts (zero network).")
    ap.add_argument("--store", type=Path, default=STORE, help="evidence store (default: the live one)")
    ap.add_argument("--write", action="store_true", help="write the store (default: report only)")
    args = ap.parse_args(argv)
    try:
        report = run(args.store, args.write)
    except (ef.FactStoreError, ProofFailed) as exc:
        print(f"REFUSED (nothing written): {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    if not args.write and report["sha256_before"] != report["sha256_after"]:
        print("report only; pass --write to apply", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
