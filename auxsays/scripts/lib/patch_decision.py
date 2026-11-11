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

THE AVOID RUNG, AND THE POLICY ITSELF, CHANGED IN GROWTH-3. The product and sentiment branches
described above are gone: they made 233 of 235 report-bearing pages WAIT on 2026-11-06, which the
owner's verdict policy (decisions 1-3, 2026-11-06) retired. The policy now lives in `decide` at the
end of this module -- an official withdrawal (AVOID), Microsoft's monthly security classification
(SECURITY UPDATE), a reviewed and still-supported reason entry (WAIT / TEST FIRST), else
INSUFFICIENT DATA -- and AVOID is reachable again, but only from the one verified lifecycle record.
The history above is kept because it explains why one function, not three, decides.
"""
from __future__ import annotations

import re
import unicodedata
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


_SCOPE_PREFIX_RE = re.compile(r"^(?:if|when|for) [^\s:][^:]*$")


def leading_decision(text: str) -> str:
    """The decision a field opens with, as a reader sees it: `PHRASE:` at the start, else "".

    Longest match first, so "WAIT for production systems:" is never read as "WAIT".

    A SCOPED lead is the same decision: GROWTH-3 stores "WAIT if you use macOS 27.2: ..." so the
    feed never prints a verdict without the setup it applies to, and that field still opens with
    WAIT. The scope must read the way a reason entry's scope reads ("if/when/for ...", no colon),
    so a vendor title that merely begins with a decision word is not mistaken for one.
    """
    body = str(text or "")
    for phrase in _LONGEST_FIRST:
        if body.startswith(phrase + ":"):
            return phrase
    for phrase in _LONGEST_FIRST:
        if body.startswith(phrase + " ") and ":" in body:
            head = body.split(":", 1)[0]
            if _SCOPE_PREFIX_RE.match(head[len(phrase) + 1:]):
                return phrase
    return ""


# ---------------------------------------------------------------------------------------------
# GROWTH-3: THE VERDICT POLICY (owner decisions 1-3, 2026-11-06).
#
# A verdict is a pure function of STORED FACTS, decided here and nowhere else:
#
#   R1  AVOID            an applicable official withdrawal for new installations (the lifecycle
#                        file; today ONE verified exception, KB5079391)
#   R2  SECURITY UPDATE  Microsoft's own classification of the exact update as a monthly security
#                        release (release-health update type "YYYY-MM B", stored on the record).
#                        User reports never override it; reviewed reasons only add a warning panel
#   R3  WAIT             a reviewed `regression` reason entry that is supported by counted rows
#   R4  TEST FIRST       a reviewed corroboration reason entry that is supported by counted rows
#   R5  INSUFFICIENT DATA, the reported problems disclosed (reports, no supported reason)
#   R6  INSUFFICIENT DATA (no reports, no official fact)
#
# WHAT IS NEVER AN INPUT. Report count, sentiment (`update_consensus_label`), `issue_theme`,
# `severity`, maturity, `update_status` and the clock. `decide` does not accept them, so no count
# can make a WAIT (G3-D4), no negative tone can (G3-D3), no theme-derived severity can (G3-D12), and
# nothing becomes SAFE ENOUGH because time passed or complaints stopped (G3-D2). SAFE ENOUGH,
# OFFICIAL ONLY and MANUAL WATCH stay canonical (recognised, ranked) but this policy produces none
# of them: no positive evidence is collected.
#
# THE TEMPLATES DO NOT DECIDE A REASONED VERDICT. WAIT, TEST FIRST and a security page's warning
# panel rest on reason entries that only Python can validate (counted rows, distinct reporters, a
# verbatim official confirmation). `build_verdict_projection.py` runs `decide` for every page at
# deploy, before QA and before Jekyll, and writes the result -- verdict, scope, line, panel -- to
# `_data/verdict_projection.yml` (lib/verdict_projection). `_includes/patch-verdict-gate.html` READS
# that row and prints it; it never evaluates an entry. The OFFICIAL verdicts travel the same way:
# the projection carries a row for every AVOID and SECURITY UPDATE page too (with its line, and
# AVOID's recommendations), so a zero-report security update -- which no writer touches -- still
# reads SECURITY UPDATE, and the gate re-derives nothing. Until review 2 it read the lifecycle file
# and parsed the release type itself (`slice` + `plus: 0`), and printed AVOID / SECURITY UPDATE
# where `decide` did not (LOW-1). No row, or no projection: INSUFFICIENT DATA, no panel (fail
# closed). `qa_patch_records --publish-strict` errors when the projection a deploy built disagrees
# with `decide` on any page, and test_growth3_verdict_policy pins the gate against Python over the
# whole corpus. (Round 0 mirrored the support rule in Liquid with a URL-only check, which published
# a WAIT that `decide` refused: GROWTH-3 review 1, D2.)
# ---------------------------------------------------------------------------------------------
SECURITY_UPDATE = "SECURITY UPDATE"
AVOID = "AVOID"
AVOID_SCOPE = "for new installations"
WAIT = "WAIT"
TEST_FIRST = "TEST FIRST"

# ASCII ONLY (PR-A2 review, LOW-2, probe P3). Without re.ASCII, `\d` matches any Unicode digit and
# int() reads it, so a preview page whose release type was rewritten with full-width or Arabic-Indic
# digits and a " B" decided SECURITY UPDATE. Now such a value is not a release type; its shape still
# marks it as meant to be one, so release_type_problem names it (windows_update_type_malformed).
_MONTHLY_SECURITY_RE = re.compile(r"^(\d{4})-(\d{2}) B$", re.ASCII)
_PREVIEW_RE = re.compile(r"^(\d{4})-(\d{2}) D$", re.ASCII)
# Every release-health type a Windows record stores today: monthly security "B", preview "D",
# out-of-band "OOB" (43 / 32 / 21 records; the 97th carries the writer default "official-source").
_RELEASE_TYPE_RE = re.compile(r"^(\d{4})-(\d{2}) (?:B|D|OOB)$", re.ASCII)
# A value that opens like one ("YYYY-") or ends with one of its type codes is MEANT to be one.
# NOT ASCII-only, on purpose (G35-04 review 2, LOW-6): this detector decides only whether a value the
# strict patterns above refuse is REPORTED, so it must see the shape in any script. With re.ASCII here
# too, full-width digits with a full-width "B" (U+FF22), full-width digits with an ideographic space
# (U+3000) before "B", and Arabic-Indic digits with a full-width "B" matched neither the strict pattern
# nor this one: a real B page lost SECURITY UPDATE with QA silent. It reads `_release_type_shape(raw)`,
# the NFKC form, so full-width forms (the hyphen U+FF0D and the letter too) show the shape they
# imitate; Unicode `\d` and `\s` cover what NFKC leaves alone (Arabic-Indic digits and letters).
# test_growth3_verdict_policy G3-Q8 carries every one of these values.
_RELEASE_TYPE_SHAPED_RE = re.compile(r"^\s*\d{4}\s*-|\s(?:B|D|OOB)\s*$")


def _release_type_shape(raw: str) -> str:
    """The form `_RELEASE_TYPE_SHAPED_RE` reads: NFKC (full-width digits, hyphen, letters and the
    ideographic space become their ASCII look-alikes). Never used to ACCEPT a value: the strict
    patterns always read the raw text."""
    return unicodedata.normalize("NFKC", raw)

# Public wording, ONE copy. The gate include renders these exact strings; the corpus test compares
# every rendered page body with what the writer stored.
OTHER_SETUPS = "Other setups: no problem is independently reported yet; the individual reports are listed below."
TEST_FIRST_TRY = "Try it on a non-critical machine or a copy of your work first."
TEST_FIRST_INSTALL = "Install it on one machine first before rolling it out more widely."
SECURITY_LEAD = ("Microsoft classifies this as a monthly security update and recommends keeping "
                 "supported systems updated.")
SECURITY_PANEL_LEAD = {
    "corroborated_install_problem": (
        "Security update - installation issues reported. Microsoft recommends keeping supported "
        "systems updated. Some users have reported installation failures on this build. Review the "
        "affected configurations and available fixes before deploying to critical systems."),
    "corroborated_issue": (
        "Security update - a problem is reported on some setups. Microsoft recommends keeping "
        "supported systems updated. Review the affected configuration before deploying to critical "
        "systems."),
    "regression": (
        "Security update - a confirmed problem affects some setups. Microsoft recommends keeping "
        "supported systems updated. Hold deployment only on the affected systems until a fix is "
        "available."),
    # G35-04: a vendor-confirmed serious defect (lib/verdict_reason_producer). Reached only while
    # PUBLIC_AUTO_ACTIVATION is on (TEMPORARY: off, pending the owner's approval).
    "vendor_confirmed_serious": (
        "Security update - Microsoft confirms a known issue on some setups. Microsoft recommends "
        "keeping supported systems updated. Hold deployment only on the affected systems until a fix "
        "is available."),
}
PANEL_KIND = {"corroborated_install_problem": "affected_configuration",
              "corroborated_issue": "affected_configuration",
              "regression": "deployment_caution",
              "vendor_confirmed_serious": "deployment_caution"}
# A vendor-confirmed reason may stand on a page with no user report, so its "other setups" line
# cannot point at reports listed below. Used only when every reason on the page is of that class and
# the page has no report (public_body).
OTHER_SETUPS_BY_CLASS = {
    "vendor_confirmed_serious": "Other setups: no problem is confirmed for them yet.",
}
PANEL_HEADING = {"affected_configuration": "Affected configuration",
                 "deployment_caution": "Deployment caution"}
# The Recommendations list under an AVOID verdict. ONE copy: the record writer stores it on a
# report-bearing page, and the verdict projection carries it for EVERY AVOID page, because the
# zero-count retraction removes the stored list from a page with no reports -- which is why the 24H2
# KB5079391 page (0 reports) printed none while 25H2 (1 report) did (GROWTH-3 review 2, LOW-4).
AVOID_RECOMMENDATIONS = (
    "If this device does not have this update yet, install the replacement update instead.",
    "Check Microsoft's known-issue and safeguard-hold list for the replacement before installing it.",
)
# The /updates/ feed card prints the page's line, but the card lists no reports under it, so a
# clause pointing at reports "listed below" is cut there (review 2, LOW-4). The patch page keeps
# it: its reports ARE listed below. `_includes/patch-feed-summary.html` applies these same pairs
# with Liquid's replace; test_growth3_verdict_policy pins the two over the corpus.
FEED_UNLISTED = (
    ("; the individual reports are listed below.", "."),
    ("; it is listed below.", "."),
    ("; they are listed below.", "."),
)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def is_monthly_security_update(record: dict[str, Any] | None) -> bool:
    """Microsoft's own classification, read from the stored release-health update type.

    "YYYY-MM B" is the monthly security release. Previews ("D") and out-of-band updates ("OOB")
    never inherit it: an OOB's security status is not in the stored data, and guessing it would be
    the inference the owner ruled out. Only Windows stores this field."""
    rec = record or {}
    if _text(rec.get("product_id")) != WINDOWS:
        return False
    match = _MONTHLY_SECURITY_RE.match(_text(rec.get("update_type")))
    return bool(match) and int(match.group(1)) >= 2000 and 1 <= int(match.group(2)) <= 12


def release_type_problem(record: dict[str, Any] | None) -> str:
    """Why a Windows record's stored release type cannot be read, or "".

    `decide` reads Microsoft's classification from `update_type` with one strict pattern, so a
    malformed value is never a SECURITY UPDATE: the page fails closed. Before GROWTH-3 review 2 the
    Liquid gate parsed the same field itself with `slice` and `plus: 0`, which reads "2026-3x B",
    "2026-+3 B" and "2026-1  B" as month numbers, and printed SECURITY UPDATE where Python did not
    (LOW-1). The gate now prints only the projection, so the page and `decide` agree; this names the
    value so QA reports it (`windows_update_type_malformed`, an ERROR under --publish-strict) instead
    of letting a security classification silently vanish.

    Only a value SHAPED like a release type (it opens "YYYY-" or ends " B" / " D" / " OOB") that
    fails the pattern is a problem. The writer's default "official-source" is not one, and an
    unrelated future word stays a fail-closed INSUFFICIENT DATA rather than a blocked lane."""
    rec = record or {}
    if _text(rec.get("product_id")) != WINDOWS:
        return ""
    raw = rec.get("update_type")
    if raw is None:
        return ""
    if not isinstance(raw, str):
        return f"update_type is a {type(raw).__name__} ({raw!r}), not a release-health type string"
    if not _RELEASE_TYPE_SHAPED_RE.search(_release_type_shape(raw)):
        return ""
    match = _RELEASE_TYPE_RE.match(raw.strip())
    if match and int(match.group(1)) >= 2000 and 1 <= int(match.group(2)) <= 12:
        return ""
    return (f"update_type {raw!r} is shaped like a release-health type but is not 'YYYY-MM B', "
            "'YYYY-MM D' or 'YYYY-MM OOB'")


def _release_context(record: dict[str, Any]) -> str:
    if is_monthly_security_update(record):
        return "It was a monthly security update."
    match = _PREVIEW_RE.match(_text(record.get("update_type")))
    if (_text(record.get("product_id")) == WINDOWS and match and int(match.group(1)) >= 2000
            and 1 <= int(match.group(2)) <= 12):
        return "It was an optional non-security preview update."
    return ""


def lifecycle_for(record: dict[str, Any] | None, lifecycle: Any = ()) -> dict[str, Any] | None:
    """The applicable official withdrawal for this exact record, or None. Exact identity only: same
    product, same KB, and this record's own OS build listed. Never inferred from a newer number."""
    rec = record or {}
    kb = _text(rec.get("target_kb"))
    build = _text(rec.get("target_build"))
    if not kb or not build:
        return None
    for entry in lifecycle or ():
        if (_text(entry.get("product_id")) == _text(rec.get("product_id"))
                and _text(entry.get("kb")) == kb
                and _text(entry.get("relationship")) == "withdrawn_for_new_installs"
                and build in [_text(b) for b in entry.get("builds") or []]):
            return dict(entry)
    return None


