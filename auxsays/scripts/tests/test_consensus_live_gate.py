#!/usr/bin/env python3
"""A live consensus claim must be supported by the authoritative accepted-evidence population.

`consensus_live` had many consumers and ZERO producers, and the cause was not an undecided
threshold. `qa_patch_records` gated it on front-matter `consensus_evidence` / `structured_evidence`
/ `evidence_objects`. Measured: 0 of 1316 generated records carried any of the three, no template
read them, and all three are ABSENT from `apply_consensus_to_records.WRITEABLE_FIELDS`, whose
else-branch is `raise RuntimeError("Refusing to write unapproved field")`. The precondition was
unsatisfiable by data AND by the approved write path.

Two further facts shaped the replacement:

  * `accepted_report_sources` carried `patch_version_matched: True` as a hardcoded literal (AUX-043
    now earns it from the row). A gate that believed the writer's own projection would be only as
    strong as that writer, so patch-matching is established upstream instead, by the real per-row
    predicate in `lib.report_counts`.
  * `evidence_samples` is capped at five. `accepted_report_sources` is the exhaustive projection,
    so it is the one a maturity claim must agree with.

WHAT THIS SUITE DOES NOT DO. It does not make anything live. No producer in this change emits
`consensus_live`; Part E pins that behaviourally rather than by inspection, so the repaired gate can
be proven correct before any record can reach it.

Offline: no network, no repo writes. The fixtures are synthetic and in-memory; the one case that
executes `main` runs it in `--read-only` mode, which is what makes a production-entry-point test
possible at all.
"""
from __future__ import annotations

import subprocess
import tempfile
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import qa_patch_records as qa                                  # noqa: E402
from lib import maturity, report_counts                        # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


PRODUCT = "obs-studio"
VERSION = "32.1.2"
KEY = (PRODUCT, VERSION, "")
N = qa.LIVE_MIN_ACCEPTED_REPORTS


def sources(count: int, *, duplicate: bool = False, bad_url: bool = False,
            malformed: bool = False) -> list:
    """`count` exhaustive accepted-report entries, shaped like the real projection.

    Every entry carries `patch_version_matched: True`, exactly as the consensus writer stamps it.
    That is deliberate: the gate must NOT be satisfied by it.
    """
    out: list = []
    for i in range(count):
        url = f"https://github.com/obsproject/obs-studio/issues/{13000 + i}"
        if duplicate and i == count - 1:
            url = "https://github.com/obsproject/obs-studio/issues/13000"
        if bad_url and i == 0:
            url = ""
        out.append({
            "source_name": "obsproject/obs-studio",
            "source_type": "github issue",
            "source_url": url,
            "source_title": f"report {i}",
            "patch_version_matched": True,
        })
    if malformed:
        out[0] = "not a mapping"
    return out


def record(*, state: str = "consensus_live", status: str = "consensus_live",
           count: int | None = None, srcs: list | None = None,
           product: str = PRODUCT, version: str = VERSION) -> dict:
    n = N if count is None else count
    # The label and stage follow the pair: a record claiming live on either half carries the live
    # label and stage (AUX-053 requires all four axes), otherwise the pilot ones.
    claims = state == "consensus_live" or status in qa.LIVE_COLLECTION_STATUSES
    pair_maturity = maturity.CONSENSUS_LIVE if claims else maturity.PILOT_SAMPLE
    return {
        "product_id": product,
        "update_version": version,
        "evidence_state": state,
        "consensus_collection_status": status,
        "evidence_state_label": pair_maturity.evidence_state_label,
        "intelligence_stage": pair_maturity.intelligence_stage,
        "update_report_count": n,
        "confirmed_patch_specific_report_count": n,
        "accepted_report_sources": sources(N) if srcs is None else srcs,
    }


