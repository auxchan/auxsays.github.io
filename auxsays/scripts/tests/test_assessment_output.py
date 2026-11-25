#!/usr/bin/env python3
"""The stored provisional assessment: the public reader of `_data/provisional_assessments.yml` (AUX-137).

The weighing of a page at the assessment trigger is computed by a separate private scheduled step that pushes ONE
output file into this repository (design B2, approved by the owner on 2026-11-25). This suite pins the PUBLIC side
with a synthetic stand-in output (no real weighing is in this repository or in this suite):

  [S] the file and entry checks: schema version, closed vocabularies, plain bounded text, tracker links only
  [F] the fingerprint: equal inputs give equal fingerprints; a change to the page's rows, its identity, another page
      of the same product, the tracker records of those rows or the reference date gives another; another product's
      page does not
  [D] the decision: no file, a stale entry and an invalid entry each give EXACTLY the count-based result plus the
      pending line; a current entry decides by its stored basis, scope and wording; official facts outrank it; an
      entry that keeps the rest of the page leaves the volume WAIT standing with the stored reason
  [Q] QA: the three output codes are warnings (never publication-blocking); a page's state is named
  [W] one writer: the shared writeback refuses the file to a lane that reaches it through a directory or glob, and
      refuses its writer any other path, in a real git round trip
  [G] the publish gate refuses compiled files, the private component's names and its reserved folders, in a built
      site and in this repository's tree
  [C] one call: `weighing_for` is called once, from `assess`; no tracked file installs a live weigher or names the
      private component; no workflow lane allows the output file
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

import yaml  # noqa: E402

import automation_writeback as wb  # noqa: E402  (a bare script in production; imported here as a module)
import qa_patch_records as qa  # noqa: E402
from ci import verify_published_payload as vpp  # noqa: E402
from lib import assessment_facts as af  # noqa: E402
from lib import assessment_output as ao  # noqa: E402
from lib import evidence_facts as ef  # noqa: E402
from lib import patch_decision as pd  # noqa: E402

N = pd.ASSESSMENT_MIN_REPORTS
PID, OTHER = "comfyui", "microsoft-teams"
VERSION = "9.8.7"
TRACKER = "github.com/example-org/example-app"
AS_OF = "2026-11-21"
COMMIT = "0" * 40

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

def vrow(i: int, *, pid: str = PID, version: str = VERSION, **over) -> dict:
    r = {"id": f"{pid}-{version}-ao-{i}", "product_id": pid, "update_version": version,
         "source_type": "github_issue", "source_url": f"https://{TRACKER}/issues/{i}",
         "report_title": f"Synthetic report {i} (AUX-137)", "report_text_excerpt": f"Synthetic report number {i}.",
         "captured_at": "2026-11-01T00:00:00Z", "source_date": "2026-10-30", "sentiment": "negative",
         "severity": "medium", "issue_theme": "unspecified issue", "counted": True, "patch_version_matched": True,
         "source_weight": 1}
    r.update(over)
    return ef.with_facts(r)


def rows(n: int, **kw) -> list[dict]:
    return [vrow(i, **kw) for i in range(1, n + 1)]


def rec(version: str = VERSION, *, pid: str = PID, **over) -> dict:
    r = {"product_id": pid, "update_version": version, "update_product": f"Product {pid}", "update_entry": True,
         "update_status": "current", "update_report_count": 0, "update_source_name": "Example Vendor",
         "update_published_at": "2026-10-01T00:00:00Z", "evidence_state": "pilot_sample",
         "permalink": f"/updates/t/{pid}/{version.replace('.', '-')}/"}
    r.update(over)
    return r


FACTS = af.DatedFacts({}, AS_OF)


class Stub:
    """A synthetic weighing with the interface the private step's result offers (no real rule)."""

    def __init__(self, verdict: str = "", basis: str = "", scope: str = "", retain: str = "",
                 page_wide: bool = False, conflicts=()) -> None:
        self.verdict, self.basis, self.scope, self.retain = verdict, basis, scope, retain
        self.page_wide = page_wide
        self.version_conflicts = list(conflicts)

    def lines(self) -> dict:
        return {"Recurring problems": "STAND-IN recurring line.", "Collection health": "STAND-IN collection line."}

    def recommendation(self, phrase: str) -> str:
        return f"{phrase}. STAND-IN recommendation."

    def body(self, n: int) -> str:
        return f"{n} accepted patch-specific problem reports. STAND-IN body."

    def retained(self) -> str:
        return "STAND-IN reason the rest of the page keeps the temporary volume-based WAIT."

    def other_setups(self) -> str:
        return ""


