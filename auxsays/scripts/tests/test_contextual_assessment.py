#!/usr/bin/env python3
"""The provisional contextual risk assessment at the report-count trigger (AUX-134).

Owner order of 2026-11-23: at 30 independent, accepted, patch-specific reports the system must run and publish a
mandatory provisional contextual risk assessment; the count is "a trigger to assess, not an automatic WAIT/AVOID
verdict or statistically representative estimate of installer failure rate". What this branch builds is the PUBLISHED part
of that, not the weighing: with no limiting fact the count alone still gives the volume-based WAIT (check B1), and
whether that stays is the owner's pending decision. `lib/patch_decision.assess` runs at
ASSESSMENT_MIN_REPORTS counted rows for every product and every outcome; `decide` returns the verdict it reached
with its basis and its limiting evidence (Decision.assessment); `lib/evidence_overview` carries the published lines
to the page (`risk_assessment`) and `_includes/patch-evidence-overview.html` prints them. Pinned here:

  [T] the trigger: nothing below it, an assessment at it on ANY product, the same result for other products,
      versions and counts (nothing is tied to a product name, a version or today's numbers)
  [N] what keeps the count out of the verdict: thirty rows carrying one stored excerpt, a missing comparison fact,
      a product outside the maintained set, a report cited twice, an unpublishable row and an official security
      identification, each named as the limiting evidence in a sentence that is true of the page (the scope rule
      says only that it is a scope rule; a number is printed only where it was measured; an empty stored excerpt
      is neither a duplicate nor a lost report). With none of them the count alone still gives WAIT ([B])
  [B] the basis of a volume WAIT: the volume alone with no cause confirmed, a reviewed finding as well, or a
      vendor-documented known issue as well; the printed verdict row is the same in all three
  [P] precedence, and caution below the trigger: a withdrawal and a monthly security classification decide the
      page and the assessment says so; a reviewed regression gives WAIT at three reports, a withdrawal AVOID at none
  [S] scattered reports: a still-valid reviewed finding is stated, and no line reads the count as one defect
  [F] favourable rows: sentiment is not an input, nothing becomes SAFE ENOUGH, positive outcomes are "Not established"
  [H] collection health, the clock, sentiment and maturity are not inputs
  [R] release context: archived, a newer release (never called safer; a fix is not assumed carried forward), proven
      newest, a product with no release comparison; and how many report links only this version counts
  [G] the public-text guard reads the assessment lines; no line states the trigger, a rate or a percentage
  [Q] QA: a page at the trigger with no assessment, or one naming another verdict than the gate, blocks publication;
      a page whose volume WAIT is withheld only by rows without a readable stored fact is named by its own warning
  [L] the shipped Liquid prints the lines as the projection gives them, and nothing without a Recommendation
  [C] corpus: every page at the trigger carries an assessment whose result is the verdict its gate prints, and no
      other page carries one

Offline: synthetic rows, and the shipped corpus read once. The liquid gem renders the real include.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_contextual_assessment.py
"""
from __future__ import annotations

import inspect
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
SCRIPTS = _AUX / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import qa_patch_records as qa  # noqa: E402
from lib import evidence_facts as ef  # noqa: E402
from lib import evidence_overview as eo  # noqa: E402
from lib import maturity  # noqa: E402
from lib import patch_decision as pd  # noqa: E402
from lib import verdict_projection as vp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402

MAINTAINED, OTHER_MAINTAINED, UNMAINTAINED, WIN = "comfyui", "microsoft-teams", "example-unmaintained", \
    "microsoft-windows-11"
ALLOWED = {"AVOID", "WAIT", "SAFE ENOUGH", "OFFICIAL ONLY", "INSUFFICIENT DATA", "SECURITY UPDATE", "TEST FIRST",
           "MANUAL WATCH"}
N = pd.ASSESSMENT_MIN_REPORTS

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

def vrow(i: int, *, pid: str = MAINTAINED, version: str = "9.8.7", url: str | None = None, **over) -> dict:
    """One counted, publishable row as the store holds it (facts computed at the persistence boundary)."""
    r = {"id": f"{pid}-{version}-ca-{i}", "product_id": pid, "update_version": version,
         "source_type": "github_issue", "source_url": url or f"https://reports.test/{pid}/{version}/{i}",
         "report_title": f"Synthetic report {i} (AUX-134)", "report_text_excerpt": f"Synthetic report number {i}.",
         "captured_at": "2026-11-01T00:00:00Z", "source_date": "2026-10-30", "sentiment": "negative",
         "severity": "medium", "issue_theme": "unspecified issue", "counted": True, "patch_version_matched": True,
         "source_weight": 1}
    r.update(over)
    return ef.with_facts(r)


def rows(n: int, **kw) -> list[dict]:
    return [vrow(i, **kw) for i in range(1, n + 1)]


def rec(version: str = "9.8.7", *, pid: str = MAINTAINED, **over) -> dict:
    r = {"product_id": pid, "update_version": version, "update_product": f"Product {pid}", "update_entry": True,
         "update_status": "current", "update_report_count": 0, "update_source_name": "Example Vendor",
         "update_published_at": "2026-10-01T00:00:00Z", "evidence_state": "pilot_sample",
         "permalink": f"/updates/t/{pid}/{version.replace('.', '-')}/"}
    r.update(over)
    return r


def entry(eid: str, verdict: str, rclass: str, *, pid: str = MAINTAINED, version: str = "9.8.7", cite=(1, 2)) -> dict:
    e = {"id": eid, "product_id": pid, "update_version": version, "verdict": verdict, "reason_class": rclass,
         "scope": "if you use the first test setup" if verdict == "TEST FIRST" else "if you use the second test setup",
         "reason": f"Two users independently report that the {eid} setup fails.",
         "evidence": [{"id": f"{pid}-{version}-ca-{i}", "source_url": f"https://reports.test/{pid}/{version}/{i}"}
                      for i in cite],
         "new_in_this_version": rclass == "regression", "reviewed_at": "2026-11-23", "basis": "AUX-134 test"}
    if verdict == "WAIT":
        e.update(transition={"working": "9.8.6", "failing": version}, material="it does not start")
    return e