def safe_main(argv: list[str]) -> int:
    """`qa.main`, but a raise becomes a distinguishable value instead of killing the run.

    A mutant must produce a NAMED failure, not a crash: a crash leaves every later check unrun and
    can mask a second regression. Two mutants in the proof for this suite raised here -- making
    read-only write unconditionally raises once the status directory is deliberately absent -- and
    both had already failed their correct checks before the exception, which the harness then
    reported as "not a catch".
    """
    try:
        return qa.main(argv)
    except Exception:  # noqa: BLE001 - deliberately broad; the point is to keep reporting
        return -1


def codes(data: dict, counts: dict | None = None, urls: dict | None = None) -> set[str]:
    errs, _warns = qa.scan_live_consensus_claims(
        [(Path("fixture.md"), data)], {KEY: N} if counts is None else counts, urls)
    return {e["code"] for e in errs}


def run_suite() -> int:
    print("=" * 92)
    print("PART A  a supported live claim passes; an unsupported one does not")
    print("=" * 92)

    check("Part A: a fully supported live claim produces no finding",
          codes(record()) == set(), str(codes(record())))
    check("Part A: one report below the published High rung is refused",
          "live_without_sufficient_accepted_evidence"
          in codes(record(count=N - 1, srcs=sources(N - 1)), {KEY: N - 1}),
          str(codes(record(count=N - 1, srcs=sources(N - 1)), {KEY: N - 1})))
    check("Part A: exactly the High rung is accepted",
          codes(record(count=N, srcs=sources(N)), {KEY: N}) == set())
    check("Part A: a published count that disagrees with the authority is refused",
          "live_count_disagrees_with_evidence" in codes(record(count=N), {KEY: N + 7}))
    check("Part A: an identity absent from the authoritative population is refused",
          "live_without_sufficient_accepted_evidence" in codes(record(), {}))
    check("Part A: a record with no canonical identity is refused",
          "live_without_canonical_identity" in codes(record(product="", version="")))

    print()
    print("=" * 92)
    print("PART B  the evidence projection a reader can actually follow")
    print("=" * 92)

    check("Part B: a live claim with no accepted report sources is refused",
          "live_without_accepted_report_sources" in codes(record(srcs=[])))
    check("Part B: a sample-sized list is refused -- this projection is exhaustive, not five",
          "live_sources_not_exhaustive" in codes(record(srcs=sources(5))))
    check("Part B: a repeated report is not independent corroboration",
          "live_sources_not_distinct" in codes(record(srcs=sources(N, duplicate=True))))
    check("Part B: a source with no usable http URL is refused",
          "live_source_without_valid_url" in codes(record(srcs=sources(N, bad_url=True))))
    check("Part B: a non-mapping entry is refused",
          "live_sources_malformed" in codes(record(srcs=sources(N, malformed=True))))

    # The regression that nearly shipped in the gate itself.
    phpbb = [{"source_url": f"https://forum.blackmagicdesign.com/viewtopic.php?f=42&t={235000 + i}",
              "patch_version_matched": True} for i in range(N)]
    check("Part B: query-distinct forum threads are DISTINCT reports, not duplicates",
          "live_sources_not_distinct" not in codes(record(srcs=phpbb)),
          str(codes(record(srcs=phpbb))))

    print()
    print("=" * 92)
    print("PART C  the projection's own matched flag is never believed")
    print("=" * 92)

    # Every fixture entry says patch_version_matched: True, as the writer stamps it. With an empty
    # authority the claim must still fail -- otherwise the check is unfalsifiable.
    unsupported = codes(record(), {})
    check("Part C: sources all claiming patch_version_matched cannot establish a live claim",
          "live_without_sufficient_accepted_evidence" in unsupported, str(unsupported))
    check("Part C: and the refusal does not depend on that flag being absent or false",
          all(item.get("patch_version_matched") is True
              for item in record()["accepted_report_sources"]))
    gate_src = (SCRIPTS / "qa_patch_records.py").read_text(encoding="utf-8")
    body = gate_src.split("def scan_live_consensus_claims", 1)[1].split("\ndef ", 1)[0]
    check("Part C: the gate body never reads patch_version_matched from the record",
          "patch_version_matched" not in body.split('"""', 2)[-1])

    # An unreadable or empty evidence store is the condition under which a live claim is LEAST
    # supported, so validation must not sit behind the caller's empty-map early return. Pinned as
    # the relative order of two exact statements rather than a grep over the function, because a
    # whole-function grep stays green with the call moved below the return.
    caller = gate_src.split("def scan_evidence_count_alignment", 1)[1].split("\ndef ", 1)[0]
    check("Part C: live claims are validated BEFORE the empty-population early return",
          "scan_live_consensus_claims(" in caller
          and caller.index("scan_live_consensus_claims(")
          < caller.index("if not evidence_counts:"))

    print()
    print("=" * 92)
    print("PART D  the pair, because the surfaces disagree about which field decides")
    print("=" * 92)

    check("Part D: live evidence_state beside a pilot collection status is refused",
          "live_state_pair_inconsistent"
          in codes(record(status="pilot_initial_sample")))
    check("Part D: a live collection status beside a pilot evidence_state is refused",
          "live_state_pair_inconsistent" in codes(record(state="pilot_sample")))
    check("Part D: and that half-claim is still VALIDATED, not waved through",
          "live_without_sufficient_accepted_evidence"
          in codes(record(state="pilot_sample"), {}))
    # The legacy word order is READ as live -- it must not be read as a pilot status, which would
    # silently skip validation of a record the detail page renders as mature -- but since AUX-053 it
    # is not ACCEPTED as a claim: nothing writes it, and a live claim must carry the canonical tuple.
    check("Part D: the legacy live_consensus spelling is read as a claim and refused as one",
          codes(record(status="live_consensus")) == {"maturity_live_axes_inconsistent"},
          str(codes(record(status="live_consensus"))))
    check("Part D: and a legacy-spelled claim is validated like any other",
          "live_without_sufficient_accepted_evidence"
          in codes(record(status="live_consensus"), {}))
    check("Part D: a pilot record is not examined at all",
          codes(record(state="pilot_sample", status="pilot_initial_sample")) == set())
    check("Part D: an official-only record is not examined at all",
          codes(record(state="official_only", status="deferred_official_only")) == set())

    print()
    print("=" * 92)
    print("PART E  nothing in this change can make a record live")
    print("=" * 92)

    states = {report_counts.evidence_state_for(n) for n in (0, 1, 5, N, N + 100)}
    statuses = {report_counts.collection_status_for(n) for n in (0, 1, 5, N, N + 100)}
    check("Part E: the shipped state mapping never returns consensus_live at any count",
          qa.LIVE_EVIDENCE_STATE not in states, str(sorted(states)))
    check("Part E: nor does the collection-status mapping",
          not (set(qa.LIVE_COLLECTION_STATUSES) & statuses), str(sorted(statuses)))
    check("Part E: consensus_live is still a recognised state, so consumers stay honest",
          qa.LIVE_EVIDENCE_STATE in qa.VALID_EVIDENCE_STATES)
    check("Part E: the unsatisfiable helper is gone, not merely unused",
          not hasattr(qa, "has_structured_evidence"))

    # Why it was unsatisfiable, pinned so nobody reintroduces the same shape.
    apply_src = (SCRIPTS / "apply_consensus_to_records.py").read_text(encoding="utf-8")
    writeable = apply_src.split("WRITEABLE_FIELDS", 1)[1].split("}", 1)[0]
    check("Part E: the three fields the old gate demanded are still unwriteable by the producer",
          not any(f'"{k}"' in writeable for k in
                  ("consensus_evidence", "structured_evidence", "evidence_objects")))
    check("Part E: while the four maturity fields it must write ARE writeable",
          all(f'"{k}"' in writeable for k in
              ("evidence_state", "consensus_collection_status", "evidence_state_label",
               "intelligence_stage")))

    print()
    print("=" * 92)
    print("PART F  the lane: a valid live record must not block the writeback or the deploy")
    print("=" * 92)

    # THE REAL RECORD, THE REAL EVIDENCE STORE. A synthetic record would have to satisfy every
    # other QA check to reach exit 0, so a failure there would say nothing about this gate. Instead
    # take the live corpus's largest candidate, promote its two maturity fields IN MEMORY, and run
    # the gate against the authoritative counts loaded from the real store. If this is clean, the
    # gate contributes zero errors for a genuine promotion -- and errors are the only thing a lane
    # blocks on, so it cannot wedge the writeback or the deploy.
    candidate = ROOT / "updates" / "generated" / "2026-04-21-obs-studio-32-1-2.md"
    if candidate.exists():
        real = qa.front_matter(candidate)
        real_counts = qa.load_counted_evidence_counts([real])
        real_key = qa.patch_key(str(real.get("product_id")), str(real.get("update_version")),
                                real.get("target_build"))
        promoted = dict(real)
        promoted.update(maturity.CONSENSUS_LIVE.axes())  # all four axes, as every writer now does
        errs, _w = qa.scan_live_consensus_claims([(candidate, promoted)], real_counts)
        check("Part F: promoting the real largest candidate yields NO gate error",
              errs == [], str([e["code"] for e in errs]))
        check("Part F: and that candidate really is at or above the rung in the live store",
              int(real_counts.get(real_key) or 0) >= N,
              f"authoritative={real_counts.get(real_key)}")
        # Same record, same store, one field tampered with: the gate must refuse.
        tampered = dict(promoted)
        tampered["update_report_count"] = int(real_counts.get(real_key) or 0) + 1
        errs2, _ = qa.scan_live_consensus_claims([(candidate, tampered)], real_counts)
        check("Part F: inflating that same record's published count by one is refused",
              "live_count_disagrees_with_evidence" in {e["code"] for e in errs2},
              str([e["code"] for e in errs2]))
    else:
        check("Part F: the real candidate record is present to promote", False, str(candidate))

    proc = subprocess.run([sys.executable, str(SCRIPTS / "qa_patch_records.py"), "--read-only"],
                          capture_output=True, text=True, cwd=str(SCRIPTS))
    check("Part F: and still reports, so CI sees the same findings production would",
          "QA scanned" in proc.stdout, proc.stdout[-160:] or proc.stderr[-160:])
    check("Part F: the real corpus has no live claim yet, so the gate is quiet today",
          proc.returncode == 0, f"exit={proc.returncode}")

    strict = subprocess.run([sys.executable, str(SCRIPTS / "qa_patch_records.py"),
                             "--read-only", "--publish-strict"],
                            capture_output=True, text=True, cwd=str(SCRIPTS))
    check("Part F: read-only composes with publish-strict, the mode the deploy lane uses",
          strict.returncode == 0 and "publish-strict" not in strict.stderr,
          f"exit={strict.returncode} {strict.stderr[-120:]}")

    # NOT ASSERTED AGAINST THE REAL _data/qa_status.json. An earlier version compared that file's
    # bytes before and after, which made the check depend on no other process on the machine
    # writing a shared, tracked, gitignored file -- and it failed once, non-reproducibly, right
    # after a killed run left QA processes behind. A test that can be broken by a neighbour is not
    # evidence about this change. The same two properties are asserted below on a path only this
    # test owns: read-only must not CREATE a status file, and must not MODIFY an existing one.
    with tempfile.TemporaryDirectory() as d:
        existing = Path(d) / "qa_status.json"
        sentinel = b'{"sentinel": "untouched"}\n'
        existing.write_bytes(sentinel)
        orig_out = qa.OUT_PATH
        qa.OUT_PATH = existing
        try:
            safe_main(["--read-only"])
            check("Part F: read-only does not modify an EXISTING status file",
                  existing.read_bytes() == sentinel)
            safe_main(["--read-only", "--publish-strict"])
            check("Part F: nor under publish-strict, the mode the deploy runs",
                  existing.read_bytes() == sentinel)
        finally:
            qa.OUT_PATH = orig_out

    # A FRESH CHECKOUT. The flag suppresses a mkdir as well as a write, so the case where neither
    # the status file nor its directory exists is the one where a missing-directory assumption
    # would surface -- and it is the state a new clone is in before any lane has run.
    with tempfile.TemporaryDirectory() as d:
        absent = Path(d) / "nonexistent" / "qa_status.json"
        orig_out = qa.OUT_PATH
        qa.OUT_PATH = absent
        try:
            safe_main(["--read-only"])
            check("Part F: read-only creates no status file when none exists",
                  not absent.exists())
            check("Part F: and does not create its parent directory either",
                  not absent.parent.exists())
        finally:
            qa.OUT_PATH = orig_out

    print()
    print("=" * 92)
    print("PART G  a promoted record through the real entry point, and failure propagation")
    print("=" * 92)

    # GPT's condition, and the right shape: a LEGITIMATE live record must clear both modes. Built
    # from the real record on disk rather than a synthetic one, so every other QA check sees a
    # genuine record and the live claim is the only variable.
    if candidate.exists():
        real = qa.front_matter(candidate)
        real_key = qa.patch_key(str(real.get("product_id")), str(real.get("update_version")),
                                real.get("target_build"))
        authoritative = int(qa.load_counted_evidence_counts([real]).get(real_key) or 0)
        with tempfile.TemporaryDirectory() as d:
            gen = Path(d)
            text = candidate.read_text(encoding="utf-8")
            promoted_text = (text
                             .replace("evidence_state: pilot_sample",
                                      f"evidence_state: {qa.LIVE_EVIDENCE_STATE}")
                             .replace("consensus_collection_status: pilot_initial_sample",
                                      f"consensus_collection_status: {qa.LIVE_EVIDENCE_STATE}")
                             .replace("evidence_state_label: Verified reports",
                                      "evidence_state_label: Live consensus")
                             .replace("intelligence_stage: pilot",
                                      "intelligence_stage: consensus_live"))
            target = gen / candidate.name
            target.write_text(promoted_text, encoding="utf-8")
            orig_dir, orig_loader = qa.GENERATED_DIR, qa.load_counted_evidence_counts
            qa.GENERATED_DIR = gen
            qa.load_counted_evidence_counts = lambda _records=None: {real_key: authoritative}
            try:
                check("Part G: a legitimate promoted record passes normal validation",
                      safe_main(["--read-only"]) == 0)
                check("Part G: and passes publish-strict, the mode the deploy runs",
                      safe_main(["--read-only", "--publish-strict"]) == 0)
                # Same record, published count inflated by one: the claim no longer matches the
                # authority, so BOTH modes must refuse and the process must exit non-zero.
                target.write_text(promoted_text.replace(
                    f"update_report_count: {authoritative}",
                    f"update_report_count: {authoritative + 1}"), encoding="utf-8")
                check("Part G: inconsistent evidence fails normal validation non-zero",
                      safe_main(["--read-only"]) == 1)
                check("Part G: and fails publish-strict non-zero",
                      safe_main(["--read-only", "--publish-strict"]) == 1)
            finally:
                qa.GENERATED_DIR, qa.load_counted_evidence_counts = orig_dir, orig_loader
    else:
        check("Part G: the real candidate record is present to promote", False, str(candidate))

    print()
    print("=" * 92)
    print("PART H  a citation the evidence does not support, with volume satisfied")
    print("=" * 92)

    # FROZEN AND SYNTHETIC, independent of the live corpus, because scheduled collection changes
    # the real one. Thirty-four reports are accepted; one is then invalidated, leaving 33 -- still
    # at the rung. The record keeps citing the invalidated report. Count, length, distinctness and
    # volume ALL agree, so a failure here is attributable to the contradiction and to nothing else.
    url_at = (lambda i: f"https://github.com/obsproject/obs-studio/issues/{20000 + i}")
    accepted_pop = {qa.normalize_url(url_at(i)) for i in range(N)}          # 33 still accepted
    withdrawn = url_at(N)                                                   # the 34th, invalidated
    cited = [{"source_url": url_at(i), "patch_version_matched": True} for i in range(N - 1)]
    cited.append({"source_url": withdrawn, "patch_version_matched": True})  # 33 cited, one unsupported
    contradiction = record(count=N, srcs=cited)

    found = codes(contradiction, {KEY: N}, {KEY: accepted_pop})
    check("Part H: a cited report absent from the accepted population is refused",
          "live_source_not_in_accepted_population" in found, str(found))
    check("Part H: and the refusal is NOT a volume failure -- the rung is met",
          "live_without_sufficient_accepted_evidence" not in found, str(found))
    check("Part H: nor a count disagreement -- the published count matches the authority",
          "live_count_disagrees_with_evidence" not in found, str(found))
    check("Part H: nor a length or distinctness failure",
          not ({"live_sources_not_exhaustive", "live_sources_not_distinct"} & found), str(found))
    # Exactly the two halves of the contradiction, and nothing else: no volume failure, no count
    # disagreement, no length or distinctness complaint.
    check("Part H: the contradiction is the ONLY thing reported",
          found == {"live_source_not_in_accepted_population", "live_accepted_report_omitted"},
          str(found))

    supported = [{"source_url": url_at(i), "patch_version_matched": True} for i in range(N)]
    check("Part H: the same record citing only supported reports passes",
          codes(record(count=N, srcs=supported), {KEY: N}, {KEY: accepted_pop}) == set())

    # A substitution must name BOTH halves: the invented citation and the real report it displaced.
    substitution = codes(record(count=N, srcs=cited), {KEY: N}, {KEY: accepted_pop})
    check("Part H: a substitution reports the unsupported citation",
          "live_source_not_in_accepted_population" in substitution, str(substitution))
    check("Part H: and names the accepted report it displaced",
          "live_accepted_report_omitted" in substitution, str(substitution))
    check("Part H: a complete, exactly-corresponding projection reports neither",
          not ({"live_source_not_in_accepted_population", "live_accepted_report_omitted"}
               & codes(record(count=N, srcs=supported), {KEY: N}, {KEY: accepted_pop})))

    # Per-comment URLs are separately countable reports. normalize_url preserves the query AND the
    # fragment; the query half is pinned in Part B by six real phpBB threads, and this pins the
    # fragment half, which nothing had exercised.
    thread = "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235179"
    comments = [{"source_url": f"{thread}#p{900 + i}", "patch_version_matched": True}
                for i in range(N)]
    comment_pop = {qa.normalize_url(c["source_url"]) for c in comments}
    check("Part H: comment-level URLs on one thread stay distinct reports",
          len(comment_pop) == N and
          codes(record(count=N, srcs=comments), {KEY: N}, {KEY: comment_pop}) == set(),
          str(codes(record(count=N, srcs=comments), {KEY: N}, {KEY: comment_pop})))

    # COUNT PARITY. The grouping function must not move a single count. Rather than assert that,
    # reimplement the tally loop as it stood before the refactor and compare on the real corpus --
    # any divergence is then a named failure instead of something I have to notice.
    from lib.report_counts import counted_evidence_rows  # noqa: PLC0415
    probe = [{"product_id": PRODUCT, "update_version": VERSION, "counted": True,
              "patch_version_matched": True, "source_url": url_at(i)} for i in range(4)]
    probe.append({"product_id": PRODUCT, "update_version": VERSION, "counted": True,
                  "patch_version_matched": False, "source_url": url_at(99)})
    rows_by_key = counted_evidence_rows(probe, windows_targets={})
    check("Part H: the row population and the count come from one predicate",
          {k: len(v) for k, v in rows_by_key.items()}
          == report_counts.counted_evidence_counts(probe, windows_targets={}))
    check("Part H: and a non-patch-matched row is in neither",
          all(r.get("patch_version_matched") is True
              for rows in rows_by_key.values() for r in rows))

    def legacy_counts(rows, *, windows_targets):
        """`counted_evidence_counts` as it tallied BEFORE the row-grouping refactor."""
        from lib.patch_identity import patch_key as pk, require_build  # noqa: PLC0415
        from lib.report_counts import WINDOWS_PRODUCT_ID, windows_identity_gate  # noqa: PLC0415
        counts: dict = {}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            product_id = str(row.get("product_id") or "").strip()
            version = str(row.get("update_version") or "").strip()
            if not product_id or not version:
                continue
            if row.get("counted") is False:
                continue
            if row.get("patch_version_matched") is not True:
                continue
            if product_id == WINDOWS_PRODUCT_ID:
                ok, _r = windows_identity_gate(
                    row, windows_targets.get(pk(product_id, version, row.get("target_build"))))
                if not ok:
                    continue
            require_build(product_id, version, row.get("target_build"), "parity probe")
            key = pk(product_id, version, row.get("target_build"))
            counts[key] = counts.get(key, 0) + 1
        return counts

    store = qa.load_yaml(qa.EVIDENCE_PATH, [])
    live_rows = store.get("evidence") if isinstance(store, dict) else store
    fronts = [qa.front_matter(p) for p in sorted(qa.GENERATED_DIR.glob("*.md"))]
    fronts = [f for f in fronts if f]
    targets = report_counts.windows_targets_from_front_matter(fronts)
    new_counts = report_counts.counted_evidence_counts(live_rows, windows_targets=targets)
    old_counts = legacy_counts(live_rows, windows_targets=targets)
    check("Part H: the refactor moves NO count on the real corpus",
          new_counts == old_counts,
          f"differs on {sorted(set(new_counts.items()) ^ set(old_counts.items()))[:3]}")
    check("Part H: and the parity comparison was not vacuous",
          len(new_counts) > 100 and sum(new_counts.values()) > 1000,
          f"identities={len(new_counts)} rows={sum(new_counts.values())}")

    # PROPAGATION, tested as its own property. The checks above establish that the validator
    # returns the right exit code; these establish that a lane HONOURS it. The failing command is
    # deliberately trivial: a fake SUCCESS would prove nothing about validation, but a fake FAILURE
    # is the only way to assert the abort path without corrupting a real tree.
    from lib.automation_writeback import (VALIDATION_FAILED_PRE_COMMIT, WritebackResult,  # noqa: PLC0415
                                          _run_validation)
    res = WritebackResult(outcome="")
    lane_cmd = "python auxsays/scripts/qa_patch_records.py --read-only --publish-strict"
    check("Part G: the lane's own validate command passes against this tree",
          _run_validation(ROOT.parent, [lane_cmd], res) is True,
          str(res.validation))
    res2 = WritebackResult(outcome="")
    check("Part G: a non-zero validate command is refused, so no commit is created",
          _run_validation(ROOT.parent, ['python -c "import sys; sys.exit(1)"'], res2) is False)
    check("Part G: and the refusal is recorded with its exit code for the lane to report",
          res2.validation and res2.validation[-1]["exit_code"] == 1, str(res2.validation))
    check("Part G: the pre-commit refusal outcome exists and is distinct",
          isinstance(VALIDATION_FAILED_PRE_COMMIT, str) and VALIDATION_FAILED_PRE_COMMIT)

    print()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
