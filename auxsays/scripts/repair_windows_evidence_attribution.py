#!/usr/bin/env python3
"""Apply measured Windows corrections to evidence ALREADY stored.

Both corrections ship in `patch_collectors/microsoft_windows.py`, and both only reach rows
collected AFTER they ship: `append_evidence_rows` refuses a source_url that already exists, so a
stored row is never revisited by ordinary collection. Without this script the corrections would be
true of new evidence and false of the evidence already on the live pages.

  A. FOREIGN-PRODUCT SUBJECT. A counted row whose title's subject is a separately-updated product
     -- "SQL Server 2022 Database Engine Recovery Handle Failed", "I got an error during HLK client
     installation", "Images are not displayed ... in classic Outlook" -- is retracted. It keeps its
     target_build: a stored uncounted row with no build groups under (product, version, ''), an
     identity no record has, which is how an earlier repair of these rows ADDED two audit errors.

  B. STOP-ERROR THEME. `classify` used to treat any hex token as a bugcheck, so every update
     failure reporting 0x800f0991 was published as "BSOD / stop error" at severity `critical`.
     Measured live: 32 rows carried that theme and only 5 contained any stop-error vocabulary.
     A row is reclassified ONLY when the evidence AUXSAYS itself publishes -- the stored title and
     excerpt -- contains no stop-error vocabulary, so the correction can never contradict the text
     a reader can see, and it is reproducible from the committed file alone. Reclassifying from the
     full thread instead was measured and rejected: the stored excerpt disagrees with the full text
     on 44 of 105 rows, so a full-text pass would silently rewrite themes this defect never touched.

  C. NO OPENING POST. A Tech Community page that serves no QAPage/mainEntity made
     `thread_candidate` fall through to the og:title meta, so the row's whole text became the
     browser TAB title. One reached production and was counted for build 26200.8655 on the words
     "hang" and "bugcheck" in that title -- whose actual claim is "(Z790, 26200.8655 clean)", the
     reporter naming that build as the one WITHOUT the defect.

Dry-run by default. Parts A and C are safe to re-run forever and should report zero, because the
collectors now enforce the same rules; a non-zero result means something escaped a gate. Part B is a
ONE-SHOT migration behind an explicit flag -- see ``run`` for why re-running it would demote genuine
reports.

    python auxsays/scripts/repair_windows_evidence_attribution.py                    # report only
    python auxsays/scripts/repair_windows_evidence_attribution.py --write            # part A
    python auxsays/scripts/repair_windows_evidence_attribution.py --write \
        --reclassify-stop-errors                                                     # A + the one-shot
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors.base import EVIDENCE_PATH, atomic_write_text  # noqa: E402

FOREIGN_REASON = "foreign_product_subject_not_windows_patch"
STOP_ERROR_THEME = "BSOD / stop error"
NO_OPENING_POST_REASON = "no_opening_post_extracted"
# The fingerprint of a Tech Community page that served no QAPage/mainEntity: `thread_candidate`
# fell through to the og:title meta, so the row's whole text is the browser TAB title -- title,
# parent_title and excerpt all identical, ending in the site's tab suffix. That shape cannot occur
# on any other source, which is what makes this safe to apply to stored rows: a Learn Q&A report
# short enough for its excerpt to equal its title is a real report and is not matched.
TAB_TITLE_SUFFIX = "| Microsoft Community Hub"
TECHCOMMUNITY_SOURCE_TYPE = "microsoft_tech_community"


def row_text(row: dict[str, Any]) -> str:
    """The same three fields `row_from_candidate` classifies, as the stored row preserves them."""
    return " ".join([
        str(row.get("parent_title") or ""),
        str(row.get("report_title") or ""),
        str(row.get("report_text_excerpt") or ""),
    ]).strip()


def retract_foreign_subject(row: dict[str, Any]) -> bool:
    if str(row.get("product_id") or "") != mw.PRODUCT_ID or row.get("counted") is not True:
        return False
    if not mw.foreign_product_subject(str(row.get("report_title") or ""),
                                     str(row.get("matched_kb") or ""),
                                     str(row.get("matched_os_build") or "")):
        return False
    row["counted"] = False
    row["exclusion_reason"] = FOREIGN_REASON
    row["evidence_valid_for_current_patch"] = False
    return True


def retract_no_opening_post(row: dict[str, Any]) -> bool:
    """A stored row that is only a page title. See TAB_TITLE_SUFFIX for the fingerprint.

    Like the foreign-subject retraction, this mirrors a rule the collector now enforces
    (`techcommunity_source.thread_candidate` refuses a body-less thread), so re-running it should
    report zero and a non-zero result means something escaped the gate.
    """
    if str(row.get("product_id") or "") != mw.PRODUCT_ID or row.get("counted") is not True:
        return False
    if str(row.get("source_type") or "") != TECHCOMMUNITY_SOURCE_TYPE:
        return False
    title = " ".join(str(row.get("report_title") or "").split())
    excerpt = " ".join(str(row.get("report_text_excerpt") or "").split())
    if not title.endswith(TAB_TITLE_SUFFIX) or excerpt != title:
        return False
    row["counted"] = False
    row["exclusion_reason"] = NO_OPENING_POST_REASON
    row["evidence_valid_for_current_patch"] = False
    return True


def reclassify_stop_error(row: dict[str, Any]) -> bool:
    if str(row.get("product_id") or "") != mw.PRODUCT_ID:
        return False
    if str(row.get("issue_theme") or "") != STOP_ERROR_THEME:
        return False
    text = row_text(row)
    if any(token in text.lower() for token in mw.BSOD_VOCABULARY):
        return False  # the published text supports the claim; leave it alone
    theme, workflow_area, platform, severity, sentiment = mw.classify(text)
    if theme == STOP_ERROR_THEME:
        return False
    row["issue_theme"] = theme
    row["workflow_area"] = workflow_area
    row["platform"] = platform
    row["severity"] = severity
    row["sentiment"] = sentiment
    return True


def load_raw(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rows EXACTLY as committed -- deliberately not through ``normalize_evidence_row``.

    The canonical writer normalizes every row it serializes, and normalization drops keys whose
    value is null. Rewriting the whole file through it would therefore delete `source_date`,
    `target_release_date` and `source_date_pass` from 185 rows belonging to five other products --
    a silent, repo-wide schema change made by a Windows repair. Production never re-normalizes
    stored rows either: `append_evidence_rows` appends serialized text to the existing file. So
    this reads and writes the raw mapping and touches only the rows it reports.
    """
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return {"schema_version": 1}, [item for item in payload if isinstance(item, dict)]
    rows = payload.get("evidence") or []
    return payload, [item for item in rows if isinstance(item, dict)]