def stand_in(pages: list[tuple[dict, list, Stub]]) -> dict:
    """A parsed output document for these synthetic pages, fingerprinted against the current population."""
    entries = [ao.entry_from(stub, r, rs, source_facts=FACTS) for r, rs, stub in pages]
    return yaml.safe_load(ao.render(entries, rule_version="stand-in-1", generated_at="2026-11-25T00:00:00Z",
                                    source_commit=COMMIT))


def decide(record: dict, counted, *, life=(), reasons=()) -> pd.Decision:
    return pd.decide(record, valid_reasons=list(reasons), lifecycle=list(life), counted_rows=list(counted),
                     source_facts=FACTS)


def lines_of(decision: pd.Decision, record: dict) -> dict[str, str]:
    return {line["label"]: line["text"] for line in pd.assessment_lines(decision.assessment, record)}


def outcome(record: dict, counted) -> tuple:
    d = decide(record, counted)
    return (d.verdict, d.rule, d.scope, d.reason_code, d.qualifier, pd.public_body(d, record, len(counted)),
            tuple(sorted(lines_of(d, record).items())))


def with_population(*pairs) -> None:
    ao.reset()
    ao.use_population(ao.population_from(pairs))


# ------------------------------------------------------------------------------------------------ [S]

def check_schema() -> None:
    section("[S] the file and entry checks")
    r, rs = rec(), rows(N)
    with_population((r, rs))
    doc = stand_in([(r, rs, Stub("WAIT", ao.BASIS_SEVERE_REGRESSION, "until the reported regression is resolved",
                                 page_wide=True))])
    entry = doc["pages"][0]
    check("S1 a rendered stand-in file and its entry pass every check",
          ao.file_errors(doc) == [] and ao.entry_errors(entry) == [], str(ao.file_errors(doc) + ao.entry_errors(entry)))
    check("S2 another schema version, a missing header key or a wrong fingerprint rule makes the whole file unusable",
          ao.file_errors({**doc, "schema_version": 2}) != []
          and ao.file_errors({k: v for k, v in doc.items() if k != "generated_at"}) != []
          and ao.file_errors({**doc, "fingerprint_rule": "other"}) != [])
    bad = {
        "a verdict with another basis": {**entry, "verdict": "TEST FIRST"},
        "a verdict the authority may not take from it": {**entry, "verdict": "SAFE ENOUGH", "basis": ""},
        "markup in a printed text": {**entry, "body": "<script>x</script>"},
        "a line label it may not print": {**entry, "lines": {"Recommendation": "x"}},
        "a fingerprint that is not one": {**entry, "fingerprint": "sha256:abc"},
        "a conflict that is not a tracker issue": {**entry, "version_conflicts": ["https://example.com/x"]},
        "an unknown retain code": {**entry, "retain": "because"},
        "page_wide on a TEST FIRST": {**entry, "verdict": "TEST FIRST", "basis": ao.BASIS_TEST_FIRST},
        "an extra key": {**entry, "note": "x"},
    }
    refused = {name: bool(ao.entry_errors(e)) for name, e in bad.items()}
    check("S3 an entry is refused for each of: " + ", ".join(bad), all(refused.values()), str(refused))
    check("S4 every line label a stored weighing may print is one the authority prints",
          set(ao.LINE_LABELS) <= set(pd.ASSESS_LABELS) and set(ao.BASES) == set(pd.PROVISIONAL_BASES))


# ------------------------------------------------------------------------------------------------ [F]

