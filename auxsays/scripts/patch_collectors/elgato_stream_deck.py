#!/usr/bin/env python3
"""Elgato Stream Deck community evidence from Elgato's own public GitHub issue tracker.

STATUS: BUILT, NOT REGISTERED. Taken through the vendor-onboarding playbook
(scripts/onboard_vendor.py). No production path registers this collector, no method plan or
ownership entry names its product, and it refuses write mode: Elgato is a per-platform vendor, and
qa_patch_records.PLATFORM_UNGATED_COMPANIES keeps community evidence away from such a vendor until
its records carry a platform gate. Nothing here runs in production.

SOURCE. github.com/elgatosf/streamdeck -- Elgato's public repository for the Stream Deck SDK, MIT
licensed, issues open. Read through GitHub's REST API with the repository's shared client
(lib/github_api.py): the same method (`github_issues`), source type (`github_issue`) and transport
OBS and ComfyUI already use against their own projects' trackers. No HTML is fetched, no login wall
is involved, and the client honours GitHub's rate-limit signals.

WHAT IT CAN AND CANNOT SEE. This tracker is where plugin developers report problems; it is not a
general Stream Deck support forum. A report counts only when its OPENING POST states the Stream Deck
APPLICATION version it concerns. The SDK package version (`@elgato/streamdeck@3.0.5`), the CLI, a
plugin's own version, Node.js and the operating system are different numbers and never establish
the application version. Measured over the tracker's whole history on 2026-11-24: 42 issues, so the
honest expectation is a handful of rows a year. Low volume is a fact about the source, not a reason
to loosen anything.

IDENTITY (this adapter), then the SHARED authority unchanged:

  1. the record's exact version occurs in the opening post (base.exact_version_match_span);
  2. an occurrence is STATED AS THE APPLICATION VERSION: it directly follows "Stream Deck",
     optionally "app / application / software / desktop" and "version", or it is the answer under an
     issue-form heading that asks for the Stream Deck version. Anything else is
     `version_not_stated_as_stream_deck_app`;
  3. it is not stated as a REQUIREMENT ("requires Stream Deck 7.1", "7.1 or later", "since 6.5"):
     `version_stated_as_requirement`. A minimum version is not the version that failed;
  4. the shared role authority (lib.target_outcome) does not contradict it ("worked on 7.5",
     "fixed in 7.6"): `version_role_<outcome>`;
  5. pull requests, and issues a maintainer labelled as a feature request or documentation, are not
     problem reports;
  6. then base.apply_acceptance_gates: exact version, a specific issue URL, dated on or after the
     release, a concrete problem. Weight 1, like every other counted row.

Every rule above only REMOVES candidates. None of them can accept what the shared gates refuse.
Exclusions are stored rows (counted: false + exclusion_reason), so every refusal is auditable.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

from lib import evidence_classification as ec
from lib import github_api
from lib.target_outcome import AFFECTED, classify_target_outcome, target_is_contradicted
from patch_collectors import base
from patch_collectors import runtime_budget as rb

ROOT = base.ROOT

PRODUCT_ID = "elgato-stream-deck"
REPO = "elgatosf/streamdeck"
METHOD_ID = "github_issues"
SOURCE_TYPE = "github_issue"
SOURCE_NAME = "elgatosf/streamdeck"
ISSUE_URL_PREFIX = f"https://github.com/{REPO}/issues/"
ENDPOINT_FAMILY = "github_elgato_streamdeck_issues"

PER_PAGE = 50
SEARCH_RESULT_CAP = 1000
DEFAULT_WINDOW_DAYS = 45
BUDGET_STOP_REASON = "run_budget_stop"

NOT_PROBLEM_LABELS = frozenset({"enhancement", "feature", "feature request", "documentation", "docs", "question"})

# "Stream Deck 7.6.1", "StreamDeck app 7.6.1", "Stream Deck software version: 7.6.1",
# "Stream Deck (7.6.1)" -- the application named, then at most a qualifier and "version", then the
# number. Anchored at the END of the text before the occurrence, on the same line.
_APP_PREFIX_RE = re.compile(
    r"stream\s?deck(?:\s+(?:app|application|software|desktop(?:\s+app)?|for\s+(?:windows|mac(?:os)?)))?"
    r"(?:\s+version)?\s*[:=(]?\s*v?\Z", re.I)
# A different component named immediately before the number. Checked first: "Stream Deck SDK 2.0".
_OTHER_COMPONENT_RE = re.compile(
    r"(?:@elgato/[\w-]+@?|\b(?:sdk|cli|plugin|node(?:\.js)?|npm|firmware|typescript|electron|qt|"
    r"windows|mac\s?os|macos|property\s+inspector)\b)[^\n]{0,24}\Z", re.I)
# Issue-form heading that asks for the application version; its answer is the next non-empty line.
_FORM_HEADING_RE = re.compile(r"^#{1,6}\s*(?:elgato\s+)?stream\s?deck(?:\s+(?:app|application|software))?\s+version\s*$",
                              re.I | re.M)
# The version is a floor or a capability statement, not the version the reporter is failing on.
_REQUIREMENT_BEFORE_RE = re.compile(
    # The requirement word must be the LAST thing before the application's name, allowing only
    # filler ("the", "version", "at least"). "requires Stream Deck 7.1" is a floor; "since updating
    # to Stream Deck 7.6.1" is a report about 7.6.1, and the word "updating" keeps it out of here.
    r"\b(?:requires?|required|requiring|needs?|minimum(?:\s+(?:version|required))?(?:\s+(?:of|is))?|min\.?|"
    r"at\s+least|since|starting\s+(?:with|from|in)|as\s+of|supports?|"
    r"supported\s+(?:in|on|from|since|by)|available\s+(?:in|from|since)|introduced\s+in|added\s+in|"
    r"new\s+in|targets?|targeting)\s+(?:(?:the|a|an|version|at\s+least|elgato)\s+)*\Z", re.I)
_REQUIREMENT_AFTER_RE = re.compile(
    r"\A\s*(?:\+|and\s+(?:later|newer|above|up)|or\s+(?:later|newer|above|higher|greater)|"
    r"(?:and\s+)?onwards?|,?\s+which\s+(?:supports|adds|introduced))", re.I)
_FENCED_RE = re.compile(r"```.*?(?:```|\Z)", re.S)

_THEME_RULES: tuple[ec.ThemeRule, ...] = (
    ec.ThemeRule("crash or freeze", "application stability", "high", "crash",
                 re.compile(r"\b(?:crash\w*|freez\w*|frozen|hang(?:s|ing)?|hung|unresponsive|"
                            r"not\s+responding|loops?|looping)\b", re.I), negatable=True),
    ec.ThemeRule("plugin fails to load or connect", "plugins", "medium", "plugin",
                 re.compile(r"\b(?:plugins?\s+(?:fails?|failed|won't|cannot|can't|does\s+not|doesn't|stops?|stopped)"
                            r"|(?:fails?|failed|unable)\s+to\s+(?:load|connect|start|register)|disconnect\w*)\b", re.I)),
    ec.ThemeRule("device or key display problem", "devices and keys", "medium", "device",
                 re.compile(r"\b(?:keys?\s+(?:blank|black|not\s+updat\w+|flicker\w*)|(?:image|icon|title)s?\s+"
                            r"(?:not\s+(?:show\w*|updat\w+|display\w*)|missing|blank)|dials?\s+not|touch\s?strip)\b", re.I)),
)
ec.validate_rules(_THEME_RULES)


def clean_text(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def issue_text(issue: dict[str, Any]) -> str:
    """The opening post as the decision path reads it: title, newline, body."""
    return clean_text(f"{issue.get('title') or ''}\n{issue.get('body') or ''}")


def occurrences(text: str, version: str) -> list[tuple[int, int]]:
    """Every position the shared matcher accepts as this exact version."""
    out: list[tuple[int, int]] = []
    offset = 0
    while offset <= len(text):
        matched, _v, _basis, start, end = base.exact_version_match_span(text[offset:], version)
        if not matched:
            break
        out.append((offset + start, offset + end))
        offset += max(end, 1)
    return out


def _line_before(text: str, start: int) -> str:
    return text[text.rfind("\n", 0, start) + 1:start]


def _form_answer_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of the answer line under each 'Stream Deck version' issue-form heading."""
    spans = []
    for heading in _FORM_HEADING_RE.finditer(text):
        rest = text[heading.end():]
        answer = re.search(r"\S[^\n]*", rest)
        if answer and not answer.group(0).lstrip().startswith("#"):
            spans.append((heading.end() + answer.start(), heading.end() + answer.end()))
    return spans


