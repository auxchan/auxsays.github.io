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
    when closing a dialog is not, and a defect the vendor calls possible, rare or occasional goes to the
    review queue (review 2, LOW-2).
    Recommendation: WAIT scoped to the setup when the vendor names this version as where the defect
    starts (the earliest version it names, or the originating build); TEST FIRST, saying the problem
    PERSISTS, when the defect is carried over from an earlier version or the vendor says so (an older
    version number anywhere in the note, "earlier" / "previous" / "older" / "prior", a temporal "since",
    "also affected": review 2, LOW-1; G38 WS2 review, MAJOR-4) -- a persistent problem is never called
    new or caused -- and for an installation failure.

  * user_corroborated_install_failure (G35-04 Amendments A1, A3; AUTH_V2_37 correction 2). The update
    fails to install, in at least MIN_INDEPENDENT_REPORTERS reports of SEPARATE incidents of ONE
    problem on the page's own counted rows.
      - A Windows row counts only when it reports THIS update failing to install
        (`windows_install_row`): it names the page's KB (a build alone is a device's current build or a
        rollback target); its install wording is not negated, not about the update scan, and takes
        THIS update as its subject or object -- "after installing KB... my driver will not install" is
        the driver failing, not the update (review 2 LOW-3), and so is install wording whose object is
        other software ("can't install the Realtek driver since KB..."); error codes are read only in
        install-error context, never from a crash or bugcheck. Acrobat rows (`acrobat_install_row`)
        show installer "Exit Code 7" that is not another Adobe product's, do not say the version
        installed, and a row shared between Pro and Reader must name this page's product.
      - One problem (A3, INSTALL_GROUPING "strict"): rows group only on a shared failure
        characteristic -- the same error code, the same named stage, for Acrobat the same SPECIFIC
        installer error (DW / DF code), never the generic Exit Code 7 every failure prints. Different
        error codes alone are not one problem.
      - Independence FAILS CLOSED (AUTH_V2_37 correction 2). Copies are DETECTED -- a declared
        cross-post, re-post or follow-up, the same log, near-identical text, a shared distinctive
        passage (a reworded re-post keeps one), the same KB set, the same incident details -- and only
        ever REMOVE a would-be second reporter; detection never touches stored evidence. A second report
        COUNTS only where the source supports a different reporter or machine: a source reporter id that
        differs (no collector stores one today), or identity details that cannot belong to one machine
        (two different computers, processors, editions, architectures, operating systems). A failure
        point or an OS version never does: one person's retry or OS upgrade shows both. Unknown is not
        independent. Shared wording or a shared author never merges two machines whose details conflict
        (conservative grouping), not even through a third row.
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

PRODUCER_VERSION = "4"
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
                     "no_shared_failure_characteristic", "uncertain_severity")
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
# A defect the vendor itself calls uncertain ("a possible crash", "a rare freeze", "can sometimes") is for a
# person: the review queue, never an automatic verdict (review 2, LOW-2).
_UNCERTAIN_RE = re.compile(r"\b(?:possible|potential|potentially|rare|rarely|random|occasional|occasionally|"
                           r"intermittent|sporadic|sometimes|in some cases)\b", re.I)
# Review 2, LOW-1 (A3): wording that says the defect was ALREADY there makes it a PERSISTENT defect: TEST FIRST
# saying it persists, never WAIT and never "new" or caused by this version. The rule is not a phrase list of
# carried-over idioms (G38 WS2 review, MAJOR-4: "that also occurred in earlier versions", "which existed in
# previous versions" read as new): "earlier", "previous(ly)", "older" or "prior" ANYWHERE in the bullet is
# persistent, and so is any older OBS version number in it (`_obs_persistence`: "(a regression in 31.0.0)",
# "as in 32.0.4", "(also seen in 31.1.2)"). Beside those: a temporal "since" ("since 31.0", "since the first
# release"; a causal one -- "since the output was freed twice" -- is not), "a regression from / since / in",
# "also affected / occurred / seen", "still present", "persists", "carried over", "long-standing",
# "pre-existing".
_PERSISTENT_RE = re.compile(
    r"\b(?:earlier|previous|previously|older|prior)\b|"
    r"\bsince (?:at least |about |around |as early as )?(?:obs (?:studio )?)?(?:v(?:ersion)? ?)?\d|"
    r"\bsince (?:the )?(?:first|initial|original|introduction|launch|release|beginning|start)\b|\bever since\b|"
    r"\bregression (?:from|since|in)\b|\balso (?:affect\w*|occur\w*|happen\w*|present|seen|existed|exists|reported)\b|"
    r"\bstill (?:present|occur\w*|happen\w*)|\bpersist\w*|\bcarried over\b|\blong-?standing\b|\bpre-?existing\b|"
    r"\bexist(?:ed|s)? (?:in|since|before)\b|\b(?:as|like) in (?:obs (?:studio )?)?v?\d", re.I)
