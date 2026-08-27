#!/usr/bin/env python3
"""A collector may write only fields whose truth is complete when that collector finishes.

An in-collector `apply_consensus_writeback` runs BEFORE `lib.report_counts.reconcile_record_counts`
and before the final consensus/coherence application. At that point it does not know the final
counted-evidence population -- `_filter_rows` and `counted_evidence_counts` apply different
predicates (live: Windows 25H2 is 9 vs 29, 26H1 is 1 vs 2) -- and reconciliation later rewrites the
NUMBERS without rewriting the prose derived from them. Two verified consequences if the collector
writes the full proposed field set:

  - it replaces human-authored editorial prose. premiere-pro-26-2's `quick_verdict`,
    `update_decision_body` and `practical_recommendations` came from a hand commit (95b68f36), not
    the engine, and its three `accepted_report_sources[].source_date` values would be blanked.
  - it publishes count-derived narrative from the smaller population, which reconciliation then
    leaves standing beside the larger number. `qa_patch_records` compares only the number, so
    nothing catches it.

The boundary is `apply_consensus_to_records.apply_collector_record_fields`, filtering through the
POSITIVE allow-list `COLLECTOR_WRITABLE_FIELDS`. Positive, not "everything except
PROTECTED|CONSENSUS_COHERENCE": a field added to `_proposed_record_fields` later must not become
collector-writable by default.

Every assertion here drives the REAL write path and inspects the REAL persisted file -- never a
stubbed `_apply_record_fields`, and never an intermediate dict. Stubbing that function is exactly
the hole that hid a defect in the previous sprint.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_collector_write_authority.py
"""
from __future__ import annotations

import importlib
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402

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


HUMAN_VERDICT = ("WAIT for production systems. Premiere Pro 26.2 includes useful workflow updates "
                 "and fixes, but early Adobe Community reports describe timeline crashes and "
                 "successful rollbacks to 26.0.1 or 26.0.2.")
HUMAN_RECS = ["Keep 26.0.1 or 26.0.2 available as a rollback target.",
              "Do not update mid-project."]
REAL_DATE = "2026 05 01T00:00:00Z"


def premiere_record(path: Path) -> Path:
    """A record shaped like the live premiere-pro-26-2: human prose plus nested source provenance."""
    data = {
        "layout": "aux-update", "update_entry": True,
        "product_id": "adobe-premiere-pro", "update_version": "26.2",
        "update_product": "Premiere Pro",
        "update_report_count": 3, "confirmed_patch_specific_report_count": 3,
        "quick_verdict": HUMAN_VERDICT,
        "update_decision_label": "WAIT for production systems",
        "update_decision_body": "Hand-written guidance naming 26.0.1/26.0.2 as rollback targets.",
        "practical_recommendations": list(HUMAN_RECS),
        "evidence_state_label": "User reports found",
        "consensus_report": "3 user reports found for Premiere Pro 26.2.",
        "evidence_last_checked": "2026-05-01T00:00:00Z",
        "record_last_updated": "2026-05-15T00:07:10.219622Z",
        # the real nested shape whose source_date the unbounded write blanked
        "accepted_report_sources": [
            {"source_name": "Adobe Community Bug Report", "source_url": "https://c/1",
             "source_date": REAL_DATE},
            {"source_name": "Adobe Community Bug Report", "source_url": "https://c/2",
             "source_date": REAL_DATE},
        ],
    }
    path.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\nbody\n",
                    encoding="utf-8")
    return path


def windows_record(path: Path, version: str, count: int, narrative: str) -> Path:
    data = {
        "layout": "aux-update", "update_entry": True,
        "product_id": "microsoft-windows-11", "update_version": version,
        "update_product": "Windows 11",
        "update_report_count": count, "confirmed_patch_specific_report_count": count,
        "consensus_report": narrative,
        "update_consensus_summary": narrative,
        "evidence_last_checked": "2026-08-01T00:00:00Z",
        "record_last_updated": "2026-08-01T00:00:00Z",
    }
    path.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\nbody\n",
                    encoding="utf-8")
    return path


