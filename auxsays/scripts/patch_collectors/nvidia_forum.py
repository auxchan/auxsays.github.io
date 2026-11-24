#!/usr/bin/env python3
"""Community evidence for NVIDIA's desktop drivers, from the NVIDIA GeForce forum's default views.

THE QUESTION THIS ANSWERS. "Is someone reporting a concrete problem on THIS exact driver, of THIS
family?" GeForce Game Ready and NVIDIA Studio are two products that share version numbers (621.14
and 621.24 each shipped as both, the same day), so a report counts for a family only when the
family is established -- never from the version alone (lib.nvidia_driver_identity).

WHAT IS READ is decided by nvidia_forum_source: the two default views, at most one cycle per 12
hours, shared by both family collectors in one run. This module decides what each comment is.

IDENTITY, IN ORDER (each refusal is stored as an excluded row with its reason, so it is auditable):

1. The comment's OWN text must name a tracked version exactly (the shared matcher, after links and
   quoted lines are removed -- a URL or a quote is not the reporter naming a version). A thread
   title alone never makes a comment a report: the title is not the commenter's words, and a
   "this driver" written after the next driver shipped names nothing. A comment naming no tracked
   version is not a candidate at all.
2. Family (GPT G47 C, lib.nvidia_driver_identity.report_family). A staff feedback thread
   establishes its family only when its TITLE names exactly one driver version AND exactly one
   family, and only for that version: "GeForce GRD 621.24 Feedback Thread" makes a 621.24 comment
   inside it Game Ready, but not a 621.14 comment. A user topic or a community never establishes a
   family. The reporter naming a family establishes it; naming the other family vetoes the thread's;
   naming both establishes nothing. A comment with no established family -- the shared-component
   defects (the SSD-write component both families install) are the measured case -- is stored as
   `driver_family_unassigned` for BOTH products and counted for neither: one report is never two
   family reports.
3. Desktop only. Both products are desktop driver packages; a laptop or notebook report is
   `notebook_driver_not_tracked`, never merged into a desktop record. A first-person notebook ("my
   laptop") is always the reporter's, and so is an unowned one ("another laptop", "a different
   laptop", "other laptop users"). A notebook is someone else's only through a possessive owner ("a
   friend's laptop", "her laptop") or inside an other-machine phrase's description ("works on
   another system with an RTX 4070 Laptop GPU"). Anything else fails closed: a notebook report.
4. The version must be the subject (GPT G44 s4). Named only on a specification line ("Driver:
   621.14", "NVIDIA Driver Version: 621.24", "Using latest drivers 621.14") it is environment, not
   attribution: `driver_version_environment_only`. Named in a sentence where the reporter says they
   cannot tell whether it is the cause: `driver_attribution_disclaimed`. A crash in a driver module
   (nvlddmkm, TDR, LiveKernelEvent) without regression evidence for THIS version -- dated to it, or a
   contrast with a version that works, and nothing saying it began on or also occurs on another
   version -- is investigated, not counted: `driver_module_crash_without_regression_evidence`. A
   post that only says the driver is fine and names no malfunction is not a problem report:
   `positive_report_not_a_problem`.
5. Role. With another tracked version named, silence is not enough: the shared role reading
   (lib.target_outcome) must say the version is the affected one; with none, a version named as
   working, fixed or rolled back to is vetoed (target_is_contradicted).

THEN THE SHARED AUTHORITY, UNCHANGED: base.apply_acceptance_gates (exact version, specific URL,
created on or after the release, concrete problem). No threshold, weight or acceptance rule of this
product's own exists. The report date is the comment's own creation time, never its last activity.
The stored URL is the forum's own link to that one comment, under its thread. A row is keyed on the
comment, so the same comment served again under another thread (a move or a merge) is never a
second row.

PUBLIC TEXT. Names (staff names, @mentions and the display names of every member in the same
responses and the thread's listing entry), e-mail addresses are removed from every stored text, and
links are replaced by a marker. Report titles are the thread's title through the same removal (the
promotion copies them into the record); the raw title is read by thread qualification, the www path
a call stands for and the presentation-only theme reading, never stored as a report title.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from lib import evidence_classification as ec
from lib import nvidia_driver_identity as identity
from lib.method_routing import plan_methods
from lib.target_outcome import AFFECTED, classify_target_outcome, target_is_contradicted
from patch_collectors import base
from patch_collectors import nvidia_forum_source as src
from patch_collectors import runtime_budget as rb

# Module-level so the governed write-authority suite can repoint it (test_collector_write_authority O8b).
ROOT = base.ROOT

PRODUCTS = (identity.GAME_READY, identity.STUDIO)
METHOD_ID = "nvidia_forum_default_views"
SOURCE_TYPE = "nvidia_forum_comment"
SOURCE_NAME = src.PROVENANCE["source_origin"]

# --- text --------------------------------------------------------------------------------------------

_QUOTE_LINE_RE = re.compile(r"^[ \t]*>.*$", re.M)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_STAFF_NAME_RE = re.compile(r"\b[\w.-]+@NVIDIA\b")
_MENTION_RE = re.compile(r"(?<![\w.@])@[A-Za-z0-9_][\w.-]{0,40}")
_URL_RE = re.compile(r"https?://[^\s)\]>]+|\bwww\.[^\s)\]>]+", re.I)


def clean_text(text: Any, names: Iterable[str] = ()) -> str:
    """The commenter's own words: quoted lines dropped, people's names and links removed.

    `names` are the display names of the forum members in the same response (display_names): a
    reply addressing someone by plain name ("I don't know, <name>...") carries no @, so those names
    are removed wherever the text uses them (scrubbable_name says which may be)."""
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = _QUOTE_LINE_RE.sub("", value)
    value = _EMAIL_RE.sub("[email]", value)
    value = _STAFF_NAME_RE.sub("NVIDIA staff", value)
    value = _MENTION_RE.sub("@user", value)
    value = _URL_RE.sub("[link]", value)
    for name in sorted({str(n).strip() for n in names if scrubbable_name(n)}, key=lambda n: (-len(n), n)):
        value = re.sub(rf"(?<![\w@]){re.escape(name)}(?!\w)", "[name]", value, flags=re.I)
    return value.strip()


def display_names(*payloads: Any) -> set[str]:
    """Every forum member's display name in these responses (the `displayName` of each user)."""
    out: set[str] = set()
    stack: list[Any] = list(payloads)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            name = node.get("displayName")
            if isinstance(name, str) and name.strip():
                out.add(name.strip())
            stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            stack.extend(v for v in node if isinstance(v, (dict, list)))
    return out


def scrubbable_name(name: Any) -> bool:
    """May this display name be removed from comment text without changing a decision? Not when it
    is under 3 characters, or when it is (or contains) a driver version, a family, or a word the
    attribution rules below read: such a name stays, the rules keep their input."""
    text = str(name or "").strip()
    if len(text) < 3 or driver_versions_in(text) or identity.families_named(text):
        return False
    return not any(rule.search(text) for rule in _NAME_PROTECTED_RULES)


_DRIVER_VERSION_RE = re.compile(r"(?<![\w.])(\d{3,4}\.\d{2})(?![\w]|\.\d)")


def driver_versions_in(text: Any) -> set[str]:
    """Every driver-version-shaped number (NNN.NN) the text names."""
    return set(_DRIVER_VERSION_RE.findall(str(text or "")))


def occurrences(text: str, version: str) -> list[tuple[int, int]]:
    """Every position the shared exact matcher accepts as this version."""
    out: list[tuple[int, int]] = []
    offset = 0
    while offset <= len(text):
        matched, _v, _basis, start, end = base.exact_version_match_span(text[offset:], version)
        if not matched:
            break
        out.append((offset + start, offset + end))
        offset += end
    return out


# --- thread qualification ------------------------------------------------------------------------------

def thread_profile(title: str, staff_author: bool) -> dict[str, Any]:
    """What a thread's TITLE establishes. A staff thread is patch-specific for a family only when
    the title names exactly one driver version and exactly one family."""
    versions = driver_versions_in(title)
    families = identity.families_named(title)
    patch_family = None
    title_version = None
    if staff_author and len(versions) == 1 and len(families) == 1:
        (title_version,) = versions
        (patch_family,) = families
    return {"title_versions": sorted(versions), "staff": bool(staff_author),
            "patch_family": patch_family, "title_version": title_version}


# --- attribution ---------------------------------------------------------------------------------------

