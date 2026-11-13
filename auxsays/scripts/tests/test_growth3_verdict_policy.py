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

ONE AUTHORITY (fix round 1, review 1 D2; review 2 LOW-1). The Liquid gate
(_includes/patch-verdict-gate.html) decides no verdict: lib/verdict_projection writes decide's answer
per page at deploy (build_verdict_projection.py, before QA and Jekyll) -- AVOID and SECURITY UPDATE
included -- and the gate prints it. It re-derives no official fact: its own reading of the lifecycle
file and of the release type ("YYYY-MM B" via slice + plus: 0) parted from Python's where QA could
not see it (review 2: probe N1, "2026-3x B").

SECTIONS. [D] the decision procedure and its invariants (G3-D1..D12). [F] the reason file's audits
(G3-F0..F7, G3-OC). [L] the lifecycle exception and its strict, ASCII typing (G3-L1..L6, G3-W0).
[W] public wording (G3-W1..W4). [Q] QA: severities, the rendered/authority comparison, the malformed
lifecycle and release type, Unicode-padded identities and unmatched lifecycle builds (G3-Q1..Q11), a
feed card that would hide its page's official verdict, each half of its line on its own (G3-Q12, Q13), and
an invisible or control character inside an identity (G3-Q14, probe P6).
[R] the gate renders exactly what Python decides: a synthetic matrix with one case per support rule
and per scope-acceptance clause, no-projection fail-closed, the whole corpus, review 2's gate2 and
refused-lifecycle cases, and padded identities (G3-R0..R8). [P] the projection IS the authority, official verdicts
included, review 1's probes A1 and A2 on the rendered page, the builder and its position in the
deploy (G3-P0..P9). [S] the scope prints with the verdict on every surface, and the feed card's
wording (G3-S1..S8, review 1 D1, review 2 LOW-4); every feed card states its page's official verdict at
any report count, and its status pill then names no verdict (G3-S9..S13, AUX-097). [X] mutants: each restores ONE thing the policy
forbids, and must be caught by a named check that was passing before it.

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
LIFECYCLE_TEXT = (_AUX / "_data" / "patch_lifecycle.yml").read_text(encoding="utf-8")
LIFECYCLE = yaml.safe_load(LIFECYCLE_TEXT)
# Review 2's probe N1, exactly as it was written: the builds as YAML numbers.
N1_LIFECYCLE_TEXT = LIFECYCLE_TEXT.replace('builds: ["26100.8116", "26200.8116"]', "builds: [26100.8116, 26200.8116]")
# Review 2's gate2 cases: Liquid's `plus: 0` read each as a month number; Python's pattern does not.
# The last two are the PR-A2 review's probe P3 (LOW-2): full-width and Arabic-Indic digits, which
# Python's `\d` and int() accepted until the release-type patterns became re.ASCII.
# Then G35-04 review 2's LOW-6 values (with re.ASCII on the shape detector, nothing reported them) and
# two that each need one half of its fix: fully full-width (only NFKC shows the shape) and Arabic-Indic
# digits with an Arabic letter (only a Unicode `\d` shows it).
GATE2_MALFORMED = ("2026-3x B", "2026-+3 B", "2026-1  B", "2026-13 B",
                   "２０２６-０８ B", "٢٠٢٦-٠٥ B",
                   "２０２６-０８ Ｂ", "２０２６-０８　B", "٢٠٢٦-٠٥ Ｂ",
                   "２０２６－０８ Ｂ", "٢٠٢٦-٠٥ ب")
REVIEW2_LOW6 = ("２０２６-０８ Ｂ", "２０２６-０８　B", "٢٠٢٦-٠٥ Ｂ")
# PR-A2 review, LOW-1 (probe P5): Unicode spaces Python's str.strip removes and Liquid's strip keeps.
UNICODE_PADS = {"NBSP": " ", "THIN SPACE": " ", "IDEOGRAPHIC SPACE": "　", "NEL": "\u0085"}
# G35-04 review 2, LOW-7 (probe P6) and its relatives: an invisible or control character INSIDE an
# identity, or at its end where it is not whitespace: (update_version, target_build) per character.
# Written as escapes so the characters stay visible in this file.
INVISIBLE_IDENTITY_PROBES = {
    "P6 zero-width space at the end": ("15.010.20056​", "26200.1500​"),
    "zero-width no-break space (BOM)": ("15.010.﻿20056", "26200.﻿1501"),
    "soft hyphen": ("15.010­.20056", "26200.15­02"),
    "word joiner": ("15.010.2005⁠6", "26200.15⁠03"),
    "inner no-break space": ("15.010 20056", "26200. 1504"),
    "inner ideographic space": ("15.010　20056", "26200.　1505"),
    "bell control character at the end": ("15.010.20056\u0007", "26200.1506\u0007"),
    "line separator": ("15.010 20056", "26200. 1507"),
    "paragraph separator": ("15.010 20056", "26200. 1508"),
}
# Printable Unicode that real changelog-title versions carry (VERIFY_3: 30 of them are non-ASCII).
PRINTABLE_IDENTITY_VALUES = ("Copilot cloud agent starts 20% faster with Actions custom images",
                             "Figma’s update", "Dev Mode — annotations", "Pricing in € for teams",
                             "Acrobat™ export", "agentâ€™s mojibake", "21 Public Beta 1")
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

    # Review 2, LOW-1. Probe N1 through the deploy's own loader: the file is refused, not coerced.
    assert N1_LIFECYCLE_TEXT != LIFECYCLE_TEXT, "the N1 anchor is no longer in patch_lifecycle.yml"
    n1_entries = yaml.safe_load(N1_LIFECYCLE_TEXT)["entries"]
    n1_errors = vr.lifecycle_errors(n1_entries)
    _r, n1_loaded, n1_problems = fact_files(N1_LIFECYCLE_TEXT)
    kb_pages = [win_record(update_type="2026-03 D", kb="KB5079391", build=b) for b in ("26100.8116", "26200.8116")]
    typed = [vr.lifecycle_errors([dict(entries[0], **{f: v})])
             for f, v in (("product_id", 11), ("kb", 5079391), ("relationship", True))]
    check("G3-L4 probe N1: lifecycle builds written as YAML numbers are refused, not coerced -- the file "
          "supports nothing, so neither KB5079391 page is AVOID -- and a non-string product_id, kb or "
          "relationship is refused too",
          any("builds[0]" in e and "not a string" in e for e in n1_errors)
          and any("builds[1]" in e for e in n1_errors) and all(typed)
          and n1_loaded == [] and any("patch_lifecycle" in m for m in n1_problems)
          and all(decide(r, (), n1_loaded).verdict != "AVOID" for r in kb_pages)
          and all(decide(r, (), LIFECYCLE["entries"]).verdict == "AVOID" for r in kb_pages),
          f"{n1_errors} {typed} {n1_problems}")
    padded = {f: vr.lifecycle_errors([dict(entries[0], **{f: v})])
              for f, v in (("product_id", " microsoft-windows-11"), ("kb", "KB5079391 "),
                           ("relationship", "withdrawn_for_new_installs "),
                           ("builds", ["26100.8116", " 26200.8116"]))}
    check("G3-L5 a padded product_id, kb, relationship or build is refused (Python must never trim a "
          "value into a match), and the shipped file passes",
          all(any("whitespace" in e for e in errs) for errs in padded.values())
          and not vr.lifecycle_errors(entries), str({k: v[:1] for k, v in padded.items()}))

    # PR-A2 review, LOW-3 (probe P4) and LOW-2: ASCII-strict builds, KB numbers and dates. Each value
    # below is a plain, unpadded string, so the padding check alone accepted every one of them.
    strict = {
        "P4 zero-width space after a build": dict(entries[0], builds=["26100.8116​", "26200.8116"]),
        "full-width digits in a build": dict(entries[0], builds=["２６１００.8116", "26200.8116"]),
        "a build without the dot": dict(entries[0], builds=["26100-8116", "26200.8116"]),
        "a zero-width space in a replacement build": dict(entries[0], replacement_builds=["26100.8117​"]),
        "a full-width digit in the KB": dict(entries[0], kb="KB５079391"),
        "full-width digits in a date": dict(entries[0], released="２０２６-03-26"),
    }
    strict_errors = {k: vr.lifecycle_errors([v]) for k, v in strict.items()}
    p4_text = LIFECYCLE_TEXT.replace('builds: ["26100.8116", "26200.8116"]', 'builds: ["26100.8116\\u200b", "26200.8116"]')
    assert p4_text != LIFECYCLE_TEXT, "the P4 anchor is no longer in patch_lifecycle.yml"
    _r, p4_loaded, p4_problems = fact_files(p4_text)
    check("G3-L6 PR-A2 review LOW-3 / LOW-2: a lifecycle build must be an ASCII 12345.6789 (P4's zero-width "
          "space, full-width digits, a missing dot, a replacement build), the KB and dates ASCII digits; the P4 "
          "file is refused through the deploy's loader, so neither KB5079391 page is AVOID; the shipped file passes",
          all(strict_errors.values()) and p4_loaded == [] and any("patch_lifecycle" in m for m in p4_problems)
          and all(decide(r, (), p4_loaded).verdict != "AVOID" for r in kb_pages) and not vr.lifecycle_errors(entries),
          str({k: v[:1] for k, v in strict_errors.items() if not v}))


