#!/usr/bin/env python3
"""One canonical accepted-evidence population per exact patch — including Windows.

A Windows record tracks ONE cumulative update (a KB / OS build) inside a feature train that rolls
over monthly. Two count authorities existed:

  A  lib.report_counts.counted_evidence_counts  -- `counted is not False` AND `patch_version_matched`
  B  apply_consensus_to_records._filter_rows    -- the same, PLUS patch_collectors.base.windows_identity_gate

Only A fed `update_report_count`; only B fed the count-derived prose. Live on `435c2620` that split
published `update_report_count: 32` beside `consensus_report: "9 user reports found..."` on
2026-06-23-windows-11-25h2.md. Row-level, all 20 disputed rows were reports about SUPERSEDED
cumulative updates of the same train -- KB5095093/26200.8737 and KB5101684/26200.8973 -- while the
record's current patch was KB5121003/26200.9168. Counting them is exactly the version-mismatched
evidence AUXSAYS doctrine forbids, so B was right and A was wrong.

Across the whole corpus the two selectors agreed on 122 of 124 groups, and `stale_due_to_patch_rollover`
was the ONLY exclusion reason anywhere -- this is Windows-train semantics, not a shared defect. The
fix therefore adds the EXISTING gate to the canonical predicate rather than inventing a rule: no
source weighting, no severity, no manual selection.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_windows_count_authority.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
from lib.patch_identity import patch_key  # noqa: E402
from lib.report_counts import (counted_evidence_counts, reconcile_record_counts,  # noqa: E402
                               windows_targets_from_front_matter)

WIN = "microsoft-windows-11"
PPT = "microsoft-powerpoint"

# the real 25H2 identities, from the live record and evidence file
CUR_KB, CUR_BUILD, RELEASED = "KB5121003", "26200.9168", "2026-08-11T00:00:00Z"
OLD_KB_A, OLD_BUILD_A = "KB5095093", "26200.8737"
OLD_KB_B, OLD_BUILD_B = "KB5101684", "26200.8973"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


# ---------------------------------------------------------------- fixtures


def row(pid=WIN, ver="25H2", *, kb=CUR_KB, build=CUR_BUILD, feat="25H2", rid=None,
        url=None, date="2026-08-20T00:00:00Z", counted=True, matched=True,
        target_build="", source_type="microsoft learn qna"):
    return {
        "id": rid or f"r-{kb}-{build}-{url or date}",
        "product_id": pid, "update_version": ver, "target_build": target_build,
        "source_url": url or f"https://learn.microsoft.com/answers/{kb}-{date}",
        "source_type": source_type, "source_date": date, "captured_at": date,
        "counted": counted, "patch_version_matched": matched,
        "matched_kb": kb, "matched_os_build": build, "matched_feature_version": feat,
        # the consensus selector also requires a classified sentiment and severity; the canonical
        # predicate does not. Both are present on 595/595 live rows, so supplying them is what makes
        # this fixture reproduce the REAL divergence -- the Windows gate -- and not a fixture artefact.
        "sentiment": "negative", "severity": "high",
    }


def record(path: Path, pid=WIN, ver="25H2", *, kb=CUR_KB, build=CUR_BUILD,
           released=RELEASED, count=0, prose="", target_build=""):
    data = {
        "layout": "aux-update", "update_entry": True,
        "product_id": pid, "update_version": ver, "update_product": "Windows 11",
        "update_report_count": count, "confirmed_patch_specific_report_count": count,
        "target_kb": kb, "target_os_build": build, "target_feature_version": ver,
        "target_release_date": released,
    }
    if target_build:
        data["target_build"] = target_build
    if prose:
        data["consensus_report"] = prose
        data["update_consensus_summary"] = prose
    path.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\nbody\n",
                    encoding="utf-8")
    return data


def canonical(rows, records):
    """The canonical population count per patch, exactly as production computes it."""
    return counted_evidence_counts(
        rows, windows_targets=windows_targets_from_front_matter(records))


def consensus(rows, rec_front, pid, ver):
    """What the consensus writer selects -- the second historical authority."""
    groups = acr._group_rows(rows, is_candidate_mode=False)
    inc, exc = acr._filter_rows(groups.get(patch_key(pid, ver, "")) or [],
                                product_id=pid, version=ver, is_candidate_mode=False,
                                record=None if rec_front is None else dict(rec_front))
    return len(inc), exc


def historical_predicate(rows):
    """`counted_evidence_counts` EXACTLY as it stood before this fix (commit 435c2620).

    Reproduced here rather than called, because the fixed function now requires the target map --
    that is the point. Keeping the old body in the test is what lets C1/C2 demonstrate the real
    divergence instead of asserting it from memory."""
    counts: dict[tuple[str, str, str], int] = {}
    for r in rows:
        pid = str(r.get("product_id") or "").strip()
        ver = str(r.get("update_version") or "").strip()
        if not pid or not ver or r.get("counted") is False:
            continue
        if r.get("patch_version_matched") is not True:
            continue
        k = patch_key(pid, ver, r.get("target_build"))
        counts[k] = counts.get(k, 0) + 1
    return counts


def run() -> int:
    print("=" * 74)
    print("Windows consensus count authority -- one canonical population per exact patch")
    print("=" * 74)

    # ---------- C1: the real 25H2 disagreement ----------
    print("\n[C1] 25H2: reports about superseded cumulative updates do not count")
    rows_25 = (
        [row(kb=CUR_KB, build=CUR_BUILD, rid=f"cur{i}", url=f"https://x/cur{i}") for i in range(12)]
        + [row(kb=OLD_KB_A, build=OLD_BUILD_A, rid=f"a{i}", url=f"https://x/a{i}",
               date="2026-07-05T00:00:00Z") for i in range(10)]
        + [row(kb=OLD_KB_B, build=OLD_BUILD_B, rid=f"b{i}", url=f"https://x/b{i}",
               date="2026-08-03T00:00:00Z") for i in range(10)]
    )
    with tempfile.TemporaryDirectory() as td:
        rec_path = Path(td) / "w25.md"
        front = record(rec_path, count=32, prose="9 user reports found for Windows 11 25H2.")
        key = patch_key(WIN, "25H2", "")

        ungated = historical_predicate(rows_25)                       # the OLD authority A
        gated = canonical(rows_25, [front])                           # the canonical predicate
        sel, exc = consensus(rows_25, front, WIN, "25H2")             # authority B
        check("C1 the OLD ungated authority counted all three cumulative updates",
              ungated.get(key) == 32, str(ungated.get(key)))
        check("C1 the consensus selector counted only the current patch",
              sel == 12, str(sel))
        check("C1 they DID disagree before the fix", ungated.get(key) != sel)
        check("C1 the canonical predicate now equals the consensus selector",
              gated.get(key) == sel == 12, f"canonical={gated.get(key)} selector={sel}")
        check("C1 every dropped row was a patch rollover, not a new rule",
              exc and all(r.get("_exclusion_reason") == "stale_due_to_patch_rollover" for r in exc),
              str({r.get("_exclusion_reason") for r in exc}))

    # ---------- C2: the real 26H1 disagreement ----------
    print("\n[C2] 26H1: same contract on the smaller record")
    rows_26 = [row(ver="26H1", kb="KB5121000", build="28000.2704", feat="26H1", rid="cur",
                   url="https://x/26cur"),
               row(ver="26H1", kb=None, build="28000.2608", feat="26H1", rid="old",
                   url="https://x/26old", date="2026-08-02T00:00:00Z")]
    with tempfile.TemporaryDirectory() as td:
        rec_path = Path(td) / "w26.md"
        front = record(rec_path, ver="26H1", kb="KB5121000", build="28000.2704", count=2)
        key = patch_key(WIN, "26H1", "")
        check("C2 the OLD authority counted 2", historical_predicate(rows_26).get(key) == 2)
        sel, _e = consensus(rows_26, front, WIN, "26H1")
        check("C2 the consensus selector counted 1", sel == 1, str(sel))
        check("C2 canonical == selector == 1",
              canonical(rows_26, [front]).get(key) == sel == 1)

    # ---------- C3: a valid reply is NOT collateral damage ----------
    print("\n[C3] a distinct reporter's reply on the CURRENT patch still counts")
    with tempfile.TemporaryDirectory() as td:
        front = record(Path(td) / "r.md")
        base = [row(rid="op", url="https://x/thread")]
        reply = row(rid="reply", url="https://x/thread#answer-2")
        key = patch_key(WIN, "25H2", "")
        check("C3 the reply counts alongside the original",
              canonical(base + [reply], [front]).get(key) == 2,
              str(canonical(base + [reply], [front]).get(key)))
        check("C3 the fix did not solve 32-vs-12 by dropping replies",
              canonical([reply], [front]).get(key) == 1)

    # ---------- C4: duplicates ----------
    print("\n[C4] a duplicate row counts once")
    with tempfile.TemporaryDirectory() as td:
        front = record(Path(td) / "r.md")
        key = patch_key(WIN, "25H2", "")
        dup = row(rid="dup", url="https://x/same")
        # the pipeline marks a duplicate by clearing `counted`; assert the predicate honours it
        check("C4 a row flagged not-counted is excluded",
              canonical([dup, {**dup, "id": "dup2", "counted": False}], [front]).get(key) == 1,
              str(canonical([dup, {**dup, "id": "dup2", "counted": False}], [front]).get(key)))

    # ---------- C5: wrong patch / wrong build ----------
    print("\n[C5] evidence belonging to another patch never counts")
    with tempfile.TemporaryDirectory() as td:
        front = record(Path(td) / "r.md")
        key = patch_key(WIN, "25H2", "")
        check("C5 a superseded OS build does not count",
              canonical([row(kb=OLD_KB_A, build=OLD_BUILD_A, rid="old")], [front]).get(key, 0) == 0)
        check("C5 a KB from a different train does not count",
              canonical([row(kb=CUR_KB, build="", feat="24H2", rid="x")], [front]).get(key, 0) == 0)
        check("C5 a row with no proven KB/build identity does not count",
              canonical([row(kb=None, build=None, feat=None, rid="bare")], [front]).get(key, 0) == 0)

    # ---------- C6/C7/C8: rows the upstream rules already rejected ----------
    print("\n[C6-C8] official notes, generic discussion and excluded rows never count")
    with tempfile.TemporaryDirectory() as td:
        front = record(Path(td) / "r.md")
        key = patch_key(WIN, "25H2", "")
        official = row(rid="off", source_type="official release notes", counted=False)
        generic = row(rid="gen", matched=False)
        excluded = row(rid="exc", counted=False)
        check("C6 an official note is not user consensus",
              canonical([official], [front]).get(key, 0) == 0)
        check("C7 evidence not matched to the patch does not count",
              canonical([generic], [front]).get(key, 0) == 0)
        check("C8 a deterministically excluded row does not count merely by existing",
              canonical([excluded], [front]).get(key, 0) == 0)

    # ---------- C9: build-aware sibling isolation ----------
    print("\n[C9] a build-aware product keeps sibling builds isolated")
    ppt_rows = [
        {"id": "p1", "product_id": PPT, "update_version": "2607", "target_build": "20228.20110",
         "counted": True, "patch_version_matched": True, "source_url": "https://x/p1"},
        {"id": "p2", "product_id": PPT, "update_version": "2607", "target_build": "20228.20124",
         "counted": True, "patch_version_matched": True, "source_url": "https://x/p2"},
    ]
    c = canonical(ppt_rows, [])
    check("C9 each sibling build holds its own population",
          c.get(patch_key(PPT, "2607", "20228.20110")) == 1
          and c.get(patch_key(PPT, "2607", "20228.20124")) == 1, str(c))
    check("C9 no version-only bucket absorbs them",
          c.get((PPT, "2607", "")) is None, str(c))
    check("C9 the Windows gate does not touch a non-Windows product",
          len(c) == 2, str(c))

    # ---------- C10: version-only products unchanged ----------
    print("\n[C10] version-only products keep their existing behaviour")
    others = [{"id": f"o{i}", "product_id": pid, "update_version": "1.0", "target_build": "",
               "counted": True, "patch_version_matched": True, "source_url": f"https://x/o{i}"}
              for i, pid in enumerate(("obs-studio", "adobe-premiere-pro", "blackmagic-davinci",
                                       "adobe-acrobat-pro"))]
    with_targets = canonical(others, [])
    without = historical_predicate(others)
    check("C10 the fix changes nothing for products that are not Windows",
          with_targets == without, f"{with_targets} != {without}")
    check("C10 each still counts its own row", len(with_targets) == 4, str(with_targets))

    # ---------- N1-N3: count and narrative agree after the real pipeline ----------
    print("\n[N1-N3] the number and the generated prose come from one population")
    with tempfile.TemporaryDirectory() as td:
        gen = Path(td) / "generated"
        gen.mkdir(parents=True)
        rec_path = gen / "2026-06-23-windows-11-25h2.md"
        record(rec_path, count=32, prose="9 user reports found for Windows 11 25H2.")
        n, details = reconcile_record_counts(rows_25, gen)
        after = yaml.safe_load(rec_path.read_text(encoding="utf-8").split("---", 2)[1])
        key = patch_key(WIN, "25H2", "")
        canon = canonical(rows_25, [after]).get(key)
        check("N1 update_report_count equals the canonical population",
              after["update_report_count"] == canon == 12,
              f"count={after['update_report_count']} canonical={canon}")
        check("N1 the confirmed count matches too",
              after["confirmed_patch_specific_report_count"] == canon)
        check("N1 reconciliation reported the change", n == 1 and details[0]["after"] == 12,
              str(details))
        # reconcile fixes NUMBERS only -- this is precisely why a scoped promotion step exists
        check("N2 reconcile alone leaves the prose stale (the gap the promotion step closes)",
              "9 user reports" in str(after.get("consensus_report")),
              str(after.get("consensus_report")))

    # ---------- N5: the pipeline wires a Windows promotion after reconciliation ----------
    print("\n[N5] the scheduled lane regenerates Windows count-derived prose")
    wf = (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml").read_text(encoding="utf-8")
    steps = [ln.strip() for ln in wf.splitlines() if ln.strip().startswith("- name:")]
    names = [s[len("- name:"):].strip() for s in steps]
    check("N5 a Windows-scoped consensus promotion step exists",
          any("Windows consensus" in n for n in names), str(names))
    win_block = wf[wf.index("Promote Windows consensus"):]
    win_block = win_block[:win_block.index("- name:", 10)]
    check("N5 it is product-scoped, never an unscoped --write-all",
          "--product-id microsoft-windows-11" in win_block and "--write-all" in win_block,
          win_block[-160:])
    check("N5 it runs AFTER the consensus/reconcile step",
          names.index("Build consensus status") < next(i for i, n in enumerate(names)
                                                       if "Windows consensus" in n))
    check("N5 QA re-runs after the promotions",
          any("Re-run QA" in n for n in names)
          and next(i for i, n in enumerate(names) if "Re-run QA" in n)
          > next(i for i, n in enumerate(names) if "Windows consensus" in n))
    check("N5 the writeback may commit the repaired Windows records",
          "auxsays/updates/generated/*windows-11*.md" in wf)

    # ---------- QA recurrence guard ----------
    print("\n[QA] the contradiction is now caught by a structured gate, not prose parsing")
    import qa_patch_records as qa  # noqa: PLC0415
    check("QA delegates to the canonical predicate",
          qa.counted_evidence_counts is counted_evidence_counts)
    import inspect  # noqa: PLC0415
    src = inspect.getsource(qa.load_counted_evidence_counts)
    check("QA supplies the Windows target identities",
          "windows_targets" in src, src)
    check("QA compares the record's own count against the canonical population",
          "generated_report_count_mismatch" in inspect.getsource(qa.scan_evidence_count_alignment))

    # ---------- C11: a forgotten target map must be loud, never a silent zero ----------
    print("\n[C11] the target map is required, so a caller bug cannot publish 0")
    try:
        counted_evidence_counts([])
        check("C11 omitting windows_targets raises instead of returning {}", False,
              "call succeeded -- a forgotten argument would read 0 reports for every Windows patch")
    except TypeError as exc:
        check("C11 omitting windows_targets raises instead of returning {}",
              "windows_targets" in str(exc), str(exc))
    with tempfile.TemporaryDirectory() as td:
        front = record(Path(td) / "r.md")
        key = patch_key(WIN, "25H2", "")
        rows = [row(rid="ok")]
        check("C11 a supplied map with no entry for the patch still fails closed",
              counted_evidence_counts(rows, windows_targets={}).get(key, 0) == 0)
        check("C11 ... while the real target counts it",
              canonical(rows, [front]).get(key) == 1)

    # ---------- C12: the OBS collector's own counter reads the same population ----------
    print("\n[C12] no product keeps a private count authority")
    import collect_obs_reports as cor  # noqa: PLC0415
    obs_rows = [{"id": f"s{i}", "product_id": "obs-studio", "update_version": "32.1.2",
                 "target_build": "", "counted": True, "patch_version_matched": True,
                 "source_url": f"https://x/s{i}"} for i in range(3)]
    check("C12 it agrees with the canonical population",
          cor.counted_evidence_count(obs_rows, "32.1.2") == 3,
          str(cor.counted_evidence_count(obs_rows, "32.1.2")))
    check("C12 it now honours patch_version_matched (its old predicate did not)",
          cor.counted_evidence_count(
              obs_rows + [{**obs_rows[0], "id": "bad", "patch_version_matched": False}],
              "32.1.2") == 3)
    check("C12 another product's rows cannot move an OBS count",
          cor.counted_evidence_count(obs_rows + rows_25, "32.1.2") == 3)
    check("C12 a Windows row with no target cannot fail an OBS count",
          cor.counted_evidence_count(obs_rows + [row(rid="nt")], "32.1.2") == 3)

    print()
    print("=" * 74)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 74)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
