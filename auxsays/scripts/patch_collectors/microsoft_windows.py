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
import time
import urllib.parse
from collections import Counter
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
# rejects it because the title names another KB. A baseline whose title names no competing KB or build is
# NOT closed (AUX-067 residual R1), so activation still needs its own measurement.
ELEVENFORUM_METHOD_ID = "elevenforum_windows_listing"
ELEVENFORUM_SOURCE_TYPE = elevenforum.DEFAULT_SOURCE_TYPE
ELEVENFORUM_SOURCE_NAME = elevenforum.DEFAULT_SOURCE_NAME
ELEVENFORUM_ENABLE_ENV = "AUXSAYS_ENABLE_WINDOWS_ELEVENFORUM_DISCOVERY"


def elevenforum_discovery_enabled(env: dict[str, str] | None = None) -> bool:
    """Default-off gate. True ONLY for the exact canonical boolean ``true`` (case-insensitive,
    trimmed); absent, empty, ``false``, ``0``, ``1``, ``yes`` and ``on`` are all False."""
    source = os.environ if env is None else env
    return str(source.get(ELEVENFORUM_ENABLE_ENV, "")).strip().lower() == "true"


# --- underfilled-evidence enrichment: Learn Q&A opening-post hydration (SHIPPED DISABLED) -----------
#
# WHAT IT IS. The search-RSS lane judges a question by its RSS title and description. When that text
# names no KB or build ("missing_kb_or_build") or no attribution ("missing_update_attribution"), the
# full opening post sometimes does. For a patch that the shipped certifier refuses ONLY for being
# short of reports, inside a recency window, this pass fetches the question page of each such
# candidate THIS RUN discovered, rebuilds the candidate from the opening post (title + the asker's
# question only; never an answer or a comment), dates it from the page, and hands it back to the
# unchanged authority, `evaluate_candidates` -- the same claims map, the same identity, intent, date
# and identity-not-the-subject rules. Configuration lives in lib/method_routing.UNDERFILL_PLANS.
#
# WHAT IT IS NOT. A method. It owns no health row, adds no source_type and is not in the ownership
# manifest: an enrichment step that owned a row would revoke the very patch it helped (measured, L1
# spec §7). Its failures NEVER enter learn_qna_search_rss's error list -- that list, and therefore
# that method's status, stays decided by the search feed alone. A primary RSS failure still reads as
# a failure; an enrichment failure is disclosed in the row's notes, in a structured per-record
# `underfill_hydration` block, in `rb.emit` events and in a run warning, and never hidden.
#
# DISABLED MEANS DISABLED. With the flag below absent (or anything but the exact string "true") no
# pass runs, no page is requested, `collect_for_record` is called exactly as before, and the output is
# byte-identical. The workflow exports the flag only on a manual dispatch that is also a dry run.
UNDERFILL_ENABLE_ENV = "AUXSAYS_ENABLE_WINDOWS_UNDERFILL_HYDRATION"
HYDRATION_ADAPTER_ID = "learn_qna_question_hydration"
# The pass starts only with this much collector discovery time left, and stops requesting once less
# than UNDERFILL_WRITEBACK_RESERVE_S remains, so the existing writeback keeps its own finalize reserve
# untouched AND this margin on top of it. If the budget cannot support enrichment, it is skipped.
UNDERFILL_MIN_START_HEADROOM_S = 60.0
UNDERFILL_WRITEBACK_RESERVE_S = 30.0
# The pass's own wall clock, independent of AUXSAYS_METHOD_DEADLINE_SECONDS.
UNDERFILL_METHOD_SECONDS = 180.0
# Circuit breaker: a 429 opens it at once; so do this many consecutive transport failures.
HYDRATION_CIRCUIT_CONSECUTIVE_FAILURES = 5
# Disclosure only (same share as Tech Community's `thin`): at least one GET in five failed.
HYDRATION_WARNING_FAILURE_FRACTION = 0.2


def windows_underfill_hydration_enabled(env: dict[str, str] | None = None) -> bool:
    """Default-off gate. True ONLY for the exact canonical boolean ``true`` (case-insensitive,
    trimmed); absent, empty, ``false``, ``0``, ``1``, ``yes`` and ``on`` are all False."""
    source = os.environ if env is None else env
    return str(source.get(UNDERFILL_ENABLE_ENV, "")).strip().lower() == "true"


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