def decide(record: dict, counted=(), reasons=(), life=()) -> pd.Decision:
    return pd.decide(record, valid_reasons=list(reasons), lifecycle=list(life), counted_rows=list(counted))


def overview(records: list[dict], groups: dict, reasons=(), life=(), reviewed=None) -> dict:
    """The overview projection exactly as a deploy builds it: the verdict projection first, then the overview from
    its rows, both from the same records, counted rows, reasons and lifecycle."""
    verdict = vp.project(records, groups, list(reasons), list(life))[0]
    return eo.project(records, groups, verdict["pages"], list(reasons), reviewed or {}, [], lifecycle=list(life))["pages"]


def one(record: dict, population: list[dict], **kw) -> dict:
    return overview([record], {vr.record_identity(record): population}, **kw).get(vp.page_key(record)) or {}


def lines_of(row: dict) -> dict[str, str]:
    return {line["label"]: line["text"] for line in (row.get("risk_assessment") or {}).get("lines") or []}


def all_strings() -> list[str]:
    """Every sentence the assessment can publish, as the module holds it."""
    out = [pd.ASSESS_MATURITY, pd.ASSESS_EXCLUSIVE_ALL, pd.ASSESS_EXCLUSIVE_SOME, pd.ASSESS_REVIEWED_TAIL,
           *pd.ASSESS_REVIEWED_LEVEL.values(), pd.ASSESS_FINDING_PREFIX, pd.ASSESS_UNCONFIRMED, pd.ASSESS_VENDOR_DECLARED, pd.ASSESS_VENDOR_NONE,
           pd.ASSESS_SEVERITY, pd.ASSESS_SETUPS_REVIEWED, pd.ASSESS_SETUPS, pd.ASSESS_POSITIVE, pd.ASSESS_RELEASED,
           pd.ASSESS_COLLECTION, pd.ASSESS_PROVISIONAL]
    return out + list(pd.ASSESS_RECOMMENDATION.values()) + list(pd.ASSESS_LIMIT.values()) + list(pd.ASSESS_RELEASE.values())


# ------------------------------------------------------------------------------------------------ [T]

def check_trigger() -> None:
    section("[T] the trigger: an assessment runs at it")
    record = rec()
    below = decide(record, rows(N - 1))
    check("T1 one report below the trigger: no assessment runs, the page keeps INSUFFICIENT DATA and its overview row "
          "carries no risk assessment",
          below.assessment is None and below.verdict == "INSUFFICIENT DATA"
          and "risk_assessment" not in one(record, rows(N - 1)), repr(below))
    at = decide(record, rows(N))
    check("T2 at the trigger the assessment runs: its result is the decision's verdict, with a basis and no limit",
          at.assessment is not None and at.assessment.result == at.verdict == "WAIT"
          and at.assessment.basis == pd.BASIS_VOLUME and at.assessment.limits == ()
          and at.assessment.rule == pd.ASSESSMENT_RULE, repr(at.assessment))
    same = []
    for pid, version, count in ((OTHER_MAINTAINED, "5", N), ("obs-studio", "77.1", N + 1), (MAINTAINED, "0.0.1", 57),
                                ("adobe-acrobat-pro", "25.001.20997", 101)):
        d = decide(rec(version, pid=pid), rows(count, pid=pid, version=version))
        same.append((d.verdict, d.assessment.basis, d.assessment.limits, d.assessment.reports == count))
    check("T3 the same result for other maintained products, versions and counts: nothing is tied to a product name, "
          "a version or today's numbers", set(same) == {("WAIT", pd.BASIS_VOLUME, (), True)}, str(same))
    unmaintained = decide(rec(pid=UNMAINTAINED), rows(N, pid=UNMAINTAINED))
    check("T4 the assessment is mandatory at the trigger on a product outside the maintained set too: it runs, and "
          "says why the count cannot set a recommendation there",
          unmaintained.assessment is not None and unmaintained.verdict == "INSUFFICIENT DATA"
          and unmaintained.assessment.basis == pd.BASIS_LIMITED
          and unmaintained.assessment.limits == ("not_promotion_product",), repr(unmaintained.assessment))
    check("T5 the trigger is the approved volume minimum, and no maturity threshold moved",
          pd.ASSESSMENT_MIN_REPORTS == pd.VOLUME_MIN_REPORTS == pd.VOLUME_MIN_UNIQUE_URLS
          == pd.VOLUME_MIN_INDEPENDENT == 30 and maturity.LIVE_MIN_ACCEPTED_REPORTS == 33)


# ------------------------------------------------------------------------------------------------ [N]

