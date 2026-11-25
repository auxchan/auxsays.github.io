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
INSUFFICIENT DATA -- and AVOID is reachable again, but only from a verified lifecycle entry.
The history above is kept because it explains why one function, not three, decides.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# Three leaves of `lib`, standard library only: the report-URL identity every count and live check uses, the
# vocabularies a row must carry to be published, and the stored duplicate-group fact of a row (G68). None
# imports the collector package.
from . import assessment_output, evidence_facts
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
#                        file; one verified entry today, KB5079391)
#   R2  SECURITY UPDATE  Microsoft's own classification of the exact update as a monthly security
#                        release (release-health update type "YYYY-MM B", stored on the record).
#                        User reports never override it; reviewed reasons only add a warning panel
#   R3V WAIT             a VOLUME-BASED PRECAUTION (G87, below): 30 or more accepted patch-specific
#                        reports with 30 or more unique report URLs, on a product whose projections the
#                        lanes maintain. Since AUX-134 `assess` runs at 30 counted reports and PUBLISHES the
#                        basis of this WAIT. The WAIT itself is unchanged: 30 counted separate reports on
#                        such a product with no limiting fact still give it on the count alone (the
#                        owner-approved volume-based WAIT of 2026-11-22; whether that stays is owner
#                        decision D1, pending). It outranks R3-R5 whenever it is at least as cautious; the
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
#   * at least VOLUME_MIN_INDEPENDENT SEPARATE reports (`independent_reports`, AUX-134): rows that carry one
#     stored excerpt are one reporter, a row with an EMPTY stored excerpt stands on its report link, and a row
#     whose stored fact is unavailable fails the page closed (QA names that page: `facts_withheld_volume`);
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
# AUX-134: the same number, read as SEPARATE reports (`independent_reports`): rows that carry one stored
# excerpt are one reporter posting twice, exactly as the reviewed reasons' distinct-reporter rule reads them.
VOLUME_MIN_INDEPENDENT = 30
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
    independent, unavailable = independent_reports(rows)
    if unavailable:
        problems.append(f"report_facts_unavailable:{unavailable}")
    elif independent < VOLUME_MIN_INDEPENDENT:
        problems.append(f"below_independent_reports:{independent}")
    if security_identified(rec):
        problems.append("officially_identified_security_update")
    return problems


def independent_reports(counted_rows: Any = ()) -> tuple[int, int]:
    """(independent, unavailable): how many of the page's counted rows stand as SEPARATE reports, and how many
    rows could not be compared at all.

    The distinct-reporter rule the reviewed reasons already use (lib.verdict_reasons.support_problems), applied
    to the whole page: a distinct report URL each, and rows that carry the SAME stored excerpt are one reporter
    posting twice. The excerpt comparison reads the structured fact written with the row
    (lib.evidence_facts.duplicate_group_key), never the stored text, and never rebuilds it: a row whose fact is
    missing, malformed, of an unknown version or computed under another rule is `unavailable`, and a page with
    any such row has not shown that its reports are separate (fail closed). Thirty copies of one complaint are
    not thirty reports; this says nothing about whether separate reports describe one problem.

    AN EMPTY STORED EXCERPT PROVES NOTHING EITHER WAY (review round 1, F3). The excerpt fact can only show
    DUPLICATION: two rows with the same text are one reporter. A row whose stored excerpt is empty has no text
    to compare, so it is neither merged with another row (two reports without stored text are not shown to be
    one reporter) nor dropped: it stands on its own report link, as every row did before this condition
    existed. ONE rule for every mix: separate reports = distinct non-empty excerpts + rows with an empty
    excerpt, never more than the distinct report links. (The first version counted the empty rows only when
    EVERY row was empty: sixty links of which fifty-nine had no stored text were read as one report.)"""
    rows = [r for r in (counted_rows or ()) if isinstance(r, dict)]
    urls = {k for k in (report_url_key(str(r.get("source_url") or "")) for r in rows) if k}
    groups: set[str] = set()
    uncompared = unavailable = 0
    for r in rows:
        try:
            key = evidence_facts.duplicate_group_key(r)
        except evidence_facts.FactUnavailable:
            unavailable += 1
            continue
        if key is None:
            uncompared += 1
        else:
            groups.add(key)
    return min(len(urls), len(groups) + uncompared), unavailable


def facts_withheld_volume(decision: "Decision | None") -> int:
    """How many counted rows without a readable stored fact are the ONLY thing that keeps the volume-based
    WAIT off this page; 0 when it is not withheld, or not for that reason alone (review round 1, F4).

    `independent_reports` fails a page closed on one such row, so a facts rule change that has not been
    migrated (migrate_evidence_facts.py --write) takes the volume WAIT off every page at once. The page says so
    in its limiting evidence; this lets QA say it too, under its own code, instead of leaving it to be inferred
    from a store-wide `evidence_facts_*` warning. Never true where an official fact decides the page."""
    found = getattr(decision, "assessment", None)
    if found is None or found.basis not in (BASIS_REVIEWED, BASIS_LIMITED) or len(found.limits) != 1:
        return 0
    code, _, number = found.limits[0].partition(":")
    return int(number) if code == "report_facts_unavailable" and number.isdigit() else 0


