"""Microsoft PowerPoint community-evidence collector (Microsoft Learn Q&A).

Discovers real Microsoft PowerPoint user reports from Microsoft Learn Q&A
(learn.microsoft.com/answers) via its search-RSS API, driving each search by the exact
*version identity* already captured on the generated record (``update_version`` /
``target_app_version`` / ``target_build`` / ``target_channel``). It then applies a fixed,
ordered, deterministic acceptance contract so a report counts ONLY when it names PowerPoint,
names the record's exact Version YYMM in context, is channel-consistent with the record
(Current Channel), does not carry a *conflicting* build, is dated on/after release, links to
a specific report URL, and describes a concrete post-install PowerPoint problem.

PowerPoint is NOT Windows: one Version YYMM maps to exactly one Current-Channel build, so
this collector keys on the exact patch identity (version AND exact build) and MUST NOT copy
the Windows KB / OS-build / servicing-train identity gate. The full Click-to-Run build is
REQUIRED for counted PowerPoint evidence: canonical patch identity here is
(product_id, update_version, target_build), because Microsoft ships several Current Channel builds
under one YYMM. A report that names only the version does not identify a patch, so it is refused
with ``missing_exact_build`` rather than attributed by inference. The repo doctrine that counts on
"the exact patch" is unchanged -- for this product the exact patch simply includes the build.

Deterministic + repo-owned: no AI, no manual candidate approval. Discovery is keyword-anchored
(search by "PowerPoint <version>" / "Version <version>"); acceptance is a fixed ordered rule set.

Safety — default-off. This collector is NOT part of the always-on runner registry. It is
registered ONLY when ``AUXSAYS_ENABLE_POWERPOINT_CONSENSUS`` is the explicit canonical
``true`` (see run_patch_evidence_collection.build_collectors), and even then a scheduled
``--write`` never enables the flag (the workflow gates it to a manual dry_run only). Observe
it with the read-only dry-run first; it writes no evidence, no method health, and never
changes a PowerPoint record's verdict.

Read-only local dry-run (never writes evidence or records):
    cd auxsays/scripts && python -m patch_collectors.microsoft_powerpoint [--update-version 2605] [--since-days 90]
"""
from __future__ import annotations

import os
import re
from typing import Any

from lib.build_claims import (
    BUILD_TOKEN_RE, OFFICE_FULL_VERSION_RE, extract_build_claims,
    select_current_failing_build, single_named_build,
)
from lib.patch_identity import is_build_aware, patch_key
from .base import (
    CollectorContext,
    PatchRecord,
    ProductCollector,
    append_evidence_rows,
    date_part,
    exact_version_match,
    generated_records,
    load_front_matter_and_body,
    make_evidence_row,
    method_health_row,
    slug,
    source_date_passes,
    source_url_is_specific,
    text_describes_issue,
    utc_now,
)
from . import microsoft_learn_qna_source as learn_qna
from . import reddit_source
from . import stack_exchange_source
from . import github_officedev_source

PRODUCT_ID = "microsoft-powerpoint"

LEARN_QNA_METHOD_ID = "learn_qna_search_rss"
LEARN_QNA_SOURCE_TYPE = "microsoft_learn_qna"
LEARN_QNA_SOURCE_NAME = "Microsoft Learn Q&A"

# Canonical repo-wide Reddit method id. It MUST equal the entry in
# collector_ownership.ALLOWED_METHODS["microsoft-powerpoint"], because every collection emits a
# Reddit health row (status "disabled" when the fallback is off) and _validate_ownership runs
# INSIDE the write transaction: an unauthorized method_id would roll back the whole
# transaction, discarding the valid Learn Q&A rows with it. Every other product that searches
# Reddit (davinci, premiere, both Acrobats) already uses this exact id.
REDDIT_METHOD_ID = "reddit_search"
REDDIT_SOURCE_TYPE = "reddit_community_report"

STACK_EXCHANGE_METHOD_ID = "stack_exchange_search"
STACK_EXCHANGE_SOURCE_TYPE = "stack_exchange_question"
# Super User carries the PowerPoint desktop reports; Stack Overflow's `powerpoint` tag carries
# add-in/automation regressions that name a build. Both are one API call per route per run.
STACK_EXCHANGE_SITES = ("superuser", "stackoverflow")
STACK_EXCHANGE_TAGS = {"superuser": "microsoft-powerpoint", "stackoverflow": "powerpoint"}

GITHUB_METHOD_ID = "github_officedev_issues"
# Event-log / crash-record vocabulary. Its presence means the version token is a FAULTING BINARY's
# version, whose owning application lib.build_claims decides from the governing AppName.
CRASH_RECORD_MARKER_RE = re.compile(r"\b(?:AppName|ModName|Faulting\s+(?:application|module))\b", re.I)
GITHUB_SOURCE_TYPE = "github_officedev_issue"
# Measured: a BARE build token finds nothing on GitHub search, the full 16.0.<build> form finds the
# issues. Symptom terms carry the recall for reports whose author never wrote a build at all.
GITHUB_SYMPTOM_QUERIES = (
    "repo:OfficeDev/office-js PowerPoint crash",
    "repo:OfficeDev/office-js PowerPoint settings",
    "repo:OfficeDev/office-js PowerPoint slideshow",
)
MAX_GITHUB_QUERIES = 4
REDDIT_SOURCE_NAME = "Reddit"
REDDIT_SUBREDDITS = ("powerpoint", "microsoft365", "Office365")
# Reddit is a documented CI-blocked fallback (PR #23). It is attempted ONLY when this flag is
# the explicit canonical "true"; otherwise it is honestly reported as method-health "disabled".
# It is never required for the pilot to pass, and never weakens the acceptance gates.
REDDIT_FALLBACK_ENV = "AUXSAYS_POWERPOINT_REDDIT_FALLBACK"


# --- deterministic content classifiers (no AI) -------------------------------
# Marketing/version identity: an Office Version is YYMM (year 2X, month 01-12), e.g. 2605.
YYMM_RE = re.compile(r"(?<![0-9.])(2\d(?:0[1-9]|1[0-2]))(?![0-9.])")
# Full Click-to-Run build, e.g. 20026.20076 (5 digits . 5 digits). REQUIRED for counted
# evidence: it is the second half of this product's canonical patch identity.
#
# Sourced from lib.build_claims so this authority and the context-resolution stage read builds
# through ONE primitive. The previous local copy used a `(?![0-9.])` trailing guard, which missed a
# build that ends a sentence ("Build 19822.20182.") because the full stop is itself in the excluded
# class -- a legitimately stated build went unseen by the gate that requires it.
BUILD_RE = BUILD_TOKEN_RE

POWERPOINT_RE = re.compile(r"\b(?:microsoft\s+)?power\s?point\b", re.I)
# Other Office apps — only matters to reject app-only reports that never name PowerPoint.
OTHER_OFFICE_APP_RE = re.compile(r"\b(?:word|excel|outlook|teams|onenote|access|publisher)\b", re.I)

CURRENT_CHANNEL_RE = re.compile(r"\bcurrent\s+channel\b", re.I)
CURRENT_CHANNEL_PREVIEW_RE = re.compile(r"\bcurrent\s+channel\s*\(?\s*preview", re.I)
CONFLICTING_CHANNEL_RE = re.compile(
    r"\b(?:monthly\s+enterprise(?:\s+channel)?|semi[\s-]?annual(?:\s+enterprise)?(?:\s+channel)?|"
    r"beta\s+channel|insider(?:\s+(?:fast|slow|beta|preview))?|dev\s+channel)\b",
    re.I,
)
STORE_RE = re.compile(r"\b(?:microsoft\s+store|windows\s+store|store\s+(?:app|version)|uwp)\b", re.I)

LATEST_RE = re.compile(
    r"\b(?:latest|newest|most\s+recent|recent|last)\s+(?:update|patch|version|build|release)\b|"
    r"\bthis\s+month'?s\s+(?:update|patch)\b|\bafter\s+(?:the\s+)?(?:last|latest|recent)\s+update\b",
    re.I,
)