# A trailing carry-over remark in a "when ..." clause (", which existed in previous versions", "that also occurred in
# earlier versions", "(also seen in 31.1.2)"): the defect's history, kept out of the scope.
_PERSISTENCE_TAIL_RE = re.compile(
    r"\s*,?\s*\b(?:that|which)\s+(?:also\s+)?(?:occurred|existed|happened|appeared|was present|were present)\b.*$|"
    r"\s*\([^()]*\b(?:regression|also|earlier|previous|older|prior|since)\b[^()]*\)\s*$", re.I)
# A three-part version number anywhere in a bullet, and the platforms / components whose own version numbers
# are not OBS versions ("on macOS 14.4.1", "Qt 6.5.3").
_ANY_VERSION_RE = re.compile(r"(?<![\w.])(\d+\.\d+\.\d+)(?![\w.]*\d)", re.ASCII)
_PLATFORM_BEFORE_RE = re.compile(
    r"\b(?:macos|mac os(?: x)?|os x|windows|linux|ubuntu|debian|fedora|kernel|mesa|qt|cef|chromium|ffmpeg|python|"
    r"lua|nvidia|amd|intel|cuda|driver|sdk|plugin|obs-websocket|websocket|pipewire|wayland|glibc|xcode|vulkan|"
    r"directx|opengl|librist|srt|x264|aja|decklink)\s*(?:version\s*)?v?$", re.I)


