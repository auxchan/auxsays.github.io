#!/usr/bin/env python3
"""GROWTH-3: every verdict comes from the owner's policy, decided once, rendered everywhere alike.

THE POLICY (owner decisions 1-3, 2026-11-06), implemented in lib/patch_decision.decide:
  R1 AVOID            an official withdrawal for new installations (_data/patch_lifecycle.yml: ONE
                      verified exception, KB5079391 -> KB5086672)
  R2 SECURITY UPDATE  Microsoft's stored monthly-security classification (release type "YYYY-MM B");
                      reports never override it, a supported reason only adds a warning panel
  R3 WAIT             a reviewed `regression` entry in _data/verdict_reasons.yml, still supported
  R4 TEST FIRST       a reviewed corroboration entry, still supported
  R5/R6 INSUFFICIENT DATA
Report count, sentiment, theme, severity, maturity and the clock decide nothing; SAFE ENOUGH stays
unreachable.

ONE AUTHORITY (fix round 1, review 1 D2). The Liquid gate (_includes/patch-verdict-gate.html) no
longer decides a reasoned verdict: lib/verdict_projection writes decide's answer per page at deploy
(build_verdict_projection.py, before QA and Jekyll) and the gate prints it. It derives only the two
official facts itself.

SECTIONS. [D] the decision procedure and its invariants (G3-D1..D12). [F] the reason file's audits
(G3-F0..F7, G3-OC). [L] the lifecycle exception (G3-L1..L3, G3-W0). [W] public wording (G3-W1..W3).
[Q] QA: severities, and the rendered/authority comparison (G3-Q1..Q6). [R] the gate renders exactly
what Python decides: a synthetic matrix with one case per support rule, no-projection fail-closed,
and the whole corpus (G3-R0..R5). [P] the projection IS the authority, review 1's probes A1 and A2
on the rendered page, the builder and its position in the deploy (G3-P0..P7). [S] the scope prints
with the verdict on every surface (G3-S1..S5, review 1 D1). [X] mutants: each restores ONE thing the
policy forbids, and must be caught by a named check that was passing before it.

Needs ruby + the liquid gem for [R], [P], [S] and the template mutants. Offline; writes only in a
temp dir.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_growth3_verdict_policy.py
"""
from __future__ import annotations

import contextlib
import copy
import inspect
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
sys.path.insert(0, str(_AUX / "scripts"))

import yaml  # noqa: E402

from lib import patch_decision as pd  # noqa: E402
from lib import verdict_projection as vp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402

GATE_PATH = _AUX / "_includes" / "patch-verdict-gate.html"
REASONS = yaml.safe_load((_AUX / "_data" / "verdict_reasons.yml").read_text(encoding="utf-8"))
LIFECYCLE = yaml.safe_load((_AUX / "_data" / "patch_lifecycle.yml").read_text(encoding="utf-8"))
WIN, OBS = "microsoft-windows-11", "obs-studio"

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
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


@contextlib.contextmanager
def captured():
    """Run checks silently and collect the labels that failed, leaving the real tally untouched."""
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


# ------------------------------------------------------------------------ synthetic facts

URLS = [f"https://reports.test/{i}" for i in range(1, 7)]


def row(i: int, excerpt: str | None = None) -> dict:
    return {"id": f"row-{i}", "source_url": URLS[i - 1],
            "report_text_excerpt": excerpt if excerpt is not None else f"Report number {i}.",
            "issue_theme": "audio mixer regression", "severity": "high", "sentiment": "negative"}


def entry(eid: str, verdict: str = "TEST FIRST", rclass: str = "corroborated_issue", *,
          pid: str = OBS, version: str = "99.0.0", build: str = "", rows=(1, 2), **extra) -> dict:
    e = {"id": eid, "product_id": pid, "update_version": version, "verdict": verdict,
         "reason_class": rclass, "scope": "if you use the test setup",
         "reason": "Two users independently report that the test setup fails.",
         "evidence": [{"id": f"row-{i}", "source_url": URLS[i - 1]} for i in rows],
         "new_in_this_version": rclass == "regression", "reviewed_at": "2026-11-10", "basis": "test"}
    if build:
        e["target_build"] = build
    if verdict == "WAIT":
        e.update(transition={"working": "98.0.0", "failing": version}, material="it does not start")
    e.update(extra)
    return e


def record(**over) -> dict:
    r = {"product_id": OBS, "update_version": "99.0.0", "update_report_count": 2,
         "update_consensus_label": "Negative", "evidence_state": "pilot_sample",
         "accepted_report_sources": [{"source_url": u} for u in URLS[:2]]}
    r.update(over)
    return r


def win_record(update_type: str = "2026-02 B", kb: str = "KB5000001", build: str = "26200.1000", **over) -> dict:
    r = record(product_id=WIN, update_version="25H2", target_kb=kb, target_build=build,
               update_type=update_type, accepted_report_sources=[])
    r.update(over)
    return r


LIFE = [{"id": "life", "product_id": WIN, "kb": "KB5000002", "builds": ["26200.2000", "26100.2000"],
         "relationship": "withdrawn_for_new_installs", "replacement_kb": "KB5000003",
         "replacement_builds": ["26200.2001"], "released": "2026-03-26", "replacement_released": "2026-03-31",
         "official_url": "https://support.microsoft.com/en-us/x", "verified_at": "2026-11-06"}]


def decide(rec, reasons=(), life=()):
    return pd.decide(rec, valid_reasons=list(reasons), lifecycle=list(life))


def code_of(fn) -> str:
    """A function's CODE, docstring removed: a docstring that names what is NOT read must not count."""
    import ast
    import textwrap
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, TypeError, SyntaxError):
        return ""
    node = tree.body[0]
    body = getattr(node, "body", None)
    if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
            and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
        node.body = body[1:] or [ast.Pass()]
    return ast.unparse(node)


# ------------------------------------------------------------------------ [D] decision procedure