def resolve_identity(text: str, version: str) -> dict[str, Any]:
    """Does the opening post state `version` as the Stream Deck APPLICATION version it concerns?

    Returns {established, basis, reason, span}. Fail closed: the version being present is not
    enough, and the first qualifying occurrence wins only if no rule refuses it."""
    spans = occurrences(text, version)
    if not spans:
        return {"established": False, "basis": "", "reason": "missing_exact_patch_version_match", "span": (-1, -1)}
    form_spans = _form_answer_spans(text)
    saw_requirement = False
    for start, end in spans:
        before = _line_before(text, start)
        in_form = any(lo <= start and end <= hi for lo, hi in form_spans)
        if not in_form:
            if _OTHER_COMPONENT_RE.search(before) and not _APP_PREFIX_RE.search(before):
                continue
            if not _APP_PREFIX_RE.search(before):
                continue
        # What precedes the application's name ("requires Stream Deck 7.1"), and what follows the
        # number ("7.1 or later"). A form answer has no preceding prose of its own.
        lead = "" if in_form else _APP_PREFIX_RE.sub("", before)
        if _REQUIREMENT_BEFORE_RE.search(lead) or _REQUIREMENT_AFTER_RE.search(text[end:end + 40]):
            saw_requirement = True
            continue
        return {"established": True, "basis": "issue_form_field" if in_form else "body",
                "reason": "", "span": (start, end)}
    return {"established": False, "basis": "",
            "reason": "version_stated_as_requirement" if saw_requirement
            else "version_not_stated_as_stream_deck_app", "span": spans[0]}


