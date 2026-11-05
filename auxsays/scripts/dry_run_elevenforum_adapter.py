#!/usr/bin/env python3
"""Zero-write dry run of the Windows 11 Forum discovery adapter.

Runs discovery, then the UNCHANGED Windows authority (``microsoft_windows.evaluate_candidates``) over
every Windows record, and prints what would be accepted and rejected, with reasons. It never calls
``append_evidence_rows``, never writes ``_data`` or any record, and PROVES that: it hashes every file
under ``_data`` and ``updates/generated`` before and after, and exits nonzero if either differs.

    cd auxsays/scripts
    python dry_run_elevenforum_adapter.py                      # replay the recorded fixtures (offline)
    python dry_run_elevenforum_adapter.py --targets synthetic  # the two fixed targets the tests use
    python dry_run_elevenforum_adapter.py --live               # BOUNDED live sample, same 49-request cap

Offline replay is the default and makes no network request. ``--live`` goes through the real paced,
capped ``Session`` and is clearly marked as a live sample in the output; it is for the human running
it, and nothing in CI uses it.

Run as a bare script (no package import of this file), like the collectors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from patch_collectors import elevenforum_source as ef  # noqa: E402
from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors.base import (  # noqa: E402
    GENERATED_DIR, ROOT, PatchRecord, WINDOWS_PRODUCT_ID, generated_records, load_evidence, utc_now,
)

FIXTURES = _HERE / "tests" / "fixtures" / "elevenforum"
WRITE_SURFACES = (ROOT / "_data", GENERATED_DIR)
# The thread the shared authority USED to attribute to the wrong patch (AUX-063, resolved by AUX-067:
# it is now rejected as identity_not_the_subject). Kept as a tripwire: if it is ever accepted again, the
# report flags it as `known_misattribution` and the adapter test fails.
KNOWN_MISATTRIBUTION_THREAD = "50506"

# The two targets the authority produced from the real 26H2/25H2 records on 2026-11-04, kept as
# literals so the offline report does not drift when the live records roll over.
SYNTHETIC_TARGETS: tuple[tuple[str, str, dict[str, str]], ...] = (
    ("26H2", "26300.9711", {
        "target_feature_version": "26H2", "target_kb": "KB5127648", "target_os_build": "26300.9711",
        "target_release_date": "2026-10-13T00:00:00Z", "update_version": "26H2"}),
    ("25H2", "26200.9711", {
        "target_feature_version": "25H2", "target_kb": "KB5127648", "target_os_build": "26200.9711",
        "target_release_date": "2026-10-13T00:00:00Z", "update_version": "25H2"}),
)


def tree_digest(roots: tuple[Path, ...]) -> str:
    h = hashlib.sha256()
    for root in roots:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            h.update(str(path.relative_to(root)).encode())
            h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


class FixtureTransport:
    """URL -> recorded page, offline.

    A listing page that was never recorded is served as an EMPTY listing (HTTP 200, no threads), which
    is what ends a category walk; it is counted in ``unrecorded_listing_pages`` and reported, so the
    output never implies the forum itself had no further pages. An unrecorded THREAD answers 404."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.unrecorded_listing_pages: list[str] = []

    def __call__(self, url: str) -> tuple[int, str]:
        kind = ef.classify_url(url)
        name = ""
        if kind == "listing":
            path = url.split("/questions/", 1)[1].strip("/")
            cat, _, page = path.partition("/page-")
            name = f"listing_{cat}_p{page or 1}.html"
        elif kind == "thread":
            name = f"thread_{ef.thread_id_of(url)}.html"
        target = self.directory / name if name else None
        if target is not None and target.is_file():
            return 200, target.read_text(encoding="utf-8")
        if kind == "listing":
            self.unrecorded_listing_pages.append(url)
            return 200, '<!DOCTYPE html><html id="XF"><head><title>Listing</title></head><body></body></html>'
        return 404, ""


class _Clock:
    """A fake clock whose sleep only advances it, so the replay is instant but the gaps are real."""
    def __init__(self) -> None:
        self.now = 1000.0
    def time(self) -> float:
        return self.now
    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _targets(mode: str) -> list[tuple[PatchRecord, dict[str, Any]]]:
    if mode == "synthetic":
        out = []
        for version, build, target in SYNTHETIC_TARGETS:
            rec = PatchRecord(WINDOWS_PRODUCT_ID, version, Path(f"synthetic-{version}.md"),
                              target["target_release_date"], "current", "Windows 11", build)
            out.append((rec, target))
        return out
    records = sorted(generated_records(WINDOWS_PRODUCT_ID, include_archived=True),
                     key=lambda r: (r.update_published_at, r.target_build), reverse=True)
    return [(rec, mw.record_target(rec)) for rec in records]


