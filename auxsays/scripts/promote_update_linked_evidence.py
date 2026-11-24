#!/usr/bin/env python3
"""Promote an update-linked (second-tier) report to a counted report when its own stored facts earn it.

    python auxsays/scripts/promote_update_linked_evidence.py --product-id microsoft-powerpoint
    python auxsays/scripts/promote_update_linked_evidence.py --product-id adobe-acrobat-pro --write

Second-tier reports are real user reports whose exact build was never established. They sit in
their own file, shown and counted nowhere (lib/tier2_evidence.py). Until now a report left that file
only if a collector happened to find the same thread again and the strict authority accepted it.
A held report had no route of its own.

THE CONDITION. A held report is promoted when, and only when, the product's OWN acceptance authority
-- the collector's unchanged `evaluate_candidates`, the function every scheduled run uses -- accepts
a candidate rebuilt from nothing but the row's stored facts (title, stored excerpt, date, link) for
EXACTLY ONE tracked patch. That is the same exact-version, dated, linked, concrete-problem test a
first-tier report passes; no gate is skipped and none is reworded. Accepted for two patches is
refused, not resolved. The release window a second-tier row was associated with is never an input:
a window is a date inference, and a date never establishes a version.

THE WRITE. The accepted row goes through the store's own append guard (`append_evidence_rows`), so
a report the store already holds for that patch -- counted or withdrawn -- is not added again. Its
`capture_method` records where it came from (`promoted_from_update_linked:<report id>`), and the
held row then leaves the second-tier file by the existing confirmation path, so one report is
never visible in both tiers. The store is only appended to; no stored row changes.

Product scope is REQUIRED and is one product. Zero network. Idempotent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

import yaml  # noqa: E402

from lib.patch_identity import patch_key  # noqa: E402
from lib.source_segments import report_url_key  # noqa: E402
from patch_collectors import adobe_acrobat_community as acrobat  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import (  # noqa: E402
    EVIDENCE_PATH, ROOT, PatchRecord, append_evidence_rows, atomic_write_text, generated_records,
    load_evidence,
)

POWERPOINT_TIER2 = ROOT / "_data" / "update_linked_evidence.yml"
ACROBAT_TIER2 = acrobat.TIER2_PATH
AUDIT_PREFIX = "promoted_from_update_linked:"
Identity = tuple[str, str, str]


def close_append_gap(path: Path) -> None:
    """Remove the blank line the store's append path leaves before an appended batch.

    `append_evidence_rows` joins the existing text and the new rows with a newline; on a store that
    already ends in one, that is an empty line between two rows. The stored format has none, and
    the text between two rows is read as the earlier row's facts. Only a blank line directly before
    a row is removed; no row changes.
    """
    text = path.read_text(encoding="utf-8")
    closed = text.replace("\n\n- id: ", "\n- id: ")
    if closed != text:
        atomic_write_text(path, closed)


def candidate_from_held(row: dict[str, Any]) -> dict[str, Any]:
    """A held row as a collector candidate. Only stored facts; the stored excerpt is the body."""
    title = str(row.get("report_title") or "")
    return {
        "source_type": str(row.get("source_type") or ""),
        "source_name": str(row.get("source_family") or ""),
        "source_url": str(row.get("source_url") or ""),
        "parent_title": title, "report_title": title,
        "report_text": str(row.get("report_excerpt") or ""),
        "source_date": str(row.get("report_date") or ""),
    }


def _powerpoint_accepts(product_id: str, records: list[PatchRecord], candidate: dict[str, Any],
                        captured_at: str) -> list[dict[str, Any]]:
    ambiguous = ppt.compute_ambiguous_identities(records)
    accepted: list[dict[str, Any]] = []
    for record in records:
        target = ppt.record_target(record)
        target["version_ambiguous"] = (
            target["target_app_version"] or target["update_version"],
            ppt._norm_channel(target["target_channel"])) in ambiguous
        # A fresh `seen` and no run map per record: each record judges the candidate on its own,
        # and "exactly one patch" is decided below, over all of them, instead of by run order.
        ok, _rejected = ppt.evaluate_candidates(record, target, [dict(candidate)], captured_at,
                                               seen=set(), run_accepted_urls=None)
        accepted.extend(ok)
    return accepted


def _acrobat_accepts(product_id: str, records: list[PatchRecord], candidate: dict[str, Any],
                     captured_at: str) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for record in records:
        ok, _rejected = acrobat.evaluate_candidates(product_id, record, [dict(candidate)], captured_at)
        accepted.extend(ok)
    return accepted


PRODUCTS: dict[str, tuple[Path, Callable[..., list[dict[str, Any]]]]] = {
    ppt.PRODUCT_ID: (POWERPOINT_TIER2, _powerpoint_accepts),
    acrobat.READER_ID: (ACROBAT_TIER2, _acrobat_accepts),
    acrobat.PRO_ID: (ACROBAT_TIER2, _acrobat_accepts),
}


def load_tier_file(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(the whole document, its report rows). A missing file is an empty tier, not an error."""
    if not path.exists():
        return {}, []
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict) or not isinstance(doc.get("reports", []), list):
        raise SystemExit(f"refusing: {path} is not a mapping with a 'reports' list")
    return doc, [r for r in doc.get("reports") or [] if isinstance(r, dict)]


