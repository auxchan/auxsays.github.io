"""Windows 11 community-evidence collector (Microsoft Learn Q&A).

Discovers real Windows 11 user reports from Microsoft Learn Q&A (learn.microsoft.com/
answers) via its search-RSS API, driving each search by the *exact current patch
identity* already captured on the generated record (target_kb / target_os_build). It
then applies deterministic acceptance gates so a report counts ONLY when it names the
record's current KB or OS build. It reuses the fail-closed Windows identity gate added
in PR #14, so evidence for an older KB/build can never count after a train rolls over.

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

import re
from typing import Any

from .base import (
    EVIDENCE_PATH,
    CollectorContext,
    PatchRecord,
    ProductCollector,
    WINDOWS_PRODUCT_ID,
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
    text_describes_issue,
    utc_now,
    windows_identity_gate,
)
from lib.patch_identity import patch_key
from . import microsoft_learn_qna_source as learn_qna
from . import runtime_budget as rb

PRODUCT_ID = WINDOWS_PRODUCT_ID
METHOD_ID = "learn_qna_search_rss"
SOURCE_TYPE = "microsoft_learn_qna"
SOURCE_NAME = "Microsoft Learn Q&A"

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


def classify(text: str) -> tuple[str, str, str, str, str]:
    lowered = (text or "").lower()
    if any(t in lowered for t in ("bsod", "blue screen", "blue-screen", "bugcheck", "bug check", "stop code", "stop error")) or re.search(r"0x[0-9a-f]{6,8}", lowered):
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
    return windows_intent_reason(report_text, report_title, matched_kb, matched_os_build)


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


def evaluate_candidates(record: PatchRecord, target: dict[str, Any], candidates: list[dict[str, Any]], captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = learn_qna.canonical_learn_qna_url(str(candidate.get("source_url") or ""))
        key = url.lower()
        if not url or key in seen:
            continue  # run-level duplicate URL dedup
        seen.add(key)
        row = row_from_candidate(record, target, {**candidate, "source_url": url}, captured_at)
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

def collect_for_record(record: PatchRecord, context: CollectorContext) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
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
    accepted, rejected = evaluate_candidates(record, target, candidates, captured_at)
    health = [health_for_method(record, target, captured_at, candidates, accepted, rejected, errors, query_terms)]
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
        for record in records:
            _b = rb.get_run_budget()
            if _b is not None and _b.collector_finalize_expired():
                rb.emit("collector_budget_stop", product_id=PRODUCT_ID, reason="collector_finalize")
                break
            accepted, rejected, health = collect_for_record(record, context)
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
                added, total, rows = append_evidence_rows(accepted)
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