def check_fingerprint() -> None:
    section("[F] the fingerprint")
    r, rs = rec(), rows(N)
    sibling, sib_rows = rec("9.8.6"), rows(N, version="9.8.6")
    other, other_rows = rec("1.0", pid=OTHER), rows(N, pid=OTHER, version="1.0")
    pop = ao.population_from([(r, rs), (sibling, sib_rows), (other, other_rows)])
    base = ao.fingerprint(r, rs, source_facts=FACTS, population=pop)
    changed_row = rs[:-1] + [vrow(N, report_title="Synthetic report changed")]
    variants = {
        "a row of the page": ao.fingerprint(r, changed_row, source_facts=FACTS, population=pop),
        "the page's version": ao.fingerprint(rec("9.8.8"), rs, source_facts=FACTS, population=pop),
        "another page of the product": ao.fingerprint(r, rs, source_facts=FACTS, population=ao.population_from(
            [(r, rs), (sibling, sib_rows[:-1]), (other, other_rows)])),
        "a tracker record of a row": ao.fingerprint(r, rs, source_facts=af.DatedFacts(
            {rs[0]["source_url"]: {"key": rs[0]["source_url"], "state": "closed"}}, AS_OF), population=pop),
        "the reference date": ao.fingerprint(r, rs, source_facts=af.DatedFacts({}, "2026-11-22"), population=pop),
        "the page's release date": ao.fingerprint({**r, "update_published_at": "2026-10-02T00:00:00Z"}, rs,
                                                  source_facts=FACTS, population=pop),
    }
    same = ao.fingerprint(r, [dict(x) for x in reversed(rs)], source_facts=FACTS, population=ao.population_from(
        [(r, rs), (sibling, sib_rows), (other, other_rows[:-1])]))
    check("F1 the same inputs give the same fingerprint, in any row order, and another product's pages do not enter it",
          same == base and base.startswith("sha256:"))
    check("F2 the fingerprint changes with each of: " + ", ".join(variants),
          all(v != base for v in variants.values()), str({k: v == base for k, v in variants.items()}))
    check("F3 the record fields it reads are the page identity the weighing reads, and nothing volatile",
          ao.RECORD_FIELDS == ("product_id", "update_version", "target_build", "update_product",
                               "update_published_at")
          and ao.fingerprint({**r, "update_report_count": 99, "evidence_state": "x"}, rs, source_facts=FACTS,
                             population=pop) == base)


# ------------------------------------------------------------------------------------------------ [D]

