#!/usr/bin/env python3
"""One maturity authority, one counted population (AUX-053).

WHY IT EXISTS. A patch record's evidence maturity is stored on four axes (evidence_state,
consensus_collection_status, evidence_state_label, intelligence_stage) and four writers each kept a
private copy of the mapping. Reconciliation never wrote intelligence_stage, so 13 records demoted to
zero kept stage `pilot`; the consensus writer wrote `manual_watch` at zero where creation wrote
`official_live`; and every writer hardcoded the two-valued table, so a live state could not survive
one cycle. Separately, seven counters re-derived "counted": the consensus writer silently dropped
rows the authority counted, the aggregate admitted a row whose title merely contained the version,
and a deleted or key-less evidence store read as an empty population that zeroed every record.

WHAT IS PINNED HERE.
  [A] lib.maturity is the canonical table, and a live decision is never inferred from a count.
  [B] every writer takes all four axes from it -- reconcile, the consensus writer, record creation --
      and a live certification survives every writer by construction, and is revoked by the same
      function, all four axes together, with counts and citations untouched.
  [C] the consensus writer's population IS the authority's; an unclassifiable counted row now
      blocks the write by name instead of shrinking the count; the secondary counters agree.
  [D] a missing or malformed evidence store is refused before any record is touched; an explicit
      empty list is still a real, empty population.
  [E] QA: a live claim on ANY axis must be the exact canonical tuple; a non-live contradiction is a
      warning; a counted row the writer cannot project is named.
  [F] the one-time stage convergence edits exactly one line, only where the stage is the sole
      disagreement, and the real records are converged.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_maturity_authority.py
"""
from __future__ import annotations

import io
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
import audit_consensus_evidence as audit  # noqa: E402
import build_consensus_from_evidence as bce  # noqa: E402
import migrate_maturity_stage_convergence as migration  # noqa: E402
import qa_patch_records as qa  # noqa: E402
import revalidate_consensus_evidence as revalidate  # noqa: E402
from lib import maturity, report_counts  # noqa: E402
from lib import write_update_record as writer  # noqa: E402
from patch_collectors import base  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + detail)
        _ERRORS.append(label)


OBS = "obs-studio"
VER = "99.1.0"
KEY = (OBS, VER, "")


def row(rid: str, *, url: str | None = None, counted=True, matched=True, sentiment="negative",
        severity="high", version: str = VER, product: str = OBS) -> dict:
    r = {"id": rid, "product_id": product, "update_version": version,
         "source_url": f"https://github.com/obsproject/obs-studio/issues/{rid}" if url is None else url,
         "source_type": "github_issue", "sentiment": sentiment, "severity": severity,
         "captured_at": "2026-10-20T00:00:00Z", "report_title": f"crash {rid}"}
    if counted is not None:
        r["counted"] = counted
    if matched is not None:
        r["patch_version_matched"] = matched
    return r


def rows(n: int) -> list[dict]:
    return [row(f"r{i}") for i in range(n)]


def write_record(gen: Path, *, count: int, axes: dict | None = None, sources: list | None = None) -> Path:
    data = {"update_entry": True, "product_id": OBS, "update_version": VER, "title": "OBS Studio 99.1.0",
            "permalink": "/updates/obs/obs-studio/99-1-0/",
            "update_report_count": count, "confirmed_patch_specific_report_count": count,
            **(axes if axes is not None else maturity.maturity_for(count).axes())}
    if sources is not None:
        data["accepted_report_sources"] = sources
    path = gen / "2026-10-01-obs-studio-99-1-0.md"
    base.write_front_matter_and_body(path, data, "body\n")
    return path


def front(path: Path) -> dict:
    return base.load_front_matter_and_body(path)[0]


def axes_of(path: Path) -> dict:
    return maturity.stored_axes(front(path))


def quiet(fn, *args, **kwargs):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