def run(write: bool, path: Path = EVIDENCE_PATH, reclassify: bool = False) -> dict[str, Any]:
    """Part A always; part B only when asked.

    THE TWO PARTS ARE NOT THE SAME KIND OF THING. Retraction enforces a rule the collector now
    enforces too, so re-running it is safe forever and a non-zero result means something escaped
    the gate. Reclassification is a ONE-SHOT historical correction whose evidence is the stored
    280-char excerpt, because a migration cannot re-read the source. The collector classifies from
    the whole thread, so the two rules legitimately disagree on rows collected since -- measured at
    7 of 1050 the day after the fix shipped -- and re-running part B would demote genuine
    stop-error reports whose stop code sits past the excerpt. It stays behind an explicit flag so
    that cannot happen by accident.
    """
    payload, rows = load_raw(path)
    retracted: list[dict[str, str]] = []
    reclassified: list[dict[str, str]] = []
    for row in rows:
        before_theme = str(row.get("issue_theme") or "")
        if retract_foreign_subject(row) or retract_no_opening_post(row):
            retracted.append({"update_version": str(row.get("update_version") or ""),
                              "target_build": str(row.get("target_build") or ""),
                              "source_url": str(row.get("source_url") or ""),
                              "exclusion_reason": str(row.get("exclusion_reason") or ""),
                              "report_title": str(row.get("report_title") or "")[:100]})
        if reclassify and reclassify_stop_error(row):
            reclassified.append({"update_version": str(row.get("update_version") or ""),
                                 "target_build": str(row.get("target_build") or ""),
                                 "from": before_theme,
                                 "to": str(row.get("issue_theme") or ""),
                                 "report_title": str(row.get("report_title") or "")[:100]})
    result = {
        "mode": "write" if write else "dry-run",
        "evidence_rows": len(rows),
        "retracted": len(retracted),
        "retracted_foreign_subject": sum(
            1 for r in retracted if r["exclusion_reason"] == FOREIGN_REASON),
        "retracted_no_opening_post": sum(
            1 for r in retracted if r["exclusion_reason"] == NO_OPENING_POST_REASON),
        "reclassified_stop_error": len(reclassified),
        "retracted_rows": retracted,
        "reclassified": reclassified,
    }
    if write and (retracted or reclassified):
        payload["evidence"] = rows
        atomic_write_text(path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True,
                                               width=1000))
        result["written"] = str(path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Apply the repair (default: report only).")
    parser.add_argument("--evidence-path", default=str(EVIDENCE_PATH))
    parser.add_argument("--reclassify-stop-errors", action="store_true",
                        help="Also run the ONE-SHOT stop-error reclassification (see run()).")
    args = parser.parse_args(argv)
    result = run(args.write, Path(args.evidence_path), reclassify=args.reclassify_stop_errors)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