def check_decision() -> None:
    section("[D] the decision")
    r, rs = rec(), rows(N)
    ao.reset()
    ao.use(None)
    ao.use_population(ao.population_from([(r, rs)]))
    plain = outcome(r, rs)
    d0 = decide(r, rs)
    status = lines_of(d0, r).get("Status", "")
    check("D1 with no file the page gets the count-based result (the volume-based WAIT) under the count-based rule "
          "name, and its Status line says the weighing is pending",
          d0.verdict == "WAIT" and d0.volume and d0.assessment.rule == pd.ASSESSMENT_RULE
          and d0.assessment.weighing is None and status == f"{pd.ASSESS_PROVISIONAL} {pd.ASSESS_PENDING}",
          f"{d0} {status!r}")
    count_based = {"Recommendation", "Limiting evidence", "Evidence maturity", "Problem confirmation",
                   "Vendor known issues", "Severity and data loss", "Affected setups", "Positive outcomes",
                   "Release and alternatives", "Collection health", "Status"}
    printed = lines_of(d0, r)
    check("D2 without a weighing the page prints only the count-based labels and texts: no stored dimension line, and "
          "the pending sentence only in Status",
          set(printed) <= count_based and printed.get("Collection health") == pd.ASSESS_COLLECTION
          and printed.get("Severity and data loss") == pd.ASSESS_SEVERITY
          and printed.get("Positive outcomes") == pd.ASSESS_POSITIVE
          and pd.ASSESS_PENDING not in " ".join(v for k, v in printed.items() if k != "Status"), str(printed))

    wait = Stub("WAIT", ao.BASIS_SEVERE_REGRESSION, "until the reported regression is resolved", page_wide=True)
    doc = stand_in([(r, rs, wait)])
    ao.use(doc)
    d1 = decide(r, rs)
    lines = lines_of(d1, r)
    check("D3 a CURRENT stored page-wide WAIT decides the page on its stored basis and scope, with the stored wording",
          (d1.verdict, d1.scope, d1.reason_code, d1.rule) == ("WAIT", wait.scope, ao.BASIS_SEVERE_REGRESSION, "R3P")
          and d1.assessment.rule == pd.ASSESSMENT_RULE_WEIGHED
          and lines.get("Recommendation", "").endswith("STAND-IN recommendation.")
          and lines.get("Recurring problems") == "STAND-IN recurring line."
          and pd.public_body(d1, r, N).startswith(f"{N} accepted patch-specific problem reports. STAND-IN body."),
          f"{d1} {lines}")

    stale_rows = rs[:-1] + [vrow(N, report_text_excerpt="An edited excerpt.")]
    ao.use_population(ao.population_from([(r, stale_rows)]))
    ao.use(doc)
    check("D4 a STALE entry (the page's rows changed since it was computed) is not used: exactly the count-based "
          "result and the pending line",
          ao.page_state(r, stale_rows, source_facts=FACTS) == "stale"
          and outcome(r, stale_rows) == _plain(r, stale_rows), str(ao.page_state(r, stale_rows, source_facts=FACTS)))

    ao.use_population(ao.population_from([(r, rs)]))
    broken = {**doc, "pages": [{**doc["pages"][0], "basis": "maintainer_confirmed_regression", "verdict": ""}]}
    ao.use(broken)
    check("D5 an INVALID entry is not used in part: exactly the count-based result, and the file's status names it",
          ao.page_state(r, rs, source_facts=FACTS) == "invalid" and outcome(r, rs) == plain
          and ao.status()["bad"] != {}, str(ao.status()))
    ao.use({**doc, "schema_version": 99})
    check("D6 a file with another schema version is used for no page",
          ao.status()["status"] == "invalid" and outcome(r, rs) == plain)

    keep = Stub("", "", "", retain="regression_not_established")
    ao.use(stand_in([(r, rs, keep)]))
    d2 = decide(r, rs)
    check("D7 a current entry that keeps the rest of the page leaves the volume-based WAIT standing, and the limiting "
          "evidence is the stored reason",
          d2.volume and lines_of(d2, r).get("Limiting evidence") == keep.retained()
          and d2.assessment.rule == pd.ASSESSMENT_RULE_WEIGHED, str(lines_of(d2, r)))

    tf = Stub("TEST FIRST", ao.BASIS_TEST_FIRST, "before relying on this version")
    ao.use(stand_in([(r, rs, tf)]))
    d3 = decide(r, rs)
    check("D8 a current stored TEST FIRST with nothing keeping the rest of the page decides TEST FIRST (R4P)",
          (d3.verdict, d3.rule, d3.reason_code) == ("TEST FIRST", "R4P", ao.BASIS_TEST_FIRST), str(d3))

    withdrawn = rec(target_kb="KB5000001", target_build="9.8.7.1")
    with_population((withdrawn, rs))
    ao.use(stand_in([(withdrawn, rs, wait)]))
    life = [{"id": "w1", "product_id": PID, "kb": "KB5000001", "relationship": "withdrawn_for_new_installs",
             "builds": ["9.8.7.1"], "verified_at": "2026-11-01", "replacement_kb": "KB5000002"}]
    stored_current = ao.page_state(withdrawn, rs, source_facts=FACTS) == "current"
    d4 = decide(withdrawn, rs, life=life)
    check("D9 an official withdrawal outranks a current stored WAIT", stored_current and d4.verdict == "AVOID",
          f"{stored_current} {d4}")
    check_wider_result()
    ao.reset()


def _reviewed(verdict: str, scope: str) -> dict:
    return {"id": "rv", "product_id": PID, "update_version": VERSION, "verdict": verdict, "reason_class":
            "regression" if verdict == "WAIT" else "corroborated_report", "scope": scope,
            "reason": "Two users report the reviewed problem.", "new_in_this_version": verdict == "WAIT"}


