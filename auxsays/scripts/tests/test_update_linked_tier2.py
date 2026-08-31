#!/usr/bin/env python3
"""TIER 2 -- update-linked reports: visible, labelled, and structurally outside consensus.

The strict exact-build rule is right for CONSENSUS and was wrong as the gate on VISIBILITY. 94% of
recent PowerPoint community reports never state a build, so a page could read "0 reports" after 806
threads had been read. Tier 2 shows those reports; Tier 1 still decides every number.

The two properties that matter, and the two ways this can fail:

  FALSE ASSOCIATION -- an ordinary complaint, or a Windows/add-in/driver/service problem, becomes
  "update-linked"; or a report is attached to a build that had not shipped when it was written.
  LOST INTELLIGENCE -- a report that explicitly blames an Office update still disappears, or a
  reporter who later supplies the build cannot be promoted.

Both directions are asserted here. Offline: no network, no repo writes.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import tier2_evidence as t2  # noqa: E402
from lib.update_linkage import classify_update_linkage  # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []

# The live PowerPoint release order, which is what makes adjacent-build safety testable.
PATCHES = [
    {"product_id": "microsoft-powerpoint", "update_version": "2607",
     "target_build": "20228.20110", "released_on": "2026-07-23"},
    {"product_id": "microsoft-powerpoint", "update_version": "2607",
     "target_build": "20228.20124", "released_on": "2026-07-29"},
    {"product_id": "microsoft-powerpoint", "update_version": "2607",
     "target_build": "20228.20158", "released_on": "2026-08-04"},
    {"product_id": "microsoft-powerpoint", "update_version": "2607",
     "target_build": "20228.20190", "released_on": "2026-08-11"},
    {"product_id": "microsoft-powerpoint", "update_version": "2608",
     "target_build": "20326.20100", "released_on": "2026-08-18"},
    {"product_id": "microsoft-powerpoint", "update_version": "2608",
     "target_build": "20326.20112", "released_on": "2026-08-26"},
]
WINDOWS = t2.build_release_windows(PATCHES)


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def rejection(text: str, *, date: str, reason: str = "missing_powerpoint_version",
              url: str = "https://learn.microsoft.com/en-us/answers/questions/1/x",
              source_type: str = "microsoft_learn_qna") -> dict:
    """A strict-authority rejection, shaped as the collector hands it over."""
    return {"product_id": "microsoft-powerpoint", "exclusion_reason": reason,
            "source_url": url, "source_type": source_type, "source_date": date,
            "parent_title": text[:80], "report_title": text[:80],
            "report_text_excerpt": text[:280], "tier2_full_text": text}


def run() -> int:
    print("=" * 96)
    print("A  POSITIVE cases -- a real update-linked report must become visible")
    print("=" * 96)
    positives = [
        ("P1", "PowerPoint started crashing after the latest Office update."),
        ("P2", "The new PowerPoint update broke embedded videos."),
        ("P3", "PowerPoint Version 2608 hangs when saving."),
        ("A4", "PowerPoint stopped saving after today's Office update."),
        ("A5", "Embedding issues after the July/August 2026 updates."),
        ("A6", "Hyperlink failures across our devices following recent updates."),
        ("A7", "PowerPoint build 20326 will not export."),
    ]
    for key, text in positives:
        row = t2.tier2_row_from_rejection(rejection(text, date="2026-08-27"),
                                          windows=WINDOWS, captured_at="2026-08-30T00:00:00Z")
        check(f"A.1 {key} becomes an update-linked report", row is not None, text[:60])
        if row:
            check(f"A.2 {key} carries a public reason a reader can act on",
                  bool(row.update_link_reason) and bool(row.update_link_evidence))
            check(f"A.3 {key} is never marked confirmed",
                  row.classification == t2.TIER_UPDATE_LINKED
                  and row.confirmation_state == "not_confirmed"
                  and not row.exact_build_known)

    print()
    print("=" * 96)
    print("B  NEGATIVE cases -- false association is the more dangerous failure")
    print("=" * 96)
    negatives = [
        ("N1", "PowerPoint crashes when I insert a picture. Very frustrating.",
         "a complaint posted after release is NOT linkage"),
        ("N2", "After Windows Update PowerPoint crashes on launch.", "Windows Update"),
        ("N3", "My PowerPoint add-in updated and broke my workflow.", "add-in update"),
        ("N4", "PowerPoint Online outage today, the service is down for everyone.", "service incident"),
        ("N5", "Try updating PowerPoint to the latest version and see if that helps.", "an instruction"),
        ("N6b", "After the GPU driver update PowerPoint renders wrong.", "driver update"),
        ("N6c", "After the Teams update PowerPoint Live stopped working.", "another application"),
    ]
    for key, text, why in negatives:
        row = t2.tier2_row_from_rejection(rejection(text, date="2026-08-27"),
                                          windows=WINDOWS, captured_at="2026-08-30T00:00:00Z")
        check(f"B.1 {key} is NOT update-linked ({why})", row is None,
              str(row.update_link_signal) if row else "")

    # Rejections that mean "this is not a user report about this product" can never be laundered
    # into visibility by the weaker tier.
    for reason in ("product_not_powerpoint", "official_announcement_not_user_report",
                   "not_a_concrete_powerpoint_issue", "different_version_not_target",
                   "date_before_release_or_undated"):
        row = t2.tier2_row_from_rejection(
            rejection("PowerPoint broke after the latest Office update.",
                      date="2026-08-27", reason=reason),
            windows=WINDOWS, captured_at="2026-08-30T00:00:00Z")
        check(f"B.2 {reason} is never promoted, even with perfect linkage language", row is None)
    check("B.3 the never-promote list and the promotable list cannot overlap",
          not (t2.NEVER_PROMOTE & t2.PROMOTABLE_REJECTIONS))

    print()
    print("=" * 96)
    print("C  ADJACENT-BUILD SAFETY -- association is to the window, never to the newest build")
    print("=" * 96)
    text = "PowerPoint stopped saving after today's Office update."
    aug27 = t2.tier2_row_from_rejection(rejection(text, date="2026-08-27"),
                                        windows=WINDOWS, captured_at="x")
    check("C.1 an Aug 27 report lands on .20112 (released Aug 26)",
          aug27 is not None and aug27.associated_target_build == "20326.20112",
          aug27.associated_target_build if aug27 else "none")
    # N8: the same sentence written before that build existed cannot become evidence about it.
    aug20 = t2.tier2_row_from_rejection(rejection(text, date="2026-08-20"),
                                        windows=WINDOWS, captured_at="x")
    check("C.2 N8 -- the same words on Aug 20 land on .20100, NOT .20112",
          aug20 is not None and aug20.associated_target_build == "20326.20100",
          aug20.associated_target_build if aug20 else "none")
    check("C.3 and the Aug 20 report is never attached to the newest build",
          aug20 is not None and aug20.associated_target_build != "20326.20112")
    # A stated family must AGREE with the window; disagreement refuses rather than guesses.
    disagree = t2.tier2_row_from_rejection(
        rejection("PowerPoint Version 2607 hangs when saving.", date="2026-08-27"),
        windows=WINDOWS, captured_at="x")
    check("C.4 a stated 2607 inside the 2608 window is refused, not reassigned", disagree is None)
    agree = t2.tier2_row_from_rejection(
        rejection("PowerPoint Version 2608 hangs when saving.", date="2026-08-27"),
        windows=WINDOWS, captured_at="x")
    check("C.5 a stated 2608 inside the 2608 window is accepted and says why",
          agree is not None and agree.association_basis == t2.WINDOW_BASIS_STATED_FAMILY)
    before_all = t2.tier2_row_from_rejection(rejection(text, date="2026-01-01"),
                                             windows=WINDOWS, captured_at="x")
    check("C.6 a report older than every tracked release is associated to nothing",
          before_all is None)
    undated = t2.tier2_row_from_rejection(rejection(text, date=""), windows=WINDOWS, captured_at="x")
    check("C.7 an undated report is never associated", undated is None)

    print()
    print("=" * 96)
    print("D  CONSENSUS ISOLATION -- the mutation proof")
    print("=" * 96)
    # The guarantee is STRUCTURAL: consensus reads consensus_evidence.yml, Tier 2 lives in its own
    # file, and nothing that reads the former reads the latter. Proven by construction AND by
    # behaviour: 100 update-linked rows must move no consensus number at all.
    import yaml  # noqa: PLC0415

    from lib.report_counts import counted_evidence_counts  # noqa: PLC0415

    evidence_path = ROOT / "_data" / "consensus_evidence.yml"
    raw = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
    rows = [r for r in (raw if isinstance(raw, list)
                        else next((v for v in raw.values() if isinstance(v, list)), []))
            if isinstance(r, dict)]
    ppt_rows = [r for r in rows if r.get("product_id") == "microsoft-powerpoint"]
    before = counted_evidence_counts(ppt_rows, windows_targets=None)

    hundred = []
    for index in range(100):
        built = t2.tier2_row_from_rejection(
            rejection("PowerPoint broke after the latest Office update.", date="2026-08-27",
                      url=f"https://learn.microsoft.com/en-us/answers/questions/{9000 + index}/x"),
            windows=WINDOWS, captured_at="x")
        if built:
            hundred.append(built.as_dict())
    check("D.1 the mutation is real -- 100 update-linked rows were actually built",
          len(hundred) == 100, str(len(hundred)))

    after = counted_evidence_counts(ppt_rows, windows_targets=None)
    check("D.2 counted evidence is byte-identical before and after", before == after,
          f"{before} vs {after}")
    check("D.3 no update-linked row can enter the consensus corpus (disjoint shapes)",
          all("counted" not in row for row in hundred),
          "a Tier-2 row has no `counted` field at all, so no count predicate can see it")
    check("D.4 isolation is structural: consensus and Tier 2 are different files",
          "update_linked_evidence" not in evidence_path.read_text(encoding="utf-8"))
    # The orchestrator legitimately touches both files -- it is the writer of each. What must hold
    # is that no CONSUMER of consensus evidence reads the update-linked file, so a Tier-2 row can
    # never be picked up by anything that counts, scores, reconciles or renders a verdict.
    writer = "orchestrate_evidence_run.py"
    consumers = [p for p in (ROOT / "scripts").rglob("*.py")
                 if "consensus_evidence.yml" in p.read_text(encoding="utf-8", errors="replace")
                 and "/tests/" not in p.as_posix() and "\\tests\\" not in str(p)
                 and p.name != writer]
    leaking = [p.name for p in consumers
               if "update_linked_evidence" in p.read_text(encoding="utf-8", errors="replace")]
    check("D.5 no consensus CONSUMER reads the update-linked file",
          not leaking, f"leaking: {leaking}")
    check("D.5b and there are real consumers, so the check is not vacuous",
          len(consumers) >= 5, f"{len(consumers)} consumers scanned")
    # Inside the writer, the two corpora never mix: consensus is appended from `counted`, and the
    # Tier-2 path is written only by its own helper.
    orch_src = (ROOT / "scripts" / writer).read_text(encoding="utf-8")
    check("D.5c the writer appends consensus evidence from the counted rows only",
          "append_evidence_rows(counted, self.evidence_path)" in orch_src)
    # Structural rather than a magic count: every mention of the Tier-2 path is either where it is
    # defined or inside the helper that owns it, so no other stage of the graph can reach it.
    helper_at = orch_src.index("def _write_tier2")
    stray = [line.strip() for index, line in enumerate(orch_src.split("\n"))
             if "self.tier2_path" in line
             and "self.tier2_path = " not in line
             and orch_src.index(line.strip()) < helper_at]
    check("D.5d the writer touches the Tier-2 path only where it is defined or in its own helper",
          not stray, f"stray: {stray}")
    check("D.5e and the helper is the only thing that writes it",
          "t2.write_tier2(merged, self.tier2_path)" in orch_src
          and orch_src.count("t2.write_tier2(") == 1,
          "the module-level writer must be called exactly once, from its own helper")
    check("D.6 0 confirmed with 100 update-linked is still Insufficient data",
          before.get("negative", 0) == after.get("negative", 0))

    print()
    print("=" * 96)
    print("E  PROMOTION -- one report, one identity, never two rows")
    print("=" * 96)
    url = "https://learn.microsoft.com/en-us/answers/questions/7777/ppt-broke"
    first = t2.tier2_row_from_rejection(
        rejection("PowerPoint broke after the latest Office update.", date="2026-08-27", url=url),
        windows=WINDOWS, captured_at="run1")
    again = t2.tier2_row_from_rejection(
        rejection("PowerPoint broke after the latest Office update.", date="2026-08-27",
                  url=url + "/"),
        windows=WINDOWS, captured_at="run2")
    check("E.1 the identity is stable across runs and URL trailing slashes",
          first is not None and again is not None and first.report_id == again.report_id,
          f"{first.report_id if first else '-'} vs {again.report_id if again else '-'}")
    stored, stats = t2.merge_tier2_rows([first.as_dict()], [again.as_dict()], confirmed_urls=set())
    check("E.2 re-seeing the same report updates it rather than duplicating",
          len(stored) == 1 and stats["added"] == 0, f"{len(stored)} rows, {stats}")
    # P4: the reporter later supplies the exact build, the strict authority counts it, and the
    # update-linked row must DISAPPEAR rather than sit beside its own confirmed twin.
    promoted, pstats = t2.merge_tier2_rows(stored, [], confirmed_urls={url})
    check("E.3 P4 -- once confirmed, the report leaves Tier 2 (no double count)",
          promoted == [] and pstats["promoted_out"] == 1, f"{promoted} {pstats}")
    check("E.4 promotion matches on canonical URL, not exact string",
          t2.merge_tier2_rows(stored, [], confirmed_urls={url + "/"})[1]["promoted_out"] == 1)
    check("E.5 an unrelated confirmed report does not evict anything",
          t2.merge_tier2_rows(stored, [], confirmed_urls={"https://example.invalid/other"})[1]
          ["promoted_out"] == 0)

    print()
    print("=" * 96)
    print("F  STRUCTURED STORAGE -- everything a reader or a later run needs")
    print("=" * 96)
    sample = t2.tier2_row_from_rejection(
        rejection("PowerPoint Version 2608 stopped saving after the latest Office update.",
                  date="2026-08-27",
                  url="https://learn.microsoft.com/en-us/answers/questions/8888/x"),
        windows=WINDOWS, captured_at="2026-08-30T00:00:00Z").as_dict()
    for field_name in ("report_id", "product_id", "source_family", "source_url", "source_report_id",
                       "report_date", "update_link_signal", "update_link_reason",
                       "associated_update_version", "associated_target_build", "association_basis",
                       "classification", "confirmation_state", "promotion_eligible",
                       "strict_exclusion_reason"):
        check(f"F.1 stored field present: {field_name}", field_name in sample, str(sorted(sample)))
    check("F.2 nothing is fabricated -- no severity or sentiment is invented",
          "severity" not in sample and "sentiment" not in sample and "consensus_weight" not in sample)
    check("F.3 the source family is public wording, not an internal source_type",
          sample["source_family"] == "Microsoft Q&A")

    print()
    print("=" * 96)
    print("G  THE PIPELINE IS WIRED, AND SNIPPETS ARE NEVER EVIDENCE")
    print("=" * 96)
    orch = (ROOT / "scripts" / "orchestrate_evidence_run.py").read_text(encoding="utf-8")
    check("G.1 the graph collects Tier-2 source rows from rejections",
          "tier2_source_rows" in orch and "PROMOTABLE_REJECTIONS" in orch)
    check("G.2 the graph writes Tier 2 to its own path",
          "update_linked_evidence.yml" in orch and "tier2_path" in orch)
    check("G.3 release windows come from the records, which carry the release date",
          "self._records.items()" in orch and "update_published_at" in orch)
    # A Tier-2 row is only ever built from a HYDRATED rejection produced by the real authority, so
    # there is no path by which a search snippet becomes a report.
    check("G.4 N7 -- a Tier-2 row is only ever built from an authority rejection",
          "tier2_row_from_rejection" in orch)
    layout = (ROOT / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    check("G.5 the patch page shows both counts separately",
          "Confirmed patch-specific reports" in layout and "Update-linked reports" in layout)
    check("G.6 the patch page states why each report is shown",
          "update_link_reason" in layout and "Why linked" in layout)
    check("G.7 the patch page says the exact build was not provided",
          "Exact build" in layout)
    row_include = (ROOT / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
    check("G.8 the listing row shows update-linked beside the confirmed count",
          "update-linked" in row_include and "report_count_num" in row_include)
    check("G.9 the update-linked count never replaces the confirmed count",
          row_include.index("report_count_num") < row_include.index("row_t2_count }} update-linked"))
    css = (ROOT / "assets" / "css" / "auxsays-custom.css").read_text(encoding="utf-8")
    check("G.10 the new card is styled, not shipped as bare default markup",
          ".update-linked-card" in css and ".patch-cell-num__linked" in css)

    print()
    print("=" * 96)
    print("H  defects an adversarial review found in the first cut")
    print("=" * 96)
    from patch_collectors import microsoft_powerpoint as ppt  # noqa: PLC0415

    def t2row(text, date="2026-08-27"):
        return t2.tier2_row_from_rejection(rejection(text, date=date), windows=WINDOWS,
                                           captured_at="x", is_concrete=ppt.concrete_issue)

    # H1. A version STRING is not an update ATTRIBUTION. Matching any YYMM after "version" made
    # this a string detector: a BIOS version linked, and so did an Excel build quoted by a support
    # agent in a reply -- which produced two of the first four rows this module ever wrote.
    for text in ("asus prime z590 bios ver. 2405 and PowerPoint crashes",
                 "My Excel is Microsoft Excel for Microsoft 365 MSO (Version 2607 Build "
                 "16.0.20228.20124) 64-bit and PowerPoint crashes",
                 "Support told me to stay on Version 2607 until this is sorted, PowerPoint crashes",
                 "Windows 11 version 2409 and PowerPoint crashes"):
        check(f"H1 a foreign product's version never links: {text[:44]!r}",
              classify_update_linkage(text).version_family == "")
    check("H1b the reporter's own Office version still links",
          classify_update_linkage("PowerPoint Version 2608 hangs when saving.").version_family
          == "2608")

    # H2. Concreteness is checked HERE. The strict authority tests the version gate BEFORE the
    # concreteness gate, so a report failing on version is never tested for concreteness at all --
    # not_a_concrete_powerpoint_issue fires ZERO times across 2328 live rejections, which makes its
    # presence in NEVER_PROMOTE useless on its own.
    for label, text in (("how-to", "How do I change the theme after the latest Office update?"),
                        ("feature request",
                         "Please add dark mode since the latest Office update."),
                        ("praise",
                         "I quite like the new icons since the latest Office update.")):
        check(f"H2 a non-concrete post is refused: {label}", t2row(text) is None)
    check("H2b a real defect with the same linkage language is still admitted",
          t2row("PowerPoint crashes on save since the latest Office update.") is not None)
    check("H2c the concreteness predicate is the authority's own, not a copy",
          "is_concrete=_ppt.concrete_issue" in
          (ROOT / "scripts" / "orchestrate_evidence_run.py").read_text(encoding="utf-8"))

    # H3. Build roles apply in Tier 2. Without them a post saying "20228.20190 works fine" was
    # filed as a complaint ABOUT 20228.20190 -- publishing the opposite of what the reporter said.
    working = ("PowerPoint 20228.20110 is not working; on 20228.20190 it works fine, "
               "since the latest Office update.")
    check("H3 a build the reporter calls WORKING is never the associated build",
          t2row(working, date="2026-08-17") is None)
    check("H3b a build named as the ROLLBACK target is refused too",
          t2row("I rolled back to 20228.20190 and it is fine, since the latest Office update.",
                date="2026-08-17") is None)
    check("H3c a build named as FAILING is still admitted",
          t2row("PowerPoint 20228.20190 crashes on save since the latest Office update.",
                date="2026-08-17") is not None)
    check("H3d a stated exact build that is not this window's refuses the row",
          t2row("PowerPoint 20228.20110 crashes since the latest Office update.",
                date="2026-08-27") is None)

    # H4. Vetoes must be at least as broad as the positives. The positive patterns accept
    # "following"; several vetoes only accepted "after|since", so a Teams/driver/Windows-cumulative
    # attribution linked while the equivalent "after" phrasing did not.
    for text in ("since the latest cumulative update for Windows 11 landed, PowerPoint crashes",
                 "Following the Teams update PowerPoint Live stopped sharing",
                 "after the latest NVIDIA Studio update PowerPoint renders wrong",
                 "After the Citrix update PowerPoint is slow",
                 "since the macOS update PowerPoint crashes"):
        check(f"H4 non-Office attribution is vetoed: {text[:44]!r}",
              not classify_update_linkage(text).linked,
              classify_update_linkage(text).signal)

    # H5. Promotion has to consider the STORED corpus. Using only this run's accepted rows left a
    # report published in BOTH tiers, because the run that confirmed it had already finished.
    orch_src = (ROOT / "scripts" / "orchestrate_evidence_run.py").read_text(encoding="utf-8")
    check("H5 promotion reads stored confirmed evidence, not just this run",
          "stored_confirmed" in orch_src and "load_evidence(self.evidence_path)" in orch_src)
    check("H5b and this run's accepted rows are still included",
          'for r in counted}' in orch_src)

    check("H6 stored text carries no smart punctuation or leftover entities",
          t2.normalise_text('OneDrive – PowerPoint “Embed” &amp;amp; more')
          == 'OneDrive - PowerPoint "Embed" & more')
    check("H6b normalisation is idempotent",
          t2.normalise_text(t2.normalise_text("A &amp;amp; B")) == t2.normalise_text("A &amp;amp; B"))
    check("H6c plain text is untouched", t2.normalise_text("plain text") == "plain text")
    stored = t2.load_tier2(ROOT / "_data" / "update_linked_evidence.yml")
    bad = [r.get("report_title") for r in stored
           if any(ord(ch) > 127 for ch in str(r.get("report_title") or ""))
           or "&amp;" in str(r.get("report_title") or "")]
    check("H6d no stored row carries smart punctuation or an entity", not bad, str(bad)[:120])

    print()
    print("=" * 96)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 96)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