def claims_and_stored_urls() -> tuple[dict[str, tuple[str, str, str]], set[str]]:
    """``claimed_urls()`` plus the canonical URL of EVERY stored Windows row, from ONE store read.

    Used only by the default-off hydration pass. `claims` skips ``counted: false`` rows, so a report
    that was refused or audited-withdrawn is not in it -- and the append guard refuses a held URL
    only under the SAME (product, version, build) key. Without the second set, hydration could
    re-accept a withdrawn report onto a sibling patch, arguing an audited withdrawal again."""
    claims: dict[str, tuple[str, str, str]] = {}
    stored: set[str] = set()
    for row in load_evidence():
        if str(row.get("product_id") or "").strip() != PRODUCT_ID:
            continue
        url = learn_qna.canonical_learn_qna_url(str(row.get("source_url") or ""))
        if not url:
            continue
        stored.add(url.lower())
        if row.get("counted") is False:
            continue
        claims.setdefault(url.lower(),
                          patch_key(PRODUCT_ID, row.get("update_version"), row.get("target_build")))
    return claims, stored


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
                       elevenforum_pool: ElevenForumPool | None = None,
                       *, rss_out: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """One record's discovery and acceptance. Returns (accepted, rejected, health) over every method.

    ``rss_out`` is an OPTIONAL out-parameter (the ``append_evidence_rows(out_added=...)`` pattern):
    when given, it receives the Learn Q&A search lane's OWN lists -- before the Tech Community and
    Windows 11 Forum merges -- so the default-off opening-post hydration pass can rebuild that one
    method's health row from the same inputs. The return value is unchanged, and a caller that does
    not pass it runs exactly the code path it ran before the parameter existed."""
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
    if rss_out is not None:
        # The SAME objects, not copies: the hydration pass must rebuild the row from the identical
        # `errors` list, so a primary RSS failure keeps deciding this method's status.
        rss_out.update({"candidates": candidates, "accepted": accepted, "rejected": rejected,
                        "errors": errors, "query_terms": query_terms, "target": target,
                        "captured_at": captured_at})
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
        # DEFAULT OFF: with the hydration flag absent, `claimed_urls()` is called exactly as before
        # and nothing below this collector's original path runs. With it on, the same read also
        # yields every stored Windows URL in ANY state (see claims_and_stored_urls).
        underfill = windows_underfill_hydration_enabled()
        stored_urls: set[str] = set()
        if underfill:
            claims, stored_urls = claims_and_stored_urls()
        else:
            claims = claimed_urls()
        underfill_states: list[dict[str, Any]] = []
        loop_stopped_on_finalize = False
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
                loop_stopped_on_finalize = True
                break
            # Flag off: `extra` is empty, so the call is byte-for-byte the call this loop always made.
            rss_out: dict[str, Any] = {}
            extra: dict[str, Any] = {"rss_out": rss_out} if underfill else {}
            if elevenforum_pool is None:
                accepted, rejected, health = collect_for_record(record, context, claims,
                                                                techcommunity_pool, **extra)
            else:
                accepted, rejected, health = collect_for_record(record, context, claims,
                                                                techcommunity_pool, elevenforum_pool,
                                                                **extra)
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
            persisted: list[dict[str, Any]] = []
            already_held: list[dict[str, Any]] = []
            if underfill:
                underfill_states.append({
                    "record": record, "result": result, "health": health, "accepted": accepted,
                    "rejected": rejected, "rss_out": rss_out, "persisted": persisted,
                    "already_held": already_held})
            if context.write:
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
        if underfill:
            # AFTER the walk, BEFORE the writeback: it spends only time the walk left over, it cannot
            # starve a record of its walk, and it never displaces the existing writer (see
            # _underfill_pass for the skip conditions).
            _underfill_pass(underfill_states, context=context, claims=claims,
                            stored_urls=stored_urls, pending=pending,
                            loop_stopped_on_finalize=loop_stopped_on_finalize)
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


# --- underfilled-evidence enrichment: the pass (default off; see UNDERFILL_ENABLE_ENV) -------------

def _underfill_now() -> datetime:
    """The instant the trigger is judged at. A seam, so a test can pin it."""
    return datetime.now(timezone.utc)


def _release_age_days(published_at: str, now: datetime) -> float | None:
    text = str(published_at or "").strip()
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (now - when).total_seconds() / 86400.0