def vendor_known_issue(record: dict[str, Any] | None) -> bool:
    """Whether the record's vendor has documented a known issue for THIS exact release, read exactly as the
    writers store it (G85 consumer contract, AUX-125): `official_notes_known_issue: declared` (official release
    notes) or `official_known_issues_present: true` (Windows Release Health). An absent field never means "no
    known issue"; it only means none is declared. The one copy: lib.evidence_overview delegates here."""
    rec = record or {}
    return (_text(rec.get("official_notes_known_issue")) == "declared"
            or rec.get("official_known_issues_present") is True)

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
    EARLIEST verified matching entry (`verified_at` first; `id` only breaks a tie): an entry verified
    later never replaces one verified earlier, file order decides nothing, and the release stays
    withdrawn while any entry for it stands. "Earlier" is by `verified_at`, not by when an entry was
    added: a newly added entry with an earlier `verified_at` does take over the page's details."""
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


# ---------------------------------------------------------------------------------------------
# AUX-134: THE PROVISIONAL CONTEXTUAL RISK ASSESSMENT (owner order of 2026-11-23).
#
# G87 gave a page WAIT as soon as it held 30 accepted reports on a maintained product. The owner's order
# changes what the number IS: "a trigger to assess, not an automatic WAIT/AVOID verdict or statistically
# representative estimate of installer failure rate". So at ASSESSMENT_MIN_REPORTS counted reports `assess`
# RUNS, for every product and whatever the verdict turns out to be, and `decide` publishes the verdict it
# reached together with WHY (`basis`) or, when the evidence cannot support a recommendation, exactly which
# stored fact limits it (`limits`). It is the same authority and the same eight verdicts; no second rubric.
#
# WHAT IT READS. Only stored facts something already validates:
#   * the page's canonical counted population: how many reports, on how many separate report URLs, and how
#     many stand as separate reports (`independent_reports`, the G68 duplicate-group fact; NEW as a
#     condition: thirty rows carrying one stored excerpt are one reporter, not thirty reports);
#   * every other G87 condition, unchanged (`volume_problems`): a maintained product, no report cited twice,
#     every row publishable, no official security identification;
#   * the SUPPORTED reviewed reason entries (a confirmed regression, a corroborated problem) and the official
#     facts that outrank everything (a withdrawal, Microsoft's monthly security classification);
#   * the vendor's own known-issue declaration for this exact release (G85's stored field).
#
# WHAT IT DOES NOT READ, because no stored field is validated for it: severity and data loss (the stored
# `severity` is derived from the issue label), recurring problem themes (the stored labels are withheld on
# four products as wrong, lib/evidence_overview), affected platforms beyond a reviewed scope, and positive
# outcomes (none are collected; silence is not positive evidence). The published assessment says "Not
# established" for each of them instead of guessing. Collection health, sentiment, maturity and the clock are
# still not inputs: the monitoring status is its own axis on the page.
#
# THE RESULT. An official fact decides and the assessment says so. Otherwise, with no limit, the result is the
# risk-management WAIT the owner approved on 2026-11-21 (unchanged row: reason code high_report_volume, label
# "Volume-based precaution"), and its basis names what stands behind it: a reviewed problem (a supported WAIT
# or TEST FIRST entry, which stays printed beneath the WAIT) as well as the
# volume, a vendor-documented known issue as well as the volume, or the volume alone with no cause
# confirmed. With any limit the count adds nothing: the reviewed outcome stands, or the page stays
# INSUFFICIENT DATA and names the limit. No denominator, percentage, rate, severity or theme is produced.
#
# WHAT THIS IS NOT (review round 1, F1). It is an EXPLANATION layer over the unchanged rule, not the contextual
# weighing the order describes. Thirty counted separate reports on a maintained product with no limiting fact
# still give WAIT on the count alone: no assessed dimension can move the verdict word (a reviewed finding or a
# vendor known issue changes only the `basis` label), and the one new condition can only REMOVE the WAIT.
# Whether the volume-based WAIT stays where no cause is confirmed is owner decision D1 (pending); whether a
# product outside VOLUME_PRODUCTS gets it is owner decision D2 (pending). AUX-137 (the block below): where a
# CURRENT stored provisional assessment of the page exists, it is weighed in; without one, nothing here changes.
# ---------------------------------------------------------------------------------------------
ASSESSMENT_RULE = "contextual-assessment-1"
# The rule name of an assessment that weighed a CURRENT stored provisional assessment (lib.assessment_output).
ASSESSMENT_RULE_WEIGHED = "contextual-assessment-3"
ASSESSMENT_MIN_REPORTS = VOLUME_MIN_REPORTS
BASIS_OFFICIAL_WITHDRAWAL = "official_withdrawal"
BASIS_OFFICIAL_SECURITY = "official_security_classification"
BASIS_REVIEWED_AND_VOLUME = "reviewed_problem_and_report_volume"
BASIS_VENDOR_ISSUE_AND_VOLUME = "vendor_known_issue_and_report_volume"
BASIS_VOLUME = "accepted_report_volume"
BASIS_REVIEWED = "reviewed_finding"
BASIS_LIMITED = "limited_evidence"
# The bases whose verdict is the volume-based WAIT. Every other basis leaves the count out of the verdict.
VOLUME_BASES = frozenset({BASIS_REVIEWED_AND_VOLUME, BASIS_VENDOR_ISSUE_AND_VOLUME, BASIS_VOLUME})
# AUX-137 (owner ruling of 2026-11-24; output-only design approved 2026-11-25): N >= ASSESSMENT_MIN_REPORTS accepted
# reports TRIGGER A PROVISIONAL RISK ASSESSMENT for every product, and maintainer decisions are supplementary
# evidence, never a prerequisite. The weighing of the page's reports is computed by a separate scheduled step and
# stored in `_data/provisional_assessments.yml`; `lib.assessment_output.weighing_for` (called from ONE place:
# `assess`) returns it only while it is CURRENT for the page's inputs, else None. A stored weighing may support a
# recommendation of its own (`basis` in PROVISIONAL_BASES); a reviewed finding at least as cautious keeps its place,
# and official facts still outrank everything. Without a current stored weighing the page is decided exactly as
# before (the count-based assessment) and its Status line says the weighing is pending (ASSESS_PENDING).
BASIS_PROVISIONAL_MAINTAINER = assessment_output.BASIS_MAINTAINER_REGRESSION
BASIS_PROVISIONAL_REGRESSION = assessment_output.BASIS_SEVERE_REGRESSION
BASIS_PROVISIONAL_TEST_FIRST = assessment_output.BASIS_TEST_FIRST
BASIS_REVIEWED_WEIGHED = "reviewed_finding_with_provisional_assessment"
PROVISIONAL_BASES = frozenset(assessment_output.BASES)
PROVISIONAL_RULES = {WAIT: "R3P", TEST_FIRST: "R4P"}
# A limit that only says which products the VOLUME rule covers. It does not stop the provisional assessment, which
# applies to every product; every other limit says the page has not shown thirty separate publishable reports.
SCOPE_ONLY_LIMITS = frozenset({"not_promotion_product"})