def dump_tier_file(doc: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    """The file as its own writers produce it: header keys first, rows key-sorted, width 100."""
    payload = {k: v for k, v in doc.items() if k != "reports"}
    payload["reports"] = [dict(sorted(r.items())) for r in rows]
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100)


def assess(product_id: str, held: list[dict[str, Any]], records: list[PatchRecord],
           accepts: Callable[..., list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """One entry per held row of this product: what the strict authority says of its stored facts."""
    out: list[dict[str, Any]] = []
    for row in held:
        if row.get("product_id") != product_id:
            continue
        entry: dict[str, Any] = {"report_id": str(row.get("report_id") or ""),
                                 "source_url": str(row.get("source_url") or ""),
                                 "classification": str(row.get("classification") or ""),
                                 "outcome": "not_accepted", "row": None, "identities": []}
        if not entry["report_id"] or not entry["source_url"] or not row.get("report_date"):
            entry["outcome"] = "missing_stored_fact"
            out.append(entry)
            continue
        accepted = accepts(product_id, records, candidate_from_held(row),
                           str(row.get("captured_at") or ""))
        identities: dict[Identity, dict[str, Any]] = {}
        for item in accepted:
            identities.setdefault(patch_key(item.get("product_id"), item.get("update_version"),
                                            item.get("target_build")), item)
        entry["identities"] = ["|".join(key) for key in identities]
        if len(identities) == 1:
            promoted = dict(next(iter(identities.values())))
            promoted["capture_method"] = AUDIT_PREFIX + entry["report_id"]
            entry["outcome"] = "qualifies"
            entry["row"] = promoted
        elif len(identities) > 1:
            entry["outcome"] = "accepted_for_more_than_one_patch"
        out.append(entry)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--product-id", required=True, choices=sorted(PRODUCTS),
                    help="the ONE product to promote for; there is no all-products mode")
    ap.add_argument("--write", action="store_true", help="apply; without it nothing is written")
    ap.add_argument("--json", default="", help="write the assessment to this file")
    ap.add_argument("--evidence-path", default=str(EVIDENCE_PATH), help=argparse.SUPPRESS)
    ap.add_argument("--tier2-path", default="", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    product_id = args.product_id
    default_path, accepts = PRODUCTS[product_id]
    tier_path = Path(args.tier2_path) if args.tier2_path else default_path
    evidence_path = Path(args.evidence_path)
    doc, held = load_tier_file(tier_path)
    records = generated_records(product_id, None)
    entries = assess(product_id, held, records, accepts)

    outcomes: dict[str, int] = {}
    for entry in entries:
        outcomes[entry["outcome"]] = outcomes.get(entry["outcome"], 0) + 1
    qualifying = [e for e in entries if e["outcome"] == "qualifies"]
    print(f"{product_id}: {len(entries)} held second-tier reports examined against "
          f"{len(records)} tracked patches; {len(qualifying)} qualify")
    for name in sorted(outcomes):
        print(f"  {name}: {outcomes[name]}")
    for entry in qualifying:
        print(f"- {entry['identities'][0]} <- {entry['source_url']}")

    promoted_ids: list[str] = []
    added: list[dict[str, Any]] = []
    already: list[dict[str, Any]] = []
    if args.write and qualifying:
        append_evidence_rows([e["row"] for e in qualifying], evidence_path,
                             out_added=added, out_already_held=already)
        close_append_gap(evidence_path)
        # A held row leaves the second tier only when the store now COUNTS that report: the row
        # just added, or a counted row the store already held for it. A report the store holds
        # withdrawn stays where it is, visible and uncounted.
        counted_urls = {report_url_key(str(r.get("source_url") or ""))
                        for r in load_evidence(evidence_path)
                        if r.get("product_id") == product_id and r.get("counted") is True}
        evict = {e["report_id"] for e in qualifying
                 if report_url_key(e["source_url"]) in counted_urls}
        promoted_ids = sorted(evict)
        if evict:
            kept = [r for r in held if str(r.get("report_id") or "") not in evict]
            tier_path.write_text(dump_tier_file(doc, kept), encoding="utf-8", newline="\n")
        print(f"appended {len(added)} counted row(s), {len(already)} already held by the store; "
              f"{len(promoted_ids)} left the second tier")
    elif not args.write:
        print("report only (pass --write to apply)")

    if args.json:
        payload = {"product_id": product_id, "examined": len(entries), "patches": len(records),
                   "outcomes": outcomes, "written": bool(args.write),
                   "appended": [r.get("id") for r in added], "promoted_out": promoted_ids,
                   "qualifying": [{"report_id": e["report_id"], "source_url": e["source_url"],
                                   "patch": e["identities"][0]} for e in qualifying],
                   "refused_for_more_than_one_patch": [
                       {"report_id": e["report_id"], "patches": e["identities"]}
                       for e in entries if e["outcome"] == "accepted_for_more_than_one_patch"]}
        Path(args.json).write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n",
                                   encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