def check_decisions() -> None:
    wait_e, tf_e = entry("w", "WAIT", "regression"), entry("t")
    sec = win_record()
    life_rec = win_record(update_type="2026-03 D", kb="KB5000002", build="26200.2000")
    ladder = [
        (life_rec, [wait_e, tf_e], LIFE, "AVOID", "R1"),
        (win_record(kb="KB5000002", build="26200.2000"), [wait_e], LIFE, "AVOID", "R1"),
        (sec, [wait_e, tf_e], LIFE, "SECURITY UPDATE", "R2"),
        (record(), [tf_e, wait_e], (), "WAIT", "R3"),
        (record(), [tf_e], (), "TEST FIRST", "R4"),
        (record(), [], (), "INSUFFICIENT DATA", "R5"),
        (record(update_report_count=0, accepted_report_sources=[]), [], (), "INSUFFICIENT DATA", "R5"),
    ]
    wrong = [(exp, d.verdict, d.rule) for rec, rs, life, exp, rule in ladder
             for d in [decide(rec, rs, life)] if (d.verdict, d.rule) != (exp, rule)]
    check("G3-D1 precedence: withdrawal, then security, then WAIT, then TEST FIRST, else INSUFFICIENT DATA",
          not wrong, str(wrong))

    params = set(inspect.signature(pd.decide).parameters)
    src = code_of(pd.decide) + code_of(pd.public_body)
    clocky = re.findall(r"\bdatetime\b|\btime\.\w+|\bnow\(|\btoday\(|\bdate\.today", src)
    check("G3-D2 no clock: decide takes no time input and reads none, so nothing relaxes with age",
          params == {"record", "valid_reasons", "lifecycle"} and not clocky, f"{params} {clocky}")

    labels = ["Negative", "Positive", "Moderate", "Mixed", "Insufficient data", "", None]
    for rs in ([], [tf_e], [wait_e]):
        got = {decide(record(update_consensus_label=lab), rs).verdict for lab in labels}
        if len(got) != 1:
            break
    else:
        got = set()
    check("G3-D3 sentiment never selects: every consensus label gives the same verdict", len(got) <= 1, str(got))

    counts = [0, 1, 2, 3, 8, 33, 500]
    by_count = {decide(record(update_report_count=n, confirmed_patch_specific_report_count=n)).verdict
                for n in counts}
    by_count_tf = {decide(record(update_report_count=n), [tf_e]).verdict for n in counts}
    check("G3-D4 count never selects: any count without a reason is INSUFFICIENT DATA, with one it is that reason",
          by_count == {"INSUFFICIENT DATA"} and by_count_tf == {"TEST FIRST"}
          and pd.decision_label(OBS, "99.0.0", "negative", 500) == "INSUFFICIENT DATA",
          f"{by_count} {by_count_tf}")

    live = dict(evidence_state="consensus_live", consensus_collection_status="consensus_live",
                evidence_state_label="Live consensus", intelligence_stage="consensus_live")
    check("G3-D5 maturity never selects: a live record decides exactly as a pilot one",
          decide(record(**live)).verdict == decide(record()).verdict == "INSUFFICIENT DATA"
          and decide(record(**live), [wait_e]).verdict == "WAIT")

    d6 = decide(sec, [wait_e])
    check("G3-D6 security whatever the reports: a supported WAIT on a monthly security update stays "
          "SECURITY UPDATE, with a deployment-caution panel",
          d6.verdict == "SECURITY UPDATE" and d6.panel_kind == "deployment_caution"
          and decide(win_record(update_report_count=900)).verdict == "SECURITY UPDATE"
          and decide(win_record(update_type="2026-01 OOB")).verdict == "INSUFFICIENT DATA"
          and decide(win_record(update_type="2026-01 D")).verdict == "INSUFFICIENT DATA",
          repr(d6))

    avoid_entry = entry("a", "AVOID", "regression")
    outcomes = {decide(r, rs).verdict for r in (record(), sec, life_rec) for rs in ([], [tf_e], [wait_e])}
    check("G3-D7 AVOID only from the lifecycle record: no reason, report or entry can produce it",
          "AVOID" not in outcomes and bool(vr.schema_errors([avoid_entry])), str(outcomes))

    bad_waits = [entry("m1", "WAIT", "regression", material=""),
                 entry("m2", "WAIT", "corroborated_issue"),
                 entry("m3", "WAIT", "regression", new_in_this_version=False),
                 entry("m4", "WAIT", "regression", transition={"working": "", "failing": "x"})]
    refused = [e["id"] for e in bad_waits if vr.schema_errors([e])]
    check("G3-D8 WAIT needs a material, new, corroborated regression: each missing part is refused",
          refused == ["m1", "m2", "m3", "m4"] and not vr.schema_errors([entry("ok", "WAIT", "regression")]),
          str(refused))

    produced = {decide(r, rs, lf).verdict for r in (record(), sec, life_rec, win_record(update_type=""))
                for rs in ([], [tf_e], [wait_e]) for lf in ((), LIFE)}
    check("G3-D9 eight canonical verdicts, no ninth; this policy produces only AVOID, WAIT, TEST FIRST, "
          "SECURITY UPDATE and INSUFFICIENT DATA",
          len(pd.RISK_ORDER) == 8 and produced <= set(pd.RISK_ORDER)
          and produced <= {"AVOID", "WAIT", "TEST FIRST", "SECURITY UPDATE", "INSUFFICIENT DATA"},
          str(produced))

    zero_sec = win_record(update_report_count=0)
    zero_life = win_record(update_type="2026-03 D", kb="KB5000002", build="26100.2000", update_report_count=0)
    check("G3-D10 an official verdict survives zero reports (security update and withdrawal)",
          decide(zero_sec).verdict == "SECURITY UPDATE" and decide(zero_life, (), LIFE).verdict == "AVOID"
          and pd.public_body(decide(zero_sec), zero_sec, 0).endswith("No user reports are matched to this update yet."))

    noisy = record(severity="critical", issue_theme="crash", update_consensus_confidence="High",
                   complaint_themes=[{"theme": "crash"}])
    src_decide = code_of(pd.decide) + code_of(pd.is_monthly_security_update) + code_of(pd.lifecycle_for)
    check("G3-D12 severity and theme never read: a critical-severity record with themes decides nothing",
          decide(noisy).verdict == "INSUFFICIENT DATA"
          and not any(w in src_decide for w in ("severity", "issue_theme", "consensus_label", "update_status")))


def check_corpus_guard() -> None:
    """G3-D11: invariants over the shipped corpus that hold however it grows."""
    c = corpus()
    recs = c["recs"]
    reason_ids = {vr.reason_identity(e) for e in REASONS["entries"]}
    problems = []
    for r in recs:
        d = decide(r, c["valid"].get(vr.record_identity(r), []), LIFECYCLE["entries"])
        if d.verdict in ("WAIT", "TEST FIRST") and vr.record_identity(r) not in reason_ids:
            problems.append(("reasonless", r.get("permalink")))
        if pd.is_monthly_security_update(r) and d.verdict not in ("SECURITY UPDATE", "AVOID"):
            problems.append(("security", r.get("permalink")))
        if d.verdict in ("SAFE ENOUGH", "OFFICIAL ONLY", "MANUAL WATCH"):
            problems.append(("unreachable", r.get("permalink")))
        if "Pause updates" in json.dumps(r, default=str):
            problems.append(("pause", r.get("permalink")))
    check(f"G3-D11 corpus guard over {len(recs)} records: every WAIT/TEST FIRST has a reviewed entry, every "
          "monthly security update reads SECURITY UPDATE, nothing unreachable, no 'Pause updates'",
          len(recs) > 1000 and not problems, str(problems[:5]))


# ------------------------------------------------------------------------ [F] reason audits

def check_reason_audits() -> None:
    rows = [row(1), row(2), row(3)]
    ok = entry("ok")
    check("G3-F1 every cited row must be counted on THIS page, with the same URL",
          not vr.support_problems(ok, rows, {})
          and vr.support_problems(entry("x", rows=(1, 5)), rows, {})
          and vr.support_problems(dict(ok, evidence=[{"id": "row-1", "source_url": URLS[3]},
                                                     {"id": "row-2", "source_url": URLS[1]}]), rows, {}))
    check("G3-F2 two distinct reporters are required unless an official confirmation is cited",
          bool(vr.support_problems(entry("one", rows=(1,)), rows, {})))
    twins = [row(1, "Same words posted twice."), row(2, "Same words  posted twice.")]
    check("G3-F3 the same text posted twice is one reporter",
          bool(vr.support_problems(entry("twin"), twins, {})))
    check("G3-F4 a regression must state its transition", bool(vr.schema_errors(
        [entry("r", "TEST FIRST", "regression", new_in_this_version=True)])) is False
          and bool(vr.schema_errors([entry("w", "WAIT", "regression", transition=None)])))
    check("G3-F5 a persistent problem is never a regression (no causal claim without 'new')",
          bool(vr.schema_errors([entry("p", "TEST FIRST", "regression", new_in_this_version=False)])))
    before = vr.support_problems(entry("wd", rows=(1, 2)), rows, {})
    after = vr.support_problems(entry("wd", rows=(1, 2)), [row(1), row(3)], {})
    valid, unsupported = vr.valid_reasons_by_identity([entry("wd", rows=(1, 2))],
                                                      {(OBS, "99.0.0", ""): [row(1), row(3)]}, {})
    check("G3-F6 an audited withdrawal of a cited row makes the entry unsupported (fall back, not keep)",
          not before and after and not valid and "wd" in unsupported, str(after))
    bad_scopes = [entry(f"s{i}", scope=s) for i, s in enumerate(("", "you use macOS", "if you use macOS."))]
    check("G3-F7 scope is mandatory and reads 'if/when/for ...'",
          all(vr.schema_errors([e]) for e in bad_scopes) and not vr.schema_errors([entry("good")]))
    conf_rec = {(OBS, "100.0.0", ""): {"official_patch_notes_body": "* Fixed the\r\ntest setup crash [dev]"}}
    conf = {"product_id": OBS, "update_version": "100.0.0", "statement": "Fixed the test setup crash"}
    check("G3-OC an official confirmation counts only when found verbatim in that record's captured notes",
          not vr.support_problems(entry("c", rows=(1,), official_confirmation=conf), rows, conf_rec)
          and vr.support_problems(entry("c", rows=(1,), official_confirmation=dict(conf, statement="Fixed it")),
                                  rows, conf_rec))
    shipped = vr.schema_errors(REASONS["entries"])
    check(f"G3-F0 the shipped reason file is valid ({len(REASONS['entries'])} entries)",
          not shipped and len(REASONS["entries"]) >= 1, str(shipped))


# ------------------------------------------------------------------------ [L] lifecycle exception

def check_lifecycle() -> None:
    entries = LIFECYCLE["entries"]
    check("G3-L1 the lifecycle file holds exactly ONE verified exception, and a second is refused",
          len(entries) == 1 and entries[0]["kb"] == "KB5079391" and entries[0]["replacement_kb"] == "KB5086672"
          and not vr.lifecycle_errors(entries) and bool(vr.lifecycle_errors(entries + [dict(entries[0], id="x")])))
    exact = win_record(update_type="2026-03 D", kb="KB5000002", build="26200.2000")
    near = [win_record(update_type="2026-03 D", kb="KB5000002", build="26200.2001"),
            win_record(update_type="2026-03 D", kb="KB5000003", build="26200.2000"),
            record(target_kb="KB5000002", target_build="26200.2000")]
    check("G3-L2 AVOID applies to the exact KB and OS build only, never a neighbour or another product",
          decide(exact, (), LIFE).verdict == "AVOID"
          and all(decide(r, (), LIFE).verdict != "AVOID" for r in near))
    keys = set(entries[0])
    check("G3-L3 the record stores KB ids, builds, dates, the URL and the relationship -- no vendor text",
          keys <= vr.ALLOWED_LIFECYCLE_KEYS and bool(vr.lifecycle_errors([dict(entries[0], note="text")])),
          str(sorted(keys)))
    body = pd.public_body(decide(exact, (), LIFE), exact, 1)
    check("G3-W0 the AVOID line is the owner's wording and applies to installing it",
          body.startswith("Microsoft withdrew this update for new installations. Replacement: KB5000003.")
          and "not to devices that already installed it" in body, body)


