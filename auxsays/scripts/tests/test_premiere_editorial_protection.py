#!/usr/bin/env python3
"""Premiere Pro 26.2 carries hand-authored consensus prose. Automation must not take it back.

WHAT HAPPENED. `davinci-updates.yml` once ran `apply_consensus_to_records.py --write-all` with no
product scope. On 2026-05-15, run `d0fd2b81` executed it and overwrote the editorial consensus block
on `2026-04-30-premiere-pro-26-2.md` -- 13 days after the last human edit (`e0a3d9ef`, 2026-05-02),
and no human has touched the file since. Of the 14 front-matter keys it changed, FOUR were editorial
judgment rather than machine state, and all four were restored verbatim from `d0fd2b81^`:

    consensus_report        "Manually reviewed Adobe Community reports naming Premiere Pro 26.2 or
                             26.2.0 Build 65 describe timeline crashes, UI slowdown, freezing, hangs,
                             and successful rollback to 26.0.x. That supports a wait/test-first
                             recommendation while keeping the consensus label Moderate and confidence
                             Low."
                        ->  "3 user reports found for Premiere Pro 26.2. Current reports mention ..."

    update_consensus_label  Moderate -> Negative

    evidence_state_label    Verified reports -> User reports found
    status_events[1].label  Verified reports -> User reports found

The first two move together: the restored sentence explicitly documents "keeping the consensus label
Moderate", so restoring the prose while leaving the label at Negative would publish a record that
contradicts itself.

The second two were the ENTIRE content of that last human edit. `e0a3d9ef` ("Update DR and Language
1") did exactly one thing: it changed "Pilot sample" to "Verified reports" in THREE places.
`d0fd2b81` overwrote two of the three and missed `evidence_status_note`, so the record shipped
`evidence_state_label: User reports found` directly above a note reading "Verified reports: this page
uses manually reviewed reports...". An earlier draft of this restoration classified those two as
current machine projections and left them; that was wrong on three independent grounds, since the
restored value is simultaneously the human's word, what `evidence_state_label_for(3)` returns today,
and what the undamaged note still says.

The counts were NOT restored. `update_report_count` went 7 -> 3, but 3 is what the structured
evidence corpus actually holds today; 7 was a human's manual tally from before that corpus existed.
Restoring it would republish stale data, which is the opposite of the point. The `status_events`
entry `d0fd2b81` APPENDED ("User report count updated to 3.") is a machine audit record and is kept.

WHAT THIS GUARD DOES. It does NOT freeze the article. Pinning the exact wording would make legitimate
future editing fail a test, which is the wrong incentive. Instead it detects the failure mode that
actually occurred: the editorial block being replaced by GENERATED BOILERPLATE, the record coming to
contradict itself, and Premiere acquiring automated consensus ownership it is not supposed to have.

SCOPE OF THE CLAIM. No currently-configured production path writes these fields. That is weaker than
"recurrence is impossible", deliberately: a scoped `--product-id adobe-premiere-pro --update-version
26.2 --write --confirm-write` reproduces the damage exactly and additionally rewrites quick_verdict.
The workflow scan below therefore keys on `--write`, not `--write-all`.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_premiere_editorial_protection.py
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

from lib.normalize import split_front_matter  # noqa: E402
from lib.report_counts import (  # noqa: E402
    CONSENSUS_PROMOTION_PRODUCTS,
    verdict_states_a_count,
)

PREMIERE = _REPO / "auxsays" / "updates" / "generated" / "2026-04-30-premiere-pro-26-2.md"
PRODUCT = "adobe-premiere-pro"
WORKFLOWS = sorted((_REPO / ".github" / "workflows").glob("*.yml"))

# The shapes the consensus writer actually emits, read out of apply_consensus_to_records.py:
#
#   :781  f"{count} user report{'s'} found for {product_label} {ver}."      -> consensus_report
#   :950  f"WAIT: {product_label} {ver} has {count} user reports found."    -> quick_verdict
#   :995  f"{decision_label}: {product_label} {ver} has {count} ... found." -> quick_verdict
#   :934  f"... is a beta build with {count} user reports found."           -> quick_verdict
#
# Two corrections over this guard's first draft. The `:934` variant says "with", not "has", so a
# pattern pinned to "has" missed one of the writer's own three summary shapes -- it sits behind a
# `pid == "blackmagic-davinci"` branch and so cannot fire for Premiere today, but the point of
# matching on shape is not to depend on that. And word-form counts cost nothing to tolerate.
_COUNT = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|no)"
GENERATED_REPORT_RE = re.compile(rf"^\s*{_COUNT}\s+user\s+reports?\s+found\s+for\b", re.I)
GENERATED_SUMMARY_RE = re.compile(rf"\b(?:has|with)\s+{_COUNT}\s+user\s+reports?\s+found\b", re.I)

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
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


def front(path: Path) -> dict:
    fr, _body = split_front_matter(path.read_text(encoding="utf-8"))
    return yaml.safe_load(fr) or {}


def promotion_scopes() -> set[str]:
    """Every product any workflow promotes, plus the sentinel UNSCOPED."""
    out: set[str] = set()
    for wf in WORKFLOWS:
        try:
            doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 - a malformed workflow is another test's problem
            continue
        for job in (doc.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                run = str(step.get("run") or "")
                # "--write", not "--write-all". Verified: `--product-id adobe-premiere-pro
                # --update-version 26.2 --write --confirm-write` reproduces the original damage
                # exactly -- label to Negative, consensus_report to the boilerplate -- and also
                # rewrites quick_verdict, which the historical incident did not. Gating on
                # "--write-all" missed the one command shape proven to do it. Every invocation in
                # the workflows today passes --write-all, which CONTAINS --write, so this widens
                # what the guard can catch without changing what it matches on the current tree.
                if "apply_consensus_to_records" not in run or "--write" not in run:
                    continue
                toks = run.replace("\\" + NEWLINE, " ").split()
                found = set()
                for i, tok in enumerate(toks):
                    if tok == "--product-id" and i + 1 < len(toks):
                        found.add(toks[i + 1].strip("'\""))
                    elif tok.startswith("--product-id="):
                        found.add(tok.split("=", 1)[1].strip("'\""))
                out |= found or {"UNSCOPED"}
    return out


def _counted_rows_for(product_id: str, version: str) -> int:
    """Counted rows the STORE holds for this patch, by the repo's own predicate."""
    from lib.report_counts import counted_evidence_counts  # noqa: PLC0415
    doc = yaml.safe_load((_REPO / "auxsays" / "_data" / "consensus_evidence.yml")
                         .read_text(encoding="utf-8")) or {}
    counts = counted_evidence_counts(doc.get("evidence") or [], windows_targets={})
    return int(counts.get((product_id, version, ""), 0))