def check_not_automatic() -> None:
    section("[N] what keeps the count out of the verdict")
    record = rec()
    copies = [vrow(i, report_text_excerpt="The same complaint, posted again.") for i in range(1, N + 6)]
    d = decide(record, copies)
    text = lines_of(one(record, copies))
    check("N1 thirty-five rows on thirty-five links that carry ONE stored excerpt are one reporter, not thirty-five "
          "reports: no WAIT, and the limiting evidence says so",
          d.verdict == "INSUFFICIENT DATA" and d.assessment.limits == ("below_independent_reports:1",)
          and d.assessment.independent == 1 and text.get("Recommendation", "").startswith("No recommendation.")
          and "identical text are read as one reporter" in text.get("Limiting evidence", ""), str(text))
    near = rows(N - 1) + [vrow(N, report_text_excerpt="Synthetic report number 1.")]
    over = rows(N) + [vrow(N + 1, report_text_excerpt="Synthetic report number 1.")]
    check("N2 the boundary: thirty rows of which two share an excerpt are twenty-nine separate reports (no WAIT); "
          "thirty-one rows of which two share one are thirty (WAIT)",
          decide(record, near).verdict == "INSUFFICIENT DATA"
          and decide(record, near).assessment.limits == (f"below_independent_reports:{N - 1}",)
          and decide(record, over).verdict == "WAIT" and decide(record, over).assessment.independent == N)
    bare = rows(N)
    bare[4] = {k: v for k, v in bare[4].items() if k not in ef.STORED_FIELDS}
    d_bare = decide(record, bare)
    check("N3 a row whose stored comparison fact is missing is never rebuilt from its text: the page has not shown "
          "its reports are separate, so no WAIT (fail closed), and the limit is named",
          d_bare.verdict == "INSUFFICIENT DATA" and d_bare.assessment.limits == ("report_facts_unavailable:1",)
          and "are not shown to be separate reports" in lines_of(one(record, bare)).get("Limiting evidence", ""))
    un = rec(pid=UNMAINTAINED, update_product="Example Suite")
    text = lines_of(one(un, rows(73, pid=UNMAINTAINED)))
    check("N4 seventy-three reports on a product outside the maintained set: INSUFFICIENT DATA stays, and the page "
          "names the precise limit and the product instead of a generic label",
          text.get("Recommendation") == pd.ASSESS_RECOMMENDATION[pd.BASIS_LIMITED]
          and text.get("Limiting evidence") == pd.ASSESS_LIMIT["not_promotion_product"].format(product="Example Suite")
          and text.get("Evidence maturity", "").startswith("73 accepted patch-specific reports on 73 separate"),
          str(text))
    dup = rows(N) + [vrow(N + 1, url=f"https://reports.test/{MAINTAINED}/9.8.7/1")]
    unpub = rows(N) + [vrow(N + 1, source_date_pass=False)]
    sec = rec(security_sensitive=True)
    cases = {"duplicate_citation_urls": decide(record, dup), "unpublishable_rows": decide(record, unpub),
             "officially_identified_security_update": decide(sec, rows(N))}
    named = {code: [limit.partition(":")[0] for limit in d.assessment.limits] for code, d in cases.items()}
    check("N5 a report cited twice, an unpublishable row and an official security identification each keep the count "
          "out of the verdict",
          all(d.verdict == "INSUFFICIENT DATA" and code in named[code] for code, d in cases.items()), str(named))
    produced = set()
    for population, record_ in ((copies, record), (bare, record), (dup, record), (unpub, record), (rows(N), sec),
                                (rows(N, pid=UNMAINTAINED), rec(pid=UNMAINTAINED)),
                                ([vrow(i, url="https://reports.test/one") for i in range(1, N + 1)], record)):
        a = decide(record_, population).assessment
        produced |= {limit.partition(":")[0] for limit in a.limits}
        pd.assessment_limit_lines(a, record_)  # raises on a code with no sentence
    check("N6 every limit the conditions can produce has its own sentence (a new limit can never publish as silence)",
          produced == set(pd.ASSESS_LIMIT), f"{sorted(produced)} vs {sorted(pd.ASSESS_LIMIT)}")
    tf = entry("tf", "TEST FIRST", "corroborated_issue")
    d_tf = decide(rec(pid=UNMAINTAINED), rows(N, pid=UNMAINTAINED), reasons=[dict(tf, product_id=UNMAINTAINED)])
    first = pd.assessment_lines(d_tf.assessment, rec(pid=UNMAINTAINED))[0]["text"]
    check("N7 with a limit, a reviewed finding still decides the page: its verdict and scope, basis reviewed_finding, "
          "and the count adds no wider recommendation",
          d_tf.verdict == "TEST FIRST" and d_tf.rule == "R4" and d_tf.assessment.basis == pd.BASIS_REVIEWED
          and first.startswith("TEST FIRST if you use the first test setup. The reviewed finding"), first)
    # Review round 1, F3: ONE rule for a row with an empty stored excerpt, in every mix.
    sparse = [vrow(i, report_text_excerpt="" if i > 1 else "The one report with stored text.") for i in range(1, 61)]
    d_sparse = decide(record, sparse)
    check("N8 sixty reports on sixty links of which fifty-nine carry no stored text are sixty separate reports, not "
          "one: an empty excerpt is not proof of duplication, so the WAIT stays and no limit is printed",
          d_sparse.verdict == "WAIT" and d_sparse.assessment.independent == 60 and d_sparse.assessment.limits == ()
          and "Limiting evidence" not in lines_of(one(record, sparse)),
          f"{d_sparse.verdict} {d_sparse.assessment.independent} {d_sparse.assessment.limits}")

    def mix(empty: int, texted: int, shared: int) -> list[dict]:
        """`empty` rows without stored text, then `texted` rows with text of which `shared` repeat the first."""
        out = [vrow(i, report_text_excerpt="") for i in range(1, empty + 1)]
        out += [vrow(empty + i, report_text_excerpt="Stored text one." if i <= shared else f"Stored text {i}.")
                for i in range(1, texted + 1)]
        return out

    counts = {name: independent_of(decide(record, population))
              for name, population in (("all_empty", mix(N, 0, 0)), ("at", mix(10, N - 9, 2)),
                                       ("below", mix(10, N - 10, 2)), ("none_empty", mix(0, N, 2)))}
    check("N9 the same rule when every row is empty and when some are: an empty row stands on its report link, and "
          "rows that DO share a text are still one reporter beside it (ten empty + twenty-one with text, two of "
          "them identical = thirty and WAIT; one fewer = twenty-nine and no WAIT)",
          counts == {"all_empty": (N, "WAIT"), "at": (N, "WAIT"), "below": (N - 1, "INSUFFICIENT DATA"),
                     "none_empty": (N - 1, "INSUFFICIENT DATA")}, str(counts))
    # Review round 1, F6: a limit sentence prints a number only where the code measured exactly that number.
    said = lines_of(one(record, near)).get("Limiting evidence", "")
    alone = sum(1 for r in near
                if sum(1 for o in near if o["report_text_excerpt"] == r["report_text_excerpt"]) == 1)
    check("N10 thirty reports of which two share a text: the sentence states the rule and the number the rule gives "
          "(twenty-nine), and no longer calls that the number of reports that differ from every other (twenty-eight)",
          alone == N - 2 and decide(record, near).assessment.independent == N - 1
          and said == pd.ASSESS_LIMIT["below_independent_reports"].format(k=N - 1, n=N)
          and re.findall(r"\d+", said) == [str(N), str(N - 1)] and "differ" not in said, said)
    thrice = rows(N + 2)[:-3] + [vrow(N + k, url=f"https://reports.test/{MAINTAINED}/9.8.7/{k}") for k in (1, 2, 3)]
    dup_line = pd.ASSESS_LIMIT["duplicate_citation_urls"].format(k="", n=len(thrice))
    said = lines_of(one(record, thrice)).get("Limiting evidence", "")
    check("N11 three report links each cited twice: the sentence about shared links states no number of them (none "
          "is measured), and never 'one report'",
          "duplicate_citation_urls" in decide(record, thrice).assessment.limits and dup_line in said
          and re.findall(r"\d+", dup_line) == [str(len(thrice))] and "one report is" not in said.lower()
          and "more than once" not in said, said)
    # Review round 1, F2: the sentence for a product outside the set says what is true of the page and no more.
    scope = pd.ASSESS_LIMIT["not_promotion_product"]
    check("N12 a product outside the set is told that the volume rule does not cover it, as a rule of scope: nothing "
          "about its counts being unreliable, unretracted or including withdrawn reports",
          scope.startswith("AUXSAYS does not apply its report-volume recommendation to {product}.")
          and "not a finding about these reports" in scope
          and not [w for w in ("retract", "withdraw", "count", "number") if w in scope.lower()], scope)


