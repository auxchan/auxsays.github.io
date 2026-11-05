"""Windows 11 community-evidence collector (Microsoft Learn Q&A + Microsoft Tech Community).

Discovers real Windows 11 user reports from TWO independent communities and applies ONE
authority to both:

  * Microsoft Learn Q&A (learn.microsoft.com/answers) via its search-RSS API, driving each
    search by the *exact current patch identity* already captured on the generated record
    (target_kb / target_os_build);
  * Microsoft Tech Community (techcommunity.microsoft.com) by walking the Windows discussion
    sitemaps and hydrating threads whose URL already carries a KB or OS build.

It then applies deterministic acceptance gates so a report counts ONLY when it names the
record's current KB or OS build. It reuses the fail-closed Windows identity gate added
in PR #14, so evidence for an older KB/build can never count after a train rolls over.

DISCOVERY DIVERSITY IS NOT ACCEPTANCE DIVERGENCE. Both methods feed `evaluate_candidates`,
sharing one claims map, so one report is one row on one patch whichever community found it.

Deterministic + repo-owned: no AI, no manual candidate approval. Discovery is
keyword-anchored (search by exact KB/build); acceptance is a fixed ordered rule set.

Activation — LIVE IN PRODUCTION, behind a default-off flag. The collector is registered by
run_patch_evidence_collection.py only when AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK is
exactly "true", and obs-evidence-collection.yml sets that in the env of the scheduled
`--write` step, so it runs on every 6-hourly cycle. (This paragraph previously said the
collector was "NOT wired to the production runner yet" and would be registered by "a later
PR". That later PR happened; the same stale claim had already been corrected once in the
runner itself, where it made the Windows writeback look unreachable during an audit.)

Read-only local dry-run (never writes evidence or records):
    cd auxsays/scripts && python -m patch_collectors.microsoft_windows [--update-version 24H2] [--since-days 45]
It builds a write=False CollectorContext, so append_evidence_rows / apply_consensus_writeback
are never reached; it only fetches Learn Q&A and prints candidate/acceptance/health JSON.
"""
from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import (
    EVIDENCE_PATH,
    CollectorContext,
    PatchRecord,
    ProductCollector,
    WINDOWS_PRODUCT_ID,
    ROOT,
    append_evidence_rows,
    finalize_method_health_delta,
    counted_rows,
    date_part,
    exact_version_match,
    generated_records,
    load_evidence,
    load_front_matter_and_body,
    make_evidence_row,
    method_health_row,
    slug,
    source_url_is_specific,
    text_describes_issue,
    utc_now,
    windows_identity_gate,
)
from lib.patch_identity import patch_key
from . import elevenforum_source as elevenforum
from . import microsoft_learn_qna_source as learn_qna
from . import runtime_budget as rb
from . import techcommunity_source as techcommunity

PRODUCT_ID = WINDOWS_PRODUCT_ID
METHOD_ID = "learn_qna_search_rss"
SOURCE_TYPE = "microsoft_learn_qna"
SOURCE_NAME = "Microsoft Learn Q&A"

# --- second discovery method -------------------------------------------------
#
# WHY A SECOND METHOD, AND WHY THIS ONE. Windows had exactly one discovery method, against a
# monitoring floor of two (`monitoring_min_healthy_methods: 2`), so its public coverage state could
# never be honest. Five candidates were measured end to end rather than argued about:
#
#   Microsoft Tech Community   sitemaps allowed by robots.txt and explicitly advertised there; 624
#                              board sitemaps, of which windows11 / windows10space /
#                              windowsinsiderprogram / windows-servicing carry server-rendered
#                              user threads. 132 identity-bearing threads since 2025-12-01, 22
#                              accepted by the UNCHANGED authority across 11 records, zero overlap
#                              with Learn Q&A (different domain). CHOSEN.
#   Super User (Stack Exchange API)  reachable, keyless, 300/day quota. 176 questions since
#                              2025-12-01, 16 carrying any KB/build token, ~2 that would survive
#                              exact-patch authority. Genuine but an order of magnitude thinner,
#                              and it spends a shared daily quota. Not chosen; see the report.
#   Reddit                     robots.txt is `User-agent: * / Disallow: /`. Foreclosed on policy,
#                              not on convenience.
#   Microsoft Q&A tag feeds    same site and same corpus as the existing method: a second way to
#                              ask the SAME community, so a Learn outage takes both down together.
#                              That is a method counter, not coverage.
#   Open-web federation        federates Learn Q&A and Stack Exchange, i.e. it is the union of
#                              lanes above rather than an independent one.
#
# ATTRIBUTION SAFETY. `techcommunity_source.thread_candidate` reads the JSON-LD `mainEntity` --
# the OPENING POST only. Replies belong to other people, and folding them in would let a stranger's
# KB become this reporter's patch identity.
TECHCOMMUNITY_METHOD_ID = "techcommunity_windows_sitemap"
TECHCOMMUNITY_SOURCE_TYPE = "microsoft_tech_community"
TECHCOMMUNITY_SOURCE_NAME = "Microsoft Tech Community"

# Measured Windows spaces. windows-servicing / windowsosplatformdiscussions / windows-deployment are
# included for servicing threads; the server, PowerShell, IoT and blog sitemaps are not Windows 11
# client user reports and are deliberately absent.
TECHCOMMUNITY_SPACES: tuple[str, ...] = (
    "sitemap_windows11.xml.gz",
    "sitemap_windows10space.xml.gz",
    "sitemap_windowsinsiderprogram.xml.gz",
    "sitemap_windows-servicing.xml.gz",
    "sitemap_windowsosplatformdiscussions.xml.gz",
    "sitemap_windows-deployment.xml.gz",
)

# The cheap first stage. 5,712 Windows threads were modified inside a nine-month window; hydrating
# all of them to find a handful is not a production behaviour, so discovery admits only threads
# whose URL SLUG already carries a KB or an OS build. This bounds the walk at the cost of recall --
# a thread naming its KB only in the body is not reachable this way, and the report says so.
WINDOWS_IDENTITY_SLUG_RE = re.compile(r"kb\d{7}|(?<!\d)2[0-9]{4}[-.]\d{3,5}(?!\d)", re.I)

# A hard ceiling on stage two, so an unbounded `--since` cannot turn one run into thousands of
# fetches. Reaching it is reported as `partial`, never as success.
TECHCOMMUNITY_MAX_HYDRATIONS = 400

# The window used when the caller supplied none. Matches the workflow's routine `--since-days 45`.
TECHCOMMUNITY_DEFAULT_WINDOW_DAYS = 45


# --- third discovery method: Windows 11 Forum (SHIPPED DISABLED) -------------
#
# elevenforum.com (XenForo). Opening posts only, three approved support listings, bounded request
# budget -- see patch_collectors/elevenforum_source.py. It is a DISCOVERY method: its candidates go
# through the same `evaluate_candidates`, the same claims map and the same identity, intent, date and
# one-report-one-patch rules as the other two. Nothing here changes what counts.
#
# DISABLED MEANS DISABLED. With the flag below absent (or anything but the exact string "true"):
#   * no elevenforum.com request is made, ever;
#   * no pool is built, so `collect_for_record` receives `elevenforum_pool=None` and runs the exact
#     code path it ran before this method existed;
#   * NO health row is emitted for it. A `disabled` row would add a row to the public health store
#     for a method that has never run, and the store retains what a run does not emit; the method
#     simply does not exist in the output until it is activated (contrast the retired-method case,
#     where a stale `blocked` row already exists and a fresh `disabled` one is the honest fix).
#   * the ownership manifest (lib/collector_ownership.py) does not list this method id or source type,
#     so even with the flag set a `--write` fails closed instead of storing a row. Activation is
#     therefore a deliberate edit in a reviewed PR, not an environment variable.
#
# ACTIVATION CAVEAT (ENGINEERING_LEDGER AUX-063, closed by AUX-067 for this shape). The shared authority
# accepts a thread when a record's build or feature-train token appears ANYWHERE in the opening post,
# including as the reporter's current baseline. Thread 50506 (a 26H2 enablement-package boot BSOD whose
# author is back on 25H2 26200.9711) was attributed to the 25H2 record; `identity_not_the_subject` now
# rejects it because the title names another KB. A baseline whose title names no competing KB or build (AUX-067
# residual R1) is closed for future acceptance by `identity_not_linked_to_issue` (AUX-076); activation still
# needs its own measurement, because the role vetoes are first exercised on full opening posts.
ELEVENFORUM_METHOD_ID = "elevenforum_windows_listing"
ELEVENFORUM_SOURCE_TYPE = elevenforum.DEFAULT_SOURCE_TYPE
ELEVENFORUM_SOURCE_NAME = elevenforum.DEFAULT_SOURCE_NAME
ELEVENFORUM_ENABLE_ENV = "AUXSAYS_ENABLE_WINDOWS_ELEVENFORUM_DISCOVERY"


def elevenforum_discovery_enabled(env: dict[str, str] | None = None) -> bool:
    """Default-off gate. True ONLY for the exact canonical boolean ``true`` (case-insensitive,
    trimmed); absent, empty, ``false``, ``0``, ``1``, ``yes`` and ``on`` are all False."""
    source = os.environ if env is None else env
    return str(source.get(ELEVENFORUM_ENABLE_ENV, "")).strip().lower() == "true"


def default_since_day(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(1, days))).strftime("%Y-%m-%d")

# --- deterministic content classifiers (no AI) -------------------------------
KB_TOKEN_RE = re.compile(r"\bKB\d{6,7}\b", re.I)
BUILD_TOKEN_RE = re.compile(r"\b\d{5}\.\d{3,5}\b")
FEATURE_TOKEN_RE = re.compile(r"\b2\dH[12]\b", re.I)

# Concrete Windows user-facing symptoms (a real report, not a how-to question).
WINDOWS_ISSUE_RE = re.compile(
    r"\b(?:bsod|blue[\s-]?screen|bug[\s-]?check|stop\s+(?:code|error)|0x[0-9a-f]{6,8}|"
    r"won'?t\s+boot|fails?\s+to\s+boot|boot\s*loop|black\s+screen|"
    r"(?:install(?:ation)?|update|upgrade)\s+(?:fail(?:ed|s|ure|ing)?|error)|"
    r"fails?\s+to\s+install|won'?t\s+install|error\s+0x|rolls?\s+back|rolled\s+back|rollback|"
    r"printer|printing|no\s+(?:audio|sound|network|internet|wi[\s-]?fi|display|signal)|"
    r"driver\s+(?:crash|fail)|crash(?:es|ing|ed)?|freez(?:e|es|ing|en)|hang(?:s|ing|ed)?|"
    r"not\s+working\s+after|broke(?:n)?\s+after|stopped\s+working\s+after)\b",
    re.I,
)
HOW_TO_RE = re.compile(
    r"\b(?:how\s+(?:do|can|would|should)\s+i|how\s+to|where\s+(?:is|do|can)|is\s+it\s+safe\s+to|"
    r"should\s+i\s+(?:install|update|upgrade)|which\s+version|what'?s\s+the\s+best|recommend(?:ation)?)\b",
    re.I,
)
OFFICIAL_NOTE_RE = re.compile(
    r"\b(?:release\s+notes|change\s*log|what'?s\s+new|known\s+issues\s+(?:for|in|list)|"
    r"official\s+(?:documentation|guidance|list))\b",
    re.I,
)
ANNOUNCE_RE = re.compile(
    r"\b(?:now\s+available|is\s+available|announc(?:e|es|ing|ed|ement)|general\s+availability|"
    r"rolling\s+out|is\s+released|has\s+been\s+released|is\s+now\s+released)\b",
    re.I,
)
TENANT_RE = re.compile(
    r"\b(?:tenant|service\s+health|admin\s+center|message\s+center|exchange\s+online|"
    r"sharepoint\s+online|onedrive\s+for\s+business|microsoft\s+365\s+(?:service|admin)|"
    r"service\s+(?:incident|degradation|outage|advisory))\b",
    re.I,
)
ACCOUNT_RE = re.compile(
    r"\b(?:sign[\s-]?in|log[\s-]?in|password\s+reset|account\s+(?:locked|issue|problem)|"
    r"activation\s+(?:error|fail)|licens(?:e|ing)\s+(?:error|issue)|azure\s+ad|entra\s+id|"
    r"\bmfa\b|multi[\s-]?factor|authenticat(?:e|ion)\s+(?:error|fail))\b",
    re.I,
)
LATEST_RE = re.compile(
    r"\b(?:latest|newest|most\s+recent|recent|last)\s+(?:update|patch|cumulative\s+update|build)\b|"
    r"\bthis\s+month'?s\s+(?:update|patch)\b|\brecent\s+windows\s+update\b",
    re.I,
)
PATCH_TUESDAY_RE = re.compile(r"\bpatch\s+tuesday\b", re.I)
MONTH_YEAR_RE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+20\d{2}\b",
    re.I,
)

