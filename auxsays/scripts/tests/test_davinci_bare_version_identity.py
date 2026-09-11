#!/usr/bin/env python3
"""A bare number is not a DaVinci version just because the page is about DaVinci.

THE DEFECT. DaVinci is the only product whose `update_version` can be a bare 1-2 digit number
("11", "20", "21"); every other product's version carries dots and identifies itself. Acceptance
used `base.exact_version_match`, which is numeric-boundary containment -- and SPACE and COLON are
legal neighbours of a genuine version mention. So these were all published as exact-patch evidence:

    "Posted by Nina Tailor on July 30, 2026 at 11:53 am"   -> DaVinci Resolve 11   (a timestamp)
    "Kouraib Abdmalek 15 Solve Coins"                      -> DaVinci Resolve 15   (a points counter)
    "davinci resolve started to use 20 gb of ram"          -> DaVinci Resolve 20   (RAM)

One Creative COW thread that states no version anywhere was counted simultaneously as evidence for
Resolve 11 (2014), 15 (2018) and 16 (2019) -- three records, three different decades, one page.

WHY NOT A BOUNDARY FIX. A colon follows a real version in "Resolve 20: crash on launch", and spaces
surround one in "on 20 the export fails". No character class can separate those from a clock time.
The missing constraint is contextual, so it lives in the DaVinci adapter -- the same shape as
`microsoft_powerpoint.version_in_context` and the OBS veto in `lib/target_outcome`, and the reason
`base.exact_version_match` stays containment and nothing more (asserted below).

WHY NOISE-REJECTION AND NOT REQUIRED-ADJACENCY. Measured on the live corpus: demanding a product
word beside the number drops 6-9 legitimate rows ("Crashing on Render After Updating to 21",
"Since the 21 Update", "21 on iPad loses sound") while STILL admitting the RAM row, whose distance
to "resolve" is only 23 characters. Rejecting demonstrable non-version shapes refuses every hostile
case and keeps every legitimate one.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_bare_version_identity.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

from lib.evidence_loss import is_audited_withdrawal  # noqa: E402
from lib.normalize import split_front_matter  # noqa: E402
from patch_collectors.base import exact_version_match  # noqa: E402
from patch_collectors.davinci import (  # noqa: E402
    bare_version_noise,
    davinci_version_match,
    version_aliases,
)

NEWLINE = chr(10)
_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

# ---------------------------------------------------------------------------
# IDENTITY PRECISION: the identities this repair is ABOUT, named once and asserted by name.
#
# This file used to assert `len(dv) == 234` and `count_of("*davinci-resolve-20.md") == 26` -- the
# population the day #82 landed. #132 made them floors so growth stopped failing them. Those pins
# were doing TWO jobs, badly, and they are now done separately and properly:
#
#   1. IDENTITY PRECISION -- that the false identities stay out and nothing true was refused. A
#      count is the wrong tool for this and never did it. #132 reasoned that the survivor check
#      covers the false rows, but it covers a row only while the STORED text still carries the
#      offending token, so exact_version_match fires and davinci_version_match refuses. The RAM
#      row's excerpt does. The two Creative COW rows' stored excerpts were truncated before the
#      timestamp and the coin counter, so the survivor check never covered those two at all --
#      reinserted verbatim, they passed #132's suite 56/56. And any row can lose its token on a
#      re-scrape; this file already records that page changing under us ("today the page contains
#      no `16` the matcher can find"). So the identities are named below and asserted directly.
#
#   2. EVIDENCE LOSS -- that accepted evidence does not vanish. The floors caught the crudest form
#      of this, for one product, by accident, and false-alarmed on every legitimate withdrawal
#      while doing it. That is a real job and the named identities here do NOT do it: an earlier
#      version of this comment claimed they were "what the count was standing in for", and review
#      proved otherwise -- delete 241 of 246 DaVinci rows, keep these five, regenerate the records
#      coherently, and this suite stayed 58/58. Loss is now guarded where it can actually be seen,
#      against the commit a change replaces: lib/evidence_loss.py, enforced in the automation
#      writeback and in ci-integrity, with its own suite (test_evidence_loss_guard.py).
#
# The precision checks range over every DaVinci row EXCEPT an audited withdrawal (`counted: false`
# with an exclusion_reason). That one exemption is required, not a relaxation: with deletion now
# refused, an audited tombstone is the only way left to remove a false identity, and checking every
# row would fail on it -- the absence check on all three tombstones, the survivor check on the RAM
# one -- so the two guards together would make a false identity impossible to remove at all.
#
# It is deliberately ONLY that exemption, not "every uncounted row". The tombstone is the one
# uncounted shape the repository guarantees; every withdrawn row it has ever held carries a reason.
# Any other uncounted shape -- a reason-less flip, a missing key, a stringly-typed flag -- is an
# anomaly, and some are one normalizing rewrite away from counting: `patch_version_matched: 'false'`
# (a string) reads as uncounted, but `bool('false')` is True, and both evidence normalizers apply
# bool(). In the scheduled OBS lane that rewrite is caught -- collector_ownership rejects it as an
# edit to an existing row and rolls the whole OBS write back, so nothing is published; instead
# every OBS run that adds a row fails, and the lane wedges. Any writer outside that transaction
# (a manual script, a future lane) would publish it. So those shapes still face the precision checks.
#
# (update_version, source_url), not `id`: the false identity is "this page is evidence for that
# version", which survives an id-slug regeneration. Keying on url ALONE would assert the wrong
# thing -- the same Creative COW thread still legitimately backs Resolve 16, which #82 deliberately
# did not remove ("a row is never deleted on absence of proof").
_RAM_ROW_URL = ("https://www.reddit.com/r/davinciresolve/comments/1svlm8w/"
                "davinci_resolve_crashing_from_nowhere_i_swear_bruh/")
_COW_THREAD_URL = "https://creativecow.net/forums/thread/failed-backup/"

# Removed by #82. Verified against ce43c853: it deleted exactly these three rows and added none.
PROVEN_FALSE_IDENTITIES = {
    ("20", _RAM_ROW_URL),      # "davinci resolve started to use 20 gb of ram"
    ("11", _COW_THREAD_URL),   # "Posted by ... on July 30, 2026 at 11:53 am"
    ("15", _COW_THREAD_URL),   # "Kouraib Abdmalek 15 Solve Coins"
}

# Kept by #82, and the reason it is noise-rejection rather than required-adjacency. The first three
# are the bare-but-genuine titles asserted against the matcher in [R]; an adjacency rule would have
# deleted them. The last two are unambiguous Resolve 20 mentions backing the record checked in [M].
# All five verified present in the store BEFORE ce43c853, AFTER it, and today, so their absence
# would mean the repair over-refused. That is a PRECISION statement about #82 -- it is not a loss
# guard, and five rows say nothing about the rest of the store (see above). All five are
# bare 1-2 digit majors, the only shape this predicate can get wrong, so they also keep the survivor
# check from passing on a store it failed to read -- the job #132's `len(bare) > 0` did, against
# named rows instead of a tally. Asserted as PRESENT, not accepted: an audited withdrawal of one of
# them is a deliberate later decision, not #82 over-refusing, and it must not fail here.
PRESERVED_IDENTITIES = {
    ("21", "https://www.reddit.com/r/davinciresolve/comments/1u0yjc0/"
           "crashing_on_render_after_updating_to_21/"),          # "Updating to 21"
    ("21", "https://www.reddit.com/r/davinciresolve/comments/1uzxa5d/"
           "i_cannot_open_my_spline_window_in_fusion/"),         # "Since the 21 Update"
    ("21", "https://www.reddit.com/r/davinciresolve/comments/1u10zc4/"
           "21_on_ipad_loses_sound_and_waveforms/"),             # bare title
    ("20", "https://www.reddit.com/r/davinciresolve/comments/1szgkt3/"
           "davinci_resolve_20_crashing_when_i_attempt_to/"),
    ("20", "https://www.reddit.com/r/davinciresolve/comments/1qndlqo/"
           "problems_with_davinci_resolve_20/"),
}


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("A bare number needs to BE a DaVinci version, not merely sit on a DaVinci page")
    print("=" * 78)

    # ---------------- hostile: the number is not a version ----------------
    print(NEWLINE + "[D] numbers that are not versions")
    hostile = [
        ("D1 timestamp", "Failed backup Posted by Nina Tailor on July 30, 2026 at 11:53 am", "11"),
        ("D2 points counter", "Mads Nybo 1316 COW Coins Kouraib Abdmalek 15 Solve Coins", "15"),
        ("D3 RAM", "davinci resolve started to use 20 gb of ram and crashing", "20"),
        ("D4 another product's version", "DaVinci Resolve crashes on my Windows 11 machine", "11"),
        ("D5 driver", "DaVinci Resolve crashing with nvidia driver 20 installed", "20"),
        ("D6 currency", "I paid $20 for Studio and Resolve still crashes", "20"),
        ("D7 quantity", "Resolve crashes when I drop 20 clips on the timeline", "20"),
        ("D8 ordinal", "see page 20 of the Resolve manual", "20"),
        ("D9 reply count", "Failed backup - DaVinci Resolve - Creative COW FORUMS 16 replies", "16"),
    ]
    for label, text, version in hostile:
        matched, _mv, _b = davinci_version_match(text, version)
        check(f"{label} is refused", not matched,
              f"accepted; noise={bare_version_noise(text, version)!r}")
    check("D the refusal names the offending token, so it is auditable",
          bare_version_noise("posted at 11:53 am", "11") != "",
          "no token reported")

    # Found by adversarial review: the first draft anchored the clock rule on the HOUR only, so
    # "11:53" caught 11 but "10:20" left 20 open -- and every live DaVinci major (16/19/20/21) is
    # a plausible minute. Worse, the same live Creative COW page carries "August 19, 2026" in a
    # sidebar headline, which would have manufactured a FOURTH false identity (Resolve 19) from
    # the very thread this change exists to clean up.
    print(NEWLINE + "[X] shapes review proved were still open")
    for label, text, version in (
        ("X clock minute field", "posted at 10:20 am", "20"),
        ("X clock seconds field", "at 11:53:16 today", "16"),
        ("X 'August 19, 2026' (the live sidebar)", "Blackmagic Design August 19, 2026 How Mavis", "19"),
        ("X ISO date", "on 2026-08-15 the render failed", "15"),
        ("X slash date", "posted 15/08/2026", "15"),
        ("X percentage", "GPU sits at 20% the whole render", "20"),
        ("X post number", "see reply #20 in this thread", "20"),
        ("X another NLE", "I moved from Final Cut Pro 11 to Resolve", "11"),
        ("X OS codename", "running macOS Sequoia 15 on an M3", "15"),
        ("X reversed points", "Coins: 15 earned this month", "15"),
    ):
        matched, _mv, _b = davinci_version_match(text, version)
        check(f"{label} is refused", not matched, f"accepted; noise={bare_version_noise(text, version)!r}")

    # ---------------- positive: real version syntax survives ----------------
    print(NEWLINE + "[P] version syntax that must keep working")
    positive = [
        ("P1 DaVinci Resolve N", "DaVinci Resolve 20 crashes on export", "20"),
        ("P2 Resolve N", "Resolve 20 keeps freezing on the colour page", "20"),
        ("P3 DaVinci N", "DaVinci 20 will not open my project", "20"),
        ("P4 Version N", "Version 20 crashes when I add a fusion node", "20"),
        ("P5 vN", "v20 has been unusable since I installed it", "20"),
        ("P6 dotted", "20.1 crashes on render", "20.1"),
        ("P7 dotted deep", "DaVinci Resolve Studio 20.3.1 build 6 crashes", "20.3.1"),
    ]
    for label, text, version in positive:
        matched, mv, _b = davinci_version_match(text, version)
        check(f"{label} still counts", matched, f"refused; matched={mv!r}")

    # Real corpus titles whose only mention is bare -- an adjacency rule would have deleted these.
    print(NEWLINE + "[R] real corpus mentions that are bare but genuine")
    for label, text in (
        ("R1 'Updating to 21'", "Crashing on Render After Updating to 21"),
        ("R2 'the 21 Update'", "Since the 21 Update I've been having issues with the Fusion Page"),
        ("R3 bare title", "21 on iPad loses sound and waveforms?"),
    ):
        check(f"{label} survives", davinci_version_match(text, "21")[0], "refused")

    # ---------------- the qualified form wins outright ----------------
    print(NEWLINE + "[Q] an unambiguous mention is never vetoed by noise elsewhere")
    mixed = "DaVinci Resolve 20 crashes on export. My machine has 20 gb of ram."
    matched, mv, basis = davinci_version_match(mixed, "20")
    check("Q a report naming 'DaVinci Resolve 20' counts even though '20 gb' also appears",
          matched, f"refused; matched={mv!r}")
    check("Q and it records WHICH form identified it", basis == "exact_version_alias" and "Resolve" in mv,
          f"{mv!r} / {basis}")
    check("Q while a bare-only mention beside noise is refused",
          not davinci_version_match("resolve started to use 20 gb of ram", "20")[0],
          "accepted")

    # ---------------- scope: dotted versions are untouched ----------------
    print(NEWLINE + "[S] dotted versions route through the shared matcher unchanged")
    for version in ("20.1", "20.3.1", "19.1.2", "21.0.3"):
        text = f"Resolve {version} crashes on render"
        check(f"S v{version} decision is bit-identical to base",
              davinci_version_match(text, version)
              == exact_version_match(text, version, version_aliases(version)),
              f"{davinci_version_match(text, version)} != "
              f"{exact_version_match(text, version, version_aliases(version))}")
    check("S the noise rule never examines a dotted version",
          bare_version_noise("20.1 gb of ram", "20.1") == "", "dotted version was examined")

    # ---------------- the shared matcher stays product-neutral ----------------
    print(NEWLINE + "[B] base.exact_version_match is not changed")
    base_src = (_REPO / "auxsays" / "scripts" / "patch_collectors" / "base.py").read_text(encoding="utf-8")
    # base.py may NAME davinci in a comment (it lists the products sharing evidence_key); what it
    # must not do is carry the product's version semantics.
    check("B base carries no DaVinci-specific version semantics",
          "bare_version_noise" not in base_src and "davinci_version_match" not in base_src,
          "base.py now knows about DaVinci's version rules")
    check("B base still matches a bare token on its own (containment, unchanged)",
          exact_version_match("posted at 11:53", "11", [])[0],
          "base behaviour changed -- other products depend on it")
    # Other products must be unaffected: none of them passes a bare 1-2 digit version.
    for product, version, text in (("acrobat", "19.012.20040", "Reader 19.012.20040 crashes"),
                                   ("premiere", "26.2", "Premiere Pro 26.2 crashes"),
                                   ("windows", "25H2", "Windows 11 25H2 fails")):
        check(f"B {product} version {version!r} still matches through base",
              exact_version_match(text, version, [])[0], "regressed")

    # ---------------- live corpus regressions ----------------
    print(NEWLINE + "[C] neighbouring products and records are unaffected")
    gen = _REPO / "auxsays" / "updates" / "generated"

    def count_of(pattern: str) -> int:
        for path in sorted(gen.glob(pattern)):
            fr, _b = split_front_matter(path.read_text(encoding="utf-8"))
            return int((yaml.safe_load(fr) or {}).get("update_report_count") or 0)
        return -1

    check("C Candidate 1 is still 2607 / 20228.20110 with one counted report",
          count_of("*powerpoint-2607-20228-20110*.md") == 1, str(count_of("*powerpoint-2607-20228-20110*.md")))
    # These two are CONTROLS: they exist to show the DaVinci migration did not disturb other
    # products. Both were pinned to a literal count of the day they were written (95 and 0) and
    # therefore broke on ordinary corpus growth -- OBS legitimately collected a 96th report and
    # Windows 25H2 rolled to a new cumulative update -- reporting a DaVinci regression where none
    # exists. Asserted as the properties they are named for instead.
    obs_now = count_of("*obs-studio-32-1-2*.md")
    check("C OBS 32.1.2 still carries its reports (the #79 exclusions stand)",
          obs_now >= 95, f"{obs_now} (floor 95; growth is legitimate, loss is not)")
    # "Converged" means the record's published count equals the canonical counted population for
    # its CURRENT target -- not that the number is any particular value.
    from lib.report_counts import (  # noqa: PLC0415
        counted_evidence_counts, windows_targets_from_front_matter,
    )
    _rows = (yaml.safe_load(Path(_REPO / "auxsays" / "_data" / "consensus_evidence.yml")
                            .read_text(encoding="utf-8")) or {}).get("evidence") or []
    _fronts = []
    for _p in gen.glob("*.md"):
        _fr, _b = split_front_matter(_p.read_text(encoding="utf-8"))
        _d = yaml.safe_load(_fr) or {}
        if isinstance(_d, dict):
            _fronts.append(_d)
    _canon = counted_evidence_counts(_rows, windows_targets=windows_targets_from_front_matter(_fronts))
    # Compared against THAT record's own patch identity. `count_of` returns the first matching
    # record's count, while the canonical side was read from ("microsoft-windows-11", "25H2", "") --
    # a key `counted_evidence_counts` never emits for a build-aware product, so it was structurally
    # 0 and the control only passed while the record side happened to be 0 as well. It failed the
    # moment 25H2 legitimately gained reports: the same vacuous-pin defect the two controls above
    # were already rewritten to avoid, one layer deeper.
    _win_path = next(iter(sorted(gen.glob("*windows-11-25h2*.md"))), None)
    _win_front = {}
    if _win_path is not None:
        _wfr, _wb = split_front_matter(_win_path.read_text(encoding="utf-8"))
        _win_front = yaml.safe_load(_wfr) or {}
    _win = _canon.get(("microsoft-windows-11",
                       str(_win_front.get("update_version") or ""),
                       str(_win_front.get("target_os_build") or "")), 0)
    check("C Windows 25H2 is still converged to its current cumulative update",
          count_of("*windows-11-25h2*.md") == _win,
          f"record={count_of('*windows-11-25h2*.md')} canonical={_win} "
          f"({_win_path.name if _win_path else 'no record'})")

    # ---------------- the migration outcome ----------------
    # One Creative COW thread that states no version was counted for Resolve 11, 15 AND 16. The
    # 11 and 15 rows are gone (a timestamp and a points counter); the 16 row is NOT removed --
    # today the page contains no `16` the matcher can find, so the predicate does not identify it,
    # and a row is never deleted on absence of proof.
    print(NEWLINE + "[M] the false identities are gone and the records converged")
    check("M Resolve 11 no longer counts a timestamp as a user report",
          count_of("*davinci-resolve-11.md") == 0, str(count_of("*davinci-resolve-11.md")))
    check("M Resolve 15 no longer counts a points counter",
          count_of("*davinci-resolve-15.md") == 0, str(count_of("*davinci-resolve-15.md")))
    # Resolve 20 is the one record of the three that legitimately KEEPS reports, so its outcome
    # cannot be a count the way the 11/15 zeroes can. `== 26` was the count the day the RAM row
    # was removed (27 - 1) and #132 made it `>= 26` -- correct about growth, but still a size, and
    # still silent about WHICH report went. What is asserted instead is precision, by name: the RAM
    # row is not projected, and the reports #82 preserved still are. It does NOT assert the record
    # kept all its other reports -- an earlier version of this comment said "the rest stayed", and
    # review cut this record from 26 reports to 2, keeping the preserved pair, with this suite
    # green. The record is regenerated from the store, so whether it lost reports is a question
    # about the store, and test_evidence_loss_guard.py answers it against the replaced commit.
    _r20 = sorted(gen.glob("*davinci-resolve-20.md"))
    _r20_front = {}
    if _r20:
        _r20_fr, _b = split_front_matter(_r20[0].read_text(encoding="utf-8"))
        _r20_front = yaml.safe_load(_r20_fr) or {}
    # The record must EXIST, or every membership test below is vacuously satisfied by an empty set.
    check("M the Resolve 20 record is present to be checked",
          bool(_r20) and bool(_r20_front.get("accepted_report_sources")),
          f"{len(_r20)} record(s) matched *davinci-resolve-20.md")
    _r20_urls = {str(s.get("source_url") or "")
                 for s in (_r20_front.get("accepted_report_sources") or [])}
    check("M Resolve 20 no longer projects the RAM row",
          _RAM_ROW_URL not in _r20_urls, "the RAM row is back in accepted_report_sources")
    _r20_keep = {u for v, u in PRESERVED_IDENTITIES if v == "20"}
    # A preserved report withdrawn since, the audited way, correctly leaves the projection; that is
    # a later deliberate decision, not #82 over-refusing, so it is not a failure here.
    _r20_withdrawn = {str(r.get("source_url") or "") for r in _rows
                      if r.get("product_id") == "blackmagic-davinci"
                      and str(r.get("update_version") or "") == "20" and is_audited_withdrawal(r)}
    check("M Resolve 20 still projects the reports the repair preserved",
          _r20_keep <= (_r20_urls | _r20_withdrawn),
          f"dropped without a withdrawal: {sorted(_r20_keep - _r20_urls - _r20_withdrawn)}")

    for pattern in ("*davinci-resolve-11.md", "*davinci-resolve-15.md"):
        for path in sorted(gen.glob(pattern)):
            fr, _b = split_front_matter(path.read_text(encoding="utf-8"))
            data = yaml.safe_load(fr) or {}
            name = path.name
            check(f"M {name} projects nothing it cannot support",
                  not data.get("accepted_report_sources") and not data.get("evidence_samples")
                  and "user report" not in str(data.get("quick_verdict") or "").lower(),
                  f"sources={len(data.get('accepted_report_sources') or [])} "
                  f"verdict={str(data.get('quick_verdict'))[:60]!r}")
            # 93 genuine zero-report DaVinci records carry no decision language; a record taken to
            # zero must match that shape rather than keep "WAIT" from when it had one report.
            check(f"M {name} carries no stale install verdict",
                  not data.get("update_decision_label") and not data.get("practical_recommendations"),
                  f"decision={data.get('update_decision_label')!r}")

    # IDENTITY PRECISION over the store. Whether evidence was LOST is not asked here -- see the note
    # on PROVEN_FALSE_IDENTITIES, and test_evidence_loss_guard.py, which owns that question.
    ev = yaml.safe_load((_REPO / "auxsays" / "_data" / "consensus_evidence.yml").read_text(encoding="utf-8")) or {}
    dv = [r for r in (ev.get("evidence") or []) if r.get("product_id") == "blackmagic-davinci"]
    # LIVE = every row except an audited withdrawal, by the same predicate the loss guard uses (one
    # definition). See the note on PROVEN_FALSE_IDENTITIES for why it is exactly that exemption.
    live = [r for r in dv if not is_audited_withdrawal(r)]
    present = {(str(r.get("update_version") or ""), str(r.get("source_url") or "")) for r in dv}
    live_ids = {(str(r.get("update_version") or ""), str(r.get("source_url") or "")) for r in live}
    # The repair did not under-reach, asserted by NAME, whatever the row's text says now. An audited
    # tombstone of a proven-false identity is the correct way to hold one -- and it also stops the
    # collector re-admitting it, since the append authority dedups against every stored row.
    check("M no proven false identity is live evidence (only an audited withdrawal may hold one)",
          not (live_ids & PROVEN_FALSE_IDENTITIES),
          f"live: {sorted(live_ids & PROVEN_FALSE_IDENTITIES)}")
    # The repair did not over-refuse. PRESENT, not counted: a later audited withdrawal of one of
    # these is a deliberate decision, not #82 overreaching. Also what keeps the survivor check below
    # from passing on a store this suite failed to read.
    check("M every identity the repair preserved is still in the store",
          PRESERVED_IDENTITIES <= present,
          f"missing: {sorted(PRESERVED_IDENTITIES - present)}")
    check("M no live DaVinci row is refused by the shipped predicate",
          not [r for r in live
               if exact_version_match(
                   " ".join(str(r.get(k) or "") for k in ("parent_title", "report_title",
                                                          "report_text_excerpt")),
                   str(r.get("update_version")), version_aliases(str(r.get("update_version"))))[0]
               and not davinci_version_match(
                   " ".join(str(r.get(k) or "") for k in ("parent_title", "report_title",
                                                          "report_text_excerpt")),
                   str(r.get("update_version")))[0]],
          "a live row would now be refused -- migration incomplete")

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