def independent_of(decision: pd.Decision) -> tuple[int, str]:
    return decision.assessment.independent, decision.verdict


# ------------------------------------------------------------------------------------------------ [B]

def check_basis() -> None:
    section("[B] why a volume WAIT applies")
    record, population = rec(), rows(N)
    plain = decide(record, population)
    tf = decide(record, population, reasons=[entry("tf", "TEST FIRST", "corroborated_issue")])
    wait = decide(record, population, reasons=[entry("w", "WAIT", "regression")])
    declared = rec(official_notes_known_issue="declared")
    health = rec(official_known_issues_present=True)
    v1, v2 = decide(declared, population), decide(health, population)
    check("B1 no reviewed finding and no vendor declaration: the basis is the volume alone, and the line says no "
          "single cause is confirmed and that it is not a failure rate",
          plain.assessment.basis == pd.BASIS_VOLUME
          and "No single cause is confirmed" in pd.ASSESS_RECOMMENDATION[pd.BASIS_VOLUME]
          and "do not show how often installations fail" in pd.ASSESS_RECOMMENDATION[pd.BASIS_VOLUME])
    check("B2 a supported reviewed TEST FIRST or WAIT beside the volume: the basis names the reviewed finding, which "
          "stays printed beneath the WAIT with its own scope",
          tf.verdict == wait.verdict == "WAIT"
          and tf.assessment.basis == wait.assessment.basis == pd.BASIS_REVIEWED_AND_VOLUME
          and (tf.assessment.corroborated, wait.assessment.confirmed) == (1, 1)
          and "Also TEST FIRST if you use the first test setup" in pd.public_body(tf, record, N)
          and "Also WAIT if you use the second test setup" in pd.public_body(wait, record, N))
    check("B3 a vendor-documented known issue for this exact release (either stored field) beside the volume: the "
          "basis names it and the line names the vendor",
          v1.assessment.basis == v2.assessment.basis == pd.BASIS_VENDOR_ISSUE_AND_VOLUME
          and pd.assessment_lines(v1.assessment, declared)[0]["text"].startswith(
              "WAIT. Example Vendor has documented a known issue affecting this version"))
    printed = [vp.row_for(d, r) for d, r in ((plain, record), (v1, declared))]
    check("B4 the printed verdict row is the approved volume WAIT in every case: same reason code, label and line",
          all(row["reason_code"] == pd.VOLUME_REASON_CODE and row["label"] == pd.VOLUME_LABEL
              and row["body"] == pd.VOLUME_BODY.format(n=N) for row in printed)
          and vp.row_for(tf, record)["reason_code"] == pd.VOLUME_REASON_CODE)
    absent = lines_of(one(record, population)).get("Vendor known issues", "")
    check("B5 an absent vendor field is never read as 'no known issue': the line says none is on record and that this "
          "is not a statement that none exists", absent == pd.ASSESS_VENDOR_NONE and "not a statement" in absent)
    # Review round 1, F7: a reviewed finding is worded at the strength of its own stored verdict.
    tf_entry, wait_entry = entry("tf", "TEST FIRST", "corroborated_issue"), entry("w", "WAIT", "regression")
    said = {name: lines_of(one(record, population, reasons=reasons))
            for name, reasons in (("tf", [tf_entry]), ("wait", [wait_entry]), ("both", [tf_entry, wait_entry]))}
    level = pd.ASSESS_REVIEWED_LEVEL
    worded = {name: (text["Recommendation"], text["Problem confirmation"]) for name, text in said.items()}
    check("B6 a reviewed TEST FIRST beside the volume is worded as TEST FIRST advice that does not confirm a problem "
          "new in this version; only a reviewed WAIT is worded as a problem new in this version (and it words the "
          "page that carries both); nothing is called 'established'",
          all(level["TEST FIRST"] in line for line in worded["tf"])
          and all(level["WAIT"] in line and level["TEST FIRST"] not in line
                  for name in ("wait", "both") for line in worded[name])
          and not any(level["WAIT"] in line for line in worded["tf"])
          and level["TEST FIRST"].startswith("A reviewed finding advises TEST FIRST on a named setup")
          and "does not confirm" in level["TEST FIRST"]
          and not [line for pair in worded.values() for line in pair
                   if "establishes" in line.lower() or line.lower().startswith("established")], str(worded["tf"]))


# ------------------------------------------------------------------------------------------------ [P]

