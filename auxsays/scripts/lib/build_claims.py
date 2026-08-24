#!/usr/bin/env python3
"""Deterministic Click-to-Run build CLAIM extraction: which build, and what the author said it was.

ONE PRIMITIVE, TWO CONSUMERS. Both the collector's acceptance gate and the orchestration graph's
context-resolution stage read builds through ``extract_build_claims`` so their interpretation cannot
drift apart. Before this module there were two copies of the build regex with different boundary
rules, which meant the resolver could see a build the acceptance authority could not.

THE TOKEN. ``BUILD_TOKEN_RE`` matches a bare Click-to-Run build with a sentence-safe boundary:

    "Build 19822.20182."      -> 19822.20182      (a full stop is punctuation, not part of a build)
    "Build 19822.20182,"      -> 19822.20182
    "(19822.20182)"           -> 19822.20182
    "16.0.19822.20182"        -> NOT a bare token (it is an Office full version, handled separately)
    "19822.20182.123"         -> nothing (never truncated into a shorter "valid" build)

WHY ROLES. Counting a report requires knowing which build it is ABOUT. An author who writes "on
2607 (Build A) it crashes; I rolled back to Build B and it works" has named two builds and told us
exactly which is which -- treating that as an unresolvable conflict throws away evidence the source
handed over. But the only thing allowed to assign a role is the author's OWN explicit language, in
the author's OWN segment. There is no inference here: no first/last build, no proximity to the
tracked YYMM, no release chronology, no AI.

FAIL CLOSED. ``select_current_failing_build`` returns a build ONLY when the segment shows exactly
one CURRENT/FAILING claim and no AMBIGUOUS build. An unlabelled build is a build whose role was not
demonstrated, so it BLOCKS selection -- proving "exactly one current build" means every other build
was positively shown to be something else, not merely left unmentioned. That is stricter than
requiring one current claim alone, and it is the reading that cannot silently pick wrong.

CRASH RECORDS. A pasted Windows Application Error block is the strongest claim available: Windows
itself recorded which binary faulted at which version. It is honoured ONLY when the faulting
application is deterministically PowerPoint -- the ``AppName`` immediately governing that
``AppVersion`` must be POWERPNT(.EXE). An ``AppVersion`` from any other application is not a claim
about PowerPoint and is discarded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# --- tokens ------------------------------------------------------------------

# A bare Click-to-Run build. The trailing guard is `(?!\d)(?!\.\d)`, NOT `(?![0-9.])`: the stricter
# form fails on a build that ends a sentence, because the full stop is itself in the excluded class.
BUILD_TOKEN_RE = re.compile(r"(?<![0-9.])(\d{4,6}\.\d{4,6})(?!\d)(?!\.\d)")

# Office reports its full version as 16.0.<build>. This is deliberately NOT a bare build token --
# it only becomes a claim through a crash record whose application identity is proven.
OFFICE_FULL_VERSION_RE = re.compile(r"(?<![0-9.])16\.0\.(\d{4,6}\.\d{4,6})(?!\d)(?!\.\d)")

# --- role vocabulary ---------------------------------------------------------

ROLE_CURRENT_FAILING = "current_failing"
ROLE_ROLLBACK_PREVIOUS = "rollback_previous"
ROLE_REFERENCE_OTHER = "reference_other"
ROLE_AMBIGUOUS = "ambiguous"

ROLES = frozenset({ROLE_CURRENT_FAILING, ROLE_ROLLBACK_PREVIOUS,
                   ROLE_REFERENCE_OTHER, ROLE_AMBIGUOUS})

# --- deterministic match bases (what actually proved the role) ---------------

BASIS_CRASH_RECORD = "powerpoint_crash_record_appversion"
BASIS_RUNNING_STATEMENT = "author_running_statement"
BASIS_VERSION_BUILD_PAIR = "version_build_pair_with_failure"
BASIS_FAILS_ON_BUILD = "failure_predicated_on_build"
BASIS_ISSUE_STARTED = "issue_started_on_build"
BASIS_ROLLBACK_PHRASE = "explicit_rollback_phrase"
BASIS_PREVIOUS_BUILD = "explicit_previous_build"
BASIS_WORKS_AFTER_ROLLBACK = "works_after_rollback"
BASIS_OTHER_MACHINE = "explicit_other_machine_or_person"
BASIS_FOREIGN_APP_CRASH_RECORD = "foreign_application_crash_record"
BASIS_NO_ROLE_STATED = "no_role_stated"
BASIS_CONTRADICTORY = "contradictory_role_claims"

# A build whose ONLY provenance is another application's crash record is not a build this report
# NAMES about PowerPoint. It is kept as a claim for diagnostics but can never satisfy "a build was
# named", so it cannot slip through the single-build shortcut below.
_NON_NAMING_BASES = frozenset({BASIS_FOREIGN_APP_CRASH_RECORD})

# Roles that POSITIVELY establish a build is not the one the report is about. "Only one build is
# named" means nothing is numerically ambiguous; it does not overrule the author having said the
# build was the one they rolled back TO, or the one on somebody else's machine.
_NON_CURRENT_ROLES = frozenset({ROLE_ROLLBACK_PREVIOUS, ROLE_REFERENCE_OTHER})

# --- cue grammars ------------------------------------------------------------
# Every cue must be EXPLICIT author language sitting in the same clause as the build. `%B` is
# substituted with the specific build being classified, so a cue can never be credited to a build
# other than the one it actually sits beside.

_B = "%B"
_NEAR = r"[^\w]{0,4}(?:build|version|v\.?|no\.?|number)?[^\w]{0,4}"

_CURRENT_CUES: list[tuple[str, str]] = [
    # "I'm on Build X", "I am currently running X", "we are using build X"
    (rf"\b(?:i|we)\s*(?:'m|’m|\s+am|\s+are)?\s*(?:currently\s+)?"
     rf"(?:on|running|using)\b{_NEAR}{_B}", BASIS_RUNNING_STATEMENT),
    # "current build X", "current version X"
    (rf"\bcurrent(?:ly)?\s+(?:build|version|channel\s+build)\b{_NEAR}{_B}",
     BASIS_RUNNING_STATEMENT),
    # "Version 2607 (Build X) ... is not working" -- the pair plus an explicit failure
    (rf"\bversion\s+\d{{4}}\b[^.;!?]{{0,60}}?{_B}[^.;!?]{{0,80}}?"
     rf"\b(?:is\s+not\s+working|not\s+working|does\s*n[o']t\s+work|is\s+broken|crash\w*|"
     rf"fail\w*|hang\w*|freez\w*)\b", BASIS_VERSION_BUILD_PAIR),
    # "build X crashes", "X hangs on save", "on build X it fails"
    (rf"{_B}[^.;!?]{{0,40}}?\b(?:crash\w*|hang\w*|freez\w*|fail\w*|break\w*|"
     rf"is\s+not\s+working|not\s+working|does\s*n[o']t\s+work|is\s+broken)\b",
     BASIS_FAILS_ON_BUILD),
    # "the issue started on build X", "problem began with X"
    (rf"\b(?:issue|problem|bug|crash\w*|error)\b[^.;!?]{{0,40}}?"
     rf"\b(?:start\w*|beg[ai]n\w*|appear\w*|introduc\w*)\b[^.;!?]{{0,30}}?{_B}",
     BASIS_ISSUE_STARTED),
    # "after updating to X it crashes" -- the failure half is required
    (rf"\b(?:updat\w*|upgrad\w*|install\w*)\s+to\b{_NEAR}{_B}[^.;!?]{{0,60}}?"
     rf"\b(?:crash\w*|fail\w*|hang\w*|freez\w*|broke\w*|is\s+not\s+working|not\s+working)\b",
     BASIS_FAILS_ON_BUILD),
]

_ROLLBACK_CUES: list[tuple[str, str]] = [
    # "rolled back to X", "reverted to X", "go back to ... X", "downgraded to X"
    (rf"\b(?:roll\w*\s+back|rollback|revert\w*|went\s+back|go(?:ing|es)?\s+back|"
     rf"down\s?grad\w*|step\w*\s+back|fall\w*\s+back|fell\s+back)\b"
     rf"[^.;!?]{{0,60}}?{_B}", BASIS_ROLLBACK_PHRASE),
    # "upgraded FROM X", "came from build X" -- explicit history: X is what they left behind.
    (rf"\b(?:upgrad\w*|updat\w*|mov\w*|migrat\w*|com\w*|cam\w*|jump\w*|went)\s+from\b"
     rf"[^.;!?]{{0,60}}?{_B}", BASIS_PREVIOUS_BUILD),
    # "previous build X", "older version X", "prior build X"
    (rf"\b(?:previous|prior|older|last(?:\s+known)?(?:\s+good)?|earlier)\s+"
     rf"(?:build|version)\b{_NEAR}{_B}", BASIS_PREVIOUS_BUILD),
    # "X works again", "on X it is working again", "X was fine"
    (rf"{_B}[^.;!?]{{0,60}}?\b(?:work\w*|fine|ok|okay|stable|no\s+issues?)\b"
     rf"[^.;!?]{{0,20}}?\b(?:again|before)\b", BASIS_WORKS_AFTER_ROLLBACK),
    (rf"\b(?:work\w*|was\s+fine|ran\s+fine)\b[^.;!?]{{0,30}}?\b(?:on|in|with|under)\b"
     rf"{_NEAR}{_B}", BASIS_WORKS_AFTER_ROLLBACK),
]

_REFERENCE_CUES: list[tuple[str, str]] = [
    # Explicitly somebody else's machine or somebody else's report.
    (rf"\b(?:another|different|other|second|spare|test)\s+"
     rf"(?:pc|machine|computer|device|laptop|desktop|workstation|install\w*|tenant)\b"
     rf"[^.;!?]{{0,80}}?{_B}", BASIS_OTHER_MACHINE),
    (rf"{_B}[^.;!?]{{0,80}}?\b(?:another|different|other)\s+"
     rf"(?:pc|machine|computer|device|laptop|desktop|workstation)\b", BASIS_OTHER_MACHINE),
    (rf"\b(?:colleague|customer|client|user|friend|coworker|co-worker|teammate)s?\b"
     rf"[^.;!?]{{0,80}}?{_B}", BASIS_OTHER_MACHINE),
]

# Clause delimiters. Builds are masked before splitting so a sentence-final build cannot be cut in
# half, and contrastive conjunctions split too -- "A works, whilst B is not working" is two claims.
_CLAUSE_SPLIT_RE = re.compile(
    r"[.;!?\n]+|,|\b(?:whilst|while|whereas|however|but|although|though)\b", re.I)


@dataclass(frozen=True)
class BuildClaim:
    """One build, the role its own author gave it, and the text that proves it."""

    build: str
    role: str
    match_basis: str
    excerpt: str

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def build_tokens(text: str) -> list[str]:
    """Distinct bare build tokens, in first-appearance order. No roles, no judgement."""
    seen: list[str] = []
    for match in BUILD_TOKEN_RE.findall(text or ""):
        if match not in seen:
            seen.append(match)
    return seen


def _clauses(text: str) -> list[str]:
    """Split into clauses without ever cutting a build token in half."""
    masked = text or ""
    tokens: list[str] = []

    def _mask(m: re.Match) -> str:
        tokens.append(m.group(0))
        return f"\x00{len(tokens) - 1}\x00"

    masked = BUILD_TOKEN_RE.sub(_mask, masked)
    masked = OFFICE_FULL_VERSION_RE.sub(_mask, masked)
    out: list[str] = []
    for part in _CLAUSE_SPLIT_RE.split(masked):
        if not part:
            continue
        restored = re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m.group(1))], part)
        if restored.strip():
            out.append(restored.strip())
    return out


def _build_windows(text: str) -> dict[str, list[str]]:
    """Per-build text neighbourhoods: the clause, cut at the neighbouring build tokens.

    Cue matching MUST be bounded this way. A clause-wide search lets a failure phrase credit a build
    it does not belong to -- "upgraded from Version 2407 (Build A) to Version 2410 (Build B) and now
    it crashes" would mark BOTH A and B as failing, turning a report whose author said exactly which
    build broke into an unresolvable conflict. A build's evidence is the text between its
    neighbours, so no phrase can ever be counted for a build with another build standing in between.
    """
    windows: dict[str, list[str]] = {}
    for clause in _clauses(text):
        spans = [(m.start(), m.end(), m.group(1)) for m in BUILD_TOKEN_RE.finditer(clause)]
        if not spans:
            continue
        for index, (start, end, build) in enumerate(spans):
            left = spans[index - 1][1] if index else 0
            right = spans[index + 1][0] if index + 1 < len(spans) else len(clause)
            windows.setdefault(build, []).append(clause[left:right])
    return windows


def crash_record_builds(text: str) -> list[tuple[str, str]]:
    """Builds asserted by a pasted Windows Application Error block, as (build, app_name).

    Each ``AppVersion`` is governed by the nearest PRECEDING ``AppName``, which is how the event
    schema orders them. Only a block whose governing application is POWERPNT is a claim about
    PowerPoint; every other application's version is discarded rather than borrowed."""
    found: list[tuple[str, str]] = []
    current_app = ""
    pattern = re.compile(
        r"AppName\s*\"?\s*>?\s*([A-Za-z0-9_.\-]+)"
        r"|AppVersion\s*\"?\s*>?\s*((?:\d{1,3}\.){0,3}\d{4,6}\.\d{4,6})", re.I)
    for match in pattern.finditer(text or ""):
        app, version = match.group(1), match.group(2)
        if app:
            current_app = app.strip().lower()
            continue
        if not version:
            continue
        build_match = OFFICE_FULL_VERSION_RE.search(version) or BUILD_TOKEN_RE.search(version)
        if build_match is None:
            continue
        found.append((build_match.group(1), current_app))
    return found


