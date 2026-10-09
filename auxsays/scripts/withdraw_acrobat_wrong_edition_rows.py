#!/usr/bin/env python3
"""Audited withdrawal of Acrobat evidence rows the repaired edition authority now refuses.

AUX-027 fixed PRO_RE so a bare "Acrobat DC Pro" is recognised as Pro. Fixing the producer does not
remove a row already in the store: the evidence store is append/dedupe oriented and nothing
re-evaluates a stored row. So the rows have to be corrected explicitly, and an audited withdrawal
is `counted: false` with a non-empty `exclusion_reason` and the ROW KEPT -- never a deletion
(lib/evidence_loss.py).

The verdict is DERIVED, not hard-coded: every stored Acrobat row is re-evaluated with the repaired
`acrobat_edition_attribution`, and this script reports every row that authority now refuses. It
WITHDRAWS only the rows whose source URL is named on the command line, so the blast radius is
visible in the invocation and reviewable in the diff. Idempotent: a row already withdrawn with this
reason is left untouched.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from patch_collectors.adobe_acrobat_community import acrobat_edition_attribution  # noqa: E402
from patch_collectors.base import EVIDENCE_PATH, load_evidence  # noqa: E402
from lib.evidence_loss import parse_store  # noqa: E402

ACROBAT = ("adobe-acrobat-reader", "adobe-acrobat-pro")


def refused_rows(rows: list[dict]) -> list[tuple[dict, str]]:
    """Stored Acrobat rows the repaired authority now refuses, with the reason it gives."""
    out: list[tuple[dict, str]] = []
    for row in rows:
        product_id = str(row.get("product_id") or "")
        if product_id not in ACROBAT:
            continue
        if row.get("counted") is False:
            continue
        text = str(row.get("report_text") or row.get("report_text_excerpt") or "")
        attributed, _alias, _appl, reason = acrobat_edition_attribution(text, product_id)
        # Only an EXPLICIT opposite-edition refusal is actionable here. `generic_acrobat_without
        # _edition` is not a refusal at all -- the shared-DC-build policy legitimately counts those,
        # and treating them as failures would withdraw most of the Acrobat corpus.
        if not attributed and reason == "wrong_product":
            out.append((row, reason))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only-url", action="append", default=[],
                    help="substring of a source_url to withdraw; repeatable. Required to write.")
    ap.add_argument("--path", default=str(EVIDENCE_PATH))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.path)
    rows = parse_store(path.read_text(encoding="utf-8"))
    refused = refused_rows(rows)

    print(f"stored rows                  : {len(rows)}")
    print(f"acrobat rows the authority now refuses as wrong_product: {len(refused)}")
    for row, reason in refused:
        selected = any(u in str(row.get("source_url") or "") for u in args.only_url)
        mark = "WITHDRAW" if selected else "report-only"
        print(f"  [{mark:11}] {row.get('product_id')} {row.get('update_version')} {reason}")
        print(f"                 {row.get('source_url')}")

    changed = 0
    for row, reason in refused:
        if not any(u in str(row.get("source_url") or "") for u in args.only_url):
            continue
        row["counted"] = False
        row["exclusion_reason"] = reason
        changed += 1
    print(f"rows withdrawn               : {changed}")

    if args.write and changed:
        import yaml  # noqa: PLC0415
        path.write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=10**6),
                        encoding="utf-8")
        print(f"written                      : {path}")
    elif args.write:
        print("written                      : nothing to do (idempotent)")
    else:
        print("dry run; pass --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