class Assessment:
    """What `assess` found for one page that reached the trigger. `result` and `scope` are the verdict the
    page prints; `basis` says why; `limits` are the `volume_problems` codes that kept the count out of the
    verdict (empty when it counts, and never the reason on an official verdict). `confirmed` and
    `corroborated` count the supported reviewed WAIT and TEST FIRST entries on the page."""

    __slots__ = ("rule", "reports", "unique_urls", "independent", "limits", "result", "scope", "basis",
                 "confirmed", "corroborated", "vendor_known_issue", "weighing", "corroborated_new", "record_facts")

    def __init__(self, *, reports: int, unique_urls: int, independent: int, limits: tuple, result: str,
                 scope: str, basis: str, confirmed: int, corroborated: int, vendor_known_issue: bool,
                 weighing: Any = None, corroborated_new: int = 0, record_facts: Any = None) -> None:
        self.rule = ASSESSMENT_RULE_WEIGHED if weighing is not None else ASSESSMENT_RULE
        self.reports = reports
        self.unique_urls = unique_urls
        self.independent = independent
        self.limits = limits
        self.result = result
        self.scope = scope
        self.basis = basis
        self.confirmed = confirmed
        self.corroborated = corroborated
        self.vendor_known_issue = vendor_known_issue
        # AUX-137: the CURRENT stored provisional assessment of the page (lib.assessment_output), or None.
        self.weighing = weighing
        # What the stored tracker records of the page's reports establish (lib.assessment_facts.Weighing), read by
        # QA whether or not a stored weighing is current.
        self.record_facts = record_facts
        # Review 2, R2-1: how many supported TEST FIRST entries are stored as new in this version.
        self.corroborated_new = corroborated_new

    def __repr__(self) -> str:
        return f"Assessment({self.result!r}, {self.basis!r}, limits={self.limits!r})"