# Concrete post-install PowerPoint problems (a real regression report, not a how-to/feature ask).
POWERPOINT_ISSUE_RE = re.compile(
    r"\b(?:"
    r"crash(?:es|ing|ed)?|won'?t\s+(?:open|start|launch)|does\s+not\s+open|cannot\s+open|can'?t\s+open|"
    r"fail(?:s|ed|ing)?\s+to\s+(?:open|start|launch|save|export|load|respond)|"
    # Unqualified failure statements. The pattern above requires "fail TO <verb>", so a report
    # saying "Copilot ... fails consistently in PowerPoint desktop" -- which is as concrete as a
    # failure claim gets -- matched nothing and was refused not_a_concrete_powerpoint_issue after
    # passing product, version, channel, build AND date. These forms are unambiguous statements
    # that something is broken; they are not how-to or feature language.
    r"fail(?:s|ed|ing)?\s+(?:consistently|constantly|always|every\s+time|intermittently|randomly|silently)|"
    r"not\s+working|does\s+not\s+work|doesn'?t\s+work|no\s+longer\s+works?|stopped\s+working|"
    r"unable\s+to\s+(?:read|open|save|export|load|print|insert|edit)|"
    r"freez(?:e|es|ing|en)|hang(?:s|ing|ed)?|not\s+responding|"
    r"corrupt(?:s|ed|ion)?|damaged\s+(?:file|presentation|deck)|blank\s+(?:slide|presentation|deck)|"
    # The same "cannot <verb>" family already covers open and save; read/write/retrieve/access are
    # the identical shape and were simply missing, so a report saying "I cannot read the value from
    # PowerPoint web" described a concrete failure the classifier could not see.
    r"(?:cannot|can'?t|could\s+not|couldn'?t)\s+(?:read|write|retrieve|access|load|update|insert|print)|"
    r"can'?t\s+save|cannot\s+save|save\s+(?:fail\w*|error)|unable\s+to\s+save|lost\s+(?:my\s+)?(?:work|slides|changes)|data\s+loss|"
    r"slide[\s-]?show\s+(?:fail\w*|crash\w*|black|freez\w*|won'?t\s+start|not\s+working)|presenter\s+view\s+(?:broken|not\s+working|black)|"
    r"export\s+(?:fail\w*|error|broken)|can'?t\s+export|animation[s]?\s+(?:broken|not\s+working|glitch\w*|regress\w*|stutter\w*)|"
    r"transition[s]?\s+(?:broken|not\s+working)|render(?:s|ing|ed)?\s+(?:issue|error|broken|wrong|incorrect)|"
    r"add[\s-]?in[s]?\s+(?:broken|not\s+working|crash\w*|incompatib\w*|fail\w*|disabled)|"
    r"(?:very\s+)?slow|lag(?:s|ging|gy)?|performance\s+(?:regress\w*|issue|problem)|high\s+cpu|memory\s+leak|"
    r"install(?:ation)?\s+(?:fail\w*|error|stuck|loop)|update\s+(?:fail\w*|error|broke\w*|stuck)|"
    r"broke\w*\s+after|stopped\s+working\s+after|no\s+longer\s+works?\s+after|not\s+working\s+after|regress\w*|"
    # Inflected like every sibling verb above. `bug` and `glitch` were the only two symptom words
    # here without their plurals, and the group's trailing \b then made the plural unmatchable --
    # "crashes" matched but "glitches" did not. A real Super User report of PowerPoint slideshow
    # annotation glitches on Build 20228.20124 passed URL, product, version, channel, build and date
    # and was then refused `not_a_concrete_powerpoint_issue` solely because all three of its symptom
    # words were plural. Same \b-boundary family as the DaVinci identity defects.
    r"bugs?|glitch(?:es|ing|ed)?|error\s+message"
    r")\b",
    re.I,
)

HOW_TO_OR_FEATURE_RE = re.compile(
    r"\b(?:how\s+(?:do|to|can|would|should)\b|where\s+(?:is|do|can)\b|is\s+it\s+safe\s+to\b|"
    # capability / "does the feature exist" / "how do I use it" questions (Part C hardening):
    r"is\s+it\s+possible\s+to\b|can\s+(?:i|we|you)\s+\w+|i(?:'m|\s+am)\s+trying\s+to\b|"
    r"does\s+(?:microsoft\s+)?(?:power\s?point|ppt|it|this)\s+(?:support|have|allow|include|offer|let|do)\b|"
    r"should\s+i\s+(?:install|update|upgrade)\b|which\s+version\b|what'?s\s+the\s+best\b|"
    r"feature\s+request|please\s+add|can\s+you\s+add|would\s+like\s+(?:to\s+see|a\s+feature|the\s+ability)|"
    r"is\s+there\s+a\s+way\s+to|how\s+about\s+adding)\b",
    re.I,
)
ANNOUNCE_OR_NOTE_RE = re.compile(
    r"\b(?:now\s+available|is\s+available|announc(?:e|es|ing|ed|ement)|general\s+availability|"
    r"rolling\s+out|is\s+released|has\s+been\s+released|release\s+notes|what'?s\s+new|change\s*log|"
    r"new\s+features|version\s+history)\b",
    re.I,
)
# Title-anchored announcement / official-note phrases (Part B). When any of these is the SUBJECT
# of the thread title, the post is an announcement/release discussion, not a user report — and it
# is rejected even if the body incidentally contains issue vocabulary (crash/bug/error/fix/issue).
ANNOUNCEMENT_TITLE_RE = re.compile(
    r"\b(?:"
    r"microsoft\s+released\s+(?:update|version|build)|released\s+(?:update|version|build)|"
    r"update\s+released|build\s+released|new\s+update\s+available|now\s+available|is\s+available|"
    r"current\s+channel\s+(?:update|release)|release\s+notes|what'?s\s+new|new\s+features|"
    r"announc(?:e|es|ing|ed|ement)|roll(?:ing|s|ed)?[\s-]?out|rollout|version\s+history|"
    r"fixed\s+issues|known\s+issues|update\s+summary|general\s+availability|change\s*log"
    r")\b",
    re.I,
)

# --- product primacy (Part A) --------------------------------------------------
# Another Office application is the PRIMARY subject of a title. Unambiguous app names match on a
# bare word boundary; app names that are also common English words (word/access/project/teams)
# only count as the app when they carry app context (Microsoft/MS prefix, "<app> app/document/
# database/...", a leading "<app>:", or "<app> <Version YYMM>"), so a noun like "word spacing"
# or the verb "access" never trips the gate. This is a structural title/parent-subject test, not
# a bare deny-list (repo doctrine: use subject structure).
_UNAMBIGUOUS_OTHER_APP = r"excel|outlook|onenote|publisher|visio"
_AMBIGUOUS_OTHER_APP = r"word|access|project|teams"
OTHER_OFFICE_APP_TITLE_RE = re.compile(
    r"\b(?:" + _UNAMBIGUOUS_OTHER_APP + r")\b"
    r"|\b(?:microsoft\s+|ms\s+)(?:" + _AMBIGUOUS_OTHER_APP + r")\b"
    r"|\b(?:" + _AMBIGUOUS_OTHER_APP + r")\s+(?:app|application|document|doc|file|workbook|spreadsheet|database|mailbox|online|server)\b"
    r"|(?:^|[\s(\[\-])(?:" + _AMBIGUOUS_OTHER_APP + r")\s*[:\-]"
    r"|\b(?:" + _AMBIGUOUS_OTHER_APP + r")\s+(?:version\s+)?(?:2\d(?:0[1-9]|1[0-2]))\b",
    re.I,
)


MIN_BODY_POWERPOINT_MENTIONS = 2


def body_attribution_is_exclusive(report_body: str) -> bool:
    """True when the body attributes the failure to PowerPoint and to nothing else.

    Requires at least two PowerPoint mentions and NO other Office application anywhere in the body.
    One passing mention is not attribution, and a single mention of Word/Excel/Outlook/Teams/
    OneNote/Access/Publisher makes the report multi-application, which fails closed exactly as a
    multi-app title does.
    """
    body = report_body or ""
    if OTHER_OFFICE_APP_RE.search(body):
        return False
    return len(POWERPOINT_RE.findall(body)) >= MIN_BODY_POWERPOINT_MENTIONS


