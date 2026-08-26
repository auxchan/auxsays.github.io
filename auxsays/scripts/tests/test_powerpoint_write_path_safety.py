#!/usr/bin/env python3
"""Build-aware WRITE-PATH safety: a sibling build must never mutate another build's record.

THE DEFECT THIS LOCKS DOWN. ``_matching_existing_path`` looks for the exact build-aware filename
first, then falls back to scanning for any record with the same ``(product_id, update_version)``.
That fallback exists for a real reason -- the filename embeds the publication DATE, so a corrected
release date would otherwise create a duplicate record -- but it compared the version ALONE. For a
build-aware product that means an incoming sibling build resolved to a DIFFERENT build's record and
refreshed it: ``target_build`` advanced to the sibling's build while the filename and permalink
stayed on the original, leaving an internally inconsistent record whose declared build no longer
matched the evidence keyed to it.

Two guarantees are asserted here:

  1. IDENTITY -- for a build-aware product an incoming (product_id, update_version, target_build)
     may only refresh a record representing that exact triple. Non-build-aware products keep the
     version-based refresh semantics they have always had, date drift included.
  2. STRUCTURE -- a build-aware record whose target_build, canonical filename and canonical
     permalink disagree is refused before it can reach the canonical generated record, through the
     SAME rule the consensus lane already enforces (one definition, two lanes).

Offline and deterministic: every write goes to a temporary directory. The real repository is never
touched, and no generated record is created.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_write_path_safety.py
"""
from __future__ import annotations

import re
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402
from lib import patch_identity as pi  # noqa: E402
from lib import write_update_record as wur  # noqa: E402

PPT = "microsoft-powerpoint"
VERSION = "2607"
BUILD_A = "20228.20110"          # Candidate 1's build, July 23
BUILD_B = "20228.20190"          # the August 11 sibling
OBS = "obs-studio"

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


def ppt_record(build: str, date: str, note: str) -> dict:
    return {
        "company_id": "microsoft", "product_id": PPT, "software": "Microsoft PowerPoint",
        "version": VERSION, "update_version": VERSION, "target_build": build,
        "published_at": date, "title": f"Microsoft PowerPoint {VERSION} (Build {build})",
        "official_url": "https://learn.microsoft.com/en-us/officeupdates/current-channel",
        "release_notes_body": note, "official_source_type": "release_notes",
        "channel": "Current Channel", "target_channel": "Current Channel",
    }


def obs_record(version: str, date: str, note: str) -> dict:
    return {
        "company_id": "obs-project", "product_id": OBS, "software": "OBS Studio",
        "version": version, "update_version": version, "published_at": date,
        "title": f"OBS Studio {version}", "official_url": "https://obsproject.com/",
        "release_notes_body": note, "official_source_type": "release_notes",
    }


def front_of(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1]) or {}


