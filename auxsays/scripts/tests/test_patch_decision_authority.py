#!/usr/bin/env python3
"""A patch publishes ONE install decision. Two generators may not each choose one.

THE DEFECT (live on main fef76436). `2026-04-14-davinci-resolve-21-public-beta-1.md` published

    update_decision_label:    "WAIT for production systems"          -> "AUXSAYS verdict", detail page
    quick_verdict:            "WAIT for production systems: ..."
    update_consensus_summary: "AVOID for production: DaVinci ..."    -> "Evidence summary", patch feed

on one record, from one writer, in one run. Both reached readers: aux-update.html renders the
verdict, aux-updates.html renders the summary. A reader on the feed was told to avoid the build; a
reader on the page was told to wait for production systems and that testing it is fine.

It was never one record. Measured over the corpus, ten carried more than one distinct decision
phrase: eight OBS records said "TEST FIRST" in the verdict and "WAIT" in the summary, the DaVinci
beta said WAIT against AVOID, and hand-authored Premiere 26.2 says "WAIT for production systems"
against "WAIT".

THE CAUSE was structural, not textual. `_record_coherence_fields` chose the verdict from product
policy; `_public_summary` called `_recommendation_prefix`, which chose again from sentiment, with
its own copy of the beta rule; `build_consensus_from_evidence.recommendation_prefix` was a third
copy. Three implementations of one policy are three chances to disagree.

WHAT THIS SUITE PINS. [W] every decision-bearing field descends from `lib.patch_decision` -- proven
by substituting the authority and watching the substitution surface in the verdict, the label AND
the summary, which a grep for the function name cannot do. [M] over the product/sentiment/state
matrix the three fields never name different actions. [P] the decisions themselves are the ones the
deterministic policy already produced, pinned literally, so "make it coherent" cannot quietly become
"make it lenient". [Q] nuance survives as a QUALIFICATION: the beta still tells production editors
to avoid it on active projects, in prose that carries no second verdict. [R] a record whose stored
prose already contradicts its verdict is repaired by ordinary regeneration, with no hand edit. [N]
the run after that writes nothing. [X] five mutants, each restoring one half of the old design,
must each be caught by a NAMED check -- a crash or an import error does not count as a catch.

Deterministic and offline: no network, no git, writes only inside a temp dir.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_decision_authority.py
"""
from __future__ import annotations

import contextlib
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
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

NEWLINE = chr(10)

import apply_consensus_to_records as acr  # noqa: E402
import build_consensus_from_evidence as bce  # noqa: E402
import collect_obs_reports as obs_collector  # noqa: E402
import qa_patch_records as qa  # noqa: E402
from collections import Counter  # noqa: E402
from lib import patch_decision  # noqa: E402
from patch_collectors import adobe_premiere as premiere_collector  # noqa: E402
from patch_collectors import davinci as davinci_collector  # noqa: E402

DAV = "blackmagic-davinci"
OBS = "obs-studio"
WIN = "microsoft-windows-11"
PREM = "adobe-premiere-pro"
ACRO = "adobe-acrobat-pro"
NEWLINE = "\n"

PRODUCT_LABEL = {
    DAV: "DaVinci Resolve",
    OBS: "OBS Studio",
    WIN: "Windows 11",
    PREM: "Premiere Pro",
    ACRO: "Acrobat Pro",
}

# A path that does not exist, so `_public_source_limitations` adds no method-health block and the
# generated prose is a function of the arguments alone.
NO_METHOD_HEALTH = Path(__file__).with_name("no-such-method-health.yml")

# Fields a reader could mistake for a decision if one hid a verdict in them.
PROSE_FIELDS = ("update_decision_body", "consensus_report", "source_freshness_note",
                "official_summary", "release_summary", "description")

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
    """Run checks without scoring them, and collect the labels that FAILED.

    The mutation section needs to know which named check notices a mutant. Re-running the real
    check functions is the only honest way to answer that: a mutant that merely makes the suite
    explode has not been caught by anything.
    """
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


# ---------------------------------------------------------------- generation helpers

def evidence_row(pid: str, version: str, n: int, *, sentiment: str = "negative") -> dict:
    """One row shaped like the live corpus, passing every gate in acr._filter_rows."""
    return {
        "id": f"{pid}-{version}-row-{n}",
        "product_id": pid,
        "update_version": version,
        "source_type": "community_forum",
        "source_name": "Community Forum",
        "source_url": f"https://forum.example.invalid/{pid}/{version}/{n}",
        "report_title": f"{version} issue {n}",
        "report_text_excerpt": f"User-verified report describing an issue on {version}.",
        "captured_at": "2026-09-01T00:00:00Z",
        "patch_version_matched": True,
        "matched_version": version,
        "counted": True,
        "issue_theme": "playback_stutter",
        "severity": "high",
        "sentiment": sentiment,
        "source_weight": 1,
    }


def proposed(pid: str, version: str, *, sentiment: str = "negative", count: int = 15,
             status: str = "current", build: str = "") -> dict:
    """The fields the real writer would put on this record, with no temp tree needed."""
    rows = [evidence_row(pid, version, i, sentiment=sentiment) for i in range(count)]
    record = {
        "update_product": PRODUCT_LABEL.get(pid, pid),
        "update_status": status,
        "path": f"updates/generated/{pid}-{version}.md",
    }
    saved = acr.METHOD_HEALTH_PATH
    acr.METHOD_HEALTH_PATH = NO_METHOD_HEALTH
    try:
        return acr._proposed_record_fields(pid, version, rows, record,
                                           "2026-09-01T00:00:00Z", build=build)
    finally:
        acr.METHOD_HEALTH_PATH = saved


def leading_decision(text: object) -> str:
    """The decision phrase a reader sees. The SHIPPED predicate, not a copy of it.

    This suite used to carry its own longest-match implementation. Two implementations of "what
    does this field say" is the same shape of defect the suite exists to prevent, one level up.
    """
    return patch_decision.leading_decision(text)


def embedded_decisions(text: object) -> set[str]:
    """Decision phrases used ANYWHERE in a string in verdict form (`PHRASE:`)."""
    body = str(text or "")
    found = set()
    for phrase in patch_decision.DECISIONS:
        if phrase + ":" in body:
            found.add(phrase)
    return found


def decisions_named(fields: dict) -> set[str]:
    """Every distinct action this record names, across verdict, label and summary."""
    names = {
        str(fields.get("update_decision_label") or "").strip(),
        leading_decision(fields.get("quick_verdict")),
        leading_decision(fields.get("update_consensus_summary")),
    }
    return {n for n in names if n}


def without_leading_decision(text: object) -> str:
    """A decision-bearing field with its ONE legitimate verdict prefix removed.

    The qualification a reader actually receives -- "Production editors should avoid it on active
    projects" -- is a sentence of the summary, not of the decision body. So the summary has to be
    scanned for nuance and for smuggled second verdicts alike; only its opening prefix is exempt.
    """
    body = str(text or "")
    phrase = leading_decision(body)
    return body[len(phrase) + 1:].strip() if phrase else body


def prose_blob(fields: dict) -> str:
    parts = [str(fields.get(f) or "") for f in PROSE_FIELDS]
    parts.extend(str(x) for x in (fields.get("practical_recommendations") or []))
    parts.append(without_leading_decision(fields.get("update_consensus_summary")))
    parts.append(without_leading_decision(fields.get("quick_verdict")))
    return " ".join(parts)


def write_record(path: Path, *, pid: str, version: str, count: int, verdict: str,
                 summary_prefix: str, status: str = "current") -> None:
    """A stored record whose prose may deliberately disagree with its verdict."""
    label = PRODUCT_LABEL.get(pid, pid)
    data = {
        "layout": "aux-update", "update_entry": True,
        "product_id": pid, "update_version": version, "update_product": label,
        "update_status": status,
        "update_report_count": count, "confirmed_patch_specific_report_count": count,
        "accepted_report_sources": [{"source": f"s{i}", "source_url": f"https://x.invalid/{i}"}
                                    for i in range(count)],
        "evidence_samples": [{"source": "s0"}],
        "update_decision_label": verdict,
        "quick_verdict": f"{verdict}: {label} {version} has {count} user reports found.",
        "update_consensus_summary": (f"{summary_prefix}: {label} {version} has {count} user "
                                     "reports found."),
        "consensus_report": f"{count} user reports found for {label} {version}.",
    }
    path.write_text("---" + NEWLINE + yaml.safe_dump(data, sort_keys=False) + "---" + NEWLINE
                    + "body" + NEWLINE, encoding="utf-8")


