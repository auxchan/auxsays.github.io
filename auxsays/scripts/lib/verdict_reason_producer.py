"""The deterministic verdict-reason producer (G35-04, first increment).

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
    so they go to the review queue, never to a page. An OBS version counts only where the vendor
    names it as the defective one ("Fixed a crash in V", "present in V"), never as where an input
    file was made ("created in V").
    Recommendation: WAIT scoped to the setup when the vendor names this version as where the defect
    starts (the earliest version it names, or the originating build); TEST FIRST when the defect is
    carried over from an earlier version (a persistent problem is never called new) or is an
    installation failure.

  * user_corroborated_install_failure (G35-04 Amendment A1; calibration G35-05 section 5). The
    update fails to install, reported by at least MIN_INDEPENDENT_REPORTERS independent users on
    the page's own counted rows. A Windows row counts only when it reports THIS update failing to
    install (`windows_install_row`): it names the page's KB (a build alone is a device's current
    build or a rollback target, not the update, unless the row says "update/upgrade to <build>"); its
    install wording is not negated ("not that the update fails to install"), not about the update
    scan ("failed to check for updates") and not about another update (the nearest update the row
    names to that wording is this page's); and only the error codes attributed to this page's update
    are listed. Acrobat rows show installer "Exit Code 7" (a row shared between Pro and Reader must
    name this page's product). The MANDATORY independence gate (I11) runs before reporters are
    counted: a declared cross-post never counts, and a row that repeats a kept row (template-stripped
    token overlap, a shared log URL, the same set of two or more KB numbers) is the same reporter.
    Different URLs alone prove nothing (AUTH_V2_35 D-A). Different error codes are grouped as one
    problem here (A1's reading). That reading was a coordinator interpretation, NOT owner wording
    (Amendment A3: the owner's text is "the same concrete issue"); A3's strict grouping (a shared
    code or a shared stage) is not built in this increment -- a recorded follow-up, and one more
    reason the switch stays OFF. Recommendation: TEST FIRST "when installing it" -- never WAIT.

Everything else -- non-install user corroboration -- is NOT produced: `corroboration_candidates` is
the placeholder interface for that later work, and it fails closed. Pages that need a person go to
the review queue, which is TEMPORARY: it has no automated promotion yet.

THE SWITCH. `PUBLIC_AUTO_ACTIVATION` is the ONE activation switch. It is OFF, and it is TEMPORARY:
public automatic activation needs the owner's approval of that transition (AUTH_V2_35 D-A). OFF,
the decision authority reads only the reviewed `_data/verdict_reasons.yml`, so nothing published
changes; the producer still runs at deploy and its candidates are written to the git-ignored
`_data/verdict_reason_candidates.yml` for review. ON, lib/verdict_projection merges the candidates
into the supported reasons, so the projection, the gate, every surface and QA carry them.

NEVER A SECOND WRITER. The producer runs only where the projection is built (deploy time,
build_verdict_projection.py) and writes only that derived, git-ignored artifact. No collector, lane
or record writer imports it.

Reads its arguments and nothing else: no network, no clock, no file, no collector import
(test_verdict_reason_producer pins the import list).
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

from . import verdict_reasons

PRODUCER_VERSION = "2"
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
                     "no_stored_official_text", "candidate_schema", "not_enough_independent_reporters")
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
    r"^Fixed (?:a |an )?(?:possible |potential |rare |random )?(?:crash|freeze|hang|issue|bug|regression|problem)e?s? "
    r"in " + _OBS_VERSION_LIST + r"|\b(?:present|introduced) in " + _OBS_VERSION_LIST, re.ASCII)
_OBS_HEAD_RE = re.compile(r"^Fixed (?:a |an )?(?:possible |potential |rare |random )?(crash|freeze|hang)\b", re.I)
_OS_RE = re.compile(r"\bon (Windows|macOS(?: [0-9]+(?:\.[0-9]+)*)?|Linux)\b", re.ASCII)
_WHEN_RE = re.compile(r"\bwhen ([a-z][^;]*?)\s*\.?$")
_LAUNCH_RE = re.compile(r"\b(?:when (?:starting|launching|opening) OBS|on (?:launch|startup)|at startup)\b", re.I)
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
    profile reset are excluded BEFORE that, unless the head noun is a crash (a crash is a crash in
    any feature). Anything the grammar does not recognise has no severity basis: excluded."""
    text = re.sub(r"\s+", " ", statement).strip()
    os_m = _OS_RE.search(text)
    os_name = os_m.group(1) if os_m else ""
    head = _OBS_HEAD_RE.match(text)
    if head:
        kind = head.group(1).lower()
        when = _WHEN_RE.search(text)
        if kind == "crash":
            severity = "crash_on_launch" if _LAUNCH_RE.search(text) else "crash_in_core_flow"
        else:
            severity = "substantial_workflow_breakage"
        if when:
            clause = when.group(1).strip().rstrip(".")
            scope = f"when {clause}"
            if os_name and f"on {os_name}" not in clause:
                scope += f" on {os_name}"
        elif os_name:
            scope = f"if you use {os_name}"
        else:
            scope = ""  # no affected setup stated: `_scope_ok` refuses it when it is proposed
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
            if "excluded" in verdict_info:
                out.exclude(VENDOR_CLASS, verdict_info["excluded"], source, product_id=OBS, update_version=version,
                            severity=verdict_info.get("severity", ""))
                continue
            first = sorted(st["named"], key=_version_key)[0]
            new = version == first
            persistent = "" if new else f", carried over from OBS {first}"
            reason = (f"OBS confirms this problem in OBS {version}{persistent}: its {st['fixed_in']} release notes "
                      f"say \"{st['statement']}\".")
            out.propose(_candidate(
                VENDOR_CLASS, page, verdict=_vendor_verdict(verdict_info["severity"], new),
                scope=verdict_info["scope"], reason=reason, severity=verdict_info["severity"],
                failure=st["statement"], new=new, fixed_in=st["fixed_in"],
                citation=dict(source, vendor="OBS Project"),
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
    return {"severity": severity, "title": title, "scope": scope}


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
            if "excluded" in info:
                out.exclude(VENDOR_CLASS, info["excluded"], source, product_id=WINDOWS, update_version=line,
                            target_build=m.group("build"), severity=info.get("severity", ""))
                continue
            resolved = m.group("resolved") or ""
            status = (f"; Microsoft marks it resolved by {resolved}" if resolved
                      else f"; Microsoft lists it as {m.group('status').strip().lower()}")
            reason = (f"Microsoft lists a known issue that originates in this update (OS build {m.group('build')}, "
                      f"{m.group('kb')}): \"{info['title']}\"{status}.")
            out.propose(_candidate(
                VENDOR_CLASS, page, verdict=_vendor_verdict(info["severity"], True), scope=info["scope"],
                reason=reason, severity=info["severity"], failure=info["title"], new=True,
                fixed_in=resolved, citation=dict(source, vendor="Microsoft"),
                inputs={"statement_sha256": _sha(source["statement"]), "body_sha256": _sha(body)}))


# ============================================================ user_corroborated_install_failure

# Calibration G35-05 (section 4/5), ported verbatim in behaviour: stored fields only (title, excerpt,
# URL, applicability, the page's KB / build / version); never issue_theme, severity or sentiment.
_INSTALL_RX = re.compile(
    r"(install(?:ation)? (?:error|fail|issue|problem)|fail(?:ed|s|ing)? to (?:install|download)|"
    r"(?:will|would|could|does|did)(?: not|n't) install|can(?:'|no)?t install|cannot install|unable to install|"
    r"won't install|not install|download(?:ing)? error|keeps? (?:failing|giving me the message)|try again|"
    r"death loop|update(?:s)? (?:fail|failed|failing)|installation fail|failed to update|backed out)")
_EXIT7_RX = re.compile(r"exit code:?\s*7\b")
_CODE_RX = re.compile(r"\b0x[0-9a-f]{3,8}\b")
_XPOST_RX = re.compile(r"(previously posted|also posted|cross-?post|posted (?:this|it) (?:on|in)|i recently posted|"
                       r"part 2|part two)")
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
INDEPENDENCE_JACCARD = 0.45   # I10: template-stripped token overlap at or above this is one reporter


def _txt(row: Mapping[str, Any]) -> str:
    return (_s(row.get("report_title")) + " \n " + _s(row.get("report_text_excerpt"))).lower()


def _content_tokens(row: Mapping[str, Any]) -> set[str]:
    text = _s(row.get("report_title")) + " " + _s(row.get("report_text_excerpt"))
    for rx in _TEMPLATE_RX:
        text = rx.sub(" ", text)
    return {w for w in re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", text.lower()) if w not in _STOP}


def _kb_set(row: Mapping[str, Any]) -> set[str]:
    return set(re.findall(r"kb ?(\d{7})", _txt(row)))


def same_reporter(a: Mapping[str, Any], b: Mapping[str, Any]) -> str:
    """Why rows a and b are one reporter under the I11 independence gate, or "" when no cue fires.
    A different URL is never evidence of a different reporter."""
    ta, tb = _content_tokens(a), _content_tokens(b)
    if ta | tb and len(ta & tb) / len(ta | tb) >= INDEPENDENCE_JACCARD:
        return "near-identical text once templates are stripped"
    if _XPOST_RX.search(_txt(a)) or _XPOST_RX.search(_txt(b)):
        return "a declared cross-post"
    la = {m.lower() for m in _LOGURL_RX.findall(_s(a.get("report_text_excerpt")))}
    lb = {m.lower() for m in _LOGURL_RX.findall(_s(b.get("report_text_excerpt")))}
    if la & lb:
        return "the same log URL"
    ka, kb = _kb_set(a), _kb_set(b)
    if len(ka) >= 2 and ka == kb:
        return "the same set of KB numbers"
    return ""


def independent_reporters(rows: list[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], list[dict[str, str]]]:
    """(kept rows, dropped rows with why). Deterministic order (source_date, id); a declared cross-post
    never counts, and a row that is one reporter with an already kept row is dropped."""
    kept: list[Mapping[str, Any]] = []
    dropped: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda r: (_s(r.get("source_date")), _s(r.get("id")))):
        if _XPOST_RX.search(_txt(row)):
            dropped.append({"id": _s(row.get("id")), "why": "a declared cross-post"})
            continue
        why = next((w for w in (same_reporter(row, k) for k in kept) if w), "")
        if why:
            dropped.append({"id": _s(row.get("id")), "why": why})
            continue
        kept.append(row)
    return kept, dropped


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


def windows_install_row(row: Mapping[str, Any], page: Mapping[str, Any]) -> dict[str, Any]:
    """{ok, why, codes}: whether this counted row reports that THIS page's update fails to install,
    and the error codes it attributes to this update. Fails closed:
      * the row must name this update (`_page_mentions`: the KB, never the build alone);
      * denied install wording refuses the whole row (`_INSTALL_NEGATION_RX`);
      * "check for updates" and "rolls back to <build>" are not install failures (`_NOT_AN_INSTALL_RX`);
      * where the row names other updates too, some install wording must be about this one, read as a
        list (`_owner_is_page`): a .NET update failing beside this one is not this one failing;
      * error codes: only those about this update, read the same way (all of them when it is the only
        update named)."""
    text = _txt(row)
    if _INSTALL_NEGATION_RX.search(text):
        return {"ok": False, "why": "the row denies an install failure", "codes": []}
    text = _blank(text, _NOT_AN_INSTALL_RX)
    page_spans = _page_mentions(text, page)
    if not page_spans:
        return {"ok": False, "why": "the row does not name this update (its KB)", "codes": []}
    kb = re.sub(r"[^0-9]", "", _s(page.get("target_kb")))
    other_spans = [(m.start(), m.end()) for m in _KB_MENTION_RX.finditer(text) if m.group(1) != kb]
    wording = [(m.start(), m.end()) for m in _INSTALL_RX.finditer(text)]
    if not wording:
        return {"ok": False, "why": "no install-failure wording", "codes": []}
    if other_spans and not any(_owner_is_page(w, page_spans, other_spans) for w in wording):
        return {"ok": False, "why": "the install failure it reports is another update's", "codes": []}
    codes = [m.group(0) for m in _CODE_RX.finditer(text)
             if m.group(0)[2:].lstrip("0") and (not other_spans
                                                or _owner_is_page((m.start(), m.end()), page_spans, other_spans))]
    return {"ok": True, "why": "", "codes": sorted(set(codes))}


def _acrobat_row_matches(row: Mapping[str, Any], product_id: str) -> bool:
    text = _txt(row)
    if not _EXIT7_RX.search(text):
        return False
    if "," in _s(row.get("applicability")):
        names_reader = "reader" in text
        if product_id.endswith("reader") and not names_reader:
            return False
        if product_id.endswith("pro") and names_reader and "acrobat dc" not in text and "acrobat pro" not in text:
            return False
    return True


_NUMBER_WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine"}


def _install_candidates(records: list[Mapping[str, Any]],
                        counted_by_identity: Mapping[tuple[str, str, str], list[Mapping[str, Any]]],
                        out: "ProducerResult") -> None:
    for page in records:
        pid = _s(page.get("product_id"))
        if pid != WINDOWS and pid not in ACROBAT:
            continue
        rows = list(counted_by_identity.get(verdict_reasons.record_identity(page), []) or [])
        if len(rows) < MIN_INDEPENDENT_REPORTERS:
            continue
        codes_by_row: dict[str, list[str]] = {}
        if pid == WINDOWS:
            if not _s(page.get("target_kb")) or not _s(page.get("target_build")):
                continue
            matching = []
            for r in rows:
                verdict = windows_install_row(r, page)
                if verdict["ok"]:
                    matching.append(r)
                    codes_by_row[_s(r.get("id"))] = verdict["codes"]
        else:
            matching = [r for r in rows if _acrobat_row_matches(r, pid)]
        if len(matching) < MIN_INDEPENDENT_REPORTERS:
            continue
        kept, dropped = independent_reporters(matching)
        source = {"record": _s(page.get("permalink")), "rows": [_s(r.get("id")) for r in matching],
                  "dropped_by_independence_gate": dropped}
        if len(kept) < MIN_INDEPENDENT_REPORTERS:
            out.exclude(INSTALL_CLASS, "not_enough_independent_reporters", source, product_id=pid,
                        update_version=_s(page.get("update_version")), target_build=_s(page.get("target_build")),
                        note=f"{len(kept)} independent reporter(s) after the independence gate")
            out.queue(INSTALL_CLASS, page, "install-failure rows that the independence gate collapsed to "
                      f"{len(kept)} reporter(s): a person decides whether they are separate incidents", source)
            continue
        n = len(kept)
        count = _NUMBER_WORDS.get(n, str(n))
        if pid == WINDOWS:
            codes = sorted({c for r in kept for c in codes_by_row.get(_s(r.get("id")), [])})
            errors = f" (errors {', '.join(codes)})" if codes else ""
            reason = f"{count} users independently report that this update fails to install{errors}."
        else:
            reason = f"{count} users independently report that installing this version fails with installer Exit Code 7."
        evidence = [{"id": _s(r.get("id")), "source_url": _s(r.get("source_url"))} for r in kept]
        out.propose(_candidate(
            INSTALL_CLASS, page, verdict="TEST FIRST", scope=INSTALL_SCOPE, reason=reason,
            severity="critical_install_failure", failure="the update fails to install", new=False, fixed_in="",
            citation={}, evidence=evidence,
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

def _candidate(cls: str, page: Mapping[str, Any], *, verdict: str, scope: str, reason: str, severity: str,
               failure: str, new: bool, fixed_in: str, citation: dict, inputs: dict,
               evidence: list | None = None) -> dict[str, Any]:
    ident = verdict_reasons.record_identity(page)
    digest = _sha([cls, list(ident), verdict, scope, reason])[:12]
    entry = {
        "id": f"auto:{cls}:{ident[0]}:{ident[1]}{(':' + ident[2]) if ident[2] else ''}:{digest}",
        "product_id": ident[0], "update_version": ident[1],
        "verdict": verdict,
        "reason_class": INSTALL_REASON_CLASS if cls == INSTALL_CLASS else VENDOR_CLASS,
        "scope": scope, "reason": reason,
        "severity_basis": severity, "failure": failure,
        "evidence": list(evidence or []),
        "citation": citation,
        "new_in_this_version": bool(new),
        "page": _s(page.get("permalink")),
        "producer": {"class": cls, "version": PRODUCER_VERSION, "inputs": inputs},
    }
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


def scope_problem(scope: Any, product_id: str = "") -> str:
    """Why `scope` is not an affected setup, or "" when it is. THE scope rule, in one place.

    The scope is worded 'if / when / for ...' (the reviewed entries' SCOPE_RE) AND names a setup:
    at least one word outside _SCOPE_GENERIC_WORDS and the product's own name. "for a small number
    of devices", "for all editions of Windows 11", "for devices that have installed this update",
    "if you use the update", "if you use application" and "if you use OBS" all read like a scope
    and name nobody in particular, so a candidate carrying one would cover everyone. The install
    class's fixed scope ("when installing it") is the one exception: there the setup IS the act of
    installing (A1), and `candidate_problems` keeps it to installation failures."""
    text = _s(scope)
    if not verdict_reasons.SCOPE_RE.match(text):
        return "the scope is not worded 'if / when / for ...'"
    if text == INSTALL_SCOPE:
        return ""
    body = re.sub(r"^(?:if you use|if|when|for)\s+", "", text, flags=re.I)
    generic = _SCOPE_GENERIC_WORDS | _PRODUCT_WORDS.get(_s(product_id), frozenset())
    words = re.findall(r"[a-z0-9](?:[a-z0-9'+.-]*[a-z0-9])?", body.lower())
    if not [w for w in words if w not in generic and not _VERSION_TOKEN_RE.match(w)]:
        return ("the scope names no setup: only a quantifier, a population, an edition, the update, a generic "
                "application or the product")
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
        if not _scope_ok(entry.get("scope"), _s(entry.get("product_id"))):
            self.exclude(cls, "ambiguous_scope", entry.get("citation") or {}, **identity,
                         severity=entry.get("severity_basis", ""),
                         note=f"proposed scope {_s(entry.get('scope'))!r}: "
                              f"{scope_problem(entry.get('scope'), _s(entry.get('product_id')))}")
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
        if reason == "ambiguous_scope" and identity.get("severity"):
            self.review_queue.append({"class": cls, "why": "a serious confirmed defect whose affected setup "
                                      "the producer cannot state", **{k: v for k, v in identity.items() if v},
                                      "source": dict(source)})

    def queue(self, cls: str, page: Mapping[str, Any], why: str, source: Mapping[str, Any]) -> None:
        self.review_queue.append({"class": cls, "why": why, "page": _s(page.get("permalink")),
                                  "source": dict(source)})

    def as_dict(self) -> dict[str, Any]:
        return {"candidates": self.candidates, "excluded": self.excluded, "review_queue": self.review_queue}


def produce(records: Iterable[Mapping[str, Any]],
            counted_by_identity: Mapping[tuple[str, str, str], list[Mapping[str, Any]]]) -> ProducerResult:
    """THE PRODUCER: every candidate, refusal and review item for this tree. Pure and deterministic:
    the same records and counted rows give the same result, byte for byte."""
    records = [r for r in records if isinstance(r, Mapping) and r.get("update_entry", True) is not False]
    pages = {verdict_reasons.record_identity(r): r for r in records}
    out = ProducerResult()
    _obs_candidates(records, pages, out)
    _windows_candidates(records, out)
    _install_candidates(records, counted_by_identity, out)
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