def full_proposal(**overrides):
    """A proposal shaped like the real _proposed_record_fields output: every class of field."""
    fields = {
        # count-derived
        "update_report_count": 9, "confirmed_patch_specific_report_count": 9,
        "consensus_report": "9 user reports found.",
        "update_consensus_summary": "9 user reports found.",
        "consensus_report_count_label": "user reports found",
        "update_consensus_confidence": "Low", "update_consensus_label": "Negative",
        "evidence_state": "pilot_sample", "evidence_state_label": "Verified reports",
        "consensus_collection_status": "pilot_initial_sample", "intelligence_stage": "pilot",
        # row-projection (nested provenance)
        "accepted_report_sources": [{"source_name": "x", "source_url": "https://c/1",
                                     "source_date": ""}],
        "evidence_samples": [], "evidence_sample_visible_limit": 5,
        "evidence_source_limitations": ["Small sample size."],
        # editorial / coherence
        "quick_verdict": "WAIT: generated boilerplate.",
        "update_decision_label": "WAIT",
        "update_decision_body": "Generated body.",
        "practical_recommendations": ["Generic item."],
        "source_freshness_note": "",
        # collector-owned
        "evidence_last_checked": "2026-08-27T00:00:00Z",
        "record_last_updated": "2026-08-27T00:00:00Z",
        # append-only event carrying a count-derived note
        "status_events_append": {"at": "2026-08-27T00:00:00Z", "label": "User reports found",
                                 "note": "User report count updated to 9."},
    }
    fields.update(overrides)
    return fields


def front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1]) or {}


def apply(rec: Path, fields: dict):
    """Drive the real boundary, converting a raise into a reportable value.

    A mutant that removes the filter lets an unapproved field reach _apply_record_fields, which
    raises RuntimeError. That is a genuine failure signal, but an uncaught traceback hides which
    assertion broke -- so surface it as (None, exc) and let the checks report it."""
    try:
        return acr.apply_collector_record_fields(rec, fields), None
    except Exception as exc:  # noqa: BLE001 -- observing it is the point
        return None, exc


SITES = [
    ("patch_collectors.adobe_premiere", "premiere"),
    ("patch_collectors.davinci", "davinci"),
    ("patch_collectors.microsoft_windows", "windows"),
    ("patch_collectors.adobe_acrobat_community", "acrobat"),
    ("collect_obs_reports", "obs"),
]


