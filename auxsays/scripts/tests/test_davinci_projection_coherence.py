#!/usr/bin/env python3
"""The lane that moves DaVinci's count must also rebuild the projections derived from it.

THE DEFECT (live on main a4b85599). 8 of 120 DaVinci records published a count their own source
list and headline contradicted -- 2026-04-14-davinci-resolve-21.md said `update_report_count: 56`
beside 40 `accepted_report_sources` and a `quick_verdict` reading "has 40 user reports found". The
count was RIGHT in every case: the canonical counted population is authoritative and the two
PROJECTIONS lagged it. 16 qa_patch_records warnings, all of this shape.

WHY. Until PR #69 (fd0cfa98) the DaVinci collector wrote the whole projection itself. #69 narrowed
every in-collector write to COLLECTOR_WRITABLE_FIELDS = {evidence_last_checked, record_last_updated}
and delegated counts and projections to "a later authority". Five products have that authority as a
scoped `apply_consensus_to_records --product-id X --write-all` step in the SCHEDULED
obs-evidence-collection.yml lane. DaVinci's only promotion lives in davinci-updates.yml, which is
workflow_dispatch-only, last ran 2026-06-18 (failed), and whose DaVinci step -- added by #76 -- has
never executed in production. Meanwhile that scheduled lane runs an UNSCOPED reconcile_record_counts
on every cron tick, which writes DaVinci's number. The gap was invisible while DaVinci discovery was
starved and opened when PR #131 restored newest-first traversal: the first divergent commit came
from the lane run created 25 seconds after that merge.

IT WAS NOT ONLY COSMETIC. A DaVinci record crossing 0 -> N with nothing to build its summary is the
#70 wedge: runs 34717343799, 34807610424 and 34998144189 all died at "QA patch records" on
2026-08-05-davinci-resolve-21-0-4.md, and because QA precedes the writeback, EVERY product's
evidence for those three cycles was discarded.

WHAT THIS SUITE PINS. [L] the scheduled lane owns the rebuild, scoped and correctly positioned --
read from the workflow's parsed `run:` scalars, with a counterfactual proving the checks can fail.
[P] end to end over a temp tree: reconciliation alone reproduces the drift, and the promotion
converges count, source list and headline -- asserted through the SHIPPED qa_patch_records
predicates, not a re-implementation. [A] new evidence moves all three together. [N] a repeat run
writes nothing. [S] no other product and no evidence row is touched, and no row moves between
versions. [Z] the zero-count residual is stated, not assumed.

Deterministic and offline: no network, no git, writes only inside a temp dir.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_projection_coherence.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
import qa_patch_records as qa  # noqa: E402
from lib.report_counts import CONSENSUS_PROMOTION_PRODUCTS, reconcile_record_counts  # noqa: E402

WORKFLOW = _REPO / ".github" / "workflows" / "obs-evidence-collection.yml"
DAV = "blackmagic-davinci"
OTHER = "obs-studio"
NEWLINE = "\n"

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
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


# ---------------------------------------------------------------- workflow reading helpers

def collect_steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["collect"]["steps"]


def shell_command(run_text: str) -> str:
    """The COMMAND text of a step, with `#` comments removed (quote-aware).

    These workflow steps carry long comments that DISCUSS `--allow` and `automation_writeback`.
    Tokenising the raw scalar harvested the literal word `entry` out of the prose
    "are in no --allow entry for this lane" and put it in the allow list -- the same vacuity class
    the writer-queue suite was rewritten to avoid.
    """
    out: list[str] = []
    for line in run_text.splitlines():
        kept: list[str] = []
        quote = ""
        for ch in line:
            if quote:
                kept.append(ch)
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                quote = ch
                kept.append(ch)
            elif ch == "#":
                break
            else:
                kept.append(ch)
        out.append("".join(kept))
    return NEWLINE.join(out)


def flag_values(run_text: str, flag: str) -> list[str]:
    """Values of `flag` in a shell scalar, tolerant of line continuations. Comments stripped."""
    toks = shell_command(run_text).replace("\\" + NEWLINE, " ").split()
    out = [toks[i + 1].strip("'\"") for i, tok in enumerate(toks[:-1]) if tok == flag]
    out += [tok.split("=", 1)[1].strip("'\"") for tok in toks if tok.startswith(flag + "=")]
    return out


def promotion_index(steps: list[dict], product: str) -> int:
    for i, st in enumerate(steps):
        run_text = str(st.get("run") or "")
        if "apply_consensus_to_records" in run_text and product in flag_values(run_text, "--product-id"):
            return i
    return -1


def indices(steps: list[dict]) -> tuple[int, list[int]]:
    reconcile = next((i for i, st in enumerate(steps)
                      if "build_consensus_from_evidence" in str(st.get("run") or "")), -1)
    qa_steps = [i for i, st in enumerate(steps) if "qa_patch_records" in str(st.get("run") or "")]
    return reconcile, qa_steps


# ---------------------------------------------------------------- fixture helpers

def evidence_row(version: str, n: int, *, product: str = DAV) -> dict:
    """One row shaped like the live corpus, passing every gate in acr._filter_rows."""
    return {
        "id": f"{product}-{version}-row-{n}",
        "product_id": product,
        "update_version": version,
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
        "source_url": f"https://forum.example.invalid/t/{version}/{n}",
        "report_title": f"{version} issue {n}",
        "report_text_excerpt": f"User-verified report describing an issue on {version}.",
        "captured_at": "2026-09-01T00:00:00Z",
        "patch_version_matched": True,
        "matched_version": version,
        "counted": True,
        "issue_theme": "playback_stutter",
        "severity": "high",
        "sentiment": "negative",
        "source_weight": 1,
    }


def write_record(path: Path, *, product: str, version: str, count: int, sources: int,
                 verdict_count: int | None = None) -> None:
    """A record carrying projections that may deliberately disagree with its count."""
    verdict_n = count if verdict_count is None else verdict_count
    label = "DaVinci Resolve" if product == DAV else "OBS Studio"
    data = {
        "layout": "aux-update", "update_entry": True,
        "product_id": product, "update_version": version, "update_product": label,
        "update_report_count": count, "confirmed_patch_specific_report_count": count,
        "accepted_report_sources": [{"source": f"s{i}", "source_url": f"https://x.invalid/{i}"}
                                    for i in range(sources)],
        "evidence_samples": [{"source": "s0"}],
        "update_consensus_summary": f"WAIT: {label} {version} has {verdict_n} user reports found.",
        "consensus_report": f"{verdict_n} user reports found for {label} {version}.",
        "quick_verdict": f"WAIT: {label} {version} has {verdict_n} user reports found.",
    }
    path.write_text("---" + NEWLINE + yaml.safe_dump(data, sort_keys=False) + "---" + NEWLINE + "body" + NEWLINE,
                    encoding="utf-8")


def front_matter(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def verdict_number(data: dict) -> int | None:
    import re
    m = re.search(r"(\d+)\s+user report", str(data.get("quick_verdict") or ""))
    return int(m.group(1)) if m else None


def qa_codes(path: Path, evidence: Path) -> set[str]:
    """The SHIPPED predicates, not a re-implementation of them.

    The two checks this defect produces live in DIFFERENT scanners: `quick_verdict_count_mismatch`
    is per-record (scan_record), while `report_count_source_list_mismatch` needs the canonical
    counted population and therefore lives in scan_evidence_count_alignment, which reads the
    module-global EVIDENCE_PATH. Calling only the first would have made this suite blind to exactly
    half the defect -- it did, on the first run.
    """
    saved = qa.EVIDENCE_PATH
    qa.EVIDENCE_PATH = evidence
    try:
        errors, warnings = qa.scan_record(path)
        e2, w2 = qa.scan_evidence_count_alignment([path])
    finally:
        qa.EVIDENCE_PATH = saved
    return {str(item.get("code") or item) for item in list(errors) + list(warnings) + list(e2) + list(w2)}


def promote(tree: Path, evidence: Path, product: str = DAV) -> int:
    """Run the real promotion against a temp tree by pointing the module's paths at it.

    ROOT travels with the tree: the writer stores each record as a path RELATIVE to ROOT
    (_index_generated_records) and reconstructs it as ``ROOT / record_rel`` before writing, so a
    tree outside ROOT raises ValueError. The fixture therefore mirrors the real layout,
    ``<tmp>/auxsays/updates/generated``, and ROOT points at its ``auxsays``.
    """
    saved = (acr.ROOT, acr.GENERATED_DIR, acr.DEFAULT_EVIDENCE_PATH, acr.METHOD_HEALTH_PATH)
    acr.ROOT = tree.parents[1]
    acr.GENERATED_DIR = tree
    acr.DEFAULT_EVIDENCE_PATH = evidence
    acr.METHOD_HEALTH_PATH = tree / "no-method-health.yml"      # absent -> no limitations block
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return acr.main(["--product-id", product, "--write-all", "--confirm-write"])
    finally:
        acr.ROOT, acr.GENERATED_DIR, acr.DEFAULT_EVIDENCE_PATH, acr.METHOD_HEALTH_PATH = saved


def write_evidence(path: Path, rows: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "evidence": rows}, sort_keys=False),
                    encoding="utf-8")


# ---------------------------------------------------------------- the suite

def run() -> int:
    print("=" * 78)
    print("DaVinci projection coherence: the lane that moves the count rebuilds its projections")
    print("=" * 78)

    # ---------- L: the scheduled lane owns the rebuild ----------
    print(NEWLINE + "[L] the SCHEDULED lane promotes DaVinci, scoped and correctly positioned")
    raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = collect_steps()
    reconcile_i, qa_steps = indices(steps)
    dav_i = promotion_index(steps, DAV)

    on = raw.get(True) if True in raw else raw.get("on")     # YAML parses bare `on:` as True
    check("L1 this lane runs on a schedule, not only by dispatch",
          bool((on or {}).get("schedule")),
          "davinci-updates.yml is workflow_dispatch-only, which is why its promotion never ran")
    check("L2 DaVinci has a scoped promotion step in the collect job", dav_i >= 0,
          str([st.get("name") for st in steps]))
    check("L3 the step names exactly one product, and never an empty one",
          dav_i >= 0 and flag_values(str(steps[dav_i].get("run") or ""), "--product-id") == [DAV],
          "an empty --product-id is falsy in run_dry_run's filter and would promote the whole corpus")
    dav_cmd = shell_command(str(steps[dav_i].get("run") or "")) if dav_i >= 0 else ""
    check("L3b the step actually WRITES -- without both flags it rebuilds nothing",
          "--write-all" in dav_cmd and "--confirm-write" in dav_cmd,
          "a step reduced to a dry run leaves every projection stale while the lane stays green")
    check("L3c it runs under the same dry-run guard as its neighbours",
          str(steps[dav_i].get("if") or "") == str(steps[promotion_index(steps, 'obs-studio')].get("if") or ""),
          f"davinci if={steps[dav_i].get('if')!r}")
    check("L4 the promotion runs AFTER reconciliation", 0 <= reconcile_i < dav_i,
          f"reconcile={reconcile_i} davinci={dav_i}")
    check("L5 nothing validates between reconciliation and the promotion",
          not [i for i in qa_steps if reconcile_i < i < dav_i],
          f"reconcile={reconcile_i} qa={qa_steps} davinci={dav_i} -- a QA step in that gap is the "
          "#70 wedge: it kills the run before the rebuild and discards every product's evidence")
    check("L6 QA still runs after the promotion", any(i > dav_i for i in qa_steps),
          f"qa={qa_steps} davinci={dav_i}")

    import fnmatch
    allows: list[str] = []
    for st in steps:
        # Select the writeback by what it RUNS, not by a substring any comment can contain.
        if "automation_writeback" in shell_command(str(st.get("run") or "")):
            allows += flag_values(str(st.get("run") or ""), "--allow")
    # Read live records with the SHIPPED loader, not yaml.safe_load: some records carry bodies with
    # CRLF inside a quoted scalar that plain safe_load refuses, and a suite that dies there would be
    # reporting on the corpus rather than on this repair.
    live_records = [p for p in sorted((_REPO / "auxsays" / "updates" / "generated").glob("*.md"))
                    if str((acr._load_front_matter(p) or {}).get("product_id") or "").strip() == DAV]
    unmatched = [p.name for p in live_records
                 if not any(fnmatch.fnmatch(f"auxsays/updates/generated/{p.name}", pat) for pat in allows)]
    check(f"L7 the writeback may commit EVERY DaVinci record ({len(live_records)} live)",
          bool(live_records) and not unmatched,
          f"unmatched={unmatched[:4]} allows={allows} -- a record the promotion rewrites but the "
          "allow list misses makes automation_writeback refuse the whole lane (UNSTAGED_CHANGED_PATH)")

    # Non-vacuity: the L-checks must FAIL when the step is gone, or they assert nothing.
    without = [st for i, st in enumerate(steps) if i != dav_i]
    w_reconcile, w_qa = indices(without)
    w_dav = promotion_index(without, DAV)
    check("L8 COUNTERFACTUAL: with the step removed these checks fail",
          w_dav < 0 and not (0 <= w_reconcile < w_dav),
          "the ordering assertions would pass with no DaVinci promotion at all")

    # ---------- P: end to end, through the shipped predicates ----------
    print(NEWLINE + "[P] reconciliation alone drifts; the promotion converges all three projections")
    with tempfile.TemporaryDirectory() as td:
        # Mirror the real layout so the writer's ROOT-relative round trip works (see promote()).
        tree = Path(td) / "auxsays" / "updates" / "generated"
        tree.mkdir(parents=True)
        evidence = Path(td) / "auxsays" / "_data" / "consensus_evidence.yml"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        dav_rec = tree / "2026-02-12-davinci-resolve-20-3-2.md"
        other_rec = tree / "2026-08-14-obs-studio-32-2-2.md"
        # The live shape: projections built when the count was 3, evidence has since grown to 5.
        write_record(dav_rec, product=DAV, version="20.3.2", count=3, sources=3)
        write_record(other_rec, product=OTHER, version="32.2.2", count=2, sources=2)
        rows = [evidence_row("20.3.2", i) for i in range(5)]
        rows += [evidence_row("32.2.2", i, product=OTHER) for i in range(2)]
        write_evidence(evidence, rows)
        evidence_before = evidence.read_bytes()

        reconcile_record_counts(rows, tree)
        # Snapshot the other product AFTER reconciliation: that step is unscoped by design and
        # legitimately normalises every record's count-derived state. What must not move it is the
        # DaVinci-SCOPED promotion, so the comparison has to bracket the promotion alone.
        other_before = other_rec.read_bytes()
        after_reconcile = front_matter(dav_rec)
        check("P1 reconciliation moves the COUNT on its own",
              after_reconcile["update_report_count"] == 5, str(after_reconcile["update_report_count"]))
        check("P2 ...and leaves the source list and headline behind -- the live defect",
              len(after_reconcile["accepted_report_sources"]) == 3 and verdict_number(after_reconcile) == 3,
              f"sources={len(after_reconcile['accepted_report_sources'])} verdict={verdict_number(after_reconcile)}")
        drift_codes = qa_codes(dav_rec, evidence)
        check("P3 the SHIPPED QA predicates report that drift",
              {"report_count_source_list_mismatch", "quick_verdict_count_mismatch"} <= drift_codes,
              str(sorted(drift_codes)))

        rc = promote(tree, evidence)
        promoted = front_matter(dav_rec)
        check("P4 the promotion exits 0", rc == 0, str(rc))
        check("P5 the source list now matches the count",
              promoted["update_report_count"] == 5 == len(promoted["accepted_report_sources"]),
              f"count={promoted['update_report_count']} sources={len(promoted['accepted_report_sources'])}")
        check("P6 the headline states the same number",
              verdict_number(promoted) == 5, str(verdict_number(promoted)))
        check("P7 and the SHIPPED QA predicates report neither warning",
              not ({"report_count_source_list_mismatch", "quick_verdict_count_mismatch"} & qa_codes(dav_rec, evidence)),
              str(sorted(qa_codes(dav_rec, evidence))))
        check("P8 the count itself was never moved by the promotion",
              promoted["update_report_count"] == after_reconcile["update_report_count"],
              "the counted population is authoritative; promotion may only rebuild what derives from it")

        # ---------- A: new evidence lands atomically ----------
        print(NEWLINE + "[A] new accepted evidence moves count, sources and headline together")
        rows.append(evidence_row("20.3.2", 99))
        write_evidence(evidence, rows)
        reconcile_record_counts(rows, tree)
        promote(tree, evidence)
        grown = front_matter(dav_rec)
        check("A1 all three projections advanced to the new population",
              grown["update_report_count"] == 6 == len(grown["accepted_report_sources"])
              and verdict_number(grown) == 6,
              f"count={grown['update_report_count']} sources={len(grown['accepted_report_sources'])} "
              f"verdict={verdict_number(grown)}")
        check("A2 the record is clean under the shipped predicates",
              not ({"report_count_source_list_mismatch", "quick_verdict_count_mismatch"} & qa_codes(dav_rec, evidence)),
              str(sorted(qa_codes(dav_rec, evidence))))

        # ---------- N: N+1 introduces no drift ----------
        print(NEWLINE + "[N] a further run writes nothing -- no drift is reintroduced")
        before_bytes = dav_rec.read_bytes()
        reconcile_record_counts(rows, tree)
        promote(tree, evidence)
        check("N1 an already-converged record is byte-identical after another cycle",
              dav_rec.read_bytes() == before_bytes,
              "a rebuild that rewrites on every run would churn the corpus and the writeback")

        # ---------- S: scope ----------
        print(NEWLINE + "[S] nothing else is touched")
        check("S1 the other product's record is untouched",
              other_rec.read_bytes() == other_before,
              "a DaVinci-scoped promotion must not rewrite another product's projections")
        # Bracket a promotion with byte snapshots of the population file. Comparing against a
        # re-serialised string instead would compare CRLF on disk with LF in memory and fail for a
        # reason that has nothing to do with the property.
        evidence_before_promote = evidence.read_bytes()
        promote(tree, evidence)
        check("S2 the evidence file itself is never rewritten by the promotion",
              evidence.read_bytes() == evidence_before_promote,
              "projections are derived from evidence; the promotion may not edit the population")
        check("S3 no row moved between versions: every published source belongs to this version",
              all(str(s.get("source_url", "")).find("/20.3.2/") >= 0
                  for s in front_matter(dav_rec)["accepted_report_sources"]),
              str(front_matter(dav_rec)["accepted_report_sources"])[:160])

        # A second DaVinci version must keep its own population.
        second = tree / "2026-04-14-davinci-resolve-21.md"
        write_record(second, product=DAV, version="21", count=0, sources=0)
        rows2 = rows + [evidence_row("21", i) for i in range(2)]
        write_evidence(evidence, rows2)
        reconcile_record_counts(rows2, tree)
        promote(tree, evidence)
        first_fm, second_fm = front_matter(dav_rec), front_matter(second)
        check("S4 each version projects only its own counted rows",
              first_fm["update_report_count"] == 6 == len(first_fm["accepted_report_sources"])
              and second_fm["update_report_count"] == 2 == len(second_fm["accepted_report_sources"]),
              f"20.3.2={first_fm['update_report_count']}/{len(first_fm['accepted_report_sources'])} "
              f"21={second_fm['update_report_count']}/{len(second_fm['accepted_report_sources'])}")

        # ---------- Z: the residual this repair deliberately does not close ----------
        print(NEWLINE + "[Z] the zero-count residual is stated, not assumed")
        check("Z1 DaVinci is still NOT retraction-eligible -- a deliberate, separate decision",
              DAV not in CONSENSUS_PROMOTION_PRODUCTS,
              "if membership is ever granted, R6 in test_windows_count_authority.py needs a new "
              "fixture product and R8/D11/O11 need rewriting; see this suite's header")
        zero = tree / "2026-07-02-davinci-resolve-21-0-2.md"
        write_record(zero, product=DAV, version="21.0.2", count=4, sources=4)
        reconcile_record_counts(rows2, tree)          # no rows for 21.0.2 -> canonical zero
        zero_fm = front_matter(zero)
        promote(tree, evidence)
        check("Z2 a canonical zero keeps its stale source list, because promotion skips it",
              zero_fm["update_report_count"] == 0
              and len(front_matter(zero).get("accepted_report_sources") or []) == 4,
              "this is the named residual: only retraction can clear it, and that needs membership")

    # ---------- D: the two predicates that decide a DaVinci count must agree ----------
    print(NEWLINE + "[D] reconcile and the promotion must count the same rows")
    # Reconcile counts a row when `counted is not False` AND `patch_version_matched is True`
    # (lib/report_counts.py). The promotion ALSO requires a non-empty source_url and a valid
    # sentiment/severity, and a single row with source_date_pass False blocks its whole group. Where
    # the two diverge, reconcile raises the count while the promotion skips the group at count <= 0,
    # leaving a record above zero with NO update_consensus_summary -- which is the same lane-killing
    # shape this repair exists to close, reopened from the other side. So the closure claim is only
    # as good as this equality, and it is measured here rather than assumed.
    import build_consensus_from_evidence as bce  # noqa: PLC0415
    from lib.report_counts import counted_evidence_counts, windows_targets_from_front_matter  # noqa: PLC0415

    live_rows = bce.load_evidence()
    live_fm = [acr._load_front_matter(p) or {}
               for p in sorted((_REPO / "auxsays" / "updates" / "generated").glob("*.md"))]
    canonical = counted_evidence_counts(live_rows, windows_targets=windows_targets_from_front_matter(live_fm))
    divergent = []
    dav_keys = [k for k in canonical if str(k[0]) == DAV]
    for key in sorted(dav_keys, key=str):
        included, _excluded = acr._filter_rows(live_rows, product_id=DAV, version=str(key[1]),
                                               is_candidate_mode=False, record=None)
        if len(included) != canonical[key]:
            divergent.append(f"{key[1]}: counted={canonical[key]} promotable={len(included)}")
    check(f"D1 every canonically counted DaVinci row is promotable ({len(dav_keys)} patch keys)",
          bool(dav_keys) and not divergent,
          "; ".join(divergent[:4]) + " -- reconcile would raise a count the promotion cannot "
          "rebuild, leaving the record at count > 0 with no summary and wedging the lane at QA")

    # The lane now regenerates DaVinci prose every 6 hours. _record_coherence_fields' davinci branch
    # owns quick_verdict / decision label+body / recommendations, and for update_version "21" also
    # description, official_summary, release_summary and the feed/status fields. Those last are NOT
    # count projections: if a human edits one, an unattended promotion would revert it within a
    # cycle -- the PR #76 premiere hazard. Today every live value already equals what the writer
    # would produce, so the promotion proposes no change to them; this check is what turns a future
    # hand edit into a failing build instead of a silent revert.
    EDITORIAL = {"description", "official_summary", "release_summary", "update_status",
                 "status_change_type", "notification_message", "update_channel_label", "feed_hidden",
                 "record_note"}
    index = acr._index_generated_records()
    results = acr.run_dry_run(evidence_path=acr.DEFAULT_EVIDENCE_PATH, product_id_filter=DAV,
                              is_candidate_mode=False, records_index=index, write_requested=True)
    contested: list[str] = []
    for result in results:
        rel = ((result.get("matched_record") or {}).get("path")
               or (result.get("record") or {}).get("path") or "")
        proposed = result.get("proposed_fields_if_written") or {}
        if not rel or not proposed:
            continue
        current = acr._load_front_matter(_REPO / "auxsays" / rel) or {}
        would_change = set(acr._fields_for_record_write(current, proposed))
        touched = sorted(would_change & EDITORIAL)
        if touched:
            contested.append(f"{Path(rel).name}: {touched}")
    check(f"D2 the promotion would rewrite no hand-ownable DaVinci field ({len(results)} groups)",
          not contested, "; ".join(contested[:4]) + " -- a human edit to these is reverted by the "
          "next scheduled run; decide ownership before letting this land")

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
        raise SystemExit(2)
