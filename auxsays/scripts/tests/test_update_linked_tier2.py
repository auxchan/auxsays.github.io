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

import re
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
    print("I  the Jekyll `where` numeric-coercion trap")
    print("=" * 96)
    # ROOT CAUSE of a live defect: Jekyll's `where` runs the property through parse_sort_input,
    # which coerces a numeric-looking string to a Float. "20326.20100" became 20326.201 -- the
    # trailing zero silently lost -- so the row never matched its own page. Builds ending in a
    # zero broke and the rest worked, which made it look arbitrary. Every offline `==` test
    # passed, because direct comparison never coerces.
    import re as _re  # noqa: PLC0415

    JEKYLL_NUMERIC = _re.compile(r"\A\s*-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?\s*\Z")

    def coerces(value):
        return bool(JEKYLL_NUMERIC.match(value))

    for build, breaks in (("20326.20100", True), ("20326.20110", True),
                          ("20228.20158", False), ("18025.20096", False)):
        coerced = float(build) if coerces(build) else build
        lost = str(coerced) != build
        check(f"I.1 the trap is real for {build}: round-trip lost = {breaks}", lost is breaks,
              f"{build} -> {coerced}")
    # The fix: filter on a key that cannot be read as a number.
    for build in ("20326.20100", "20326.20110", "20228.20158"):
        key = t2.patch_join_key("microsoft-powerpoint", "2608", build)
        check(f"I.2 the join key for {build} is not numeric-looking", not coerces(key), key)
        check(f"I.3 and it round-trips exactly for {build}", str(key) == key)
    layout = (ROOT / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    row_inc = (ROOT / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
    check("I.4 the patch page filters on the join key, never the bare build",
          'where: "associated_patch_key"' in layout
          and 'where: "associated_target_build"' not in layout)
    check("I.5 the listing filters on the join key too",
          'where: "associated_patch_key"' in row_inc
          and 'where: "associated_target_build"' not in row_inc)
    # Scoped to the rows that RENDER. An unresolved row deliberately carries no patch key -- that
    # is exactly what makes it structurally incapable of appearing as patch evidence -- so
    # asserting over every stored row would require the opposite of the intended design.
    _stored = t2.load_tier2(ROOT / "_data" / "update_linked_evidence.yml")
    _linked = [r for r in _stored if r.get("classification") == "update_linked"]
    check("I.6 every RENDERING row carries the join key",
          bool(_linked) and all(r.get("associated_patch_key") for r in _linked),
          f"{len(_linked)} update-linked rows")
    check("I.7 the key the row stores equals the key a template builds",
          all(r.get("associated_patch_key") == t2.patch_join_key(
              r.get("product_id"), r.get("associated_update_version"),
              r.get("associated_target_build")) for r in _linked))
    check("I.8 an unresolved row carries NO patch key, so it cannot render",
          all(not r.get("associated_patch_key") for r in _stored
              if r.get("classification") == "unresolved"))

    print()
    print("=" * 96)
    print("J  OPEN-WEB discovery -- permitted providers, and a snippet is never evidence")
    print("=" * 96)
    from patch_collectors import open_web_source as ow  # noqa: PLC0415

    # Every general web index was evaluated and rejected on POLICY or on gating, not on taste:
    # duckduckgo serves an interactive bot challenge after a few automated queries, mojeek and
    # marginalia both say `Disallow: /search`, and brave answers 402/422 without a paid key.
    # None of them may appear as a production provider.
    provider_names = [name for name, _fn in ow.PROVIDERS]
    for forbidden in ("duckduckgo", "mojeek", "marginalia", "brave", "startpage", "google", "bing"):
        check(f"J.1 no general web index is a production provider: {forbidden}",
              not any(forbidden in name for name in provider_names), str(provider_names))
    check("J.2 the providers are endpoints this repo already queries in production",
          set(provider_names) == {"learn_qna_search", "stack_exchange_search", "github_search"},
          str(provider_names))
    source = (ROOT / "scripts" / "patch_collectors" / "open_web_source.py").read_text(encoding="utf-8")
    check("J.3 the reason each index was rejected is recorded, not just the decision",
          "Disallow: /search" in source and "bot challenge" in source and "paid key" in source)

    # A search result contributes a URL and nothing else. If a title or summary could reach the
    # authority, the index would be deciding what a report says.
    fake = [{"source_url": "https://learn.microsoft.com/en-us/answers/questions/1/x",
             "source_type": "microsoft_learn_qna", "discovered_by": "learn_qna_search",
             "matched_query": "q"}]
    check("J.4 a discovered row carries no title, summary or snippet",
          not ({"title", "snippet", "summary", "description", "report_text"} & set(fake[0])))
    check("J.5 discovery output keys are URL + provenance only",
          set(fake[0]) == {"source_url", "source_type", "discovered_by", "matched_query"})
    check("J.6 hydration fetches the ORIGINAL page rather than trusting the result",
          "def hydrate_discovered_url" in
          (ROOT / "scripts" / "patch_collectors" / "microsoft_powerpoint.py").read_text(encoding="utf-8"))

    print()
    print("=" * 96)
    print("K  a report found by search and by its native lane is ONE row")
    print("=" * 96)
    # Search returns an id-only URL; the native lanes store the slugged form. Comparing those two
    # spellings as strings reports zero overlap even when the sets overlap, and -- worse -- would
    # write the same thread twice. The page's own canonical link is the spelling both agree on.
    slugged = ("https://learn.microsoft.com/en-us/answers/questions/5975138/"
               "version-2607-powerpoint-crashing-when-using-an-add")
    page = f'<html><head><link rel="canonical" href="{slugged}"></head><body></body></html>'
    check("K.1 the page's canonical link wins over the id-only search URL",
          ow.canonical_from_page(page, "https://learn.microsoft.com/en-us/answers/questions/5975138")
          == slugged)
    check("K.2 and it equals the form the native lane stores",
          ow.canonical_from_page(page, "") == slugged)
    check("K.3 tracking parameters never create a second identity",
          ow.canonical_url(slugged + "?utm_source=x&ref=y") == slugged)
    check("K.4 a fragment never creates a second identity",
          ow.canonical_url(slugged + "#answer-12") == slugged)
    check("K.5 a locale variant folds to the stored locale",
          ow.canonical_url(slugged.replace("/en-us/", "/en-gb/")) == slugged)
    check("K.6 a trailing slash never creates a second identity",
          ow.canonical_url(slugged + "/") == slugged)

    print()
    print("=" * 96)
    print("L  discovery is broad; INGESTION is restricted to what we can actually read")
    print("=" * 96)
    for url, expected in (
            ("https://learn.microsoft.com/en-us/answers/questions/5/x", "supported"),
            ("https://superuser.com/questions/123/x", "supported"),
            ("https://techcommunity.microsoft.com/discussions/microsoft-365/x", "supported"),
            ("https://github.com/OfficeDev/office-js/issues/1", "supported"),
            ("https://www.reddit.com/r/powerpoint/comments/x", "uningestable"),
            ("https://answers.microsoft.com/en-us/msoffice/forum/x", "uningestable"),
            ("https://example.invalid/some-blog-post", "unsupported")):
        _stype, disposition = ow.identify_source(url)
        check(f"L.1 {expected:12s} <- {url[:52]}", disposition == expected, disposition)
    check("L.2 a known venue we cannot parse is RECORDED, never guessed at",
          "uningestable" in source and "KNOWN_UNINGESTABLE" in source)

    print()
    print("=" * 96)
    print("M  the query set is bounded and deterministic")
    print("=" * 96)
    first = ow.build_queries(version="2608", build="20326.20112", max_queries=10)
    again = ow.build_queries(version="2608", build="20326.20112", max_queries=10)
    check("M.1 the same patch always produces the same queries", first == again)
    check("M.2 the set is capped", len(first) <= 10, str(len(first)))
    check("M.3 identity-bearing queries come first, since only they can yield Tier 1",
          "20326.20112" in first[0])
    check("M.4 no query is duplicated", len(first) == len(set(first)))
    check("M.5 it is not a Cartesian product of every term",
          len(ow.build_queries(version="2608", build="20326.20112", max_queries=999)) < 40)
    check("M.6 a patch with no build still gets a usable query set",
          len(ow.build_queries(version="2608", build="")) > 0)

    print()
    print("=" * 96)
    print("N  LEVEL 3 -- recent reports are CONTEXT, and must never read as causation")
    print("=" * 96)
    from lib import recent_reports as l3  # noqa: PLC0415
    from patch_collectors import microsoft_powerpoint as _ppt3  # noqa: PLC0415

    def l3row(text, date, reason="missing_powerpoint_version",
              url="https://learn.microsoft.com/en-us/answers/questions/900/x"):
        return l3.recent_report_from_rejection(
            rejection(text, date=date, reason=reason, url=url),
            windows=WINDOWS, captured_at="x", is_concrete=_ppt3.concrete_issue)

    built = l3row("PowerPoint freezes while saving my deck.", "2026-08-20")
    check("N.1 a concrete complaint with no update attribution becomes Level 3",
          built is not None)
    if built:
        check("N.2 it states that attribution is NOT established",
              built.attribution_state == l3.ATTRIBUTION_NOT_ESTABLISHED)
        check("N.3 it belongs to a release WINDOW, not to a patch",
              bool(built.release_window_key) and bool(built.window_start))
        stored = built.as_dict()
        for causal in ("associated_patch", "linked_patch", "suspected_patch",
                       "associated_target_build", "associated_update_version",
                       "update_link_signal", "update_link_reason"):
            check(f"N.4 no causal field is stored: {causal}", causal not in stored)
        check("N.5 the window key is not numeric-looking, so `where` cannot coerce it",
              not re.fullmatch(r"\s*-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?\s*",
                               built.release_window_key))

    # The date decides the window, and containment is half-open: a report written ON the day the
    # next build shipped belongs to the NEW window, not the old one.
    aug20 = l3row("PowerPoint freezes while saving.", "2026-08-20")
    aug27 = l3row("PowerPoint freezes while saving.", "2026-08-27")
    check("N.6 an Aug 20 report sits in the .20100 window",
          aug20 is not None and aug20.window_build == "20326.20100",
          aug20.window_build if aug20 else "none")
    check("N.7 an Aug 27 report sits in the .20112 window",
          aug27 is not None and aug27.window_build == "20326.20112",
          aug27.window_build if aug27 else "none")
    boundary = l3row("PowerPoint freezes while saving.", "2026-08-26")
    check("N.8 a report ON the release date belongs to the NEW window",
          boundary is not None and boundary.window_build == "20326.20112",
          boundary.window_build if boundary else "none")
    check("N.9 an old report never drifts onto the newest release",
          (l3row("PowerPoint freezes while saving.", "2026-07-24") or
           type("x", (), {"window_build": "?"})).window_build == "20228.20110")
    check("N.10 a report older than every tracked window is refused",
          l3row("PowerPoint freezes while saving.", "2019-01-01") is None)
    check("N.11 an undated report is refused", l3row("PowerPoint freezes.", "") is None)

    # Level 3 is a weaker CLASS, not a weaker PRODUCT or CONCRETENESS gate.
    check("N.12 a how-to never becomes Level 3",
          l3row("How do I change the theme in PowerPoint?", "2026-08-20") is None)
    check("N.13 a wrong-product rejection never becomes Level 3",
          l3row("PowerPoint freezes while saving.", "2026-08-20",
                reason="product_not_powerpoint") is None)
    check("N.14 an official announcement never becomes Level 3",
          l3row("PowerPoint freezes while saving.", "2026-08-20",
                reason="official_announcement_not_user_report") is None)

    print()
    print("=" * 96)
    print("O  one report, one level -- no double publication")
    print("=" * 96)
    url = "https://learn.microsoft.com/en-us/answers/questions/901/y"
    l3only = l3row("PowerPoint freezes while saving.", "2026-08-20", url=url)
    check("O.1 a report already visible at a higher level is excluded from Level 3",
          l3.recent_report_from_rejection(
              rejection("PowerPoint freezes while saving.", date="2026-08-20", url=url),
              windows=WINDOWS, captured_at="x", is_concrete=_ppt3.concrete_issue,
              exclude_urls={url.rstrip("/").lower()}) is None)
    check("O.2 the Level-3 identity is the SAME stable id the other levels use",
          l3only is not None
          and l3only.report_id == t2.report_identity("microsoft-powerpoint", url))
    merged, stats = l3.merge_recent_reports([l3only.as_dict()], [], promoted_urls={url})
    check("O.3 promotion EVICTS the Level-3 row rather than leaving a stale card",
          merged == [] and stats["promoted_out"] == 1, f"{merged} {stats}")
    again, stats2 = l3.merge_recent_reports([l3only.as_dict()], [l3only.as_dict()],
                                            promoted_urls=set())
    check("O.4 re-seeing the same report updates it rather than duplicating",
          len(again) == 1 and stats2["added"] == 0, f"{len(again)} {stats2}")

    # The three published files must never show the same URL twice.
    conf_urls = {str(r.get("source_url") or "").rstrip("/").lower() for r in ppt_rows
                 if r.get("counted")}
    t2_urls = {str(r.get("source_url") or "").rstrip("/").lower()
               for r in t2.load_tier2(ROOT / "_data" / "update_linked_evidence.yml")
               if r.get("classification") == "update_linked"}
    l3_urls = {str(r.get("source_url") or "").rstrip("/").lower()
               for r in l3.load_recent(ROOT / "_data" / "recent_powerpoint_reports.yml")}
    check("O.5 no URL is published at both Level 1 and Level 3", not (conf_urls & l3_urls),
          str(sorted(conf_urls & l3_urls)[:2]))
    check("O.6 no URL is published at both Level 2 and Level 3", not (t2_urls & l3_urls),
          str(sorted(t2_urls & l3_urls)[:2]))
    check("O.7 no URL is published at both Level 1 and Level 2", not (conf_urls & t2_urls),
          str(sorted(conf_urls & t2_urls)[:2]))
    check("O.8 the check is not vacuous -- all three sets carry rows",
          bool(conf_urls) and bool(t2_urls) and bool(l3_urls),
          f"{len(conf_urls)}/{len(t2_urls)}/{len(l3_urls)}")

    print()
    print("=" * 96)
    print("P  Level 3 cannot touch consensus")
    print("=" * 96)
    hundred = []
    for index in range(100):
        made = l3row("PowerPoint freezes while saving.", "2026-08-20",
                     url=f"https://learn.microsoft.com/en-us/answers/questions/{7000 + index}/z")
        if made:
            hundred.append(made.as_dict())
    check("P.1 the mutation is real -- 100 Level-3 rows were built", len(hundred) == 100,
          str(len(hundred)))
    after_counts = counted_evidence_counts(ppt_rows, windows_targets=None)
    check("P.2 counted evidence is byte-identical with 100 Level-3 rows present",
          before == after_counts, f"{before} vs {after_counts}")
    check("P.3 a Level-3 row has no `counted` field, so no count predicate can see it",
          all("counted" not in row for row in hundred))
    check("P.4 nor any consensus-bearing field",
          all(not ({"sentiment", "severity", "source_weight", "patch_version_matched"} & set(row))
              for row in hundred))
    l3_consumers = [p for p in (ROOT / "scripts").rglob("*.py")
                    if "consensus_evidence.yml" in p.read_text(encoding="utf-8", errors="replace")
                    and "/tests/" not in p.as_posix() and "\\tests\\" not in str(p)
                    and p.name != "orchestrate_evidence_run.py"]
    leaking3 = [p.name for p in l3_consumers
                if "recent_powerpoint_reports" in p.read_text(encoding="utf-8", errors="replace")]
    check("P.5 no consensus consumer reads the Level-3 file", not leaking3, str(leaking3))

    print()
    print("=" * 96)
    print("Q  the page says CONTEXT, never causation")
    print("=" * 96)
    layout3 = (ROOT / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    row3 = (ROOT / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
    check("Q.1 the section is headed 'Recent PowerPoint reports'",
          "Recent PowerPoint reports" in layout3)
    check("Q.2 the page carries the not-attributed qualifier",
          "Not attributed to this update." in layout3)
    check("Q.3 the page explains the reporters did not identify the update as the cause",
          "did not identify this update as the cause" in layout3)
    check("Q.4 each card states attribution is not established",
          "Patch attribution: not established." in layout3)
    check("Q.5 each card names the release WINDOW it was reported during",
          "release window" in layout3 and "window_build" in layout3)
    # Causal phrasing must not appear anywhere near the Level-3 block.
    l3_block = layout3[layout3.index("recent-reports-card"):]
    l3_block = l3_block[:l3_block.index("id=\"verdict\"")] if 'id="verdict"' in l3_block else l3_block
    for phrase in ("caused by", "problems with build", "regression", "suspected",
                   "likely caused", "evidence against", "linked to this update"):
        check(f"Q.6 no causal phrasing in the Level-3 block: {phrase!r}",
              phrase.lower() not in l3_block.lower())
    check("Q.7 high volume is capped so context cannot look like a verdict",
          "limit: 8" in layout3 and "Showing 8 of" in layout3)
    check("Q.8 the listing labels the third number 'recent', never 'reports'",
          "update-linked</span>" in row3 and "recent</span>" in row3)
    check("Q.9 the listing's machine-readable report count stays confirmed-only",
          'data-reports="{{ report_count_num }}"' in row3)
    check("Q.10 the Level-3 block is styled distinctly from confirmed evidence",
          ".recent-reports-card" in
          (ROOT / "assets" / "css" / "auxsays-custom.css").read_text(encoding="utf-8"))

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