# --- intent / update-attribution filter (hardening) --------------------------
# Identity + concrete-issue + date gates are necessary but NOT sufficient: a post can carry
# the exact KB/build yet be a question, a config request, a driver how-to, or a meta/spam
# post rather than a confirmed patch REGRESSION. A row counts only when the issue is
# ATTRIBUTED to the exact update via one of three deterministic patterns:
#   A  install/update FAILURE of the exact patch (INSTALL_FAILURE_RE)
#   B  temporal breakage tied to the update, incl. "uninstalling KB fixed it" (TEMPORAL_REGRESSION_RE)
#   C  the record's OWN KB/build in the post TITLE next to an issue (build_as_affected_state)

INSTALL_FAILURE_RE = re.compile(
    r"(?i)\b(?:"
    r"will\s+not\s+install|won'?t\s+install|wont\s+install|"
    r"fail(?:ed|s|ing)?\s+to\s+(?:install|update|apply|complete)|"
    r"cannot\s+install|can'?t\s+install|unable\s+to\s+install|"
    r"install(?:ation)?\s+(?:fail(?:ed|s|ure|ing)?|error|stuck|loop)|"
    r"update\s+(?:fail(?:ed|s|ure|ing)?|error|stuck|loop)|"
    r"update\s+(?:will\s+not|won'?t|wont)\s+(?:install|complete|finish)|"
    r"update\s+not\s+(?:install\w*|function\w*|complet\w*|working)|"
    r"windows\s+update\s+not\s+(?:function\w*|working)|"
    r"updates?\s+fail(?:ed|s|ing)?|"
    r"stuck\s+(?:install\w*|updat\w*|download\w*)|"
    r"restart(?:ing|ed)?\s+to\s+install|"
    r"keeps?\s+(?:fail\w*|restart\w*)\s+to\s+install|"
    r"failed\s+attempts?\b|"
    r"rollback\s+loop|"
    r"error\s+(?:code\s+)?0x[0-9a-f]{4,8}"
    r")"
)

TEMPORAL_REGRESSION_RE = re.compile(
    r"(?i)(?:"
    r"after\b[^.]{0,45}\b(?:updat\w*|upgrad\w*|install\w*|applied|kb\s?\d{6,7}|build\s?\d{5})|"
    r"since\b[^.]{0,45}\b(?:updat\w*|upgrad\w*|install\w*|kb\s?\d{6,7})|"
    r"(?:updat\w*|upgrad\w*|install\w*|kb\s?\d{6,7})\b[^.]{0,45}\b(?:no\s+longer|stopped\s+work\w*|broke|breaks|can'?t|cannot|unable|fails?\b)|"
    r"immediately\s+after\b[^.]{0,30}\b(?:updat\w*|install\w*|kb)|"
    r"when\b[^.]{0,45}\b(?:kb\s?\d{6,7}|update)\b[^.]{0,25}\binstall\w*[^.]{0,50}\b(?:no\s+longer|can'?t|cannot|unable|fail\w*|stop\w*|broke)|"
    r"(?:no\s+longer|stopped)\s+(?:work\w*|respond\w*|abl\w*|connect\w*)\b[^.]{0,50}\b(?:updat\w*|kb\s?\d{6,7})|"
    r"(?:uninstall\w*|remov\w*|roll\w*\s*back|revert\w*)\b[^.]{0,45}\b(?:kb\s?\d{6,7}|update|patch|it)\b[^.]{0,45}\b(?:fix\w*|resolv\w*|work\w*|solv\w*|help\w*)|"
    r"(?:fix\w*|resolv\w*|work\w*\s+again|solv\w*)\b[^.]{0,45}\b(?:uninstall\w*|remov\w*|roll\w*\s*back|revert\w*)\b[^.]{0,30}\b(?:kb\s?\d{6,7}|update|patch)|"
    r"(?:uninstall\w*|remov\w*)\s+(?:the\s+)?(?:kb\s?\d{6,7}|update|patch)\b|"
    r"go\s+back\s+to\b[^.]{0,30}\b(?:previous\s+build|build\s?\d{5})|"
    r"roll\w*\s*back\s+to\s+(?:the\s+)?previous\s+build"
    r")"
)

META_SPAM_RE = re.compile(
    r"(?i)(?:rejected\s+(?:by\s+the\s+system\s+)?as\s+spam|flagged\s+as\s+spam|marked\s+as\s+spam|"
    r"this\s+(?:post|subject|message|thread)\s+(?:was|is|got)\s+(?:rejected|flagged)\b[^.]{0,20}\bspam|"
    r"very\s+strange\b[^.]{0,40}\biso\b|\bmct\b[^.]{0,15}\biso|media\s+creation\s+tool\b[^.]{0,30}\b(?:strange|weird|issues))"
)

FEATURE_QUESTION_RE = re.compile(
    r"(?i)\b(?:does\s+this\s+mean|what\s+does\s+this\s+mean|is\s+there\s+a\s+way\s+to|is\s+it\s+possible\s+to|"
    r"can\s+(?:someone|anyone)\s+(?:explain|clarify)|is\s+this\s+(?:normal|expected|by\s+design|intended)|"
    r"what'?s\s+the\s+(?:difference|meaning|point|purpose))\b"
)

HOWTO_QUESTION_RE = re.compile(
    r"(?i)\b(?:how\s+do\s+i|how\s+to\b|how\s+can\s+i|why\s+can'?t\s+i|why\s+cant\s+i|where\s+(?:do|is|can)\s+i)\b"
)

DRIVER_QUESTION_RE = re.compile(
    r"(?i)(?:"
    r"(?:intel|nvidia|amd|realtek|geforce|radeon|graphics?|display|chipset|network|wi-?fi|audio)\s+driver|"
    r"driver\s+(?:version|update|upgrade|beyond)|"
    r"(?:upgrade|update|install|roll\s*back)\s+(?:the\s+|my\s+)?(?:intel|nvidia|amd|realtek|graphics?|display|audio|chipset)\s+driver"
    r")"
)

# --- foreign-product subject -------------------------------------------------
#
# WHAT THIS CLOSES, MEASURED. `update_attributed` below is satisfied by ANY install/update
# vocabulary anywhere in the body, unlinked from the record's own KB or build. A Windows Q&A post
# about a DIFFERENT product's installer therefore attributes to whichever Windows patch the author
# happened to declare running: "Java 8 update 491 installation error code1603", "DirectX End-User
# Runtime June 2010 installation keeps failing", "Can't install Resident Evil 7 from Microsoft
# store", "Microsoft Outlook 2024 no longer synchronizes imap email from gmail". Nineteen such rows
# were measured -- 13 in a historical replay and 6 already published on live patch pages.
#
# THE TITLE, AND ONLY THE TITLE. Same shape as DRIVER_QUESTION_RE, for the same reason: the title
# is the post's primary SUBJECT, while a body names other software constantly and innocently. A
# body-scoped rule would delete genuine Windows regressions that merely name an affected app.
#
# WHY NOT A GENERAL ATTRIBUTION TIGHTENING. Measured and rejected. Requiring the attribution cue to
# sit in a clause with a Windows-update referent drops 41 of the 408 rows a full historical replay
# accepts, and the casualties are ordinary Windows reports: "Why Did My Bluetooth Stop Working
# After Win 11 Update", "2026-06 update issues", "How do I remove the recent windows update??",
# "After update no longer detecting a connected screen" -- plus every non-English report, because
# a referent lexicon is a list of English phrasings. Cue and referent routinely land in different
# clauses. That is exactly the over-deletion the OBS version-outcome veto module in lib/ documents
# (it names it in its own "WHAT THIS IS NOT" paragraph, and is deliberately NOT imported here -- a
# governed test pins that independence). This veto stays narrow instead: it fires only when the
# title's subject is a separately-updated product AND the title carries neither the record's own
# identity, nor a Windows update, nor a Windows component.
FOREIGN_PRODUCT_SUBJECT_RE = re.compile(
    r"(?i)\b(?:"
    r"teams|onedrive|outlook|office\s*(?:365|2016|2019|2021|2024)|excel|powerpoint|"
    r"microsoft\s+edge|edge|chrome|firefox|opera|brave|"
    r"java|jre|jdk|directx|visual\s+studio|vs\s*code|"
    r"sql\s+server|ssms|hlk|"
    r"steam|epic\s+games|resident\s+evil|minecraft|roblox|valorant|fortnite|"
    r"adobe|acrobat|photoshop|autocad|solidworks|"
    r"quickbooks|dropbox|zoom|slack|discord|spotify|itunes|vmware|virtualbox|docker"
    r")\b"
)

# The Windows update itself as the title's subject. "2026-05 Preview Update appears to break Excel"
# is a report ABOUT the update; Excel is the symptom. A live row the veto would otherwise delete.
WINDOWS_UPDATE_SUBJECT_RE = re.compile(
    r"(?i)(?:"
    r"\bkb\s?\d{6,7}\b|\bos\s+build\b|\b2[0-9]{4}\.\d{3,5}\b|"
    r"(?:cumulative|security|preview|quality|feature|windows)\s+updat\w*|windows\s+11\s+updat\w*|"
    r"\bpatch\s+tuesday\b|servicing\s+stack"
    r")"
)

# A Windows component named alongside the foreign product. "Virtual keyboard/Clipboard history,
# Start menu Search bar, and Outlook (MS Store) ..." is a Windows report that lists an Office app
# among several symptoms -- also a live row the veto would otherwise delete.
WINDOWS_COMPONENT_SUBJECT_RE = re.compile(
    r"(?i)\b(?:taskbar|start\s+menu|file\s+explorer|explorer\.exe|windows\s+search|clipboard|"
    r"virtual\s+keyboard|windows\s+hello|bitlocker|windows\s+defender|windows\s+update|bluetooth|"
    r"wi-?fi|printer|print\s+spooler|hyper-?v|wsl|winsxs|dism|sfc|blue\s+screen|bsod|boot|bugcheck)\b"
)

SYSTEM_SPEC_RE = re.compile(
    r"(?i)(?:"
    r"secure\s+boot\s*[=:]|csm\s+(?:support\s+)?(?:enabled|disabled)|\btpm\s*(?:2\.0|version|enabled|:)|"
    r"\bos\s+build\s*[:=]?\s*\d|\bedition\b\s*[:=]|\bprocessor\b\s*[:=]|installed\s+ram\b|system\s+type\s*[:=]|"
    r"device\s+specifications?|windows\s+specifications?|vs\.?\s*10\.0\.\d{5}|"
    r"\bbios\b\s+(?:version|supporting|setting)|dxdiag|systeminfo"
    r")"
)


# --- helpers -----------------------------------------------------------------

def _has_exact(text: str, token: str) -> bool:
    if not token:
        return False
    matched, _matched, _basis = exact_version_match(text, token)
    return bool(matched)