def _excerpt(text: str, build: str, width: int = 150) -> str:
    idx = (text or "").find(build)
    if idx < 0:
        return " ".join((text or "").split())[:width]
    start = max(0, idx - width // 2)
    return " ".join(text[start:idx + len(build) + width // 2].split())


def extract_build_claims(text: str) -> list[BuildClaim]:
    """Every build the text names, each with the role its own author explicitly gave it.

    Precedence, highest first: a PowerPoint crash record; an explicit rollback/history phrase; an
    explicit current/failing statement; an explicit other-machine/other-person reference. A build
    carrying BOTH a current and a rollback claim is CONTRADICTORY and therefore AMBIGUOUS -- the
    author said two incompatible things about it, so nothing about it is demonstrated."""
    body = str(text or "")
    tokens = build_tokens(body)
    tokens_in_prose = set(tokens)

    # A crash record's build may be written as 16.0.<build>, which is not a bare token, so collect
    # those separately and treat them as named builds too.
    crash: dict[str, set[str]] = {}
    for build, app in crash_record_builds(body):
        crash.setdefault(build, set()).add(app)
    for build in crash:
        if build not in tokens:
            tokens.append(build)

    claims: list[BuildClaim] = []
    windows = _build_windows(body)
    for build in tokens:
        roles: dict[str, str] = {}

        apps = crash.get(build) or set()
        bare = build in tokens_in_prose
        if any("powerpnt" in app for app in apps):
            roles[ROLE_CURRENT_FAILING] = BASIS_CRASH_RECORD
        elif apps and not bare:
            # An AppVersion belonging to some other application says nothing about PowerPoint, and
            # it is not a build this report names either -- it only appears inside 16.0.X.Y under a
            # foreign AppName.
            roles[ROLE_REFERENCE_OTHER] = BASIS_FOREIGN_APP_CRASH_RECORD

        escaped = re.escape(build)
        for window in windows.get(build, []):
            for cue_set, role in ((_ROLLBACK_CUES, ROLE_ROLLBACK_PREVIOUS),
                                  (_CURRENT_CUES, ROLE_CURRENT_FAILING),
                                  (_REFERENCE_CUES, ROLE_REFERENCE_OTHER)):
                for pattern, basis in cue_set:
                    if re.search(pattern.replace(_B, escaped), window, re.I):
                        roles.setdefault(role, basis)

        excerpt = _excerpt(body, build)
        if ROLE_CURRENT_FAILING in roles and ROLE_ROLLBACK_PREVIOUS in roles:
            # Explicitly contradictory: fail closed rather than pick the "stronger" cue.
            claims.append(BuildClaim(build, ROLE_AMBIGUOUS, BASIS_CONTRADICTORY, excerpt))
        elif ROLE_CURRENT_FAILING in roles and roles[ROLE_CURRENT_FAILING] == BASIS_CRASH_RECORD:
            claims.append(BuildClaim(build, ROLE_CURRENT_FAILING, BASIS_CRASH_RECORD, excerpt))
        elif ROLE_ROLLBACK_PREVIOUS in roles:
            claims.append(BuildClaim(build, ROLE_ROLLBACK_PREVIOUS,
                                     roles[ROLE_ROLLBACK_PREVIOUS], excerpt))
        elif ROLE_CURRENT_FAILING in roles:
            claims.append(BuildClaim(build, ROLE_CURRENT_FAILING,
                                     roles[ROLE_CURRENT_FAILING], excerpt))
        elif ROLE_REFERENCE_OTHER in roles:
            claims.append(BuildClaim(build, ROLE_REFERENCE_OTHER,
                                     roles[ROLE_REFERENCE_OTHER], excerpt))
        else:
            claims.append(BuildClaim(build, ROLE_AMBIGUOUS, BASIS_NO_ROLE_STATED, excerpt))
    return claims


def role_counts(claims: list[BuildClaim]) -> dict[str, int]:
    counts = {role: 0 for role in sorted(ROLES)}
    for claim in claims:
        counts[claim.role] = counts.get(claim.role, 0) + 1
    return counts


def select_current_failing_build(claims: list[BuildClaim]) -> tuple[str, str, str]:
    """The one build the segment demonstrates as current/failing, or nothing.

    Returns ``(build, match_basis, refusal_reason)``. Exactly one of build / refusal_reason is set.

    Selection requires exactly one CURRENT/FAILING claim AND no AMBIGUOUS build. A build whose role
    was never stated might BE the current one, so leaving it unclassified is not the same as ruling
    it out -- with one present, "exactly one current build" has not been demonstrated."""
    if not claims:
        return "", "", "no_build_named"
    current = [c for c in claims if c.role == ROLE_CURRENT_FAILING]
    ambiguous = [c for c in claims if c.role == ROLE_AMBIGUOUS]

    if len(current) > 1:
        return "", "", "multiple_current_failing_claims"
    if not current:
        return "", "", "no_current_failing_claim"
    if ambiguous:
        return "", "", "unclassified_build_present"
    return current[0].build, current[0].match_basis, ""


def single_named_build(claims: list[BuildClaim]) -> str:
    """The one build a single-build text is ABOUT, or nothing.

    A report that mentions one build has nothing NUMERICALLY to disambiguate, so an unlabelled
    single build behaves exactly as it did before the role classifier existed. But "only one build
    exists" is not a licence to ignore what the author said about it. If the classifier positively
    established that build as the one they rolled back TO, or as one running on somebody else's
    machine, or if they said two contradictory things about it, then the report demonstrates no
    current/failing build at all -- and being the only candidate does not make it one.

    A build that was never actually NAMED -- one that exists only inside another application's crash
    record -- likewise does not count. Otherwise an Excel fault block would satisfy PowerPoint's
    exact-build requirement through this shortcut."""
    builds = {c.build for c in claims if c.match_basis not in _NON_NAMING_BASES}
    if len(builds) != 1:
        return ""
    build = next(iter(builds))
    for claim in claims:
        if claim.build != build:
            continue
        if claim.role in _NON_CURRENT_ROLES or claim.match_basis == BASIS_CONTRADICTORY:
            return ""
    return build