def fact_files(lifecycle_text: str, reasons: list | None = None) -> tuple[list, list, list]:
    """lib/verdict_projection.load_fact_files over a temp tree holding these two files: exactly what a
    deploy hands decide (a refused file contributes nothing)."""
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "_data"
        data.mkdir()
        (data / "patch_lifecycle.yml").write_text(lifecycle_text, encoding="utf-8")
        (data / "verdict_reasons.yml").write_text(
            yaml.safe_dump({"schema_version": 1, "entries": list(reasons or [])}), encoding="utf-8")
        return vp.load_fact_files(Path(td))


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
    check_menu_bar_reason()


MENU_BAR_ENTRY = "obs-studio:32.2.2:macos-27-menu-bar-icon-crash"


def check_menu_bar_reason() -> None:
    """G3-W4 (review 2, LOW-3): working on macOS 26.3.1 shows the crash depends on the OS; it does not
    show that earlier OBS versions also crash on macOS 27, so the line may not say it is not new."""
    reason = next((str(e.get("reason") or "") for e in REASONS["entries"] if e.get("id") == MENU_BAR_ENTRY), "")
    overclaims = [p for p in ("not new in this OBS version", "comes with macOS 27", "is not new")
                  if p in reason]
    check("G3-W4 the OBS 32.2.2 menu-bar reason is non-causal: triggered by macOS 27, and no report shows "
          "this OBS update caused it -- never that it is not new in this OBS version",
          "so it is triggered by macOS 27; no report shows it was caused by this OBS update." in reason
          and not overclaims, reason or "entry missing")


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
    check_qa_official(qa, tmp / "official")


def _qa_win_tree(tmp: Path, update_type: str, *, life_text: str | None = None,
                 kb: str = "KB5000001", build: str = "26200.1000"):
    """A one-page Windows QA fixture (no reports) with its own lifecycle file."""
    tree = _qa_tree(tmp, [], [], rec_over={"product_id": WIN, "update_version": "25H2", "target_kb": kb,
                                           "target_build": build, "update_type": update_type,
                                           "update_report_count": 0})
    if life_text is not None:
        tree[3].write_text(life_text, encoding="utf-8")
    return tree