def check_wider_result() -> None:
    """REVIEW3 F2: an equally cautious stored result that covers EVERY setup is wider than a reviewed finding scoped to
    one; the page keeps the wider one, and the reviewed finding is printed beneath it, never the other way round."""
    r, rs = rec(), rows(N)
    with_population((r, rs))
    reviewed_wait = _reviewed("WAIT", "if you use connected accounts on macOS")
    wide = Stub("WAIT", ao.BASIS_SEVERE_REGRESSION, "until the reported regression is resolved", page_wide=True)
    ao.use(stand_in([(r, rs, wide)]))
    d = decide(r, rs, reasons=[reviewed_wait])
    body, rec_line = pd.public_body(d, r, N), lines_of(d, r).get("Recommendation", "")
    check("D10 (REVIEW3 F2) a stored page-wide WAIT beside a reviewed WAIT scoped to one setup keeps the page-wide WAIT "
          "(R3P, its stored scope); the reviewed finding is printed beneath it, and no line says the assessment "
          "supports nothing more cautious",
          (d.verdict, d.rule, d.scope, d.reason_code) == ("WAIT", "R3P", wide.scope, ao.BASIS_SEVERE_REGRESSION)
          and f"Also WAIT {reviewed_wait['scope']}: " in body and "nothing more cautious" not in rec_line + body,
          f"{d} {rec_line[:160]}")
    everyone = Stub("TEST FIRST", ao.BASIS_TEST_FIRST, "before relying on this version")
    ao.use(stand_in([(r, rs, everyone)]))
    d_tf = decide(r, rs, reasons=[_reviewed("TEST FIRST", "when installing it")])
    check("D11 (REVIEW3 F2) the same for TEST FIRST: a stored TEST FIRST for every setup beside a reviewed TEST FIRST "
          "scoped to installing it keeps the wider one, with the reviewed finding beneath",
          (d_tf.verdict, d_tf.rule, d_tf.scope) == ("TEST FIRST", "R4P", everyone.scope)
          and "Also TEST FIRST when installing it: " in pd.public_body(d_tf, r, N), str(d_tf))
    scoped = Stub("WAIT", ao.BASIS_SEVERE_REGRESSION, "if you use Windows")
    ao.use(stand_in([(r, rs, scoped)]))
    d_sc = decide(r, rs, reasons=[reviewed_wait])
    sc_line = lines_of(d_sc, r).get("Recommendation", "")
    ao.use(stand_in([(r, rs, everyone)]))
    d_less = decide(r, rs, reasons=[reviewed_wait])
    less_line = lines_of(d_less, r).get("Recommendation", "")
    check("D12 (REVIEW3 F2) an equally cautious stored WAIT scoped to ANOTHER setup is not dropped either: it takes the "
          "page and the reviewed finding is printed beneath it (neither line claims the other supports nothing more "
          "cautious); a reviewed finding keeps the page only beside a LESS cautious stored result, and then says so",
          (d_sc.verdict, d_sc.scope, d_sc.rule) == ("WAIT", "if you use Windows", "R3P")
          and f"Also WAIT {reviewed_wait['scope']}: " in pd.public_body(d_sc, r, N)
          and "nothing more cautious" not in sc_line
          and (d_less.verdict, d_less.scope, d_less.assessment.basis) == ("WAIT", reviewed_wait["scope"],
                                                                         pd.BASIS_REVIEWED_WEIGHED)
          and "supports nothing more cautious" in less_line, f"{d_sc} {sc_line[:120]} || {less_line[:200]}")
    # The reader refuses a stored entry whose page-wide flag contradicts its scope (the private writer's contract).
    entry = stand_in([(r, rs, wide)])["pages"][0]
    check("D13 (REVIEW3 F2) a WAIT entry whose page-wide flag contradicts its scope is refused: marked page-wide with a "
          "setup named, or not page-wide with none",
          ao.entry_errors({**entry, "scope": "if you use Windows"}) != [] and ao.entry_errors(entry) == []
          and ao.entry_errors({**entry, "page_wide": False}) != [],
          str(ao.entry_errors({**entry, "scope": "if you use Windows"})))