# ------------------------------------------------------------------------ [W] wording

def check_wording() -> None:
    pause = []
    for path in [*(_AUX / "scripts").glob("*.py"), *(_AUX / "scripts" / "lib").glob("*.py"),
                 *(_AUX / "_includes").glob("*.html"), *(_AUX / "_layouts").glob("*.html")]:
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"[^\n]*(?:Pause updates|pause Windows Update|disable Windows Update)[^\n]*", text, re.I):
            if not m.group(0).lstrip().startswith("#") and "no advice" not in m.group(0).lower():
                pause.append(f"{path.name}: {m.group(0).strip()[:80]}")
    check("G3-W1 no writer, include or layout advises pausing or disabling Windows Update", not pause, str(pause[:3]))
    causal = re.compile(r"\b(introduced|caused by|regression)\b", re.I)
    bodies = [pd.public_body(decide(r), r, n) for r in (record(), win_record(), record(product_id="x"))
              for n in (1, 2, 40)]
    check("G3-W2 no causal word appears in a line no reviewed reason supports",
          not any(causal.search(b) for b in bodies), str([b for b in bodies if causal.search(b)][:1]))


# ------------------------------------------------------------------------ [Q] QA severities

def _qa_tree(tmp: Path, reasons: list, rows: list, conf_records: list = (), rec_over: dict | None = None):
    """A one-page QA fixture: (record paths, evidence, reasons, lifecycle, projection path)."""
    gen = tmp / "gen"
    gen.mkdir(parents=True, exist_ok=True)
    paths = []
    rec = record(update_entry=True, update_decision_label="TEST FIRST", accepted_report_sources=[],
                 permalink="/updates/t/obs-studio/99-0-0/", **(rec_over or {}))
    for i, data in enumerate([rec, *[dict(c, update_entry=True, update_report_count=0) for c in conf_records]]):
        path = gen / f"r{i}.md"
        path.write_text("---\n" + yaml.safe_dump(data) + "---\nbody\n", encoding="utf-8")
        paths.append(path)
    ev = tmp / "ev.yml"
    ev.write_text(yaml.safe_dump({"schema_version": 1, "evidence": [
        dict(r, product_id=OBS, update_version="99.0.0", counted=True, patch_version_matched=True) for r in rows]}),
        encoding="utf-8")
    rs = tmp / "reasons.yml"
    rs.write_text(yaml.safe_dump({"schema_version": 1, "entries": reasons}), encoding="utf-8")
    life = tmp / "life.yml"
    life.write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    return paths, ev, rs, life, tmp / "verdict_projection.yml"


def _qa_scan(qa, tree):
    paths, ev, rs, life, proj = tree
    saved = (qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH)
    try:
        qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH = rs, life, ev, proj
        return qa.scan_verdict_policy(paths)
    finally:
        qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH = saved


def check_qa(tmp: Path) -> None:
    import qa_patch_records as qa
    tmp.mkdir(parents=True, exist_ok=True)
    # One counted row, an entry citing two: unsupported.
    tree = _qa_tree(tmp / "q1", [entry("t")], [row(1)])
    errors, warnings = _qa_scan(qa, tree)
    codes_w = {w["code"] for w in warnings}
    check("G3-Q1 an entry whose rows stopped counting is a WARNING, never an error",
          not errors and "verdict_reason_unsupported" in codes_w, f"{errors} {codes_w}")
    promoted, kept = qa.promote_for_publication(errors, warnings)
    check("G3-Q2 ...and publish-strict does not promote it (the page has already fallen back)",
          not promoted and "verdict_reason_unsupported" in {w["code"] for w in kept}
          and "verdict_policy_drift" in codes_w)
    bad = _qa_tree(tmp / "q3", [entry("b", scope="nope")], [row(1)])
    errors, _w = _qa_scan(qa, bad)
    check("G3-Q3 a malformed reason file is an ERROR (it only changes by reviewed pull request)",
          "verdict_reasons_invalid" in {e["code"] for e in errors}, str(errors)[:200])

    # G3-Q4: what the gate will READ against what Python decides. Two counted rows support entry t.
    good = _qa_tree(tmp / "q4", [entry("t")], [row(1), row(2)])
    paths, ev, rs, life, proj = good
    errors_absent, _w = _qa_scan(qa, good)
    data = yaml.safe_load(paths[0].read_text(encoding="utf-8").split("---")[1])
    right = vp.project([data], {(OBS, "99.0.0", ""): [row(1), row(2)]}, [entry("t")], [])[0]
    proj.write_text(vp.render(right), encoding="utf-8")
    errors_right, _w = _qa_scan(qa, good)
    forged = copy.deepcopy(right)
    forged["pages"][vp.page_key(data)].update(verdict="WAIT")
    proj.write_text(vp.render(forged), encoding="utf-8")
    errors_forged, _w = _qa_scan(qa, good)
    stale = copy.deepcopy(right)
    stale["pages"][vp.page_key(data)]["body"] = "A line nobody decided."
    proj.write_text(vp.render(stale), encoding="utf-8")
    errors_stale, _w = _qa_scan(qa, good)
    proj.write_text(vp.render({"schema_version": 1, "pages": {}}), encoding="utf-8")
    errors_empty, _w = _qa_scan(qa, good)
    codes = lambda es: {e["code"] for e in es}  # noqa: E731
    check("G3-Q4 a Python/rendered disagreement is an ERROR: a forged verdict, a stale line or an empty "
          "projection where the authority gives TEST FIRST; the exact projection, or none, is clean",
          "verdict_render_disagrees" not in codes(errors_absent) | codes(errors_right)
          and all("verdict_render_disagrees" in codes(es) for es in (errors_forged, errors_stale, errors_empty)),
          f"absent={codes(errors_absent)} right={codes(errors_right)} forged={codes(errors_forged)} "
          f"stale={codes(errors_stale)} empty={codes(errors_empty)}")
    proj.write_text(vp.render({"schema_version": 1, "pages": {}, "error": "EvidenceStoreError: unreadable"}),
                    encoding="utf-8")
    errors_failed, _w = _qa_scan(qa, good)
    proj.write_text("schema_version: 1\npages: [not, a, mapping]\n", encoding="utf-8")
    errors_invalid, _w = _qa_scan(qa, good)
    check("G3-Q6 a projection whose builder failed, or that cannot be read, is an ERROR",
          "verdict_projection_failed" in codes(errors_failed)
          and "verdict_projection_invalid" in codes(errors_invalid),
          f"{codes(errors_failed)} {codes(errors_invalid)}")

    # G3-Q5: the warning says what the page renders. A1's shape (the WAIT's confirmation reworded,
    # a TEST FIRST still supported) and A2's (one of two rows left).
    conf_rec = {"product_id": OBS, "update_version": "100.1.0",
                "official_patch_notes_body": "* Fixed a crash in the test setup [dev]"}
    a1 = _qa_tree(tmp / "q5a", [entry("w", "WAIT", "regression", rows=(1,), official_confirmation=CONF_REWORDED),
                                entry("t", rows=(2, 3))], [row(1), row(2), row(3)], [conf_rec])
    _e1, w1 = _qa_scan(qa, a1)
    a2 = _qa_tree(tmp / "q5b", [entry("a2", rows=(1,))], [row(1), row(2)])
    _e2, w2 = _qa_scan(qa, a2)
    msg1 = next((w["message"] for w in w1 if w["code"] == "verdict_reason_unsupported"), "")
    msg2 = next((w["message"] for w in w2 if w["code"] == "verdict_reason_unsupported"), "")
    check("G3-Q5 the unsupported-entry warning names what the page actually renders: the next supported "
          "TEST FIRST in A1's shape, INSUFFICIENT DATA in A2's -- never a fall-back it does not make",
          "renders 'TEST FIRST if you use the test setup'" in msg1 and "INSUFFICIENT DATA" not in msg1
          and "renders 'INSUFFICIENT DATA'" in msg2, f"A1: {msg1[-160:]} | A2: {msg2[-120:]}")


# ------------------------------------------------------------------------ [R] Liquid == Python