def check_qa_official(qa, tmp: Path) -> None:
    """Review 2, LOW-1: the malformed inputs fail closed AND are QA errors; a partial projection too."""
    codes = lambda es: {e["code"] for e in es}  # noqa: E731
    n1 = _qa_win_tree(tmp / "n1", "2026-03 D", life_text=N1_LIFECYCLE_TEXT, kb="KB5079391", build="26200.8116")
    e_n1, _w = _qa_scan(qa, n1)
    padded = _qa_win_tree(tmp / "pad", "2026-03 D", kb="KB5079391", build="26200.8116",
                          life_text=LIFECYCLE_TEXT.replace("relationship: withdrawn_for_new_installs",
                                                           "relationship: 'withdrawn_for_new_installs '"))
    e_pad, _w = _qa_scan(qa, padded)
    shipped = _qa_win_tree(tmp / "ok", "2026-03 D", life_text=LIFECYCLE_TEXT, kb="KB5079391", build="26200.8116")
    e_ok, _w = _qa_scan(qa, shipped)
    check("G3-Q7 probe N1 (numeric builds) and a padded relationship are QA ERRORS (patch_lifecycle_invalid), "
          "and QA's own view of the page fails closed with the file (no AVOID it would disagree with); the "
          "shipped file is clean",
          "patch_lifecycle_invalid" in codes(e_n1) and "patch_lifecycle_invalid" in codes(e_pad)
          and "verdict_render_disagrees" not in codes(e_n1) | codes(e_pad)
          and not e_ok, f"n1={codes(e_n1)} pad={codes(e_pad)} ok={codes(e_ok)}")
    flagged, published, clean = {}, {}, {}
    for i, value in enumerate(GATE2_MALFORMED + ("2026-03 B", "2026-03 D", "2026-03 OOB", "official-source")):
        tree = _qa_win_tree(tmp / f"t{i}", value, build=f"26200.{1100 + i}")
        errors, warnings = _qa_scan(qa, tree)
        promoted, _kept = qa.promote_for_publication(errors, warnings)
        bucket = flagged if value in GATE2_MALFORMED else clean
        bucket[value] = ("windows_update_type_malformed" in codes(warnings), codes(errors),
                         "windows_update_type_malformed" in codes(promoted))
        published[value] = decide(win_record(update_type=value)).verdict
    # An AVOID page's preview context line reads the strict ASCII preview pattern too.
    avoid_ascii = win_record(update_type="2026-03 D", kb="KB5000002", build="26200.2000")
    avoid_wide = win_record(update_type="２０２６-０３ D", kb="KB5000002", build="26200.2000")
    body_ascii = pd.public_body(decide(avoid_ascii, (), LIFE), avoid_ascii, 1)
    body_wide = pd.public_body(decide(avoid_wide, (), LIFE), avoid_wide, 1)
    check("G3-Q8 review 2's gate2 release types ('2026-3x B', '2026-+3 B', '2026-1  B', and '2026-13 B'), "
          "the PR-A2 review's P3 (full-width / Arabic-Indic digits + ' B') and G35-04 review 2's LOW-6 values "
          "(a full-width 'Ｂ', an ideographic space, Arabic-Indic digits + 'Ｂ'; also fully full-width, and "
          "Arabic-Indic digits + an Arabic letter) are each a QA publication ERROR (windows_update_type_malformed: "
          "a writeback warning, promoted by --publish-strict) and decide fails closed on them; B, D, OOB and the "
          "writer default are clean; an AVOID page's preview line reads only an ASCII 'YYYY-MM D'",
          all(f == (True, set(), True) for f in flagged.values()) and set(REVIEW2_LOW6) <= set(flagged)
          and all(c == (False, set(), False) for c in clean.values())
          and all(published[v] == "INSUFFICIENT DATA" for v in GATE2_MALFORMED)
          and published["2026-03 B"] == "SECURITY UPDATE"
          and "non-security preview update" in body_ascii and "preview update" not in body_wide,
          f"{flagged} {clean} {published} ascii={body_ascii!r} wide={body_wide!r}")
    sec = _qa_win_tree(tmp / "partial", "2026-03 B", build="26200.1200")
    paths, _ev, _rs, _life, proj = sec
    data = yaml.safe_load(paths[0].read_text(encoding="utf-8").split("---")[1])
    full = vp.project([data], {}, [], [])[0]
    proj.write_text(vp.render({"schema_version": 1, "pages": {}}), encoding="utf-8")
    e_partial, _w = _qa_scan(qa, sec)
    proj.write_text(vp.render(full), encoding="utf-8")
    e_full, _w = _qa_scan(qa, sec)
    msg = next((e["message"] for e in e_partial if e["code"] == "verdict_render_disagrees"), "")
    check("G3-Q9 a deploy projection without a page's OFFICIAL row (round 1's shape: reasoned rows only) is "
          "an ERROR -- the page would render INSUFFICIENT DATA where decide gives SECURITY UPDATE -- and the "
          "full projection is clean",
          "renders 'INSUFFICIENT DATA'" in msg and "'SECURITY UPDATE'" in msg
          and full["pages"] and "verdict_render_disagrees" not in codes(e_full), f"{msg[:200]} {codes(e_full)}")

    # G3-Q10 (PR-A2 review, LOW-1, probe P5): an identity Liquid and Python strip differently.
    pad_found, pad_clean = {}, {}
    for i, (name, pad) in enumerate(UNICODE_PADS.items()):
        for field, tree in (
                ("target_build", _qa_win_tree(tmp / f"pad-b{i}", "2026-03 B", build=f"26200.{1400 + i}{pad}")),
                ("update_version", _qa_tree(tmp / f"pad-v{i}", [], [], rec_over={"update_version": f"99.{i}.0{pad}"}))):
            errors, warnings = _qa_scan(qa, tree)
            promoted, _kept = qa.promote_for_publication(errors, warnings)
            pad_found[f"{name} {field}"] = ("record_identity_unicode_padding" in codes(warnings), codes(errors),
                                            "record_identity_unicode_padding" in codes(promoted))
    for name, value in (("ascii-padded", " 26200.1500 "), ("curly quote inside", "Figma’s update")):
        tree = _qa_win_tree(tmp / f"pad-ok-{name}", "2026-03 B", build=value)
        _e, warnings = _qa_scan(qa, tree)
        pad_clean[name] = "record_identity_unicode_padding" in codes(warnings)
    corpus_padded = [r.get("permalink") for r in corpus()["recs"] if vr.identity_padding_problems(r)]
    check("G3-Q10 an identity field padded with U+00A0, U+2009, U+3000 or U+0085 (Liquid keeps it, Python's "
          "strip drops it) is a QA publication ERROR on target_build and update_version alike; ASCII padding "
          "and an inner non-ASCII character are not, and the shipped corpus has none",
          all(v == (True, set(), True) for v in pad_found.values()) and not any(pad_clean.values())
          and not corpus_padded, f"{pad_found} {pad_clean} {corpus_padded[:3]}")

    # G3-Q11 (PR-A2 review, LOW-3): every lifecycle BUILD must be carried by a record; one is enough to fail.
    one = _qa_win_tree(tmp / "life-one", "2026-03 D", life_text=LIFECYCLE_TEXT, kb="KB5079391", build="26200.8116")
    both = _qa_tree(tmp / "life-both", [], [], conf_records=[win_record(update_type="2026-03 D", kb="KB5079391",
                                                                         build="26100.8116", update_version="24H2")],
                    rec_over={"product_id": WIN, "update_version": "25H2", "target_kb": "KB5079391",
                              "target_build": "26200.8116", "update_type": "2026-03 D", "update_report_count": 0})
    both[3].write_text(LIFECYCLE_TEXT, encoding="utf-8")

    def scan_both(tree):
        """scan_verdict_policy + scan_lifecycle_builds over one fixture, as qa.main runs them."""
        e1, w1 = _qa_scan(qa, tree)
        saved = qa.LIFECYCLE_PATH
        try:
            qa.LIFECYCLE_PATH = tree[3]
            e2, w2 = qa.scan_lifecycle_builds(tree[0])
        finally:
            qa.LIFECYCLE_PATH = saved
        return e1 + e2, w1 + w2
    e_one, w_one = scan_both(one)
    e_both, w_both = scan_both(both)
    promoted_one, _k = qa.promote_for_publication(e_one, w_one)
    msg = next((w["message"] for w in w_one if w["code"] == "patch_lifecycle_build_unmatched"), "")
    check("G3-Q11 a lifecycle build no record carries is a QA publication ERROR, per build (the entry still "
          "matches its other page, so the per-entry warning stays quiet); with both pages present it is clean",
          "patch_lifecycle_build_unmatched" in codes(promoted_one) and "26100.8116" in msg
          and "patch_lifecycle_unmatched" not in codes(w_one)
          and "patch_lifecycle_build_unmatched" not in codes(w_both) and not e_both,
          f"one={codes(w_one)} both={codes(w_both)} {codes(e_both)}")

    # G3-Q14 (G35-04 review 2, LOW-7, probe P6; AUTH_V2_38 WS2 first commit): an invisible or control
    # character INSIDE an identity field. Printable Unicode (the changelog-title versions) stays valid.
    inv_found, inv_clean = {}, {}
    for i, (name, (version, build)) in enumerate(INVISIBLE_IDENTITY_PROBES.items()):
        for field, tree in (
                ("update_version", _qa_tree(tmp / f"inv-v{i}", [], [], rec_over={"update_version": version})),
                ("target_build", _qa_win_tree(tmp / f"inv-b{i}", "2026-03 B", build=build))):
            errors, warnings = _qa_scan(qa, tree)
            promoted, _kept = qa.promote_for_publication(errors, warnings)
            inv_found[f"{name} {field}"] = ("record_identity_invisible_character" in codes(warnings), codes(errors),
                                            "record_identity_invisible_character" in codes(promoted))
    # product_id too (G38 WS2 review: a mutant that stopped checking product_id survived): the probe's own
    # invisible character inside the OBS product id.
    inv_pid = {}
    for i, (name, (version, _build)) in enumerate(INVISIBLE_IDENTITY_PROBES.items()):
        extra = "".join(ch for ch in version if ch not in "0123456789.")
        tree = _qa_tree(tmp / f"inv-p{i}", [], [], rec_over={"product_id": f"obs-{extra}studio"})
        errors, warnings = _qa_scan(qa, tree)
        promoted, _kept = qa.promote_for_publication(errors, warnings)
        inv_pid[name] = ("record_identity_invisible_character" in codes(warnings),
                         "record_identity_invisible_character" in codes(promoted))
    for i, value in enumerate(PRINTABLE_IDENTITY_VALUES):
        tree = _qa_tree(tmp / f"inv-ok{i}", [], [], rec_over={"update_version": value})
        _e, warnings = _qa_scan(qa, tree)
        inv_clean[value] = "record_identity_invisible_character" in codes(warnings)
    corpus_invisible = [r.get("permalink") for r in corpus()["recs"] if vr.identity_invisible_problems(r)]
    corpus_titles = sum(1 for r in corpus()["recs"]
                        if not re.fullmatch(r"[A-Za-z0-9._-]+", vr.liquid_strip(r.get("update_version"))))
    check("G3-Q14 an invisible or control character inside product_id / update_version / target_build (probe P6's "
          "U+200B, U+FEFF, a soft hyphen, a word joiner, an inner no-break or ideographic space, a control "
          "character, a line or paragraph separator) is a QA publication ERROR; printable Unicode titles (curly "
          "quotes, dashes, a euro or trade-mark sign, mojibake) are not, and the shipped corpus has none -- its "
          "hundreds of changelog-title versions all pass",
          all(v == (True, set(), True) for v in inv_found.values()) and not any(inv_clean.values())
          and len(inv_pid) == len(INVISIBLE_IDENTITY_PROBES) and all(v == (True, True) for v in inv_pid.values())
          and not corpus_invisible and corpus_titles > 600,
          f"{inv_found} pid={inv_pid} {inv_clean} {corpus_invisible[:3]} titles={corpus_titles}")


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


RECS_PROBE = "##{{ gate_recommendations | join: '~' }}##"


def gate_template(text: str | None = None, suffix: str = "") -> str:
    text = text if text is not None else GATE_PATH.read_text(encoding="utf-8")
    return text.replace("include.record", "rec").replace("include.count", "cnt") + PROBE + suffix


def render_gate(cases: dict, site_data: dict, template: str | None = None, suffix: str = "") -> dict | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script, payload, out = Path(td) / "g.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload.write_text(json.dumps({"template": gate_template(template, suffix), "site": {"data": site_data},
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
)


