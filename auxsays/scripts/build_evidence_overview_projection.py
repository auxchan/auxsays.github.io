#!/usr/bin/env python3
"""Write the evidence overview projection for the patch page, at deploy time (G82-A, AUX-123).

`_includes/patch-evidence-overview.html` prints, per patch page, only what this file writes to
`_data/evidence_overview_projection.yml`: the counted report population stated as a count, its source
families, what the report list does and does not establish, and a newer release in the same servicing
line. See lib/evidence_overview for the contract.

POSITION IS LOAD-BEARING. pages.yml runs this after the verdict projection and BEFORE
`qa_patch_records.py --publish-strict` (which compares this file with a recompute and errors on any
difference, and on a deploy that built the verdict projection but not this one) and BEFORE
`jekyll build` (which renders it).

FAILURE. Any failure writes an EMPTY projection carrying the error and exits 0 with a ::warning::.
Rendered, that is fail closed: no page prints an overview or a newer-release note. It is not silent:
QA reports the failed build as an ERROR, so a deploy cannot quietly drop them.

GENERATED AT DEPLOY, NEVER COMMITTED (git-ignored).

Run:  python auxsays/scripts/build_evidence_overview_projection.py [--root DIR] [--output FILE]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run as a bare script by pages.yml: `lib` and `patch_collectors` live beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import evidence_overview  # noqa: E402
from patch_collectors.base import atomic_write_text  # noqa: E402

AUX = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=AUX,
                    help="the site tree to read (default: this repository's auxsays/)")
    ap.add_argument("--output", type=Path, default=None,
                    help=f"where to write (default: <root>/_data/{evidence_overview.PROJECTION_NAME})")
    args = ap.parse_args(argv)
    output = args.output or (args.root / "_data" / evidence_overview.PROJECTION_NAME)
    try:
        projection, problems = evidence_overview.build(args.root)
    except Exception as exc:  # noqa: BLE001 - deliberately broad; see FAILURE above
        print(f"::warning::evidence overview projection is EMPTY, so no page prints an overview: "
              f"{type(exc).__name__}: {exc}")
        projection = {"schema_version": evidence_overview.SCHEMA_VERSION,
                      "rule_version": evidence_overview.RULE_VERSION, "pages": {},
                      "error": f"{type(exc).__name__}: {exc}"}
        problems = []
    for problem in problems:
        print(f"::warning::{problem}")
    atomic_write_text(output, evidence_overview.render(projection))
    pages = projection.get("pages") or {}
    overview = sum(1 for row in pages.values() if row.get("count_line"))
    newer = sum(1 for row in pages.values() if row.get("newer"))
    assessed = sorted({row.get("assessment") for row in pages.values() if row.get("assessment")})
    print(f"Wrote {output}: {len(pages)} page(s); {overview} with an evidence overview, {newer} with a newer "
          f"release; reviewed findings shown: {', '.join(assessed) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