def _collect_steps() -> list[dict]:
    """The collection lane's own steps, in order."""
    doc = yaml.safe_load((_REPO / ".github" / "workflows" / "obs-evidence-collection.yml")
                         .read_text(encoding="utf-8")) or {}
    return list(((doc.get("jobs") or {}).get("collect") or {}).get("steps") or [])


def run() -> int:
    print("=" * 78)
    print("Premiere Pro 26.2 editorial consensus is not automation's to write")
    print("=" * 78)

    check("P0 the record exists", PREMIERE.exists(), str(PREMIERE))
    if not PREMIERE.exists():
        print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
        return 1
    data = front(PREMIERE)

    # ---------- the failure mode that actually occurred ----------
    # WHAT CHANGED, AND WHY. The guard below used to assert that Premiere's editorial block is NOT
    # generated -- that nothing automated may write it. That protection has been deliberately ended:
    # keeping it meant Premiere's records could be corrected only by hand, and a record no automated
    # lane may touch is a record that stays wrong. `adobe-premiere-pro` now has a scoped promotion
    # step in the lane and is retraction-eligible, so `consensus_report`, `quick_verdict`,
    # `update_decision_body` and `practical_recommendations` are generated from the counted
    # population by the premiere branch of `_record_coherence_fields`.
    #
    # WHAT STILL MATTERS IS UNCHANGED. The 2026-05-15 damage was not caused by promotion existing;
    # it was caused by an UNSCOPED `--write-all` reaching every product at once. That is still
    # refused below, and so is any collector-stage write to an editorial field. What this suite now
    # guards is the boundary that survives: official identity is not promotion's to rewrite.
    print(NEWLINE + "[P1] the editorial block is generated, and says so honestly")
    report = str(data.get("consensus_report") or "")
    check("P1 consensus_report is present", bool(report.strip()), "empty")
    count = int(data.get("update_report_count") or 0)
    verdict = str(data.get("quick_verdict") or "")
    stated = re.search(r"(\d+)\s+user report", verdict)
    check("P1 a verdict that states a count states the PERSISTED one",
          not stated or int(stated.group(1)) == count,
          f"verdict says {stated.group(1) if stated else '-'}, count={count}")
    check("P1 the record does not claim more reports than the store holds",
          count == _counted_rows_for(PRODUCT, str(data.get("update_version") or "")),
          f"record={count} store={_counted_rows_for(PRODUCT, str(data.get('update_version') or ''))}")

    print(NEWLINE + "[P2] Premiere's automated ownership is SCOPED, and stops at official identity")
    scopes = promotion_scopes()
    check("P2 exactly one scoped workflow promotion names adobe-premiere-pro",
          PRODUCT in scopes, str(sorted(scopes)))
    check("P2 no production-reachable unscoped consensus write remains",
          "UNSCOPED" not in scopes, str(sorted(scopes)))
    check("P2 Premiere is retraction-eligible, because the lane can rebuild it",
          PRODUCT in CONSENSUS_PROMOTION_PRODUCTS, str(sorted(CONSENSUS_PROMOTION_PRODUCTS)))
    # The reason retraction is only safe WITH a promotion step: reconciliation deletes, and only a
    # scoped promotion restores. Asserted as the pair, so neither can be granted without the other.
    check("P2 retraction-eligibility and the promotion step move together",
          (PRODUCT in CONSENSUS_PROMOTION_PRODUCTS) == (PRODUCT in scopes))

    # OFFICIAL IDENTITY IS NOT PROMOTION'S TO WRITE. Driven through the real engine rather than
    # asserted from a field list: a key added to WRITEABLE_FIELDS later must fail this.
    import apply_consensus_to_records as _acr  # noqa: PLC0415
    proposals = {}
    for group in _acr.run_dry_run(evidence_path=_REPO / "auxsays" / "_data" / "consensus_evidence.yml",
                                  product_id_filter=PRODUCT, is_candidate_mode=False,
                                  records_index=_acr._index_generated_records(),
                                  write_requested=True):
        proposals.update(group.get("proposed_fields_if_written") or {})
    OFFICIAL = ("update_version", "update_published_at", "update_source_url", "official_sources",
                "official_patch_notes_body", "official_checksums_body", "permalink",
                "official_source_type", "update_product", "product_id")
    leaked = [f for f in OFFICIAL if f in proposals]
    check("P2 promotion proposes no official identity field", not leaked, str(leaked))
    check("P2 and it did propose SOMETHING, so the check is not vacuous",
          bool(proposals), "promotion proposed nothing at all")

    print(NEWLINE + "[P3] the collector stage cannot reach editorial fields")
    import apply_consensus_to_records as acr  # noqa: PLC0415
    owned = set(acr.COLLECTOR_WRITABLE_FIELDS)
    editorial = {"consensus_report", "update_consensus_label", "update_consensus_summary",
                 "quick_verdict", "update_decision_label", "update_decision_body",
                 "practical_recommendations"}
    check("P3 collectors own only the two freshness fields",
          owned == {"evidence_last_checked", "record_last_updated"}, str(sorted(owned)))
    check("P3 no editorial field is collector-writable",
          not (owned & editorial), str(sorted(owned & editorial)))

    print(NEWLINE + "[P4] the record stays internally consistent")
    # The restored sentence documents the label it was written against. If a future edit changes one
    # without the other the record contradicts itself -- which is exactly what the damage produced.
    label = str(data.get("update_consensus_label") or "")
    named = re.search(r"consensus label (\w+)", report, re.I)
    check("P4 if the prose names a consensus label, the field agrees",
          not named or named.group(1).lower() == label.lower(),
          f"prose says {named.group(1) if named else '-'!r}, field is {label!r}")
    # The counts were deliberately left as current machine state, so the prose must not assert one.
    # Only the GENERATED shape is banned. A human may legitimately cite a number in passing --
    # "Adobe Community shows 3 threads naming Build 65" -- and forbidding that would work against
    # this suite's own stated goal of keeping the article editable.
    check("P4 the prose is not a generated count summary",
          not GENERATED_SUMMARY_RE.search(report), report[:110])

    print(NEWLINE + "[P5] the evidence-state vocabulary still moves together")
    # `e0a3d9ef` -- the LAST human edit, "Update DR and Language 1" -- did exactly one thing: it
    # changed "Pilot sample" to "Verified reports" in THREE places (evidence_state_label, the
    # status_events entry, and evidence_status_note's leading phrase). `d0fd2b81` overwrote the
    # first two and left the third, so HEAD shipped `evidence_state_label: User reports found`
    # above a note reading "Verified reports: this page uses manually reviewed reports...".
    # Corroborating the restored value: evidence_state_label_for(3) also returns "Verified
    # reports", so the human's word and the machine's current derivation agree. That is NOT
    # asserted here -- pinning the label to the count would make a legitimate hand-edit of the
    # count fail a test. What is asserted is that the three places cannot silently disagree.
    state_label = str(data.get("evidence_state_label") or "").strip()
    note = str(data.get("evidence_status_note") or "").strip()
    check("P5 evidence_state_label matches evidence_status_note's leading vocabulary",
          bool(state_label) and note.lower().startswith(state_label.lower()),
          f"label {state_label!r} vs note {note[:60]!r}")
    # The human's own status event, identified by its note rather than its index. The entry
    # `d0fd2b81` APPENDED ("User report count updated to 3.") is a machine audit record and is
    # deliberately not covered -- it is allowed to say whatever the count did.
    human_events = [e for e in (data.get("status_events") or [])
                    if str((e or {}).get("note") or "").startswith("Initial AUXSAYS")]
    check("P5 the human status event carries that same vocabulary",
          bool(human_events)
          and all(str(e.get("label") or "").strip() == state_label for e in human_events),
          str([(e.get("label")) for e in human_events]))

    # There is deliberately NO "neighbouring records are unaffected" check here. An earlier draft
    # carried one over from another sprint: it pinned a PowerPoint record to
    # `update_report_count == 1`. That is a literal-state assertion about a DIFFERENT product's live
    # data, so PowerPoint automation legitimately accepting a second report would have failed this
    # Premiere suite. `test_powerpoint_write_path_safety.py` already fails on main for exactly that
    # reason. Blast radius is a property of a diff, not of the current tree; the sweep and
    # `git diff --stat` are what establish it.

    # ---------- P6: the withdrawals, and the state they produced ----------
    # Three rows were withdrawn with reasons. A withdrawal is counted:false PLUS a named reason with
    # the row KEPT (lib/evidence_loss), so nothing downstream has to guess whether a missing row was
    # withdrawn or lost. These assertions read the STORE, not a fixture.
    print(NEWLINE + "[P6] the withdrawn rows, and the records that follow from them")
    import yaml  # noqa: PLC0415
    from lib.evidence_loss import is_audited_withdrawal  # noqa: PLC0415
    store = yaml.safe_load((_REPO / "auxsays" / "_data" / "consensus_evidence.yml")
                           .read_text(encoding="utf-8")) or {}
    rows = [r for r in (store.get("evidence") or []) if r.get("product_id") == PRODUCT]
    withdrawn = [r for r in rows if r.get("counted") is False]
    check("P6 every non-counted Premiere row is an AUDITED withdrawal, never a bare flag",
          withdrawn and all(is_audited_withdrawal(r) for r in withdrawn),
          str([(str(r.get("id"))[:40], r.get("exclusion_reason")) for r in withdrawn
               if not is_audited_withdrawal(r)]))

    LISTING = "/t5/premiere-pro-discussions/bd-p/premiere-pro"
    listing_rows = [r for r in rows if LISTING in str(r.get("source_url") or "")]
    check("P6-H the board LISTING url is present in the store but counts for nothing",
          listing_rows and not any(r.get("counted") is True for r in listing_rows),
          str([(r.get("counted"), r.get("exclusion_reason")) for r in listing_rows]))
    check("P6-H and it was withdrawn for the reason the collector itself uses",
          all(str(r.get("exclusion_reason")) == "source_url_not_specific_report"
              for r in listing_rows), str({str(r.get("exclusion_reason")) for r in listing_rows}))

    # The row whose Adobe thread now returns "Page not found". A dead source is not a refused one.
    dead = [r for r in rows if str(r.get("exclusion_reason") or "") == "source_report_no_longer_resolves"]
    check("P6 the unresolvable report is withdrawn under its own distinct reason",
          len(dead) == 1, str([r.get("id") for r in dead]))
    check("P6 that reason is not reused for a transport refusal",
          all("block" not in str(r.get("exclusion_reason") or "")
              and "rate" not in str(r.get("exclusion_reason") or "") for r in dead))

    # I. WHAT SURVIVED, AS A PROPERTY RATHER THAN A SNAPSHOT. This block used to assert "exactly the
    # two live 26.2 bug reports survive" and "26.2.2 is empty". Both were true the day the
    # withdrawals landed and both became false the moment production legitimately acquired evidence
    # -- the Algolia chain persisted 22 rows on its first write-enabled run. A test that pins a
    # count pins a moment; what matters is that the withdrawn rows stay withdrawn and that whatever
    # IS counted is a specific, live Premiere report. Counts are an observation, not a target.
    counted = [r for r in rows if r.get("counted") is True]
    check("P6-I the withdrawn rows are not among the counted ones",
          not [r for r in counted if r.get("id") in {str(w.get("id")) for w in withdrawn}],
          str([r.get("id") for r in counted if r.get("id") in {str(w.get("id")) for w in withdrawn}]))
    check("P6-I every counted row names a tracked Premiere patch",
          counted and all(str(r.get("update_version")) in {"26.2", "26.2.2"} for r in counted),
          str(sorted({str(r.get("update_version")) for r in counted})))
    import patch_collectors.adobe_premiere as _ap  # noqa: PLC0415
    published = [str(s.get("source_url") or "") for s in (data.get("accepted_report_sources") or [])
                 if isinstance(s, dict)]
    check("P6-K every published source url is a SPECIFIC Adobe report, by the collector's own rule",
          published and all(_ap.adobe_report_url_is_specific(_ap.canonical_adobe_url(u))
                            for u in published), str(published))
    check("P6-K the published list is drawn from this record's own counted rows",
          set(published) <= {str(r.get("source_url")) for r in counted
                             if str(r.get("update_version")) == str(data.get("update_version"))},
          f"published-only={sorted(set(published) - {str(r.get('source_url')) for r in counted})}")

    # M/N. The relationship between a record and its population, whatever that population is.
    other = front(_REPO / "auxsays" / "updates" / "generated" / "2026-05-01-premiere-pro-26-2-2.md")
    for label, record in (("26.2", data), ("26.2.2", other)):
        version = str(record.get("update_version") or "")
        population = [r for r in counted if str(r.get("update_version")) == version]
        count = int(record.get("update_report_count") or 0)
        check(f"P6-M {label}'s count is its counted population, neither more nor less",
              count == len(population), f"record={count} store={len(population)}")
        if population:
            check(f"P6-M {label} publishes a summary and samples for a non-zero count",
                  bool(str(record.get("update_consensus_summary") or "").strip())
                  and bool(record.get("evidence_samples")),
                  f"summary={bool(record.get('update_consensus_summary'))} "
                  f"samples={len(record.get('evidence_samples') or [])}")
            check(f"P6-M {label}'s visible samples stay within the presentation cap",
                  len(record.get("evidence_samples") or []) <= 5,
                  str(len(record.get("evidence_samples") or [])))
        else:
            check(f"P6-N {label} retracted its projections rather than keeping them",
                  not (record.get("accepted_report_sources") or [])
                  and not (record.get("evidence_samples") or [])
                  and not str(record.get("update_consensus_summary") or "").strip(),
                  f"sources={len(record.get('accepted_report_sources') or [])}")
            check(f"P6-N {label} fell back to the official-only shape, not a half-empty one",
                  str(record.get("evidence_state")) == "official_only"
                  and str(record.get("update_consensus_label")) == "Insufficient data",
                  f"{record.get('evidence_state')!r} {record.get('update_consensus_label')!r}")
    check("P6 no record claims a theme frequency the counted population cannot support",
          not (data.get("complaint_themes") or []) or len(data.get("complaint_themes") or [])
          <= int(data.get("update_report_count") or 0),
          str(data.get("complaint_themes")))

    # R/S. The promotion step is scoped and positioned, like every other product's.
    steps = _collect_steps()
    prem_i = next((i for i, st in enumerate(steps)
                   if "apply_consensus_to_records" in str(st.get("run") or "")
                   and PRODUCT in str(st.get("run") or "")), -1)
    reconcile_i = next((i for i, st in enumerate(steps)
                        if "build_consensus_from_evidence" in str(st.get("run") or "")), -1)
    qa = [i for i, st in enumerate(steps) if "qa_patch_records" in str(st.get("run") or "")]
    check("P6-S the Premiere promotion runs after reconciliation", 0 <= reconcile_i < prem_i,
          f"reconcile={reconcile_i} premiere={prem_i}")
    check("P6-S nothing validates between reconciliation and it",
          not [i for i in qa if reconcile_i < i < prem_i], f"qa={qa} premiere={prem_i}")
    check("P6-S and QA still runs after it", any(i > prem_i for i in qa), str(qa))
    check("P6-R the step names exactly one product, so it cannot reach another",
          str(steps[prem_i].get("run") or "").count("--product-id") == 1
          and "--write-all" in str(steps[prem_i].get("run") or ""),
          str(steps[prem_i].get("run") or "")[:160])

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