def check_render_matrix(template: str | None = None) -> None:
    template = template if template is not None else TEMPLATE_OVERRIDE
    cases = matrix_cases()
    records, counted, entries, projection = matrix_facts(cases)
    want = matrix_expectations(cases, records, counted, entries)
    site = {"verdict_projection": projection, "patch_lifecycle": {"schema_version": 1, "entries": LIFE},
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

    # A forged row: the gate prints the projection as it is (it re-derives nothing, official verdicts
    # included), so QA's model of the gate must say exactly what the gate prints -- that is how QA's
    # comparison with decide sees the forgery and stops the deploy (G3-Q4).
    # The PR-A2 review's MB1/MB2 gap: the gate's scope-acceptance clauses are pinned too -- a SCOPED
    # SECURITY UPDATE row and an AVOID / WAIT / TEST FIRST row with NO scope are malformed, so the gate
    # prints neither (and QA's model says the same, so QA reports the page's lost verdict).
    test_scope = "if you use the test setup"
    shapes = {  # name: (page, forged verdict, forged scope, what the gate must print)
        "forged WAIT": ("sec-forged-row", "WAIT", test_scope, ("WAIT", test_scope)),
        "MB1 scoped SECURITY UPDATE": ("sec-0", "SECURITY UPDATE", test_scope, ("INSUFFICIENT DATA", "")),
        "MB2 unscoped AVOID": ("avoid-preview", "AVOID", "", ("INSUFFICIENT DATA", "")),
        "MB2 unscoped WAIT": ("wait+also", "WAIT", "", ("INSUFFICIENT DATA", "")),
        "MB2 unscoped TEST FIRST": ("tf-only", "TEST FIRST", "", ("INSUFFICIENT DATA", "")),
    }
    forged = copy.deepcopy(projection)
    for page, verdict, scope, _printed in shapes.values():
        forged["pages"][vp.page_key(cases[page]["rec"])] = {
            "verdict": verdict, "scope": scope, "rule": "R3", "reasons": ["forged"],
            "body": "A forged line.", "panel_heading": "", "panel_text": "", "recommendations": []}
    f_out = render_gate({name: slim[page] for name, (page, *_rest) in shapes.items()},
                        dict(site, verdict_projection=forged), template) or {}
    f_got = {name: (parse_probe(f_out.get(name, "")) or ("",) * 5)[:2] for name in shapes}
    f_model = {name: vp.rendered_verdict(cases[page]["rec"], forged["pages"], LIFE)
               for name, (page, *_rest) in shapes.items()}
    f_want = {name: printed for name, (*_rest, printed) in shapes.items()}
    check("G3-R4j a forged WAIT row on a security page prints exactly what QA's model of the gate says, so QA "
          "sees it differ from decide's SECURITY UPDATE (the gate trusts only the projection; QA guards it); "
          "a scoped SECURITY UPDATE row (MB1) and an unscoped AVOID / WAIT / TEST FIRST row (MB2) print nothing, "
          "in the gate and in QA's model alike",
          f_got == f_model == f_want and want["sec-forged-row"][0] == "SECURITY UPDATE"
          and all(want[page][0] == verdict for page, verdict in
                  (("sec-0", "SECURITY UPDATE"), ("avoid-preview", "AVOID"), ("wait+also", "WAIT"), ("tf-only", "TEST FIRST"))),
          f"rendered {f_got!r}; model {f_model!r}")

    # No projection at all (a local render, a fresh checkout): fail closed -- no verdict of any kind.
    bare = render_gate(slim, {"patch_lifecycle": {"schema_version": 1, "entries": LIFE},
                              "verdict_reasons": {"schema_version": 1, "entries": entries}}, template)
    bare_got = {k: parse_probe((bare or {}).get(k, "")) or ("",) * 5 for k in cases}
    want_bare = {k: ("INSUFFICIENT DATA", "", pd.public_body(pd.Decision("INSUFFICIENT DATA", "R5"), c["rec"], c["n"]),
                     "", "") for k, c in cases.items()}
    model_bare = {k: vp.rendered_verdict(c["rec"], {}, LIFE) for k, c in cases.items()}
    check("G3-R5 with no projection the gate publishes no verdict at all -- no AVOID, SECURITY UPDATE, WAIT, "
          "TEST FIRST or panel, only the no-verdict line -- and QA's model of the gate says the same",
          bare is not None and "__error__" not in bare and bare_got == want_bare
          and set(model_bare.values()) == {("INSUFFICIENT DATA", "")},
          str([(k, bare_got[k][:2]) for k in cases if bare_got[k] != want_bare[k]][:4]))


def check_render_official(template: str | None = None) -> None:
    """G3-R6/R7 (review 2, LOW-1): the two places the gate used to derive an official verdict itself."""
    template = template if template is not None else TEMPLATE_OVERRIDE
    types = GATE2_MALFORMED + ("2026-03 B", "2026-03 D", "2026-03 OOB")
    recs = {t: win_record(update_type=t, build=f"26200.{1300 + i}", update_report_count=2)
            for i, t in enumerate(types)}
    projection = vp.project(list(recs.values()), {}, [], [])[0]
    out = render_gate({t: {"rec": slim(r), "cnt": 2} for t, r in recs.items()},
                      {"verdict_projection": projection, "patch_lifecycle": {"schema_version": 1, "entries": []}},
                      template) or {}
    got = {t: parse_probe(out.get(t, "")) for t in types}
    want = {t: python_view(r, [], [], 2) for t, r in recs.items()}
    check("G3-R6 review 2's gate2 release types render INSUFFICIENT DATA through the real gate, exactly as "
          "decide says (nothing parses '2026-3x B' as a month any more); a well-formed B renders SECURITY UPDATE",
          "__error__" not in out and got == want
          and all(got[t][0] == "INSUFFICIENT DATA" for t in GATE2_MALFORMED)
          and got["2026-03 B"][0] == "SECURITY UPDATE",
          str({t: (got[t] or ("",))[0] for t in types}))

    # A lifecycle file the deploy REFUSES (here: two entries, one with a foreign URL), which Liquid
    # still sees in site.data: the gate must not match it. And N1 itself.
    refused = copy.deepcopy(LIFECYCLE)
    refused["entries"] = [dict(refused["entries"][0], official_url="https://example.test/kb5079391"),
                          dict(refused["entries"][0], id="second")]
    cases, wants = {}, {}
    for name, text, life_data in (("refused", yaml.safe_dump(refused, sort_keys=False), refused),
                                  ("n1", N1_LIFECYCLE_TEXT, yaml.safe_load(N1_LIFECYCLE_TEXT))):
        _r, loaded, problems = fact_files(text)
        assert problems and loaded == [], (name, problems)
        pages = [win_record(update_type="2026-03 D", kb="KB5079391", build=b, update_report_count=1)
                 for b in ("26100.8116", "26200.8116")]
        proj = vp.project(pages, {}, [], loaded)[0]
        res = render_gate({str(i): {"rec": slim(r), "cnt": 1} for i, r in enumerate(pages)},
                          {"verdict_projection": proj, "patch_lifecycle": life_data}, template) or {}
        cases[name] = [parse_probe(res.get(str(i), "")) for i in range(len(pages))]
        wants[name] = [python_view(r, [], loaded, 1) for r in pages]
    check("G3-R7 a lifecycle file the deploy refuses (a schema-invalid file, or probe N1's numeric builds) "
          "renders no AVOID even though Jekyll still loads it: the gate matches no lifecycle entry itself",
          cases == wants and all(g and g[0] == "INSUFFICIENT DATA" for gs in cases.values() for g in gs),
          f"{ {k: [g and g[0] for g in v] for k, v in cases.items()} }")
    check_render_identity(template)


def check_render_identity(template: str | None = None) -> None:
    """G3-R8 (PR-A2 review, LOW-1, probe P5): the page key Python builds is the key the gate builds.

    Each Unicode pad is one Liquid's `| strip` keeps and Python's str.strip used to drop. A padded
    security page must still render its SECURITY UPDATE (the projection row is found under the padded
    key), and a padded reasoned page must render what decide gives it -- no transferred TEST FIRST, since
    the reviewed entry names the unpadded version -- while the unpadded control page renders TEST FIRST."""
    recs, counted, entries, kinds = {}, {}, [], {}
    for i, (name, pad) in enumerate(UNICODE_PADS.items()):
        sec = win_record(build=f"26200.{1600 + i}{pad}", update_report_count=0)
        recs[f"sec {name}"], kinds[f"sec {name}"] = sec, "SECURITY UPDATE"
        version = f"9.{40 + i}"
        tf = record(update_version=f"{version}{pad}", update_report_count=2)
        recs[f"tf {name}"], kinds[f"tf {name}"] = tf, "INSUFFICIENT DATA"
        counted[vr.record_identity(tf)] = [row(1), row(2)]
        entries.append(_e(f"pad-{i}", version))
    control = record(update_version="9.49", update_report_count=2)
    recs["tf control"], kinds["tf control"] = control, "TEST FIRST"
    counted[vr.record_identity(control)] = [row(1), row(2)]
    entries.append(_e("pad-control", "9.49"))
    projection = vp.project(list(recs.values()), counted, entries, [])[0]
    by_ident = {vr.record_identity(r): r for r in recs.values()}
    valid, _u = vr.valid_reasons_by_identity(entries, counted, by_ident)
    out = render_gate({k: {"rec": slim(r), "cnt": int(r["update_report_count"])} for k, r in recs.items()},
                      {"verdict_projection": projection}, template) or {}
    got = {k: parse_probe(out.get(k, "")) for k in recs}
    want = {k: python_view(r, valid.get(vr.record_identity(r), []), [], int(r["update_report_count"]))
            for k, r in recs.items()}
    check("G3-R8 an identity padded with U+00A0, U+2009, U+3000 or U+0085 renders exactly what decide gives it "
          "through the real gate: the padded security pages keep SECURITY UPDATE, a padded version takes no "
          "reviewed TEST FIRST meant for the unpadded one, and the unpadded control renders it",
          "__error__" not in out and got == want and {k: (g or ("",))[0] for k, g in got.items()} == kinds,
          str({k: ((got[k] or ("",))[0], want[k][0]) for k in recs if got[k] != want[k]})[:600])


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
        d = pd.decide(r, valid_reasons=mine, lifecycle=LIFECYCLE["entries"])
        if d.verdict != "INSUFFICIENT DATA":
            expect[vp.page_key(r)] = vp.row_for(d, r)
    check(f"G3-P1 the projection IS the authority: one row per page with a verdict ({len(rows)}: official "
          "ones included), each equal to decide/public_body/panel_text for that page",
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
          "accepted source, only the projection",
          "verdict_reasons" not in code and "accepted_report_sources" not in code and ".evidence" not in code
          and "site.data.verdict_projection.pages[pvg_key]" in code, "")
    derives = [n for n in ("patch_lifecycle", "update_type", "target_kb", "slice:", "withdrawn_for_new_installs",
                           "monthly security update") if n in code]
    check("G3-P8 the gate re-derives no official verdict: it reads no lifecycle file, release type or KB, and "
          "parses nothing (review 2, LOW-1: its own slice + plus: 0 reading parted from Python's)",
          not derives and code.count("plus: 0") == 1 and "include.count | default: 0 | plus: 0" in code,
          str(derives))


def check_projection_official() -> None:
    """G3-P9: a FRESH projection over the shipped corpus carries every official verdict."""
    c = corpus()
    rows = vp.project(c["recs"], c["groups"], REASONS["entries"], LIFECYCLE["entries"])[0]["pages"]
    security = [r for r in c["recs"] if pd.is_monthly_security_update(r)]
    withdrawn = [r for r in c["recs"] if pd.lifecycle_for(r, LIFECYCLE["entries"])]
    missing = [vp.page_key(r) for r in security if (rows.get(vp.page_key(r)) or {}).get("verdict") != "SECURITY UPDATE"]
    missing += [vp.page_key(r) for r in withdrawn
                if (rows.get(vp.page_key(r)) or {}).get("verdict") != "AVOID"
                or (rows.get(vp.page_key(r)) or {}).get("scope") != "for new installations"]
    check(f"G3-P9 the projection carries every official verdict: SECURITY UPDATE for each of the "
          f"{len(security)} monthly security updates and AVOID for both KB5079391 pages ({len(withdrawn)})",
          # Non-vacuity only: the corpus grows with every monthly ingest, so the count is a floor, never a pin
          # (it read == 43 and turned main red at 48).
          len(security) >= 1 and len(withdrawn) == 2 and not missing, str(missing[:4]))


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
        if not str(r.get("update_consensus_summary") or "").strip() and verdict not in vp.OFFICIAL:
            # No stored summary (no reports) and a reasoned verdict: the card has no evidence line.
            # An OFFICIAL verdict prints at any report count (AUX-097): G3-S9..S12.
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


def check_feed_wording() -> None:
    """G3-S6/S7 (review 2, LOW-4): the feed card's line over every report-bearing page."""
    c = corpus()
    site = {"data": {"verdict_projection": c["projection"], "patch_lifecycle": LIFECYCLE}}
    bearing = [r for r in c["recs"] if int(r.get("update_report_count") or 0) > 0]
    cases = {str(i): {"template": FEED_T, "item": dict(r, url=r.get("permalink")),
                      "summary": str(r.get("update_consensus_summary") or "")} for i, r in enumerate(bearing)}
    # The fallback: a stored line that lags (another lead), on each kind of identity the feed names.
    kinds = {}
    for r in bearing:
        pid = str(r.get("product_id"))
        kind = (pid, vp.rendered_verdict(r, c["projection"]["pages"])[0])
        kinds.setdefault(kind, r)
    for i, r in enumerate(kinds.values()):
        cases[f"lag:{i}"] = {"template": FEED_T, "item": dict(r, url=r.get("permalink")),
                             "summary": "STALE: an old line with another verdict."}
    out = render_includes(cases, site) or {}

    def line(key):
        m = re.search(r"@@(.*?)@@", out.get(key, ""), re.S)
        return m.group(1) if m else None

    def expected(r):
        d = pd.decide(r, valid_reasons=c["valid"].get(vr.record_identity(r), []), lifecycle=LIFECYCLE["entries"])
        return pd.summary_line(d, r, int(r.get("update_report_count") or 0), identity=identity_of(r))
    listed = [(r.get("permalink"), (line(str(i)) or "")[-80:]) for i, r in enumerate(bearing)
              if line(str(i)) is None or "listed below" in line(str(i))]
    unequal = [(r.get("permalink"), (line(str(i)) or "")[:70], expected(r)[:70]) for i, r in enumerate(bearing)
               if line(str(i)) != expected(r) or str(r.get("update_consensus_summary") or "") != expected(r)]
    check(f"G3-S6 no /updates/ feed card says its reports are 'listed below' (nothing is listed under a card): "
          f"over all {len(bearing)} report-bearing pages the card prints the stored line, which is the policy's "
          "feed line (lib/patch_decision.summary_line)",
          "__error__" not in out and len(bearing) > 200 and not listed and not unequal,
          f"{listed[:2]} {unequal[:2]}")
    lag_bad = [(r.get("permalink"), line(f"lag:{i}"), expected(r)[:80]) for i, r in enumerate(kinds.values())
               if line(f"lag:{i}") != expected(r)]
    check(f"G3-S7 when the feed falls back to the gate's own line it still names the exact patch, build "
          f"included, and equals the stored form ({len(kinds)} kinds of page: "
          f"{', '.join(sorted({k[0] for k in kinds}))})",
          bool(kinds) and any(k[0] == WIN for k in kinds) and not lag_bad, str(lag_bad[:2])[:400])


def check_avoid_recommendations() -> None:
    """G3-S8 (review 2, LOW-4): both KB5079391 pages carry the replacement step, the 24H2 one (0 reports,
    no writer, its stored list retracted at zero) included."""
    c = corpus()
    fresh = vp.project(c["recs"], c["groups"], REASONS["entries"], LIFECYCLE["entries"])[0]
    pages = [r for r in c["recs"] if pd.lifecycle_for(r, LIFECYCLE["entries"])]
    out = render_gate({str(i): {"rec": slim(r), "cnt": int(r.get("update_report_count") or 0)}
                       for i, r in enumerate(pages)},
                      {"verdict_projection": fresh, "patch_lifecycle": LIFECYCLE}, TEMPLATE_OVERRIDE,
                      suffix=RECS_PROBE) or {}
    printed = {r.get("permalink"): (re.search(r"##(.*?)##", out.get(str(i), ""), re.S) or [None, None])[1]
               for i, r in enumerate(pages)}
    want = "~".join(pd.AVOID_RECOMMENDATIONS)
    counts = sorted(int(r.get("update_report_count") or 0) for r in pages)
    stored = [list(r.get("practical_recommendations") or []) for r in pages if int(r.get("update_report_count") or 0)]
    layout = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    decision = (_AUX / "_includes" / "patch-decision.html").read_text(encoding="utf-8")
    check("G3-S8 both KB5079391 AVOID pages carry the same Recommendations list from the projection -- "
          "'install the replacement update instead' -- the zero-report 24H2 page included, and the report-"
          "bearing page's stored list is that same list",
          len(pages) == 2 and counts[0] == 0 and set(printed.values()) == {want}
          and "install the replacement update instead" in want
          and stored == [list(pd.AVOID_RECOMMENDATIONS)]
          and "{% assign decision_recommendations = gate_recommendations %}" in decision
          and "{% assign rec_list = decision_recommendations %}" in layout
          and "{%- for rec in rec_list -%}" in layout, f"{printed} {stored}")


# ------------------------------------------------------------------------ [X] mutants

# ------------------------------------------------------------------------ AUX-097: official verdicts in the feed

FEED_LAYOUT_PATH = _AUX / "_layouts" / "aux-updates.html"
LAYOUT_OVERRIDE: str | None = None   # the feed layout's text, set only by mutants X48 and X51
_FEED_ELSE = ("{% else %}{% include patch-feed-summary.html item=item summary='' %}"
              "{% if feed_summary_line != '' %}")


def feed_summary_of(r: dict) -> str:
    """The stored summary a feed card hands the include ('' when the record stores none)."""
    return str(r.get("update_consensus_summary") or r.get("community_summary") or "").strip()


def pre_aux097_feed_line(record, rows, summary=""):
    """The feed card's contract before AUX-097 (X47 and G3-Q12's probe only): no stored summary, no line."""
    return REAL_FEED_LINE(record, rows, summary) if str(summary or "").strip() else ""


REAL_FEED_LINE = vp.feed_line


def pre_aux097_layout() -> str:
    """The feed layout before AUX-097 (X48 only): a card with no stored summary prints nothing."""
    text = FEED_LAYOUT_PATH.read_text(encoding="utf-8")
    out = re.sub(r"\{% else %\}\{% include patch-feed-summary\.html item=item summary='' %\}.*?"
                 r"\{% endif %\}\{% endif %\}", "{% endif %}", text, flags=re.S)
    assert out != text
    return out


def feed_card_fragments(text: str) -> list[str]:
    """Each feed loop's evidence/verdict markup, from the stored-summary lookup to the card links:
    the part of the card AUX-097 changes, rendered as shipped (both loops: current and archive)."""
    return re.findall(r"(\{% assign consensus_summary = .*?)\n[ ]*<div class=\"patch-card-links\">", text, re.S)


PILL_SPAN = '<span class="patch-status patch-status--{{ reaction_class }}">'


def feed_pill_fragments(text: str) -> list[str]:
    """Each feed loop's status pill as shipped -- its label lookup, its class and its span -- wrapped
    in @@ so the rendered pill can be read back (both loops: current and archive)."""
    labels = re.findall(r"\{% assign reaction = item\.update_consensus_label [^%]*%\}", text)
    classes = re.findall(r"\{% assign reaction_class = reaction [^%]*%\}", text)
    pills = re.findall(re.escape(PILL_SPAN) + r".*?</span>", text)
    if not (len(labels) == len(classes) == len(pills)):
        return []
    return [f"{a}{b}@@{p}@@" for a, b, p in zip(labels, classes, pills)]


def stored_label(r: dict) -> str:
    """The label the card's pill used to print: the layout's `default` chain over the stored fields."""
    return str(r.get("update_consensus_label") or r.get("community_reaction") or "Insufficient")


def pre_review_pill_layout() -> str:
    """The feed layout as round 1 shipped it (X51 only): the pill prints the stored label, bare."""
    text = FEED_LAYOUT_PATH.read_text(encoding="utf-8")
    out = text.replace(PILL_SPAN + "{% include patch-feed-pill.html item=item label=reaction %}</span>",
                       PILL_SPAN + "{{ reaction }}</span>")
    assert out != text
    return out


def check_qa_feed(tmp: Path) -> None:
    """G3-Q12 (AUX-097): QA sees a feed card that would hide its page's official verdict."""
    import qa_patch_records as qa
    codes = lambda es: {e["code"] for e in es}  # noqa: E731
    code = "feed_official_verdict_unprinted"
    trees = {"security": _qa_win_tree(tmp / "sec", "2026-03 B", build="26200.1300"),
             "avoid": _qa_win_tree(tmp / "avoid", "2026-03 D", life_text=LIFECYCLE_TEXT, kb="KB5079391",
                                   build="26200.8116")}
    shipped = {k: _qa_scan(qa, tree) for k, tree in trees.items()}
    mutate, restore = swap(vp, "feed_line", pre_aux097_feed_line)
    mutate()
    try:
        hidden = {k: _qa_scan(qa, tree) for k, tree in trees.items()}
    finally:
        restore()
    seen = {k: (code in codes(w), code in codes(qa.promote_for_publication(e, w)[0]), code in codes(e))
            for k, (e, w) in hidden.items()}
    check("G3-Q12 a zero-report SECURITY UPDATE and the zero-report KB5079391 AVOID are clean in QA as shipped; "
          "with the feed card's pre-AUX-097 contract (no stored summary, no line) each is "
          "feed_official_verdict_unprinted: a writeback WARNING that --publish-strict makes an ERROR",
          not any(code in codes(e) | codes(w) for e, w in shipped.values())
          and seen == {"security": (True, True, False), "avoid": (True, True, False)},
          f"shipped={ {k: sorted(codes(e) | codes(w)) for k, (e, w) in shipped.items()} } hidden={seen}")

    # G3-Q13 (review 1, LOW-3): each half of the contract is checked on its own. A line that keeps the
    # verdict but not the page's line, or the page's line under another verdict, hides the verdict too.
    def lead_only(record, rows, summary=""):
        return REAL_FEED_LINE(record, rows, summary).split(": ", 1)[0] + ": Windows 11. An old reason."

    def tail_only(record, rows, summary=""):
        return "WAIT: " + REAL_FEED_LINE(record, rows, summary).split(": ", 1)[-1]
    halves = {}
    for name, fake in (("lead only", lead_only), ("tail only", tail_only)):
        mutate, restore = swap(vp, "feed_line", fake)
        mutate()
        try:
            halves[name] = {k: code in codes(_qa_scan(qa, tree)[1]) for k, tree in trees.items()}
        finally:
            restore()
    check("G3-Q13 QA checks each half of the feed line on its own: a line that keeps the verdict but drops the "
          "page's line, and one that keeps the page's line under another verdict, are each "
          "feed_official_verdict_unprinted",
          halves == {"lead only": {"security": True, "avoid": True}, "tail only": {"security": True, "avoid": True}},
          str(halves))


def check_feed_official() -> None:
    """G3-S9..S12 (AUX-097): every feed card states the official verdict its page prints, at any report
    count, and the include, its Python contract and the feed layout agree on every page."""
    c = corpus()
    recs = c["recs"]
    rows = c["projection"]["pages"]
    site = {"data": {"verdict_projection": c["projection"], "patch_lifecycle": LIFECYCLE}}
    layout = LAYOUT_OVERRIDE if LAYOUT_OVERRIDE is not None else FEED_LAYOUT_PATH.read_text(encoding="utf-8")
    fragments = feed_card_fragments(layout)
    pill_frags = feed_pill_fragments(layout)
    cases = {}
    for i, r in enumerate(recs):
        item = dict(r, url=r.get("permalink"))
        cases[f"inc:{i}"] = {"template": FEED_T, "item": item, "summary": feed_summary_of(r)}
        for j, frag in enumerate(fragments):
            cases[f"lay{j}:{i}"] = {"template": frag, "item": item, "summary": ""}
        for j, frag in enumerate(pill_frags):
            cases[f"pill{j}:{i}"] = {"template": frag, "item": item, "summary": ""}
    out = render_includes(cases, site) or {}

    def line(key):
        m = re.search(r"@@(.*?)@@", out.get(key, ""), re.S)
        return m.group(1) if m else None
    apart = [(r.get("permalink"), (line(f"inc:{i}") or "")[:70], vp.feed_line(r, rows, feed_summary_of(r))[:70])
             for i, r in enumerate(recs) if line(f"inc:{i}") != vp.feed_line(r, rows, feed_summary_of(r))]
    check(f"G3-S9 over all {len(recs)} records the feed card's include prints exactly "
          "lib/verdict_projection.feed_line, the contract QA reads",
          "__error__" not in out and len(recs) > 1000 and not apart,
          str(apart[:2])[:400] or str(out.get("__error__"))[:300])
    official, wrong, zero, quiet, lined = [], [], [], [], []
    decisions = {}
    for i, r in enumerate(recs):
        d = pd.decide(r, valid_reasons=c["valid"].get(vr.record_identity(r), []), lifecycle=LIFECYCLE["entries"])
        decisions[i] = d
        n = int(r.get("update_report_count") or 0)
        got = line(f"inc:{i}")
        if d.verdict in vp.OFFICIAL:
            official.append(r)
            if n == 0 and not feed_summary_of(r):
                zero.append((r.get("permalink"), d.verdict))
            if got != pd.summary_line(d, r, n, identity=identity_of(r)):
                wrong.append((r.get("permalink"), (got or "(no line)")[:80]))
        elif n == 0 and not feed_summary_of(r):
            (lined if got else quiet).append(r.get("permalink"))
    zero_kinds = {v for _p, v in zero}
    check(f"G3-S10 every page decide gives AVOID or SECURITY UPDATE ({len(official)}) has a feed card that "
          "states it -- verdict, scope, the exact patch and the page's line (lib/patch_decision.summary_line) "
          f"-- at any report count: {len(zero)} of them have no reports, the withdrawn KB5079391 among them",
          len(official) > 20 and zero_kinds == {"AVOID", "SECURITY UPDATE"}
          and "/updates/microsoft/microsoft-windows-11/24h2/26100.8116/" in {p for p, _v in zero} and not wrong,
          str(wrong[:2])[:400])
    check(f"G3-S11 a zero-report page with no verdict (INSUFFICIENT DATA, {len(quiet)} pages) still prints no "
          "feed line", len(quiet) > 500 and not lined, str(lined[:3]))
    bad_layout = []
    for j in range(len(fragments)):
        for i, r in enumerate(recs):
            html = out.get(f"lay{j}:{i}", "")
            d = decisions[i]
            n = int(r.get("update_report_count") or 0)
            lines = re.findall(r'<p class="patch-consensus-line">(.*?)</p>', html, re.S)
            labels = re.findall(r'<span class="patch-consensus-label">(.*?)</span>', html, re.S)
            if d.verdict in vp.OFFICIAL:
                want_label = "AUXSAYS verdict" if not feed_summary_of(r) else "Evidence summary"
                if lines != [pd.summary_line(d, r, n, identity=identity_of(r))] or labels != [want_label]:
                    bad_layout.append((j, r.get("permalink"), labels, [s[:60] for s in lines]))
            elif n == 0 and not feed_summary_of(r) and html.strip():
                bad_layout.append((j, r.get("permalink"), "a block on a zero-report INSUFFICIENT DATA card"))
    check(f"G3-S12 both feed loops ({len(fragments)}: current and archive), rendered as shipped, print every "
          "official verdict under 'AUXSAYS verdict' when the card stores no summary (the evidence pill beside it "
          "is not the verdict) and under 'Evidence summary' beside a stored one, and nothing on a zero-report "
          "INSUFFICIENT DATA card",
          len(fragments) == 2 and layout.count(_FEED_ELSE) == 2 and "__error__" not in out and not bad_layout,
          str(bad_layout[:2])[:400])
    # G3-S13 (review 1, MAJOR-1): the pill above that line is evidence, so on an official card it must not
    # print "Insufficient data", the name of a verdict. It prints the patch page's word for that label.
    bad_pill, renamed = [], []
    for j in range(len(pill_frags)):
        for i, r in enumerate(recs):
            label = stored_label(r)
            reworded = decisions[i].verdict in vp.OFFICIAL and "insufficient" in label.lower()
            want = "Not enough reports" if reworded else label
            cls = label.lower().replace(" ", "-")
            m = re.search(r'@@<span class="patch-status patch-status--([^"]*)">(.*?)</span>@@',
                          out.get(f"pill{j}:{i}", ""), re.S)
            if not m or m.group(1) != cls or m.group(2) != want \
                    or (decisions[i].verdict in vp.OFFICIAL and m.group(2).upper() in pd.CANONICAL_DECISIONS):
                bad_pill.append((j, r.get("permalink"), label, m and m.group(2)))
            elif reworded and j == 0:
                renamed.append(r.get("permalink"))
    check(f"G3-S13 both feed loops' status pill names no verdict on an official card: the {len(renamed)} "
          "AVOID / SECURITY UPDATE cards whose stored label is 'Insufficient data' print the patch page's "
          "community-signal word 'Not enough reports' (the withdrawn KB5079391 among them), and every other "
          f"card of {len(recs)} prints its stored label, its class and data-status untouched",
          len(pill_frags) == 2 and "__error__" not in out and not bad_pill and len(renamed) > 10
          and "/updates/microsoft/microsoft-windows-11/24h2/26100.8116/" in renamed,
          str(bad_pill[:3])[:400])


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


def swap_many(owner, replacements: dict):
    """swap() for several attributes of one owner that together are ONE fix (e.g. a set of patterns)."""
    originals = {name: getattr(owner, name) for name in replacements}
    return ((lambda: [setattr(owner, n, v) for n, v in replacements.items()]),
            (lambda: [setattr(owner, n, v) for n, v in originals.items()]))


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
    real_strict = vr._strict_string_problem
    real_project = vp.project

    def reasoned_only(records, groups, reasons, lifecycle):
        projection, unsupported = real_project(records, groups, reasons, lifecycle)
        return dict(projection, pages={k: v for k, v in projection["pages"].items()
                                       if v["verdict"] in vp.REASONED}), unsupported

    def old_model(record, rows, lifecycle=()):
        """rendered_verdict before review 2: the official facts read from the record, not the row."""
        if pd.lifecycle_for(dict(record), list(lifecycle or ())):
            return pd.AVOID, pd.AVOID_SCOPE
        if pd.is_monthly_security_update(dict(record)):
            return pd.SECURITY_UPDATE, ""
        row = rows.get(vp.page_key(record)) if isinstance(rows, dict) else None
        if isinstance(row, dict) and row.get("verdict") in vp.REASONED and str(row.get("scope") or "").strip():
            return str(row["verdict"]), str(row["scope"])
        return pd.INSUFFICIENT_DATA, ""

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
        ("X10 the gate drops a projected security update at zero reports", check_render_matrix,
         tpl("{%- if pvg_row_scope == '' -%}{%- assign pvg_printed = true -%}{%- endif -%}",
             "{%- if pvg_row_scope == '' and pvg_count > 0 -%}{%- assign pvg_printed = true -%}{%- endif -%}")),
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
        ("X17 the gate words the no-verdict line differently from Python", check_render_matrix,
         tpl("If one matches your setup, test before relying on this update.{%- endcapture -%}",
             "If one matches your setup, install it anyway.{%- endcapture -%}")),
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
         check_surfaces, inc("patch-feed-summary.html", "{%- if pfs_compose -%}", "{%- if false -%}")),
        ("X24 the writer's summary goes back to a bare verdict beside a count", check_surfaces,
         swap(pd, "summary_line", lambda d, r, n, fallback="", identity="": real_summary(
             d, r, n, fallback, identity).replace(pd.verdict_phrase(d) + ":", d.verdict + ":", 1))),
        # Review 2 (LOW-1..4): each restores ONE half of one fix.
        ("X25 (probe N1) the lifecycle check accepts a value that is not a string", check_lifecycle,
         swap(vr, "_strict_string_problem", lambda v: "" if not isinstance(v, str) else real_strict(v))),
        ("X26 the lifecycle check trims a padded value instead of refusing it", check_lifecycle,
         swap(vr, "_strict_string_problem", lambda v: real_strict(v.strip()) if isinstance(v, str) else real_strict(v))),
        ("X27 (gate2) the gate parses the release type itself again (slice + plus: 0)", check_render_official,
         tpl("{%- if pvg_printed -%}", OLD_TYPE_PARSE + "{%- if pvg_printed -%}")),
        ("X28 the gate matches the lifecycle file itself again", check_render_official,
         tpl("{%- if pvg_printed -%}", OLD_LIFECYCLE_MATCH + "{%- if pvg_printed -%}")),
        ("X29 the projection carries the reasoned rows only, as before review 2", check_projection_official,
         swap(vp, "project", reasoned_only)),
        ("X30 QA's model of the gate derives the official verdicts from the record again",
         check_render_matrix, swap(vp, "rendered_verdict", old_model)),
        ("X31 QA no longer reports a malformed release type", lambda: check_qa(tmp / f"x31-{next(qa_runs)}"),
         swap(pd, "release_type_problem", lambda record: "")),
        ("X32 the writer's feed line keeps 'listed below' (Python half)", check_feed_wording,
         swap(pd, "feed_body", lambda body: str(body or ""))),
        ("X33 the feed card keeps 'listed below' (Liquid half)", check_feed_wording,
         inc("patch-feed-summary.html",
             "{%- assign pfs_body = gate_body | replace: '; the individual reports are listed below.', '.' | "
             "replace: '; it is listed below.', '.' | replace: '; they are listed below.', '.' -%}",
             "{%- assign pfs_body = gate_body -%}")),
        ("X34 the feed's fallback line drops the patch name", check_feed_wording,
         inc("patch-feed-summary.html", "{% if pfs_identity != '' %}{{ pfs_identity }}. {% endif %}", "")),
        ("X35 an AVOID row carries no recommendations (Python half)", check_avoid_recommendations,
         swap(pd, "recommendations", lambda decision: [])),
        ("X36 the gate drops the row's recommendations (Liquid half)", check_avoid_recommendations,
         tpl("{%- if pvg_row.recommendations and pvg_row.recommendations.size > 0 -%}{%- assign gate_recommendations "
             "= pvg_row.recommendations -%}{%- endif -%}", "")),
        ("X37 the menu-bar reason says the crash is not new in this OBS version again", check_wording,
         swap(sys.modules[__name__], "REASONS", menu_bar_overclaim())),
        # PR-A2 review (LOW-1..3, MB1/MB2): each restores ONE half of one fix.
        ("X38 (probe P5) the page key strips Unicode spaces again (Python's str.strip)", check_render_identity,
         swap(vr, "record_identity", lambda r: tuple(str(r.get(f) if r.get(f) is not None else "").strip()
                                                     for f in vr.IDENTITY_FIELDS))),
        ("X39 (probe P5) QA no longer reports an identity Liquid and Python strip differently",
         lambda: check_qa(tmp / f"x39-{next(qa_runs)}"), swap(vr, "identity_padding_problems", lambda r: [])),
        # X40 (probe P3), split one mutant per pattern (G35-04 review 2, LOW-6): reverting four at once
        # let the shape detector's own fail-open survive.
        ("X40a (probe P3) the monthly-security pattern reads any Unicode digit again (no re.ASCII)",
         check_render_official, swap(pd, "_MONTHLY_SECURITY_RE", re.compile(pd._MONTHLY_SECURITY_RE.pattern))),
        ("X40b the preview pattern reads any Unicode digit again (no re.ASCII)",
         lambda: check_qa(tmp / f"x40b-{next(qa_runs)}"), swap(pd, "_PREVIEW_RE", re.compile(pd._PREVIEW_RE.pattern))),
        ("X40c the strict release-type pattern reads any Unicode digit again (no re.ASCII)",
         lambda: check_qa(tmp / f"x40c-{next(qa_runs)}"),
         swap(pd, "_RELEASE_TYPE_RE", re.compile(pd._RELEASE_TYPE_RE.pattern))),
        ("X40d (review 2, LOW-6) the shape detector is ASCII-only again (A2's re.ASCII)",
         lambda: check_qa(tmp / f"x40d-{next(qa_runs)}"),
         swap(pd, "_RELEASE_TYPE_SHAPED_RE", re.compile(pd._RELEASE_TYPE_SHAPED_RE.pattern, re.ASCII))),
        ("X40e (review 2, LOW-6) the shape detector reads the raw value, not its NFKC form",
         lambda: check_qa(tmp / f"x40e-{next(qa_runs)}"), swap(pd, "_release_type_shape", lambda raw: raw)),
        ("X41 the lifecycle KB and date patterns read any Unicode digit again", check_lifecycle,
         swap_many(vr, {"KB_RE": re.compile(r"^KB\d{7}$"), "DATE_RE": re.compile(r"^\d{4}-\d{2}-\d{2}$")})),
        ("X42 (probe P4) a lifecycle build is not checked against the ASCII build pattern", check_lifecycle,
         swap(vr, "LIFECYCLE_BUILD_RE", re.compile(r".+", re.S))),
        ("X43 (probe P4) QA no longer reports a lifecycle build that no record carries",
         lambda: check_qa(tmp / f"x43-{next(qa_runs)}"),
         swap(qa, "add", lambda bucket, path, code, msg: None if code == "patch_lifecycle_build_unmatched"
              else real_add(bucket, path, code, msg))),
        ("X44 (MB1) the gate prints a SECURITY UPDATE row that carries a scope", check_render_matrix,
         tpl("{%- if pvg_row_scope == '' -%}{%- assign pvg_printed = true -%}{%- endif -%}",
             "{%- assign pvg_printed = true -%}")),
        ("X45 (MB2) the gate prints an AVOID / WAIT / TEST FIRST row that carries no scope", check_render_matrix,
         tpl("{%- if pvg_row_scope != '' -%}{%- assign pvg_printed = true -%}{%- endif -%}",
             "{%- assign pvg_printed = true -%}")),
        # AUX-097: each restores ONE half of the zero-report official feed line.
        ("X46 the feed card composes a line only beside a stored summary again (Liquid half)", check_feed_official,
         inc("patch-feed-summary.html", "{%- if feed_summary_line != '' or gate_official -%}",
             "{%- if feed_summary_line != '' -%}")),
        ("X47 QA's contract of the feed card drops the official line too (Python half)", check_feed_official,
         swap(vp, "feed_line", pre_aux097_feed_line)),
        ("X48 the feed layout gives a card with no stored summary no line again", check_feed_official,
         swap(sys.modules[__name__], "LAYOUT_OVERRIDE", pre_aux097_layout())),
        ("X49 QA reports a hidden official verdict but no longer blocks publication on it",
         lambda: check_qa_feed(tmp / f"x49-{next(qa_runs)}"),
         swap(qa, "PUBLICATION_BLOCKING_CODES", qa.PUBLICATION_BLOCKING_CODES - {"feed_official_verdict_unprinted"})),
        ("X50 QA no longer checks the feed card's official line", lambda: check_qa_feed(tmp / f"x50-{next(qa_runs)}"),
         swap(qa, "add", lambda bucket, path, code, msg: None if code == "feed_official_verdict_unprinted"
              else real_add(bucket, path, code, msg))),
        # AUX-097 review 1 (MAJOR-1): each restores ONE half of the official card's pill wording.
        ("X51 the feed layout prints the stored label bare again ('Insufficient data' over the verdict)",
         check_feed_official, swap(sys.modules[__name__], "LAYOUT_OVERRIDE", pre_review_pill_layout())),
        ("X52 the pill rewords every 'Insufficient data' card, official verdict or not", check_feed_official,
         inc("patch-feed-pill.html", "{%- if gate_official -%}{%- assign pfp_label = 'Not enough reports' -%}{%- endif -%}",
             "{%- assign pfp_label = 'Not enough reports' -%}")),
        ("X53 the pill rewords an official card whatever its stored label", check_feed_official,
         inc("patch-feed-pill.html", "{%- if pfp_key contains 'insufficient' -%}", "{%- if true -%}")),
        # G35-04 review 2, LOW-7 (probe P6; AUTH_V2_38 WS2 first commit): each restores ONE half.
        ("X54 (probe P6) QA no longer reports an invisible or control character inside an identity",
         lambda: check_qa(tmp / f"x54-{next(qa_runs)}"), swap(vr, "identity_invisible_problems", lambda r: [])),
        ("X55 (probe P6) an invisible identity character is reported but no longer blocks publication",
         lambda: check_qa(tmp / f"x55-{next(qa_runs)}"),
         swap(qa, "PUBLICATION_BLOCKING_CODES",
              qa.PUBLICATION_BLOCKING_CODES - {"record_identity_invisible_character"})),
    ]
    for label, body, (mutate, restore) in cases:
        run_mutant(label, body, mutants, mutate=mutate, restore=restore)
    for label, failures, crash in mutants:
        detail = (f"mutant crashed instead of being caught: {crash}" if crash
                  else "no NAMED check failed that was not already failing")
        check(f"{label} -> caught", bool(failures), detail)
        if failures:
            print(f"        caught by: {', '.join(sorted(failures)[:4])}")