# ------------------------------------------------------------------------------------------------
def section_a() -> None:
    print("\n[A] the canonical table")
    check("A1 zero reports is the official tuple, with the official_live stage",
          maturity.maturity_for(0).axes() == {
              "evidence_state": "official_only", "consensus_collection_status": "deferred_official_only",
              "evidence_state_label": "Official source only", "intelligence_stage": "official_live"})
    check("A2 any positive count is the pilot tuple, however large -- volume never implies live",
          all(maturity.maturity_for(n) is maturity.PILOT_SAMPLE for n in (1, 32, 33, 500)))
    check("A3 a live decision at the High rung is the canonical live tuple",
          maturity.maturity_for(maturity.LIVE_MIN_ACCEPTED_REPORTS, live=True).axes() == {
              axis: "consensus_live" if axis != "evidence_state_label" else "Live consensus"
              for axis in maturity.AXES})
    raised = []
    for bad in ((32, True), (-1, False)):
        try:
            maturity.maturity_for(bad[0], live=bad[1])
            raised.append(False)
        except ValueError:
            raised.append(True)
    check("A4 a live decision below 33, or a negative count, raises instead of publishing",
          all(raised), str(raised))
    check("A5 33 is the High rung of the published strength ladder, read from the one constant",
          maturity.LIVE_MIN_ACCEPTED_REPORTS == maturity.HIGH_STRENGTH_MIN_REPORTS == 33
          and qa.LIVE_MIN_ACCEPTED_REPORTS == 33 and acr._confidence(33) == "High"
          and acr._confidence(32) == "Medium" and bce.confidence(33) == "High")
    decision = maturity.certify_live({"product_id": OBS}, rows(500))
    check("A6 a writer holding no run context never promotes: the certifier declines even 500 reports",
          decision.live is False and decision.reasons == ("no_run_context",))
    pair_only = {**maturity.PILOT_SAMPLE.axes(), "evidence_state": "consensus_live",
                 "consensus_collection_status": "consensus_live"}
    check("A7 contradictions name exactly the disagreeing axes",
          maturity.contradictions(maturity.maturity_for(5).axes(), 5) == []
          and maturity.contradictions({**maturity.OFFICIAL_ONLY.axes(), "intelligence_stage": "pilot"}, 0)
          == ["intelligence_stage"]
          and maturity.contradictions(pair_only, 40) == ["evidence_state_label", "intelligence_stage"])
    single_axis_claims = [maturity.claims_live({**maturity.PILOT_SAMPLE.axes(), axis: value})
                          for axis, value in (("evidence_state", "consensus_live"),
                                              ("consensus_collection_status", "live_consensus"),
                                              ("evidence_state_label", "Live consensus"),
                                              ("intelligence_stage", "consensus_live"))]
    check("A8 a live claim on ANY single axis, including the legacy word, is a live claim",
          all(single_axis_claims) and not maturity.claims_live(maturity.PILOT_SAMPLE.axes()),
          str(single_axis_claims))
    check("A9 QA reads the authority's vocabulary rather than keeping its own copy",
          qa.VALID_EVIDENCE_STATES == set(maturity.VALID_EVIDENCE_STATES)
          and qa.VALID_INTELLIGENCE_STAGES == set(maturity.VALID_INTELLIGENCE_STAGES)
          and "manual_watch" in maturity.VALID_INTELLIGENCE_STAGES
          and qa.LIVE_COLLECTION_STATUSES == ("consensus_live", "live_consensus"))