def _other_kbs(text: str, target_kb: str) -> set[str]:
    found = {m.upper() for m in KB_TOKEN_RE.findall(text or "")}
    return found - ({target_kb.upper()} if target_kb else set())


def _other_builds(text: str, target_build: str) -> set[str]:
    found = set(BUILD_TOKEN_RE.findall(text or ""))
    return found - ({target_build} if target_build else set())


def _other_features(text: str, target_feature: str) -> set[str]:
    found = {m.upper() for m in FEATURE_TOKEN_RE.findall(text or "")}
    return found - ({target_feature.upper()} if target_feature else set())


def describes_windows_issue(text: str) -> bool:
    """A concrete user-facing Windows problem, not a how-to/recommendation question.

    An install/update failure or an explicit temporal breakage IS a concrete issue, so
    those strong signals also qualify (and override a how-to phrasing)."""
    strong = bool(
        WINDOWS_ISSUE_RE.search(text or "")
        or INSTALL_FAILURE_RE.search(text or "")
        or TEMPORAL_REGRESSION_RE.search(text or "")
    )
    if not (text_describes_issue(text) or strong):
        return False
    if HOW_TO_RE.search(text or "") and not strong:
        return False
    return True


def build_as_affected_state(report_title: str, matched_kb: str, matched_os_build: str) -> bool:
    """Pattern C: the record's OWN current KB/build appears in the post TITLE (the problem
    statement) next to a concrete issue term -- e.g. 'Build 26200.8737 (KB...): ... bug' or
    '25H2 (26200.8737): ... boot hang'. A build that only appears in a body system-spec
    signature never triggers this."""
    title = report_title or ""
    id_in_title = bool(
        (matched_os_build and matched_os_build in title)
        or (matched_kb and re.search(re.escape(matched_kb), title, re.I))
    )
    return bool(id_in_title and (WINDOWS_ISSUE_RE.search(title) or text_describes_issue(title)))


def update_attributed(report_text: str, report_title: str, matched_kb: str, matched_os_build: str) -> bool:
    """True when the concrete issue is attributed to the exact update (pattern A/B/C)."""
    return bool(
        INSTALL_FAILURE_RE.search(report_text)
        or TEMPORAL_REGRESSION_RE.search(report_text)
        or build_as_affected_state(report_title, matched_kb, matched_os_build)
    )


# A dot inside 26200.7462 is not the end of a sentence. Splitting on bare punctuation cuts every
# build token in half, so a rule that looks for "this build, in this clause" silently never fires
# on builds at all -- which is exactly how the first version of the veto below measured zero.
_BUILD_DOT_SENTINEL = "␟"


def sentences(text: str) -> list[str]:
    """Clause-level segments, with version tokens kept whole."""
    masked = BUILD_TOKEN_RE.sub(lambda m: m.group(0).replace(".", _BUILD_DOT_SENTINEL), text or "")
    return [part.replace(_BUILD_DOT_SENTINEL, ".") for part in re.split(r"[.;!?\n]", masked)]


# "There is a new OS version for my computer: 22631.6936 that may fix this problem" -- the build is
# named as a REMEDY the reporter has not installed, not as the cause of anything. Counting it makes
# the patch's own page say one person reported a defect in it, when that person said the opposite.
PROSPECTIVE_REMEDY_RE = re.compile(
    r"(?i)\b(?:may|might|should|would|will|hopefully|supposed\s+to|meant\s+to|expected\s+to)\b"
    r"[^.;!?\n]{0,30}\b(?:fix|resolve|solve|correct|address)\w*"
)


def identity_named_as_prospective_fix(report_text: str, matched_os_build: str) -> bool:
    """The record's own BUILD is named only as a future remedy, by someone running another build.

    Deliberately narrow, and measured: over 408 rows accepted by a full historical replay this
    fires exactly once -- on the one row a hand audit had already identified as wrong -- and on
    nothing else.

    BUILD ONLY, never KB. "KB5073455 Not Offered via Windows Update on Windows 11 23H2 Pro" names
    a KB the reporter has not installed either, but that IS a report about the patch: it is not
    reaching them. A build named as a remedy carries no such complaint.

    The "another build" clause is what makes this a ROLE rule rather than a keyword rule: it holds
    only when the reporter has placed themselves somewhere else, which is the situation in which
    the target can be a remedy at all.
    """
    build = str(matched_os_build or "").strip()
    if not build:
        return False
    text = report_text or ""
    if not any(build in segment and PROSPECTIVE_REMEDY_RE.search(segment)
               for segment in sentences(text)):
        return False
    return any(token != build for token in BUILD_TOKEN_RE.findall(text))