def assess(record: dict[str, Any] | None, reviewed_reasons: Any = (), counted_rows: Any = (), *,
           withdrawn: bool = False, security: bool = False, source_facts: Any = None) -> Assessment | None:
    """The provisional contextual risk assessment for one page, or None below the trigger.

    `reviewed_reasons` are the page's SUPPORTED reason entries, most cautionary first (as `decide` orders
    them); `withdrawn` and `security` are the two official facts `decide` has already established. Called by
    `decide` and by nothing else: the verdict a page prints and the assessment it prints are one result."""
    rec = record or {}
    rows = [r for r in (counted_rows or ()) if isinstance(r, dict)]
    if len(rows) < ASSESSMENT_MIN_REPORTS:
        return None
    reasons = [e for e in (reviewed_reasons or ()) if isinstance(e, dict)]
    limits = tuple(volume_problems(rec, rows))
    confirmed = sum(1 for e in reasons if _text(e.get("verdict")) == WAIT)
    corroborated = sum(1 for e in reasons if _text(e.get("verdict")) == TEST_FIRST)
    known_issue = vendor_known_issue(rec)
    reviewed_verdict = _text(reasons[0].get("verdict")) if reasons else INSUFFICIENT_DATA
    # THE ONE CALL for the stored provisional assessment (AUX-137): the page's weighing when a CURRENT one is
    # stored for exactly these inputs, else None. `source_facts` None means the tracked facts file. No clock.
    weighing = assessment_output.weighing_for(rec, rows, source_facts=source_facts)
    structural = tuple(code for code in limits if code.partition(":")[0] not in SCOPE_ONLY_LIMITS)
    if withdrawn:
        result, scope, basis = AVOID, AVOID_SCOPE, BASIS_OFFICIAL_WITHDRAWAL
    elif security:
        result, scope, basis = SECURITY_UPDATE, "", BASIS_OFFICIAL_SECURITY
    elif weighing is not None and not structural and weighing.verdict \
            and (not (weighing.retain and not limits) or weighing.page_wide):
        # The stored weighing supports a recommendation of its own. It takes the page only when it is MORE
        # cautious than the reviewed finding; an equally cautious reviewed finding is the more specific statement
        # and keeps its place. A scoped WAIT on a page whose REST keeps the volume-based WAIT (`retain`) does not
        # narrow the page: where the product has the volume rule, the page-wide volume WAIT below covers it and its
        # limiting evidence names why. A stored WAIT for the whole page (`page_wide`) is as cautious as the volume
        # WAIT for every setup and states its cause, so it takes the page either way.
        if risk_rank(weighing.verdict) < risk_rank(reviewed_verdict):
            result, scope, basis = weighing.verdict, weighing.scope, weighing.basis
        else:
            result, scope, basis = reviewed_verdict, _text(reasons[0].get("scope")), BASIS_REVIEWED_WEIGHED
    elif not limits and risk_rank(WAIT) <= risk_rank(reviewed_verdict):
        # No stored weighing supports a replacement (none current, or it keeps the rest of the page): the owner's
        # temporary volume-based WAIT stays, and where a stored weighing says why, its limiting evidence says so.
        result, scope = WAIT, ""
        basis = (BASIS_REVIEWED_AND_VOLUME if confirmed or corroborated
                 else BASIS_VENDOR_ISSUE_AND_VOLUME if known_issue else BASIS_VOLUME)
    elif reasons:
        result, scope, basis = reviewed_verdict, _text(reasons[0].get("scope")), BASIS_REVIEWED
    else:
        result, scope, basis = INSUFFICIENT_DATA, "", BASIS_LIMITED
    keys = {k for k in (report_url_key(str(r.get("source_url") or "")) for r in rows) if k}
    return Assessment(reports=len(rows), unique_urls=len(keys), independent=independent_reports(rows)[0],
                      limits=limits, result=result, scope=scope, basis=basis, confirmed=confirmed,
                      corroborated=corroborated, vendor_known_issue=known_issue, weighing=weighing,
                      corroborated_new=sum(1 for e in reasons if _text(e.get("verdict")) == TEST_FIRST
                                           and e.get("new_in_this_version") is True),
                      record_facts=assessment_output.record_facts(rec, rows, source_facts=source_facts))


# The assessment's public wording, ONE copy. lib/evidence_overview carries these lines to the page
# (`risk_assessment` in its projection row) and _includes/patch-evidence-overview.html prints them; neither
# words anything. No line states the trigger, a rate, a percentage or a share of installations.
ASSESS_NOT_ESTABLISHED = "Not established."
ASSESS_VOLUME_CONFIRMED = (
    "WAIT. This is a risk-management recommendation: it rests on the number of accepted reports that name this exact "
    "version. {authority} have confirmed some of these reports as defects (stated under problem confirmation), but no "
    "confirmed defect is shown to explain the other reports, and the reports do not show how often installations "
    "fail.")