def _plain(record: dict, counted) -> tuple:
    """The outcome with no stored file at all, over the same population."""
    saved = ao._STATE.get("override", ao.OUTPUT_PATH)  # noqa: SLF001
    ao.use(None)
    try:
        return outcome(record, counted)
    finally:
        ao.use(saved)


# ------------------------------------------------------------------------------------------------ [Q]

def check_qa() -> None:
    section("[Q] QA")
    codes = {"assessment_output_invalid", "assessment_output_missing", "assessment_output_stale",
             "report_source_facts_aging"}
    source = (SCRIPTS / "qa_patch_records.py").read_text(encoding="utf-8")
    check("Q1 the output codes and the facts-aging code are warnings that never block a deploy; the stale-records "
          "code still does where a stored weighing reads the records",
          not codes & qa.PUBLICATION_BLOCKING_CODES and "report_source_facts_stale" in qa.PUBLICATION_BLOCKING_CODES
          and all(c in source or c.rsplit("_", 1)[0] in source for c in codes))
    r, rs = rec(), rows(N)
    with_population((r, rs))
    ao.use(None)
    missing = ao.page_state(r, rs, source_facts=FACTS)
    ao.use(stand_in([(r, rs, Stub(retain="collection_stale"))]))
    current = ao.page_state(r, rs, source_facts=FACTS)
    stale = ao.page_state(r, rs[:-1] + [vrow(N, source_date="2026-10-31")], source_facts=FACTS)
    check("Q2 a page's state is missing, current or stale exactly as its file and inputs are",
          (missing, current, stale) == ("missing", "current", "stale"), str((missing, current, stale)))
    ao.reset()


# ------------------------------------------------------------------------------------------------ [W]

def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def check_single_writer(tmp: Path) -> None:
    section("[W] one writer")
    path = ao.OUTPUT_RELPATH
    check("W1 the shared writeback names the output file as single-writer, and it is the reader's own path",
          wb.SINGLE_WRITER_PATHS == (path,) and str(ao.OUTPUT_PATH).replace("\\", "/").endswith(path))
    origin = tmp / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    seed = tmp / "seed"
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True, capture_output=True)
    git(seed, "config", "user.name", "t")
    git(seed, "config", "user.email", "t@example.invalid")
    (seed / "auxsays" / "_data").mkdir(parents=True)
    (seed / "auxsays" / "_data" / "other.yml").write_text("a: 1\n", encoding="utf-8")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "seed")
    git(seed, "push", "-q", "origin", "HEAD:main")

    def attempt(name: str, allow: list[str], files: dict[str, str]) -> wb.WritebackResult:
        clone = tmp / name
        subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True, capture_output=True)
        for rel, text in files.items():
            (clone / rel).parent.mkdir(parents=True, exist_ok=True)
            (clone / rel).write_text(text, encoding="utf-8")
        cfg = wb.WritebackConfig(repo=clone, message="test", allow=allow, pages_cmd="true",
                                 pages_backoff=[0], sleep_fn=lambda _s: None)
        return wb.run_writeback(cfg)

    lane = attempt("lane", ["auxsays/_data"], {path: "x: 1\n"})
    globbed = attempt("glob", ["auxsays/_data/*.yml"], {path: "x: 1\n"})
    mixed = attempt("mixed", [path, "auxsays/_data/other.yml"], {path: "x: 1\n", "auxsays/_data/other.yml": "a: 2\n"})
    writer = attempt("writer", [path], {path: "x: 1\n"})
    others = attempt("others", ["auxsays/_data"], {"auxsays/_data/other.yml": "a: 3\n"})
    check("W2 a lane that reaches the file through a directory or a glob is refused and pushes nothing",
          (lane.outcome, lane.pushed, globbed.outcome, globbed.pushed)
          == (wb.UNEXPECTED_CHANGED_PATH, False, wb.UNEXPECTED_CHANGED_PATH, False),
          str((lane.outcome, globbed.outcome)))
    check("W3 its writer, naming it exactly, may not carry any other path beside it",
          (mixed.outcome, mixed.pushed, mixed.conflicting_paths)
          == (wb.UNEXPECTED_CHANGED_PATH, False, ["auxsays/_data/other.yml"]), str(mixed.as_dict()))
    check("W4 its writer, naming it exactly and carrying it alone, pushes it; a lane writing other files is unaffected",
          writer.pushed and writer.ok and others.pushed and others.ok, str((writer.outcome, others.outcome)))


