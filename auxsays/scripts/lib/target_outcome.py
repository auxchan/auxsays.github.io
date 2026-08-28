#!/usr/bin/env python3
"""What does a report say about ONE specific version/build identity?

THE DEFECT THIS CLOSES. Version-only lanes accept a report for a version because the version
STRING occurs in the text -- `exact_version_match` (``patch_collectors/base.py``) and
``collect_obs_reports.exact_version_re`` are numeric-boundary containment and nothing more. So a
report saying "I downgraded to 32.1.2, which doesn't have this problem" was counted as a NEGATIVE
report about 32.1.2: the version the author named as their fix became evidence against it. Seven
such associations were live in ``_data/consensus_evidence.yml`` when this module was written.

WHAT THIS IS NOT. It is not a positive "prove the target is affected" gate. That was measured and
rejected. Of the 351 accepted rows an audit could positively classify as affected, 176 carry no
defect word within 100 characters of their own identity: they state the version only as a
structured environment declaration. In the OBS lane 164 of 188 counted rows declare their version
in the GitHub issue template's ``### OBS Studio Version`` field (130 name it ONLY there), with the
defect prose in a different section. Requiring affected language near the identity would delete
roughly half the legitimate corpus to remove seven bad rows. So this module only ever VETOES, and
only on explicit contradictory language. Silence keeps today's behaviour.

THE CONTRACT, and the real false positive that forced each rule:

  R1  A target the reporter DECLARED running is never vetoed. Their own structured self-report
      outranks ambient prose. Without R1, obs #13495 / #13518 / #13562 were wrongly dropped: each
      declares 32.1.2 in the template and says "cannot reproduce" about the REPRODUCER, not the
      version.
  R2  A cue may not bind across another identity. In "fails ... in 32.2.0, works in 32.1.2",
      `works` must not reach 32.2.0 nor `fails` reach 32.1.2. Applied symmetrically to affected and
      excluding cues so it cannot bias the outcome. Without R2, obs #13708's 32.2.0 -- the version
      the title indicts -- was wrongly dropped.
  R3  An explicit affected statement about the target beats an excluding one (contested -> keep).
      Reports routinely test several versions and declare only one: "the issue occurs in both
      versions", "reproduced with both", "31.0.4: black screen". Without R3, obs #13568 / #13711 /
      #13559 / #13436 / #13606 / #13659 / #13746 were all wrongly dropped -- seven legitimate
      multi-version reports, i.e. the veto would have done more damage than the bug.

Deterministic, offline, no network, no model. Cue lists are deliberately small: they were derived
from measured corpus frequency, where one lemma covers most of each category (`works` 84% of
working phrasings, `revert`/`from`/`previous` 84% of rollback).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# Outcomes. Only AFFECTED and NONE keep a row; the rest are vetoes.
AFFECTED = "affected"
WORKING = "working"
ROLLBACK = "rollback_target"
FIXED = "fixed_in_target"
REFERENCE = "reference_only"
NONE = "no_outcome_language"

VETO_OUTCOMES = frozenset({WORKING, ROLLBACK, FIXED, REFERENCE})

_T = "%T"

# A clause boundary. A cue on the far side of a full stop, semicolon, newline or contrastive
# conjunction is about something else.
_STOP = r"[^.;!?\n]"

_ROLLBACK_CUES: list[tuple[str, str]] = [
    # "downgraded to X", "revert back to X", "went back to X", "staying on X"
    (rf"\b(?:down\s?grad(?:e|ed|ing)?|revert(?:ed|ing)?|roll(?:ed|ing)?\s*back|went\s+back"
     rf"|go(?:ing)?\s+back|fall(?:ing)?\s+back|fell\s+back|stay(?:ed|ing)?|remain(?:ed|ing)?"
     rf"|stick(?:ing)?)\b{_STOP}{{0,40}}?\b(?:back\s+)?(?:to|on|with)\b{_STOP}{{0,25}}?{_T}",
     "rollback_to_target"),
    # "the previous/older/last known good version X"
    (rf"\b(?:previous|older|earlier|last\s+(?:known\s+)?(?:good|working))\s+"
     rf"(?:version|build|install\w*)\b{_STOP}{{0,25}}?{_T}", "previous_version_is_target"),
]

_WORKING_CUES: list[tuple[str, str]] = [
    # "X doesn't have this problem", "X does not exhibit this issue"
    (rf"{_T}{_STOP}{{0,40}}?\b(?:do(?:es)?\s*n[o']?t\s+(?:have|exhibit|show|reproduce)\s+"
     rf"th(?:is|e)\s+(?:problem|issue|bug|behaviou?r)|has\s+no\s+(?:such\s+)?(?:problem|issue))",
     "target_lacks_problem"),
    # "works in X" / "worked as intended on X"
    (rf"\bwork(?:s|ed|ing)?\b{_STOP}{{0,30}}?\b(?:in|on|with|under)\b{_STOP}{{0,15}}?{_T}",
     "works_on_target"),
    # "X works" -- but never "X workaround"/"X workflow", and never a path segment such as
    # ".../obs-studio-32.1.0/work/..." (real: obs #13319, a compile-failure report).
    (rf"{_T}(?![/\-]){_STOP}{{0,25}}?\bwork(?:s|ed|ing)?\b(?!\s*(?:around|flow))", "target_works"),
    # a results table cell: "32.0.4 (working)" / "32.0.4 - ok"
    (rf"{_T}\s*[\(\[\-–:]\s*(?:work|ok|fine|good|no\s+issue)", "target_marked_working"),
    (rf"\bcan(?:no|')?t\s+reproduce|unable\s+to\s+reproduce\b{_STOP}{{0,30}}?{_T}",
     "cannot_reproduce_on_target"),
    (rf"{_T}{_STOP}{{0,25}}?\b(?:is\s+)?(?:not\s+affected|unaffected)\b", "target_not_affected"),
    # "a 32.1.2 log ... showing successful loading" (obs #13692). Requiring the SHOWING verb keeps
    # this off "Built OBS Studio 32.2.1 successfully from source" (obs #13770), which is a build
    # report, not a claim that the version is healthy.
    (rf"{_T}{_STOP}{{0,40}}?\bshow(?:s|ing|ed)?\s+successful\w*", "target_successful"),
]

_FIXED_CUES: list[tuple[str, str]] = [
    (rf"\b(?:fix(?:ed|es)?|resolv(?:ed|es)|patch(?:ed)?)\b{_STOP}{{0,25}}?"
     rf"\b(?:in|by|with|as\s+of)\b{_STOP}{{0,15}}?{_T}", "fixed_in_target"),
]

_REFERENCE_CUES: list[tuple[str, str]] = [
    # "(e.g. 32.2.0)" -- illustrative, not the reporter's version (obs #13693).
    (rf"(?<![A-Za-z])(?:e\.?\s?g\.?|for\s+example|such\s+as)\s*[,:]?\s*\)?\s*{_T}",
     "example_reference"),
]

_AFFECTED_CUES: list[tuple[str, str]] = [
    # a results table cell: "32.1.2 - broken"
    (rf"{_T}\s*[\(\[\-–:]\s*(?:broken|crash|fail|not\s+working|bug|black\s+screen)",
     "target_marked_broken"),
    # "X crashes", "32.1.2 has this behavior", "31.0.4: black screen"
    (rf"{_T}{_STOP}{{0,45}}?\b(?:crash(?:es|ed|ing)?|break(?:s)?|broke(?:n)?|fail(?:s|ed|ing)?"
     rf"|hang(?:s|ing)?|freez(?:e|es|ing)|terminates?|do(?:es)?\s*n[o']?t\s+work|not\s+working"
     rf"|is\s+broken|happens?|occurs?|same\s+(?:behaviou?r|issue|problem)|this\s+behaviou?r"
     rf"|black\s+screen|flicker\w*|ghost\w*|blank\w*)\b", "target_then_failure"),
    # "fails ... in X", "crashes on X" -- the mirror direction, which the build-role cue set lacks
    (rf"\b(?:crash(?:es|ed|ing)?|break(?:s|ing)?|broke(?:n)?|fail(?:s|ed|ing)?|hang(?:s|ing)?"
     rf"|freez(?:e|es|ing)|terminat\w*|regress\w*|reproduc\w*|do(?:es)?\s*n[o']?t\s+work"
     rf"|not\s+working)\b{_STOP}{{0,45}}?\b(?:in|on|with|under|since|after|as\s+of|both)\b"
     rf"{_STOP}{{0,20}}?{_T}", "failure_then_target"),
    # "also tested X with the same behavior"
    (rf"\b(?:also\s+)?tested\b{_STOP}{{0,25}}?{_T}{_STOP}{{0,45}}?"
     rf"\b(?:same|too|as\s+well|also|both)\b", "tested_same_behaviour"),
    (rf"\b(?:still|also)\s+(?:broken|crashes|fails|happens|occurs|present)\b"
     rf"{_STOP}{{0,30}}?{_T}", "still_broken_on_target"),
]

# Any identity of the same shape as the target. Used only by R2, to detect a cue that reaches
# across a DIFFERENT identity; it never selects targets itself.
_NEIGHBOUR_IDENTITY = re.compile(r"(?<![0-9.])\d+(?:\.\d+){1,3}(?![0-9.])")

# Cues whose meaning inverts under negation or cessation. "works in X" is a working claim;
# "stopped working in X" and "no longer works on X" are DEFECT reports -- and
# `collect_obs_reports.CONCRETE_ISSUE_TERMS` already lists those exact phrases as defect
# indicators, so without this the same substring would mean opposite things in two gates of the
# same funnel. Applied ONLY to these bases: `target_lacks_problem` legitimately contains "does
# not have this problem" and must keep firing.
_POLARITY_SENSITIVE = frozenset({"works_on_target", "target_works", "target_successful",
                                 "fixed_in_target"})
_POLARITY_INVERTER = re.compile(
    r"\b(?:stopped|no\s+longer|never|not|n't|ceased|quit|fail(?:s|ed|ing)?\s+to)\b", re.I)


@dataclass(frozen=True)
class Outcome:
    """What the report says about one identity, and the exact text that established it."""

    outcome: str
    basis: str
    excerpt: str

    @property
    def vetoes(self) -> bool:
        return self.outcome in VETO_OUTCOMES


def _spans_another_identity(matched: str, target: str) -> bool:
    """R2: does this match reach across a DIFFERENT identity to find its cue?

    Only an identity of the SAME SHAPE as the target counts. Report bodies are full of dotted
    numbers that are not product versions -- driver revisions ("driver 610.88"), frame rates,
    resolutions -- and treating those as a neighbouring identity silently disables a cue. Matching
    the target's component count keeps "610.88" from shielding "32.1.2" while still stopping
    "32.2.0" from stealing "32.1.2"'s cue.
    """
    components = target.count(".")
    blanked = matched
    for hit in re.finditer(re.escape(target), matched):
        blanked = blanked[:hit.start()] + (" " * (hit.end() - hit.start())) + blanked[hit.end():]
    return any(found != target and found.count(".") == components
               for found in _NEIGHBOUR_IDENTITY.findall(blanked))


def _mask_foreign_numbers(text: str, target: str) -> str:
    """Blank dotted numbers that cannot be a version of this product, preserving offsets.

    Bodies are full of dotted numbers that are not product versions -- "driver 610.88", frame
    rates, resolutions. Their dots are clause boundaries to ``_STOP``, so one of them sitting
    between an identity and its verb silently hides the AFFECTED cue and lets a WORKING cue
    elsewhere win -- i.e. noise deletes evidence. Only tokens with the target's own component
    count survive, so a genuine sibling version still blocks a cue via R2.
    """
    components = target.count(".")
    out = text
    for hit in _NEIGHBOUR_IDENTITY.finditer(text):
        found = hit.group(0)
        if found == target or found.count(".") == components:
            continue
        out = out[:hit.start()] + ("#" * len(found)) + out[hit.end():]
    return out


# How far back to look for a word that inverts a cue's polarity. "stopped working", "no longer
# works" and "still not fixed" all put the inverter BEFORE the cue verb, outside the match.
_POLARITY_LOOKBACK = 28


def _first_hit(text: str, target: str, cues: list[tuple[str, str]]) -> tuple[str, str] | None:
    escaped = re.escape(target)
    scanned = _mask_foreign_numbers(text, target)
    for pattern, basis in cues:
        for match in re.finditer(pattern.replace(_T, escaped), scanned, re.I):
            if _spans_another_identity(match.group(0), target):
                continue
            if basis in _POLARITY_SENSITIVE:
                lead = scanned[max(0, match.start() - _POLARITY_LOOKBACK):match.start()]
                # Only the SAME clause may invert a cue. Without this the lookback reached back
                # over a full stop in obs #13692 -- "CoreAudio fails to load. OBS 32.1.2 log ...
                # showing successful loading" -- and let a statement about 32.2 cancel a working
                # claim about 32.1.2.
                lead = re.split(r"[.;!?\n]", lead)[-1]
                if _POLARITY_INVERTER.search(lead) or _POLARITY_INVERTER.search(match.group(0)):
                    continue
            # Report the ORIGINAL text, never the masked form, so the audit trail is verbatim.
            return basis, " ".join(text[match.start():match.end()].split())[:160]
    return None


def classify_target_outcome(text: str, target: str, declared: Iterable[str] = ()) -> Outcome:
    """What does ``text`` say about ``target``?

    ``declared`` is the identity/identities the reporter structurally declared running -- for a
    GitHub issue template, the answer to its own version question. R1: a declared target is never
    vetoed, because that field IS the author saying "this is what I am on".
    """
    body = str(text or "")
    identity = str(target or "").strip()
    if not identity or identity not in body:
        return Outcome(NONE, "target_not_in_text", "")

    if identity in {str(d or "").strip() for d in declared}:
        return Outcome(AFFECTED, "declared_by_reporter", identity)          # R1

    affected = _first_hit(body, identity, _AFFECTED_CUES)
    if affected is not None:                                                # R3
        return Outcome(AFFECTED, affected[0], affected[1])

    for cues, outcome in ((_ROLLBACK_CUES, ROLLBACK), (_WORKING_CUES, WORKING),
                          (_FIXED_CUES, FIXED), (_REFERENCE_CUES, REFERENCE)):
        hit = _first_hit(body, identity, cues)
        if hit is not None:
            return Outcome(outcome, hit[0], hit[1])

    return Outcome(NONE, "no_outcome_language", "")


def target_is_contradicted(text: str, target: str, declared: Iterable[str] = ()) -> Outcome | None:
    """The Outcome when the report contradicts ``target`` being affected, else ``None``.

    Callers use this as a veto on an already-established version match. Silence -- and any
    affirmative statement -- returns ``None``, so existing acceptance is unchanged.
    """
    outcome = classify_target_outcome(text, target, declared)
    return outcome if outcome.vetoes else None
