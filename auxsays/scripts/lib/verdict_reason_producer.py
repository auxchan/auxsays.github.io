"""The deterministic verdict-reason producer (G35-04; independence and shadow repairs, AUX-099).

WHAT IT IS. A pure function of stored data -- the generated records and their counted evidence rows
-- that proposes reason entries of two classes, in the shape lib/patch_decision.decide already reads:

  * vendor_confirmed_serious (AUTH_V2_35 D-B; owner decision 1, safeguard 1: "a vendor-confirmed
    serious defect can justify caution without two user reports"). Derived from official vendor text
    ALREADY STORED on records, in two closed grammars:
      - OBS release notes: a bug-fix bullet "Fixed <defect> in [OBS Studio] V[ and V2]" in a LATER
        release's captured notes names V as carrying the defect (the template OBS uses for hotfixes);
      - the Microsoft release-health roll-up the official Windows lane writes into a record's body:
        "- Active|Resolved: <title> <description> -- status <S>; originating OS Build <b> <KB>; ...".
    A candidate needs: the exact affected version (named by the vendor, and a record carrying it),
    the stored statement it rests on (record + field + line, re-checked verbatim on every run), a
    concrete failure with a severity basis from a CLOSED vocabulary (data loss, critical install
    failure, substantial workflow breakage, crash on launch or in a core flow), and the affected setup.
    It FAILS CLOSED to no candidate on: a minor lag, a recoverable preference/profile reset, a narrow
    cosmetic issue, no exact version, no stored official text, an ambiguous scope. A scope is
    ambiguous unless it names a SETUP (`scope_problem`): "for a small number of devices", "for all
    editions of Windows 11", "if you use the update" or "if you use OBS" name nobody in particular,
    and "for some consumer devices" or "for devices in some regions" name one only vaguely, so they
    go to the review queue, never to a page. An OBS version counts only where the vendor
    names it as the defective one ("Fixed a crash in V", "present in V"), never as where an input
    file was made ("created in V"). An OBS crash, freeze or hang is serious only on launch or in a core
    workflow the note names (recording, streaming, capture, scenes, sources, outputs, audio ...); one
    when closing a dialog is not, and a defect the vendor hedges anywhere in the note (possible, rare,
    occasional, "could", "may", "might", "in some cases") goes to the review queue (review 2, LOW-2; G38
    WS2 review 2, LOW-1).
    FAIL CLOSED ON WORDING (G38 WS2 review 2, MAJOR-3). A vendor WAIT says the defect is NEW in this version,
    so it is drafted only when the producer has read every word of the vendor's statement: an OBS bullet
    must be the head and one recognised tail of plain words (`_obs_unrecognised`); a Microsoft row must say
    nothing about the issue's history (`_WIN_HISTORY_RE`). Anything left over -- a trailing "that ..." /
    "which ..." clause, a parenthesis, an aside, a version number, a history word -- sends the statement
    to the review queue (`unrecognised_wording`), never to a page, and never into a scope. Phrases are not
    what keeps a carried-over defect off a page: an unlisted phrasing is still unrecognised text.
    Recommendation: WAIT scoped to the setup when the vendor names this version as where the defect
    starts (the earliest version it names, or the originating build) in a fully recognised statement;
    TEST FIRST, saying the problem PERSISTS, when a fully recognised OBS bullet carries the defect over:
    it names an older version too ("in 31.1.0 and 31.1.1" on 31.1.1) or qualifies its version list with
    "and earlier" -- "earlier" / "previous" / "older" / "prior" count as carry-over only where they
    qualify a version or a release; a persistent problem is never called new or caused -- and for an
    installation failure.

  * user_corroborated_install_failure (G35-04 Amendments A1, A3; AUTH_V2_37 correction 2). The update
    fails to install, in at least MIN_INDEPENDENT_REPORTERS reports of SEPARATE incidents of ONE
    problem on the page's own counted rows.
      - A Windows row counts only when it reports THIS update failing to install
        (`windows_install_row`): it names the page's KB (a build alone is a device's current build or a
        rollback target); its install wording is not negated, not about the update scan, and takes
        THIS update as its subject or object -- an ALLOW-LIST (G38 WS2 review 2, MAJOR-2): the KB, "this /
        the update", or "update" qualified only by articles and this update's own qualifiers. "The .NET /
        driver / next / feature update" is another update; "unable to install WSL since KB..." or "Since
        KB... Zoom fails to install" is another object or subject; unknown counts as foreign. Error codes
        are read only in install-error context, never from a crash or bugcheck. Acrobat rows
        (`acrobat_install_row`) show installer "Exit Code 7" that is not another Adobe product's, name no
        other Acrobat version or generation and not only the other product (Reader / Pro), do not say the
        version installed, and a row shared between Pro and Reader must name this page's product.
      - One problem (A3, INSTALL_GROUPING "strict"): rows group only on a shared failure
        characteristic -- the same error code, a named stage for rows that state no code, for Acrobat the
        same SPECIFIC installer error (DW / DF code), never the generic Exit Code 7 every failure prints.
        Different error codes alone are not one problem, and a shared stage never joins two codes.
      - Independence FAILS CLOSED (AUTH_V2_37 correction 2). Copies are DETECTED -- a declared
        cross-post, re-post, follow-up or copy, the same log, a shared distinctive passage (a reworded
        re-post keeps one), near-identical text, the same KB set, the same incident details -- and only
        ever REMOVE a would-be second reporter; detection never touches stored evidence. A second report
        COUNTS only where the source supports a different reporter or machine: a source reporter id that
        differs on the same site (no collector stores one today), or identity details that cannot belong
        to one machine (two different computers, processors, editions, architectures, operating systems),
        read ONLY from the reporter's statements about their own machine -- "my Dell laptop", "I'm on
        Windows 10", a system-information line -- never from an app name, a file path, an update title, a
        question about another download or a third party (G38 WS2 review 2, MAJOR-1). A failure point or
        an OS version never separates two reports: one person's retry or OS upgrade shows both. Unknown is
        not independent. A shared distinctive passage or log joins two rows whatever machines they name
        (a copy that adds a machine detail is still a copy); the weaker cues never merge two machines
        whose own-machine details conflict (conservative grouping), not even through a third row.
    Recommendation: TEST FIRST "when installing it" -- never WAIT.

Everything else -- non-install user corroboration -- is NOT produced: `corroboration_candidates` is
the placeholder interface for that later work, and it fails closed. Pages that need a person go to
the review queue, which is TEMPORARY: it has no automated promotion yet.

THE SWITCH. `PUBLIC_AUTO_ACTIVATION` is the ONE activation switch. It is OFF, and it is TEMPORARY:
public automatic activation needs the owner's approval of that transition (AUTH_V2_35 D-A). OFF,
the decision authority reads only the reviewed `_data/verdict_reasons.yml`, so nothing published
changes; the producer still runs at deploy -- SHADOW operation -- and its candidates are written to the
git-ignored `_data/verdict_reason_candidates.yml`, which lib/producer_shadow turns into bounded,
public-safe diagnostics. ON, lib/verdict_projection merges the candidates into the supported reasons,
so the projection, the gate, every surface and QA carry them.

NEVER A SECOND WRITER. The producer runs only where reasons are gathered for a decision and writes
nothing; build_verdict_projection.py writes its derived, git-ignored artifact. No collector imports it.

Reads its arguments and nothing else: no network, no clock, no file, no collector import
(test_verdict_reason_producer pins the import list).
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

from . import verdict_reasons

# A LABEL for people reading a candidate (round 3 of AUX-099 is "5"). The shadow ledger does NOT key rules
# changes on it: lib/producer_shadow.rules_version hashes this module's source, so a forgotten bump cannot
# make rule-made candidates look prospective (G38 WS2 review 2, LOW-6).
PRODUCER_VERSION = "5"
# THE ONE ACTIVATION SWITCH. TEMPORARY: OFF until the owner approves public auto-activation
# (AUTH_V2_35 D-A). Flipping it is a reviewed one-line change, never an environment variable or a
# workflow input, so no deploy can turn it on by itself.
PUBLIC_AUTO_ACTIVATION = False

VENDOR_CLASS = "vendor_confirmed_serious"
INSTALL_CLASS = "user_corroborated_install_failure"
INSTALL_REASON_CLASS = "corroborated_install_problem"   # the existing reason class decide words
SEVERITY_BASES = ("data_loss", "critical_install_failure", "substantial_workflow_breakage",
                  "crash_on_launch", "crash_in_core_flow")
EXCLUSION_REASONS = ("minor_lag", "recoverable_preference_or_profile", "narrow_cosmetic",
                     "no_severity_basis", "no_exact_version", "no_exact_page", "ambiguous_scope",
                     "no_stored_official_text", "candidate_schema", "not_enough_independent_reporters",
                     "no_shared_failure_characteristic", "uncertain_severity", "unrecognised_wording")
# A1: "at least 2 independent reporters remain". The single named threshold.
MIN_INDEPENDENT_REPORTERS = 2
REVIEW_QUEUE_LABEL = ("TEMPORARY review queue: no automated promotion exists for these yet; a person "
                      "reads them and, where they hold, writes a reviewed entry")

OBS = "obs-studio"
WINDOWS = "microsoft-windows-11"
ACROBAT = ("adobe-acrobat-pro", "adobe-acrobat-reader")
INSTALL_SCOPE = "when installing it"


def _s(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _sha(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _version_key(version: str) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"[.]", version))


# ============================================================ vendor_confirmed_serious: OBS

# A bullet ends with its author ("[name]") and, in newer notes, a pull-request link ("([#13863](url))").
_OBS_BULLET_RE = re.compile(r"^\s*[*-]\s*(Fixed\b.*?)\s*(?:\[[^\]\n]*\]\s*(?:\(\[#[0-9]+\]\([^)\n]*\)\))?)?\s*$", re.M)
# The versions a fix bullet names AS DEFECTIVE: right after the defect head ("Fixed a possible crash in
# 32.0.0", "Fixed an issue in OBS Studio 31.1.0 and 31.1.1") or after "present in" / "introduced in"
# ("regression present in 32.1.0 and 32.1.1"). A version anywhere else is not one: "Fixed a crash when
# loading scene collections created in 31.0.4" names where an input file was made, and the defect is in
# the newer release (review 1, LOW-3). A bare number (macOS 27.2) is never one either.
_OBS_VERSION_LIST = r"(?:OBS Studio )?(\d+\.\d+\.\d+)((?:(?:,|,? and) (?:OBS Studio )?\d+\.\d+\.\d+)*)"
_OBS_NAMED_RE = re.compile(
    r"^Fixed (?:a |an )?(?:(?:possible|potential|rare|random|occasional|intermittent|sporadic) )?"
    r"(?:crash|freeze|hang|issue|bug|regression|problem)e?s? "
    r"in " + _OBS_VERSION_LIST + r"|\b(?:present|introduced) in " + _OBS_VERSION_LIST, re.ASCII)
_OBS_HEAD_RE = re.compile(r"^Fixed (?:a |an )?(?P<q>(?:possible|potential|rare|random|occasional|intermittent|sporadic) )?"
                          r"(?P<kind>crash|freeze|hang)\b", re.I)
_OS_RE = re.compile(r"\bon (Windows|macOS(?: [0-9]+(?:\.[0-9]+)*)?|Linux)\b", re.ASCII)
_WHEN_RE = re.compile(r"\bwhen ([a-z][^;]*?)\s*\.?$")
_LAUNCH_RE = re.compile(r"\b(?:when (?:starting|launching|opening) OBS|on (?:launch|startup)|at startup)\b", re.I)
# Review 2, LOW-2: a crash is serious when OBS will not launch or when it breaks a CORE workflow -- what the
# "when ..." clause names: recording, streaming, capture, scenes, sources and their properties, outputs,
# encoders, audio, transitions, the virtual camera, the replay buffer. A crash that names neither ("when
# closing the About dialog", "when attempting to log info about ...") has no severity basis.
_OBS_CORE_FLOW_RE = re.compile(
    r"\b(?:record\w*|stream\w*|broadcast\w*|going live|outputs?|encod\w*|captur\w*|scenes?|sources?|properties|"
    r"transitions?|virtual ?cam\w*|replay buffer|studio mode|audio|mixer|filters?|multitrack|decklink|ndi|"
    r"websocket|hotkeys?)\b", re.I)
_OBS_NOT_CORE_RE = re.compile(
    r"\b(?:log\w*|about (?:dialog|window|box)|help|crash report\w*|crash handler|update check\w*|checking for "
    r"updates|auto-?config\w*|wizard|tooltips?|themes?|exit\w*|clos(?:e|ing) OBS|shut\w* down|shutdown|quit\w*)\b",
    re.I)
# A defect the vendor itself calls uncertain ("a possible crash", "a rare freeze", "can sometimes", "a crash that
# could occur", "may happen") is for a person: the review queue, never an automatic verdict (review 2, LOW-2; G38
# WS2 review 2, LOW-1). Read on the WHOLE bullet, before anything else is decided about it.
_UNCERTAIN_RE = re.compile(r"\b(?:possible|possibly|potential|potentially|rare|rarely|random|randomly|occasional|"
                           r"occasionally|intermittent|intermittently|sporadic|sporadically|sometimes|seldom|"
                           r"could|may|might|can(?!'t|not)|in (?:some|certain|rare) (?:cases|situations|circumstances|"
                           r"conditions|setups)|under (?:some|certain) (?:conditions|circumstances)|at times|"
                           r"from time to time|now and then|once in a while)\b", re.I)

# FAIL CLOSED ON WORDING (G38 WS2 review 2, MAJOR-3; round-3 brief items 3 and 7). A vendor WAIT says the defect
# is NEW in this version, so the producer drafts one only when it has read EVERY word of the bullet: the head
# ("Fixed [a|an] <crash|freeze|hang|issue|bug|regression|problem> [present|introduced] in <versions> [and
# earlier] [on <OS>]") and ONE recognised tail -- "when <clause> [on <OS>]", "on launch" / "at startup",
# "where <feature> <stops working> [<context>]", "causing <feature> to fail [<context>]" -- whose clause,
# feature and context are plain words. Anything else left over is UNRECOGNISED and the bullet goes to the
# review queue (`unrecognised_wording`), never to a page: a trailing "that ..." / "which ..." clause, a
# parenthesis, a ", a bug ..." aside, a dash, a version number, a release noun ("versions", "the 31.x series"),
# or any HISTORY word ("old", "since", "long", "already", "also", "first", "predates", "dating back",
# "around", "still" ...). The list of history words is not what keeps a carried-over defect off a page -- the
# grammar is: an unlisted history phrase is still unrecognised text, so it is queued too. And "earlier" /
# "previous" / "older" / "prior" count as carry-over only where they qualify a version or a release ("in
# 32.1.0 and earlier", "earlier versions"); anywhere else ("earlier than the stream") they are unrecognised
# text: queued, never published as "persists" (brief item 7).
_OBS_QUALIFIER = r"(?:possible|potential|rare|random|occasional|intermittent|sporadic)"
_OBS_OS = r"(?:Windows|macOS(?: [0-9]+(?:\.[0-9]+)*)?|Linux)"
_OBS_VLIST = r"(?:OBS Studio )?\d+\.\d+\.\d+(?:(?:,|,? and) (?:OBS Studio )?\d+\.\d+\.\d+)*"
# The one recognised carry-over: "and earlier" / "and older versions" qualifying the version list itself.
_OBS_CARRY = r" and (?:all )?(?:earlier|older|prior|previous)(?: versions?| releases?)?"
_OBS_RECOGNISED_RE = re.compile(
    r"^Fixed (?:(?:a|an) )?(?:" + _OBS_QUALIFIER + r" )?(?:crash|freeze|hang|issue|bug|regression|problem)(?:e?s)? "
    r"(?:(?:present|introduced) )?in " + _OBS_VLIST + r"(?P<carry>" + _OBS_CARRY + r")?(?: on " + _OBS_OS + r")?"
    r"(?P<tail>(?: .*)?)$", re.ASCII)
_OBS_TAILS = (
    re.compile(r"^ when (?P<clause>.+?)(?: on " + _OBS_OS + r")?$", re.ASCII),
    re.compile(r"^ (?:on (?:launch|startup)|at startup)(?: on " + _OBS_OS + r")?$", re.ASCII),
    re.compile(r"^ where (?P<feature>.+?) (?:did not work|does not work|didn't work|doesn't work|stopped working|"
               r"no longer worked|no longer works|would break|broke|would fail|failed|fails|would not (?:start|load|"
               r"open|connect))(?: in the (?P<variant>[A-Z][\w-]*(?: [A-Z][\w-]*){0,2}) version|"
               r" (?P<context>(?:in|on|after|when|while|with|for|if) .+))?$", re.ASCII),
    re.compile(r"^ causing (?P<feature>.+?) to (?:fail|break|stop working)(?: in the (?P<variant>[A-Z][\w-]*(?: "
               r"[A-Z][\w-]*){0,2}) version| (?P<context>(?:in|on|after|when|while|with|for|if) .+))?$", re.ASCII),
)
# What makes a clause, feature or context NOT plain words: a clause marker, a version number, a release noun, a
# history word, or carry-over wording outside the recognised "and earlier" slot.
_CLAUSE_MARKER_RE = re.compile(r"[,;:()\[\]{}\"—–]|\s-\s|\b(?:that|which|who|whose|whom)\b", re.I)
_VERSION_NUMBER_RE = re.compile(r"\d+\.(?:\d+|x)\b", re.I)
_RELEASE_NOUN_RE = re.compile(r"\b(?:versions?|releases?|builds?|series|updates?|hotfix(?:es)?|patch(?:es)?)\b", re.I)
_PERSISTENT_RE = re.compile(
    r"\b(?:old|since|ago|already|still|long|longstanding|long-standing|persist\w*|carr(?:y|ies|ied)|regress\w*|also|"
    r"before|first|introduc\w*|exist\w*|pre-?existing|predat\w*|dating|dates|back|again|anymore|later|originally|"
    r"original|initial|initially|histor\w*|recurr\w*|reappear\w*|return\w*|ever|until|present|as well|too|"
    r"known)\b", re.I)
_CARRY_WORD_RE = re.compile(r"\b(?:earlier|previous|previously|older|prior)\b", re.I)


def _not_plain(text: str) -> str:
    """The first thing in `text` that is not a plain word of a recognised tail, or "" (fails closed)."""
    for rx in (_CLAUSE_MARKER_RE, _VERSION_NUMBER_RE, _RELEASE_NOUN_RE, _PERSISTENT_RE, _CARRY_WORD_RE,
               _UNCERTAIN_RE):
        m = rx.search(text)
        if m:
            return m.group(0)
    return ""


def _obs_unrecognised(statement: str) -> str:
    """What in an OBS fix bullet the grammar does not read, or "" when every word is recognised: the head,
    then exactly one recognised tail of plain words (see above). Fails closed: unrecognised is never new."""
    text = re.sub(r"\s+", " ", statement).strip().rstrip(".").strip()
    m = _OBS_RECOGNISED_RE.match(text)
    if not m:
        return "the wording around the defect and the version it names"
    tail = m.group("tail")
    if not tail:
        return ""
    for rx in _OBS_TAILS:
        t = rx.match(tail)
        if t:
            parts = [v for k, v in t.groupdict().items() if v and k != "variant"]
            bad = next((b for b in map(_not_plain, parts) if b), "")
            variant = t.groupdict().get("variant") or ""   # "in the Flatpak version": a build variant, kept
            hist = _PERSISTENT_RE.search(variant) or _CARRY_WORD_RE.search(variant)
            bad = bad or (hist.group(0) if hist else "")
            return f"{bad!r} in {tail.strip()!r}" if bad else ""
    return f"the clause {tail.strip()!r}"


# A three-part version number anywhere in a bullet, and the platforms / components whose own version numbers
# are not OBS versions ("on macOS 14.4.1", "Qt 6.5.3").
_ANY_VERSION_RE = re.compile(r"(?<![\w.])(\d+\.\d+\.\d+)(?![\w.]*\d)", re.ASCII)
_PLATFORM_BEFORE_RE = re.compile(
    r"\b(?:macos|mac os(?: x)?|os x|windows|linux|ubuntu|debian|fedora|kernel|mesa|qt|cef|chromium|ffmpeg|python|"
    r"lua|nvidia|amd|intel|cuda|driver|sdk|plugin|obs-websocket|websocket|pipewire|wayland|glibc|xcode|vulkan|"
    r"directx|opengl|librist|srt|x264|aja|decklink)\s*(?:version\s*)?v?$", re.I)
# Carry-over wording that qualifies a version or a release (brief item 7): "and earlier", "or older", "earlier
# versions", "previous releases", "prior builds".
_CARRY_QUALIFIES_RE = re.compile(
    r"\b(?:and|or) (?:all )?(?:earlier|older|prior|previous)\b(?! than)|"
    r"\b(?:earlier|previous|older|prior) (?:obs (?:studio )?)?(?:versions?|releases?|builds?)\b", re.I)
# What `_obs_persistence` returns for a bullet that says MORE than the grammar reads after its head (a trailing
# clause, a parenthesis, an aside, a history word): not established as new. Such a bullet is queued, never drafted.
UNRECOGNISED_HISTORY = "an unrecognised remark (it may say the defect is older)"


def _obs_persistence(statement: str, version: str) -> str:
    """Whether an OBS bullet says the defect was already there BEFORE `version`. Fails closed: "" (new in
    `version`) ONLY when nothing in the bullet says or might say otherwise.
      * "OBS <v>": the earliest older OBS version it names anywhere ("in 31.1.0 and 31.1.1" read on 31.1.1;
        "as in 32.0.4"). A platform's or component's version number ("macOS 14.4.1") is not an OBS version.
      * "earlier versions": carry-over wording that qualifies a version or a release ("in 32.1.0 and
        earlier", "earlier versions"); "earlier" anywhere else is not carry-over (brief item 7).
      * UNRECOGNISED_HISTORY: anything after the head and its tail that the grammar does not read, or a history
        word anywhere -- `_obs_unrecognised`. Not new; the producer queues it.
    Only the first two are ever published, and only for a fully recognised bullet."""
    key = _version_key(version)
    older = {m.group(1) for m in _ANY_VERSION_RE.finditer(statement)
             if _version_key(m.group(1)) < key
             and not _PLATFORM_BEFORE_RE.search(statement[max(0, m.start() - 40):m.start()])}
    if older:
        return f"OBS {sorted(older, key=_version_key)[0]}"
    if _CARRY_QUALIFIES_RE.search(statement):
        return "earlier versions"
    head = _OBS_RECOGNISED_RE.match(re.sub(r"\s+", " ", statement).strip().rstrip(".").strip())
    if head is None:
        return UNRECOGNISED_HISTORY
    rest = head.group("tail")
    if rest and (_PERSISTENT_RE.search(rest) or _CLAUSE_MARKER_RE.search(rest)
                 or not any(rx.match(rest) for rx in _OBS_TAILS)):
        return UNRECOGNISED_HISTORY
    return ""


_DATA_LOSS_RE = re.compile(r"\bdata loss\b|\b(?:recordings?|files?|projects?|scene collections?|data)\b[^.]{0,40}"
                           r"\b(?:lost|deleted|corrupt\w*|overwritten|wiped)\b", re.I)
_INSTALL_FAIL_RE = re.compile(r"\b(?:fail(?:s|ed|ing)? to install|install(?:ation|er)? (?:fail\w*|error)|"
                              r"could not be installed|cannot be installed|might not install)\b", re.I)
# A feature that stops working outright. "where <subject> did not work", "causing <subject> to fail".
_BREAK_WHERE_RE = re.compile(r"\bwhere (?P<np>[^,;]+?) (?:did not work|does not work|didn't work|doesn't work|"
                             r"stopped working|no longer worked|no longer works|would break|broke|would fail|"
                             r"failed|fails|would not (?:start|load|open|connect))\b(?P<ctx>.*)$", re.I)
_BREAK_CAUSING_RE = re.compile(r"\bcausing (?P<np>[^,;]+?) to (?:fail|break|stop working)\b(?P<ctx>.*)$", re.I)
_LAG_RE = re.compile(r"\b(?:lag|lagging|latency|slow|slowness|stutter\w*|delay(?:ed|s)?|sluggish)\b", re.I)
_COSMETIC_RE = re.compile(r"\b(?:styled|style|spacing|cosmetic|visual|appearance|misaligned|alignment|icons?|"
                          r"tooltips?|typo|colou?rs?|fonts?|scrollbars?|progress bars?|padding|margins?)\b", re.I)
_PREFERENCE_RE = re.compile(r"\b(?:preferences?|settings?|profiles?|default value|set (?:to|it to)|reset)\b", re.I)


def _obs_versions(statement: str) -> list[str]:
    named: list[str] = []
    for m in _OBS_NAMED_RE.finditer(statement):
        first, rest = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        named.append(first)
        named.extend(re.findall(r"\d+\.\d+\.\d+", rest or "", re.ASCII))
    return list(dict.fromkeys(named))


def _scope_np(np: str) -> str:
    np = np.strip()
    np = re.sub(r"^(?:the|a|an) ", "", np, flags=re.I)
    return np


def classify_obs_statement(statement: str) -> dict[str, str]:
    """{severity, failure_kind, scope} for one OBS fix bullet, or {excluded: reason}.

    Severity comes from the defect the bullet names, through a CLOSED grammar: a crash / freeze head
    noun, or "where <feature> did not work" / "causing <feature> to fail" (the feature stops working
    outright), or data loss, or an installation failure. A lag, a cosmetic issue and a preference or
    profile reset are excluded BEFORE that, unless the head noun is a crash (a crash outranks those).
    A crash, freeze or hang is serious only on launch or in a CORE workflow the "when ..." clause names
    (review 2, LOW-2; G38 WS2 review, LOW-1): otherwise it has no severity basis. A defect the vendor calls
    uncertain anywhere in the bullet ("a possible crash", "a rare freeze", "a crash that could occur", "may
    happen", "in some cases") is `uncertain_severity`: refused, and queued for a person (G38 WS2 review 2,
    LOW-1). A serious defect whose bullet says more than the grammar reads is `unrecognised_wording`
    (`_obs_unrecognised`): refused, and queued -- so a carry-over remark never becomes a "new" WAIT and never
    reaches the scope. Anything without a severity basis is excluded."""
    text = re.sub(r"\s+", " ", statement).strip()
    os_m = _OS_RE.search(text)
    os_name = os_m.group(1) if os_m else ""
    head = _OBS_HEAD_RE.match(text)
    if head:
        kind = head.group("kind").lower()
        when = _WHEN_RE.search(text)
        # The core-flow rule holds for a freeze or a hang as for a crash (G38 WS2 review, LOW-1): "a freeze
        # when closing the About dialog" or "a hang when opening the Help menu" breaks no core workflow.
        core = bool(when) and bool(_OBS_CORE_FLOW_RE.search(when.group(1))) \
            and not _OBS_NOT_CORE_RE.search(when.group(1))
        launch = bool(_LAUNCH_RE.search(text))
        if kind == "crash":
            severity = ("crash_on_launch" if launch else
                        "crash_in_core_flow" if core else "")
        else:
            severity = "substantial_workflow_breakage" if launch or core else ""
        if when:
            clause = when.group(1).strip().rstrip(".")
            scope = f"when {clause}" if clause else ""
            if os_name and f"on {os_name}" not in clause:
                scope += f" on {os_name}"
        elif os_name:
            scope = f"if you use {os_name}"
        else:
            scope = ""  # no affected setup stated: `_scope_ok` refuses it when it is proposed
        if head.group("q") or _UNCERTAIN_RE.search(text):
            return {"excluded": "uncertain_severity", "severity": severity, "failure_kind": kind, "scope": scope,
                    "note": f"the vendor calls this {kind} uncertain" + ("" if severity else
                                                                        ", outside a launch or a core workflow")}
        if not severity:
            return {"excluded": "no_severity_basis", "note": f"a {kind} outside a launch or a core workflow"}
        # The vendor's hedge was read just above, once (G38 WS2 review 2, LOW-1: MM21).
        return _recognised(text, {"severity": severity, "failure_kind": kind, "scope": scope}, hedges=False)
    if _LAG_RE.search(text):
        return {"excluded": "minor_lag"}
    if _COSMETIC_RE.search(text):
        return {"excluded": "narrow_cosmetic"}
    if _PREFERENCE_RE.search(text):
        return {"excluded": "recoverable_preference_or_profile"}
    if _DATA_LOSS_RE.search(text):
        severity, kind = "data_loss", "data loss"
    elif _INSTALL_FAIL_RE.search(text):
        return _recognised(text, {"severity": "critical_install_failure", "failure_kind": "install failure",
                                  "scope": INSTALL_SCOPE})
    else:
        severity, kind = "", ""
    m = _BREAK_WHERE_RE.search(text) or _BREAK_CAUSING_RE.search(text)
    if m:
        severity = severity or "substantial_workflow_breakage"
        kind = kind or "stops working"
        np = _scope_np(m.group("np"))
        if not np or len(np.split()) > 8 or re.search(r"\b(?:user|you|it|this|that)\b", np, re.I):
            return _recognised(text, {"severity": severity, "failure_kind": kind, "scope": ""})
        scope = f"if you use {np}"
        ctx = (m.group("ctx") or "").strip().rstrip(".")
        if os_name and f"on {os_name}" not in np:
            scope += f" on {os_name}"
        elif re.match(r"^in the [A-Za-z][\w -]{0,30}$", ctx):
            scope += f" {ctx}"
        return _recognised(text, {"severity": severity, "failure_kind": kind, "scope": scope})
    if severity:
        return _recognised(text, {"severity": severity, "failure_kind": kind, "scope": ""})
    return {"excluded": "no_severity_basis"}


def _recognised(text: str, info: dict[str, str], *, hedges: bool = True) -> dict[str, str]:
    """`info` (a serious defect) when the vendor does not hedge it and every word of the bullet is recognised;
    otherwise the refusal that sends it to the review queue (G38 WS2 review 2: LOW-1, MAJOR-3). `hedges`
    False: the caller already read the hedge."""
    if hedges and _UNCERTAIN_RE.search(text):
        return {"excluded": "uncertain_severity", **info, "note": f"the vendor calls this {info['failure_kind']} "
                                                                  "uncertain"}
    unrecognised = _obs_unrecognised(text)
    if unrecognised:
        return {"excluded": "unrecognised_wording", **info,
                "note": f"the producer does not recognise {unrecognised}: it may say the defect is older, or narrower"}
    return info


def _obs_statements(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Every OBS fix bullet that names at least one version, deduplicated: hotfix notes repeat the
    earlier hotfixes' lists, so a statement is cited at the EARLIEST release whose notes carry it."""
    obs = sorted((r for r in records if _s(r.get("product_id")) == OBS),
                 key=lambda r: (_s(r.get("update_published_at")), _s(r.get("update_version"))))
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in obs:
        body = str(rec.get("official_patch_notes_body") or "")
        fixed_in = _s(rec.get("update_version"))
        for line_no, line in enumerate(body.replace("\r\n", "\n").split("\n"), start=1):
            m = _OBS_BULLET_RE.match(line)
            if not m:
                continue
            statement = re.sub(r"\s+", " ", m.group(1)).strip()
            named = [v for v in _obs_versions(statement) if v != fixed_in]
            key = (statement.lower(), ",".join(named))
            if key in seen:
                continue
            seen[key] = {"statement": statement, "named": named, "fixed_in": fixed_in, "line": line_no,
                         "record": rec, "body_sha256": _sha(body)}
    return list(seen.values())


def _obs_candidates(records: list[Mapping[str, Any]], pages: Mapping[tuple[str, str, str], Mapping[str, Any]],
                    out: "ProducerResult") -> None:
    for st in _obs_statements(records):
        rec = st["record"]
        source = {"record": _s(rec.get("permalink")), "field": "official_patch_notes_body", "line": st["line"],
                  "url": _s(rec.get("official_patch_notes_source_url") or rec.get("update_source_url")),
                  "statement": st["statement"]}
        verdict_info = classify_obs_statement(st["statement"])
        if not st["named"]:
            out.exclude(VENDOR_CLASS, "no_exact_version", source, product_id=OBS,
                        note="the bullet names no affected version",
                        also=verdict_info.get("excluded") or verdict_info.get("severity", ""))
            continue
        for version in st["named"]:
            page = pages.get((OBS, version, ""))
            if page is None:
                out.exclude(VENDOR_CLASS, "no_exact_page", source, product_id=OBS, update_version=version)
                continue
            problem_key = "obs: " + st["statement"].lower()
            if "excluded" in verdict_info:
                out.exclude(VENDOR_CLASS, verdict_info["excluded"], source, product_id=OBS, update_version=version,
                            severity=verdict_info.get("severity", ""), note=verdict_info.get("note", ""),
                            problem_key=problem_key)
                continue
            persists_from = _obs_persistence(st["statement"], version)
            if persists_from == UNRECOGNISED_HISTORY:
                # Unreachable while classify_obs_statement queues every unrecognised bullet; kept so the two
                # readings can never disagree into a page (fails closed).
                out.exclude(VENDOR_CLASS, "unrecognised_wording", source, product_id=OBS, update_version=version,
                            severity=verdict_info["severity"], note=persists_from, problem_key=problem_key)
                continue
            new = not persists_from
            lead = (f"OBS confirms this problem persists in OBS {version} (carried over from {persists_from})"
                    if persists_from else f"OBS confirms this problem in OBS {version}")
            reason = f"{lead}: its {st['fixed_in']} release notes say \"{st['statement']}\"."
            out.propose(_candidate(
                VENDOR_CLASS, page, verdict=_vendor_verdict(verdict_info["severity"], new),
                scope=verdict_info["scope"], reason=reason, severity=verdict_info["severity"],
                failure=st["statement"], new=new, fixed_in=st["fixed_in"],
                citation=dict(source, vendor="OBS Project"), problem_key=problem_key,
                inputs={"statement_sha256": _sha(st["statement"]), "body_sha256": st["body_sha256"]}))


def _vendor_verdict(severity: str, new: bool) -> str:
    """WAIT where the vendor names this version as where the serious defect starts; TEST FIRST for a
    carried-over defect (never called new) and for an installation failure (the policy's install
    treatment: TEST FIRST, never WAIT)."""
    if severity == "critical_install_failure" or not new:
        return "TEST FIRST"
    return "WAIT"


# ============================================================ vendor_confirmed_serious: Windows

_WIN_HEADER_RE = re.compile(r"^Microsoft Release Health status \(official\) for Windows 11 ([0-9]{2}H[12]):", re.M | re.ASCII)
_WIN_ROW_RE = re.compile(
    r"^- (?P<state>Active|Resolved): (?P<summary>.+?) — status (?P<status>[^;]+); originating "
    r"(?:OS Build (?P<build>[0-9]{5}\.[0-9]{1,5}) (?P<kb>KB[0-9]{7})|(?P<other>[^;]+)); last updated [^;]+?"
    r"(?:; resolved by (?P<resolved>KB[0-9]{7}))?(?:; safeguard ID [0-9]+)?\.$", re.M)
# Where Microsoft's description sentence starts (the roll-up joins title and description).
_WIN_DESC_START_RE = re.compile(r" (?=(?:This issue|Microsoft has|Microsoft is|Some |After installing|When |"
                                r"You might|Users might|Affected )\b)")
_WIN_AFFECTS_RE = re.compile(r"\bThis issue affects (?P<np>[^.]+?)\.")
_WIN_OCCURS_IN_RE = re.compile(r"\bthis issue occurring in (?:some )?(?P<np>[^.]+?)\.", re.I)
_WIN_CRASH_RE = re.compile(r"\b(?:close unexpectedly|closes unexpectedly|stop responding|stops responding|crash\w*)\b", re.I)
_WIN_BREAK_RE = re.compile(r"\b(?:might fail\b|fail to (?:start|connect|open|load|boot)|might not (?:start|work|connect|"
                           r"open|load|boot)|black screen|blue screen|no sound|unable to sign in|be unable to|cannot sign in|"
                           r"lose (?:their |its )?(?:secure )?trust relationship|boot loop)", re.I)
_WIN_DATA_LOSS_RE = re.compile(r"\b(?:data loss|lose (?:data|files)|files? might be deleted|corrupt\w*)\b", re.I)
_WIN_LAG_RE = re.compile(r"\b(?:slow|slower|lag|latency|delay\w*|performance)\b", re.I)
_WIN_COSMETIC_RE = re.compile(r"\b(?:display incorrectly|appear incorrectly|cosmetic|visual|misaligned|icons?|"
                              r"animation|wallpaper)\b", re.I)
# FAIL CLOSED (G38 WS2 review 2, MAJOR-3; brief item 3). Microsoft states where an issue STARTS in a structured
# field (the originating build), so a known issue is new in that update -- WAIT -- only when nothing in its title
# and description speaks about its history. Any history or carry-over word there ("also affects earlier
# updates", "since the June update", "still", "first", "or later", "previously" ...) makes the row
# `unrecognised_wording`: refused and queued for a person, never published as new and never as "persists".
_WIN_HISTORY_RE = re.compile(_PERSISTENT_RE.pattern + r"|" + _CARRY_WORD_RE.pattern, re.I)


def _win_subject_scope(subject: str) -> str:
    words = subject.split()
    if not words or len(words) > 10:
        return ""
    first = words[0]
    keep = first.isupper() or (len(words) > 1 and words[1][:1].isupper())
    lead = first if keep else first[:1].lower() + first[1:]
    return "if you use " + " ".join([lead] + words[1:])


def classify_windows_issue(summary: str) -> dict[str, str]:
    """{severity, title, scope} for one release-health known-issue summary, or {excluded: reason}."""
    text = re.sub(r"\s+", " ", summary).strip().rstrip("…").strip()
    parts = _WIN_DESC_START_RE.split(text, maxsplit=1)
    title, desc = parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")
    if " might " not in title:
        return {"excluded": "no_severity_basis", "title": title}
    subject, predicate = title.split(" might ", 1)
    if _WIN_DATA_LOSS_RE.search(predicate):
        severity = "data_loss"
    elif _INSTALL_FAIL_RE.search(predicate):
        severity = "critical_install_failure"
    elif _WIN_CRASH_RE.search(predicate):
        severity = "crash_in_core_flow"
    elif _WIN_BREAK_RE.search("might " + predicate):
        severity = "substantial_workflow_breakage"
    else:
        severity = ""
    if severity in ("", "substantial_workflow_breakage") and _WIN_LAG_RE.search(predicate):
        return {"excluded": "minor_lag", "title": title}
    if severity in ("", "substantial_workflow_breakage") and _WIN_COSMETIC_RE.search(predicate):
        return {"excluded": "narrow_cosmetic", "title": title}
    if not severity:
        return {"excluded": "no_severity_basis", "title": title}
    # The affected setup, from Microsoft's own words, in this order: "This issue affects <setup>",
    # "this issue occurring in <setup>", the title's subject. The FIRST that names a setup wins
    # (`scope_problem`); "This issue affects a small number of devices" names none, so the subject is
    # tried next, and with a generic subject too ("Devices might ...") the scope stays "" -- refused as
    # an ambiguous scope when proposed, and queued for a person (review 1, MAJOR-1).
    affects = _WIN_AFFECTS_RE.search(desc)
    occurs = _WIN_OCCURS_IN_RE.search(desc)
    options = ([f"for {affects.group('np').strip()}"] if affects else []) \
        + ([f"if you use {occurs.group('np').strip()}"] if occurs else []) \
        + [_win_subject_scope(subject.strip())]
    scope = next((s for s in options if s and not scope_problem(s, WINDOWS)), "")
    refused = "; ".join(f"{s!r}: {scope_problem(s, WINDOWS)}" for s in options if s) if not scope else ""
    return {"severity": severity, "title": title, "scope": scope, "scope_refused": refused}


def _windows_candidates(records: list[Mapping[str, Any]], out: "ProducerResult") -> None:
    by_exact: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for rec in records:
        if _s(rec.get("product_id")) == WINDOWS:
            by_exact[(verdict_reasons.liquid_strip(rec.get("update_version")),
                      verdict_reasons.liquid_strip(rec.get("target_build")),
                      verdict_reasons.liquid_strip(rec.get("target_kb")))] = rec
    seen: set[tuple[str, str, str]] = set()
    for rec in sorted((r for r in records if _s(r.get("product_id")) == WINDOWS),
                      key=lambda r: (_s(r.get("update_published_at")), _s(r.get("target_build"))), reverse=True):
        body = str(rec.get("official_patch_notes_body") or "")
        header = _WIN_HEADER_RE.search(body)
        if not header:
            continue
        line = header.group(1)
        if line != _s(rec.get("update_version")):
            continue  # a roll-up stored on a record of another servicing line is not read
        offset = body[:header.start()].count("\n")
        for m in _WIN_ROW_RE.finditer(body, header.end()):
            info = classify_windows_issue(m.group("summary"))
            key = (line, info.get("title", m.group("summary"))[:120], m.group("kb") or m.group("other") or "")
            if key in seen:
                continue  # the newest record's roll-up wins (sorted newest first)
            seen.add(key)
            row_line = offset + body[header.start():m.start()].count("\n") + 1
            source = {"record": _s(rec.get("permalink")), "field": "official_patch_notes_body", "line": row_line,
                      "url": _s(rec.get("official_patch_notes_source_url") or rec.get("update_source_url")),
                      "statement": re.sub(r"\s+", " ", m.group(0)).strip()}
            if not m.group("kb"):
                out.exclude(VENDOR_CLASS, "no_exact_version", source, product_id=WINDOWS, update_version=line,
                            note="the originating build is not stated")
                continue
            page = by_exact.get((line, m.group("build"), m.group("kb")))
            if page is None:
                out.exclude(VENDOR_CLASS, "no_exact_page", source, product_id=WINDOWS, update_version=line,
                            target_build=m.group("build"))
                continue
            problem_key = f"windows: {info.get('title', '').lower()} ({m.group('kb')})"
            if "excluded" in info:
                out.exclude(VENDOR_CLASS, info["excluded"], source, product_id=WINDOWS, update_version=line,
                            target_build=m.group("build"), severity=info.get("severity", ""), problem_key=problem_key)
                continue
            resolved = m.group("resolved") or ""
            status = (f"; Microsoft marks it resolved by {resolved}" if resolved
                      else f"; Microsoft lists it as {m.group('status').strip().lower()}")
            # The originating build is where Microsoft says the issue STARTS; a word about its history in the
            # text makes that uncertain, so a person reads it (review 2 LOW-1, A3; G38 WS2 review 2, MAJOR-3).
            history = _WIN_HISTORY_RE.search(m.group("summary"))
            if history:
                out.exclude(VENDOR_CLASS, "unrecognised_wording", source, product_id=WINDOWS, update_version=line,
                            target_build=m.group("build"), severity=info["severity"], problem_key=problem_key,
                            note=f"Microsoft's text speaks about the issue's history ({history.group(0)!r}): a person "
                                 "decides whether it starts in this update")
                continue
            new = True
            lead = "Microsoft lists a known issue that originates in this update"
            reason = f"{lead} (OS build {m.group('build')}, {m.group('kb')}): \"{info['title']}\"{status}."
            candidate = _candidate(
                VENDOR_CLASS, page, verdict=_vendor_verdict(info["severity"], new), scope=info["scope"],
                reason=reason, severity=info["severity"], failure=info["title"], new=new,
                fixed_in=resolved, citation=dict(source, vendor="Microsoft"), problem_key=problem_key,
                inputs={"statement_sha256": _sha(source["statement"]), "body_sha256": _sha(body)})
            if info.get("scope_refused"):
                # Why no wording named a setup, for the review queue (VERIFY_3 note 3: it read only "scope ''").
                candidate["scope_note"] = info["scope_refused"]
            out.propose(candidate)


# ============================================================ user_corroborated_install_failure

# Calibration G35-05 (section 4/5), ported verbatim in behaviour: stored fields only (title, excerpt,
# URL, applicability, the page's KB / build / version); never issue_theme, severity or sentiment.
_INSTALL_RX = re.compile(
    r"(install(?:ation)? (?:error|fail|issue|problem)|fail(?:ed|s|ing)? to (?:install|download)|"
    r"(?:will|would|could|does|did)(?: not|n't) install|can(?:'|no)?t install|cannot install|unable to install|"
    r"won't install|not install|download(?:ing)? error|keeps? (?:failing|giving me the message)|try again|"
    r"death loop|update(?:s)? (?:fail|failed|failing)|installation fail|failed to update|backed out)")
# The install wordings that can take the update as their OBJECT ("failed to install KB5072033", "unable to
# install the 2025-12 Security Update (KB...)", "Install error - 0x... 2025-11 Preview Update (KB...)").
_INSTALL_TRANSITIVE_RX = re.compile(
    r"^(?:fail(?:ed|s|ing)? to (?:install|download)|(?:will|would|could|does|did)(?: not|n't) install|"
    r"can(?:'|no)?t install|cannot install|unable to install|won't install|not install|"
    r"install(?:ation)? (?:error|fail|issue|problem)|download(?:ing)? error|failed to update)")
_EXIT7_RX = re.compile(r"exit code:?\s*7\b")
# Windows install errors are HRESULTs: exactly eight hex digits, read without a trailing word boundary so a
# code glued to the next word still reads ("0x800f0983How", "0x800f09912026": review 2, note 12). A
# shorter code must end at a word boundary.
_CODE_RX = re.compile(r"\b0x(?:[0-9a-f]{8}|[0-9a-f]{3,7}\b)")
# A code inside a crash or bugcheck report is not an install error ("HYPERVISOR_ERROR 0x20001", review 2
# LOW-3): read on the 60 characters before the code.
_CRASH_CONTEXT_RX = re.compile(r"(?:bug ?check|bsod|blue ?screen|stop (?:code|error)|crash\w*|minidump|kernel|"
                               r"[a-z]+_(?:error|exception|failure|violation))[^.;\n]{0,40}$")
# A code LABELLED as an install or download error is in install-error context wherever it stands ("Install
# error - 0x...", "Download error - 0x...", "Errore di installazione - 0x..."); read on the text right
# before the code. In the clause after one that reports this update failing, an "error" / "code" label is.
_INSTALL_ERROR_LABEL_RX = re.compile(r"(?:install\w*|download\w*)\W{0,3}(?:error|errore|fehler|erreur|failure)\W{0,5}$|"
                                     r"(?:error|errore|fehler|erreur)\W{0,3}(?:de |di |d')?(?:install\w*|download\w*)"
                                     r"\W{0,5}$")
_ERROR_LABEL_RX = re.compile(r"\b(?:error|code)\b[^.;\n]{0,12}$")
# A DECLARED copy: the author says this row repeats or continues their own earlier post -- a cross-post, a
# re-post, a follow-up ("following up on my question from last week", "reposting", "my previous thread";
# G38 WS2 review, MAJOR-1), or an explicit copy ("I asked the same question on the Tech Community", "this is a
# copy of my post", "duplicate of my question", "copying my question from ..."; G38 WS2 review 2, LOW-5). Such
# a row is never a second reporter. A SUPPLEMENT only: what keeps a copy from counting twice is that a second
# reporter needs an own-machine statement the first one contradicts (`incident_details`), and that a shared
# distinctive passage joins two rows whatever they state (`same_reporter`).
_XPOST_RX = re.compile(r"(previously posted|also posted|cross-?post|posted (?:this|it) (?:on|in)|i recently posted|"
                       r"part 2|part two|follow(?:ing)?[- ]?up (?:on|to|from) my|\bre-?post(?:ing|ed|s)?\b|"
                       r"posting (?:this |it )?again|(?:i )?posted (?:this |it )?(?:before|earlier|already|yesterday|"
                       r"last week)|my (?:earlier|previous|original|last|other) (?:post|question|thread|topic)|"
                       r"same as my (?:earlier|previous|other|original) |"
                       r"\b(?:asked|posted|posting|asking) (?:the |this )?(?:same|identical) (?:question|post|thing)|"
                       r"\b(?:a |an )?(?:exact )?(?:copy|duplicate|dupe) of my (?:own )?(?:post|question|thread|topic)|"
                       r"\bcopy(?:ing)? (?:over )?my (?:own )?(?:post|question|thread|topic)|"
                       r"\bcopied (?:over )?(?:my|this) (?:own )?(?:post|question|thread|topic)|"
                       r"\bcopy(?:ing)? (?:this|it) (?:over )?(?:from|to) )")
_LOGURL_RX = re.compile(r"obsproject\.com/logs/[a-z0-9]+", re.I)
_STOP = set("the a an and or of to in on for with is are was it its this that my i me we our you your after when "
            "not no from at by be as but if any all can can't cannot does doesn't won't will update updates windows "
            "microsoft q&a adobe acrobat reader dc pro davinci resolve obs studio premiere issue issues problem "
            "problems help error version build kb 11 25h2 24h2 23h2 26h2 26h1 studio free".split())
_TEMPLATE_RX = (
    re.compile(r"###\s*[a-z /()]+?(?=###|$)", re.I),
    re.compile(r"_no response_", re.I),
    re.compile(r"exit code:?\s*7 please see specific errors below for troubleshooting\. for example, error:[^.]*", re.I),
    re.compile(r"-{5,}\s*summary\s*-{5,}|- ?\d+ fatal error\(s\), \d+ error\(s\)|-{5,}|payload:", re.I),
    re.compile(r"\b20\d\d-\d\d (?:cumulative |preview |security )?update[^)]*\(kb\d{7}\)\s*\([\d.]+\)", re.I),
    re.compile(r"install(?:ation)? error\s*-?\s*0x[0-9a-f]+|download(?:ing)? error\s*-?\s*0x[0-9a-f]+", re.I),
    re.compile(r"- microsoft q&a", re.I),
)
INDEPENDENCE_JACCARD = 0.45   # I10: template-stripped token overlap at or above this is one report
# A distinctive passage: this many consecutive content words (template-stripped, function words removed)
# shared by two rows make them one report, however the rest is reworded (review 1 LOW-2, review 2 LOW-4).
SHARED_PASSAGE_WORDS = 8
# Strict install grouping (Amendment A3, the default): rows are ONE problem only when they share a specific
# failure characteristic -- the same install error code, the same named stage (rolls back; stops at the same
# percentage) or, for Acrobat, the installer's Exit Code 7. "lenient" is A1's superseded reading (any install
# failure is one problem), kept only so the two readings can be measured side by side.
INSTALL_GROUPING = "strict"
INSTALL_GROUPINGS = ("strict", "lenient")
# A source-provided reporter identity on a counted row. The evidence schema stores none today (no collector
# writes an author field), so independence rests on incident details alone; a row that carries one is
# compared by it.
REPORTER_ID_FIELD = "source_reporter_id"


def _txt(row: Mapping[str, Any]) -> str:
    return (_s(row.get("report_title")) + " \n " + _s(row.get("report_text_excerpt"))).lower()


def _stripped(row: Mapping[str, Any]) -> str:
    text = _s(row.get("report_title")) + " " + _s(row.get("report_text_excerpt"))
    for rx in _TEMPLATE_RX:
        text = rx.sub(" ", text)
    return text.lower()


def _content_words(row: Mapping[str, Any]) -> list[str]:
    """The row's content words in order: template-stripped, function words dropped, and a word's trailing
    punctuation dropped ("retry." and "retry" are one word; "26200.7623" keeps its inner dot)."""
    words = (w.rstrip(".+-") for w in re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", _stripped(row)))
    return [w for w in words if len(w) >= 3 and w not in _STOP]


def _content_tokens(row: Mapping[str, Any]) -> set[str]:
    return set(_content_words(row))


def _passages(row: Mapping[str, Any]) -> set[tuple[str, ...]]:
    words = _content_words(row)
    n = SHARED_PASSAGE_WORDS
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _kb_set(row: Mapping[str, Any]) -> set[str]:
    return set(re.findall(r"kb ?(\d{7})", _txt(row)))


# ---------------------------------------------------------------- incident details (independence)
# AUTH_V2_37 correction 2: reporter independence FAILS CLOSED. Text similarity may DETECT that two rows are
# one report; it can never ESTABLISH that two unknown accounts are two people. A second report counts only
# when the source supports a DISTINCT identity (REPORTER_ID_FIELD, different on both rows, from the same source
# site) or a DISTINCT MACHINE: both rows state a detail of the same IDENTITY kind (IDENTITY_DETAIL_KINDS) and the
# values cannot belong to one machine -- two different computers (manufacturer or model family), processors,
# Windows editions or architectures, or operating systems (an Acrobat installer on a Mac and on Windows 10). A
# row that states no such detail cannot be told apart from anyone, so it never makes a second reporter: unknown
# is not independent.
# WHERE identity details come from (G38 WS2 review 2, MAJOR-1; round-3 brief item 1): ONLY the reporter's own
# statements about their own machine, read through a closed grammar (`_own_machine_phrases`):
#   * "my / our [new | work | old ...] <computer>": a computer family ("my ThinkPad T14", "our Surface Laptop 7",
#     "my MacBook Pro", "my Mac"), a manufacturer beside a computer noun ("my Dell laptop", "our HP desktops"),
#     a Windows computer ("my Windows 10 PC"), or a manufacturer that ends the phrase ("on my Dell.");
#   * "I'm on / I am on / I'm running / I am running / I have [a | an | the] <system>", the system named right
#     there: a computer ("I have a Dell Desktop XPS 8930"), an operating system ("I'm on Windows 10", "I'm running
#     macOS Sonoma"), a processor or an architecture;
#   * a system-information line ("Edition Windows 11 Pro", "Processor 13th Gen Intel(R) Core(TM) i9", "System
#     type 64-bit operating system, x64-based processor", "System Manufacturer: Dell").
# NEVER from anything else -- an app or product name ("Microsoft PC Manager", "Microsoft Remote Desktop", "the HP
# Smart app"), a file path ("C:\Program Files (x86)"), an update title ("... for x64-based Systems (KB...)"), a
# question about another download ("Is the Mac download any different?") or a third party ("my brother's HP
# laptop") -- and never from a bare manufacturer: "Microsoft" is not a computer brand here (the Surface families
# are). Anything the grammar does not read is unknown, and unknown is not independent.
# What ONE person on ONE machine can show twice is never a second incident (G38 WS2 review, MAJOR-1): a
# retry that stops at another percentage, a CPU at 100% beside an install at 20%, the same Mac upgraded from
# Sierra to High Sierra between two posts. Failure points and OS versions are COPY_ONLY_DETAIL_KINDS: read
# (anywhere in the row) only as copy-detection cues, never as independence and never as a conflict.
IDENTITY_DETAIL_KINDS = ("architecture", "cpu", "device", "edition", "os")
COPY_ONLY_DETAIL_KINDS = ("failure_point", "os_version")
_DEVICE_FAMILY_RX = (
    ("surface", re.compile(r"\bsurface (?:laptop|pro|book|go|studio)\b")),
    ("lenovo", re.compile(r"\b(?:ideapad|thinkpad|thinkbook|thinkcentre|legion|yoga)\b")),
    ("dell", re.compile(r"\b(?:xps|inspiron|latitude|optiplex|alienware|vostro)\b")),
    ("hp", re.compile(r"\b(?:elitebook|probook|zbook|pavilion|victus|elitedesk|prodesk)\b")),
    ("asus", re.compile(r"\b(?:zenbook|vivobook|rog strix|tuf gaming)\b")),
    ("acer", re.compile(r"\b(?:aspire|predator helios|travelmate)\b")),
    ("huawei", re.compile(r"\bmatebook\b")),
    ("toshiba", re.compile(r"\bdynabook\b")),
    ("samsung", re.compile(r"\bgalaxy book\b")),
    ("apple", re.compile(r"\b(?:macbook|imac|mac mini|mac pro|mac studio|mac)\b")),
)
# The computer manufacturers. NOT "microsoft" (G38 WS2 review 2, MAJOR-1): "Microsoft PC Manager" and
# "Microsoft Remote Desktop" are apps; a Microsoft computer is named by its Surface family.
_DEVICE_BRANDS = ("dell", "hp", "lenovo", "asus", "acer", "msi", "samsung", "razer", "gigabyte", "huawei", "toshiba",
                  "fujitsu", "medion")
_BRAND = r"(?:" + "|".join(_DEVICE_BRANDS) + r")"
_COMPUTER_NOUN = r"(?:laptop|notebook|pc|desktop|computer|machine|tablet|workstation|ultrabook|all-in-one|rig)s?"
_MODEL_TOKEN = r"(?:[a-z]*\d[a-z0-9-]*|pro|air|max|mini|plus|ultra|carbon|nano|gen|go|flip|spin|book|studio|x)"
_FAMILY = (r"(?:surface (?:laptop|pro|book|go|studio)|ideapad|thinkpad|thinkbook|thinkcentre|legion|yoga|xps|"
           r"inspiron|latitude|optiplex|alienware|vostro|elitebook|probook|zbook|pavilion|victus|elitedesk|prodesk|"
           r"zenbook|vivobook|rog strix|tuf gaming|aspire|predator helios|travelmate|matebook|dynabook|galaxy book|"
           r"macbook|imac|mac mini|mac pro|mac studio|mac)")
_DEVICE_NP = (r"(?:" + _BRAND + r" )?(?:" + _COMPUTER_NOUN + r" )?" + _FAMILY + r"(?: " + _MODEL_TOKEN + r"){0,3}"
              r"(?: " + _COMPUTER_NOUN + r")?|" + _BRAND + r"(?: " + _MODEL_TOKEN + r"){0,2} " + _COMPUTER_NOUN)
_OS_NP = (r"(?:windows ?(?:7|8\.1|8|10|11|xp|vista)(?: (?:home|pro|enterprise|education|iot|se))?(?: (?:x64|arm64|x86))?|"
          r"mac ?os(?: x)?(?: [a-z]+| \d+(?:\.\d+)*)?|os x(?: [a-z]+| \d+(?:\.\d+)*)?|osx)")
_CPU_NP = (r"(?:(?:\d+(?:st|nd|rd|th) gen )?intel(?:\(r\))? (?:core|celeron|pentium|xeon)(?:\(tm\))?(?: (?:i[3579]|ultra)"
           r"[\w-]*)?|core(?:\(tm\))? i[3579][\w-]*|core ultra [\w-]+|(?:amd )?ryzen[\w-]*(?: \d[\w-]*)?|threadripper|"
           r"athlon|snapdragon[\w-]*(?: x)?(?: elite| plus)?|apple m\d[\w-]*)")
_ARCH_NP = r"(?:arm64|x64|x86)(?:-based)?(?: " + _COMPUTER_NOUN + r")?"
_OWN_ADJ = r"(?:(?:own|new|old|work|home|personal|company|main|primary|current|only|brand-new|second|other) )?"
_OWN_POSSESSIVE_RX = re.compile(
    r"\b(?:my|our) " + _OWN_ADJ + r"(?P<np>(?:" + _DEVICE_NP + r"|" + _OS_NP + r" " + _COMPUTER_NOUN + r")(?![\w-])|"
    + _BRAND + r"(?= ?(?:[.,;:!?)]|$)))")
_OWN_STATEMENT_RX = re.compile(
    r"\bi(?:'|’)?(?:m| am) (?:on|running) (?:(?:a|an|the|this|my) )?" + _OWN_ADJ
    + r"(?P<np>(?:" + _DEVICE_NP + r"|" + _OS_NP + r"|" + _CPU_NP + r"|" + _ARCH_NP + r")(?![\w-]))|"
    r"\bi have (?:(?:a|an|the|this|my) )?" + _OWN_ADJ
    + r"(?P<np2>(?:" + _DEVICE_NP + r"|" + _OS_NP + r"|" + _CPU_NP + r"|" + _ARCH_NP + r")(?![\w-]))")
_SYSINFO_RX = re.compile(
    r"\b(?:edition|os name|operating system)\s*:?\s*(?P<edition>(?:microsoft )?windows ?1[01] (?:home|pro|enterprise|"
    r"education|iot|se))\b|"
    r"\b(?:processor|cpu)\s*:?\s*(?P<cpu>" + _CPU_NP + r")|"
    r"\bsystem type\s*:?\s*(?P<arch>(?:\d\d-bit operating system,? )?(?:x64|arm64|x86)-based)|"
    r"\b(?:system )?manufacturer\s*:?\s*(?P<maker>" + _BRAND + r")\b|"
    r"\b(?:system )?model\s*:?\s*(?P<model>" + _FAMILY + r"(?: " + _MODEL_TOKEN + r"){0,3})(?![\w-])")
# A processor only where the row names one ("Intel(R) Core(TM) i9", "Ryzen", "Snapdragon"), never a bare
# vendor name, which is as often a driver ("failed error: Intel - SoftwareComponent").
_CPU_RX = (("intel", re.compile(r"\b(?:intel(?:\(r\))? (?:core|celeron|pentium|xeon|processor|cpu)|"
                                r"core(?:\(tm\))? i[3579]|core ultra|celeron|pentium|xeon)\b")),
           ("amd", re.compile(r"\b(?:ryzen|threadripper|athlon|amd (?:processor|cpu))\b")),
           ("qualcomm", re.compile(r"\b(?:snapdragon|qualcomm (?:processor|cpu))\b")),
           ("apple", re.compile(r"\bapple m\d")))
_EDITION_RX = re.compile(r"\bwindows ?1[01] ?(home|pro|enterprise|education|iot|se)\b")
_ARCH_RX = re.compile(r"\b(x64|arm64|x86)(?:-based)?\b")
_MAC_RX = re.compile(r"\b(?:mac|macos|mac os|os x|osx|macbook|imac|el capitan|sierra|mojave|catalina|big sur|monterey|"
                     r"ventura|sonoma|sequoia)\b")
_WINDOWS_OS_RX = re.compile(r"\b(?:windows ?(7|8\.1|8|10|11|xp|vista)|win ?(7|8|10|11))\b")
_MAC_NAMES = {"el capitan": "10.11", "high sierra": "10.13", "sierra": "10.12", "mojave": "10.14", "catalina": "10.15",
              "big sur": "11", "monterey": "12", "ventura": "13", "sonoma": "14", "sequoia": "15"}
_MAC_VERSION_RX = re.compile(r"\b(?:mac ?os(?: x)?|os x|osx)\s*(10\.\d{1,2}|1[1-9])\b|\b(10\.(?:[4-9]|1[0-5]))\.\d+\b")
_PERCENT_RX = re.compile(r"\b(?:at|to|reaches|reached|reaching|around|about|until)\s+(\d{1,3})\s?(?:%|percent\b)")


def _own_machine_phrases(text: str) -> list[str]:
    """The phrases in which the reporter names THEIR OWN machine (the closed grammar above), lower-case. Nothing
    else in a row is ever read for identity."""
    phrases = [m.group("np") for m in _OWN_POSSESSIVE_RX.finditer(text)]
    phrases += [m.group("np") or m.group("np2") for m in _OWN_STATEMENT_RX.finditer(text)]
    for m in _SYSINFO_RX.finditer(text):
        phrases += [v for v in m.groups() if v]
    return phrases


def incident_details(row: Mapping[str, Any], product_id: str = "") -> dict[str, frozenset]:
    """The concrete incident details a row states, by kind (only kinds it states): IDENTITY_DETAIL_KINDS read
    ONLY from the reporter's own-machine phrases (`_own_machine_phrases`), and COPY_ONLY_DETAIL_KINDS read
    anywhere (copy cues only)."""
    text = _blank(_txt(row), _NOT_AN_INSTALL_RX)
    found: dict[str, set] = {}

    def add(kind: str, value: str) -> None:
        found.setdefault(kind, set()).add(value)
    for phrase in _own_machine_phrases(text):
        for family, rx in _DEVICE_FAMILY_RX:
            if rx.search(phrase):
                add("device", family)
        brand = re.match(_BRAND + r"\b", phrase)
        if brand:
            add("device", brand.group(0))
        for cpu, rx in _CPU_RX:
            if rx.search(phrase):
                add("cpu", cpu)
        for m in _EDITION_RX.finditer(phrase):
            add("edition", m.group(1))
        for m in _ARCH_RX.finditer(phrase):
            add("architecture", m.group(1))
        if _s(product_id) != WINDOWS:
            if _MAC_RX.search(phrase):
                add("os", "mac")
            if _WINDOWS_OS_RX.search(phrase):
                add("os", "windows")
    if _s(product_id) != WINDOWS:
        for m in _WINDOWS_OS_RX.finditer(text):
            add("os_version", "windows-" + (m.group(1) or m.group(2)))
        for name, version in _MAC_NAMES.items():
            if re.search(r"\b" + name + r"\b", text) and not (name == "sierra" and "high sierra" in text):
                add("os_version", "macos-" + version)
        for m in _MAC_VERSION_RX.finditer(text):
            add("os_version", "macos-" + (m.group(1) or m.group(2)))
    for m in _PERCENT_RX.finditer(text):
        if int(m.group(1)) <= 100:
            add("failure_point", m.group(1) + "%")
    return {k: frozenset(v) for k, v in sorted(found.items())}


def _conflicting(a: Mapping[str, frozenset], b: Mapping[str, frozenset]) -> list[str]:
    """The IDENTITY detail kinds both state with values that cannot belong to one machine (disjoint), or [].
    Overlapping values ("my Dell" and "my Dell and my HP") can be one machine: no conflict. A failure point
    or an OS version never conflicts (one machine retried, or upgraded)."""
    return [k for k in IDENTITY_DETAIL_KINDS if a.get(k) and b.get(k) and not (a[k] & b[k])]


def _source_site(row: Mapping[str, Any]) -> str:
    m = re.match(r"^[a-z][a-z0-9+.-]*://([^/?#]+)", _s(row.get("source_url")).lower())
    return m.group(1) if m else ""


def _reporter_ids(row: Mapping[str, Any]) -> frozenset:
    """The row's source reporter id, qualified by the site it comes from: an id is an identity only on its own
    site, so ids from two different sites are never compared (one person, two sites, two account names)."""
    value = _s(row.get(REPORTER_ID_FIELD))
    return frozenset({f"{_source_site(row)}|{value}"}) if value else frozenset()


def _ids_differ(a: frozenset, b: frozenset) -> bool:
    """Whether two sets of site-qualified reporter ids show different reporters: ids of ONE site that share
    none. Ids from different sites say nothing (fails closed)."""
    sites = {i.split("|", 1)[0] for i in a} & {i.split("|", 1)[0] for i in b}
    return bool(sites) and not (a & b)


# The copy cues an identity conflict never overrides (brief item 1): the same log, and a shared distinctive
# passage -- a re-post that keeps the long passage and adds a machine detail ("I also use an HP laptop") is
# still one report. The weaker cues (near-identical short text, the same KB set, the same details) stay
# conservative: two own-machine statements that conflict keep two short, similar rows apart (AUTH item 2).
COPY_CUES_OVER_IDENTITY = ("the same log URL", "a shared distinctive passage")


def same_reporter(a: Mapping[str, Any], b: Mapping[str, Any], product_id: str = "") -> str:
    """Why rows a and b are ONE report (a copy or cross-post), or "" when no cue fires. DETECTION ONLY:
    a cue removes a would-be second reporter; no cue never makes two rows independent (that needs
    `distinct_incident`), and nothing here touches stored evidence.

    Cues: a declared cross-post, re-post, follow-up or copy; the same log URL; a shared distinctive passage
    (SHARED_PASSAGE_WORDS consecutive content words: a reworded re-post keeps one); near-identical text once
    templates are stripped; the same set of two or more KB numbers; the same source reporter id; the same
    incident details (any kinds, the copy-only ones included).
    The first three fire whatever the rows' identity details say (COPY_CUES_OVER_IDENTITY): a copy that adds a
    machine detail is still a copy. The others are CONSERVATIVE: two rows whose own-machine details conflict
    are two machines, so near-identical short wording, a shared KB set or a shared author alone never
    collapses them."""
    if _XPOST_RX.search(_txt(a)) or _XPOST_RX.search(_txt(b)):
        return "a declared cross-post"
    la = {m.lower() for m in _LOGURL_RX.findall(_s(a.get("report_text_excerpt")))}
    lb = {m.lower() for m in _LOGURL_RX.findall(_s(b.get("report_text_excerpt")))}
    if la & lb:
        return "the same log URL"
    if _passages(a) & _passages(b):
        return "a shared distinctive passage"
    da, db = incident_details(a, product_id), incident_details(b, product_id)
    if _conflicting(da, db):
        return ""
    ta, tb = _content_tokens(a), _content_tokens(b)
    if ta | tb and len(ta & tb) / len(ta | tb) >= INDEPENDENCE_JACCARD:
        return "near-identical text once templates are stripped"
    ka, kb = _kb_set(a), _kb_set(b)
    if len(ka) >= 2 and ka == kb:
        return "the same set of KB numbers"
    if _reporter_ids(a) and _reporter_ids(a) == _reporter_ids(b):
        return "the same source reporter id"
    shared = set(da) & set(db)
    if len(shared) >= 2 and all(da[k] == db[k] for k in shared):
        return "the same incident details"
    return ""


def distinct_incident(a: Mapping[str, Any], b: Mapping[str, Any], product_id: str = "") -> str:
    """What the SOURCE supports as a different reporter or incident for a and b (row or cluster
    mappings: `details`, `reporter_ids`), or "" -- unknown is never independent (fails closed)."""
    conflict = _conflicting(a["details"], b["details"])
    if conflict:
        return "different " + " and ".join(k.replace("_", " ") for k in conflict)
    if a["reporter_ids"] and b["reporter_ids"] and _ids_differ(a["reporter_ids"], b["reporter_ids"]):
        return "different source reporter ids"
    return ""


def _may_join(why: str, a: Mapping[str, frozenset], b: Mapping[str, frozenset]) -> bool:
    """Whether two clusters a copy cue links may become ONE report: always on a cue identity never overrides
    (COPY_CUES_OVER_IDENTITY); otherwise never when their merged identity details conflict (a detail-less third
    row that is near-identical to both never bridges two machines; review P2b)."""
    return why in COPY_CUES_OVER_IDENTITY or not _conflicting(a, b)


def _merge_details(rows: list[Mapping[str, frozenset]]) -> dict[str, frozenset]:
    merged: dict[str, set] = {}
    for d in rows:
        for k, v in d.items():
            merged.setdefault(k, set()).update(v)
    return {k: frozenset(v) for k, v in sorted(merged.items())}


def _max_clique(n: int, edge: Any) -> list[int]:
    """The largest set of vertices 0..n-1 pairwise joined by `edge`; ties go to the lexicographically
    smallest index list (deterministic). Bron-Kerbosch with pivoting; the graphs here are a few dozen
    vertices at most, because a cluster that states no detail and no reporter id has no edge at all."""
    adj = [{j for j in range(n) if j != i and edge(i, j)} for i in range(n)]
    best: list[list[int]] = [[]]

    def expand(r: list[int], p: set[int], x: set[int]) -> None:
        if not p and not x:
            cand = sorted(r)
            if len(cand) > len(best[0]) or (len(cand) == len(best[0]) and cand < best[0]):
                best[0] = cand
            return
        if len(r) + len(p) < len(best[0]):
            return
        pivot = max(p | x, key=lambda u: (len(adj[u] & p), -u))
        for v in sorted(p - adj[pivot]):
            expand(r + [v], p & adj[v], x & adj[v])
            p = p - {v}
            x = x | {v}
    expand([], set(range(n)), set())
    return best[0]


def independent_reporters(rows: list[Mapping[str, Any]], product_id: str = "",
                          ) -> tuple[list[Mapping[str, Any]], list[dict[str, str]]]:
    """(one kept row per INDEPENDENT report, dropped rows with why). Fails closed.

    1. A declared cross-post, re-post or follow-up never counts.
    2. Rows one report under `same_reporter` are joined (union-find over EVERY pair, so a row matching
       only a row that is itself joined to another still joins that one: a copy of a copy is one report).
       CONSERVATIVE at the cluster too: a join that would put machines whose identity details conflict
       into one report is refused (a detail-less third row quoting the same text never bridges a Dell
       and a ThinkPad incident; review P2b), except on the same log URL.
    3. Reports count together only where every pair is a `distinct_incident`: the largest such set is
       kept (`_max_clique` returns at least one cluster whenever there is one). One report with no stated
       detail is one reporter; two of them are still one."""
    ordered = sorted(rows, key=lambda r: (_s(r.get("source_date")), _s(r.get("id"))))
    dropped: list[dict[str, str]] = []
    live = []
    for row in ordered:
        if _XPOST_RX.search(_txt(row)):
            dropped.append({"id": _s(row.get("id")), "why": "a declared cross-post"})
        else:
            live.append(row)
    parent = list(range(len(live)))
    cluster_details = {i: incident_details(row, product_id) for i, row in enumerate(live)}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    joined_by: dict[int, str] = {}
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            why = same_reporter(live[i], live[j], product_id)
            ri, rj = find(i), find(j)
            if not why or ri == rj or not _may_join(why, cluster_details[ri], cluster_details[rj]):
                continue
            joined_by.setdefault(j, f"one report with {_s(live[i].get('id'))}: {why}")
            parent[rj] = ri
            cluster_details[ri] = _merge_details([cluster_details[ri], cluster_details.pop(rj)])
    clusters: dict[int, list[int]] = {}
    for i in range(len(live)):
        clusters.setdefault(find(i), []).append(i)
    groups = sorted(clusters.values(), key=lambda members: members[0])
    info = [{"details": _merge_details([incident_details(live[i], product_id) for i in g]),
             "reporter_ids": frozenset().union(*[_reporter_ids(live[i]) for i in g])} for g in groups]
    chosen = _max_clique(len(groups), lambda a, b: bool(distinct_incident(info[a], info[b], product_id)))
    kept = [live[groups[c][0]] for c in chosen]
    for gi, members in enumerate(groups):
        for pos, i in enumerate(members):
            if gi in chosen and pos == 0:
                continue
            why = joined_by.get(i) or ("the source does not establish a different reporter or incident from "
                                      "the reports counted")
            dropped.append({"id": _s(live[i].get("id")), "why": why})
    dropped.sort(key=lambda d: d["id"])
    return kept, dropped


def independence_basis(kept: list[Mapping[str, Any]], product_id: str = "") -> list[str]:
    """The detail kinds (never their values) that separate the kept reports: what a reviewer checks."""
    kinds: set[str] = set()
    for i in range(len(kept)):
        for j in range(i + 1, len(kept)):
            a = {"details": incident_details(kept[i], product_id), "reporter_ids": _reporter_ids(kept[i])}
            b = {"details": incident_details(kept[j], product_id), "reporter_ids": _reporter_ids(kept[j])}
            kinds.update(_conflicting(a["details"], b["details"]))
            if a["reporter_ids"] and b["reporter_ids"] and _ids_differ(a["reporter_ids"], b["reporter_ids"]):
                kinds.add("source_reporter_id")
    return sorted(kinds)


# Review 1, MAJOR-2: a row "about" this update is not a row reporting that THIS update fails to install.
# Install wording that is denied ("The issue is not that the update fails to install but that it does
# install and then ..."; "it did not fail to install, it installed fine") never counts: the whole row
# is refused.
_INSTALL_NEGATION_RX = re.compile(
    r"\b(?:did|does|do|has|have|had|was|is)(?: not|n't) fail(?:ed|s|ing)? to (?:install|download)|"
    r"\bnever fail(?:ed|s)? to install|"
    r"\bnot that (?:the |this |it |my )?(?:[a-z0-9-]+ ){0,2}(?:fails?|failed|failing|won'?t|will not|"
    r"doesn'?t|does not|didn'?t|did not|can'?t|cannot) (?:to )?install|"
    r"\b(?:does|did) install\b|"
    r"\b(?:it|this|the update|this update|the patch) (?:has |had |was )?install(?:ed|s) (?:fine|ok|okay|correctly|"
    r"successfully|normally|without (?:any )?(?:issues?|problems?|errors?))\b|"
    r"\b(?:it|this update|the update) (?:has |had |was )?(?:successfully|correctly|properly) installed\b")
# Spans that name an update or a build without reporting that it fails to install: the update SCAN
# ("Windows Update failed to check for updates with error 0x80240438"), and the build a device returns
# to after ANOTHER update failed ("Insider Build 26220.9022 keeps failing to install and rolls back to
# 26200.9168"). Blanked (positions kept) before install wording, update names and codes are read.
_NOT_AN_INSTALL_RX = re.compile(
    r"(?:fail(?:s|ed|ing|ure)?|errors?|unable|can'?t|cannot|could not|couldn'?t)(?: to| when| while)? "
    r"check(?:ing)? for (?:new )?updates?(?: with (?:the )?(?:error|code)(?: code)?:? ?\(?0x[0-9a-f]+\)?)?|"
    r"\broll(?:s|ed|ing)? ?back to (?:os )?(?:build )?[0-9]{5}\.[0-9]{1,5}")
_KB_MENTION_RX = re.compile(r"\bkb ?([0-9]{7})\b")
# The source's title template (Microsoft Q&A appends " - Microsoft Q&A" to every title): not the reporter's words.
_SOURCE_TITLE_SUFFIX_RX = re.compile(r"\s[-–—]\s*microsoft q&a\b")
# THE INSTALL SUBJECT AND OBJECT ARE AN ALLOW-LIST (G38 WS2 review 2, MAJOR-2; round-3 brief item 2). Install
# wording counts for this update only when what fails to install is THIS update itself: its KB, "this / the
# update", or "update" qualified only by articles and THIS update's own qualifiers (`_own_update_words`: its
# servicing month, its release type -- security for a B release, preview / optional for a D release,
# out-of-band for an OOB one --, its version line, and "latest", "cumulative", "Windows" ...). Any other word
# before "update" makes it ANOTHER update ("the .NET update", "the driver update", "the next update", "the 25H2
# feature update", "the June update" on a May page); any other object of a transitive wording refuses the
# wording ("unable to install WSL / Zoom / iTunes / Python 3.13 / Hyper-V since KB..."); any other word between
# the update and intransitive wording is another subject ("Since KB... Zoom fails to install"). Unknown counts
# as foreign: the lists below say what is ALLOWED, never what is refused.
_UPDATE_WORD_RX = re.compile(r"\bupdates?\b")
# Words that END an update's noun phrase when read backwards from "update" (a determiner, a preposition, a verb
# before it): the phrase is then this page's by the list reading, as before.
_NP_BOUNDARY_WORDS = frozenset("""
the this that a an my our its your their his her these those
since after before when while and or but with for of to from in on at by via through until because if as so then
i we you it is was are were be been being has have had will would could should can not no also still just again
even only once now today yesterday every each
install installs installed installing download downloads downloaded downloading reinstall reinstalled
get gets got getting try tries tried trying apply applies applied applying need needs needed run ran running
see saw seeing says said shows showed showing named called
""".split())
# Qualifiers that name any update the same way ("the latest cumulative update", "Windows Update").
_GENERIC_UPDATE_WORDS = frozenset("""
latest newest new recent most current cumulative monthly quality windows 11 lcu kb os month's today's
following above below pending same attached listed mentioned aforementioned
""".split())
# The words of a Windows Update title ("2026-10 Cumulative Update Preview", "Security Update"): what a name its
# KB follows may hold.
_UPDATE_TITLE_WORDS = _GENERIC_UPDATE_WORDS | frozenset("""
security preview optional non-security nonsecurity out-of-band oob emergency servicing stack dynamic feature
version 10 .net framework
""".split())
_RELEASE_TYPE_WORDS = {
    "B": frozenset("security patch tuesday b".split()),
    "D": frozenset("preview optional non-security nonsecurity d".split()),
    "OOB": frozenset("out-of-band oob emergency".split()),
}
_MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                "november", "december")
# Fillers that may stand between an update's name and install wording that takes it as subject ("KB... (26200.8524)
# keeps failing to install", "the update - it fails to install"), or before install wording when no update is
# named in the clause ("I keep getting install error ..."): no other subject.
_SUBJECT_FILLER_WORDS = frozenset("""
the this that a an it its is was has had have been be keeps keep kept still just always again repeatedly also
simply now then constantly continuously consistently currently today yesterday even never only all both twice
i we me us get gets getting got receive receives received receiving see sees seeing saw shows showing showed
says said gives giving gave same here there just tried try trying when while and but will with due to
error errors code codes message failed failing on build builds version os for systems x64-based arm64-based
x86-based how do does fix solve resolve why what can help please
""".split())
# Articles and adverbs a transitive install wording may take where its object would stand ("fails to install
# properly", "unable to install the 2026-05 cumulative update").
_OBJECT_ADVERBS = frozenset("""
the this that a an my our its
correctly properly successfully completely fully automatically manually normally fine ok okay either
now today yesterday repeatedly twice still even all
""".split())
# The clause right after one that reports this update failing may lend it its error code only when it names
# nothing else ("Get error code 0x800f0991"; never "Zoom gives error 0x...").
_FOLLOW_FILLER_WORDS = frozenset("""
get gets getting got gives gave giving shows showing showed says said receive received receiving see seeing saw
error errors code codes message number the an a it and then again i we me now still same this that is was it's
every each time times attempt try always reads read returns returned keep keeps
""".split())
_TOKEN_RX = re.compile(r"[^\s]+")
_DATE_TOKEN_RX = re.compile(r"^(20\d\d)[-./](\d\d?)$")
_BUILD_TOKEN_RX = re.compile(r"^\d{5}\.\d{1,5}$")
# Where a transitive wording's object ends: punctuation, a dash between spaces (a title's " - Microsoft Q&A"), an
# error code, a linking word.
_OBJECT_END_RX = re.compile(r"[,;:.!?()\n\"]|\s[-–—]+\s|\b0x[0-9a-f]|\b(?:since|after|before|when|while|because|as|"
                            r"but|and|or|so|then|with|on|in|from|for|due|via|through|using|at|to|until|every|each|"
                            r"again|anymore|despite|although|though|regardless|even|last|error|code)\b")
_CLAUSE_BREAK_RX = re.compile(r"[.!?;](?=\s)|\n")
_SUBJECT_GAP = 80   # characters between the update's name and install wording that takes it as subject
_OBJECT_GAP = 60    # characters between transitive install wording and the update it takes as object
_ROLLBACK_RX = re.compile(r"\b(?:roll(?:s|ed|ing)?[ -]?back|undo(?:ing)? (?:the )?changes|revert(?:s|ed|ing)? (?:the )?"
                          r"changes|could ?n[o']?t complete the updates?)\b")


def _own_update_words(page: Mapping[str, Any]) -> frozenset:
    """The words that qualify THIS update and no other: generic ones, its version line, its servicing and
    release month (as "2026-05", "2026.05", "may"), and its release type's words."""
    words = set(_GENERIC_UPDATE_WORDS)
    line = _s(page.get("update_version")).lower()
    if line:
        words.add(line)
    m = re.match(r"^(20\d\d)-(\d\d)\s*([a-z]+)?", _s(page.get("update_type")), re.I)
    months = []
    if m:
        months.append((m.group(1), int(m.group(2))))
        words |= _RELEASE_TYPE_WORDS.get((m.group(3) or "").upper(), frozenset())
    p = re.match(r"^(20\d\d)-(\d\d)", _s(page.get("update_published_at")))
    if p:
        months.append((p.group(1), int(p.group(2))))
    for year, month in months:
        if 1 <= month <= 12:
            words |= {f"{year}-{month:02d}", f"{year}.{month:02d}", f"{year}/{month:02d}", year,
                      _MONTH_NAMES[month - 1], _MONTH_NAMES[month - 1][:3]}
    return frozenset(words)


def _bare(token: str) -> str:
    return token.strip("()[]{}\"'“”‘’")


def _token_is_own(token: str, own: frozenset, page: Mapping[str, Any]) -> bool | None:
    """True: the token qualifies THIS update; False: it names ANOTHER one (another KB, another month, another
    build) or something else; None: not a qualifier at all (the caller decides)."""
    word = _bare(token)
    kb = re.sub(r"[^0-9]", "", _s(page.get("target_kb")))
    m = re.match(r"^kb ?(\d{7})$", word)
    if m:
        return m.group(1) == kb
    if _DATE_TOKEN_RX.match(word) or _BUILD_TOKEN_RX.match(word):
        return word in own or word == _s(page.get("target_build"))
    if word in own:
        return True
    return None


def _update_np(text: str, start: int, page: Mapping[str, Any], own: frozenset) -> tuple[bool | None, int]:
    """(whose update the word "update" at `start` names, where its noun phrase starts), read BACKWARDS over the
    phrase: True when the words before it are THIS update's KB or qualifiers, or when the phrase is a name
    its KB follows; False when any other word qualifies it ("the .NET update", "the next update", "the driver
    update", a plural "updates"), or another KB follows it; None when nothing qualifies it beyond an article
    (the list reading decides, as before)."""
    if text[start:start + 7] == "updates":
        return False, start
    # A name followed by its KB is that KB's name ("2026-09 Security Update (KB5129195)", as Windows Update
    # prints it): the KB decides, whatever words its title holds.
    named = re.match(r"update[\s\"'“”(]*kb ?(\d{7})\b", text[start:start + 30])
    kb = re.sub(r"[^0-9]", "", _s(page.get("target_kb")))
    np_start = start
    for m in reversed(list(_TOKEN_RX.finditer(text, max(0, start - 120), start))):
        token = m.group(0)
        if token[-1:] in ",.;:!?" and _bare(token[:-1]) == token[:-1]:
            break   # a clause break right before the phrase
        word = _bare(token)
        if not word:
            continue
        if word in _NP_BOUNDARY_WORDS or not re.search(r"[a-z0-9]", word):
            break   # a determiner, a linking word, or a dash or ampersand: the phrase ends here
        kb_token = re.match(r"^kb ?(\d{7})$", word)
        if kb_token and not named:
            return kb_token.group(1) == kb, m.end()
        if named:
            if not (word in _UPDATE_TITLE_WORDS or _DATE_TOKEN_RX.match(word) or word.isdigit()):
                break   # the KB names the update; its title is only these words ("install error" is not)
        else:
            own_token = _token_is_own(word, own, page)
            if own_token is not True:
                return False, m.start()   # "the .NET update", "the next update": unknown counts as foreign
        np_start = m.start()
    if named:
        return named.group(1) == kb, np_start
    return None, np_start


def _update_np_owner(text: str, start: int, page: Mapping[str, Any], own: frozenset) -> bool | None:
    """`_update_np`'s owner alone."""
    return _update_np(text, start, page, own)[0]


def _only_fillers(text: str, allowed: frozenset, own: frozenset, page: Mapping[str, Any]) -> bool:
    """Whether `text` holds nothing but punctuation, `allowed` words, this update's own qualifiers, numbers
    and this update's KB / build (an allow-list: any other word is another subject or object)."""
    for token in _TOKEN_RX.findall(text):
        word = _bare(token).rstrip(",.;:!?").strip("-–—")
        if not word or word in allowed or re.fullmatch(r"[\W_]+|0x[0-9a-f]+|\d{1,3}%", word):
            continue
        own_token = _token_is_own(word, own, page)
        if own_token is True or (own_token is None and re.fullmatch(r"\d+", word)) or _BUILD_TOKEN_RX.match(word):
            continue   # a build number: the OS build(s) of the KB it follows ("(OS builds 26200.8875 and 26100.8875)")
        return False
    return True


def _blank(text: str, rx: re.Pattern) -> str:
    return rx.sub(lambda m: " " * len(m.group(0)), text)


def _page_mentions(text: str, page: Mapping[str, Any]) -> list[tuple[int, int]]:
    """Where the row names THIS update: its KB, or its build as the update being installed ("upgrade
    to build 26100.8457"). A build on its own is not the update: it is how a row states the device's
    current build ("OS build 26200.8246", "Windows 11 Pro 25H2 26200.9457") or a rollback target, and
    4 of the 5 build-only rows the first increment cited were about something else (A1 and AUX-095
    both say "the page's KB")."""
    kb = re.sub(r"[^0-9]", "", _s(page.get("target_kb")))
    build = _s(page.get("target_build"))
    spans = [(m.start(), m.end()) for m in _KB_MENTION_RX.finditer(text) if kb and m.group(1) == kb]
    if build:
        spans += [(m.start(), m.end()) for m in re.finditer(
            r"\b(?:update|upgrade|updating|upgrading) to (?:the )?(?:os )?(?:build )?" + re.escape(build) + r"\b", text)]
    return sorted(spans)


def _owner_is_page(span: tuple[int, int], page_spans: list[tuple[int, int]],
                   other_spans: list[tuple[int, int]]) -> bool:
    """Whether `span` (install wording, an error code) is about THIS page's update, in a row that names
    several. The row is read as a list, the way Windows Update prints one ("<name> (KB1) (build) Install
    error - 0x... <name> (KB2) Install error - 0x..."): what follows an update's name, up to the next
    name, is about that update; what comes before the first name is about the first one named."""
    names = sorted([(s[0], True) for s in page_spans] + [(s[0], False) for s in other_spans])
    if not names:
        return False
    owner = names[0][1]
    for start, is_page in names:
        if start > span[0]:
            break
        owner = is_page
    return owner


def _clause(text: str, pos: int) -> tuple[int, int]:
    start, end = 0, len(text)
    for m in _CLAUSE_BREAK_RX.finditer(text):
        if m.end() <= pos:
            start = m.end()
        elif m.start() >= pos:
            end = m.start()
            break
    return start, end


def _install_subject(text: str, span: tuple[int, int], refs: list[tuple[int, int, bool]],
                     page_spans: list[tuple[int, int]], other_spans: list[tuple[int, int]],
                     page: Mapping[str, Any] | None = None) -> bool:
    """Whether the install wording at `span` takes THIS update as its subject or object -- an ALLOW-LIST (G38
    WS2 review 2, MAJOR-2). A transitive wording's OBJECT, read up to the next update named or a linking word,
    may hold only articles, this update's own qualifiers and adverbs ("unable to install the update",
    "fails to install properly"); anything else is another object ("unable to install WSL since KB...") and
    refuses the wording, wherever the update is named. Then, in its clause: the nearest update named before
    it, with only fillers in between; else, for a transitive wording, the update named right after it; else,
    with no update named before it in the clause and only fillers there, the update the row is about (the
    list reading). Otherwise -- another update, another program, an unknown subject -- it does not count."""
    page = page or {}
    own = _own_update_words(page)
    c0, c1 = _clause(text, span[0])
    if text[span[0]:span[1]].startswith("update"):
        # "update failed": its own subject, unless the words before "update" name another one.
        return _update_np_owner(text, span[0], page, own) is not False \
            and _owner_is_page(span, page_spans, other_spans)
    before = [r for r in refs if c0 <= r[0] and r[1] <= span[0]]
    after = [r for r in refs if span[1] <= r[0] < c1]
    transitive = bool(_INSTALL_TRANSITIVE_RX.match(text[span[0]:span[1]]))
    word_end = span[1]
    while word_end < len(text) and (text[word_end].isalnum() or text[word_end] == "'"):
        word_end += 1   # the rest of the wording's last word: "installation fail|s", "not install|ing"
    if transitive:
        stop = _OBJECT_END_RX.search(text, word_end)
        obj_end = min([c1] + [r[0] for r in after] + ([stop.start()] if stop else []))
        if not _only_fillers(text[word_end:max(obj_end, word_end)], _OBJECT_ADVERBS, own, page):
            return False
    if before:
        gap = text[before[-1][1]:span[0]]
        if len(gap) <= _SUBJECT_GAP and _only_fillers(gap, _SUBJECT_FILLER_WORDS, own, page):
            return _coordinated(text, before, len(before) - 1, -1)
    if after and transitive:
        gap = text[word_end:after[0][0]]
        if len(gap) <= _OBJECT_GAP and _only_fillers(gap, _OBJECT_ADVERBS, own, page):
            return _coordinated(text, after, 0, 1)
    if not before and _only_fillers(text[c0:span[0]], _SUBJECT_FILLER_WORDS, own, page):
        return _owner_is_page(span, page_spans, other_spans)
    return False


# Updates named together as one subject or object: "KB5099999 and KB5088888 failed to install", "failed to
# install KB5088888, KB5099999 and KB5077777".
_COORDINATION_RX = re.compile(r"^[\s(),]*(?:and|&|or|plus|as well as|,)[\s(),]*$")


def _coordinated(text: str, refs: list[tuple[int, int, bool]], i: int, step: int) -> bool:
    """Whether this page's update is among the updates named together with refs[i] (walking `step`)."""
    while True:
        if refs[i][2]:
            return True
        j = i + step
        if not 0 <= j < len(refs):
            return False
        gap = text[refs[j][1]:refs[i][0]] if step < 0 else text[refs[i][1]:refs[j][0]]
        if not _COORDINATION_RX.match(gap):
            return False
        i = j


def windows_install_row(row: Mapping[str, Any], page: Mapping[str, Any]) -> dict[str, Any]:
    """{ok, why, codes, stages}: whether this counted row reports that THIS page's update fails to install,
    the install error codes it attributes to this update, and the named failure stages. Fails closed:
      * the row must name this update (`_page_mentions`: the KB, never the build alone);
      * denied install wording refuses the whole row (`_INSTALL_NEGATION_RX`);
      * "check for updates" and "rolls back to <build>" are not install failures (`_NOT_AN_INSTALL_RX`);
      * some install wording must take THIS update as its subject or object (`_install_subject`): a
        driver, an app or another update failing to install after this one is not this one failing;
      * error codes: only in a clause that reports this update failing to install, never in a crash or
        bugcheck context, and, where the row names several updates, only this update's (the list
        reading, `_owner_is_page`)."""
    text = _txt(row)
    if _INSTALL_NEGATION_RX.search(text):
        return {"ok": False, "why": "the row denies an install failure", "codes": [], "stages": []}
    text = _blank(_blank(text, _NOT_AN_INSTALL_RX), _SOURCE_TITLE_SUFFIX_RX)
    page_spans = _page_mentions(text, page)
    if not page_spans:
        return {"ok": False, "why": "the row does not name this update (its KB)", "codes": [], "stages": []}
    kb = re.sub(r"[^0-9]", "", _s(page.get("target_kb")))
    other_spans = [(m.start(), m.end()) for m in _KB_MENTION_RX.finditer(text) if m.group(1) != kb]
    wording = [(m.start(), m.end()) for m in _INSTALL_RX.finditer(text)]
    if not wording:
        return {"ok": False, "why": "no install-failure wording", "codes": [], "stages": []}
    own = _own_update_words(page)
    generic = []
    for m in _UPDATE_WORD_RX.finditer(text):
        if any(m.start() < e and s < m.end() for s, e in page_spans + other_spans):
            continue
        # "the .NET update", "the next update": ANOTHER update (brief item 2); a bare "the update": the list reading.
        np_owner, np_start = _update_np(text, m.start(), page, own)
        generic.append((np_start, m.end(), np_owner if np_owner is not None
                        else _owner_is_page((m.start(), m.end()), page_spans, other_spans)))
    refs = sorted([(s, e, True) for s, e in page_spans] + [(s, e, False) for s, e in other_spans] + generic)
    accepted = [w for w in wording if _install_subject(text, w, refs, page_spans, other_spans, page)]
    if not accepted:
        if other_spans and not any(_owner_is_page(w, page_spans, other_spans) for w in wording):
            return {"ok": False, "why": "the install failure it reports is another update's", "codes": [], "stages": []}
        return {"ok": False, "why": "the install failure it reports is not this update's (another subject fails "
                "to install)", "codes": [], "stages": []}
    clauses = sorted({_clause(text, w[0]) for w in accepted})
    # The clause right after one that reports this update failing, when it holds nothing but an error label
    # (an allow-list): "20206-01 update won't install. Get error code 0x800f0991".
    follow = []
    for c0, c1 in clauses:
        nxt = _clause(text, min(c1 + 1, len(text)))
        if nxt[0] > c0 and not any(nxt[0] <= s < nxt[1] for s, _e in other_spans) \
                and _only_fillers(_CODE_RX.sub(" ", text[nxt[0]:nxt[1]]), _FOLLOW_FILLER_WORDS, own, page):
            follow.append(nxt)
    codes = []
    for m in _CODE_RX.finditer(text):
        code = m.group(0)
        lead = text[max(0, m.start() - 60):m.start()]
        if not code[2:].lstrip("0") or _CRASH_CONTEXT_RX.search(lead):
            continue
        clause = next(((c0, c1) for c0, c1 in clauses if c0 <= m.start() < c1), None)
        if not (clause or _INSTALL_ERROR_LABEL_RX.search(lead)
                or (any(c0 <= m.start() < c1 for c0, c1 in follow) and _ERROR_LABEL_RX.search(lead))):
            continue
        # Whose code: the install wording it follows in its clause ("KB1 and KB2 failed to install, error
        # 0x..." is both updates'; in a listing, "KB2 ... Install error - 0x..." is KB2's), else the list reading.
        before = [w for w in wording if clause and clause[0] <= w[0] < m.start()]
        if before:
            if before[-1] not in accepted:
                continue
        elif other_spans and not _owner_is_page((m.start(), m.end()), page_spans, other_spans):
            continue
        codes.append(code)
    stages = set()
    for c0, c1 in clauses + follow:   # "... fails to install. It rolls back after the restart."
        clause = text[c0:c1]
        if _ROLLBACK_RX.search(clause):
            stages.add("rolls back")
        for m in _PERCENT_RX.finditer(clause):
            if int(m.group(1)) <= 100:
                stages.add(f"stops at {m.group(1)}%")
    return {"ok": True, "why": "", "codes": sorted(set(codes)), "stages": sorted(stages)}


# Acrobat (G38 WS2 review, MAJOR-2 and MAJOR-3). The installer prints "Exit Code: 7 Please see specific
# errors below" for EVERY failure; the specific error is the DW / DF code after it ("ERROR: DW003, DW006").
_ADOBE_INSTALLER_CODE_RX = re.compile(r"\b(d[wf]\d{3})\b")
# Another Adobe product, whose installer prints the same Exit Code 7.
_ADOBE_OTHER_PRODUCT_RX = re.compile(
    r"\b(?:photoshop|illustrator|premiere|after effects|lightroom|indesign|incopy|dreamweaver|audition|"
    r"media encoder|character animator|fireworks|speedgrade|captivate|framemaker|robohelp|"
    r"adobe (?:xd|animate|bridge|dimension|muse|prelude|fresco|substance\w*)|flash player)\b")
_ACROBAT_NAME_RX = re.compile(r"\b(?:acrobat|reader)\b")
# THIS Acrobat product and version (G38 WS2 review 2, LOW-3; brief item 6), as Windows refuses another KB: a row
# that names another Acrobat version ("15.020.20039", "15.006.30279", "2015.006.30279", "15.020"), another
# generation ("Acrobat XI", "Reader 2017" on a 15.x page), or the OTHER product only (Reader on the Pro page,
# Acrobat Pro / Standard / DC on the Reader page) is about that version or product, and is refused.
_ACROBAT_VERSION_RX = re.compile(r"(?<![\d.])(?:20)?(\d{2})\.(\d{3})(?:\.(\d{5}))?(?![\d.]*\d)")
_ACROBAT_GENERATION_RX = re.compile(r"\b(?:acrobat|reader)(?: (?:pro|standard|dc))? (xi|x|9|8|7|20\d\d)\b")
_ACROBAT_GENERATION_MAJOR = {"xi": "11", "x": "10", "9": "9", "8": "8", "7": "7"}
_READER_NAME_RX = re.compile(r"\breader\b")
_PRO_NAME_RX = re.compile(r"\bacrobat\b(?! reader)")
# The row says this version DID install, or that the error went away.
_ACROBAT_NEGATION_RX = re.compile(
    r"\binstall(?:ed|s) (?:fine|ok|okay|correctly|successfully|normally|without (?:any )?(?:issues?|problems?|"
    r"errors?))\b|\b(?:successfully|correctly|properly) installed\b|"
    r"\b(?:exit code:?\s*7|the error|the problem|the issue|it)\b(?:\W+\w+){0,3}?\W+(?:is|was|has been) "
    r"(?:gone|fixed|resolved|solved)\b|\bno longer (?:get|gets|getting|see|seeing|shows?)\b")


def _acrobat_other_version(text: str, version: str) -> str:
    """The first Acrobat version or generation the row names that is not `version` (the page's), or ""."""
    parts = version.split(".")
    for m in _ACROBAT_VERSION_RX.finditer(text):
        named = [m.group(1), m.group(2)] + ([m.group(3)] if m.group(3) else [])
        if not parts[:len(named)] or named != [p.zfill(len(n)) for p, n in zip(parts, named)]:
            return m.group(0)
    for m in _ACROBAT_GENERATION_RX.finditer(text):
        gen = m.group(1)
        major = _ACROBAT_GENERATION_MAJOR.get(gen) or gen[2:]
        if parts and major != parts[0].lstrip("0"):
            return m.group(0)
    return ""


def acrobat_install_row(row: Mapping[str, Any], product_id: str, version: str = "") -> dict[str, Any]:
    """{ok, why, codes}: whether this counted row reports that THIS Acrobat product (and `version`, the page's)
    fails to install, and the installer's specific error codes (DW / DF) it shows. Fails closed:
      * installer Exit Code 7 must be shown, and a row shared between Pro and Reader must name this page's
        product (the calibration's P15/P16 refusal);
      * a row that names ANOTHER Acrobat version or generation, or only the other product (Reader on the Pro
        page, Acrobat Pro / DC on the Reader page), is refused, as Windows refuses another KB (G38 WS2 review 2,
        LOW-3);
      * a row that says the version installed, or that the error is gone, is refused;
      * Exit Code 7 counts only where it is not another Adobe product's ("Acrobat installed fine, but
        Photoshop fails with Exit Code: 7"): the product named nearest before it in its clause, else the
        first after it, else the row's.
    Codes are read outside clauses about another product."""
    text = _txt(row)
    if not _EXIT7_RX.search(text):
        return {"ok": False, "why": "no installer Exit Code 7", "codes": []}
    other = _acrobat_other_version(text, _s(version)) if _s(version) else ""
    if other:
        return {"ok": False, "why": f"the row names another Acrobat version ({other})", "codes": []}
    reader, pro = bool(_READER_NAME_RX.search(text)), bool(_PRO_NAME_RX.search(text))
    if (product_id.endswith("pro") and reader and not pro) or (product_id.endswith("reader") and pro and not reader):
        return {"ok": False, "why": "the row names the other Acrobat product only", "codes": []}
    if "," in _s(row.get("applicability")):
        names_reader = "reader" in text
        if product_id.endswith("reader") and not names_reader:
            return {"ok": False, "why": "a shared row that does not name this product", "codes": []}
        if product_id.endswith("pro") and names_reader and "acrobat dc" not in text and "acrobat pro" not in text:
            return {"ok": False, "why": "a shared row that does not name this product", "codes": []}
    if _INSTALL_NEGATION_RX.search(text) or _ACROBAT_NEGATION_RX.search(text):
        return {"ok": False, "why": "the row denies an install failure", "codes": []}
    names = sorted([(m.start(), False) for m in _ACROBAT_NAME_RX.finditer(text)]
                   + [(m.start(), True) for m in _ADOBE_OTHER_PRODUCT_RX.finditer(text)])
    row_foreign = any(f for _p, f in names) and not any(not f for _p, f in names)
    owned = []
    for m in _EXIT7_RX.finditer(text):
        c0, c1 = _clause(text, m.start())
        before = [f for p, f in names if c0 <= p < m.start()]
        after = [f for p, f in names if m.start() <= p < c1]
        foreign = before[-1] if before else after[0] if after else row_foreign
        owned.append(not foreign)
    if not any(owned):
        return {"ok": False, "why": "the Exit Code 7 it reports is another Adobe product's", "codes": []}
    foreign_clauses = {_clause(text, p) for p, f in names if f}
    codes = sorted({m.group(1).upper() for m in _ADOBE_INSTALLER_CODE_RX.finditer(text)
                    if not any(c0 <= m.start() < c1 for c0, c1 in foreign_clauses)})
    return {"ok": True, "why": "", "codes": codes}


_NUMBER_WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine"}
ACROBAT_GROUP_PREFIX = "installer error "


def install_groups(rows: list[tuple[Mapping[str, Any], dict[str, Any]]], mode: str = "") -> dict[str, list]:
    """Rows that report ONE install problem, by the characteristic they share (Amendment A3). Strict (the
    default, INSTALL_GROUPING): the same error code, the same named stage, or, for Acrobat, the same
    SPECIFIC installer error (DW / DF code) -- never the generic Exit Code 7 the installer prints for every
    failure (G38 WS2 review, MAJOR-3). Different codes alone are not one problem, and a row with no specific
    characteristic joins no group. A row that states an error code groups ON ITS CODE ONLY: a named stage
    every failed update shows ("it rolls back", "it gets to 100%") never joins two rows whose codes differ
    (G38 WS2 review 2, probes N5a / N5c); the stages group rows that state no code. Lenient (A1's superseded
    reading, for measurement only): every install row is one problem."""
    mode = mode or INSTALL_GROUPING
    if mode not in INSTALL_GROUPINGS:
        raise ValueError(f"unknown install grouping {mode!r}")
    groups: dict[str, list] = {}
    for row, info in rows:
        if mode == "lenient":
            keys = ["any install failure"]
        elif info.get("acrobat"):
            keys = [ACROBAT_GROUP_PREFIX + c for c in info.get("codes", [])]
        else:
            keys = [f"error {c}" for c in info.get("codes", [])] or list(info.get("stages", []))
        for key in keys:
            groups.setdefault(key, []).append(row)
    return groups


def _install_reason(n: int, key: str, product_id: str) -> str:
    count = _NUMBER_WORDS.get(n, str(n))
    if product_id in ACROBAT:
        detail = (f"installer error {key[len(ACROBAT_GROUP_PREFIX):]} (Exit Code 7)"
                  if key.startswith(ACROBAT_GROUP_PREFIX) else "installer Exit Code 7")
        return f"{count} reports of separate incidents say that installing this version fails with {detail}."
    if key.startswith("error "):
        detail = f" with error {key[len('error '):]}"
    elif key == "rolls back":
        detail = ": it rolls back instead of completing"
    elif key.startswith("stops at "):
        detail = f": it stops at {key[len('stops at '):]}"
    else:
        detail = ""
    return f"{count} reports of separate incidents say that this update fails to install{detail}."


def _install_candidates(records: list[Mapping[str, Any]],
                        counted_by_identity: Mapping[tuple[str, str, str], list[Mapping[str, Any]]],
                        out: "ProducerResult", mode: str = "") -> None:
    for page in records:
        pid = _s(page.get("product_id"))
        if pid != WINDOWS and pid not in ACROBAT:
            continue
        rows = list(counted_by_identity.get(verdict_reasons.record_identity(page), []) or [])
        if len(rows) < MIN_INDEPENDENT_REPORTERS:
            continue
        matching: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
        if pid == WINDOWS:
            if not _s(page.get("target_kb")) or not _s(page.get("target_build")):
                continue
            for r in rows:
                info = windows_install_row(r, page)
                if info["ok"]:
                    matching.append((r, info))
        else:
            for r in rows:
                info = acrobat_install_row(r, pid, _s(page.get("update_version")))
                if info["ok"]:
                    matching.append((r, dict(info, acrobat=True)))
        if len(matching) < MIN_INDEPENDENT_REPORTERS:
            continue
        identity = {"product_id": pid, "update_version": _s(page.get("update_version")),
                    "target_build": _s(page.get("target_build"))}
        groups = install_groups(matching, mode)
        scored = []
        for key, members in groups.items():
            kept, dropped = independent_reporters(members, pid)
            scored.append((len(kept), len(members), key, kept, dropped, members))
        scored.sort(key=lambda s: (-s[0], -s[1], s[2]))
        if not scored or scored[0][1] < MIN_INDEPENDENT_REPORTERS:
            source = {"record": _s(page.get("permalink")), "rows": [_s(r.get("id")) for r, _i in matching]}
            what = "specific installer error" if pid in ACROBAT else "error code or named stage"
            out.exclude(INSTALL_CLASS, "no_shared_failure_characteristic", source, **identity,
                        note=f"{len(matching)} install-failure rows share no {what}")
            out.queue(INSTALL_CLASS, page, f"install-failure reports that share no {what}: a person decides "
                      "whether they are one problem", source, problem_key="no shared characteristic")
            continue
        n, _members_n, key, kept, dropped, members = scored[0]
        source = {"record": _s(page.get("permalink")), "problem": key, "rows": [_s(r.get("id")) for r in members],
                  "dropped_by_independence_gate": dropped}
        if n < MIN_INDEPENDENT_REPORTERS:
            out.exclude(INSTALL_CLASS, "not_enough_independent_reporters", source, **identity,
                        note=f"{len(members)} rows report this problem ({key}); the source establishes {n} "
                             "independent report(s)")
            out.queue(INSTALL_CLASS, page, f"install-failure reports of one problem ({key}) whose independence the "
                      "source does not establish: a person decides whether they are separate incidents", source,
                      problem_key=key)
            continue
        evidence = [{"id": _s(r.get("id")), "source_url": _s(r.get("source_url"))} for r in kept]
        out.propose(_candidate(
            INSTALL_CLASS, page, verdict="TEST FIRST", scope=INSTALL_SCOPE, reason=_install_reason(n, key, pid),
            severity="critical_install_failure", failure="the update fails to install", new=False, fixed_in="",
            citation={}, evidence=evidence, problem_key=key,
            independence=independence_basis(kept, pid),
            inputs={"rows_sha256": _sha([[e["id"], e["source_url"]] for e in evidence]),
                    "excerpts_sha256": _sha([_s(r.get("report_text_excerpt")) for r in kept])}))


# ============================================================ corroboration placeholder (later work)

INDEPENDENCE_VERDICTS = ("independent", "not_independent", "uncertain")


def corroboration_candidates(page: Mapping[str, Any], counted_rows: Iterable[Mapping[str, Any]], *,
                             incident_independence: Any = None) -> list[dict[str, Any]]:
    """PLACEHOLDER for user-report corroboration of a NON-install problem. Not implemented; it
    always returns [] (fails closed).

    The interface later work must fill:
      * `incident_independence(row_a, row_b)` returns one of INDEPENDENCE_VERDICTS for two counted
        rows, from evidence of DIFFERENT INCIDENTS (distinct authors, distinct hardware or logs,
        no cross-post), never from different URLs: the OBS cross-post withdrawal showed one person
        behind two URLs (AUTH_V2_35 D-A). "uncertain" counts as not independent.
      * a candidate needs MIN_INDEPENDENT_REPORTERS rows that are pairwise "independent" AND describe
        the same concrete problem on this exact version, with the affected workflow identified.
      * it returns entries in the same shape `_candidate` builds, class
        "user_corroborated_issue", verdict TEST FIRST only (no automatic WAIT; A1).
    With no verifier (the only state today) nothing can be shown independent, so nothing is proposed;
    those pages stay with the reviewed entries and the review queue."""
    del page, counted_rows, incident_independence
    return []


def rows_are_independent(row_a: Mapping[str, Any], row_b: Mapping[str, Any], *,
                         incident_independence: Any = None) -> bool:
    """The placeholder's independence predicate: True only when a verifier says "independent".
    Different source URLs are NOT enough, so without a verifier this is always False."""
    if incident_independence is None:
        return False
    return incident_independence(row_a, row_b) == "independent"


# ============================================================ assembly

def candidate_key(cls: str, identity: Iterable[str], verdict: str, scope: str, problem_key: str) -> str:
    """The STABLE identity of a candidate: its class, exact page, verdict, scope and the problem it is about
    (the vendor's statement, or the install failure's shared characteristic). Never the reporter count, the
    cited rows or the reason's wording, so one more report of the same problem is the same candidate (a
    repeat appearance), not a new one. The shadow diagnostics key on it (lib/producer_shadow)."""
    return _sha([cls, list(identity), verdict, scope, problem_key])[:16]


def _candidate(cls: str, page: Mapping[str, Any], *, verdict: str, scope: str, reason: str, severity: str,
               failure: str, new: bool, fixed_in: str, citation: dict, inputs: dict, problem_key: str,
               evidence: list | None = None, independence: list | None = None) -> dict[str, Any]:
    ident = verdict_reasons.record_identity(page)
    key = candidate_key(cls, ident, verdict, scope, problem_key)
    entry = {
        "id": f"auto:{cls}:{ident[0]}:{ident[1]}{(':' + ident[2]) if ident[2] else ''}:{key[:12]}",
        "candidate_key": key,
        "product_id": ident[0], "update_version": ident[1],
        "verdict": verdict,
        "reason_class": INSTALL_REASON_CLASS if cls == INSTALL_CLASS else VENDOR_CLASS,
        "scope": scope, "reason": reason,
        "severity_basis": severity, "failure": failure, "problem_key": problem_key,
        "evidence": list(evidence or []),
        "citation": citation,
        "new_in_this_version": bool(new),
        "page": _s(page.get("permalink")),
        "producer": {"class": cls, "version": PRODUCER_VERSION, "inputs": inputs},
    }
    if cls == INSTALL_CLASS:
        entry["independence_basis"] = list(independence or [])
    if ident[2]:
        entry["target_build"] = ident[2]
    if fixed_in:
        entry["fixed_in"] = fixed_in
    return entry


# Words that name nobody in particular (review 1, MAJOR-1). A scope must carry at least one word
# outside this list -- a SETUP word: a feature, a device class, a configuration, a platform. Listed:
# function words; quantifiers ("a small number of", "some", "most", "all", "only", "a subset of");
# population nouns (devices, users, PCs, systems, customers); editions and versions; the update
# itself and its verbs ("devices that have installed this update"); a generic "application" or
# "program"; generic activities ("when starting ..."). The product's own name is added per product
# (`_PRODUCT_WORDS`): "if you use OBS" names every OBS user. Version numbers never name a setup.
_SCOPE_GENERIC_WORDS = frozenset("""
a an the this that these those it its they them their there your you my our we us i me
of to in on at by with without from into onto for and or nor but as than then also both either
if when where whenever while who whom whose which what
is are was were be been being am has have had having do does did done can could may might will would should
some most many all any only several certain various multiple every each few fewer other others more less much
very just even especially particularly typically usually mostly mainly generally potentially possibly
small large limited growing increasing significant number numbers subset subsets portion portions
percentage fraction minority majority handful set group groups range variety kind kinds type types
affected impacted unaffected specific particular
device devices user users pc pcs computer computers machine machines system systems customer customers
people person persons someone anyone everyone everybody organization organizations client clients
endpoint endpoints hardware configuration configurations setup setups
edition editions version versions release releases build builds channel channels sku skus
home pro professional enterprise education business iot ltsc ltsb se
update updates updated updating patch patches patched install installs installed installing installation
installations upgrade upgrades upgraded upgrading apply applied applying download downloaded downloading
application applications app apps program programs software tool tools feature features product products
use uses used using run runs running ran start starts started starting launch launches launched launching
open opens opened opening load loads loaded loading close closes closed closing exit exits exited exiting
""".split())
_PRODUCT_WORDS = {
    WINDOWS: frozenset({"windows", "microsoft", "11", "os"}),
    OBS: frozenset({"obs", "studio", "obs-studio"}),
}
_VERSION_TOKEN_RE = re.compile(r"^(?:v?[0-9]+(?:\.[0-9]+)*|[0-9]{2}h[12]|kb[0-9]{7})$")
# HEDGES (review 2, MAJOR-1). The list above is a deny-list, so the next unlisted word was always a
# "setup": "for a small number of devices in some environments" passed on "environments", "for some
# consumer devices" on "consumer". A scope that says WHO is affected only vaguely now fails closed to
# the review queue (ambiguous_scope), whatever else it names: a hedge word anywhere, a "small /
# limited number" phrase anywhere, or "environment(s)" without a named environment TYPE right before
# it ("virtual desktop environments" names one; "some", "these", "such" or "enterprise environments"
# do not).
_SCOPE_HEDGE_WORDS = frozenset("""
some certain specific specified particular subset subsets various worldwide
region regions condition conditions circumstance circumstances scenario scenarios situation situations cases
""".split())
_SCOPE_HEDGE_PHRASE_RE = re.compile(
    r"\b(?:small|smaller|limited|low|tiny|reduced)\s+(?:number|numbers|subset|subsets|portion|percentage|fraction|"
    r"share|group|groups|amount|count|set)\b|\ba\s+(?:few|handful|minority|fraction|portion)\b", re.ASCII)
_SCOPE_ENVIRONMENT_WORDS = frozenset({"environment", "environments"})
# Words that never name an environment type when they stand right before "environment(s)", beyond
# the generic words, the hedges and the product's own name.
_SCOPE_NOT_AN_ENVIRONMENT_TYPE = frozenset(
    "such other different diverse mixed varied unusual uncommon atypical rare".split())


def _names_environment_type(word: str, generic: frozenset) -> bool:
    """Whether `word`, standing right before "environment(s)", names a type of environment."""
    return bool(word) and not (word in generic or word in _SCOPE_HEDGE_WORDS
                               or word in _SCOPE_NOT_AN_ENVIRONMENT_TYPE or _VERSION_TOKEN_RE.match(word))


def _scope_hedge(body: str, words: list[str], generic: frozenset) -> str:
    """The vague part of a scope's body ("some", "a small number", "some environments"), or ""."""
    hedge = next((w for w in words if w in _SCOPE_HEDGE_WORDS), "")
    if hedge:
        return hedge
    phrase = _SCOPE_HEDGE_PHRASE_RE.search(body)
    if phrase:
        return phrase.group(0)
    for i, word in enumerate(words):
        if word in _SCOPE_ENVIRONMENT_WORDS and not _names_environment_type(words[i - 1] if i else "", generic):
            return " ".join(words[max(i - 1, 0):i + 1])
    return ""


def scope_problem(scope: Any, product_id: str = "") -> str:
    """Why `scope` is not an affected setup, or "" when it is. THE scope rule, in one place.

    The scope is worded 'if / when / for ...' (the reviewed entries' SCOPE_RE) AND names a setup:
    at least one word outside _SCOPE_GENERIC_WORDS and the product's own name. "for a small number
    of devices", "for all editions of Windows 11", "for devices that have installed this update",
    "if you use the update", "if you use application" and "if you use OBS" all read like a scope
    and name nobody in particular, so a candidate carrying one would cover everyone. A scope that
    names a setup only vaguely -- "for some consumer devices", "for devices that meet certain
    conditions", "for a small number of devices in some environments" -- is ambiguous too
    (`_scope_hedge`, review 2): it says that SOME of a setup is affected, not which. The install
    class's fixed scope ("when installing it") is the one exception: there the setup IS the act of
    installing (A1), and `candidate_problems` keeps it to installation failures."""
    text = _s(scope)
    if not verdict_reasons.SCOPE_RE.match(text):
        return "the scope is not worded 'if / when / for ...'"
    if text == INSTALL_SCOPE:
        return ""
    body = re.sub(r"^(?:if you use|if|when|for)\s+", "", text, flags=re.I).lower()
    generic = _SCOPE_GENERIC_WORDS | _PRODUCT_WORDS.get(_s(product_id), frozenset())
    words = re.findall(r"[a-z0-9](?:[a-z0-9'+.-]*[a-z0-9])?", body)
    if not [w for w in words if w not in generic and not _VERSION_TOKEN_RE.match(w)]:
        return ("the scope names no setup: only a quantifier, a population, an edition, the update, a generic "
                "application or the product")
    hedge = _scope_hedge(body, words, generic)
    if hedge:
        return f"the scope is vague ({hedge!r}): it says some of a setup is affected, not which"
    return ""


def _scope_ok(scope: Any, product_id: str = "") -> bool:
    """The scope requirement: `scope_problem` finds nothing. A statement whose setup the grammar cannot
    state has scope '' -- or one that names nobody in particular -- and is refused here as an
    ambiguous scope (and queued for a person), never published unscoped or scoped to everyone."""
    return not scope_problem(scope, product_id)


def candidate_problems(entry: Mapping[str, Any]) -> list[str]:
    """Why a candidate may not be proposed (its own schema), or []. Fails closed."""
    problems = []
    if entry.get("verdict") not in ("WAIT", "TEST FIRST"):
        problems.append("verdict is not WAIT or TEST FIRST")
    if not _scope_ok(entry.get("scope"), _s(entry.get("product_id"))):
        problems.append("scope is not 'if/when/for <a setup>'")
    if _s(entry.get("scope")) == INSTALL_SCOPE and entry.get("severity_basis") != "critical_install_failure":
        problems.append("'when installing it' is the scope of an installation failure only")
    reason = _s(entry.get("reason"))
    if not reason or "\n" in reason or len(reason) > 320:
        problems.append("reason is not one public line of 1-320 characters")
    if entry.get("severity_basis") not in SEVERITY_BASES:
        problems.append("severity basis is outside the closed vocabulary")
    cls = (entry.get("producer") or {}).get("class")
    if cls == VENDOR_CLASS and not (_s((entry.get("citation") or {}).get("statement"))
                                    and _s((entry.get("citation") or {}).get("record"))):
        problems.append("no stored official statement is cited")
    if cls == INSTALL_CLASS and len(entry.get("evidence") or []) < MIN_INDEPENDENT_REPORTERS:
        problems.append("fewer independent reporters than MIN_INDEPENDENT_REPORTERS")
    if entry.get("verdict") == "WAIT" and (cls != VENDOR_CLASS or entry.get("new_in_this_version") is not True):
        problems.append("WAIT needs a vendor-confirmed defect that starts in this version")
    if not _s(entry.get("product_id")) or not _s(entry.get("update_version")):
        problems.append("no exact identity")
    return problems


# Refusals a person reads: the TEMPORARY review queue, with why.
QUEUED_EXCLUSIONS = {
    "ambiguous_scope": "a serious confirmed defect whose affected setup the producer cannot state",
    "uncertain_severity": "a defect the vendor itself calls possible, rare or occasional: a person decides whether "
                          "it is serious",
    "unrecognised_wording": "a serious confirmed defect whose vendor text says more than the producer reads (a remark "
                            "about its history, a qualifying clause): a person decides whether it starts in this "
                            "version",
}


def _queue_key(cls: str, kind: str, fields: Mapping[str, Any]) -> str:
    """The STABLE identity of a review-queue item: class, kind, exact page and problem -- never the rows."""
    return _sha([cls, kind] + [_s(fields.get(k)) for k in ("product_id", "update_version", "target_build",
                                                              "problem_key")])[:16]


class ProducerResult:
    """What one run proposes, refuses and queues. Every list is in a deterministic order."""

    def __init__(self) -> None:
        self.candidates: list[dict[str, Any]] = []
        self.excluded: list[dict[str, Any]] = []
        self.review_queue: list[dict[str, Any]] = []

    def propose(self, entry: dict[str, Any]) -> None:
        cls = (entry.get("producer") or {}).get("class", "")
        identity = {"product_id": entry.get("product_id", ""), "update_version": entry.get("update_version", ""),
                    "target_build": entry.get("target_build", "")}
        scope_note = entry.pop("scope_note", "")
        if not _scope_ok(entry.get("scope"), _s(entry.get("product_id"))):
            self.exclude(cls, "ambiguous_scope", entry.get("citation") or {}, **identity,
                         severity=entry.get("severity_basis", ""), problem_key=entry.get("problem_key", ""),
                         note=f"proposed scope {_s(entry.get('scope'))!r}: "
                              f"{scope_problem(entry.get('scope'), _s(entry.get('product_id')))}"
                              + (f"; refused wording: {scope_note}" if scope_note else ""))
            return
        problems = candidate_problems(entry)
        if problems:
            self.exclude(cls, "candidate_schema", entry.get("citation") or {}, **identity, note="; ".join(problems))
            return
        if any(c["id"] == entry["id"] for c in self.candidates):
            return
        self.candidates.append(entry)

    def exclude(self, cls: str, reason: str, source: Mapping[str, Any], **identity: Any) -> None:
        item = {"class": cls, "excluded": reason, **{k: v for k, v in identity.items() if v not in ("", None)},
                "source": dict(source)}
        self.excluded.append(item)
        why = QUEUED_EXCLUSIONS.get(reason)
        if why and (identity.get("severity") or reason == "uncertain_severity"):
            fields = {k: v for k, v in identity.items() if v}
            self.review_queue.append({"class": cls, "why": why, "queue_key": _queue_key(cls, reason, fields),
                                      "kind": reason, **fields, "source": dict(source)})

    def queue(self, cls: str, page: Mapping[str, Any], why: str, source: Mapping[str, Any], *,
              problem_key: str = "") -> None:
        ident = verdict_reasons.record_identity(page)
        fields = {k: v for k, v in (("product_id", ident[0]), ("update_version", ident[1]),
                                    ("target_build", ident[2]), ("problem_key", problem_key)) if v}
        self.review_queue.append({"class": cls, "why": why, "queue_key": _queue_key(cls, "independence", fields),
                                  "kind": "independence", **fields, "page": _s(page.get("permalink")),
                                  "source": dict(source)})

    def as_dict(self) -> dict[str, Any]:
        return {"candidates": self.candidates, "excluded": self.excluded, "review_queue": self.review_queue}


def produce(records: Iterable[Mapping[str, Any]],
            counted_by_identity: Mapping[tuple[str, str, str], list[Mapping[str, Any]]], *,
            install_grouping: str = "") -> ProducerResult:
    """THE PRODUCER: every candidate, refusal and review item for this tree. Pure and deterministic:
    the same records and counted rows give the same result, byte for byte. `install_grouping` exists to
    MEASURE A1's superseded lenient reading beside the strict default (A3); nothing ships with it."""
    records = [r for r in records if isinstance(r, Mapping) and r.get("update_entry", True) is not False]
    pages = {verdict_reasons.record_identity(r): r for r in records}
    out = ProducerResult()
    _obs_candidates(records, pages, out)
    _windows_candidates(records, out)
    _install_candidates(records, counted_by_identity, out, install_grouping)
    out.candidates.sort(key=lambda c: (c["product_id"], c["update_version"], c.get("target_build", ""), c["id"]))
    out.excluded.sort(key=lambda e: json.dumps(e, sort_keys=True, ensure_ascii=False))
    out.review_queue.sort(key=lambda e: json.dumps(e, sort_keys=True, ensure_ascii=False))
    return out


def merge(valid_by_identity: Mapping[tuple[str, str, str], list[dict[str, Any]]],
          candidates: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    """The reviewed entries with the candidates added behind them. A candidate that repeats a
    reviewed entry's verdict and scope on the same page adds nothing: the reviewed one stands."""
    merged = {k: list(v) for k, v in valid_by_identity.items()}
    for cand in candidates:
        ident = verdict_reasons.reason_identity(cand)
        mine = merged.setdefault(ident, [])
        if any((_s(e.get("verdict")), _s(e.get("scope"))) == (cand["verdict"], cand["scope"]) for e in mine):
            continue
        mine.append(dict(cand))
    return {k: v for k, v in merged.items() if v}


def agreement_with_reviewed(result: ProducerResult,
                            reviewed: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """For each reviewed entry: whether the producer proposes the same verdict and scope on its page."""
    rows = []
    for entry in reviewed:
        ident = verdict_reasons.reason_identity(entry)
        same_page = [c for c in result.candidates if verdict_reasons.reason_identity(c) == ident]
        match = [c for c in same_page if (c["verdict"], c["scope"]) == (_s(entry.get("verdict")), _s(entry.get("scope")))]
        rows.append({"entry": _s(entry.get("id")), "reason_class": _s(entry.get("reason_class")),
                     "producer": "agrees" if match else ("differs" if same_page else "abstains"),
                     "candidates": [c["id"] for c in same_page]})
    return rows


ARTIFACT_NAME = "verdict_reason_candidates.yml"
ARTIFACT_HEADER = (
    "# GENERATED at deploy by auxsays/scripts/build_verdict_projection.py (lib/verdict_reason_producer) --\n"
    "# do not edit by hand. Never committed. The producer's candidates, refusals and TEMPORARY review queue,\n"
    "# derived from stored records and counted evidence only. PUBLIC_AUTO_ACTIVATION is OFF (TEMPORARY,\n"
    "# pending the owner's approval), so no page renders from this file; with it ON the verdict projection\n"
    "# carries the candidates.\n"
)


def artifact(result: ProducerResult) -> dict[str, Any]:
    return {"schema_version": 1, "producer_version": PRODUCER_VERSION,
            "public_auto_activation": bool(PUBLIC_AUTO_ACTIVATION),
            "min_independent_reporters": MIN_INDEPENDENT_REPORTERS,
            "review_queue_label": REVIEW_QUEUE_LABEL, **result.as_dict()}
