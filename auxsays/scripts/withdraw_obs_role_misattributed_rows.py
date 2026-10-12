#!/usr/bin/env python3
"""Audited withdrawal of OBS evidence rows the repaired role authority now refuses.

AUX-028 added the OBS forum family. Its first production run counted obsproject.com thread
190590 against 31.1.2 -- but that thread is about 32.0.0 removing a flag, and it closes with
"my current solution is to just use version 31.1.2". 31.1.2 is the author's WORKAROUND, the
version that works. The `target_is_the_workaround` cue now vetoes that phrasing.

Fixing the producer does not remove a row already stored: the evidence store is append/dedupe
oriented, nothing re-evaluates a stored row, and obs_forum_thread has no revalidation adapter.
An audited withdrawal is `counted: false` with a non-empty `exclusion_reason` and the ROW KEPT
-- never a deletion (lib/evidence_loss.py).

The verdict is DERIVED, not hard-coded: every stored OBS row is re-evaluated with the shared
role authority and this script REPORTS every row that authority now refuses. It WITHDRAWS only
rows whose source URL is named on the command line, so the blast radius is visible in the
invocation. Idempotent: a row already withdrawn with this reason is left alone.

The block-scoped text edit is IMPORTED from the Acrobat withdrawal tool rather than copied. Its
selector is the one that had to learn that locating a row by URL alone takes whichever block
comes first in the file -- which withdrew a correctly accepted report in AUX-027. Two copies of
a selector are two predicates waiting to drift, so there is one.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

import collect_obs_reports as legacy_obs  # noqa: E402
from patch_collectors.base import EVIDENCE_PATH, load_evidence  # noqa: E402
from withdraw_acrobat_wrong_edition_rows import withdraw  # noqa: E402

OBS = "obs-studio"


def refused_rows(rows: list[dict]) -> list[tuple[dict, str]]:
    """Stored OBS rows the repaired role authority now refuses, with the reason it gives.

    Re-evaluated from the row's own stored text through `contradiction_reason`, the same
    predicate the collector consults at acceptance time. A row already withdrawn is skipped, so
    a second run reports nothing left to do.
    """
    out: list[tuple[dict, str]] = []
    for row in rows:
        if str(row.get("product_id") or "") != OBS:
            continue
        if row.get("counted") is False:
            continue
        version = str(row.get("update_version") or "").strip()
        if not version:
            continue
        text = " ".join(str(row.get(key) or "") for key in
                        ("report_title", "parent_title", "report_text", "report_text_excerpt"))
        reason = legacy_obs.contradiction_reason({"title": "", "body": text}, version)
        if reason:
            out.append((row, reason))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only-url", action="append", default=[],
                    help="Withdraw ONLY rows with this source_url. Repeatable.")
    ap.add_argument("--path", default=str(EVIDENCE_PATH))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    rows = load_evidence(path)
    obs_rows = [r for r in rows if str(r.get("product_id") or "") == OBS]
    refused = refused_rows(rows)
    targeted = set(args.only_url)

    print("stored OBS rows: " + str(len(obs_rows)))
    print("rows the repaired role authority now refuses: " + str(len(refused)))
    for row, reason in refused:
        url = str(row.get("source_url") or "")
        mark = "WITHDRAW   " if url in targeted else "report-only"
        print("  [" + mark + "] " + str(row.get("update_version")) + "  " + reason)
        print("                 " + str(row.get("id")))
        print("                 " + url)

    if not targeted:
        print("no --only-url given: reporting only, nothing withdrawn")
        return 0

    changed = 0
    for row, reason in refused:
        if str(row.get("source_url") or "") not in targeted:
            continue
        text, moved = withdraw(text, row, reason)
        changed += 1 if moved else 0

    print("rows moved to audited withdrawal: " + str(changed))
    if changed and args.write:
        path.write_text(text, encoding="utf-8", newline="")
        print("WROTE " + str(path))
    elif changed:
        print("dry run: pass --write to persist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