_NOTEBOOK_RE = re.compile(r"\b(?:laptops?|notebooks?|max-q|mobile\s+gpu)\b", re.I)
# The reporter's OWN notebook: a first-person possessive governing the notebook's noun phrase ("my
# laptop", "My RTX 4060 laptop", "on our notebook"). Always a notebook report, whatever else the
# sentence says ("Like other users here, my laptop crashes ..."). "my wife's laptop" is not first
# person: the possessive belongs to someone else.
_OWN_NOTEBOOK_LEAD_RE = re.compile(r"\b(?:my|our)\s+(?:(?![\w.-]+'s\b)[\w.+-]+\s+){0,4}\Z", re.I)
# A notebook named as SOMEONE ELSE's machine says nothing about the reporter's own install, in TWO
# shapes only, and everything else fails closed (a notebook report, never counted for a desktop
# record):
#   1. the notebook word owned by another PERSON, through a possessive ("a friend's laptop", "my
#      wife's laptop", "his/her laptop", "their laptop");
#   2. an other-machine phrase -- "another"/"a different"/a possessive qualifying a machine noun --
#      whose own description holds the notebook mention, AND the same sentence says, immediately
#      before the phrase, that it works or runs on (or with) that machine ("works on another system
#      with an RTX 4070 Laptop GPU", comment 3633451).
# "another laptop", "a different laptop", "other laptop users" are NOT shape 1: nothing says whose
# laptop it is, and it is usually the reporter's own ("Another laptop user here: since 621.14 ...").
# Nor is a described other machine without that works-on cue shape 2: "On my second system with an
# RTX 4070 Laptop GPU, since 621.14 every game crashes" is the reporter's own notebook.
# An "other" or "different" qualifying anything else ("other users", "different games") is neither
# shape and turns nothing off.
_POSSESSIVE_OWNER = (r"(?:friend'?s|wife'?s|husband'?s|partner'?s|brother'?s|sister'?s|son'?s|daughter'?s"
                     r"|his|her|their)")
_OTHER_OWNER = rf"(?:another|other|second|different|{_POSSESSIVE_OWNER})"
_MACHINE_NOUN = r"(?:systems?|pcs?|machines?|computers?|rigs?|devices?|builds?|laptops?|notebooks?)"
_OTHER_MACHINE_RE = re.compile(rf"\b{_OTHER_OWNER}\s+{_MACHINE_NOUN}\b", re.I)
_POSSESSIVE_PHRASE_RE = re.compile(rf"{_POSSESSIVE_OWNER}\s", re.I)
# What may sit between that machine noun and the notebook mention: a short description of the
# same machine, introduced as one ("with an RTX 4070", "running a", "that has the") and nothing
# else -- "another PC but the laptop crashes" names two machines.
_MACHINE_DESCRIPTION_RE = re.compile(
    r"\A\s+(?:with|using|running|that\s+has|which\s+has|having)\s+(?:an?\s+|the\s+)?"
    r"(?:[\w+-]+\s+){0,4}\Z", re.I)
# The works-on cue that must end the sentence's text before that other-machine phrase ("It works on
# another system ...", "runs fine with a different PC ...").
_WORKS_ON_RE = re.compile(
    r"\b(?:works?|worked|working|runs?|ran|running)\s+(?:fine\s+|well\s+|perfectly\s+)?(?:on|with)\s+"
    r"(?:an?\s+|the\s+)?\Z", re.I)

# A specification line names a version as environment: a short label (driver, driver version, ver.)
# immediately before the number, inside its own comma/sentence segment, with no defect word in the
# segment on either side. A label with a colon ("Driver: 621.14") is a field whatever follows in
# another segment; a bare label ("Using latest drivers 621.14", "driver 621.24" in a comma list) is a
# field only when its whole segment is short -- "Game Ready Driver 621.14 fucks up my system" is a
# sentence about the driver, not a field.
_SEGMENT_BREAK_RE = re.compile(r"[,;|\n]|(?<![Vv]er)\.(?=\s|$)|\s[-–—]\s")
_ENV_COLON_LABEL_RE = re.compile(
    r"\b(?:drivers?(?:\s+ver(?:sion|\.)?)?|ver(?:sion|\.)?)\s*[:=]\s*(?:nvidia\s+|geforce\s+)?v?\s*\Z", re.I)
_ENV_BARE_LABEL_RE = re.compile(
    r"\b(?:drivers?(?:\s+ver(?:sion|\.)?)?|ver(?:sion|\.)?)\s*(?:nvidia\s+|geforce\s+)?v?\s*\Z", re.I)
_DEFECT_WORDS = (r"crash\w*|freez\w*|froze|hang\w*|black|blank|flicker\w*|stutter\w*|broke\w*|break\w*"
                 r"|bug\w*|issue\w*|problem\w*|regress\w*|fail\w*|artifact\w*|tdrs?|bsod|error\w*|corrupt\w*"
                 r"|lag\w*|slow\w*|drops?|capped|locked|affected|bad|worse|glitch\w*|fuck\w*|mess\w*"
                 r"|screw\w*|ruin\w*|kill\w*|not\s+work\w*|doesn'?t\s+work|won'?t|can'?t|cannot")
_DEFECT_RE = re.compile(rf"\b(?:{_DEFECT_WORDS})\b", re.I)
# A field is environment only while nothing in its segment ties the version to a problem or a change.
_ENV_BREAK_RE = re.compile(rf"\b(?:{_DEFECT_WORDS}|caus\w*|introduc\w*|since|after|still|new)\b", re.I)
_ENV_MAX_WORDS = 6

# G44 s4 row 4: a crash in an NVIDIA driver module, without RELEASE-SPECIFIC regression evidence, is
# investigated, never counted automatically. The evidence must concern the record's own version
# (regression_evidence_for): the reporter dating the problem to that version, a contrast with a
# version that works, or the template's regression field -- and a text that says the problem began on
# another version, or also occurs on another one, has none (comment 3634344: "black screen after
# upgrading to 621.01 ... tried 617.42 but still happened ... clean installed 621.24, still do happen").
_MODULE_CRASH_RE = re.compile(
    r"\b(?:nvlddmkm(?:\.sys)?|video_tdr_failure|livekernelevent|tdrs?|0x116|0x141|0x1b8|bug\s*check)\b", re.I)
# Dating cues. Each must be followed, within a short run of plain words, by the version it dates.
_ONSET_CUE_RE = re.compile(
    r"\b(?:since|after|when)\s+(?:(?:i|we)\s+)?(?:updat\w*|upgrad\w*|install\w*|switch\w*|mov\w*|went|going)\b"
    r"|\b(?:since|after)\s+(?:the\s+)?(?:update|upgrade|installation)\s+(?:to|of)\b"
    r"|\bnew\s+(?:in|with|since)\b|\b(?:started|began|begun|appeared)\s+(?:with|on|after|since|in)\b"
    r"|\b(?:broken|affected|bad)\s*(?:driver|version)?\s*[:=]", re.I)
_ONSET_MAX_GAP_WORDS = 8
_ONSET_GAP_RE = re.compile(r"[\w\s.'+-]*")
# ... or the version named first: "621.14 introduced / broke / caused ...".
_ONSET_FOLLOW_RE = re.compile(
    r"\s*(?:(?:driver|update|version)\s+)?(?:introduced|broke|brought|caused|causes|triggered|started)\b", re.I)
# Dating to "the update" with no version: release-specific only when no other version is named.
_IMPLICIT_ONSET_RE = re.compile(
    r"\b(?:since|after)\s+(?:updating|upgrading|installing"
    r"|the\s+(?:latest\s+|last\s+|new\s+|recent\s+)?(?:driver\s+)?(?:update|upgrade)|the\s+new\s+driver)\b", re.I)
# A contrast with a version that works: a rollback, a last working driver, a version not affected,
# or the template's own regression field.
_CONTRAST_RE = re.compile(
    r"\b(?:roll(?:ed|ing|s)?\s*back|revert\w*|downgrad\w*)\b"
    r"|\b(?:went|go(?:ing|es)?)\s+back\s+to\s+(?:the\s+|an?\s+)?(?:(?:older|previous|old|last|earlier)\s+)?"
    r"(?:drivers?\b|versions?\b|v?\d{3,4}\.\d{2})"
    r"|\bnot\s+affected\b|\bunaffected\b|\b(?:is|was|runs?|ran)\s+clean\b|\bwas\s+(?:fine|stable)\b"
    r"|\blast\s+(?:known[\s-]+)?(?:good|working|stable)\b|\bdriver\s+regression\s*[:=]\s*yes\b", re.I)
# The problem persisting on another driver ("tried 617.42 but still happened", "same on older
# drivers", "rolled back, same crash") ...
_PERSISTS_RE = re.compile(r"\b(?:still|also|too|same|as\s+well|even\s+(?:on|with)|again|persist\w*)\b", re.I)
_OLDER_DRIVER_RE = re.compile(
    r"\b(?:older|previous|earlier|prior|past|other|old)\s+(?:\w+\s+)?(?:drivers?|versions?|releases?)\b"
    r"|\b(?:roll(?:ed|ing|s)?\s*back|revert\w*|downgrad\w*)\b", re.I)
