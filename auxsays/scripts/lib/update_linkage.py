#!/usr/bin/env python3
"""Deterministic UPDATE LINKAGE: did the reporter tie their problem to an Office update?

WHY THIS EXISTS. AUXSAYS counts a report only when the exact Click-to-Run build is proven, which is
correct for consensus and wrong as the visibility gate for everything else. Measured on the live
PowerPoint corpus, 94% of recent community reports never state a build -- so a strict gate used as a
visibility gate throws away almost all real user intelligence. This module decides the second,
weaker question: independent of any build, did this reporter say their problem started with an
Office/PowerPoint update?

WHAT IT IS NOT. It is not a build resolver, it is not a consensus input, and it never upgrades
anything. It answers one question and returns the reporter's own words as the reason, so a page can
say WHY a report is being shown.

FAIL CLOSED. Linkage must be stated, not inferred from timing. "Posted after the release date" is
explicitly NOT linkage -- that is the single most dangerous inference available here, because every
complaint in a release window would qualify. A veto (Windows Update, an add-in, a GPU driver, a
service outage, or an instruction to go update) beats every positive cue, because those sentences
routinely contain the word "update" while attributing the fault elsewhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- linkage strengths
LINK_EXPLICIT_UPDATE = "explicit_update_attribution"
LINK_VERSION_FAMILY = "version_family_stated"
LINK_BUILD_FAMILY = "build_family_stated"
LINK_NONE = "no_update_linkage"

# Ordered strongest-first. A report can satisfy several; the strongest is reported.
LINK_STRENGTHS = (LINK_EXPLICIT_UPDATE, LINK_VERSION_FAMILY, LINK_BUILD_FAMILY)

# Public, human-readable reason shown beside the report. The point is that a reader can tell why
# AUXSAYS is showing it, so these are descriptions of the reporter's own claim, not verdicts.
LINK_REASONS = {
    LINK_EXPLICIT_UPDATE: "Reporter says the problem began after an Office or PowerPoint update.",
    LINK_VERSION_FAMILY: "Reporter identifies the update version; exact build not supplied.",
    LINK_BUILD_FAMILY: "Reporter identifies the build family; exact build not supplied.",
}

_OFFICE = r"(?:office|microsoft\s*365|m365|powerpoint|power\s*point|ppt)"

# "after the latest Office update", "since the new PowerPoint update", "the update broke X",
# "started after updating Office". The Office/PowerPoint word and the update word must both be
# present and close together -- "update" alone is the most common word in this corpus.
_EXPLICIT_PATTERNS: tuple[str, ...] = (
    rf"\b(?:after|since|following)\b[^.;!?]{{0,40}}?\b(?:latest|recent|new|today'?s|this\s+month'?s|last)\b"
    rf"[^.;!?]{{0,30}}?{_OFFICE}[^.;!?]{{0,20}}?\bupdat",
    rf"\b(?:after|since|following)\b[^.;!?]{{0,30}}?{_OFFICE}[^.;!?]{{0,25}}?\bupdat(?:e|ed|ing)\b",
    rf"\b(?:after|since|following)\b[^.;!?]{{0,25}}?\bupdat(?:e|ed|ing)\b[^.;!?]{{0,25}}?{_OFFICE}",
    rf"{_OFFICE}[^.;!?]{{0,25}}?\bupdate\b[^.;!?]{{0,30}}?\b(?:broke|broken|caused|causing|started|"
    rf"introduced|triggered|ruined|killed)\b",
    rf"\b(?:the\s+)?(?:latest|new|recent|today'?s)\b[^.;!?]{{0,20}}?{_OFFICE}[^.;!?]{{0,15}}?\bupdate\b"
    rf"[^.;!?]{{0,30}}?\b(?:broke|broken|caused|causing|started|introduced|triggered)\b",
    rf"\b(?:started|began|happens|happening|occurs?)\b[^.;!?]{{0,30}}?\b(?:right\s+)?after\b"
    rf"[^.;!?]{{0,30}}?{_OFFICE}[^.;!?]{{0,20}}?\bupdat",
    # Attribution WITHOUT the Office word adjacent -- "issues after the July/August 2026 updates",
    # "following recent updates". This is safe here and nowhere else: a candidate only reaches this
    # classifier after the strict authority has already proven the product, so the surrounding
    # thread IS a PowerPoint report, and the vetoes below strip the cases where the reporter blamed
    # Windows, an add-in, a driver, another app, or a service. Requiring adjacency instead cost real
    # reports -- both of the above are live examples that were being discarded.
    rf"\b(?:after|since|following)\b[^.;!?]{{0,30}}?\b(?:the\s+|these\s+|those\s+)?"
    rf"(?:recent|latest|last|new|newest|monthly|january|february|march|april|may|june|july|"
    rf"august|september|october|november|december|\d{{4}})\b[^.;!?]{{0,25}}?\bupdates?\b",
)

# A stated release identity WITHOUT a full build. "Version 2608", "Current Channel 2608".
#
# The version token is NOT enough on its own. A YYMM-shaped number after the word "version" is one
# of the most common strings in a support thread, and matching it alone made this a version-STRING
# detector rather than an update-ATTRIBUTION one: "asus prime z590 bios ver. 2405" linked, and so
# did an Excel build quoted by a support agent in a reply. Two of the first four rows this module
# produced were exactly that error. So the version has to be Office-scoped -- named alongside
# PowerPoint, Office, Microsoft 365, or a Click-to-Run channel -- and any OTHER application named
# beside it disqualifies it, because then the version belongs to that application.
_VERSION_FAMILY_RE = re.compile(
    r"\b(?:version|ver\.?|current\s+channel|monthly\s+enterprise|semi-?annual)\s*"
    r"(?:channel\s*)?(?:version\s*)?((?:19|2[0-9])(?:0[1-9]|1[0-2]))\b", re.I)
_OFFICE_SCOPE_RE = re.compile(
    r"(?:powerpoint|power\s*point|\bppt\b|\boffice\b|microsoft\s*365|\bm365\b|"
    r"current\s+channel|monthly\s+enterprise|semi-?annual)", re.I)
# Another product's version string. If one of these sits beside the number, the number is theirs.
_FOREIGN_VERSION_OWNER_RE = re.compile(
    r"(?:\bexcel\b|\bword\b|\boutlook\b|\bteams\b|\bonedrive\b|\bsharepoint\b|\bvisio\b|"
    r"\bproject\b|\baccess\b|\bbios\b|\bfirmware\b|\bdriver\b|\bwindows\b|\bandroid\b|\bios\b|"
    r"\bmacos\b|\bchrome\b|\bedge\b|\bfirefox\b|\bacrobat\b|\bcitrix\b|\bnvidia\b)", re.I)


# A version the reporter is being POINTED AT rather than running: advice, a rollback target, a
# support instruction. "Support told me to stay on Version 2607" identifies a version, but not the
# one the reporter is attributing their problem to.
_ADVISED_VERSION_RE = re.compile(
    r"(?:told\s+(?:me|us)\s+to|advised\s+(?:me|us)?|you\s+should|please|recommend|"
    r"stay\s+on|remain\s+on|revert\s+to|roll\s*back\s+to|downgrade\s+to|"
    r"pin(?:ned)?\s+to|go\s+back\s+to)", re.I)


def _office_scoped(text: str, start: int, end: int, window: int = 60) -> bool:
    """Is this version token the reporter's OWN Office version, and not some other product's?"""
    left = max(0, start - window)
    right = min(len(text), end + window)
    around = text[left:right]
    if _FOREIGN_VERSION_OWNER_RE.search(around):
        return False
    # Advice is checked on the text BEFORE the token: "stay on Version 2607" is advice, whereas
    # "Version 2607 crashes, support told me to open a ticket" is a report that happens to mention
    # being advised of something else.
    if _ADVISED_VERSION_RE.search(text[left:start]):
        return False
    return bool(_OFFICE_SCOPE_RE.search(around))
# A partial build family such as "build 20326", with no ".NNNNN" suffix following it.
#
# A bare five-digit number is NOT enough. Measured on the live corpus, the first thing this matched
# was "Error 30088-29" -- an error code -- and support threads are full of ticket numbers, error
# codes and pixel counts in that shape. The reporter has to actually call it a build or version, and
# it has to be in the Office range, or this stops being evidence and becomes pattern noise.
_BUILD_FAMILY_RE = re.compile(
    r"\b(?:build|version|ver\.?|channel)\s*(?:no\.?|number)?\s*[:#]?\s*"
    r"(?<![\d.])(1[6-9]\d{3}|2[0-9]\d{3})(?!\s*[.\-]\s*\d)(?![\d.])",
    re.I)

# --------------------------------------------------------------------------- vetoes
# Each of these sentences contains "update" while attributing the fault somewhere other than an
# Office patch. They are checked BEFORE the positive cues and they win outright.
VETO_WINDOWS_UPDATE = "attributed_to_windows_update"
VETO_ADDIN_UPDATE = "attributed_to_addin_update"
VETO_DRIVER_UPDATE = "attributed_to_driver_update"
VETO_SERVICE_INCIDENT = "service_incident_not_desktop_patch"
VETO_INSTRUCTION = "update_mentioned_as_instruction"
VETO_OTHER_APP = "attributed_to_another_application"

_VETOES: tuple[tuple[str, str], ...] = (
    (VETO_WINDOWS_UPDATE,
     r"\b(?:after|since|following)\b[^.;!?]{0,30}?\bwindows\s*(?:10|11)?\s*"
     r"(?:cumulative\s+|feature\s+|security\s+)?updat"
     r"|\b(?:after|since|following)\b[^.;!?]{0,25}?\b(?:cumulative|feature)\s+update"
     r"|\bwindows\s+update\b[^.;!?]{0,25}?\b(?:broke|caused|started)\b"
     r"|\bKB\d{7}\b"),
    (VETO_ADDIN_UPDATE,
     r"\badd-?in\b[^.;!?]{0,25}?\bupdat(?:e|ed|ing)\b"
     r"|\bupdat(?:e|ed|ing)\b[^.;!?]{0,20}?\badd-?in\b"
     r"|\bplug-?in\b[^.;!?]{0,20}?\bupdat"),
    (VETO_DRIVER_UPDATE,
     r"\b(?:gpu|graphics|display|nvidia|amd|intel|audio|printer|firmware)\b"
     r"[^.;!?]{0,25}?\bdriver\b[^.;!?]{0,25}?\bupdat"
     r"|\bdriver\s+updat(?:e|ed|ing)\b"
     r"|\b(?:after|since|following)\b[^.;!?]{0,25}?\b(?:nvidia|amd|radeon|geforce|intel|"
     r"realtek|hp|dell|lenovo|logitech)\b[^.;!?]{0,25}?\bupdat"),
    (VETO_SERVICE_INCIDENT,
     r"\b(?:powerpoint|office|microsoft\s*365)\s*(?:for\s+the\s+)?(?:online|web|on\s+the\s+web)\b"
     r"[^.;!?]{0,30}?\b(?:outage|down|unavailable|incident|service\s+status)\b"
     r"|\b(?:service\s+(?:outage|incident|degradation)|MO\d{6})\b"),
    (VETO_INSTRUCTION,
     r"\b(?:try|please|you\s+should|you\s+can|recommend(?:ed)?\s+(?:to|that\s+you)?|suggest)\b"
     r"[^.;!?]{0,25}?\bupdat(?:e|ing)\b"
     r"|\b(?:make\s+sure|ensure)\b[^.;!?]{0,30}?\bup\s*to\s*date\b"),
    (VETO_OTHER_APP,
     r"\b(?:after|since|following)\b[^.;!?]{0,25}?\b(?:teams|outlook|onedrive|sharepoint|"
     r"excel|word|visio|access|acrobat|chrome|edge|firefox|zoom|citrix|vmware|dropbox|"
     r"macos|android|ios|defender|intune|sccm)\b[^.;!?]{0,25}?\bupdat"),
)

_COMPILED_EXPLICIT = tuple(re.compile(p, re.I) for p in _EXPLICIT_PATTERNS)
_COMPILED_VETOES = tuple((name, re.compile(pattern, re.I)) for name, pattern in _VETOES)


@dataclass
class LinkageOutcome:
    """The linkage decision, with the reporter's own words as the reason it was made."""

    linked: bool = False
    signal: str = LINK_NONE
    reason: str = ""
    evidence_phrase: str = ""
    version_family: str = ""
    build_family: str = ""
    veto: str = ""
    signals_found: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, str | bool | list[str]]:
        return {
            "linked": self.linked,
            "update_link_signal": self.signal,
            "update_link_reason": self.reason,
            "update_link_evidence": self.evidence_phrase,
            "stated_version_family": self.version_family,
            "stated_build_family": self.build_family,
            "update_link_veto": self.veto,
        }