def _url_key(url: str) -> str:
    return learn_qna.canonical_learn_qna_url(str(url or "")).lower()


def _hydrate_question(url: str, budget: Any) -> dict[str, Any]:
    """ONE bounded GET of a question page. Never raises: every failure becomes a reason token.

    `RequestDeadlineExceeded` and `BudgetError` are not `OSError`s, so they are caught by name; an
    exception escaping here would roll back the whole Windows collector -- every record's rows."""
    from . import microsoft_qna_tags_source as qna_tags  # noqa: PLC0415 - default-off path only

    try:
        final_url, html = qna_tags.fetch_bounded(url, budget=budget)
    except qna_tags.QnaTagError as exc:
        return {"fetched": False, "reason": exc.reason, "status": exc.status}
    except rb.BudgetError as exc:
        return {"fetched": False, "reason": f"budget_{exc.reason}", "status": None}
    except Exception as exc:  # noqa: BLE001 - isolated per URL by design
        return {"fetched": False, "reason": f"error_{type(exc).__name__}", "status": None}
    return {"fetched": True, "final_url": final_url, "html": html}


def _hydrated_candidate(url: str, rss_candidate: dict[str, Any], final_url: str,
                        page_html: str) -> tuple[dict[str, Any] | None, str]:
    """A fetched question page -> (candidate, "") or (None, refusal reason).

    The candidate is the tag lane's shape: the RSS title as `parent_title`/`report_title` (so a
    title-only rule judges the SAME title it judged on the excerpt), and `report_text` = that title
    plus the asker's OWN question segment. Answers and comments are never read.

    The date is the opening post's own date from the page, with NO fallback. The RSS date is the
    thread's last activity (lib/post_dates); feeding it to the date gate would let a reply carry an
    old thread into a later patch. An undated page is refused, not re-judged.

    The parser does not enforce identity, so this does: a page whose final URL or JSON-LD question id
    is another question is refused, as is a page with no QAPage block, a mainEntity that is not a
    Question, or a machine-generated question segment."""
    from lib import source_segments as seg  # noqa: PLC0415 - default-off path only
    from lib.post_dates import original_post_date_from_html  # noqa: PLC0415

    wanted = seg.learn_qna_question_id(url)
    if not wanted or seg.learn_qna_question_id(final_url) != wanted:
        return None, "redirect"
    thread = seg.parse_learn_qna_thread(url, page_html)
    if thread.parse_status == seg.PARSE_UNEXPECTED_SHAPE:
        return None, "not_a_question"
    question = thread.question() if thread.ok else None
    if question is None:
        return None, "no_qapage"
    if str(question.segment_id or "").strip() != wanted:
        return None, "id_mismatch"
    if question.machine_generated:
        return None, "machine_generated"
    opening = str(question.segment_text or "").strip()
    if not opening:
        return None, "no_opening_post"
    posted = original_post_date_from_html(page_html)
    if not posted:
        return None, "undated"
    title = str(rss_candidate.get("report_title") or rss_candidate.get("parent_title") or "").strip()
    return {
        "source_type": SOURCE_TYPE,
        "source_name": SOURCE_NAME,
        "source_url": url,
        "parent_title": str(rss_candidate.get("parent_title") or title),
        "report_title": title,
        "report_text": " ".join(x for x in (title, opening) if x)[:6000],
        "source_date": posted,
        "original_post_date": posted,
        "qna_question_id": wanted,
    }, ""


def _post_date_source(page_html: str) -> str:
    """Diagnostic only: which rule of lib/post_dates dated the page."""
    return "jsonld_date_created" if re.search(r'"dateCreated"\s*:', page_html or "") else "earliest_datetime_attribute"