# --- identity not linked to the issue (AUX-076, the AUX-067 residual R1) -----------------------
#
# THE INTERACTION THIS CLOSES. `update_attributed` is identity-blind (any install/update cue
# anywhere), and `build_only_in_system_specs` is consulted only when attribution already FAILED, so
# it can relabel a refusal but never veto an acceptance. A build quoted only in a spec block, a
# running statement, a diagnostic log or an upgrade-source clause therefore counted whenever any
# generic cue appeared elsewhere in the post. Measured over the 527 counted Windows rows on their
# retained text: 14 rows change, every one from counted to this reason, and nothing else moves.
#
# SCOPE. Build-only identity (no KB matched) whose title names neither the target build nor the
# target KB, and whose body contains the build. Everything else is untouched: a KB match has named
# its patch, and a title that names the build has made it the subject.
#
# ROLES. Every occurrence of the build gets exactly one role, from patterns ANCHORED AT THAT
# OCCURRENCE inside its sentence: each pattern either ends exactly at the occurrence or starts
# exactly at it. The identity filler allowed between a cue and the build is a closed list of
# identity words (Windows, 11, Pro, 25H2, OS, build, version, the, latest, update, ...) and never
# spans another build, a date, a colon label, "on", or a KB other than the "(KBnnnnnnn) (build)"
# Windows Update naming.
#   1. a VETO, tested first: source, baseline, history, prospective, platform, clean;
#   2. else a LINK -> "affected": the build named as the change, the destination of a change, an
#      update phrase attached to it, an onset at it, or a failure predicated directly on it;
#   3. else "environment" (a running statement or spec label) or "unlinked" (diagnostics only).
# A generic cue that is not anchored at the build never links: that was the R1 interaction itself,
# and it is why "On X ... since the update" and "I'm on X and since the update" are treated alike.
# The row is refused when no occurrence is "affected". An unlisted word between a cue and the build
# breaks the link, so the rule fails closed. FORWARD-ONLY: collection never rewrites a stored row
# (only accepted rows are appended, and a URL the store already holds is not appended again), so a
# stored row changes only by an audited withdrawal.
R1_B = r"(?<!\d)\d{5}\.\d{3,5}"
R1_PAREN_RE = re.compile(r"\([^()\n]{0,160}\)")
R1_SENTENCE_SPLIT_RE = re.compile(r"[.;!?\n]+")
R1_PAREN_MASK = str.maketrans({".": "\x1b", ";": "\x1d", "?": "\x1a", "!": "\x19"})
R1_UNMASK = str.maketrans({"\x1f": ".", "\x1b": ".", "\x1d": ";", "\x1a": "?", "\x19": "!"})
R1_ID_WORDS = (
    r"the|a|an|new|newest|latest|recent|newer|current|this|that|it|its|windows|win|win1[01]|11|10|pro|"
    r"home|enterprise|education|edu|iot|ltsc|n|single|language|workstations?|for|os|build|version|ver|v|release|"
    r"preview|insider|beta|dev|canary|channel|cumulative|security|quality|monthly|optional|"
    r"non-security|update|x64|arm64|based|systems?|v?2\dh[12]|\d{4}-\d{2}"
)
# No colon: "OS: X" / "Version: X" is a spec LABEL, and a label never continues a change phrase.
R1_FILLER = (r"(?:[\s()\[\]\"'“”‘’,;/–—-]|\(\s*kb\s?\d{6,7}\s*\)|\b(?:" + R1_ID_WORDS + r")\b){0,40}?")
R1_CHANGE = (
    r"(?:updat(?:e|es|ed|ing)|upgrad(?:e|es|ed|ing)|(?<!clean\s)(?<!fresh\s)install(?:s|ed|ing)?|"
    r"patch(?:es|ed|ing)?|download(?:s|ed|ing)?|received|(?<!'ve\s)(?<!’ve\s)(?<!have\s)(?<!has\s)got|"
    r"moved|went|jumped|bumped|switched|pushed|rolled\s+out|"
    r"put\s+(?:me|us|it|him|her|them|(?:my|our|the)\s+\w+)\s+on|"
    r"brought\s+(?:me|us|it|(?:my|our|the)\s+\w+)\s+(?:up\s+)?to)"
)
R1_TO = r"(?:\s+(?:up\s+)?(?:to|onto|auf|naar|vers|zu|na))?"
R1_CHANGE_WORD_RE = re.compile(r"(?i)\b(?:updat\w*|upgrad\w*|install\w*|moved|went|jumped|bumped|switch\w*|migrat\w*)\b")
R1_UPDATE_NP = (
    r"(?:(?:the|a|an|this|that|last|latest|recent|most|new|newest|todays|today['’]?s|yesterday['’]?s|"
    r"tonight['’]?s|last\s+night['’]?s|this\s+morning['’]?s|this\s+week['’]?s|last\s+week['’]?s|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day['’]?s|patch\s+tuesday['’]?s?|"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)(?:['’]s)?|"
    r"\d{4}-\d{2}|windows|win|11|monthly|cumulative|security|quality|preview|optional|feature|"
    r"automatic|overnight|kb\s?\d{6,7})\s+){0,6}(?:update|upgrade|patch)s?\b"
)
R1_VERSIONISH = r"(?:the\s+)?(?:build\s+|version\s+|windows\s+(?:11\s+)?|os\s+|v)?(?:\d|2\dh|latest|newest|next|new|newer|insider)"
R1_INSTALL_OBJECT = (r"\s+(?:the|a|an|any|this|that|my|our|its|kb\s?\d|\d{4}-\d{2}|next|new|latest|january|february|march|"
                     r"april|may|june|july|august|september|october|november|december|[\w.-]+\s+(?:update|pack|app|driver|feature))\b")
R1_PLATFORM_HOST = (r"(?:(?:my|our|a|the|this|his|her)\s+)?(?:(?:pc|laptop|machine|device|computer|system|desktop|notebook)s?\s+)?"
                    r"(?:running\s+|with\s+)?")


def _r1(rx: str) -> re.Pattern:
    return re.compile(rx.replace("<B>", R1_B), re.I)


# Each entry: (role, kind, pattern[, second pattern]). kind "pre": the pattern must END at the
# occurrence (searched with \Z over the sentence up to the occurrence's end); "post": it must START at
# the occurrence; "mid": both a pre and a post pattern hold for the same occurrence.
R1_VETOES = (
    ("source", "pre", _r1(r"\bfrom\b(?:(?!\bto\b)[^.;!?\n]){0,40}<B>\Z")),
    ("source", "post", _r1(r"<B>\W{0,6}(?:to|->|→|=>)\s*" + R1_VERSIONISH)),
    ("source", "mid", _r1(r"\b(?:upgrad\w*|updat\w*|migrat\w*|mov\w*)\s+(?:(?!to\b|from\b)\w+\s+){0,4}<B>\Z"),
     _r1(r"<B>\b[^.;!?\n]{0,40}?\bto\s+" + R1_VERSIONISH)),
    ("baseline", "pre", _r1(r"\b(?:was|were|had\s+been|used\s+to\s+be)\s+(?:on|running|using|at)\b" + R1_FILLER + r"<B>\Z")),
    ("baseline", "pre", _r1(r"\bprevious(?:ly)?\b(?:\s+(?:on|running|using|installed|had))?" + R1_FILLER + r"<B>\Z")),
    ("baseline", "pre", _r1(r"\b(?:back|revert(?:ed|ing)?|downgrad\w*)\s+to\b" + R1_FILLER + r"<B>\Z")),
    ("baseline", "pre", _r1(r"\b(?:old|older|prior|last\s+(?:good|working|known\s+good)|known\s+good|stable)\s+"
                            r"(?:build|version|os|update)\b" + R1_FILLER + r"<B>\Z")),
    ("history", "pre", _r1(r"\bsuccessfully\s+installed\b" + R1_FILLER + r"<B>\Z")),
    ("history", "pre", _r1(r"\bupdate\s+history\b[^.;!?\n]{0,80}<B>\Z")),
    ("history", "post", _r1(r"<B>\W{0,6}(?:[\w-]+\W+){0,2}?successfully\s+installed\b")),
    ("prospective", "mid", _r1(r"\b(?:will|would|should|could|might|may|does|did|hopefully|supposed\s+to|meant\s+to|"
                               r"expected\s+to|going\s+to)\b[^.;!?\n]{0,40}<B>\Z"),
     _r1(r"<B>[^.;!?\n]{0,40}?\b(?:fix|resolve|solve|correct|address)\w*")),
    ("prospective", "post", _r1(r"<B>[^.;!?\n]{0,12}?\b(?:may|might|should|would|will|is\s+supposed\s+to|"
                                r"is\s+expected\s+to|is\s+meant\s+to)\s+(?:\w+\s+)?(?:fix|resolve|solve|correct|address)\w*")),
    ("prospective", "post", _r1(r"<B>\W{0,4}(?:to|in\s+order\s+to)\s+(?:fix|resolve|solve|correct|address)\w*")),
    ("prospective", "pre", _r1(r"\b(?:should|shall|can|could)\s+(?:i|we)\s+(?:safely\s+)?(?:install|update\s+to|upgrade\s+to|"
                               r"apply|get)\b" + R1_FILLER + r"<B>\Z")),
    ("prospective", "pre", _r1(r"\bis\s+it\s+safe\s+to\s+(?:install|update\s+to|upgrade\s+to|apply)\b" + R1_FILLER + r"<B>\Z")),
    ("prospective", "pre", _r1(r"\b(?:wait(?:ing)?\s+for|hoping\s+for)\b" + R1_FILLER + r"<B>\Z")),
    # Something else is installed / applied ON the build: the build is the platform, not the patch.
    # (a) an install-type VERB, any object ("fails to install on X", "installing the Media Feature
    # Pack on X"); (b) update/upgrade/patch followed by a predicate or an object before "on" ("Windows
    # Update fails on X"); (c) a qualified update noun naming ANOTHER update ("the next update on X",
    # "the Defender update on X"). A bare "the update on X" is none of these: it names the build as
    # the update (see the named links), exactly as "the update to X" does.
    ("platform", "pre", _r1(r"\b(?:install(?:s|ed|ing)?|download\w*|apply\w*|applied|enabl\w*|deploy\w*)\b"
                            r"(?:(?!\b(?:put|got|moved|brought|landed|placed)\b)[^.;!?\n]){0,60}?\bon\s+" + R1_PLATFORM_HOST
                            + R1_FILLER + r"<B>\Z")),
    ("platform", "pre", _r1(r"\b(?:updat\w*|upgrad\w*|patch\w*)\s+(?!on\b)(?:(?!\b(?:put|got|moved|brought|landed|placed)\b)"
                            r"[^.;!?\n]){1,60}?\s+on\s+" + R1_PLATFORM_HOST + R1_FILLER + r"<B>\Z")),
    ("platform", "pre", _r1(r"\b(?:next|following|subsequent|newer|later|other|another|defender|definitions?|driver|firmware|"
                            r"bios|app|apps|store|office|edge|teams|framework|kb\s?\d{6,7}|january|february|march|april|may|"
                            r"june|july|august|september|october|november|december)\s+(?:[\w.-]+\s+){0,2}?"
                            r"(?:update|upgrade|patch)e?s?\s+on\s+" + R1_PLATFORM_HOST + R1_FILLER + r"<B>\Z")),
    ("clean", "post", _r1(r"<B>(?:(?!fail|error|crash|broke|stuck|won['’]?t|can['’]?t|cannot)[^.;!?\n]){0,60}?"
                          r"\bwithout\s+(?:any\s+)?(?:problems?|issues?|trouble|a\s+hitch|incident)")),
    ("clean", "post", _r1(r"<B>\W{0,4}(?:no|zero)\s+(?:problems?|issues?)\b")),
)
R1_LINKS = (
    ("named", "pre", _r1(r"\b" + R1_CHANGE + r"\b" + R1_TO + R1_FILLER + r"<B>\Z")),
    # "Since the update on 25H2 build X": a BARE update noun directly on the build names it (a
    # qualified one, "the next update on X", is the platform veto above and never reaches here).
    ("named", "pre", _r1(r"\b(?:the|this|that|latest|last|recent|new)\s+(?:(?:windows|cumulative|security|quality|latest|"
                         r"recent|monthly)\s+){0,2}(?:update|upgrade|patch)\s+on\s+" + R1_FILLER + r"<B>\Z")),
    ("named", "post", _r1(r"<B>\W{0,4}(?:cumulative\s+|security\s+|preview\s+|quality\s+|feature\s+)?(?:update|upgrade|patch)\b"
                          r"(?!\s+(?:health|stack|assistant|service|orchestrator|agent|catalog|troubleshoot\w*|history|"
                          r"settings|medic|components?|client|page))")),
    ("named", "post", _r1(r"<B>\W{0,4}(?:was\s+|got\s+|has\s+been\s+|have\s+been\s+|just\s+|finally\s+|then\s+)?"
                          r"(?:installed|downloaded|arrived|landed|rolled\s+out)\b(?!\s+on\b)")),
    ("named", "post", _r1(r"<B>\W{0,4}which\s+(?:\w+\s+)?(?:arrived|came|was\s+installed|got\s+installed|installed|"
                          r"was\s+pushed|was\s+delivered|landed|was\s+applied|got\s+applied)\b")),
    ("destination", "pre", _r1(r"\b(?:to|onto|auf|naar|vers|zu)\b" + R1_FILLER + r"<B>\Z")),
    ("attached", "post", _r1(r"<B>\W{0,4}(?:ever\s+)?(?:since|after|with|following|via|through)\s+" + R1_UPDATE_NP)),
    ("attached", "post", _r1(r"<B>\W{0,4}(?:ever\s+)?(?:since|after)\s+(?:updating|upgrading|installing|the\s+install\w*)\b")),
    ("onset", "pre", _r1(r"\b(?:since|after|following)\s+(?:installing\s+|updating\s+to\s+|upgrading\s+to\s+|moving\s+to\s+|"
                         r"getting\s+|receiving\s+)?" + R1_FILLER + r"<B>\Z")),
    # A failure predicated on the build. When the build is the SUBJECT installing something else
    # ("X fails to install the Media Feature Pack", "X can't install the March update") it is the
    # platform, so an install predicate followed by an object does not link.
    ("direct", "post", _r1(r"<B>\W{0,4}(?:(?:has|is|keeps|seems\s+to|just|now|also|then|again|apparently|completely|"
                           r"totally|really)\s+){0,2}(?:caus\w*|crash\w*|break\w*|broke\w*|brick\w*|introduc\w*|"
                           r"fail\w*(?!\s+to\s+(?:install|update|apply|download)\w*" + R1_INSTALL_OBJECT + r")|"
                           r"(?:won['’]?t|can['’]?t|cannot)\s+install\b(?!" + R1_INSTALL_OBJECT + r")|"
                           r"broken|not\s+working|does\s*n[o'’]?t\s+work|won['’]?t\s+(?:boot|start|load|work|finish|complete)|"
                           r"can['’]?t\s+(?:boot|start)|cannot\s+(?:boot|start)|froze|freez\w*|hang\w*|"
                           r"roll\w*\s*back|reverted|stuck|bsod\w*|blue\s*screen\w*|killed|ruined|messed)\b")),
)
# A running statement, a spec label or the Settings "Installed on" field. Diagnostic label only:
# environment is not a veto (an attached link still counts) and not a link.
R1_ENVIRONMENT_RE = re.compile(
    r"(?i)\b(?:i|we)\s*(?:'m|’m|\s+am|\s+are)?\s*(?:currently\s+)?(?:on|running|using)\b"
    r"|\b(?:running|using)\s+(?:windows|win\s?1[01])\b|\bdevice\s+running\b|\binstalled\s+on\b"
    r"|\b(?:os|system|environment|platform|configuration|product|version|build|edition)\s*:"
)


def _r1_sentences(text: str) -> list[str]:
    """Sentences, with build tokens and short parentheticals kept whole (their dots do not split)."""
    masked = BUILD_TOKEN_RE.sub(lambda m: m.group(0).replace(".", "\x1f"), text or "")
    masked = R1_PAREN_RE.sub(lambda m: m.group(0).translate(R1_PAREN_MASK), masked)
    return [part.translate(R1_UNMASK) for part in R1_SENTENCE_SPLIT_RE.split(masked) if part.strip()]


def _r1_holds(kind: str, patterns: tuple, sentence: str, start: int, end: int) -> bool:
    if kind == "pre":
        return patterns[0].search(sentence[:end]) is not None
    if kind == "post":
        return patterns[0].match(sentence, start) is not None
    return patterns[0].search(sentence[:end]) is not None and patterns[1].match(sentence, start) is not None


def _r1_occurrence_role(sentence: str, start: int, end: int) -> tuple[str, str]:
    """(role, rule) for the build occurrence sentence[start:end]: a veto, else affected, else a label."""
    for role, kind, *patterns in R1_VETOES:
        if _r1_holds(kind, patterns, sentence, start, end):
            return role, f"{role}:{kind}"
    for link, kind, *patterns in R1_LINKS:
        if link == "destination" and not R1_CHANGE_WORD_RE.search(sentence[:start]):
            continue
        if _r1_holds(kind, patterns, sentence, start, end):
            return "affected", f"{link}:{kind}"
    spans = [m.span() for m in BUILD_TOKEN_RE.finditer(sentence)]
    left = max([e for _s, e in spans if e <= start], default=0)
    right = min([s for s, _e in spans if s >= end], default=len(sentence))
    window = sentence[left:right]
    if R1_ENVIRONMENT_RE.search(window) or SYSTEM_SPEC_RE.search(window):
        return "environment", ""
    return "unlinked", ""


def identity_link_details(report_text: str, report_title: str, build: str) -> list[tuple[str, str, str]]:
    """(role, rule, sentence) for every occurrence of `build` in the body."""
    # The title is the post's subject and names no build here. Only the LEADING copies are removed
    # (row_from_candidate prepends parent_title + report_title, and a Learn/Tech Community body starts
    # with its title again); a mid-body substring is kept.
    body = (report_text or "").lstrip()
    title = (report_title or "").strip()
    while title and body.startswith(title):
        body = body[len(title):].lstrip()
    out = []
    for sentence in _r1_sentences(body):
        for m in BUILD_TOKEN_RE.finditer(sentence):
            if m.group(0) == build:
                role, rule = _r1_occurrence_role(sentence, m.start(), m.end())
                out.append((role, rule, sentence))
    return out


def identity_link_roles(report_text: str, report_title: str, build: str,
                        target_kb: str = "") -> list[tuple[str, str]]:
    """(role, sentence) for every occurrence of `build` in the body. Diagnostics and tests read this."""
    return [(role, sentence) for role, _rule, sentence in identity_link_details(report_text, report_title, build)]


def identity_not_linked_to_issue(report_text: str, report_title: str, matched_kb: str,
                                 matched_os_build: str, target_kb: str = "") -> bool:
    """R1: a build-only identity, title silent on it, none of whose occurrences is linked as affected."""
    build = str(matched_os_build or "").strip()
    if not build or matched_kb:
        return False
    title = report_title or ""
    if _has_exact(title, build) or (target_kb and _has_exact(title, target_kb)):
        return False
    roles = identity_link_roles(report_text, title, build, target_kb)
    if not roles:
        return False
    return not any(role == "affected" for role, _w in roles)


def foreign_product_subject(report_title: str, matched_kb: str, matched_os_build: str) -> bool:
    """The post's SUBJECT is a separately-updated product, not this Windows cumulative update.

    Four ordered escapes, each derived from a measured live row (see FOREIGN_PRODUCT_SUBJECT_RE):
      1. the record's own KB or build in the title -- the post names this patch, whatever else it
         mentions ("OS Build 26200.8894 Office Errors");
      2. no foreign product in the title at all -- nothing to veto;
      3. a Windows update named in the title -- the update is the subject, the app is the symptom;
      4. a Windows component named in the title -- a Windows report listing an app among symptoms.
    """
    title = report_title or ""
    if (matched_os_build and matched_os_build in title) or (
            matched_kb and re.search(re.escape(matched_kb), title, re.I)):
        return False
    if not FOREIGN_PRODUCT_SUBJECT_RE.search(title):
        return False
    if WINDOWS_UPDATE_SUBJECT_RE.search(title):
        return False
    return not WINDOWS_COMPONENT_SUBJECT_RE.search(title)


def build_only_in_system_specs(report_text: str, report_title: str, matched_kb: str, matched_os_build: str) -> bool:
    """The identity token is present but only in a system-spec/diagnostics context (a spec
    footer or signature), not in the problem statement."""
    if build_as_affected_state(report_title, matched_kb, matched_os_build):
        return False
    return bool(SYSTEM_SPEC_RE.search(report_text))


def windows_intent_reason(report_text: str, report_title: str, matched_kb: str, matched_os_build: str) -> str | None:
    """Update-attribution / intent filter (runs only after identity + concrete-issue + date
    gates pass). Returns a rejection reason, or None to count. Rejects meta/spam, driver
    how-to/upgrade questions, feature/how-to clarification questions, posts where the build
    appears only in a spec signature, and anything not attributed to the exact update."""
    if META_SPAM_RE.search(report_text):
        return "meta_or_spam_report"
    # A driver-centric upgrade/how-to question is not a Windows-patch regression. Keyed on
    # the TITLE (the post's primary subject) so a genuine Windows regression that merely
    # mentions a driver/CPU in its body is not misclassified; still allow explicit temporal
    # attribution to the Windows update to rescue "after KB..., my driver broke" reports.
    if DRIVER_QUESTION_RE.search(report_title) and not TEMPORAL_REGRESSION_RE.search(report_text):
        return "driver_update_question_not_windows_patch"
    # A separately-updated product's own failure is not this cumulative update's defect. Placed
    # next to the driver rule because it is the same rule one category wider, and BEFORE the
    # attribution check because the whole point is that generic install/update vocabulary in the
    # body must not attribute another product's installer to this patch.
    if foreign_product_subject(report_title, matched_kb, matched_os_build):
        return "foreign_product_subject_not_windows_patch"
    # The build named as a not-yet-installed remedy is the fixed-in role, and a fix is not a defect.
    if identity_named_as_prospective_fix(report_text, matched_os_build):
        return "identity_named_as_prospective_fix"
    if FEATURE_QUESTION_RE.search(report_text) and not update_attributed(report_text, report_title, matched_kb, matched_os_build):
        return "feature_question_not_regression"
    attributed = update_attributed(report_text, report_title, matched_kb, matched_os_build)
    if HOWTO_QUESTION_RE.search(report_text) and not attributed:
        return "how_to_question_not_regression"
    if not attributed:
        if (matched_kb or matched_os_build) and build_only_in_system_specs(report_text, report_title, matched_kb, matched_os_build):
            return "build_only_in_system_specs"
        return "missing_update_attribution"
    # NOTE (deferred): preview-channel gating. The 25H2/24H2 records mark themselves as
    # "General Availability Channel" only in prose (no structured channel field), and the
    # observed false accepts were NOT preview-related, so preview_channel_mismatch is
    # intentionally NOT enforced here. Preview-Update reports of the exact current KB/build
    # still count. Revisit if/when a structured channel field exists (see test marker).
    return None


def identity_basis(matched_kb: str, matched_os_build: str, matched_feature: str) -> tuple[bool, str]:
    if matched_os_build:
        return True, "exact_os_build"
    if matched_kb and matched_feature:
        return True, "exact_kb_feature_train"
    return False, "no_exact_windows_identity"


# A stop error names itself. Windows update failures do not: their error codes are ordinary
# HRESULT/NTSTATUS values (0x800f0991, 0x80070306, 0x8024001e, 0xc000009c) and a bare hex token is
# therefore NOT evidence of a bugcheck. It used to be: `re.search(r"0x[0-9a-f]{6,8}")` sat in the
# BSOD branch, which runs FIRST, so every install-failure report was published as "BSOD / stop
# error" at severity `critical`. Measured on the live corpus: 32 rows carried that theme and only 5
# contained any stop-error vocabulary -- "WINDOWS UPDATE not functioning" and "cannot connect to
# shares" among the 27 that did not. Bugcheck NAMES are added so a report that gives the stop code
# in words rather than the acronym still classifies correctly.
BSOD_VOCABULARY = (
    "bsod", "blue screen", "blue-screen", "bugcheck", "bug check", "stop code", "stop error",
    "kernel_security_check", "memory_management", "irql_not_less_or_equal", "page_fault_in",
    "page fault in nonpaged area", "dpc_watchdog", "unexpected_kernel_mode_trap",
    "critical_process_died", "whea_uncorrectable", "system_service_exception",
    "driver_irql_not_less_or_equal", "video_tdr", "kmode_exception_not_handled",
)


def classify(text: str) -> tuple[str, str, str, str, str]:
    lowered = (text or "").lower()
    if any(t in lowered for t in BSOD_VOCABULARY):
        return "BSOD / stop error", "system stability", "windows", "critical", "negative"
    if any(t in lowered for t in ("won't boot", "wont boot", "fails to boot", "boot loop", "black screen", "no boot")):
        return "boot failure", "startup / boot", "windows", "critical", "negative"
    if any(t in lowered for t in ("install", "update fail", "upgrade fail", "rollback", "rolled back", "0x800", "fails to install", "won't install")):
        return "update/install failure", "windows update", "windows", "high", "negative"
    if "printer" in lowered or "printing" in lowered:
        return "printer regression", "printing", "windows", "high", "negative"
    if any(t in lowered for t in ("network", "wifi", "wi-fi", "internet", "ethernet", "vpn")):
        return "network regression", "networking", "windows", "high", "negative"
    if any(t in lowered for t in ("audio", "sound", "microphone")):
        return "audio regression", "audio", "windows", "medium", "negative"
    if any(t in lowered for t in ("display", "monitor", "graphics", "gpu", "resolution", "screen")):
        return "display regression", "display / graphics", "windows", "medium", "negative"
    if any(t in lowered for t in ("slow", "lag", "performance", "high cpu", "memory leak")):
        return "performance regression", "performance", "windows", "medium", "negative"
    if any(t in lowered for t in ("crash", "freeze", "hang")):
        return "crash or hang", "system stability", "windows", "high", "negative"
    return "unspecified Windows issue", "Windows workflow", "windows", "medium", "negative"


# --- identity is not the subject (AUX-067) -------------------------------------
#
# WHAT THIS CLOSES, MEASURED OFFLINE OVER THE 535 COUNTED WINDOWS ROWS. `row_from_candidate` stamps
# `matched_os_build` wherever the record's build token appears in the title + body, and a build alone
# is an accepted identity (`exact_os_build`). So a post whose TITLE is about a different update --
# "I can't install KB2267602", "KB5127936 breaks Xbox 360 Wireless Controller", "Excel 2608 (Build
# 16.0.20326.20100) crashes" -- counted against whichever record's build the author happened to quote
# in a system-spec line. Eight published rows were false acceptances of exactly this shape.
#
# THE RULE (all four, nothing broader): the identity is build-ONLY (no KB matched); the TITLE names
# neither the target build nor the target KB; the TITLE names a competing KB or build; and nothing in
# the title establishes the target build as AFFECTED. A KB match is never touched: a report that quotes
# the record's own KB has identified the patch it is about. The train alone is never a competing
# identity (a "24H2 and 25H2" title is one report about two trains), and neither is the body: the
# title is the post's subject, the body quotes baselines constantly. The broader variants that count a
# train in the title, or a baseline clause in the body, were measured and rejected.
#
# THE ONE EXCEPTION. "... update (build 26200.8875+)" says the defect begins at 26200.8875 and persists
# above it, so 26200.8894 IS affected. The exception is deliberately mechanical: a build of the SAME
# train with an explicit "+" / "and later" / "or later" marker written directly against it, at or
# below the target build. It is never "any older build mentioned counts for all later patches", and it
# is withheld when the title uses remedy vocabulary ("fixed in 26200.8875+" names a fix, not a defect).
AFFECTED_RANGE_RE = re.compile(r"\b(\d{5})\.(\d{3,5})\s*(?:\+|(?:and|or)\s+later\b)", re.I)
FIXED_IN_TITLE_RE = re.compile(r"(?i)\b(?:fix(?:ed|es)?|resolv\w*|address(?:ed|es)?|patch(?:ed)?|solved)\b")


def title_states_affected_range(report_title: str, target_build: str) -> bool:
    """The title explicitly says an open-ended range starting at or below the target build is affected."""
    parts = str(target_build or "").strip().split(".")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return False
    title = report_title or ""
    if FIXED_IN_TITLE_RE.search(title):
        return False
    train, revision = parts[0], int(parts[1])
    return any(m.group(1) == train and int(m.group(2)) <= revision
               for m in AFFECTED_RANGE_RE.finditer(title))


def identity_not_the_subject(target: dict[str, Any], report_title: str, matched_kb: str, matched_os_build: str) -> bool:
    """A build-only identity whose TITLE is about some other update; see the block above."""
    if not matched_os_build or matched_kb:
        return False
    title = report_title or ""
    target_build = str(target.get("target_os_build") or "").strip()
    target_kb = str(target.get("target_kb") or "").strip()
    if _has_exact(title, target_build) or _has_exact(title, target_kb):
        return False
    if not (_other_kbs(title, target_kb) or _other_builds(title, target_build)):
        return False
    return not title_states_affected_range(title, target_build)


def windows_learn_qna_reason(
    target: dict[str, Any],
    source_url: str,
    source_date: str,
    report_text: str,
    report_title: str,
    matched_kb: str,
    matched_os_build: str,
    matched_feature: str,
) -> str | None:
    """Ordered, deterministic acceptance. Returns an exclusion reason, or None to count."""
    if not source_url_is_specific(source_url):
        return "no_specific_source_url"
    if OFFICIAL_NOTE_RE.search(report_text) and not WINDOWS_ISSUE_RE.search(report_text):
        return "official_note_not_user_report"
    if ANNOUNCE_RE.search(report_text) and not describes_windows_issue(report_text):
        return "release_announcement_not_user_report"
    if not describes_windows_issue(report_text):
        return "generic_support_request"

    has_identity = bool(matched_os_build) or bool(matched_kb and matched_feature)
    if not has_identity:
        if TENANT_RE.search(report_text):
            return "tenant_service_incident_not_client_patch"
        if ACCOUNT_RE.search(report_text):
            return "account_backend_issue_not_patch"
        if matched_kb and not matched_feature and _other_features(report_text, target.get("target_feature_version", "")):
            return "wrong_feature_train_for_kb"
        if _other_kbs(report_text, target.get("target_kb", "")) or _other_builds(report_text, target.get("target_os_build", "")):
            return "wrong_kb_for_current_patch"
        if LATEST_RE.search(report_text):
            return "vague_latest_update"
        if PATCH_TUESDAY_RE.search(report_text) or MONTH_YEAR_RE.search(report_text):
            return "date_only_inference"
        return "missing_kb_or_build"

    # Exact identity present -> confirm against the record's CURRENT patch + date via the
    # shared fail-closed gate (PR #14). This also enforces stale-after-rollover and date.
    gate_row = {
        "matched_kb": matched_kb,
        "matched_os_build": matched_os_build,
        "matched_feature_version": matched_feature,
        "source_date": source_date,
    }
    ok, gate_reason = windows_identity_gate(gate_row, target)
    if not ok:
        if gate_reason == "source_date_before_target_release_date":
            return "date_before_release"
        return gate_reason  # missing_kb_or_build / wrong_feature_train_for_kb / stale_due_to_patch_rollover / windows_record_missing_target_identity
    # Intent / update-attribution hardening: the concrete issue must be attributed to the
    # exact update (not a question/config/meta post that merely cites the KB/build).
    reason = windows_intent_reason(report_text, report_title, matched_kb, matched_os_build)
    if reason is not None:
        return reason
    # LAST, so an existing, more specific rejection (spam, how-to, system-spec) keeps its reason and
    # only a row that would otherwise COUNT is affected. A build-only identity whose title is about
    # another update is a report about THAT update.
    if identity_not_the_subject(target, report_title, matched_kb, matched_os_build):
        return "identity_not_the_subject"
    # AUX-076: after every existing rule, AUX-067 included, so an existing reason is never relabelled
    # and only a row that would otherwise COUNT changes. A build-only identity whose title is silent
    # on it counts only when the body links the build itself to the issue.
    if identity_not_linked_to_issue(report_text, report_title, matched_kb, matched_os_build,
                                    str(target.get("target_kb") or "")):
        return "identity_not_linked_to_issue"
    return None


def row_from_candidate(record: PatchRecord, target: dict[str, Any], candidate: dict[str, Any], captured_at: str) -> dict[str, Any]:
    report_text = " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ]).strip()

    matched_kb = target.get("target_kb", "") if _has_exact(report_text, target.get("target_kb", "")) else ""
    matched_os_build = target.get("target_os_build", "") if _has_exact(report_text, target.get("target_os_build", "")) else ""
    matched_feature = target.get("target_feature_version", "") if _has_exact(report_text, target.get("target_feature_version", "")) else ""
    patch_matched, match_basis = identity_basis(matched_kb, matched_os_build, matched_feature)
    matched_version = matched_os_build or matched_kb or matched_feature or ""

    source_date = date_part(candidate.get("source_date"))
    target_release_date = date_part(target.get("target_release_date") or record.update_published_at)
    theme, workflow_area, platform, severity, sentiment = classify(report_text)

    row = make_evidence_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        source_type=str(candidate.get("source_type") or SOURCE_TYPE),
        source_name=str(candidate.get("source_name") or SOURCE_NAME),
        source_url=str(candidate.get("source_url") or ""),
        parent_title=str(candidate.get("parent_title") or ""),
        report_title=str(candidate.get("report_title") or ""),
        report_text=str(candidate.get("report_text") or ""),
        captured_at=captured_at,
        source_date=source_date,
        target_release_date=target_release_date,
        patch_version_matched=patch_matched,
        matched_version=matched_version,
        match_basis=match_basis,
        counted=False,
        exclusion_reason=None,
        matched_kb=matched_kb,
        matched_os_build=matched_os_build,
        matched_feature_version=matched_feature,
        issue_theme=theme,
        workflow_area=workflow_area,
        platform=platform,
        severity=severity,
        sentiment=sentiment,
        row_id=f"{PRODUCT_ID}-{slug(record.update_version)}-{slug(SOURCE_TYPE)}-{slug(str(candidate.get('source_url') or ''))}",
    )

    reason = windows_learn_qna_reason(target, str(candidate.get("source_url") or ""), source_date, report_text, str(candidate.get("report_title") or ""), matched_kb, matched_os_build, matched_feature)
    counted = reason is None
    row["counted"] = counted
    row["exclusion_reason"] = reason
    # Durable exact-build attribution, required since Windows became build-aware: the canonical
    # patch identity is (product_id, update_version, target_build), so a counted row that carries
    # no build belongs to no page. Set from the RECORD's build rather than from `matched_os_build`,
    # and only once the gate has passed, because the gate is what proves the row belongs to this
    # record -- and it accepts TWO exact bases, not one. `exact_kb_feature_train` (KB + train, no
    # build named) is as exact as `exact_os_build`: a KB identifies exactly one cumulative update
    # inside one servicing train, which is precisely why the gate demands both together. Taking
    # `matched_os_build` alone would leave every KB-only report unattributed -- four live rows,
    # measured -- and those reports name their patch just as unambiguously as the rest.
    row["target_build"] = str(target.get("target_os_build") or "").strip() if counted else ""
    row["evidence_valid_for_current_patch"] = counted
    row["stale_due_to_patch_rollover"] = reason == "stale_due_to_patch_rollover"
    return row