# ... unless the same sentence says that driver works ("rolling back to 610.88 fixes it"). Negated
# forms ("still not working", "doesn't fix it") are not that.
_FIXED_RE = re.compile(
    r"(?<!not\s)(?<!n't\s)(?<!never\s)(?<!no\slonger\s)"
    r"\b(?:fix(?:es|ed)?|fine|stable|works?|worked|working|resolv\w*|solv\w*|gone|unaffected"
    r"|no\s+(?:more\s+)?(?:issues?|problems?|crash\w*))\b", re.I)

# A post that only says the driver is fine is not a problem report, whatever the shared concreteness
# vocabulary makes of it ("Installed 621.24 over 591, clean install ... No issues at all": the word
# "install" is in that vocabulary). Only when it names no malfunction at all.
_POSITIVE_RE = re.compile(
    r"\b(?:no\s+(?:issues?|problems?)(?:\s+at\s+all)?|zero\s+issues?"
    r"|(?:looks|seems|is)\s+(?:like\s+)?an?\s+(?:good|great|solid|stable)\s+driver"
    r"|(?:works?|working|runs?|running|seems?|performs?)\s+(?:fine|great|perfectly|flawless\w*|very\s+well|well))\b",
    re.I)

_SENTENCE_BREAK_RE = re.compile(r"[!?;\n]|\.(?=\s|$)")
_DISCLAIMER_RE = re.compile(
    r"\b(?:cannot|can't|can not|not able to|unable to)\s+(?:confirm|tell|say|determine)\s+(?:whether|if)\b"
    r"|\bnot\s+(?:an?\s+)?(?:issue|problem|bug)\s+(?:specific|related|limited)\s+to\b"
    r"|\bnot\s+sure\s+(?:whether|if)\b", re.I)

# Display names that collide with the vocabulary these rules read are never removed from a comment.
_NAME_PROTECTED_RULES: tuple[re.Pattern[str], ...] = (
    _NOTEBOOK_RE, _OTHER_MACHINE_RE, re.compile(r"\b(?:my|our|drivers?|ver(?:sion)?|game|ready|studio)\b", re.I),
    _DEFECT_RE, _ENV_BREAK_RE, _MODULE_CRASH_RE, _ONSET_CUE_RE, _IMPLICIT_ONSET_RE, _CONTRAST_RE,
    _PERSISTS_RE, _OLDER_DRIVER_RE, _FIXED_RE, _POSITIVE_RE, _DISCLAIMER_RE)


def _bounds(text: str, start: int, end: int, pattern: re.Pattern[str]) -> tuple[int, int]:
    lo = 0
    for hit in pattern.finditer(text, 0, start):
        lo = hit.end()
    nxt = pattern.search(text, end)
    return lo, (nxt.start() if nxt else len(text))


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def is_environment_occurrence(text: str, start: int, end: int) -> bool:
    lo, hi = _bounds(text, start, end, _SEGMENT_BREAK_RE)
    prefix = re.sub(r"[*`_]", " ", text[lo:start])
    prefix = re.sub(r"\A[\s•#>-]+", "", prefix)
    suffix = text[end:hi]
    if _ENV_BREAK_RE.search(prefix) or _ENV_BREAK_RE.search(suffix):
        return False
    if _ENV_COLON_LABEL_RE.search(prefix):
        return _words(prefix) <= _ENV_MAX_WORDS
    if _ENV_BARE_LABEL_RE.search(prefix):
        return _words(prefix) + _words(suffix) <= _ENV_MAX_WORDS
    return False


def _notebook_is_other_machine(text: str, sentence_start: int, start: int, end: int) -> bool:
    """Is this notebook mention inside an other-machine phrase of its own sentence?"""
    for phrase in _OTHER_MACHINE_RE.finditer(text, sentence_start, end):
        if phrase.start() <= start and phrase.end() >= end:
            # The notebook word IS the phrase's machine: someone else's only through a possessive
            # owner ("a friend's notebook", "her laptop"); "another laptop" is the reporter's.
            if _POSSESSIVE_PHRASE_RE.match(phrase.group(0)):
                return True
            continue
        if phrase.end() <= start and _MACHINE_DESCRIPTION_RE.match(text[phrase.end():start]) \
                and _WORKS_ON_RE.search(text[sentence_start:phrase.start()]):
            return True                     # "works on another system with an RTX 4070 Laptop GPU"
    return False


def own_machine_is_notebook(text: str) -> bool:
    """Does the reporter's own machine look like a notebook? Every notebook mention counts unless it
    is plainly another machine's; a first-person one ("my laptop") always counts."""
    for hit in _NOTEBOOK_RE.finditer(text):
        lo, _hi = _bounds(text, hit.start(), hit.end(), _SENTENCE_BREAK_RE)
        if _OWN_NOTEBOOK_LEAD_RE.search(text[lo:hit.start()]):
            return True
        if not _notebook_is_other_machine(text, lo, hit.start(), hit.end()):
            return True
    return False


def _sentences_naming(text: str, version: str) -> list[tuple[int, int, int, int]]:
    """(sentence start, sentence end, occurrence start, occurrence end) for every exact occurrence."""
    return [(*_bounds(text, s, e, _SENTENCE_BREAK_RE), s, e) for s, e in occurrences(text, version)]


def _onset_names(text: str, version: str) -> bool:
    """Does the text date the problem to `version` itself? "since updating to V", "after upgrading
    from X to V", "new in V", "started with V", "Broken: V", or "V introduced/broke/caused ...".
    A version the reporter updated FROM is not the one they date the problem to."""
    for lo, _hi, start, end in _sentences_naming(text, version):
        lead = text[lo:start]
        for cue in _ONSET_CUE_RE.finditer(lead):
            gap = lead[cue.end():]
            if not _ONSET_GAP_RE.fullmatch(gap) or len(re.findall(r"[\w.'+-]+", gap)) > _ONSET_MAX_GAP_WORDS \
                    or re.search(r"\bfrom\s+(?:(?:driver|version)\s+|v)?\Z", gap, re.I):
                continue
            # Only a "from X" may sit between the cue and the version; any other version there is
            # the one the cue is about.
            if all(re.search(r"\bfrom\s+(?:(?:driver|version)\s+|v)?\Z", gap[:m.start()], re.I)
                   for m in _DRIVER_VERSION_RE.finditer(gap)):
                return True
        if _ONSET_FOLLOW_RE.match(text, end):
            return True
    return False


def _fixed_in(sentence: str) -> bool:
    return bool(_FIXED_RE.search(sentence))


def _problem_predates_or_persists(text: str, version: str) -> bool:
    """Does the text say the problem began on another version, or also occurs on another (older)
    one? Then nothing in it is release-specific to `version`."""
    for other in sorted(driver_versions_in(text) - {version}):
        if _onset_names(text, other):
            return True                     # "black screen after upgrading to 621.01"
        for lo, hi, _s, _e in _sentences_naming(text, other):
            sentence = text[lo:hi]
            if _PERSISTS_RE.search(sentence) and not _fixed_in(sentence):
                return True                 # "I tried 617.42 but still happened"
    for sentence in _SENTENCE_BREAK_RE.split(text):
        if _OLDER_DRIVER_RE.search(sentence) and _PERSISTS_RE.search(sentence) and not _fixed_in(sentence):
            return True                     # "happened on older drivers too", "rolled back, same crash"
    return False


def regression_evidence_for(text: str, version: str) -> bool:
    """Release-specific regression evidence for THIS version (G44 s4 row 4): the reporter dates the
    problem to it, contrasts it with a version that works (a rollback that fixes it, a last working
    driver, a version not affected), or fills the template's regression field -- and nothing says
    the problem began on, or also occurs on, another version."""
    if _problem_predates_or_persists(text, version):
        return False
    if _onset_names(text, version):
        return True
    if not (driver_versions_in(text) - {version}) and _IMPLICIT_ONSET_RE.search(text):
        return True                         # "since the update", with no other version named
    return bool(_CONTRAST_RE.search(text))


def module_crash_without_regression(text: str, version: str) -> bool:
    return bool(_MODULE_CRASH_RE.search(text)) and not regression_evidence_for(text, version)


def positive_only(text: str) -> bool:
    """Says the driver is fine, and -- the positive phrases set aside -- names no problem at all."""
    if not _POSITIVE_RE.search(text):
        return False
    return not _DEFECT_RE.search(_POSITIVE_RE.sub(" ", text))


def attribution_disclaimed(text: str, spans: list[tuple[int, int]]) -> bool:
    for start, end in spans:
        lo, hi = _bounds(text, start, end, _SENTENCE_BREAK_RE)
        if _DISCLAIMER_RE.search(text[lo:hi]):
            return True
    return False


