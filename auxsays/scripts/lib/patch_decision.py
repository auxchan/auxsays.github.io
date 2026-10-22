"""The ONE install/wait/avoid decision for a patch.

WHY THIS MODULE EXISTS. A patch page carried two decision-shaped statements produced by two
independent generators. `2026-04-14-davinci-resolve-21-public-beta-1.md` published

    update_decision_label:     "WAIT for production systems"      <- rendered as "AUXSAYS verdict"
    quick_verdict:             "WAIT for production systems: ..."
    update_consensus_summary:  "AVOID for production: ..."        <- rendered as "Evidence summary"

on the same record, and both reached readers: the detail page renders the verdict, the patch feed
renders the summary. A page cannot tell one reader to WAIT and another to AVOID.

It was not one record. Measured over the corpus at fef76436, ten records carried more than one
distinct decision phrase: eight OBS records said "TEST FIRST" in the verdict and "WAIT" in the
summary, the DaVinci beta said WAIT versus AVOID, and Premiere 26.2 (hand-authored, promoted by
nothing) says "WAIT for production systems" beside "WAIT".

THE CAUSE. `apply_consensus_to_records._record_coherence_fields` chose the verdict per product,
while `_public_summary` called `_recommendation_prefix`, which chose again from sentiment -- with
its own copy of the beta rule. A third copy lived in `build_consensus_from_evidence`. Three
implementations of one policy, free to disagree, and they did.

THE RULE. This function is the only place a decision is chosen. The verdict, the summary prefix and
anything else that names an action all read it. Supporting prose may still add nuance -- the beta
record still tells production editors to avoid it on active projects -- but nuance is a
QUALIFICATION of the decision, never a second decision.

WHICH DECISION THE BETA GETS, and why it is derived rather than preferred: of the five
decision-bearing fields on that record, four already said WAIT (`update_decision_label`,
`quick_verdict`, `update_decision_body`, `practical_recommendations`); only the summary prefix said
AVOID, and the avoid-on-active-projects sentence survives verbatim in `_affected_workflow_sentence`.
So the policy already in force is "wait before installing, and do not put it on active projects",
which is one decision plus a qualification -- not two decisions.

WHAT MOVES, STATED PLAINLY. Every one of the ten was already incoherent, but they do not all move
in the same direction, and the OBS half is the half that gets MORE permissive:

  * DaVinci 21 Public Beta 1: the feed summary goes AVOID -> WAIT for production systems. Stricter
    in wording than the verdict it now matches? No -- softer than the summary it replaces. The
    verdict does not move.
  * Eight OBS records: the feed summary goes WAIT -> TEST FIRST, following the verdict those pages
    have always shown. On `2026-04-21-obs-studio-32-1-2.md` that is 97 negative reports whose feed
    line now invites testing. This is what the deterministic policy says (maintained OBS build ->
    TEST FIRST), which is why it is here; it is not a judgement that OBS got safer.
  * Premiere 26.2 is hand-authored, carries hand commits, and is promoted by NO lane -- the
    scheduled lane's comment says it "is deliberately absent and must stay absent" (PR #77 restored
    those keys by hand after a scoped write reverted them). Its two phrasings, "WAIT for production
    systems" and "WAIT", name the SAME action, so it is a phrasing variant rather than a
    contradiction, and it stays as it is. Nothing here will repair it, by design.

A related consequence worth naming: for the four policy products the summary prefix no longer
responds to evidence sentiment at all, because the verdict never did. Sentiment still drives
`update_consensus_label`, the feed pill, the feed ordering and the home-page dot -- none of which
this module touches.

THE AVOID RUNG IS GONE, not merely re-scoped. No input to `decision_label` returns "AVOID" or
"AVOID for production": the only rule that produced them was the summary's own beta clause. That is
deliberate -- no record has ever STORED an AVOID as its decision label, and the verdict path has
never had an AVOID branch -- but it means the site can no longer publish that word as a decision.
Restoring it is a policy change, to be made here, once.
"""
from __future__ import annotations

import re
from typing import Any

INSUFFICIENT_DATA = "INSUFFICIENT DATA"