# The two official derivations the gate carried until review 2, restored by X27 / X28 only.
OLD_TYPE_PARSE = """{%- assign pvg_type = pvg_record.update_type | default: '' | strip -%}
{%- if pvg_pid == 'microsoft-windows-11' and pvg_type.size == 9 and pvg_printed == false -%}
  {%- assign pvg_year = pvg_type | slice: 0, 4 | plus: 0 -%}
  {%- assign pvg_dash = pvg_type | slice: 4, 1 -%}
  {%- assign pvg_month = pvg_type | slice: 5, 2 | plus: 0 -%}
  {%- assign pvg_tail = pvg_type | slice: 7, 2 -%}
  {%- if pvg_year >= 2000 and pvg_dash == '-' and pvg_month >= 1 and pvg_month <= 12 and pvg_tail == ' B' -%}
    {%- assign pvg_printed = true -%}{%- assign pvg_row_verdict = 'SECURITY UPDATE' -%}{%- assign pvg_row_scope = '' -%}
    {%- assign pvg_row_body = 'Microsoft classifies this as a monthly security update.' -%}
  {%- endif -%}
{%- endif -%}
"""
OLD_LIFECYCLE_MATCH = """{%- assign pvg_kb = pvg_record.target_kb | default: '' | strip -%}
{%- for pvg_entry in site.data.patch_lifecycle.entries -%}
  {%- if pvg_entry.product_id == pvg_pid and pvg_entry.kb == pvg_kb and pvg_entry.relationship == 'withdrawn_for_new_installs' and pvg_entry.builds contains pvg_build -%}
    {%- assign pvg_printed = true -%}{%- assign pvg_row_verdict = 'AVOID' -%}{%- assign pvg_row_scope = 'for new installations' -%}
    {%- assign pvg_row_body = 'Microsoft withdrew this update for new installations.' -%}{%- break -%}
  {%- endif -%}
{%- endfor -%}
"""


def menu_bar_overclaim() -> dict:
    """The shipped reasons with round 1's menu-bar line restored (X37 only)."""
    mutated = copy.deepcopy(REASONS)
    for e in mutated["entries"]:
        if e.get("id") == MENU_BAR_ENTRY:
            e["reason"] = str(e["reason"]).replace(
                "so it is triggered by macOS 27; no report shows it was caused by this OBS update.",
                "so the crash comes with macOS 27 and is not new in this OBS version.")
    return mutated


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
        check_qa_feed(tmp / "qf")
        print("\n[R] the Liquid gate renders what Python decides")
        check_render_matrix()
        check_render_corpus()
        check_render_official()
        print("\n[P] one authority: the projection, review 1's probes, the builder")
        check_projection()
        check_projection_official()
        check_projection_probes()
        check_projection_builder(tmp / "p")
        print("\n[S] the scope prints with the verdict on every surface; the feed card's wording")
        check_surfaces()
        check_feed_wording()
        check_avoid_recommendations()
        check_feed_official()
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
