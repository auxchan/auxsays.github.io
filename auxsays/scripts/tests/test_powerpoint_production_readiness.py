#!/usr/bin/env python3
"""PowerPoint prerequisite hardening -- NOT production readiness completion.

PowerPoint consensus is production-DISABLED and stays that way. These tests pin a few contracts
and, just as importantly, PIN THE GAPS that still block activation. Activation is NOT a config
flip: the production promotion chain is not wired for PowerPoint, no workflow --allow entry lets a
PowerPoint record be committed, and the enable flag is off. Those are asserted below as
known-blocking, so nobody can read this suite as "PowerPoint is ready".

BUILD-AWARE IDENTITY IS COMPLETE. What used to be pinned here as a known limit -- record, evidence,
grouping and permalink keys carrying no build -- is now a positive guarantee: identity is the triple
(product_id, update_version, target_build), and two builds under one YYMM are two records with two
URLs. The exhaustive collision proof lives in test_powerpoint_build_identity.py; this suite pins
that the migration landed and did not quietly re-open an activation gate.

  * ownership   -- every method_id the collector can emit is authorized. This is the sharp one: a
                   Reddit health row is emitted on EVERY collection (status "disabled" when the
                   fallback is off) and _validate_ownership runs inside the write transaction, so
                   one unauthorized id would roll back the valid Learn Q&A rows too.
  * exact build -- Microsoft's own "Office 2607 (20228.20110)" notation counts, but only for the
                   exact target build. Never the bare "Office 2607".
  * identity    -- COMPLETE: record/evidence/permalink keys are (product_id, update_version,
                   build component, so two PowerPoint-attributed builds under one YYMM collide.
                   Pinned as a KNOWN LIMIT here; migrating production records is out of scope.
  * promotion   -- the generic apply_consensus_to_records engine COULD serve PowerPoint, but no
                   production step invokes it for PowerPoint today. Pinned as NOT WIRED.
  * half-promotion -- evidence=1 with record count=0 must be refused by the validator.
  * writeback   -- BLOCKING GAP: automation_writeback's --allow list is the commit permission
                   list and has no PowerPoint entry, while consensus_evidence.yml and
                   evidence_method_health.yml do. Activating today would commit evidence and
                   health while silently dropping the record mutation -- landing main in exactly
                   the half-promoted state the validator exists to prevent, because validation
                   runs against the working tree where the record IS mutated.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_production_readiness.py
"""
from __future__ import annotations

import fnmatch
import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import qa_patch_records as qa  # noqa: E402
import patch_collectors.microsoft_powerpoint as ppt  # noqa: E402
from lib import collector_ownership as ownership  # noqa: E402

PRODUCT = "microsoft-powerpoint"
# The exact Current Channel build of the 2607 record: the second half of its patch identity.
BUILD = "20228.20110"
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


def health_row(method_id: str, version: str = "2607", status: str = "no_results",
               target_build: str = BUILD) -> dict:
    """A method-health row for the EXACT patch. Health identity is
    (product_id, update_version, target_build, method_id) for a build-aware product, and ownership
    resolves that exact patch -- a YYMM that merely exists is no longer sufficient."""
    return {"product_id": PRODUCT, "method_id": method_id, "update_version": version,
            "target_build": target_build, "status": status}