def family_reason(product_id: str, own: str, version: str, thread: dict[str, Any]) -> str:
    """'' when the family is established as `product_id`; else why not."""
    thread_family = thread.get("patch_family") if thread.get("title_version") == version else None
    named = identity.families_named(own)
    family = identity.report_family(own, thread_family)
    if family == product_id:
        return ""
    if family is not None:
        return "driver_family_is_other"
    if len(named) > 1:
        return "driver_family_both_named"
    if named and thread_family:
        return "driver_family_conflicts_with_thread"
    return "driver_family_unassigned"


# --- classification (presentation only, never acceptance) ----------------------------------------------

_THEME_RULES: tuple[ec.ThemeRule, ...] = (
    ec.ThemeRule("excessive disk writes", "storage", "high", "disk_writes",
                 re.compile(r"\b(?:(?:ssd|disk|nvme|drive)\s+writ\w*|writ\w*\s+(?:to\s+)?(?:the\s+)?(?:ssd|disk|nvme)"
                            r"|nvlog|nvtopps|gigabytes?\s+(?:per|an?)\s+hour)\b", re.I)),
    ec.ThemeRule("crash or driver reset", "system stability", "high", "crash",
                 re.compile(r"\b(?:crash\w*|tdr|bsod|blue\s+screen|nvlddmkm|freez\w*|froze|hang(?:s|ing)?"
                            r"|watchdog|reboots?|restarts?)\b", re.I), negatable=True),
    ec.ThemeRule("black screen or display loss", "display output", "high", "display",
                 re.compile(r"\b(?:black\s+screen\w*|blank\s+screen|no\s+signal|not\s+detected"
                            r"|monitor\w*\s+(?:goes|go|went|stays?)\s+black|won'?t\s+wake)\b", re.I),
                 negatable=True),
    ec.ThemeRule("flicker or wrong colors", "rendering", "medium", "visual",
                 re.compile(r"\b(?:flicker\w*|artifact\w*|washed\s+out|wrong\s+colou?rs?|incorrect\s+colou?rs?"
                            r"|corrupt\w*|raises?\s+black)\b", re.I), negatable=True),
    ec.ThemeRule("performance or stutter", "performance", "medium", "performance",
                 re.compile(r"\b(?:stutter\w*|fps\s+drops?|frame\s*drops?|slow\w*|lag\w*|hitch\w*"
                            r"|performance)\b", re.I)),
    ec.ThemeRule("power or thermal limit", "power and thermals", "medium", "power",
                 re.compile(r"\b(?:power\s+(?:limit\w*|capped|locked)|watts?\b|temperature\w*|thermal)\b", re.I)),
)
ec.validate_rules(_THEME_RULES)


def classify(title: str, text: str) -> tuple[str, str, str, str]:
    platform = ec.resolve_platform(text, heading=title or "").label
    verdict = ec.score_themes(title or "", text, _THEME_RULES)
    if verdict is None:
        return "", "", platform, ""
    return verdict.theme, verdict.area, platform, verdict.severity


# --- one decision per (product, record, comment) -------------------------------------------------------