# ------------------------------------------------------------------------------------------------
def section_b() -> None:
    print("\n[B] every writer takes all four axes from the authority")
    with tempfile.TemporaryDirectory() as td:
        gen = Path(td)
        path = write_record(gen, count=0, axes={**maturity.OFFICIAL_ONLY.axes(), "intelligence_stage": "pilot"})
        quiet(report_counts.reconcile_record_counts, [], gen)
        check("B1 reconcile now writes intelligence_stage: a zero record's stale `pilot` converges",
              axes_of(path) == maturity.OFFICIAL_ONLY.axes(), str(axes_of(path)))
        path.unlink()
        path = write_record(gen, count=0, axes={**maturity.OFFICIAL_ONLY.axes(), "intelligence_stage": ""})
        quiet(report_counts.reconcile_record_counts, rows(3), gen)
        check("B2 a record gaining reports moves all four axes to pilot, the stage included",
              axes_of(path) == maturity.PILOT_SAMPLE.axes() and front(path)["update_report_count"] == 3,
              str(axes_of(path)))
        changed, _ = quiet(report_counts.reconcile_record_counts, rows(3), gen)
        check("B3 reconcile is idempotent on a canonical record", changed == 0)

    fields = acr._proposed_record_fields(OBS, VER, rows(3), None, "2026-10-20T00:00:00Z", build="")
    zero = acr._proposed_record_fields(OBS, VER, [], None, "2026-10-20T00:00:00Z", build="")
    check("B4 the consensus writer proposes the authority's tuple, never its old `manual_watch`",
          {a: fields[a] for a in maturity.AXES} == maturity.PILOT_SAMPLE.axes()
          and {a: zero[a] for a in maturity.AXES} == maturity.OFFICIAL_ONLY.axes())

    created = writer.build_front_matter({"company_id": "obs", "company": "OBS Project", "software": "OBS Studio",
                                         "product_id": OBS, "version": VER, "title": "OBS Studio 99.1.0",
                                         "source_url": "https://obsproject.com/", "report_count": 4,
                                         "published_at": "2026-10-01T00:00:00Z",
                                         "evidence_state": "pilot_sample"})
    refused = False
    try:
        writer.build_front_matter({"company_id": "obs", "company": "OBS Project", "software": "OBS Studio", "product_id": OBS,
                                   "version": VER, "title": "OBS Studio 99.1.0",
                                   "source_url": "https://obsproject.com/", "report_count": 0,
                                   "published_at": "2026-10-01T00:00:00Z",
                                   "evidence_state": "consensus_live"})
    except ValueError:
        refused = True
    check("B5 record creation derives maturity and refuses a caller-supplied value that disagrees",
          {a: created[a] for a in maturity.AXES} == maturity.PILOT_SAMPLE.axes() and refused)

    # BY CONSTRUCTION: whatever the run context decides, every writer writes -- and keeps writing.
    # The stub stands in for live_eligibility.RunContext (whose real decisions are pinned in
    # test_live_promotion); what is pinned here is that no writer overrules it.
    class _Context:
        def __init__(self, live: bool) -> None:
            self.live = live

        def bind(self, _groups):
            return self

        def decide(self, _record, _counted_rows=None):
            return maturity.LiveDecision(self.live, () if self.live else ("test",))

    sources = [{"source_url": r["source_url"]} for r in rows(33)]
    with tempfile.TemporaryDirectory() as td:
        gen = Path(td)
        path = write_record(gen, count=33, sources=sources)
        certifies = _Context(True)
        quiet(report_counts.reconcile_record_counts, rows(33), gen, live_context=certifies)
        promoted = axes_of(path)
        again, _ = quiet(report_counts.reconcile_record_counts, rows(33), gen, live_context=certifies)
        index = {KEY: {"path": path.name, "abs_path": path, "product_id": OBS, "update_version": VER,
                       "evidence_state": "consensus_live", "legacy_manual_report_count": None}}
        proposed = acr._result_for_group(OBS, VER, rows(33), is_candidate_mode=False, records_index=index,
                                         live_context=certifies)["proposed_fields_if_written"]
        check("B6 a certified identity is written live on all four axes by reconciliation",
              promoted == maturity.CONSENSUS_LIVE.axes(), str(promoted))
        check("B7 ...and SURVIVES the next reconciliation (no demotion by any writer literal)", again == 0)
        check("B8 ...and the consensus writer proposes the same live tuple",
              {a: proposed.get(a) for a in maturity.AXES} == maturity.CONSENSUS_LIVE.axes(),
              str({a: proposed.get(a) for a in maturity.AXES}))
        quiet(report_counts.reconcile_record_counts, rows(33), gen, live_context=_Context(False))
        after = front(path)
        check("B9 revocation is the same function: all four axes demote together, and the count and "
              "the cited sources are untouched",
              maturity.stored_axes(after) == maturity.PILOT_SAMPLE.axes()
              and after["update_report_count"] == 33 and after.get("accepted_report_sources") == sources,
              str(maturity.stored_axes(after)))