def issue_kind_exclusion(labels: list[str]) -> str:
    names = {str(label or "").strip().lower() for label in labels}
    return "feature_or_docs_request_not_a_problem_report" if names & NOT_PROBLEM_LABELS else ""


def classify(title: str, body: str) -> tuple[str, str, str, str]:
    prose = _FENCED_RE.sub(" ", clean_text(body))
    platform = ec.resolve_platform(prose, heading=title or "").label
    verdict = ec.score_themes(title or "", prose, _THEME_RULES)
    if verdict is None:
        return "", "", platform, ""
    return verdict.theme, verdict.area, platform, verdict.severity


def evaluate_issue(record: base.PatchRecord, issue: dict[str, Any], captured_at: str,
                   tracked_versions: Any = ()) -> dict[str, Any]:
    """One evidence row for (record, issue), counted or excluded with its reason.

    `tracked_versions` are the versions of every Stream Deck record. A post that names MORE THAN
    ONE of them is comparing releases, and silence about which one failed is then not enough: the
    shared role authority must read this version as AFFECTED (the rule ComfyUI and Acrobat apply to
    a post naming several tracked versions). Measured on the real tracker on 2026-11-24, before
    this rule: a post stating that 6.8.1 showed NO lag was accepted as a report against 6.8.1."""
    version = str(record.update_version or "")
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    own = issue_text(issue)
    number = issue.get("number")
    url = str(issue.get("html_url") or f"{ISSUE_URL_PREFIX}{number}")
    theme, area, platform, severity = classify(title, body)

    identity = resolve_identity(own, version)
    reason = identity["reason"] or issue_kind_exclusion(
        [str((label or {}).get("name") or "") for label in issue.get("labels") or [] if isinstance(label, dict)])
    if not reason:
        declared = [version] if identity["basis"] == "issue_form_field" else []
        others = [v for v in tracked_versions if v and v != version and v in own and occurrences(own, v)]
        if others:
            outcome = classify_target_outcome(own, version, declared)
            if outcome.outcome != AFFECTED:
                reason = (f"version_role_{outcome.outcome}" if outcome.vetoes
                          else "several_app_versions_named_role_not_established")
        else:
            contradiction = target_is_contradicted(own, version, declared)
            if contradiction is not None:
                reason = f"version_role_{contradiction.outcome}"
    span_start, span_end = identity["span"]
    provenance = base.match_provenance([("report_text", own)], span_start, span_end) if span_start >= 0 else {}
    row = base.make_evidence_row(
        product_id=PRODUCT_ID, update_version=version, source_type=SOURCE_TYPE, source_name=SOURCE_NAME,
        source_url=url, parent_title=title, report_title=title, report_text=own, captured_at=captured_at,
        # The issue's own creation time. updated_at moves with every comment and is never read.
        source_date=base.date_part(issue.get("created_at") or ""),
        target_release_date=base.date_part(record.update_published_at or ""),
        patch_version_matched=bool(identity["established"]),
        matched_version=version if identity["established"] else "",
        match_basis=identity["basis"], counted=False, exclusion_reason=reason or None,
        issue_theme=theme, workflow_area=area, platform=platform, severity=severity, sentiment="",
        row_id=f"{PRODUCT_ID}-{base.slug(version)}-github-issue-{number}",
        matched_text=provenance.get("matched_text", ""), matched_field=provenance.get("matched_field", ""),
        matched_context=provenance.get("matched_context", ""))
    if reason:
        row["counted"] = False
        row["exclusion_reason"] = reason
        return base.normalize_evidence_row(row)
    gated = base.apply_acceptance_gates(row, report_text=own)
    if gated.get("counted") is True:
        gated["sentiment"] = "negative"      # derived: a counted row has passed the concreteness gate
    return base.normalize_evidence_row(gated)