def check_precedence() -> None:
    section("[P] official facts decide, and serious harm needs no count")
    win_b = rec("25H2", pid=WIN, target_build="26200.1000", target_kb="KB5000001", update_type="2026-02 B")
    sec = decide(win_b, rows(40, pid=WIN, version="25H2"))
    life = [{"id": "life", "product_id": WIN, "kb": "KB5000002", "builds": ["26200.2000"],
             "relationship": "withdrawn_for_new_installs", "replacement_kb": "KB5000003"}]
    win_w = rec("25H2", pid=WIN, target_build="26200.2000", target_kb="KB5000002", update_type="2026-03 D")
    gone = decide(win_w, rows(40, pid=WIN, version="25H2"), life=life)
    check("P1 a monthly security classification decides the page at any count; the assessment runs and says the "
          "reports do not override it, with no limiting-evidence line",
          sec.verdict == "SECURITY UPDATE" and sec.assessment.basis == pd.BASIS_OFFICIAL_SECURITY
          and pd.assessment_limit_lines(sec.assessment, win_b) == []
          and "do not override it" in pd.assessment_lines(sec.assessment, win_b)[0]["text"])
    check("P2 an official withdrawal decides the page at any count: AVOID for new installations",
          gone.verdict == "AVOID" and gone.assessment.basis == pd.BASIS_OFFICIAL_WITHDRAWAL
          and gone.assessment.scope == pd.AVOID_SCOPE
          and pd.assessment_lines(gone.assessment, win_w)[0]["text"].startswith("AVOID for new installations."))
    three = decide(rec(), rows(3), reasons=[entry("w", "WAIT", "regression")])
    none = decide(win_w, [], life=life)
    check("P3 below the trigger, serious verified harm already gets earlier caution: a supported reviewed regression "
          "is WAIT at three reports and a withdrawal is AVOID at none; neither waits for a count",
          (three.verdict, three.rule, three.scope) == ("WAIT", "R3", "if you use the second test setup")
          and three.assessment is None and none.verdict == "AVOID" and none.assessment is None)


# ------------------------------------------------------------------------------------------------ [S] [F] [H]

def check_scattered_favourable_health() -> None:
    section("[S] scattered reports, [F] favourable rows, [H] collection health")
    record, population = rec(), rows(N)
    finding = "No individual problem was confirmed in the available evidence."
    reviewed = {"schema_version": 1, "label_withheld_products": [], "assessments": [{
        "id": "t:finding", "product_id": MAINTAINED, "update_version": "9.8.7", "target_build": "",
        "finding": finding, "basis": "test", "assessed_reports": N,
        "assessed_population_sha256": eo.population_digest(population), "reviewed_at": "2026-11-23"}]}
    held = lines_of(one(record, population, reviewed=reviewed))
    moved = lines_of(one(record, population + [vrow(N + 1)], reviewed=reviewed))
    check("S1 thirty different complaints are not thirty corroborations: a reviewed finding still valid for exactly "
          "this population is stated; one added report and the line returns to 'Not established'",
          held.get("Problem confirmation") == pd.ASSESS_FINDING_PREFIX + finding
          and moved.get("Problem confirmation") == pd.ASSESS_UNCONFIRMED
          and "not a count of one defect" in pd.ASSESS_UNCONFIRMED, str(held.get("Problem confirmation")))
    kind = {s: rows(N, sentiment=s) for s in sorted(pd.VALID_SENTIMENTS)}
    verdicts = {s: (decide(record, pop).verdict, decide(record, pop).assessment.basis) for s, pop in kind.items()}
    check("F1 sentiment is not an input: rows marked positive, moderate or negative give one result, and a favourable "
          "tone never becomes SAFE ENOUGH", len(set(verdicts.values())) == 1
          and all(v == "WAIT" for v, _b in verdicts.values()), str(verdicts))
    seen = set()
    for count in (0, 1, N - 1, N, N + 30):
        for r in (rec(), rec(pid=UNMAINTAINED), rec(official_notes_known_issue="declared"),
                  rec(update_status="archived"), rec(security_sensitive=True)):
            pop = rows(count, pid=r["product_id"])
            for reasons in ((), [dict(entry("tf", "TEST FIRST", "corroborated_issue"), product_id=r["product_id"])]):
                seen.add(decide(r, pop, reasons=reasons if count >= 2 else ()).verdict)
    check("F2 over every synthetic context the result is an allowed verdict, and the count never produces SAFE ENOUGH, "
          "OFFICIAL ONLY, MANUAL WATCH or AVOID", seen <= ALLOWED
          and not seen & {"SAFE ENOUGH", "OFFICIAL ONLY", "MANUAL WATCH", "AVOID"}, str(sorted(seen)))
    check("F3 positive outcomes are stated as not established, and silence is not read as safety",
          lines_of(one(record, population)).get("Positive outcomes") == pd.ASSESS_POSITIVE
          and "a lack of complaints is not evidence that a version is safe" in pd.ASSESS_POSITIVE)
    params = set(inspect.signature(pd.decide).parameters) | set(inspect.signature(pd.assess).parameters)
    stale = rec(evidence_state="collector_blocked", consensus_collection_status="collector_stale",
                update_consensus_label="Positive", update_report_count=0)
    check("H1 collection health, the clock, sentiment, maturity and the stored count are not inputs: the authority "
          "accepts none of them, and a record that stores a blocked collector decides exactly as a healthy one",
          params == {"record", "valid_reasons", "lifecycle", "counted_rows", "reviewed_reasons", "withdrawn",
                     "security"}
          and (decide(stale, population).verdict, decide(stale, population).assessment.basis)
          == (decide(record, population).verdict, decide(record, population).assessment.basis)
          and lines_of(one(stale, population)).get("Collection health") == pd.ASSESS_COLLECTION
          and "does not change this assessment" in pd.ASSESS_COLLECTION)


# ------------------------------------------------------------------------------------------------ [R]

def check_release_context() -> None:
    section("[R] release context and patch-specific links")
    old = rec("9.8.7", update_published_at="2026-09-01T00:00:00Z")
    new = rec("9.9.0", update_published_at="2026-10-15T00:00:00Z", update_product="Product comfyui")
    old_rows, new_rows = rows(N), rows(2, version="9.9.0")
    pages = overview([old, new], {vr.record_identity(old): old_rows, vr.record_identity(new): new_rows})
    superseded = lines_of(pages[vp.page_key(old)]).get("Release and alternatives", "")
    check("R1 a superseded release names the newer one on record, never calls it safer, and does not assume a fix "
          "carries forward",
          superseded.startswith("Released 2026-09-01. A newer release is on record: Product comfyui 9.9.0.")
          and "Newer is not necessarily safer" in superseded and "not assumed to carry into a later one" in superseded,
          superseded)
    archived = lines_of(one(rec(update_status="archived"), rows(N))).get("Release and alternatives", "")
    newest = lines_of(one(rec(), rows(N))).get("Release and alternatives", "")
    windows = rec("25H2", pid=WIN, target_build="26200.1000", target_kb="KB5000001", update_type="2026-02 B")
    excluded = lines_of(one(windows, rows(N, pid=WIN, version="25H2", target_build="26200.1000"))).get(
        "Release and alternatives", "")
    check("R2 archived, proven newest and a product with no release comparison each get their own sentence",
          archived == "Released 2026-10-01. This release is archived."
          and newest == "Released 2026-10-01. AUXSAYS has no record of a newer release."
          and excluded.endswith("AUXSAYS does not compare releases of this product."),
          f"{archived!r} {newest!r} {excluded!r}")
    shared = rows(N + 2)
    twin = [vrow(900 + i, version="9.9.0", url=shared[i]["source_url"]) for i in range(3)]
    pages = overview([old, new], {vr.record_identity(old): shared, vr.record_identity(new): twin})
    mine = lines_of(pages[vp.page_key(old)]).get("Evidence maturity", "")
    alone = lines_of(one(rec(), rows(N))).get("Evidence maturity", "")
    check("R3 how many report links only this version counts is stated from the whole population: three links also "
          "counted for another version are named; a page whose links are all its own says so",
          mine == (f"{N + 2} accepted patch-specific reports on {N + 2} separate report links. {N - 1} of those "
                   "links are counted for this version only; 3 are also counted for another tracked version.")
          and alone.endswith("Each of those links is counted for this version only."), mine)


