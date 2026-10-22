#!/usr/bin/env python3
"""Report-count reconciliation contract (generated_report_count_mismatch fix).

Run 30804068954 (adobe-acrobat-pro): collection + consensus succeeded, but QA failed with
`generated_report_count_mismatch: Generated report count is 4, but structured counted evidence has 14
rows.` Root cause: the record's update_report_count was written by the consensus writer
(apply_consensus_to_records._filter_rows -> len(included)), whose predicate is STRICTER than the QA gate
(it also requires a non-empty source_url and valid sentiment/severity). A counted, version-matched row
with e.g. unclassified sentiment is counted by QA but excluded from the record -> 4 vs 14.

Fix: lib.report_counts.counted_evidence_counts is the SINGLE authoritative predicate (counted != False
AND patch_version_matched is True), used by BOTH qa_patch_records (the gate) and reconcile_record_counts
(the post-collection writer), so the record count can never diverge from what QA enforces -- without
weakening QA, changing acceptance flags, or discarding evidence.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_report_count_reconciliation.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib.report_counts import counted_evidence_counts, reconcile_record_counts  # noqa: E402
from patch_collectors.base import load_front_matter_and_body, write_front_matter_and_body  # noqa: E402
import qa_patch_records  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def row(pid: str, ver: str, *, counted=True, matched=True, rid="r", url="http://x/1",
        sentiment="negative", source_type="adobe_community_bug_report") -> dict:
    r = {"id": rid, "product_id": pid, "update_version": ver, "source_url": url,
         "source_type": source_type, "sentiment": sentiment, "patch_version_matched": matched}
    if counted is not None:
        r["counted"] = counted
    return r


def make_record(gen: Path, name: str, pid: str, ver: str, *, count=0, state="official_only",
                label="Official source only", status="deferred_official_only") -> Path:
    p = gen / name
    data = {"update_entry": True, "product_id": pid, "update_version": ver,
            "update_report_count": count, "confirmed_patch_specific_report_count": count,
            "evidence_state": state, "evidence_state_label": label,
            "consensus_collection_status": status,
            "permalink": f"/updates/x/{pid}/{ver.replace('.', '-')}/"}
    write_front_matter_and_body(p, data, "body\n")
    return p


def rec_count(path: Path) -> int:
    data, _ = load_front_matter_and_body(path)
    return int(data.get("update_report_count") or 0)


def rec_field(path: Path, field: str):
    data, _ = load_front_matter_and_body(path)
    return data.get(field)


def tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="rcr-"))
    (d / "gen").mkdir()
    return d / "gen"


def run() -> int:
    print("=" * 70)
    print("Report-count reconciliation contract")
    print("=" * 70)

    # 0. shared predicate: QA delegates to the same function (can never diverge)
    check("shared predicate: qa uses lib.report_counts.counted_evidence_counts",
          qa_patch_records.counted_evidence_counts is counted_evidence_counts)

    # 1. THE BUG: record shows 4, structured evidence has 14 counted+matched -> reconcile to 14
    gen = tmp()
    r = make_record(gen, "acrobat-pro-v.md", "adobe-acrobat-pro", "26.001.21563", count=4, state="pilot_sample", label="Verified reports", status="pilot_initial_sample")
    ev = [row("adobe-acrobat-pro", "26.001.21563", rid=f"a{i}", url=f"http://x/{i}",
              sentiment=("" if i >= 4 else "negative")) for i in range(14)]  # 14 counted+matched; 10 have empty sentiment (excluded by the stricter writer, counted by QA)
    changed, detail = reconcile_record_counts(ev, gen)
    check("1 reproduces + fixes: 4 -> 14", changed == 1 and rec_count(r) == 14, f"count={rec_count(r)}")
    check("1 QA invariant holds after reconcile (record == QA count)",
          rec_count(r) == counted_evidence_counts(ev, windows_targets={}).get(
              ("adobe-acrobat-pro", "26.001.21563", "")))
    check("1 same-boundary count fix does NOT rewrite the label", rec_field(r, "evidence_state_label") == "Verified reports")

    # 2. idempotent: reconciling an aligned tree writes nothing
    changed2, _ = reconcile_record_counts(ev, gen)
    check("2 idempotent rerun: 0 changes second time", changed2 == 0)

    # 3. historical + newly accepted rows count together
    gen = tmp()
    r = make_record(gen, "obs.md", "obs-studio", "32.2.1", count=0)
    ev = [row("obs-studio", "32.2.1", rid=f"h{i}", url=f"http://h/{i}", source_type="github_issue") for i in range(5)] \
       + [row("obs-studio", "32.2.1", rid=f"n{i}", url=f"http://n/{i}", source_type="github_issue") for i in range(9)]
    reconcile_record_counts(ev, gen)
    check("3 historical + new = 14", rec_count(r) == 14)
    check("3 zero->N crosses boundary: state + label updated", rec_field(r, "evidence_state") == "pilot_sample" and rec_field(r, "evidence_state_label") == "Verified reports")

    # 4. multiple sequential collectors (2 source types, same product/version)
    gen = tmp()
    r = make_record(gen, "dav.md", "blackmagic-davinci", "21.0.3", count=0)
    ev = [row("blackmagic-davinci", "21.0.3", rid=f"rd{i}", url=f"http://rd/{i}", source_type="reddit_community_report") for i in range(8)] \
       + [row("blackmagic-davinci", "21.0.3", rid=f"fo{i}", url=f"http://fo/{i}", source_type="blackmagic_forum") for i in range(6)]
    reconcile_record_counts(ev, gen)
    check("4 multiple collectors same product/version summed = 14", rec_count(r) == 14)

    # 5. counted flags: counted=False and patch_version_matched!=True are excluded (matches QA)
    gen = tmp()
    r = make_record(gen, "flags.md", "adobe-acrobat-pro", "20.0", count=99)
    ev = [row("adobe-acrobat-pro", "20.0", rid="ok1"), row("adobe-acrobat-pro", "20.0", rid="ok2"),
          row("adobe-acrobat-pro", "20.0", rid="nc", counted=False),
          row("adobe-acrobat-pro", "20.0", rid="nm", matched=False)]
    reconcile_record_counts(ev, gen)
    check("5 counted/matched flags respected: only 2 count", rec_count(r) == 2)

    # 6. duplicate id / url counted consistently by BOTH sides (no silent divergence)
    gen = tmp()
    r = make_record(gen, "dup.md", "adobe-acrobat-pro", "22.0", count=0)
    ev = [row("adobe-acrobat-pro", "22.0", rid="same", url="http://dup"),
          row("adobe-acrobat-pro", "22.0", rid="same", url="http://dup")]
    reconcile_record_counts(ev, gen)
    check("6 duplicate rows: record == QA count (both count 2 identically)",
          rec_count(r) == counted_evidence_counts(ev, windows_targets={}).get(
              ("adobe-acrobat-pro", "22.0", "")))

    # 7. Reader/Pro isolation: distinct product_ids never merge
    gen = tmp()
    rr = make_record(gen, "reader.md", "adobe-acrobat-reader", "26.001.21563", count=0)
    rp = make_record(gen, "pro.md", "adobe-acrobat-pro", "26.001.21563", count=0)
    ev = [row("adobe-acrobat-reader", "26.001.21563", rid=f"rd{i}") for i in range(3)] \
       + [row("adobe-acrobat-pro", "26.001.21563", rid=f"pr{i}") for i in range(9)]
    reconcile_record_counts(ev, gen)
    check("7 Reader/Pro isolated: reader=3, pro=9 (no cross-product merge)", rec_count(rr) == 3 and rec_count(rp) == 9)

    # 8. exact version keying (no accidental normalization merge)
    gen = tmp()
    r262 = make_record(gen, "p262.md", "adobe-premiere-pro", "26.2", count=0)
    r2620 = make_record(gen, "p2620.md", "adobe-premiere-pro", "26.2.0", count=0)
    ev = [row("adobe-premiere-pro", "26.2", rid=f"a{i}") for i in range(4)] \
       + [row("adobe-premiere-pro", "26.2.0", rid=f"b{i}") for i in range(1)]
    reconcile_record_counts(ev, gen)
    check("8 distinct version strings keyed exactly (26.2=4, 26.2.0=1)", rec_count(r262) == 4 and rec_count(r2620) == 1)

    # 9. record with NO evidence resets to 0 + official_only (over-count corrected downward)
    gen = tmp()
    r = make_record(gen, "stale.md", "adobe-acrobat-pro", "99.0", count=7, state="pilot_sample", label="Verified reports", status="pilot_initial_sample")
    reconcile_record_counts([], gen)
    check("9 no-evidence record reset 7 -> 0 + official_only", rec_count(r) == 0 and rec_field(r, "evidence_state") == "official_only")

    # 10. only-successful evidence is seen (rolled-back rows never reach consensus_evidence.yml)
    gen = tmp()
    r = make_record(gen, "partial.md", "obs-studio", "32.1.0", count=0)
    committed = [row("obs-studio", "32.1.0", rid=f"c{i}", source_type="github_issue") for i in range(4)]
    reconcile_record_counts(committed, gen)  # a failed collector's rows simply aren't in `committed`
    check("10 partial run: counts only committed evidence (4)", rec_count(r) == 4)

    # 11. non-update markdown is never touched
    gen = tmp()
    other = gen / "not-a-record.md"
    write_front_matter_and_body(other, {"title": "x"}, "body\n")  # no update_entry
    changed, _ = reconcile_record_counts([row("obs-studio", "1.0")], gen)
    check("11 non-update markdown ignored", changed == 0)

    # 12. QA catches a deliberately introduced mismatch (gate NOT weakened)
    gen = tmp()
    r = make_record(gen, "bad.md", "obs-studio", "32.2.1", count=2, state="pilot_sample")
    ev = [row("obs-studio", "32.2.1", rid=f"g{i}", source_type="github_issue") for i in range(14)]
    # QA's scan_evidence_count_alignment must ERROR when record (2) != counted (14)
    orig = qa_patch_records.load_counted_evidence_counts
    qa_patch_records.load_counted_evidence_counts = (
        lambda _records=None: counted_evidence_counts(ev, windows_targets={}))
    try:
        errs, _ = qa_patch_records.scan_evidence_count_alignment([r])
        check("12 QA catches mismatch (2 vs 14) before fix", any(e.get("code") == "generated_report_count_mismatch" for e in errs), str(errs))
        # 13. after reconcile, QA passes -- gate unchanged, record now authoritative
        reconcile_record_counts(ev, gen)
        errs2, _ = qa_patch_records.scan_evidence_count_alignment([r])
        check("13 reconcile makes QA pass without weakening the gate", errs2 == [] and rec_count(r) == 14)
    finally:
        qa_patch_records.load_counted_evidence_counts = orig

    print()
    print("=" * 70)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 70)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