def product_primacy_reason(parent_title: str, report_title: str, report_body: str = "",
                           declared_host: str = "") -> str | None:
    """PowerPoint must be the PRIMARY subject via title/parent structure (Part A). Returns an
    exclusion reason or None.

    Accept the product gate when the report title explicitly names PowerPoint, or a patch-specific
    parent thread title names PowerPoint and the reply stays on topic. Reject when PowerPoint is
    absent from both titles (a body-only mention never establishes primacy), when another Office
    app is the clear subject of the report title without PowerPoint, or when the report title names
    PowerPoint AND another Office app (multi-application — fail closed)."""
    # A STRUCTURED host declaration outranks title text in both directions. OfficeDev's issue
    # template asks "Host [Excel, Word, PowerPoint, etc.]:" and the reporter answers it, which is a
    # far better product signal than which words appear in a title -- and the template's own
    # placeholder puts "Excel, Word" in every body, so text heuristics read that as multi-app.
    host = (declared_host or "").strip().lower()
    if host:
        return None if host == "powerpoint" else "product_not_powerpoint"
    parent_title = parent_title or ""
    report_title = report_title or ""
    pp_report = bool(POWERPOINT_RE.search(report_title))
    pp_parent = bool(POWERPOINT_RE.search(parent_title))
    if not (pp_report or pp_parent):
        # EXCLUSIVE BODY ATTRIBUTION is the one way a title-less report still identifies the
        # product. A user who writes "Copilot works in web PowerPoint and all other office desktop
        # apps, but fails consistently in PowerPoint desktop" has attributed the failure to
        # PowerPoint more precisely than a title mention ever does -- but their thread is titled
        # "Copilot Unable to Read Document Error", so title primacy alone discards it.
        #
        # Deliberately narrow and fail-closed: the body must name PowerPoint at least twice AND
        # name no other Office application anywhere, so a multi-app thread can never qualify.
        # Measured over 486 symptom-discovered candidates, 12 qualify, every one PowerPoint-specific
        # (slideshow, PPSX, presentation, PowerPoint Copilot). They still face every remaining
        # gate -- version, exact build, channel, date, concrete issue -- unchanged.
        if body_attribution_is_exclusive(report_body):
            return None
        return "product_not_powerpoint"  # PowerPoint is not the titled subject
    # Reply/title primarily about another Office app (a body mention must not override the title).
    if OTHER_OFFICE_APP_TITLE_RE.search(report_title) and not pp_report:
        return "product_not_powerpoint"
    # Multi-application report title (PowerPoint AND another Office app) -> fail closed.
    if pp_report and OTHER_OFFICE_APP_TITLE_RE.search(report_title):
        return "product_not_powerpoint"
    return None


# --- feature-location / regression evidence (Part C) ---------------------------
# A question that only asks where a feature/menu/command/option went (or how to do something) is
# not a post-install regression report — unless it also carries deterministic regression evidence
# tying the change to the exact patch.
FEATURE_LOCATION_RE = re.compile(
    r"\b(?:can'?t|cannot|unable\s+to)\s+find\b"
    r"|\bwhere\s+(?:is|are|did|do|can|has)\b"
    r"|\bwhere\s+.{0,40}?\bgo(?:ne|es)?\b"
    r"|\bmissing\s+(?:button|menu|option|feature|command|ribbon|toolbar|icon|tab|setting|function)\b"
    r"|\b(?:button|menu|option|feature|command|ribbon|toolbar|icon|tab|setting|function)\s+(?:is\s+)?missing\b"
    r"|\bhow\s+(?:do|can|to|would|should)\s+i\b|\bwhich\s+setting\b"
    r"|\b\w+\s+function\s+(?:is\s+)?(?:missing|gone|disappear\w*)\b"
    r"|\b(?:can'?t|cannot|unable\s+to)\s+(?:find|locate|see)\s+(?:the\s+|my\s+)?(?:\w+\s+){0,3}(?:function|feature|button|menu|option|command|tool|setting)\b",
    re.I,
)
# Deterministic evidence that a feature/behavior REGRESSED as a result of the patch/update.
REGRESSION_EVIDENCE_RE = re.compile(
    r"\b(?:worked|working|was\s+(?:there|available|fine|present)|used\s+to\s+(?:work|be))\b[^\n]{0,60}?\b(?:before|until|prior\s+to)\b"
    r"|\b(?:disappear\w*|gone|removed|missing|broke\w*|stopped\s+working|no\s+longer\s+(?:work\w*|available|there)|crash\w*|error|fail\w*)\b[^\n]{0,50}?\b(?:after|since|following|once\s+i)\b[^\n]{0,50}?\b(?:updat\w*|version|patch|install\w*|upgrad\w*|2\d(?:0[1-9]|1[0-2]))\b"
    r"|\bafter\s+(?:installing|updating|the\s+update|the\s+patch|version|upgrad\w*)\b[^\n]{0,70}?\b(?:crash\w*|error|broke\w*|fail\w*|gone|missing|disappear\w*|no\s+longer|stopped|grey(?:ed)?\s+out|can'?t)\b"
    r"|\b(?:broke|stopped\s+working|no\s+longer\s+works?|not\s+working|disappeared|greyed?\s+out)\s+(?:right\s+|immediately\s+)?after\b",
    re.I,
)

# --- source-content integrity (Part E) -----------------------------------------
# Learn Q&A supplies only the search-RSS title + description snippet (no full-thread hydration,
# no replies, no author). Acceptance therefore uses self-contained snippet content; when the
# decisive version evidence exists only inside a visibly TRUNCATED snippet body (missing context
# that could flip the meaning), fail closed rather than accept on partial content.
_TRUNCATION_RE = re.compile(r"(?:…|\.\.\.|\[\s*\.\.\.\s*\]|&hellip;|\bread\s+more\b|\bsee\s+more\b|\bshow\s+more\b)\s*$", re.I)


def snippet_truncated(text: str) -> bool:
    return bool(_TRUNCATION_RE.search((text or "").strip()))


# --- version-in-context / drift -------------------------------------------------

def version_in_context(text: str, version: str, target_build: str = "") -> bool:
    """True when ``version`` (a Version YYMM) appears with an explicit version/product context,
    e.g. 'Version 2605', 'PowerPoint 2605', 'Microsoft PowerPoint Version 2605', or
    '2605 (Build ...)'. A bare four-digit number with no such context never qualifies.

    EXACT-BUILD NOTATION. Microsoft's own compatibility tables write the pair without the literal
    word "build" -- "Office 2607 (20228.20110)" -- which none of the forms above accept, so a
    report naming PowerPoint in its title and the exact target build in its body was rejected as
    ``bare_version_no_context``. That notation now qualifies, but ONLY when ``target_build`` is
    supplied AND the parenthesised build is exactly it. This is strictly stronger evidence than a
    bare version, not weaker: the report has to state the full build this record was cut from.
    "Office 2607" alone still does NOT qualify, and a wrong build (2607 (20228.20200)) does not
    either. No date-proximity inference is used anywhere.
    """
    v = re.escape(str(version or "").strip())
    if not v:
        return False
    if re.search(rf"\b(?:version|ver\.?|build\s+version)\s+(?:no\.?\s*)?{v}\b", text, re.I):
        return True
    if re.search(rf"\bpower\s?point\s+(?:version\s+)?{v}\b", text, re.I):
        return True
    if re.search(rf"\bmicrosoft\s+365\s+(?:apps\s+)?(?:version\s+)?{v}\b", text, re.I):
        return True
    if re.search(rf"\bcurrent\s+channel\b[^\n]{{0,25}}\b{v}\b", text, re.I):
        return True
    if re.search(rf"(?<![0-9.]){v}(?![0-9.])\s*\(\s*build", text, re.I):
        return True
    build = str(target_build or "").strip()
    if build and re.search(rf"(?<![0-9.]){v}(?![0-9.])\s*\(\s*{re.escape(build)}(?![0-9.])",
                           text, re.I):
        return True
    return False


def versions_in_context(text: str) -> set[str]:
    """Every Version YYMM that appears *in context* anywhere in ``text``."""
    found: set[str] = set()
    for match in YYMM_RE.finditer(text or ""):
        candidate = match.group(1)
        if version_in_context(text, candidate):
            found.add(candidate)
    return found


def _bare_version_present(text: str, version: str) -> bool:
    matched, _matched, _basis = exact_version_match(text or "", version)
    return bool(matched)


# A Version YYMM named only as a historical / upgrade SOURCE ("upgraded from 2407 to 2410",
# "was on 2407", "old version 2407"). Requires an explicit migration verb so a bare "from" or a
# normal mention is never stripped. Used to keep a migration reference from making the report
# ambiguous or attributable to the version the user moved AWAY from (Part D).
HISTORICAL_SOURCE_RE = re.compile(
    r"\b(?:upgrad\w+\s+from|updat\w+\s+from|migrat\w+\s+from|switch\w+\s+from|mov\w+\s+from|"
    r"came?\s+from|went\s+from|was\s+(?:on|using|running)|previously\s+(?:on|using|had|ran)|"
    r"prior\s+version|old(?:er)?\s+version|before\s+(?:updating|installing|the\s+update|upgrad\w+))"
    r"\s+(?:to\s+)?(?:version\s+)?(?:2\d(?:0[1-9]|1[0-2]))\b",
    re.I,
)