# ------------------------------------------------------------------------------------------------ [G]

def check_publish_gate(tmp: Path) -> None:
    section("[G] the publish gate")
    site = tmp / "_site"
    for rel in ("index.html", "assets/x.css", "lib/provisional_assessment.cpython-312.pyc", "lib/native.so",
                "x/private_assessment/notes.txt", "fixtures/provisional_history/pages.json",
                "test_provisional_assessment.txt", "data/provisional_assessments.json"):
        (site / rel).parent.mkdir(parents=True, exist_ok=True)
        (site / rel).write_text("x", encoding="utf-8")
    flagged = sorted(r for r, _ in vpp.findings_for(site))
    check("G1 a built site carrying compiled files or the private component's names or folders is refused, and the "
          "public output's own name is not",
          flagged == ["fixtures/provisional_history/pages.json", "lib/native.so",
                      "lib/provisional_assessment.cpython-312.pyc", "test_provisional_assessment.txt",
                      "x/private_assessment/notes.txt"], str(flagged))
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True,
                             check=True).stdout.splitlines()
    check("G2 this repository's tree holds none of the private component's files or folders",
          len(tracked) > 100 and vpp.private_component_findings(tracked) == [],
          str(vpp.private_component_findings(tracked)[:5]))


# ------------------------------------------------------------------------------------------------ [C]

def check_one_call() -> None:
    section("[C] one call")
    code = re.sub(r"#[^\n]*", "", (SCRIPTS / "lib" / "patch_decision.py").read_text(encoding="utf-8"))
    production = [p for p in SCRIPTS.rglob("*.py") if "tests" not in p.relative_to(SCRIPTS).parts]
    readers = sorted(p.name for p in production
                     if p.name != "assessment_output.py" and "weighing_for(" in p.read_text(encoding="utf-8"))
    check("C1 the decision authority calls the reader once, from `assess`, and nothing else calls it",
          code.count("assessment_output.weighing_for(") == 1 and readers == ["patch_decision.py"], str(readers))
    installers = sorted(p.name for p in production
                        if p.name != "assessment_output.py" and "install_weigher(" in p.read_text(encoding="utf-8"))
    check("C2 no production file of this repository installs a live weigher (only the private step does)",
          installers == [],
          str(installers))
    workflows = {p.name: p.read_text(encoding="utf-8") for p in (REPO / ".github" / "workflows").glob("*.y*ml")}
    naming = sorted(n for n, t in workflows.items() if ao.OUTPUT_NAME in t)
    check("C3 no workflow of this repository names the output file (its one writer is outside it)", naming == [],
          str(naming))
    shipped = ao.OUTPUT_PATH
    ok = True
    if shipped.is_file():
        doc = yaml.load(shipped.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
        ok = ao.file_errors(doc) == [] and all(ao.entry_errors(e) == [] for e in doc["pages"])
    check("C4 the shipped output file, where present, passes every check (absent is the safe state)", ok)


def run() -> int:
    try:
        check_schema()
        check_fingerprint()
        check_decision()
        check_qa()
        with tempfile.TemporaryDirectory(prefix="aux137-") as td:
            check_single_writer(Path(td))
        with tempfile.TemporaryDirectory(prefix="aux137-") as td:
            check_publish_gate(Path(td))
        check_one_call()
    finally:
        ao.reset()
    print("\n" + "=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    for f in FAILURES:
        print(f"  failed: {f}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