ASSESS_RECOMMENDATION = {
    BASIS_VOLUME: (
        "WAIT. This is a risk-management recommendation: it rests on the number of accepted reports that name "
        "this exact version. No single cause is confirmed, and the reports do not show how often installations "
        "fail."),
    BASIS_REVIEWED_AND_VOLUME: (
        "WAIT. {level} It is stated with the verdict above. This exact version also carries a high number of "
        "accepted reports. The other reports are not confirmed as one defect, and they do not show how often "
        "installations fail."),
    BASIS_VENDOR_ISSUE_AND_VOLUME: (
        "WAIT. {vendor} has documented a known issue affecting this version, and it also carries a high number "
        "of accepted reports. The reports are not confirmed as one defect, and they do not show how often "
        "installations fail."),
    BASIS_OFFICIAL_WITHDRAWAL: (
        "AVOID for new installations. The vendor's withdrawal of this update decides this page; the accepted "
        "reports do not change it."),
    BASIS_OFFICIAL_SECURITY: (
        "SECURITY UPDATE. Microsoft's classification of this update as a monthly security release decides this "
        "page; the accepted reports do not override it."),
    BASIS_REVIEWED: (
        "{phrase}. The reviewed finding stated with the verdict above decides this page. The number of accepted "
        "reports adds no wider recommendation here; the limiting evidence says why."),
    BASIS_LIMITED: (
        "No recommendation. The accepted reports cannot support one here; the limiting evidence says why."),
}
# One sentence per `volume_problems` code: the precise limiting evidence. "{k}" is the code's own number,
# "{n}" the counted reports, "{product}" the record's product name. A sentence prints a number only where the
# code measured exactly that number (review round 1, F6).
ASSESS_LIMIT = {
    # A RULE OF SCOPE, and the sentence says only that (review round 1, F2). VOLUME_PRODUCTS is the literal copy
    # of report_counts.CONSENSUS_PROMOTION_PRODUCTS, and what membership of THAT set grants is one thing: the
    # lane may DELETE a record's published projections when its counted population reaches zero. A product is
    # kept out of it where that deletion is judged unsafe in the collection lane (the workflow comment above the
    # scoped promotion step of the one promoted non-member says why). It is not a statement about the count on a
    # page: counts are reconciled for every product, and a page at the trigger holds thirty reports or more, so
    # the zero-count residual cannot apply to a page that prints this. The first wording ("not yet retracted
    # automatically when a report is withdrawn") said the opposite of what the code does.
    "not_promotion_product": (
        "AUXSAYS does not apply its report-volume recommendation to {product}. That is a rule about which "
        "products the recommendation covers, not a finding about these reports."),
    "below_volume_unique_urls": "Only {k} separate report links stand behind the {n} reports.",
    # No number: the condition is measured as "some link is not a row's own" (a shared link, or two rows with
    # no readable link), never as how many.
    "duplicate_citation_urls": "Not every one of the {n} reports has a report link of its own.",
    "unpublishable_rows": (
        "{k} of the {n} reports cannot be published as a citation (a missing link, a failed date check or an "
        "unreadable classification)."),
    "report_facts_unavailable": (
        "The stored comparison facts are missing for {k} of the {n} reports, so they are not shown to be "
        "separate reports."),
    # "{k}" is `independent_reports`' own result, and the sentence states the rule that produced it. (It used
    # to say "{k} of the {n} reports carry text that differs from every other report": thirty rows of which two
    # share a text printed 29, and the reports that differ from every other number 28.)
    "below_independent_reports": (
        "Reports with identical text are read as one reporter and each report link is counted once; read that "
        "way, the number of separate reports among the {n} is {k}."),
    "officially_identified_security_update": (
        "The vendor identifies this release as a security update, so a number of reports does not set its "
        "recommendation."),
}
ASSESS_MATURITY = "{n} accepted patch-specific reports on {u} separate report links."
ASSESS_EXCLUSIVE_ALL = "Each of those links is counted for this version only."
ASSESS_EXCLUSIVE_SOME = ("{x} of those links are counted for this version only; {y} are also counted for another "
                         "tracked version.")
# A reviewed finding is worded at the strength of ITS OWN stored verdict, never above it (review round 1, F7).
# A WAIT entry is a `regression` (lib.verdict_reasons: a version transition, a material impact,
# `new_in_this_version: true`); a TEST FIRST entry is a corroboration, which may rest on two reporters or on a
# cited official confirmation, so the line names its level and nothing about how it is supported. The page
# with both is worded by the WAIT entry, the one `decide` puts first.
ASSESS_REVIEWED_LEVEL = {
    WAIT: "A reviewed finding describes a problem new in this version on a named setup.",
    TEST_FIRST: ("A reviewed finding advises TEST FIRST on a named setup; it does not confirm a problem new in "
                 "this version."),
}
# Review 2, R2-1: whether a reviewed problem is new in the version is its own stored field, and the schema lets a
# TEST FIRST entry carry `true`. The TEST FIRST sentence above then denied what the reviewed line beneath it
# said, so a page with such an entry gets the sentence that stops at the setup.
ASSESS_REVIEWED_TEST_FIRST_NEW = "A reviewed finding advises TEST FIRST on a named setup."
ASSESS_REVIEWED_TAIL = ("Each reviewed finding is stated with the verdict above. The other reports are not "
                        "confirmed as one problem.")
ASSESS_FINDING_PREFIX = "Reviewed finding: "
ASSESS_UNCONFIRMED = ("Not established. AUXSAYS has no reviewed finding that confirms any one problem across "
                      "these reports, so their number is not a count of one defect.")
ASSESS_VENDOR_DECLARED = ("{vendor} has documented a known issue affecting this version; see its official "
                          "notes for this release.")
ASSESS_VENDOR_NONE = ("AUXSAYS has no record of a vendor-documented known issue for this version. That is not a "
                      "statement that none exists.")
ASSESS_SEVERITY = ("Not established. AUXSAYS holds no verified severity or data-loss finding for these reports; "
                   "a reviewed finding, where one is shown above, states its own impact.")
ASSESS_SETUPS_REVIEWED = ("Each reviewed finding stated with the verdict above names the setup it applies to. For "
                          "the other reports: not established.")
ASSESS_SETUPS = "Not established. AUXSAYS has not verified which platforms or workflows these reports concern."
ASSESS_SETUPS_REVIEWED_TAIL = "Each reviewed finding stated with the verdict above names the setup it applies to."
ASSESS_POSITIVE = ("Not established. AUXSAYS does not collect reports of successful installations, and a lack "
                   "of complaints is not evidence that a version is safe.")
ASSESS_RELEASED = "Released {date}."
ASSESS_RELEASE = {
    "archived": "This release is archived.",
    "excluded_product": "AUXSAYS does not compare releases of this product.",
    "newer_release": ("A newer release is on record: {identity}. Newer is not necessarily safer, and a fix in "
                      "one release is not assumed to carry into a later one."),
    "newest": "AUXSAYS has no record of a newer release.",
    "not_established": "AUXSAYS has not established a better-supported alternative.",
}
ASSESS_COLLECTION = ("Shown in the monitoring status on this page. It does not change this assessment: accepted "
                     "reports stay counted while collection is degraded or stopped, and a lack of new reports "
                     "is not positive evidence.")