class Decision:
    """What `decide` returns. `reasons` are the SUPPORTED reason entries for the page, most
    cautionary first (file order breaks ties, exactly as the template iterates)."""

    __slots__ = ("verdict", "rule", "scope", "reasons", "lifecycle", "security")

    def __init__(self, verdict: str, rule: str, *, scope: str = "", reasons: tuple = (),
                 lifecycle: dict[str, Any] | None = None, security: bool = False) -> None:
        self.verdict = verdict
        self.rule = rule
        self.scope = scope
        self.reasons = reasons
        self.lifecycle = lifecycle
        self.security = security

    def __repr__(self) -> str:
        return f"Decision({self.verdict!r}, {self.rule!r}, scope={self.scope!r})"

    @property
    def panel_kind(self) -> str:
        if self.verdict == SECURITY_UPDATE and self.reasons:
            return PANEL_KIND.get(_text(self.reasons[0].get("reason_class")), "")
        return ""


def decide(record: dict[str, Any] | None, *, valid_reasons: Any = (), lifecycle: Any = ()) -> Decision:
    """THE decision for one patch. `valid_reasons` must already be the entries SUPPORTED by the
    page's counted rows (lib.verdict_reasons.valid_reasons_by_identity); `lifecycle` the validated
    lifecycle entries. No count, sentiment, theme, severity, maturity or clock is accepted."""
    rec = record or {}
    ordered = tuple(sorted((dict(e) for e in valid_reasons or ()),
                           key=lambda e: risk_rank(_text(e.get("verdict")))))
    security = is_monthly_security_update(rec)
    life = lifecycle_for(rec, lifecycle)
    if life:
        # Scoped like every non-default verdict: the withdrawal applies to INSTALLING the update,
        # not to a device that already has it (owner decision 2).
        return Decision(AVOID, "R1", scope=AVOID_SCOPE, lifecycle=life, reasons=ordered, security=security)
    if security:
        return Decision(SECURITY_UPDATE, "R2", reasons=ordered, security=True)
    if ordered:
        head = ordered[0]
        verdict = _text(head.get("verdict"))
        return Decision(verdict, "R3" if verdict == WAIT else "R4", scope=_text(head.get("scope")),
                        reasons=ordered)
    return Decision(INSUFFICIENT_DATA, "R5")


