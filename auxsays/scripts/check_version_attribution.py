#!/usr/bin/env python3
"""Flag counted rows whose own stored text disagrees with the version they are counted for.

    python auxsays/scripts/check_version_attribution.py [--json OUT] [--github] [--product-id ID]

Read-only. Runs `lib.version_attribution` over the accepted-evidence store and prints every counted
row that (a) names its own version as working, rolled back to, the fix or a reference, (b) names
another tracked version and not its own, or (c) is counted for a bare release line while its text
names an exact point release. It is the same code in a pull request and in the scheduled lane.

A FLAG IS A WARNING, NEVER A FAILURE. Stored excerpts are cut at about 280 characters, so a flag is a
bounded review item, not a verdict; and a bot commit must not turn main red because a collector
stored a new row (the corpus changes between a green PR and the next push). A row stops counting
only through the audited withdrawal path. This command therefore exits 0 with flags present.

Exit codes:  0 ran (flags or none)   2 the store or the records could not be read (never a pass)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import version_attribution as va  # noqa: E402
from lib.report_counts import EvidenceStoreError, load_evidence_store  # noqa: E402

ROOT = _REPO / "auxsays"
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
GENERATED_DIR = ROOT / "updates" / "generated"
EXIT_OK = 0
EXIT_UNREADABLE = 2
MAX_SHOWN = 60

_FM_FIELD = re.compile(r"^(product_id|update_version|target_build):\s*(.*)$", re.M)


def load_record_identities(generated_dir: Path = GENERATED_DIR) -> list[dict[str, str]]:
    """(product_id, update_version, target_build) of every generated record, from its front matter."""
    out: list[dict[str, str]] = []
    for path in sorted(generated_dir.glob("*.md")):
        head = path.read_text(encoding="utf-8", errors="replace").split("\n---", 1)[0]
        fields = {name: value.strip().strip("'\"") for name, value in _FM_FIELD.findall(head)}
        if fields.get("product_id"):
            out.append(fields)
    return out


def render(flags: list[va.Flag], *, examined: int, shown: int = MAX_SHOWN) -> list[str]:
    summary = va.summarise(flags)
    lines = [f"version attribution guard: {examined} counted rows examined, "
             f"{summary['rows']} flagged ({summary['flags']} flags)"]
    for code in va.FLAG_ORDER:
        lines.append(f"  {code}: {summary['by_code'][code]}")
    for product, counts in summary["by_product"].items():
        lines.append(f"  {product}: " + ", ".join(f"{code} {n}" for code, n in counts.items()))
    for f in flags[:shown]:
        mark = " [stored text truncated]" if f.truncated else ""
        target = f.update_version + (f" build {f.target_build}" if f.target_build else "")
        lines.append(f"- {f.code} | {f.product_id} {target} | {f.row_id} | {f.detail}{mark}")
    if len(flags) > shown:
        lines.append(f"... and {len(flags) - shown} more (use --json for all)")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--evidence-path", default=str(EVIDENCE_PATH))
    ap.add_argument("--generated-dir", default=str(GENERATED_DIR))
    ap.add_argument("--product-id", default="", help="report one product only (the vocabulary is "
                    "still built from the whole corpus)")
    ap.add_argument("--json", default="", help="write every flag to this file")
    ap.add_argument("--github", action="store_true",
                    help="emit one ::warning:: and append the report to $GITHUB_STEP_SUMMARY")
    args = ap.parse_args(argv)

    try:
        rows = load_evidence_store(Path(args.evidence_path))
        records = load_record_identities(Path(args.generated_dir))
    except (EvidenceStoreError, OSError) as exc:
        print(f"::error::version attribution guard: {exc}")
        return EXIT_UNREADABLE

    flags = va.assess_corpus(rows, records)
    counted = [r for r in rows if r.get("counted") is True]
    if args.product_id:
        flags = [f for f in flags if f.product_id == args.product_id]
        counted = [r for r in counted if r.get("product_id") == args.product_id]
    lines = render(flags, examined=len(counted))
    print("\n".join(lines))

    if args.json:
        payload = {"examined": len(counted), "summary": va.summarise(flags),
                   "flags": [f.as_dict() for f in flags]}
        Path(args.json).write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n",
                                   encoding="utf-8")
    if args.github:
        summary = va.summarise(flags)
        if flags:
            print(f"::warning::version attribution guard: {summary['rows']} counted row(s) whose "
                  f"stored text disagrees with the version they are counted for (review items; "
                  f"nothing was withdrawn)")
        target = os.environ.get("GITHUB_STEP_SUMMARY")
        if target:
            with open(target, "a", encoding="utf-8") as handle:
                handle.write("### Version attribution guard\n\n```\n" + "\n".join(lines) + "\n```\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