# --- discovery -------------------------------------------------------------------------------------

def budget_expired() -> bool:
    budget = rb.get_run_budget()
    return budget is not None and budget.collector_finalize_expired()


def window_start(since: str | None, now: datetime | None = None) -> str:
    text = str(since or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    moment = now or datetime.now(timezone.utc)
    return (moment - timedelta(days=DEFAULT_WINDOW_DAYS)).date().isoformat()


def search_page_url(since: str, page: int) -> str:
    query = f"repo:{REPO} is:issue created:>={since}"
    return f"{github_api.API_ORIGIN}/search/issues?" + urllib.parse.urlencode({
        "q": query, "sort": "created", "order": "desc", "per_page": PER_PAGE, "page": page})


def request_json(url: str) -> tuple[Any, dict[str, str]]:
    """One GitHub API GET through the shared transport (the test seam)."""
    return github_api.get_json(url, endpoint_family=ENDPOINT_FAMILY)


def enumerate_issues(since: str, errors: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every issue (never a pull request) created on or after `since`, newest first, one pass."""
    issues: list[dict[str, Any]] = []
    seen: set[int] = set()
    telemetry: dict[str, Any] = {"since": since, "pages": 0, "requests": 0, "total_count": 0,
                                 "incomplete_results": False, "truncated": False}
    for page in range(1, SEARCH_RESULT_CAP // PER_PAGE + 1):
        if budget_expired():
            errors.append({"source_url": github_api.API_ORIGIN, "reason": BUDGET_STOP_REASON})
            break
        telemetry["requests"] += 1
        try:
            payload, meta = request_json(search_page_url(since, page))
        except Exception as exc:  # noqa: BLE001 -- the reason is recorded for method health
            errors.append({"source_url": github_api.API_ORIGIN, "reason": github_api.error_reason(exc)})
            break
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            errors.append({"source_url": github_api.API_ORIGIN, "reason": "payload_parse_failed"})
            break
        telemetry["pages"] += 1
        telemetry["total_count"] = int(payload.get("total_count") or 0)
        telemetry["incomplete_results"] = telemetry["incomplete_results"] or bool(payload.get("incomplete_results"))
        for item in payload["items"]:
            if not isinstance(item, dict) or item.get("pull_request"):
                continue
            number, url = item.get("number"), str(item.get("html_url") or "")
            if not isinstance(number, int) or not url.startswith(ISSUE_URL_PREFIX) or number in seen:
                continue
            seen.add(number)
            issues.append(item)
        if not github_api.has_next_page(meta, payload, page=page, per_page=PER_PAGE, result_cap=SEARCH_RESULT_CAP):
            break
    telemetry["truncated"] = telemetry["total_count"] > SEARCH_RESULT_CAP
    return issues, telemetry


def method_status(errors: list[dict[str, Any]], telemetry: dict[str, Any], accepted: int) -> str:
    """Canonical health. A refused or broken walk is never "nothing found"."""
    reasons = [str(e.get("reason") or "") for e in errors]
    if not int(telemetry.get("pages") or 0):
        if any(github_api.is_stop(r) or r == "http_429_error" for r in reasons):
            return "blocked"
        if any(r == BUDGET_STOP_REASON for r in reasons):
            return "partial"
        return "broken" if reasons else "no_results"
    if reasons or telemetry.get("incomplete_results") or telemetry.get("truncated"):
        return "partial"
    return "success" if accepted else "no_results"


class ElgatoStreamDeckCollector(base.ProductCollector):
    """Community evidence for the Stream Deck releases the official lane already tracks. Patch
    targets come from the EXISTING generated records, never from version arithmetic."""

    product_id = PRODUCT_ID

    def collect(self, context: base.CollectorContext) -> list[dict[str, Any]]:
        if context.write:
            # Persisting evidence and touching records is part of ACTIVATION, which this collector
            # has not been through (see the module docstring and the playbook's checklist).
            raise RuntimeError("elgato_stream_deck collector is not activated: dry-run only")
        # ONE scan of the generated records: the run's targets and the tracked-version list both
        # come from it (a scan reads every record file in the repository).
        every_record = base.generated_records(PRODUCT_ID, None)
        targets = getattr(context, "target_versions", None)
        records = base.newest_first([r for r in every_record if not targets or r.update_version in targets])
        captured_at = base.utc_now()
        since = window_start(getattr(context, "since", None))
        errors: list[dict[str, Any]] = []
        started = time.monotonic()
        issues, telemetry = enumerate_issues(since, errors)        # ONE walk for the whole run
        walk_ms = int((time.monotonic() - started) * 1000)
        rb.emit("elgato_stream_deck_issue_walk", product_id=PRODUCT_ID, since=since, issues=len(issues),
                pages=telemetry.get("pages"), errors=len(errors))
        texts = {id(issue): issue_text(issue) for issue in issues}
        tracked = sorted({str(r.update_version or "") for r in every_record} - {""})
        results: list[dict[str, Any]] = []
        run_rows: list[dict[str, Any]] = []
        for index, record in enumerate(records):
            if budget_expired():
                rb.emit("collector_budget_stop", product_id=PRODUCT_ID, reason="collector_finalize")
                break
            version = str(record.update_version or "")
            candidates = [issue for issue in issues
                          if version in texts[id(issue)] and occurrences(texts[id(issue)], version)]
            accepted: list[dict[str, Any]] = []
            rejected: list[dict[str, Any]] = []
            for issue in candidates:
                row = evaluate_issue(record, issue, captured_at, tracked)
                (accepted if row.get("counted") else rejected).append(row)
            status = method_status(errors, telemetry, len(accepted))
            blocked = ""
            if status in ("blocked", "broken", "partial"):
                blocked = (str(errors[0].get("reason") or "") if errors else "search_incomplete_results")[:120]
            health = [base.method_health_row(
                product_id=PRODUCT_ID, update_version=version, method_id=METHOD_ID, source_type=SOURCE_TYPE,
                status=status, candidates_found=len(candidates), accepted_reports=len(accepted),
                rejected_reports=len(rejected), blocked_reason=blocked, last_run=captured_at,
                notes=(f"{REPO} GitHub issues created since {since}, opening posts only; {len(issues)} issues "
                       f"walked, {len(candidates)} name {version}, accepted {len(accepted)}, "
                       f"excluded {len(rejected)}."),
                # The walk is made once and serves every record: its cost is stated on the first
                # record's row, and the others state the zero requests they caused.
                duration_ms=walk_ms if index == 0 else 0,
                requests=int(telemetry.get("requests") or 0) if index == 0 else 0,
                rejection_reasons=base.rejection_reason_counts(rejected))]
            results.append({
                "product_id": PRODUCT_ID, "version": version,
                "mode": "write" if context.write else "dry-run",
                "candidates_reviewed": len(candidates), "accepted_count": len(accepted),
                "rejected_count": len(rejected), "accepted_urls": [r["source_url"] for r in accepted],
                "rejection_reasons": base.rejection_reason_counts(rejected), "method_health": health,
            })
            run_rows.extend(accepted + rejected)

        return results
