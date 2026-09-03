"""Shared Adobe Acrobat (Reader + Acrobat Pro) COMMUNITY-EVIDENCE collector.

One config-driven `ProductCollector` serves BOTH editions. It is registered per edition
(`AdobeAcrobatCollector(READER_ID)` and `(PRO_ID)`), so each instance discovers, filters,
and writes evidence for exactly one `product_id`. Because consensus writeback is keyed by
`(product_id, update_version)`, Reader and Pro (which share the same DC build number) can
NEVER cross-contaminate.

Doctrine (fail-closed, deterministic, no AI/manual dependency):
- Multi-method discovery: Adobe Community search (HTML) + Reddit (shared `reddit_source`).
  Each method emits diagnosable method health; a blocked method degrades and the run
  continues.
- A community report counts ONLY when it passes, in order: exact-edition attribution →
  exact current DC-build version match → specific thread/post URL → source date on/after
  the official release date → a concrete post-install user-facing issue → not an official
  announcement/release-note. Every gate failure records a precise `exclusion_reason`.
- Edition attribution never guesses: bare "Acrobat"/"Adobe Acrobat"/"PDF app"/bare "Reader"
  fail closed; the opposite edition is `wrong_product`; only an explicit both-editions report
  counts for both (with explicit `applicability`).
- Official ingestion / release notes are NEVER counted as community evidence.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError

from . import reddit_source
from . import runtime_budget as rb
from lib.target_outcome import (
    AFFECTED as OUTCOME_AFFECTED,
    classify_target_outcome,
    target_is_contradicted,
)

# Active RuntimeBudget for the collector currently running (set by AdobeAcrobatCollector.collect). Safe as
# a module global because collectors run strictly serially (no concurrent repository writes / requests).
_ACTIVE_BUDGET: Any = None


def acrobat_version_aliases(version: str) -> tuple[str, ...]:
    """Other spellings of THIS build that mean the same build, and nothing else.

    Acrobat's Help > About dialog shows the year-prefixed form -- 2026.001.21789 for the build the
    release notes call 26.001.21789 -- and that is the string admins copy verbatim into a post. The
    matcher saw two different versions and refused the report. This is a spelling alias, not a
    loosening: the trailing build number must still be exactly this record's.
    """
    text = str(version or "").strip()
    match = re.fullmatch(r"(\d{2})(\.\d{3}\.\d{4,6})", text)
    return (f"20{match.group(1)}{match.group(2)}",) if match else ()


def record_applicability(record: Any) -> tuple[str, ...]:
    """The editions Adobe ships THIS build to, as the record itself states.

    Read from the record's front matter rather than assumed: the Acrobat adapter derives
    `applicability` from the release-note text and narrows it when Adobe says an update is
    edition-specific. Falling back to an EMPTY tuple matters -- a record that does not declare
    shared applicability gets no shared-build attribution at all.
    """
    try:
        data, _body = load_front_matter_and_body(record.path)
    except Exception:
        return ()
    declared = data.get("applicability")
    if not isinstance(declared, list):
        return ()
    return tuple(str(item).strip() for item in declared if str(item).strip())



# Acrobat STANDARD named as the product the reporter is running. Requires a product-ish context
# ("updating to Acrobat Standard 26.x", "Acrobat Standard crashes"), so a licensing sentence like
# "signs in with a Pro or Standard license" is untouched -- that is a different claim.
_STANDARD_PRODUCT_RE = re.compile(
    r"\b(?:adobe\s+)?acrobat\s+standard\b(?!\s+licen)", re.I)


def _tracked_builds_named(text: str, product_id: str, target: str) -> set[str]:
    """Every build AUXSAYS tracks for this product that appears in the report.

    Deliberately scoped to TRACKED builds rather than anything version-shaped: a post is full of
    numbers -- dates, error codes, OS versions -- and only a real patch identity should make a
    report ambiguous about which patch it is about.
    """
    found = {str(target or "").strip()} if str(target or "").strip() in (text or "") else set()
    for record in generated_records(product_id):
        version = str(record.update_version or "").strip()
        if version and version in (text or ""):
            found.add(version)
    return found

def _newest_first(records: list[Any]) -> list[Any]:
    """Most recently released patch first.

    `generated_records` returns the corpus sorted by FILENAME, and every filename is date-prefixed,
    so the natural order is oldest-first: 2015 before 2026. This collector is bounded by a
    wall-clock budget and stops mid-corpus when it expires, so oldest-first meant it re-scraped
    2015-2017 patches on every run and never reached the current ones. Measured before this change:
    44 of the 48 Acrobat records released since 2025-12-01 had NEVER been attempted by any method,
    and the situation was getting worse, because each backfilled historical record inserts AHEAD of
    the recent tail.

    Reversing the order does not create budget, it spends it where a reader is actually looking.
    Old records keep whatever remains, and they are the ones that already carry evidence.
    Deterministic: ties break on version so two runs walk the same order.
    """
    return sorted(records,
                  key=lambda r: (str(getattr(r, "update_published_at", "") or ""),
                                 str(getattr(r, "update_version", "") or "")),
                  reverse=True)


def _retired_methods_enabled() -> bool:
    """Re-enable the two blocked fallback methods, for a one-off reachability re-test.

    Off by default. A transport that is blocked from CI today may not be tomorrow, and the way to
    find out is a deliberate probe, not a permanent tax on every record of every run.
    """
    import os  # noqa: PLC0415
    return str(os.environ.get("AUXSAYS_ACROBAT_RETIRED_METHODS") or "").strip().lower() in {
        "1", "true", "yes", "on"}


# This module IS the Acrobat safety authority the tiering adapter re-applies. Passing it in by
# reference keeps the rules in one place -- a second copy inside lib/ would be free to drift.
_SAFETY: Any = None


def _set_active_budget(budget: Any) -> None:
    global _ACTIVE_BUDGET
    _ACTIVE_BUDGET = budget
from .base import (
    CollectorContext,
    EVIDENCE_PATH,
    PatchRecord,
    ProductCollector,
    ROOT,
    append_evidence_rows,
    counted_rows,
    date_part,
    exact_version_match,
    generated_records,
    load_front_matter_and_body,
    make_evidence_row,
    method_health_row,
    slug,
    source_url_is_specific,
    utc_now,
)

READER_ID = "adobe-acrobat-reader"
PRO_ID = "adobe-acrobat-pro"
ACROBAT_PRODUCT_IDS = (READER_ID, PRO_ID)

# The two published tier files. Per-product, deliberately: cross-product isolation would
# otherwise rest on a Liquid `where` filter, and that filter has already failed silently once
# via Float coercion of a numeric-looking key.
TIER2_PATH = ROOT / "_data" / "acrobat_update_linked_evidence.yml"
TIER3_PATH = ROOT / "_data" / "recent_acrobat_reports.yml"

ADOBE_COMMUNITY_SOURCE_TYPE = "adobe_community_bug_report"
REDDIT_SOURCE_TYPE = "reddit_community_report"

ADOBE_SEARCH_URL = (
    "https://community.adobe.com/t5/forums/searchpage/tab/message"
    "?advanced=false&allow_punctuation=false&q={query}&page={page}"
)
# --- inSided/Algolia keyless JSON discovery (reachable from CI; the /t5 HTML search
#     endpoint above is CloudFront-blocked from datacenter IPs, but these JSON endpoints
#     are not). searchToken issues an anonymous, secured Algolia search key; the Algolia
#     query returns thread hits (topic id + title + body + date); getTopics returns the
#     authoritative canonical URL + full first-post content for a batch of topic ids.
ADOBE_SEARCH_TOKEN_URL = "https://community.adobe.com/search/searchToken"
ADOBE_GET_TOPICS_URL = "https://community.adobe.com/search/getTopics"
ALGOLIA_QUERY_URL_TMPL = "https://{app_id}-dsn.algolia.net/1/indexes/{index}/query"
MAX_ALGOLIA_QUERIES = 3
MAX_ALGOLIA_HITS_PER_QUERY = 8
MAX_TOPICS_PER_RECORD = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AUXSAYS-patch-intelligence/1.0; +https://auxsays.com)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}
JSON_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}
MAX_SEARCH_QUERIES = 3
MAX_SEARCH_PAGES = 1

# --- edition attribution (never inferred) ------------------------------------
# Explicit product names PLUS the unambiguous macOS bundle identifiers that appear in
# crash logs (com.adobe.Acrobat.Pro == Acrobat Pro; com.adobe.Reader == Reader). The bundle
# id is a precise, non-inferred edition signal -- it is NOT a loosening of the exact-edition
# rule; a Pro crash report often carries com.adobe.Acrobat.Pro but never the literal phrase
# "Acrobat Pro". Bare "com.adobe.Acrobat" (no .Pro/.Reader) stays ambiguous and is not added.
READER_RE = re.compile(r"\b(?:adobe\s+)?acrobat\s+reader(?:\s+dc)?\b|\badobe\s+reader\b|\breader\s+dc\b|\bcom\.adobe\.reader\b", re.I)
PRO_RE = re.compile(r"\b(?:adobe\s+)?acrobat\s+pro(?:\s+dc)?\b|\badobe\s+acrobat\s+dc\s+pro\b|\bcom\.adobe\.acrobat\.pro\b", re.I)
ACROBAT_BARE_RE = re.compile(r"\b(?:adobe\s+)?acrobat\b", re.I)
# A licensing/entitlement TIER context: an edition name here denotes the license the user
# holds, not the patched product. E.g. "signs in with an Acrobat Pro or Standard license",
# "Reader switches to licensed Acrobat mode", "Pro or Standard mode". This lets a report whose
# only Pro mention is a license state (the failing product being Reader) be classified
# Reader-only instead of shared. Narrow on purpose -- it does not match a plain "Acrobat Pro
# crashes" failure report (no license/entitlement/"Pro or Standard" tier language nearby).
_LICENSE_TIER_RE = re.compile(
    r"licen[sc]e|licen[sc]ed|subscription|entitlement"
    r"|acrobat\s+standard|standard\s+or\s+(?:acrobat\s+)?pro|pro\s+or\s+(?:acrobat\s+)?standard"
    r"|signs?\s+in\s+with|switch(?:es|ed|ing)?\s+to\s+(?:licensed|pro\b|standard)",
    re.I,
)
_LICENSE_WINDOW = 45  # chars of context on each side of an edition mention

EDITION_CONFIG: dict[str, dict[str, Any]] = {
    READER_ID: {
        "software": "Adobe Acrobat Reader",
        "subreddits": ("Acrobat", "Adobe", "pdf"),
        "query_products": ("Acrobat Reader", "Adobe Acrobat Reader"),
    },
    PRO_ID: {
        "software": "Adobe Acrobat Pro",
        "subreddits": ("Acrobat", "Adobe", "pdf"),
        "query_products": ("Acrobat Pro", "Adobe Acrobat Pro"),
    },
}

# --- concrete post-install issue (Acrobat-specific) --------------------------
# Terminal "failure" verbs allowing common suffixes (fails/failed/failure/errors/...).
_F = r"(?:fail(?:s|ed|ure)?|error(?:s|ed)?|broke|broken|invalid|problem|issue)"
ACROBAT_STRONG_ISSUE_RE = re.compile(
    # "crash", "crashes", "crashed" were accepted but "crashING" was not, so the single most
    # common way a person titles an Acrobat crash report -- "Acrobat DC (26.001.21529) crashing
    # with eSignatures" -- was refused as not-a-real-issue after passing every other gate.
    r"\b(?:crash(?:e[sd]|ing)?"
    # "won't print" was accepted; "will not print" and "does not print" were not, though they are
    # the same claim written out. Both forms take the same verb list, so neither widens what
    # counts as a failure -- they only stop the matcher depending on a contraction.
    r"|(?:won'?t|will\s+not|do(?:es)?\s+not|doesn'?t|cannot|can'?t)\s+"
    r"(?:open|launch|install|start|print|save|load|sign|update|respond)"
    r"|stopped\s+(?:print|work|respond|open|load|sav)\w*"
    r"|(?:fail(?:s|ed|ure)?|unable)\s+to\s+(?:install|update|open|launch|print|sign|save|load|activate)"
    rf"|install(?:ation)?\s+{_F}"
    rf"|update\s+{_F}"
    rf"|print(?:ing)?\s+(?:{_F}|regression|blank)"
    r"|(?:pdf|render(?:ing)?|display)\s+(?:blank|broken|garbled|corrupt|wrong|not\s+render)"
    r"|form(?:s|\s+field)?\s+(?:broke|broken|not\s+work|fail(?:s|ed|ure)?|blank)"
    rf"|(?:signature|signing|certificate)\s+{_F}"
    r"|freeze[sd]?|frozen|hang(?:s|ing)?|not\s+responding|high\s+(?:cpu|memory)|memory\s+leak"
    r"|corrupt(?:ed|ion)?|data\s+loss"
    rf"|deploy(?:ment)?\s+{_F}|licens(?:e|ing)\s+{_F}|activation\s+{_F}"
    r"|(?:plugin|add-?in|extension)\s+(?:broke|broken|not\s+work|crash(?:e[sd])?|incompat\w*)"
    r"|regression|broke\s+after|broken\s+after|stopped\s+working\s+after|no\s+longer\s+works)\b",
    re.I,
)
ACROBAT_NON_REPORT_RE = re.compile(
    r"\b(release\s+notes|what'?s\s+new|announcing|announcement|new\s+feature|feature\s+request|"
    r"please\s+add|would\s+be\s+nice|pric(?:e|ing)|subscription\s+cost|too\s+expensive|refund|"
    r"how\s+do\s+i|how\s+to)\b",
    re.I,
)
_GENUINE_FAILURE_RE = re.compile(r"\b(crash|fail|broke|broken|error|corrupt|freeze|hang|regression|not\s+responding)\b", re.I)

# --- vendor authority: official information is not user consensus -------------
# Adobe publishes its OWN release announcements and support documents as ordinary community
# threads, from accounts the platform ranks like any other member. There is nothing structural to
# key on: the evidence schema stores no author/rank/role/post-type field at all, and source_type,
# source_name and sentiment are constant across every stored Acrobat row. (The platform's own
# rank.name == "Adobe Employee" flag rides on LAST posts and was observed firing on none of the
# fetchable openers, both vendor threads included -- but that is a network observation, not
# something this repo can assert.) So authority has to be read off what the post IS.
#
# Deliberately NOT cancellable by _GENUINE_FAILURE_RE: a release announcement enumerates the
# defects it fixes, so a failure word is EXPECTED in vendor prose. That cancellation is precisely
# how "Adobe Acrobat and Reader DC - June 2021 Update Release" was counted as three user reports.
#
# TITLE-anchored, and only the title. A member titles a thread with the symptom they hit; only the
# publisher titles one as the release itself. Two properties make the title safe to read where the
# body is not:
#   * a title is short and is stored whole, so what this rule sees in production is exactly what the
#     corpus lets us audit. The BODY is not: collection passes ~6000 chars (`_clean_html(...)[:6000]`
#     at the fetch sites) while `report_text_excerpt` keeps only 280, an ~18x gap, so any body rule
#     is validated against ~5% of its real input.
#   * on the /t5 path the body is the whole thread page with every reply concatenated -- post
#     boundaries are already destroyed by _clean_html -- so body prose cannot be attributed to the
#     opening author at all.
#
# Deliberately NOT cancellable by _GENUINE_FAILURE_RE: a release announcement enumerates the defects
# it fixes, so a failure word is EXPECTED in vendor prose. That cancellation is precisely how
# "Adobe Acrobat and Reader DC - June 2021 Update Release" was counted as three user reports.
ACROBAT_VENDOR_ANNOUNCEMENT_TITLE_RE = re.compile(
    r"\b(?:update\s+release|release\s+notes?|what'?s\s+new|announc\w+"
    r"|(?:is|are)\s+now\s+available|release\s+is\s+now|new\s+release)\b",
    re.I,
)
# ...cancelled when the TITLE ITSELF states a problem or asks a question. Several of the tokens
# above carry no vendor semantics at all -- "update release", "new release" and "is now available"
# are ordinary English, and the last is Acrobat's own updater dialog string, which a member will
# quote. Without this, "Crashes since the June update release" and "New release 21.005.20048 breaks
# printing" were both refused as vendor-authored: 10 of 10 realistic member titles destroyed.
#
# This does NOT reopen the cancellation the announcement rule was written to defeat. That one was
# body-scoped, and an announcement's BODY enumerates the defects it fixes, so failure words there
# are expected. A publisher's TITLE names the release ("Adobe Acrobat and Reader DC - June 2021
# Update Release") and carries no symptom or question; a member's title states what broke.
ACROBAT_MEMBER_TITLE_CUE_RE = re.compile(
    r"\?"
    r"|\b(?:crash\w*|fail\w*|broke\w*|break\w*|error\w*|corrupt\w*|freez\w*|hang\w*|stuck"
    r"|regress\w*|bug|bugs|issue\w*|problem\w*|glitch\w*|loop|lag\w*|slow|blank|missing|lost"
    r"|not\s+responding|won'?t|will\s+not|can'?t|cannot|unable|doesn'?t|does\s+not|don'?t"
    r"|no\s+longer|stopped|stops|refus\w*|denied|help|anyone\s+else)\b",
    re.I,
)

# NOT IMPLEMENTED, deliberately: Adobe support documents ("Problem : ... Solution: ...").
# One is counted today (thread 1288217, adobe-acrobat-pro 21.005.20058) and stays counted. A
# Problem/Solution text rule was built, measured and REJECTED: `problem:` occurs mid-sentence in
# ordinary member prose ("keep running into a problem: I'm getting the error" -- four such rows are
# counted right now), the true positive's own label sits mid-run at offset 147 so no start-anchor
# separates them, and whitespace is already collapsed so no line anchor exists. Every narrowing
# tried either lost the one true positive or kept refusing real reports. That trade is not
# recoverable: `append_evidence_rows` builds `seen_urls` from ALL rows regardless of `counted`, so a
# genuine report once stamped vendor-authored is never re-collected. Prefer counting one vendor
# document to permanently destroying real user reports. Reopen only with an author/role signal.


def acrobat_vendor_authority(title: str, text: str) -> str:
    """Vendor-authority reason for this post, or '' when it reads as a member report.

    Returns a stable reason token; never raises. Refuses exactly one shape: a title that uses
    announcement vocabulary AND states no problem of its own. `text` is accepted for call-site
    symmetry and is deliberately NOT read; see the note above on why body prose is not a sound
    authority signal on this platform.

    The refusal is narrow ON PURPOSE, because it is irreversible: `append_evidence_rows` builds its
    dedupe sets from ALL rows regardless of `counted`, so a member report refused here is never
    re-collected. Missing a vendor announcement costs one over-counted report; refusing a member
    costs that report permanently. When those trade against each other, miss the announcement.
    """
    text_title = str(title or "")
    if not ACROBAT_VENDOR_ANNOUNCEMENT_TITLE_RE.search(text_title):
        return ""
    if ACROBAT_MEMBER_TITLE_CUE_RE.search(text_title):
        return ""
    return "vendor_release_announcement"


# --- specific Adobe Community thread/message URL -----------------------------
_ADOBE_THREAD_RE = re.compile(r"/t5/[^/]+/[^/]+/(?:td-p|m-p|idi-p)/\d+", re.I)
_ADOBE_BUG_RE = re.compile(r"/bug-reports?[-\w]*/[\w%-]+/\d+", re.I)
# New inSided platform: a specific thread is /{board}-{boardId}/{slug}-{topicId} (two path
# segments, trailing numeric topic id). Board roots (/questions-9) and categories (/acrobat-7)
# have no second slug-id segment and are correctly rejected.
_ADOBE_QUESTIONS_RE = re.compile(r"^/[a-z][a-z0-9]*-\d+/[a-z0-9%\-]+-\d+/?$", re.I)
_HREF_RE = re.compile(r'href=["\'](https?://community\.adobe\.com[^"\']+)["\']', re.I)
_TAG_RE = re.compile(r"(?is)<(script|style|noscript).*?</\1>|<[^>]+>")
_OG_TITLE_RE = re.compile(r"""<meta\s+property=["']og:title["']\s+content=["']([^"']+)["']""", re.I)
_H1_RE = re.compile(r"(?is)<h1[^>]*>(.*?)</h1>")
_TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")


class AcrobatCommunityAccessError(RuntimeError):
    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


def _has_non_license_mention(text: str, edition_re: "re.Pattern[str]") -> bool:
    """True when the edition has at least one PRODUCT-level mention -- i.e. a mention that is
    not merely a licensing/entitlement tier state. If every mention sits in a license context,
    the edition is not the patched product and is not attributed."""
    for match in edition_re.finditer(text or ""):
        window = text[max(0, match.start() - _LICENSE_WINDOW): match.end() + _LICENSE_WINDOW]
        if not _LICENSE_TIER_RE.search(window):
            return True
    return False


def acrobat_edition_attribution(text: str, product_id: str) -> tuple[bool, str, str, str | None]:
    """Deterministic, non-inferred edition attribution.

    Returns (attributed, matched_alias, applicability_csv, exclusion_reason). A report counts
    for an edition only when that edition is explicitly named AS THE PATCHED PRODUCT. Merely
    mentioning an edition as a licensing tier (e.g. "signs in with an Acrobat Pro license",
    "Reader switches to licensed Acrobat mode") does not attribute the patch failure to it, so
    a Reader update whose only Pro reference is a later license transition is Reader-only, not
    shared. Shared applicability requires BOTH editions to have a real product-level mention;
    bare Acrobat / bare Reader / the opposite edition fail closed.
    """
    text = text or ""
    reader_attributed = bool(READER_RE.search(text)) and _has_non_license_mention(text, READER_RE)
    pro_attributed = bool(PRO_RE.search(text)) and _has_non_license_mention(text, PRO_RE)
    if reader_attributed and pro_attributed:
        return True, "acrobat reader + acrobat pro", f"{READER_ID},{PRO_ID}", None
    if product_id == READER_ID:
        if reader_attributed:
            return True, "acrobat reader", READER_ID, None
        if pro_attributed:
            return False, "", "", "wrong_product"
    if product_id == PRO_ID:
        if pro_attributed:
            return True, "acrobat pro", PRO_ID, None
        if reader_attributed:
            return False, "", "", "wrong_product"
    if ACROBAT_BARE_RE.search(text):
        return False, "", "", "generic_acrobat_without_edition"
    return False, "", "", "missing_product_attribution"


def acrobat_strong_issue_match(text: str) -> bool:
    lowered = (text or "").lower()
    if not ACROBAT_STRONG_ISSUE_RE.search(lowered):
        return False
    if ACROBAT_NON_REPORT_RE.search(lowered) and not _GENUINE_FAILURE_RE.search(lowered):
        return False
    return True


def acrobat_url_is_specific(url: str) -> bool:
    parsed = urllib.parse.urlparse(url or "")
    if "community.adobe.com" not in parsed.netloc.lower():
        return False
    path = parsed.path.lower()
    if "/announcement" in path or path.rstrip("/").endswith(("/search", "/searchpage")):
        return False
    return bool(_ADOBE_THREAD_RE.search(path) or _ADOBE_BUG_RE.search(path) or _ADOBE_QUESTIONS_RE.match(path))


def _url_specific(url: str, source_type: str) -> bool:
    """Adobe Community requires a specific thread/message/bug URL (stricter than base's
    generic community.adobe.com fallback); Reddit and other hosts use the shared gate."""
    if source_type == ADOBE_COMMUNITY_SOURCE_TYPE:
        return acrobat_url_is_specific(url)
    return source_url_is_specific(url)


# What a report is ABOUT, scored rather than first-match.
#
# The previous rule was a bare substring scan in a fixed order with `crash` checked LAST, over the
# whole ~6000-character body. Two consequences, both measured on published rows: "sign" matched
# "de-SIGN", "SIGN in" and "signature pad", and any mention of printing anywhere -- including in a
# workaround the reporter had tried -- won outright. 59 of 63 counted rows whose own TITLE says
# crash/freeze/hang published a different theme, and that theme is the sentence the patch page
# prints as "Current reports mention ...".
#
# Three changes: word boundaries, the reporter's own TITLE weighted far above the body, and stability
# scored alongside everything else instead of last.
_THEME_RULES: tuple[tuple[str, str, str, str, "re.Pattern[str]"], ...] = (
    ("crash or launch failure", "application stability", "high",
     "crash", re.compile(r"\b(?:crash\w*|freez\w*|hang(?:s|ing|ed)?|not\s+responding|"
                        r"appcrash|fails?\s+to\s+launch|won'?t\s+(?:launch|start|open))\b", re.I)),
    ("printing regression", "printing", "high",
     "print", re.compile(r"\b(?:print\w*|printer|print\s+queue|spooler)\b", re.I)),
    ("signing/certificate failure", "e-signatures", "high",
     "sign", re.compile(r"\b(?:e-?sign\w*|signature\w*|signing|certificat\w*|digital\s+id)\b", re.I)),
    ("form behavior regression", "forms", "high",
     "form", re.compile(r"\b(?:form\s+field\w*|fillable|form\w*)\b", re.I)),
    ("install/update failure", "deployment", "high",
     "install", re.compile(r"\b(?:install\w*|uninstall\w*|deploy\w*|msi|silent\s+update|"
                          r"update\s+fail\w*|patch\s+fail\w*)\b", re.I)),
    ("PDF rendering regression", "PDF rendering", "high",
     "render", re.compile(r"\b(?:render\w*|blank\s+page|garbled|corrupt\w*|display\s+issue)\b", re.I)),
    ("browser/plugin handoff failure", "browser integration", "medium",
     "browser", re.compile(r"\b(?:browser|plugin|plug-in|add-?in|extension|edge|chrome|firefox)\b", re.I)),
    ("performance regression", "performance", "medium",
     "perf", re.compile(r"\b(?:high\s+cpu|memory\s+leak|slow\w*|sluggish|performance)\b", re.I)),
)
# Everything after one of these headings is what the reporter has ALREADY TRIED, not what failed.
_TRIED_SPLIT_RE = re.compile(
    r"(?is)\b(?:troubleshooting|already\s+tried|things?\s+i(?:'ve)?\s+tried|what\s+i(?:'ve)?\s+tried|"
    r"work\s?around|steps?\s+to\s+reproduce\s*:)\b")


def acrobat_classify(text: str, title: str = "") -> tuple[str, str, str, str, str]:
    """(theme, workflow_area, platform, severity, sentiment) for one report."""
    body = str(text or "")
    heading = str(title or "")
    if not heading:
        # No title supplied: treat the first line as one, which is how these candidates are built.
        heading = body.splitlines()[0][:200] if body.strip() else ""
    # Whatever the heading turned out to be, it stops at the point the reporter starts listing what
    # they already tried -- otherwise a one-line post carries its own workaround into the title.
    heading = _TRIED_SPLIT_RE.split(heading, maxsplit=1)[0]
    scored_body = _TRIED_SPLIT_RE.split(body, maxsplit=1)[0]

    lowered = body.lower()
    platform = "unknown"
    for token, label in (("windows", "windows"), ("macos", "macos"), ("mac os", "macos"),
                         ("mac ", "macos")):
        if token in lowered:
            platform = label
            break

    best = None
    for theme, area, severity, _key, pattern in _THEME_RULES:
        # The title is the reporter's own one-line summary of what went wrong, so a hit there is
        # worth far more than a passing mention buried in a long body.
        score = 5 * len(pattern.findall(heading)) + len(pattern.findall(scored_body))
        if score and (best is None or score > best[0]):
            best = (score, theme, area, severity)
    if best is None:
        return "unspecified Acrobat issue", "Acrobat workflow", platform, "medium", "negative"
    return best[1], best[2], platform, best[3], "negative"


# --- HTTP (Adobe Community) ---------------------------------------------------

def _bounded_fetch(url: str, *, budget: Any, headers: dict[str, str], data: bytes | None, method: str | None,
                   max_bytes: int, family: str) -> tuple[int, str, str]:
    """Hard-bounded (total wall-clock deadline, byte-capped) Acrobat Community/Algolia fetch. Converts a
    method-budget breach into an AcrobatCommunityAccessError so it flows through the existing degradation
    path (method-health survives)."""
    try:
        budget.note_request()
    except rb.MethodBudgetExhausted as exc:
        raise AcrobatCommunityAccessError(f"budget_{exc.reason}") from exc
    try:
        resp = rb.bounded_request(url, budget=budget, endpoint_family=family, headers=headers, data=data, method=method, max_bytes=max_bytes)
    except rb.RequestDeadlineExceeded as exc:
        raise AcrobatCommunityAccessError("request_deadline") from exc
    except rb.BudgetError as exc:
        raise AcrobatCommunityAccessError(f"network_{exc.reason}") from exc
    content_type = resp.headers.get("Content-Type", "") if resp.headers is not None else ""
    return resp.status, content_type, resp.body.decode("utf-8", errors="replace")


def _request_text(url: str, timeout: int = 30, max_bytes: int = 800000) -> str:
    if _ACTIVE_BUDGET is not None:
        status, content_type, body = _bounded_fetch(url, budget=_ACTIVE_BUDGET, headers=HEADERS, data=None,
                                                    method=None, max_bytes=max_bytes, family="adobe_community_html")
        signature = _blocked_signature(body, status=status, content_type=content_type)
        if signature != "none":
            raise AcrobatCommunityAccessError(signature, status=status)
        return body
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", None)
            content_type = response.headers.get("Content-Type", "")
            body = response.read(max_bytes).decode("utf-8", errors="replace")
    except HTTPError as exc:
        try:
            body = exc.read(8000).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        raise AcrobatCommunityAccessError(_blocked_signature(body, status=exc.code), status=exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AcrobatCommunityAccessError(f"network_{type(exc).__name__}") from exc
    signature = _blocked_signature(body, status=status, content_type=content_type)
    if signature != "none":
        raise AcrobatCommunityAccessError(signature, status=status)
    return body


def _blocked_signature(text: str, *, status: int | None = None, content_type: str = "") -> str:
    lowered = (text or "").lower()
    if status in {401, 403}:
        return "blocked"
    if status == 429 or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "captcha" in lowered:
        return "captcha_challenge"
    if "access denied" in lowered or "request blocked" in lowered:
        return "blocked"
    if "checking your browser" in lowered or "cloudflare" in lowered:
        return "browser_challenge"
    if not text:
        return "empty_body"
    return "none"


def _error_is_blocked(exc: Exception) -> bool:
    reason = getattr(exc, "reason", type(exc).__name__).lower()
    return any(token in reason for token in ("blocked", "challenge", "captcha", "rate_limited", "http_401", "http_403", "http_429"))


def _request_json(url: str, *, headers: dict[str, str], data: bytes | None = None, timeout: int = 30, max_bytes: int = 1200000) -> Any:
    """GET (or POST when ``data`` is given) a JSON endpoint, raising AcrobatCommunityAccessError
    with a block/rate-limit/network signature on failure so method health degrades honestly."""
    method = "POST" if data is not None else "GET"
    if _ACTIVE_BUDGET is not None:
        status, _content_type, body = _bounded_fetch(url, budget=_ACTIVE_BUDGET, headers=headers, data=data,
                                                     method=method, max_bytes=max_bytes, family="adobe_algolia")
        if status in {401, 403, 429}:
            raise AcrobatCommunityAccessError(_blocked_signature(body, status=status), status=status)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise AcrobatCommunityAccessError("invalid_json") from exc
    req = urllib.request.Request(url, headers=headers, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", None)
            body = response.read(max_bytes).decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise AcrobatCommunityAccessError(f"http_{exc.code}_{_blocked_signature('', status=exc.code)}", status=exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AcrobatCommunityAccessError(f"network_{type(exc).__name__}") from exc
    if status in {401, 403, 429}:
        raise AcrobatCommunityAccessError(_blocked_signature(body, status=status), status=status)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise AcrobatCommunityAccessError("invalid_json") from exc


def _clean_html(html_text: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", html_text or ""))).strip()


def _extract_title(html_text: str) -> str:
    for pattern in (_OG_TITLE_RE, _H1_RE, _TITLE_RE):
        match = pattern.search(html_text or "")
        if match:
            title = unescape(_TAG_RE.sub(" ", match.group(1))).strip()
            title = re.sub(r"\s*[-|]\s*Adobe (?:Community|Support Community).*$", "", title).strip()
            if title:
                return title
    return ""


def _canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunsplit(("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


# --- discovery methods --------------------------------------------------------

def _search_queries(edition: dict[str, Any], version: str) -> list[str]:
    queries: list[str] = []
    for product in edition["query_products"]:
        queries.append(f'"{product} {version}"')
    return queries[:MAX_SEARCH_QUERIES]


def adobe_community_search_candidates(
    edition: dict[str, Any], record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in _search_queries(edition, record.update_version):
        for page in range(1, min(MAX_SEARCH_PAGES, max(1, context.max_pages)) + 1):
            url = ADOBE_SEARCH_URL.format(query=urllib.parse.quote(query), page=page)
            try:
                html_text = _request_text(url)
            except Exception as exc:  # noqa: BLE001
                errors.append({"source_url": url, "reason": f"adobe_community_search_fetch_failed:{getattr(exc, 'reason', type(exc).__name__)}"})
                if _error_is_blocked(exc):
                    return candidates
                break
            for link in _HREF_RE.findall(html_text):
                canonical = _canonical_url(link)
                if not canonical or not acrobat_url_is_specific(canonical) or canonical.lower() in seen:
                    continue
                seen.add(canonical.lower())
                try:
                    thread_html = _request_text(canonical)
                except Exception as exc:  # noqa: BLE001
                    errors.append({"source_url": canonical, "reason": f"adobe_community_thread_fetch_failed:{getattr(exc, 'reason', type(exc).__name__)}"})
                    if _error_is_blocked(exc):
                        return candidates
                    continue
                title = _extract_title(thread_html)
                text = _clean_html(thread_html)[:6000]
                candidates.append({
                    "source_type": ADOBE_COMMUNITY_SOURCE_TYPE,
                    "source_name": "Adobe Community",
                    "source_url": canonical,
                    "parent_title": title,
                    "report_title": title,
                    "report_text": text,
                    "source_date": "",
                })
    return candidates


def _algolia_search_queries(edition: dict[str, Any], version: str) -> list[str]:
    """Exact-version, product-constrained Algolia queries (quoted so the token is matched as
    a phrase). No site: operator is needed -- the anonymous searchToken already scopes the
    index to the Adobe community forums."""
    queries = [f'"{version}" "{product}"' for product in edition["query_products"]]
    queries.append(f'"{version}"')
    return queries[:MAX_ALGOLIA_QUERIES]


def _algolia_credentials(errors: list[dict[str, Any]]) -> dict[str, str] | None:
    """Fetch the anonymous inSided/Algolia search credentials (app id, secured search key,
    index) from the keyless /search/searchToken endpoint. Returns None (with a recorded error)
    when the endpoint is blocked or the payload is incomplete."""
    try:
        data = _request_json(ADOBE_SEARCH_TOKEN_URL, headers=JSON_HEADERS)
    except Exception as exc:  # noqa: BLE001
        errors.append({"source_url": ADOBE_SEARCH_TOKEN_URL, "reason": f"adobe_search_token_fetch_failed:{getattr(exc, 'reason', type(exc).__name__)}"})
        return None
    payload = data if isinstance(data, dict) else {}
    app_id = str(payload.get("client_id") or "").strip()
    key = str(payload.get("token") or "").strip()
    indexes = payload.get("availableIndexes")
    index = str(indexes[0]).strip() if isinstance(indexes, list) and indexes else ""
    if not (app_id and key and index):
        errors.append({"source_url": ADOBE_SEARCH_TOKEN_URL, "reason": "adobe_search_token_incomplete"})
        return None
    return {"app_id": app_id, "key": key, "index": index}


def _algolia_search(creds: dict[str, str], query: str, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    url = ALGOLIA_QUERY_URL_TMPL.format(app_id=urllib.parse.quote(creds["app_id"]), index=urllib.parse.quote(creds["index"]))
    headers = {**JSON_HEADERS, "X-Algolia-Application-Id": creds["app_id"], "X-Algolia-API-Key": creds["key"], "Content-Type": "application/json"}
    body = json.dumps({"params": urllib.parse.urlencode({"query": query, "hitsPerPage": MAX_ALGOLIA_HITS_PER_QUERY})}).encode("utf-8")
    try:
        data = _request_json(url, headers=headers, data=body)
    except Exception as exc:  # noqa: BLE001
        errors.append({"source_url": url, "reason": f"adobe_algolia_search_failed:{getattr(exc, 'reason', type(exc).__name__)}"})
        return []
    hits = data.get("hits") if isinstance(data, dict) else None
    return [h for h in hits if isinstance(h, dict)] if isinstance(hits, list) else []


def _get_topics(topic_ids: list[int], errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Batch-fetch authoritative topic records (canonical URL + full first-post content + date)
    for the discovered topic ids from the keyless /search/getTopics endpoint."""
    if not topic_ids:
        return []
    params = urllib.parse.urlencode([("topicIds[]", str(tid)) for tid in topic_ids[:MAX_TOPICS_PER_RECORD]])
    url = f"{ADOBE_GET_TOPICS_URL}?{params}"
    try:
        data = _request_json(url, headers=JSON_HEADERS)
    except Exception as exc:  # noqa: BLE001
        errors.append({"source_url": ADOBE_GET_TOPICS_URL, "reason": f"adobe_get_topics_failed:{getattr(exc, 'reason', type(exc).__name__)}"})
        return []
    return [t for t in data if isinstance(t, dict)] if isinstance(data, list) else []


def _unix_to_date(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _topic_to_candidate(topic: dict[str, Any]) -> dict[str, Any] | None:
    """Turn one authoritative getTopics record into a discovery candidate. Discovery only --
    row_from_candidate still applies the unchanged edition/version/URL/date/issue gates."""
    url = _canonical_url(str(topic.get("url") or ""))
    if not url:
        return None
    first_post = topic.get("firstPost") if isinstance(topic.get("firstPost"), dict) else {}
    title = str(topic.get("title") or "").strip()
    body = _clean_html(str(first_post.get("content") or ""))[:6000]
    if not title and not body:
        return None
    source_date = date_part(first_post.get("creationDate")) or _unix_to_date(topic.get("dateAdded") or topic.get("date_added"))
    return {
        "source_type": ADOBE_COMMUNITY_SOURCE_TYPE,
        "source_name": "Adobe Community",
        "source_url": url,
        "parent_title": title,
        "report_title": title,
        "report_text": f"{title} {body}".strip(),
        "source_date": source_date,
        # When the QUESTION was written, taken structurally from the opening post rather than from
        # a listing stamp that a later reply bumps. Release-window ownership uses this. `report_text`
        # above is the first post ONLY -- no answers, no comments -- so a reply can neither enrich
        # this report's identity nor drift it into a newer window.
        "original_post_date": date_part(first_post.get("creationDate")) or source_date,
        # The opening author's forum rank, as the platform states it ("Participant",
        # "Community Manager"). Carried so vendor-authored posts are distinguishable from user
        # reports without inferring it from wording.
        "author_rank": str((first_post.get("author") or {}).get("rank", {}).get("name") or "")
        if isinstance(first_post.get("author"), dict) else "",
    }


def adobe_community_algolia_search_candidates(
    edition: dict[str, Any], record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Keyless, CI-reachable discovery: anonymous Algolia search (exact version + product) to
    find candidate topic ids, then the getTopics content endpoint for authoritative URL/body/date.
    Neither endpoint is the CloudFront-blocked /t5 HTML search path. All acceptance gates are
    applied downstream by row_from_candidate; this method never widens them.

    Exact-patch lifetime window: this method's lower date bound is the patch's OFFICIAL RELEASE
    DATE, not the runner's global --since-days lookback. The exact full version already scopes
    the query to one patch, so the applicable window is [release_date, now]. Using the global
    45-day cutoff here would hide valid post-release reports for an older-but-current patch
    (e.g. 26.001.21529, released May 1, whose May 12/15 Pro reports are >45 days old). Reports
    dated before the release date are still rejected -- both here and, authoritatively, by the
    source_date gate in row_from_candidate."""
    creds = _algolia_credentials(errors)
    if not creds:
        return []
    # Authoritative lower bound = the record's official release date (never the global cutoff).
    release_lower_bound = date_part(record.update_published_at)
    topic_ids: list[int] = []
    seen_ids: set[int] = set()
    for query in _algolia_search_queries(edition, record.update_version):
        for hit in _algolia_search(creds, query, errors):
            raw_id = hit.get("id")
            tid = int(raw_id) if isinstance(raw_id, int) or (isinstance(raw_id, str) and raw_id.isdigit()) else None
            if tid is not None and tid not in seen_ids:
                seen_ids.add(tid)
                topic_ids.append(tid)
        if len(topic_ids) >= MAX_TOPICS_PER_RECORD:
            break
    topic_ids = topic_ids[:MAX_TOPICS_PER_RECORD]
    if not topic_ids:
        return []
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for topic in _get_topics(topic_ids, errors):
        candidate = _topic_to_candidate(topic)
        if not candidate:
            continue
        url = candidate["source_url"].lower()
        if url in seen_urls:
            continue
        seen_urls.add(url)
        # Discovery pre-filter on the patch's own release date (NOT context.since). Pre-release
        # candidates are dropped here to avoid processing them; the same rule is re-applied
        # authoritatively by the source_date gate in row_from_candidate.
        if release_lower_bound and candidate.get("source_date") and date_part(candidate["source_date"]) < release_lower_bound:
            continue
        candidates.append(candidate)
    return candidates


def reddit_search_candidates(
    edition: dict[str, Any], record: PatchRecord, context: CollectorContext, errors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    queries: list[str] = []
    for product in edition["query_products"]:
        queries.append(f'{product} {record.update_version}')
    return reddit_source.collect_reddit_candidates(
        subreddits=edition["subreddits"],
        queries=queries,
        context=context,
        errors=errors,
        source_type=REDDIT_SOURCE_TYPE,
        version_hints=[record.update_version],
    )


# --- acceptance ---------------------------------------------------------------

def row_from_candidate(product_id: str, record: PatchRecord, candidate: dict[str, Any], captured_at: str) -> dict[str, Any]:
    # De-duplicate the parts before joining. Every Adobe candidate sets parent_title and
    # report_title to the SAME thread title, so the naive join repeated it, and repetition is not
    # harmless for any rule that reads word order: "…rolled back to 26.001.21745" followed by a
    # second copy beginning "Acrobat crashes…" puts a failure word next to the build the reporter
    # rolled back TO, and the outcome classifier then reads it as affected rather than as a
    # rollback. One copy of each distinct part says exactly what the reporter said.
    seen_parts: set[str] = set()
    parts: list[str] = []
    for field in ("parent_title", "report_title", "report_text"):
        value = str(candidate.get(field) or "").strip()
        key = " ".join(value.lower().split())
        if not value or key in seen_parts:
            continue
        seen_parts.add(key)
        parts.append(value)
    report_text = " ".join(parts)
    matched, matched_version, basis = exact_version_match(
        report_text, record.update_version, aliases=acrobat_version_aliases(record.update_version))
    attributed, alias, applicability, edition_reason = acrobat_edition_attribution(report_text, product_id)
    # SHARED BUILD. Adobe ships ONE DC build to Reader and to Pro, and every Acrobat record states
    # so itself in a structured `applicability` field derived from the release note -- not guessed
    # here. Users write what Adobe's own UI and forum call the product: bare "Acrobat", or
    # "Acrobat DC", or "Acrobat Standard". Requiring the words "Reader" or "Pro" refused 73 of 98
    # recent candidates, including reports that named the exact build and described a concrete
    # post-install failure. Naming the edition is not what makes a report about this patch; naming
    # the build is, and gate 2 below still demands it.
    edition_basis = "explicit_edition" if attributed else ""
    if not attributed and edition_reason == "generic_acrobat_without_edition":
        shared = record_applicability(record)
        # "Acrobat Standard" is a NAMED edition, not a generic mention. It is treated as licensing
        # language by the tier rule, so it fell through to "generic" and the shared-build fallback
        # then published it on both tracked editions. Adobe ships Standard from the Pro binary, and
        # Reader is a separate installer, so a Standard report on a READER page is simply wrong --
        # one such report was the entire evidentiary basis of the 26.001.21789 Reader page.
        if _STANDARD_PRODUCT_RE.search(report_text):
            edition_reason = "acrobat_standard_edition_not_tracked"
        elif product_id in shared:
            attributed, alias = True, "acrobat (shared DC build)"
            applicability = ",".join(shared)
            edition_reason, edition_basis = None, "shared_build_generic_acrobat"
    # Pass the reporter's OWN title, not a guess at the first line: the title is the one-line
    # summary of what went wrong and the classifier weights it far above the body.
    theme, workflow_area, platform, severity, sentiment = acrobat_classify(
        report_text,
        title=str(candidate.get("report_title") or candidate.get("parent_title") or ""))
    source_date = date_part(candidate.get("source_date"))
    source_type = str(candidate.get("source_type") or ADOBE_COMMUNITY_SOURCE_TYPE)

    row = make_evidence_row(
        product_id=product_id,
        update_version=record.update_version,
        source_type=source_type,
        source_name=str(candidate.get("source_name") or "Adobe Community"),
        source_url=str(candidate.get("source_url") or ""),
        parent_title=str(candidate.get("parent_title") or ""),
        report_title=str(candidate.get("report_title") or ""),
        report_text=str(candidate.get("report_text") or ""),
        captured_at=captured_at,
        source_date=source_date,
        target_release_date=date_part(record.update_published_at),
        patch_version_matched=matched,
        matched_version=matched_version,
        match_basis=basis,
        matched_product_alias=alias,
        applicability=applicability,
        counted=False,
        exclusion_reason=None,
        issue_theme=theme,
        workflow_area=workflow_area,
        platform=platform,
        severity=severity,
        sentiment=sentiment,
        # Canonical, product-INDEPENDENT evidence id: version + source_type + URL. A genuinely
        # shared report (applicability = both editions) therefore carries the SAME id and URL on
        # both the Reader and Pro product paths -- one canonical identity, not two unrelated ones
        # -- while append_evidence_rows still keys dedup by (product_id, version, url) so each
        # applicable product stores exactly one row and counts it once.
        row_id=f"acrobat-{slug(record.update_version)}-{slug(source_type)}-{slug(str(candidate.get('source_url') or ''))}",
    )
    source_date_pass = row.get("source_date_pass")
    if not source_date:
        row["source_date_pass"] = None
        source_date_pass = None

    # Fail-closed gate order (Part C): 1 exact-edition attribution -> 2 exact current
    # DC-build version -> 3 specific thread/post URL -> 4 source date >= release date ->
    # 5 concrete post-install issue. The FIRST failing gate sets the exclusion reason, so an
    # ambiguous / wrong-edition report is never masked by a later reason.
    reason: str | None = None
    if not attributed:
        reason = edition_reason or "missing_product_attribution"
    elif not matched:
        reason = "missing_exact_patch_version_match"
    # Naming the build is not the same as blaming it. "26.001.21745 works fine, it is .21789 that
    # crashes" and "rolled back to 26.001.21745 and it works" both satisfy the version match above,
    # and both say the OPPOSITE of what counting them would publish. This is the defect PR #79
    # fixed for OBS and DaVinci; the shared-build relaxation above widens acceptance, so the veto
    # has to be in place with it, not after it. Silence and any affirmative statement pass through.
    elif (contradiction := target_is_contradicted(report_text, record.update_version)) is not None:
        reason = f"version_named_but_{contradiction.outcome}"
    # MULTIPLE BUILDS NAMED. A person comparing versions names several: the one that broke, the one
    # they want to revert to, the one a release note mentions, the one they were on before. The
    # directional veto above only catches phrasings it has cues for, and it missed all of these --
    # one live thread was published as a confirmed report against THREE builds, two of which its
    # author explicitly did not blame ("Can I get the installer for 26.001.21771 to revert in the
    # meantime?" and a release-note citation of 26.001.21651). Where more than one tracked build is
    # named, silence is no longer enough: the report has to say THIS build is the one failing.
    elif len(_tracked_builds_named(report_text, product_id, record.update_version)) > 1 and \
            classify_target_outcome(report_text, record.update_version).outcome != OUTCOME_AFFECTED:
        reason = "multiple_builds_named_target_not_blamed"
    elif not _url_specific(str(row.get("source_url") or ""), source_type):
        reason = "source_url_not_specific_report"
    elif source_date_pass is False:
        reason = "source_date_before_or_unverified_against_release"
    elif vendor_reason := acrobat_vendor_authority(str(row.get("report_title") or ""), report_text):
        reason = vendor_reason
    elif not acrobat_strong_issue_match(report_text):
        reason = "not_a_real_issue_report"

    row["counted"] = reason is None
    row["exclusion_reason"] = reason
    row["source_weight"] = 1
    return row


def evaluate_candidates(product_id: str, record: PatchRecord, candidates: list[dict[str, Any]], captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = _canonical_url(str(candidate.get("source_url") or ""))
        if not url or url.lower() in seen:
            continue
        seen.add(url.lower())
        row = row_from_candidate(product_id, record, {**candidate, "source_url": url}, captured_at)
        if row.get("counted") is True:
            accepted.append(row)
            continue
        # Carry the FULL candidate text and the original post date on the REJECTED row only.
        # The persisted row keeps a truncated excerpt, and an update attribution is routinely
        # stated further into a post than the excerpt reaches -- classifying the excerpt would
        # silently discard the reports Levels 2 and 3 exist to recover. Transient by design:
        # rejected rows are never written to the evidence file.
        rejected.append({**row,
                         "tier2_full_text": str(candidate.get("report_text") or "")[:8000],
                         "original_post_date": str(candidate.get("original_post_date") or ""),
                         "author_rank": str(candidate.get("author_rank") or "")})
    return accepted, rejected


def _method_status(candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if accepted and errors:
        return "partial"
    if accepted:
        return "success"
    if candidates and errors:
        return "partial"
    if candidates:
        return "no_results"
    if errors:
        reasons = " ".join(str(e.get("reason") or "") for e in errors).lower()
        if any(token in reasons for token in ("blocked", "challenge", "captcha", "rate_limited", "http_401", "http_403", "http_429")):
            return "blocked"
        return "broken"
    return "no_results"


def _blocked_reason(errors: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for error in errors:
        reason = str(error.get("reason") or "fetch_failed")
        counts[reason] = counts.get(reason, 0) + 1
    return "; ".join(f"{reason} x{count}" if count > 1 else reason for reason, count in counts.items())


def apply_consensus_writeback(product_id: str, update_version: str) -> bool:
    from apply_consensus_to_records import _index_generated_records, apply_collector_record_fields, run_dry_run
    from patch_collectors.base import load_front_matter_and_body

    records_index = _index_generated_records()
    results = run_dry_run(
        evidence_path=EVIDENCE_PATH,
        product_id_filter=product_id,
        is_candidate_mode=False,
        records_index=records_index,
        write_requested=True,
    )
    matches = [item for item in results if item["update_version"] == update_version]
    if len(matches) != 1 or not matches[0].get("would_write"):
        return False
    result = matches[0]
    # The dry-run already resolved this group's record by CANONICAL identity
    # (apply_consensus_to_records._result_for_group -> records_index.get(patch_key(pid, ver, build))),
    # so reuse that resolution instead of re-deriving a key here. Re-deriving is what broke: the index
    # has been keyed by the identity TRIPLE since #58 (4fe9e415), while this 2-tuple predates it and
    # therefore missed every record, leaving this writeback silently inert. Reusing the resolved path also guarantees the write lands on the
    # same record the gates were evaluated against, and is build-exact for free. Fail closed when the
    # group resolved to no record -- never fall back to a version-level pick.
    record_rel = result.get("matched_generated_record_path")
    if not record_rel:
        return False
    record_path = ROOT / record_rel
    fields = dict(result["proposed_fields_if_written"])
    data, _body = load_front_matter_and_body(record_path)
    comparable = {k: v for k, v in fields.items() if k != "status_events_append"}
    if all(data.get(k) == v for k, v in comparable.items()):
        return False
    # Report whether bytes actually changed, not merely that we reached the write.
    # `comparable` above always differs (proposed_fields carries a fresh record_last_updated), so
    # the early-exit never fires; the collector boundary then recomputes substantiveness EXCLUDING
    # that timestamp and can legitimately write nothing. Returning True regardless would report
    # record_updated for a no-op -- and in the OBS caller it would suppress the count fallback that
    # runs only `if not record_updated`.
    return bool(apply_collector_record_fields(record_path, fields)["write_plan"]["fields"])


class AdobeAcrobatCollector(ProductCollector):
    """Community-evidence collector for one Acrobat edition (Reader or Pro)."""

    def __init__(self, product_id: str) -> None:
        if product_id not in EDITION_CONFIG:
            raise ValueError(f"unsupported acrobat product_id: {product_id}")
        self.product_id = product_id
        self.edition = EDITION_CONFIG[product_id]

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        budget = getattr(context, "budget", None)
        _set_active_budget(budget)  # bounds every Acrobat Community/Algolia/Reddit request in this collector
        # The finally resets on EVERY exit -- success, ordinary bounded termination, ownership violation,
        # any exception, or a collector-deadline breach -- so a second Acrobat invocation (Reader then Pro)
        # can never inherit the first's active budget. Serial execution makes this module global safe.
        try:
            captured_at = utc_now()
            results: list[dict[str, Any]] = []
            records = generated_records(self.product_id, context.target_versions, include_archived=bool(context.target_versions))
            records = _newest_first(records)
            return self._collect_records(records, context, captured_at, budget, results)
        finally:
            _set_active_budget(None)

    def _collect_records(self, records: Any, context: CollectorContext, captured_at: str, budget: Any,
                         results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for record in records:
            # Bounded stop: once the collector's discovery budget (deadline minus the reserved
            # finalization tail) is spent, stop processing further records and return what we have. This
            # is a NORMAL partial outcome -- prior records' evidence + health survive; the collector
            # commits. (The hard collector deadline breach -> CollectorBudgetExhausted is the emergency
            # backstop, raised by the runner, that rolls back.)
            if budget is not None and budget.collector_finalize_expired():
                rb.emit("collector_budget_stop", product_id=self.product_id,
                        remaining_records=len(records) - len(results), reason="collector_finalize")
                break
            accepted, rejected, method_health = self.collect_for_record(record, context, captured_at)
            result: dict[str, Any] = {
                "product_id": self.product_id,
                "version": record.update_version,
                "mode": "write" if context.write else "dry-run",
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [row["source_url"] for row in accepted],
                "rejection_reasons": _rejection_counts(rejected),
                "method_health": method_health,
            }
            if context.write:
                added, total, rows = append_evidence_rows(accepted)
                structured = len(counted_rows(rows, self.product_id, record.update_version))
                record_updated = apply_consensus_writeback(self.product_id, record.update_version) if accepted else False
                result.update({
                    "evidence_rows_added": added,
                    "evidence_rows_total": total,
                    "counted_for_version": structured,
                    "record_updated": record_updated,
                })
            results.append(result)
            # Levels 2 and 3, from THIS record's rejections while they are still in hand. Rejected
            # rows are transient by design, so the tiers are built here rather than in the runner,
            # which only ever sees counts. See lib/acrobat_tiering.
            self._collect_tiers(record, rejected, captured_at)
        self._write_tiers(context)
        return results

    # --- Levels 2 and 3 ---------------------------------------------------------------------
    # Kept on the collector so Acrobat stays on its existing production routing: no runner change,
    # no orchestration-graph onboarding (the graph binds product_ids[0], which would promote Reader
    # and silently skip Pro). The tiering rules themselves live in lib/acrobat_tiering, over the
    # product-neutral primitives PowerPoint already uses.

    def _tier_windows(self) -> list[Any]:
        from lib.acrobat_tiering import build_release_windows  # noqa: PLC0415
        if getattr(self, "_windows_cache", None) is None:
            patches = [{"product_id": pid, "update_version": rec.update_version,
                        # Acrobat's canonical identity is the DC version; there is no second build
                        # token, so the window key carries the version in both slots.
                        "target_build": rec.update_version,
                        "released_on": rec.update_published_at[:10]}
                       for pid in ACROBAT_PRODUCT_IDS for rec in generated_records(pid)]
            self._windows_cache = build_release_windows(patches)
        return self._windows_cache

    def _confirmed_urls(self) -> set[str]:
        """URLs already visible at Level 1 for THIS product. One report, one level."""
        if getattr(self, "_confirmed_cache", None) is None:
            from .base import load_evidence  # noqa: PLC0415
            rows = load_evidence(EVIDENCE_PATH) if EVIDENCE_PATH.exists() else []
            self._confirmed_cache = {
                str(r.get("source_url") or "").strip().rstrip("/").lower()
                for r in rows if r.get("counted") is True and r.get("product_id") == self.product_id}
        return self._confirmed_cache

    def _collect_tiers(self, record: PatchRecord, rejected: list[dict[str, Any]],
                       captured_at: str) -> None:
        from lib import acrobat_tiering as at  # noqa: PLC0415
        if getattr(self, "_tier2_rows", None) is None:
            self._tier2_rows, self._tier3_rows = [], []
            self._tier_seen2, self._tier_seen3 = set(), set()
        windows = self._tier_windows()
        applicability = record_applicability(record)
        confirmed = self._confirmed_urls()
        for row in rejected:
            linked = at.acrobat_update_linked_from_rejection(
                row, windows=windows, captured_at=captured_at, safety=_SAFETY,
                applicability=applicability, exclude_urls=confirmed)
            if linked is not None:
                if linked.report_id not in self._tier_seen2:
                    self._tier_seen2.add(linked.report_id)
                    self._tier2_rows.append(linked.as_dict())
                continue
            recent = at.acrobat_recent_from_rejection(
                row, windows=windows, captured_at=captured_at, safety=_SAFETY,
                applicability=applicability, exclude_urls=confirmed)
            if recent is not None and recent.report_id not in self._tier_seen3:
                self._tier_seen3.add(recent.report_id)
                self._tier3_rows.append(recent.as_dict())

    def _write_tiers(self, context: CollectorContext) -> None:
        """Merge this run's tier rows into the two published files, evicting on promotion."""
        from lib import acrobat_tiering as at  # noqa: PLC0415
        from lib.recent_reports import load_recent, merge_recent_reports, write_recent  # noqa: PLC0415
        fresh2 = list(getattr(self, "_tier2_rows", None) or [])
        fresh3 = list(getattr(self, "_tier3_rows", None) or [])
        confirmed = self._confirmed_urls()
        merged2, stats2 = at.merge_tier2_rows(
            [r for r in at.load_tier2(TIER2_PATH) if r.get("product_id") == self.product_id]
            if TIER2_PATH.exists() else [], fresh2, confirmed_urls=confirmed)
        # A report that has since become Level 1 OR Level 2 is no longer a Level-3 row. Only rows
        # visible at a HIGHER level evict -- never the whole of the other file, which is what made
        # the PowerPoint layer delete itself on the run after it was populated.
        higher = set(confirmed) | {str(r.get("source_url") or "").strip().rstrip("/").lower()
                                   for r in merged2
                                   if r.get("classification") == at.TIER_UPDATE_LINKED}
        merged3, stats3 = merge_recent_reports(
            [r for r in load_recent(TIER3_PATH) if r.get("product_id") == self.product_id]
            if TIER3_PATH.exists() else [], fresh3, promoted_urls=higher)
        rb.emit("acrobat_tiers", product_id=self.product_id, mode="write" if context.write else "dry",
                level2_fresh=len(fresh2), level2_stored=len(merged2), level2_stats=stats2,
                level3_fresh=len(fresh3), level3_stored=len(merged3), level3_stats=stats3)
        if not context.write:
            return
        # Each edition owns only its own rows in the shared files, so a Reader run must not drop
        # Pro's rows and vice versa.
        others2 = [r for r in at.load_tier2(TIER2_PATH) if r.get("product_id") != self.product_id] \
            if TIER2_PATH.exists() else []
        others3 = [r for r in load_recent(TIER3_PATH) if r.get("product_id") != self.product_id] \
            if TIER3_PATH.exists() else []
        at.write_tier2(others2 + merged2, TIER2_PATH)
        write_recent(others3 + merged3, TIER3_PATH)

    def collect_for_record(self, record: PatchRecord, context: CollectorContext, captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        methods = (
            # Primary, CI-reachable: keyless inSided/Algolia JSON discovery + getTopics content.
            ("adobe_community_algolia_search", ADOBE_COMMUNITY_SOURCE_TYPE, adobe_community_algolia_search_candidates),
        )
        # RETIRED, not deleted -- their health rows stay honest, they just stop costing time.
        # Measured over the whole recorded history, 143 runs each:
        #   adobe_community_algolia_search  0 blocked, 83 success, 128 accepted reports
        #   adobe_community_search        143 blocked (100%),        0 accepted   <- CloudFront
        #   reddit_search                 142 blocked (99%),         0 accepted   <- robots + 403
        # Keeping a method that has never once returned a candidate is not free: this collector is
        # bounded by a wall-clock budget and stops mid-corpus when it expires, so every second the
        # two dead methods spend failing is a record at the END of the list -- the RECENT one -- that
        # is never reached at all. They were costing the reach they were supposed to widen.
        if _retired_methods_enabled():
            methods = methods + (
                ("adobe_community_search", ADOBE_COMMUNITY_SOURCE_TYPE, adobe_community_search_candidates),
                ("reddit_search", REDDIT_SOURCE_TYPE, reddit_search_candidates),
            )
        all_accepted: list[dict[str, Any]] = []
        all_rejected: list[dict[str, Any]] = []
        method_health: list[dict[str, Any]] = []
        accepted_urls: set[str] = set()
        budget = getattr(context, "budget", None)
        for method_id, source_type, fn in methods:
            errors: list[dict[str, Any]] = []
            if budget is not None:
                budget.start_method(method_id)  # per-method deadline (capped by remaining collector-finalize)
            candidates = fn(self.edition, record, context, errors)
            accepted, rejected = evaluate_candidates(self.product_id, record, candidates, captured_at)
            for row in accepted:
                url = str(row.get("source_url") or "").lower()
                if url in accepted_urls:
                    continue
                accepted_urls.add(url)
                all_accepted.append(row)
            all_rejected.extend(rejected)
            method_health.append(method_health_row(
                product_id=self.product_id,
                update_version=record.update_version,
                method_id=method_id,
                source_type=source_type,
                status=_method_status(candidates, accepted, rejected, errors),
                candidates_found=len(candidates),
                accepted_reports=len(accepted),
                rejected_reports=len(rejected),
                blocked_reason=_blocked_reason(errors) or None,
                last_run=captured_at,
                notes=f"acrobat community collector; edition={self.product_id}",
            ))
        return all_accepted, all_rejected, method_health


def _rejection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("exclusion_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


_SAFETY = sys.modules[__name__]
