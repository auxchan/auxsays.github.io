#!/usr/bin/env python3
"""Community evidence for ComfyUI, from ComfyUI's own public GitHub issues (Comfy-Org/ComfyUI).

THE QUESTION THIS ANSWERS. "Are people reporting a concrete problem after installing THIS exact
ComfyUI release?" Not "is anyone unhappy with ComfyUI or with something built on it". A report
counts only when its opening post establishes that the reporter ran the exact core release a
tracked record covers, describes a concrete problem, and was written on or after that release.

DISCOVERY IS ENUMERATION, NOT A VERSION QUERY. One paginated walk of the issues CREATED in the
run's window (GitHub search with a `created:` qualifier, newest first) feeds every tracked record,
and each record keeps only the issues whose text names its version exactly. Measured on the live
repository (G42): searching `"0.44.0"` and `"v0.44.0"` return DIFFERENT issue sets, because
GitHub's tokenizer treats the `v` prefix as part of the token, so a per-version query would need
two searches per record and would still be bounded by how the reporter spelled it. Enumeration is
bounded by WHERE we look (every issue opened in the window), costs a handful of requests per run
for all records together, and reads `created_at` -- the issue's own creation time, which a later
comment never moves (feed dates elsewhere are last activity; see lib/post_dates).

WHY COMFYUI NEEDS ITS OWN IDENTITY RESOLUTION. A version string in a ComfyUI issue is very often
NOT the ComfyUI core version. The same body routinely carries the frontend package version, the
workflow-templates and embedded-docs package versions, the versions of every installed Python
package (`llvmlite 0.44.0`, `yapf==0.43.0`, `wheel-0.45.0`) and of custom-node packs
(`comfyui-mixlab-nodes-0.46.0`). Exact containment would attribute all of those to the ComfyUI
release that happens to share the number. So identity is established only from what names the
CORE: the startup log line and the error-report system information block that ComfyUI itself
prints, or the reporter's own words naming ComfyUI immediately before the version. And a build
that is not the release is refused: ComfyUI-Manager prints `git describe` output (`v0.44.0-27-g...`
is 27 commits past the tag) and reporters say "master" or "+ N commits". A git checkout between
releases still prints the previous release number on its startup line, so this is the only way
those builds are told apart from the release.

THE ACCEPTANCE AUTHORITY IS THE SHARED ONE. Identity is this adapter's job; everything after it is
not. A row that passes identity is built by base.make_evidence_row and judged by
base.apply_acceptance_gates (exact version, specific URL, source date on or after the release,
concrete problem) and by lib.target_outcome (a version the report names as working, the fix or the
rollback target is not a report against it). No threshold, cue list or acceptance rule of this
product's own exists, and no promotion happens here: counts and projections belong to
reconciliation and the scoped promotion step in the collection workflow.

Exclusions are stored rows (counted: false + exclusion_reason), so every refusal is auditable from
the evidence store, not only from a run log.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

from lib import evidence_classification as ec
from lib import github_api
from lib.target_outcome import AFFECTED, classify_target_outcome, target_is_contradicted
from patch_collectors import base
from patch_collectors import github_officedev_source as github
from patch_collectors import runtime_budget as rb

# Module-level so the governed write-authority suite can repoint it at a temp tree and drive this
# collector's REAL writeback (test_collector_write_authority O8b).
ROOT = base.ROOT

PRODUCT_ID = "comfyui"
REPO = "Comfy-Org/ComfyUI"
# Shared method id and source type: this is the same mechanic and the same source family OBS uses
# (GitHub Issues of the project's own repository), so it is catalogued once, not per product.
METHOD_ID = "github_issues"
SOURCE_TYPE = "github_issue"
SOURCE_NAME = "Comfy-Org/ComfyUI"
ISSUE_URL_PREFIX = f"https://github.com/{REPO}/issues/"

# Page size is a payload bound, not a recall bound. Measured: issues here paste full startup logs,
# 100 issues per page weighed about 1.0 MB, and the shared transport reads at most 2 MB, so a
# log-heavy page could be truncated into a parse failure. 50 per page measured at most 0.67 MB.
PER_PAGE = 50
# GitHub search returns at most 1000 results for one query; past that the walk is truncated.
SEARCH_RESULT_CAP = 1000
DEFAULT_WINDOW_DAYS = 45
BUDGET_STOP_REASON = "run_budget_stop"

# --- identity -------------------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# What ComfyUI itself prints about its CORE version:
#   startup log          "[INFO] ComfyUI version: 0.44.0"
#   error report         "- **ComfyUI Version:** 0.44.0"
#   ComfyUI-Manager      "### ComfyUI Version: v0.44.0-27-g1332fab | Released on '...'"
# The optional describe suffix is `git describe`: N commits past the tag.
#
# A DECLARATION IS A LINE, NOT A PHRASE. The pattern alone also matches the reporter's prose
# ("Downgrading to ComfyUI version 0.43.0 avoids it"), and a declaration is what the shared role
# reading (lib.target_outcome R1) treats as the reporter's own build: immune to every veto, and it
# turns any other version beside the product name into "declared_core_version_differs". So a match
# is a declaration only when it is the whole of its line: before it, only what a log or a report
# template puts there (a timestamp, bracketed segments such as [INFO], a log level, a container's
# "name  | " prefix, list and markdown markers); after it, only markup, ComfyUI-Manager's
# "| Released on" segment, a parenthetical, a ", commit <sha>" note or a series marker (".x", "+").
# Measured on the 368-issue corpus (G42 review): every match the unanchored pattern found was
# already such a line, so this removes no real declaration. Prose naming "ComfyUI version X" still
# names the core (core_version_text); it just carries no immunity.
CORE_DECLARATION_RE = re.compile(
    r"\bcomfyui\s+version\b[\s:=*_`]*v?(?P<version>\d+(?:\.\d+){1,3})(?![0-9])(?!\.[0-9])"
    r"(?P<describe>-(?P<ahead>\d+)(?:-g[0-9a-f]{4,40})?(?![0-9A-Za-z]))?",
    re.I)
# Removed from the text before a declaration, before checking that no word is left. Alternatives do
# not overlap and nothing is nested, so a long line of brackets cannot backtrack.
_DECLARATION_PREFIX_SEGMENT_RE = re.compile(
    r"\[\d{1,3}(?:;\d{1,3})*m"                  # a colour code whose escape byte was lost: [32m
    r"|\[[^\]\n]*\]"                              # [INFO], [2026-11-05 10:00:00.123]
    r"|\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"          # 2026-10-30T21:52:08.393092
    r"|\b(?i:info|debug|warning|warn|error)\b"    # a log level
    r"|\A[\w.-]+[ \t]+\|")                        # docker compose: "comfyui  | "
_DECLARATION_TAIL_RE = re.compile(
    r"\A[\s*_`.+]*(?:\Z|\|\s*released\s+on\b|\([^()\n]*\)[\s*_`.]*\Z|,\s*commit\b|x\b)", re.I)
_LETTER_RE = re.compile(r"[A-Za-z]")

# The reporter's own words naming the core right before the version: "ComfyUI v0.45.0",
# "ComfyUI 0.43.0, portable", "**ComfyUI:** v0.42.0", "| ComfyUI | v0.38.0", "ComfyUI portable
# 0.39.0". Only markup, separators and these few words may stand between the name and the number;
# any other word ("comfyui-frontend-package", "ComfyUI Desktop", "comfyui-mixlab-nodes-") makes the
# number something else's.
_PRODUCT_NAME_RE = re.compile(r"comfyui", re.I)
_PRODUCT_GAP_RE = re.compile(
    r"\A(?:[\s*_`|:=(\[\]-]|\b(?:version|ver|portable|core|release|stable)\b)*v?\Z", re.I)
_PRODUCT_LOOKBACK = 40

# A build that is not the release: a describe suffix or an explicit commit offset after the number
# ("0.41.0-6-ge087d8f6", "v0.39.0-29", "0.41.0 + 6 commits").
_UNTAGGED_SUFFIX_RE = re.compile(r"\A(?:-\d+(?:-g[0-9a-f]{4,40})?(?![0-9A-Za-z.])|\s*\+\s*\d+\s+commits?\b)", re.I)
# ...or a development line named AS the build the number belongs to: "master @ c5751c81 (v0.45.0)",
# "On master `e0a32bce` (v0.40.0)", "ComfyUI v0.41.0, master `5cc4b87`", "0.43.0 (master fd7639f47)".
# Only when nothing but a build descriptor (punctuation, a commit hash, "at"/"@", "commit") separates
# the marker from the number. Measured: reporters who RAN the release routinely add "the code is
# unchanged on master `b2f6707`" or "the same lines are on master"; a marker separated from the
# number by words like those is a code reference, not their build.
_DEVELOPMENT_MARKER_RE = re.compile(r"\b(?:master|nightly)\b", re.I)
_BUILD_DESCRIPTOR_RE = re.compile(
    r"\A(?:[\s`'\"(),:=@\[\]*-]|\b(?:at|on|commit|comfyui|comfyui_version\.py)\b|\b[0-9a-f]{7,40}\b)*\Z", re.I)
_DESCRIPTOR_WINDOW = 72

# Maintainer triage labels that say what kind of issue this is. Labels are applied by people, and the
# repository's own issue form routes custom-node problems away from core ("If the bug only happens
# when certain custom nodes are used, most likely that custom node is what has the bug").
CUSTOM_NODE_LABELS = frozenset({"custom nodes bug"})
FEATURE_LABELS = frozenset({"feature"})

# ComfyUI's own startup warning that the installed companion packages are older than the release
# requires: "Installed comfyui-frontend-package version 1.39.19 is lower than the recommended
# version 1.57.6." The core number on such an install is the release's; the rest of it is not, so
# the install is not the release as shipped.
_PACKAGES_BEHIND_RE = re.compile(
    r"\binstalled\s+comfyui[-\w]*\s+version\s+\S+\s+is\s+lower\s+than\s+the\s+recommended\s+version\b", re.I)


def clean_text(text: str) -> str:
    """Terminal colour codes removed and line endings normalised. Logs are pasted from consoles."""
    return _ANSI_RE.sub("", str(text or "")).replace("\r\n", "\n").replace("\r", "\n")


def _line_of(text: str, start: int, end: int) -> str:
    lo = text.rfind("\n", 0, start) + 1
    hi = text.find("\n", end)
    return text[lo: hi if hi >= 0 else len(text)]


def _is_declaration_line(text: str, hit: re.Match) -> bool:
    """Is this match the whole of its line, as ComfyUI or a report template prints it (see above)?"""
    lo = text.rfind("\n", 0, hit.start()) + 1
    hi = text.find("\n", hit.end())
    prefix = _DECLARATION_PREFIX_SEGMENT_RE.sub(" ", text[lo:hit.start()])
    tail = text[hit.end(): hi if hi >= 0 else len(text)]
    return not _LETTER_RE.search(prefix) and bool(_DECLARATION_TAIL_RE.match(tail))


def declared_core_versions(text: str) -> dict[str, list[int]]:
    """Every core version ComfyUI's own output in the post declares, with each declaration's offset
    past the tag (0 when the declaration is the tag itself). Prose is never a declaration."""
    found: dict[str, list[int]] = {}
    body = clean_text(text)
    for hit in CORE_DECLARATION_RE.finditer(body):
        if not _is_declaration_line(body, hit):
            continue
        ahead = int(hit.group("ahead") or 0)
        found.setdefault(hit.group("version"), []).append(ahead)
    return found


def _occurrences(text: str, version: str) -> list[tuple[int, int]]:
    """Every position the shared matcher accepts as this exact version (not only the first)."""
    out: list[tuple[int, int]] = []
    offset = 0
    while offset <= len(text):
        matched, _v, _basis, start, end = base.exact_version_match_span(text[offset:], version)
        if not matched:
            break
        out.append((offset + start, offset + end))
        offset += end
    return out


def _development_build(text: str, start: int, end: int) -> bool:
    """Is this occurrence of the number named as a development-line build (see the rule above)?"""
    line = _line_of(text, start, end)
    line_start = text.rfind("\n", 0, start) + 1
    s, e = start - line_start, end - line_start
    for marker in _DEVELOPMENT_MARKER_RE.finditer(line):
        if marker.end() <= s and s - marker.end() <= _DESCRIPTOR_WINDOW:
            gap = line[marker.end():s]
        elif marker.start() >= e and marker.start() - e <= _DESCRIPTOR_WINDOW:
            gap = line[e:marker.start()]
        else:
            continue
        gap = re.sub(r"v\Z", "", gap)
        if _BUILD_DESCRIPTOR_RE.match(gap):
            return True
    return False


def _names_core(text: str, start: int) -> bool:
    lo = max(0, start - _PRODUCT_LOOKBACK)
    window = text[lo:start]
    hits = list(_PRODUCT_NAME_RE.finditer(window))
    if not hits:
        return False
    gap = window[hits[-1].end():]
    return bool(_PRODUCT_GAP_RE.match(gap))


def resolve_identity(text: str, version: str) -> dict[str, Any]:
    """Is this post about the exact ComfyUI core release `version`?

    Returns {"established": bool, "reason": str, "basis": str, "declared": set[str]}. `reason` is
    the auditable exclusion when not established. The order is fixed: not named at all, named only
    as a build past the release, named only as some other component's version, then the reporter's
    own declaration naming a different core version.
    """
    body = clean_text(text)
    declared = declared_core_versions(body)
    spans = _occurrences(body, version)
    result = {"established": False, "reason": "", "basis": "", "declared": set(declared)}
    if not spans:
        result["reason"] = "missing_exact_patch_version_match"
        return result
    # A describe suffix is checked at every occurrence below, which includes the one inside a
    # ComfyUI-Manager line ("v0.44.0-27-g1332fab"): one rule for prose and declarations alike.
    core_named = False
    for start, end in spans:
        if _UNTAGGED_SUFFIX_RE.match(body[end:end + 60]) or _development_build(body, start, end):
            result["reason"] = "core_version_untagged_build"
            return result
        if _names_core(body, start):
            core_named = True
    in_declaration = version in declared
    if not (core_named or in_declaration):
        result["reason"] = "version_not_core_identity"
        return result
    if declared and not in_declaration:
        result["reason"] = "declared_core_version_differs"
        return result
    if _PACKAGES_BEHIND_RE.search(body):
        result["reason"] = "release_packages_not_as_shipped"
        return result
    result["established"] = True
    result["basis"] = "core_version_declaration" if in_declaration else "core_version_text"
    return result


# A Python traceback frame inside a custom-node pack: `File ".../custom_nodes/<pack>/...", line N`.
# The failure the post shows ran through third-party code, so it is not established as a defect of
# the core release, whatever the post's version line says.
_CUSTOM_NODE_FRAME_RE = re.compile(r"\bFile \"[^\"\n]*[\\/]custom_nodes[\\/][^\"\n]*\", line \d+")
# The same failure in the browser: a JavaScript source position inside a custom-node pack's web
# code. ComfyUI's server serves each custom node's web directory at `/extensions/<pack>/`
# (server.py, nodes.EXTENSION_WEB_DIRS); only `/extensions/core/` is the core's own. A stack frame
# names a line (`.../extensions/comfyui-videohelpersuite/js/VHS.core.js:614:65`, in Chrome's
# `at fn (...)` and Firefox's `fn@...` alike); ComfyUI's deprecation warning naming
# `/extensions/core/groupNode.js.` names no line and is the core's path anyway. Measured (G42
# review): issue #17021's error report ran through VideoHelperSuite's frontend this way.
_CUSTOM_NODE_WEB_FRAME_RE = re.compile(
    r"/extensions/(?!core/)[^/\s()\"'<>]+/[^\s()\"'<>?#:]*\.m?js(?:\?[^\s()\"'<>:]*)?:\d+")


def issue_kind_exclusion(labels: list[str], text: str = "") -> str:
    """Why this is not a problem report about the core release itself, or ''.

    A maintainer's triage label (custom node, feature request), or a failure whose traceback runs
    through a custom-node pack -- Python frames or the pack's browser code -- the ecosystem, not the
    release.
    """
    names = {str(label or "").strip().lower() for label in labels}
    if names & CUSTOM_NODE_LABELS:
        return "custom_node_issue"
    if names & FEATURE_LABELS:
        return "feature_request_not_a_problem_report"
    body = clean_text(text)
    if _CUSTOM_NODE_FRAME_RE.search(body) or _CUSTOM_NODE_WEB_FRAME_RE.search(body):
        return "custom_node_in_failure_path"
    return ""


# --- classification (deterministic; presentation only, never acceptance) --------------------------
# Read from the reporter's PROSE: fenced blocks (pasted logs and tracebacks) are removed first, so a
# log line cannot pick the theme. Sentiment is not produced here (see evaluate_issue).
_FENCED_RE = re.compile(r"```.*?(?:```|\Z)", re.S)

_COMFYUI_THEME_RULES: tuple[ec.ThemeRule, ...] = (
    ec.ThemeRule("crash or freeze", "application stability", "high", "crash",
                 re.compile(r"\b(?:crash\w*|segfault\w*|core\s?dump\w*|freez\w*|frozen|hang(?:s|ing)?|hung|"
                            r"access\s+violation|stalls?|stalled)\b", re.I),
                 negatable=True),
    ec.ThemeRule("out of memory", "GPU and system memory", "high", "oom",
                 re.compile(r"\b(?:out\s+of\s+memory|oom|memory\s+leak\w*|vram\s+(?:leak\w*|usage|grows?|spikes?)|"
                            r"ram\s+(?:leak\w*|usage|grows?))\b", re.I)),
    ec.ThemeRule("wrong or corrupted output", "generation output", "high", "output",
                 re.compile(r"\b(?:black\s+(?:image|images|output|frames?)|pure\s+noise|(?:gray|grey|purple)\s+"
                            r"(?:image|images|output|noise)|corrupt\w*|garbled|artifacts?|nans?)\b", re.I)),
    ec.ThemeRule("performance regression", "performance", "medium", "performance",
                 re.compile(r"\b(?:slow\w*|slower|lag(?:s|gy|ging|ged)?|\d+x\s+slower)\b", re.I)),
    ec.ThemeRule("startup or install failure", "installation and startup", "medium", "startup",
                 re.compile(r"\b(?:(?:won't|cannot|can't|fails?\s+to|unable\s+to)\s+(?:start|launch|install|"
                            r"load\s+the\s+ui)|import\s?error|dll\s+load\s+failed|startup\s+(?:error|failure))\b",
                            re.I)),
    ec.ThemeRule("workflow load or save problem", "workflows", "medium", "workflow",
                 re.compile(r"\b(?:(?:cannot|can't|fails?\s+to|unable\s+to|won't)\s+(?:load|save|open|import)\s+"
                            r"(?:the\s+|a\s+|my\s+)?(?:workflow|metadata)|workflow\s+(?:metadata\s+)?(?:lost|broken|"
                            r"missing))\b", re.I)),
)
ec.validate_rules(_COMFYUI_THEME_RULES)


def classify(title: str, body: str) -> tuple[str, str, str, str]:
    """(theme, workflow_area, platform, severity). No supported theme -> ("", "", platform, "")."""
    prose = _FENCED_RE.sub(" ", clean_text(body))
    platform = ec.resolve_platform(prose, heading=title or "").label
    verdict = ec.score_themes(title or "", prose, _COMFYUI_THEME_RULES)
    if verdict is None:
        return "", "", platform, ""
    return verdict.theme, verdict.area, platform, verdict.severity


# --- one acceptance path for every candidate -------------------------------------------------------

def evaluate_issue(record: base.PatchRecord, issue: dict[str, Any], captured_at: str) -> dict[str, Any]:
    """One evidence row for (record, issue), counted or excluded with its reason.

    Identity first (this adapter), then the shared authority unchanged.
    """
    version = str(record.update_version or "")
    release_date = base.date_part(record.update_published_at or "")
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    own = clean_text(title + "\n" + body)
    number = issue.get("number")
    url = str(issue.get("html_url") or f"{ISSUE_URL_PREFIX}{number}")
    theme, area, platform, severity = classify(title, body)

    identity = resolve_identity(own, version)
    reason = identity["reason"] or issue_kind_exclusion(
        [str((label or {}).get("name") or "") for label in issue.get("labels") or [] if isinstance(label, dict)],
        own)
    if not reason:
        declared = identity["declared"]
        if len(declared) > 1:
            # Several sessions' logs, several core versions: a pasted log is not a statement of
            # WHICH run failed, so no declaration may claim the shared R1 immunity. Measured: a
            # post carrying a 0.41.0 log and a 0.26.0 log was about 0.41.0, and 0.26.0 was the
            # version it rolled back to. The durable rule for a post naming more than one tracked
            # version (acrobat shared-build lesson): silence is not enough, the shared role reading
            # must say AFFECTED.
            outcome = classify_target_outcome(own, version)
            if outcome.outcome != AFFECTED:
                reason = (f"version_role_{outcome.outcome}" if outcome.vetoes
                          else "multiple_core_versions_declared")
        else:
            contradiction = target_is_contradicted(own, version, declared)
            if contradiction is not None:
                reason = f"version_role_{contradiction.outcome}"
    matched = bool(identity["established"]) or bool(_occurrences(own, version))
    span_start, span_end = (_occurrences(own, version) or [(-1, -1)])[0]
    provenance = base.match_provenance([("report_text", own)], span_start, span_end)

    row = base.make_evidence_row(
        product_id=PRODUCT_ID,
        update_version=version,
        source_type=SOURCE_TYPE,
        source_name=SOURCE_NAME,
        source_url=url,
        parent_title=title,
        report_title=title,
        report_text=own,
        captured_at=captured_at,
        # The issue's own creation time. updated_at moves with every comment and is never read.
        source_date=base.date_part(issue.get("created_at") or ""),
        target_release_date=release_date,
        patch_version_matched=bool(identity["established"]),
        matched_version=version if identity["established"] else "",
        match_basis=identity["basis"],
        counted=False,
        exclusion_reason=reason or None,
        issue_theme=theme,
        workflow_area=area,
        platform=platform,
        severity=severity,
        sentiment="",
        row_id=f"{PRODUCT_ID}-{base.slug(version)}-github-issue-{number}",
        matched_text=provenance.get("matched_text", "") if matched else "",
        matched_field=provenance.get("matched_field", "") if matched else "",
        matched_context=provenance.get("matched_context", "") if matched else "",
    )
    if reason:
        row["counted"] = False
        row["exclusion_reason"] = reason
        return base.normalize_evidence_row(row)
    gated = base.apply_acceptance_gates(row, report_text=own)
    # DERIVED, NOT INVENTED (the Teams rule). A counted row has already passed the concreteness
    # gate, so "negative" restates what acceptance means. It is load-bearing: the promotion refuses a
    # counted row without a sentiment while reconciliation counts it, which would publish a count
    # with no summary -- the blocking QA error that discards every product's cycle.
    if gated.get("counted") is True:
        gated["sentiment"] = "negative"
    return base.normalize_evidence_row(gated)


# --- discovery -------------------------------------------------------------------------------------

def budget_expired() -> bool:
    budget = rb.get_run_budget()
    return budget is not None and budget.collector_finalize_expired()


def window_start(since: str | None, now: datetime | None = None) -> str:
    """The `created:` lower bound. The run's own `since` when given, else the routine horizon."""
    text = str(since or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    moment = now or datetime.now(timezone.utc)
    return (moment - timedelta(days=DEFAULT_WINDOW_DAYS)).date().isoformat()


def search_page_url(since: str, page: int) -> str:
    query = f"repo:{REPO} is:issue created:>={since}"
    return f"{github.API_BASE}/search/issues?" + urllib.parse.urlencode({
        "q": query, "sort": "created", "order": "desc", "per_page": PER_PAGE, "page": page})


def enumerate_issues(since: str, errors: list[dict[str, Any]], *,
                     fetch: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every issue (never a pull request) created on or after `since`, newest first, one pass.

    Returns (issues, telemetry). Transport failures are appended to `errors` with the shared GitHub
    taxonomy (`rate_limited`, `access_denied`, `http_403_error`, `http_<code>_error`,
    `network_unreachable`, `payload_parse_failed`), so method health can tell a refused walk from an
    empty window.

    The walk ends where GitHub's pagination contract says it ends -- no rel="next" in the Link
    header -- not where a page happens to be shorter than the requested size.
    """
    fetcher = fetch or github.request_json
    issues: list[dict[str, Any]] = []
    seen: set[int] = set()
    telemetry: dict[str, Any] = {"since": since, "pages": 0, "total_count": 0,
                                 "incomplete_results": False, "truncated": False}
    max_pages = SEARCH_RESULT_CAP // PER_PAGE
    for page in range(1, max_pages + 1):
        if budget_expired():
            errors.append({"source_url": github.API_BASE, "reason": BUDGET_STOP_REASON})
            break
        try:
            payload, _meta = fetcher(search_page_url(since, page))
        except Exception as exc:  # noqa: BLE001 -- the reason is recorded for method health
            errors.append({"source_url": github.API_BASE, "reason": github.error_reason(exc)})
            break
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            errors.append({"source_url": github.API_BASE, "reason": "payload_parse_failed"})
            break
        telemetry["pages"] += 1
        telemetry["total_count"] = int(payload.get("total_count") or 0)
        if payload.get("incomplete_results"):
            telemetry["incomplete_results"] = True
        items = payload["items"]
        for item in items:
            if not isinstance(item, dict) or item.get("pull_request"):
                continue
            number = item.get("number")
            url = str(item.get("html_url") or "")
            if not isinstance(number, int) or not url.startswith(ISSUE_URL_PREFIX) or number in seen:
                continue
            seen.add(number)
            issues.append(item)
        if not github_api.has_next_page(_meta, payload, page=page, per_page=PER_PAGE,
                                        result_cap=SEARCH_RESULT_CAP):
            break
    if telemetry["total_count"] > SEARCH_RESULT_CAP:
        telemetry["truncated"] = True
    return issues, telemetry


def issue_text(issue: dict[str, Any]) -> str:
    """The opening post as the decision path reads it: title, newline, body, cleaned."""
    return clean_text(f"{issue.get('title') or ''}\n{issue.get('body') or ''}")


def candidates_for(version: str, issues: list[dict[str, Any]], *,
                   texts: dict[int, str] | None = None) -> list[dict[str, Any]]:
    """Issues whose opening post names this version at all, by the shared exact matcher.

    An issue that never names the version is not a REJECTED candidate for it, it was never a
    candidate (the OBS forum rule): counting every issue in the window as a rejection for every
    record would make the telemetry meaningless. `texts` caches issue_text per issue for a run that
    tests one walk against every record.
    """
    out = []
    for issue in issues:
        text = texts.get(id(issue)) if texts else None
        if text is None:
            text = issue_text(issue)
        if version in text and _occurrences(text, version):
            out.append(issue)
    return out


def reposts(candidates: list[dict[str, Any]]) -> dict[int, int]:
    """issue number -> the earlier issue it repeats, for one person filing the same report twice.

    Same author account and the same title, normalised: one report, posted twice (the AUX-098 rule).
    The lower issue number is kept. The author is compared in memory only and never stored.
    """
    first: dict[tuple[str, str], int] = {}
    out: dict[int, int] = {}
    for issue in sorted(candidates, key=lambda item: int(item.get("number") or 0)):
        author = str(((issue.get("user") or {}).get("id")) or "")
        title = re.sub(r"\W+", " ", str(issue.get("title") or "").lower()).strip()
        if not author or not title:
            continue
        key = (author, title)
        number = int(issue.get("number") or 0)
        if key in first:
            out[number] = first[key]
        else:
            first[key] = number
    return out


def method_status(errors: list[dict[str, Any]], telemetry: dict[str, Any], accepted: int) -> str:
    """Canonical health. A refused or broken walk is never "nothing found"; a truncated one is partial."""
    reasons = [str(e.get("reason") or "") for e in errors]
    walked = int(telemetry.get("pages") or 0) > 0
    if not walked:
        # GitHub signals secondary rate limits with 403, so 403 and 429 are refusals however they
        # arrive (the shared transport maps both to rate_limited; a raw HTTPError names its code).
        if any(github_api.is_stop(r) or r == "http_429_error" for r in reasons):
            return "blocked"
        if any(r == BUDGET_STOP_REASON for r in reasons):
            return "partial"
        return "broken" if reasons else "no_results"
    if reasons or telemetry.get("incomplete_results") or telemetry.get("truncated"):
        return "partial"
    return "success" if accepted else "no_results"


def apply_consensus_writeback(update_version: str) -> bool:
    """Hand this patch to the SHARED consensus authority; the collector writes freshness only.

    apply_collector_record_fields filters every proposal through COLLECTOR_WRITABLE_FIELDS, so
    what lands here is evidence_last_checked and record_last_updated -- never the count, summary or
    samples, which belong to reconciliation and the scoped promotion step. Selects by canonical
    identity and refuses an ambiguous resolution.
    """
    return apply_consensus_writebacks([update_version]).get(update_version, False)


def apply_consensus_writebacks(update_versions: list[str]) -> dict[str, bool]:
    """`apply_consensus_writeback` for several patches from ONE dry run of the shared authority.

    The dry run reads the whole evidence store and indexes every generated record; measured, one
    call per accepted patch was ~25 s each, most of a ComfyUI run. Selection per patch is unchanged:
    exactly one group under the version, `would_write`, and the record the dry run resolved.
    """
    from apply_consensus_to_records import (_index_generated_records,  # noqa: PLC0415
                                            apply_collector_record_fields, run_dry_run)

    wanted = [str(v) for v in update_versions if str(v or "")]
    out = {version: False for version in wanted}
    if not wanted:
        return out
    results = run_dry_run(evidence_path=base.EVIDENCE_PATH, product_id_filter=PRODUCT_ID,
                          is_candidate_mode=False, records_index=_index_generated_records(),
                          write_requested=True)
    for version in wanted:
        matches = [item for item in results if item.get("update_version") == version]
        if len(matches) != 1 or not matches[0].get("would_write"):
            continue
        record_rel = matches[0].get("matched_generated_record_path")
        if not record_rel:
            continue
        fields = dict(matches[0].get("proposed_fields_if_written") or {})
        applied = apply_collector_record_fields(ROOT / record_rel, fields) or {}
        out[version] = bool((applied.get("write_plan") or {}).get("fields"))
    return out


class ComfyUICollector(base.ProductCollector):
    """Community evidence for the ComfyUI core releases the official lane already tracks.

    Patch targets come from the EXISTING generated records, never from version arithmetic: a report
    can only attach to a release AUXSAYS already has an official record for.
    """

    product_id = PRODUCT_ID

    def collect(self, context: base.CollectorContext) -> list[dict[str, Any]]:
        records = base.newest_first(base.generated_records(
            PRODUCT_ID, getattr(context, "target_versions", None)))
        captured_at = base.utc_now()
        since = window_start(getattr(context, "since", None))
        errors: list[dict[str, Any]] = []
        # ONE walk for the whole run: the window is the same corpus for every record.
        issues, telemetry = enumerate_issues(since, errors)
        rb.emit("comfyui_issue_walk", product_id=PRODUCT_ID, since=since, issues=len(issues),
                pages=telemetry.get("pages"), total_count=telemetry.get("total_count"),
                truncated=bool(telemetry.get("truncated")), errors=len(errors))

        results: list[dict[str, Any]] = []
        run_rows: list[dict[str, Any]] = []
        texts = {id(issue): issue_text(issue) for issue in issues}
        for record in records:
            if budget_expired():
                rb.emit("collector_budget_stop", product_id=PRODUCT_ID, reason="collector_finalize")
                break
            version = str(record.update_version or "")
            candidates = candidates_for(version, issues, texts=texts)
            repeated = reposts(candidates)
            accepted: list[dict[str, Any]] = []
            rejected: list[dict[str, Any]] = []
            for issue in candidates:
                row = evaluate_issue(record, issue, captured_at)
                original = repeated.get(int(issue.get("number") or 0))
                if original is not None and row.get("counted"):
                    row["counted"] = False
                    row["sentiment"] = ""
                    row["exclusion_reason"] = f"same_report_reposted_of_issue_{original}"
                    row = base.normalize_evidence_row(row)
                (accepted if row.get("counted") else rejected).append(row)

            status = method_status(errors, telemetry, len(accepted))
            blocked = ""
            if status in ("blocked", "broken", "partial"):
                blocked = (str(errors[0].get("reason") or "") if errors
                           else ("search_result_window_truncated" if telemetry.get("truncated")
                                 else "search_incomplete_results"))[:120]
            health = [base.method_health_row(
                product_id=PRODUCT_ID, update_version=version, method_id=METHOD_ID,
                source_type=SOURCE_TYPE, status=status, candidates_found=len(candidates),
                accepted_reports=len(accepted), rejected_reports=len(rejected),
                blocked_reason=blocked, last_run=captured_at,
                notes=(f"{REPO} GitHub issues created since {since}, opening posts only; "
                       f"{len(issues)} issues walked, {len(candidates)} name {version}, "
                       f"accepted {len(accepted)}, excluded {len(rejected)}."
                       + (f" {github_api.stop_note()}" if errors and github_api.stop_state() else "")))]
            result: dict[str, Any] = {
                "product_id": PRODUCT_ID,
                "version": version,
                "mode": "write" if context.write else "dry-run",
                "candidates_reviewed": len(candidates),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [r["source_url"] for r in accepted],
                "rejection_reasons": dict(sorted(
                    {reason: sum(1 for r in rejected if r.get("exclusion_reason") == reason)
                     for reason in {str(r.get("exclusion_reason") or "") for r in rejected}}.items())),
                "method_health": health,
            }
            run_rows.extend(accepted + rejected)
            results.append(result)

        if context.write:
            # ONE append for the run. The store is read and rewritten once, not once per record:
            # measured, per-record appends plus per-record writebacks cost ~390 s for 50 records,
            # almost all of it re-reading the same 3,000-row store.
            persisted: list[dict[str, Any]] = []
            already_held: list[dict[str, Any]] = []
            if run_rows:
                base.append_evidence_rows(
                    run_rows, out_added=persisted, out_already_held=already_held,
                    method_health=[row for result in results for row in result["method_health"]])
            # The health delta speaks about ACCEPTED reports: excluded rows are stored for audit,
            # and must not be credited as reports this method added (or already held). Attribution
            # is per (patch, source type), so one call finalizes every record's row.
            base.finalize_method_health_delta(
                [row for result in results for row in result["method_health"]],
                [r for r in persisted if r.get("counted")],
                [r for r in already_held if r.get("counted")])
            new_accepted = sorted({str(r.get("update_version") or "") for r in persisted if r.get("counted")})
            # Freshness moves only when a new accepted report arrived; a re-found report changes
            # nothing the writeback could write.
            updated = apply_consensus_writebacks(new_accepted)
            for result in results:
                version = str(result["version"])
                result["evidence_rows_added"] = sum(
                    1 for r in persisted if str(r.get("update_version") or "") == version)
                result["record_updated"] = bool(updated.get(version, False))
        return results