def run() -> int:
    print("=" * 74)
    print("Collector write authority -- positive ownership, fail closed")
    print("=" * 74)

    # ---------- O1: the ownership primitive is positive ----------
    print("\n[O1] ownership is a positive allow-list, not a denylist")
    owned = acr.COLLECTOR_WRITABLE_FIELDS
    check("O1 COLLECTOR_WRITABLE_FIELDS exists and is immutable",
          isinstance(owned, frozenset) and owned, str(type(owned)))
    check("O1 it is far smaller than the proposed field set",
          len(owned) < 5, str(sorted(owned)))
    # A denylist would admit every field not explicitly protected. Prove we do not do that.
    not_protected = {k for k in full_proposal()
                     if k not in acr.PROTECTED_FIELDS and k not in acr.CONSENSUS_COHERENCE_FIELDS}
    check("O1 a denylist would have admitted far more than the allow-list does",
          len(not_protected) > len(owned) + 5,
          f"denylist would admit {len(not_protected)}, allow-list admits {len(owned)}")
    check("O1 no count-derived field is collector-owned",
          not (owned & {"update_report_count", "confirmed_patch_specific_report_count",
                        "consensus_report", "update_consensus_summary",
                        "update_consensus_confidence", "consensus_report_count_label",
                        "evidence_state", "evidence_state_label",
                        "consensus_collection_status", "intelligence_stage"}), str(sorted(owned)))
    check("O1 no editorial/coherence field is collector-owned",
          not (owned & set(acr.CONSENSUS_COHERENCE_FIELDS)), str(sorted(owned)))
    check("O1 no row-projection field is collector-owned",
          not (owned & {"accepted_report_sources", "evidence_samples",
                        "evidence_source_limitations"}), str(sorted(owned)))

    # ---------- O2 / section 19: unknown field fails closed ----------
    print("\n[O2] an unknown future field is NOT collector-writable")
    proposal = full_proposal(future_new_field="value")
    kept = acr.collector_owned_fields(proposal)
    check("O2 the unknown field is filtered out", "future_new_field" not in kept, str(sorted(kept)))
    check("O2 filtering does not raise", True)
    with tempfile.TemporaryDirectory() as td:
        rec = premiere_record(Path(td) / "r.md")
        _plan, exc = apply(rec, proposal)
        check("O2 the boundary did not raise", exc is None, repr(exc))
        check("O2 it is not persisted to the record", "future_new_field" not in front(rec),
              str(sorted(front(rec))))

    # ---------- O3 / section 13: Premiere editorial preservation ----------
    print("\n[O3] human-authored editorial content survives the collector write")
    with tempfile.TemporaryDirectory() as td:
        rec = premiere_record(Path(td) / "premiere.md")
        before = front(rec)
        _plan, exc = apply(rec, full_proposal())
        check("O3 the boundary did not raise", exc is None, repr(exc))
        after = front(rec)          # PERSISTED file, not an intermediate dict
        check("O3 quick_verdict is the human one", after["quick_verdict"] == HUMAN_VERDICT,
              str(after["quick_verdict"])[:90])
        check("O3 update_decision_label preserved",
              after["update_decision_label"] == before["update_decision_label"])
        check("O3 update_decision_body preserved",
              after["update_decision_body"] == before["update_decision_body"])
        check("O3 practical_recommendations preserved",
              after["practical_recommendations"] == HUMAN_RECS, str(after["practical_recommendations"]))
        check("O3 no generated boilerplate reached the file",
              "generated boilerplate" not in str(after["quick_verdict"]).lower())

        # ---------- O4 / section 20: provenance is not destructively blanked ----------
        print("\n[O4] a weaker/empty proposal cannot erase existing provenance")
        dates = [s.get("source_date") for s in after["accepted_report_sources"]]
        check("O4 nested source_date values survive", dates == [REAL_DATE, REAL_DATE], str(dates))
        check("O4 the source list itself is untouched",
              after["accepted_report_sources"] == before["accepted_report_sources"])
        check("O4 count-derived prose was not refreshed either",
              after["consensus_report"] == before["consensus_report"])

    # ---------- O5 / sections 14+15: Windows count/narrative contradiction ----------
    print("\n[O5] the collector cannot introduce count-inconsistent narrative")
    for version, collector_pop, reconciled in (("25H2", 9, 29), ("26H1", 1, 2)):
        with tempfile.TemporaryDirectory() as td:
            # the record as reconciliation will leave it: the LARGER count
            rec = windows_record(Path(td) / f"w{version}.md", version, reconciled,
                                 f"{reconciled} user reports found for Windows 11 {version}.")
            before = front(rec)
            _plan, exc = apply(
                rec, full_proposal(update_report_count=collector_pop,
                                   confirmed_patch_specific_report_count=collector_pop,
                                   consensus_report=f"{collector_pop} user reports found.",
                                   update_consensus_summary=f"{collector_pop} user reports found."))
            check(f"O5 {version}: the boundary did not raise", exc is None, repr(exc))
            after = front(rec)
            # NB "29 user reports" CONTAINS "9 user reports", so compare the LEADING count token.
            leading = str(after.get("consensus_report") or "").split(" ", 1)[0]
            check(f"O5 {version}: the narrative does not lead with the collector count "
                  f"{collector_pop}", leading != str(collector_pop), leading)
            check(f"O5 {version}: the reconciled count is not overwritten with {collector_pop}",
                  after.get("update_report_count") == reconciled, str(after.get("update_report_count")))
            check(f"O5 {version}: narrative and count still agree",
                  str(reconciled) in str(after.get("consensus_report")),
                  str(after.get("consensus_report")))
            check(f"O5 {version}: the pre-existing narrative is preserved, not rewritten",
                  after.get("consensus_report") == before.get("consensus_report"))

    # ---------- O6 / section 16: a legitimate collector update still works ----------
    print("\n[O6] a collector-owned change is still written")
    with tempfile.TemporaryDirectory() as td:
        rec = premiere_record(Path(td) / "r.md")
        raw_before = rec.read_text(encoding="utf-8")
        out, exc = apply(rec, full_proposal(evidence_last_checked="2026-09-09T00:00:00Z"))
        check("O6 the boundary did not raise", exc is None, repr(exc))
        plan = (out or {"write_plan": {"fields": {}}})["write_plan"]
        after = front(rec)
        check("O6 the record file changed", rec.read_text(encoding="utf-8") != raw_before)
        check("O6 evidence_last_checked was updated",
              after["evidence_last_checked"] == "2026-09-09T00:00:00Z",
              str(after["evidence_last_checked"]))
        check("O6 the write plan reports a substantive change", bool(plan["fields"]),
              str(plan["fields"]))
        check("O6 and it still did not touch editorial content",
              after["quick_verdict"] == HUMAN_VERDICT)

    # ---------- O7 / section 17: true no-op ----------
    print("\n[O7] a proposal of only non-owned fields writes nothing")
    with tempfile.TemporaryDirectory() as td:
        rec = premiere_record(Path(td) / "r.md")
        raw_before = rec.read_text(encoding="utf-8")
        # evidence_last_checked matches the record; only forbidden fields differ
        out, exc = apply(rec, full_proposal(evidence_last_checked="2026-05-01T00:00:00Z"))
        check("O7 the boundary did not raise", exc is None, repr(exc))
        plan = (out or {"write_plan": {"fields": {}}})["write_plan"]
        check("O7 the file is byte-identical", rec.read_text(encoding="utf-8") == raw_before)
        check("O7 the write plan is empty", not plan["fields"], str(plan["fields"]))

    # ---------- O8 / section 18: the OBS fallback stays eligible ----------
    print("\n[O8] the OBS fallback remains eligible when nothing collector-owned changed")
    obs = importlib.import_module("collect_obs_reports")
    with tempfile.TemporaryDirectory() as td:
        rec = premiere_record(Path(td) / "r.md")
        # NOT stubbing _apply_record_fields -- that omission hid a defect once already.
        out, exc = apply(rec, full_proposal(evidence_last_checked="2026-10-10T00:00:00Z"))
        check("O8 the boundary did not raise", exc is None, repr(exc))
        owned_change = bool((out or {"write_plan": {"fields": {}}})["write_plan"]["fields"])
        check("O8 a collector-owned change reports True", owned_change is True)
    with tempfile.TemporaryDirectory() as td:
        rec = premiere_record(Path(td) / "r.md")
        out2, _e2 = apply(rec, full_proposal(evidence_last_checked="2026-05-01T00:00:00Z"))
        coherence_only = bool((out2 or {"write_plan": {"fields": {}}})["write_plan"]["fields"])
        check("O8 a coherence-only proposal reports False -> fallback eligible",
              coherence_only is False)
    check("O8 the OBS fallback is still gated on `not record_updated`",
          "if not record_updated" in (_SCRIPTS / "collect_obs_reports.py").read_text(encoding="utf-8"))
    check("O8 update_obs_record still exists as the fallback writer",
          hasattr(obs, "update_obs_record"))

    # ---------- O9 / section 33: no bypass inside the repaired collector flow ----------
    print("\n[O9] no collector can reach the record around the boundary")
    bypass = []
    for module_name, label in SITES:
        rel = module_name.replace(".", "/") + ".py"
        text = (_SCRIPTS / rel).read_text(encoding="utf-8")
        code = "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("#"))
        if "_apply_record_fields(" in code:
            bypass.append(f"{label}: calls the raw record writer directly")
    check("O9 no collector calls the raw record writer", not bypass, str(bypass))
    # OBS is the one collector with a sanctioned SECOND writer: update_obs_record, its narrow count
    # fallback. It is allowed to exist, but it must stay narrow -- if it ever grew a coherence or
    # count-narrative field it would reopen the same hole from the other side.
    obs_src = (_SCRIPTS / "collect_obs_reports.py").read_text(encoding="utf-8")
    fallback = obs_src[obs_src.index("def update_obs_record"):]
    fallback = fallback[:fallback.index("\ndef ", 1)]
    leaked = sorted(f for f in ("consensus_report", "update_consensus_summary", "quick_verdict",
                                "update_decision_body", "update_decision_label",
                                "practical_recommendations", "evidence_samples",
                                "accepted_report_sources", "update_consensus_confidence")
                    if f in fallback)
    check("O9 the OBS fallback writes no coherence or narrative field", not leaked, str(leaked))
    # Pin the fallback's field set exactly. Under the boundary the collector write returns False in
    # the steady state, so the fallback becomes eligible again -- which is precisely what it did on
    # main, where that writeback returned False unconditionally. That is RESTORED behaviour, not a
    # regression. What must not happen is the fallback GROWING: it writes front matter directly and
    # so bypasses PROTECTED_FIELDS (it already latches legacy_report_count /
    # evidence_backfill_status that way -- pre-existing, carried as backlog). Pinning the set means a
    # future field cannot quietly join an ungated writer.
    import re as _re  # noqa: PLC0415

    fallback_fields = set(_re.findall(r'"([a-z_]+)":', fallback))
    NARROW = {"update_report_count", "confirmed_patch_specific_report_count",
              "evidence_last_checked", "record_last_updated", "evidence_scope",
              "legacy_report_count", "evidence_backfill_status"}
    check("O9 the OBS fallback writes only counts, timestamps and the one-way backfill latch",
          fallback_fields <= NARROW, str(sorted(fallback_fields - NARROW)))
    check("O9 the fallback still writes the count it is there to repair",
          {"update_report_count", "confirmed_patch_specific_report_count"} <= fallback_fields,
          str(sorted(fallback_fields)))
    for module_name, label in SITES:
        mod = importlib.import_module(module_name)
        check(f"O9 {label} imports the boundary, not the raw writer",
              hasattr(mod, "apply_collector_record_fields")
              or "apply_collector_record_fields" in (_SCRIPTS / (module_name.replace('.', '/') + '.py')
                                                     ).read_text(encoding="utf-8"))

    # ---------- O10: PowerPoint still has no collector record-write path ----------
    print("\n[O10] the build-aware product still has no collector record write")
    ppt = (_SCRIPTS / "patch_collectors" / "microsoft_powerpoint.py").read_text(encoding="utf-8")
    check("O10 microsoft_powerpoint defines no writeback",
          "apply_consensus_writeback" not in ppt and "_apply_record_fields" not in ppt)
    check("O10 nor the collector boundary", "apply_collector_record_fields" not in ppt)

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