_RENDER_RB = r"""
require 'liquid'
require 'json'
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
tpl = Liquid::Template.parse(payload["template"])
out = {}
payload["cases"].each do |name, c|
  begin
    out[name] = tpl.render!({ "rec" => c["rec"], "cnt" => c["cnt"], "site" => payload["site"] })
  rescue => e
    out[name] = "<<ERR #{e.class}: #{e.message}>>"
  end
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""
PROBE = "@@{{ gate_label }}|{{ gate_scope }}|{{ gate_body }}|{{ gate_panel_heading }}|{{ gate_panel_text }}@@"


def gate_template(text: str | None = None) -> str:
    text = text if text is not None else GATE_PATH.read_text(encoding="utf-8")
    return text.replace("include.record", "rec").replace("include.count", "cnt") + PROBE


def render_gate(cases: dict, site_data: dict, template: str | None = None) -> dict | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script, payload, out = Path(td) / "g.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload.write_text(json.dumps({"template": gate_template(template), "site": {"data": site_data},
                                       "cases": cases}, default=str), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=900)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


def parse_probe(text: str) -> tuple | None:
    m = re.search(r"@@(.*?)\|(.*?)\|(.*?)\|(.*?)\|(.*?)@@", text or "", re.S)
    return tuple(s.strip() for s in m.groups()) if m else None


def python_view(rec: dict, reasons: list, life: list, count: int) -> tuple:
    d = pd.decide(rec, valid_reasons=reasons, lifecycle=life)
    heading = pd.PANEL_HEADING.get(d.panel_kind, "")
    return (d.verdict, d.scope, pd.public_body(d, rec, count), heading, pd.panel_text(d))


# The synthetic matrix. Every case is its own page (its own identity), with the rows COUNTED on it,
# the reason entries naming it, and the verdict it must render whatever the template does. The
# gate is given ONLY the projection Python builds from these facts (no reason file at all), so a
# case passes only if the authority's answer reaches the page unchanged. One case per support rule
# (F1 x3, F2, F3, OC x2) as review 1 asked: the gate holds no copy of them, and each must still
# fail closed on the rendered page.
CONF_OK = {"product_id": OBS, "update_version": "100.0.0", "statement": "Fixed the test setup crash"}
CONF_REWORDED = {"product_id": OBS, "update_version": "100.1.0", "statement": "Fixed the test setup crash"}
CONF_RECORDS = [
    {"product_id": OBS, "update_version": "100.0.0", "official_patch_notes_body": "* Fixed the\r\ntest setup crash [dev]"},
    # A1's shape: the vendor note no longer carries the statement verbatim.
    {"product_id": OBS, "update_version": "100.1.0", "official_patch_notes_body": "* Fixed a crash in the test setup [dev]"},
]


def _case(version: str, n: int, rows, entries=(), want: str = "INSUFFICIENT DATA", *, rec=None, **over) -> dict:
    base = rec if rec is not None else record(update_version=version)
    base = dict(base, update_report_count=n, **over)
    return {"rec": base, "n": n, "rows": list(rows), "entries": list(entries), "want": want}


def _e(eid, version, verdict="TEST FIRST", rclass="corroborated_issue", **kw):
    return entry(eid, verdict, rclass, version=version, **kw)


def matrix_cases() -> dict:
    twins = [row(1, "Same words posted twice."), row(2, "Same words  posted twice.")]
    return {
        "wait+also": _case("9.1", 4, [row(1), row(2), row(3), row(4)],
                           [_e("w", "9.1", "WAIT", "regression"), _e("t", "9.1", rows=(3, 4))], "WAIT"),
        "tf-only": _case("9.2", 2, [row(3), row(4)], [_e("t2", "9.2", rows=(3, 4))], "TEST FIRST"),
        "F1-withdrawn": _case("9.3", 1, [row(1)], [_e("f1w", "9.3")]),
        "F1-url-differs": _case("9.4", 2, [row(1), row(2)],
                                [dict(_e("f1u", "9.4"), evidence=[{"id": "row-1", "source_url": URLS[0]},
                                                                  {"id": "row-2", "source_url": URLS[3]}])]),
        "F1-other-page": _case("9.5", 2, [row(3), row(4)], [_e("f1o", "9.5")]),
        "F2-one-reporter": _case("9.7", 2, [row(1), row(2)], [_e("f2", "9.7", rows=(1,))]),
        "F3-twins": _case("9.8", 2, twins, [_e("f3", "9.8")]),
        "OC-found": _case("9.9", 1, [row(1)],
                          [_e("oc", "9.9", "WAIT", "regression", rows=(1,), official_confirmation=CONF_OK)], "WAIT"),
        "OC-reworded": _case("9.10", 3, [row(1), row(2), row(3)],
                             [_e("ocr", "9.10", "WAIT", "regression", rows=(1,), official_confirmation=CONF_REWORDED),
                              _e("ocr-t", "9.10", rows=(2, 3))], "TEST FIRST"),
        "A2-one-of-two": _case("9.11", 4, [row(1), row(2)],
                               [_e("a2", "9.11", "TEST FIRST", "corroborated_install_problem", rows=(1,),
                                   scope="when installing it")]),
        "stored-wait-no-row": _case("9.12", 5, [row(1)], [], update_decision_label="WAIT",
                                    update_consensus_summary="WAIT: a stored line"),
        "nothing-2": _case("9.13", 2, [row(1), row(2)]),
        "nothing-1": _case("9.14", 1, [row(1)]),
        "zero": _case("9.15", 0, []),
        "sec-0": _case("", 0, [], rec=win_record(build="26200.1100"), want="SECURITY UPDATE"),
        "sec-1": _case("", 1, [row(1)], rec=win_record(build="26200.1101"), want="SECURITY UPDATE"),
        "sec-9": _case("", 9, [row(1), row(2)], rec=win_record(build="26200.1102"), want="SECURITY UPDATE"),
        "sec-install": _case("", 2, [row(1), row(2)], [
            entry("si", "TEST FIRST", "corroborated_install_problem", pid=WIN, version="25H2", build="26200.1000",
                  scope="when installing it")], rec=win_record(build="26200.1000"), want="SECURITY UPDATE"),
        "sec-regression": _case("", 2, [row(1), row(2)], [
            entry("sr", "WAIT", "regression", pid=WIN, version="25H2", build="26200.3000")],
            rec=win_record(build="26200.3000"), want="SECURITY UPDATE"),
        "sec-unsupported": _case("", 1, [row(1)], [
            entry("su", "TEST FIRST", "corroborated_install_problem", pid=WIN, version="25H2", build="26200.3100",
                  scope="when installing it")], rec=win_record(build="26200.3100"), want="SECURITY UPDATE"),
        "sec-forged-row": _case("", 3, [row(1)], [], rec=win_record(build="26200.3200"), want="SECURITY UPDATE"),
        "avoid-preview": _case("", 1, [row(1)], rec=win_record(update_type="2026-03 D", kb="KB5000002",
                                                               build="26200.2000"), want="AVOID"),
        "avoid-security": _case("", 0, [], rec=win_record(kb="KB5000002", build="26100.2000"), want="AVOID"),
        "oob": _case("", 2, [row(1), row(2)], rec=win_record(update_type="2026-03 OOB", build="26200.5000")),
        "preview-tf": _case("", 2, [row(1), row(2)], [
            entry("ptf", pid=WIN, version="25H2", build="26200.4000")],
            rec=win_record(update_type="2026-03 D", build="26200.4000"), want="TEST FIRST"),
    }


def matrix_facts(cases: dict) -> tuple[list, dict, list, dict]:
    """(records, counted rows by identity, every entry, the projection Python builds from them)."""
    records = [c["rec"] for c in cases.values()] + CONF_RECORDS
    counted = {vr.record_identity(c["rec"]): c["rows"] for c in cases.values()}
    # F1-other-page: its cited rows are counted, but on ANOTHER page.
    counted[(OBS, "9.6", "")] = [row(1), row(2)]
    entries = [e for c in cases.values() for e in c["entries"]]
    projection, _unsupported = vp.project(records, counted, entries, LIFE)
    return records, counted, entries, projection


def matrix_expectations(cases: dict, records, counted, entries) -> dict:
    by_ident = {vr.record_identity(r): r for r in records}
    valid, _u = vr.valid_reasons_by_identity(entries, counted, by_ident)
    return {k: python_view(c["rec"], valid.get(vr.record_identity(c["rec"]), []), LIFE, c["n"])
            for k, c in cases.items()}


TEMPLATE_OVERRIDE: str | None = None   # set only by the template mutants in [X]
RULE_CASES = (
    ("G3-R4a F1: a cited row that stopped counting (an audited withdrawal) falls back", "F1-withdrawn"),
    ("G3-R4b F1: a cited row whose counted URL differs falls back", "F1-url-differs"),
    ("G3-R4c F1: a cited row counted on ANOTHER page falls back", "F1-other-page"),
    ("G3-R4d F2: one reporter without an official confirmation falls back", "F2-one-reporter"),
    ("G3-R4e F3: the same text posted twice is one reporter, and falls back", "F3-twins"),
    ("G3-R4f OC: a confirmation found verbatim admits one reporter (WAIT renders)", "OC-found"),
    ("G3-R4g OC: a reworded confirmation drops the WAIT to the next supported entry (A1's shape)", "OC-reworded"),
    ("G3-R4h a page with no projected row renders no verdict from its stored WAIT", "stored-wait-no-row"),
    ("G3-R4i A2's shape: an entry left with one of its two rows falls back", "A2-one-of-two"),
    ("G3-R4j a forged WAIT row on a security page cannot displace SECURITY UPDATE", "sec-forged-row"),
)


def check_render_matrix(template: str | None = None) -> None:
    template = template if template is not None else TEMPLATE_OVERRIDE
    cases = matrix_cases()
    records, counted, entries, projection = matrix_facts(cases)
    want = matrix_expectations(cases, records, counted, entries)
    site_projection = copy.deepcopy(projection)
    site_projection["pages"][vp.page_key(cases["sec-forged-row"]["rec"])] = {
        "verdict": "WAIT", "scope": "if you use the test setup", "rule": "R3", "reasons": ["forged"],
        "body": "A forged line.", "panel_heading": "", "panel_text": ""}
    site = {"verdict_projection": site_projection, "patch_lifecycle": {"schema_version": 1, "entries": LIFE},
            # Present ONLY for the template mutants that try to read it; the shipped gate never does.
            "verdict_reasons": {"schema_version": 1, "entries": entries}}
    slim = {k: {"rec": dict(c["rec"], accepted_report_sources=[{"source_url": r["source_url"]} for r in c["rows"]]),
                "cnt": c["n"]} for k, c in cases.items()}
    out = render_gate(slim, site, template)
    check("G3-R0 the liquid gem is available, so the template checks run for real",
          out is not None and "__error__" not in out, str(out)[:200] if out else "ruby missing")
    if not out or "__error__" in out:
        return
    got = {k: parse_probe(out.get(k, "")) for k in cases}
    diffs = [(k, got[k], want[k]) for k in cases if got[k] != want[k]]
    check(f"G3-R1 the gate renders exactly what decide/public_body/panel_text say ({len(cases)} cases: "
          "every rule, both panels, zero reports, a withdrawn citation)", not diffs, str(diffs[:2])[:600])
    verdicts = {k: (g or ("",))[0] for k, g in got.items()}
    absolute = {k: c["want"] for k, c in cases.items()}
    check("G3-R2 the matrix is not vacuous: it reaches all five published verdicts, each case renders the "
          "verdict written beside it, and both security panels render",
          verdicts == absolute and set(verdicts.values()) == {"AVOID", "SECURITY UPDATE", "WAIT", "TEST FIRST",
                                                              "INSUFFICIENT DATA"}
          and (got["sec-install"] or ("",) * 5)[3] == "Affected configuration"
          and (got["sec-regression"] or ("",) * 5)[3] == "Deployment caution",
          str({k: (verdicts[k], absolute[k]) for k in cases if verdicts[k] != absolute[k]}))
    for label, name in RULE_CASES:
        check(label, got[name] == want[name] and verdicts[name] == absolute[name],
              f"rendered {got[name]!r}; authority {want[name][:2]!r}; expected {absolute[name]!r}")

    # No projection at all (a local render, a fresh checkout): fail closed, official facts remain.
    bare = render_gate(slim, {"patch_lifecycle": {"schema_version": 1, "entries": LIFE},
                              "verdict_reasons": {"schema_version": 1, "entries": entries}}, template)
    bare_got = {k: parse_probe((bare or {}).get(k, "")) or ("",) * 5 for k in cases}
    reasoned = [k for k, g in bare_got.items() if g[0] in ("WAIT", "TEST FIRST") or g[4]]
    official = {k: bare_got[k][0] for k in ("sec-9", "sec-install", "avoid-preview", "avoid-security")}
    check("G3-R5 with no projection the gate publishes no WAIT, no TEST FIRST and no panel, and the "
          "official verdicts still render",
          bare is not None and "__error__" not in bare and not reasoned
          and official == {"sec-9": "SECURITY UPDATE", "sec-install": "SECURITY UPDATE",
                           "avoid-preview": "AVOID", "avoid-security": "AVOID"},
          f"{reasoned} {official}")


# ------------------------------------------------------------------------ corpus facts (shared)

_CORPUS: dict = {}


def corpus() -> dict:
    """The shipped records, their counted evidence, the authority's supported entries and the
    projection a deploy builds from this tree. Loaded once."""
    if _CORPUS:
        return _CORPUS
    from lib import report_counts  # noqa: PLC0415 - imports the collector base; offline
    gen = _AUX / "updates" / "generated"
    recs = []
    for path in sorted(gen.glob("*.md")):
        m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", path.read_text(encoding="utf-8"), re.S)
        data = yaml.safe_load(m.group(1)) if m else {}
        if isinstance(data, dict) and data.get("update_entry") is True:
            recs.append(data)
    rows = report_counts.load_evidence_store(_AUX / "_data" / "consensus_evidence.yml")
    groups = report_counts.counted_evidence_rows(
        rows, windows_targets=report_counts.windows_targets_from_front_matter(recs))
    by_ident = {vr.record_identity(r): r for r in recs}
    valid, unsupported = vr.valid_reasons_by_identity(REASONS["entries"], groups, by_ident)
    projection, _u = vp.project(recs, groups, REASONS["entries"], LIFECYCLE["entries"])
    _CORPUS.update(recs=recs, groups=groups, valid=valid, unsupported=unsupported, projection=projection)
    return _CORPUS


def slim(r: dict) -> dict:
    s = {k: r.get(k) for k in ("product_id", "update_version", "target_build", "target_kb", "update_type")}
    s["accepted_report_sources"] = [{"source_url": x.get("source_url")} for x in r.get("accepted_report_sources") or []]
    return s


def check_render_corpus() -> None:
    c = corpus()
    recs = c["recs"]
    cases = {str(i): {"rec": slim(r), "cnt": int(r.get("update_report_count") or 0)} for i, r in enumerate(recs)}
    want = {str(i): python_view(r, c["valid"].get(vr.record_identity(r), []), LIFECYCLE["entries"],
                                int(r.get("update_report_count") or 0)) for i, r in enumerate(recs)}
    out = render_gate(cases, {"verdict_projection": c["projection"], "patch_lifecycle": LIFECYCLE})
    if not out or "__error__" in out:
        check("G3-R3 the gate renders the authority's verdict on every corpus record", False, str(out)[:200])
        return
    diffs = [(recs[int(k)].get("permalink"), parse_probe(out.get(k, "")), w) for k, w in want.items()
             if parse_probe(out.get(k, "")) != w]
    check(f"G3-R3 over all {len(recs)} records the gate, reading this tree's projection, renders the "
          "authority's verdict, scope, line and panel", not diffs and len(recs) > 1000, str(diffs[:2])[:600])


# ------------------------------------------------------------------------ [P] one authority: the projection

OBS_NOTE = "Fixed a crash on macOS 27.2 when starting OBS Studio"
A2_ENTRY = "adobe-acrobat-pro:15.023.20053:installer-exit-code-7"


def probe_a1() -> tuple[list, list, dict]:
    """Review 1's probe A1: OBS 33.0.0's stored note reworded, nothing else changed."""
    c = corpus()
    recs = copy.deepcopy(c["recs"])
    hits = 0
    for r in recs:
        if r.get("product_id") == OBS and str(r.get("update_version")) == "33.0.0":
            body = str(r.get("official_patch_notes_body") or "")
            hits += body.count(OBS_NOTE)
            r["official_patch_notes_body"] = body.replace(OBS_NOTE, "Fixed a startup crash on macOS 27.2")
    assert hits >= 1, "the OBS 33.0.0 note this probe rewords is no longer stored"
    return recs, REASONS["entries"], {"target": (OBS, "32.2.2", "")}


def probe_a2() -> tuple[list, list, dict]:
    """Review 1's probe A2: one of the two rows dropped from the Acrobat 15.023.20053 entry."""
    reasons = copy.deepcopy(REASONS["entries"])
    target = next(e for e in reasons if e["id"] == A2_ENTRY)
    assert len(target["evidence"]) == 2, "the A2 entry no longer cites exactly two rows"
    target["evidence"] = target["evidence"][:1]
    return copy.deepcopy(corpus()["recs"]), reasons, {"target": ("adobe-acrobat-pro", "15.023.20053", "")}


