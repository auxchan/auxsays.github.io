#!/usr/bin/env python3
"""GROWTH-3: every verdict comes from the owner's policy, decided once, rendered everywhere alike.

THE POLICY (owner decisions 1-3, 2026-11-06), implemented in lib/patch_decision.decide and mirrored
for Liquid in _includes/patch-verdict-gate.html:
  R1 AVOID            an official withdrawal for new installations (_data/patch_lifecycle.yml: ONE
                      verified exception, KB5079391 -> KB5086672)
  R2 SECURITY UPDATE  Microsoft's stored monthly-security classification (release type "YYYY-MM B");
                      reports never override it, a supported reason only adds a warning panel
  R3 WAIT             a reviewed `regression` entry in _data/verdict_reasons.yml, still supported
  R4 TEST FIRST       a reviewed corroboration entry, still supported
  R5/R6 INSUFFICIENT DATA
Report count, sentiment, theme, severity, maturity and the clock decide nothing; SAFE ENOUGH stays
unreachable.

SECTIONS. [D] the decision procedure and its invariants (G3-D1..D12). [F] the reason file's audits
(G3-F1..F7, G3-OC). [L] the lifecycle exception (G3-L1..L3). [W] public wording (G3-W1..W2).
[Q] QA severities (G3-Q1..Q3). [R] the Liquid gate renders exactly what Python decides, on a
synthetic matrix and over the whole corpus (G3-R1..R3). [X] mutants: each restores ONE thing the
policy forbids, and must be caught by a named check that was passing before it.

Needs ruby + the liquid gem for [R] and the template mutants. Offline; writes only in a temp dir.
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
    gen = _AUX / "updates" / "generated"
    recs = []
    for path in sorted(gen.glob("*.md")):
        m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", path.read_text(encoding="utf-8"), re.S)
        data = yaml.safe_load(m.group(1)) if m else {}
        if isinstance(data, dict) and data.get("update_entry") is True:
            recs.append(data)
    reason_ids = {vr.reason_identity(e) for e in REASONS["entries"]}
    problems = []
    for r in recs:
        d = decide(r, gate_valid(r), LIFECYCLE["entries"])
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


def gate_valid(rec: dict) -> list[dict]:
    """The reason entries the template's render-time rule supports for this record."""
    urls = {str(s.get("source_url") or "") for s in rec.get("accepted_report_sources") or []}
    return [e for e in REASONS["entries"] if vr.reason_identity(e) == vr.record_identity(rec)
            and e.get("evidence") and all(str(ev.get("source_url")) in urls for ev in e["evidence"])]


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

def check_qa(tmp: Path) -> None:
    import qa_patch_records as qa
    saved = (qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH)
    gen = tmp / "gen"
    gen.mkdir(parents=True, exist_ok=True)
    rec_path = gen / "r.md"
    rec = record(update_entry=True, update_decision_label="TEST FIRST", accepted_report_sources=[])
    rec_path.write_text("---\n" + yaml.safe_dump(rec) + "---\nbody\n", encoding="utf-8")
    ev = tmp / "ev.yml"
    ev.write_text(yaml.safe_dump({"schema_version": 1, "evidence": [
        dict(row(1), product_id=OBS, update_version="99.0.0", counted=True, patch_version_matched=True)]}),
        encoding="utf-8")
    good = tmp / "reasons.yml"
    good.write_text(yaml.safe_dump({"schema_version": 1, "entries": [entry("t")]}), encoding="utf-8")
    bad = tmp / "bad.yml"
    bad.write_text(yaml.safe_dump({"schema_version": 1, "entries": [entry("b", scope="nope")]}), encoding="utf-8")
    life = tmp / "life.yml"
    life.write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    try:
        qa.EVIDENCE_PATH, qa.LIFECYCLE_PATH = ev, life
        qa.REASONS_PATH = good
        errors, warnings = qa.scan_verdict_policy([rec_path])
        codes_w = {w["code"] for w in warnings}
        check("G3-Q1 an entry whose rows stopped counting is a WARNING, never an error",
              not errors and "verdict_reason_unsupported" in codes_w, f"{errors} {codes_w}")
        promoted, kept = qa.promote_for_publication(errors, warnings)
        check("G3-Q2 ...and publish-strict does not promote it (the page has already fallen back)",
              not promoted and "verdict_reason_unsupported" in {w["code"] for w in kept}
              and "verdict_policy_drift" in codes_w)
        qa.REASONS_PATH = bad
        errors, _w = qa.scan_verdict_policy([rec_path])
        check("G3-Q3 a malformed reason file is an ERROR (it only changes by reviewed pull request)",
              "verdict_reasons_invalid" in {e["code"] for e in errors}, str(errors)[:200])
    finally:
        qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH = saved


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