def run() -> int:  # noqa: PLR0915
    print("=" * 74)
    print("Build-aware write-path safety")
    print("=" * 74)

    # ================= the corruption reproduction =================
    print("\n[repro] two real 2607 sibling builds written in order")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        p1, a1 = wur.write_record(out, ppt_record(BUILD_A, "2026-07-23T00:00:00Z", "July 23 notes"))
        print(f"    build {BUILD_A} -> {a1}  {p1.name}")

        second = ppt_record(BUILD_B, "2026-08-11T00:00:00Z", "August 11 notes")
        matched = wur._matching_existing_path(out, second)
        print(f"    _matching_existing_path for {BUILD_B} -> {matched.name if matched else None}")
        check("repro: the sibling does NOT resolve to the other build's record",
              matched is None or matched != p1,
              f"resolved to {matched.name if matched else None}")

        p2, a2 = wur.write_record(out, second)
        print(f"    build {BUILD_B} -> {a2}  {p2.name}")
        files = sorted(f.name for f in out.glob("*.md"))
        check("repro: TWO records exist", len(files) == 2, str(files))
        check("repro: the sibling was CREATED, not a refresh of its sibling", a2 == "created", a2)
        check("repro: the two records are different files", p1 != p2)

        f1, f2 = front_of(p1), front_of(p2)
        check(f"repro: {BUILD_A} record still declares {BUILD_A}",
              f1.get("target_build") == BUILD_A, str(f1.get("target_build")))
        check(f"repro: {BUILD_A} record's permalink still carries {BUILD_A}",
              f1.get("permalink", "").rstrip("/").endswith(BUILD_A), str(f1.get("permalink")))
        check(f"repro: {BUILD_A} filename still carries {BUILD_A}", BUILD_A.replace(".", "-") in p1.name)
        check(f"repro: {BUILD_B} record declares {BUILD_B}",
              f2.get("target_build") == BUILD_B, str(f2.get("target_build")))
        check(f"repro: {BUILD_B} permalink carries {BUILD_B}",
              f2.get("permalink", "").rstrip("/").endswith(BUILD_B), str(f2.get("permalink")))
        check(f"repro: {BUILD_B} filename carries {BUILD_B}", BUILD_B.replace(".", "-") in p2.name)
        check("repro: neither record mentions its sibling's build anywhere",
              BUILD_B not in p1.read_text(encoding="utf-8")
              and BUILD_A not in p2.read_text(encoding="utf-8"))
        check("repro: the first record's body was not replaced by the sibling's",
              "August 11" not in p1.read_text(encoding="utf-8"))
        check("repro: each record's permalink is unique",
              f1.get("permalink") != f2.get("permalink"))

    # ================= A: same (version, build) twice =================
    print("\n[A] the SAME (version, build) written twice refreshes, never duplicates")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        p1, a1 = wur.write_record(out, ppt_record(BUILD_A, "2026-07-23T00:00:00Z", "first"))
        p2, a2 = wur.write_record(out, ppt_record(BUILD_A, "2026-07-23T00:00:00Z", "first"))
        check("A first write creates", a1 == "created", a1)
        check("A second write does not create", a2 != "created", a2)
        check("A still exactly one record", len(list(out.glob("*.md"))) == 1)
        check("A the same file was reused", p1 == p2)
        # date drift on the SAME build must still resolve to the same record (the reason the
        # version-scan fallback exists at all).
        p3, a3 = wur.write_record(out, ppt_record(BUILD_A, "2026-07-24T00:00:00Z", "date corrected"))
        check("A publication-date drift still refreshes the same build's record",
              p3 == p1 and a3 != "created", f"{p3.name} {a3}")
        check("A date drift did not create a duplicate", len(list(out.glob("*.md"))) == 1)

    # ================= B: same version, different build =================
    print("\n[B] same version, different build -> a distinct record")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        wur.write_record(out, ppt_record(BUILD_A, "2026-07-23T00:00:00Z", "a"))
        wur.write_record(out, ppt_record(BUILD_B, "2026-08-11T00:00:00Z", "b"))
        wur.write_record(out, ppt_record("20228.20158", "2026-08-04T00:00:00Z", "c"))
        builds = sorted(front_of(f).get("target_build") for f in out.glob("*.md"))
        check("B three sibling builds -> three records", len(builds) == 3, str(builds))
        check("B each record keeps its own build",
              builds == sorted([BUILD_A, "20228.20158", BUILD_B]), str(builds))
        perms = {front_of(f).get("permalink") for f in out.glob("*.md")}
        check("B three distinct permalinks", len(perms) == 3, str(perms))

    # ================= C: build-aware, build missing =================
    print("\n[C] a build-aware record with no build fails closed")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        wur.write_record(out, ppt_record(BUILD_A, "2026-07-23T00:00:00Z", "a"))
        broken = ppt_record("", "2026-08-11T00:00:00Z", "no build")
        raised = ""
        try:
            wur.write_record(out, broken)
        except pi.MissingBuildIdentity as exc:
            raised = type(exc).__name__
        except Exception as exc:  # noqa: BLE001
            raised = f"other:{type(exc).__name__}"
        check("C it raises MissingBuildIdentity", raised == "MissingBuildIdentity", raised)
        check("C it did NOT fall back to the version-only match",
              len(list(out.glob("*.md"))) == 1
              and front_of(next(out.glob("*.md"))).get("target_build") == BUILD_A)
        check("C nothing new was written", len(list(out.glob("*.md"))) == 1)

    # ================= D: non-build-aware unchanged =================
    print("\n[D] a non-build-aware product keeps its existing refresh semantics")
    check("D obs-studio is not build-aware", not pi.is_build_aware(OBS))
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        p1, a1 = wur.write_record(out, obs_record("31.0.0", "2026-05-01T00:00:00Z", "first"))
        check("D first write creates", a1 == "created", a1)
        # SAME version, DIFFERENT publication date -> must refresh the same record, exactly as
        # before this change. This is the behaviour the version-scan fallback exists to provide.
        p2, a2 = wur.write_record(out, obs_record("31.0.0", "2026-05-09T00:00:00Z", "date drift"))
        check("D same version + date drift refreshes the SAME record",
              p2 == p1 and a2 != "created", f"{p2.name} {a2}")
        check("D no duplicate was created", len(list(out.glob("*.md"))) == 1)
        p3, a3 = wur.write_record(out, obs_record("31.0.1", "2026-05-20T00:00:00Z", "next"))
        check("D a different version still creates its own record",
              a3 == "created" and p3 != p1, f"{p3.name} {a3}")
        check("D two OBS records now exist", len(list(out.glob("*.md"))) == 2)
        check("D no OBS permalink carries a build segment",
              all(pi.permalink_build_segment(front_of(f).get("permalink") or "") == ""
                  for f in out.glob("*.md")))
        # A stray target_build on a non-build-aware record must not re-key it.
        stray = obs_record("31.0.1", "2026-05-20T00:00:00Z", "next")
        stray["target_build"] = "99999.99999"
        p4, a4 = wur.write_record(out, stray)
        check("D a stray target_build does not re-key a non-build-aware product",
              p4 == p3 and a4 != "created", f"{p4.name} {a4}")
        check("D still two OBS records", len(list(out.glob("*.md"))) == 2)

    # ================= E: pre-existing inconsistent record =================
    print("\n[E] an already-inconsistent build-aware record is REFUSED, not refreshed")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        p1, _ = wur.write_record(out, ppt_record(BUILD_A, "2026-07-23T00:00:00Z", "a"))
        # Corrupt it on disk exactly the way the old fallback would have: declared build advances
        # while filename and permalink stay behind.
        text = p1.read_text(encoding="utf-8")
        p1.write_text(re.sub(r"^target_build:.*$", f"target_build: '{BUILD_B}'", text,
                             flags=re.M), encoding="utf-8")
        before = p1.read_text(encoding="utf-8")
        raised = ""
        try:
            wur.refresh_existing_record(p1, ppt_record(BUILD_B, "2026-08-11T00:00:00Z", "b"))
        except pi.InconsistentBuildIdentity as exc:
            raised = exc.reason
        except Exception as exc:  # noqa: BLE001
            raised = f"other:{type(exc).__name__}"
        check("E the inconsistency is detected",
              raised == pi.REASON_PERMALINK_BUILD_MISMATCH, raised)
        check("E the corrupt record was not rewritten", p1.read_text(encoding="utf-8") == before)
        reason = pi.build_identity_reason(PPT, VERSION, BUILD_B,
                                          f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_A}/", p1.name)
        check("E the shared rule names the same reason",
              reason == pi.REASON_PERMALINK_BUILD_MISMATCH, reason)

    # ================= F: a newly produced inconsistent record =================
    print("\n[F] a newly produced inconsistent record cannot be written or reported as success")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        # The create path DERIVES both the filename slug and the permalink from the one identity,
        # so a caller-supplied bad permalink is recomputed and cannot corrupt the record. Prove
        # that rather than assume it: an attacker-shaped permalink is simply overwritten.
        bad = ppt_record(BUILD_B, "2026-08-11T00:00:00Z", "b")
        bad["permalink"] = f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_A}/"
        path, action = wur.write_record(out, bad)
        f = front_of(path)
        check("F a caller-supplied wrong permalink is recomputed, not trusted",
              (f.get("permalink") or "").rstrip("/").endswith(BUILD_B), str(f.get("permalink")))
        check("F the derived record is internally consistent",
              pi.build_identity_reason(PPT, VERSION, f.get("target_build"),
                                       f.get("permalink"), path.name) == "")
        check("F it was created normally", action == "created", action)

        # And the gate itself refuses a hand-assembled inconsistent record before any write,
        # which is what protects every future caller that assembles front matter elsewhere.
        raised = ""
        try:
            wur._assert_record_consistent(
                out / f"2026-08-11-microsoft-powerpoint-{VERSION}-20228-20110.md",
                {"product_id": PPT, "update_version": VERSION, "target_build": BUILD_B,
                 "permalink": f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_B}/"})
        except pi.InconsistentBuildIdentity as exc:
            raised = exc.reason
        check("F the gate refuses a filename that disagrees with the build",
              raised == pi.REASON_FILENAME_BUILD_MISMATCH, raised)
        raised = ""
        try:
            wur._assert_record_consistent(
                out / f"2026-08-11-microsoft-powerpoint-{VERSION}-20228-20190.md",
                {"product_id": PPT, "update_version": VERSION, "target_build": BUILD_B,
                 "permalink": f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_A}/"})
        except pi.InconsistentBuildIdentity as exc:
            raised = exc.reason
        check("F the gate refuses a permalink that disagrees with the build",
              raised == pi.REASON_PERMALINK_BUILD_MISMATCH, raised)
        raised = ""
        try:
            wur._assert_record_consistent(
                out / "2026-08-11-microsoft-powerpoint-2607.md",
                {"product_id": PPT, "update_version": VERSION, "target_build": "",
                 "permalink": f"/updates/microsoft/{PPT}/{VERSION}/"})
        except pi.InconsistentBuildIdentity as exc:
            raised = exc.reason
        check("F the gate refuses a build-aware record with no build",
              raised == pi.REASON_BUILD_MISSING, raised)
        check("F only the one legitimate record exists",
              len(list(out.glob("*.md"))) == 1, str(sorted(p.name for p in out.glob("*.md"))))

    print("\n[F2] the failure cannot poison the seen ledger")
    # write -> mark_seen ordering: mark_seen is only reached after write_record returns, so a
    # refused write leaves the identity unseen and therefore retryable.
    src = (_REPO / "auxsays" / "scripts" / "patch_ingest.py").read_text(encoding="utf-8")
    # ORDER, not adjacency: other work may legitimately sit between the write and the ledger
    # update (version-landing generation does). What must never change is that mark_seen cannot be
    # reached unless write_record returned, so a refused write leaves the identity retryable.
    write_at = src.find("path, action = write_record(")
    seen_at = src.find("mark_seen(state, product_id, record_id)")
    check("F2 mark_seen runs strictly AFTER write_record returns",
          write_at != -1 and seen_at != -1 and write_at < seen_at,
          "the write/seen ordering changed -- re-audit before trusting retry")
    between = src[write_at:seen_at]
    check("F2 nothing between the write and the ledger can swallow the failure",
          "try" not in between and "except" not in between,
          f"a try/except appeared between write_record and mark_seen: {between!r}")
    from lib import state as st  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        ledger: dict = {}
        rid = "microsoft-powerpoint:build-less-record"
        raised = ""
        # Execute the production sequence verbatim: write_record, then mark_seen on the next line.
        try:
            wur.write_record(out, ppt_record("", "2026-08-11T00:00:00Z", "no build"))
            st.mark_seen(ledger, PPT, rid)
        except (pi.MissingBuildIdentity, pi.InconsistentBuildIdentity) as exc:
            raised = type(exc).__name__
        check("F2 the refused write raises out of the record loop", raised != "", raised)
        check("F2 the identity was NOT marked seen, so the next run retries it",
              not st.is_seen(ledger, PPT, rid))
        check("F2 no partial record was left behind",
              list(out.glob("*.md")) == [], str(list(out.glob("*.md"))))
    check("F2 the exception carries a diagnosable reason",
          pi.InconsistentBuildIdentity(pi.REASON_BUILD_MISSING, "d").reason == pi.REASON_BUILD_MISSING)
    # The per-source handler marks the source ERRORED (never successful) when run_source raises.
    check("F2 a raising source is recorded as an error, not a success",
          "update_source_error(" in src
          and src.index("except Exception as exc:") < src.index("update_source_error("))

    # ================= shared rule: one definition, two lanes =================
    print("\n[shared] the consensus lane and the official lane use ONE rule")
    from lib import collector_ownership as own  # noqa: PLC0415
    check("shared: ownership delegates build-segment extraction to the identity authority",
          own._permalink_build_segment(f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_A}/")
          == pi.permalink_build_segment(f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_A}/")
          == BUILD_A)
    for perm, build, expect in [
        (f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_A}/", BUILD_A, ""),
        (f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_A}/", BUILD_B,
         pi.REASON_PERMALINK_BUILD_MISMATCH),
        (f"/updates/microsoft/{PPT}/{VERSION}/", BUILD_A, pi.REASON_PERMALINK_BUILD_MISMATCH),
        (f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_A}/", "", pi.REASON_BUILD_MISSING),
    ]:
        got = pi.build_identity_reason(PPT, VERSION, build, perm)
        check(f"shared: {perm.split('/')[-2] or 'version-only'} + build {build or '(none)'} -> "
              f"{expect or 'OK'}", got == expect, got)
    check("shared: a non-build-aware product with a build segment is refused",
          pi.build_identity_reason(OBS, "31.0.0", "", "/updates/obs-project/obs-studio/31-0-0/9.9/")
          == pi.REASON_PERMALINK_BUILD_UNEXPECTED)
    check("shared: a non-build-aware product with a clean permalink is fine",
          pi.build_identity_reason(OBS, "31.0.0", "", "/updates/obs-project/obs-studio/31-0-0/") == "")
    check("shared: filename disagreement is caught too",
          pi.build_identity_reason(PPT, VERSION, BUILD_B,
                                   f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_B}/",
                                   f"2026-08-11-microsoft-powerpoint-{VERSION}-20228-20110.md")
          == pi.REASON_FILENAME_BUILD_MISMATCH)
    check("shared: a matching filename passes",
          pi.build_identity_reason(PPT, VERSION, BUILD_B,
                                   f"/updates/microsoft/{PPT}/{VERSION}/{BUILD_B}/",
                                   f"2026-08-11-microsoft-powerpoint-{VERSION}-20228-20190.md") == "")

    # ================= I: Candidate 1 =================
    print("\n[I] Candidate 1's identity is untouched by all of this")
    live = sorted((_REPO / "auxsays" / "updates" / "generated").glob("*powerpoint*2607*.md"))
    check("I exactly one live 2607 record today", len(live) == 1, str([p.name for p in live]))
    if live:
        f = front_of(live[0])
        check(f"I it declares {BUILD_A}", f.get("target_build") == BUILD_A, str(f.get("target_build")))
        check(f"I its permalink carries {BUILD_A}",
              (f.get("permalink") or "").rstrip("/").endswith(BUILD_A), str(f.get("permalink")))
        check("I filename, permalink and target_build all agree",
              pi.build_identity_reason(PPT, str(f.get("update_version")),
                                       str(f.get("target_build")), str(f.get("permalink")),
                                       live[0].name) == "",
              pi.build_identity_reason(PPT, str(f.get("update_version")),
                                       str(f.get("target_build")), str(f.get("permalink")),
                                       live[0].name))
        check("I it still carries its counted report", int(f.get("update_report_count") or 0) >= 1,
              str(f.get("update_report_count")))

    print()
    print("=" * 74)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 74)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
