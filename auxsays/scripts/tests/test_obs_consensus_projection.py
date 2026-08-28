#!/usr/bin/env python3
"""OBS consensus projections must describe the population the count comes from.

THE LIVE DEFECT (main `4f504a0d`). 2026-08-14-obs-studio-32-2-2.md published:

    update_report_count: 7          accepted_report_sources: 3 entries
    evidence_samples:    3          evidence_sample_visible_limit: 5
    consensus_report:        "3 user reports found for OBS Studio 32.2.2. ..."
    update_consensus_summary: "WAIT: OBS Studio 32.2.2 has 3 user reports found. ..."
    quick_verdict:            "TEST FIRST: OBS Studio 32.2.2 has 3 user reports found."

A reader saw 7 and 3 on one page. Row-level, the count was RIGHT: all seven rows are counted, none
excluded, and the three published sources are a strict SUBSET (issues 13803/13806/13807) of the
seven, with zero entries published that are not counted. The other four -- 13823, 13824, 13829,
13830 -- are valid counted reports that the projection never picked up. Classification:
STALE_EXHAUSTIVE_PROJECTION.

WHY IT DRIFTED, and why the fix is a workflow step rather than a value edit. `accepted_report_sources`
is exhaustive by construction (obs 32.1.2 live: count 101, sources 101) and `evidence_samples` is
capped at 5 by `_representative_rows`. The `evidence_sample_visible_limit` field is inert: the layout
assigns `visible_evidence_limit` from it once and never reads that variable, and the source-list
collapse uses its own hardcoded `> 5`. Reconciliation writes only the NUMBER, so
projections are rebuilt only by a scoped `apply_consensus_to_records --write-all`. obs-studio had no
such step in the scheduled lane -- its coherence had been restored only by the UNSCOPED --write-all in
davinci-updates.yml, which is workflow_dispatch-only. Any OBS record accumulating rows after the last
manual run drifted silently. Exactly 1 of 124 live records with a positive count was drifting; the
other 123 are what establish the semantics asserted here.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_obs_consensus_projection.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
from lib.patch_identity import patch_key  # noqa: E402
from lib.report_counts import (CONSENSUS_PROMOTION_PRODUCTS,  # noqa: E402
                               counted_evidence_counts, windows_targets_from_front_matter)
from lib.write_update_record import DEFAULT_CONSENSUS, DEFERRED_CONSENSUS_REPORT  # noqa: E402

OBS = "obs-studio"
VER = "32.2.2"
# the real issue numbers, so a reader can check the fixture against the source
COUNTED_ISSUES = ("13803", "13806", "13807", "13823", "13824", "13829", "13830")
PUBLISHED_SUBSET = ("13803", "13806", "13807")

NEWLINE = chr(10)

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


def row(issue: str, *, counted=True, matched=True, sentiment="negative", severity="medium",
        theme="capture-source issues", url=None):
    return {
        "id": f"obs-{issue}",
        "product_id": OBS, "update_version": VER, "target_build": "",
        "source_url": url or f"https://github.com/obsproject/obs-studio/issues/{issue}",
        "source_type": "github_issue", "source_name": "OBS Studio GitHub",
        "captured_at": "2026-08-20T00:00:00Z", "source_date": "2026-08-18T00:00:00Z",
        "counted": counted, "patch_version_matched": matched,
        "sentiment": sentiment, "severity": severity,
        "issue_theme": theme, "match_basis": "body",
    }


def obs_record(path: Path, *, count: int, sources: int, samples: int, prose_count: int) -> None:
    """An OBS record in the DRIFTED shape: the count already advanced, projections did not."""
    data = {
        "layout": "aux-update", "update_entry": True,
        "product_id": OBS, "update_version": VER, "update_product": "OBS Studio",
        "update_report_count": count, "confirmed_patch_specific_report_count": count,
        "evidence_state": "pilot_sample", "evidence_state_label": "Verified reports",
        "consensus_collection_status": "pilot_initial_sample",
        "evidence_sample_visible_limit": 5,
        "consensus_report": f"{prose_count} user reports found for OBS Studio {VER}.",
        "update_consensus_summary": f"WAIT: OBS Studio {VER} has {prose_count} user reports found.",
        "quick_verdict": f"TEST FIRST: OBS Studio {VER} has {prose_count} user reports found.",
        "update_decision_label": "TEST FIRST",
        "update_decision_body": "Test on a backup profile before using this OBS build.",
        "practical_recommendations": ["Test with a backup scene collection and profile."],
        "accepted_report_sources": [{"url": f"https://github.com/obsproject/obs-studio/issues/{i}"}
                                    for i in PUBLISHED_SUBSET[:sources]],
        "evidence_samples": [{"issue": "capture"} for _ in range(samples)],
    }
    path.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\nbody\n",
                    encoding="utf-8")


def canonical(rows) -> dict:
    return counted_evidence_counts(rows, windows_targets={})


def proposal(rows, record):
    """What the intended writer proposes -- the real functions, not a re-implementation."""
    fields = acr._proposed_record_fields(OBS, VER, rows, record, "2026-08-20T00:00:00Z", build="")
    fields.update(acr._record_coherence_fields(OBS, VER, len(rows), record,
                                              acr._issue_counter(OBS, rows)))
    return fields


def run() -> int:
    print("=" * 78)
    print("OBS consensus projections vs the counted population")
    print("=" * 78)

    seven = [row(i) for i in COUNTED_ISSUES]

    # ---------- O1 ----------
    print("\n[O1] the canonical counted population is seven, and nothing is excluded")
    key = patch_key(OBS, VER, "")
    check("O1 canonical count is 7", canonical(seven).get(key) == 7,
          str(canonical(seven).get(key)))
    groups = acr._group_rows(seven, is_candidate_mode=False)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "obs.md"
        obs_record(p, count=7, sources=3, samples=3, prose_count=3)
        front = yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1])
    inc, exc = acr._filter_rows(groups.get(key) or [], product_id=OBS, version=VER,
                                is_candidate_mode=False, record=front)
    check("O1 the consensus selector agrees at 7", len(inc) == 7, f"{len(inc)} included")
    check("O1 no row is excluded", not exc, str([r.get("_exclusion_reason") for r in exc]))

    # ---------- O2 ----------
    print("\n[O2] each public field obeys its own documented semantics")
    fields = proposal(seven, front)
    check("O2 accepted_report_sources is EXHAUSTIVE -- one entry per counted row",
          len(fields["accepted_report_sources"]) == 7,
          str(len(fields["accepted_report_sources"])))
    limit = int(fields.get("evidence_sample_visible_limit") or 0)
    # Two SEPARATE literal 5s: the field at apply_consensus_to_records.py:907 and the cap in
    # _representative_rows(limit=5). The field governs no rendering -- the layout assigns
    # visible_evidence_limit from it once and never reads that variable, and the source-list
    # collapse uses its own hardcoded > 5. So this asserts the WRITER caps samples and that the
    # two literals agree, which is a real coupling test; it does not claim the field causes the cap.
    check("O2 evidence_samples is a SAMPLE, and the writer's cap matches the published limit",
          limit > 0 and len(fields["evidence_samples"]) == min(limit, 7),
          f"limit={limit} samples={len(fields['evidence_samples'])}")
    check("O2 the count-derived sentences state the counted total",
          "7 user report" in fields["consensus_report"]
          and "has 7 user report" in fields["update_consensus_summary"],
          f"{fields['consensus_report'][:60]!r} / {fields['update_consensus_summary'][:60]!r}")
    check("O2 the numeric fields state the counted total",
          fields["update_report_count"] == 7
          and fields["confirmed_patch_specific_report_count"] == 7)
    # The exhaustive list must never be silently truncated to the sample cap.
    check("O2 the exhaustive list is NOT capped at the sample limit",
          len(fields["accepted_report_sources"]) > limit,
          "sources were truncated to the sample cap")

    # ---------- O3 ----------
    print("\n[O3] duplicates cannot inflate the projection")
    # The guarantee lives at APPEND time, not at projection time -- `_filter_rows` does no URL
    # dedup, and the projection writer faithfully emits one entry per row it is handed. So this
    # asserts the layer that actually owns it. NOTE the exemption: rows whose match_basis is
    # `embedded_listing_report_card` are deliberately NOT URL-deduplicated, because several distinct
    # reports legitimately share one listing-page URL -- the single duplicate append-key in the live
    # corpus is exactly that (two Premiere reports, distinct ids). A duplicate CAN therefore reach a
    # projection via that basis. It cannot happen for OBS: collect_obs_reports.match_basis() returns
    # only "title" or "body", so this fixture uses the default basis on purpose.
    from patch_collectors.base import (append_evidence_rows, evidence_key,  # noqa: PLC0415
                                       write_evidence_file)
    with tempfile.TemporaryDirectory() as td:
        ev = Path(td) / "consensus_evidence.yml"
        # Seed through the real writer. append_evidence_rows does an ATOMIC APPEND that preserves the
        # existing bytes exactly, so a hand-written `evidence: []` inline empty list would make the
        # appended block-list items invalid YAML -- the seed has to be a file the writer produced.
        write_evidence_file(list(seven), ev)
        added_again, total_after, rows_after = append_evidence_rows([row("13803")], ev)
        check("O3 the seven distinct reports are stored", len(rows_after) >= 7, str(len(rows_after)))
        check("O3 re-appending an existing source URL adds nothing",
              added_again == 0 and total_after == 7, f"added={added_again} total={total_after}")
        keys = [evidence_key(r, "source_url") for r in rows_after]
        check("O3 the stored corpus holds no duplicate append-key",
              len(keys) == len(set(keys)), f"{len(keys)} rows, {len(set(keys))} unique keys")
    urls = [str(s.get("url") or s.get("source_url") or "")
            for s in fields["accepted_report_sources"]]
    check("O3 the projection over that population has no repeated URL",
          len(urls) == len(set(urls)), f"{len(urls)} entries, {len(set(urls))} unique")

    # ---------- O4 ----------
    print("\n[O4] excluded evidence never reaches the projection")
    with_excluded = seven + [row("99999", counted=False),
                             row("99998", matched=False),
                             row("99997", sentiment="unclassified")]
    g2 = acr._group_rows(with_excluded, is_candidate_mode=False)
    inc2, exc2 = acr._filter_rows(g2.get(key) or [], product_id=OBS, version=VER,
                                  is_candidate_mode=False, record=front)
    f2 = proposal(inc2, front)
    proj = " ".join(str(s) for s in f2["accepted_report_sources"])
    check("O4 the selector still admits exactly the seven", len(inc2) == 7, f"{len(inc2)}")
    check("O4 no excluded row appears in the source projection",
          not any(bad in proj for bad in ("99999", "99998", "99997")), proj[:160])
    check("O4 the count does not include excluded rows",
          f2["update_report_count"] == 7, str(f2["update_report_count"]))

    # ---------- O5 ----------
    print("\n[O5] only count-bearing text is rewritten; other editorial text is left alone")
    # quick_verdict IS count-derived on OBS ("has N user reports found"), so it MUST change. The
    # decision body and recommendations are not, and must come back identical -- the repair is not a
    # licence to regenerate editorial prose.
    check("O5 quick_verdict is updated, because it states the count",
          "has 7 user reports found" in str(fields.get("quick_verdict")),
          str(fields.get("quick_verdict")))
    check("O5 the decision body is not rewritten with different content",
          str(fields.get("update_decision_body") or front["update_decision_body"]).strip() != "",
          "decision body came back empty")
    check("O5 no field outside the writer's own set is proposed",
          "release_summary" not in fields and "official_summary" not in fields,
          str(sorted(set(fields) & {"release_summary", "official_summary"})))

    # ---------- O6 ----------
    print("\n[O6] the drifted record becomes coherent")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "obs.md"
        obs_record(p, count=7, sources=3, samples=3, prose_count=3)
        before = yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1])
        check("O6 the fixture reproduces the real contradiction",
              before["update_report_count"] == 7
              and len(before["accepted_report_sources"]) == 3
              and "has 3 user reports found" in before["quick_verdict"],
              str(before["update_report_count"]))
        after = dict(before)
        after.update(proposal(seven, before))
        check("O6 count, sources and prose all state 7 afterwards",
              after["update_report_count"] == 7
              and len(after["accepted_report_sources"]) == 7
              and "7 user report" in after["consensus_report"]
              and "has 7 user reports found" in after["quick_verdict"],
              f"count={after['update_report_count']} "
              f"sources={len(after['accepted_report_sources'])}")
        check("O6 samples land on the cap, not on the stale 3",
              len(after["evidence_samples"]) == 5, str(len(after["evidence_samples"])))

        # ---------- O7 ----------
        print("\n[O7] a second application changes nothing substantive")
        again = dict(after)
        again.update(proposal(seven, after))
        ignored = set(getattr(acr, "RECORD_SUBSTANTIVE_COMPARE_IGNORED", set())) | {
            "record_last_updated", "evidence_last_checked", "status_events",
            "status_events_append"}
        drift = [k for k in set(after) | set(again)
                 if k not in ignored and after.get(k) != again.get(k)]
        check("O7 no substantive field changes on the second pass", not drift, str(drift))

    # ---------- O8 ----------
    print("\n[O8] the #69 collector boundary is untouched")
    owned = set(acr.COLLECTOR_WRITABLE_FIELDS)
    projection_fields = {"accepted_report_sources", "evidence_samples",
                         "evidence_sample_visible_limit", "consensus_report",
                         "update_consensus_summary", "quick_verdict",
                         "update_report_count", "confirmed_patch_specific_report_count"}
    check("O8 collectors own only the two freshness fields",
          owned == {"evidence_last_checked", "record_last_updated"}, str(sorted(owned)))
    check("O8 no projection field is collector-writable",
          not (owned & projection_fields), str(sorted(owned & projection_fields)))
    probe = {k: "MUTANT" for k in projection_fields}
    probe["evidence_last_checked"] = "2026-08-21T00:00:00Z"
    kept = acr.collector_owned_fields(probe)
    check("O8 a collector proposing projection fields has them filtered out",
          set(kept) <= owned, str(sorted(set(kept) - owned)))

    # ---------- O9 ----------
    print("\n[O9] the QA warning that exposed this clears for repaired data, and only then")
    import qa_patch_records as qa  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        drifted = Path(td) / "2026-08-14-obs-studio-32-2-2.md"
        obs_record(drifted, count=7, sources=3, samples=3, prose_count=3)
        orig = qa.load_yaml
        try:
            qa.load_yaml = lambda *_a, **_k: seven
            errs_before, warns_before = qa.scan_evidence_count_alignment([drifted])
            fixed = Path(td) / "2026-08-14-obs-studio-32-2-2-fixed.md"
            obs_record(fixed, count=7, sources=3, samples=3, prose_count=3)
            data = yaml.safe_load(fixed.read_text(encoding="utf-8").split("---", 2)[1])
            data.update(proposal(seven, data))
            fixed.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\nbody\n",
                             encoding="utf-8")
            errs_after, warns_after = qa.scan_evidence_count_alignment([fixed])
        finally:
            qa.load_yaml = orig
        codes_before = [w.get("code") for w in warns_before]
        codes_after = [w.get("code") for w in warns_after]
        check("O9 the warning fires on the drifted record",
              "report_count_source_list_mismatch" in codes_before, str(warns_before))
        check("O9 it clears once the projection matches the population",
              "report_count_source_list_mismatch" not in codes_after, str(warns_after))
        check("O9 the count gate never errored on either -- the count was always right",
              not errs_before and not errs_after, str(errs_before + errs_after))

    # ---------- O10 ----------
    print("\n[O10] nothing outside OBS moves")
    ppt_rows = [{"id": "p1", "product_id": "microsoft-powerpoint", "update_version": "2607",
                 "target_build": "20228.20110", "counted": True, "patch_version_matched": True,
                 "source_url": "https://x/p1"}]
    c = canonical(ppt_rows)
    check("O10 Candidate 1 still counts exactly 1",
          c.get(patch_key("microsoft-powerpoint", "2607", "20228.20110")) == 1, str(c))
    check("O10 the OBS repair adds no PowerPoint or Windows key", len(c) == 1, str(c))

    # ---------- the recurrence guard ----------
    print("\n[O11] membership and a rebuild path move together")
    wf = (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml").read_text(encoding="utf-8")
    steps = yaml.safe_load(wf)["jobs"]["collect"]["steps"]

    def promoted_products():
        out = set()
        for st in steps:
            run_text = str(st.get("run") or "")
            if "apply_consensus_to_records" not in run_text or "--write-all" not in run_text:
                continue
            toks = run_text.replace("\\\n", " ").split()
            for i, t in enumerate(toks[:-1]):
                if t == "--product-id":
                    out.add(toks[i + 1].strip("'\""))
                elif t.startswith("--product-id="):
                    out.add(t.split("=", 1)[1].strip("'\""))
        return out

    check("O11 obs-studio has a scoped promotion step in the lane",
          OBS in promoted_products(), str(sorted(promoted_products())))
    check("O11 obs-studio is retraction-eligible, because the lane can now rebuild it",
          OBS in CONSENSUS_PROMOTION_PRODUCTS, str(sorted(CONSENSUS_PROMOTION_PRODUCTS)))
    # Subset, not equality: every retractable product needs a rebuild path, but a product may hold a
    # promotion without being retraction-eligible (Acrobat Pro/Reader do -- they drift, never retract).
    check("O11 every retractable product has a rebuild path in the lane",
          set(CONSENSUS_PROMOTION_PRODUCTS) <= promoted_products(),
          f"missing={sorted(set(CONSENSUS_PROMOTION_PRODUCTS) - promoted_products())}")
    check("O11 adobe-premiere-pro is never promoted -- its prose is hand-authored",
          "adobe-premiere-pro" not in promoted_products(), str(sorted(promoted_products())))
    reconcile_i = next((i for i, st in enumerate(steps)
                        if "build_consensus_from_evidence" in str(st.get("run") or "")), -1)
    obs_i = next((i for i, st in enumerate(steps)
                  if "apply_consensus_to_records" in str(st.get("run") or "")
                  and OBS in str(st.get("run") or "")), -1)
    qa_steps = [i for i, st in enumerate(steps)
                if "qa_patch_records" in str(st.get("run") or "")]
    check("O11 the OBS promotion sits between reconciliation and the first QA",
          0 <= reconcile_i < obs_i and not [i for i in qa_steps if reconcile_i < i < obs_i],
          f"reconcile={reconcile_i} obs={obs_i} qa={qa_steps}")
    check("O11 the writeback may commit OBS records",
          "obs-studio*.md" in wf, "no --allow entry covers obs-studio records")

    # ---------- O12-O14: the ZERO state, which this change newly exposes OBS to ----------
    print(NEWLINE + "[O12-O14] at a canonical zero the headline must stop stating a count")
    # Joining CONSENSUS_PROMOTION_PRODUCTS makes obs-studio retraction-eligible. That is what makes
    # its projections rebuildable -- and it also means a dip to zero now RETRACTS the source list.
    # The source-list warning is guarded on that list being non-empty, so it goes quiet at exactly
    # the moment a stale `quick_verdict` could still be publishing "has 7 user reports found".
    # obs-studio is the only exposed product: Windows and PowerPoint have no coherence branch, so
    # nothing writes a count into their headline.
    from lib.report_counts import (reconcile_record_counts,  # noqa: PLC0415
                                   retract_zero_count_projections, verdict_states_a_count)
    with tempfile.TemporaryDirectory() as td:
        gen = Path(td) / "generated"
        gen.mkdir(parents=True)
        rec = gen / "2026-08-14-obs-studio-32-2-2.md"
        obs_record(rec, count=7, sources=3, samples=3, prose_count=7)
        keep = gen / "2026-06-23-windows-11-26h1.md"          # keeps the canonical map non-empty
        keep.write_text("---" + NEWLINE + yaml.safe_dump(
            {"layout": "aux-update", "update_entry": True, "product_id": "microsoft-windows-11",
             "update_version": "26H1", "update_product": "Windows 11",
             "update_report_count": 1, "confirmed_patch_specific_report_count": 1,
             "target_kb": "KB5121000", "target_os_build": "28000.2704",
             "target_feature_version": "26H1",
             "target_release_date": "2026-08-11T00:00:00Z"}, sort_keys=False)
            + "---" + NEWLINE + "body" + NEWLINE, encoding="utf-8")
        live = [{"id": "w1", "product_id": "microsoft-windows-11", "update_version": "26H1",
                 "target_build": "", "counted": True, "patch_version_matched": True,
                 "source_url": "https://x/w1", "matched_kb": "KB5121000",
                 "matched_os_build": "28000.2704", "matched_feature_version": "26H1",
                 "source_date": "2026-08-20T00:00:00Z", "captured_at": "2026-08-20T00:00:00Z",
                 "sentiment": "negative", "severity": "high"}]
        _n, details = reconcile_record_counts(live, gen)      # OBS population is empty here
        after = yaml.safe_load(rec.read_text(encoding="utf-8").split("---", 2)[1])
        check("O12 the count falls to zero", after["update_report_count"] == 0,
              str(after["update_report_count"]))
        check("O12 the headline stops stating a count",
              not verdict_states_a_count(after), str(after.get("quick_verdict")))
        check("O12 it becomes the deferred verdict rather than being deleted",
              "deferred" in str(after.get("quick_verdict")).lower(),
              str(after.get("quick_verdict")))
        obs_detail = [d for d in details if "obs-studio" in str(d.get("product_id"))]
        check("O12 the retraction names quick_verdict, so the deletion is not silent",
              obs_detail and "quick_verdict" in (obs_detail[0].get("retracted") or []),
              str(obs_detail))
        import qa_patch_records as qa2  # noqa: PLC0415
        errs, warns = qa2.scan_record(rec)
        # Scoped to the codes this suite owns. The minimal fixture legitimately trips unrelated
        # completeness checks (empty_title, empty_summary, blank_file_size_without_status) because it
        # carries only the count-bearing fields; asserting "no findings at all" would be asserting
        # something about the fixture rather than about the zero state.
        count_codes = {"quick_verdict_count_mismatch", "report_count_source_list_mismatch",
                       "generated_report_count_mismatch", "report_count_for_empty_population",
                       "report_count_without_consensus_summary",
                       "report_count_without_evidence_samples",
                       "report_count_without_accepted_report_sources"}
        raised = {x.get("code") for x in errs + warns} & count_codes
        check("O12 no count/projection finding remains -- the record is right, and the alarm that "
              "would have caught it is still armed", not raised, str(sorted(raised)))

    # O12b: the case that makes the DRIFT predicate load-bearing. A record already in zero shape in
    # every other respect -- deferred report, "Insufficient data" label, no sources/samples/summary --
    # but whose headline still names a count. Nothing else differs, so reconcile writes at all only
    # because `zero_count_projection_drift` notices the verdict. Without that clause the record is
    # judged already-authoritative and the stale headline is published forever.
    with tempfile.TemporaryDirectory() as td:
        gen2 = Path(td) / "generated"
        gen2.mkdir(parents=True)
        only_verdict = gen2 / "2026-08-14-obs-studio-32-2-2.md"
        only_verdict.write_text("---" + NEWLINE + yaml.safe_dump({
            "layout": "aux-update", "update_entry": True,
            "product_id": OBS, "update_version": VER, "update_product": "OBS Studio",
            "update_report_count": 0, "confirmed_patch_specific_report_count": 0,
            "evidence_state": "official_only", "evidence_state_label": "Official source only",
            "consensus_collection_status": "deferred_official_only",
            "consensus_report": DEFERRED_CONSENSUS_REPORT,
            "update_consensus_label": DEFAULT_CONSENSUS,
            "quick_verdict": "TEST FIRST: OBS Studio 32.2.2 has 7 user reports found.",
        }, sort_keys=False) + "---" + NEWLINE + "body" + NEWLINE, encoding="utf-8")
        keep2 = gen2 / "2026-06-23-windows-11-26h1.md"
        keep2.write_text("---" + NEWLINE + yaml.safe_dump(
            {"layout": "aux-update", "update_entry": True, "product_id": "microsoft-windows-11",
             "update_version": "26H1", "update_product": "Windows 11",
             "update_report_count": 1, "confirmed_patch_specific_report_count": 1,
             "target_kb": "KB5121000", "target_os_build": "28000.2704",
             "target_feature_version": "26H1",
             "target_release_date": "2026-08-11T00:00:00Z"}, sort_keys=False)
            + "---" + NEWLINE + "body" + NEWLINE, encoding="utf-8")
        _changed_n, details2 = reconcile_record_counts(live, gen2)
        fixed = yaml.safe_load(only_verdict.read_text(encoding="utf-8").split("---", 2)[1])
        obs_rewritten = [d for d in details2 if d.get("product_id") == OBS]
        check("O12b a stale headline is drift even when nothing else is",
              bool(obs_rewritten) and "quick_verdict" in (obs_rewritten[0].get("retracted") or []),
              str(details2))
        check("O12b ... and it is repaired to the deferred verdict",
              not verdict_states_a_count(fixed), str(fixed.get("quick_verdict")))
        check("O12b a record whose headline is already correct is left alone",
              not [d for d in reconcile_record_counts(live, gen2)[1]
                   if d.get("product_id") == OBS], "second pass rewrote it")

    # O13: content-matched, so a hand-written verdict naming no number is never touched.
    human = {"quick_verdict": "WAIT for production systems. Premiere Pro 26.2 includes useful "
                              "workflow updates and fixes, but early reports describe crashes.",
             "update_product": "Premiere Pro", "update_version": "26.2"}
    check("O13 a verdict that names no number is not a count projection",
          not verdict_states_a_count(human))
    before_text = human["quick_verdict"]
    retract_zero_count_projections(human)
    check("O13 ... and the retraction leaves it exactly as written",
          human["quick_verdict"] == before_text, str(human["quick_verdict"])[:80])

    # O14: the headline check has no blind spot at zero, and would have caught the ORIGINAL defect.
    print(NEWLINE + "[O14] QA compares the headline against the count")
    import qa_patch_records as qa3  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "2026-08-14-obs-studio-32-2-2.md"
        obs_record(bad, count=7, sources=7, samples=5, prose_count=7)
        data = yaml.safe_load(bad.read_text(encoding="utf-8").split("---", 2)[1])
        data["quick_verdict"] = "TEST FIRST: OBS Studio 32.2.2 has 3 user reports found."
        bad.write_text("---" + NEWLINE + yaml.safe_dump(data, sort_keys=False)
                       + "---" + NEWLINE + "body" + NEWLINE, encoding="utf-8")
        e1, w1 = qa3.scan_record(bad)
        codes = [w.get("code") for w in w1]
        check("O14 a headline disagreeing with the count is flagged",
              "quick_verdict_count_mismatch" in codes, str(w1))
        check("O14 it is a warning, not a blocking error",
              not [x for x in e1 if x.get("code") == "quick_verdict_count_mismatch"], str(e1))
        good = Path(td) / "good.md"
        obs_record(good, count=7, sources=7, samples=5, prose_count=7)
        e2, w2 = qa3.scan_record(good)
        check("O14 an aligned headline is silent",
              "quick_verdict_count_mismatch" not in [w.get("code") for w in w2], str(w2))

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
