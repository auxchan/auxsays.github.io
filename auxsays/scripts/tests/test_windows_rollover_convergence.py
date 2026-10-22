#!/usr/bin/env python3
"""A Windows record counts exactly its own cumulative update -- across a rollover, and at zero.

A Windows record tracks ONE cumulative update (a KB / OS build) inside a feature train, and the
train rolls over roughly monthly. Evidence accepted for the superseded update is still true --
about the OLD patch -- but it is not evidence about the NEW one. AUXSAYS answers "should I install
THIS exact update", so each patch's page must count its own population and nobody else's.

WHAT CHANGED, AND WHY THIS FILE READS DIFFERENTLY THAN ITS TITLE SUGGESTS. It was written when one
record tracked a whole TRAIN: the single 25H2 page followed the newest KB, so a rollover moved the
page's identity and every report about the superseded update stopped counting anywhere. Windows is
now build-aware -- one record IS one cumulative update -- so a rollover CREATES a record rather
than re-pointing one, and moving a published record's build is refused on the write path. The
superseded update keeps its page, its URL and its reports.

WHAT THIS LOCKS DOWN, end to end, in passes of the authority:

    state A    record A targets KB-A / build-A, two rows name A  -> count 2, projections present
    rollover   record B appears alongside A, no B rows           -> A stays 2; B is 0 and claims
                                                                    nothing; A's rows never move
    population record A's rows leave the accepted set            -> count 0, projections retracted
    recovery   one row names B                                   -> count 1, projections rebuilt

At the zero step the record must stop CLAIMING reports, not merely print 0: the source list, the
samples and the count-bearing prose all have to go, or the page keeps asserting evidence its own
authority says does not exist. Equally, the historical A rows must remain in the evidence store --
convergence changes the current PROJECTION, never the historical record of what was observed.

Measured motivation, from the live corpus at the time of writing: all 38 counted Windows rows
returned ``stale_due_to_patch_rollover`` against the current targets while the records published
2 / 14 / 1 reports; and across 16 target advances in git history, not one changed
``update_report_count`` in the same commit.

Offline and deterministic: every record is written into a temporary directory. The real repository
is never read for mutation and never written.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_windows_rollover_convergence.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

from lib.normalize import split_front_matter  # noqa: E402
from lib.report_counts import (  # noqa: E402
    CONSENSUS_PROMOTION_PRODUCTS,
    ZERO_COUNT_PROJECTION_FIELDS,
    counted_evidence_counts,
    reconcile_record_counts,
    windows_targets_from_front_matter,
)
from patch_collectors.base import windows_identity_gate  # noqa: E402

WIN = "microsoft-windows-11"
NEWLINE = chr(10)

KB_A, BUILD_A = "KB5101684", "26200.8973"
KB_B, BUILD_B = "KB5121003", "26200.9168"

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
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


def record(train: str, kb: str, build: str, count: int) -> dict:
    """A Windows record in the shape reconcile expects, with projections for `count` reports.

    Carries ``target_build`` because Windows is build-aware: one record is one cumulative update,
    so its exact build is part of its canonical identity and every count keys on it."""
    data = {
        "update_entry": True,
        "product_id": WIN,
        "update_version": train,
        "update_product": "Windows 11",
        "target_build": build,
        "target_kb": kb,
        "target_os_build": build,
        "target_feature_version": train,
        "target_release_date": "2026-08-01T00:00:00Z",
        "update_report_count": count,
        "confirmed_patch_specific_report_count": count,
        # Fields the RETRACTION must not touch. They were described here as "human-owned", which
        # is no longer accurate for Windows: the scoped consensus promotion now owns
        # update_decision_label / update_decision_body / practical_recommendations, because a
        # Windows page that gathered reports otherwise kept publishing "consensus is deferred"
        # beside its own report count. What W7 tests is unchanged and still worth pinning --
        # reconcile retracts COUNT PROJECTIONS and nothing else, so a lane that only reconciles
        # never silently rewrites the verdict.
        "update_decision_label": "WAIT",
        "update_decision_body": "Hand-written editorial guidance that automation must not rewrite.",
        "practical_recommendations": ["Pilot on a spare device first."],
        "update_consensus_confidence": "Low-Medium",
    }
    if count:
        data.update({
            "update_report_count": count,
            "consensus_report": f"{count} user reports found for Windows 11 {train}.",
            "quick_verdict": f"WAIT: Windows 11 {train} has {count} user reports found.",
            "update_consensus_summary": f"WAIT: Windows 11 {train} has {count} user reports found.",
            "update_consensus_label": "Negative",
            "accepted_report_sources": [{"source_url": f"https://example.invalid/{i}"}
                                        for i in range(count)],
            "evidence_samples": [{"source_url": f"https://example.invalid/{i}"} for i in range(count)],
            "evidence_sample_visible_limit": 5,
            "evidence_source_limitations": ["Small sample size."],
        })
    return data


def row(train: str, kb: str, build: str, n: int) -> dict:
    return {
        "product_id": WIN,
        "update_version": train,
        # The row states the patch it belongs to, exactly as the collector now writes it.
        "target_build": build,
        "source_url": f"https://learn.microsoft.com/en-us/answers/questions/{n}/x",
        "counted": True,
        "patch_version_matched": True,
        "matched_kb": kb,
        "matched_os_build": build,
        "matched_feature_version": train,
        "source_date": "2026-08-05",
        "report_title": f"Report {n}",
    }


def other_product_record() -> dict:
    """A non-Windows record with live evidence.

    Retraction is fenced behind `bool(counts)` -- a wholly empty count map means the evidence file
    was missing or unreadable, and stripping 124 records on that basis is not recoverable. That
    fence is GLOBAL, so a tree containing only Windows records whose rows have all gone stale
    produces an empty map and never retracts. Production always has other products' evidence, so
    the fixture must too, or it would test a state the lane never reaches.
    """
    return {"update_entry": True, "product_id": "obs-studio", "update_version": "32.1.2",
            "update_product": "OBS Studio", "update_report_count": 1,
            "confirmed_patch_specific_report_count": 1}


def other_product_row() -> dict:
    return {"product_id": "obs-studio", "update_version": "32.1.2", "counted": True,
            "patch_version_matched": True, "source_url": "https://example.invalid/obs"}


def write_tree(tmp: Path, records: dict[str, dict]) -> None:
    for name, data in records.items():
        text = "---" + NEWLINE + yaml.safe_dump(data, sort_keys=False, allow_unicode=True) + "---" + NEWLINE
        (tmp / name).write_text(text, encoding="utf-8")


def read_record(tmp: Path, name: str) -> dict:
    fr, _body = split_front_matter((tmp / name).read_text(encoding="utf-8"))
    return yaml.safe_load(fr) or {}


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Windows consensus converges to the CURRENT cumulative update after rollover")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ---------------- STATE A ----------------
        print(NEWLINE + "[W-A] state A: target KB-A/build-A with two matching rows")
        evidence = [row("25H2", KB_A, BUILD_A, 1), row("25H2", KB_A, BUILD_A, 2),
                    other_product_row()]
        write_tree(tmp, {"25h2.md": record("25H2", KB_A, BUILD_A, 0),
                         "obs.md": other_product_record()})
        reconcile_record_counts(evidence, tmp)
        a = read_record(tmp, "25h2.md")
        check("W-A count is 2", int(a.get("update_report_count") or 0) == 2,
              str(a.get("update_report_count")))

        # rebuild the projections a real promotion would have written, so the rollover step has
        # something to retract -- reconcile sets counts, promotion writes the source list.
        write_tree(tmp, {"25h2.md": record("25H2", KB_A, BUILD_A, 2),
                         "obs.md": other_product_record()})

        # ---------------- ROLLOVER ----------------
        # WHAT A ROLLOVER IS NOW. This step used to REWRITE 25h2.md so its target advanced to
        # KB-B/build-B -- the one-record-per-train model, where a single page followed the train
        # and its evidence went dark every Patch Tuesday. That advance is now refused on the write
        # path (lib.write_update_record.refresh_existing_record): a record's build is its identity,
        # stamped into its permalink and filename, so a new cumulative update gets its OWN record.
        #
        # So the rollover is modelled as it actually happens: record B APPEARS alongside record A.
        # The first thing to assert is the property this whole change exists to create -- A does
        # not go dark. Its two reports stay counted, on A's own page, forever.
        print(NEWLINE + "[W0] rollover: record B appears; record A keeps its own evidence")
        write_tree(tmp, {"25h2.md": record("25H2", KB_A, BUILD_A, 2),
                         "25h2-b.md": record("25H2", KB_B, BUILD_B, 0),
                         "obs.md": other_product_record()})
        reconcile_record_counts(evidence, tmp)
        a_after, b_new = read_record(tmp, "25h2.md"), read_record(tmp, "25h2-b.md")
        check("W0 the superseded update keeps its own count -- it does not go dark",
              int(a_after.get("update_report_count") or 0) == 2,
              str(a_after.get("update_report_count")))
        check("W0 the new update starts at zero and claims nothing",
              int(b_new.get("update_report_count") or 0) == 0
              and "accepted_report_sources" not in b_new,
              str(b_new.get("update_report_count")))
        check("W0 A's rows are never borrowed by B",
              counted_evidence_counts(
                  evidence, windows_targets=windows_targets_from_front_matter([a_after, b_new])
              ).get((WIN, "25H2", BUILD_B), 0) == 0,
              str(counted_evidence_counts(
                  evidence, windows_targets=windows_targets_from_front_matter([a_after, b_new]))))

        # ---------------- RETRACTION ----------------
        # The zero state is still reachable, and still has to be safe: a record's accepted
        # population empties when its rows are re-adjudicated or withdrawn, not only when a target
        # moves. Drive it the way production now can, and assert the identical guarantees.
        print(NEWLINE + "[W1-W7] the accepted population empties: the page must stop claiming reports")
        write_tree(tmp, {"25h2.md": record("25H2", KB_B, BUILD_B, 2),
                         "obs.md": other_product_record()})
        before_rows = list(evidence)
        changed, detail = reconcile_record_counts(evidence, tmp)
        b = read_record(tmp, "25h2.md")

        check("W1 the current count converges to 0", int(b.get("update_report_count") or 0) == 0,
              str(b.get("update_report_count")))
        check("W1 confirmed_patch_specific_report_count agrees",
              int(b.get("confirmed_patch_specific_report_count") or 0) == 0,
              str(b.get("confirmed_patch_specific_report_count")))
        check("W2 historical evidence rows are NOT deleted", evidence == before_rows and len(evidence) == 3,
              f"{len(evidence)} rows")
        check("W3 the A rows are excluded by identity, not by deletion",
              all(windows_identity_gate(r, {"target_kb": KB_B, "target_os_build": BUILD_B,
                                            "target_feature_version": "25H2"})
                  == (False, "stale_due_to_patch_rollover")
                  for r in evidence if r.get("product_id") == WIN),
              str([windows_identity_gate(r, {"target_kb": KB_B, "target_os_build": BUILD_B,
                                             "target_feature_version": "25H2"})
                   for r in evidence if r.get("product_id") == WIN]))
        check("W4 the accepted-source projection is retracted",
              "accepted_report_sources" not in b, str(b.get("accepted_report_sources")))
        check("W5 evidence samples are retracted",
              "evidence_samples" not in b and "evidence_sample_visible_limit" not in b,
              str(b.get("evidence_samples")))
        check("W6 count-bearing prose no longer claims reports",
              "2 user reports" not in str(b.get("consensus_report"))
              and "2 user reports" not in str(b.get("quick_verdict"))
              and "update_consensus_summary" not in b,
              f"report={str(b.get('consensus_report'))[:60]!r} verdict={str(b.get('quick_verdict'))[:60]!r}")
        check("W6 the consensus label returns to the zero shape",
              str(b.get("update_consensus_label")) != "Negative", str(b.get("update_consensus_label")))
        # W7 SPLIT, because these three fields changed hands. The install VERDICT
        # (update_decision_label / update_decision_body / practical_recommendations) is written by
        # the scoped consensus promotion for every product in CONSENSUS_PROMOTION_PRODUCTS, so at a
        # canonical zero it is a count projection like any other and must go -- otherwise the record
        # stores "WAIT" with no reports behind it, which is precisely what
        # qa_patch_records.official_only_zero_reports_recommendation_language names. The retraction
        # fence keeps this away from adobe-premiere-pro, the product whose prose really is hand
        # authored, because premiere is not in that set and so is never retracted at all.
        for field in ("update_decision_label", "update_decision_body", "practical_recommendations"):
            check(f"W7 the verdict field {field} is retracted at zero", field not in b,
                  f"{field} = {b.get(field)!r}")
        # Confidence is NOT a count projection in this codebase: a real zero record stores "Low",
        # and 779 of 896 live records already disagree with _confidence(0), so touching it here
        # would be a corpus-wide rewrite disguised as a coherence fix.
        check("W7 update_consensus_confidence is still untouched",
              b.get("update_consensus_confidence") == record("25H2", KB_B, BUILD_B, 0).get("update_consensus_confidence"),
              f"update_consensus_confidence = {b.get('update_consensus_confidence')!r}")

        # ---------------- RECOVERY ----------------
        print(NEWLINE + "[W8/W9] recovery: one report naming the NEW target")
        evidence.append(row("25H2", KB_B, BUILD_B, 3))
        reconcile_record_counts(evidence, tmp)
        c = read_record(tmp, "25h2.md")
        check("W8 the count repopulates to 1", int(c.get("update_report_count") or 0) == 1,
              str(c.get("update_report_count")))
        # Keyed by the canonical TRIPLE: with only record B in view, B counts its one row and the
        # two A rows are attributed to no record at all rather than folded into B's number.
        check("W8 the historical A rows are still stored and still not counted here",
              len(evidence) == 4
              and counted_evidence_counts(
                  evidence, windows_targets=windows_targets_from_front_matter([c])
              ) == {(WIN, "25H2", BUILD_B): 1, ("obs-studio", "32.1.2", ""): 1},
              str(counted_evidence_counts(
                  evidence, windows_targets=windows_targets_from_front_matter([c]))))
        again, _d = reconcile_record_counts(evidence, tmp)
        check("W9 a second identical pass writes nothing (idempotent)", again == 0, f"{again} writes")

        # ---------------- TRAIN INDEPENDENCE ----------------
        print(NEWLINE + "[W10/W11] trains are independent and never borrow each other's evidence")
        tmp2 = tmp / "multi"
        tmp2.mkdir()
        write_tree(tmp2, {
            "obs.md": other_product_record(),
            "24h2.md": record("24H2", KB_B, "26100.9278", 0),
            "25h2.md": record("25H2", KB_B, BUILD_B, 0),
            "26h1.md": record("26H1", "KB5120996", "28000.2804", 0),
        })
        shared = [row("25H2", KB_B, BUILD_B, 10), row("24H2", KB_B, "26100.9278", 11),
                  other_product_row()]
        reconcile_record_counts(shared, tmp2)
        r24, r25, r26 = (read_record(tmp2, n) for n in ("24h2.md", "25h2.md", "26h1.md"))
        check("W10 each train counts only its own rows",
              (int(r24.get("update_report_count") or 0),
               int(r25.get("update_report_count") or 0),
               int(r26.get("update_report_count") or 0)) == (1, 1, 0),
              f"{r24.get('update_report_count')}/{r25.get('update_report_count')}/{r26.get('update_report_count')}")
        # 24H2 and 25H2 genuinely share KB5121003 in the live corpus, so the shared KB must not
        # let a 25H2 row count for 24H2: the OS build is what separates them.
        cross = windows_identity_gate(row("25H2", KB_B, BUILD_B, 12),
                                      {"target_kb": KB_B, "target_os_build": "26100.9278",
                                       "target_feature_version": "24H2"})
        check("W11 a shared KB does not let one train borrow another's build",
              cross[0] is False, str(cross))

        # ---------------- FENCES ----------------
        print(NEWLINE + "[W-F] retraction fences")
        check("W-F Windows is retraction-eligible", WIN in CONSENSUS_PROMOTION_PRODUCTS,
              str(sorted(CONSENSUS_PROMOTION_PRODUCTS)))
        tmp3 = tmp / "empty"
        tmp3.mkdir()
        write_tree(tmp3, {"25h2.md": record("25H2", KB_B, BUILD_B, 2),
                          "obs.md": other_product_record()})
        reconcile_record_counts([], tmp3)
        e = read_record(tmp3, "25h2.md")
        check("W-F an EMPTY evidence file never retracts (unreadable != nothing happened)",
              "accepted_report_sources" in e, "projections were stripped on an empty evidence map")
        check("W-F the zero-projection field set is the documented one",
              set(ZERO_COUNT_PROJECTION_FIELDS) == {
                  "update_consensus_summary", "accepted_report_sources", "evidence_samples",
                  "evidence_sample_visible_limit", "evidence_source_limitations",
                  "update_decision_label", "update_decision_body", "practical_recommendations"},
              str(ZERO_COUNT_PROJECTION_FIELDS))

    # ---------------- W14: the rollover lane owns its own repair ----------------
    print(NEWLINE + "[W14] the lane that advances the identity repairs it, before QA")
    wf = _REPO / ".github" / "workflows" / "patch-ingest.yml"
    doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
    steps: list[dict] = []
    for job in (doc.get("jobs") or {}).values():
        steps.extend(job.get("steps") or [])
    runs = [str(s.get("run") or "") for s in steps]

    def index_of(needle: str) -> int:
        return next((i for i, r in enumerate(runs) if needle in r), -1)

    ingest_at = index_of("patch_ingest.py")
    reconcile_at = index_of("build_consensus_from_evidence.py")
    promote_at = index_of("apply_consensus_to_records.py")
    qa_at = index_of("qa_patch_records.py")
    writeback_at = index_of("automation_writeback.py")
    check("W14 the ingest lane reconciles after ingesting", 0 <= ingest_at < reconcile_at,
          f"ingest={ingest_at} reconcile={reconcile_at}")
    # Structural, not a literal string: the scope must be exactly the set of products whose EXISTING
    # record identity this lane can advance. Pinning the literal would let a second rolling-identity
    # product be added to the repo and silently omitted here.
    rolling_products = {WIN}          # products with in-place target identity; see WINDOWS_IDENTITY_FIELDS
    scoped = set()
    if reconcile_at >= 0:
        toks = runs[reconcile_at].replace(chr(92) + NEWLINE, " ").split()
        for i, tok in enumerate(toks):
            if tok == "--product-id" and i + 1 < len(toks):
                scoped.add(toks[i + 1].strip("'\""))
            elif tok.startswith("--product-id="):
                scoped.add(tok.split("=", 1)[1].strip("'\""))
    check("W14 its reconcile is SCOPED to exactly the rolling-identity products",
          scoped == rolling_products, f"scoped={sorted(scoped)} expected={sorted(rolling_products)}")
    check("W14 every rolling-identity product is retraction-eligible",
          rolling_products <= set(CONSENSUS_PROMOTION_PRODUCTS),
          f"{sorted(rolling_products - set(CONSENSUS_PROMOTION_PRODUCTS))} cannot be rebuilt")
    check("W14 the repair steps only run when this dispatch could have touched that product",
          all("github.event.inputs.source" in str(steps[i].get("if") or "")
              for i in (reconcile_at, promote_at) if i >= 0),
          "a dispatch scoped to another product would still reconcile/promote Windows")
    check("W14 it reconciles ONLY, without republishing consensus it did not gather",
          reconcile_at >= 0 and "--reconcile-only" in runs[reconcile_at],
          runs[reconcile_at] if reconcile_at >= 0 else "no reconcile step")
    check("W14 promotion follows reconcile (the repopulate half)",
          0 <= reconcile_at < promote_at, f"reconcile={reconcile_at} promote={promote_at}")
    check("W14 both run BEFORE QA -- a gate ahead of the repair is the #70 wedge",
          0 <= promote_at < qa_at, f"promote={promote_at} qa={qa_at}")
    check("W14 and before writeback, so the repair is what gets committed",
          0 <= qa_at < writeback_at, f"qa={qa_at} writeback={writeback_at}")
    check("W14 writeback still covers the generated records it just repaired",
          writeback_at >= 0 and "auxsays/updates/generated" in runs[writeback_at],
          "generated records are not in the writeback allow list")

    # ---------------- CROSS-PRODUCT ----------------
    print(NEWLINE + "[W12/W13] neighbouring products are unaffected")
    cand = (_REPO / "auxsays" / "updates" / "generated"
            / "2026-07-23-microsoft-powerpoint-2607-20228-20110.md")
    check("W12 Candidate 1 record exists", cand.exists(), str(cand))
    if cand.exists():
        fr, _b = split_front_matter(cand.read_text(encoding="utf-8"))
        d = yaml.safe_load(fr) or {}
        check("W12 Candidate 1 is still 2607 / 20228.20110 with one counted report",
              str(d.get("update_version")) == "2607"
              and str(d.get("target_build")) == "20228.20110"
              and int(d.get("update_report_count") or 0) == 1,
              f"{d.get('update_version')}/{d.get('target_build')} count={d.get('update_report_count')}")
    obs_src = (_REPO / "auxsays" / "scripts" / "collect_obs_reports.py").read_text(encoding="utf-8")
    check("W13 the OBS contrast veto from #79 is still wired in",
          "contradiction_reason" in obs_src and "target_outcome" in obs_src,
          "the OBS version veto is missing")

    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
