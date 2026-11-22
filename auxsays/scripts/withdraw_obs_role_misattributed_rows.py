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

FIELD AND LINE BOUNDARIES (AUX-129). The stored text is rebuilt the way the collector read it at
acceptance: the title, a line break, then the body -- never every field run together with spaces.
Joined with spaces, a cue could bind across two fields, and rule R1 (a version the reporter
DECLARED is never vetoed) could not apply, because the issue template's version answer is found by
the line break after its heading. Stored OBS excerpts are whitespace-collapsed, so that line break
is gone from every one of them. When the authority would refuse a row whose stored text holds the
template's version heading but not that line break, the row is reported as UNDETERMINABLE -- the
stored text cannot say whether R1 protects it -- and it is never withdrawn, even when its URL is
named. obs #13518 was reported as refused only because of this loss and a hoped-for "will work"
read as a working claim (lib/target_outcome.py): the issue declares 32.1.2 and reports that it
cannot be installed. It is an install-failure report and it stays counted.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

import collect_obs_reports as legacy_obs  # noqa: E402
from patch_collectors.base import EVIDENCE_PATH, load_evidence  # noqa: E402
from withdraw_acrobat_wrong_edition_rows import withdraw  # noqa: E402

OBS = "obs-studio"

# The issue template's version heading, with or without the line break that delimits its answer.
# legacy_obs.DECLARED_VERSION_FIELDS finds the answer only when that line break survives; the
# difference between the two counts is the number of declarations the stored text has lost.
_DECLARED_VERSION_HEADING = re.compile(r"###\s*OBS Studio Version(?:\s*\(Other\))?", re.I)


def _distinct_lines(row: dict, keys: tuple[str, ...]) -> str:
    """The non-empty values of `keys`, each once, one per line: a field never runs into the next."""
    out: list[str] = []
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value and value not in out:
            out.append(value)
    return "\n".join(out)


def stored_issue(row: dict) -> dict:
    """The issue as the collector read it, rebuilt from the stored row with its boundaries kept.

    `contradiction_reason` joins title and body with a line break, as at acceptance. The body is
    the stored report text with its own line breaks; only without it, the excerpt, which is a
    whitespace-collapsed window of that same text (OBS rows store only the excerpt).
    """
    body = str(row.get("report_text") or "").strip() or str(row.get("report_text_excerpt") or "").strip()
    return {"title": _distinct_lines(row, ("report_title", "parent_title")), "body": body}


def declaration_lost(issue: dict) -> bool:
    """Does the stored text carry a template version heading whose answer it can no longer read?

    Then R1 cannot be evaluated from storage. Any such heading counts, including one whose answer
    is a different version; that errs towards UNDETERMINABLE, which is never withdrawn.

    A row with no heading at all is treated as decidable, and that is an ASSUMPTION, not a
    guarantee. The collector's excerpt opens about 90 characters before the version's first
    mention, and a declared version is normally first mentioned in the template's version field,
    so the heading normally falls inside the excerpt. A long answer to the "(Other)" field can
    push the heading out of it; such a row reads as decidable and can be refused even though R1
    would protect it. When this was written, no stored GitHub OBS row without a heading was
    refused, and the only cut heading fragment sat in one uncounted forum row.
    """
    body = str(issue.get("body") or "")
    headings = len(_DECLARED_VERSION_HEADING.findall(body))
    readable = len(legacy_obs.DECLARED_VERSION_FIELDS.findall(body))
    return headings > readable


def assess_rows(rows: list[dict]) -> tuple[list[tuple[dict, str]], list[tuple[dict, str]]]:
    """(refused, undeterminable): stored OBS rows the role authority refuses, with its reason,
    and rows it would refuse only because the stored text lost the declaration R1 reads.

    Re-evaluated from the row's own stored text through `contradiction_reason`, the same
    predicate the collector consults at acceptance time. A row already withdrawn is skipped, so
    a second run reports nothing left to do.
    """
    refused: list[tuple[dict, str]] = []
    undeterminable: list[tuple[dict, str]] = []
    for row in rows:
        if str(row.get("product_id") or "") != OBS:
            continue
        if row.get("counted") is False:
            continue
        version = str(row.get("update_version") or "").strip()
        if not version:
            continue
        issue = stored_issue(row)
        reason = legacy_obs.contradiction_reason(issue, version)
        if not reason:
            continue
        (undeterminable if declaration_lost(issue) else refused).append((row, reason))
    return refused, undeterminable


def refused_rows(rows: list[dict]) -> list[tuple[dict, str]]:
    """Stored OBS rows the repaired role authority refuses, with the reason it gives. Never a row
    whose refusal depends on a declaration the stored text lost (see `assess_rows`)."""
    return assess_rows(rows)[0]


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
    refused, undeterminable = assess_rows(rows)
    targeted = set(args.only_url)

    print("stored OBS rows: " + str(len(obs_rows)))
    print("rows the repaired role authority now refuses: " + str(len(refused)))
    for row, reason in refused:
        url = str(row.get("source_url") or "")
        mark = "WITHDRAW   " if url in targeted else "report-only"
        print("  [" + mark + "] " + str(row.get("update_version")) + "  " + reason)
        print("                 " + str(row.get("id")))
        print("                 " + url)
    print("rows UNDETERMINABLE from stored text (declared version lost its line break; "
          "never withdrawn): " + str(len(undeterminable)))
    for row, reason in undeterminable:
        print("  [undeterminable] " + str(row.get("update_version")) + "  would be " + reason)
        print("                 " + str(row.get("id")))
        print("                 " + str(row.get("source_url") or ""))

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