def render_probe(recs: list, reasons: list, target: tuple, template: str | None = None,
                 project_fn=None) -> tuple[tuple | None, tuple]:
    """(rendered probe, authority view) for the target page, the projection rebuilt from the
    probe's facts exactly as a deploy would."""
    c = corpus()
    by_ident = {vr.record_identity(r): r for r in recs}
    valid, _u = vr.valid_reasons_by_identity(reasons, c["groups"], by_ident)
    projection, _u2 = (project_fn or vp.project)(recs, c["groups"], reasons, LIFECYCLE["entries"])
    rec = by_ident[target]
    n = int(rec.get("update_report_count") or 0)
    out = render_gate({"p": {"rec": slim(rec), "cnt": n}},
                      {"verdict_projection": projection, "patch_lifecycle": LIFECYCLE,
                       "verdict_reasons": {"schema_version": 1, "entries": reasons}},
                      template if template is not None else TEMPLATE_OVERRIDE)
    return parse_probe((out or {}).get("p", "")), python_view(rec, valid.get(target, []), LIFECYCLE["entries"], n)


PROJECT_OVERRIDE = None   # set only by the projection mutant in [X]


def check_projection_probes() -> None:
    recs, reasons, meta = probe_a1()
    got, want = render_probe(recs, reasons, meta["target"], project_fn=PROJECT_OVERRIDE)
    check("G3-P3 probe A1 (OBS 33.0.0's note reworded) fails closed on the rendered 32.2.2 page: the "
          "unsupported WAIT is gone and the page renders the authority's TEST FIRST",
          got is not None and got == want and got[:2] == ("TEST FIRST", "if you use the menu-bar icon on macOS 27"),
          f"rendered {got and got[:2]!r}; authority {want[:2]!r}")
    recs, reasons, meta = probe_a2()
    got, want = render_probe(recs, reasons, meta["target"], project_fn=PROJECT_OVERRIDE)
    check("G3-P4 probe A2 (one of two rows dropped from the Acrobat 15.023.20053 entry) fails closed on the "
          "rendered page: INSUFFICIENT DATA, as the authority decides",
          got is not None and got == want and got[:2] == ("INSUFFICIENT DATA", ""),
          f"rendered {got and got[:2]!r}; authority {want[:2]!r}")