def claimed_urls() -> dict[str, tuple[str, str, str]]:
    """canonical URL -> the Windows patch that already holds it, from stored evidence.

    See ``evaluate_candidates``: this is the CROSS-RUN half of one-report-one-patch."""
    claims: dict[str, tuple[str, str, str]] = {}
    for row in load_evidence():
        if str(row.get("product_id") or "").strip() != PRODUCT_ID:
            continue
        if row.get("counted") is False:
            continue
        url = learn_qna.canonical_learn_qna_url(str(row.get("source_url") or ""))
        if url:
            claims.setdefault(url.lower(),
                              patch_key(PRODUCT_ID, row.get("update_version"), row.get("target_build")))
    return claims


def evaluate_candidates(record: PatchRecord, target: dict[str, Any], candidates: list[dict[str, Any]],
                        captured_at: str,
                        claims: dict[str, tuple[str, str, str]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate one record's candidates.

    ``claims`` maps a canonical URL to the patch that already holds it, and enforces
    ONE REPORT, ONE PATCH across every record in the run and across previous runs.

    THIS USED TO BE FREE. `append_evidence_rows` refuses a source_url already present under the
    same `evidence_key`, and that key's build slot was empty for Windows, so the append guard was
    build-blind and a URL could physically exist only once for the product. Stamping the exact
    build onto rows -- required for build-aware counting -- silently WIDENED that key, and one
    thread naming two builds became two counted rows on two different patches. Measured on the
    first production run after the change: 14 URLs counted twice, e.g. a single
    "ngcctnrsvc crashes" report counted for both 24H2 26100.9168 and 25H2 26200.9168 because both
    ship KB5121003.

    A person reporting one problem is one report. Which patch keeps it follows the walk order,
    which is newest-first, so the most recent update naming the report wins -- the same rule
    PowerPoint's `run_accepted_urls` exclusivity applies for the same reason."""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    mine = patch_key(PRODUCT_ID, record.update_version, record.target_build)
    for candidate in candidates:
        url = learn_qna.canonical_learn_qna_url(str(candidate.get("source_url") or ""))
        key = url.lower()
        if not url or key in seen:
            continue  # run-level duplicate URL dedup
        seen.add(key)
        row = row_from_candidate(record, target, {**candidate, "source_url": url}, captured_at)
        if row.get("counted") is True and claims is not None:
            holder = claims.get(key)
            if holder is not None and holder != mine:
                row["counted"] = False
                row["exclusion_reason"] = "cross_patch_duplicate"
                row["evidence_valid_for_current_patch"] = False
                # The row KEEPS the build it was refused for. Blanking it looked tidier -- only a
                # counted row is attributed for COUNTING -- but it conflates that with attribution
                # for DIAGNOSIS. A stored uncounted row with no build belongs to no patch, so it
                # groups under (product, version, ''), a key no record has: `audit_consensus_evidence`
                # then reports "structured evidence without matching generated record ... 0 rows",
                # which is how the first repair of these rows added 2 integrity errors. `counted:
                # false` is what keeps it out of every count; the build is what makes the audit
                # trail say WHICH patch refused this URL.
            else:
                claims[key] = mine
        (accepted if row.get("counted") is True else rejected).append(row)
    return accepted, rejected


# --- record target + queries -------------------------------------------------

def record_target(record: PatchRecord) -> dict[str, Any]:
    front, _body = load_front_matter_and_body(record.path)
    return {
        "target_feature_version": str(front.get("target_feature_version") or "").strip(),
        "target_kb": str(front.get("target_kb") or "").strip(),
        "target_os_build": str(front.get("target_os_build") or "").strip(),
        "target_release_date": str(front.get("target_release_date") or "").strip(),
        "update_version": str(front.get("update_version") or record.update_version).strip(),
    }


def search_query_terms(target: dict[str, Any]) -> list[str]:
    """Exact-identity search terms only: KB and OS build. The feature train (24H2) is
    context, never a standalone search — searching it alone would surface the whole train."""
    terms: list[str] = []
    if target.get("target_kb"):
        terms.append(target["target_kb"])
    if target.get("target_os_build"):
        terms.append(target["target_os_build"])
    return terms


# --- Tech Community discovery ------------------------------------------------

def techcommunity_slug(url: str) -> str:
    """The thread's title slug, which is its identity ACROSS spaces.

    Tech Community cross-posts: the same report appears under /windows11/ and
    /windowsinsiderprogram/ with different thread ids, and one user posted the identical thread
    three times into one space (ids 4526757/4526758/4526760). Both were measured. Keying dedup on
    the full URL counts one person's report two or three times; keying it on the slug is the same
    one-report-one-row rule `evaluate_candidates` already enforces for URLs.
    """
    path = urllib.parse.urlsplit(str(url or "")).path
    parts = [part for part in path.rstrip("/").split("/") if part]
    if len(parts) < 2:
        return ""
    return urllib.parse.unquote(parts[-2]).lower()


def collect_techcommunity_candidates(context: CollectorContext,
                                     errors: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Enumerate, dedupe and hydrate Windows threads. Returns (candidates, discovery telemetry).

    Run-scoped, NOT record-scoped: the sitemaps are the same for all 71 records, so walking them
    once per record would cost 71x the fetches to reach the identical thread set. The candidates
    are then offered to every record, and the unchanged authority decides which patch (if any) each
    belongs to.
    """
    # NO WINDOW MEANS THE DEFAULT WINDOW, never the whole archive. The runner always supplies one
    # (`--since`, or `--since-days`, which the workflow always passes), but a caller that omits it
    # would otherwise walk every Windows thread Tech Community has ever published -- thousands of
    # 400KB hydrations from a context that asked for nothing in particular. A sitemap walk has no
    # natural bound the way a keyword search does, so it needs an explicit one.
    since = str(getattr(context, "since", "") or "") or default_since_day(TECHCOMMUNITY_DEFAULT_WINDOW_DAYS)
    sitemap_errors: list[dict[str, Any]] = []
    listed = techcommunity.enumerate_sitemaps(
        TECHCOMMUNITY_SPACES, since=since, url_pattern=WINDOWS_IDENTITY_SLUG_RE,
        errors=sitemap_errors)
    errors.extend(sitemap_errors)
    by_slug: dict[str, dict[str, str]] = {}
    for row in listed:
        key = techcommunity_slug(row.get("source_url", ""))
        if key and key not in by_slug:
            by_slug[key] = row
    unique = list(by_slug.values())
    truncated = len(unique) > TECHCOMMUNITY_MAX_HYDRATIONS
    hydrate = unique[:TECHCOMMUNITY_MAX_HYDRATIONS]
    candidates: list[dict[str, Any]] = []
    attempted = 0
    hydration_errors = 0
    for row in hydrate:
        budget = rb.get_run_budget()
        if budget is not None and budget.collector_finalize_expired():
            truncated = True
            break
        url = row["source_url"]
        attempted += 1
        try:
            page = techcommunity.fetch(url)
        except Exception as exc:  # noqa: BLE001 - recorded for method health
            hydration_errors += 1
            errors.append({"source_url": url, "reason": techcommunity.error_reason(exc)})
            continue
        candidate = techcommunity.thread_candidate(
            url, date=row.get("date", ""), page_html=page,
            source_type=TECHCOMMUNITY_SOURCE_TYPE, source_name=TECHCOMMUNITY_SOURCE_NAME)
        if not candidate:
            continue
        # The date gate is `source_date >= target_release_date`, so it must run on the day the
        # report was WRITTEN. A sitemap <lastmod> moves with the newest reply, which would let a
        # thread written before the patch shipped pass as evidence about it. See lib/post_dates.
        candidate["source_date"] = candidate.get("original_post_date") or row.get("date", "")
        candidates.append(candidate)
        techcommunity._pace()  # noqa: SLF001 - the module's own politeness pacing
    telemetry = {
        "listed": len(listed),
        "unique_slugs": len(unique),
        "hydrated": len(candidates),
        "attempted": attempted,
        "sitemap_errors": len(sitemap_errors),
        "hydration_errors": hydration_errors,
        "truncated": truncated,
    }
    return candidates, telemetry


@dataclass(frozen=True)
class TechCommunityPool:
    """One run's Tech Community discovery, shared by every record."""

    candidates: list[dict[str, Any]]
    telemetry: dict[str, Any]
    errors: list[dict[str, Any]]


def build_techcommunity_pool(context: CollectorContext) -> TechCommunityPool:
    errors: list[dict[str, Any]] = []
    candidates, telemetry = collect_techcommunity_candidates(context, errors)
    return TechCommunityPool(candidates=candidates, telemetry=telemetry, errors=errors)


def techcommunity_method_status(pool: TechCommunityPool, accepted: list[dict[str, Any]],
                                rejected: list[dict[str, Any]]) -> str:
    """Canonical source-health vocabulary only, with the SAME meaning as the Learn Q&A method.

    A method that reached the source but found nothing for THIS patch is `no_results`, not
    `success`. The first wiring of this method returned `success` whenever the shared pool held
    any candidate at all -- which was every record, because the pool is run-scoped -- so all 71
    rows read healthy while 60 of them had found nothing. That is exactly the "do not mark a
    zero-value source healthy to satisfy the method floor" failure, arrived at by accident.
    """
    telemetry = pool.telemetry
    attempted = int(telemetry.get("attempted") or 0)
    hydration_errors = int(telemetry.get("hydration_errors") or 0)
    # An ISOLATED thread that would not hydrate is normal operation on a 130-page walk, and
    # reporting it as `partial` would mark all 71 patches MONITORING DEGRADED over one dead
    # thread. A whole SPACE that would not enumerate is real degradation, and so is a walk that
    # ran out of budget or hit the hydration ceiling.
    thin = attempted > 0 and hydration_errors * 5 >= attempted
    degraded = bool(telemetry.get("sitemap_errors")) or bool(telemetry.get("truncated")) or thin
    # EVERY hydration refused is a blocked source, not a degraded one. Measured in production run
    # 33995052762: the sitemaps returned 200 and listed 141 threads, and all 133 thread pages
    # returned HTTP 403 from the GitHub runner. `partial` would describe that as "some results",
    # which is the opposite of what happened -- nothing was read at all.
    if attempted > 0 and hydration_errors == attempted:
        return "blocked"
    if telemetry.get("sitemap_errors") and not pool.candidates:
        return "blocked"
    if accepted:
        return "partial" if degraded else "success"
    if degraded:
        return "partial"
    return "no_results"


def techcommunity_health(record: PatchRecord, captured_at: str, pool: TechCommunityPool,
                         accepted: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    telemetry = pool.telemetry
    notes = (
        "Microsoft Tech Community discussion sitemaps (techcommunity.microsoft.com) for "
        "microsoft-windows-11. Enumerated spaces: "
        f"{', '.join(TECHCOMMUNITY_SPACES)}. "
        f"Threads listed with a KB/OS-build slug {telemetry.get('listed', 0)}, unique after "
        f"cross-post slug dedupe {telemetry.get('unique_slugs', 0)}, hydrated "
        f"{telemetry.get('hydrated', 0)}. "
        f"For this record: accepted {len(accepted)}, rejected {len(rejected)}. "
        "The pool is enumerated once per run and offered to every record; the unchanged Windows "
        "authority decides which patch each thread belongs to. Discovery admits only threads whose "
        "URL slug already carries a KB or OS build, so a thread naming its patch only in the body "
        "is out of reach of this method."
    )
    if telemetry.get("truncated"):
        notes += f" Hydration truncated at {TECHCOMMUNITY_MAX_HYDRATIONS} or by the run budget."
    if pool.errors:
        notes += f" Fetch failures: {blocked_reason_from_errors(pool.errors)}."
    return method_health_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        target_build=record.target_build,
        method_id=TECHCOMMUNITY_METHOD_ID,
        source_type=TECHCOMMUNITY_SOURCE_TYPE,
        status=techcommunity_method_status(pool, accepted, rejected),
        candidates_found=len(pool.candidates),
        accepted_reports=len(accepted),
        rejected_reports=len(rejected),
        blocked_reason=blocked_reason_from_errors(pool.errors),
        last_run=captured_at,
        notes=notes,
    )


# --- Windows 11 Forum discovery (disabled by default) -------------------------

@dataclass(frozen=True)
class ElevenForumPool:
    """One run's Windows 11 Forum discovery, shared by every record. Same shape as the Tech
    Community pool, plus the threads that were hydrated but yielded no candidate."""

    candidates: list[dict[str, Any]]
    telemetry: dict[str, Any]
    errors: list[dict[str, Any]]
    unparseable: list[dict[str, str]]


def build_elevenforum_pool(context: CollectorContext,
                           session: "elevenforum.Session | None" = None) -> ElevenForumPool:
    """Enumerate and hydrate once per run. Only ever called behind ``elevenforum_discovery_enabled``.

    ``session`` is injectable so a test or dry run supplies a fixture transport; the default session
    is the real, paced, capped one."""
    since = str(getattr(context, "since", "") or "") or default_since_day(TECHCOMMUNITY_DEFAULT_WINDOW_DAYS)

    def _budget_expired() -> bool:
        budget = rb.get_run_budget()
        return bool(budget is not None and budget.collector_finalize_expired())

    discovery = elevenforum.discover(session or elevenforum.Session(), since=since,
                                     should_stop=_budget_expired)
    return ElevenForumPool(candidates=discovery.candidates, telemetry=discovery.telemetry,
                           errors=discovery.errors, unparseable=discovery.rejected_threads)


def elevenforum_method_status(pool: ElevenForumPool, accepted: list[dict[str, Any]],
                              rejected: list[dict[str, Any]]) -> str:
    """Canonical source-health vocabulary, with the same meaning as the other two methods.

    blocked     nothing could be read: a challenge or refusal, an unreachable site, or every
                hydration refused.
    partial     something was read but the walk was degraded (a listing page failed, the walk was
                stopped, or one hydration in five failed) -- including a walk stopped by a block
                after it had already read threads.
    no_results  the source was reached and read cleanly and yielded nothing for this patch.
    success     accepted reports and a clean walk.

    Hitting the 40-hydration cap is NOT degradation: the cap is the approved design, and reporting
    it as `partial` would mark every Windows patch MONITORING DEGRADED on every healthy run.
    """
    t = pool.telemetry
    attempted = int(t.get("attempted") or 0)
    hydration_errors = int(t.get("hydration_errors") or 0)
    listing_ok = int(t.get("listing_ok") or 0)
    listing_errors = int(t.get("listing_errors") or 0)
    if t.get("blocked") and not pool.candidates:
        return "blocked"
    if listing_ok == 0:
        return "blocked"
    if attempted > 0 and hydration_errors == attempted:
        return "blocked"
    thin = attempted > 0 and hydration_errors * 5 >= attempted
    degraded = bool(t.get("aborted")) or listing_errors > 0 or thin
    if accepted:
        return "partial" if degraded else "success"
    if degraded:
        return "partial"
    return "no_results"


def elevenforum_health(record: PatchRecord, captured_at: str, pool: ElevenForumPool,
                       accepted: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    t = pool.telemetry
    notes = (
        "Windows 11 Forum (elevenforum.com) listings "
        f"{', '.join(elevenforum.APPROVED_LISTINGS)}, up to {elevenforum.MAX_LISTING_PAGES} pages each. "
        f"Listing pages read {t.get('listing_ok', 0)}, threads listed {t.get('listed', 0)}, eligible by "
        f"title cue and window {t.get('eligible', 0)}, hydrated {t.get('hydrated', 0)} of "
        f"{t.get('attempted', 0)} attempted (cap {elevenforum.MAX_HYDRATIONS}), opening posts without a "
        f"valid date or text {t.get('unparseable', 0)}. "
        f"For this record: accepted {len(accepted)}, rejected {len(rejected)}. "
        "Opening posts only; the original post date is the thread's JSON-LD datePublished. The pool is "
        "enumerated once per run and the unchanged Windows authority decides which patch each thread "
        "belongs to. Discovery admits only threads whose listing title already carries a patch cue."
    )
    if t.get("capped"):
        notes += f" More eligible threads than the {elevenforum.MAX_HYDRATIONS}-hydration cap; the newest were read."
    if t.get("aborted"):
        notes += f" Walk stopped early: {t.get('abort_reason') or 'unknown'}."
    if pool.errors:
        notes += f" Fetch failures: {blocked_reason_from_errors(pool.errors)}."
    return method_health_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        target_build=record.target_build,
        method_id=ELEVENFORUM_METHOD_ID,
        source_type=ELEVENFORUM_SOURCE_TYPE,
        status=elevenforum_method_status(pool, accepted, rejected),
        candidates_found=len(pool.candidates),
        accepted_reports=len(accepted),
        rejected_reports=len(rejected),
        blocked_reason=blocked_reason_from_errors(pool.errors),
        last_run=captured_at,
        notes=notes,
    )


# --- method health -----------------------------------------------------------

def learn_qna_method_status(candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if accepted:
        return "partial" if errors else "success"
    if errors and (candidates or rejected):
        return "partial"
    if errors:
        if any(str(e.get("blocked_signature")) == "broken" or "feed_parse_failed" in str(e.get("reason") or "") for e in errors):
            return "broken"
        return "blocked"
    return "no_results"


def rejection_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("exclusion_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def format_rejection_counts(rows: list[dict[str, Any]]) -> str:
    return ", ".join(f"{reason}={count}" for reason, count in sorted(rejection_counts(rows).items()))


def blocked_reason_from_errors(errors: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for error in errors:
        reason = str(error.get("reason") or "fetch_failed")
        counts[reason] = counts.get(reason, 0) + 1
    return "; ".join(f"{reason} x{count}" if count > 1 else reason for reason, count in counts.items())


def build_notes(target: dict[str, Any], candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]], query_terms: list[str]) -> str:
    parts = [
        "Microsoft Learn Q&A search RSS (learn.microsoft.com/api/search/rss) for microsoft-windows-11.",
        f"Searched exact terms: {', '.join(query_terms) if query_terms else 'none (record missing target KB/build)'}.",
        f"Exact KB/OS-build search attempted: {bool(query_terms)}.",
        f"Candidates {len(candidates)}, accepted {len(accepted)}, rejected {len(rejected)}.",
    ]
    if rejected:
        parts.append(f"Top rejections: {format_rejection_counts(rejected)}.")
    if errors:
        parts.append(f"Fetch failures: {len(errors)}.")
    parts.append("Candidates require exact KB/OS-build identity for the record's current patch, a concrete issue, a specific question URL, and source date on/after release before counting.")
    return " ".join(parts)


def health_for_method(record: PatchRecord, target: dict[str, Any], captured_at: str, candidates: list[dict[str, Any]], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], errors: list[dict[str, Any]], query_terms: list[str]) -> dict[str, Any]:
    return method_health_row(
        product_id=PRODUCT_ID,
        update_version=record.update_version,
        # Method health is stored per EXACT patch, and Windows is build-aware, so the row must
        # state the build of the record it describes. Omitted, the row keys on
        # (product, "25H2", "") -- an identity no record has had since one record came to mean one
        # cumulative update -- and `collector_ownership.validate_method_health` fails the whole run
        # closed with `method_health_version_unresolved`. It did, in production run 33941301615.
        # A row that named no build would also project one build's telemetry onto its 22 siblings.
        target_build=record.target_build,
        method_id=METHOD_ID,
        source_type=SOURCE_TYPE,
        status=learn_qna_method_status(candidates, accepted, rejected, errors),
        candidates_found=len(candidates),
        accepted_reports=len(accepted),
        rejected_reports=len(rejected),
        blocked_reason=blocked_reason_from_errors(errors),
        last_run=captured_at,
        notes=build_notes(target, candidates, accepted, rejected, errors, query_terms),
    )


# --- collection --------------------------------------------------------------

def collect_for_record(record: PatchRecord, context: CollectorContext,
                       claims: dict[str, tuple[str, str, str]] | None = None,
                       techcommunity_pool: TechCommunityPool | None = None,
                       elevenforum_pool: ElevenForumPool | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    captured_at = utc_now()
    target = record_target(record)
    query_terms = search_query_terms(target)
    errors: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    if query_terms:
        candidates = learn_qna.collect_learn_qna_candidates(
            queries=query_terms,
            context=context,
            errors=errors,
            source_type=SOURCE_TYPE,
            source_name=SOURCE_NAME,
        )
    accepted, rejected = evaluate_candidates(record, target, candidates, captured_at, claims)
    health = [health_for_method(record, target, captured_at, candidates, accepted, rejected, errors, query_terms)]
    if techcommunity_pool is not None:
        # THE SAME AUTHORITY, DELIBERATELY. Discovery diversity must never become acceptance
        # divergence: the Tech Community pool goes through `evaluate_candidates`, i.e. the same
        # identity gate, concrete-issue gate, date gate, role rules, foreign-subject veto and
        # one-report-one-patch claims map as Learn Q&A. `claims` is the SAME dict, so a URL taken
        # by one method cannot be taken again by the other.
        tc_accepted, tc_rejected = evaluate_candidates(
            record, target, techcommunity_pool.candidates, captured_at, claims)
        accepted = accepted + tc_accepted
        rejected = rejected + tc_rejected
        health.append(techcommunity_health(record, captured_at, techcommunity_pool,
                                           tc_accepted, tc_rejected))
    if elevenforum_pool is not None:
        # Only reachable when the explicit flag built a pool. Same authority, same `claims` dict as
        # the two methods above, so a URL taken by one method cannot be taken again by another.
        ef_accepted, ef_rejected = evaluate_candidates(
            record, target, elevenforum_pool.candidates, captured_at, claims)
        accepted = accepted + ef_accepted
        rejected = rejected + ef_rejected
        health.append(elevenforum_health(record, captured_at, elevenforum_pool,
                                         ef_accepted, ef_rejected))
    return accepted, rejected, health


def _newest_first(records: list[PatchRecord]) -> list[PatchRecord]:
    """Most recently released cumulative update first.

    `generated_records` returns the corpus in FILENAME order, and every filename is date-prefixed,
    so the natural order is oldest-first. That was harmless while one record meant one servicing
    TRAIN (four records, all current). It is not harmless now: one record means one cumulative
    update, and there are 71 of them in the ingestion window. This collector stops mid-corpus when
    its wall-clock budget expires, so oldest-first would spend every run re-searching December 2025
    patches and never reach the update a reader is deciding about today. It is the same starvation
    the Acrobat collector measured (44 of 48 recent records never attempted), arriving here through
    the record expansion rather than through backfill.

    Ordering also decides ATTRIBUTION, not just spend. `append_evidence_rows` refuses a source_url
    that already exists in evidence, so when one thread names two KBs the record processed first
    keeps it. Newest-first means the current patch wins that tie rather than a superseded one.

    Deterministic: ties break on version then build, so two runs walk the identical order."""
    return sorted(records,
                  key=lambda r: (str(getattr(r, "update_published_at", "") or ""),
                                 str(getattr(r, "update_version", "") or ""),
                                 str(getattr(r, "target_build", "") or "")),
                  reverse=True)


class WindowsLearnQnaCollector(ProductCollector):
    product_id = PRODUCT_ID

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        records = _newest_first(generated_records(PRODUCT_ID, context.target_versions))
        results: list[dict[str, Any]] = []
        # (canonical patch key -> that record's result dict) for every record that accepted rows.
        # The consensus writeback is applied to all of them in ONE pass after the loop; see
        # _writeback_all for why it cannot stay inside it.
        pending: list[tuple[tuple[str, str, str], dict[str, Any]]] = []
        # ONE REPORT, ONE PATCH. Seeded from stored evidence so the rule holds across runs, then
        # extended in place as this run accepts. See evaluate_candidates for what broke without it.
        claims = claimed_urls()
        # ONE ENUMERATION PER RUN. See collect_techcommunity_candidates: the sitemaps do not vary
        # by record, so walking them inside the loop would cost 71x the fetches for the identical
        # thread set -- and it would spend that out of the collector's wall-clock budget, i.e. in
        # records never searched. Built before the loop so every record sees the same pool.
        techcommunity_pool = build_techcommunity_pool(context)
        rb.emit("windows_techcommunity_pool", product_id=PRODUCT_ID, **techcommunity_pool.telemetry)
        # DISABLED BY DEFAULT: no flag, no pool, no request, no health row, no code-path change.
        elevenforum_pool: ElevenForumPool | None = None
        if elevenforum_discovery_enabled():
            elevenforum_pool = build_elevenforum_pool(context)
            rb.emit("windows_elevenforum_pool", product_id=PRODUCT_ID, **elevenforum_pool.telemetry)
        for record in records:
            _b = rb.get_run_budget()
            if _b is not None and _b.collector_finalize_expired():
                rb.emit("collector_budget_stop", product_id=PRODUCT_ID, reason="collector_finalize")
                break
            if elevenforum_pool is None:
                accepted, rejected, health = collect_for_record(record, context, claims,
                                                                techcommunity_pool)
            else:
                accepted, rejected, health = collect_for_record(record, context, claims,
                                                                techcommunity_pool, elevenforum_pool)
            result: dict[str, Any] = {
                "product_id": PRODUCT_ID,
                "version": record.update_version,
                "mode": "write" if context.write else "dry-run",
                "record_path": str(record.path.relative_to(record.path.parents[2])),
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [row["source_url"] for row in accepted],
                "rejection_reasons": rejection_counts(rejected),
                "method_health": health,
            }
            if context.write:
                persisted: list[dict[str, Any]] = []
                already_held: list[dict[str, Any]] = []
                added, total, rows = append_evidence_rows(
                    accepted, out_added=persisted, out_already_held=already_held)
                # The health rows were built before the append and could not know the delta; this is
                # where it becomes knowable. Both methods' rows are in `health`, and attribution is
                # by source_type, so each family gets its own true count.
                finalize_method_health_delta(health, persisted, already_held)
                structured_count = len(counted_rows(rows, PRODUCT_ID, record.update_version))
                result.update({
                    "evidence_rows_added": added,
                    "evidence_rows_total": total,
                    "structured_count_for_version": structured_count,
                    # Filled after the loop -- see _writeback_all.
                    "windows_record_updated": False,
                })
                if accepted:
                    pending.append((patch_key(PRODUCT_ID, record.update_version,
                                              record.target_build), result))
            results.append(result)
        if context.write and pending:
            _writeback_all(pending)
        return results


def _writeback_all(pending: list[tuple[tuple[str, str, str], dict[str, Any]]]) -> None:
    """Apply the consensus writeback to EVERY record that accepted rows, in one pass.

    WHY THIS IS NOT IN THE LOOP. `apply_consensus_writeback` rebuilds the whole picture on every
    call: `_index_generated_records()` reads all 1110 generated records (4.2s measured) and
    `run_dry_run` regroups the entire evidence corpus (5.4s). That cost was paid at most four
    times a run while one Windows record meant one servicing train. There are now 71 records, so
    leaving it inside the loop spends 11 minutes per run re-deriving the same two structures --
    and it spends it out of the collector's wall-clock BUDGET, so the price is paid in records
    never searched. Both structures are identical for every record in the run, so they are built
    once here and each pending patch is resolved out of the same results.

    Deliberately AFTER all appends: the results are computed from the evidence file as it stands
    when the run has finished writing, so every record sees the final population rather than the
    one that happened to exist when its own turn came round.
    """
    from apply_consensus_to_records import (_index_generated_records,  # noqa: PLC0415
                                            apply_collector_record_fields, run_dry_run)

    results = run_dry_run(
        evidence_path=EVIDENCE_PATH,
        product_id_filter=PRODUCT_ID,
        is_candidate_mode=False,
        records_index=_index_generated_records(),
        write_requested=True,
    )
    # key -> LIST, not key -> item. Collapsing duplicates into a dict would silently pick the last
    # one; an identity that resolves to more than one group is ambiguous and must be refused, which
    # is the guarantee the previous `len(matches) != 1` check carried and the one `[I8c]` pins.
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in results:
        by_key.setdefault(
            patch_key(PRODUCT_ID, item.get("update_version"), item.get("target_build")),
            []).append(item)
    for key, result_row in pending:
        matches = by_key.get(key) or []
        if len(matches) != 1 or not matches[0].get("would_write"):
            continue
        item = matches[0]
        record_rel = item.get("matched_generated_record_path")
        if not record_rel:
            continue
        record_path = ROOT / record_rel
        fields = dict(item["proposed_fields_if_written"])
        data, _body = load_front_matter_and_body(record_path)
        comparable = {k: v for k, v in fields.items() if k != "status_events_append"}
        if all(data.get(k) == v for k, v in comparable.items()):
            continue
        applied = apply_collector_record_fields(record_path, fields) or {}
        result_row["windows_record_updated"] = bool(
            ((applied.get("write_plan") or {}).get("fields")))


def apply_consensus_writeback(update_version: str, target_build: str = "") -> bool:
    """Run the deterministic consensus writeback for ONE Windows patch. Returns whether the
    record's bytes actually changed.

    Selects by canonical patch identity, not by version. Matching on ``update_version`` alone was
    correct while one record meant one servicing train; 28 records now share "25H2", so a
    version-only filter matched 28 groups and returned False for every one of them.

    Delegates to ``_writeback_all`` so there is ONE writeback implementation: the collector's
    batched path and this single-patch entry point cannot drift into different notions of what a
    writeback does, and the behavioural suites that drive this function are therefore exercising
    the code production actually runs.
    """
    row: dict[str, Any] = {}
    _writeback_all([(patch_key(PRODUCT_ID, update_version, target_build), row)])
    return bool(row.get("windows_record_updated"))


def _dry_run_main(argv: list[str] | None = None) -> int:
    """Read-only local dry-run entry point. Hardcodes write=False, so this can NEVER write
    evidence or generated records — it only fetches Learn Q&A and prints diagnostics."""
    import argparse
    import json
    from datetime import datetime, timedelta, timezone

    parser = argparse.ArgumentParser(description="Windows Learn Q&A collector — read-only dry-run (no writeback).")
    parser.add_argument("--update-version", action="append", help="Exact Windows update_version filter (e.g. 24H2). Repeatable.")
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
    results = WindowsLearnQnaCollector().collect(context)
    print(json.dumps({"mode": "dry-run", "write": False, "products": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_dry_run_main())
