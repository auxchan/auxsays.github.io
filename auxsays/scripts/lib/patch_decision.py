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

# The full decision vocabulary. Anything that names an action must come from this set, so a new
# phrase cannot enter the corpus without passing through here.
#
# It is also the RECOGNISER, which is why it lists phrases `decision_label` never returns. "AVOID"
# and "AVOID for production" stay because prose has to be checked for them -- a supporting sentence
# that opens "AVOID for production:" is a second verdict whoever wrote it -- and because
# `_includes/patch-table-row.html` still ranks an AVOID label red at the top of the verdict sort.
# A word this authority cannot produce is not a word the site can stop recognising.
INSUFFICIENT_DATA = "INSUFFICIENT DATA"
DECISIONS = frozenset({
    "AVOID",
    "AVOID for production",
    "WAIT",
    "WAIT for production systems",
    "SAFE ENOUGH to test",
    "OFFICIAL ONLY",
    INSUFFICIENT_DATA,
    "SECURITY UPDATE",
    "TEST FIRST",
    "MANUAL WATCH",
})

# Which decisions invite the reader to put the build on a machine. A POSITIVE list, so a decision
# phrase nobody has thought about yet defaults to cautious rather than to "go ahead".
#
# Supporting prose asks this before offering an installation. "Most users can test the update"
# under a WAIT verdict is a second, quieter recommendation -- the same defect as a second verdict,
# in a sentence that carries no colon.
INVITES_TESTING = frozenset({"SAFE ENOUGH to test", "TEST FIRST"})

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
    """May supporting prose invite the reader to install or test this build?"""
    return str(decision or "").strip() in INVITES_TESTING


# Phrasings that give the SAME instruction. Two fields saying "WAIT" and "WAIT for production
# systems" are one decision in two registers; "WAIT" against "TEST FIRST", or "AVOID" against
# "WAIT", are two instructions to the same reader. Anything that audits a record for coherence has
# to know the difference, or it reports the DaVinci beta and hand-authored Premiere 26.2 alike.
_ACTION_OF = {
    "AVOID": "AVOID",
    "AVOID for production": "AVOID",
    "WAIT": "WAIT",
    "WAIT for production systems": "WAIT",
}

_LONGEST_FIRST = tuple(sorted(DECISIONS, key=len, reverse=True))


def action_of(decision: str) -> str:
    """The instruction a decision phrase gives, with phrasing collapsed."""
    text = str(decision or "").strip()
    return _ACTION_OF.get(text, text)


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
        # A beta is not a harsher sentiment, it is a different install decision: wait for production
        # systems, and keep it off active projects (the qualification lives in the prose).
        return "WAIT for production systems" if version_is_beta(version) else "WAIT"
    if pid == OBS:
        archived = str((record or {}).get("update_status") or "").strip().lower() == "archived"
        return "WAIT" if archived else "TEST FIRST"
    if pid == WINDOWS:
        return "WAIT"
    if pid == PREMIERE:
        return "WAIT"

    if label == "negative":
        return "WAIT"
    if label == "positive":
        return "SAFE ENOUGH to test"
    return "TEST FIRST"