# ---------------------------------------------------------------------------------------------
# THE CANONICAL VOCABULARY. Exactly eight production verdicts, MOST CAUTIONARY FIRST.
#
# The order IS the policy: the index is the risk rank the row emitter publishes as
# `data-verdict-rank`, and the sort JS orders that number rather than re-reading the words. Moving
# an entry changes what the product recommends, so it is moved here or nowhere.
# ---------------------------------------------------------------------------------------------
RISK_ORDER: tuple[str, ...] = (
    "AVOID",
    "WAIT",
    "TEST FIRST",
    "SECURITY UPDATE",
    "SAFE ENOUGH",
    "OFFICIAL ONLY",
    INSUFFICIENT_DATA,
    "MANUAL WATCH",
)
CANONICAL_DECISIONS = frozenset(RISK_ORDER)

# An unrecognised label sorts LAST and stays visible. Not 0: a phrase nobody has classified must
# never inherit the rank of the most cautionary verdict, and must never be hidden either.
UNKNOWN_RANK = 99

# LEGACY PHRASINGS. Recognised, never produced. They exist in records written before the
# vocabulary was fixed, and they must keep resolving to an action so conflict detection, audits
# and the template fallback all read an old record the same way a new one.
#
# "SECURITY UPDATE, TEST FIRST" names two of them; its ACTION is TEST FIRST, the more cautionary
# of the pair and the one that tells the reader what to do. That also matches the rank the site
# has always given it -- the Liquid `contains` chain reaches TEST FIRST first -- so recognising it
# here changes no published ordering.
LEGACY_ALIASES: dict[str, str] = {
    "AVOID for production": "AVOID",
    "WAIT for production systems": "WAIT",
    "SAFE ENOUGH to test": "SAFE ENOUGH",
    "SECURITY UPDATE, TEST FIRST": "TEST FIRST",
}

# The RECOGNISER: everything a field may legitimately open with. Wider than what this module
# produces, on purpose -- a word the authority cannot produce is still a word the site has to be
# able to read.
DECISIONS = frozenset(CANONICAL_DECISIONS | set(LEGACY_ALIASES))

# Which ACTIONS invite the reader to put the build on a machine. A POSITIVE list, so a decision
# phrase nobody has thought about yet defaults to cautious rather than to "go ahead".
#
# Keyed on the canonical action, not on phrasings, so the legacy "SAFE ENOUGH to test" is admitted
# through `action_of` instead of needing its own entry here. Listing phrasings is how a set like
# this falls behind the vocabulary.
#
# Supporting prose asks this before offering an installation. "Most users can test the update"
# under a WAIT verdict is a second, quieter recommendation -- the same defect as a second verdict,
# in a sentence that carries no colon.
INVITES_TESTING = frozenset({"SAFE ENOUGH", "TEST FIRST"})

_BETA_RE = re.compile(r"\b(?:public\s+)?beta\b|b\d+\b", re.I)

# Literals, not imports. `lib` is a leaf: pulling WINDOWS_PRODUCT_ID from patch_collectors.base
# would make the decision policy depend on the whole collector package, which imports lib itself.
# test_patch_decision_authority pins these against the canonical constant instead, so the
# duplication cannot drift silently.
DAVINCI = "blackmagic-davinci"
OBS = "obs-studio"
WINDOWS = "microsoft-windows-11"
PREMIERE = "adobe-premiere-pro"


def version_is_beta(version: str) -> bool:
    """Is this version string a beta / preview / release-candidate build?

    One definition, shared. It used to exist twice -- `_davinci_version_is_beta` in
    apply_consensus_to_records and `version_is_beta` in build_consensus_from_evidence -- which is
    how a beta could be judged by one rule in the verdict and another in the summary.
    """
    return bool(_BETA_RE.search(str(version or "")))


def permits_testing(decision: str) -> bool:
    """May supporting prose invite the reader to install or test this build?

    Asked of the ACTION, so a record still carrying the legacy "SAFE ENOUGH to test" answers the
    same as one carrying canonical "SAFE ENOUGH".
    """
    return action_of(decision) in INVITES_TESTING


_LONGEST_FIRST = tuple(sorted(DECISIONS, key=len, reverse=True))


def action_of(decision: str) -> str:
    """The instruction a decision phrase gives, with phrasing collapsed to the canonical action.

    Two fields saying "WAIT" and "WAIT for production systems" are one decision in two registers;
    "WAIT" against "TEST FIRST", or "AVOID" against "WAIT", are two instructions to the same
    reader. Anything auditing a record for coherence has to know the difference.

    AN UNRECOGNISED PHRASE IS RETURNED UNCHANGED, and that is the fail-safe direction. Collapsing
    it to "" would make it invisible to the conflict check in qa_patch_records, so a record whose
    summary opened with an unvetted decision word would read as coherent. Returned as itself it
    stays a DISTINCT action, so pairing it with a canonical one is still reported as a conflict.
    What it never does is acquire a canonical action it was not given.
    """
    text = str(decision or "").strip()
    return LEGACY_ALIASES.get(text, text)