def _strip_historical(text: str) -> str:
    """Blank out historical/upgrade-source version phrases so only the version the report is
    actually ABOUT is considered for multi-version ambiguity."""
    return HISTORICAL_SOURCE_RE.sub(" ", text or "")


# --- channel / build / issue gates ---------------------------------------------

def channel_reason(text: str) -> str | None:
    """Reject reports explicitly tied to a channel that conflicts with the record's Current
    Channel identity. A Current-Channel mention or no channel mention passes. (All current
    PowerPoint records are Current Channel, and one Version YYMM maps to one Current-Channel
    build, so a bare version is not channel-ambiguous.)"""
    if CURRENT_CHANNEL_PREVIEW_RE.search(text or ""):
        return "channel_conflict"  # Current Channel (Preview) is a distinct channel
    current = bool(CURRENT_CHANNEL_RE.search(text or ""))
    if CONFLICTING_CHANNEL_RE.search(text or "") and not current:
        return "channel_conflict"
    if STORE_RE.search(text or "") and not current:
        return "store_identity_unmapped"
    return None


def build_check(text: str, target_build: str) -> tuple[str | None, bool]:
    """Full-build cross-check. Returns (exclusion_reason_or_None, build_matched).

    ONE build named: the report has nothing to disambiguate, so it matches the target or it does
    not -- exactly as before the role classifier existed.

    SEVERAL builds named: which one the report is ABOUT decides, and only the author's own explicit
    language may say. "On 2607 (Build A) it crashes, I rolled back to Build B and it works" names A
    as current and B as previous; the report is about A. Previously any named build satisfying the
    target was enough, so that report also counted as evidence for B -- a build its author said was
    WORKING. Now the target must be the build shown current/failing.

    If no build is named, ``build_matched`` is False and the caller refuses the report with
    ``missing_exact_build`` -- the exact build is a prerequisite for counted evidence, not a bonus.
    If several are named and none is deterministically shown current, the report also carries no
    usable build: ``missing_exact_build`` again, which is what makes it eligible for same-segment
    context resolution rather than silently accepted or silently mismatched."""
    claims = extract_build_claims(text or "")
    if not claims:
        return None, False
    target = str(target_build or "").strip()

    named = single_named_build(claims)
    if named:
        return (None, True) if target and named == target else ("build_mismatch", False)

    selected, _basis, _refusal = select_current_failing_build(claims)
    if not selected:
        return None, False
    return (None, True) if target and selected == target else ("build_mismatch", False)


def concrete_issue(text: str) -> bool:
    """A concrete post-install PowerPoint problem, not a how-to/feature-location/announcement.

    A feature-location ("can't find the compare function", "where did X go", "missing menu") or a
    how-to/feature-request question counts ONLY when it also carries deterministic regression
    evidence tying the change to the exact patch (worked before / disappeared after installing /
    broke after the update) — otherwise it is not a post-install regression (Part C)."""
    text = text or ""
    strong = bool(POWERPOINT_ISSUE_RE.search(text))
    regression = bool(REGRESSION_EVIDENCE_RE.search(text))
    if FEATURE_LOCATION_RE.search(text) and not (strong or regression):
        return False
    if HOW_TO_OR_FEATURE_RE.search(text) and not (strong or regression):
        return False
    if not (strong or regression or text_describes_issue(text)):
        return False
    return True


# --- theme classification (deterministic; no AI) -------------------------------

def classify(text: str) -> tuple[str, str, str, str, str]:
    lowered = (text or "").lower()
    if any(t in lowered for t in ("corrupt", "damaged", "data loss", "lost my work", "lost slides", "lost changes")):
        return "file corruption / data loss", "file integrity", "windows", "critical", "negative"
    if "can't save" in lowered or "cannot save" in lowered or "save fail" in lowered or "unable to save" in lowered:
        return "save failure", "save / storage", "windows", "high", "negative"
    if any(t in lowered for t in ("won't open", "wont open", "cannot open", "can't open", "fails to open", "won't launch", "won't start", "fails to launch")):
        return "launch / open failure", "startup", "windows", "high", "negative"
    if "slideshow" in lowered or "slide show" in lowered or "presenter view" in lowered:
        return "slideshow failure", "presenting", "windows", "high", "negative"
    if "export" in lowered:
        return "export failure", "export", "windows", "high", "negative"
    if "animation" in lowered or "transition" in lowered:
        return "animation / transition regression", "animation", "windows", "medium", "negative"
    if "add-in" in lowered or "add in" in lowered or "addin" in lowered:
        return "add-in incompatibility", "add-ins", "windows", "medium", "negative"
    if "render" in lowered or "display" in lowered or "blank slide" in lowered:
        return "rendering regression", "rendering", "windows", "medium", "negative"
    if any(t in lowered for t in ("slow", "lag", "performance", "high cpu", "memory leak")):
        return "performance regression", "performance", "windows", "medium", "negative"
    if "install" in lowered or "update fail" in lowered:
        return "install/update failure", "update", "windows", "high", "negative"
    if any(t in lowered for t in ("crash", "freeze", "hang", "not responding")):
        return "crash or hang", "system stability", "windows", "high", "negative"
    return "unspecified PowerPoint issue", "PowerPoint workflow", "windows", "medium", "negative"


# --- ordered, deterministic acceptance -----------------------------------------

def powerpoint_reason(target: dict[str, Any], source_url: str, source_date: str, parent_title: str, report_title: str, report_body: str, declared_host: str = "") -> tuple[str | None, str, bool]:
    """Ordered acceptance for a PowerPoint candidate. Returns
    (exclusion_reason_or_None, match_basis, build_matched).

    ``target`` = the record identity (update_version / target_build / target_channel /
    target_release_date). ``parent_title``/``report_title`` are the thread title (used for
    reply-inheritance); ``report_body`` is the reply/description text (used for drift)."""
    version = str(target.get("update_version") or "").strip()
    target_build = str(target.get("target_build") or "").strip()
    target_release_date = str(target.get("target_release_date") or "").strip()
    title_text = f"{parent_title} {report_title}".strip()
    combined = f"{title_text}\n{report_body}".strip()

    match_basis = "no_exact_version"
    build_matched = False

    # 1. Specific report URL (search/category/landing pages are rejected).
    if not source_url_is_specific(source_url):
        return "no_specific_source_url", match_basis, build_matched
    # 2. Title-anchored announcement / official note (Part B). Runs BEFORE product/version so an
    #    official release post is rejected as an announcement even when it names another suite/app
    #    and even when its body carries incidental issue vocabulary (crash/bug/error/fix/issue).
    if ANNOUNCEMENT_TITLE_RE.search(title_text):
        return "official_announcement_not_user_report", match_basis, build_matched
    # 3. Product primacy (Part A) — PowerPoint must be the titled subject; another Office app as the
    #    title subject (or a multi-application title) fails closed. A body-only mention never counts.
    primacy = product_primacy_reason(parent_title, report_title, report_body, declared_host)
    if primacy:
        return primacy, match_basis, build_matched
    # 4. Official announcement / release note phrased only in the body (not a user report).
    if ANNOUNCE_OR_NOTE_RE.search(combined) and not concrete_issue(combined):
        return "official_announcement_not_user_report", match_basis, build_matched

    # 5. Exact version attribution (single-subject, with inheritance + drift/multi-version guards).
    target_in_context = version_in_context(combined, version, target_build)
    target_in_title = version_in_context(title_text, version, target_build)
    target_in_body = version_in_context(report_body, version, target_build)
    # Other in-context versions, ignoring any named only as a historical/upgrade source, so
    # "upgraded from 2407 to 2410" is attributable to 2410 only and never counts for 2407 (Part D).
    other_versions = versions_in_context(_strip_historical(combined)) - {version}
    other_in_body = versions_in_context(_strip_historical(report_body)) - {version}
    other_in_title = versions_in_context(_strip_historical(title_text)) - {version}
    if not target_in_context:
        if other_versions:
            return "different_version_not_target", match_basis, build_matched
        if _bare_version_present(combined, version):
            return "bare_version_no_context", match_basis, build_matched
        if LATEST_RE.search(combined):
            return "vague_latest_update", match_basis, build_matched
        return "missing_powerpoint_version", match_basis, build_matched
    # A version-only attribution must name EXACTLY ONE Version YYMM (the target). If the report
    # also names another version in context, which patch it is about is ambiguous — UNLESS an
    # exact matching build is present to disambiguate it. Fail closed (precision over recall).
    if other_versions and not build_check(combined, target_build)[1]:
        if not target_in_title and other_in_title:
            return "different_version_in_title", match_basis, build_matched
        if target_in_title and other_in_body and not target_in_body:
            return "reply_drifted_to_other_version", match_basis, build_matched
        return "ambiguous_multiple_versions", match_basis, build_matched
    match_basis = "exact_version_current_channel"

    # 5b. Source-content integrity (Part E) — when the exact version was established ONLY from a
    #     visibly truncated snippet body (no full-thread hydration is fetched), the missing context
    #     could flip the meaning, so fail closed rather than accept on partial content. A version in
    #     the title/parent (self-contained) or a complete snippet is unaffected.
    if not target_in_title and snippet_truncated(report_body):
        return "insufficient_source_content", match_basis, build_matched

    # 6. Channel consistency.
    channel = channel_reason(combined)
    if channel:
        return channel, match_basis, build_matched
    # 7. Exact-build gate. A stated build must match target_build; a report that states none
    #    is refused below, because the canonical patch identity includes the build.
    build_reason, build_matched = build_check(combined, target_build)
    if build_reason:
        return build_reason, match_basis, build_matched
    if build_matched:
        match_basis = "exact_version_channel_build"
    elif is_build_aware(PRODUCT_ID):
        # Canonical PowerPoint patch identity is (product_id, update_version, target_build).
        # A report that names only the YYMM therefore does NOT identify a patch, even when
        # AUXSAYS happens to track a single build under that version today: stamping this
        # record's build onto it would manufacture exact-build evidence by inference, and the
        # next build released under the same YYMM would retroactively make that attribution
        # wrong. Fail closed -- the report must state the exact build itself.
        return "missing_exact_build", match_basis, build_matched
    elif target.get("version_ambiguous"):
        # Exact-patch ambiguity: two or more tracked PowerPoint records share this exact
        # Version YYMM on a compatible channel, so a version-only report cannot deterministically
        # identify which patch it is about. Fail closed — an exact matching build (or another
        # deterministic unique identity) is required. Report-date proximity is NEVER used to pick
        # between the candidate builds. Parent-title inheritance obeys the same rule (this gate
        # runs regardless of where the version was found).
        return "ambiguous_version_needs_build", match_basis, build_matched
    # 8. Date gate — on/after release; pre-release/undated rejected.
    if source_date_passes(source_date, target_release_date) is False:
        return "date_before_release_or_undated", match_basis, build_matched
    # 9. Concrete post-install issue (feature-location/how-to require regression evidence).
    if not concrete_issue(combined):
        return "not_a_concrete_powerpoint_issue", match_basis, build_matched
    return None, match_basis, build_matched