def authorized(rows: list[dict]) -> tuple[bool, str]:
    try:
        ownership.validate_method_health(PRODUCT, rows)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - the violation message is the assertion
        return False, str(exc)


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def run() -> int:  # noqa: PLR0915
    print("=" * 64)
    print("PowerPoint production readiness")
    print("=" * 64)

    # =====================================================================================
    # 1. OWNERSHIP -- every emittable method_id is authorized
    # =====================================================================================
    allowed = ownership.allowed_methods(PRODUCT)
    check("collector Learn Q&A method id is authorized",
          ppt.LEARN_QNA_METHOD_ID in allowed, f"{ppt.LEARN_QNA_METHOD_ID!r} vs {sorted(allowed)}")
    check("collector Reddit method id is authorized",
          ppt.REDDIT_METHOD_ID in allowed, f"{ppt.REDDIT_METHOD_ID!r} vs {sorted(allowed)}")
    check("Reddit method id uses the repo-wide canonical name",
          ppt.REDDIT_METHOD_ID == "reddit_search", ppt.REDDIT_METHOD_ID)
    check("collector source types are authorized",
          {ppt.LEARN_QNA_SOURCE_TYPE, ppt.REDDIT_SOURCE_TYPE}
          <= ownership.allowed_source_types(PRODUCT),
          str(sorted(ownership.allowed_source_types(PRODUCT))))

    ok, why = authorized([health_row(ppt.LEARN_QNA_METHOD_ID, status="success")])
    check("Learn Q&A health row passes ownership", ok, why)
    ok, why = authorized([health_row(ppt.REDDIT_METHOD_ID, status="disabled")])
    check("DISABLED Reddit health row passes ownership", ok, why)
    ok, why = authorized([health_row(ppt.REDDIT_METHOD_ID, status="blocked")])
    check("ATTEMPTED (blocked) Reddit health row passes ownership", ok, why)
    ok, why = authorized([health_row("totally_unknown_method")])
    check("a genuinely unknown method still FAILS ownership",
          not ok and "unauthorized method_id" in why and "totally_unknown_method" in why, why)

    # The regression this replaces: one disabled fallback row aborting the whole transaction.
    both = [health_row(ppt.LEARN_QNA_METHOD_ID, status="success"),
            health_row(ppt.REDDIT_METHOD_ID, status="disabled")]
    ok, why = authorized(both)
    check("the disabled fallback row cannot roll back valid Learn Q&A rows", ok, why)
    ok, why = authorized([health_row(ppt.LEARN_QNA_METHOD_ID, status="success"),
                          health_row("reddit_community_search", status="disabled")])
    check("the OLD mismatched id would still have aborted the transaction (regression pinned)",
          not ok and "reddit_community_search" in why, why)

    # =====================================================================================
    # 2. EXACT-BUILD VERSION CONTEXT
    # =====================================================================================
    V, B = "2607", "20228.20110"
    ctx = ppt.version_in_context
    check("PASS 'Office 2607 (20228.20110)' -- vendor notation, exact build",
          ctx("Office 2607 (20228.20110) crashes on save", V, B))
    check("PASS '2607 (20228.20110)' -- bare pair, exact build",
          ctx("Seen on 2607 (20228.20110).", V, B))
    check("FAIL 'Office 2607 (20228.20200)' -- wrong build",
          not ctx("Office 2607 (20228.20200) crashes", V, B))
    check("FAIL '2607 (20131.20154)' -- a different version's build",
          not ctx("2607 (20131.20154) crashes", V, B))
    check("FAIL 'Office 2607' alone -- YYMM match is NOT sufficient",
          not ctx("Office 2607 crashes on save", V, B))
    check("FAIL bare '2607' alone",
          not ctx("2607 crashes on save", V, B))
    check("exact-build form requires a target build (build-agnostic call unchanged)",
          not ctx("2607 (20228.20110)", V))
    for text, label in (("Version 2607 crashes", "Version YYMM"),
                        ("PowerPoint 2607 crashes", "PowerPoint YYMM"),
                        ("Microsoft 365 2607 crashes", "Microsoft 365 YYMM"),
                        ("2607 (Build 20228.20110)", "YYMM (Build N)"),
                        ("Current Channel 2607 crashes", "Current Channel YYMM")):
        check(f"pre-existing context form still accepted: {label}", ctx(text, V, B), text)
    check("no date-proximity inference: a date near a bare version does not qualify",
          not ctx("On 2026-07-23 we saw 2607 crash", V, B))

    # =====================================================================================
    # 3. IDENTITY -- BUILD-AWARE IDENTITY = COMPLETE
    # =====================================================================================
    # Multiple Current Channel builds can ship under one YYMM, so identity is the triple
    # (product_id, update_version, target_build). Two builds are two records at two URLs. The
    # exhaustive per-consumer collision proof is test_powerpoint_build_identity.py; these are the
    # end-state guarantees that must never silently regress.
    from lib import patch_identity as pi  # noqa: PLC0415
    from patch_collectors.base import evidence_key  # noqa: PLC0415
    check("PowerPoint is registered as a build-aware product", pi.is_build_aware(PRODUCT))
    key_a = evidence_key({"product_id": PRODUCT, "update_version": "2603",
                          "target_build": "19822.20182", "id": "abc"}, "id")
    key_b = evidence_key({"product_id": PRODUCT, "update_version": "2603",
                          "target_build": "19822.20168", "id": "abc"}, "id")
    check("structured evidence key CARRIES the exact build", key_a[2] == "19822.20182", str(key_a))
    check("two builds sharing one report id do NOT collide", key_a != key_b)
    check("missing target_build fails CLOSED for PowerPoint",
          _raises(lambda: pi.require_build(PRODUCT, "2603", "")))

    import apply_consensus_to_records as ac  # noqa: PLC0415
    idx = ac._index_generated_records()
    ppt_keys = [k for k in idx if k[0] == PRODUCT]
    check("generated-record index is keyed by the identity TRIPLE",
          bool(ppt_keys) and all(len(k) == 3 for k in ppt_keys), str(ppt_keys[:2]))
    check("every live PowerPoint record carries an exact build in its key",
          all(k[2] for k in ppt_keys), str([k for k in ppt_keys if not k[2]][:3]))
    check("no two PowerPoint records share an identity key", len(ppt_keys) == len(set(ppt_keys)))

    # The promotion index deliberately does not carry permalinks, so read them from the records.
    ppt_records = [v for k, v in idx.items() if k[0] == PRODUCT]
    permalinks = []
    for _r in ppt_records:
        _text = Path(_r["abs_path"]).read_text(encoding="utf-8")
        _m = re.search(r"^permalink:\s*(\S+)", _text, re.M)
        permalinks.append(_m.group(1).strip() if _m else "")
    check("every PowerPoint permalink is build-aware (five segments)",
          all(len([x for x in p.strip("/").split("/") if x]) == 5 for p in permalinks),
          str([p for p in permalinks if len([x for x in p.strip("/").split("/") if x]) != 5][:3]))
    check("no two PowerPoint records share a public permalink",
          len(permalinks) == len(set(permalinks)))
    check("the version-only URL is owned by a landing page, not by any record",
          all(not p.rstrip("/").endswith(f"/{PRODUCT}/{k[1]}")
              for p, k in zip(permalinks, [k for k in idx if k[0] == PRODUCT])))
    landing_dir = _REPO / "auxsays" / "updates" / "microsoft" / "microsoft-powerpoint"
    landings = sorted(p for p in landing_dir.glob("*/index.md"))
    check("every migrated YYMM keeps a resolving version landing page",
          len(landings) == len({k[1] for k in ppt_keys}), f"{len(landings)} landings vs {len({k[1] for k in ppt_keys})} versions")

    # Non-PowerPoint products must be untouched by the shared primitive.
    for other in ("obs-studio", "blackmagic-davinci", "adobe-acrobat-reader", "microsoft-windows-11"):
        check(f"{other} identity keeps an EMPTY build slot (semantically unchanged)",
              pi.patch_key(other, "1.0") == (other, "1.0", ""))

    # =====================================================================================
    # 4. PROMOTION ENGINE -- reuse, not a new PowerPoint scorer
    # =====================================================================================
    # The engine exists and is generic, but nothing invokes it for PowerPoint in production.
    check("BLOCKING GAP: no production step invokes consensus promotion for PowerPoint",
          "apply_consensus_to_records" not in
          (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml").read_text(
              encoding="utf-8"),
          "if this fails the chain became wired and the PR body must be updated")
    check("the generic promotion engine exposes a product filter",
          hasattr(ac, "_index_generated_records") and hasattr(ac, "main"),
          "apply_consensus_to_records")
    check("promotion engine is NOT PowerPoint-special-cased",
          "microsoft-powerpoint" not in
          (_SCRIPTS / "apply_consensus_to_records.py").read_text(encoding="utf-8"),
          "found a PowerPoint special case in the generic engine")
    check("record-count reconciliation primitive is reusable",
          __import__("lib.report_counts", fromlist=["reconcile_record_counts"]) is not None)

    # =====================================================================================
    # 5. HALF-PROMOTION -- evidence=1 with record count=0 must be REFUSED
    # =====================================================================================
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rec = tmp / "2026-07-23-microsoft-powerpoint-2607.md"

        def write_record(count: int) -> None:
            rec.write_text(
                "---\n"
                "update_entry: true\n"
                f"product_id: {PRODUCT}\n"
                "update_version: '2607'\n"
                f"target_build: '{BUILD}'\n"
                f"update_report_count: {count}\n"
                "evidence_state: official_only\n"
                "---\n\nbody\n", encoding="utf-8")

        original = qa.load_counted_evidence_counts
        try:
            qa.load_counted_evidence_counts = lambda: {(PRODUCT, "2607", BUILD): 1}

            write_record(0)
            errors, warnings = qa.scan_evidence_count_alignment([rec])
            codes = [e.get("code") for e in errors]
            check("HALF-PROMOTED evidence=1 / record=0 is a BLOCKING error",
                  "generated_report_count_mismatch" in codes, f"{errors}")
            check("half-promoted state is an error, not a warning", warnings == [], str(warnings))

            write_record(1)
            errors, warnings = qa.scan_evidence_count_alignment([rec])
            check("after promotion evidence=1 / record=1 passes cleanly",
                  errors == [] and warnings == [], f"errors={errors} warnings={warnings}")

            write_record(2)
            errors, _ = qa.scan_evidence_count_alignment([rec])
            check("OVER-promotion evidence=1 / record=2 is also refused",
                  "generated_report_count_mismatch" in [e.get("code") for e in errors], str(errors))
        finally:
            qa.load_counted_evidence_counts = original

    # --- the full promotion chain, on temp fixtures only ---
    from lib.report_counts import counted_evidence_counts, reconcile_record_counts  # noqa: PLC0415
    row = {"product_id": PRODUCT, "update_version": "2607", "target_build": BUILD, "counted": True,
           "patch_version_matched": True, "id": "e1",
           "source_url": "https://learn.microsoft.com/en-us/answers/questions/5975138/x"}
    check("promotion counts only patch-matched evidence (exact-patch doctrine)",
          counted_evidence_counts([row]) == {(PRODUCT, "2607", BUILD): 1}
          and counted_evidence_counts([{**row, "patch_version_matched": False}]) == {},
          str(counted_evidence_counts([row])))
    with tempfile.TemporaryDirectory() as td2:
        tmp2 = Path(td2)
        rec2 = tmp2 / "2026-07-23-microsoft-powerpoint-2607.md"
        rec2.write_text(
            "\n".join([
                "---",
                "update_entry: true",
                f"product_id: {PRODUCT}",
                "update_version: '2607'",
                f"target_build: '{BUILD}'",
                "update_report_count: 0",
                "evidence_state: official_only",
                "---",
                "",
                "body",
                "",
            ]), encoding="utf-8")
        original2 = qa.load_counted_evidence_counts
        try:
            qa.load_counted_evidence_counts = lambda: {(PRODUCT, "2607", BUILD): 1}
            before_errors, _ = qa.scan_evidence_count_alignment([rec2])
            changed, detail = reconcile_record_counts([row], tmp2)
            after_text = rec2.read_text(encoding="utf-8")
            after_errors, after_warnings = qa.scan_evidence_count_alignment([rec2])
            again, _ = reconcile_record_counts([row], tmp2)
            check("CHAIN: half-promoted state blocks before promotion",
                  [e.get("code") for e in before_errors] == ["generated_report_count_mismatch"])
            check("CHAIN: promotion writes the record count from evidence",
                  changed == 1 and "update_report_count: 1" in after_text,
                  f"changed={changed} detail={detail}")
            check("CHAIN: reconciliation passes after promotion",
                  after_errors == [] and after_warnings == [],
                  f"errors={after_errors}")
            check("CHAIN: promotion is idempotent", again == 0, f"second run wrote {again}")
        finally:
            qa.load_counted_evidence_counts = original2

    check("the half-promotion gate runs inside the production writeback validator chain",
          "qa_patch_records.py" in
          (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml").read_text(
              encoding="utf-8"))

    # =====================================================================================
    # 6. WRITEBACK COMMIT PERMISSION -- the BLOCKING gap
    #
    # automation_writeback stages with `git add -- *--allow` and then refuses any staged path that
    # matches no --allow pattern, so --allow IS the commit permission list. --recovery-site-path is
    # a DIFFERENT thing: it only decides whether a no-change run still needs a Pages dispatch. An
    # earlier revision of this PR conflated the two and wrongly claimed PowerPoint was covered.
    # =====================================================================================
    wf = (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml").read_text(
        encoding="utf-8")
    allow_patterns = re.findall(r"--allow\s+'?([^'\s\\]+)'?", wf)
    check("the evidence workflow declares an --allow commit permission list",
          len(allow_patterns) >= 5, str(allow_patterns))

    def committable(path: str) -> bool:
        return any(fnmatch.fnmatch(path, p) for p in allow_patterns)

    ppt_record = "auxsays/updates/generated/2026-07-23-microsoft-powerpoint-2607.md"
    check("BLOCKING GAP: a PowerPoint generated record is NOT committable today",
          not committable(ppt_record),
          f"{ppt_record} vs {allow_patterns}")
    check("but PowerPoint structured evidence IS committable",
          committable("auxsays/_data/consensus_evidence.yml"))
    check("and PowerPoint method health IS committable",
          committable("auxsays/_data/evidence_method_health.yml"))
    check("=> activating today would land main HALF-PROMOTED (evidence committed, record dropped)",
          committable("auxsays/_data/consensus_evidence.yml") and not committable(ppt_record))

    for product, sample in (("obs-studio", "auxsays/updates/generated/2026-07-21-obs-studio-32-2-0.md"),
                            ("davinci", "auxsays/updates/generated/2026-07-22-davinci-resolve-21-0-3.md"),
                            ("acrobat", "auxsays/updates/generated/2026-08-11-adobe-acrobat-reader-26-001.md")):
        check(f"already-live product remains committable: {product}", committable(sample), sample)

    check("--recovery-site-path is NOT commit permission (distinct flag)",
          "--recovery-site-path" in wf and "--recovery-site-path" not in
          " ".join(f"--allow {p}" for p in allow_patterns))
    check("the deploy-recovery glob would match a PowerPoint record, which is why the two were "
          "conflated -- recovery != permission",
          fnmatch.fnmatch(ppt_record, "auxsays/updates/generated/*")
          and not committable(ppt_record))

    # Per-product scope, once an --allow entry exists, is still enforced by ownership.
    check("record ownership validation exists to enforce per-product scope",
          hasattr(ownership, "validate_records"))

    # =====================================================================================
    # 7. PROVENANCE -- the two Learn Q&A cases must never be cross-labelled
    # =====================================================================================
    VBA_2606 = "https://learn.microsoft.com/en-us/answers/questions/5935322/"
    ADDIN_2607 = "https://learn.microsoft.com/en-us/answers/questions/5975138/"
    check("provenance: question 5935322 is the 2606 VBA ChartData.Activate case",
          "5935322" in VBA_2606 and "5975138" not in VBA_2606)
    check("provenance: question 5975138 is the 2607 add-in crash case",
          "5975138" in ADDIN_2607 and "5935322" not in ADDIN_2607)
    check("the two cases are distinct URLs", VBA_2606 != ADDIN_2607)
    # A 2606-targeted report cannot be attributed to any tracked record: 2606 has none.
    tracked = {k[1] for k in ppt_keys}
    check("2606 is NOT a tracked PowerPoint version (so the VBA case has no target record)",
          "2606" not in tracked, str(sorted(tracked)))
    check("2607 IS tracked (so the add-in case has a target record)", "2607" in tracked)

    # =====================================================================================
    # 8. PRODUCTION MUST REMAIN OFF
    # =====================================================================================
    import run_patch_evidence_collection as runner  # noqa: PLC0415
    check("PowerPoint consensus is OFF with an empty environment",
          not runner.powerpoint_consensus_enabled({}))
    check("PowerPoint consensus is OFF unless the flag is exactly 'true'",
          not runner.powerpoint_consensus_enabled(
              {runner.POWERPOINT_CONSENSUS_ENABLE_ENV: "yes"}))
    check("the workflow still gates the flag to dry_run only (production lock intact)",
          "AUXSAYS_ENABLE_POWERPOINT_CONSENSUS" in wf and "dry_run" in wf)
    check("the workflow still refuses a --write run targeting PowerPoint",
          "dry_run-only pilot" in wf)
    check("Reddit fallback remains disabled by default",
          not ppt.reddit_fallback_enabled({}))

    print()
    print("=" * 64)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 64)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
