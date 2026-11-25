#!/usr/bin/env python3
"""Source-supplied report facts: the data layer the provisional assessment reads (AUX-137).

AUX-137 (owner ruling of 2026-11-24; output-only design of 2026-11-25): the weighing is computed by a separate
scheduled step and read back through lib/assessment_output (test_assessment_output.py); this suite pins the DATA
LAYER only. Option B: `closed_by_reporter` is stored as
true, false or "unknown", compared in memory and never with an account; a closure is never a maintainer decision by
itself (the round-2 close-reason basis is withdrawn); a closed report's dismissal class is decided in one place; a
form version is a relation (same, earlier, later), never a silent exclusion.

Owner order of 2026-11-24: the absence of validated severity, recurring-issue, platform and positive-outcome fields
is an infrastructure deficiency; store deterministic facts, weigh them at 30 accepted reports, never infer a
successful installation from silence, and never hold a permanent automatic negative verdict on complaint volume
alone. `lib/assessment_facts` reads what a tracker's own record says about a report that is already counted (state,
close reason, maintainer labels, three issue-form fields); `scripts/backfill_report_source_facts.py` is the one
writer of `_data/report_source_facts.yml`; `lib/patch_decision.assess` calls `assessment_facts.weigh` once. The
independent review of 2026-11-24 found that the first rule could REMOVE caution from missing data; the checks
marked M1-M4 and S1-S7 pin its findings. Its re-check found that a bare closure (closed as completed, no maintainer
label: what a reporter closing their own report leaves) was counted as a maintainer decision; the checks marked N1
pin that a closure decides only with a maintainer's own mark on the record, and F6 that the refresh step cannot
cost the lane its writeback. Pinned here, on SYNTHETIC trackers, products, versions and counts (nothing
is tied to a product name or to today's numbers):

  [E] reading a source record: only the closed lists are read, and never a title, text or account
  [S] the store: its schema, a malformed file supporting nothing, an entry of another rule not being read
  [V] the vocabularies are data: the shipped file, a malformed one, and no label named in code (M2)
  [W] (AUX-137) what each stored fact means: option B, the dismissal classes, the version relation, the counting
  [R] review 2, R2-1: a reviewed TEST FIRST entry stored as new in the version is not worded as "not new"
  [B] the backfill tool: counted reports of known trackers only, bounded, resumable, pruned, dry by default; an open
      report is re-read after one day and a closed one after three
  [F] the scheduled lane refreshes the facts: one bounded step before the promotions, and the writeback allows the file
  [Q] QA names a missing facts file, a broken vocabulary and stale records under their own codes (S6, M3)
  [M] one module, one call: `weigh` is called once, from `assess`; the module imports no collector and no clock
  [C] the shipped facts file: well formed, and every entry belongs to a counted report (corpus-independent count)
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "tests"))

import yaml  # noqa: E402

import backfill_report_source_facts as tool  # noqa: E402
from lib import assessment_facts as af  # noqa: E402
from lib import evidence_facts as ef  # noqa: E402
from lib import evidence_overview as eo  # noqa: E402
from lib import patch_decision as pd  # noqa: E402
from lib import verdict_projection as vp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402
from lib.report_counts import row_is_counted  # noqa: E402
from lib.source_segments import report_url_key  # noqa: E402

N = pd.ASSESSMENT_MIN_REPORTS
TRACKER, OTHER_TRACKER = "github.com/example-org/example-app", "github.com/other-org/other-tool"
BARE_TRACKER = "github.com/third-org/third-app"          # a tracker with NO confirmation label (M2)
PLAIN_TRACKER = "github.com/fourth-org/fourth-app"       # a confirmation label, but NO maintainer close reason (N1)
MAINTAINED, OTHER_MAINTAINED, UNMAINTAINED, WIN = "comfyui", "microsoft-teams", "example-unmaintained", \
    "microsoft-windows-11"
VERSION = "9.8.7"
CHECKED, AS_OF = "2026-11-20", "2026-11-21"
VOCAB = {
    TRACKER: af.Vocabulary(authority="the example team", confirmed=("triage: accepted",), defect=("type: defect",),
                           regression=("type: regressed",), crash=("type: crash",),
                           dismissal={"triage: will not fix": "declined", "triage: no repro": "unreproducible"},
                           workaround=("triage: workaround",),
                           platform={"os: win": "windows", "os: mac": "macos"}, form_os="System",
                           os_values=((r"Win [0-9]+", "windows"), (r"Mac [0-9]+", "macos"), (r"Other", "other")),
                           form_crash="Crash dump", form_version="Version",
                           version_values=r"[0-9]+\.[0-9]+\.[0-9]+"),
    OTHER_TRACKER: af.Vocabulary(authority="the other team", confirmed=("ok",), defect=("type: defect",),
                                 regression=("broke",)),
    BARE_TRACKER: af.Vocabulary(authority="the third team", defect=("bug",), regression=("regressed",)),
    PLAIN_TRACKER: af.Vocabulary(authority="the fourth team", confirmed=("yes",)),
}
TYPED = ["type: defect"]            # the maintainers' own type label, in TRACKER's and OTHER_TRACKER's vocabulary

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")


# ------------------------------------------------------------------------------------------------ fixtures

def link(i: int, tracker: str = TRACKER) -> str:
    return f"https://{tracker}/issues/{i}"


def vrow(i: int, *, pid: str = MAINTAINED, version: str = VERSION, tracker: str = TRACKER, **over) -> dict:
    r = {"id": f"{pid}-{version}-af-{i}", "product_id": pid, "update_version": version,
         "source_type": "github_issue", "source_url": link(i, tracker),
         "report_title": f"Synthetic report {i} (AUX-137)", "report_text_excerpt": f"Synthetic report number {i}.",
         "captured_at": "2026-11-01T00:00:00Z", "source_date": "2026-10-30", "sentiment": "negative",
         "severity": "medium", "issue_theme": "unspecified issue", "counted": True, "patch_version_matched": True,
         "source_weight": 1}
    r.update(over)
    return ef.with_facts(r)


def rows(n: int, **kw) -> list[dict]:
    return [vrow(i, **kw) for i in range(1, n + 1)]


def rec(version: str = VERSION, *, pid: str = MAINTAINED, **over) -> dict:
    r = {"product_id": pid, "update_version": version, "update_product": f"Product {pid}", "update_entry": True,
         "update_status": "current", "update_report_count": 0, "update_source_name": "Example Vendor",
         "update_published_at": "2026-10-01T00:00:00Z", "evidence_state": "pilot_sample",
         "permalink": f"/updates/t/{pid}/{version.replace('.', '-')}/"}
    r.update(over)
    return r


def fact(i: int, *, tracker: str = TRACKER, state: str = "open", reason: str = "", labels=(), os: str = "",
         crash=None, version: str = "", checked: str = CHECKED, rule: str = af.RULE_VERSION, closed_by=None) -> dict:
    by = closed_by if closed_by is not None else (af.REPORTER_UNKNOWN if state == "open" else False)
    return {"key": link(i, tracker), "source": tracker, "state": state, "state_reason": reason,
            "labels": sorted(labels), "os": os, "crash_log": crash, "form_version": version,
            "closed_by_reporter": by, "checked_at": checked, "rule": rule}


def facts(n: int, special: dict | None = None, **kw) -> dict:
    """Records for reports 1..n: OPEN AND UNLABELLED (nobody decided anything), except the entries `special` gives
    by number."""
    out = {}
    for i in range(1, n + 1):
        entry = fact(i, **{**kw, **((special or {}).get(i) or {})})
        out[entry["key"]] = entry
    return out


def decided(n: int, special: dict | None = None, **kw) -> dict:
    """Records for reports 1..n that each carry a maintainer DECISION confirming nothing (closed as completed AND
    carrying the maintainers' type label: a closure as completed with no maintainer label is no decision, N1),
    except the entries `special` gives by number."""
    return facts(n, special, **{"state": "closed", "reason": "completed", "labels": TYPED, **kw})


def unmarked(n: int, special: dict | None = None, **kw) -> dict:
    """Records for reports 1..n that are each a BARE closure: closed as completed with no label at all, which is
    what a reporter closing their own report leaves on the tracker (N1)."""
    return facts(n, special, **{"state": "closed", "reason": "completed", **kw})


def reviewed(eid: str, verdict: str, rclass: str, *, new: bool | None = None, cite=(1, 2)) -> dict:
    e = {"id": eid, "product_id": MAINTAINED, "update_version": VERSION, "verdict": verdict, "reason_class": rclass,
         "scope": "if you use the first test setup" if verdict == "TEST FIRST" else "if you use the second test setup",
         "reason": f"Two users independently report that the {eid} setup fails.",
         "evidence": [{"id": f"{MAINTAINED}-{VERSION}-af-{i}", "source_url": link(i)} for i in cite],
         "new_in_this_version": (rclass == "regression") if new is None else new, "reviewed_at": "2026-11-24",
         "basis": "AUX-137 test"}
    if verdict == "WAIT":
        e.update(transition={"working": "9.8.6", "failing": VERSION}, material="it does not start")
    return e


def decide(record: dict, counted=(), source_facts=None, reasons=(), life=(), as_of: str = AS_OF) -> pd.Decision:
    return pd.decide(record, valid_reasons=list(reasons), lifecycle=list(life), counted_rows=list(counted),
                     source_facts=af.DatedFacts(source_facts, as_of))


def weigh(counted, source_facts, **kw) -> af.Weighing:
    kw.setdefault("version", VERSION)
    kw.setdefault("as_of", AS_OF)
    return af.weigh(counted, source_facts, minimum=N, **kw)


def lines_of(decision: pd.Decision, record: dict) -> dict[str, str]:
    return {line["label"]: line["text"] for line in pd.assessment_lines(decision.assessment, record)}


OPEN = {"state": "open", "reason": ""}
CONFIRMED = {"labels": ["triage: accepted"], **OPEN}
REGRESSED = {"labels": ["triage: accepted", "type: regressed"], **OPEN}
DECLINED = {"state": "closed", "reason": "not_planned"}
DUPLICATE = {"state": "closed", "reason": "duplicate"}


# ------------------------------------------------------------------------------------------------ [E]

def check_entries() -> None:
    section("[E] reading a tracker's own record of a report")
    body = ("### System\n\nWin 11\n\n### Version\n\n9.8.7\n\n### Crash dump\n\nhttps://dumps.test/abc\n\n"
            "### Notes\n\nfree text")
    issue = {"number": 7, "state": "closed", "state_reason": "not_planned", "title": "A PRIVATE TITLE",
             "body": body, "user": {"login": "someone", "id": 42}, "author_association": "MEMBER",
             "labels": [{"name": "os: win"}, {"name": "triage: accepted"}, {"name": "bad\nname"}, {"name": ""}]}
    entry = af.entry_from_issue(link(7), issue, CHECKED)
    check("E1 an entry holds the state, the close reason, the label names, the form's operating-system family and "
          "version, whether the crash field holds a link, and the day it was read",
          entry == {"key": link(7), "source": TRACKER, "state": "closed", "state_reason": "not_planned",
                    "labels": ["os: win", "triage: accepted"], "os": "windows", "crash_log": True,
                    "form_version": "9.8.7", "closed_by_reporter": af.REPORTER_UNKNOWN, "checked_at": CHECKED,
                    "rule": af.RULE_VERSION}, repr(entry))
    blob = json.dumps(entry)
    check("E2 it holds no title, no text, no account name, no account identifier and no role",
          tuple(entry) == af.ENTRY_KEYS and not any(s in blob for s in ("PRIVATE", "someone", "42", "MEMBER",
                                                                         "free text", "dumps.test")), blob)

    def read(text: str) -> dict:
        return af.entry_from_issue(link(7), dict(issue, body=text), CHECKED)

    check("E3 a value outside a closed list is not read: free text in the operating-system field gives no family, and "
          "text that is not a link in the crash field gives 'not established', never false",
          read("### System\n\nWin 11 Pro N build\n\n### Crash dump\n\nsee above")["os"] == ""
          and read("### System\n\nWin 11\n\n### Crash dump\n\nsee above")["crash_log"] is None
          and read("### System\n\nWin 11\n\n### Crash dump\n\n_No response_")["crash_log"] is False)
    check("E4 a form field that appears twice is ambiguous and is left out (a heading typed inside free text)",
          read("### System\n\nWin 11\n\n### Notes\n\nx\n\n### System\n\nMac 15")["os"] == "")
    check("E5 an object that is not that issue gives no entry: another number, a pull request, a state or close "
          "reason outside the closed lists, a tracker with no vocabulary, a link that is not an issue",
          af.entry_from_issue(link(8), issue, CHECKED) is None
          and af.entry_from_issue(link(7), dict(issue, pull_request={}), CHECKED) is None
          and af.entry_from_issue(link(7), dict(issue, state="merged"), CHECKED) is None
          and af.entry_from_issue(link(7), dict(issue, state_reason="spam"), CHECKED) is None
          and af.entry_from_issue("https://github.com/unknown-org/unknown/issues/7", issue, CHECKED) is None
          and af.entry_from_issue(f"https://{TRACKER}/pull/7", issue, CHECKED) is None)
    check("E6 every entry the reader returns passes the store's own schema",
          af.entry_errors(entry) == [] and af.entry_errors(af.entry_from_issue(
              link(9), {"number": 9, "state": "open", "state_reason": None, "labels": [], "body": None},
              CHECKED)) == [])
    check("E7 (S1) the form's version is read only when the WHOLE value is a version: 'Other', a list of versions "
          "and free text are not established, and a tracker with no version field stores none",
          read("### Version\n\nOther")["form_version"] == ""
          and read("### Version\n\n9.8.6, 9.8.7")["form_version"] == ""
          and read("### Version\n\n9.8.7 (64 bit)")["form_version"] == ""
          and read("### Version\n\n9.8.6")["form_version"] == "9.8.6"
          and af.entry_from_issue(link(7, OTHER_TRACKER), dict(issue, body="### Version\n\n9.8.7"),
                                  CHECKED)["form_version"] == "")
    closer = dict(issue, closed_by={"login": "someone", "id": 42})
    other = dict(issue, closed_by={"login": "a-maintainer", "id": 7})
    blobs = json.dumps([af.entry_from_issue(link(7), x, CHECKED) for x in (closer, other)])
    check("E8 (option B) the reporter's and the closer's accounts are compared in memory and only true, false or "
          "'unknown' is kept: the reporter's own closure is true, another account's false, and an open report, a "
          "deleted account ('ghost') or a missing side is 'unknown'; no account name or id reaches the entry",
          af.entry_from_issue(link(7), closer, CHECKED)["closed_by_reporter"] is True
          and af.entry_from_issue(link(7), other, CHECKED)["closed_by_reporter"] is False
          and af.entry_from_issue(link(7), dict(closer, state="open", state_reason=None), CHECKED)[
              "closed_by_reporter"] == af.REPORTER_UNKNOWN
          and af.entry_from_issue(link(7), dict(issue, closed_by={"login": "ghost"}, user={"login": "ghost"}),
                                  CHECKED)["closed_by_reporter"] == af.REPORTER_UNKNOWN
          and af.entry_from_issue(link(7), dict(issue, user=None, closed_by={"login": "x"}), CHECKED)[
              "closed_by_reporter"] == af.REPORTER_UNKNOWN
          and not any(t in blobs for t in ("someone", "a-maintainer", "42", '"7"', "login")), blobs)


# ------------------------------------------------------------------------------------------------ [S]

def check_store(tmp: Path) -> None:
    section("[S] the store")
    good = {"schema_version": af.SCHEMA_VERSION, "facts": [fact(1), fact(2, state="closed", reason="completed")]}
    check("S1 a well-formed file has no schema error and renders to text that loads to the same entries",
          af.schema_errors(good) == []
          and af.schema_errors(yaml.safe_load(af.render(good["facts"]))) == []
          and af.index(yaml.safe_load(af.render(good["facts"]))) == af.index(good))
    bad = {
        "an unknown key": dict(fact(1), reporter="x"),
        "a missing key": {k: v for k, v in fact(1).items() if k != "os"},
        "an entry of the first schema (no form version)": {k: v for k, v in fact(1).items() if k != "form_version"},
        "a state outside the list": fact(1, state="merged"),
        "a close reason outside the list": fact(1, reason="spam"),
        "unsorted labels": dict(fact(1), labels=["b", "a"]),
        "an operating system outside the list": fact(1, os="amiga"),
        "a crash value that is not true, false or null": dict(fact(1), crash_log="yes"),
        "a form version that is not a version": fact(1, version="the latest one"),
        "a key that is not a canonical issue link": dict(fact(1), key=link(1) + "/"),
        "a source that is not the key's tracker": dict(fact(1), source=OTHER_TRACKER),
        "a malformed date": dict(fact(1), checked_at="yesterday"),
        "a date that does not exist": dict(fact(1), checked_at="2026-02-31"),
        "(option B) an account in closed_by_reporter": fact(1, state="closed", reason="completed", closed_by="someone"),
        "(option B) a yes/no on an open report": fact(1, closed_by=True),
        "(option B) a missing closed_by_reporter": {k: v for k, v in fact(1).items() if k != "closed_by_reporter"},
    }
    wrong = [name for name, entry in bad.items()
             if not af.schema_errors({"schema_version": af.SCHEMA_VERSION, "facts": [entry]})]
    check("S2 each malformed entry is refused: " + ", ".join(bad), not wrong, str(wrong))
    check("S3 a duplicate key, a wrong schema version and a file that is not a mapping are refused",
          af.schema_errors({"schema_version": af.SCHEMA_VERSION, "facts": [fact(1), fact(1)]})
          and af.schema_errors({"schema_version": 99, "facts": []}) and af.schema_errors([fact(1)]))
    path = tmp / "facts.yml"
    path.write_text(yaml.safe_dump({"schema_version": af.SCHEMA_VERSION, "facts": [fact(1), fact(2, state="x")]}),
                    encoding="utf-8")
    refused = False
    try:
        af.load(path)
    except af.FactsFileError:
        refused = True
    check("S4 a file with ONE malformed entry supports nothing (it raises; it is never partly trusted), and a file "
          "that does not exist is simply no facts", refused and af.load(tmp / "absent.yml") == {})
    other_rule = {"schema_version": af.SCHEMA_VERSION, "facts": [fact(1), fact(2, rule="source-facts-0")]}
    check("S5 an entry written under another rule is well formed but is not read",
          af.schema_errors(other_rule) == [] and sorted(af.index(other_rule)) == [link(1)]
          and af.facts_for(vrow(2), {link(2): fact(2, rule="source-facts-0")}) is None)
    store = tmp / "store.yml"
    store.write_text("evidence:\n- id: a\n  captured_at: '2026-11-03T10:00:00Z'\n- id: b\n  captured_at: "
                     "2026-11-19T23:59:59Z\n- id: c\n  captured_at: '2026-13-45T00:00:00Z'\n- id: d\n  "
                     "source_date: '2027-01-01'\n", encoding="utf-8")
    check("S6 (M3) the date staleness is measured against is the newest day the evidence store collected a report: "
          "read from the tree, never from a clock; an impossible date is ignored and a missing store gives none",
          af.newest_capture(store) == "2026-11-19" and af.newest_capture(tmp / "absent-store.yml") == "")
    check("S7 (M3) a record is stale more than the stated number of days before that date, and when there is no "
          "readable date at all",
          not af.is_stale("2026-11-20", "2026-11-27") and af.is_stale("2026-11-20", "2026-11-28")
          and af.is_stale("2026-11-20", "") and af.is_stale("nonsense", "2026-11-21")
          and not af.is_stale("2026-11-25", "2026-11-21") and af.STALE_AFTER_DAYS == 7)


# ------------------------------------------------------------------------------------------------ [V]

def check_vocabulary(tmp: Path, shipped: dict) -> None:
    section("[V] the vocabularies are data")
    doc = yaml.safe_load(af.VOCABULARY_PATH.read_text(encoding="utf-8")) if af.VOCABULARY_PATH.is_file() else None
    check("V1 the shipped vocabulary file is well formed and is what the module reads",
          doc is not None and af.vocabulary_errors(doc) == [] and sorted(shipped) == sorted(doc["sources"])
          and af.sources_problem() == "", str(af.vocabulary_errors(doc) if doc else "absent")[:200])
    good = {"schema_version": 2, "sources": {TRACKER: {"authority": "the example team", "verified_at": "2026-11-24",
                                                         "confirmed": ["triage: accepted"],
                                                         "platform": {"os: win": "windows"},
                                                         "os_values": [["Win [0-9]+", "windows"]],
                                                         "form_version": "Version", "version_values": "[0-9.]+"}}}

    def broken(**change) -> dict:
        return {"schema_version": 2, "sources": {TRACKER: {**good["sources"][TRACKER], **change}}}

    bad = {"an unknown key": broken(owner="x"), "no authority": broken(authority=""),
           "no verification date": broken(verified_at="recently"), "labels that are not a list": broken(confirmed="x"),
           "a platform family outside the list": broken(platform={"os: x": "amiga"}),
           "a pattern that does not compile": broken(os_values=[["Win [", "windows"]]),
           "a version field with no pattern": broken(version_values=""),
           "(round 2, withdrawn) maintainer close reasons": broken(maintainer_close_reasons=["not_planned"]),
           "a dismissal class outside the list": broken(dismissal={"x": "fixed"}),
           "dismissal labels that are not a mapping": broken(dismissal=["x"]),
           "workaround labels that are not a list": broken(workaround="x"),
           "a tracker name that is not one": {"schema_version": 2, "sources": {"Example/App": {}}},
           "another schema version": {"schema_version": 1, "sources": {}}}
    wrong = [name for name, d in bad.items() if not af.vocabulary_errors(d)]
    check("V2 a well-formed vocabulary is accepted and each malformed one is refused: " + ", ".join(bad),
          af.vocabulary_errors(good) == [] and not wrong, str(wrong))
    path = tmp / "vocab.yml"
    path.write_text(yaml.safe_dump(broken(owner="x")), encoding="utf-8")
    refused = missing = False
    try:
        af.load_vocabularies(path)
    except af.VocabularyFileError:
        refused = True
    try:
        af.load_vocabularies(tmp / "absent-vocab.yml")
    except af.VocabularyFileError:
        missing = True
    path.write_text(yaml.safe_dump(good), encoding="utf-8")
    loaded = af.load_vocabularies(path)[TRACKER]
    check("V3 a malformed or missing vocabulary file declares no tracker (it raises), and a good one loads what it says",
          refused and missing and loaded.confirmed == frozenset({"triage: accepted"}) and loaded.confirmable
          and loaded.platform == {"os: win": "windows"} and loaded.form_version == "Version")
    code = (SCRIPTS / "lib" / "assessment_facts.py").read_text(encoding="utf-8").split('"""', 2)[2]
    named = sorted({label for vocab in shipped.values()
                    for label in vocab.confirmed | vocab.defect | vocab.regression | vocab.crash | set(vocab.platform)
                    if label in code} | {t for t in shipped if t in code})
    check("V4 (M2) no tracker and no label of a shipped vocabulary is named in the module's code: they are data",
          bool(shipped) and not named, str(named))
    bare = [t for t, v in shipped.items() if not v.confirmable]
    check("V5 (M2) a tracker declared without a confirmation label is not confirmable, and M4: no vocabulary folds a "
          "regression or crash label into its confirmation or defect labels",
          not VOCAB[BARE_TRACKER].confirmable and VOCAB[TRACKER].confirmable
          and all(not (v.confirmed & (v.regression | v.crash)) and not (v.defect & (v.regression | v.crash))
                  for v in list(shipped.values()) + list(VOCAB.values())), str(bare))
    path.write_text(yaml.safe_dump(broken(dismissal={"wontfix": "declined"}, workaround=["has workaround"])),
                    encoding="utf-8")
    declared = af.load_vocabularies(path)[TRACKER]
    check("V6 (option B) what a maintainer decision is, is DATA: a vocabulary's dismissal and workaround labels load as "
          "declared and are maintainer marks; a vocabulary that declares none has none; no shipped vocabulary "
          "declares a close reason (a closure is never a decision by itself)",
          declared.dismissal == {"wontfix": "declined"} and declared.workaround == frozenset({"has workaround"})
          and {"wontfix", "has workaround"} <= declared.marks and loaded.dismissal == {}
          and loaded.workaround == frozenset()
          and "maintainer_close_reasons" not in af.VOCABULARY_PATH.read_text(encoding="utf-8").split("schema_version")[1],
          repr({t: sorted(v.dismissal.items()) for t, v in shipped.items()}))


# ------------------------------------------------------------------------------------------------ [W]

def check_weighing() -> None:
    section("[W] (AUX-137) what each stored fact means")

    def one(**kw) -> af.ReportFacts:
        return af.ReportFacts(fact(1, **kw), VERSION, AS_OF)

    check("W1 a closure is NEVER a maintainer decision by itself, whatever its reason or closer; only a label from "
          "the vocabulary is",
          not any(one(state="closed", reason=r, closed_by=b).decided for r in ("completed", "not_planned", "duplicate")
                  for b in (True, False, af.REPORTER_UNKNOWN))
          and one(state="closed", reason="completed", labels=TYPED).decided and one(labels=TYPED).decided
          and one(labels=["triage: will not fix"]).decided and not one().decided)
    classes = {
        "reporter": one(state="closed", reason="not_planned", closed_by=True, labels=["triage: will not fix"]),
        "declined": one(state="closed", reason="not_planned", labels=["triage: will not fix"]),
        "unreproducible": one(state="closed", reason="completed", labels=["triage: no repro"]),
        "duplicate": one(state="closed", reason="duplicate"),
        "unknown_closer": one(state="closed", reason="completed", closed_by=af.REPORTER_UNKNOWN),
        "administrative": one(state="closed", reason="not_planned"),
        "unexplained": one(state="closed", reason="completed"),
    }
    check("W2 (residual path 2) every closed report that is not a confirmed fix is in exactly ONE dismissal class, the "
          "reporter's own closure first: " + ", ".join(classes),
          all(f.dismissal == name for name, f in classes.items()) and set(classes) <= set(af.DISMISSALS),
          repr({n: f.dismissal for n, f in classes.items()}))
    fix = one(state="closed", reason="completed", labels=["triage: accepted"])
    self_closed = one(state="closed", reason="completed", labels=["triage: accepted"], closed_by=True)
    check("W3 a confirmed fix is a CONFIRMED report closed as completed by another account; the same report closed by "
          "its own reporter is a self-closure, never a fix, and a closure by another account is never called a "
          "maintainer's",
          fix.confirmed_fix and fix.dismissal == "" and not self_closed.confirmed_fix
          and self_closed.dismissal == "reporter"
          and "does not show that a maintainer was involved" in af.Weighing().response() + _response())
    rel = {v: one(labels=["triage: accepted"], version=v).version for v in ("9.8.7", "9.8.6", "9.9.0", "")}
    check("W4 (residual path 1) the form's version is a RELATION to the page's, never an exclusion: same, earlier, "
          "later or not established, and the report stays confirmed in every case",
          rel == {"9.8.7": "same", "9.8.6": "earlier", "9.9.0": "later", "": ""}
          and all(one(labels=["triage: accepted"], version=v).confirmed for v in rel)
          and af.version_relation("33.0", "33.0.0") == "same" and af.version_relation("x", "1.0") == "")
    population = rows(6)
    source = facts(6, {1: dict(labels=["triage: accepted", "type: regressed"]),
                       2: dict(labels=["triage: accepted"], state="closed", reason="completed"),
                       3: dict(state="closed", reason="not_planned", closed_by=True),
                       4: dict(state="closed", reason="duplicate"), 5: dict(labels=TYPED)})
    w = af.weigh(population, source, version=VERSION, as_of=AS_OF)
    groups = (w.confirmed + sum(w.dismissals.values()) + w.open_marked + w.open_undecided)
    check("W5 the counting puts every fresh record in exactly one group and decides no verdict",
          (w.confirmed, w.regressions, w.confirmed_open, w.confirmed_fix, w.dismissals["reporter"],
           w.dismissals["duplicate"], w.open_marked, w.open_undecided) == (2, 1, 1, 1, 1, 1, 1, 1)
          and groups == w.fresh == 6 and not hasattr(w, "verdict") and not hasattr(w, "available"),
          repr((w.confirmed, w.dismissals, w.open_marked, w.open_undecided)))
    old = af.weigh(population, source, version=VERSION, as_of="2026-12-30")
    check("W6 (M3) records read too long before the newest collected report are not used",
          old.stale == 6 and old.fresh == 0 and old.confirmed == 0)


def _response() -> str:
    w = af.weigh(rows(2), facts(2, {1: dict(state="closed", reason="completed")}), version=VERSION, as_of=AS_OF)
    return w.response()


# ------------------------------------------------------------------------------------------------ [R]

def check_review_finding() -> None:
    section("[R] review 2, R2-1")
    record, population = rec(), rows(N + 2)
    new = decide(record, population, reasons=[reviewed("first", "TEST FIRST", "corroborated_issue", new=True)])
    old = decide(record, population, reasons=[reviewed("first", "TEST FIRST", "corroborated_issue", new=False)])
    check("R1 a supported TEST FIRST entry stored as new in this version is not worded as 'does not confirm a problem "
          "new in this version'; one stored as not new still is",
          "does not confirm a problem new" not in json.dumps(lines_of(new, record))
          and pd.ASSESS_REVIEWED_TEST_FIRST_NEW in lines_of(new, record)["Problem confirmation"]
          and pd.ASSESS_REVIEWED_LEVEL["TEST FIRST"] in lines_of(old, record)["Problem confirmation"])


# ------------------------------------------------------------------------------------------------ [B]

def check_backfill(tmp: Path) -> None:
    section("[B] the backfill tool")
    store, out, replay = tmp / "store.yml", tmp / "report_source_facts.yml", tmp / "replay"
    replay.mkdir()
    counted = [vrow(i) for i in range(1, 6)]
    uncounted = dict(vrow(6), counted=False)
    elsewhere = dict(vrow(7), source_url="https://forum.test/thread/7")
    other_product = vrow(8, pid=OTHER_MAINTAINED)
    store.write_text(yaml.safe_dump({"evidence": counted + [uncounted, elsewhere, other_product]}), encoding="utf-8")
    for i in range(1, 9):
        (replay / f"example-org__example-app__{i}.json").write_text(json.dumps(
            {"number": i, "state": "closed" if i == 4 else "open", "state_reason": "completed" if i == 4 else None,
             "title": "T", "body": "### System\n\nWin 11\n\n### Version\n\n9.8.7",
             "labels": [{"name": "triage: accepted"}] if i == 2 else [], "user": {"login": "x"}}), encoding="utf-8")
    check("B0 the fixture's rows are counted as the store counts them", all(row_is_counted(r) for r in counted)
          and not row_is_counted(uncounted))
    dry = tool.run(store, out, replay_dir=replay, today="2026-11-20")
    check("B1 a dry run reads and writes nothing to disk", dry["read"] == 6 and not out.exists())
    first = tool.run(store, out, replay_dir=replay, today="2026-11-20", max_requests=2, write=True)
    kept = af.load(out)
    check("B2 a run is bounded: two reads, two entries, the rest left for the next run",
          (first["read"], first["written"], first["remaining"], len(kept)) == (2, 2, 4, 2), repr(first))
    second = tool.run(store, out, replay_dir=replay, today="2026-11-20", write=True)
    kept = af.load(out)
    check("B3 the next run continues where the first stopped, and reads only counted reports of a tracker with a "
          "vocabulary: never an uncounted row, never another source",
          second["read"] == 4 and sorted(kept) == sorted(link(i) for i in (1, 2, 3, 4, 5, 8)), repr(sorted(kept)))
    check("B4 the stored entries carry the facts (the form's version among them) and nothing of the report",
          kept[link(2)]["labels"] == ["triage: accepted"] and kept[link(1)]["os"] == "windows"
          and kept[link(1)]["form_version"] == "9.8.7"
          and '"T"' not in out.read_text(encoding="utf-8") and "login" not in out.read_text(encoding="utf-8"))
    again = tool.run(store, out, replay_dir=replay, today="2026-11-20", write=True)
    next_day = tool.run(store, out, replay_dir=replay, today="2026-11-21", max_requests=3, write=True)
    rest = tool.run(store, out, replay_dir=replay, today="2026-11-21", write=True)
    after_one = af.load(out)
    third_day = tool.run(store, out, replay_dir=replay, today="2026-11-23", write=True)
    check("B5 (M3) an entry read today is left alone; an OPEN report is read again after one day, the oldest read "
          "first and within the bound; a CLOSED one only after three days",
          (again["read"], again["changed"]) == (0, False) and (next_day["read"], next_day["remaining"]) == (3, 2)
          and rest["read"] == 2 and after_one[link(4)]["checked_at"] == "2026-11-20"
          and sorted(e["checked_at"] for e in after_one.values()).count("2026-11-21") == 5
          and third_day["read"] == 6 and af.load(out)[link(4)]["checked_at"] == "2026-11-23"
          and tool.DEFAULT_MAX_AGE_DAYS < af.STALE_AFTER_DAYS and tool.DEFAULT_OPEN_MAX_AGE_DAYS == 1,
          repr((again, next_day, rest, third_day)))
    store.write_text(yaml.safe_dump({"evidence": counted[:3] + [other_product]}), encoding="utf-8")
    scoped = tool.run(store, out, replay_dir=replay, today="2026-11-23", product_id=MAINTAINED, write=True)
    check("B6 entries of reports that no longer count are dropped, and a product-scoped run keeps the other "
          "products' entries",
          scoped["dropped"] == 2 and sorted(af.load(out)) == sorted(link(i) for i in (1, 2, 3, 8)), repr(scoped))
    (replay / "example-org__example-app__3.json").write_text(json.dumps({"number": 999, "state": "open"}),
                                                              encoding="utf-8")
    before = af.load(out)[link(3)]
    bad = tool.run(store, out, replay_dir=replay, today="2026-12-30", write=True)
    check("B7 a record that is not that issue leaves the earlier entry in place and is counted as unreadable",
          bad["unreadable"] == 1 and af.load(out)[link(3)] == before, repr(bad))
    out.write_text(f"schema_version: {af.SCHEMA_VERSION}\nfacts:\n- key: nonsense\n", encoding="utf-8")
    refused = False
    try:
        tool.run(store, out, replay_dir=replay, today="2026-12-30", write=True)
    except af.FactsFileError:
        refused = True
    check("B8 a malformed facts file is never overwritten blindly: the tool stops", refused)
    check("B9 the tool's request goes to the tracker's REST issue endpoint for exactly that issue",
          tool.api_url(link(41)) == "https://api.github.com/repos/example-org/example-app/issues/41")
    out.unlink()
    store.write_text(yaml.safe_dump({"evidence": counted}), encoding="utf-8")
    ticks = iter(range(0, 1000, 10))
    timed = tool.run(store, out, replay_dir=replay, today="2026-12-30", write=True, max_seconds=25,
                     clock=lambda: next(ticks))
    check("B10 (M3) a run stops READING by itself when its time budget is spent, and still writes what it read: the "
          "workflow step's hard cap never has to kill it",
          (timed["stopped"], timed["read"], timed["remaining"]) == ("time_budget", 2, 3) and len(af.load(out)) == 2,
          repr(timed))


# ------------------------------------------------------------------------------------------------ [F]

def check_lane() -> None:
    section("[F] the scheduled lane refreshes the facts")
    path = REPO / ".github" / "workflows" / "obs-evidence-collection.yml"
    doc = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
    steps = doc["jobs"]["collect"]["steps"]

    def code(step: dict) -> str:
        """A step's shell with its comment lines removed (a mention in a comment runs nothing)."""
        return "\n".join(line for line in str(step.get("run") or "").splitlines() if not line.lstrip().startswith("#"))

    calls = [i for i, s in enumerate(steps) if "backfill_report_source_facts.py" in code(s)]
    step = steps[calls[0]] if calls else {}
    run = code(step)
    promotions = [i for i, s in enumerate(steps) if "apply_consensus_to_records.py" in code(s)]
    collect = [i for i, s in enumerate(steps) if "run_patch_evidence_collection.py" in code(s)]
    seconds = re.search(r"--max-seconds\s+([1-9][0-9]*)\b", run)
    check("F1 (M3) exactly one step of the scheduled collection lane runs the backfill, in write mode and bounded: "
          "by a number of requests, and by a time budget of its own that ends before the step's hard cap",
          len(calls) == 1 and "--write" in run.split() and re.search(r"--max-requests\s+[1-9][0-9]*\b", run) is not None
          and isinstance(step.get("timeout-minutes"), int) and seconds is not None
          and int(seconds.group(1)) + 60 <= step["timeout-minutes"] * 60, run)
    check("F2 it runs after collection and before every promotion that reads the facts, and never on a dry run",
          bool(calls and collect and promotions) and collect[0] < calls[0] < min(promotions)
          and "dry_run != 'true'" in str(step.get("if") or ""), str((collect, calls, promotions[:1])))
    check("F3 its shell fails on an error anywhere in the step (bash with pipefail set by the step itself)",
          step.get("shell") == "bash" and "set -euo pipefail" in run)
    writeback = [s for s in steps if "automation_writeback.py" in code(s)]
    allowed = re.findall(r"--allow\s+'?([^'\s\\]+)'?", code(writeback[0])) if writeback else []
    check("F4 the lane's writeback allows the facts file (an unlisted tracked change would fail the commit), and the "
          "schedule that runs the lane is still there",
          f"auxsays/_data/{af.FACTS_NAME}" in allowed and allowed.count(f"auxsays/_data/{af.FACTS_NAME}") == 1
          and bool((doc.get(True) or doc.get("on") or {}).get("schedule")), str(allowed[-3:]))
    others = [p.name for p in (REPO / ".github" / "workflows").glob("*.yml")
              if p != path and "backfill_report_source_facts" in p.read_text(encoding="utf-8")]
    check("F5 no other workflow writes the facts file (one writer, one lane)", others == [], str(others))
    gates = [s for s in steps[calls[0] + 1:] if "qa_patch_records.py" in code(s) or "automation_writeback.py" in code(s)] \
        if calls else []
    check("F6 (review round 2) the refresh is NOT fatal to the lane: the step is continue-on-error, so a crash or its "
          "time cap never skips the writeback of the cycle's collected evidence; it still ends non-zero and prints a "
          "warning when the tool fails (the failure stays in the log), and the QA and writeback steps after it are "
          "not continue-on-error themselves",
          step.get("continue-on-error") is True and re.search(r"if ! python \S*backfill_report_source_facts\.py", run)
          is not None and "::warning" in run and re.search(r"^\s*exit 1\s*$", run, re.M) is not None
          and len(gates) >= 2 and not any(s.get("continue-on-error") for s in gates),
          repr((step.get("continue-on-error"), len(gates))))


# ------------------------------------------------------------------------------------------------ [G]

# ------------------------------------------------------------------------------------------------ [Q]

def check_qa() -> None:
    section("[Q] QA names missing and stale facts")
    import qa_patch_records as qa  # noqa: PLC0415

    files = sorted((SCRIPTS.parent / "updates" / "generated").glob("*.md"))

    def codes(found: list) -> set[str]:
        return set(re.findall(r"report_source_\w+", json.dumps(found)))

    saved_sources = dict(af._SOURCES_STATE)
    try:
        af.reset_stored()
        af._STORED.update(facts={}, problem="", missing=True)
        af._SOURCES_STATE.update(loaded=True, problem="report_source_vocabularies.yml: 1 schema error(s)")
        errors, _warnings = qa.scan_verdict_policy(files)
        gone = codes(errors)
        af._SOURCES_STATE.clear()
        af._SOURCES_STATE.update(saved_sources)
        af.reset_stored()
        af.stored()
        af._STORED["as_of"] = "2999-01-01"
        stale_errors, stale_warnings = qa.scan_verdict_policy(files)
        aged = codes(stale_warnings)
        named = [w for w in stale_warnings if "report_source_facts_stale" in json.dumps(w)
                 or "report_source_facts_aging" in json.dumps(w)]
    finally:
        af._SOURCES_STATE.clear()
        af._SOURCES_STATE.update(saved_sources)
        af.reset_stored()
    check("Q1 (S6) a missing facts file is a QA error under its own code, and so is a vocabulary file that cannot be "
          "read; neither passes as a silent fallback",
          {"report_source_facts_missing", "report_source_vocabulary_invalid"} <= gone, str(sorted(gone)))
    pages_with_records = bool(af.stored())
    check("Q2 (M3) records too old to use are named page by page under their own QA code, as a warning: the pages "
          "fall back to the count, and the deploy is not blocked by a refresh that did not run (AUX-137: "
          "report_source_facts_aging where no current stored assessment reads them)",
          (not pages_with_records) or (bool({"report_source_facts_stale", "report_source_facts_aging"} & aged)
                                       and len(named) >= 1
                                       and not {"report_source_facts_stale", "report_source_facts_aging"}
                                       & codes(stale_errors)),
          str((sorted(aged), len(named))))
    af.reset_stored()


# ------------------------------------------------------------------------------------------------ [M]

def check_one_call() -> None:
    section("[M] one module, one call")
    authority = (SCRIPTS / "lib" / "patch_decision.py").read_text(encoding="utf-8")
    code = re.sub(r"#[^\n]*", "", authority)
    callers = [p.name for p in list(SCRIPTS.glob("*.py")) + list((SCRIPTS / "lib").glob("*.py"))
               if p.name != "assessment_facts.py" and "assessment_facts.weigh(" in p.read_text(encoding="utf-8")]
    check("M1 (AUX-137) the counting is called from one place, the reader of the stored provisional assessment, and "
          "the decision authority calls that reader once",
          code.count("assessment_output.weighing_for(") == 1 and "assessment_facts.weigh(" not in code
          and callers == ["assessment_output.py"], str(callers))
    source = (SCRIPTS / "lib" / "assessment_facts.py").read_text(encoding="utf-8")
    imports = sorted(set(re.findall(r"^(?:from|import)\s+([.\w]+)", source, re.M)))
    body = source.split('"""', 2)[2]
    check("M2 the module imports no collector and no network client, and reads no clock: the one date it compares "
          "against comes from the tree",
          imports == [".source_segments", "__future__", "collections", "datetime", "pathlib", "re", "typing"]
          and not re.search(r"\.(?:now|today|utcnow)\(|\btime\.", body), str(imports))
    weighing = source[source.index("class Weighing"):]
    check("M3 the weighing never names a product or a tracker: the trackers are data",
          not re.search(r"obs|comfy|office|github", weighing, re.I), "a product or tracker name in the weighing")


# ------------------------------------------------------------------------------------------------ [C]

def check_corpus() -> None:
    section("[C] the shipped facts file")
    path = SCRIPTS.parent / "_data" / af.FACTS_NAME
    doc = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader) if path.is_file() else None
    check("C1 the shipped file exists and is well formed", doc is not None and af.schema_errors(doc) == [],
          str((af.schema_errors(doc) if doc else ["absent"])[:2]))
    _records, groups = vp.load_inputs(SCRIPTS.parent)
    counted = {report_url_key(str(r.get("source_url") or "")) for rows_ in groups.values() for r in rows_}
    stray = sorted(set(af.index(doc or {"facts": []})) - counted)
    check("C2 every entry belongs to a report that is counted today (the file holds no other report)", not stray,
          str(stray[:3]))
    check("C3 the file is exactly what its one writer renders (never edited by hand)",
          doc is not None and path.read_text(encoding="utf-8") == af.render(doc["facts"]))
    blob = path.read_text(encoding="utf-8") if path.is_file() else ""
    check("C4 no entry carries a key outside the schema (no title, text or account field)",
          doc is not None and all(tuple(e) == af.ENTRY_KEYS for e in doc["facts"])
          and not re.search(r"^\s*(?:title|body|user|login|author\w*|reporter\w*):", blob, re.M))
    undeclared = sorted({e["source"] for e in (doc or {"facts": []})["facts"]} - set(af.sources()))
    check("C5 every entry belongs to a tracker the vocabulary file declares", not undeclared, str(undeclared))


def run() -> int:
    shipped = dict(af.sources())
    af.sources().update(VOCAB)
    try:
        check_entries()
        with tempfile.TemporaryDirectory(prefix="aux135-") as td:
            check_store(Path(td))
        with tempfile.TemporaryDirectory(prefix="aux135-") as td:
            check_vocabulary(Path(td), shipped)
        check_weighing()
        check_review_finding()
        with tempfile.TemporaryDirectory(prefix="aux135-") as td:
            check_backfill(Path(td))
        check_one_call()
    finally:
        af.sources().clear()
        af.sources().update(shipped)
    check_lane()
    check_qa()
    check_corpus()
    print()
    for label in FAILURES:
        print(f"  failed: {label}")
    print("=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
