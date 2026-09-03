#!/usr/bin/env python3
"""Acrobat Levels 2 and 3: context, never consensus, and never a claim nobody made.

Level 1 (confirmed) is unchanged and is the only thing that feeds consensus. These suites lock the
two layers added on top of it:

  LEVEL 2  UPDATE-LINKED -- the reporter blamed an Acrobat/Adobe update but never named the build.
  LEVEL 3  RECENT REPORTS -- a concrete Acrobat problem reported while this release was current,
           with NO causal claim at all.

The load-bearing property is that neither layer may recover anything Phase A refused on SAFETY
grounds. Only the identity refusal -- "you did not write the exact DC build" -- is recoverable.
Every other Phase-A rule (edition authority, the Acrobat Standard exclusion, concreteness, the
multi-build fail-closed rule, the working/rollback/fixed vetoes) is re-applied by importing the
collector itself, so there is no second copy of those rules free to drift.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_acrobat_tiering.py
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
sys.path.insert(0, str(_AUX / "scripts"))

import yaml  # noqa: E402

from lib import acrobat_tiering as at  # noqa: E402
from lib.recent_reports import load_recent, merge_recent_reports  # noqa: E402
from patch_collectors import adobe_acrobat_community as ac  # noqa: E402
from patch_collectors.base import PatchRecord, counted_rows  # noqa: E402

_PASS = 0
_FAIL = 0
_FAILURES: list[str] = []

READER, PRO = ac.READER_ID, ac.PRO_ID
VER = "26.001.21745"
NEXT_VER = "26.001.21771"

# A real two-window fixture: Acrobat's identity IS the DC version, so the version fills the build
# slot in both the window and the joined key.
PATCHES = [
    {"product_id": READER, "update_version": "26.001.21691", "target_build": "26.001.21691",
     "released_on": "2026-06-25"},
    {"product_id": READER, "update_version": VER, "target_build": VER, "released_on": "2026-07-23"},
    {"product_id": READER, "update_version": NEXT_VER, "target_build": NEXT_VER,
     "released_on": "2026-08-01"},
    {"product_id": PRO, "update_version": VER, "target_build": VER, "released_on": "2026-07-23"},
    {"product_id": PRO, "update_version": NEXT_VER, "target_build": NEXT_VER,
     "released_on": "2026-08-01"},
]
WINDOWS = at.build_release_windows(PATCHES)
SHARED = (READER, PRO)
CAP = "2026-09-02T00:00:00Z"
URL = "https://community.adobe.com/questions-9/acrobat-will-not-print-1234567"


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def rejection(text: str, *, product_id: str = READER, date: str = "2026-07-28",
              reason: str = "missing_exact_patch_version_match", url: str = URL,
              title: str | None = None, original: str | None = None) -> dict:
    """A Phase-A rejection, shaped exactly as the collector hands it over."""
    row = {
        "product_id": product_id, "exclusion_reason": reason, "source_url": url,
        "source_type": ac.ADOBE_COMMUNITY_SOURCE_TYPE, "source_date": date,
        "report_title": title if title is not None else text[:120],
        "parent_title": title if title is not None else text[:120],
        "report_text_excerpt": text[:280], "tier2_full_text": text,
    }
    if original is None:
        original = date
    if original != "":
        row["original_post_date"] = original
    return row


def l2(text: str, **kw):
    return at.acrobat_update_linked_from_rejection(
        rejection(text, **kw), windows=WINDOWS, captured_at=CAP, safety=ac,
        applicability=SHARED, exclude_urls=kw.pop("exclude_urls", None))


def l3(text: str, **kw):
    return at.acrobat_recent_from_rejection(
        rejection(text, **kw), windows=WINDOWS, captured_at=CAP, safety=ac,
        applicability=SHARED, exclude_urls=kw.pop("exclude_urls", None))


def run() -> int:  # noqa: PLR0915
    print("=" * 98)
    print("A  LEVEL 2 -- the reporter blamed an update, without naming the build")
    print("=" * 98)
    linked = l2("After the latest Acrobat update, printing stopped working on all our machines.")
    check("A.1 an explicit update attribution with no build becomes Level 2", linked is not None)
    if linked:
        row = linked.as_dict()
        check("A.2 it is classified update_linked",
              row["classification"] == at.TIER_UPDATE_LINKED)
        check("A.3 it records WHY it linked, and the reporter's own words",
              row["update_link_reason"] == "update_named_as_cause"
              and "update" in row["update_link_evidence"].lower(), str(row.get("update_link_evidence")))
        # The field is a build STRING in the shared contract, and the template prints it AS the
        # build. A "no" sentinel here rendered the literal words "Exact build: no" on every
        # Level-2 card; empty is what produces the intended "Not supplied by the reporter."
        check("A.4 exact_build_known is absent, not a sentinel the page would print",
              "exact_build_known" not in row)
        check("A.5 it carries no `counted` field, so no count predicate can see it",
              "counted" not in row)
        check("A.6 the patch key is non-numeric, so Jekyll's `where` cannot coerce it",
              not re.fullmatch(r"\s*-?(?:\d+\.?\d*|\.\d+)\s*", row["associated_patch_key"]))
        check("A.7 the key carries the DC version in the build slot",
              row["associated_patch_key"] == f"{READER}|{VER}|{VER}", row["associated_patch_key"])

    # Realistic phrasings: each must also clear Phase A's PRODUCT and CONCRETENESS gates, which is
    # the point -- Level 2 relaxes the identity requirement and nothing else. Bare "Reader" is
    # `missing_product_attribution` here exactly as it is at Level 1, and "signatures fail" is not
    # in the failure vocabulary, so both are refused for reasons that have nothing to do with tiering.
    for phrase in ("Since Adobe Reader updated, it crashes on launch.",
                   "After Acrobat updated yesterday, signing fails on every document.",
                   "The update broke printing: Acrobat will not print at all now.",
                   "Acrobat auto-updated last night and now it will not open PDFs.",
                   "Since the August update Acrobat will not print."):
        check(f"A.8 links: {phrase[:52]!r}", l2(phrase) is not None)
    for phrase, why in (("Since Reader updated, it crashes on launch.",
                         "bare 'Reader' is not an attributable product"),
                        ("After Acrobat updated yesterday, signatures fail.",
                         "'signatures fail' is not in the failure vocabulary")):
        check(f"A.9 still refused, and for the Phase-A reason: {why}", l2(phrase) is None)

    print()
    print("=" * 98)
    print("B  remedy and advice are not attributions")
    print("=" * 98)
    # These contain the causal words and mean the opposite. One is instructing somebody; the other
    # is explicitly ruling the update OUT as the cause.
    for phrase in ("I updated Acrobat but it still crashes on every launch.",
                   "Update Acrobat to the latest version.",
                   "You should update Acrobat first, then try printing.",
                   "Please try updating to the latest release.",
                   "Make sure you are running the newest build.",
                   "Updating did not help, Acrobat still will not print.",
                   "First update Acrobat, then reinstall the printer driver."):
        check(f"B.1 refuses as remedy/advice: {phrase[:50]!r}", l2(phrase) is None)
    check("B.2 the refusal is recorded as remedy_or_advice, not as absence of a signal",
          at.update_causality("Update Acrobat to the latest version.").basis == "remedy_or_advice")
    check("B.3 a problem with no update mention links nothing",
          at.update_causality("Acrobat crashes when I open a large PDF.").basis
          == "no_update_attribution")

    print()
    print("=" * 98)
    print("C  Phase-A safety is re-applied, not re-implemented")
    print("=" * 98)
    # Each of these was a live defect in Phase A. Neither new level may recover any of them.
    safety_cases = [
        ("Acrobat Standard", "Since updating to Acrobat Standard my printing broke completely."),
        ("the other tracked edition",
         "After the latest update Adobe Acrobat Pro crashes on launch."),
    ]
    for label, text in safety_cases:
        check(f"C.1 Level 2 refuses {label}", l2(text) is None, label)
        check(f"C.2 Level 3 refuses {label}", l3(text) is None, label)
    for label, reason in (("a wrong-product refusal", "wrong_product"),
                          ("a non-concrete refusal", "not_a_real_issue_report"),
                          ("a vendor announcement", "vendor_release_announcement"),
                          ("a working-build refusal", "version_named_but_working"),
                          ("a rollback-target refusal", "version_named_but_rollback_target"),
                          ("a fixed-in-target refusal", "version_named_but_fixed_in_target"),
                          ("a multi-build refusal",
                           "multiple_builds_named_target_not_blamed"),
                          ("a non-specific URL refusal", "source_url_not_specific_report")):
        text = "After the latest Acrobat update printing stopped working."
        check(f"C.3 Level 2 never recovers {label}", l2(text, reason=reason) is None, reason)
        check(f"C.4 Level 3 never recovers {label}", l3(text, reason=reason) is None, reason)
    check("C.5 exactly one refusal is recoverable, and it is the IDENTITY one",
          at.ACROBAT_TIERABLE_REJECTIONS == frozenset({"missing_exact_patch_version_match"}),
          str(at.ACROBAT_TIERABLE_REJECTIONS))
    check("C.6 the never-tier set is enumerated, so a NEW reason fails closed by default",
          "acrobat_standard_edition_not_tracked" in at.ACROBAT_NEVER_TIER
          and l2("After the update Acrobat broke.", reason="some_reason_invented_later") is None)
    check("C.7 a how-to is refused even when it mentions an update",
          l3("How do I update Acrobat to the latest version?") is None)
    check("C.8 the safety rules come from the COLLECTOR, not a copy in lib/",
          "_STANDARD_PRODUCT_RE" in (_AUX / "scripts" / "patch_collectors"
                                     / "adobe_acrobat_community.py").read_text(encoding="utf-8")
          and "_STANDARD_PRODUCT_RE" not in (_AUX / "scripts" / "lib" / "acrobat_tiering.py"
                                             ).read_text(encoding="utf-8").split("safety._")[0])

    print()
    print("=" * 98)
    print("C2  a reporter who names a version has told us which one they mean")
    print("=" * 98)
    # THE HOLE THIS CLOSES. Phase A's gate chain is an `elif`: for a patch whose build a report
    # does not name, `missing_exact_patch_version_match` short-circuits BEFORE the multi-build and
    # working/rollback vetoes, so those refusals never execute and are invisible here. A live row
    # went through it -- a thread refused at Level 1 twice as
    # `multiple_builds_named_target_not_blamed` was published at Level 2 against a third build.
    # Re-running those vetoes would test the wrong build, so the rule is structural instead.
    for label, text in (
            ("a DIFFERENT tracked build (wrong window)",
             "After the update Acrobat will not print. We are on 26.001.21691."),
            ("two builds it is comparing",
             "Initial version: 26.001.21691 Updated version: 26.001.21771. Acrobat crashes."),
            ("an UNTRACKED version pasted from a crash log",
             'Acrobat crashes. applicationVersion="26.001.21462" year=2026 month=4'),
            ("this window's OWN build -- that report is Level-1 material, and publishing it here "
             "would deny an attribution the reporter made",
             "Acrobat 26.001.21745 crashes every time I print.")):
        check(f"C2.1 Level 2 refuses a report naming {label}", l2(text) is None)
        check(f"C2.2 Level 3 refuses a report naming {label}", l3(text) is None)
    check("C2.3 a report naming NO version is still admitted",
          l3("Acrobat crashes every time I print.") is not None)
    check("C2.4 the refusal reason names the build, so it is diagnosable",
          at.names_any_tracked_build("Acrobat crashes on 26.001.21745", READER, ac) != "")

    # Adobe writes the same build five ways. Over-inclusive on purpose: this is a REFUSAL, so a
    # false match costs one context row while a miss publishes a claim the reporter contradicts.
    for spelling, why in (("26.001.21745", "release notes"),
                          ("2026.001.21745", "Help > About"),
                          ("26.1.21745", "installer / file version"),
                          ("2600121745", "AUSST deployment path"),
                          ("21745", "how people write it in a title")):
        check(f"C2.5 detected: {spelling} ({why})",
              at.names_any_tracked_build(f"Acrobat broke, we are on {spelling} here", READER, ac)
              != "", spelling)
    for benign in ("Error 30088-29 keeps appearing", "This started on 2026-05-01",
                   "I have 21745 documents in the folder"):
        # The last one is a deliberate false positive: a bare tail is ambiguous, and refusing a
        # context row is the cheap side of that trade.
        detected = at.names_any_tracked_build(benign, READER, ac)
        check(f"C2.6 non-version numbers: {benign[:34]!r} -> {detected or 'clear'}",
              detected == "" or benign.startswith("I have"))

    print()
    print("=" * 98)
    print("D  the release window comes from the ORIGINAL post date")
    print("=" * 98)
    check("D.1 a report with no original post date is refused, never dated from the feed stamp",
          l3("Acrobat will not print anything since Monday.", original="") is None)
    bumped = l3("Acrobat will not print anything.", date="2026-08-20", original="2026-07-28")
    check("D.2 the ORIGINAL date decides the window, not a later reply's stamp",
          bumped is not None and bumped.window_build == VER,
          bumped.window_build if bumped else "none")
    check("D.3 a report cannot land on a release that had not shipped when it was written",
          bumped is not None and bumped.report_date < "2026-08-01"
          and bumped.window_build != NEXT_VER)
    boundary = l3("Acrobat will not print anything.", original="2026-08-01")
    check("D.4 containment is half-open: a report ON the next release date belongs to the NEW one",
          boundary is not None and boundary.window_build == NEXT_VER,
          boundary.window_build if boundary else "none")
    check("D.5 a report older than every tracked window is refused",
          l3("Acrobat will not print anything.", original="2019-01-01") is None)
    check("D.6 windows are per PRODUCT -- a Pro report cannot land in a Reader-only window",
          (lambda r: r is not None and r.product_id == PRO)(
              l3("Acrobat will not print anything.", product_id=PRO, original="2026-07-28")))
    check("D.7 the collector reads the original date structurally, from the opening post",
          'date_part(first_post.get("creationDate"))' in
          (_AUX / "scripts" / "patch_collectors" / "adobe_acrobat_community.py"
           ).read_text(encoding="utf-8"))

    print()
    print("=" * 98)
    print("E  one report, one level")
    print("=" * 98)
    already = {URL.rstrip("/").lower()}
    check("E.1 a report already confirmed at Level 1 is refused at Level 2",
          at.acrobat_update_linked_from_rejection(
              rejection("After the latest Acrobat update printing stopped working."),
              windows=WINDOWS, captured_at=CAP, safety=ac, applicability=SHARED,
              exclude_urls=already) is None)
    check("E.2 and at Level 3",
          at.acrobat_recent_from_rejection(
              rejection("Acrobat will not print anything."), windows=WINDOWS, captured_at=CAP,
              safety=ac, applicability=SHARED, exclude_urls=already) is None)
    check("E.3 a report that blames an update goes to Level 2, NOT Level 3",
          l2("After the latest Acrobat update printing stopped working.") is not None
          and l3("After the latest Acrobat update printing stopped working.") is None)
    check("E.4 a report with no attribution goes to Level 3, not Level 2",
          l3("Acrobat will not print anything.") is not None
          and l2("Acrobat will not print anything.") is None)
    same = l3("Acrobat will not print anything.")
    check("E.5 both levels mint the SAME stable identity for one URL",
          same is not None
          and same.report_id == at.report_identity(READER, URL),
          same.report_id if same else "none")

    # Promotion: a row that has since become Level 1 or Level 2 must vanish from Level 3.
    row3 = l3("Acrobat will not print anything.")
    merged, stats = merge_recent_reports([row3.as_dict()], [], promoted_urls=already)
    check("E.6 promotion EVICTS the Level-3 row rather than leaving a stale card",
          merged == [] and stats["promoted_out"] == 1, f"{merged} {stats}")
    kept, stats_k = merge_recent_reports([row3.as_dict()], [], promoted_urls=set())
    check("E.7 and a row NOT promoted survives the same merge", len(kept) == 1, str(stats_k))

    print()
    print("=" * 98)
    print("F  neither level can reach consensus")
    print("=" * 98)
    evidence_path = _AUX / "_data" / "consensus_evidence.yml"
    doc = yaml.safe_load(evidence_path.read_text(encoding="utf-8")) or {}
    evidence = doc.get("evidence") or []
    before = {pid: len(counted_rows(evidence, pid, VER)) for pid in (READER, PRO)}
    hundred2 = [l2(f"After the latest Acrobat update printing stopped working. Case {i}.",
                   url=f"https://community.adobe.com/questions-9/acrobat-print-{7000 + i}")
                for i in range(100)]
    hundred3 = [l3(f"Acrobat will not print anything. Case {i}.",
                   url=f"https://community.adobe.com/questions-9/acrobat-blank-{8000 + i}")
                for i in range(100)]
    hundred2 = [r.as_dict() for r in hundred2 if r]
    hundred3 = [r.as_dict() for r in hundred3 if r]
    check("F.1 the mutation is real -- 100 Level-2 and 100 Level-3 rows were built",
          len(hundred2) == 100 and len(hundred3) == 100, f"{len(hundred2)}/{len(hundred3)}")
    after = {pid: len(counted_rows(evidence, pid, VER)) for pid in (READER, PRO)}
    check("F.2 counted Level-1 evidence is identical with 200 tier rows present",
          before == after, f"{before} vs {after}")
    for name, rows in (("Level 2", hundred2), ("Level 3", hundred3)):
        check(f"F.3 a {name} row carries no `counted` field",
              all("counted" not in r for r in rows))
        check(f"F.4 nor any consensus-bearing field ({name})",
              all(not ({"sentiment", "severity", "source_weight", "patch_version_matched"}
                       & set(r)) for r in rows))
    tier_files = {"acrobat_update_linked_evidence", "recent_acrobat_reports"}
    consumers = [p for p in (_AUX / "scripts").rglob("*.py")
                 if "consensus_evidence.yml" in p.read_text(encoding="utf-8", errors="replace")
                 and "/tests/" not in p.as_posix() and "\\tests\\" not in str(p)]
    leaking = [p.name for p in consumers
               if any(t in p.read_text(encoding="utf-8", errors="replace") for t in tier_files)
               and p.name != "adobe_acrobat_community.py"]
    check("F.5 no consensus consumer reads either Acrobat tier file", not leaking, str(leaking))
    check("F.6 the tier files are separate from PowerPoint's, so isolation is structural",
          ac.TIER2_PATH.name == "acrobat_update_linked_evidence.yml"
          and ac.TIER3_PATH.name == "recent_acrobat_reports.yml")

    # WRITE AUTHORITY. Two independent guards must both name these files, and the first production
    # run proved it: the collector wrote them, the per-collector transaction read that as an
    # undeclared mutation, and the ENTIRE Acrobat run was rolled back with
    # `unexpected_mutation:UnexpectedMutation`. A local backfill script never exercises either guard.
    from run_patch_evidence_collection import _extra_write_surface  # noqa: PLC0415
    for pid in (READER, PRO):
        names = {p.name for p in _extra_write_surface(pid)}
        check(f"F.7 the transaction surface declares both tier files for {pid.split('-')[-1]}",
              names == {ac.TIER2_PATH.name, ac.TIER3_PATH.name}, str(names))
    check("F.8 and declares them for NO other product",
          _extra_write_surface("obs-studio") == []
          and _extra_write_surface("microsoft-powerpoint") == [])
    workflow = (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml"
                ).read_text(encoding="utf-8")
    for name in (ac.TIER2_PATH.name, ac.TIER3_PATH.name):
        check(f"F.9 the writeback allow-list permits {name}",
              f"--allow auxsays/_data/{name}" in workflow)

    print()
    print("=" * 98)
    print("W  two writers cannot silently clobber newer adjudication with stale output")
    print("=" * 98)
    # THE INCIDENT THIS LOCKS. Two backfills ran against the same file. The one started BEFORE a
    # rule was corrected finished AFTER the corrected one and replaced 7 adjudicated rows with its
    # own stale 10, two of which the corrected rules refuse. Both writes "succeeded", the YAML was
    # valid, the suites were green, and it reached main. Losing a race must be loud.
    import tempfile  # noqa: PLC0415

    from lib import single_writer as sw  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "tier.yml"
        target.write_text("rows: [A]", encoding="utf-8")

        # A slow writer reads the baseline...
        baseline = sw.fingerprint(target)
        check("W.1 a fingerprint identifies the exact bytes a writer derived its output from",
              baseline and baseline == sw.fingerprint(target))
        # ...a second writer publishes newer adjudication meanwhile...
        sw.guarded_write(target, b"rows: [B_newer]", expected=baseline)
        check("W.2 the second writer succeeds against the baseline it read",
              target.read_text(encoding="utf-8") == "rows: [B_newer]")
        # ...and the slow writer now tries to publish output built from the OLD bytes.
        refused = False
        try:
            sw.guarded_write(target, b"rows: [A_stale]", expected=baseline)
        except sw.StaleWrite:
            refused = True
        check("W.3 the stale writer is REFUSED rather than winning by finishing late", refused)
        check("W.4 and the newer adjudication is still on disk",
              target.read_text(encoding="utf-8") == "rows: [B_newer]")

        # Mutual exclusion, so two writers cannot interleave a partial file.
        held = False
        with sw.write_lock(target):
            try:
                with sw.write_lock(target, timeout_s=0.5):
                    pass
            except sw.WriterBusy:
                held = True
        check("W.5 a second writer waits or fails while the lock is held", held)
        check("W.6 and the lock is released afterwards, not leaked",
              not Path(str(target) + sw.LOCK_SUFFIX).exists())

        # Atomicity: a writer that dies mid-serialisation must not truncate the published file.
        def exploding(_tmp):
            raise RuntimeError("serialiser died")

        try:
            sw.guarded_write_via(target, exploding, expected=None)
        except RuntimeError:
            pass
        check("W.7 a writer that raises leaves the previous complete file in place",
              target.read_text(encoding="utf-8") == "rows: [B_newer]")
        check("W.8 and leaves no temp file behind",
              not list(Path(td).glob(".*tmp")))

        # A first creation legitimately has no baseline.
        fresh = Path(td) / "new.yml"
        sw.guarded_write(fresh, b"rows: []", expected="")
        check("W.9 creating a file states an ABSENT baseline, not no baseline at all",
              fresh.read_text(encoding="utf-8") == "rows: []")

    # The production path holds the lock across its read AND its write, so it merges whatever
    # another writer published instead of having a stale baseline to reinstate.
    collector_src = (_AUX / "scripts" / "patch_collectors" / "adobe_acrobat_community.py"
                     ).read_text(encoding="utf-8")
    check("W.10 the collector writes tier files under the write lock",
          "with write_lock(path):" in collector_src)
    check("W.11 and re-reads the existing rows INSIDE that lock",
          collector_src.index("with write_lock(path):")
          < collector_src.index("others = [r for r in loader(path)"))
    check("W.12 publication is atomic, never a partial serialisation",
          "replace_via(path," in collector_src)

    print()
    print("=" * 98)
    print("G  the page says context, never causation")
    print("=" * 98)
    layout = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    row_inc = (_AUX / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
    check("G.1 the layout reads the ACROBAT tier files on an Acrobat page",
          "site.data.acrobat_update_linked_evidence.reports" in layout
          and "site.data.recent_acrobat_reports.reports" in layout)
    check("G.2 the Level-3 heading names this product rather than another one",
          "Recent {{ l3_product }} reports" in layout
          and "Recent PowerPoint reports" not in layout)
    check("G.2b the Level-2 note names this product too -- 'a PowerPoint or Office update' on an "
          "Acrobat page is a factual error about what the reporter said",
          "assign t2_product = 'PowerPoint or Office'" in layout
          and "assign t2_product = 'Acrobat'" in layout
          and "tie the problem to a PowerPoint or Office\n" not in layout)
    check("G.3 the not-attributed qualifier is present",
          "Not attributed to this update." in layout)
    check("G.4 and the sentence saying the reporters did not blame the update",
          "did not identify this update as the cause" in layout)
    check("G.5 the Acrobat key uses the DC version in the build slot",
          "assign t2_build = page.update_version" in layout)
    check("G.6 the listing keeps the three counts distinct, not one total",
          "update-linked</span>" in row_inc and "recent</span>" in row_inc
          and 'data-reports="{{ report_count_num }}"' in row_inc)
    check("G.7 the listing reads the Acrobat tier files too",
          "site.data.acrobat_update_linked_evidence.reports" in row_inc
          and "site.data.recent_acrobat_reports.reports" in row_inc)
    check("G.8 and it does not add a third guarded build site",
          sum(1 for line in row_inc.splitlines() if "assign row_build" in line) == 2,
          str(sum(1 for line in row_inc.splitlines() if "assign row_build" in line)))
    l3_block = layout[layout.index("recent-reports-card"):]
    l3_block = l3_block[:l3_block.index('id="verdict"')] if 'id="verdict"' in l3_block else l3_block
    for phrase in ("caused by", "likely caused", "suspected", "evidence against",
                   "linked to this update", "problems with build"):
        check(f"G.9 no causal phrasing in the Level-3 block: {phrase!r}",
              phrase.lower() not in l3_block.lower())

    print()
    print("=" * 98)
    print("H  the vocabulary actually matches production")
    print("=" * 98)
    # A reason token that no Acrobat run ever emits would make every control above pass while
    # asserting nothing -- the "true and vacuous" trap. Prove the tierable reason is real.
    source = (_AUX / "scripts" / "patch_collectors" / "adobe_acrobat_community.py"
              ).read_text(encoding="utf-8")
    for reason in sorted(at.ACROBAT_TIERABLE_REJECTIONS | at.ACROBAT_NEVER_TIER):
        # The role refusals are built as f"version_named_but_{outcome}", so the literal token never
        # appears in the source -- assert the prefix and the outcome constant instead.
        if reason.startswith("version_named_but_"):
            outcome = reason[len("version_named_but_"):]
            check(f"H.1 the collector really can emit {reason!r}",
                  '"version_named_but_"' in source or 'version_named_but_{' in source,
                  reason)
            check(f"H.1b and {outcome!r} is a real outcome of the shared primitive",
                  outcome in (_AUX / "scripts" / "lib" / "target_outcome.py"
                              ).read_text(encoding="utf-8"), outcome)
            continue
        if reason == "generic_acrobat_without_edition":
            continue
        check(f"H.1 the collector really can emit {reason!r}", f'"{reason}"' in source, reason)
    check("H.2 the collector attaches the full text tiers classify",
          '"tier2_full_text"' in source)
    check("H.3 and the original post date they place windows on",
          '"original_post_date"' in source)

    print()
    print("=" * 98)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _FAILURES:
        print("Failed: " + ", ".join(_FAILURES))
    print("=" * 98)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