# ------------------------------------------------------------------------------------------------
def section_c() -> None:
    print("\n[C] one counted population")
    mixed = [row("in1"), row("in2", counted=None), row("out-counted-false", counted=False),
             row("out-unmatched", matched=False), row("out-match-missing", matched=None),
             row("blank-sentiment", sentiment=""), row("bad-severity", severity="catastrophic"),
             row("blank-url", url="")]
    included, _ = acr._filter_rows(mixed, product_id=OBS, version=VER, is_candidate_mode=False)
    authority = report_counts.counted_evidence_rows(mixed, windows_targets={}).get(KEY, [])
    check("C1 the consensus writer's population is exactly the authority's, row for row",
          sorted(r["id"] for r in included) == sorted(r["id"] for r in authority)
          == sorted(["in1", "in2", "blank-sentiment", "bad-severity", "blank-url"]),
          f"{sorted(r['id'] for r in included)} vs {sorted(r['id'] for r in authority)}")
    with tempfile.TemporaryDirectory() as td:
        rec = write_record(Path(td), count=5)
        index = {KEY: {"path": rec.name, "abs_path": rec, "product_id": OBS, "update_version": VER,
                       "evidence_state": "pilot_sample", "legacy_manual_report_count": None}}
        blocked = acr._result_for_group(OBS, VER, mixed, is_candidate_mode=False, records_index=index)
        clean = acr._result_for_group(OBS, VER, rows(5), is_candidate_mode=False, records_index=index)
    check("C2 an unclassifiable counted row blocks the write by name instead of shrinking the count",
          blocked["included_candidate_count"] == 5 and blocked["would_write"] is False
          and {"gate_11_source_url_required", "gate_17_counted_rows_classified"}
          <= set(blocked["blocking_gate_failures"]),
          str(blocked["blocking_gate_failures"]))
    check("C3 a clean population still writes", clean["would_write"] is True,
          str(clean["blocking_gate_failures"]))
    check("C4 the aggregate's title-substring admission path is gone",
          not hasattr(bce, "is_patch_specific"))
    check("C5 collector diagnostics and revalidation read the one row predicate",
          [r["id"] for r in base.counted_rows(mixed, OBS, VER)] == [r["id"] for r in authority]
          and [revalidate.is_counted(r) for r in mixed] == [base.row_is_counted(r) for r in mixed])
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        gen = tdp / "generated"
        gen.mkdir()
        write_record(gen, count=1)
        store = tdp / "consensus_evidence.yml"
        store.write_text(yaml.safe_dump({"evidence": [row("a"), row("unmatched", matched=None)]}),
                         encoding="utf-8")
        saved = (audit.EVIDENCE_PATH, audit.GENERATED_DIR, audit.STATE_PATH, audit.ROOT)
        try:
            audit.EVIDENCE_PATH, audit.GENERATED_DIR, audit.STATE_PATH, audit.ROOT = (
                store, gen, tdp / "state.json", tdp)
            result = audit.audit()
        finally:
            audit.EVIDENCE_PATH, audit.GENERATED_DIR, audit.STATE_PATH, audit.ROOT = saved
    check("C6 the audit counts the authority's population (a row with no patch match is not a report)",
          not result["integrity_errors"], str(result["integrity_errors"])[:300])