def check_projection() -> None:
    c = corpus()
    rows = c["projection"]["pages"]
    expect, wrong = {}, []
    for r in c["recs"]:
        mine = c["valid"].get(vr.record_identity(r), [])
        if mine:
            d = pd.decide(r, valid_reasons=mine, lifecycle=LIFECYCLE["entries"])
            expect[vp.page_key(r)] = vp.row_for(d, r)
    check(f"G3-P1 the projection IS the authority: one row per page with a supported entry ({len(rows)}), "
          "each equal to decide/public_body/panel_text for that page",
          rows == expect and len(rows) >= 1 and all(set(v) == set(vp.ROW_KEYS) for v in rows.values()),
          str(sorted(set(rows) ^ set(expect)))[:300])
    model = [(r.get("permalink"), vp.rendered_verdict(r, rows, LIFECYCLE["entries"]))
             for r in c["recs"]
             if vp.rendered_verdict(r, rows, LIFECYCLE["entries"])
             != (lambda d: (d.verdict, d.scope))(pd.decide(r, valid_reasons=c["valid"].get(vr.record_identity(r), []),
                                                          lifecycle=LIFECYCLE["entries"]))]
    check(f"G3-P2 QA's model of the gate (rendered_verdict) equals decide on all {len(c['recs'])} records",
          not model, str(model[:3]))
    gate = GATE_PATH.read_text(encoding="utf-8")
    code = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", gate, flags=re.S)
    check("G3-P0 the gate holds no copy of the support rule: it reads no reason entry, no cited row and no "
          "accepted source, only the projection and the two official facts",
          "verdict_reasons" not in code and "accepted_report_sources" not in code and ".evidence" not in code
          and "site.data.verdict_projection.pages[pvg_key]" in code, "")