# ------------------------------------------------------------------------------------------------ [G]

def check_guards() -> None:
    section("[G] public text")
    strings = all_strings()
    joined = " ".join(strings).lower()
    bad = [p for p in eo.FORBIDDEN_WORDING if p in joined]
    check("G1 no assessment sentence states an acceptance rule, a threshold, a rate, a percentage or a number of its "
          "own, and 'safer' appears only as 'not necessarily safer'",
          not bad and "%" not in joined and "percent" not in joined and not re.search(r"\d", joined)
          and joined.count("safer") == joined.count("not necessarily safer") == 1, f"{bad}")
    record, population = rec(), rows(N)
    row = one(record, population)
    clean = eo.public_text_problems(row, population)
    forged = json.loads(json.dumps(row))
    forged["risk_assessment"]["lines"][0]["text"] += " This needs at least a few more reports."
    leak = json.loads(json.dumps(row))
    leak["risk_assessment"]["lines"][2]["text"] += " " + population[0]["report_text_excerpt"] + " again and again."
    check("G2 the public-text guard reads the assessment lines: a clean row passes, a threshold phrase or a stored "
          "report text inside a line is refused",
          clean == [] and any("at least" in p for p in eo.public_text_problems(forged, population))
          and any("more reports" in p for p in eo.public_text_problems(forged, population)), str(clean))
    labels = [line["label"] for line in row["risk_assessment"]["lines"]]
    order = [label for label in pd.ASSESS_LABELS if label in labels]
    check("G3 the lines come in one fixed order, each label once, Recommendation first, and every dimension the "
          "stored facts cannot support reads 'Not established'",
          labels == order and labels[0] == "Recommendation"
          and all(lines_of(row)[k].startswith(pd.ASSESS_NOT_ESTABLISHED)
                  for k in ("Problem confirmation", "Severity and data loss", "Affected setups", "Positive outcomes")),
          str(labels))
    source = "".join(inspect.getsource(f) for f in (pd.assess, pd.assessment_lines, pd.assessment_limit_lines,
                                                    pd.independent_reports, eo.risk_assessment))
    named = [w for w in ("obs", "davinci", "windows", "acrobat", "33.0", "32.1", "comfyui") if w in source.lower()]
    check("G4 the assessment code names no product and no version", not named, str(named))
    # Review round 1, F5: the Status line names only inputs the assessment reads, and each one it names moves it.
    status = pd.ASSESS_PROVISIONAL
    base_lines = lines_of(row)
    with_finding = lines_of(one(record, population, reasons=[entry("tf", "TEST FIRST", "corroborated_issue")]))
    with_issue = lines_of(one(rec(official_notes_known_issue="declared"), population))
    life = [{"id": "life", "product_id": WIN, "kb": "KB5000002", "builds": ["26200.2000"],
             "relationship": "withdrawn_for_new_installs", "replacement_kb": "KB5000003"}]
    win = rec("25H2", pid=WIN, target_build="26200.2000", target_kb="KB5000002", update_type="2026-03 D")
    win_rows = rows(N, pid=WIN, version="25H2")
    moved = {"reports arrive or are withdrawn": one(record, population[:-1]).get("risk_assessment") is None,
             "a reviewed finding is added or removed":
                 with_finding["Problem confirmation"] != base_lines["Problem confirmation"],
             "the vendor documents a known issue": with_issue["Vendor known issues"] != base_lines["Vendor known issues"],
             "withdraws the update": (lines_of(one(win, win_rows, life=life))["Recommendation"]
                                      != lines_of(one(win, win_rows))["Recommendation"]),
             "a newer release is recorded": "newer_release" in pd.ASSESS_RELEASE}
    check("G5 the Status line promises no vendor fix (nothing reads one), and every change it does name is an input "
          "that moves the published assessment",
          " fix" not in status.lower() and all(phrase in status for phrase in moved) and all(moved.values()),
          f"{status} {moved}")


# ------------------------------------------------------------------------------------------------ [Q]

def write_record(path: Path, data: dict) -> None:
    path.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\nbody\n", encoding="utf-8")


