#!/usr/bin/env python3
"""Apply two measured Windows corrections to evidence ALREADY stored.

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

Idempotent: a second run changes nothing. Dry-run by default.

    python auxsays/scripts/repair_windows_evidence_attribution.py            # report only
    python auxsays/scripts/repair_windows_evidence_attribution.py --write    # apply
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


def run(write: bool, path: Path = EVIDENCE_PATH) -> dict[str, Any]:
    payload, rows = load_raw(path)
    retracted: list[dict[str, str]] = []
    reclassified: list[dict[str, str]] = []
    for row in rows:
        before_theme = str(row.get("issue_theme") or "")
        if retract_foreign_subject(row):
            retracted.append({"update_version": str(row.get("update_version") or ""),
                              "target_build": str(row.get("target_build") or ""),
                              "source_url": str(row.get("source_url") or ""),
                              "report_title": str(row.get("report_title") or "")[:100]})
        if reclassify_stop_error(row):
            reclassified.append({"update_version": str(row.get("update_version") or ""),
                                 "target_build": str(row.get("target_build") or ""),
                                 "from": before_theme,
                                 "to": str(row.get("issue_theme") or ""),
                                 "report_title": str(row.get("report_title") or "")[:100]})
    result = {
        "mode": "write" if write else "dry-run",
        "evidence_rows": len(rows),
        "retracted_foreign_subject": len(retracted),
        "reclassified_stop_error": len(reclassified),
        "retracted": retracted,
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
    args = parser.parse_args(argv)
    result = run(args.write, Path(args.evidence_path))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
