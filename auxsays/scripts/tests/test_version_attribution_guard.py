#!/usr/bin/env python3
"""The version-attribution corpus guard and DaVinci release-line identity.

Two things are pinned here.

THE GUARD (lib/version_attribution.py, check_version_attribution.py). For every counted row it reads
the row's OWN stored text and flags: the row's version named as the rollback target or the fix; a
different tracked version named and the row's own never; a release-line row that names an exact
point release. A flag is a warning, never a failure and never a withdrawal. Measured at 12d207ba on
1,620 counted rows: 17 flags (11 other-version, 6 point-release); the role check with `working` and
`reference` included raised 5 flags, all wrong, and those two outcomes are not reported.

RELEASE-LINE IDENTITY (lib/davinci_release_line.py). A bare DaVinci version is a release line as
soon as it counts reports: the collector refuses a report that names an exact point release, the
record writer states the line and its range, and the migration applies the same predicate to the
stored rows.

Offline. Frozen fixtures, a temporary store, and read-only passes over the shipped store whose
assertions hold for any corpus a collector can produce (a bot commit must not turn this red).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402
import apply_consensus_to_records as writer  # noqa: E402
from lib import davinci_release_line as drl  # noqa: E402
from lib import patch_decision as pd  # noqa: E402
from lib import version_attribution as va  # noqa: E402
from patch_collectors import base, davinci  # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


def row(**over) -> dict:
    data = {"id": "r1", "product_id": "obs-studio", "update_version": "32.1.2", "counted": True,
            "source_url": "https://example.test/1", "parent_title": "", "report_title": "",
            "report_text_excerpt": ""}
    data.update(over)
    return data


def codes(flags) -> list[str]:
    return [f.code for f in flags]


def run_suite() -> int:
    vocab = frozenset({"32.1.2", "32.2.0", "32.0.4", "KB5074109", "KB5074105", "26200.7705"})

    print("G. guard: own version named as rollback target or fix")
    f = va.assess_row(row(report_text_excerpt="Crashes on stream start in 32.2.0. "
                                             "I downgraded to 32.1.2 and it is stable."), vocab)
    check("G1 a rolled-back-to version is flagged", va.FLAG_CONTRADICTED in codes(f), str(codes(f)))
    f = va.assess_row(row(report_text_excerpt="Black screen in 32.2.0. Resolved in 32.1.2."), vocab)
    check("G2 a fixed-in version is flagged", va.FLAG_CONTRADICTED in codes(f), str(codes(f)))
    keep = [
        "OBS 32.1.2 crashes when I start the virtual camera.",
        "32.1.2 and 32.2.0 won't work with my capture card anymore.",
        "After update 32.1.2 I work in IT and users cannot open the settings dialog.",
        "Update 32.1.2 fails to install. How do I get this to work?",
        "Installed 32.1.2 and restarted the working laptop too, sources are black.",
        "I reverted to 32.1.2 and it still crashes on 32.1.2.",
    ]
    for index, text in enumerate(keep, start=3):
        f = va.assess_row(row(report_text_excerpt=text), vocab)
        check(f"G{index} keep: {text[:52]!r}", va.FLAG_CONTRADICTED not in codes(f), str(codes(f)))
    # KNOWN LIMIT, pinned so it is not mistaken for a guarantee: the shared role authority reads
    # "rolled back to X and the problem is still there" as a rollback. The guard then raises a
    # review flag for a row that should stay counted. That is why a flag never withdraws a row.
    f = va.assess_row(row(report_text_excerpt="I rolled back to 32.1.2 and the problem is still there."),
                      vocab)
    check("G10 known limit: 'rolled back to X, problem still there' is flagged for review",
          va.FLAG_CONTRADICTED in codes(f), str(codes(f)))
    check("G9 only rollback and fixed are reported roles",
          va.REPORTED_ROLES == frozenset({"rollback_target", "fixed_in_target"}),
          str(sorted(va.REPORTED_ROLES)))

    print("O. guard: another tracked version named, own never")
    f = va.assess_row(row(report_title="Black screen since 32.2.0",
                          report_text_excerpt="Black screen since 32.2.0 on every scene."), vocab)
    check("O1 other tracked version only is flagged", codes(f) == [va.FLAG_OTHER_ONLY], str(codes(f)))
    check("O2 the flag names the version the text names", f and f[0].named == ("32.2.0",), str(f))
    f = va.assess_row(row(report_text_excerpt="Fails in 32.1.2; 32.2.0 has it too."), vocab)
    check("O3 own version present: not flagged", va.FLAG_OTHER_ONLY not in codes(f), str(codes(f)))
    f = va.assess_row(row(report_text_excerpt="Using 16 GB of RAM and 20 sources it stutters."), vocab)
    check("O4 no version named: not flagged", codes(f) == [], str(codes(f)))
    f = va.assess_row(row(product_id="microsoft-windows-11", update_version="25H2",
                          target_build="26200.7705", matched_kb="KB5074105",
                          report_text_excerpt="KB5074109 makes the GPU unusable."), vocab)
    check("O5 a KB is vocabulary", codes(f) == [va.FLAG_OTHER_ONLY] and f[0].named == ("KB5074109",),
          str(f))
    f = va.assess_row(row(product_id="microsoft-windows-11", update_version="25H2",
                          target_build="26200.7705", matched_kb="KB5074105",
                          report_text_excerpt="KB5074105 broke sign-in. KB5074109 did not."), vocab)
    check("O6 the row's own KB present: not flagged", va.FLAG_OTHER_ONLY not in codes(f), str(codes(f)))
    check("O7 a bare integer is never vocabulary",
          not va.is_self_identifying("20") and not va.is_self_identifying("2607")
          and va.is_self_identifying("20.3.2") and va.is_self_identifying("KB5074109"))
    f = va.assess_row(row(report_text_excerpt="Black screen since 32.2.0."), vocab,
                      counted_for=frozenset({"32.1.2", "32.2.0"}))
    check("O8 a second count of one report is named",
          f and f[0].extra.get("also_counted_for") == ["32.2.0"], str(f and f[0].extra))
    f = va.assess_row(row(report_text_excerpt="Works in 32.2.01 only."), vocab)
    check("O9 a longer number is not the tracked version", codes(f) == [], str(codes(f)))
    trunc = row(report_text_excerpt="Black screen since 32.2.0 on every scene and it continues...")
    check("O10 a cut excerpt is marked truncated",
          va.assess_row(trunc, vocab)[0].truncated is True
          and va.assess_row(row(report_text_excerpt="Black screen since 32.2.0."), vocab)[0].truncated is False)

    print("P. point releases of a release line")
    spr = drl.stated_point_releases
    check("P1 dotted point releases are read", spr("both 20.2.2 and 21.0.3 Free", "20") == ["20.2.2"]
          and spr("both 20.2.2 and 21.0.3 Free", "21") == ["21.0.3"])
    check("P2 a sentence end is not a point release", spr("I am on Resolve 21. It crashes.", "21") == [])
    check("P3 an aspect ratio, a price and a longer number are not",
          spr("21:9 timeline, $21.50 plugin, build 121.4, 2021.1", "21") == [])
    check("P4 a version prefix is accepted, a word is not",
          spr("on v21.1 now", "21") == ["21.1"] and spr("rev21.1", "21") == [])
    check("P5 N.0 is the first release unless it has its own record",
          spr("Resolve 20.0 crashes", "20") == []
          and spr("Resolve 21.0 crashes", "21", ["21", "21.0"]) == ["21.0"]
          and spr("iPad 21.0.0.1", "21") == ["21.0.0.1"])
    check("P6 only a bare line has point releases", spr("20.3.2 crash", "20.3") == [])
    versions = ["20", "20.0.1", "20.3.3", "20.2", "21", "21 Public Beta 1", "19.1"]
    check("P7 line members are the stable releases of the line, oldest first",
          drl.line_members("20", versions) == ["20", "20.0.1", "20.2", "20.3.3"]
          and drl.line_members("21", versions) == ["21"])
    ident = drl.identity_fields("DaVinci Resolve", "20", versions)
    check("P8 a line with point releases gets a release-line identity",
          ident.get(drl.SCOPE_FIELD) == "release_line"
          and ident.get("update_channel_label") == "Release line: 20 to 20.3.3"
          and "not one exact update" in ident.get("record_note", ""), str(ident))
    check("P9 a line with no point release is one exact update",
          drl.identity_fields("DaVinci Resolve", "21", versions) == {})
    none_note = ident.get("record_note", "")
    two_note = drl.identity_fields("DaVinci Resolve", "20", versions, shared=2).get("record_note", "")
    one_note = drl.identity_fields("DaVinci Resolve", "20", versions, shared=1).get("record_note", "")
    check("P10 the note claims no overlap with exact releases only while the store shows none",
          "No report counted here is also counted" in none_note
          and "No report counted here" not in two_note and "known to name" not in two_note
          and "2 of the reports counted here are also counted on an exact release's page" in two_note
          and "1 of the reports counted here is also counted" in one_note, two_note)
    lo_rows = [{"product_id": drl.PRODUCT_ID, "update_version": v, "source_url": u, "counted": c}
               for v, u, c in [("20", "u1", True), ("20.2", "u1", True), ("20", "u2", True),
                               ("20.2", "u2", False), ("20", "u3", True), ("21.1", "u3", True),
                               ("21", "u4", True), ("21.0.2", "u4", True)]]
    lo_rows.append({"product_id": "obs-studio", "update_version": "20", "source_url": "u5", "counted": True})
    check("P11 line_overlaps counts a line row only when the same report is counted on a point "
          "release of THAT line",
          drl.line_overlaps(lo_rows) == {"20": 1, "21": 1}, str(drl.line_overlaps(lo_rows)))

    print("C. collector: the line page refuses a report that names a point release")
    record20 = next(r for r in base.generated_records("blackmagic-davinci", include_archived=True)
                    if r.update_version == "20")
    cand = {"source_type": "creator_forum_report", "source_name": "Forum",
            "source_url": "https://forum.example.test/viewtopic.php?t=901",
            "source_date": "2026-01-10"}

    def gate(text: str) -> dict:
        return davinci.row_from_candidate(record20, {**cand, "parent_title": text, "report_title": text,
                                                     "report_text": text}, "2026-01-11T00:00:00Z")

    r = gate("DaVinci Resolve 20 crashes on export every time.")
    check("C1 a line report is still counted", r.get("counted") is True, str(r.get("exclusion_reason")))
    r = gate("DaVinci Resolve Studio 20 Version 20.3 Build 10 crashes on export every time.")
    check("C2 a report naming 20.3 is refused for the line",
          r.get("counted") is False and r.get("exclusion_reason") == drl.REASON_POINT_RELEASE_NAMED,
          str(r.get("exclusion_reason")))
    r = gate("DaVinci Resolve 20 crashes on export; my old 19.1.4 install was fine.")
    check("C3 another line's point release does not refuse it", r.get("counted") is True,
          str(r.get("exclusion_reason")))

    print("M. migration on a temporary store")
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        common = {"product_id": "blackmagic-davinci", "source_type": "creator_forum_report",
                  "source_name": "Forum", "captured_at": "2026-01-11T00:00:00Z",
                  "source_date": "2026-01-10", "patch_version_matched": True, "counted": True,
                  "exclusion_reason": None, "source_weight": 1, "match_basis": "exact_version_text"}
        t_line = "DaVinci Resolve 20 crashes on export every time."
        t_point = "DaVinci Resolve Studio 20 Version 20.3 Build 10 crashes on export every time."
        t_dup = "DaVinci Resolve 20.2.2 crashes on export every time, same on 20 before."
        rows = [
            {**common, "id": "line-keep", "update_version": "20", "matched_version": "20",
             "source_url": "https://forum.example.test/viewtopic.php?t=1",
             "parent_title": t_line, "report_title": t_line, "report_text_excerpt": t_line},
            {**common, "id": "line-point", "update_version": "20", "matched_version": "20",
             "source_url": "https://forum.example.test/viewtopic.php?t=2",
             "parent_title": t_point, "report_title": t_point, "report_text_excerpt": t_point},
            {**common, "id": "line-dup", "update_version": "20", "matched_version": "20",
             "source_url": "https://forum.example.test/viewtopic.php?t=3",
             "parent_title": t_dup, "report_title": t_dup, "report_text_excerpt": t_dup},
            {**common, "id": "exact-dup", "update_version": "20.2.2", "matched_version": "20.2.2",
             "source_url": "https://forum.example.test/viewtopic.php?t=3",
             "parent_title": t_dup, "report_title": t_dup, "report_text_excerpt": t_dup},
            {**common, "id": "other-product", "product_id": "obs-studio", "update_version": "32.1.2",
             "matched_version": "32.1.2", "source_url": "https://forum.example.test/viewtopic.php?t=4",
             "parent_title": "OBS 32.1.2 crash", "report_title": "OBS 32.1.2 crash",
             "report_text_excerpt": "OBS 32.1.2 crash on start."},
        ]
        base.write_evidence_file(rows, store)
        tool = str(SCRIPTS / "migrate_davinci_release_line_identity.py")
        receipt = Path(tmp) / "receipt.json"

        def run(*extra: str) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, tool, "--evidence-path", str(store), *extra],
                                  capture_output=True, text=True)

        before = store.read_bytes()
        dry = run()
        check("M1 without --write nothing is written", dry.returncode == 0 and store.read_bytes() == before,
              dry.stdout[-300:] + dry.stderr[-300:])
        done = run("--write", "--receipt", str(receipt))
        after = {r["id"]: r for r in base.load_evidence(store)}
        check("M2 --write succeeds", done.returncode == 0, done.stdout[-300:] + done.stderr[-400:])
        check("M3 the two rows naming a point release are withdrawn and kept",
              all(after.get(i, {}).get("counted") is False
                  and after[i].get("exclusion_reason") == drl.REASON_POINT_RELEASE_NAMED
                  for i in ("line-point", "line-dup")),
              str({i: (after.get(i, {}).get("counted"), after.get(i, {}).get("exclusion_reason"))
                   for i in ("line-point", "line-dup")}))
        check("M4 the line row that names no point release still counts",
              after["line-keep"].get("counted") is True)
        moved = [r for r in after.values() if r.get("update_version") == "20.3"
                 and r.get("source_url", "").endswith("t=2")]
        check("M5 the report is appended to the release it names, through that record's own gates",
              len(moved) == 1 and moved[0].get("counted") is True, str(moved))
        check("M6 a report already counted for the named release is not appended again",
              sum(1 for r in after.values() if r.get("source_url", "").endswith("t=3")) == 2)
        check("M7 no row is deleted and the other product is untouched",
              len(after) == len(rows) + 1 and after["other-product"] == base.load_evidence(store)[4]
              and after["other-product"].get("counted") is True, str(len(after)))
        data = json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else {}
        check("M8 the receipt proves the untouched rows are byte-identical",
              data.get("untouched_rows_identical") is True and data.get("untouched_rows") == 3
              and len(data.get("withdrawn", [])) == 2 and len(data.get("appended", [])) == 1, str(data)[:300])
        second = store.read_bytes()
        again = run("--write", "--receipt", str(receipt))
        check("M9 a second run changes nothing", again.returncode == 0 and store.read_bytes() == second,
              again.stdout[-200:])

    print("F. fix round 1: the review's findings")
    dv = {"product_id": "blackmagic-davinci", "update_version": "21", "matched_version": "21"}
    f = va.assess_row(row(**dv, report_title="Resolve crash",
                          report_text_excerpt="DaVinci Resolve 21.0.3 crashes on export."),
                      frozenset({"21.0.3"}))
    check("F1 (S3) a release-line row whose stored text names a point release is flagged",
          va.FLAG_POINT_RELEASE in codes(f) and f[-1].named == ("21.0.3",), str(codes(f)))
    f = va.assess_row(row(**dv, report_text_excerpt="DaVinci Resolve 21 crashes on export."),
                      frozenset({"21.0.3"}))
    check("F2 (S3) a release-line row that names only the line is not flagged", not f, str(codes(f)))
    cut = "DaVinci Resolve 21 crashes on export every time I render a long..."
    f = va.assess_row(row(**dv, report_text_excerpt=cut), frozenset({"21.0.2"}),
                      frozenset({"21", "21.0.2"}))
    check("F3 (M2) a line row whose report is also counted on a point release of the line is flagged",
          codes(f) == [va.FLAG_POINT_RELEASE] and f[0].extra.get("also_counted_for") == ["21.0.2"],
          str([x.as_dict() for x in f])[:300])
    f = va.assess_row(row(**dv, report_text_excerpt=cut), frozenset({"20.3"}), frozenset({"21", "20.3"}))
    check("F4 (M2) a count on another line's release does not flag it", not f, str(codes(f)))

    win = {"product_id": "microsoft-windows-11", "update_version": "25H2", "target_build": "26200.8973",
           "matched_feature_version": "25H2", "matched_os_build": "26200.8973"}
    wv = frozenset({"26200.8875", "26200.8973", "KB5094126"})
    f = va.assess_row(row(**win, report_title="Store and Start menu crash - 25H2 26200.8875",
                          report_text_excerpt="On Windows 11 25H2 build 26200.8875 the Store crashes."), wv)
    check("F5 (S2) a feature-update name is not the row's own identity: another build is flagged",
          codes(f) == [va.FLAG_OTHER_ONLY] and f[0].named == ("26200.8875",), str(codes(f)))
    f = va.assess_row(row(**win, report_title="Store crash on 25H2 26200.8973",
                          report_text_excerpt="Build 26200.8973 crashes; 26200.8875 was fine."), wv)
    check("F6 (S2) the row's own build in the text still clears it",
          va.FLAG_OTHER_ONLY not in codes(f), str(codes(f)))
    f = va.assess_row(row(product_id="microsoft-windows-11", update_version="25H2",
                          report_text_excerpt="Windows 11 25H2 crashes; 26200.8875 was fine."), wv)
    check("F7 (S2) a row whose ONLY identity is the feature name keeps it",
          va.FLAG_OTHER_ONLY not in codes(f), str(codes(f)))

    tracked20 = ("20", "20.2", "20.3", "21", "21.0", "21.0.4", "21.1")
    ordinary = [("21", "Since the update on 21.10.2026 Resolve 21 crashes on export"),
                ("20", "Resolve 20 crashes; project is 20.5 GB on disk"),
                ("20", "Resolve 20 timeline at 20.5 fps stutters"),
                ("21", "Resolve 21 drops to 21.3 fps on playback"),
                ("19", "Resolve 19 render takes 19.5 hours now"),
                ("16", "Resolve 16 crashes with 16.7 ms frame time"),
                ("21", "Resolve 21 crash at 21.30 last night"),
                ("20", "Resolve 20 timeline at 20.3 fps stutters"),
                ("21", "Resolve 21 uses 21.5% more memory and 21.5GB of swap")]
    wrong = [(line, text, drl.stated_point_releases(text, line, tracked20)) for line, text in ordinary
             if drl.stated_point_releases(text, line, tracked20)]
    check(f"F8 (S4) a date, a time or a measurement is not a point release ({len(ordinary)} texts)",
          not wrong, str(wrong[:3]))
    still = [("21", "Resolve 21 is broken, 21.0.4 was fine, rolled back", ["21.0.4"]),
             ("21", "DaVinci Resolve v21.1 crashes", ["21.1"]),
             ("21", "Resolve (21.0.3 Free) crashes", ["21.0.3"]),
             ("21", "DaVinci Resolve for iPad 21.0.0.1 crashes", ["21.0.0.1"]),
             ("21", "Resolve 21.1 w/ Studio licence crashes", ["21.1"]),
             ("20", "Resolve 20.2 x64 build crashes", ["20.2"]),
             ("21", "Resolve 21.3 crashes on export", ["21.3"]),
             ("21", "Resolve 21.2.1 crashes after 30 minutes", ["21.2.1"])]
    lost = [(line, text, drl.stated_point_releases(text, line, tracked20)) for line, text, want in still
            if drl.stated_point_releases(text, line, tracked20) != want]
    check(f"F9 (S4) a point release is still read as one ({len(still)} texts)", not lost, str(lost[:3]))

    decision = pd.decide({"product_id": "blackmagic-davinci", "update_version": "21"})
    line_body = pd.public_body(decision, {drl.SCOPE_FIELD: drl.SCOPE_RELEASE_LINE}, 65)
    exact_body = pd.public_body(decision, {}, 65)
    one_body = pd.public_body(decision, {drl.SCOPE_FIELD: drl.SCOPE_RELEASE_LINE}, 1)
    check("F10 (M1) a release-line page's line says its reports are matched to the release line",
          "65 user reports are matched to this release line" in line_body
          and "exact update" not in line_body
          and "one user report is matched to this release line" in one_body, line_body[:120])
    check("F11 (M1) every other page keeps 'matched to this exact update'",
          "65 user reports are matched to this exact update" in exact_body, exact_body[:120])
    gate = (ROOT / "_includes" / "patch-verdict-gate.html").read_text(encoding="utf-8")
    check("F12 (M1) the verdict gate keys the same two sentences on the same field",
          gate.count("pvg_record.update_identity_scope == 'release_line'") == 2
          and gate.count("this release line") == 2 and gate.count("this exact update") == 2)
    ident21 = drl.identity_fields("DaVinci Resolve", "21", ("21", "21.0", "21.2"))
    said = ident21.get("record_note", "") + " " + ident21.get("description", "")
    check("F13 (M2) the page states only what the store can show of its rows",
          "name no point release" not in said and "without a point release" not in said
          and "matched to" in said and "not one exact update" in said, said[:200])

    # The record writer composes the stored line in the same pass that decides the scope, so it
    # must hand the policy the scope it is about to write (the shipped tree has 21.x records).
    record21 = {"update_product": "DaVinci Resolve"}
    scoped = writer._with_identity_scope("blackmagic-davinci", "21", 65, record21, {"product_id": "x"})
    check("F18 (M1) the record writer composes a line page's stored line with the release-line scope",
          scoped.get(drl.SCOPE_FIELD) == drl.SCOPE_RELEASE_LINE and scoped.get("product_id") == "x"
          and drl.SCOPE_FIELD not in writer._with_identity_scope("blackmagic-davinci", "21", 0, record21, {})
          and drl.SCOPE_FIELD not in writer._with_identity_scope("blackmagic-davinci", "21.0.2", 9, record21, {})
          and drl.SCOPE_FIELD not in writer._with_identity_scope(
              "obs-studio", "21", 9, record21, {drl.SCOPE_FIELD: drl.SCOPE_RELEASE_LINE}), str(scoped))

    # Review 2 item b: the writer derives the overlap sentence from the store it is given, in memory
    # (dry run, nothing written). One line-"21" report also counted on 21.1 turns the claim into a count.
    store_rows = base.load_evidence()
    line21 = next((r for r in store_rows if r.get("product_id") == drl.PRODUCT_ID
                   and r.get("counted") is True and str(r.get("update_version")) == "21"), None)
    notes = {}
    if line21 is not None:
        probe = {**line21, "id": str(line21["id"]) + "-overlap-probe", "update_version": "21.1"}
        index, _fronts = writer._scan_generated_records()
        for label, given in (("plain", store_rows), ("overlap", store_rows + [probe])):
            for res in writer.run_dry_run(evidence_path=base.EVIDENCE_PATH, product_id_filter=drl.PRODUCT_ID,
                                          is_candidate_mode=False, records_index=index, rows=given):
                if res.get("update_version") == "21":
                    notes[label] = str((res.get("proposed_fields_if_written") or {}).get("record_note") or "")
    check("F19 the record writer derives the line page's overlap sentence from the store it reads",
          "1 of the reports counted here is also counted on an exact release's page" in notes.get("overlap", "")
          and "No report counted here" not in notes.get("overlap", "")
          and ("No report counted here" in notes.get("plain", "")) == (not drl.line_overlaps(store_rows).get("21")),
          str(notes)[:300])

    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        common = {"product_id": "blackmagic-davinci", "source_type": "creator_forum_report",
                  "source_name": "Forum", "captured_at": "2026-07-11T00:00:00Z",
                  "source_date": "2026-07-10", "patch_version_matched": True, "counted": True,
                  "exclusion_reason": None, "source_weight": 1, "match_basis": "exact_version_text"}
        t_cut = "DaVinci Resolve 21 crashes on export every time I render a long timeline with..."

        def stored(row_id: str, version: str, n: int, **over) -> dict:
            return {**common, "id": row_id, "update_version": version, "matched_version": version,
                    "source_url": f"https://forum.example.test/viewtopic.php?t={n}",
                    "parent_title": t_cut, "report_title": t_cut, "report_text_excerpt": t_cut, **over}

        rows = [stored("line-twice", "21", 10), stored("shared-id", "21.0.4", 10),
                stored("line-alone", "21", 11),
                stored("line-held", "21", 12),
                stored("shared-id", "21.1", 12, counted=False, exclusion_reason="not_a_real_issue_report")]
        base.write_evidence_file(rows, store)
        tool = str(SCRIPTS / "migrate_davinci_release_line_identity.py")
        receipt = Path(tmp) / "receipt.json"
        done = subprocess.run([sys.executable, tool, "--evidence-path", str(store), "--write",
                               "--receipt", str(receipt)], capture_output=True, text=True)
        after = base.load_evidence(store)
        state = {(r["id"], r["update_version"]): (r.get("counted"), r.get("exclusion_reason")) for r in after}
        check("F14 (M2) a line row whose report is counted on a point release is withdrawn, row kept",
              done.returncode == 0 and len(after) == len(rows)
              and state[("line-twice", "21")] == (False, drl.REASON_POINT_RELEASE_NAMED),
              done.stdout[-300:] + done.stderr[-300:])
        check("F15 (M2) one count per report: it stays counted on the release that counts it",
              state[("shared-id", "21.0.4")] == (True, None), str(state))
        check("F16 (M2) a report only HELD for a point release, not counted there, stays on the line",
              state[("line-held", "21")] == (True, None) and state[("line-alone", "21")] == (True, None),
              str(state))
        data = json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else {}
        check("F17 (M2) the receipt names the basis and counts EVERY row, shared ids included",
              [w.get("basis") for w in data.get("withdrawn", [])] == ["counted_on_point_release"]
              and data.get("rows_before") == 5 and data.get("rows_after") == 5
              and data.get("untouched_rows") == 4, str(data)[:300])

    print("S. the shipped store (read only; true for any corpus a collector can produce)")
    rows = base.load_evidence()
    counted = [r for r in rows if r.get("counted") is True]
    disagreements = []
    for r in counted:
        text = va.stored_text(r)
        for identity in va.own_identities(r):
            shared = base.exact_version_match(text, identity)[0]
            if shared != va.names_version(text, identity):
                disagreements.append((r["id"], identity))
    check(f"S1 the guard's matcher equals the shared exact_version_match ({len(counted)} rows)",
          not disagreements, str(disagreements[:3]))
    tracked = drl.versions_on_disk(base.GENERATED_DIR)
    stray = [r["id"] for r in counted if r.get("product_id") == drl.PRODUCT_ID
             and drl.is_bare_line(r.get("update_version"))
             and drl.stated_point_releases(va.stored_text(r), r.get("update_version"), tracked)]
    check("S2 no counted DaVinci release-line row names a point release", not stray, str(stray[:3]))
    flags = va.assess_corpus(rows)
    check("S3 the guard reports no point-release flag on a release-line row",
          not [f for f in flags if f.code == va.FLAG_POINT_RELEASE and f.product_id == drl.PRODUCT_ID
               and f.extra.get("tracked_point_releases")], str(len(flags)))
    check("S4 every flag names a counted row and one of the three codes",
          all(f.code in va.FLAG_ORDER and f.row_id for f in flags)
          and {f.row_id for f in flags} <= {r["id"] for r in counted})
    # S5 used to pin "no report is counted on a line AND on a point release" over the store, a fact no
    # scheduled step keeps true (review 2, item b). The page now DERIVES its sentence from the store on
    # every record write, so what is pinned is that each line page states the overlap the store shows.
    overlaps = drl.line_overlaps(rows)
    stated = []
    for path in sorted(base.GENERATED_DIR.glob("*.md")):
        head = path.read_text(encoding="utf-8", errors="replace").split("\n---", 1)[0]
        if "update_identity_scope: release_line" not in head:
            continue
        front = yaml.safe_load(head) or {}
        version = str(front.get("update_version") or "").strip()
        note = " ".join(str(front.get("record_note") or "").split())
        n = overlaps.get(version, 0)
        says_none = "No report counted here is also counted on an exact release's page" in note
        says_n = f"{n} of the reports counted here" in note
        stated.append((path.name, n, says_none if n == 0 else (says_n and not says_none)))
    check(f"S5 each release-line page states the overlap with exact releases that the store shows "
          f"({len(stated)} pages; {sum(overlaps.values())} shared rows)",
          stated and all(ok for _, _, ok in stated), str([s for s in stated if not s[2]]))
    lines = []
    for path in sorted(base.GENERATED_DIR.glob("*.md")):
        head = path.read_text(encoding="utf-8", errors="replace").split("\n---", 1)[0]
        if "update_identity_scope: release_line" in head:
            lines.append((path.name, "matched to this exact update" in head,
                          "name no point release" in head, "matched to this release line" in head))
    bad = [name for name, exact, denies, line in lines if exact or denies]
    check(f"S6 no release-line record says 'this exact update' or 'name no point release' ({len(lines)})",
          not bad, str(bad))
    check("S7 a release-line record with a 'no verdict yet' line says 'this release line'",
          all(line for name, exact, denies, line in lines
              if "No verdict yet" in (base.GENERATED_DIR / name).read_text(encoding="utf-8",
                                                                          errors="replace")),
          str([name for name, exact, denies, line in lines if not line]))

    print("X. the command")
    cli = str(SCRIPTS / "check_version_attribution.py")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "flags.json"
        ok = subprocess.run([sys.executable, cli, "--json", str(out)], capture_output=True, text=True)
        payload = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        check("X1 flags are a warning: exit 0, with the count stated",
              ok.returncode == 0 and "counted rows examined" in ok.stdout
              and payload.get("examined") == len(counted), ok.stdout[:200] + ok.stderr[-200:])
        missing = subprocess.run([sys.executable, cli, "--evidence-path", str(Path(tmp) / "none.yml")],
                                 capture_output=True, text=True)
        check("X2 an unreadable store is exit 2, never a pass", missing.returncode == 2,
              str(missing.returncode))
        flagged = Path(tmp) / "store.yml"
        base.write_evidence_file([{**row(report_title="Black screen since 32.2.0",
                                         report_text_excerpt="Black screen since 32.2.0."),
                                   "source_type": "github_issue", "source_name": "GitHub",
                                   "captured_at": "2026-01-01T00:00:00Z", "patch_version_matched": True,
                                   "matched_version": "32.1.2", "match_basis": "exact_version_text",
                                   "exclusion_reason": None, "source_weight": 1}], flagged)
        hit = subprocess.run([sys.executable, cli, "--evidence-path", str(flagged), "--github"],
                             capture_output=True, text=True)
        check("X3 a flagged row prints a ::warning:: and still exits 0",
              hit.returncode == 0 and "::warning::" in hit.stdout and "other_version_only" in hit.stdout,
              hit.stdout[-300:])

    print("=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