def _reports_phrase(count: int) -> str:
    return "one user report is" if count == 1 else f"{count} user reports are"


def public_body(decision: Decision, record: dict[str, Any] | None, report_count: int) -> str:
    """The verdict box's recommendation line. "" means: keep the zero-report page's existing line
    (a non-official page with no reports, which this policy does not reword)."""
    rec = record or {}
    n = max(int(report_count or 0), 0)
    if decision.verdict == AVOID and decision.lifecycle:
        parts = [f"Microsoft withdrew this update for new installations. Replacement: "
                 f"{_text(decision.lifecycle.get('replacement_kb'))}."]
        context = _release_context(rec)
        if context:
            parts.append(context)
        parts.append("This applies to installing it, not to devices that already installed it.")
        return " ".join(parts)
    if decision.verdict == SECURITY_UPDATE:
        if decision.reasons:
            return SECURITY_PANEL_LEAD[_text(decision.reasons[0].get("reason_class"))]
        if n == 0:
            return f"{SECURITY_LEAD} No user reports are matched to this update yet."
        if n == 1:
            return (f"{SECURITY_LEAD} One user report is matched to this update, and one report does "
                    "not show a pattern; it is listed below.")
        return (f"{SECURITY_LEAD} {n} user reports are matched to this update, and no problem in them "
                "is confirmed as reported independently by two or more users; they are listed below.")
    if decision.verdict in (WAIT, TEST_FIRST) and decision.reasons:
        head = decision.reasons[0]
        install = _text(head.get("reason_class")) == "corroborated_install_problem"
        parts = [_text(head.get("reason"))]
        if decision.verdict == TEST_FIRST:
            parts.append(TEST_FIRST_INSTALL if install else TEST_FIRST_TRY)
        for other in decision.reasons[1:]:
            parts.append(f"Also {_text(other.get('verdict'))} {_text(other.get('scope'))}: "
                         f"{_text(other.get('reason'))}")
        if not install:
            # The vendor line only where nothing else stands: no user-report reason and no report.
            # Beside reports (or an "Also ... users independently report" reason) the usual line is
            # the true one (G35-04 review 1, LOW-5).
            alone = n == 0 and len({_text(e.get("reason_class")) for e in decision.reasons}) == 1
            parts.append(OTHER_SETUPS_BY_CLASS.get(_text(head.get("reason_class")), OTHER_SETUPS) if alone
                         else OTHER_SETUPS)
        return " ".join(parts)
    if n == 0:
        return ""
    if n == 1:
        return ("No verdict yet: one user report is matched to this exact update, and one report does "
                "not show a pattern. If it matches your setup, test before relying on this update.")
    return (f"No verdict yet: {n} user reports are matched to this exact update, but no problem in "
            "them is confirmed as reported independently by two or more users. If one matches your "
            "setup, test before relying on this update.")