SYN_REASONS = [entry("w", "WAIT", "regression"), entry("t", rows=(3, 4)),
               entry("i", "TEST FIRST", "corroborated_install_problem", pid=WIN, version="25H2",
                     build="26200.1000", rows=(1, 2), scope="when installing it"),
               entry("r", "WAIT", "regression", pid=WIN, version="25H2", build="26200.3000", rows=(1, 2))]


def synthetic_cases() -> dict:
    src4 = [{"source_url": u} for u in URLS[:4]]
    return {
        "wait+also": (record(accepted_report_sources=src4, update_report_count=4), 4),
        "tf-only": (record(accepted_report_sources=[{"source_url": u} for u in URLS[2:4]]), 2),
        "withdrawn": (record(accepted_report_sources=[{"source_url": URLS[0]}], update_report_count=1), 1),
        "nothing-2": (record(accepted_report_sources=[]), 2),
        "nothing-1": (record(accepted_report_sources=[], update_report_count=1), 1),
        "zero": (record(accepted_report_sources=[], update_report_count=0), 0),
        "sec-0": (win_record(update_report_count=0), 0),
        "sec-1": (win_record(update_report_count=1), 1),
        "sec-9": (win_record(update_report_count=9), 9),
        "sec-install": (win_record(accepted_report_sources=[{"source_url": u} for u in URLS[:2]]), 2),
        "sec-regression": (win_record(build="26200.3000", accepted_report_sources=[{"source_url": u} for u in URLS[:2]]), 2),
        "avoid-preview": (win_record(update_type="2026-03 D", kb="KB5000002", build="26200.2000"), 1),
        "avoid-security": (win_record(kb="KB5000002", build="26100.2000", update_report_count=0), 0),
        "oob": (win_record(update_type="2026-03 OOB"), 2),
        "preview-tf": (win_record(update_type="2026-03 D", accepted_report_sources=[{"source_url": u} for u in URLS[:2]]), 2),
    }


TEMPLATE_OVERRIDE: str | None = None   # set only by the template mutants in [X]


def check_render_matrix(template: str | None = None) -> None:
    template = template if template is not None else TEMPLATE_OVERRIDE
    cases = synthetic_cases()
    site = {"verdict_reasons": {"schema_version": 1, "entries": SYN_REASONS},
            "patch_lifecycle": {"schema_version": 1, "entries": LIFE}}
    out = render_gate({k: {"rec": r, "cnt": n} for k, (r, n) in cases.items()}, site, template)
    check("G3-R0 the liquid gem is available, so the template checks run for real",
          out is not None and "__error__" not in out, str(out)[:200] if out else "ruby missing")
    if not out or "__error__" in out:
        return
    diffs = []
    for name, (rec, n) in cases.items():
        urls = {s["source_url"] for s in rec.get("accepted_report_sources") or []}
        supported = [e for e in SYN_REASONS if vr.reason_identity(e) == vr.record_identity(rec)
                     and all(ev["source_url"] in urls for ev in e["evidence"])]
        want = python_view(rec, supported, LIFE, n)
        got = parse_probe(out.get(name, ""))
        if got != want:
            diffs.append((name, got, want))
    check(f"G3-R1 the gate renders exactly what decide/public_body/panel_text say ({len(cases)} cases: "
          "every rule, both panels, zero reports, a withdrawn citation)", not diffs, str(diffs[:2])[:600])
    verdicts = {k: (parse_probe(v) or ("",))[0] for k, v in out.items()}
    check("G3-R2 the matrix is not vacuous: it reaches all five published verdicts and fails closed",
          {verdicts["avoid-preview"], verdicts["sec-9"], verdicts["wait+also"], verdicts["tf-only"],
           verdicts["withdrawn"]} == {"AVOID", "SECURITY UPDATE", "WAIT", "TEST FIRST", "INSUFFICIENT DATA"}
          and verdicts["avoid-security"] == "AVOID" and verdicts["sec-0"] == "SECURITY UPDATE", str(verdicts))


