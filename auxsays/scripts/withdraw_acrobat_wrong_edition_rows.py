#!/usr/bin/env python3
"""Audited withdrawal of Acrobat evidence rows the repaired edition authority now refuses.

AUX-027 fixed PRO_RE so a bare "Acrobat DC Pro" is recognised as Pro. Fixing the producer does not
remove a row already in the store: the evidence store is append/dedupe oriented and nothing
re-evaluates a stored row. An audited withdrawal is `counted: false` with a non-empty
`exclusion_reason` and the ROW KEPT -- never a deletion (lib/evidence_loss.py).

The verdict is DERIVED, not hard-coded: every stored Acrobat row is re-evaluated with the repaired
`acrobat_edition_attribution`, and this script REPORTS every row that authority now refuses. It
WITHDRAWS only rows whose source URL is named on the command line, so the blast radius is visible
in the invocation. Idempotent: a row already withdrawn with this reason is left alone.

The edit is a block-scoped TEXT edit. Re-serialising the store through the canonical writer
normalizes every row and drops null keys, which rendered as 44 insertions / 276 deletions across a
file where exactly one row should move. An audited withdrawal has to read as one row changing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from patch_collectors.adobe_acrobat_community import acrobat_edition_attribution  # noqa: E402
from patch_collectors.base import EVIDENCE_PATH, load_evidence  # noqa: E402

ACROBAT = ("adobe-acrobat-reader", "adobe-acrobat-pro")

EOL = chr(10)
NEW_ROW = EOL + "- id:"
COUNTED_TRUE = EOL + "  counted: true" + EOL
COUNTED_FALSE = EOL + "  counted: false" + EOL
REASON_NULL = EOL + "  exclusion_reason: null" + EOL


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
        # Only an EXPLICIT opposite-edition refusal is actionable. generic_acrobat_without_edition
        # is not a refusal at all -- the shared-DC-build policy legitimately counts those, and
        # treating them as failures would withdraw most of the Acrobat corpus.
        if not attributed and reason == "wrong_product":
            out.append((row, reason))
    return out


def withdraw(text: str, url: str, reason: str) -> tuple[str, bool]:
    """Flip counted/exclusion_reason inside ONE row block. Returns (text, changed)."""
    anchor = text.index(url)
    start = text.rindex(NEW_ROW, 0, anchor) + 1
    nxt = text.find(NEW_ROW, anchor)
    end = nxt + 1 if nxt != -1 else len(text)
    block = text[start:end]
    if COUNTED_FALSE in block and (EOL + "  exclusion_reason: " + reason + EOL) in block:
        return text, False
    if COUNTED_TRUE not in block:
        raise SystemExit("refusing: unexpected counted shape for " + url)
    if REASON_NULL not in block:
        raise SystemExit("refusing: unexpected exclusion_reason shape for " + url)
    block = block.replace(COUNTED_TRUE, COUNTED_FALSE, 1)
    block = block.replace(REASON_NULL, EOL + "  exclusion_reason: " + reason + EOL, 1)
    return text[:start] + block + text[end:], True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only-url", action="append", default=[],
                    help="substring of a source_url to withdraw; repeatable")
    ap.add_argument("--path", default=str(EVIDENCE_PATH))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.path)
    rows = load_evidence(path)
    refused = refused_rows(rows)

    print("stored rows                  : " + str(len(rows)))
    print("acrobat rows the authority now refuses as wrong_product: " + str(len(refused)))
    for row, reason in refused:
        url = str(row.get("source_url") or "")
        mark = "WITHDRAW" if any(u in url for u in args.only_url) else "report-only"
        print("  [" + mark.ljust(11) + "] " + str(row.get("product_id")) + " "
              + str(row.get("update_version")) + " " + reason)
        print("                 " + url)

    text = path.read_text(encoding="utf-8")
    changed = 0
    for row, reason in refused:
        url = str(row.get("source_url") or "")
        if not any(u in url for u in args.only_url):
            continue
        text, did = withdraw(text, url, reason)
        changed += 1 if did else 0
    print("rows withdrawn               : " + str(changed))

    if args.write and changed:
        path.write_text(text, encoding="utf-8", newline="")
        print("written                      : " + str(path))
    elif args.write:
        print("written                      : nothing to do (idempotent)")
    else:
        print("dry run; pass --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