def panel_text(decision: Decision) -> str:
    """The security page's affected-configuration / deployment-caution box, or ""."""
    if not decision.panel_kind:
        return ""
    head = decision.reasons[0]
    scope = _text(head.get("scope"))
    return f"{scope[:1].upper()}{scope[1:]}: {_text(head.get('reason'))}"


def recommendations(decision: Decision) -> list[str]:
    """The Recommendations list an OFFICIAL verdict carries on every page it decides, or [].

    Only AVOID has one: the stored `practical_recommendations` exist only where a writer ran (a page
    with reports), so a zero-report withdrawal page would otherwise tell a reader to avoid the update
    without telling them what to install instead (review 2, LOW-4)."""
    if decision.verdict == AVOID and decision.lifecycle:
        return list(AVOID_RECOMMENDATIONS)
    return []


def feed_body(body: str) -> str:
    """The page's line as the /updates/ feed card prints it: no pointer to reports "listed below",
    because nothing is listed below a card (review 2, LOW-4)."""
    text = str(body or "")
    for old, new in FEED_UNLISTED:
        text = text.replace(old, new)
    return text


def verdict_phrase(decision: Decision) -> str:
    """The verdict as every surface prints it: the word and its scope, never one without the other.

    "WAIT if you use macOS 27.2", "TEST FIRST when installing it", "AVOID for new installations";
    an unscoped verdict (SECURITY UPDATE, INSUFFICIENT DATA) is the word alone. GROWTH-3 review 1
    (D1) found three surfaces printing the word without its scope -- a WAIT that applies to one
    setup read as a WAIT for everyone."""
    return f"{decision.verdict} {decision.scope}".strip()


