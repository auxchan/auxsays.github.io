#!/usr/bin/env python3
"""Write lib/patch_decision.decide's reasoned verdicts for the Liquid gate, at deploy time.

`_includes/patch-verdict-gate.html` publishes WAIT, TEST FIRST and a security page's warning panel
ONLY from `_data/verdict_projection.yml`, the file this writes: per page, the verdict, scope, line
and panel Python decided from the counted evidence and the reviewed reason entries. The gate never
evaluates an entry itself (GROWTH-3 review 1, D2: a Liquid copy of the support rule published
verdicts `decide` refused). See lib/verdict_projection for the contract.

POSITION IS LOAD-BEARING. pages.yml runs this after the inputs are final and BEFORE
`qa_patch_records.py --publish-strict` (which compares the file with `decide` and errors on any
difference) and BEFORE `jekyll build` (which renders it).

FAILURE. An unreadable evidence store, or any failure while deciding, writes an EMPTY projection
carrying the error and exits 0 with a ::warning::. Rendered, that is fail closed: no page publishes
a WAIT or TEST FIRST. It is not silent: QA then reports every page the authority would have given
one as an ERROR, so a deploy cannot quietly drop them.

GENERATED AT DEPLOY, NEVER COMMITTED (git-ignored).

Run:  python auxsays/scripts/build_verdict_projection.py [--root DIR] [--output FILE]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run as a bare script by pages.yml: `lib` and `patch_collectors` live beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import verdict_projection  # noqa: E402
from patch_collectors.base import atomic_write_text  # noqa: E402

AUX = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=AUX,
                    help="the site tree to read (default: this repository's auxsays/)")
    ap.add_argument("--output", type=Path, default=None,
                    help=f"where to write (default: <root>/_data/{verdict_projection.PROJECTION_NAME})")
    args = ap.parse_args(argv)
    output = args.output or (args.root / "_data" / verdict_projection.PROJECTION_NAME)
    try:
        projection, unsupported, problems = verdict_projection.build(args.root)
    except Exception as exc:  # noqa: BLE001 - deliberately broad; see FAILURE above
        print(f"::warning::verdict projection is EMPTY, so no page publishes WAIT or TEST FIRST: "
              f"{type(exc).__name__}: {exc}")
        projection = {"schema_version": verdict_projection.SCHEMA_VERSION, "pages": {},
                      "error": f"{type(exc).__name__}: {exc}"}
        unsupported, problems = {}, []
    for problem in problems:
        print(f"::warning::verdict fact file refused, it supports nothing: {problem}")
    for reason_id, why in sorted(unsupported.items()):
        print(f"{reason_id}: not supported ({'; '.join(why)})")
    atomic_write_text(output, verdict_projection.render(projection))
    pages = projection.get("pages") or {}
    print(f"Wrote {output}: {len(pages)} page(s) with a supported reason entry, "
          f"{len(unsupported)} entr{'y' if len(unsupported) == 1 else 'ies'} unsupported")
    for key, row in pages.items():
        print(f"  {row.get('url') or key}: {verdict_projection.phrase(row.get('verdict', ''), row.get('scope', ''))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