def row_from_candidate(record: PatchRecord, target: dict[str, Any], candidate: dict[str, Any], captured_at: str) -> dict[str, Any]:
    parent_title = str(candidate.get("parent_title") or "")
    report_title = str(candidate.get("report_title") or "")
    report_body = str(candidate.get("report_text") or "")
    combined = f"{parent_title} {report_title}\n{report_body}".strip()
    source_url = str(candidate.get("source_url") or "")
    source_date = date_part(candidate.get("source_date"))
    target_release_date = date_part(target.get("target_release_date") or record.update_published_at)
    version = str(target.get("update_version") or record.update_version).strip()

    reason, match_basis, build_matched = powerpoint_reason(
        target, source_url, source_date, parent_title, report_title, report_body,
        str(candidate.get("github_declared_host") or ""),
    )
    version_matched = version_in_context(combined, version, str(target.get("target_build") or ""))
    matched_version = version if version_matched else ""
    theme, workflow_area, platform, severity, sentiment = classify(combined)

    row = make_evidence_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        source_type=str(candidate.get("source_type") or LEARN_QNA_SOURCE_TYPE),
        source_name=str(candidate.get("source_name") or LEARN_QNA_SOURCE_NAME),
        source_url=source_url,
        parent_title=parent_title,
        report_title=str(candidate.get("report_title") or ""),
        report_text=str(candidate.get("report_text") or ""),
        captured_at=captured_at,
        source_date=source_date,
        target_release_date=target_release_date,
        patch_version_matched=version_matched,
        matched_version=matched_version,
        match_basis=match_basis,
        counted=False,
        exclusion_reason=None,
        applicability="microsoft-powerpoint",
        issue_theme=theme,
        workflow_area=workflow_area,
        platform=platform,
        severity=severity,
        sentiment=sentiment,
        row_id=f"{PRODUCT_ID}-{slug(record.update_version)}-{slug(str(candidate.get('source_type') or LEARN_QNA_SOURCE_TYPE))}-{slug(source_url)}",
    )
    row["counted"] = reason is None
    row["exclusion_reason"] = reason
    # Durable exact-build attribution. Set ONLY from the build this report actually named and
    # that matched the target (build_matched); never copied from the record just because the
    # YYMM lined up. A row that did not name the exact build carries no build and therefore
    # cannot be counted as exact-build evidence downstream.
    row["target_build"] = str(target.get("target_build") or "").strip() if build_matched else ""
    return row