def front_matter(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def write_evidence(path: Path, rows: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "evidence": rows}, sort_keys=False),
                    encoding="utf-8")


def promote(tree: Path, evidence: Path, product: str) -> int:
    """Run the REAL promotion against a temp tree by pointing the module's paths at it."""
    saved = (acr.ROOT, acr.GENERATED_DIR, acr.DEFAULT_EVIDENCE_PATH, acr.METHOD_HEALTH_PATH)
    acr.ROOT = tree.parents[1]
    acr.GENERATED_DIR = tree
    acr.DEFAULT_EVIDENCE_PATH = evidence
    acr.METHOD_HEALTH_PATH = tree / "no-method-health.yml"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return acr.main(["--product-id", product, "--write-all", "--confirm-write"])
    finally:
        acr.ROOT, acr.GENERATED_DIR, acr.DEFAULT_EVIDENCE_PATH, acr.METHOD_HEALTH_PATH = saved


# ---------------------------------------------------------------- [W] one authority

def check_wiring() -> None:
    """Substitute the authority; every decision-bearing field must change with it.

    This is the duplicated-authority detector. A call site that kept its own policy would keep
    producing its own word while the others moved, so the sentinel would be missing from exactly
    the field that had stopped listening. Grepping for `patch_decision` proves only that the name
    appears somewhere in the file.
    """
    sentinel = "MANUAL WATCH"          # a real decision, so nothing downstream rejects it as junk
    original = patch_decision.decision_label
    patch_decision.decision_label = lambda *a, **k: sentinel
    try:
        fields = proposed(DAV, "21 Public Beta 1")
        check("W1 the summary prefix follows the substituted authority",
              leading_decision(fields.get("update_consensus_summary")) == sentinel,
              repr(str(fields.get("update_consensus_summary"))[:90]))
        check("W2 the quick_verdict follows the substituted authority",
              leading_decision(fields.get("quick_verdict")) == sentinel,
              repr(str(fields.get("quick_verdict"))[:90]))
        check("W3 the update_decision_label follows the substituted authority",
              str(fields.get("update_decision_label")) == sentinel,
              repr(fields.get("update_decision_label")))
        check("W4 build_consensus_from_evidence follows the substituted authority",
              bce.recommendation_prefix(DAV, "21 Public Beta 1", "negative", 15) == sentinel,
              repr(bce.recommendation_prefix(DAV, "21 Public Beta 1", "negative", 15)))
        check("W5 the consensus_status summary follows it too",
              leading_decision(bce.consensus_summary(
                  DAV, "21 Public Beta 1",
                  [evidence_row(DAV, "21 Public Beta 1", i) for i in range(15)],
                  bce.Counter({"negative": 15}), bce.Counter({"playback_stutter": 15}))) == sentinel)
    finally:
        patch_decision.decision_label = original

    # And the beta rule itself is single-sourced: both former copies now answer from one definition.
    beta_re_original = patch_decision._BETA_RE
    patch_decision._BETA_RE = __import__("re").compile(r"NEVERMATCHESANYTHING")
    try:
        check("W6 both former beta rules read the one shared definition",
              not acr._davinci_version_is_beta("21 Public Beta 1")
              and not bce.version_is_beta("21 Public Beta 1"))
    finally:
        patch_decision._BETA_RE = beta_re_original

    # The product ids in the authority are literals, so that `lib` stays a leaf. Pin every one of
    # them against its canonical constant: a duplicated identity that nothing compares is a rename
    # away from a policy that silently stops applying. Windows alone was not enough -- renaming
    # PREMIERE was caught by nothing, because the Premiere branch and the sentiment fallback agree
    # on the only sentiment the tables fed it.
    canonical = {
        "DAVINCI": (patch_decision.DAVINCI, davinci_collector.PRODUCT_ID),
        "OBS": (patch_decision.OBS, obs_collector.PRODUCT_ID),
        "WINDOWS": (patch_decision.WINDOWS, acr.WINDOWS_PRODUCT_ID),
        "PREMIERE": (patch_decision.PREMIERE, premiere_collector.PRODUCT_ID),
    }
    drifted = [f"{name}: {mine!r} != {theirs!r}" for name, (mine, theirs) in canonical.items()
               if mine != theirs]
    check(f"W7 all {len(canonical)} product ids match the repo's canonical ids",
          not drifted, "; ".join(drifted))

    # The decision is computed ONCE per record and handed to both writers. Counting the calls is
    # what pins that: two calls could judge different version strings -- the summary path used to
    # read `patch_display_label(...)` while the verdict read the raw version -- and a suite whose
    # fixtures all have an empty build would never see the difference in the output.
    original = patch_decision.decision_label
    calls = []

    def counting(*a, **k):
        calls.append((a, tuple(sorted(k))))
        return original(*a, **k)

    patch_decision.decision_label = counting
    try:
        proposed(WIN, "25H2", build="26200.1234")
    finally:
        patch_decision.decision_label = original
    check("W8 one record asks the authority exactly once",
          len(calls) == 1, f"{len(calls)} calls: {calls}")

    # THE TWO WRITERS MUST AGREE, which is this check's job and why it predates AUX-029. The record
    # writer reads the record; build_consensus never loaded records at all, so when OBS still keyed
    # its decision on `update_status` the aggregate answered TEST FIRST for the one live archived
    # build (32.1.1, 43 reports) while the record said WAIT.
    #
    # AUX-007 removed the record-state input, so this now pins something STRONGER: the two writers
    # agree AND both answer the same whichever way `update_status` is set. The sentiment is
    # negative, so the evidence-driven answer is WAIT for both.
    pairs = []
    answers = set()
    for status in ("archived", "current"):
        writer = proposed(OBS, "32.1.1", sentiment="negative", count=43, status=status)
        aggregate = bce.recommendation_prefix(OBS, "32.1.1", "negative", 43, update_status=status)
        answers |= decisions_named(writer) | {aggregate}
        if not (decisions_named(writer) == {"WAIT"} and aggregate == "WAIT"):
            pairs.append(f"{status}: record={sorted(decisions_named(writer))} "
                         f"aggregate={aggregate!r} expected='WAIT'")
    if len(answers) != 1:
        pairs.append(f"update_status changed the decision: {sorted(answers)}")
    check("W10 both writers agree, and update_status does not change the decision",
          not pairs, "; ".join(pairs))

    # A product with no verdict branch publishes no verdict field, so the `decision=None` fallback
    # in _record_coherence_fields cannot reach a reader whatever it computes.
    branchless = acr._record_coherence_fields(ACRO, "25.001.20800", 15,
                                              {"update_product": "Acrobat Pro"}, Counter())
    check("W9 a branchless product writes no verdict field at all",
          branchless == {}, repr(branchless)[:120])


# ---------------------------------------------------------------- [M] matrix coherence

MATRIX = [
    # (pid, version, sentiment, status, human description)
    (DAV, "21 Public Beta 1", "negative", "current", "DaVinci public beta, negative"),
    (DAV, "21 Public Beta 1", "moderate", "current", "DaVinci public beta, moderate"),
    (DAV, "21 Public Beta 1", "positive", "current", "DaVinci public beta, positive"),
    (DAV, "21", "negative", "current", "DaVinci stable, negative"),
    (DAV, "20.2", "positive", "current", "DaVinci stable, positive"),
    (OBS, "31.2.1", "negative", "current", "OBS maintained, negative"),
    (OBS, "30.0.0", "negative", "archived", "OBS archived, negative"),
    (OBS, "31.2.1", "positive", "current", "OBS maintained, positive"),
    (OBS, "31.2.1", "positive", "archived", "OBS archived, positive"),
    (OBS, "31.2.1", "moderate", "archived", "OBS archived, moderate"),
    (WIN, "25H2", "negative", "current", "Windows, negative"),
    (WIN, "25H2", "positive", "current", "Windows, positive"),
    (PREM, "26.2", "negative", "current", "Premiere, negative"),
    (ACRO, "25.001.20800", "negative", "current", "Acrobat, negative"),
    (ACRO, "25.001.20800", "positive", "current", "Acrobat, positive"),
    (ACRO, "25.001.20800", "moderate", "current", "Acrobat, moderate"),
]