def _excerpt(text: str, start: int, end: int, width: int = 150) -> str:
    """The reporter's own sentence around the match, normalized for display."""
    left = max(0, start - 40)
    right = min(len(text), end + width - (end - start))
    return " ".join(text[left:right].split())


def classify_update_linkage(text: str) -> LinkageOutcome:
    """Decide whether this report attributes its problem to an Office/PowerPoint update.

    Vetoes are evaluated first and win outright: a sentence blaming Windows Update, an add-in, a
    driver, a service outage, or merely telling somebody to update contains all the same words as a
    genuine attribution, and treating those as linkage is the failure mode that would flood a patch
    page with reports that have nothing to do with it.
    """
    body = " ".join(str(text or "").split())
    outcome = LinkageOutcome()
    if not body:
        return outcome

    for name, pattern in _COMPILED_VETOES:
        found = pattern.search(body)
        if found:
            outcome.veto = name
            outcome.signal = LINK_NONE
            outcome.evidence_phrase = _excerpt(body, found.start(), found.end())
            return outcome

    for pattern in _COMPILED_EXPLICIT:
        found = pattern.search(body)
        if found:
            outcome.signals_found.append(LINK_EXPLICIT_UPDATE)
            outcome.evidence_phrase = _excerpt(body, found.start(), found.end())
            break

    for version in _VERSION_FAMILY_RE.finditer(body):
        if not _office_scoped(body, version.start(), version.end()):
            continue
        outcome.version_family = version.group(1)
        outcome.signals_found.append(LINK_VERSION_FAMILY)
        if not outcome.evidence_phrase:
            outcome.evidence_phrase = _excerpt(body, version.start(), version.end())
        break

    if not outcome.version_family:
        family = _BUILD_FAMILY_RE.search(body)
        if family and _office_scoped(body, family.start(), family.end()):
            outcome.build_family = family.group(1)
            outcome.signals_found.append(LINK_BUILD_FAMILY)
            if not outcome.evidence_phrase:
                outcome.evidence_phrase = _excerpt(body, family.start(), family.end())

    for strength in LINK_STRENGTHS:
        if strength in outcome.signals_found:
            outcome.signal = strength
            outcome.linked = True
            outcome.reason = LINK_REASONS[strength]
            break
    return outcome