def _r1_flags(candidate: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """AUX-067 R1 diagnostics for a would-be row (dry run only; computed AFTER acceptance and never
    able to change it): the matched build's author-stated role, the competing identities the opening
    post names, and whether it states an open-ended affected range."""
    from lib.build_claims import extract_build_claims  # noqa: PLC0415 - default-off path only

    post = str(candidate.get("report_text") or "")
    build = str(target.get("target_os_build") or "").strip()
    revision = build.split(".")[-1] if "." in build else ""
    claim = next((c for c in extract_build_claims(post) if c.build == build), None)
    return {
        "matched_build_claim": ({"role": claim.role, "basis": claim.match_basis, "excerpt": claim.excerpt}
                                if claim else None),
        "competing_kbs": sorted(_other_kbs(post, str(target.get("target_kb") or ""))),
        # A same-revision build on a sibling train is the SAME cumulative update, not a competitor.
        "competing_builds": sorted(b for b in _other_builds(post, build) if b.split(".")[-1] != revision),
        "states_affected_range": title_states_affected_range(post, build),
    }


def _bracket(counts: Counter) -> str:
    return f" [{', '.join(f'{k}={v}' for k, v in sorted(counts.items()))}]" if counts else ""


def _hydration_notes_clause(c: dict[str, Any]) -> str:
    """The fixed-format disclosure appended to the learn_qna_search_rss row of a queued patch.
    It says what the pass is, what it did, and -- always -- that it is not a complete inspection."""
    clause = (
        "Opening-post hydration (optional enrichment of this method, separately budgeted; it never "
        "sets this method's status): "
        f"queued {c['queued']}, held {c['held']}, skipped {sum(c['skipped'].values())}{_bracket(c['skipped'])}, "
        f"fetched {c['fetched']}, cache hits {c['cache_hits']}, parsed {c['parsed']}, "
        f"undated {c['undated']}, refused-page {c['refused']}{_bracket(c['refused_reasons'])}, "
        f"accepted {c['accepted']}, still rejected {c['still_rejected']}{_bracket(c['still_rejected_reasons'])}, "
        f"failed {c['failed']}{_bracket(c['failure_reasons'])}, "
        f"not reached {c['not_reached']}{_bracket(c['not_reached_reasons'])}."
    )
    queued, parsed = c["queued"], c["parsed"]
    if queued == 0:
        clause += " Nothing was eligible to hydrate."
    elif parsed < queued:
        clause += (f" Hydration incomplete: {parsed} of {queued} queued opening posts were read and "
                   f"re-judged; the other {queued - parsed} keep their excerpt-time rejection.")
    else:
        clause += (f" All {queued} queued opening posts were read and re-judged; the queue holds only "
                   "this run's excerpt rejections of two kinds, so this is not a complete inspection.")
    return clause


_RUN_COUNTERS = ("queued", "held", "fetched", "cache_hits", "parsed", "undated", "refused", "accepted",
                 "still_rejected", "failed", "not_reached")


def _underfill_pass(states: list[dict[str, Any]], *, context: CollectorContext,
                    claims: dict[str, tuple[str, str, str]], stored_urls: set[str],
                    pending: list[tuple[tuple[str, str, str], dict[str, Any]]],
                    loop_stopped_on_finalize: bool) -> dict[str, Any]:
    """Opening-post hydration for underfilled patches. Default off; see UNDERFILL_ENABLE_ENV.

    SKIPPED (no request, nothing changed, the reason recorded) when the walk already stopped on the
    collector's finalize reserve, when less than UNDERFILL_MIN_START_HEADROOM_S of discovery time is
    left, or when the product declares no valid underfill plan. Then two phases:

      network, in memory -- the trigger through the shipped `live_eligibility.evaluate`, the queues,
        the bounded GETs, and the re-judgement through `evaluate_candidates`. Any exception here
        DISCARDS the whole pass (`hydration_aborted:<type>`) and changes nothing.
      write -- only what the existing loop already does: replace the RSS row (found by method_id),
        append through `append_evidence_rows`, re-finalize the health delta over the loop's AND the
        pass's persisted rows, and add a record that gained rows to the existing writeback.
    """
    started = time.monotonic()
    budget = rb.get_run_budget()
    summary: dict[str, Any] = {"outcome": "skipped", "reason": ""}
    skip = ""
    plan: dict[str, Any] | None = None
    if loop_stopped_on_finalize:
        skip = "collector_finalize_expired"
    elif budget is not None and budget.remaining_collector_finalize() < UNDERFILL_MIN_START_HEADROOM_S:
        skip = "insufficient_headroom"
    else:
        try:
            from lib import method_routing  # noqa: PLC0415 - default-off path only
            plan = method_routing.plan_underfill(PRODUCT_ID)
        except Exception as exc:  # noqa: BLE001 - a bad plan disables the pass, never the collector
            skip = f"invalid_plan:{type(exc).__name__}"
        else:
            if plan is None:
                skip = "no_plan"
    if not skip:
        try:
            prepared, summary = _underfill_network_phase(
                states, plan=plan or {}, claims=dict(claims), stored_urls=stored_urls, budget=budget,
                dry_run=not context.write)
        except Exception as exc:  # noqa: BLE001 - failure isolation: discard the pass, keep the run
            skip = f"hydration_aborted:{type(exc).__name__}"
            summary = {"outcome": "aborted", "reason": skip}
    if skip:
        summary.setdefault("outcome", "skipped")
        summary["reason"] = skip
        for state in states:
            state["result"]["underfill_hydration"] = {"decision": "not_evaluated",
                                                      "pass": summary["outcome"], "reason": skip}
    else:
        _underfill_write_phase(prepared, write=bool(context.write), pending=pending)
    summary["wall_s"] = round(time.monotonic() - started, 1)
    _emit_underfill_summary(summary)
    return summary


def _underfill_network_phase(states: list[dict[str, Any]], *, plan: dict[str, Any],
                             claims: dict[str, tuple[str, str, str]], stored_urls: set[str],
                             budget: Any, dry_run: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from lib import live_eligibility, maturity, method_routing, monitoring_health  # noqa: PLC0415
    from lib.report_counts import (counted_evidence_rows, load_evidence_store,  # noqa: PLC0415
                                   windows_targets_from_front_matter)
    from lib.source_segments import learn_qna_question_id  # noqa: PLC0415
    from .base import GENERATED_DIR, evidence_key  # noqa: PLC0415

    now = _underfill_now()
    thresholds = monitoring_health.load_thresholds(ROOT / "_config.yml")
    # The trigger's population: the WHOLE store (exclusivity is a property of every product's rows)
    # read by the strict loader -- a missing or malformed store aborts the pass rather than reading
    # as "nobody has any reports" -- plus this run's accepted rows that are not stored yet (a dry run).
    fronts: dict[str, dict[str, Any]] = {}
    for path in sorted(GENERATED_DIR.glob("*.md")):
        data, _body = load_front_matter_and_body(path)
        if isinstance(data, dict) and data.get("update_entry") is True \
                and str(data.get("product_id") or "").strip() == PRODUCT_ID:
            fronts[str(path)] = data
    stored_rows = load_evidence_store(EVIDENCE_PATH)
    held_keys = {evidence_key(r, "source_url") for r in stored_rows if r.get("source_url")}
    run_rows: list[dict[str, Any]] = []
    for state in states:
        for row in state["accepted"]:
            key = evidence_key(row, "source_url")
            if key not in held_keys:
                held_keys.add(key)
                run_rows.append(row)
    groups = counted_evidence_rows(stored_rows + run_rows,
                                   windows_targets=windows_targets_from_front_matter(fronts.values()))
    exclusive = live_eligibility.exclusive_url_counts(groups)
    live_min = maturity.LIVE_MIN_ACCEPTED_REPORTS

    decisions: Counter = Counter()
    entries: list[dict[str, Any]] = []
    candidate_for: dict[str, dict[str, Any]] = {}
    get_url: dict[str, str] = {}
    for state in states:
        record: PatchRecord = state["record"]
        mine = patch_key(PRODUCT_ID, record.update_version, record.target_build)
        state["key"] = mine
        decision = live_eligibility.evaluate(
            fronts.get(str(record.path)) or {}, groups, emh_rows=state["health"], now=now,
            thresholds=thresholds, exclusive=exclusive)
        age = _release_age_days(record.update_published_at, now)
        justified, why = method_routing.underfill_justified(
            decision.live, decision.reasons, release_age_days=age, window_days=plan["window_days"])
        decisions[why] += 1
        block: dict[str, Any] = {"decision": why, "window_days": plan["window_days"],
                                 "release_age_days": None if age is None else round(age, 1)}
        state["block"] = block
        state["queue"] = []
        if not justified:
            continue
        rss = state["rss_out"]
        shortfall = max(0, live_min - int(exclusive.get(mine, 0)), live_min - len(groups.get(mine, ())))
        by_key = {}
        for cand in rss.get("candidates") or []:
            k = _url_key(cand.get("source_url"))
            if k:
                by_key.setdefault(k, cand)
        held = 0
        skipped: Counter = Counter()
        seen: set[str] = set()
        for row in rss.get("rejected") or []:
            if str(row.get("exclusion_reason") or "") not in plan["enrichable_reasons"]:
                continue
            if str(row.get("source_type") or "") != SOURCE_TYPE:
                continue
            url = learn_qna.canonical_learn_qna_url(str(row.get("source_url") or ""))
            key = url.lower()
            if not url or key in seen:
                continue
            seen.add(key)
            if not learn_qna_question_id(url) or not source_url_is_specific(url):
                skipped["not_a_question_url"] += 1
                continue
            holder = claims.get(key)
            if holder == mine:
                held += 1
                continue
            if holder is not None:
                skipped["claimed_by_another_patch"] += 1
                continue
            if key in stored_urls:
                skipped["stored_in_any_state"] += 1
                continue
            state["queue"].append({"url": key, "date": str(row.get("source_date") or ""), "row": row})
            candidate_for.setdefault(key, by_key.get(key) or row)
            get_url.setdefault(key, url)
        block.update({"shortfall": shortfall, "queued": len(state["queue"]), "held": held,
                      "skipped": dict(skipped)})
        state["held"], state["skipped"] = held, skipped
        entries.append({"key": mine, "release_date": record.update_published_at,
                        "shortfall": shortfall,
                        "queue": [{"url": q["url"], "date": q["date"]} for q in state["queue"]]})

    order = method_routing.underfill_order(
        entries, max_fetches_per_run=plan["max_fetches_per_run"],
        max_fetches_per_identity=plan["max_fetches_per_identity"],
        recency_reserve=plan["recency_reserve"])

    # --- the bounded GETs ------------------------------------------------------------------------
    memo: dict[str, dict[str, Any]] = {}
    stop_reason = ""
    circuit = "closed"
    consecutive = 0
    method_started = time.monotonic()
    if budget is not None and order["fetch"]:
        budget.start_method(HYDRATION_ADAPTER_ID)
    for key in order["fetch"]:
        if circuit != "closed":
            stop_reason = "circuit"
            break
        if time.monotonic() - method_started >= UNDERFILL_METHOD_SECONDS:
            stop_reason = "deadline"
            break
        if budget is not None:
            if budget.remaining_collector_finalize() < UNDERFILL_WRITEBACK_RESERVE_S or budget.method_expired():
                stop_reason = "deadline"
                break
            try:
                budget.note_request()
            except rb.MethodBudgetExhausted as exc:
                stop_reason = "cap" if exc.reason == "max_requests" else "deadline"
                break
        outcome = _hydrate_question(get_url[key], budget)
        if not outcome["fetched"]:
            consecutive += 1
            memo[key] = {"kind": "failed", "reason": str(outcome["reason"])}
            rb.emit("windows_hydration_failure", url=get_url[key], product_id=PRODUCT_ID,
                    reason=str(outcome["reason"]))
            if outcome.get("status") == 429:
                circuit = "open:rate_limited"
            elif consecutive >= HYDRATION_CIRCUIT_CONSECUTIVE_FAILURES:
                circuit = "open:consecutive_failures"
            continue
        consecutive = 0
        try:
            candidate, refusal = _hydrated_candidate(get_url[key], candidate_for.get(key) or {},
                                                     outcome["final_url"], outcome["html"])
        except Exception as exc:  # noqa: BLE001 - a page that breaks the parser is refused, not fatal
            candidate, refusal = None, f"parse_error_{type(exc).__name__}"
        if candidate is None:
            memo[key] = {"kind": "undated" if refusal == "undated" else "refused", "reason": refusal}
        else:
            memo[key] = {"kind": "parsed", "candidate": candidate,
                         "date_source": _post_date_source(outcome["html"])}

    # --- re-judgement through the unchanged authority, in the newest-first WALK order -------------
    planned = set(order["fetch"])
    totals: Counter = Counter()
    prepared: list[dict[str, Any]] = []
    for state in states:
        item: dict[str, Any] = {"state": state, "block": state["block"]}
        prepared.append(item)
        if state["block"]["decision"] != "underfilled":
            continue
        record = state["record"]
        rss = state["rss_out"]
        mine = state["key"]
        c: dict[str, Any] = {"queued": len(state["queue"]), "held": state["held"], "skipped": state["skipped"],
                             "fetched": 0, "cache_hits": 0, "parsed": 0, "undated": 0, "refused": 0,
                             "accepted": 0, "still_rejected": 0, "failed": 0, "not_reached": 0,
                             "refused_reasons": Counter(), "still_rejected_reasons": Counter(),
                             "failure_reasons": Counter(), "not_reached_reasons": Counter()}
        candidates: list[dict[str, Any]] = []
        excerpt_reason: dict[str, str] = {}
        for q in state["queue"]:
            key = q["url"]
            excerpt_reason[key] = str(q["row"].get("exclusion_reason") or "")
            outcome = memo.get(key)
            if outcome is None:
                c["not_reached"] += 1
                c["not_reached_reasons"]["cap" if key not in planned else (stop_reason or "deadline")] += 1
                continue
            if order["charged"].get(key) == mine:
                c["fetched"] += 1
            else:
                c["cache_hits"] += 1
            kind = outcome["kind"]
            if kind == "failed":
                c["failed"] += 1
                c["failure_reasons"][outcome["reason"]] += 1
            elif kind == "undated":
                c["undated"] += 1
            elif kind == "refused":
                c["refused"] += 1
                c["refused_reasons"][outcome["reason"]] += 1
            else:
                c["parsed"] += 1
                candidates.append(outcome["candidate"])
        accepted, rejected = evaluate_candidates(record, rss["target"], candidates, rss["captured_at"], claims)
        c["accepted"] = len(accepted)
        c["still_rejected"] = len(rejected)
        for row in rejected:
            c["still_rejected_reasons"][str(row.get("exclusion_reason") or "unknown")] += 1
        moved = {_url_key(row.get("source_url")) for row in accepted}

        positions = [i for i, row in enumerate(state["health"]) if row.get("method_id") == METHOD_ID]
        if len(positions) != 1:
            raise RuntimeError(f"expected exactly one {METHOD_ID} row, found {len(positions)}")
        before = dict(state["health"][positions[0]])
        new_accepted = list(rss["accepted"]) + accepted
        new_rejected = [row for row in rss["rejected"] if _url_key(row.get("source_url")) not in moved]
        # THE SAME `errors` OBJECT: hydration failures are not in it and never will be, so the
        # status this row carries is still decided by the search feed alone.
        new_row = health_for_method(record, rss["target"], rss["captured_at"], rss["candidates"],
                                    new_accepted, new_rejected, rss["errors"], rss["query_terms"])
        new_row["notes"] = f"{new_row['notes']} {_hydration_notes_clause(c)}"

        block = state["block"]
        block.update({
            "closable": len(state["queue"]) >= block["shortfall"] > 0,
            "attempts": c["fetched"], "cache_hits": c["cache_hits"],
            "successes": c["parsed"] + c["undated"] + c["refused"],
            "failures": c["failed"], "failure_reasons": dict(c["failure_reasons"]),
            "parsed": c["parsed"], "undated": c["undated"], "refused": c["refused"],
            "refused_reasons": dict(c["refused_reasons"]),
            "accepted": c["accepted"], "accepted_urls": [row["source_url"] for row in accepted],
            "still_rejected": c["still_rejected"], "still_rejected_reasons": dict(c["still_rejected_reasons"]),
            "not_reached": c["not_reached"], "not_reached_reasons": dict(c["not_reached_reasons"]),
            "circuit_breaker": circuit,
            "rss_status_before": before.get("status"), "rss_status_after": new_row.get("status"),
        })
        if dry_run:
            block["rss_row_before"] = before
            block["rss_row_after"] = dict(new_row)
            would_be = []
            for row in accepted:
                key = _url_key(row.get("source_url"))
                cand = memo[key]["candidate"]
                rss_cand = candidate_for.get(key) or {}
                would_be.append({
                    "url": row["source_url"], "question_id": cand.get("qna_question_id"),
                    "update_version": row.get("update_version"), "target_build": row.get("target_build"),
                    "match_basis": row.get("match_basis"), "original_date": cand.get("source_date"),
                    "original_date_source": memo[key]["date_source"],
                    "rss_date": str(rss_cand.get("source_date") or ""),
                    "release_date": row.get("target_release_date"),
                    "excerpt_reason": excerpt_reason.get(key, ""),
                    "r1": _r1_flags(cand, rss["target"]),
                })
            block["would_be_rows"] = would_be
        for name in _RUN_COUNTERS:
            totals[name] += int(c[name])
        totals["skipped"] += sum(state["skipped"].values())
        item.update({"rss_index": positions[0], "new_row": new_row, "accepted_rows": accepted,
                     "moved": moved})

    attempts = len(memo)
    failures = sum(1 for m in memo.values() if m["kind"] == "failed")
    summary: dict[str, Any] = {
        "outcome": "ran", "reason": "",
        "window_days": plan["window_days"], "max_fetches_per_run": plan["max_fetches_per_run"],
        "max_fetches_per_identity": plan["max_fetches_per_identity"],
        "recency_reserve": plan["recency_reserve"],
        "identities_walked": len(states), "identities_queued": len(entries),
        "planned": len(order["fetch"]), "attempts": attempts, "successes": attempts - failures,
        "failures": failures, "stop_reason": stop_reason, "circuit_breaker": circuit,
        "method_wall_s": round(time.monotonic() - method_started, 1),
        **{f"decision_{name}": decisions.get(name, 0) for name in
           ("underfilled", "live", "certifier_unreachable", "not_count_limited", "outside_recency_window")},
        **{f"total_{name}": totals.get(name, 0) for name in (*_RUN_COUNTERS, "skipped")},
    }
    return prepared, summary


def _underfill_write_phase(prepared: list[dict[str, Any]], *, write: bool,
                           pending: list[tuple[tuple[str, str, str], dict[str, Any]]]) -> None:
    """Apply the in-memory pass through the collector's EXISTING writers only."""
    pending_keys = {key for key, _result in pending}
    for item in prepared:
        state = item["state"]
        result = state["result"]
        result["underfill_hydration"] = item["block"]
        if "new_row" not in item:
            continue
        record: PatchRecord = state["record"]
        health = state["health"]
        health[item["rss_index"]] = item["new_row"]
        accepted = item["accepted_rows"]
        moved = item["moved"]
        merged_rejected = [row for row in state["rejected"]
                           if not (str(row.get("source_type") or "") == SOURCE_TYPE
                                   and _url_key(row.get("source_url")) in moved)]
        result.update({
            "accepted_count": int(result.get("accepted_count") or 0) + len(accepted),
            "rejected_count": len(merged_rejected),
            "accepted_urls": list(result.get("accepted_urls") or []) + [row["source_url"] for row in accepted],
            "rejection_reasons": rejection_counts(merged_rejected),
        })
        if write:
            persisted: list[dict[str, Any]] = []
            already_held: list[dict[str, Any]] = []
            if accepted:
                added, total, rows = append_evidence_rows(
                    accepted, out_added=persisted, out_already_held=already_held)
                result.update({
                    "evidence_rows_added": int(result.get("evidence_rows_added") or 0) + added,
                    "evidence_rows_total": total,
                    "structured_count_for_version": len(counted_rows(rows, PRODUCT_ID, record.update_version)),
                })
                key = patch_key(PRODUCT_ID, record.update_version, record.target_build)
                if key not in pending_keys:
                    pending_keys.add(key)
                    pending.append((key, result))
            # Over the loop's AND the pass's persisted rows: the rebuilt row starts at zero stored.
            finalize_method_health_delta(health, list(state["persisted"]) + persisted,
                                         list(state["already_held"]) + already_held)
            item["block"]["evidence_rows_added"] = len(persisted)
        for row in accepted:
            rb.emit("windows_hydration_accept", url=str(row.get("source_url") or ""),
                    product_id=PRODUCT_ID, update_version=str(row.get("update_version") or ""),
                    target_build=str(row.get("target_build") or ""), stored=write)


def _emit_underfill_summary(summary: dict[str, Any]) -> None:
    """Run-level structured telemetry, plus a run warning when enrichment was degraded."""
    rb.emit("windows_underfill", product_id=PRODUCT_ID, **summary)
    attempts = int(summary.get("attempts") or 0)
    failures = int(summary.get("failures") or 0)
    circuit = str(summary.get("circuit_breaker") or "closed")
    if summary.get("outcome") == "aborted" or circuit != "closed" or (
            attempts and failures >= HYDRATION_WARNING_FAILURE_FRACTION * attempts):
        print("::warning title=Windows opening-post hydration::optional enrichment degraded "
              f"(outcome {summary.get('outcome')}, {failures} of {attempts} page fetches failed, "
              f"circuit {circuit}{', ' + str(summary.get('reason')) if summary.get('reason') else ''}); "
              "learn_qna_search_rss status is unaffected.", flush=True)


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