def run(args: argparse.Namespace) -> dict[str, Any]:
    before = tree_digest(WRITE_SURFACES)
    clock = _Clock()
    transport = None
    if args.live:
        session = ef.Session()
    else:
        transport = FixtureTransport(Path(args.fixtures))
        session = ef.Session(transport, clock=clock.time, sleep=clock.sleep)
    context = mw.CollectorContext(write=False, since=args.since, max_pages=1)
    pool = mw.build_elevenforum_pool(context, session)

    captured = utc_now()
    claims = mw.claimed_urls() if args.targets == "repo" else {}
    accepted_rows: list[dict[str, Any]] = []
    rejected_by_url: dict[str, list[str]] = {}
    health_status: dict[str, str] = {}
    for rec, target in _targets(args.targets):
        acc, rej = mw.evaluate_candidates(rec, target, pool.candidates, captured, claims)
        for row in acc:
            accepted_rows.append({
                "patch": f"{rec.update_version} {rec.target_build}",
                "source_url": row["source_url"], "match_basis": row["match_basis"],
                "matched_kb": row.get("matched_kb", ""), "matched_os_build": row.get("matched_os_build", ""),
                "matched_feature_version": row.get("matched_feature_version", ""),
                "original_post_date": row["source_date"], "title": row["report_title"],
                "known_misattribution": ef.thread_id_of(row["source_url"]) == KNOWN_MISATTRIBUTION_THREAD,
            })
        for row in rej:
            rejected_by_url.setdefault(row["source_url"], []).append(str(row.get("exclusion_reason")))
        h = mw.elevenforum_health(rec, captured, pool, acc, rej)
        health_status[f"{rec.update_version} {rec.target_build}"] = h["status"]
    accepted_urls = {r["source_url"] for r in accepted_rows}
    # A thread is "rejected" only if NO record accepted it; report its most common reason.
    rejected = []
    for url, reasons in sorted(rejected_by_url.items()):
        if url in accepted_urls:
            continue
        top = max(sorted(set(reasons)), key=reasons.count)  # sorted: a tie must not depend on hash order
        rejected.append({"source_url": url, "reason": top})
    reason_counts: dict[str, int] = {}
    for item in rejected:
        reason_counts[item["reason"]] = reason_counts.get(item["reason"], 0) + 1

    references = []
    if args.targets == "repo":
        references = [{"source_url": str(r.get("source_url") or ""),
                       "text": " ".join(str(r.get(k) or "") for k in ("report_title", "report_text_excerpt", "report_text"))}
                      for r in load_evidence()
                      if str(r.get("product_id") or "") == WINDOWS_PRODUCT_ID
                      and str(r.get("source_type") or "") != ef.DEFAULT_SOURCE_TYPE]
    duplicates = ef.duplicate_candidates(pool.candidates, references) if references else []

    after = tree_digest(WRITE_SURFACES)
    return {
        "mode": "live-sample" if args.live else "fixture-replay",
        "write": False,
        "targets": args.targets,
        "since": args.since,
        "requests": {
            "listing": session.counts["listing"], "thread": session.counts["thread"],
            "total": session.total_requests, "cap_total": ef.MAX_REQUESTS_PER_CYCLE,
            "min_gap_seconds": round(min(session.gaps), 3) if session.gaps else None,
        },
        "discovery": pool.telemetry,
        "errors": pool.errors,
        "unrecorded_listing_pages_served_empty": (transport.unrecorded_listing_pages if transport else []),
        "unparseable_threads": pool.unparseable,
        "candidates": len(pool.candidates),
        "accepted": accepted_rows,
        "rejected_summary": reason_counts,
        "rejected": rejected,
        "would_be_method_status": health_status,
        "duplicate_candidates_not_dropped": duplicates,
        "write_surfaces_unchanged": before == after,
        "write_surface_digest": after[:16],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zero-write dry run of the Windows 11 Forum adapter.")
    parser.add_argument("--live", action="store_true", help="bounded LIVE sample instead of fixture replay")
    parser.add_argument("--fixtures", default=str(FIXTURES))
    parser.add_argument("--targets", choices=("repo", "synthetic"), default="synthetic")
    parser.add_argument("--since", default="2026-10-18",
                        help="window start (YYYY-MM-DD); the fixtures were recorded 2026-11-04")
    args = parser.parse_args(argv)
    report = run(args)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["write_surfaces_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