def check_matrix() -> None:
    incoherent = []
    off_vocabulary = []
    for pid, version, sentiment, status, label in MATRIX:
        fields = proposed(pid, version, sentiment=sentiment, status=status)
        names = decisions_named(fields)
        if len(names) > 1:
            incoherent.append(f"{label}: {sorted(names)}")
        off = names - patch_decision.DECISIONS
        if off:
            off_vocabulary.append(f"{label}: {sorted(off)}")
    check(f"M1 no record in the matrix names two actions ({len(MATRIX)} cases)",
          not incoherent, "; ".join(incoherent[:4]))
    check("M2 every action named is in the decision vocabulary",
          not off_vocabulary, "; ".join(off_vocabulary[:4]))

    # Zero evidence is its own decision and must also be single-voiced.
    empty = proposed(ACRO, "25.001.20800", count=0)
    check("M3 a zero-evidence record says INSUFFICIENT DATA and nothing else",
          decisions_named(empty) <= {patch_decision.INSUFFICIENT_DATA},
          repr(sorted(decisions_named(empty))))

    # A record with NO coherence branch still gets its summary from the canonical authority, so a
    # product cannot re-acquire a private policy by simply not having a branch.
    acro = proposed(ACRO, "25.001.20800", sentiment="negative")
    check("M4 a branchless product's summary still comes from the canonical authority",
          leading_decision(acro.get("update_consensus_summary"))
          == patch_decision.decision_label(ACRO, "25.001.20800", "Negative", 15))


# ---------------------------------------------------------------- [P] the decisions themselves

# The decision each case produced under the deterministic policy already in force, pinned so that
# "make the two fields agree" can never drift into "make the recommendation friendlier". Every
# entry here is the word the READER-FACING VERDICT published before this change; the summary is what
# moved to meet it.
POLICY = [
    # DaVinci: the beta and the stable build name the same ACTION. The label was
    # "WAIT for production systems" until AUX-029; that phrasing is a legacy alias now, and the
    # production-systems half is a qualification the prose still states.
    (DAV, "21 Public Beta 1", "negative", "current", "WAIT"),
    (DAV, "21 Public Beta 1", "positive", "current", "WAIT"),
    (DAV, "21", "negative", "current", "WAIT"),
    (DAV, "20.2", "positive", "current", "WAIT"),
    # OBS IS EVIDENCE-DRIVEN (AUX-007). It used to read `update_status`: maintained -> TEST FIRST,
    # archived -> WAIT, which let a positional metadata field outrank the community consensus. The
    # archived row below is UNCHANGED in outcome and that is the point -- the old rule happened to
    # agree with the evidence there, which is how it passed for as long as it did.
    (OBS, "31.2.1", "negative", "current", "WAIT"),
    (OBS, "30.0.0", "negative", "archived", "WAIT"),
    (OBS, "31.2.1", "positive", "current", "SAFE ENOUGH"),
    (OBS, "31.2.1", "moderate", "current", "TEST FIRST"),
    # The same three sentiments with the status flipped. These are the rows that FAIL if
    # `update_status` is ever wired back into the decision.
    (OBS, "31.2.1", "negative", "archived", "WAIT"),
    (OBS, "31.2.1", "positive", "archived", "SAFE ENOUGH"),
    (OBS, "31.2.1", "moderate", "archived", "TEST FIRST"),
    (WIN, "25H2", "negative", "current", "WAIT"),
    # The positive rows are the ones that prove these branches EXIST. On negative sentiment the
    # Windows and Premiere branches and the sentiment fallback both answer "WAIT", so deleting
    # either branch was previously caught by nothing.
    (WIN, "25H2", "positive", "current", "WAIT"),
    (PREM, "26.2", "negative", "current", "WAIT"),
    (PREM, "26.2", "positive", "current", "WAIT"),
    (PREM, "26.2", "moderate", "current", "WAIT"),
    (ACRO, "25.001.20800", "negative", "current", "WAIT"),
    (ACRO, "25.001.20800", "positive", "current", "SAFE ENOUGH"),
    (ACRO, "25.001.20800", "moderate", "current", "TEST FIRST"),
]


def check_policy() -> None:
    drifted = []
    for pid, version, sentiment, status, expected in POLICY:
        fields = proposed(pid, version, sentiment=sentiment, status=status)
        names = decisions_named(fields)
        if names != {expected}:
            drifted.append(f"{pid} {version} {sentiment}: {sorted(names)} != {expected!r}")
    check(f"P1 every case still decides what the policy decided ({len(POLICY)} cases)",
          not drifted, "; ".join(drifted[:4]))

    # The public beta specifically: the field readers see on the feed used to say AVOID.
    beta = proposed(DAV, "21 Public Beta 1")
    check("P2 the public beta's summary no longer opens with AVOID",
          leading_decision(beta.get("update_consensus_summary")) != "AVOID for production",
          repr(str(beta.get("update_consensus_summary"))[:110]))
    check("P3 the public beta decides one canonical action, everywhere",
          decisions_named(beta) == {"WAIT"},
          repr(sorted(decisions_named(beta))))
    check("P3b and that action is canonical, not the legacy phrasing",
          patch_decision.is_canonical("WAIT")
          and "WAIT for production systems" not in decisions_named(beta),
          repr(sorted(decisions_named(beta))))

    # A beta of a product with no DaVinci-style beta rule is not silently swept into one.
    #
    # POSITIVE sentiment on purpose. This case used negative sentiment, and after AUX-007 made OBS
    # evidence-driven both policies answer WAIT there -- the check would have passed while proving
    # nothing. On positive sentiment they genuinely differ: OBS says SAFE ENOUGH, the DaVinci beta
    # rule says WAIT. So if that rule ever leaked into OBS, this fails.
    obs_beta = proposed(OBS, "31.2.1 beta", sentiment="positive")
    dav_beta = proposed(DAV, "21 Public Beta 1", sentiment="positive")
    check("P4 a beta version of another product keeps that product's own decision",
          decisions_named(obs_beta) == {"SAFE ENOUGH"}, repr(sorted(decisions_named(obs_beta))))
    check("P4b and the case discriminates: the two products answer differently here",
          decisions_named(obs_beta) != decisions_named(dav_beta),
          f"obs={sorted(decisions_named(obs_beta))} davinci={sorted(decisions_named(dav_beta))}")

    # ZERO EVIDENCE. An official-source-only record must not drift into an invitation to
    # install. The authority answers INSUFFICIENT DATA at count 0 BEFORE any product or
    # sentiment branch is consulted, so a positive label cannot turn it into SAFE ENOUGH.
    for sentiment in ("negative", "moderate", "positive"):
        for status in ("current", "archived"):
            zero = patch_decision.decision_label(
                OBS, "31.2.1", sentiment, 0, record={"update_status": status})
            check(f"P5 OBS at zero reports is INSUFFICIENT DATA ({sentiment}/{status})",
                  zero == patch_decision.INSUFFICIENT_DATA, repr(zero))
            check(f"P5b and never permits testing ({sentiment}/{status})",
                  not patch_decision.permits_testing(zero))
    check("P5c the zero rung is reached before the product branches",
          patch_decision.decision_label(DAV, "21 Public Beta 1", "positive", 0)
          == patch_decision.INSUFFICIENT_DATA)

    # ONE ACTION per record, across all three decision-bearing fields. `proposed` builds the
    # fields the writers actually write, so this reads what a reader would see.
    for pid, version, sentiment in ((OBS, "31.2.1", "negative"), (OBS, "31.2.1", "positive"),
                                    (OBS, "31.2.1", "moderate"), (DAV, "21 Public Beta 1", "negative"),
                                    (ACRO, "25.001.20800", "positive")):
        fields = proposed(pid, version, sentiment=sentiment)
        actions = {patch_decision.action_of(str(fields.get("update_decision_label") or "")),
                   patch_decision.action_of(leading_decision(fields.get("quick_verdict"))),
                   patch_decision.action_of(leading_decision(fields.get("update_consensus_summary")))}
        actions.discard("")
        check(f"P6 {pid} {sentiment}: label, quick verdict and summary name ONE action",
              len(actions) == 1, repr(sorted(actions)))
        check(f"P6b {pid} {sentiment}: and that action is canonical",
              actions and patch_decision.is_canonical(next(iter(actions))), repr(sorted(actions)))


# ------------------------------------- [B] the body obeys the decision, status only qualifies


