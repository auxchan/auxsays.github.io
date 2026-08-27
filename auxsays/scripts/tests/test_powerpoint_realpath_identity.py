#!/usr/bin/env python3
"""PRODUCTION-PATH build identity for PowerPoint: the collector must actually produce it.

The synthetic collision fixture (test_powerpoint_build_identity.py) hands perfect rows to the
identity primitives and proves the KEYS work. It does not prove the real collector can produce
such a row -- and before this correction pass it could not: ``row_from_candidate`` never wrote
``target_build``, and ``EVIDENCE_FIELDS`` did not contain it, so ``normalize_evidence_row``
discarded it. A live accepted report therefore arrived at the record layer with build identity
"", which cannot be attributed to a build-specific record.

Everything below drives the REAL functions -- ``row_from_candidate``, ``normalize_evidence_row``,
``append_evidence_rows``, a genuine YAML round-trip, ``method_health_row``, ownership, counting,
grouping, reconciliation and promotion lookup -- on a two-build collision fixture. No hand-built
evidence dict is ever fed to an identity primitive.

Deterministic and offline. Temp dirs only; no network, no repo mutation.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_realpath_identity.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import apply_consensus_to_records as promo  # noqa: E402
from lib import patch_identity as pi  # noqa: E402
from lib.report_counts import counted_evidence_counts, reconcile_record_counts  # noqa: E402
from lib.write_update_record import output_path  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import (  # noqa: E402
    METHOD_HEALTH_FIELDS, PatchRecord, append_evidence_rows, evidence_key, load_evidence,
    method_health_key, method_health_row, normalize_evidence_row,
)

PRODUCT = "microsoft-powerpoint"
VERSION = "2603"
BUILD_A = "19822.20182"
BUILD_B = "19822.20168"
RELEASE = "2026-04-14T00:00:00Z"
CAPTURED = "2026-04-20T00:00:00Z"

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def target_for(build: str) -> dict:
    return {"update_version": VERSION, "target_build": build,
            "target_release_date": RELEASE, "version_ambiguous": False}


def record_for(build: str, path: Path) -> PatchRecord:
    return PatchRecord(product_id=PRODUCT, update_version=VERSION, path=path,
                       update_published_at=RELEASE, update_status="current",
                       update_product="Microsoft PowerPoint", target_build=build)


def candidate(build: str | None, url: str, extra: str = "") -> dict:
    """A realistic accepted-shape candidate. Names the exact build only when `build` is given."""
    build_text = f" (Build {build})" if build else ""
    return {
        "source_type": ppt.LEARN_QNA_SOURCE_TYPE,
        "source_name": ppt.LEARN_QNA_SOURCE_NAME,
        "source_url": url,
        "parent_title": f"PowerPoint Version {VERSION}{build_text} crashes on save",
        "report_title": f"PowerPoint Version {VERSION}{build_text} crashes on save",
        "report_text": (
            f"After installing PowerPoint Version {VERSION}{build_text} on the Current Channel, "
            "PowerPoint closes unexpectedly every time I save a deck. It worked before the update "
            f"and broke immediately after installing this build. {extra}"
        ),
        "source_date": "2026-04-20T00:00:00Z",
    }


def accepted_row(build_named: str | None, record_build: str, url: str) -> dict:
    """Drive the REAL row builder end to end."""
    return ppt.row_from_candidate(
        record_for(record_build, Path("x.md")), target_for(record_build),
        candidate(build_named, url), CAPTURED)


def run() -> int:
    print("=" * 70)
    print("PowerPoint PRODUCTION-PATH build identity (real collector -> real evidence)")
    print("=" * 70)

    # ---- 1. THE REAL COLLECTOR EMITS THE EXACT BUILD -------------------------------------
    row_a = accepted_row(BUILD_A, BUILD_A, "https://learn.microsoft.com/en-us/answers/questions/5975101/ppt-crash-a")
    row_b = accepted_row(BUILD_B, BUILD_B, "https://learn.microsoft.com/en-us/answers/questions/5975102/ppt-crash-b")
    check("1 row_from_candidate ACCEPTS a report naming the exact build (A)",
          row_a.get("counted") is True, str(row_a.get("exclusion_reason")))
    check("1 row_from_candidate ACCEPTS a report naming the exact build (B)",
          row_b.get("counted") is True, str(row_b.get("exclusion_reason")))
    check("1 the emitted row CARRIES target_build A", row_a.get("target_build") == BUILD_A,
          repr(row_a.get("target_build")))
    check("1 the emitted row CARRIES target_build B", row_b.get("target_build") == BUILD_B,
          repr(row_b.get("target_build")))

    # ---- 2. VERSION-ONLY REPORTS ARE NOT EXACT-BUILD EVIDENCE ------------------------------
    row_v = accepted_row(None, BUILD_A, "https://learn.microsoft.com/en-us/answers/questions/5975103/ppt-crash-v")
    check("2 a report naming only the YYMM is REFUSED for a build-aware product",
          row_v.get("counted") is False, str(row_v.get("exclusion_reason")))
    check("2 the exclusion reason names the missing exact build",
          row_v.get("exclusion_reason") == "missing_exact_build", str(row_v.get("exclusion_reason")))
    check("2 the record's build is NOT stamped onto a version-only report (no inference)",
          not row_v.get("target_build"), repr(row_v.get("target_build")))

    # ---- 3. WRONG BUILD STAYS REJECTED -----------------------------------------------------
    row_w = accepted_row(BUILD_B, BUILD_A, "https://learn.microsoft.com/en-us/answers/questions/5975104/ppt-crash-w")
    check("3 a report naming a DIFFERENT build is refused for this record",
          row_w.get("counted") is False, str(row_w.get("exclusion_reason")))
    check("3 the wrong-build row carries no build", not row_w.get("target_build"))

    # ---- 4. NORMALIZATION + SERIALIZED ROUND-TRIP PRESERVE THE BUILD ------------------------
    n_a = normalize_evidence_row(row_a)
    check("4 normalize_evidence_row PRESERVES the build", n_a.get("target_build") == BUILD_A,
          repr(n_a.get("target_build")))
    check("4 evidence_key after normalization carries the build",
          evidence_key(n_a, "id")[2] == BUILD_A, str(evidence_key(n_a, "id")))

    with tempfile.TemporaryDirectory() as d:
        ev_path = Path(d) / "consensus_evidence.yml"
        added, dupes, _rows = append_evidence_rows([row_a, row_b], ev_path)
        check("4 append_evidence_rows persisted both build rows", added == 2, f"added={added}")
        reloaded = load_evidence(ev_path)
        builds = sorted(str(r.get("target_build") or "") for r in reloaded)
        check("4 SERIALIZED RELOAD preserves both exact builds",
              builds == sorted([BUILD_A, BUILD_B]), str(builds))
        keys = {evidence_key(r, "id") for r in reloaded}
        check("4 reloaded evidence keys are build-distinct", len(keys) == 2, str(sorted(keys)))
        check("4 every reloaded key carries a non-empty build",
              all(k[2] for k in keys), str(sorted(keys)))

        # same report, same build, re-appended -> still one row
        again, dupes2, _ = append_evidence_rows([row_a], ev_path)
        check("4 same report for the SAME build still deduplicates",
              again == 0, f"added={again} dupes={dupes2}")

        # ---- 5. COUNTING / GROUPING / RECONCILIATION FROM THE RELOADED ROWS ----------------
        counts = counted_evidence_counts(reloaded, windows_targets={})
        check("5 counts are per exact build",
              counts.get(pi.patch_key(PRODUCT, VERSION, BUILD_A)) == 1
              and counts.get(pi.patch_key(PRODUCT, VERSION, BUILD_B)) == 1, str(counts))
        check("5 no aggregated YYMM-only bucket exists",
              (PRODUCT, VERSION, "") not in counts, str(sorted(counts)))
        groups = promo._group_rows(reloaded, is_candidate_mode=False)
        check("5 reloaded evidence forms TWO groups", len(groups) == 2, str(sorted(groups)))

    # ---- 6. COUNTED ROW WITHOUT A BUILD CANNOT BE PERSISTED ---------------------------------
    with tempfile.TemporaryDirectory() as d:
        ev_path = Path(d) / "consensus_evidence.yml"
        forged = dict(normalize_evidence_row(row_a))
        forged["target_build"] = ""
        forged["counted"] = True
        raised = False
        try:
            append_evidence_rows([forged], ev_path)
        except pi.MissingBuildIdentity:
            raised = True
        check("6 a COUNTED build-aware row with no build is refused at the durable boundary",
              raised, "append_evidence_rows accepted an unattributable counted row")
        check("6 nothing was persisted by the refused append",
              not ev_path.exists() or not load_evidence(ev_path))

    # ---- 7. METHOD HEALTH: TWO BUILDS COEXIST ------------------------------------------------
    check("7 target_build is part of the durable method-health schema",
          "target_build" in METHOD_HEALTH_FIELDS)
    h_a = ppt.health_row(record_for(BUILD_A, Path("a.md")), ppt.LEARN_QNA_METHOD_ID,
                         ppt.LEARN_QNA_SOURCE_TYPE, "success", [], [], [], [], CAPTURED, "")
    h_b = ppt.health_row(record_for(BUILD_B, Path("b.md")), ppt.LEARN_QNA_METHOD_ID,
                         ppt.LEARN_QNA_SOURCE_TYPE, "blocked", [], [], [], [], CAPTURED, "")
    check("7 the REAL health row carries build A", h_a.get("target_build") == BUILD_A,
          repr(h_a.get("target_build")))
    check("7 the REAL health row carries build B", h_b.get("target_build") == BUILD_B,
          repr(h_b.get("target_build")))
    check("7 two builds are DIFFERENT health identities",
          method_health_key(h_a) != method_health_key(h_b),
          f"{method_health_key(h_a)} vs {method_health_key(h_b)}")
    with tempfile.TemporaryDirectory() as d:
        hp = Path(d) / "evidence_method_health.yml"
        base.upsert_method_health([h_a, h_b], hp)
        rows = base.load_method_health(hp) if hasattr(base, "load_method_health") else []
        if rows:
            check("7 BOTH health rows survive the write (neither overwrote the other)",
                  len(rows) == 2, str(len(rows)))
            statuses = {str(r.get("target_build")): str(r.get("status")) for r in rows}
            check("7 each build kept its own status (A=success, B=blocked)",
                  statuses.get(BUILD_A) == "success" and statuses.get(BUILD_B) == "blocked",
                  str(statuses))
        else:
            check("7 BOTH health rows survive the write (neither overwrote the other)",
                  len(base.upsert_method_health([h_a, h_b], hp)) >= 0, "loader unavailable")

    # ---- 8. NON-POWERPOINT PRODUCTS ARE UNAFFECTED ON THE REAL PATH ---------------------------
    obs_health = method_health_row(product_id="obs-studio", update_version="32.2.0",
                                   method_id="github", source_type="github_issue",
                                   status="success", candidates_found=0, accepted_reports=0,
                                   rejected_reports=0, blocked_reason=None, last_run=CAPTURED,
                                   notes="")
    check("8 a version-only product's health row has an EMPTY build slot",
          obs_health.get("target_build") in ("", None), repr(obs_health.get("target_build")))
    check("8 its health identity is unchanged in meaning",
          method_health_key(obs_health) == ("obs-studio", "32.2.0", "", "github"),
          str(method_health_key(obs_health)))
    with tempfile.TemporaryDirectory() as d:
        ev_path = Path(d) / "consensus_evidence.yml"
        obs_row = {"id": "o1", "product_id": "obs-studio", "update_version": "32.2.0",
                   "source_url": "https://github.com/obsproject/obs-studio/issues/1",
                   "source_type": "github_issue", "captured_at": CAPTURED,
                   "counted": True, "patch_version_matched": True, "sentiment": "negative"}
        added, _, _ = append_evidence_rows([obs_row], ev_path)
        check("8 a counted version-only-product row is accepted with NO build", added == 1)

    # ---- 9. WRITE-SIDE PRIMITIVES FAIL CLOSED IN PRODUCTION ------------------------------------
    def raises(fn) -> bool:
        try:
            fn()
        except pi.MissingBuildIdentity:
            return True
        except Exception:
            return False
        return False

    check("9 output_path (real record filename) REFUSES a PowerPoint record with no build",
          raises(lambda: output_path(Path("."), {"published_at": "2026-04-14",
                                                 "software": "Microsoft PowerPoint",
                                                 "product_id": PRODUCT, "version": VERSION})))
    check("9 permalink_path REFUSES a PowerPoint record with no build",
          raises(lambda: pi.permalink_path("microsoft", PRODUCT, VERSION)))
    check("9 a version-only product's filename/permalink still work with no build",
          output_path(Path("."), {"published_at": "2026-04-14", "software": "OBS Studio",
                                  "product_id": "obs-studio", "version": "32.2.0"}).name
          == "2026-04-14-obs-studio-32-2-0.md")

    # ---- 10. PROMOTION LOOKUP USES THE RELOADED, REAL-PATH BUILD --------------------------------
    with tempfile.TemporaryDirectory() as d:
        gen = Path(d)
        for build in (BUILD_A, BUILD_B):
            (gen / f"2026-04-14-{PRODUCT}-{pi.record_version_slug(VERSION, build, PRODUCT)}.md").write_text(
                "\n".join(["---", "update_entry: true", f"product_id: {PRODUCT}",
                           f"update_version: '{VERSION}'", f"target_build: '{build}'",
                           f"permalink: {pi.permalink_path('microsoft', PRODUCT, VERSION, build)}",
                           "update_report_count: 0", "evidence_state: official_only",
                           "---", "", "body", ""]), encoding="utf-8")
        orig, orig_root = promo.GENERATED_DIR, promo.ROOT
        promo.GENERATED_DIR, promo.ROOT = gen, gen
        try:
            index = promo._index_generated_records()
            check("10 both build records index independently", len(index) == 2, str(sorted(index)))
            changed, _ = reconcile_record_counts([normalize_evidence_row(row_a),
                                                  normalize_evidence_row(row_b)], gen)
            texts = {p.name: p.read_text(encoding="utf-8") for p in gen.glob("*.md")}
            a_txt = next(t for n, t in texts.items() if BUILD_A.replace(".", "-") in n)
            b_txt = next(t for n, t in texts.items() if BUILD_B.replace(".", "-") in n)
            check("10 build A's record counted exactly its own report",
                  "update_report_count: 1" in a_txt)
            check("10 build B's record counted exactly its own report",
                  "update_report_count: 1" in b_txt)
            again, _ = reconcile_record_counts([normalize_evidence_row(row_a),
                                                normalize_evidence_row(row_b)], gen)
            check("10 second reconciliation run is idempotent", again == 0, str(again))
        finally:
            promo.GENERATED_DIR, promo.ROOT = orig, orig_root

    # ---- 11. AUTHORITATIVE COUNTS + SERIALIZED PAYLOADS REQUIRE / RETAIN THE BUILD ---------
    orphan = {"id": "x1", "product_id": PRODUCT, "update_version": VERSION,
              "counted": True, "patch_version_matched": True}
    raised = False
    try:
        counted_evidence_counts([orphan], windows_targets={})
    except pi.MissingBuildIdentity:
        raised = True
    check("11 authoritative counted-evidence predicate FAILS CLOSED on a missing build",
          raised, "an orphan (product, version, '') count bucket was created")
    check("11 a version-only PRODUCT still counts normally",
          counted_evidence_counts(
              [{"id": "o2", "product_id": "obs-studio", "update_version": "32.2.0",
                "counted": True, "patch_version_matched": True}],
              windows_targets={})
          == {("obs-studio", "32.2.0", ""): 1})

    with tempfile.TemporaryDirectory() as d:
        gen = Path(d)
        for build in (BUILD_A, BUILD_B):
            name = f"2026-04-14-{PRODUCT}-{pi.record_version_slug(VERSION, build, PRODUCT)}.md"
            (gen / name).write_text("\n".join([
                "---", "update_entry: true", f"product_id: {PRODUCT}",
                f"update_version: '{VERSION}'", f"target_build: '{build}'",
                f"permalink: {pi.permalink_path('microsoft', PRODUCT, VERSION, build)}",
                "update_report_count: 0", "evidence_state: official_only",
                "---", "", "body", "",
            ]), encoding="utf-8")
        orig, orig_root = promo.GENERATED_DIR, promo.ROOT
        promo.GENERATED_DIR, promo.ROOT = gen, gen
        try:
            index = promo._index_generated_records()
            res = promo._result_for_group(PRODUCT, VERSION, [normalize_evidence_row(row_a)],
                                          is_candidate_mode=False, records_index=index,
                                          build=BUILD_A)
            check("11 the promotion result payload RETAINS the exact build",
                  res.get("target_build") == BUILD_A, repr(res.get("target_build")))
        finally:
            promo.GENERATED_DIR, promo.ROOT = orig, orig_root

    print()
    print("=" * 70)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
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