def _obs_persistence(statement: str, version: str) -> str:
    """Where an OBS bullet says the defect was already there BEFORE `version`: "OBS <v>" for the earliest
    older OBS version it names ANYWHERE (as the defective one -- "in 31.1.0 and 31.1.1" read on 31.1.1 -- or
    not: "a regression in 31.0.0", "as in 32.0.4"), "earlier versions" for carried-over wording without one,
    or "" when the bullet names `version` as where the defect starts (new in it). A version number that
    belongs to a platform or component ("macOS 14.4.1") is not an OBS version."""
    key = _version_key(version)
    older = {m.group(1) for m in _ANY_VERSION_RE.finditer(statement)
             if _version_key(m.group(1)) < key
             and not _PLATFORM_BEFORE_RE.search(statement[max(0, m.start() - 40):m.start()])}
    if older:
        return f"OBS {sorted(older, key=_version_key)[0]}"
    return "earlier versions" if _PERSISTENT_RE.search(statement) else ""


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
    (review 2, LOW-2; G38 WS2 review, LOW-1): otherwise it has no severity basis. A crash, freeze or hang
    the vendor calls uncertain ("a possible crash", "a rare freeze") is `uncertain_severity`: refused, and
    queued for a person. Anything the grammar does not recognise has no severity basis: excluded."""
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
            # The carry-over remark is about the defect's history, not the setup: "when starting a recording
            # that also occurred in earlier versions" is scoped "when starting a recording".
            clause = _PERSISTENCE_TAIL_RE.sub("", when.group(1).strip().rstrip(".")).strip()
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
        return {"severity": severity, "failure_kind": kind, "scope": scope}
    if _LAG_RE.search(text):
        return {"excluded": "minor_lag"}
    if _COSMETIC_RE.search(text):
        return {"excluded": "narrow_cosmetic"}
    if _PREFERENCE_RE.search(text):
        return {"excluded": "recoverable_preference_or_profile"}
    if _DATA_LOSS_RE.search(text):
        severity, kind = "data_loss", "data loss"
    elif _INSTALL_FAIL_RE.search(text):
        return {"severity": "critical_install_failure", "failure_kind": "install failure", "scope": INSTALL_SCOPE}
    else:
        severity, kind = "", ""
    m = _BREAK_WHERE_RE.search(text) or _BREAK_CAUSING_RE.search(text)
    if m:
        severity = severity or "substantial_workflow_breakage"
        kind = kind or "stops working"
        np = _scope_np(m.group("np"))
        if not np or len(np.split()) > 8 or re.search(r"\b(?:user|you|it|this|that)\b", np, re.I):
            return {"severity": severity, "failure_kind": kind, "scope": ""}
        scope = f"if you use {np}"
        ctx = (m.group("ctx") or "").strip().rstrip(".")
        if os_name and f"on {os_name}" not in np:
            scope += f" on {os_name}"
        elif re.match(r"^in the [A-Za-z][\w -]{0,30}$", ctx):
            scope += f" {ctx}"
        return {"severity": severity, "failure_kind": kind, "scope": scope}
    if severity:
        return {"severity": severity, "failure_kind": kind, "scope": ""}
    return {"excluded": "no_severity_basis"}


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
# Microsoft's wording that an issue is older than its originating build (narrower than OBS's: a known
# issue "since installing this update" is new in it).
_WIN_PERSISTENT_RE = re.compile(r"\b(?:and earlier|or earlier|also affect\w* (?:earlier|previous|older)|(?:earlier|previous|"
                                r"older) (?:updates|versions|builds|releases) (?:are|were) also affected|still present|"
                                r"persist\w*|long-?standing|pre-?existing)\b", re.I)


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
            # The originating build is where Microsoft says the issue STARTS. Wording that it also affects
            # earlier updates makes it a persistent defect: TEST FIRST, never "originates" (review 2 LOW-1, A3).
            new = not _WIN_PERSISTENT_RE.search(m.group("summary"))
            lead = ("Microsoft lists a known issue that originates in this update" if new
                    else "Microsoft lists a known issue that persists in this update (it also affects earlier updates)")
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
# G38 WS2 review, MAJOR-1). Such a row is never a second reporter.
_XPOST_RX = re.compile(r"(previously posted|also posted|cross-?post|posted (?:this|it) (?:on|in)|i recently posted|"
                       r"part 2|part two|follow(?:ing)?[- ]?up (?:on|to|from) my|\bre-?post(?:ing|ed|s)?\b|"
                       r"posting (?:this |it )?again|(?:i )?posted (?:this |it )?(?:before|earlier|already|yesterday|"
                       r"last week)|my (?:earlier|previous|original|last|other) (?:post|question|thread|topic)|"
                       r"same as my (?:earlier|previous|other|original) )")
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
# when the source supports a DISTINCT identity (REPORTER_ID_FIELD, different on both rows) or a DISTINCT
# MACHINE: both rows state a detail of the same IDENTITY kind (IDENTITY_DETAIL_KINDS) and the values cannot
# belong to one machine -- two different computers (manufacturer or model family), processors, Windows
# editions or architectures, or operating systems (an Acrobat installer on a Mac and on Windows 10). A row
# that states no such detail cannot be told apart from anyone, so it never makes a second reporter: unknown
# is not independent.
# What ONE person on ONE machine can show twice is never a second incident (G38 WS2 review, MAJOR-1): a
# retry that stops at another percentage, a CPU at 100% beside an install at 20%, the same Mac upgraded from
# Sierra to High Sierra between two posts. Failure points and OS versions are COPY_ONLY_DETAIL_KINDS: read
# only as copy-detection cues (the same ones on two rows), never as independence and never as a conflict
# that keeps two copies apart.
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
    ("apple", re.compile(r"\b(?:macbook|imac|mac mini|mac pro)\b")),
)
# A manufacturer counts as the computer's only beside a computer noun ("my Dell laptop"), never alone
# ("the HP Smart printer app").
_DEVICE_BRAND_RX = re.compile(
    r"\b(dell|hp|lenovo|asus|acer|msi|samsung|razer|gigabyte|huawei|toshiba|fujitsu|medion|microsoft)\b"
    r"(?:\s+[a-z0-9-]+){0,2}?\s+(?:laptop|notebook|pc|desktop|computer|machine|tablet|workstation|ultrabook|"
    r"all-in-one)s?\b")
# A processor only where the row names one ("Intel(R) Core(TM) i9", "Ryzen", "Snapdragon"), never a bare
# vendor name, which is as often a driver ("failed error: Intel - SoftwareComponent").
_CPU_RX = (("intel", re.compile(r"\b(?:intel(?:\(r\))? (?:core|celeron|pentium|xeon|processor|cpu)|"
                                r"core(?:\(tm\))? i[3579]|core ultra|celeron|pentium|xeon)\b")),
           ("amd", re.compile(r"\b(?:ryzen|threadripper|athlon|amd (?:processor|cpu))\b")),
           ("qualcomm", re.compile(r"\b(?:snapdragon|qualcomm (?:processor|cpu))\b")))
_EDITION_RX = re.compile(r"\bwindows ?11 ?(home|pro|enterprise|education|iot|se)\b|\b(home|pro|enterprise|education) "
                         r"edition\b")
_ARCH_RX = re.compile(r"\b(x64|arm64|x86)(?:-based)?\b")
_MAC_RX = re.compile(r"\b(?:mac|macos|mac os|os x|osx|macbook|imac|el capitan|sierra|mojave|catalina|big sur|monterey|"
                     r"ventura|sonoma|sequoia)\b")
_WINDOWS_OS_RX = re.compile(r"\b(?:windows ?(7|8\.1|8|10|11|xp|vista)|win ?(7|8|10|11))\b")
_MAC_NAMES = {"el capitan": "10.11", "high sierra": "10.13", "sierra": "10.12", "mojave": "10.14", "catalina": "10.15",
              "big sur": "11", "monterey": "12", "ventura": "13", "sonoma": "14", "sequoia": "15"}
_MAC_VERSION_RX = re.compile(r"\b(?:mac ?os(?: x)?|os x|osx)\s*(10\.\d{1,2}|1[1-9])\b|\b(10\.(?:[4-9]|1[0-5]))\.\d+\b")
_PERCENT_RX = re.compile(r"\b(?:at|to|reaches|reached|reaching|around|about|until)\s+(\d{1,3})\s?(?:%|percent\b)")


def incident_details(row: Mapping[str, Any], product_id: str = "") -> dict[str, frozenset]:
    """The concrete incident details a row states, by kind (only kinds it states): IDENTITY_DETAIL_KINDS
    and COPY_ONLY_DETAIL_KINDS."""
    text = _blank(_txt(row), _NOT_AN_INSTALL_RX)
    found: dict[str, set] = {}

    def add(kind: str, value: str) -> None:
        found.setdefault(kind, set()).add(value)
    for family, rx in _DEVICE_FAMILY_RX:
        if rx.search(text):
            add("device", family)
    for m in _DEVICE_BRAND_RX.finditer(text):
        add("device", "surface" if m.group(1) == "microsoft" else m.group(1))
    for cpu, rx in _CPU_RX:
        if rx.search(text):
            add("cpu", cpu)
    for m in _EDITION_RX.finditer(text):
        add("edition", m.group(1) or m.group(2))
    for m in _ARCH_RX.finditer(text):
        add("architecture", m.group(1))
    if _s(product_id) != WINDOWS:
        if _MAC_RX.search(text):
            add("os", "mac")
        for m in _WINDOWS_OS_RX.finditer(text):
            add("os", "windows")
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


def _reporter_ids(row: Mapping[str, Any]) -> frozenset:
    value = _s(row.get(REPORTER_ID_FIELD))
    return frozenset({value}) if value else frozenset()


def same_reporter(a: Mapping[str, Any], b: Mapping[str, Any], product_id: str = "") -> str:
    """Why rows a and b are ONE report (a copy or cross-post), or "" when no cue fires. DETECTION ONLY:
    a cue removes a would-be second reporter; no cue never makes two rows independent (that needs
    `distinct_incident`), and nothing here touches stored evidence.

    Cues: a declared cross-post, re-post or follow-up; the same log URL; near-identical text once templates
    are stripped; a shared distinctive passage (SHARED_PASSAGE_WORDS consecutive content words: a reworded
    re-post keeps one); the same set of two or more KB numbers; the same source reporter id; the same
    incident details (any kinds, the copy-only ones included).
    CONSERVATIVE: two rows whose IDENTITY details conflict are two machines, so no cue but a declaration or
    the shared log merges them -- shared wording or a shared author alone never collapses genuinely distinct
    incidents."""
    if _XPOST_RX.search(_txt(a)) or _XPOST_RX.search(_txt(b)):
        return "a declared cross-post"
    la = {m.lower() for m in _LOGURL_RX.findall(_s(a.get("report_text_excerpt")))}
    lb = {m.lower() for m in _LOGURL_RX.findall(_s(b.get("report_text_excerpt")))}
    if la & lb:
        return "the same log URL"
    da, db = incident_details(a, product_id), incident_details(b, product_id)
    if _conflicting(da, db):
        return ""
    ta, tb = _content_tokens(a), _content_tokens(b)
    if ta | tb and len(ta & tb) / len(ta | tb) >= INDEPENDENCE_JACCARD:
        return "near-identical text once templates are stripped"
    if _passages(a) & _passages(b):
        return "a shared distinctive passage"
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
    if a["reporter_ids"] and b["reporter_ids"] and not (a["reporter_ids"] & b["reporter_ids"]):
        return "different source reporter ids"
    return ""


def _may_join(why: str, a: Mapping[str, frozenset], b: Mapping[str, frozenset]) -> bool:
    """Whether two clusters a copy cue links may become ONE report: never when their merged identity details
    conflict (that would put two machines into one report), except on the same log URL."""
    return why == "the same log URL" or not _conflicting(a, b)


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
            if a["reporter_ids"] and b["reporter_ids"] and not (a["reporter_ids"] & b["reporter_ids"]):
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
# An update named without its KB ("the update", "this security update", "Windows Update", "update"): about
# this page's update only where the row names this page's KB and the list reading gives it to this page.
_GENERIC_UPDATE_RX = re.compile(r"\b(?:(?:this|the|that|an?|latest|recent|new|newest|security|cumulative|preview|"
                                r"quality|monthly|optional|non-security|windows|11)\s+)*updates?\b")
# Words that put ANOTHER subject or object between the update and the install wording (review 2 LOW-3, F7:
# "After installing KB5089573 my Nvidia graphics driver will not install anymore", "Since KB5089573 the HP
# Smart printer app fails to install from the Store"): other software, or a new possessive subject ("my
# driver"; "on my laptop" is a place, not a subject).
_OTHER_SOFTWARE = (r"\b(?:drivers?|apps?|applications?|programs?|software|games?|printers?|office|store|nvidia|"
                   r"geforce|radeon|realtek|dotnet|framework|defender|edge|teams|outlook|chrome|firefox|"
                   r"steam|bios|firmware|antivirus|language packs?|feature update|other updates?|another update)\b"
                   r"|\.net\b")
_FOREIGN_SUBJECT_RX = re.compile(
    _OTHER_SOFTWARE + r"|(?<!\bon )(?<!\bin )(?<!\bfor )(?<!\bwith )(?<!\bfrom )(?<!\bto )\b(?:my|our|his|her|their)\b")
# The OBJECT of a transitive install wording, read from the wording up to the next update named, a clause
# break, a comma or a linking word: "I can't install the new Realtek audio driver since KB...", "unable to
# install Office after KB..." -- the driver or Office is what fails to install, not the update (G38 WS2
# review, MAJOR-2). Other software there refuses the wording, wherever the update is named.
_FOREIGN_OBJECT_RX = re.compile(_OTHER_SOFTWARE)
_OBJECT_END_RX = re.compile(r"[,;:.!?()\n]|\b(?:since|after|before|when|while|because|as|but|and|or|so|then|with|on|"
                            r"in|from|for|due|via|through|using|at|to|until|every|each|again|anymore|error|code)\b")
_CLAUSE_BREAK_RX = re.compile(r"[.!?;](?=\s)|\n")
_SUBJECT_GAP = 80   # characters between the update's name and install wording that takes it as subject
_OBJECT_GAP = 60    # characters between transitive install wording and the update it takes as object
_ROLLBACK_RX = re.compile(r"\b(?:roll(?:s|ed|ing)?[ -]?back|undo(?:ing)? (?:the )?changes|revert(?:s|ed|ing)? (?:the )?"
                          r"changes|could ?n[o']?t complete the updates?)\b")


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
                     page_spans: list[tuple[int, int]], other_spans: list[tuple[int, int]]) -> bool:
    """Whether the install wording at `span` takes THIS update as its subject or object (review 2 LOW-3,
    F7). A transitive wording whose OBJECT is other software ("can't install the new Realtek driver since
    KB...") is that software failing: refused first, wherever the update is named (G38 WS2 review,
    MAJOR-2). Then, in its clause: the nearest update named before it, with no other subject in between;
    else, for a transitive wording, the update named right after it; else, with no update and no other
    subject named before it in the clause, the update the row is about (the list reading). Otherwise it is
    about something else -- a driver, an app, another update -- and does not count."""
    c0, c1 = _clause(text, span[0])
    if text[span[0]:span[1]].startswith("update"):
        return _owner_is_page(span, page_spans, other_spans)   # "update failed": its own subject
    before = [r for r in refs if c0 <= r[0] and r[1] <= span[0]]
    after = [r for r in refs if span[1] <= r[0] < c1]
    if _INSTALL_TRANSITIVE_RX.match(text[span[0]:span[1]]):
        stop = _OBJECT_END_RX.search(text, span[1])
        obj_end = min([c1] + [r[0] for r in after] + ([stop.start()] if stop else []))
        if _FOREIGN_OBJECT_RX.search(text[span[1]:max(obj_end, span[1])]):
            return False
    if before:
        gap = text[before[-1][1]:span[0]]
        if len(gap) <= _SUBJECT_GAP and not _FOREIGN_SUBJECT_RX.search(gap):
            return _coordinated(text, before, len(before) - 1, -1)
    if after and _INSTALL_TRANSITIVE_RX.match(text[span[0]:span[1]]):
        gap = text[span[1]:after[0][0]]
        if len(gap) <= _OBJECT_GAP and not _FOREIGN_SUBJECT_RX.search(gap):
            return _coordinated(text, after, 0, 1)
    if not before and not _FOREIGN_SUBJECT_RX.search(text[c0:span[0]]):
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
    text = _blank(text, _NOT_AN_INSTALL_RX)
    page_spans = _page_mentions(text, page)
    if not page_spans:
        return {"ok": False, "why": "the row does not name this update (its KB)", "codes": [], "stages": []}
    kb = re.sub(r"[^0-9]", "", _s(page.get("target_kb")))
    other_spans = [(m.start(), m.end()) for m in _KB_MENTION_RX.finditer(text) if m.group(1) != kb]
    wording = [(m.start(), m.end()) for m in _INSTALL_RX.finditer(text)]
    if not wording:
        return {"ok": False, "why": "no install-failure wording", "codes": [], "stages": []}
    refs = sorted([(s, e, True) for s, e in page_spans] + [(s, e, False) for s, e in other_spans]
                  + [(m.start(), m.end(), _owner_is_page((m.start(), m.end()), page_spans, other_spans))
                     for m in _GENERIC_UPDATE_RX.finditer(text)
                     if not any(m.start() < e and s < m.end() for s, e in page_spans + other_spans)])
    accepted = [w for w in wording if _install_subject(text, w, refs, page_spans, other_spans)]
    if not accepted:
        if other_spans and not any(_owner_is_page(w, page_spans, other_spans) for w in wording):
            return {"ok": False, "why": "the install failure it reports is another update's", "codes": [], "stages": []}
        return {"ok": False, "why": "the install failure it reports is not this update's (another subject fails "
                "to install)", "codes": [], "stages": []}
    clauses = sorted({_clause(text, w[0]) for w in accepted})
    # The clause right after one that reports this update failing, when it names no other update or
    # subject: "20206-01 update won't install. Get error code 0x800f0991".
    follow = []
    for c0, c1 in clauses:
        nxt = _clause(text, min(c1 + 1, len(text)))
        if nxt[0] > c0 and not any(nxt[0] <= s < nxt[1] for s, _e in other_spans) \
                and not _FOREIGN_SUBJECT_RX.search(text[nxt[0]:nxt[1]]):
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
# The row says this version DID install, or that the error went away.
_ACROBAT_NEGATION_RX = re.compile(
    r"\binstall(?:ed|s) (?:fine|ok|okay|correctly|successfully|normally|without (?:any )?(?:issues?|problems?|"
    r"errors?))\b|\b(?:successfully|correctly|properly) installed\b|"
    r"\b(?:exit code:?\s*7|the error|the problem|the issue|it)\b(?:\W+\w+){0,3}?\W+(?:is|was|has been) "
    r"(?:gone|fixed|resolved|solved)\b|\bno longer (?:get|gets|getting|see|seeing|shows?)\b")


def acrobat_install_row(row: Mapping[str, Any], product_id: str) -> dict[str, Any]:
    """{ok, why, codes}: whether this counted row reports that THIS Acrobat product fails to install, and
    the installer's specific error codes (DW / DF) it shows. Fails closed:
      * installer Exit Code 7 must be shown, and a row shared between Pro and Reader must name this page's
        product (the calibration's P15/P16 refusal);
      * a row that says the version installed, or that the error is gone, is refused;
      * Exit Code 7 counts only where it is not another Adobe product's ("Acrobat installed fine, but
        Photoshop fails with Exit Code: 7"): the product named nearest before it in its clause, else the
        first after it, else the row's.
    Codes are read outside clauses about another product."""
    text = _txt(row)
    if not _EXIT7_RX.search(text):
        return {"ok": False, "why": "no installer Exit Code 7", "codes": []}
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
    characteristic joins no group. Lenient (A1's superseded reading, for measurement only): every install
    row is one problem."""
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
            keys = [f"error {c}" for c in info.get("codes", [])] + list(info.get("stages", []))
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
                info = acrobat_install_row(r, pid)
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