# ------------------------------------------------------------------------------------------------
def section_d() -> None:
    print("\n[D] a missing or malformed evidence store is refused before any write")
    cases = {"missing file": None, "key-less mapping": "schema_version: 1\n",
             "evidence is not a list": "evidence: {}\n", "unparseable": "evidence: [\n",
             "a row that is not a mapping": "evidence:\n- just a string\n"}
    outcomes = {}
    with tempfile.TemporaryDirectory() as td:
        for name, text in cases.items():
            path = Path(td) / (name.replace(" ", "_") + ".yml")
            if text is not None:
                path.write_text(text, encoding="utf-8")
            try:
                report_counts.load_evidence_store(path)
                outcomes[name] = "accepted"
            except report_counts.EvidenceStoreError:
                outcomes[name] = "refused"
        empty = Path(td) / "empty.yml"
        empty.write_text("schema_version: 1\nevidence: []\n", encoding="utf-8")
        bare = Path(td) / "bare.yml"
        bare.write_text("[]\n", encoding="utf-8")
        valid_empty = report_counts.load_evidence_store(empty) == [] and report_counts.load_evidence_store(bare) == []
    check("D1 missing, key-less, wrongly typed, unparseable and non-mapping-row stores are all refused",
          set(outcomes.values()) == {"refused"}, str(outcomes))
    check("D2 an EXPLICIT empty list is still a real, empty population", valid_empty)

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        gen = tdp / "generated"
        gen.mkdir()
        rec = write_record(gen, count=7)
        before = rec.read_bytes()
        keyless = tdp / "keyless.yml"
        keyless.write_text("schema_version: 1\n", encoding="utf-8")
        saved = (bce.EVIDENCE_PATH, bce.GENERATED_DIR, bce.OUT_PATH)
        try:
            bce.EVIDENCE_PATH, bce.GENERATED_DIR, bce.OUT_PATH = tdp / "absent.yml", gen, tdp / "out.json"
            rc_missing = quiet(bce.main, [])
            bce.EVIDENCE_PATH = keyless
            rc_keyless = quiet(bce.main, [])
        finally:
            bce.EVIDENCE_PATH, bce.GENERATED_DIR, bce.OUT_PATH = saved
        check("D3 reconciliation refuses a missing or key-less store and touches no record",
              rc_missing == 1 and rc_keyless == 1 and rec.read_bytes() == before)
        # Each check starts from the same record, so one refusal failing cannot fail the next.
        rec.write_bytes(before)
        saved_acr = (acr.DEFAULT_EVIDENCE_PATH, acr.GENERATED_DIR, acr.ROOT)
        try:
            # ROOT too: a writer that wrongly ACCEPTS the store indexes these records relative to
            # it, and must reach a named failure below rather than crash the suite on a temp path.
            acr.DEFAULT_EVIDENCE_PATH, acr.GENERATED_DIR, acr.ROOT = keyless, gen, tdp
            rc_apply = quiet(acr.main, ["--product-id", OBS, "--write-all", "--confirm-write"])
        except Exception as exc:  # noqa: BLE001 - an exception is not a refusal
            rc_apply = f"raised {type(exc).__name__}"
        finally:
            acr.DEFAULT_EVIDENCE_PATH, acr.GENERATED_DIR, acr.ROOT = saved_acr
        check("D4 the consensus writer refuses a key-less store and touches no record",
              rc_apply == 1 and rec.read_bytes() == before, f"rc={rc_apply!r}")

        # The PowerPoint graph reconciles through its own node, not build_consensus_from_evidence.
        import orchestrate_evidence_run as orch  # noqa: PLC0415 - heavy; only this check needs it
        from lib.orchestration import OrchestrationState  # noqa: PLC0415
        rec.write_bytes(before)
        (tdp / "repo").mkdir()  # the checkpoint dir must sit OUTSIDE the repo root
        pipeline = orch.Pipeline(tdp / "repo", [OBS], write=True, checkpoint_dir=tdp / "ckpt",
                                 evidence_path=tdp / "absent.yml", health_path=tdp / "health.yml",
                                 generated_dir=gen, methods={}, authorities={})
        graph_refused = False
        try:
            pipeline.reconcile_counts(OrchestrationState(product_ids=[OBS]))
        except report_counts.EvidenceStoreError:
            graph_refused = True
        check("D5 the graph's reconcile node refuses a missing store and touches no record",
              graph_refused and rec.read_bytes() == before)


# ------------------------------------------------------------------------------------------------
def _live_record(**axes) -> dict:
    sources = [{"source_url": r["source_url"]} for r in rows(33)]
    return {"product_id": OBS, "update_version": VER, "update_report_count": 33,
            "confirmed_patch_specific_report_count": 33, "accepted_report_sources": sources,
            **maturity.CONSENSUS_LIVE.axes(), **axes}