# Names ONLY inputs `assess` and `assessment_lines` read (review round 1, F5): the counted rows, the supported
# reviewed findings, the vendor's known-issue declaration, an official withdrawal, the release context. Nothing
# here reads a vendor FIX, so the line does not promise one.
ASSESS_PROVISIONAL = ("Provisional. Recomputed on every site build from the accepted reports, the reviewed "
                      "findings and the vendor records on file; it changes when reports arrive or are "
                      "withdrawn, when a reviewed finding is added or removed, when the vendor documents a "
                      "known issue or withdraws the update, and when a newer release is recorded.")
# AUX-137: a page that holds maintainer records also changes when the SCHEDULED read of the
# tracker (the collection lane's facts refresh) finds a record changed. Said only where records are held, and
# said as what it is: a scheduled read, not a live view.
ASSESS_PROVISIONAL_RECORDS = (
    "Provisional. Recomputed on every site build from the accepted reports, the reviewed findings, the vendor "
    "records and the maintainer records on file; it changes when reports arrive or are withdrawn, when a reviewed "
    "finding is added or removed, when the vendor documents a known issue or withdraws the update, when a "
    "scheduled read of the tracker finds that the maintainers' record of a report changed or is too old to "
    "use, and when a newer release is recorded.")
# AUX-137: said on every page at the trigger that has no CURRENT stored provisional assessment (none computed yet,
# or computed from evidence that has since changed). True in both cases; the page then shows the count-based result.
ASSESS_PENDING = ("The weighing of these reports by failure, severity, setup and regression is pending: it has not "
                  "been computed for the evidence now on file, so this page shows the count-based assessment until "
                  "it is.")
ASSESS_LABELS = ("Recommendation", "Limiting evidence", "Evidence maturity", "Representativeness",
                 "Problem confirmation", "Independent corroboration", "Maintainer response", "Recurring problems",
                 "Vendor known issues", "Severity and data loss", "Affected setups", "Positive outcomes",
                 "Fixes and open problems", "Release and alternatives", "Collection health", "Status")
# AUX-137: recommendation and evidence maturity are separate lines; this one says what the reports are a sample of.
ASSESS_REPRESENTATIVENESS = ("These are public reports from people who chose to report a problem. They are not a "
                             "sample of installations: they show that problems were reported, not how often an "
                             "installation fails or which share of users is affected.")
ASSESS_REVIEWED_WEIGHED = ("{phrase}. The reviewed finding stated with the verdict above decides this page; the "
                           "provisional assessment of the accepted reports supports nothing more cautious.")
_ISO_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[T ]|$)", re.ASCII)


def _vendor(record: dict[str, Any]) -> str:
    return _text(record.get("update_source_name")) or "The vendor"


def assessment_limit_lines(assessment: Assessment, record: dict[str, Any] | None) -> list[str]:
    """The precise limiting evidence, one sentence per limit, or [] when the count stands or an official fact
    decides the page (the limits are then not what decides it). A code with no sentence is a programming
    error and raises, so a new limit can never be published as silence."""
    weighing = assessment.weighing
    if assessment.basis in VOLUME_BASES and weighing is not None and weighing.retain:
        # AUX-137: why the stored weighing found no replacement for the temporary WAIT, in its own words.
        return [weighing.retained()]
    if assessment.basis not in (BASIS_REVIEWED, BASIS_LIMITED):
        return []
    rec = record or {}
    product = _text(rec.get("update_product")) or _text(rec.get("product_id")) or "this product"
    lines = []
    for limit in assessment.limits:
        code, _, number = limit.partition(":")
        if code == "below_volume_reports":
            continue  # unreachable at the trigger; never a sentence
        lines.append(ASSESS_LIMIT[code].format(k=number, n=assessment.reports, product=product))
    return lines