def evaluate_candidates(record: PatchRecord, target: dict[str, Any], candidates: list[dict[str, Any]], captured_at: str, seen: set[str] | None = None, run_accepted_urls: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate candidates for one record.

    ``seen`` is a per-record canonical-URL set that de-duplicates the SAME URL across methods
    within this record (cross-method dedup). ``run_accepted_urls`` is a run-wide map of
    canonical-URL -> canonical PATCH IDENTITY that enforces cross-PATCH exclusivity (Part D): a single report URL
    may be attributed to at most one PowerPoint version across the whole run. The two are separate
    (cross-method dedup vs cross-version exclusivity)."""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen = seen if seen is not None else set()
    for candidate in candidates:
        url = str(candidate.get("source_url") or "").strip().rstrip("/")
        key = url.lower()
        if not url or key in seen:
            continue  # per-record cross-method canonical-URL dedup
        seen.add(key)
        row = row_from_candidate(record, target, candidate, captured_at)
        # Cross-version exclusivity: if this canonical URL was already accepted for a DIFFERENT
        # version in this run, reject the later attribution as a cross-version duplicate.
        if row.get("counted") is True and run_accepted_urls is not None:
            # Exclusivity is per exact PATCH, not per YYMM. Two PowerPoint builds can share a
            # version, so comparing versions alone would let one report URL be attributed to BOTH
            # builds -- two distinct patches -- in a single run. Compare the canonical patch
            # identity instead. (The exact-build acceptance gate already makes this hard to reach;
            # this keeps the exclusivity contract itself correct rather than relying on that.)
            identity = "|".join(patch_key(record.product_id, record.update_version,
                                          row.get("target_build")))
            prior = run_accepted_urls.get(key)
            if prior is not None and prior != identity:
                row["counted"] = False
                row["exclusion_reason"] = "cross_version_duplicate"
            else:
                run_accepted_urls[key] = identity
        (accepted if row.get("counted") is True else rejected).append(row)
    return accepted, rejected


# --- record target + queries -------------------------------------------------

# Hard per-record bound on Learn Q&A search requests (Part F cost control). Each term is one
# search-RSS request; the shared source hydrates content from the RSS item (no per-thread fetch)
# and de-duplicates by canonical URL, so total requests per full run = MAX_QUERIES_PER_RECORD x
# (records selected). No pagination, no per-candidate hydration, no retry multiplier.
MAX_QUERIES_PER_RECORD = 3


def _norm_channel(channel: str) -> str:
    return re.sub(r"\s+", " ", str(channel or "").strip().lower())


def compute_ambiguous_identities(records: list[PatchRecord]) -> set[tuple[str, str]]:
    """Return the set of (version, normalized-channel) identities carried by MORE THAN ONE
    tracked PowerPoint record. Computed from the ACTUAL tracked record set (never a hardcoded
    list): a Version YYMM on a given channel is ambiguous only when two or more records claim
    it, in which case a version-only community report cannot be attributed to a single patch."""
    counts: dict[tuple[str, str], int] = {}
    for record in records:
        target = record_target(record)
        key = (target["target_app_version"] or target["update_version"], _norm_channel(target["target_channel"]))
        counts[key] = counts.get(key, 0) + 1
    return {key for key, count in counts.items() if count > 1}


def record_target(record: PatchRecord) -> dict[str, Any]:
    front, _body = load_front_matter_and_body(record.path)
    return {
        "update_version": str(front.get("update_version") or record.update_version).strip(),
        "target_app_version": str(front.get("target_app_version") or front.get("update_version") or "").strip(),
        "target_build": str(front.get("target_build") or "").strip(),
        "target_channel": str(front.get("target_channel") or "").strip(),
        "target_release_date": str(front.get("update_published_at") or record.update_published_at or "").strip(),
    }


def search_query_terms(target: dict[str, Any]) -> list[str]:
    """Exact-version discovery terms (hard-capped at MAX_QUERIES_PER_RECORD). The version is
    searched with product/version context so the RSS surfaces PowerPoint threads that name the
    exact patch. The build is also searched: it is part of this product's patch identity, and a
    report that never names it cannot become counted evidence."""
    version = str(target.get("update_version") or "").strip()
    terms: list[str] = []
    if version:
        terms.append(f"PowerPoint {version}")
        terms.append(f"PowerPoint Version {version}")
    build = str(target.get("target_build") or "").strip()
    if version and build:
        terms.append(f"PowerPoint {build}")
    return terms[:MAX_QUERIES_PER_RECORD]


# SYMPTOM-FIRST discovery terms. Identity-first search cannot find the reports that matter most:
# a user titles their thread with what broke, not with a build number, and often supplies the build
# only when asked. Measured against the live index: the 67 identity queries this collector issues
# across all 25 PowerPoint records returned 6591 items and 2199 distinct threads, and a real
# PowerPoint Copilot failure report was in NONE of them -- its title is "Copilot Unable to Read
# Document Error", which contains neither "PowerPoint" nor any version, and its build sits in a
# comment the search index does not cover. A symptom query returns it immediately.
#
# Recall and precision are separate stages: these terms only widen what is LOOKED AT. Every
# candidate still faces the unchanged acceptance authority, which decides identity on its own.
# Ordered by MEASURED reach against the live index, not by guesswork. "PowerPoint Copilot error"
# returns the Copilot failure thread that identity search cannot reach; it sat below an earlier
# 3-query cap and was silently never issued, which is exactly the kind of unmeasured truncation
# that makes a widened funnel look like it did not help.
SYMPTOM_QUERY_TERMS = (
    "PowerPoint Copilot error",
    "PowerPoint crash after update",
    "PowerPoint not responding update",
    "PowerPoint slideshow problem after update",
    "PowerPoint save export fails",
)
MAX_SYMPTOM_QUERIES = 5


# Symptom queries are PRODUCT-level: they carry no version or build, so every record in a run would
# otherwise issue the identical searches and pay for them 25 times over. The results are cached for
# the process, which is the natural scope of one collection run. Identity-first queries are NOT
# cached -- those genuinely differ per record.
_SYMPTOM_CACHE: dict[str, list[dict[str, Any]]] = {}


def reset_symptom_cache() -> None:
    """Drop the per-run symptom cache.

    The cache's correct lifetime is ONE collection run: results are product-level, but they are
    still a point-in-time view of the index. A long-lived process (the orchestration graph, a test
    session) must not serve one run's discoveries to the next.
    """
    _SYMPTOM_CACHE.clear()


def cached_product_candidates(namespace: str, key_parts: list[str], produce):
    """Memoise a PRODUCT-level discovery route for the lifetime of one run.

    Record-level routes (a specific build token) must run per record. Product-level routes -- the
    symptom queries, the PowerPoint tag route -- return the same result for all 25 records, so
    issuing them per record burns 25x the API budget for identical answers. That is not theoretical:
    the merged run drained GitHub's search allowance to `blocked` on two records this way.
    """
    key = namespace + "::" + " | ".join(key_parts)
    hit = _SYMPTOM_CACHE.get(key)
    if hit is not None:
        return list(hit)
    found = produce()
    _SYMPTOM_CACHE[key] = list(found)
    return found


def cached_symptom_candidates(queries: list[str], context: CollectorContext,
                              errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key = " | ".join(queries)
    hit = _SYMPTOM_CACHE.get(key)
    if hit is not None:
        return list(hit)
    found = learn_qna.collect_learn_qna_candidates(
        queries=queries, context=context, errors=errors,
        source_type=LEARN_QNA_SOURCE_TYPE, source_name=LEARN_QNA_SOURCE_NAME)
    _SYMPTOM_CACHE[key] = list(found)
    return found


def symptom_query_terms() -> list[str]:
    """Product-level symptom terms, independent of any one record's identity.

    Deliberately NOT version-parameterised: the whole point is to reach threads that never state a
    version in indexed text. Bounded so a widened funnel cannot become an unbounded request budget.
    """
    return list(SYMPTOM_QUERY_TERMS[:MAX_SYMPTOM_QUERIES])


# --- method health -----------------------------------------------------------

NEAR_MISS_REASONS = {"bare_version_no_context", "different_version_not_target", "build_mismatch", "channel_conflict", "reply_drifted_to_other_version", "insufficient_source_content"}


def rejection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("exclusion_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def format_rejection_counts(rows: list[dict[str, Any]]) -> str:
    return ", ".join(f"{reason}={count}" for reason, count in sorted(rejection_counts(rows).items()))


def learn_qna_method_status(candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if accepted:
        return "partial" if errors else "success"
    if errors and (candidates or rejected):
        return "partial"
    if errors:
        if any("feed_parse_failed" in str(e.get("reason") or "") or str(e.get("blocked_signature")) == "broken" for e in errors):
            return "broken"
        return "blocked"
    # Reachable, nothing accepted. "low_confidence" when relevant-looking PowerPoint threads
    # were found but narrowly missed attribution; plain "no_results" otherwise.
    if rejected and any(str(r.get("exclusion_reason")) in NEAR_MISS_REASONS for r in rejected):
        return "low_confidence"
    return "no_results"


def reddit_method_status(attempted: bool, candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if not attempted:
        return "disabled"
    if accepted:
        return "partial" if errors else "success"
    if errors and not candidates:
        return "blocked"
    if errors:
        return "partial"
    return "no_results"


def blocked_reason_from_errors(errors: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for error in errors:
        reason = str(error.get("reason") or "fetch_failed")
        counts[reason] = counts.get(reason, 0) + 1
    return "; ".join(f"{reason} x{count}" if count > 1 else reason for reason, count in counts.items())


def health_row(record: PatchRecord, method_id: str, source_type: str, status: str, candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]], captured_at: str, notes: str) -> dict[str, Any]:
    return method_health_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        # Health is per exact patch: 2603/build-A learn_qna=success and 2603/build-B
        # learn_qna=blocked are two different facts and must not overwrite one another.
        target_build=record.target_build,
        method_id=method_id,
        source_type=source_type,
        status=status,
        candidates_found=len(candidates),
        accepted_reports=len(accepted),
        rejected_reports=len(rejected),
        blocked_reason=blocked_reason_from_errors(errors),
        last_run=captured_at,
        notes=notes,
    )


# --- collection --------------------------------------------------------------

def reddit_fallback_enabled(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(REDDIT_FALLBACK_ENV, "")).strip().lower() == "true"


def run_primary_method(record: PatchRecord, target: dict[str, Any], context: CollectorContext, seen: set[str], run_accepted_urls: dict[str, str] | None, captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """PRIMARY — Microsoft Learn Q&A (proven CI-reachable, keyless).

    Extracted from collect_for_record so the orchestration control plane can invoke exactly the
    production method path; collect_for_record composes this same function. Acceptance gates are
    unchanged and identical for every method."""
    # Identity-first terms find threads that state the patch; symptom-first terms find the ones
    # whose author described what broke instead. Both feed the same unchanged acceptance authority.
    identity_terms = search_query_terms(target)
    symptom_terms = symptom_query_terms()
    query_terms = identity_terms + symptom_terms
    lq_errors: list[dict[str, Any]] = []
    lq_candidates: list[dict[str, Any]] = []
    if identity_terms:
        lq_candidates = learn_qna.collect_learn_qna_candidates(
            queries=identity_terms,
            context=context,
            errors=lq_errors,
            source_type=LEARN_QNA_SOURCE_TYPE,
            source_name=LEARN_QNA_SOURCE_NAME,
        )
    if symptom_terms:
        lq_candidates = lq_candidates + cached_symptom_candidates(symptom_terms, context, lq_errors)
    lq_accepted, lq_rejected = evaluate_candidates(record, target, lq_candidates, captured_at, seen, run_accepted_urls)
    lq_status = learn_qna_method_status(lq_candidates, lq_accepted, lq_rejected, lq_errors)
    lq_notes = (
        "Microsoft Learn Q&A search RSS (learn.microsoft.com/api/search/rss) for microsoft-powerpoint. "
        f"Searched: {', '.join(query_terms) if query_terms else 'none (record missing version)'}. "
        f"Candidates {len(lq_candidates)}, accepted {len(lq_accepted)}, rejected {len(lq_rejected)}. "
        + (f"Top rejections: {format_rejection_counts(lq_rejected)}. " if lq_rejected else "")
        + "Counts only when the report names PowerPoint, the exact Version YYMM in context, is Current-Channel-consistent, "
        "carries no conflicting build, has a specific URL, is dated on/after release, and describes a concrete issue."
    )
    row = health_row(record, LEARN_QNA_METHOD_ID, LEARN_QNA_SOURCE_TYPE, lq_status, lq_candidates, lq_accepted, lq_rejected, lq_errors, captured_at, lq_notes)
    return lq_accepted, lq_rejected, row


def run_fallback_method(record: PatchRecord, target: dict[str, Any], context: CollectorContext, seen: set[str], run_accepted_urls: dict[str, str] | None, captured_at: str, attempted: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """FALLBACK — Reddit (documented CI-blocked, PR #23).

    ``attempted`` is the production capability gate decision (reddit_fallback_enabled); when
    False the method is honestly reported as "disabled" and nothing is fetched. Same acceptance
    gates as the primary, never weakened. Extracted from collect_for_record for the orchestration
    control plane; collect_for_record composes this same function."""
    query_terms = search_query_terms(target)
    rd_errors: list[dict[str, Any]] = []
    rd_candidates: list[dict[str, Any]] = []
    rd_accepted: list[dict[str, Any]] = []
    rd_rejected: list[dict[str, Any]] = []
    if attempted and query_terms:
        version = str(target.get("update_version") or "").strip()
        rd_candidates = reddit_source.collect_reddit_candidates(
            subreddits=REDDIT_SUBREDDITS,
            queries=[f"PowerPoint {version}", f"Version {version}"],
            context=context,
            errors=rd_errors,
            source_type=REDDIT_SOURCE_TYPE,
            version_hints=[version] if version else None,
        )
        rd_accepted, rd_rejected = evaluate_candidates(record, target, rd_candidates, captured_at, seen, run_accepted_urls)
    rd_status = reddit_method_status(attempted, rd_candidates, rd_accepted, rd_rejected, rd_errors)
    rd_notes = (
        f"Reddit community search across {', '.join('r/' + s for s in REDDIT_SUBREDDITS)}. "
        + ("Fallback disabled by default (documented CI-blocked, PR #23); enable with "
           f"{REDDIT_FALLBACK_ENV}=true. Not required for the pilot." if not attempted
           else f"Candidates {len(rd_candidates)}, accepted {len(rd_accepted)}, rejected {len(rd_rejected)}. Same acceptance gates as Learn Q&A.")
    )
    row = health_row(record, REDDIT_METHOD_ID, REDDIT_SOURCE_TYPE, rd_status, rd_candidates, rd_accepted, rd_rejected, rd_errors, captured_at, rd_notes)
    return rd_accepted, rd_rejected, row


def stack_exchange_method_status(candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if accepted:
        return "partial" if errors else "success"
    if errors and (candidates or rejected):
        return "partial"
    if errors:
        # A throttled source is capacity-limited, not broken; the distinction matters because a
        # "broken" method invites debugging an endpoint that is working perfectly well.
        return "blocked" if any("rate_limited" in str(e.get("reason") or "") for e in errors) else "broken"
    if rejected and any(str(r.get("exclusion_reason")) in NEAR_MISS_REASONS for r in rejected):
        return "low_confidence"
    return "no_results"


def run_stack_exchange_method(record: PatchRecord, target: dict[str, Any], context: CollectorContext, seen: set[str], run_accepted_urls: dict[str, str] | None, captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Stack Exchange (Super User + Stack Overflow), keyless official API.

    Two routes per site because they fail differently: the TAG route surfaces PowerPoint questions
    whose author never wrote a build, and the TEXT route finds an exact build token wherever it was
    written. Acceptance is the same unchanged authority used by every other method -- only discovery
    is new."""
    se_errors: list[dict[str, Any]] = []
    build = str(target.get("target_build") or "").strip()
    version = str(target.get("update_version") or "").strip()
    queries = [q for q in (build, f"PowerPoint {version}" if version else "") if q]
    # The tag route is product-level and identical for every record, so it runs ONCE per run; only
    # the build/version text routes are record-specific.
    se_candidates = list(cached_product_candidates(
        "stack_exchange_tag", sorted(STACK_EXCHANGE_SITES),
        lambda: stack_exchange_source.collect_stack_exchange_candidates(
            sites=list(STACK_EXCHANGE_SITES), queries=[], tags_by_site=dict(STACK_EXCHANGE_TAGS),
            errors=se_errors, max_requests=len(STACK_EXCHANGE_SITES),
            source_type=STACK_EXCHANGE_SOURCE_TYPE)))
    if queries:
        se_candidates += stack_exchange_source.collect_stack_exchange_candidates(
            sites=list(STACK_EXCHANGE_SITES), queries=queries, tags_by_site=None,
            errors=se_errors, max_requests=len(STACK_EXCHANGE_SITES) * len(queries),
            source_type=STACK_EXCHANGE_SOURCE_TYPE)
    _seen_se: set[str] = set()
    se_candidates = [c for c in se_candidates
                     if not (str(c.get("source_url") or "").rstrip("/").lower() in _seen_se
                             or _seen_se.add(str(c.get("source_url") or "").rstrip("/").lower()))]
    se_accepted, se_rejected = evaluate_candidates(record, target, se_candidates, captured_at, seen, run_accepted_urls)
    se_status = stack_exchange_method_status(se_candidates, se_accepted, se_rejected, se_errors)
    se_notes = (
        "Stack Exchange official API (api.stackexchange.com/2.3), keyless, across "
        + ", ".join(stack_exchange_source.SITE_NAMES.get(s, s) for s in STACK_EXCHANGE_SITES) + ". "
        f"Queried: {', '.join(queries) if queries else 'none (record missing version)'}; plus the PowerPoint tag route. "
        f"Candidates {len(se_candidates)}, accepted {len(se_accepted)}, rejected {len(se_rejected)}. "
        + (f"Top rejections: {format_rejection_counts(se_rejected)}. " if se_rejected else "")
        + "report_text is the QUESTION's own title and body only -- answers and comments are never "
        "folded in, so an answerer's build can never become the asker's patch identity. Same "
        "acceptance gates as Learn Q&A."
    )
    row = health_row(record, STACK_EXCHANGE_METHOD_ID, STACK_EXCHANGE_SOURCE_TYPE, se_status, se_candidates, se_accepted, se_rejected, se_errors, captured_at, se_notes)
    return se_accepted, se_rejected, row


def github_method_status(candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if accepted:
        return "partial" if errors else "success"
    if errors and (candidates or rejected):
        return "partial"
    if errors:
        return "blocked" if any("rate_limited" in str(e.get("reason") or "") for e in errors) else "broken"
    if rejected and any(str(r.get("exclusion_reason")) in NEAR_MISS_REASONS for r in rejected):
        return "low_confidence"
    return "no_results"


def canonicalise_github_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Reduce Office's 16.0.<build> full form to the canonical token, host permitting.

    lib.build_claims deliberately does not treat 16.0.<build> as a bare token, because that form
    appears in crash records whose AppName may be Word or Excel -- it becomes a claim only when
    the application is proven. An OfficeDev issue answering "Host: PowerPoint" beside its
    version field IS that proof, so the reduction is applied here, using the SHARED primitive,
    and only for a PowerPoint-declared host.
    """
    if str(candidate.get("github_declared_host") or "") != "powerpoint":
        return candidate
    # ONLY the reporter's declared DESKTOP version is reduced, prepended as its own statement.
    # Substituting across the whole body also reduced the WEB build (web: 16.0.20329.45605) to a
    # bare token, so the authority saw TWO builds and refused -- reintroducing exactly the
    # web/desktop confusion the desktop scoping exists to prevent. The body's remaining 16.0.
    # forms are deliberately left alone: as non-tokens they stay invisible to the build gate.
    desktop = str(candidate.get("github_desktop_version") or "").strip()
    if not desktop:
        return candidate
    # A crash record pasted into the version field is NOT a version declaration, and reducing it
    # would defeat the guard it exists for: lib.build_claims classifies 16.0.<build> governed by
    # a foreign AppName as reference_other, but a pre-reduced bare token reaches it as an
    # ordinary claim and an EXCEL.EXE crash version becomes PowerPoint patch evidence. Leave any
    # crash record raw and let the shared primitive apply its own AppName reasoning.
    if CRASH_RECORD_MARKER_RE.search(desktop):
        return candidate
    reduced = OFFICE_FULL_VERSION_RE.sub(lambda m: m.group(1), desktop)
    if reduced == desktop:
        return candidate
    text = str(candidate.get("report_text") or "")
    return {**candidate, "report_text": f"Office desktop version: {reduced}. {text}"}


def run_github_method(record: PatchRecord, target: dict[str, Any], context: CollectorContext, seen: set[str], run_accepted_urls: dict[str, str] | None, captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """OfficeDev/office-js issues, public GitHub API, read-only.

    Build-first uses the FULL Office form because the bare token matches nothing in GitHub search;
    symptom-first carries recall. The issue's structured `Host:` answer decides the product, and only
    the DESKTOP half of the version field can supply a Click-to-Run build."""
    gh_errors: list[dict[str, Any]] = []
    build = str(target.get("target_build") or "").strip()
    # Split by SCOPE, not convenience: the build query is record-specific, the symptom queries are
    # product-level and identical for all 25 records. Issuing all four per record sent ~75 of every
    # 100 search requests as exact duplicates and exhausted the 30/min allowance mid-run.
    build_queries = [f'repo:{github_officedev_source.REPO} "16.0.{build}"'] if build else []
    queries = build_queries + list(GITHUB_SYMPTOM_QUERIES)

    def _symptom_route():
        found, tel = github_officedev_source.collect_officedev_candidates(
            queries=list(GITHUB_SYMPTOM_QUERIES), errors=gh_errors,
            max_requests=len(GITHUB_SYMPTOM_QUERIES), source_type=GITHUB_SOURCE_TYPE)
        return [{"candidates": found, "telemetry": tel}]

    payload = cached_product_candidates("github_symptom", list(GITHUB_SYMPTOM_QUERIES),
                                        _symptom_route)[0]
    gh_candidates = list(payload["candidates"])
    telemetry = dict(payload["telemetry"])
    if build_queries:
        build_found, build_tel = github_officedev_source.collect_officedev_candidates(
            queries=build_queries, errors=gh_errors, max_requests=len(build_queries),
            source_type=GITHUB_SOURCE_TYPE)
        gh_candidates += build_found
        # Telemetry is the RUN's cost as this record saw it: the record-specific request is added to
        # the cached symptom cost, and the rate headers come from the most recent live call.
        for field in ("queries", "requests", "issues_discovered"):
            telemetry[field] = int(telemetry.get(field) or 0) + int(build_tel.get(field) or 0)
        telemetry["rate_remaining"] = build_tel.get("rate_remaining", telemetry.get("rate_remaining"))
        telemetry["rate_limit"] = build_tel.get("rate_limit", telemetry.get("rate_limit"))
    # Dedupe across the two routes: the same issue found by build AND symptom is ONE candidate.
    _seen_gh: set[str] = set()
    gh_candidates = [c for c in gh_candidates
                     if not (str(c.get("source_url") or "") in _seen_gh
                             or _seen_gh.add(str(c.get("source_url") or "")))]
    gh_candidates = [canonicalise_github_candidate(c) for c in gh_candidates]
    gh_accepted, gh_rejected = evaluate_candidates(record, target, gh_candidates, captured_at, seen, run_accepted_urls)
    gh_status = github_method_status(gh_candidates, gh_accepted, gh_rejected, gh_errors)
    gh_notes = (
        f"OfficeDev/office-js public GitHub issues API. Queries {telemetry.get('queries')}, "
        f"requests {telemetry.get('requests')}, issues discovered {telemetry.get('issues_discovered')}, "
        f"rate remaining {telemetry.get('rate_remaining')}/{telemetry.get('rate_limit')}. "
        f"Candidates {len(gh_candidates)}, accepted {len(gh_accepted)}, rejected {len(gh_rejected)}. "
        + (f"Top rejections: {format_rejection_counts(gh_rejected)}. " if gh_rejected else "")
        + "Product comes from the template's Host field, so an Excel issue stays Excel however often "
        "it says PowerPoint; only the desktop half of the Office version field can supply a build. "
        "Same acceptance gates as every other method."
    )
    row = health_row(record, GITHUB_METHOD_ID, GITHUB_SOURCE_TYPE, gh_status, gh_candidates, gh_accepted, gh_rejected, gh_errors, captured_at, gh_notes)
    return gh_accepted, gh_rejected, row


def collect_for_record(record: PatchRecord, context: CollectorContext, env: dict[str, str] | None = None, version_ambiguous: bool = False, run_accepted_urls: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    captured_at = utc_now()
    target = record_target(record)
    target["version_ambiguous"] = version_ambiguous
    seen: set[str] = set()

    lq_accepted, lq_rejected, lq_health = run_primary_method(record, target, context, seen, run_accepted_urls, captured_at)
    health = [lq_health]

    se_accepted, se_rejected, se_health = run_stack_exchange_method(record, target, context, seen, run_accepted_urls, captured_at)
    health.append(se_health)

    gh_accepted, gh_rejected, gh_health = run_github_method(record, target, context, seen, run_accepted_urls, captured_at)
    health.append(gh_health)

    rd_attempted = reddit_fallback_enabled(env)
    rd_accepted, rd_rejected, rd_health = run_fallback_method(record, target, context, seen, run_accepted_urls, captured_at, rd_attempted)
    health.append(rd_health)

    accepted = lq_accepted + se_accepted + gh_accepted + rd_accepted
    rejected = lq_rejected + se_rejected + gh_rejected + rd_rejected
    return accepted, rejected, health


class PowerPointLearnQnaCollector(ProductCollector):
    product_id = PRODUCT_ID

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        reset_symptom_cache()   # one run, one point-in-time view of the index
        records = generated_records(PRODUCT_ID, context.target_versions)
        # Exact-patch ambiguity is computed over the FULL tracked record set (unfiltered), so a
        # --update-version filter can never hide a sibling record that makes a version ambiguous.
        ambiguous = compute_ambiguous_identities(generated_records(PRODUCT_ID, None))
        # Run-wide canonical-URL -> version map: enforces cross-version exclusivity across every
        # record in this run (a single report URL is attributed to at most one PowerPoint version).
        run_accepted_urls: dict[str, str] = {}
        results: list[dict[str, Any]] = []
        for record in records:
            rec_target = record_target(record)
            version_ambiguous = (rec_target["target_app_version"] or rec_target["update_version"], _norm_channel(rec_target["target_channel"])) in ambiguous
            accepted, rejected, health = collect_for_record(record, context, version_ambiguous=version_ambiguous, run_accepted_urls=run_accepted_urls)
            result: dict[str, Any] = {
                "product_id": PRODUCT_ID,
                "version": record.update_version,
                "mode": "write" if context.write else "dry-run",
                "record_path": str(record.path.name),
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [row["source_url"] for row in accepted],
                "rejection_reasons": rejection_counts(rejected),
                "method_health": health,
            }
            if context.write:
                # Evidence-only pilot: append accepted rows; NEVER change the PowerPoint
                # record's verdict / consensus fields here (activation is a separate step).
                added, total, _rows = append_evidence_rows(accepted)
                result.update({"evidence_rows_added": added, "evidence_rows_total": total})
            results.append(result)
        return results


def _dry_run_main(argv: list[str] | None = None) -> int:
    """Read-only local dry-run entry point. Hardcodes write=False, so this can NEVER write
    evidence or generated records — it only fetches Learn Q&A and prints diagnostics."""
    import argparse
    import json
    from datetime import datetime, timedelta, timezone

    parser = argparse.ArgumentParser(description="PowerPoint Learn Q&A collector — read-only dry-run (no writeback).")
    parser.add_argument("--update-version", action="append", help="Exact PowerPoint update_version filter (e.g. 2605). Repeatable.")
    parser.add_argument("--since-days", type=int, help="Optional source-date lower bound relative to today.")
    parser.add_argument("--max-pages", type=int, default=1)
    args = parser.parse_args(argv)

    since = None
    if args.since_days is not None:
        since = (datetime.now(timezone.utc) - timedelta(days=max(0, args.since_days))).date().isoformat()
    context = CollectorContext(
        write=False,  # hardcoded: this entry point can never write
        since=since,
        max_pages=args.max_pages,
        target_versions=set(args.update_version) if args.update_version else None,
    )
    results = PowerPointLearnQnaCollector().collect(context)
    print(json.dumps({"mode": "dry-run", "write": False, "products": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_dry_run_main())