_NO_VERDICT_LEAD = "No verdict yet: "


def summary_line(decision: Decision, record: dict[str, Any] | None, report_count: int,
                 fallback: str = "", identity: str = "") -> str:
    """The stored `update_consensus_summary`, which the /updates/ feed card prints: the verdict and
    its scope FIRST, then the exact patch it is about, then the page's own recommendation line.

    "WAIT if you use macOS 27.2: OBS Studio 32.2.2. A user reports, and OBS confirms, ..." -- not
    "WAIT: OBS Studio 32.2.2 has 53 user reports found.", where an unscoped verdict beside a count
    reads as "53 reports, so wait", the inference the policy forbids (counts never decide). The line
    states the count where it is the point (no verdict yet, a security update) and the card prints
    the confirmed count beside it. `identity` names the exact patch (a Windows build, not just its
    train: 28 records share "25H2"). `fallback` is used only when the policy has no line (a
    zero-report page, which no writer stores a summary for). The feed prints this string while its
    lead equals the page's verdict and scope, and composes the same lead from the gate when it does
    not, so the feed never shows a verdict the page does not. The line is the FEED's form of the
    page's line (`feed_body`): a feed card lists no reports, so it never says they are listed below."""
    body = feed_body(public_body(decision, record, report_count))
    if body.startswith(_NO_VERDICT_LEAD):
        body = body[len(_NO_VERDICT_LEAD):]
        body = body[:1].upper() + body[1:]
    text = body or fallback
    if identity and body:
        text = f"{identity.strip().rstrip('.')}. {body}"
    return f"{verdict_phrase(decision)}: {text}".strip()


def decision_label(product_id: str, version: str, consensus_label: str = "", count: int = 0,
                   *, record: dict[str, Any] | None = None, valid_reasons: Any = (),
                   lifecycle: Any = ()) -> str:
    """The canonical verdict word -- `decide(...).verdict`, kept under its historical name.

    `consensus_label` and `count` are ACCEPTED AND IGNORED. They are the two inputs the old policy
    read -- a negative sentiment made OBS, Acrobat and every branchless product WAIT, and the
    product branches made every DaVinci, Windows and Premiere record WAIT with any count at all
    (233 of 235 report-bearing pages on 2026-11-06). The owner's rule is that neither decides a
    verdict; the parameters stay only so existing callers keep their shape, and G3-D3/G3-D4 prove
    that changing them changes nothing."""
    rec = dict(record or {})
    rec.setdefault("product_id", product_id)
    rec.setdefault("update_version", version)
    return decide(rec, valid_reasons=valid_reasons, lifecycle=lifecycle).verdict