def check_body_follows_decision() -> None:
    """Supporting prose may qualify the decision; it may not invite an action it withholds.

    Found by adversarial review AFTER AUX-007 landed: the OBS branch picked its body from
    `update_status` alone, so a record whose verdict had just become WAIT still said "Test on a
    backup profile before using this OBS build". Live on all eight records that move, because
    every one of them is a maintained build.
    """
    from collections import Counter as _C
    for decision, invites in (("WAIT", False), ("TEST FIRST", True), ("SAFE ENOUGH", True)):
        for status in ("current", "archived"):
            fields = acr._record_coherence_fields(
                "obs-studio", "32.2.2", 42,
                {"update_product": "OBS Studio", "update_status": status}, _C(),
                decision=decision)
            body = str(fields.get("update_decision_body") or "")
            steps = " ".join(fields.get("practical_recommendations") or [])
            offers = "Test on a backup profile" in body
            check(f"B1 {decision}/{status}: the body offers testing == {invites}",
                  offers is invites, repr(body[:90]))
            if not invites:
                check(f"B2 {decision}/{status}: the recommendations do not open with an invitation",
                      not steps.startswith("Test with a backup"), repr(steps[:90]))
            # The authority decides whether prose may invite installation; the branch must agree.
            check(f"B3 {decision}/{status}: the body agrees with permits_testing",
                  offers is patch_decision.permits_testing(decision))
    # `update_status` may QUALIFY and may not DECIDE: same decision, same instruction, one extra
    # sentence for the archived build.
    from collections import Counter as _C2
    cur = acr._record_coherence_fields("obs-studio", "32.1.1", 43,
                                       {"update_product": "OBS Studio", "update_status": "current"},
                                       _C2(), decision="WAIT")
    arc = acr._record_coherence_fields("obs-studio", "32.1.1", 43,
                                       {"update_product": "OBS Studio", "update_status": "archived"},
                                       _C2(), decision="WAIT")
    check("B4 archived does not change the decision label",
          cur["update_decision_label"] == arc["update_decision_label"] == "WAIT")
    check("B5 archived does not change the quick verdict",
          cur["quick_verdict"] == arc["quick_verdict"])
    check("B6 archived adds a qualification and nothing else",
          arc["update_decision_body"].startswith(cur["update_decision_body"])
          and "archived build" in arc["update_decision_body"],
          repr(arc["update_decision_body"][-110:]))
    check("B7 and the maintained build carries no archived sentence",
          "archived" not in cur["update_decision_body"])


