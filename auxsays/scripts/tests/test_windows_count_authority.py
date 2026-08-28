#!/usr/bin/env python3
"""One canonical accepted-evidence population per exact patch — including Windows.

A Windows record tracks ONE cumulative update (a KB / OS build) inside a feature train that rolls
over monthly. Two count authorities existed:

  A  lib.report_counts.counted_evidence_counts  -- `counted is not False` AND `patch_version_matched`
  B  apply_consensus_to_records._filter_rows    -- the same, PLUS patch_collectors.base.windows_identity_gate

Only A fed `update_report_count`; only B fed the count-derived prose. Live on `435c2620` that split
published `update_report_count: 32` beside `consensus_report: "9 user reports found..."` on
2026-06-23-windows-11-25h2.md. Row-level, all 21 disputed rows were reports about SUPERSEDED
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
from patch_collectors.base import (load_front_matter_and_body,  # noqa: E402
                                   write_front_matter_and_body)
from lib.report_counts import (CONSENSUS_PROMOTION_PRODUCTS,  # noqa: E402
                               counted_evidence_counts, reconcile_record_counts,
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


def flag_value(command: str, flag: str) -> str | None:
    """Value of `flag` in a shell command, accepting both `--flag value` and `--flag=value`.

    Property, not spelling: the two forms are equivalent to the shell, so a test that only
    recognises one fails on a harmless rewrite."""
    tokens = command.replace("\\\n", " ").split()
    for i, tok in enumerate(tokens):
        if tok == flag:
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if tok.startswith(flag + "="):
            return tok.split("=", 1)[1]
    return None


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
    # Parsed as YAML and asserted as PROPERTIES. An earlier version sliced the raw text with
    # `wf.index("Promote Windows consensus")` and `names.index("Build consensus status")`; renaming a
    # step -- a behaviour-neutral edit -- crashed the suite with an uncaught ValueError and printed no
    # Results line at all, and `"--product-id microsoft-windows-11" in block` failed on the equally
    # valid `--product-id=microsoft-windows-11`. A test must not pin the spelling of a thing whose
    # PROPERTY is what matters.
    wf_path = _REPO / ".github" / "workflows" / "obs-evidence-collection.yml"
    wf = wf_path.read_text(encoding="utf-8")
    job = yaml.safe_load(wf)["jobs"]["collect"]
    steps = job["steps"]

    def find_step(token):
        """Index of the step whose run: invokes a promotion scoped to `token`; -1 if none."""
        for i, st in enumerate(steps):
            run = str(st.get("run") or "")
            if "apply_consensus_to_records" in run and flag_value(run, "--product-id") == token:
                return i
        return -1

    def find_named(token):
        for i, st in enumerate(steps):
            if token.lower() in str(st.get("name") or "").lower():
                return i
        return -1

    win_i = find_step(WIN)
    check("N5 a promotion step scoped to microsoft-windows-11 exists", win_i >= 0,
          str([st.get("name") for st in steps]))
    if win_i >= 0:
        run = str(steps[win_i].get("run") or "")
        check("N5 it is product-scoped, never an unscoped --write-all",
              flag_value(run, "--product-id") == WIN and "--write-all" in run, run)
        check("N5 it does not also carry another product's scope",
              run.count("--product-id") == 1, run)
    reconcile_i = next((i for i, st in enumerate(steps)
                        if "build_consensus_from_evidence" in str(st.get("run") or "")), -1)
    check("N5 the reconcile step is identifiable by what it RUNS, not its title",
          reconcile_i >= 0, str([st.get("name") for st in steps]))
    check("N5 promotion runs AFTER reconciliation",
          0 <= reconcile_i < win_i, f"reconcile={reconcile_i} windows={win_i}")
    qa_steps = [i for i, st in enumerate(steps)
                if "qa_patch_records" in str(st.get("run") or "")]
    check("N5 QA runs after the promotion", any(i > win_i for i in qa_steps), str(qa_steps))

    # ---------- N5b: the ordering property, for EVERY retractable product ----------
    # Asserted over the constant, not for one product by name. Reconciliation retracts projections
    # for every product in CONSENSUS_PROMOTION_PRODUCTS; only that product's OWN scoped promotion
    # rebuilds them. A QA step in that gap kills the job on the first run after a population empties
    # and refills -- report_count_without_consensus_summary / _without_evidence_samples -- before the
    # promotion can run, taking the whole writeback and therefore every OTHER product's evidence for
    # that cycle with it. Reproduced twice: once for Windows, and then again for PowerPoint after the
    # Windows-only fix, which is exactly why this is a loop and not a second hard-coded check.
    #
    # Scope note: this reads the `collect` job only. PowerPoint is ALSO promoted inside
    # orchestrate_evidence_run.py in the powerpoint-orchestrated job; that path reconciles and
    # promotes within one graph, so it has no such gap. If a promotion ever moves out of `collect`
    # entirely, R7's equality assertion below is what will fail and bring someone back here.
    for product in sorted(CONSENSUS_PROMOTION_PRODUCTS):
        pi = find_step(product)
        check(f"N5b {product} has a scoped promotion step in the lane", pi >= 0,
              str([st.get("name") for st in steps]))
        if pi < 0:
            continue
        check(f"N5b {product} is promoted AFTER reconciliation",
              0 <= reconcile_i < pi, f"reconcile={reconcile_i} {product}={pi}")
        check(f"N5b nothing validates between reconciliation and {product}'s promotion",
              not [i for i in qa_steps if reconcile_i < i < pi],
              f"reconcile={reconcile_i} qa={qa_steps} {product}={pi}")
        check(f"N5b QA still runs after {product}'s promotion",
              any(i > pi for i in qa_steps), f"qa={qa_steps} {product}={pi}")
    # Find the WRITEBACK step by what it runs, then read its --allow values as TOKENS and glob them
    # against a real record path. An earlier version asked whether "windows-11" and "--allow" both
    # appeared anywhere in the same step's run:, which the collection step satisfied by accident --
    # `microsoft-windows-11` sits in its product-id list and `--allow` appears in one of its code
    # comments. Deleting the real allow entry, the one thing that lets the lane commit these records,
    # left the suite fully green.
    import fnmatch  # noqa: PLC0415
    # Steps that INVOKE the writeback, not steps that merely mention it -- "automation_writeback"
    # appears in a comment in a neighbouring step too, and matching that one found no real flags.
    wb_steps = [st for st in steps
                if "automation_writeback.py" in str(st.get("run") or "")]
    check("N5 the conflict-safe writeback step is identifiable", bool(wb_steps),
          str([st.get("name") for st in steps]))
    allows = []
    for st in wb_steps:
        toks = str(st.get("run") or "").replace("\\\n", " ").split()
        allows += [toks[i + 1].strip("'\"") for i, t in enumerate(toks[:-1]) if t == "--allow"]
    target = "auxsays/updates/generated/2026-06-23-windows-11-25h2.md"
    check("N5 an --allow entry actually authorizes a Windows record path",
          any(fnmatch.fnmatch(target, pat) for pat in allows),
          f"allow entries: {allows}")

    # ---------- N6: the promotion structurally cannot rewrite Windows verdict prose ----------
    print("\n[N6] the unattended promotion cannot touch editorial prose")
    # The workflow comment claims this; nothing enforced it. Adding a Windows branch to
    # _record_coherence_fields let an unattended cron step overwrite quick_verdict,
    # update_decision_body, practical_recommendations, release_summary and official_summary on all
    # three live Windows records with every test and QA still green. Pin the property.
    from collections import Counter  # noqa: PLC0415
    win_record = {"update_product": "Windows 11", "product_id": WIN, "update_version": "25H2"}
    check("N6 _record_coherence_fields yields nothing for Windows",
          acr._record_coherence_fields(WIN, "25H2", 12, win_record, Counter({"bsod": 3})) == {},
          str(acr._record_coherence_fields(WIN, "25H2", 12, win_record, Counter({"bsod": 3}))))
    editorial = {"quick_verdict", "update_decision_label", "update_decision_body",
                 "practical_recommendations", "release_summary", "official_summary"}
    proposed = acr._proposed_record_fields(
        WIN, "25H2", [row(rid=f"p{i}", url=f"https://x/p{i}") for i in range(12)],
        win_record, "2026-08-27T00:00:00Z", build="")
    leaked = editorial & set(proposed)
    check("N6 the promotion proposes no editorial field for Windows", not leaked, str(leaked))

    # ---------- QA recurrence guard ----------
    print("\n[QA] the contradiction is caught behaviourally, not by reading source text")
    import qa_patch_records as qa  # noqa: PLC0415
    check("QA delegates to the canonical predicate",
          qa.counted_evidence_counts is counted_evidence_counts)
    # BEHAVIOURAL. This previously asserted that the string "windows_targets" appeared in the
    # function's source -- which a mutation passing `windows_targets={}` satisfied while silently
    # disabling the gate: with an empty map the Windows count is 0, the key is absent from the map,
    # and `if key not in evidence_counts: continue` skips the comparison entirely. QA went from 2
    # blocking errors to 0 on the real defective records with this suite still at 41/41. Assert the
    # ERROR, so only a QA that really resolves the Windows identity can pass.
    with tempfile.TemporaryDirectory() as td:
        rec_path = Path(td) / "2026-06-23-windows-11-25h2.md"
        record(rec_path, count=32, prose="9 user reports found for Windows 11 25H2.")
        orig_loader = qa.load_yaml
        try:
            qa.load_yaml = lambda *_a, **_k: rows_25
            errors, _warn = qa.scan_evidence_count_alignment([rec_path])
        finally:
            qa.load_yaml = orig_loader
        codes = [e.get("code") for e in errors]
        check("QA blocks a Windows record that claims more reports than the canonical population",
              "generated_report_count_mismatch" in codes, str(errors))
        check("QA names the canonical count, not the inflated one",
              any("12" in str(e.get("message", "")) for e in errors), str(errors))

    # An EMPTY canonical population is surfaced as a WARNING, never an error, and both halves of that
    # are load-bearing. Erroring here fails the run that PERFORMS a KB rollover: `patch-ingest.yml`
    # runs this gate with no reconcile step, so its writeback never commits the new target and the
    # rollover can never land -- verified, a permanent cross-lane wedge. Staying silent instead loses
    # the one signal that a record is claiming reports for a patch with no accepted evidence at all.
    with tempfile.TemporaryDirectory() as td:
        rolled_path = Path(td) / "2026-06-23-windows-11-25h2.md"
        record(rolled_path, count=12, prose="12 user reports found for Windows 11 25H2.")
        rolled, body = load_front_matter_and_body(rolled_path)
        rolled["target_kb"], rolled["target_os_build"] = "KB5130777", "26200.9400"
        write_front_matter_and_body(rolled_path, rolled, body)
        honest_path = Path(td) / "2026-06-09-windows-11-23h2.md"
        record(honest_path, ver="23H2", kb="KB5120240", build="22631.7517", count=0)
        keep_path = Path(td) / "2026-06-23-windows-11-26h1.md"
        record(keep_path, ver="26H1", kb="KB5121000", build="28000.2704", count=1)
        live = rows_25 + [row(ver="26H1", kb="KB5121000", build="28000.2704", feat="26H1",
                              rid="keep2", url="https://x/keep2")]
        orig_loader = qa.load_yaml
        try:
            qa.load_yaml = lambda *_a, **_k: live
            errs, warns = qa.scan_evidence_count_alignment(
                [rolled_path, honest_path, keep_path])
        finally:
            qa.load_yaml = orig_loader
        rolled_errs = [e for e in errs if "25h2" in str(e.get("file", ""))]
        rolled_warns = [w for w in warns
                        if w.get("code") == "report_count_for_empty_population"
                        and "25h2" in str(w.get("file", ""))]
        check("QA warns when a record claims reports for an EMPTY population",
              bool(rolled_warns), str(warns))
        check("QA does NOT error there -- that would wedge the lane that writes the rollover",
              not rolled_errs, str(rolled_errs))
        check("QA stays silent on a record honestly at zero",
              not [w for w in warns if "23h2" in str(w.get("file", ""))]
              and not [e for e in errs if "23h2" in str(e.get("file", ""))], str(warns))

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

    # ---------- R1-R4: the monthly KB rollover ----------
    print("\n[R1-R4] when the population empties, the record stops claiming reports")
    # The failure this pins: a rollover moves the record's target to next month's cumulative update,
    # every accepted row becomes stale, and the count correctly falls to 0 -- but BOTH downstream
    # writers bail out at count <= 0 (`--write-all` skips the group, _record_coherence_fields returns
    # {}), so the record kept publishing "0 / Official source only" beside "WAIT: ... has 12 user
    # reports found" and twelve source links about a superseded KB. Same contradiction, inverted, and
    # it recurred every patch Tuesday.
    with tempfile.TemporaryDirectory() as td:
        gen = Path(td) / "generated"
        gen.mkdir(parents=True)
        rec_path = gen / "2026-06-23-windows-11-25h2.md"
        record(rec_path, count=12, prose="12 user reports found for Windows 11 25H2.")
        # give it the full projection set a healthy record carries
        data, body = load_front_matter_and_body(rec_path)
        data["accepted_report_sources"] = [{"source": f"s{i}"} for i in range(12)]
        data["evidence_samples"] = [{"issue": "bsod"} for _ in range(5)]
        data["evidence_sample_visible_limit"] = 5
        data["update_consensus_label"] = "Negative"
        write_front_matter_and_body(rec_path, data, body)

        rolled, _b = load_front_matter_and_body(rec_path)
        rolled["target_kb"] = "KB5130777"          # next month's cumulative update
        rolled["target_os_build"] = "26200.9400"
        rolled["target_release_date"] = "2026-09-08T00:00:00Z"
        write_front_matter_and_body(rec_path, rolled, _b)

        # A second patch that still HAS accepted evidence, because retraction is fenced behind a
        # non-empty canonical population (see R5) and production's map is never empty -- 124 keys
        # live. Without this the fixture would exercise the guard, not the rollover.
        keep = gen / "2026-06-23-windows-11-26h1.md"
        record(keep, ver="26H1", kb="KB5121000", build="28000.2704", count=1)
        rollover_rows = rows_25 + [row(ver="26H1", kb="KB5121000", build="28000.2704",
                                       feat="26H1", rid="keep", url="https://x/keep")]
        changed, details = reconcile_record_counts(rollover_rows, gen)
        details = [d for d in details if "25h2" in d.get("record", "")]
        after, _ = load_front_matter_and_body(rec_path)
        check("R1 the count falls to zero after the rollover",
              after["update_report_count"] == 0, str(after["update_report_count"]))
        check("R2 the record stops asserting reports in prose",
              "user report" not in str(after.get("consensus_report") or ""),
              str(after.get("consensus_report"))[:90])
        check("R2 the summary claiming N reports is withdrawn",
              "update_consensus_summary" not in after, str(after.get("update_consensus_summary")))
        check("R3 stale source links and samples are withdrawn",
              "accepted_report_sources" not in after and "evidence_samples" not in after,
              f"sources={len(after.get('accepted_report_sources') or [])} "
              f"samples={len(after.get('evidence_samples') or [])}")
        check("R3 the verdict label returns to insufficient data",
              str(after.get("update_consensus_label")) == "Insufficient data",
              str(after.get("update_consensus_label")))
        check("R3 the retraction is reported, not silent",
              details and details[0].get("retracted"), str(details))
        # and the state fields still agree with the zero count
        check("R4 re-running does not rewrite the just-retracted record",
              reconcile_record_counts(rollover_rows, gen)[0] == 0,
              "a second pass rewrote an already-retracted record")
        check("R4 the zero state is internally consistent",
              after.get("evidence_state") == "official_only"
              and after.get("evidence_state_label") == "Official source only"
              and after.get("consensus_collection_status") == "deferred_official_only",
              str({k: after.get(k) for k in ("evidence_state", "evidence_state_label",
                                             "consensus_collection_status")}))

    # ---------- R5-R8: retraction must never outrun restoration ----------
    print("\n[R5-R8] the one deleting operation is fenced in")
    # Retracting DELETES published content, and deletion and regeneration are NOT symmetric:
    # reconciliation runs for every product, but only a product with a scoped --write-all step in the
    # lane gets its projections rebuilt. Two guards, each with its own failure story.
    def _projected(path):
        d, _b = load_front_matter_and_body(path)
        return {k: (len(d[k]) if isinstance(d.get(k), list) else "present")
                for k in ("update_consensus_summary", "accepted_report_sources",
                          "evidence_samples") if k in d}

    with tempfile.TemporaryDirectory() as td:
        gen = Path(td) / "generated"
        gen.mkdir(parents=True)
        win = gen / "2026-06-23-windows-11-25h2.md"
        record(win, count=12, prose="12 user reports found for Windows 11 25H2.")
        d, b = load_front_matter_and_body(win)
        d["accepted_report_sources"] = [{"source": f"s{i}"} for i in range(12)]
        d["evidence_samples"] = [{"issue": "bsod"}]
        write_front_matter_and_body(win, d, b)

        # R5: an EMPTY canonical population means the evidence file was missing, empty or key-less --
        # load_evidence() returns [] for all three -- not that every patch lost its reports. Live,
        # retracting on that input stripped 124 records and deleted 570 source entries in one pass,
        # and only two products could ever rebuild them. Reconciling the NUMBERS on an empty map is
        # fine: the next healthy run restores it. Deleting content is not.
        changed, _det = reconcile_record_counts([], gen)
        check("R5 an empty evidence population zeroes the count",
              load_front_matter_and_body(win)[0]["update_report_count"] == 0)
        check("R5 ... but deletes nothing",
              _projected(win) == {"update_consensus_summary": "present",
                                  "accepted_report_sources": 12, "evidence_samples": 1},
              str(_projected(win)))

    with tempfile.TemporaryDirectory() as td:
        gen = Path(td) / "generated"
        gen.mkdir(parents=True)
        # R6: a product with NO promotion step must never be retracted -- its count can legitimately
        # dip and recover (revalidate_consensus_evidence can mark rows uncounted), and coming back
        # with the count restored but the summary gone is a blocking QA error with no automated exit.
        # The fixture is blackmagic-davinci because obs-studio LEFT this category: it gained a
        # scoped promotion step and joined CONSENSUS_PROMOTION_PRODUCTS, which is the pairing this
        # test enforces -- membership and a rebuild path move together or not at all.
        dav = gen / "2026-04-14-davinci-resolve-21.md"
        dav_fm = {"layout": "aux-update", "update_entry": True, "product_id": "blackmagic-davinci",
                  "update_version": "21", "update_product": "DaVinci Resolve",
                  "update_report_count": 9, "confirmed_patch_specific_report_count": 9,
                  "consensus_report": "9 user reports found for DaVinci Resolve 21.",
                  "update_consensus_summary": "WAIT: DaVinci Resolve 21 has 9 user reports found.",
                  "accepted_report_sources": [{"source": f"s{i}"} for i in range(9)]}
        dav.write_text("---\n" + yaml.safe_dump(dav_fm, sort_keys=False) + "---\nbody\n",
                       encoding="utf-8")
        keep = gen / "2026-06-23-windows-11-26h1.md"   # keeps the canonical map non-empty
        record(keep, ver="26H1", kb="KB5121000", build="28000.2704", count=1)
        live = [row(ver="26H1", kb="KB5121000", build="28000.2704", feat="26H1",
                    rid="k", url="https://x/k")]
        reconcile_record_counts(live, gen)            # the davinci population is empty in `live`
        after, _ = load_front_matter_and_body(dav)
        check("R6 the dipped count is still corrected", after["update_report_count"] == 0)
        check("R6 a product the lane cannot regenerate keeps its projections",
              len(after.get("accepted_report_sources") or []) == 9
              and "update_consensus_summary" in after, str(_projected(dav)))

    # R6b: the log must NAME what was deleted. "0 -> 0" reads as a no-op.
    from lib.report_counts import format_reconcile_detail  # noqa: PLC0415
    line = format_reconcile_detail({"record": "w.md", "product_id": WIN, "version": "23H2",
                                    "before": 0, "after": 0,
                                    "retracted": ["accepted_report_sources", "evidence_samples"]})
    check("R6b a retraction is named in the run log, not hidden behind 0 -> 0",
          "accepted_report_sources" in line and "evidence_samples" in line, line)
    check("R6b an ordinary count change stays a one-liner",
          "retracted" not in format_reconcile_detail(
              {"record": "w.md", "product_id": WIN, "version": "25H2",
               "before": 32, "after": 12, "retracted": []}))

    # R7: the set of retractable products must EQUAL the scoped promotions in the lane, or the two
    # drift and retraction silently outruns restoration again.
    promoted = {flag_value(str(st.get("run") or ""), "--product-id")
                for st in steps
                if "apply_consensus_to_records" in str(st.get("run") or "")
                and "--write-all" in str(st.get("run") or "")}
    promoted.discard(None)
    # SUBSET, not equality. The safety property is one-directional: every RETRACTABLE product must
    # have a rebuild path, because retraction without one strands a record. The converse is not a
    # hazard -- promoting a product that is not retraction-eligible is always safe, and Acrobat
    # Pro/Reader need exactly that (they can drift, but never retract). Equality forbade giving them
    # a rebuild path at all, which is how 83 Acrobat records came to have none once the unscoped
    # --write-all in davinci-updates.yml was scoped away.
    check("R7 every retractable product has a scoped promotion in the lane",
          set(CONSENSUS_PROMOTION_PRODUCTS) <= promoted,
          f"missing={sorted(set(CONSENSUS_PROMOTION_PRODUCTS) - promoted)} "
          f"workflow={sorted(promoted)}")
    check("R7 adobe-premiere-pro is never promoted -- its prose is hand-authored",
          "adobe-premiere-pro" not in promoted, str(sorted(promoted)))
    check("R8 Windows is retractable, because the lane can rebuild it",
          WIN in CONSENSUS_PROMOTION_PRODUCTS)
    check("R8 obs-studio is retractable, because the lane now rebuilds it",
          "obs-studio" in CONSENSUS_PROMOTION_PRODUCTS)
    check("R8 a product with no promotion step is not retractable",
          "blackmagic-davinci" not in CONSENSUS_PROMOTION_PRODUCTS
          and "adobe-premiere-pro" not in CONSENSUS_PROMOTION_PRODUCTS
          and "adobe-acrobat-pro" not in CONSENSUS_PROMOTION_PRODUCTS)

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