def qa_tree(tmp: Path, record: dict, population: list[dict], *, overview_rows=None):
    tmp.mkdir(parents=True, exist_ok=True)
    gen = tmp / "gen"
    gen.mkdir(exist_ok=True)
    write_record(gen / "r0.md", record)
    (tmp / "ev.yml").write_text(yaml.safe_dump({"schema_version": 1, "evidence": list(population)}), encoding="utf-8")
    (tmp / "reasons.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    (tmp / "life.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    groups = {vr.record_identity(record): population}
    verdict = vp.project([record], groups, [], [])[0]
    (tmp / "vp.yml").write_text(vp.render(verdict), encoding="utf-8")
    built = eo.project([record], groups, verdict["pages"], [], {}, [], lifecycle=[])
    if overview_rows is not None:
        built = dict(built, pages=overview_rows(json.loads(json.dumps(built["pages"]))))
    (tmp / "eo.yml").write_text(eo.render(built), encoding="utf-8")
    return [gen / "r0.md"], tmp


QA_PATHS = ("REASONS_PATH", "LIFECYCLE_PATH", "EVIDENCE_PATH", "PROJECTION_PATH", "EVIDENCE_OVERVIEW_PATH",
            "EVIDENCE_PRESENTATION_PATH", "ROOT")


def qa_run(tree, **kw):
    files, tmp = tree
    saved = {k: getattr(qa, k) for k in QA_PATHS}
    try:
        qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH = tmp / "reasons.yml", tmp / "life.yml", tmp / "ev.yml"
        qa.PROJECTION_PATH, qa.EVIDENCE_OVERVIEW_PATH = tmp / "vp.yml", tmp / "eo.yml"
        qa.EVIDENCE_PRESENTATION_PATH, qa.ROOT = tmp / "no-presentation.yml", tmp
        errors, warnings = qa.scan_evidence_overview(files, **kw)
    finally:
        for k, v in saved.items():
            setattr(qa, k, v)
    return {e["code"] for e in errors}, {w["code"] for w in warnings}


def check_qa(tmp: Path) -> None:
    section("[Q] QA: the assessment is mandatory and names the page's own verdict")
    code = "evidence_overview_assessment_mismatch"
    record, population = rec(update_report_count=N), rows(N)

    def drop(pages):
        for row in pages.values():
            row.pop("risk_assessment", None)
        return pages

    def forge(pages):
        for row in pages.values():
            row["risk_assessment"]["result"] = "TEST FIRST"
        return pages

    def blank(pages):
        for row in pages.values():
            row["risk_assessment"]["lines"] = row["risk_assessment"]["lines"][1:]
        return pages

    ok_e, ok_w = qa_run(qa_tree(tmp / "ok", record, population), publish_strict=True)
    results = {name: qa_run(qa_tree(tmp / name, record, population, overview_rows=fn), publish_strict=True)
               for name, fn in (("drop", drop), ("forge", forge), ("blank", blank))}
    promoted, _kept = qa.promote_for_publication([], [{"code": code, "file": "x", "message": "m"}])
    check("Q1 a deploy whose page at the trigger carries its assessment is clean",
          not ok_e and code not in ok_w, f"{ok_e} {ok_w}")
    check("Q2 the same page with its assessment dropped, with one that names another verdict than the gate prints, or "
          "with no Recommendation line is reported, and --publish-strict makes it an ERROR",
          all(code in w for _e, w in results.values()) and code in qa.PUBLICATION_BLOCKING_CODES
          and [p["code"] for p in promoted] == [code], str(results))
    small = rec("1.0.0", update_report_count=3)
    donor = one(record, population)["risk_assessment"]

    def plant(pages):
        for row in pages.values():
            row["risk_assessment"] = json.loads(json.dumps(donor))
        return pages

    _e, planted = qa_run(qa_tree(tmp / "plant", small, rows(3, version="1.0.0"), overview_rows=plant),
                         publish_strict=True)
    check("Q3 an assessment on a page below the trigger is reported too", code in planted, str(planted))
    problems = eo.assessment_problems(one(record, population),
                                      vp.project([record], {vr.record_identity(record): population}, [], [])[0]
                                      ["pages"][vp.page_key(record)], N)
    check("Q4 a row the rule wrote has no problem against the verdict row it stands beside", problems == [],
          str(problems))
    # Review round 1, F4: the page that loses its volume WAIT to a row without a readable fact is NAMED.
    held = "volume_wait_withheld_report_facts"
    big = rec(update_report_count=101)
    bare = rows(101)
    bare[4] = {k: v for k, v in bare[4].items() if k not in ef.STORED_FIELDS}
    found = policy_run(qa_tree(tmp / "bare", big, bare))
    clean = policy_run(qa_tree(tmp / "clean", big, rows(101)))
    messages = [w["message"] for w in found[1] if w["code"] == held]
    check("Q5 one counted row of 101 without a readable stored fact takes the volume WAIT off the page, and QA names "
          "that page under its own code, with the numbers and the remedy; the same page with its facts is silent",
          decide(big, bare).verdict == "INSUFFICIENT DATA" and pd.facts_withheld_volume(decide(big, bare)) == 1
          and len(messages) == 1 and "1 of this page's 101 counted reports" in messages[0]
          and "migrate_evidence_facts.py --write" in messages[0]
          and held not in {w["code"] for w in clean[0] + clean[1]}, str(messages))
    other = rec(pid=UNMAINTAINED, update_report_count=101)
    other_rows = rows(101, pid=UNMAINTAINED)
    other_rows[4] = {k: v for k, v in other_rows[4].items() if k not in ef.STORED_FIELDS}
    win = rec("25H2", pid=WIN, target_build="26200.1000", target_kb="KB5000001", update_type="2026-02 B",
              update_report_count=40)
    win_rows = rows(40, pid=WIN, version="25H2")
    win_rows[4] = {k: v for k, v in win_rows[4].items() if k not in ef.STORED_FIELDS}
    _errors, kept = qa.promote_for_publication([], [{"code": held, "file": "x", "message": "m"}])
    check("Q6 it is a warning that publication mode does not promote and no error carries (the page already prints a "
          "true limit), and it is silent where the missing fact is not the one thing withholding the WAIT: another "
          "limit as well, an official classification that decides the page, or a page below the trigger",
          held not in qa.PUBLICATION_BLOCKING_CODES and [w["code"] for w in kept] == [held]
          and held not in {e["code"] for e in found[0]}
          and pd.facts_withheld_volume(decide(other, other_rows)) == 0
          and pd.facts_withheld_volume(decide(win, win_rows)) == 0
          and pd.facts_withheld_volume(decide(record, bare[:N - 1])) == 0
          and pd.facts_withheld_volume(None) == 0)


def policy_run(tree):
    """qa.scan_verdict_policy over one fixture tree, as qa.main runs it: (errors, warnings)."""
    files, tmp = tree
    saved = {k: getattr(qa, k) for k in QA_PATHS}
    try:
        qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH = tmp / "reasons.yml", tmp / "life.yml", tmp / "ev.yml"
        qa.PROJECTION_PATH, qa.ROOT = tmp / "vp.yml", tmp
        return qa.scan_verdict_policy(files)
    finally:
        for k, v in saved.items():
            setattr(qa, k, v)


# ------------------------------------------------------------------------------------------------ [L]

_INCLUDE_RB = r"""
require 'liquid'
require 'json'
module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
end
Liquid::Template.register_filter(Shims)
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
source = File.read(payload["include"], encoding: "utf-8")
out = {}
payload["cases"].each do |name, c|
  begin
    out[name] = Liquid::Template.parse(source).render!(
      { "site" => { "data" => { "evidence_overview_projection" => { "pages" => c["pages"] } } },
        "include" => { "part" => "assessment", "record" => c["record"] } })
  rescue => e
    out[name] = "<<ERR #{e.class}: #{e.message}>>"
  end
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""


def render_assessment(cases: dict) -> dict:
    ruby = shutil.which("ruby")
    if not ruby:
        return {"__error__": "ruby is not on PATH"}
    with tempfile.TemporaryDirectory() as td:
        script, payload, out = Path(td) / "i.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_INCLUDE_RB, encoding="utf-8")
        payload.write_text(json.dumps({"cases": cases, "include": str(_AUX / "_includes" /
                                                                       "patch-evidence-overview.html")}),
                           encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


def text_of(html: str) -> str:
    from html import unescape  # noqa: PLC0415
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip())


def check_liquid() -> None:
    section("[L] the shipped include")
    record, population = rec(pid=UNMAINTAINED, update_product="Example <Suite>"), rows(N, pid=UNMAINTAINED)
    pages = overview([record], {vr.record_identity(record): population})
    key = vp.page_key(record)
    headless = json.loads(json.dumps(pages))
    headless[key]["risk_assessment"]["lines"] = headless[key]["risk_assessment"]["lines"][1:]
    bare = {key: {k: v for k, v in pages[key].items() if k != "risk_assessment"}}
    out = render_assessment({"full": {"pages": pages, "record": record},
                             "headless": {"pages": headless, "record": record},
                             "bare": {"pages": bare, "record": record},
                             "none": {"pages": {}, "record": record}})
    check("L0 the liquid gem renders every case", "__error__" not in out
          and not any(str(v).startswith("<<ERR") for v in out.values()), str(out)[:300])
    full = out.get("full", "")
    text = text_of(full)
    lines = pages[key]["risk_assessment"]["lines"]
    expected = ("Provisional risk assessment: " + lines[0]["text"] + " Limiting evidence: " + lines[1]["text"]
                + " What this assessment checked "
                + " ".join(f"{line['label']}: {line['text']}" for line in lines[2:]))
    check("L1 the page prints the projection's lines, character for character and in its order: the recommendation "
          "and the limiting evidence in view, the checked dimensions folded beneath",
          text == expected and lines[1]["label"] == "Limiting evidence", f"{text!r}\n !=\n{expected!r}")
    check("L2 values are escaped, and the block is one labelled note",
          "Example &lt;Suite&gt;" in full and "<Suite>" not in full
          and full.count('aria-label="Provisional risk assessment"') == 1 and full.count("<details") == 1)
    check("L3 no assessment in the row, no row at all, or no Recommendation line first: nothing is printed (fail "
          "closed)", all(not str(out.get(k, "x")).strip() for k in ("headless", "bare", "none")),
          str({k: out.get(k) for k in ("headless", "bare", "none")})[:300])
    layout = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    check("L4 the patch layout prints the assessment once, before the newer-release note and the way forward",
          layout.count("patch-evidence-overview.html part='assessment' record=page") == 1
          and layout.index("part='assessment' record=page") < layout.index("part='newer' record=page")
          < layout.index("part='next' record=page"))


# ------------------------------------------------------------------------------------------------ [C]

def check_corpus() -> None:
    section("[C] the shipped corpus")
    records, groups = vp.load_inputs(_AUX)
    reasons, lifecycle, _problems = vp.load_fact_files(_AUX)
    verdict = vp.project(records, groups, reasons, lifecycle)[0]["pages"]
    reviewed = eo.load_reviewed(_AUX / "_data" / eo.REVIEWED_NAME)
    pages = eo.project(records, groups, verdict, reasons, reviewed, eo.split_products_from(_AUX),
                       lifecycle=lifecycle)["pages"]
    supported = vp.supported_reasons(records, groups, reasons)[0]
    at, wrong, stray, guard, disagree = [], [], [], [], []
    for record in records:
        ident, key = vr.record_identity(record), vp.page_key(record)
        counted = groups.get(ident, [])
        row = pages.get(key) or {}
        decision = pd.decide(dict(record), valid_reasons=supported.get(ident, []), lifecycle=lifecycle,
                             counted_rows=counted)
        if (decision.assessment is None) != (len(counted) < N) or (
                decision.assessment is not None and decision.assessment.result != decision.verdict):
            disagree.append(key)
        problems = eo.assessment_problems(row, vp.printed_row(record, verdict), len(counted))
        if len(counted) >= N:
            at.append(key)
            if problems or not eo.assessment_printable(row.get("risk_assessment")):
                wrong.append((key, problems))
            if eo.public_text_problems(row, counted):
                guard.append((key, eo.public_text_problems(row, counted)))
        elif "risk_assessment" in row or problems:
            stray.append(key)
    check("C1 the corpus holds pages at the trigger (the guard below is not vacuous)", len(at) >= 1, str(len(at)))
    check("C2 every page at the trigger carries a printable assessment whose result and qualifier are the verdict its "
          "gate prints", not wrong, str(wrong[:3]))
    check("C3 no page below the trigger carries one", not stray, str(stray[:3]))
    check("C4 on every record, the assessment exists exactly at the trigger and its result is the decision's verdict",
          not disagree, str(disagree[:3]))
    check("C5 every assessment row passes the public-text guard against its own counted reports", not guard,
          str(guard[:2]))
    results = {pages[key]["risk_assessment"]["result"] for key in at}
    check("C6 every assessed result on the corpus is an allowed verdict", results <= ALLOWED, str(sorted(results)))


def run() -> int:
    check_trigger()
    check_not_automatic()
    check_basis()
    check_precedence()
    check_scattered_favourable_health()
    check_release_context()
    check_guards()
    with tempfile.TemporaryDirectory(prefix="aux134-") as td:
        check_qa(Path(td))
    check_liquid()
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