def section_e() -> None:
    print("\n[E] QA: four-axis invariants")
    counts = {KEY: 33}
    urls = {KEY: {base.normalize_url(r["source_url"]) for r in rows(33)}}

    def codes(data: dict) -> list[str]:
        errors, _ = qa.scan_live_consensus_claims([(Path("x.md"), data)], counts, urls)
        return [e["code"] for e in errors]

    check("E1 the canonical live tuple with its full population raises nothing", codes(_live_record()) == [],
          str(codes(_live_record())))
    pair_only = codes(_live_record(evidence_state_label="Verified reports", intelligence_stage="pilot"))
    check("E2 a pair-only promotion (rendered 'Live consensus · Early reports') is now an ERROR",
          "maturity_live_axes_inconsistent" in pair_only, str(pair_only))
    stage_only = codes({**_live_record(), **maturity.PILOT_SAMPLE.axes(), "intelligence_stage": "consensus_live"})
    check("E3 a live claim on the stage alone -- invisible to the old pair check -- is an ERROR",
          "maturity_live_axes_inconsistent" in stage_only, str(stage_only))
    legacy = codes(_live_record(consensus_collection_status="live_consensus"))
    check("E4 the legacy `live_consensus` spelling is read, never accepted as a claim",
          "maturity_live_axes_inconsistent" in legacy, str(legacy))

    with tempfile.TemporaryDirectory() as td:
        gen = Path(td)
        drift = write_record(gen, count=0, axes={**maturity.OFFICIAL_ONLY.axes(), "intelligence_stage": "pilot"})
        errors, warnings = qa.scan_record(drift)
    check("E5 a non-live contradiction is a WARNING, never an error that would wedge a lane",
          "maturity_axes_inconsistent" in {w["code"] for w in warnings}
          and "maturity_axes_inconsistent" not in {e["code"] for e in errors})
    with tempfile.TemporaryDirectory() as td:
        negative = write_record(Path(td), count=0, axes=maturity.PILOT_SAMPLE.axes())
        data, body = base.load_front_matter_and_body(negative)
        data["update_report_count"] = -1
        base.write_front_matter_and_body(negative, data, body)
        try:
            _e, neg_warnings = qa.scan_record(negative)
            neg_outcome = "maturity_axes_inconsistent" in {w["code"] for w in neg_warnings}
        except Exception as exc:  # noqa: BLE001 - the defect being pinned is exactly a raise here
            neg_outcome = f"raised {type(exc).__name__}"
    check("E7 a malformed negative count is reported, not raised -- QA runs in every lane",
          neg_outcome is True, str(neg_outcome))
    flagged = qa.scan_counted_row_classification(
        [row("ok"), row("s", sentiment="meh"), row("u", url=""), row("v", severity="catastrophic"),
         row("not-counted", counted=False, sentiment="meh")])
    check("E6 QA names each counted row the writer cannot project, and ignores uncounted rows",
          len(flagged) == 3 and {w["code"] for w in flagged} == {"counted_row_unclassified"},
          str([w["message"][:60] for w in flagged]))


# ------------------------------------------------------------------------------------------------
def _record_text(stage_line: str | None, *, count: int = 0, label: str = "Official source only",
                 state: str = "official_only") -> str:
    lines = ["---", "update_entry: true", "product_id: obs-studio", "update_version: 99.1.0",
             f"update_report_count: {count}", f"evidence_state: {state}", f"evidence_state_label: {label}"]
    if stage_line is not None:
        lines.append(stage_line)
    lines += ["consensus_collection_status: deferred_official_only", "title: X", "---", "body", ""]
    return "\n".join(lines)


def section_f() -> None:
    print("\n[F] the one-time stage convergence")
    replaced = migration.converge_text(_record_text("intelligence_stage: pilot"))
    inserted = migration.converge_text(_record_text(None))
    original = _record_text("intelligence_stage: pilot")

    def diff_lines(a: str, b: str) -> int:
        return len(set(a.splitlines()) ^ set(b.splitlines()))

    check("F1 a stale stage is replaced in place: one line in, one line out",
          replaced is not None and "intelligence_stage: official_live" in replaced[0]
          and diff_lines(original, replaced[0]) == 2)
    check("F2 a missing stage is inserted as one line after the label",
          inserted is not None
          and "evidence_state_label: Official source only\nintelligence_stage: official_live\n" in inserted[0])
    check("F3 a record whose other axes also disagree is never written, and a canonical one is a no-op",
          migration.converge_text(_record_text("intelligence_stage: pilot", state="pilot_sample")) is None
          and migration.converge_text(_record_text("intelligence_stage: official_live")) is None
          and migration.converge_text(replaced[0]) is None)
    entries, other = migration.plan(_REPO / "auxsays" / "updates" / "generated")
    check("F4 the real records are converged: nothing left to migrate, nothing contradicting",
          entries == [] and other == [],
          str([e["path"].name for e in entries][:5]) + str(other[:5]))


def main() -> int:
    for section in (section_a, section_b, section_c, section_d, section_e, section_f):
        section()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
