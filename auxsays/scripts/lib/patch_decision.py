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

# Two leaves of `lib`, standard library only: the report-URL identity every count and live check uses, and
# the vocabularies a row must carry to be published. Neither imports the collector package.
from .evidence_classification import VALID_SENTIMENTS, VALID_SEVERITIES
from .source_segments import report_url_key

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
    so a vendor title that merely begins with a decision word is not mistaken for one. The
    volume-based precaution's lead, "WAIT Volume-based precaution:" (G87), is WAIT too -- that exact
    label and no other.
    """
    body = str(text or "")
    if body.startswith(VOLUME_LEAD + ":"):
        return WAIT
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
#   R3V WAIT             a VOLUME-BASED PRECAUTION (G87, below): 30 or more accepted patch-specific
#                        reports with 30 or more unique report URLs, on a product whose projections the
#                        lanes maintain. It outranks R3-R5 whenever it is at least as cautious; the
#                        reviewed entries R3/R4 would have printed stay visible beneath it
#   R3  WAIT             a reviewed `regression` reason entry that is supported by counted rows
#   R4  TEST FIRST       a reviewed corroboration reason entry that is supported by counted rows
#   R5  INSUFFICIENT DATA, the reported problems disclosed (reports, no supported reason)
#   R6  INSUFFICIENT DATA (no reports, no official fact)
#
# WHAT IS NEVER AN INPUT. Sentiment (`update_consensus_label`), `issue_theme`, `severity`, maturity,
# collection health (`evidence_method_health.yml`, the monitoring notice), `update_status` and the
# clock. `decide` does not accept them, so no negative tone can make a WAIT (G3-D3), no theme-derived
# severity can (G3-D12), no collector outage can add or remove one, and nothing becomes SAFE ENOUGH
# because time passed or complaints stopped (G3-D2). SAFE ENOUGH, OFFICIAL ONLY and MANUAL WATCH stay
# canonical (recognised, ranked) but this policy produces none of them: no positive evidence is
# collected.
#
# THE ONE COUNT THAT IS AN INPUT (G87, owner amendment of 2026-11-21 to the 2026-11-06 policy). Until
# G87 no count could make a WAIT (G3-D4). The owner amended that for one rule: a page whose canonical
# counted population reaches VOLUME_MIN_REPORTS accepted patch-specific reports with VOLUME_MIN_UNIQUE_URLS
# unique report URLs gets a WAIT labelled "Volume-based precaution" (reason high_report_volume). It is a
# provisional policy constant, not a statistical claim: it says the volume of accepted reports warrants
# caution, never that one defect is confirmed or how often installations fail. The count is read ONLY
# from `counted_rows`, the page's population as lib.report_counts.counted_evidence_rows returns it --
# the same rows every public count uses -- never from a record's stored update_report_count, which can
# lag. Every other count rule still stands: the live rung (maturity.LIVE_MIN_ACCEPTED_REPORTS, 33) and
# the evidence-strength ladder are untouched, and a count below the volume minimum still decides nothing.
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

# ---------------------------------------------------------------------------------------------
# G87: THE VOLUME-BASED PRECAUTION (owner-approved 2026-11-21; provisional policy constant, not a
# statistical claim). A WAIT with reason code high_report_volume, printed with the label below in the
# place every surface prints a verdict's scope. Eligibility, ALL required (`volume_problems` names each
# failure):
#   * the product is one whose projections the lanes rebuild and retract (VOLUME_PRODUCTS, the literal copy of
#     report_counts.CONSENSUS_PROMOTION_PRODUCTS pinned to it by test: ten products today);
#   * at least VOLUME_MIN_REPORTS counted rows in the page's canonical population (`counted_rows`);
#   * at least VOLUME_MIN_UNIQUE_URLS distinct report URLs among them (source_segments.report_url_key, the
#     identity every count and the live check use), and no report cited twice;
#   * every row publishable: the live gate's condition (e) per row (`publishable_row`, which
#     live_eligibility uses too), so the population can be printed under the publish-strict gate;
#   * the record is not officially identified as a security update outside Windows (`security_identified`).
# NOT an input: collection health. A blocked or stale collector changes the monitoring notice only; the
# accepted rows it already collected still count (GPT C3). Also not an input: maturity (live or pilot),
# sentiment values, themes, severity values and the clock. Recomputed from scratch every build; no state.
#
# PRECEDENCE. An official withdrawal (R1 AVOID) and Microsoft's monthly security classification (R2
# SECURITY UPDATE) always win, and so does an official security identification outside Windows (the
# volume rule does not apply there). Otherwise the volume WAIT is the PRIMARY verdict whenever it is at
# least as cautious as what the reviewed entries would print (RISK_ORDER): it replaces INSUFFICIENT DATA,
# supersedes a reviewed TEST FIRST, and stands beside an equally cautious reviewed WAIT. Those reviewed
# entries stay in `reasons` and are printed beneath it with their own scope and wording ("Also WAIT if you
# use macOS 27.2: ..."), never rewritten as a universal regression.
# ---------------------------------------------------------------------------------------------
VOLUME_REASON_CODE = "high_report_volume"
VOLUME_LABEL = "Volume-based precaution"
VOLUME_RULE = "R3V"
VOLUME_MIN_REPORTS = 30
VOLUME_MIN_UNIQUE_URLS = 30
# report_counts.CONSENSUS_PROMOTION_PRODUCTS, as literals (the module comment above DAVINCI says why);
# test_volume_precaution pins the two sets equal.
VOLUME_PRODUCTS = frozenset({"microsoft-powerpoint", "microsoft-windows-11", "obs-studio", "adobe-acrobat-pro",
                             "adobe-acrobat-reader", "microsoft-teams", "adobe-premiere-pro", "comfyui",
                             "nvidia-geforce-game-ready", "nvidia-studio-driver"})
# The volume WAIT's line, ONE copy. "{n}" is the canonical count; the reviewed entries follow it as "Also ...".
VOLUME_BODY = ("{n} accepted patch-specific problem reports. "
               "AUXSAYS recommends delaying this version unless you need its changes. "
               "AUXSAYS recommends waiting because of the volume of accepted problem reports, not because one "
               "widespread defect has been confirmed. "
               "These reports do not establish how likely the update is to cause problems on your system. "
               "Next step: If your current version works, consider keeping it while you review known issues and "
               "available alternatives. A newer version is not necessarily safer.")
VOLUME_LEAD = f"{WAIT} {VOLUME_LABEL}"
# The structured fields that already mark a record as an officially identified security update outside
# Windows (the same four _includes/patch-decision.html reads for its security-sensitive wording).
SECURITY_FLAG_FIELDS = ("security_sensitive", "update_security_sensitive")
SECURITY_SOURCE_FIELDS = ("official_patch_notes_source_type", "official_source_type")
SECURITY_SOURCE_TYPE = "security_advisory"


def publishable_row(row: dict[str, Any] | None) -> bool:
    """May this counted row be printed as a citation? The live gate's condition (e), per row, and the one copy
    of it (lib/live_eligibility delegates here): an http(s) URL, a source date that did not fail, and a
    sentiment and severity inside the writer's vocabularies. Reads whether a value is IN a vocabulary, never
    which one it is, so no sentiment or severity can select a verdict."""
    r = row or {}
    url = str(r.get("source_url") or "").strip().lower()
    return (url.startswith(("http://", "https://"))
            and r.get("source_date_pass") is not False
            and str(r.get("sentiment") or "").strip().lower() in VALID_SENTIMENTS
            and (str(r.get("severity") or "").strip().lower() or "low") in VALID_SEVERITIES)


def security_identified(record: dict[str, Any] | None) -> bool:
    """Is this record officially identified as a security update by the structured fields the site already
    stores (a security flag, or an official source that is a security advisory)? Windows' monthly releases
    are decided by R2 instead; this covers every other product, where the volume WAIT must never override one."""
    rec = record or {}
    return (any(rec.get(field) is True for field in SECURITY_FLAG_FIELDS)
            or any(_text(rec.get(field)) == SECURITY_SOURCE_TYPE for field in SECURITY_SOURCE_FIELDS))


def volume_problems(record: dict[str, Any] | None, counted_rows: Any = ()) -> list[str]:
    """Why this page does NOT get the volume-based precaution; [] when it does. Every condition is evaluated,
    so a diagnostic names all of them."""
    rec = record or {}
    rows = [r for r in (counted_rows or ()) if isinstance(r, dict)]
    problems: list[str] = []
    if _text(rec.get("product_id")) not in VOLUME_PRODUCTS:
        problems.append("not_promotion_product")
    if len(rows) < VOLUME_MIN_REPORTS:
        problems.append(f"below_volume_reports:{len(rows)}")
    keys = [report_url_key(str(r.get("source_url") or "")) for r in rows]
    unique = {k for k in keys if k}
    if len(unique) < VOLUME_MIN_UNIQUE_URLS:
        problems.append(f"below_volume_unique_urls:{len(unique)}")
    if len(set(keys)) != len(keys):
        problems.append("duplicate_citation_urls")
    unpublishable = sum(1 for r in rows if not publishable_row(r))
    if unpublishable:
        problems.append(f"unpublishable_rows:{unpublishable}")
    if security_identified(rec):
        problems.append("officially_identified_security_update")
    return problems

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


def _lifecycle_order(entry: dict[str, Any]) -> tuple[str, str, str]:
    """Earliest verified first, then id, then the entry's whole content: a total order that file
    order never enters."""
    return (_text(entry.get("verified_at")), _text(entry.get("id")),
            repr(sorted((str(k), repr(v)) for k, v in entry.items())))


def lifecycle_for(record: dict[str, Any] | None, lifecycle: Any = ()) -> dict[str, Any] | None:
    """The applicable official withdrawal for this exact record, or None. Exact identity only: same
    product, same KB, and this record's own OS build listed. Never inferred from a newer number.

    EVERY MATCHING ENTRY IS READ (G94, AUX-131). The first match in file order used to win, so with a
    second entry for the same release (a later official statement about the same update) reordering
    the file changed the replacement KB and the source the page printed. Now the page rests on the
    EARLIEST verified matching entry: a later entry never replaces an earlier one, file order decides
    nothing, and the release stays withdrawn while any entry for it stands."""
    rec = record or {}
    kb = _text(rec.get("target_kb"))
    build = _text(rec.get("target_build"))
    if not kb or not build:
        return None
    matches = [entry for entry in lifecycle or ()
               if (_text(entry.get("product_id")) == _text(rec.get("product_id"))
                   and _text(entry.get("kb")) == kb
                   and _text(entry.get("relationship")) == "withdrawn_for_new_installs"
                   and build in [_text(b) for b in entry.get("builds") or []])]
    return dict(min(matches, key=_lifecycle_order)) if matches else None


class Decision:
    """What `decide` returns. `reasons` are the SUPPORTED reason entries for the page, most
    cautionary first (file order breaks ties, exactly as the template iterates). A volume-based WAIT
    (G87) carries `reason_code` high_report_volume, its `label`, and `reports`, the canonical count it
    rests on; its scope is empty (it applies to every setup), and its `reasons` are the reviewed entries
    it stands above, still shown."""

    __slots__ = ("verdict", "rule", "scope", "reasons", "lifecycle", "security", "reason_code", "label",
                 "reports")

    def __init__(self, verdict: str, rule: str, *, scope: str = "", reasons: tuple = (),
                 lifecycle: dict[str, Any] | None = None, security: bool = False, reason_code: str = "",
                 label: str = "", reports: int = 0) -> None:
        self.verdict = verdict
        self.rule = rule
        self.scope = scope
        self.reasons = reasons
        self.lifecycle = lifecycle
        self.security = security
        self.reason_code = reason_code
        self.label = label
        self.reports = reports

    def __repr__(self) -> str:
        return f"Decision({self.verdict!r}, {self.rule!r}, scope={self.scope!r})"

    @property
    def panel_kind(self) -> str:
        if self.verdict == SECURITY_UPDATE and self.reasons:
            return PANEL_KIND.get(_text(self.reasons[0].get("reason_class")), "")
        return ""

    @property
    def volume(self) -> bool:
        """Is this the volume-based precaution (a WAIT with reason code high_report_volume)?"""
        return self.verdict == WAIT and self.reason_code == VOLUME_REASON_CODE

    @property
    def qualifier(self) -> str:
        """What every surface prints beside the verdict word: the setup scope, or -- for the volume-based
        precaution, which has none -- its label."""
        return self.scope or (self.label if self.volume else "")


def decide(record: dict[str, Any] | None, *, valid_reasons: Any = (), lifecycle: Any = (),
           counted_rows: Any = ()) -> Decision:
    """THE decision for one patch. `valid_reasons` must already be the entries SUPPORTED by the
    page's counted rows (lib.verdict_reasons.valid_reasons_by_identity); `lifecycle` the validated
    lifecycle entries; `counted_rows` the page's canonical counted population
    (lib.report_counts.counted_evidence_rows for this identity), read ONLY by the volume rule. No stored
    count, sentiment, theme, severity, maturity, collection health or clock is accepted. A caller that
    passes no rows gets no volume-based WAIT: it fails closed to the reviewed outcome."""
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
        reviewed = Decision(verdict, "R3" if verdict == WAIT else "R4", scope=_text(head.get("scope")),
                            reasons=ordered)
    else:
        reviewed = Decision(INSUFFICIENT_DATA, "R5")
    rows = [r for r in (counted_rows or ()) if isinstance(r, dict)]
    if risk_rank(WAIT) <= risk_rank(reviewed.verdict) and not volume_problems(rec, rows):
        return Decision(WAIT, VOLUME_RULE, reasons=ordered, reason_code=VOLUME_REASON_CODE,
                        label=VOLUME_LABEL, reports=len(rows))
    return reviewed


def _reports_phrase(count: int) -> str:
    return "one user report is" if count == 1 else f"{count} user reports are"


def public_body(decision: Decision, record: dict[str, Any] | None, report_count: int) -> str:
    """The verdict box's recommendation line. "" means: keep the zero-report page's existing line
    (a non-official page with no reports, which this policy does not reword)."""
    rec = record or {}
    n = max(int(report_count or 0), 0)
    if decision.volume:
        # The canonical count the decision rests on, never the caller's (a stored count can lag). The
        # reviewed entries it stands above follow with their own verdict, scope and wording.
        parts = [VOLUME_BODY.format(n=decision.reports)]
        for other in decision.reasons:
            parts.append(f"Also {_text(other.get('verdict'))} {_text(other.get('scope'))}: "
                         f"{_text(other.get('reason'))}")
        return " ".join(parts)
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


def official_source(decision: Decision) -> dict[str, str]:
    """The official statement an AVOID rests on, for the patch page to link (G66), else empty strings.

    A plain deep link to the article's own URL -- the one use of a Microsoft support article the
    2026-11-10 source assessment rated PERMITTED (the link lands on the originating page) -- with an
    AUXSAYS label and the date the statement was verified. Never the article's text. It decides
    nothing: the verdict is chosen above and is the same with or without it."""
    empty = {"url": "", "label": "", "checked": ""}
    if decision.verdict != AVOID or not decision.lifecycle:
        return empty
    url = _text(decision.lifecycle.get("official_url"))
    kb = _text(decision.lifecycle.get("kb"))
    if not url.startswith("https://") or not kb:
        return empty
    return {"url": url, "label": f"Microsoft support article for {kb}",
            "checked": _text(decision.lifecycle.get("verified_at"))}


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
    setup read as a WAIT for everyone. The volume-based precaution (G87) applies to every setup and
    has no scope; its label stands in that place: "WAIT Volume-based precaution"."""
    return f"{decision.verdict} {decision.qualifier}".strip()


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
                   lifecycle: Any = (), counted_rows: Any = ()) -> str:
    """The canonical verdict word -- `decide(...).verdict`, kept under its historical name.

    `consensus_label` and `count` are ACCEPTED AND IGNORED. They are the two inputs the old policy
    read -- a negative sentiment made OBS, Acrobat and every branchless product WAIT, and the
    product branches made every DaVinci, Windows and Premiere record WAIT with any count at all
    (233 of 235 report-bearing pages on 2026-11-06). The owner's rule is that neither decides a
    verdict; the parameters stay only so existing callers keep their shape, and G3-D3/G3-D4 prove
    that changing them changes nothing. The volume-based precaution (G87) reads the page's canonical
    population from `counted_rows`, never `count` (a caller's number, often a stale stored one)."""
    rec = dict(record or {})
    rec.setdefault("product_id", product_id)
    rec.setdefault("update_version", version)
    return decide(rec, valid_reasons=valid_reasons, lifecycle=lifecycle, counted_rows=counted_rows).verdict