def _iso(stamp: Any) -> str:
    try:
        return datetime.fromtimestamp(int(stamp), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def evaluate_comment(product_id: str, record: base.PatchRecord, tracked_versions: set[str],
                     thread: dict[str, Any], item: dict[str, Any], captured_at: str) -> dict[str, Any] | None:
    """The evidence row for one comment and one record, or None when the comment does not name the
    record's version (never a candidate)."""
    version = str(record.update_version or "")
    own = str(item.get("own_text") or "")
    spans = occurrences(own, version)
    if not spans:
        return None
    reason = family_reason(product_id, own, version, thread)
    if not reason and own_machine_is_notebook(own):
        reason = "notebook_driver_not_tracked"
    if not reason and all(is_environment_occurrence(own, s, e) for s, e in spans):
        reason = "driver_version_environment_only"
    if not reason and attribution_disclaimed(own, spans):
        reason = "driver_attribution_disclaimed"
    if not reason and module_crash_without_regression(own, version):
        reason = "driver_module_crash_without_regression_evidence"
    if not reason and positive_only(own):
        reason = "positive_report_not_a_problem"
    if not reason:
        # Another TRACKED version of this product named too: silence is not enough, the shared role
        # reading must say this one is the affected one (the Acrobat shared-build rule). Untracked
        # versions are left to the single-version veto, as every other collector does.
        named = {v for v in tracked_versions if v != version and occurrences(own, v)}
        if named:
            outcome = classify_target_outcome(own, version)
            if outcome.outcome != AFFECTED:
                reason = (f"version_role_{outcome.outcome}" if outcome.vetoes
                          else "multiple_tracked_versions_named")
        else:
            contradiction = target_is_contradicted(own, version, set())
            if contradiction is not None:
                reason = f"version_role_{contradiction.outcome}"

    title = str(thread.get("title") or "")
    # The STORED title goes through the same name removal as the comment text (the promotion copies
    # it into the record's source_title): a user topic's title can carry a member's @handle or display
    # name. `names` are the forum members of the topic, its comments and its listing entry
    # (_read_thread). The raw title stays the input of thread_profile and of the presentation-only
    # theme reading below, so no decision reads the scrubbed text.
    stored_title = clean_text(title, thread.get("names") or ())
    theme, area, platform, severity = classify(title, own)
    start, end = spans[0]
    provenance = base.match_provenance([("report_text", own)], start, end)
    row = base.make_evidence_row(
        product_id=product_id,
        update_version=version,
        source_type=SOURCE_TYPE,
        source_name=SOURCE_NAME,
        source_url=str(item.get("url") or ""),
        parent_title=stored_title,
        report_title=stored_title,
        report_text=own,
        captured_at=captured_at,
        # The comment's own creation time. lastActivityStamp and updatedStamp move with replies,
        # votes and edits and are never read as the report date.
        source_date=_iso(item.get("created")),
        target_release_date=base.date_part(record.update_published_at or ""),
        patch_version_matched=True,
        matched_version=version,
        match_basis="exact_version_text",
        counted=False,
        exclusion_reason=reason or None,
        issue_theme=theme,
        workflow_area=area,
        platform=platform,
        severity=severity,
        sentiment="",
        # Keyed on the COMMENT, never on the thread: comment ids are forum-wide, and a moderator's
        # move or merge serves the same comment under another topic. The stored row (with the URL
        # of the thread it was first seen under) wins; the second sighting is "already held".
        row_id=f"{product_id}-{base.slug(version)}-nvidia-forum-comment-{int(item['comment_id'])}",
        matched_text=provenance.get("matched_text", ""),
        matched_field=provenance.get("matched_field", ""),
        matched_context=provenance.get("matched_context", ""),
    )
    if reason:
        row["counted"] = False
        row["exclusion_reason"] = reason
        return base.normalize_evidence_row(row)
    gated = base.apply_acceptance_gates(row, report_text=own)
    # DERIVED, NOT INVENTED (the Teams rule): a counted row has passed the concreteness gate, and the
    # promotion refuses a counted row without a sentiment while reconciliation counts it.
    if gated.get("counted") is True:
        gated["sentiment"] = "negative"
    return base.normalize_evidence_row(gated)


# --- the cycle: one per process, shared by both family collectors --------------------------------------

_CYCLE: dict[str, Any] | None = None
# Both families' records, read once per process: every scan parses every generated record's front
# matter, and the two collectors of one run would otherwise scan the corpus eight times.
_RECORDS: dict[str, list[base.PatchRecord]] | None = None


def reset_cycle() -> None:
    """Forget this process's cycle. Tests only; production runs one cycle per process."""
    global _CYCLE, _RECORDS
    _CYCLE = None
    _RECORDS = None


def _records() -> dict[str, list[base.PatchRecord]]:
    global _RECORDS
    if _RECORDS is None:
        _RECORDS = {pid: base.generated_records(pid) for pid in PRODUCTS}
    return _RECORDS


def state_title(title: str, staff: bool, names: Iterable[str]) -> str:
    """The title a thread's state entry keeps. A staff thread's raw title (thread_profile reads it
    back to re-establish a remembered feedback thread's family); a user topic's title through the
    same name removal as its stored evidence title (nothing reads it back for a decision)."""
    return title if staff else clean_text(title, names)


def _items_for(thread: dict[str, Any], topic: dict[str, Any], comments: list[dict[str, Any]],
               community_id: int, community_slug: str, names: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Every user-authored, visible comment the default view shows, as candidates. Every forum
    member named in the topic and comments responses (and the listing entry: `names`, from
    _read_thread) is removed from each comment's text."""
    topic_id = int(topic["id"])
    topic_slug = src.forum_slug(topic.get("title"))
    names = set(names) if names is not None else display_names(topic, comments)
    out: list[dict[str, Any]] = []

    def add(comment: dict[str, Any], own: str) -> None:
        if src.is_staff(comment.get("user")) or comment.get("isOfficialReply") == 1 or not src.visible(comment):
            return
        out.append({"comment_id": int(comment["id"]), "created": int(comment["createdStamp"]),
                    "own_text": clean_text(own, names),
                    "url": src.comment_url(community_id, community_slug, topic_id, topic_slug, int(comment["id"]))})

    first = topic.get("firstComment") or {}
    if not thread["staff"] and isinstance(first.get("id"), int) and isinstance(first.get("createdStamp"), int) \
            and isinstance(first.get("body"), str):
        # The opening post of a user topic: its title IS the author's own words.
        add(first, f"{topic.get('title') or ''}\n{first.get('body') or ''}")
    for comment in comments:
        add(comment, str(comment.get("body") or ""))
        for reply in comment.get("comments") or []:
            add(reply, str(reply.get("body") or ""))
    return out


def _select_threads(listings: list[tuple[int, str, dict[str, Any]]], state: dict[str, Any],
                    versions: set[str]) -> list[dict[str, Any]]:
    """Threads to read this cycle, best first.

    1. Staff patch-specific threads: listed now, remembered from an earlier listing (a feedback
       thread stays relevant after it is unpinned), or a seed not read yet. Newest first.
    2. User topics whose title names a tracked version, while the community's default listing
       shows them (newest activity first). A user topic READ before that dropped out of the listing
       is not re-read; it stays remembered, and its window is compared again when it reappears.
    3. Owed work (GPT G61 Q5): a thread an earlier cycle deferred -- the thread cap, the request
       ceiling or the time budget reached it first -- is selected again from the state file with
       its pending deferral, even when the listing no longer shows it and even when it was never
       read (a seed whose title is not known yet), until it is read or invalidated (run_cycle).
    A thread is tracked only if its title names a version a record exists for.

    PRIORITY, deterministic: owed work first, longest waiting first (its `queued_at`: when it was
    first deferred, or when a failed read of it sent it back to the end); then everything else in
    the order of 1 and 2; ties by that order, then by topic id. So a deferred thread is never
    overtaken by a thread that was deferred after it, or by a thread that arrived after it, and a
    thread the cap never reaches rotates to the front instead of starving. This orders the work
    only: MAX_THREADS_PER_CYCLE and MAX_REQUESTS_PER_CYCLE are unchanged.

    A QUARANTINED thread (GPT G62 R1) is never selected, by any path, until a reviewed change
    releases it. A queued thread the listing does not show this cycle, other than a seed never read
    (its title not known yet), is marked `per_thread_failures`: a failure of its own views is handled as that thread's
    (_read_thread), so it cannot stop the cycle for every other thread. A listed thread and a seed
    never read keep the stops every thread had before the queue existed."""
    known: dict[int, dict[str, Any]] = {}
    for community_id, community_slug, topic in listings:
        title = str(topic.get("title") or "")
        profile = thread_profile(title, src.is_staff(topic.get("user")))
        if not set(profile["title_versions"]) & versions:
            continue
        tid = int(topic["id"])
        known[tid] = {"topic_id": tid, "community_id": community_id, "community_slug": community_slug,
                      "title": title, "listed_activity": int(topic["lastActivityStamp"]),
                      "created": int(topic.get("createdStamp") or 0),
                      # Removed from the stored evidence title; never written to the state file.
                      "listing_names": sorted(display_names(topic)), **profile}
    for tid_text, entry in (state.get("threads") or {}).items():
        tid = int(tid_text)
        profile = thread_profile(str(entry.get("title") or ""), bool(entry.get("staff")))
        if tid in known or not profile["patch_family"] or not set(profile["title_versions"]) & versions:
            continue
        known[tid] = {"topic_id": tid, "community_id": int(entry.get("community_id") or 0),
                      "community_slug": str(entry.get("community_slug") or ""),
                      "title": str(entry.get("title") or ""), "listed_activity": None,
                      "created": int(entry.get("created") or 0), **profile}
    for tid_text, entry in (state.get("threads") or {}).items():
        tid = int(tid_text)
        if tid in known or not src.is_owed(entry):
            continue
        title = str(entry.get("title") or "")
        profile = thread_profile(title, bool(entry.get("staff")))
        if title and not set(profile["title_versions"]) & versions:
            continue                        # owed for a record outside this (targeted) run: kept
        known[tid] = {"topic_id": tid, "community_id": int(entry.get("community_id") or 0),
                      "community_slug": str(entry.get("community_slug") or ""), "title": title,
                      "listed_activity": None, "created": int(entry.get("created") or 0), **profile,
                      "seed": not title}
    slugs = dict(src.COMMUNITIES)
    seeds_read = {int(t) for t in state.get("seeds_read") or []}
    for community_id, tid in src.SEED_THREADS:
        if tid not in known and str(tid) not in (state.get("threads") or {}) and tid not in seeds_read:
            known[tid] = {"topic_id": tid, "community_id": community_id,
                          "community_slug": slugs.get(community_id, ""), "title": "", "listed_activity": None,
                          "created": 0, "title_versions": [], "staff": False, "patch_family": None,
                          "title_version": None, "seed": True}
    threads = state.get("threads") or {}
    known = {tid: thread for tid, thread in known.items() if not src.is_quarantined(threads.get(str(tid)))}
    listed = {int(topic["id"]) for _community_id, _community_slug, topic in listings}
    for tid, thread in known.items():
        entry = threads.get(str(tid))
        if src.is_owed(entry):
            marker = entry["deferred"]
            thread["owed_since"] = str(marker.get("queued_at") or marker.get("first_deferred_at") or "")
            # Not a seed never read: one known only by its id, its title not learnt yet.
            thread["per_thread_failures"] = tid not in listed and not thread.get("seed")
    return sorted(known.values(), key=lambda t: (
        0 if t.get("owed_since") is not None else 1, str(t.get("owed_since") or ""),
        0 if (t.get("patch_family") or t.get("seed")) else 1,
        -int(t.get("created") or 0) if (t.get("patch_family") or t.get("seed")) else -int(t.get("listed_activity") or 0),
        -int(t["topic_id"])))


def run_cycle(context: base.CollectorContext, versions: set[str], *, keep_versions: set[str] | None = None,
              now: datetime | None = None) -> dict[str, Any]:
    """This process's forum cycle (network, at most once). Returns what both collectors read.

    `versions` are the records this run walks (a targeted run narrows them); `keep_versions` are all
    tracked records, so a targeted run never forgets the other threads it remembers."""
    global _CYCLE
    if _CYCLE is not None:
        return _CYCLE
    current = now or datetime.now(timezone.utc)
    cycle: dict[str, Any] = {"stop": "", "stop_status": "", "detail": "", "skipped": "", "threads": [],
                             "deferred": [], "invalidated": [], "quarantined": [], "released": [],
                             "queue": None, "requests": 0, "state": None, "saved": False, "ran": False,
                             "at": current.replace(microsecond=0).isoformat().replace("+00:00", "Z")}
    _CYCLE = cycle
    try:
        state = src.load_state()
    except src.SchemaIntegrityStop as exc:
        cycle.update(stop="schema_changed", stop_status="broken", detail=str(exc))
        return cycle
    cycle["state"] = state
    # A reviewed change's quarantine releases (GPT G62 R1), applied whenever the state is loaded; a
    # cycle that saves the state file keeps them (and their log).
    cycle["released"] = src.apply_quarantine_releases(state, cycle["at"])
    cycle["queue"] = queue_status(state, current)
    suspended = src.suspension(state, current)
    if suspended:
        cycle.update(stop="access_refused", stop_status="blocked", detail=suspended)
        return cycle
    if not versions:
        cycle["skipped"] = "no_tracked_records"
        return cycle
    if not src.cycle_due(state, current):
        cycle["skipped"] = "cadence"
        return cycle

    transport = src.Transport(state)
    cycle["ran"] = True
    read: list[dict[str, Any]] = []
    refused: src.AccessRefused | None = None
    try:
        policies = src.read_robots(transport)
        listings: list[tuple[int, str, dict[str, Any]]] = []
        for community_id, community_slug in src.COMMUNITIES:
            for url in src.community_view_urls(community_id):
                src.check_robots(policies, url, f"{src.WWW_FORUM_PATH}/{community_slug}/{community_id}/")
                payload = transport.get_json(url)
                listings.extend((community_id, community_slug, topic)
                                for topic in src.listing_topics(payload, "a community listing"))
        candidates = _select_threads(listings, state, versions)
        for thread in candidates:
            reason = _deferral_reason(len(read), transport)
            if reason:
                cycle["deferred"].append(dict(thread, deferral_reason=reason))
                continue
            stored = (state.get("threads") or {}).get(str(thread["topic_id"])) or {}
            # Read before (an empty window is still a read window) and no activity since: no request.
            if thread.get("listed_activity") is not None and stored.get("last_activity") is not None \
                    and int(stored["last_activity"]) == thread["listed_activity"]:
                read.append(dict(thread, outcome="unchanged", items=[], gap=[], coverage=[]))
                continue
            read.append(_read_thread(transport, policies, thread, stored, versions))
    except src.AccessRefused as exc:
        cycle.update(stop="access_refused", stop_status="blocked", detail=str(exc))
        refused = exc
    except src.RobotsStop as exc:
        cycle.update(stop="robots_policy", stop_status="blocked", detail=str(exc))
    except src.SourceAuthorityStop as exc:
        cycle.update(stop="source_authority_stop", stop_status="broken", detail=str(exc))
    except src.SchemaIntegrityStop as exc:
        cycle.update(stop="schema_changed", stop_status="broken", detail=str(exc))
    except src.ForbiddenRequest as exc:
        cycle.update(stop="request_outside_default_views", stop_status="broken", detail=str(exc))
    except (src.TransportError, src.RequestBudgetExhausted) as exc:
        cycle.update(stop="network_error", stop_status="broken", detail=str(exc))
    cycle["requests"] = len(transport.requests)
    cycle["request_urls"] = list(transport.requests)
    state["last_cycle"] = {"at": cycle["at"], "requests": len(transport.requests),
                           "outcome": cycle["stop"] or "ok"}
    if refused is not None and refused.queued_topic_id is not None:
        # GPT G62 R1: the method is suspended exactly as before (Transport persisted the refusal), and
        # the queued thread whose own view was refused is held for human disposition, so it cannot
        # suspend the method again once a reviewed change clears the refusal. Nothing else changes.
        _quarantine(state, cycle, str(refused.queued_topic_id), "access_refused", refused.detail)
    if not cycle["stop"]:
        # Windows are remembered only from a cycle that finished: a stop keeps the last good ones,
        # and the deferred-thread queue exactly as it was.
        cycle["threads"] = read
        keep = set(keep_versions or versions)
        seed_ids = {tid for _community_id, tid in src.SEED_THREADS}
        # A queued thread's success:false is confirmed as its own when another thread was read in
        # full in this cycle: both default views then answered validly for that thread.
        confirmed = any(thread.get("outcome") == "read" for thread in read)
        for thread in read:
            if thread.get("outcome") == "read":
                # The new entry carries no deferral: an owed thread read is processed.
                state.setdefault("threads", {})[str(thread["topic_id"])] = thread["state_entry"]
            elif src.is_owed((state.get("threads") or {}).get(str(thread["topic_id"]))):
                _settle_owed(state, cycle, thread, keep, confirmed)
            # A seed read by ANY path -- as a seed, through the listing, remembered or owed -- is
            # recorded, so it never comes back as a title-less seed (G61 R3-T4).
            if int(thread["topic_id"]) in seed_ids and thread.get("outcome") in ("read", "unchanged", "not_tracked"):
                state["seeds_read"] = sorted({int(t) for t in state.get("seeds_read") or []}
                                             | {int(thread["topic_id"])})
        for thread in cycle["deferred"]:
            _defer(state, thread, cycle["at"])
        for tid_text, entry in list((state.get("threads") or {}).items()):
            versions_named = set(entry.get("title_versions") or [])
            if src.is_owed(entry) and versions_named and not versions_named & keep:
                _invalidate(state, cycle, tid_text, "no_tracked_record")
        src.prune_threads(state, keep, current)
    cycle["queue"] = queue_status(state, current)
    return cycle


# --- the deferred-thread queue (GPT G61 Q5) ---------------------------------------------------------
#
# Work a cycle could not reach is kept in the state file, on the thread's own entry, as
#   "deferred": {"reason": thread_cap | request_budget | runtime_budget | thread_read_failed,
#                "first_deferred_at": ..., "queued_at": ..., "times_deferred": n}
# until a finished cycle reads the thread (a new entry replaces it), finds it unchanged, or
# invalidates it: its title names no version a record exists for (title_names_no_tracked_version), or
# no record is left for any version its title names (no_tracked_record). An invalidated thread leaves
# the state file and its reason is kept in `deferred_invalidated` (the last
# MAX_DEFERRED_INVALIDATIONS_KEPT). Nothing else removes it: not the window-retention prune, not the
# listing, not a missing last activity, not a stop.
#
# QUARANTINE (GPT G62 R1). A queued thread can instead be held, on its own entry, as
#   "quarantined": {"reason": thread_unreadable | thread_invalid_response | access_refused,
#                   "detail": ..., "at": ..., "first_deferred_at": ..., "times_deferred": n}
# when its own topic view answers 404/410 (thread_unreadable), when a queued thread the listing does
# not show answers success:false and another thread was read in full in the same cycle
# (thread_invalid_response), or when such a thread's own view is refused (access_refused; the method
# is suspended as before; a 429 is a rate limit and holds nothing). A quarantined thread keeps its
# identity, window and reason in the state file, is never selected, never pruned and never retried
# automatically; only a reviewed change releases it (nvidia_forum_source.QUARANTINE_RELEASES).

def _deferral_reason(threads_read: int, transport: src.Transport) -> str:
    """Why this thread cannot be read now, or ''. The same three ceilings, tested in the same order,
    as before the queue existed; none is raised."""
    if threads_read >= src.MAX_THREADS_PER_CYCLE:
        return "thread_cap"
    if transport.remaining() < 2:
        return "request_budget"
    if _budget_expired():
        return "runtime_budget"
    return ""


def _defer(state: dict[str, Any], thread: dict[str, Any], at: str) -> None:
    """Put a thread the cycle could not reach on the queue (or keep it there, in its place)."""
    threads = state.setdefault("threads", {})
    tid = str(thread["topic_id"])
    entry = threads.get(tid)
    if entry is None:
        # Never read. A user topic's title goes through the same name removal as its stored
        # evidence title; a seed's title is not known yet ("") and is learnt when it is read.
        entry = threads[tid] = {
            "community_id": thread["community_id"], "community_slug": thread["community_slug"],
            "title": state_title(thread["title"], thread["staff"], thread.get("listing_names") or ()),
            "staff": thread["staff"],
            "title_versions": thread["title_versions"], "created": thread.get("created") or 0,
            "last_activity": None, "window": []}
    reason = str(thread.get("deferral_reason") or "thread_cap")
    marker = entry.get("deferred")
    if isinstance(marker, dict):
        marker.update(reason=reason, times_deferred=int(marker.get("times_deferred") or 0) + 1)
    else:
        entry["deferred"] = {"reason": reason, "first_deferred_at": at, "queued_at": at, "times_deferred": 1}


def _settle_owed(state: dict[str, Any], cycle: dict[str, Any], thread: dict[str, Any], keep: set[str],
                 confirmed: bool) -> None:
    """An owed thread this cycle reached without a new window: unchanged (processed), not tracked
    any more (invalidated), unreadable (404/410: quarantined), a confirmed success:false
    (quarantined), or any other failed read -- a timeout, a 5xx, an unconfirmed success:false,
    another shape, a redirect -- which keeps it owed and sends it to the end (GPT G62 R1: never
    classified as permanently invalid; it uses at most one slot of a cycle, so it cannot wedge it)."""
    tid = str(thread["topic_id"])
    entry = state["threads"][tid]
    outcome = thread.get("outcome")
    if outcome == "unchanged":
        entry.pop("deferred", None)         # read before, no activity since: nothing is owed
    elif outcome == "not_tracked":
        if not set(thread.get("title_versions") or []) & keep:
            _invalidate(state, cycle, tid, "title_names_no_tracked_version")
        # Otherwise its title names a record outside this targeted run: still owed.
    elif outcome == "failed":
        if thread.get("gone"):
            _quarantine(state, cycle, tid, "thread_unreadable", f"HTTP {thread.get('http_status')}")
        elif thread.get("invalid_response") and confirmed:
            _quarantine(state, cycle, tid, "thread_invalid_response", "success=false")
        else:
            marker = entry["deferred"]
            marker.update(reason="thread_read_failed", queued_at=cycle["at"],
                          times_deferred=int(marker.get("times_deferred") or 0) + 1)


def _quarantine(state: dict[str, Any], cycle: dict[str, Any], tid: str, reason: str, detail: str) -> None:
    """Hold a queued thread out of selection until a reviewed change releases it (GPT G62 R1). Its
    entry -- identity, title, window -- stays in the state file with the reason, the time and its
    first deferral; the prune never removes it; nothing retries it automatically."""
    entry = state["threads"][str(tid)]
    marker = entry.pop("deferred", None) or {}
    entry["quarantined"] = {"reason": reason, "detail": str(detail or ""), "at": cycle["at"],
                            "first_deferred_at": str(marker.get("first_deferred_at") or ""),
                            "times_deferred": int(marker.get("times_deferred") or 0)}
    cycle["quarantined"].append({"topic_id": int(tid), "reason": reason})


def _invalidate(state: dict[str, Any], cycle: dict[str, Any], tid: str, reason: str) -> None:
    entry = (state.get("threads") or {}).pop(str(tid), None) or {}
    marker = entry.get("deferred") if isinstance(entry.get("deferred"), dict) else {}
    record = {"topic_id": int(tid), "reason": reason, "at": cycle["at"],
              "first_deferred_at": str(marker.get("first_deferred_at") or "")}
    cycle["invalidated"].append(record)
    kept = list(state.get("deferred_invalidated") or []) + [record]
    state["deferred_invalidated"] = kept[-src.MAX_DEFERRED_INVALIDATIONS_KEPT:]


def queue_status(state: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """The queue's depth and its oldest deferral, and the quarantined threads (how many, and why),
    for the health notes and the runtime event."""
    entries = list(((state or {}).get("threads") or {}).values())
    owed = [entry["deferred"] for entry in entries if src.is_owed(entry)]
    firsts = sorted(str(m.get("first_deferred_at") or "") for m in owed if m.get("first_deferred_at"))
    oldest = firsts[0] if firsts else ""
    since = src.parse_instant(oldest)
    age = max(0, int((now - since).total_seconds() // 3600)) if since is not None else None
    held = [str(entry["quarantined"].get("reason") or "") for entry in entries if src.is_quarantined(entry)]
    return {"depth": len(owed), "oldest_deferred_at": oldest, "oldest_age_hours": age,
            "quarantined": len(held), "quarantine_reasons": sorted(set(held))}


def _budget_expired() -> bool:
    budget = rb.get_run_budget()
    return budget is not None and budget.collector_finalize_expired()


def _read_thread(transport: src.Transport, policies: dict[str, Any], thread: dict[str, Any],
                 stored: dict[str, Any], versions: set[str]) -> dict[str, Any]:
    """One thread's two default views (_read_views). For a queued thread the listing does not show
    this cycle, other than a seed never read (`per_thread_failures`, _select_threads), a failure of
    its own views is that thread's, not the cycle's (GPT G62 R1):
      * a JSON answer with success:false and no refusal in it: outcome failed, `invalid_response`;
        run_cycle quarantines it when another thread was read in full in the same cycle, which
        confirms the failure is the thread's own, and otherwise keeps it owed;
      * any other shape its views do not have, or a redirect (refused before the hop, nothing sent
        there): outcome failed, kept owed and sent to the end of the queue, as a timeout or a 5xx;
      * an access refusal still stops the cycle and suspends the method (unchanged). Unless it is an
        HTTP 429 (a rate limit: the thread stays owed), the refused thread is named on the exception,
        and run_cycle quarantines it for human disposition.
    Every other thread keeps the stops it had before the queue existed. A 404/410 from the topic
    view is `gone` for any thread (_read_views)."""
    per_thread = bool(thread.get("per_thread_failures"))
    try:
        return _read_views(transport, policies, thread, stored, versions)
    except src.AccessRefused as exc:
        if per_thread and exc.code != 429:
            exc.queued_topic_id = int(thread["topic_id"])
        raise
    except src.ResponseNotSuccessful as exc:
        if not per_thread:
            raise
        return dict(thread, outcome="failed", invalid_response=True, detail=str(exc),
                    items=[], gap=[], coverage=[])
    except (src.SchemaIntegrityStop, src.SourceAuthorityStop) as exc:
        if not per_thread:
            raise
        return dict(thread, outcome="failed", detail=str(exc), items=[], gap=[], coverage=[])


def _read_views(transport: src.Transport, policies: dict[str, Any], thread: dict[str, Any],
                stored: dict[str, Any], versions: set[str]) -> dict[str, Any]:
    tid = int(thread["topic_id"])
    path = src.www_topic_path(thread["community_id"], thread["community_slug"], tid,
                              src.forum_slug(thread["title"]) if thread.get("title") else "")
    url = src.topic_url(tid)
    src.check_robots(policies, url, path)
    try:
        topic = src.topic_view(transport.get_json(url), tid)
    except src.TransportError as exc:
        # The topic's own default view answering 404/410 is the forum saying the thread cannot be
        # read: owed work is quarantined as thread_unreadable, never retried automatically
        # (run_cycle). Any other failure keeps it owed.
        return dict(thread, outcome="failed", detail=str(exc), gone=exc.code in (404, 410),
                    http_status=exc.code, items=[], gap=[], coverage=[])
    community = topic["communities"][0]
    community_id = int(community["id"])
    community_slug = src.forum_slug(community.get("title"))
    profile = thread_profile(topic["title"], src.is_staff(topic.get("user")))
    merged = dict(thread, title=topic["title"], community_id=community_id, community_slug=community_slug,
                  created=int(topic["createdStamp"]), **profile)
    if not set(profile["title_versions"]) & versions:
        # A seed or remembered thread whose title no longer names a tracked version.
        return dict(merged, outcome="not_tracked", items=[], gap=[], coverage=[])
    last_activity = int(topic["lastActivityStamp"])
    read_before = stored.get("last_activity") is not None
    if read_before and int(stored["last_activity"]) == last_activity:
        return dict(merged, outcome="unchanged", items=[], gap=[], coverage=[])
    last_comment = int(topic["lastComment"]["id"])
    transport.anchors[tid] = last_comment
    comments_url = src.topic_comments_url(tid, last_comment)
    src.check_robots(policies, comments_url, src.www_topic_path(community_id, community_slug, tid,
                                                                  src.forum_slug(topic["title"])))
    try:
        comments, total = src.comments_view(transport.get_json(comments_url))
    except src.TransportError as exc:
        return dict(merged, outcome="failed", detail=str(exc), items=[], gap=[], coverage=[])
    window = src.window_of(comments)
    gap = src.compare_windows(list(stored.get("window") or []) if read_before else None, window,
                              stored.get("total_rows"), total)
    coverage: list[str] = []
    expected = min(src.COMMENT_PAGE_SIZE, total)
    if len(comments) < expected:
        coverage.append("incomplete_window")
    if total > len(comments):
        coverage.append("older_comments_outside_window")
    if any(int(c.get("replyCount") or 0) > len(c.get("comments") or []) for c in comments):
        coverage.append("replies_not_embedded")
    # Every forum member of the topic, its comments and its listing entry: removed from each
    # comment's text (_items_for), from the stored title (evaluate_comment) and from a user topic's
    # title in the state file, the same removal for all. Held for this cycle only, never written to
    # the state file.
    names = sorted(display_names(topic, comments) | set(thread.get("listing_names") or ()))
    entry = {"community_id": community_id, "community_slug": community_slug,
             "title": state_title(topic["title"], profile["staff"], names),
             "staff": profile["staff"], "title_versions": profile["title_versions"],
             "created": int(topic["createdStamp"]), "last_activity": last_activity, "total_rows": total,
             "window": window, "last_read_at": base.utc_now(),
             "first_read_at": stored.get("first_read_at") or base.utc_now(),
             "gap_reasons": gap, "coverage": coverage}
    return dict(merged, outcome="read",
                items=_items_for(merged, topic, comments, community_id, community_slug, names),
                gap=gap, coverage=coverage, state_entry=entry, names=names)


# --- health ---------------------------------------------------------------------------------------------

def _version_status(cycle: dict[str, Any], version: str, accepted: int) -> tuple[str, str, list[str]]:
    """(status, blocked_reason, gap_reasons) for one version, from what this cycle saw."""
    if cycle.get("stop"):
        return cycle["stop_status"], cycle["stop"], []
    relevant = [t for t in cycle.get("threads", []) if version in (t.get("title_versions") or [])]
    # A deferred thread whose title is not known yet (a seed never read) may hold any version's
    # reports, so its deferral is partial coverage for every version (G61 R3-T4), not for none.
    deferred = [t for t in cycle.get("deferred", [])
                if version in (t.get("title_versions") or []) or not t.get("title_versions")]
    gaps = sorted({reason for t in relevant for reason in (t.get("gap") or [])})
    if gaps:
        return "partial", "possible_missed_comments", gaps
    if any("incomplete_window" in (t.get("coverage") or []) for t in relevant):
        return "partial", "incomplete_response", []
    if any(t.get("outcome") == "failed" for t in relevant):
        return "partial", "thread_read_failed", []
    if deferred:
        return "partial", "threads_deferred_by_request_budget", []
    return ("success" if accepted else "no_results"), "", []


def _notes(cycle: dict[str, Any], version: str, candidates: int, accepted: int, rejected: int,
           gaps: list[str]) -> str:
    if cycle.get("stop"):
        return (f"NVIDIA GeForce forum default views: no comment read this cycle ({cycle['stop']}). "
                f"Nothing already stored was removed.{_queue_note(cycle)}")
    relevant = [t for t in cycle.get("threads", []) if version in (t.get("title_versions") or [])]
    read = sum(1 for t in relevant if t.get("outcome") == "read")
    unchanged = sum(1 for t in relevant if t.get("outcome") == "unchanged")
    hidden = any("older_comments_outside_window" in (t.get("coverage") or []) for t in relevant)
    text = (f"NVIDIA GeForce forum default views only (latest {src.COMMENT_PAGE_SIZE} top-level comments "
            f"per thread and the replies the forum embeds). {read} thread(s) naming {version} read, "
            f"{unchanged} unchanged since their last read; {candidates} comment(s) name {version}: "
            f"accepted {accepted}, excluded {rejected}.")
    if hidden:
        text += " Older comments in these threads are outside the visible window and were not read."
    if gaps:
        text += f" Possible missed comments since the last read: {', '.join(gaps)}."
    return text + _queue_note(cycle)


def _queue_note(cycle: dict[str, Any]) -> str:
    """The forum-wide deferred-thread queue (GPT G61 Q5): its depth and oldest deferral after this
    cycle, and any deferred thread this cycle invalidated, with the reasons. Telemetry only."""
    queue = cycle.get("queue")
    if not isinstance(queue, dict):
        return ""
    text = f" Deferred-thread queue (whole forum): {int(queue.get('depth') or 0)} waiting"
    if queue.get("depth") and queue.get("oldest_deferred_at"):
        text += f", oldest deferred {queue['oldest_deferred_at']} ({queue.get('oldest_age_hours')} h ago)"
    text += "."
    if queue.get("quarantined"):
        text += (f" Quarantined, not read until a reviewed change releases them: {int(queue['quarantined'])} "
                 f"({', '.join(queue.get('quarantine_reasons') or [])}).")
    dropped = cycle.get("invalidated") or []
    if dropped:
        text += (f" {len(dropped)} deferred thread(s) invalidated this cycle: "
                 f"{', '.join(sorted({str(d.get('reason')) for d in dropped}))}.")
    return text


# --- writeback (freshness only) -----------------------------------------------------------------------

def apply_consensus_writeback(product_id: str, update_version: str) -> bool:
    return apply_consensus_writebacks(product_id, [update_version]).get(update_version, False)


def apply_consensus_writebacks(product_id: str, update_versions: list[str]) -> dict[str, bool]:
    """Freshness for several patches from ONE dry run of the shared consensus authority (the ComfyUI
    shape). apply_collector_record_fields filters every proposal to COLLECTOR_WRITABLE_FIELDS: the
    count, summary and samples belong to reconciliation and the scoped promotion step."""
    from apply_consensus_to_records import (_index_generated_records,  # noqa: PLC0415
                                            apply_collector_record_fields, run_dry_run)

    wanted = [str(v) for v in update_versions if str(v or "")]
    out = {version: False for version in wanted}
    if not wanted:
        return out
    results = run_dry_run(evidence_path=base.EVIDENCE_PATH, product_id_filter=product_id,
                          is_candidate_mode=False, records_index=_index_generated_records(),
                          write_requested=True)
    for version in wanted:
        matches = [item for item in results if item.get("update_version") == version]
        if len(matches) != 1 or not matches[0].get("would_write"):
            continue
        record_rel = matches[0].get("matched_generated_record_path")
        if not record_rel:
            continue
        fields = dict(matches[0].get("proposed_fields_if_written") or {})
        applied = apply_collector_record_fields(ROOT / record_rel, fields) or {}
        out[version] = bool((applied.get("write_plan") or {}).get("fields"))
    return out


# --- the collector -------------------------------------------------------------------------------------

class NvidiaForumCollector(base.ProductCollector):
    """One driver family's evidence from the forum. Registered once per family; both share the cycle."""

    def __init__(self, product_id: str = identity.GAME_READY) -> None:
        if product_id not in PRODUCTS:
            raise ValueError(f"not an NVIDIA driver product: {product_id!r}")
        self.product_id = product_id

    def _disabled_result(self, record: base.PatchRecord, context: base.CollectorContext) -> dict[str, Any]:
        version = str(record.update_version or "")
        health = base.method_health_row(
            product_id=self.product_id, update_version=version, method_id=METHOD_ID, source_type=SOURCE_TYPE,
            status="disabled", candidates_found=0, accepted_reports=0, rejected_reports=0,
            blocked_reason="disabled_in_method_routing", last_run="",
            notes="NVIDIA GeForce forum default views: switched off in method routing. Nothing was read; "
                  "nothing already stored was removed.")
        return {"product_id": self.product_id, "version": version, "mode": "write" if context.write else "dry-run",
                "candidates_reviewed": 0, "accepted_count": 0, "rejected_count": 0, "accepted_urls": [],
                "rejection_reasons": {}, "method_health": [health]}

    def collect(self, context: base.CollectorContext) -> list[dict[str, Any]]:
        target = getattr(context, "target_versions", None)
        known = _records()
        records = base.newest_first([r for r in known[self.product_id] if not target or r.update_version in target])
        tracked = {r.update_version for r in known[self.product_id]}
        everything = [r for pid in PRODUCTS for r in known[pid]]
        versions = {r.update_version for r in everything if not target or r.update_version in target}
        if METHOD_ID in plan_methods(self.product_id).get("disabled", []):
            # Switched off in method routing for this family: no forum request on its behalf, an
            # honest `disabled` row per record (a method that stops emitting leaves a frozen row),
            # and nothing already stored is touched. The other family may still read.
            return [self._disabled_result(record, context) for record in records]
        cycle = run_cycle(context, versions, keep_versions={r.update_version for r in everything})
        if context.write and cycle.get("state") is not None and cycle.get("ran") and not cycle.get("saved"):
            src.save_state(cycle["state"])
            cycle["saved"] = True
        queue = cycle.get("queue") or {}
        rb.emit("nvidia_forum_cycle", product_id=self.product_id, ran=bool(cycle.get("ran")),
                skipped=cycle.get("skipped") or "", stop=cycle.get("stop") or "",
                requests=int(cycle.get("requests") or 0),
                threads=sum(1 for t in cycle.get("threads", []) if t.get("outcome") == "read"),
                deferred=len(cycle.get("deferred") or []), invalidated=len(cycle.get("invalidated") or []),
                queue_depth=int(queue.get("depth") or 0), queue_oldest_age_hours=queue.get("oldest_age_hours"),
                quarantined=int(queue.get("quarantined") or 0), released=len(cycle.get("released") or []))
        if cycle.get("skipped"):
            # Between cycles nothing is read and nothing is claimed: the last rows stand as written,
            # with their own timestamps (the keyed upsert retains what it is not given).
            return []
        captured_at = base.utc_now()
        results: list[dict[str, Any]] = []
        run_rows: list[dict[str, Any]] = []
        for record in records:
            if _budget_expired():
                rb.emit("collector_budget_stop", product_id=self.product_id, reason="collector_finalize")
                break
            version = str(record.update_version or "")
            accepted: list[dict[str, Any]] = []
            rejected: list[dict[str, Any]] = []
            for thread in cycle.get("threads", []):
                for item in thread.get("items") or []:
                    row = evaluate_comment(self.product_id, record, tracked, thread, item, captured_at)
                    if row is not None:
                        (accepted if row.get("counted") else rejected).append(row)
            status, blocked, gaps = _version_status(cycle, version, len(accepted))
            health = [base.method_health_row(
                product_id=self.product_id, update_version=version, method_id=METHOD_ID,
                source_type=SOURCE_TYPE, status=status, candidates_found=len(accepted) + len(rejected),
                accepted_reports=len(accepted), rejected_reports=len(rejected),
                blocked_reason=blocked, last_run="" if status == "disabled" else captured_at,
                notes=_notes(cycle, version, len(accepted) + len(rejected), len(accepted), len(rejected), gaps))]
            results.append({
                "product_id": self.product_id,
                "version": version,
                "mode": "write" if context.write else "dry-run",
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [r["source_url"] for r in accepted],
                "rejection_reasons": dict(sorted(
                    {reason: sum(1 for r in rejected if r.get("exclusion_reason") == reason)
                     for reason in {str(r.get("exclusion_reason") or "") for r in rejected}}.items())),
                "method_health": health,
            })
            run_rows.extend(accepted + rejected)

        if context.write:
            persisted: list[dict[str, Any]] = []
            already_held: list[dict[str, Any]] = []
            if run_rows:
                base.append_evidence_rows(
                    run_rows, out_added=persisted, out_already_held=already_held,
                    method_health=[row for result in results for row in result["method_health"]])
            base.finalize_method_health_delta(
                [row for result in results for row in result["method_health"]],
                [r for r in persisted if r.get("counted")],
                [r for r in already_held if r.get("counted")])
            new_accepted = sorted({str(r.get("update_version") or "") for r in persisted if r.get("counted")})
            updated = apply_consensus_writebacks(self.product_id, new_accepted)
            for result in results:
                version = str(result["version"])
                result["evidence_rows_added"] = sum(
                    1 for r in persisted if str(r.get("update_version") or "") == version)
                result["record_updated"] = bool(updated.get(version, False))
        return results