def assessment_lines(assessment: Assessment, record: dict[str, Any] | None, *, finding: str = "",
                     exclusive: int | None = None, release_kind: str = "",
                     newer_identity: str = "") -> list[dict[str, str]]:
    """The published assessment: {"label", "text"} lines in print order. The caller supplies only facts this
    module cannot see from one page: a still-valid reviewed finding about the population (`finding`), how many
    of the page's report URLs no other tracked version counts (`exclusive`, None when unknown: the line then
    says nothing about it), and the release context the page's way forward already computes (`release_kind`,
    one of ASSESS_RELEASE, with the newer release's name)."""
    rec = record or {}
    out: list[dict[str, str]] = []

    def add(label: str, text: str) -> None:
        if text:
            out.append({"label": label, "text": text})

    phrase = f"{assessment.result} {assessment.scope}".strip()
    level = (ASSESS_REVIEWED_LEVEL[WAIT] if assessment.confirmed
             else ASSESS_REVIEWED_TEST_FIRST_NEW if assessment.corroborated_new else ASSESS_REVIEWED_LEVEL[TEST_FIRST])
    weighing = assessment.weighing
    # The dimension lines the stored weighing words, by label; {} when there is none (the count-based wording).
    facts = weighing.lines() if weighing is not None else {}
    if weighing is not None:
        facts["Representativeness"] = ASSESS_REPRESENTATIVENESS
    if assessment.basis in PROVISIONAL_BASES:
        add("Recommendation", weighing.recommendation(phrase))
    elif assessment.basis == BASIS_REVIEWED_WEIGHED:
        add("Recommendation", ASSESS_REVIEWED_WEIGHED.format(phrase=phrase))
    elif assessment.basis == BASIS_VOLUME and weighing is not None and weighing.facts.confirmed:
        # Review of 2026-11-24, N3: never "No single cause is confirmed" beside the maintainers' own confirmations.
        add("Recommendation", ASSESS_VOLUME_CONFIRMED.format(authority=weighing.facts.cap()))
    else:
        add("Recommendation", ASSESS_RECOMMENDATION[assessment.basis].format(vendor=_vendor(rec), phrase=phrase,
                                                                             level=level))
    add("Limiting evidence", " ".join(assessment_limit_lines(assessment, rec)))
    maturity = ASSESS_MATURITY.format(n=assessment.reports, u=assessment.unique_urls)
    if exclusive is not None:
        shared = max(assessment.unique_urls - int(exclusive), 0)
        maturity += " " + (ASSESS_EXCLUSIVE_SOME.format(x=int(exclusive), y=shared) if shared
                           else ASSESS_EXCLUSIVE_ALL)
    add("Evidence maturity", maturity)
    add("Representativeness", facts.get("Representativeness", ""))
    reviewed = bool(assessment.confirmed or assessment.corroborated)
    confirmation = (f"{level} {ASSESS_REVIEWED_TAIL}" if reviewed
                    else f"{ASSESS_FINDING_PREFIX}{finding}" if finding else ASSESS_UNCONFIRMED)
    if weighing is not None and weighing.facts.confirmed:
        # The maintainers' own confirmations are a stored fact; the reviewed sentence, where there is one, follows.
        f = weighing.facts
        confirmation = (f"{f.cap()} have confirmed {f.confirmed} of the accepted reports as "
                        f"{'a defect' if f.confirmed == 1 else 'defects'} and label {f.regressions or 'none'} of them a "
                        f"regression; filed against an earlier version: {f.confirmed_earlier}, against a later "
                        f"version: {f.confirmed_later}. A confirmation says the maintainers treat a report as a real "
                        f"defect, not how many users it affects. {f.dated()}".strip()
                        + (f" {level} {ASSESS_REVIEWED_TAIL}" if reviewed else ""))
    add("Problem confirmation", confirmation)
    add("Independent corroboration", facts.get("Independent corroboration", ""))
    add("Maintainer response", facts.get("Maintainer response", ""))
    add("Recurring problems", facts.get("Recurring problems", ""))
    add("Vendor known issues", ASSESS_VENDOR_DECLARED.format(vendor=_vendor(rec))
        if assessment.vendor_known_issue else ASSESS_VENDOR_NONE)
    add("Severity and data loss", facts.get("Severity and data loss", ASSESS_SEVERITY))
    setups = ASSESS_SETUPS_REVIEWED if reviewed else ASSESS_SETUPS
    if "Affected setups" in facts:
        setups = facts["Affected setups"] + (f" {ASSESS_SETUPS_REVIEWED_TAIL}" if reviewed else "")
    add("Affected setups", setups)
    add("Positive outcomes", facts.get("Positive outcomes", ASSESS_POSITIVE))
    add("Fixes and open problems", facts.get("Fixes and open problems", ""))
    released = _ISO_DATE_RE.match(_text(rec.get("update_published_at")))
    release = [ASSESS_RELEASED.format(date=released.group(1))] if released else []
    if release_kind:
        release.append(ASSESS_RELEASE[release_kind].format(identity=newer_identity))
    add("Release and alternatives", " ".join(release))
    add("Collection health", facts.get("Collection health", ASSESS_COLLECTION))
    add("Status", ASSESS_PROVISIONAL_RECORDS if weighing is not None and weighing.facts.records
        else ASSESS_PROVISIONAL if weighing is not None else f"{ASSESS_PROVISIONAL} {ASSESS_PENDING}")
    return out


class Decision:
    """What `decide` returns. `reasons` are the SUPPORTED reason entries for the page, most
    cautionary first (file order breaks ties, exactly as the template iterates). A volume-based WAIT
    (G87) carries `reason_code` high_report_volume, its `label`, and `reports`, the canonical count it
    rests on; its scope is empty (it applies to every setup), and its `reasons` are the reviewed entries
    it stands above, still shown."""

    __slots__ = ("verdict", "rule", "scope", "reasons", "lifecycle", "security", "reason_code", "label",
                 "reports", "assessment")

    def __init__(self, verdict: str, rule: str, *, scope: str = "", reasons: tuple = (),
                 lifecycle: dict[str, Any] | None = None, security: bool = False, reason_code: str = "",
                 label: str = "", reports: int = 0, assessment: "Assessment | None" = None) -> None:
        self.verdict = verdict
        self.rule = rule
        self.scope = scope
        self.reasons = reasons
        self.lifecycle = lifecycle
        self.security = security
        self.reason_code = reason_code
        self.label = label
        self.reports = reports
        # AUX-134: the provisional contextual risk assessment the page's counted reports triggered, or None
        # below the trigger. `assessment.result` is ALWAYS this decision's verdict: `decide` builds both.
        self.assessment = assessment

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
    def facts(self) -> bool:
        """Is this a verdict the provisional assessment of the page's reports decides (AUX-137)?"""
        return self.reason_code in PROVISIONAL_BASES

    @property
    def qualifier(self) -> str:
        """What every surface prints beside the verdict word: the setup scope, or -- for the volume-based
        precaution, which has none -- its label."""
        return self.scope or (self.label if self.volume else "")