def check_projection_builder(tmp: Path) -> None:
    """The bare script pages.yml runs, on a temp tree: writes the projection, and fails closed."""
    script = _AUX / "scripts" / "build_verdict_projection.py"
    out = tmp / "vp.yml"
    proc = subprocess.run([sys.executable, str(script), "--output", str(out)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(_REPO), timeout=600)
    written = vp.load(out) if out.exists() else None
    check("G3-P5 build_verdict_projection.py, run as pages.yml runs it, writes exactly this tree's projection",
          proc.returncode == 0 and written is not None and written.get("pages") == corpus()["projection"]["pages"],
          (proc.stdout + proc.stderr)[-300:])
    root = tmp / "broken"
    (root / "_data").mkdir(parents=True)
    (root / "updates" / "generated").mkdir(parents=True)
    (root / "_data" / "consensus_evidence.yml").write_text("evidence: [unclosed\n", encoding="utf-8")
    bad_out = tmp / "vp_bad.yml"
    bad = subprocess.run([sys.executable, str(script), "--root", str(root), "--output", str(bad_out)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(_REPO),
                         timeout=300)
    bad_written = vp.load(bad_out) if bad_out.exists() else None
    check("G3-P6 an unreadable evidence store writes an EMPTY projection carrying the error and exits 0 "
          "(rendered: fail closed; QA then errors)",
          bad.returncode == 0 and bad_written is not None and bad_written.get("pages") == {}
          and bool(bad_written.get("error")) and "::warning::" in bad.stdout, (bad.stdout + bad.stderr)[-300:])
    ignored = (_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    order = {}
    for wf_name in ("pages.yml", "davinci-archive-build-check.yml"):
        wf = yaml.safe_load((_REPO / ".github" / "workflows" / wf_name).read_text(encoding="utf-8"))
        steps = next(iter((wf.get("jobs") or {}).values())).get("steps") or [] if wf_name != "pages.yml" \
            else (wf.get("jobs") or {}).get("build", {}).get("steps") or []
        runs = [str(s.get("run") or "") for s in steps]
        at = lambda needle: next((i for i, r in enumerate(runs) if needle in r), -1)  # noqa: E731
        order[wf_name] = (at("pip install"), at("build_verdict_projection.py"), at("qa_patch_records.py"),
                          at("jekyll build"))
    check("G3-P7 pages.yml and the DaVinci archive build check build the projection after pip install, "
          "BEFORE QA and BEFORE Jekyll; the projection is git-ignored",
          "auxsays/_data/verdict_projection.yml" in ignored
          and all(-1 < p < g < q < b for p, g, q, b in order.values()), str(order))


# ------------------------------------------------------------------------ [S] the scope prints with the verdict

_INCLUDE_RB = r"""
require 'liquid'
require 'json'
module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def where(input, prop, val) = Array(input).select { |x| x.is_a?(Hash) && x[prop].to_s == val.to_s }
end
Liquid::Template.register_filter(Shims)
class JekyllInclude < Liquid::Tag
  SYNTAX = /([\w.\/-]+)((\s+\w+\s*=\s*(?:"[^"]*"|'[^']*'|[\w.\[\]\/-]+))*)/
  def initialize(name, markup, tokens)
    super
    m = markup.strip.match(SYNTAX) or raise Liquid::SyntaxError, "bad include: #{markup}"
    @file = m[1]
    @params = {}
    (m[2] || "").scan(/(\w+)\s*=\s*("[^"]*"|'[^']*'|[\w.\[\]\/-]+)/) { |k, v| @params[k] = v }
  end
  def render(context)
    path = File.join(context.registers[:include_root], @file)
    raise Liquid::FileSystemError, "missing include #{@file}" unless File.exist?(path)
    vals = {}
    @params.each { |k, v| vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v] }
    partial = (context.registers[:cache] ||= {})[path] ||=
      Liquid::Template.parse(File.read(path, encoding: "utf-8"))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
out = {}
payload["cases"].each do |name, c|
  begin
    tpl = Liquid::Template.parse(c["template"])
    out[name] = tpl.render!({ "site" => payload["site"], "item" => c["item"], "summary" => c["summary"] },
                            registers: { include_root: payload["includes"] })
  rescue => e
    out[name] = "<<ERR #{e.class}: #{e.message}>>"
  end
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""
INCLUDE_OVERRIDES: dict = {}   # {include file name: mutated text}, set only by the surface mutants in [X]


def render_includes(cases: dict, site: dict) -> dict | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        inc = Path(td) / "_includes"
        shutil.copytree(_AUX / "_includes", inc)
        for name, text in INCLUDE_OVERRIDES.items():
            (inc / name).write_text(text, encoding="utf-8")
        script, payload, out = Path(td) / "i.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_INCLUDE_RB, encoding="utf-8")
        payload.write_text(json.dumps({"cases": cases, "site": site, "includes": str(inc)}, default=str),
                           encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


def identity_of(r: dict) -> str:
    """The exact patch name the writer puts in the summary: product + build-aware display label."""
    from lib.patch_identity import patch_display_label  # noqa: PLC0415
    return (f"{str(r.get('update_product') or r.get('product_id') or '').strip()} "
            f"{patch_display_label(r.get('update_version'), r.get('target_build'), r.get('product_id'))}")


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


ROW_T = "{% include patch-table-row.html item=item %}"
FEED_T = "{% include patch-feed-summary.html item=item summary=summary %}@@{{ feed_summary_line }}@@"


def check_surfaces() -> None:
    """G3-S1..S3: every surface that prints a scoped verdict prints its scope, on the shipped corpus."""
    c = corpus()
    rows = c["projection"]["pages"]
    scoped = [r for r in c["recs"] if vp.rendered_verdict(r, rows, LIFECYCLE["entries"])[1]]
    site = {"data": {"verdict_projection": c["projection"], "patch_lifecycle": LIFECYCLE,
                     "patch_verdicts": yaml.safe_load((_AUX / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8"))}}
    cases = {}
    for i, r in enumerate(scoped):
        item = dict(r, url=r.get("permalink"))
        cases[f"row:{i}"] = {"template": ROW_T, "item": item, "summary": ""}
        cases[f"feed:{i}"] = {"template": FEED_T, "item": item,
                              "summary": str(r.get("update_consensus_summary") or "")}
    # A stored summary that LAGS the policy (round 0's format) must still not lead the card.
    drift = scoped[0] if scoped else {}
    drift_v, drift_s = vp.rendered_verdict(drift, rows, LIFECYCLE["entries"]) if drift else ("", "")
    cases["feed:drift"] = {"template": FEED_T, "item": dict(drift, url=drift.get("permalink")),
                           "summary": f"{drift_v}: {drift.get('update_product')} has 53 user reports found."}
    # ...and one that opens with the right verdict and scope but carries a reason the page no longer gives.
    cases["feed:stale-line"] = {"template": FEED_T, "item": dict(drift, url=drift.get("permalink")),
                                "summary": f"{vp.phrase(drift_v, drift_s)}: {identity_of(drift)}. An old reason."}
    out = render_includes(cases, site) or {}
    bad_rows, bad_feed, bad_store = [], [], []
    for case in ("feed:drift", "feed:stale-line"):
        drift_line = re.search(r"@@(.*?)@@", out.get(case, ""), re.S)
        if not drift_line or not drift_line.group(1).startswith(f"{vp.phrase(drift_v, drift_s)}: ") \
                or "An old reason" in drift_line.group(1) or "53 user reports found" in drift_line.group(1):
            bad_feed.append((f"lagging stored summary ({case})", drift_line and drift_line.group(1)[:80]))
    for i, r in enumerate(scoped):
        verdict, scope = vp.rendered_verdict(r, rows, LIFECYCLE["entries"])
        cell = re.search(r'<td data-label="Verdict">(.*?)</td>', out.get(f"row:{i}", ""), re.S)
        if not cell or _text(cell.group(1)) != f"{verdict} {scope}":
            bad_rows.append((r.get("permalink"), cell and _text(cell.group(1)), out.get(f"row:{i}", "")[:120]))
        line = re.search(r"@@(.*?)@@", out.get(f"feed:{i}", ""), re.S)
        if not str(r.get("update_consensus_summary") or "").strip():
            # No stored summary (no reports): the card has no evidence line, so it prints no verdict.
            if not line or line.group(1).strip():
                bad_feed.append((r.get("permalink"), "a line without a stored summary", line and line.group(1)[:80]))
        elif not line or not line.group(1).startswith(f"{verdict} {scope}: "):
            bad_feed.append((r.get("permalink"), line and line.group(1)[:80]))
        d = pd.decide(r, valid_reasons=c["valid"].get(vr.record_identity(r), []), lifecycle=LIFECYCLE["entries"])
        stored = str(r.get("update_consensus_summary") or "")
        if int(r.get("update_report_count") or 0) > 0 and \
                (stored != pd.summary_line(d, r, int(r.get("update_report_count") or 0), identity=identity_of(r))
                 or (line and line.group(1) != stored)):
            bad_store.append((r.get("permalink"), stored[:60], line and line.group(1)[:60]))
    check(f"G3-S1 every product/vendor table row prints its verdict WITH its scope ({len(scoped)} scoped pages: "
          "WAIT, TEST FIRST and AVOID)", bool(scoped) and "__error__" not in out and not bad_rows,
          str(bad_rows[:2])[:400] or str(out.get("__error__", ""))[:300])
    check("G3-S2 every /updates/ feed card leads with the verdict and its scope, never the bare verdict",
          bool(scoped) and not bad_feed, str(bad_feed[:2]))
    check("G3-S3 each report-bearing scoped page's stored summary leads with the verdict and its scope, and is "
          "exactly the feed card's line (lib/patch_decision.summary_line)", bool(scoped) and not bad_store,
          str(bad_store[:2]))
    lead = [r.get("permalink") for r in c["recs"] if int(r.get("update_report_count") or 0) > 0
            and str(r.get("update_consensus_summary") or "").split(":", 1)[0].strip()
            != pd.verdict_phrase(pd.decide(r, valid_reasons=c["valid"].get(vr.record_identity(r), []),
                                           lifecycle=LIFECYCLE["entries"]))]
    check("G3-S4 every report-bearing record's stored summary opens with exactly the verdict phrase the "
          "pages render (none opens with a bare verdict beside a count)", not lead, str(lead[:3]))
    layout = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    home = (_AUX / "_layouts" / "aux-home.html").read_text(encoding="utf-8")
    check("G3-S5 the patch page and the homepage row print the scope in the same statement as the verdict",
          "<strong>{{ decision_label }}</strong>{% if decision_scope != '' %} <span class=\"update-decision-scope\">"
          "{{ decision_scope }}</span>{% endif %}" in layout
          and "Verdict: {{ decision_label }}{% if decision_scope != '' %} {{ decision_scope }}{% endif %}" in home, "")


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


def wrap_decide(transform):
    real = pd.decide

    def mutated(record, *, valid_reasons=(), lifecycle=()):
        return transform(real(record, valid_reasons=valid_reasons, lifecycle=lifecycle), record or {},
                         list(valid_reasons or ()))
    return swap(pd, "decide", mutated)


URL_RULE_GATE = """{%- assign pvg_row = nil -%}{%- assign pvg_row_rank = 99 -%}
{%- capture pvg_urls -%}|{%- for pvg_src in pvg_record.accepted_report_sources -%}{{ pvg_src.source_url }}|{%- endfor -%}{%- endcapture -%}
{%- for pvg_e in site.data.verdict_reasons.entries -%}
  {%- assign pvg_e_version = pvg_e.update_version | append: '' | strip -%}
  {%- assign pvg_e_build = pvg_e.target_build | append: '' | strip -%}
  {%- if pvg_e.product_id == pvg_pid and pvg_e_version == pvg_version and pvg_e_build == pvg_build -%}
    {%- assign pvg_ok = true -%}
    {%- for pvg_ev in pvg_e.evidence -%}{%- assign pvg_k = '|' | append: pvg_ev.source_url | append: '|' -%}{%- unless pvg_urls contains pvg_k -%}{%- assign pvg_ok = false -%}{%- endunless -%}{%- endfor -%}
    {%- if pvg_e.verdict == 'WAIT' -%}{%- assign pvg_r = 1 -%}{%- else -%}{%- assign pvg_r = 2 -%}{%- endif -%}
    {%- if pvg_ok and pvg_r < pvg_row_rank -%}{%- assign pvg_row = pvg_e -%}{%- assign pvg_row_rank = pvg_r -%}{%- endif -%}
  {%- endif -%}
{%- endfor -%}
{%- assign pvg_row_verdict = pvg_row.verdict | default: '' | strip -%}
{%- assign pvg_row_scope = pvg_row.scope | default: '' | strip -%}
{%- assign pvg_row_body = pvg_row.reason | default: '' | strip -%}"""
PROJECTION_READ = """{%- assign pvg_row = site.data.verdict_projection.pages[pvg_key] -%}
{%- assign pvg_row_verdict = pvg_row.verdict | default: '' | strip -%}
{%- assign pvg_row_scope = pvg_row.scope | default: '' | strip -%}
{%- assign pvg_row_body = pvg_row.body | default: '' | strip -%}"""


def weak_project(records, groups, reasons, lifecycle):
    """The projection built with only F1 (every cited row counted, same URL): the rule round 0's gate
    applied. It diverges from decide exactly where review 1's probes did."""
    real = vr.support_problems

    def f1_only(entry_, rows, recs):
        return [p for p in real(entry_, rows, recs)
                if "distinct counted reporter" not in p and "official confirmation" not in p]
    vr.support_problems = f1_only
    try:
        return vp.project(records, groups, reasons, lifecycle)
    finally:
        vr.support_problems = real


def check_mutations(tmp: Path) -> None:
    D = pd.Decision
    import qa_patch_records as qa
    mutants: list = []
    real_support = vr.support_problems
    real_schema = vr.schema_errors
    real_body = pd.public_body
    real_add = qa.add
    real_summary = pd.summary_line

    def tpl(old: str, new: str):
        """(mutate, restore) for the SHIPPED gate include, changed in memory only."""
        text = GATE_PATH.read_text(encoding="utf-8")
        assert text.count(old) == 1, old
        return swap(sys.modules[__name__], "TEMPLATE_OVERRIDE", text.replace(old, new))

    def inc(name: str, old: str, new: str):
        """(mutate, restore) for another shipped include, changed in a temp copy only."""
        text = (_AUX / "_includes" / name).read_text(encoding="utf-8")
        assert text.count(old) == 1, old
        return swap(sys.modules[__name__], "INCLUDE_OVERRIDES", {name: text.replace(old, new)})

    qa_runs = iter(range(100))
    cases = [
        ("X1 security falls below a reason entry (R2/R3 swapped)", check_decisions,
         wrap_decide(lambda d, r, rs: D(rs[0]["verdict"], "R3", scope=rs[0]["scope"], reasons=tuple(rs))
                     if d.verdict == "SECURITY UPDATE" and rs else d)),
        ("X2 decide takes a clock", check_decisions,
         swap(pd, "decide", (lambda real: (lambda record, *, valid_reasons=(), lifecycle=(), now=None:
                                            real(record, valid_reasons=valid_reasons, lifecycle=lifecycle)))(pd.decide))),
        ("X3 negative sentiment makes a WAIT", check_decisions,
         wrap_decide(lambda d, r, rs: D("WAIT", "R3") if d.verdict == "INSUFFICIENT DATA"
                     and str(r.get("update_consensus_label") or "").lower() == "negative" else d)),
        ("X4 two or more reports make a TEST FIRST", check_decisions,
         wrap_decide(lambda d, r, rs: D("TEST FIRST", "R4") if d.verdict == "INSUFFICIENT DATA"
                     and int(r.get("update_report_count") or 0) >= 2 else d)),
        ("X5 a live record is a WAIT", check_decisions,
         wrap_decide(lambda d, r, rs: D("WAIT", "R3") if r.get("evidence_state") == "consensus_live" else d)),
        ("X6 many reports override the security classification", check_decisions,
         wrap_decide(lambda d, r, rs: D("TEST FIRST", "R4") if d.verdict == "SECURITY UPDATE"
                     and int(r.get("update_report_count") or 0) > 100 else d)),
        ("X7 a reason entry may say AVOID", check_decisions,
         swap(vr, "REASON_VERDICTS", ("WAIT", "TEST FIRST", "AVOID"))),
        ("X8 WAIT without a written material impact", check_decisions,
         swap(vr, "schema_errors", lambda entries: [m for m in real_schema(entries) if "material" not in m])),
        ("X9 a ninth verdict", check_decisions,
         swap(pd, "RISK_ORDER", pd.RISK_ORDER + ("SUPERSEDED",))),
        ("X10 the gate drops a security update at zero reports", check_render_matrix,
         tpl("{%- elsif pvg_security -%}", "{%- elsif pvg_security and pvg_count > 0 -%}")),
        ("X11 one reporter is enough", check_reason_audits,
         swap(vr, "support_problems", lambda e, rows, recs: [p for p in real_support(e, rows, recs)
                                                              if "distinct counted reporter" not in p])),
        ("X12 a critical severity makes a WAIT", check_decisions,
         wrap_decide(lambda d, r, rs: D("WAIT", "R3") if r.get("severity") == "critical" else d)),
        ("X13 a second lifecycle entry is accepted", check_lifecycle,
         swap(vr, "MAX_LIFECYCLE_ENTRIES", 2)),
        ("X14 the gate trusts a stored label when the page has no projected row", check_render_matrix,
         tpl("{%- assign gate_label = 'INSUFFICIENT DATA' -%}",
             "{%- assign gate_label = pvg_record.update_decision_label | default: 'INSUFFICIENT DATA' -%}")),
        ("X15 QA reports an unsupported entry as an error", lambda: check_qa(tmp / f"x15-{next(qa_runs)}"),
         swap(qa, "add", lambda bucket, path, code, msg: real_add(
             bucket, path, "verdict_reasons_invalid" if code == "verdict_reason_unsupported" else code, msg))),
        ("X16 'Pause updates' comes back to a Windows line", check_wording_writer,
         swap(pd, "public_body", lambda d, r, n: real_body(d, r, n) + (
             " Pause updates if this machine is doing production work." if (r or {}).get("product_id") == WIN else ""))),
        ("X17 the gate words the security line differently from Python", check_render_matrix,
         tpl("recommends keeping supported systems updated.' -%}", "recommends installing it now.' -%}")),
        # Review 1's two probes, as mutants: each restores one way the render gate failed open.
        ("X18 (probe A1) the gate re-derives support from the cited URLs, round 0's rule, instead of reading "
         "the projection", check_projection_probes, tpl(PROJECTION_READ, URL_RULE_GATE)),
        ("X19 (probe A2) the projection is built with a weaker support rule than decide's",
         check_projection_probes, swap(sys.modules[__name__], "PROJECT_OVERRIDE", weak_project)),
        ("X20 QA ignores the projection a deploy built and checks only its own", lambda: check_qa(tmp / f"x20-{next(qa_runs)}"),
         swap(vp, "load", lambda path: None)),
        ("X21 QA's unsupported warning claims a fall-back to INSUFFICIENT DATA it does not make (round 0's text)",
         lambda: check_qa(tmp / f"x21-{next(qa_runs)}"),
         swap(qa, "add", lambda bucket, path, code, msg: real_add(
             bucket, path, code, re.sub(r"renders .*?;", "renders 'INSUFFICIENT DATA';", msg)
             if code == "verdict_reason_unsupported" else msg))),
        ("X22 a table row prints the verdict without its scope", check_surfaces,
         inc("patch-table-row.html",
             "{% if row_verdict_scope != '' %} <span class=\"patch-verdict-scope\">{{ row_verdict_scope }}</span>{% endif %}",
             "")),
        ("X23 the feed card prints the stored summary as is, so a lagging one leads with a bare verdict",
         check_surfaces, inc("patch-feed-summary.html", "{%- if feed_summary_line != '' and gate_body != '' -%}",
                             "{%- if false -%}")),
        ("X24 the writer's summary goes back to a bare verdict beside a count", check_surfaces,
         swap(pd, "summary_line", lambda d, r, n, fallback="", identity="": real_summary(
             d, r, n, fallback, identity).replace(pd.verdict_phrase(d) + ":", d.verdict + ":", 1))),
    ]
    for label, body, (mutate, restore) in cases:
        run_mutant(label, body, mutants, mutate=mutate, restore=restore)
    for label, failures, crash in mutants:
        detail = (f"mutant crashed instead of being caught: {crash}" if crash
                  else "no NAMED check failed that was not already failing")
        check(f"{label} -> caught", bool(failures), detail)
        if failures:
            print(f"        caught by: {', '.join(sorted(failures)[:4])}")


def check_wording_writer() -> None:
    """G3-W3: the writer's Windows output carries no pause advice (exercised through the authority)."""
    rec = win_record(update_report_count=3)
    body = pd.public_body(decide(rec), rec, 3)
    check("G3-W3 the Windows verdict line advises neither pausing nor disabling updates",
          "pause" not in body.lower() and "disable" not in body.lower(), body)


# ------------------------------------------------------------------------ the suite

def run() -> int:
    print("=" * 78)
    print("GROWTH-3 VERDICT POLICY")
    print("=" * 78)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "q").mkdir()
        (tmp / "p").mkdir()
        print("\n[D] the decision procedure")
        check_decisions()
        check_corpus_guard()
        print("\n[F] the reason file's audits")
        check_reason_audits()
        print("\n[L] the single lifecycle exception")
        check_lifecycle()
        print("\n[W] wording")
        check_wording()
        check_wording_writer()
        print("\n[Q] QA: severities, and what renders against what the authority decides")
        check_qa(tmp / "q")
        print("\n[R] the Liquid gate renders what Python decides")
        check_render_matrix()
        check_render_corpus()
        print("\n[P] one authority: the projection, review 1's probes, the builder")
        check_projection()
        check_projection_probes()
        check_projection_builder(tmp / "p")
        print("\n[S] the scope prints with the verdict on every surface")
        check_surfaces()
        print("\n[X] mutants, each caught by a named check")
        check_mutations(tmp)
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
