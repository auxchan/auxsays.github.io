#!/usr/bin/env python3
"""G84 (G82-B1): one validation contract for every verdict reason.

THE DEFECTS (G82 T2_DECISION_PATH.md sections 1b, 3 and 6; G78 D1_SHADOW.md):
  * H-1, the activation bypass. With PUBLIC_AUTO_ACTIVATION on, lib/verdict_projection merged every producer
    candidate behind the reviewed entries with no reviewed check: no schema, no WAIT facts, no
    support_problems. decide's own precondition ("valid_reasons must already be the entries SUPPORTED by the
    page's counted rows") was broken, and a Windows vendor WAIT citing 0 counted rows reached a page.
  * H-2, the user class. `_candidate` gave a user-corroboration candidate the VENDOR reason class, and
    `candidate_problems` held only the install class to the reporter minimum.
  * D-1, the official confirmation. `support_problems` and the record writer looked the confirming record up
    by (product, version, ""), so on Windows and PowerPoint, whose every record carries a build, a TRUE
    confirmation made a supported entry unsupported.

WHAT THIS PINS. [H1] every candidate meets `verdict_reasons.machine_schema_errors` (the reviewed schema and every
WAIT fact; basis automatic:<rule version>) and `support_problems` before decide may read it, at BOTH call sites
(the projection's `supported_reasons`, the writers' `page_supported_reasons`); a refused one is listed with the
unsupported entries; the reviewed path is unchanged; QA rejects a projection that carries a refused candidate.
[H2] the class mapping and the reporter minimum for every user class. [D1] the confirmation keyed on the full
identity, monotonic, blank-build products exactly as before, the writer path too. [N] the switch stays OFF.
[X] one in-suite mutant per fix site (pre-G84 copies of the changed functions), each caught by a named check.

FOR G79 (its "D1 bypass safety fixture"). `bypass_fixture()` is the activation-bypass case on its own records,
and `activation_view()` runs the shipped path with the switch forced ON in memory (restored after). Since G84 a
fixture like this one must EXPECT: the candidate is produced, it is ABSENT from the merged reasons, the writer
path and the projection, and it is PRESENT in the unsupported list with its schema problems; the projection
equals the switch-OFF projection. A guard "the switch is on while the bypass exists" then has nothing left to
guard; the switch-OFF pin (VRP-S0, RVC-N1) stays.

Offline; writes only in a temp dir; PUBLIC_AUTO_ACTIVATION is never changed on disk.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_reason_validation_contract.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import re
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Mapping

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
sys.path.insert(0, str(_AUX / "scripts"))

import yaml  # noqa: E402

from lib import evidence_facts as ef  # noqa: E402
from lib import patch_decision as pd  # noqa: E402
from lib import verdict_projection as vp  # noqa: E402
from lib import verdict_reason_producer as vrp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402

PRODUCER_PATH = _AUX / "scripts" / "lib" / "verdict_reason_producer.py"
WIN, OBS, PPT, PRO = "microsoft-windows-11", "obs-studio", "microsoft-powerpoint", "adobe-acrobat-pro"
EM = "—"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: Any, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


@contextlib.contextmanager
def captured():
    global _PASS, _FAIL, _ERRORS
    saved = (_PASS, _FAIL, _ERRORS)
    _PASS, _FAIL, _ERRORS = 0, 0, []
    failures: list[str] = []
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield failures
    finally:
        failures.extend(_ERRORS)
        _PASS, _FAIL, _ERRORS = saved


@contextlib.contextmanager
def switch(on: bool):
    """PUBLIC_AUTO_ACTIVATION forced in process memory only, always restored."""
    saved = vrp.PUBLIC_AUTO_ACTIVATION
    vrp.PUBLIC_AUTO_ACTIVATION = on
    try:
        yield
    finally:
        vrp.PUBLIC_AUTO_ACTIVATION = saved


# ------------------------------------------------------------------------ fixtures

def win(line, build, kb, published, body="", update_type="2026-09 D", count=0, **over):
    r = {"update_entry": True, "product_id": WIN, "update_version": line, "target_build": build, "target_kb": kb,
         "target_feature_version": line, "update_type": update_type, "update_published_at": published,
         "permalink": f"/updates/microsoft/microsoft-windows-11/{line.lower()}/{build}/",
         "official_patch_notes_body": body, "update_report_count": count}
    r.update(over)
    return r


def obs(version, notes="", count=0):
    return {"update_entry": True, "product_id": OBS, "update_version": version,
            "permalink": f"/updates/obs-project/obs-studio/{version.replace('.', '-')}/",
            "official_patch_notes_body": notes, "update_report_count": count}


def row(rid, url, title, excerpt, **over):
    """A counted row as the persistence boundary writes it: with its structured evidence facts (G68), which
    the distinct-reporter rule reads instead of the excerpt text."""
    r = {"id": rid, "source_url": url, "report_title": title, "report_text_excerpt": excerpt}
    r.update(over)
    return ef.with_facts(r)


def cites(rows):
    return [{"id": r["id"], "source_url": r["source_url"]} for r in rows]


# The activation bypass on its own records (G79 reuses this). Microsoft's release-health roll-up, stored on a
# later record, names 24H2 26100.9550 as the originating build of a Remote Desktop known issue; the producer
# drafts "WAIT for non-admin users ..." on that page citing NO counted row -- the shape of the corpus's Windows
# candidates (G78 D1 shadow C2/C4: 26200.9550 carries 12 counted reports, none cited). Before G84 the switch-ON
# path merged it and the page read WAIT.
HEADER_24H2 = ("Microsoft Release Health status (official) for Windows 11 24H2: 1 active known issue(s), 0 resolved, "
               "0 safeguard hold(s). Source: official Microsoft Windows release-health status page. This is "
               "vendor-published operational status, not user reports.")
RDP_24H2 = (f"- Active: Remote Desktop connections might fail for non-admin users with error 0xC000000D This issue "
            f"affects non-admin users connecting through Remote Desktop with Administrator protection enabled. {EM} "
            "status Mitigated; originating OS Build 26100.9550 KB5124010; last updated 2026-10-13 10:13 PT.")
BYPASS_PAGE = win("24H2", "26100.9550", "KB5124010", "2026-09-22T00:00:00Z", count=2)
BYPASS_ROLLUP = win("24H2", "26100.9725", "KB5134133", "2026-10-26T00:00:00Z",
                    "Base text.\n\n" + "\n".join([HEADER_24H2, RDP_24H2]), update_type="2026-10 OOB")
BYPASS_ROWS = [
    row("b-1", "https://learn.test/q/b1", "Start menu will not open after KB5124010",
        "Since KB5124010 the Start menu does not open on my Surface."),
    row("b-2", "https://learn.test/q/b2", "Taskbar flickers after the September preview",
        "The taskbar flickers every few seconds after the September preview update on my desktop."),
]


def bypass_fixture() -> tuple[list[dict], dict]:
    """(records, counted rows per identity): one page the producer gives a WAIT candidate that cites no counted
    row, so the reviewed checks refuse it. Fresh copies on every call."""
    return ([copy.deepcopy(BYPASS_PAGE), copy.deepcopy(BYPASS_ROLLUP)],
            {vr.record_identity(BYPASS_PAGE): copy.deepcopy(BYPASS_ROWS)})


def activation_view(records: list, counted: Mapping, reasons: list = (), lifecycle: list = ()) -> dict:
    """The shipped path with the switch forced ON in memory (restored after): what was produced, what decide
    reads per page (projection site and writer site), what was refused, and the projections ON and OFF."""
    reasons, lifecycle = list(reasons or ()), list(lifecycle or ())
    produced = vrp.produce(records, counted)
    off = vp.project(records, counted, reasons, lifecycle)[0]
    by_ident = {vr.record_identity(r): r for r in records}
    reviewed_valid, _u = vr.valid_reasons_by_identity(reasons, counted, by_ident)
    with switch(True):
        merged, unsupported = vp.supported_reasons(records, counted, reasons)
        on = vp.project(records, counted, reasons, lifecycle)[0]
        writer = {vp.page_key(r): [str(e.get("id")) for e in vp.page_supported_reasons(
            r, counted.get(vr.record_identity(r), []), reviewed_valid.get(vr.record_identity(r), []), records)]
                  for r in records}
    return {"candidates": [c["id"] for c in produced.candidates], "produced": produced.candidates,
            "merged": {"|".join(k): [str(e.get("id")) for e in v] for k, v in merged.items()},
            "unsupported": unsupported, "writer": writer, "on": on, "off": off}


# A candidate that PASSES the contract: two counted reports of one specific installer error from two different
# machines (a Mac and Windows 10) on an Acrobat Pro page -- test_verdict_reason_producer VRP-I3's Pro rows.
ACRO = {"update_entry": True, "product_id": PRO, "update_version": "15.099.20001",
        "permalink": "/updates/adobe/adobe-acrobat-pro/15-099-20001/", "update_report_count": 2}
ACRO_ROWS = [
    row("a-11", "https://community.test/t/11", "Acrobat DC install fails on my Mac",
        "Acrobat DC install fails with Exit Code: 7 on El Capitan 10.11.3, the Creative Cloud app shows an error. "
        "ERROR: DW003", applicability="adobe-acrobat-reader,adobe-acrobat-pro"),
    row("a-12", "https://community.test/t/12", "Cannot install Acrobat Pro DC on Windows 10",
        "I'm on Windows 10. The installer stops with Exit Code: 7 after the extraction step. For example, ERROR: DW003",
        applicability="adobe-acrobat-reader,adobe-acrobat-pro"),
]


def mixed_fixture() -> tuple[list[dict], dict]:
    recs, counted = bypass_fixture()
    recs.append(copy.deepcopy(ACRO))
    counted[vr.record_identity(ACRO)] = copy.deepcopy(ACRO_ROWS)
    return recs, counted


# A page for hand-built machine entries: two counted reports at different URLs with different text.
PROBE = obs("9.1.0", count=3)
PROBE_ROWS = [
    row("p-1", "https://github.test/i/1", "Capture source black", "The probe capture source shows a black screen."),
    row("p-2", "https://forum.test/t/2", "Black capture after update", "After updating, my probe capture is black."),
    row("p-3", "https://forum.test/t/3", "Audio drift", "Audio drifts after ten minutes of recording."),
]
PROBE_COUNTED = {vr.record_identity(PROBE): PROBE_ROWS}


def user_candidate(page=PROBE, rows=PROBE_ROWS[:2], **over) -> dict:
    """A user-corroboration candidate exactly as the producer's `_candidate` shapes it (H-2's class)."""
    c = vrp._candidate(vrp.USER_CLASS, page, verdict="TEST FIRST", scope="if you use the probe capture source",
                       reason="Two users independently report that the probe capture source shows a black screen.",
                       severity="substantial_workflow_breakage", failure="the capture source shows a black screen",
                       new=False, fixed_in="", citation={}, inputs={"rows_sha256": "0" * 64},
                       problem_key="probe black screen", evidence=cites(rows))
    c.update(over)
    return c


def reviewed_shape(machine: dict) -> dict:
    """The same reason as a reviewed file entry: review fields in, producer provenance out."""
    e = {k: v for k, v in machine.items() if k not in vr.MACHINE_PROVENANCE_KEYS}
    e.update(reviewed_at="2026-11-21", basis="probe")
    return e


# D-1 fixtures: build-keyed Windows and PowerPoint pages, a blank-build OBS pair.
WIN_D1 = win("25H2", "26200.8117", "KB5099117", "2026-03-24T00:00:00Z",
             "Base text.\nThis update improves the reliability of the Remote Desktop client.\n"
             "It also fixes an issue that affects printing.", update_type="2026-03 D", count=2)
WIN_D1_ROWS = [row("w-1", "https://learn.test/q/w1", "KB5099117 fails to install", "KB5099117 fails with 0x800f0991."),
               row("w-2", "https://learn.test/q/w2", "Update will not install", "The March preview will not install.")]
WIN_STATEMENT = "This update improves the reliability of the Remote Desktop client."
WIN_ENTRY = {"id": "microsoft-windows-11:25H2:26200.8117:probe", "product_id": WIN, "update_version": "25H2",
             "target_build": "26200.8117", "verdict": "TEST FIRST", "reason_class": "corroborated_install_problem",
             "scope": "when installing it", "reason": "Two users independently report that this update fails to install.",
             "evidence": cites(WIN_D1_ROWS), "new_in_this_version": False, "reviewed_at": "2026-11-10",
             "basis": "G84 D-1 probe"}
PPT_D1 = {"update_entry": True, "product_id": PPT, "update_version": "2510", "target_build": "19328.20190",
          "official_patch_notes_body": "Version 2510 (Build 19328.20190)\nFixed an issue where slide transitions "
                                       "stopped playing in Presenter View.", "update_report_count": 2}
PPT_ROWS = [row("pp-1", "https://answers.test/1", "Transitions stop", "Slide transitions stop in Presenter View."),
            row("pp-2", "https://answers.test/2", "Presenter view broken", "In presenter view the transitions freeze.")]
PPT_ENTRY = {"id": "microsoft-powerpoint:2510:19328.20190:probe", "product_id": PPT, "update_version": "2510",
             "target_build": "19328.20190", "verdict": "TEST FIRST", "reason_class": "corroborated_issue",
             "scope": "if you use Presenter View", "reason": "Two users report that slide transitions stop in Presenter View.",
             "evidence": cites(PPT_ROWS), "new_in_this_version": False, "reviewed_at": "2026-11-10", "basis": "probe"}
PPT_STATEMENT = "Fixed an issue where slide transitions stopped playing in Presenter View."
OBS_FIX = obs("33.0.0", "## OBS Studio 33.0.0 Changes\r\n* Fixed a crash on macOS 27.2 when starting OBS Studio [PatTheMav]")
OBS_PAGE = obs("32.2.2", count=2)
OBS_ROWS = [row("o-1", "https://github.test/o/1", "Crash on launch", "OBS crashes on every launch on macOS 27.2."),
            row("o-2", "https://forum.test/o/2", "Will not start", "Since 32.2.2 OBS will not start on my Mac.")]
OBS_ENTRY = {"id": "obs-studio:32.2.2:probe", "product_id": OBS, "update_version": "32.2.2", "verdict": "TEST FIRST",
             "reason_class": "corroborated_issue", "scope": "if you use macOS 27.2",
             "reason": "Two users report that OBS crashes on launch on macOS 27.2.", "evidence": cites(OBS_ROWS),
             "new_in_this_version": False, "reviewed_at": "2026-11-10", "basis": "probe"}
OBS_STATEMENT = "Fixed a crash on macOS 27.2 when starting OBS Studio"
D1_RECORDS = [WIN_D1, PPT_D1, OBS_FIX, OBS_PAGE]
D1_BY_IDENT = {vr.record_identity(r): r for r in D1_RECORDS}


def conf(entry, statement, **over):
    c = {"product_id": entry["product_id"], "update_version": entry["update_version"], "statement": statement}
    if entry.get("target_build"):
        c["target_build"] = entry["target_build"]
    c.update(over)
    return c


def with_conf(entry, c):
    e = copy.deepcopy(entry)
    e["official_confirmation"] = c
    return e


# ------------------------------------------------------------------------ pre-G84 copies (the mutants' bodies)

def supported_reasons_pre_g84(records, counted_by_identity, reasons):
    records = [r for r in records if isinstance(r, Mapping)]
    by_identity = {vr.record_identity(r): r for r in records}
    valid, unsupported = vr.valid_reasons_by_identity(list(reasons or ()), counted_by_identity, by_identity)
    if vrp.PUBLIC_AUTO_ACTIVATION:
        produced = vrp.produce(records, counted_by_identity)
        valid = vrp.merge(valid, produced.candidates)
    return valid, unsupported


def page_supported_reasons_pre_g84(page, rows, reviewed_valid, records=()):
    reviewed = [dict(e) for e in reviewed_valid or ()]
    if not vrp.PUBLIC_AUTO_ACTIVATION:
        return reviewed
    pool = [r for r in (records() if callable(records) else records or ()) if isinstance(r, Mapping)]
    ident = vr.record_identity(page)
    if not any(vr.record_identity(r) == ident for r in pool):
        pool.append(dict(page))
    produced = vrp.produce(pool, {ident: list(rows or ())})
    mine = [c for c in produced.candidates if vr.reason_identity(c) == ident]
    return vrp.merge({ident: reviewed}, mine).get(ident, [])


def support_problems_pre_g84(entry, counted_rows, records_by_identity):
    """verdict_reasons.support_problems as main had it just before G84 (after G68's excerpt fact)."""
    problems = []
    by_id = {vr._s(r.get("id")): r for r in counted_rows}
    cited = []
    for item in entry.get("evidence") or []:
        r = by_id.get(vr._s(item.get("id")))
        if r is None:
            problems.append(f"row {item.get('id')!r} is not counted on this page")
            continue
        if vr._s(r.get("source_url")) != vr._s(item.get("source_url")):
            problems.append(f"row {item.get('id')!r} source_url differs from the counted row")
            continue
        cited.append(r)
    urls = {vr._s(r.get("source_url")) for r in cited}
    excerpts = set()
    for r in cited:
        try:
            key = ef.duplicate_group_key(r)
        except ef.FactUnavailable as exc:
            problems.append(f"row {r.get('id')!r}: {exc}")
            continue
        if key is not None:
            excerpts.add(key)
    reporters = min(len(urls), len(excerpts) if excerpts else len(urls))
    c = entry.get("official_confirmation")
    if c:
        rec = records_by_identity.get((vr._s(c.get("product_id")), vr._s(c.get("update_version")), ""))
        body = vr._norm_ws((rec or {}).get("official_patch_notes_body"))
        if not rec or vr._norm_ws(c.get("statement")) not in body:
            problems.append("official confirmation is not found in the named record's captured official notes")
    needed = 1 if c else 2
    if reporters < needed:
        problems.append(f"{reporters} distinct counted reporter(s); {needed} required")
    return problems


def confirmation_records_pre_g84(acr):
    def old(entries):
        wanted = {(str((e.get("official_confirmation") or {}).get("product_id") or "").strip(),
                   str((e.get("official_confirmation") or {}).get("update_version") or "").strip(), "")
                  for e in entries if e.get("official_confirmation")}
        found = {}
        if not wanted:
            return found
        for path in sorted(acr.GENERATED_DIR.glob("*.md")):
            data = acr._load_front_matter(path)
            ident = vr.record_identity(data)
            if data.get("update_entry") and ident in wanted:
                found[ident] = data
        return found
    return old


# ------------------------------------------------------------------------ [H1] one contract for every reason

def check_bypass_closed() -> None:
    recs, counted = bypass_fixture()
    view = activation_view(recs, counted)
    key = vp.page_key(BYPASS_PAGE)
    cands = [c for c in view["produced"] if vr.reason_identity(c) == vr.record_identity(BYPASS_PAGE)]
    cid = cands[0]["id"] if cands else ""
    # Non-vacuity: the pre-G84 merge (no reviewed check) puts the candidate on the page as WAIT.
    old = vrp.merge({}, view["produced"]).get(vr.record_identity(BYPASS_PAGE), [])
    old_verdict = pd.decide(dict(BYPASS_PAGE), valid_reasons=old).verdict
    problems = view["unsupported"].get(cid, [])
    check("RVC-H1a THE BYPASS IS CLOSED (switch forced ON in memory; the fixture G79 reuses): the producer drafts a "
          "Windows vendor WAIT citing no counted row, which the pre-G84 merge put on the page as WAIT; now it is in "
          "no page's merged reasons, not in the writer path, not in the projection (the page stays INSUFFICIENT "
          "DATA and the ON projection equals the OFF one), and it is listed as unsupported with its schema "
          "problems (no counted evidence, no regression facts)",
          len(cands) == 1 and cands[0]["verdict"] == "WAIT" and not cands[0]["evidence"] and old_verdict == "WAIT"
          and all(cid not in ids for ids in view["merged"].values()) and cid not in view["writer"].get(key, [])
          and key not in view["on"]["pages"] and view["on"] == view["off"]
          and any("evidence must list the counted rows" in p for p in problems)
          and any("WAIT requires reason_class regression" in p for p in problems)
          and vrp.PUBLIC_AUTO_ACTIVATION is False,
          f"cands={[c['id'] for c in cands]} old={old_verdict} merged={view['merged']} writer={view['writer'].get(key)} "
          f"on={list(view['on']['pages'])} problems={problems}")


def check_machine_schema() -> None:
    recs, counted = mixed_fixture()
    install = [c for c in vrp.produce(recs, counted).candidates if c["producer"]["class"] == vrp.INSTALL_CLASS]
    cand = install[0] if install else {}
    reviewed_view = vr.schema_errors([cand]) if cand else ["no candidate"]
    check("RVC-H1b the machine schema reads a candidate EXACTLY as the producer wrote it: the Acrobat install "
          "candidate (two counted reports) has no machine-schema problem, while the reviewed schema refuses the same "
          "dict only for what a person adds (reviewed_at, basis) -- the two differ in the review fields alone",
          cand and vr.machine_schema_errors([cand]) == [] and vr.machine_basis(cand) == f"automatic:{vrp.PRODUCER_VERSION}"
          and reviewed_view == [f"{cand.get('id')}: missing ['reviewed_at', 'basis']"],
          f"{vr.machine_schema_errors([cand]) if cand else 'no candidate'} {reviewed_view}")
    base = user_candidate()
    no_version = copy.deepcopy(base)
    no_version["producer"] = {"class": vrp.USER_CLASS, "inputs": {}}
    bad_version = copy.deepcopy(base)
    bad_version["producer"]["version"] = "5 beta"
    no_producer = {k: v for k, v in base.items() if k != "producer"}
    claims_review = dict(base, reviewed_at="2026-11-21")
    wrong_basis = dict(base, basis="reviewed by hand")
    right_basis = dict(base, basis=f"automatic:{vrp.PRODUCER_VERSION}")
    errs = {n: vr.machine_schema_errors([e]) for n, e in (
        ("no_version", no_version), ("bad_version", bad_version), ("no_producer", no_producer),
        ("claims_review", claims_review), ("wrong_basis", wrong_basis), ("right_basis", right_basis))}
    check("RVC-H1c an automatic reason must name the rule version that drafted it (basis automatic:<rule version>, "
          "from its producer block): no producer, no version or a malformed one is refused; a stated basis must equal "
          "it; a machine entry may not claim a review date; a value that is not a mapping is refused, never read",
          vr.machine_schema_errors([base]) == [] and errs["right_basis"] == []
          and any("rule version that drafted it" in p for p in errs["no_version"])
          and any("rule version that drafted it" in p for p in errs["bad_version"])
          and errs["no_producer"] == [f"{base['id']}: missing ['producer']"]
          and any("unknown keys ['reviewed_at']" in p for p in errs["claims_review"])
          and any("is not 'automatic:" in p for p in errs["wrong_basis"])
          and vr.machine_schema_errors(["not a mapping"]) == ["entries[0]: not a mapping"], str(errs))
    # The same checks: every reviewed-schema rule that is not about the review gives the SAME message on the same
    # reason, whether a person or the producer wrote it.
    variants = {
        "verdict": dict(verdict="AVOID"), "class": dict(reason_class="vendor_confirmed_serious"),
        "scope": dict(scope="if you use x: y"), "reason": dict(reason="a\nb"), "new": dict(new_in_this_version="yes"),
        "no evidence": dict(evidence=[]), "evidence item": dict(evidence=[{"id": "p-1"}]),
        "confirmation": dict(official_confirmation={"product_id": OBS, "update_version": "9.2.0"}),
        "confirmation build": dict(official_confirmation={"product_id": OBS, "update_version": "9.2.0",
                                                          "target_build": 26200.811, "statement": "s"}),
        "wait facts": dict(verdict="WAIT"), "regression not new": dict(reason_class="regression"),
        "empty identity": dict(product_id=" "),
    }
    differ = {}
    for name, over in variants.items():
        machine = dict(base, **over)
        a, b = vr.machine_schema_errors([machine]), vr.schema_errors([reviewed_shape(machine)])
        if a != b or not a:
            differ[name] = (a, b)
    check("RVC-H1d ONE contract: on every rule that is not about the review -- verdict, reason class, scope, the "
          "one-line reason, new_in_this_version, the cited evidence, the official confirmation's shape and build, "
          "every WAIT fact, regression-means-new, an empty identity -- a candidate gets exactly the message a "
          "reviewed entry gets for the same reason", not differ, str(differ)[:400])


# The reviewed path is unchanged: these are the messages the PRE-G84 schema_errors gave (frozen from b64fa539).
_REVIEWED_BASE = {"id": "p:1.0:probe", "product_id": "p", "update_version": "1.0", "verdict": "TEST FIRST",
                  "reason_class": "corroborated_issue", "scope": "if you use the probe",
                  "reason": "Two users report the probe fails.",
                  "evidence": [{"id": "r1", "source_url": "https://x.test/1"}, {"id": "r2", "source_url": "https://x.test/2"}],
                  "new_in_this_version": False, "reviewed_at": "2026-11-01", "basis": "probe"}
_L = "p:1.0:probe: "
REVIEWED_FROZEN = [
    ({}, []),
    ({"basis": ...}, [_L + "missing ['basis']"]),
    ({"reviewed_at": ...}, [_L + "missing ['reviewed_at']"]),
    ({"producer": {"class": "x", "version": "5"}}, [_L + "unknown keys ['producer']"]),
    ({"verdict": "AVOID"}, [_L + "verdict 'AVOID' is not one of ('WAIT', 'TEST FIRST')"]),
    ({"reason_class": "vendor_confirmed_serious"}, [_L + "reason_class 'vendor_confirmed_serious' is not one of "
                                                    "('regression', 'corroborated_issue', 'corroborated_install_problem')"]),
    ({"scope": "if you use x: y"}, [_L + "scope must read 'if ...', 'when ...' or 'for ...' without a colon or a final period"]),
    ({"reason": "a\nb"}, [_L + "reason must be one public line (1-320 characters)"]),
    ({"new_in_this_version": "yes"}, [_L + "new_in_this_version must be true or false"]),
    ({"reviewed_at": "2026/11/01"}, [_L + "reviewed_at must be YYYY-MM-DD"]),
    ({"basis": ""}, [_L + "basis is empty"]),
    ({"evidence": []}, [_L + "evidence must list the counted rows it rests on"]),
    ({"evidence": [{"id": "r1"}]}, [_L + "every evidence item needs id and source_url"]),
    ({"official_confirmation": {"product_id": "p", "update_version": "1.1"}},
     [_L + "official_confirmation needs product_id, update_version, statement"]),
    ({"official_confirmation": {"product_id": "p", "update_version": "1.1", "target_build": "26200.8117",
                                "statement": "s"}}, []),
    ({"verdict": "WAIT"}, [_L + "WAIT requires reason_class regression",
                           _L + "WAIT requires transition.working and transition.failing",
                           _L + "WAIT requires a written material impact",
                           _L + "WAIT requires new_in_this_version: true (a persistent problem is not a regression)"]),
    ({"verdict": "WAIT", "reason_class": "regression", "new_in_this_version": True,
      "transition": {"working": "0.9", "failing": "1.0"}, "material": "It does not start."}, []),
    ({"reason_class": "regression"}, [_L + "reason_class regression requires new_in_this_version: true"]),
]


def check_reviewed_path_unchanged() -> None:
    drift = []
    for over, want in REVIEWED_FROZEN:
        e = copy.deepcopy(_REVIEWED_BASE)
        for k, v in over.items():
            if v is ...:
                e.pop(k)
            else:
                e[k] = v
        got = vr.schema_errors([e])
        if got != want:
            drift.append((over, got))
    dup = vr.schema_errors([copy.deepcopy(_REVIEWED_BASE), copy.deepcopy(_REVIEWED_BASE)])
    shipped = vr.load_reasons(_AUX / "_data" / "verdict_reasons.yml")
    check(f"RVC-H1e the REVIEWED path is unchanged: on {len(REVIEWED_FROZEN) + 1} frozen reviewed-entry shapes "
          "schema_errors gives the pre-G84 messages word for word (a confirmation that names a build as text was "
          "already accepted), and the shipped reasons file is schema-clean",
          not drift and dup == [_L + "duplicate id"] and shipped and vr.schema_errors(shipped) == [],
          f"{drift[:2]} {dup}")


def check_wait_facts() -> None:
    bare = user_candidate(verdict="WAIT", reason="Two users report that the probe capture source turns black.")
    facts = dict(bare, reason_class="regression", new_in_this_version=True,
                 transition={"working": "9.0.0", "failing": "9.1.0"}, material="The capture shows nothing at all.")
    accepted_bare, refused_bare = vp.validated_candidates([bare], PROBE_COUNTED, {})
    accepted_facts, refused_facts = vp.validated_candidates([facts], PROBE_COUNTED, {})
    d = pd.decide(dict(PROBE), valid_reasons=accepted_facts)
    check("RVC-H1f the WAIT facts bind a machine entry as they bind a reviewed one: a WAIT candidate citing two "
          "counted reporters but no regression class, version transition, material impact or 'new in this version' "
          "is refused with exactly those four problems; with them it is accepted and decide reads it as WAIT (R3)",
          not accepted_bare and refused_bare.get(bare["id"]) == [
              "WAIT requires reason_class regression", "WAIT requires transition.working and transition.failing",
              "WAIT requires a written material impact",
              "WAIT requires new_in_this_version: true (a persistent problem is not a regression)"]
          and [c["id"] for c in accepted_facts] == [facts["id"]] and not refused_facts
          and (d.verdict, d.rule) == ("WAIT", "R3"), f"{refused_bare} {refused_facts} {d}")


def check_support_half() -> None:
    # The same problem drafted four ways shares one candidate id; each gets its own here so each refusal is visible.
    one = user_candidate(rows=PROBE_ROWS[:1], id="auto:probe:one-reporter")
    elsewhere = user_candidate(rows=[row("x-9", "https://forum.test/t/9", "x", "y")] + PROBE_ROWS[:1],
                               id="auto:probe:uncounted-row")
    moved = user_candidate(evidence=[{"id": "p-1", "source_url": "https://github.test/i/1"},
                                     {"id": "p-2", "source_url": "https://forum.test/t/other"}], id="auto:probe:moved-url")
    two = user_candidate(id="auto:probe:two-reporters")
    accepted, refused = vp.validated_candidates([one, elsewhere, moved, two], PROBE_COUNTED, {})
    other_page = vp.validated_candidates([user_candidate(page=obs("9.2.0"))], PROBE_COUNTED, {})
    check("RVC-H1g support_problems binds a machine entry on ITS OWN page's counted rows: a schema-valid candidate "
          "citing one counted reporter, a row not counted on its page, or a row whose URL differs from the counted "
          "one is refused with the reviewed rule's own message; the same two rows cited from another page are not "
          "counted there; two counted reporters pass",
          [c["id"] for c in accepted] == [two["id"]]
          and refused.get(one["id"]) == ["1 distinct counted reporter(s); 2 required"]
          and "row 'x-9' is not counted on this page" in refused.get(elsewhere["id"], [])
          and "row 'p-2' source_url differs from the counted row" in refused.get(moved["id"], [])
          and not other_page[0] and other_page[1],
          f"{refused} {other_page}")


def check_both_sites() -> None:
    recs, counted = mixed_fixture()
    reviewed = {"id": "adobe-acrobat-pro:15.099.20001:probe", "product_id": PRO, "update_version": "15.099.20001",
                "verdict": "TEST FIRST", "reason_class": "corroborated_issue", "scope": "if you use the Creative Cloud installer",
                "reason": "Two users report that the Creative Cloud installer stops with error DW003.",
                "evidence": cites(ACRO_ROWS), "new_in_this_version": False, "reviewed_at": "2026-11-21", "basis": "probe"}
    view = activation_view(recs, counted, [reviewed])
    acro_key, bypass_key = vp.page_key(ACRO), vp.page_key(BYPASS_PAGE)
    produced = {c["id"]: c for c in view["produced"]}
    passing = [i for i, c in produced.items() if c["producer"]["class"] == vrp.INSTALL_CLASS]
    refused = [i for i, c in produced.items() if c["producer"]["class"] == vrp.VENDOR_CLASS]
    on_row = view["on"]["pages"].get(acro_key, {})
    check("RVC-H1h the PROJECTION site (supported_reasons, project): switch ON, the passing install candidate joins "
          "the reviewed entry on its page and the row prints both, the refused vendor WAIT reaches no page and is "
          "listed as unsupported, and the reviewed entry is kept",
          len(passing) == 1 and len(refused) == 1
          and view["merged"].get("|".join(vr.record_identity(ACRO))) == [reviewed["id"], passing[0]]
          and on_row.get("reasons") == [reviewed["id"], passing[0]] and bypass_key not in view["on"]["pages"]
          and refused[0] in view["unsupported"] and reviewed["id"] not in view["unsupported"],
          f"merged={view['merged']} row={on_row.get('reasons')} unsupported={sorted(view['unsupported'])}")
    check("RVC-H1i the WRITER site (page_supported_reasons, what apply_consensus_to_records and "
          "build_consensus_from_evidence store): switch ON, the Acrobat page gathers the reviewed entry and the "
          "passing candidate, and the bypass page gathers nothing -- the writers refuse what the projection refuses",
          view["writer"].get(acro_key) == [reviewed["id"], passing[0]] and view["writer"].get(bypass_key) == [],
          str(view["writer"]))


def _write_tree(root: Path, recs: list, rows: list) -> None:
    gen = root / "updates" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(recs):
        (gen / f"r{i:02d}.md").write_text("---\n" + yaml.safe_dump(r, allow_unicode=True) + "---\nbody\n",
                                          encoding="utf-8")
    data = root / "_data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "consensus_evidence.yml").write_text(yaml.safe_dump({"schema_version": 1, "evidence": rows}), encoding="utf-8")
    (data / "verdict_reasons.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    (data / "patch_lifecycle.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")


def check_qa_rejects(tmp: Path) -> None:
    import qa_patch_records as qa  # noqa: PLC0415 - offline QA, paths redirected to the temp tree
    recs, _counted = bypass_fixture()
    tmp.mkdir(parents=True, exist_ok=True)
    _write_tree(tmp, recs, [])
    files = sorted((tmp / "updates" / "generated").glob("*.md"))
    proj_path = tmp / "_data" / vp.PROJECTION_NAME
    saved = (qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH)

    def scan(projection: dict) -> set:
        proj_path.write_text(vp.render(projection), encoding="utf-8")
        qa.REASONS_PATH = tmp / "_data" / "verdict_reasons.yml"
        qa.LIFECYCLE_PATH = tmp / "_data" / "patch_lifecycle.yml"
        qa.EVIDENCE_PATH = tmp / "_data" / "consensus_evidence.yml"
        qa.PROJECTION_PATH = proj_path
        try:
            return {e["code"] for e in qa.scan_verdict_policy(files)[0]}
        finally:
            qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH = saved
    merged = vrp.merge({}, vrp.produce(recs, {}).candidates)
    forged = {"schema_version": vp.SCHEMA_VERSION, "pages": {}}
    for rec in recs:
        d = pd.decide(dict(rec), valid_reasons=merged.get(vr.record_identity(rec), []))
        if d.verdict != pd.INSUFFICIENT_DATA:
            forged["pages"][vp.page_key(rec)] = vp.row_for(d, rec)
    with switch(True):
        honest = vp.project(recs, {}, [], [])[0]
        e_forged, e_honest = scan(forged), scan(honest)
    check("RVC-H1j publication QA rejects an unsupported candidate (switch ON): a projection that prints the "
          "refused vendor WAIT -- what the activation path built before G84 -- is a verdict_render_disagrees ERROR; "
          "the projection the contract builds is clean",
          forged["pages"] and not honest["pages"] and "verdict_render_disagrees" in e_forged
          and "verdict_render_disagrees" not in e_honest, f"forged={e_forged} honest={e_honest}")


def check_corpus() -> None:
    records, groups = vp.load_inputs(_AUX)
    reasons, lifecycle, problems = vp.load_fact_files(_AUX)
    by_ident = {vr.record_identity(r): r for r in records}
    reviewed_valid, reviewed_unsupported = vr.valid_reasons_by_identity(reasons, groups, by_ident)
    off_valid, off_unsupported = vp.supported_reasons(records, groups, reasons)
    with switch(True):
        on_valid, on_unsupported = vp.supported_reasons(records, groups, reasons)
    produced = vrp.produce(records, groups).candidates
    reviewed_ids = {str(e.get("id")) for e in reasons}
    on_reviewed = {k: [e for e in v if str(e.get("id")) in reviewed_ids] for k, v in on_valid.items()}
    on_reviewed = {k: v for k, v in on_reviewed.items() if v}
    accounted = {c["id"] for c in produced} <= ({str(e.get("id")) for v in on_valid.values() for e in v}
                                                 | set(on_unsupported))
    n_refused = len(set(on_unsupported) - reviewed_ids)
    check(f"RVC-H1k over the shipped corpus the reviewed entries' support is identical with the switch OFF, ON and "
          f"through valid_reasons_by_identity ({len(reasons)} entries, {len(reviewed_unsupported)} unsupported), and "
          f"every one of the {len(produced)} producer candidates is either merged or listed as unsupported "
          f"({n_refused} refused today)",
          not problems and reasons and produced and off_valid == reviewed_valid and on_reviewed == reviewed_valid
          and off_unsupported == reviewed_unsupported
          and {k: v for k, v in on_unsupported.items() if k in reviewed_ids} == reviewed_unsupported and accounted,
          f"problems={problems} refused={n_refused}")


# ------------------------------------------------------------------------ [H2] the user class

def check_class_mapping() -> None:
    page = dict(PROBE)
    def make(cls):  # noqa: E306
        return vrp._candidate(cls, page, verdict="TEST FIRST", scope="if you use the probe capture source", reason="r.",
                              severity="substantial_workflow_breakage", failure="f", new=False, fixed_in="",
                              citation={}, inputs={}, problem_key="k", evidence=cites(PROBE_ROWS[:2]))
    got = {cls: make(cls)["reason_class"] for cls in (vrp.USER_CLASS, vrp.INSTALL_CLASS, vrp.VENDOR_CLASS, "unknown_class")}
    unknown = make("unknown_class")
    check("RVC-H2a the class mapping: a user-corroboration candidate is worded as the user class "
          "'corroborated_issue', never as a vendor confirmation; install stays 'corroborated_install_problem' and "
          "vendor 'vendor_confirmed_serious'; a class the producer does not know drafts no reason class, which the "
          "machine schema refuses",
          got == {vrp.USER_CLASS: "corroborated_issue", vrp.INSTALL_CLASS: "corroborated_install_problem",
                  vrp.VENDOR_CLASS: "vendor_confirmed_serious", "unknown_class": ""}
          and vrp.USER_REASON_CLASS in vr.REASON_CLASSES
          and any("reason_class ''" in p for p in vr.machine_schema_errors([unknown])), str(got))


def check_reporter_minimum() -> None:
    probs = {n: vrp.candidate_problems(user_candidate(rows=PROBE_ROWS[:n])) for n in (0, 1, 2)}
    install = vrp.candidate_problems(dict(user_candidate(rows=PROBE_ROWS[:1]), scope=vrp.INSTALL_SCOPE,
                                          severity_basis="critical_install_failure",
                                          producer={"class": vrp.INSTALL_CLASS, "version": vrp.PRODUCER_VERSION}))
    minimum = "fewer independent reporters than MIN_INDEPENDENT_REPORTERS"
    check("RVC-H2b the reporter minimum holds for EVERY user class: the producer's own gate refuses a "
          "user-corroboration candidate citing 0 or 1 rows and passes one citing 2, as it does for the install class",
          minimum in probs[0] and minimum in probs[1] and probs[2] == [] and minimum in install
          and vrp.USER_CLASSES == (vrp.INSTALL_CLASS, vrp.USER_CLASS), str(probs))


def check_user_class_end_to_end() -> None:
    cand = user_candidate()
    accepted, refused = vp.validated_candidates([cand], PROBE_COUNTED, {})
    d = pd.decide(dict(PROBE), valid_reasons=accepted)
    body = pd.public_body(d, dict(PROBE), 3)
    sec = win("25H2", "26200.9900", "KB5099900", "2026-10-14T00:00:00Z", update_type="2026-10 B", count=2)
    sec_rows = [row("s-1", "https://learn.test/q/s1", "a", "Printing stops after the update."),
                row("s-2", "https://learn.test/q/s2", "b", "My printer no longer prints since the update.")]
    sec_cand = user_candidate(page=sec, rows=sec_rows, scope="if you use network printers")
    sec_ok, _r = vp.validated_candidates([sec_cand], {vr.record_identity(sec): sec_rows}, {})
    ds = pd.decide(dict(sec), valid_reasons=sec_ok)
    check("RVC-H2c end to end, a user-corroboration candidate on two counted reports passes the contract and is "
          "worded as a USER report: TEST FIRST (R4) whose line ends with the usual 'Other setups' line, never the "
          "vendor-only one; on a monthly security update it adds the 'a problem is reported on some setups' panel",
          [c["id"] for c in accepted] == [cand["id"]] and not refused and (d.verdict, d.rule) == ("TEST FIRST", "R4")
          and body.endswith(pd.OTHER_SETUPS) and pd.OTHER_SETUPS_BY_CLASS[vrp.VENDOR_CLASS] not in body
          and ds.verdict == "SECURITY UPDATE" and pd.public_body(ds, dict(sec), 2) == pd.SECURITY_PANEL_LEAD["corroborated_issue"],
          f"{refused} {d} {body[-80:]!r} {ds}")


# ------------------------------------------------------------------------ [D1] confirmation by full identity

def check_d1_repro() -> None:
    rows = WIN_D1_ROWS
    before = vr.support_problems(WIN_ENTRY, rows, D1_BY_IDENT)
    named = with_conf(WIN_ENTRY, conf(WIN_ENTRY, WIN_STATEMENT))
    after = vr.support_problems(named, rows, D1_BY_IDENT)
    no_build = with_conf(WIN_ENTRY, {"product_id": WIN, "update_version": "25H2", "statement": WIN_STATEMENT})
    valid, _u = vr.valid_reasons_by_identity([named], {vr.reason_identity(WIN_ENTRY): rows}, D1_BY_IDENT)
    d = pd.decide(dict(WIN_D1), valid_reasons=valid.get(vr.reason_identity(WIN_ENTRY), []))
    check("RVC-D1a the G82 T2 D-1 repro, fixed: a supported Windows entry stays supported when a TRUE official "
          "confirmation (a line of that record's own captured notes, naming it by product, version AND build) is "
          "added, and decide still gives TEST FIRST; a confirmation that names no build still looks up the "
          "blank-build record, which no Windows record is, so it is not found -- exactly as before",
          before == [] and vr.schema_errors([named]) == [] and after == [] and (d.verdict, d.rule) == ("TEST FIRST", "R4")
          and vr.support_problems(no_build, rows, D1_BY_IDENT)
          == ["official confirmation is not found in the named record's captured official notes"],
          f"before={before} after={after} {d}")


def check_d1_fail_closed() -> None:
    rows = WIN_D1_ROWS
    cases = {
        "another build": conf(WIN_ENTRY, WIN_STATEMENT, target_build="26200.8118"),
        "statement not in the notes": conf(WIN_ENTRY, "This update fixes everything."),
        "another version": conf(WIN_ENTRY, WIN_STATEMENT, update_version="24H2"),
        "a build on a blank-build product": conf(OBS_ENTRY, OBS_STATEMENT, update_version="33.0.0", target_build="1"),
    }
    entries = {"a build on a blank-build product": OBS_ENTRY}
    got = {n: vr.support_problems(with_conf(entries.get(n, WIN_ENTRY), c),
                                  OBS_ROWS if n in entries else rows, D1_BY_IDENT) for n, c in cases.items()}
    check("RVC-D1b the lookup stays fail closed: a confirmation naming another build, another version, a build the "
          "named product's records do not carry, or a statement absent from the named record's notes is not found",
          all(g == ["official confirmation is not found in the named record's captured official notes"]
              for g in got.values()), str(got))


def check_d1_monotonic() -> None:
    pairs = [(WIN_ENTRY, WIN_D1_ROWS, conf(WIN_ENTRY, WIN_STATEMENT)),
             (PPT_ENTRY, PPT_ROWS, conf(PPT_ENTRY, PPT_STATEMENT)),
             (OBS_ENTRY, OBS_ROWS, conf(OBS_ENTRY, OBS_STATEMENT, update_version="33.0.0"))]
    lost = []
    for entry, rows, c in pairs:
        for n in (1, 2):
            base = dict(copy.deepcopy(entry), evidence=cites(rows[:n]))
            before, after = vr.support_problems(base, rows, D1_BY_IDENT), vr.support_problems(with_conf(base, c), rows, D1_BY_IDENT)
            if set(after) - set(before) or (n == 1 and after):
                lost.append((entry["id"], n, before, after))
    check("RVC-D1c MONOTONIC: on Windows, PowerPoint and OBS, adding a TRUE confirmation never adds a problem, and a "
          "one-reporter entry with one is supported -- on a build-keyed product too, which the old lookup made "
          "impossible", not lost, str(lost)[:400])


def check_d1_blank_build_unchanged() -> None:
    cases = []
    for n in (1, 2):
        base = dict(copy.deepcopy(OBS_ENTRY), evidence=cites(OBS_ROWS[:n]))
        cases += [base,
                  with_conf(base, conf(OBS_ENTRY, OBS_STATEMENT, update_version="33.0.0")),
                  with_conf(base, conf(OBS_ENTRY, OBS_STATEMENT, update_version="33.0.0", target_build="")),
                  with_conf(base, conf(OBS_ENTRY, "Fixed something else", update_version="33.0.0")),
                  with_conf(base, conf(OBS_ENTRY, OBS_STATEMENT, update_version="99.0.0"))]
    differ = [(c.get("official_confirmation"), vr.support_problems(c, OBS_ROWS, D1_BY_IDENT),
               support_problems_pre_g84(c, OBS_ROWS, D1_BY_IDENT)) for c in cases
              if vr.support_problems(c, OBS_ROWS, D1_BY_IDENT) != support_problems_pre_g84(c, OBS_ROWS, D1_BY_IDENT)]
    shipped = vr.load_reasons(_AUX / "_data" / "verdict_reasons.yml")
    named_builds = [e["id"] for e in shipped if (e.get("official_confirmation") or {}).get("target_build")]
    check(f"RVC-D1d blank-build products behave exactly as before: on {len(cases)} OBS cases (one or two reporters; "
          "no confirmation, a true one with no build or a blank build, a wrong statement, a missing record) "
          "support_problems equals the pre-G84 function; no shipped entry's confirmation names a build",
          not differ and not named_builds, f"{differ[:2]} {named_builds}")


def check_d1_schema() -> None:
    errs = {v: vr.schema_errors([with_conf(WIN_ENTRY, conf(WIN_ENTRY, WIN_STATEMENT, target_build=v))])
            for v in ("26200.8117", "", 26200.811)}
    check("RVC-D1e official_confirmation accepts target_build as text (a build, or empty for a blank-build record) "
          "and refuses a YAML number, which drops digits (26200.8110 reads back as 26200.811)",
          errs["26200.8117"] == [] and errs[""] == []
          and errs[26200.811] == [f"{WIN_ENTRY['id']}: official_confirmation target_build must be a quoted string, "
                                  "not a float"], str(errs))


def check_d1_writer(tmp: Path) -> None:
    import apply_consensus_to_records as acr  # noqa: PLC0415 - the writer itself, offline
    import build_consensus_from_evidence as bce  # noqa: PLC0415
    gen = tmp / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(D1_RECORDS):
        (gen / f"r{i:02d}.md").write_text("---\n" + yaml.safe_dump(r, allow_unicode=True) + "---\nbody\n",
                                          encoding="utf-8")
    entry = with_conf(WIN_ENTRY, conf(WIN_ENTRY, WIN_STATEMENT))
    index = {(r["product_id"], r["update_version"], r.get("target_build", "")): r for r in D1_RECORDS}
    saved = (acr.GENERATED_DIR, list(acr._ALL_ENTRY_RECORDS), vr.load_reasons)
    got = {}
    try:
        acr.GENERATED_DIR = gen
        vr.load_reasons = lambda *a, **k: [copy.deepcopy(entry)]
        fetched = acr._confirmation_records([entry])
        a = acr._policy_decision(WIN, "25H2", "26200.8117", [dict(r) for r in WIN_D1_ROWS], dict(WIN_D1))[0]
        b = bce.policy_decision(WIN, "25H2", "26200.8117", [dict(r) for r in WIN_D1_ROWS], dict(WIN_D1), index)[0]
        got = {"fetched": sorted("|".join(k) for k in fetched), "apply": (a.verdict, a.rule), "build": (b.verdict, b.rule)}
    finally:
        acr.GENERATED_DIR, vr.load_reasons = saved[0], saved[2]
        acr._ALL_ENTRY_RECORDS[:] = saved[1]
    check("RVC-D1f the WRITER path keys on the full identity too: apply_consensus_to_records._confirmation_records "
          "fetches the build-keyed confirming record, and both record writers store TEST FIRST for the Windows page "
          "whose entry cites a true confirmation (before G84 they stored INSUFFICIENT DATA)",
          got.get("fetched") == ["microsoft-windows-11|25H2|26200.8117"] and got.get("apply") == ("TEST FIRST", "R4")
          and got.get("build") == ("TEST FIRST", "R4"), str(got))


# ------------------------------------------------------------------------ [N] the switch

def check_switch_off() -> None:
    text = PRODUCER_PATH.read_text(encoding="utf-8")
    check("RVC-N1 PUBLIC_AUTO_ACTIVATION stays OFF on disk and in this process after every forced-ON measurement",
          re.findall(r"^PUBLIC_AUTO_ACTIVATION\s*=\s*(.+)$", text, re.M) == ["False"] and vrp.PUBLIC_AUTO_ACTIVATION is False)


# ------------------------------------------------------------------------ [X] mutants

def run_mutant(label: str, body, mutants: list, *, mutate, restore) -> None:
    try:
        with captured() as baseline:
            body()
    except Exception as exc:  # noqa: BLE001
        mutants.append((label, [], f"baseline raised {type(exc).__name__}: {exc}"))
        return
    mutate()
    try:
        with captured() as failures:
            body()
    except Exception as exc:  # noqa: BLE001
        mutants.append((label, [], f"{type(exc).__name__}: {exc}"))
        return
    finally:
        restore()
    mutants.append((label, [f for f in failures if f not in set(baseline)], ""))


def swap(owner, name, replacement):
    original = getattr(owner, name)
    return (lambda: setattr(owner, name, replacement)), (lambda: setattr(owner, name, original))


def check_mutations(tmp: Path) -> None:
    import apply_consensus_to_records as acr  # noqa: PLC0415
    real_schema = vr._schema_errors

    def drop_build_check(entries, *, machine):
        return [m for m in real_schema(entries, machine=machine) if "target_build must be a quoted string" not in m]

    cases = [
        ("RX1 (H-1, projection site) supported_reasons merges every candidate unchecked again (pre-G84)",
         lambda: (check_bypass_closed(), check_both_sites()),
         [swap(vp, "supported_reasons", supported_reasons_pre_g84)]),
        ("RX2 (H-1, writer site) page_supported_reasons merges every candidate unchecked again (pre-G84)",
         lambda: (check_bypass_closed(), check_both_sites()),
         [swap(vp, "page_supported_reasons", page_supported_reasons_pre_g84)]),
        ("RX3 (H-1, schema half) the machine schema finds nothing", check_wait_facts,
         [swap(vr, "machine_schema_errors", lambda entries: [])]),
        ("RX4 (H-1, support half) support_problems finds nothing", check_support_half,
         [swap(vr, "support_problems", lambda entry, rows, records: [])]),
        ("RX5 (H-2, class) a user-corroboration candidate gets the vendor class again",
         lambda: (check_class_mapping(), check_user_class_end_to_end()),
         [swap(vrp, "REASON_CLASS_BY_CLASS", {**vrp.REASON_CLASS_BY_CLASS, vrp.USER_CLASS: vrp.VENDOR_CLASS})]),
        ("RX6 (H-2, minimum) the reporter minimum binds the install class only again", check_reporter_minimum,
         [swap(vrp, "USER_CLASSES", (vrp.INSTALL_CLASS,))]),
        ("RX7 (D-1, support_problems) the confirmation is looked up by (product, version, '') again",
         lambda: (check_d1_repro(), check_d1_monotonic()), [swap(vr, "support_problems", support_problems_pre_g84)]),
        ("RX8 (D-1, writer) _confirmation_records fetches by (product, version, '') again",
         lambda: check_d1_writer(tmp / "rx8"), [swap(acr, "_confirmation_records", confirmation_records_pre_g84(acr))]),
        ("RX9 (D-1, schema) a numeric confirmation target_build is accepted", check_d1_schema,
         [swap(vr, "_schema_errors", drop_build_check)]),
        ("RX10 (H-1, basis) a candidate that names no rule version gets a basis anyway", check_machine_schema,
         [swap(vr, "machine_basis", lambda entry: "automatic:x")]),
    ]
    mutants: list = []
    for label, body, swaps in cases:
        run_mutant(label, body, mutants, mutate=lambda s=swaps: [m() for m, _r in s],
                   restore=lambda s=swaps: [r() for _m, r in s])
    for label, failures, crash in mutants:
        check(f"{label} -> caught", bool(failures),
              f"mutant crashed instead of being caught: {crash}" if crash else "no NAMED check failed")
        if failures:
            print(f"        caught by: {', '.join(sorted(f.split(' ')[0] for f in failures))}")


# ------------------------------------------------------------------------ the suite

def run() -> int:
    print("=" * 78)
    print("G84 ONE VALIDATION CONTRACT FOR EVERY REASON")
    print("=" * 78)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print("\n[H1] the activation path meets the reviewed checks")
        check_bypass_closed()
        check_machine_schema()
        check_reviewed_path_unchanged()
        check_wait_facts()
        check_support_half()
        check_both_sites()
        check_qa_rejects(tmp / "qa")
        check_corpus()
        print("\n[H2] the user class")
        check_class_mapping()
        check_reporter_minimum()
        check_user_class_end_to_end()
        print("\n[D1] the official confirmation by full identity")
        check_d1_repro()
        check_d1_fail_closed()
        check_d1_monotonic()
        check_d1_blank_build_unchanged()
        check_d1_schema()
        check_d1_writer(tmp / "d1")
        print("\n[X] mutants, one per fix site, each caught by a named check")
        check_mutations(tmp)
        print("\n[N] the switch")
        check_switch_off()
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
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