def decide(record: dict[str, Any] | None, *, valid_reasons: Any = (), lifecycle: Any = (),
           counted_rows: Any = (), source_facts: Any = None) -> Decision:
    """THE decision for one patch. `valid_reasons` must already be the entries SUPPORTED by the
    page's counted rows (lib.verdict_reasons.valid_reasons_by_identity); `lifecycle` the validated
    lifecycle entries; `counted_rows` the page's canonical counted population
    (lib.report_counts.counted_evidence_rows for this identity), read ONLY by the volume rule. No stored
    count, sentiment, theme, severity, maturity, collection health or clock is accepted. A caller that
    passes no rows gets no volume-based WAIT: it fails closed to the reviewed outcome. `source_facts` are the
    stored source records of reports (lib.assessment_facts), None meaning the tracked file; they are read ONLY
    at the trigger, by `assess`. At
    ASSESSMENT_MIN_REPORTS counted rows the result carries `assessment` (AUX-134): the provisional
    contextual risk assessment that reached this verdict, with its basis and its limits."""
    rec = record or {}
    ordered = tuple(sorted((dict(e) for e in valid_reasons or ()),
                           key=lambda e: risk_rank(_text(e.get("verdict")))))
    security = is_monthly_security_update(rec)
    life = lifecycle_for(rec, lifecycle)
    rows = [r for r in (counted_rows or ()) if isinstance(r, dict)]
    # AUX-134: at ASSESSMENT_MIN_REPORTS counted reports `assess` runs for every product and every outcome,
    # and the verdict below is the one it reached, with its basis and its limiting evidence; below the trigger
    # it is None and nothing here reads the count. With no limit its result is still the volume WAIT, on the
    # count alone (see WHAT THIS IS NOT above).
    assessment = assess(rec, ordered, rows, withdrawn=bool(life), security=security, source_facts=source_facts)
    if life:
        # Scoped like every non-default verdict: the withdrawal applies to INSTALLING the update,
        # not to a device that already has it (owner decision 2).
        return Decision(AVOID, "R1", scope=AVOID_SCOPE, lifecycle=life, reasons=ordered, security=security,
                        assessment=assessment)
    if security:
        return Decision(SECURITY_UPDATE, "R2", reasons=ordered, security=True, assessment=assessment)
    if assessment is not None and assessment.basis in VOLUME_BASES:
        return Decision(WAIT, VOLUME_RULE, reasons=ordered, reason_code=VOLUME_REASON_CODE,
                        label=VOLUME_LABEL, reports=len(rows), assessment=assessment)
    if assessment is not None and assessment.basis in PROVISIONAL_BASES:
        # AUX-137: the provisional assessment of the page's reports decides. Scoped like every reasoned verdict;
        # the reviewed entries it stands above stay printed beneath it.
        return Decision(assessment.result, PROVISIONAL_RULES[assessment.result], scope=assessment.scope,
                        reasons=ordered,
                        reason_code=assessment.basis, reports=len(rows), assessment=assessment)
    if ordered:
        head = ordered[0]
        verdict = _text(head.get("verdict"))
        return Decision(verdict, "R3" if verdict == WAIT else "R4", scope=_text(head.get("scope")),
                        reasons=ordered, assessment=assessment)
    return Decision(INSUFFICIENT_DATA, "R5", assessment=assessment)


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
    if decision.facts:
        # Worded by the weighing module from the records it read; the reviewed entries follow as under a
        # volume-based WAIT.
        parts = [decision.assessment.weighing.body(decision.reports)]
        if decision.verdict == TEST_FIRST:
            parts.append(TEST_FIRST_TRY)
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
            # AUX-137: where the maintainers' records are on file and confirm reports of their own, "no problem is
            # independently reported yet" would be false beside them; the weighing words that sentence instead.
            weighed = (decision.assessment.weighing.other_setups()
                       if decision.assessment is not None and decision.assessment.basis == BASIS_REVIEWED_WEIGHED
                       else "")
            parts.append(weighed or (OTHER_SETUPS_BY_CLASS.get(_text(head.get("reason_class")), OTHER_SETUPS)
                                     if alone else OTHER_SETUPS))
        return " ".join(parts)
    if n == 0:
        return ""
    # A release-line page (a bare version that collects every report naming the line) is not one
    # exact update, and its reports are matched to the line (lib.davinci_release_line).
    matched_to = ("this release line" if _text(rec.get("update_identity_scope")) == "release_line"
                  else "this exact update")
    if n == 1:
        return (f"No verdict yet: one user report is matched to {matched_to}, and one report does "
                "not show a pattern. If it matches your setup, test before relying on this update.")
    return (f"No verdict yet: {n} user reports are matched to {matched_to}, but no problem in "
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