def is_canonical(decision: str) -> bool:
    """Is this exactly one of the eight canonical production verdicts?"""
    return str(decision or "").strip() in CANONICAL_DECISIONS


def risk_rank(decision: str) -> int:
    """Position in RISK_ORDER, most cautionary first; UNKNOWN_RANK for anything unrecognised.

    Legacy phrasings rank as the action they name, so an old record sorts beside a new one. This
    is the normative definition that `_includes/patch-table-row.html` mirrors when it emits
    `data-verdict-rank`; test_patch_decision_authority pins the two against each other.
    """
    action = action_of(decision)
    try:
        return RISK_ORDER.index(action)
    except ValueError:
        return UNKNOWN_RANK


def leading_decision(text: str) -> str:
    """The decision a field opens with, as a reader sees it: `PHRASE:` at the start, else "".

    Longest match first, so "WAIT for production systems:" is never read as "WAIT".
    """
    body = str(text or "")
    for phrase in _LONGEST_FIRST:
        if body.startswith(phrase + ":"):
            return phrase
    return ""


def decision_label(product_id: str, version: str, consensus_label: str, count: int,
                   *, record: dict[str, Any] | None = None) -> str:
    """The canonical decision for this patch, from the deterministic policy already in force.

    Product policy first, because that is the policy the reader-facing verdict has always used;
    sentiment supplies the default for products that state no policy of their own. Returning the
    SAME string to the verdict and to the summary prefix is what makes a contradiction
    unrepresentable rather than merely unlikely.

    ONE DELIBERATE NARROWING. The deleted `_recommendation_prefix` tested the beta rule with no
    product check, so any negative beta of ANY product got "AVOID for production" in its summary,
    while the verdict path applied beta logic to DaVinci alone. The verdict is the canonical
    surface, so the beta rule is scoped to DaVinci here. Measured over the whole corpus at
    fef76436 -- 212 evidence groups, 1166 records -- no non-DaVinci record's decision moves because
    of this: the 9 non-DaVinci records whose version string matches the beta pattern are all Figma
    RELEASE-NOTE TITLES ("Slots is available in open beta"), all at zero reports, and Figma has no
    evidence rows, no collector and no promotion step. The old rule was matching prose.

    The `count <= 0` branch is defensive. Both callers short-circuit at zero before asking --
    `_public_summary` and `consensus_summary` each return their own INSUFFICIENT DATA sentence --
    so nothing reaches it today. It stays because the alternative is a policy that answers "TEST
    FIRST" for a patch with no evidence at all.
    """
    if int(count or 0) <= 0:
        return INSUFFICIENT_DATA

    pid = str(product_id or "").strip()
    label = str(consensus_label or "").strip().lower()

    if pid == DAVINCI:
        # A beta is not a harsher sentiment, it is a different install decision: wait before
        # installing, and keep it off active projects. Both halves used to live in the LABEL
        # ("WAIT for production systems"); the action is WAIT either way, and the production-systems
        # half is a qualification, which belongs in the prose where `_affected_workflow_sentence`
        # already states it verbatim. The label is now canonical; `version_is_beta` stays because
        # the prose still asks it.
        return "WAIT"
    if pid == OBS:
        # EVIDENCE-DRIVEN (AUX-007). This branch used to read `update_status`: an "archived" record
        # got WAIT and everything else got TEST FIRST. That made a positional metadata field the
        # install recommendation, and the field is no longer meaningfully maintained -- 15 of 16 OBS
        # records say "current". The effect was that eight records whose community consensus is
        # NEGATIVE published TEST FIRST, including 32.1.2 with 107 negative reports. The one
        # "archived" record happened to agree with the evidence, so the field looked like it was
        # working.
        #
        # `update_status` remains descriptive metadata and may still shape prose ("an older
        # archived build"). It MUST NOT reach this decision, which is why `record` is no longer
        # consulted here.
        if label == "negative":
            return "WAIT"
        if label == "positive":
            return "SAFE ENOUGH"
        return "TEST FIRST"
    if pid == WINDOWS:
        return "WAIT"
    if pid == PREMIERE:
        return "WAIT"

    if label == "negative":
        return "WAIT"
    if label == "positive":
        return "SAFE ENOUGH"
    return "TEST FIRST"