def check_detail_page_failsafe() -> None:
    """The DETAIL page must refuse an unrecognised label too, not just the listing row.

    Phase 1 first added the refusal to _includes/patch-table-row.html only. Rendered with the
    liquid gem, the same record then produced INSUFFICIENT DATA in the table and
    "GitHub / Copilot Copilot code review" in the detail page's AUXSAYS verdict box -- the two
    surfaces disagreeing about one patch, which is the invariant this sprint exists to establish.
    """
    layout = DETAIL_LAYOUT.read_text(encoding="utf-8")
    check("B8 the detail layout reads the shared vocabulary",
          "site.data.patch_verdicts" in layout,
          "the detail page still publishes unvalidated labels")
    vocab = yaml.safe_load((_REPO / "auxsays" / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8"))
    base = {"update_report_count": 1, "evidence_state": "pilot_sample",
            "evidence_state_label": "Verified reports",
            "consensus_collection_status": "pilot_initial_sample",
            "update_version": "1.0", "product_id": "x"}
    cases = {
        "prose": dict(base, update_decision_label="",
                      update_consensus_summary="GitHub / Copilot Copilot code review: now flags imports."),
        "garbage": dict(base, update_decision_label="SHIP IT"),
        "wait": dict(base, update_decision_label="WAIT"),
        "legacy": dict(base, update_decision_label="WAIT for production systems"),
        "safe": dict(base, update_decision_label="SAFE ENOUGH"),
    }
    liquid_ok, html = render_detail(cases, vocab=vocab)
    check("B9 the liquid gem is available, so these assertions run for real", liquid_ok,
          "install liquid 4.0.4; CI does this explicitly and must not skip these silently")
    if not liquid_ok:
        return
    for name, expected in (("prose", "INSUFFICIENT DATA"), ("garbage", "INSUFFICIENT DATA"),
                           ("wait", "WAIT"), ("legacy", "WAIT for production systems"),
                           ("safe", "SAFE ENOUGH")):
        got = rendered_verdict(html[name])
        check(f"B10 detail page publishes {expected!r} for the {name} record",
              got == expected, repr(got))


# ------------------------------------------------------- [G] the publication gate (AUX-009)


# A REAL shipped record, copied and then overridden. A hand-written minimal fixture fails
# scan_record's other requirements (title, summary, file-size status), and those findings mask the
# one this gate is about -- the first attempt at these checks reported `empty_title` instead of the
# contradiction.
_GATE_SEED = _REPO / "auxsays" / "updates" / "generated" / "2025-07-28-obs-studio-31-1-2.md"


def _record(path, label, verdict, summary):
    """The seed record with its three decision-bearing fields replaced."""
    text = _GATE_SEED.read_text(encoding="utf-8")
    head, body = text.split(NEWLINE + "---", 1)
    data = yaml.safe_load(head.lstrip("-" + NEWLINE)) or {}
    data["update_decision_label"] = label
    data["quick_verdict"] = verdict
    data["update_consensus_summary"] = summary
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---" + NEWLINE
                    + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
                    + "---" + body, encoding="utf-8")


def _qa_on(tree, argv):
    """Run the REAL qa_patch_records.main over a fixture tree, isolating unrelated scans.

    Only the record scan is exercised: the corpus-wide scans have nothing to say about a
    one-record fixture, and leaving them live would report THEIR findings as this gate's.
    """
    import qa_patch_records as qa
    out = tree / "qa_status.json"
    keys = ("scan_priority_source_coverage", "scan_evidence_count_alignment",
            "scan_update_layout_public_copy", "scan_required_record_paths",
            "scan_route_integrity")
    saved = {k: getattr(qa, k) for k in keys}
    saved_dir, saved_out = qa.GENERATED_DIR, qa.OUT_PATH
    try:
        qa.GENERATED_DIR = tree
        qa.OUT_PATH = out
        qa.scan_priority_source_coverage = lambda: ([], [])
        qa.scan_evidence_count_alignment = lambda files: ([], [])
        qa.scan_update_layout_public_copy = lambda: ([], [])
        qa.scan_required_record_paths = lambda: ([], [])
        qa.scan_route_integrity = lambda: ([], [])
        with contextlib.redirect_stdout(io.StringIO()):
            rc = qa.main(argv)
        return rc, json.loads(out.read_text(encoding="utf-8"))
    finally:
        for k, v in saved.items():
            setattr(qa, k, v)
        qa.GENERATED_DIR, qa.OUT_PATH = saved_dir, saved_out


def _codes(items):
    return {str(i.get("code") or "") for i in items}


CONFLICT_CODE = "record_names_conflicting_actions"


def check_publication_gate(tmp):
    """Same finding, two consequences: a warning for the writeback lane, fatal for publication."""
    import qa_patch_records as qa
    check("G0 the conflict code is what publication blocks on",
          CONFLICT_CODE in qa.PUBLICATION_BLOCKING_CODES,
          repr(sorted(qa.PUBLICATION_BLOCKING_CODES)))

    # TWO published decisions: the verdict says WAIT, the summary opens AVOID.
    bad = tmp / "bad"
    _record(bad / "2026-01-01-obs-studio-9-9-9.md", "WAIT",
            "WAIT: hold this build.", "AVOID: do not install this build.")
    rc_warn, st_warn = _qa_on(bad, [])
    rc_strict, st_strict = _qa_on(bad, ["--publish-strict"])
    check("G1 normal mode reports the contradiction as a WARNING",
          CONFLICT_CODE in _codes(st_warn["warnings"]), repr(_codes(st_warn["warnings"])))
    check("G2 normal mode does not make it fatal",
          CONFLICT_CODE not in _codes(st_warn["errors"]), repr(_codes(st_warn["errors"])))
    check("G3 publish-strict reports it as an ERROR",
          CONFLICT_CODE in _codes(st_strict["errors"]), repr(_codes(st_strict["errors"])))
    check("G4 publish-strict exits non-zero", rc_strict != 0, "rc=" + str(rc_strict))
    check("G5 the status file records which mode ran",
          st_warn["mode"] == "blocking" and st_strict["mode"] == "publish-strict",
          st_warn["mode"] + " / " + st_strict["mode"])

    # A COHERENT record passes both modes. Without this the gate could be failing everything.
    good = tmp / "good"
    _record(good / "2026-01-01-obs-studio-9-9-9.md", "WAIT",
            "WAIT: hold this build.", "WAIT: hold this build while reports settle.")
    rc_ok, st_ok = _qa_on(good, [])
    rc_ok_strict, st_ok_strict = _qa_on(good, ["--publish-strict"])
    check("G6 a coherent record is clean in normal mode",
          rc_ok == 0 and CONFLICT_CODE not in _codes(st_ok["warnings"]),
          repr(_codes(st_ok["warnings"])))
    check("G7 a coherent record passes publish-strict too", rc_ok_strict == 0,
          "rc=" + str(rc_ok_strict) + " errors=" + repr(_codes(st_ok_strict["errors"])))

    # A LEGACY phrasing beside its canonical form is one action in two registers, not a
    # contradiction. If this blocked, every old record would stop the site deploying.
    legacy = tmp / "legacy"
    _record(legacy / "2026-01-01-obs-studio-9-9-9.md", "WAIT",
            "WAIT for production systems: hold this build.", "WAIT: hold this build.")
    rc_leg, st_leg = _qa_on(legacy, ["--publish-strict"])
    check("G8 a legacy phrasing beside its canonical form is not a conflict",
          rc_leg == 0 and CONFLICT_CODE not in _codes(st_leg["errors"]),
          repr(_codes(st_leg["errors"])))

    # AN UNVETTED STORED LABEL is caught at the DATA level, not only by the render fail-safes.
    # Without this the vocabulary is enforced twice in Liquid and nowhere in the corpus, so a
    # record could name a decision nothing classified and the site would publish INSUFFICIENT
    # DATA for it rather than reporting the record as wrong.
    unknown = tmp / "unknown"
    _record(unknown / "2026-01-01-obs-studio-9-9-9.md", "SHIP IT",
            "SHIP IT: ship it.", "SHIP IT: ship it.")
    rc_unk_warn, st_unk_warn = _qa_on(unknown, [])
    rc_unk, st_unk = _qa_on(unknown, ["--publish-strict"])
    check("G16 an unrecognised stored verdict is reported",
          "record_names_unknown_verdict" in _codes(st_unk_warn["warnings"]),
          repr(_codes(st_unk_warn["warnings"])))
    check("G17 and it blocks publication", rc_unk != 0
          and "record_names_unknown_verdict" in _codes(st_unk["errors"]),
          "rc=" + str(rc_unk) + " " + repr(_codes(st_unk["errors"])))
    # A canonical label and a legacy phrasing must BOTH pass, or the check blocks the corpus.
    for label, name in (("WAIT", "canonical"), ("WAIT for production systems", "legacy")):
        d = tmp / ("ok-" + name)
        _record(d / "2026-01-01-obs-studio-9-9-9.md", label,
                label + ": hold this build.", label + ": hold this build.")
        rc_ok2, st_ok2 = _qa_on(d, ["--publish-strict"])
        check(f"G18 a {name} stored verdict passes publication ({label!r})",
              rc_ok2 == 0 and "record_names_unknown_verdict" not in _codes(st_ok2["errors"]),
              "rc=" + str(rc_ok2) + " " + repr(_codes(st_ok2["errors"])))

    # Promotion moves ONLY the publication-blocking code.
    errs, warns = qa.promote_for_publication(
        [], [{"code": CONFLICT_CODE, "file": "a"}, {"code": "some_other_advisory", "file": "b"}])
    check("G9 promotion moves the blocking code", _codes(errs) == {CONFLICT_CODE}, repr(_codes(errs)))
    check("G10 promotion leaves every other warning alone",
          _codes(warns) == {"some_other_advisory"}, repr(_codes(warns)))


def check_pages_gate():
    """Pages must run the record QA in publication mode, BEFORE Jekyll builds."""
    wf = yaml.safe_load((_REPO / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
    job = wf["jobs"].get("build") or list(wf["jobs"].values())[0]
    steps = job["steps"]
    qa_idx = [i for i, s in enumerate(steps) if "qa_patch_records.py" in str(s.get("run") or "")]
    build_idx = [i for i, s in enumerate(steps) if "jekyll build" in str(s.get("run") or "")]
    check("G11 Pages runs the generated-record QA exactly once", len(qa_idx) == 1, str(qa_idx))
    check("G12 Pages builds the site exactly once", len(build_idx) == 1, str(build_idx))
    if not (qa_idx and build_idx):
        return
    qa_step = steps[qa_idx[0]]
    check("G13 that QA invocation is publication-strict",
          "--publish-strict" in str(qa_step.get("run") or ""),
          repr(str(qa_step.get("run") or ""))[:140])
    check("G14 QA runs BEFORE the Jekyll build", qa_idx[0] < build_idx[0],
          "qa at " + str(qa_idx[0]) + ", build at " + str(build_idx[0]))
    check("G15 a QA failure is allowed to stop the build",
          not qa_step.get("continue-on-error") and not qa_step.get("if"),
          repr({k: v for k, v in qa_step.items() if k in ("continue-on-error", "if")}))


# ------------------------------------------------------------- [K] the canonical vocabulary (AUX-008)

CANONICAL_EIGHT = ("AVOID", "WAIT", "TEST FIRST", "SECURITY UPDATE",
                   "SAFE ENOUGH", "OFFICIAL ONLY", "INSUFFICIENT DATA", "MANUAL WATCH")


def check_vocabulary() -> None:
    """The eight canonical verdicts, the legacy aliases, and ONE risk order for the whole repo."""
    check("K1 exactly eight canonical verdicts",
          tuple(patch_decision.RISK_ORDER) == CANONICAL_EIGHT,
          repr(patch_decision.RISK_ORDER))
    check("K2 the canonical set and the risk order hold the same labels",
          patch_decision.CANONICAL_DECISIONS == frozenset(CANONICAL_EIGHT))
    # Rank is position, most cautionary first. Pinned VALUE by value: asserting
    # `index(x) == index(x)` would pass against any ordering at all.
    for expected, label in enumerate(CANONICAL_EIGHT):
        check(f"K3 {label} ranks {expected}",
              patch_decision.risk_rank(label) == expected,
              str(patch_decision.risk_rank(label)))
    # Legacy phrasings: recognised, mapped, and NEVER canonical.
    for legacy, canonical in (("AVOID for production", "AVOID"),
                              ("WAIT for production systems", "WAIT"),
                              ("SAFE ENOUGH to test", "SAFE ENOUGH"),
                              ("SECURITY UPDATE, TEST FIRST", "TEST FIRST")):
        check(f"K4 {legacy!r} -> {canonical}",
              patch_decision.action_of(legacy) == canonical,
              repr(patch_decision.action_of(legacy)))
        check(f"K4b {legacy!r} ranks as {canonical} does",
              patch_decision.risk_rank(legacy) == patch_decision.risk_rank(canonical))
        check(f"K4c {legacy!r} is NOT itself canonical",
              not patch_decision.is_canonical(legacy))
        check(f"K4d {legacy!r} is still RECOGNISED",
              legacy in patch_decision.DECISIONS)
    # UNKNOWN FAILS SAFE: no canonical action is invented for it, it never ranks as a real
    # verdict, and it never permits testing. It is returned unchanged rather than blanked, so
    # the QA conflict check still sees it as a distinct action.
    for unknown in ("Figma New feature", "GitHub / Copilot GitHub Actions", "almost AVOID", ""):
        check(f"K5 {unknown!r} gets no canonical action",
              not patch_decision.is_canonical(unknown))
        check(f"K5b {unknown!r} ranks last ({patch_decision.UNKNOWN_RANK})",
              patch_decision.risk_rank(unknown) == patch_decision.UNKNOWN_RANK,
              str(patch_decision.risk_rank(unknown)))
        check(f"K5c {unknown!r} does not permit testing",
              not patch_decision.permits_testing(unknown))
    check("K5d an unknown label keeps its text, so a conflict stays visible",
          patch_decision.action_of("Figma New feature") == "Figma New feature")
    # Longest match: a field opening with the longer phrase is never read as the shorter one.
    check("K6 longest match wins for a legacy prefix",
          leading_decision("WAIT for production systems: holds") == "WAIT for production systems",
          repr(leading_decision("WAIT for production systems: holds")))
    check("K6b the short form is still read when it is what the field says",
          leading_decision("WAIT: holds") == "WAIT")
    check("K6c arbitrary prose before a colon is NOT classified",
          leading_decision("Figma New feature: code layers") == "",
          repr(leading_decision("Figma New feature: code layers")))
    # permits_testing is a POSITIVE list keyed on the action.
    for label, allowed in (("TEST FIRST", True), ("SAFE ENOUGH", True),
                           ("SAFE ENOUGH to test", True), ("WAIT", False),
                           ("AVOID", False), ("INSUFFICIENT DATA", False),
                           ("OFFICIAL ONLY", False), ("MANUAL WATCH", False),
                           ("SECURITY UPDATE", False)):
        check(f"K7 permits_testing({label!r}) is {allowed}",
              patch_decision.permits_testing(label) is allowed)


def check_vocabulary_mirror() -> None:
    """Liquid cannot import Python, so _data/patch_verdicts.yml mirrors it. Pin the mirror."""
    data = yaml.safe_load((_REPO / "auxsays" / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8"))
    check("K8 the data file is non-empty (this section is not vacuous)",
          bool(data) and bool(data.get("risk_order")), repr(data)[:80])
    check("K8b risk_order mirrors RISK_ORDER exactly, in order",
          tuple(data["risk_order"]) == tuple(patch_decision.RISK_ORDER),
          repr(data.get("risk_order")))
    check("K8c legacy_aliases mirrors LEGACY_ALIASES exactly",
          data.get("legacy_aliases") == dict(patch_decision.LEGACY_ALIASES),
          repr(data.get("legacy_aliases")))
    check("K8d unknown_rank mirrors UNKNOWN_RANK",
          data.get("unknown_rank") == patch_decision.UNKNOWN_RANK,
          repr(data.get("unknown_rank")))
    # The retired JS copy must stay retired: a third vocabulary is what AUX-008 was about.
    js = (_REPO / "auxsays" / "assets" / "js" / "patch-table-sort.mjs").read_text(encoding="utf-8")
    # Pin the DECLARATION, not the word. The retirement comment names both identifiers on purpose,
    # so a substring check would fail on the explanation of its own fix.
    js_code = re.sub(r"(?m)^\s*//.*$", "", js)
    check("K9 the sort JS declares no verdict vocabulary",
          "export const VERDICT_ORDER" not in js_code
          and "function verdictRank" not in js_code,
          "a third copy of the order came back")
    for label in ("AVOID", "MANUAL WATCH", "OFFICIAL ONLY"):
        check(f"K9b {label!r} is not a literal in the sort JS code",
              ("'" + label + "'") not in js_code)
    check("K9c the retirement is explained where it was removed",
          "AUX-008" in js, "no comment records why the vocabulary left this module")
    # The include must take the order from the data file rather than its own ladder.
    row = (_REPO / "auxsays" / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
    check("K10 the row include reads the shared vocabulary",
          "site.data.patch_verdicts" in row)
    check("K10b and no longer carries its own eight-way verdict ladder",
          "vkey contains" not in row, "the elsif ladder came back")


# ---------------------------------------------------------------- [Q] nuance, not a second verdict

def check_qualification() -> None:
    beta = proposed(DAV, "21 Public Beta 1")
    blob = prose_blob(beta)
    check("Q1 the beta still warns production editors off active projects",
          "avoid it on active projects" in blob.lower(), repr(blob[:160]))
    check("Q2 that warning is prose, not a second verdict",
          not embedded_decisions(blob), repr(sorted(embedded_decisions(blob))))

    obs = proposed(OBS, "31.2.1", sentiment="negative")
    obs_blob = prose_blob(obs)
    check("Q3 a TEST FIRST record may still counsel caution in prose",
          "test on a backup profile" in obs_blob.lower(), repr(obs_blob[:160]))
    check("Q4 that caution names no competing action",
          not embedded_decisions(obs_blob), repr(sorted(embedded_decisions(obs_blob))))

    # A qualification may soften the decision; it may not reverse it. The positive-sentiment
    # sentence offers testing, and for the four policy products a positive record can carry a WAIT.
    pos_wait = proposed(WIN, "25H2", sentiment="positive")
    check("Q6 prose does not invite testing under a WAIT decision",
          decisions_named(pos_wait) == {"WAIT"}
          and "most users can test the update" not in prose_blob(pos_wait).lower(),
          repr(prose_blob(pos_wait)[:200]))

    every_prose_clean = []
    for pid, version, sentiment, status, label in MATRIX:
        fields = proposed(pid, version, sentiment=sentiment, status=status)
        found = embedded_decisions(prose_blob(fields))
        if found:
            every_prose_clean.append(f"{label}: {sorted(found)}")
    check(f"Q5 no supporting prose anywhere in the matrix carries a verdict ({len(MATRIX)} cases)",
          not every_prose_clean, "; ".join(every_prose_clean[:4]))


# ---------------------------------------------------------------- [C] the corpus is audited too

def qa_codes_for(path: Path) -> set[str]:
    """The SHIPPED qa_patch_records predicate over one record, not a re-implementation."""
    saved_root, saved_evidence = qa.ROOT, qa.EVIDENCE_PATH
    qa.ROOT = path.parents[2]
    qa.EVIDENCE_PATH = path.parent / "no-evidence.yml"
    try:
        errors, warnings = qa.scan_record(path)
    finally:
        qa.ROOT, qa.EVIDENCE_PATH = saved_root, saved_evidence
    return {str(item.get("code") or item) for item in list(errors) + list(warnings)}


def check_corpus_audit(tmp: Path) -> None:
    """The generator can no longer PRODUCE a contradiction. Something must also DETECT one on disk.

    Nothing did. `qa_patch_records` asserted only that a summary exists, never that it agreed with
    the verdict, which is why ten records sat in the corpus for months with no check failing. The
    repair to the writer does not fix a stored record; only regeneration does, and until it runs
    the contradiction is live.
    """
    tree = tmp / "auxsays" / "updates" / "generated"
    tree.mkdir(parents=True)
    CODE = "record_names_conflicting_actions"

    conflict = tree / "conflict.md"
    write_record(conflict, pid=DAV, version="21 Public Beta 1", count=15,
                 verdict="WAIT for production systems", summary_prefix="AVOID for production")
    check("C1 the shipped audit reports a record naming two actions",
          CODE in qa_codes_for(conflict), repr(sorted(qa_codes_for(conflict))))

    # Hand-authored Premiere 26.2 says "WAIT for production systems" in one field and "WAIT" in the
    # other. That is ONE instruction in two registers, on a record no lane regenerates. Reporting it
    # would put a permanent finding in front of every future reader of this audit, and the real
    # conflicts would be read as noise.
    phrasing = tree / "phrasing.md"
    write_record(phrasing, pid=PREM, version="26.2", count=3,
                 verdict="WAIT for production systems", summary_prefix="WAIT")
    check("C2 a phrasing variant of ONE action is not reported",
          CODE not in qa_codes_for(phrasing), repr(sorted(qa_codes_for(phrasing))))

    coherent = tree / "coherent.md"
    write_record(coherent, pid=OBS, version="31.2.1", count=9,
                 verdict="TEST FIRST", summary_prefix="TEST FIRST")
    check("C3 a coherent record is not reported",
          CODE not in qa_codes_for(coherent), repr(sorted(qa_codes_for(coherent))))

    # And the audit must agree with the writer: regenerate the conflicting record the ordinary way
    # and the finding has to clear itself, with no hand edit. Its OWN tree -- `conflict.md` above is
    # a second record for the same patch identity, and the writer refuses an ambiguous match, so
    # sharing the directory tested nothing except that nothing was written.
    regen_tree = tmp / "regen" / "auxsays" / "updates" / "generated"
    regen_tree.mkdir(parents=True)
    evidence = tmp / "evidence.yml"
    write_evidence(evidence, [evidence_row(DAV, "21 Public Beta 1", i) for i in range(15)])
    record = regen_tree / "2026-04-14-davinci-resolve-21-public-beta-1.md"
    write_record(record, pid=DAV, version="21 Public Beta 1", count=15,
                 verdict="WAIT for production systems", summary_prefix="AVOID for production")
    before = qa_codes_for(record)
    promote(regen_tree, evidence, DAV)
    check("C4 ordinary regeneration clears the finding",
          CODE in before and CODE not in qa_codes_for(record),
          f"before={CODE in before} after={sorted(qa_codes_for(record))}")


# ---------------------------------------------------------------- [V] what the reader is told

DETAIL_LAYOUT = _REPO / "auxsays" / "_layouts" / "aux-update.html"

# render! rather than render, so a Liquid error RAISES instead of landing in the output where an
# extraction that finds no verdict would read as "no contradiction".
_RENDER_RB = """
require 'liquid'
require 'json'

module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def markdownify(i) = i.to_s
end
Liquid::Template.register_filter(Shims)

payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
out = {}
payload['cases'].each do |name, vars|
  out[name] = tpl.render!('site' => payload['site'], 'page' => vars, 'content' => '')
end
print JSON.generate(out)
"""


def render_detail(cases: dict[str, dict], vocab: dict | None = None) -> tuple[bool, dict[str, str]]:
    """Render the SHIPPED patch-detail layout over each case. (liquid_ok, {name: html}).

    `site.data.patch_verdicts` is supplied from the REAL data file, because Jekyll supplies it:
    since AUX-029 the layout looks its vocabulary up there and refuses a label it cannot find.
    Rendering with an empty `site` would blank every verdict and these assertions would be
    measuring the harness instead of the template.
    """
    src = DETAIL_LAYOUT.read_text(encoding="utf-8").split("---", 2)[-1]
    src = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", src, flags=re.S)
    ruby = shutil.which("ruby")
    if not ruby:
        return False, {n: "<<RENDER FAILED: ruby is not on PATH>>" for n in cases}
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload = Path(td) / "p.json"
        payload.write_text(json.dumps({
            "template": src,
            "site": {"time": "2026-09-09T00:00:00Z", "data": {
                "evidence_method_health": {},
                "patch_verdicts": vocab if vocab is not None else yaml.safe_load(
                    (_REPO / "auxsays" / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8")),
            }},
            "cases": cases,
        }), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
    if proc.returncode != 0:
        return True, {n: f"<<RENDER FAILED: {(proc.stderr or '')[-300:]}>>" for n in cases}
    return True, json.loads(proc.stdout)


def rendered_verdict(html: str) -> str:
    """The words under the "AUXSAYS verdict" eyebrow -- what the patch page actually tells a reader."""
    m = re.search(r'update-decision-eyebrow">AUXSAYS verdict</span>\s*<strong>(.*?)</strong>',
                  html, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def check_render() -> None:
    """The two decision-bearing fields reach readers on DIFFERENT pages.

    aux-update.html renders the verdict; aux-updates.html renders `update_consensus_summary` under
    "Evidence summary". The detail layout never prints the summary, so no single page showed the
    contradiction and neither surface could catch it alone. This renders the real layout and
    compares what it says against the summary the feed would print for the same record.
    """
    page = {
        "product_id": DAV, "update_version": "21 Public Beta 1", "target_build": "",
        "update_product": "DaVinci Resolve", "update_consensus_label": "Negative",
        "update_published_at": "2026-04-14T00:00:00Z",
        "update_source_url": "https://example.test/notes",
        "consensus_collection_status": "pilot_initial_sample",
        "evidence_state": "pilot_sample",
        "update_report_count": 15, "confirmed_patch_specific_report_count": 15,
        "accepted_report_sources": [{"source_type": "forum_thread"}],
        "evidence_last_checked": "2099-01-01T00:00:00Z",
    }
    after = proposed(DAV, "21 Public Beta 1")
    fixed = dict(page, **{k: after.get(k, "") for k in
                          ("quick_verdict", "update_decision_label", "update_decision_body")})
    # The record exactly as it shipped: the same verdict, beside the summary that disagreed with it.
    broken = dict(fixed, update_consensus_summary=(
        "AVOID for production: DaVinci Resolve 21 Public Beta 1 has 15 user reports found."))

    liquid_ok, html = render_detail({"fixed": fixed, "broken": broken})
    check("V1 the liquid gem is available, so these assertions run for real", liquid_ok,
          "install liquid 4.0.4; CI does this explicitly and must not skip these silently")
    check("V2 the patch page renders the record's own verdict",
          rendered_verdict(html["fixed"]) == str(after.get("update_decision_label") or ""),
          f"page renders {rendered_verdict(html['fixed'])!r}, record says "
          f"{after.get('update_decision_label')!r}")
    check("V3 the rendered verdict and the feed's summary name the same action",
          rendered_verdict(html["fixed"])
          == leading_decision(after.get("update_consensus_summary")),
          f"page says {rendered_verdict(html['fixed'])!r}, feed would say "
          f"{leading_decision(after.get('update_consensus_summary'))!r}")
    # Non-vacuity has to require a real render: with ruby absent `rendered_verdict` returns "",
    # and "" != "AVOID for production" would let this check pass on a page that never rendered.
    broken_verdict = rendered_verdict(html["broken"])
    check("V4 the same comparison DOES detect the shipped contradiction (non-vacuous)",
          bool(broken_verdict)
          and broken_verdict != leading_decision(broken["update_consensus_summary"]),
          f"rendered verdict {broken_verdict!r} -- the extraction cannot see a contradiction it "
          "is supposed to catch")


# ---------------------------------------------------------------- [R]/[N] regeneration repairs

def build_tree(tmp: Path) -> tuple[Path, Path, dict[str, Path]]:
    tree = tmp / "auxsays" / "updates" / "generated"
    tree.mkdir(parents=True)
    evidence = tmp / "evidence.yml"
    paths = {
        "beta": tree / "2026-04-14-davinci-resolve-21-public-beta-1.md",
        "stable": tree / "2026-04-14-davinci-resolve-21.md",
        "obs": tree / "2026-05-01-obs-studio-31-2-1.md",
    }
    # The live defect, stored: verdict WAIT, summary AVOID, on one record.
    write_record(paths["beta"], pid=DAV, version="21 Public Beta 1", count=15,
                 verdict="WAIT for production systems", summary_prefix="AVOID for production")
    write_record(paths["stable"], pid=DAV, version="21", count=12,
                 verdict="WAIT", summary_prefix="WAIT")
    write_record(paths["obs"], pid=OBS, version="31.2.1", count=9,
                 verdict="TEST FIRST", summary_prefix="WAIT")
    rows = ([evidence_row(DAV, "21 Public Beta 1", i) for i in range(15)]
            + [evidence_row(DAV, "21", i) for i in range(12)]
            + [evidence_row(OBS, "31.2.1", i) for i in range(9)])
    write_evidence(evidence, rows)
    return tree, evidence, paths


def check_regeneration(tmp: Path) -> None:
    tree, evidence, paths = build_tree(tmp)

    # A PRECONDITION, not a check. It reads back the literals `write_record` just wrote, so it can
    # never fail for a production reason -- as a scored check it was a tautology occupying a
    # governed slot, and worse, the mutation harness excluded it as "unrelated noise" while the
    # checks that really do fail for unrelated reasons (the render section, when ruby is missing)
    # were not excluded at all.
    before_beta = front_matter(paths["beta"])
    assert len({str(before_beta.get("update_decision_label")),
                leading_decision(before_beta.get("update_consensus_summary"))}) == 2, \
        "fixture no longer reproduces the shipped contradiction"

    stable_before = decisions_named(front_matter(paths["stable"]))
    rc_dav = promote(tree, evidence, DAV)
    rc_obs = promote(tree, evidence, OBS)
    check("R1 ordinary promotion runs clean", rc_dav == 0 and rc_obs == 0, f"{rc_dav}/{rc_obs}")

    after_beta = front_matter(paths["beta"])
    check("R2 regeneration repaired the stale contradictory summary with no hand edit",
          decisions_named(after_beta) == {"WAIT"},
          repr(sorted(decisions_named(after_beta))))
    check("R2b and it wrote the CANONICAL label, not the legacy phrasing",
          patch_decision.is_canonical(str(after_beta.get("update_decision_label") or "")),
          repr(after_beta.get("update_decision_label")))
    check("R3 the repaired summary is the one the verdict already published",
          leading_decision(after_beta.get("update_consensus_summary"))
          == str(after_beta.get("update_decision_label")))

    after_obs = front_matter(paths["obs"])
    # WAIT, not TEST FIRST, since AUX-007. The fixture's OBS evidence is negative, and the decision
    # now follows that evidence instead of `update_status`. The repair this check exists to prove --
    # that regeneration collapses the two decision-shaped fields onto one action with no hand edit
    # -- is unchanged; only the action it lands on moved, and it moved because the policy did.
    check("R4 the OBS half of the class is repaired by the same path",
          decisions_named(after_obs) == {"WAIT"}, repr(sorted(decisions_named(after_obs))))

    after_stable = front_matter(paths["stable"])
    check("R5 the stable sibling still decides WAIT",
          decisions_named(after_stable) == {"WAIT"}, repr(sorted(decisions_named(after_stable))))
    check("R6 the stable sibling's decision text did not move",
          leading_decision(after_stable.get("quick_verdict")) == "WAIT"
          and leading_decision(after_stable.get("update_consensus_summary")) == "WAIT")
    # Compare AFTER against BEFORE. The old version of this check asserted that the fixture's own
    # literal was in the fixture and that one particular word was absent, so a promotion that
    # churned the stable sibling from WAIT to TEST FIRST passed it.
    check("R7 a record that was already coherent is not churned into a new decision",
          decisions_named(after_stable) == stable_before,
          f"{sorted(stable_before)} -> {sorted(decisions_named(after_stable))}")

    snapshot = {k: p.read_bytes() for k, p in paths.items()}
    promote(tree, evidence, DAV)
    promote(tree, evidence, OBS)
    unchanged = [k for k, b in snapshot.items() if paths[k].read_bytes() != b]
    check("N1 the next identical run writes nothing (N+1 deterministic)",
          not unchanged, f"changed: {unchanged}")


# ---------------------------------------------------------------- [X] mutations

def _old_recommendation_prefix(pid, ver, consensus_label, count):
    """The pre-repair summary policy, verbatim: sentiment plus its own copy of the beta rule.

    Note what is NOT here: a product check around the beta rule. The deleted
    `_recommendation_prefix` applied "AVOID for production" to any negative beta of any product,
    while the verdict applied beta logic to DaVinci alone.
    """
    label = str(consensus_label or "").lower()
    if count <= 0:
        return "INSUFFICIENT DATA"
    if acr._davinci_version_is_beta(ver) and label == "negative":
        return "AVOID for production"
    if label == "negative":
        return "WAIT"
    if label == "positive":
        return "SAFE ENOUGH to test"
    return "TEST FIRST"


def _old_style_summary(*, rows, consensus_label, decision, **kw):
    """The summary as it behaved before: generated, then re-prefixed with its OWN chosen action."""
    text = _REAL_PUBLIC_SUMMARY(rows=rows, consensus_label=consensus_label, decision=decision, **kw)
    chosen = _old_recommendation_prefix(kw.get("pid"), kw.get("ver"), consensus_label, len(rows))
    body = text.split(":", 1)[1] if ":" in text else f" {text}"
    return f"{chosen}:{body}"


_REAL_PUBLIC_SUMMARY = acr._public_summary


def run_mutant(label: str, body, mutants: list, *, mutate, restore) -> None:
    """Score one mutant against a BASELINE of the same checks.

    Two things this must not count as a catch. A mutant that merely explodes -- so the exception is
    caught and recorded as a crash. And a check that was already failing for a reason of its own:
    with ruby off PATH the render checks fail whether or not the mutant is present, and a mutation
    section that scored those would go green on environment noise. So the same check functions run
    UNMUTATED first, and their failures are subtracted from the mutated run's.
    """
    try:
        with captured() as baseline:
            body()
    except Exception as exc:                                  # noqa: BLE001 - deliberate
        mutants.append((label, [], f"baseline raised {type(exc).__name__}: {exc}"))
        return

    mutate()
    try:
        with captured() as failures:
            body()
    except Exception as exc:                                  # noqa: BLE001 - deliberate
        mutants.append((label, [], f"{type(exc).__name__}: {exc}"))
        return
    finally:
        restore()

    already = set(baseline)
    mutants.append((label, [f for f in failures if f not in already], ""))


def swap(owner, name: str, replacement):
    """(mutate, restore) that puts `replacement` on owner.name and puts the original back."""
    original = getattr(owner, name)

    def mutate():
        setattr(owner, name, replacement)

    def restore():
        setattr(owner, name, original)

    return mutate, restore


def check_mutations(tmp: Path) -> None:
    mutants: list[tuple[str, list[str], str]] = []
    real_coherence = acr._record_coherence_fields
    real_write_fields = acr._fields_for_record_write

    def hardcoded(*a, **k):
        fields = dict(real_coherence(*a, **k))
        if fields:
            fields["update_decision_label"] = "AVOID for production"
            fields["quick_verdict"] = "AVOID for production: hardcoded."
        return fields

    def drop_summary(current, proposed_fields):
        return {k: v for k, v in real_write_fields(current, proposed_fields).items()
                if k != "update_consensus_summary"}

    # Each regeneration run needs its OWN tree: the baseline run repairs the fixture, so a mutated
    # run over the same directory would find nothing left to repair and report a false catch.
    regen_runs = iter(range(2, 99))

    cases = [
        # X1 -- the summary re-acquires its own policy. This IS the shipped defect.
        ("X1 summary re-derives the decision from sentiment (the shipped defect)",
         lambda: (check_matrix(), check_policy(), check_render()),
         swap(acr, "_public_summary", _old_style_summary)),
        # X2 -- a verdict branch keeps its own hard-coded decision while the summary asks the authority.
        ("X2 a verdict branch hard-codes its own decision",
         lambda: (check_wiring(), check_matrix()),
         swap(acr, "_record_coherence_fields", hardcoded)),
        # X3 -- the third copy in build_consensus_from_evidence comes back.
        ("X3 build_consensus keeps a private copy of the policy",
         check_wiring,
         swap(bce, "recommendation_prefix",
              lambda pid, ver, label, total, **k: (
                  "AVOID for production" if pid == DAV and bce.version_is_beta(ver) else "WAIT"))),
        # X4 -- "coherence" achieved by deleting the nuance instead of subordinating it.
        ("X4 the beta's avoid-on-active-projects nuance is deleted",
         check_qualification,
         swap(acr, "_affected_workflow_sentence", lambda *a, **k: "")),
        # X5 -- prose may invite testing again regardless of the decision.
        ("X5 supporting prose offers testing under a WAIT decision",
         check_qualification,
         swap(patch_decision, "permits_testing", lambda decision: True)),
        # X6 -- regeneration stops refreshing the summary, so stale contradictory prose survives.
        ("X6 stale contradictory prose survives regeneration",
         lambda: check_regeneration(tmp / f"x-{next(regen_runs)}"),
         swap(acr, "_fields_for_record_write", drop_summary)),
        # X7 -- the corpus audit stops telling two actions apart, so every record looks coherent.
        ("X7 the corpus audit collapses every action into one",
         lambda: check_corpus_audit(tmp / f"x-{next(regen_runs)}"),
         swap(patch_decision, "action_of", lambda decision: "WAIT")),
    ]

    for label, body, (mutate, restore) in cases:
        run_mutant(label, body, mutants, mutate=mutate, restore=restore)

    for label, failures, crash in mutants:
        detail = (f"mutant crashed instead of being caught: {crash}" if crash
                  else "no NAMED check failed that was not already failing")
        check(f"{label} -> caught", bool(failures), detail)
        if failures:
            print(f"        caught by: {', '.join(sorted(failures)[:5])}")


# ---------------------------------------------------------------- the suite

def run() -> int:
    print("=" * 78)
    print("ONE PATCH DECISION AUTHORITY")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        print("\n[W] one authority, proven by substitution")
        check_wiring()

        print("\n[M] the matrix never names two actions")
        check_matrix()

        print("\n[P] the decisions are the policy's, not a preferred word")
        check_policy()

        print("\n[K] the canonical vocabulary, and its one mirror")
        check_vocabulary()
        check_vocabulary_mirror()

        print("\n[B] the body obeys the decision; the detail page refuses unknown labels")
        check_body_follows_decision()
        check_detail_page_failsafe()

        print("\n[G] the publication gate: warn for writeback, fatal for publish")
        check_publication_gate(tmp / "gate")
        check_pages_gate()

        print("\n[Q] nuance survives as a qualification")
        check_qualification()

        print("\n[C] the corpus is audited, not just the generator")
        check_corpus_audit(tmp / "corpus")

        print("\n[V] the rendered page and the feed's summary agree")
        check_render()

        print("\n[R]/[N] ordinary regeneration repairs stale prose, then writes nothing")
        check_regeneration(tmp / "regen")

        print("\n[X] mutations -- each must be caught by a NAMED check")
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
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