def check_render_corpus() -> None:
    gen = _AUX / "updates" / "generated"
    sys.path.insert(0, str(_AUX / "scripts"))
    from lib import report_counts  # noqa: PLC0415 - imports the collector base; offline
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
    valid, _unsupported = vr.valid_reasons_by_identity(REASONS["entries"], groups, by_ident)
    cases, want = {}, {}
    for i, r in enumerate(recs):
        n = int(r.get("update_report_count") or 0)
        slim = {k: r.get(k) for k in ("product_id", "update_version", "target_build", "target_kb", "update_type",
                                      "accepted_report_sources")}
        slim["accepted_report_sources"] = [{"source_url": s.get("source_url")}
                                           for s in r.get("accepted_report_sources") or []]
        cases[str(i)] = {"rec": slim, "cnt": n}
        want[str(i)] = python_view(r, valid.get(vr.record_identity(r), []), LIFECYCLE["entries"], n)
    out = render_gate(cases, {"verdict_reasons": REASONS, "patch_lifecycle": LIFECYCLE})
    if not out or "__error__" in out:
        check("G3-R3 the gate renders the authority's verdict on every corpus record", False, str(out)[:200])
        return
    diffs = [(recs[int(k)].get("permalink"), parse_probe(out.get(k, "")), w) for k, w in want.items()
             if parse_probe(out.get(k, "")) != w]
    check(f"G3-R3 over all {len(recs)} records the gate renders the authority's verdict, scope, line and panel "
          "(the authority validating against the counted evidence store)", not diffs and len(recs) > 1000,
          str(diffs[:2])[:600])


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


def template_mutant(old: str, new: str):
    text = GATE_PATH.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    mutated = text.replace(old, new)
    return lambda: check_render_matrix(template=mutated)


def check_mutations(tmp: Path) -> None:
    D = pd.Decision
    import qa_patch_records as qa
    mutants: list = []
    real_support = vr.support_problems
    real_schema = vr.schema_errors
    real_body = pd.public_body
    real_add = qa.add

    def tpl(old: str, new: str):
        """(mutate, restore) for the SHIPPED gate include, changed in memory only."""
        text = GATE_PATH.read_text(encoding="utf-8")
        assert text.count(old) == 1, old
        return swap(sys.modules[__name__], "TEMPLATE_OVERRIDE", text.replace(old, new))

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
        ("X14 the gate stops checking that the cited reports still count", check_render_matrix,
         tpl("{%- unless pvg_urls contains pvg_key -%}{%- assign pvg_ok = false -%}{%- endunless -%}\n"
             "      {%- assign pvg_n = pvg_n | plus: 1 -%}", "{%- assign pvg_n = pvg_n | plus: 1 -%}")),
        ("X15 QA reports an unsupported entry as an error", lambda: check_qa(tmp / f"x15-{next(qa_runs)}"),
         swap(qa, "add", lambda bucket, path, code, msg: real_add(
             bucket, path, "verdict_reasons_invalid" if code == "verdict_reason_unsupported" else code, msg))),
        ("X16 'Pause updates' comes back to a Windows line", check_wording_writer,
         swap(pd, "public_body", lambda d, r, n: real_body(d, r, n) + (
             " Pause updates if this machine is doing production work." if (r or {}).get("product_id") == WIN else ""))),
        ("X17 the gate words the security line differently from Python", check_render_matrix,
         tpl("recommends keeping supported systems updated.' -%}", "recommends installing it now.' -%}")),
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
        print("\n[Q] QA severities")
        check_qa(tmp / "q")
        print("\n[R] the Liquid gate renders what Python decides")
        check_render_matrix()
        check_render_corpus()
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
