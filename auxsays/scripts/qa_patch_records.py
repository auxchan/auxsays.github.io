#!/usr/bin/env python3
"""Warning-first QA for generated AUXSAYS update records and priority source coverage."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from lib.patch_identity import identity_build, is_build_aware, patch_key

from lib.report_counts import counted_evidence_counts, windows_targets_from_front_matter

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"
UPDATES_DIR = ROOT / "updates"
OUT_PATH = ROOT / "_data" / "qa_status.json"
PRODUCTS_PATH = ROOT / "_data" / "patch_products.yml"
SOURCES_PATH = ROOT / "_data" / "patch_ingestion_sources.yml"
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
UPDATE_LAYOUT_PATH = ROOT / "_layouts" / "aux-update.html"

VALID_EVIDENCE_STATES = {"official_only", "pilot_sample", "pilot_initial_sample", "consensus_live", "insufficient_data"}
VALID_INTELLIGENCE_STAGES = {"staged", "official_live", "pilot", "consensus_live", "archived", "manual_watch"}
PATCH_NOTE_SOURCE_TYPES = {"release_notes", "fixed_issues", "security_advisory", "changelog"}
NON_PATCH_NOTE_SOURCE_TYPES = {"whats_new", "vendor_blog", "community_official_post", "download_portal"}
OPERATIONAL_SOURCE_TYPES = {"release_health", "known_issues", "help_center_release_notes"}
LEGACY_SOURCE_TYPES = {"official-source", "adobe-official-release-source", "github-release", "rss-feed", "vendor-release-page"}
KNOWN_SOURCE_TYPES = PATCH_NOTE_SOURCE_TYPES | NON_PATCH_NOTE_SOURCE_TYPES | OPERATIONAL_SOURCE_TYPES | LEGACY_SOURCE_TYPES
BANNED_PUBLIC_TERMS = {
    "consensus_evidence.yml",
    "deterministically accepted",
    "source-backed",
    "source_weight",
    "promoted evidence rows",
    "promoted rows",
    "write-back",
    "writeback",
    "verified reports set",
    "not broad consensus",
    "low-confidence",
    "low confidence",
    "broad consensus",
    "evidence state",
    "collector",
    "candidate rows",
}
# Per-term, per-field exemptions for the internal-language gate.
#
# Most banned terms are unambiguous AUXSAYS implementation vocabulary and are rejected in every
# public field. "collector" is different: it is also an ordinary English word that vendors use in
# their own release notes. GitHub's changelog entry "Enterprise managed settings in GitHub Copilot
# for JetBrains" describes configuring OpenTelemetry "including the collector endpoint, protocol,
# service name, resource attributes and headers", and that vendor prose lands verbatim in
# `release_summary` (rss_feed sets record["summary"], which write_update_record copies to
# release_summary). Flattening every public field into one blob before matching therefore failed
# the whole ingestion run on a legitimate upstream sentence.
#
# The exemption is deliberately as narrow as the evidence: ONE term, ONE field, and only because
# `release_summary` is the single public field proven to carry source-authored vendor prose on that
# path. `official_summary` is NOT exempt -- rss_feed leaves it unset and write_update_record
# substitutes AUXSAYS-authored fallback text there. Every other banned term still applies inside
# `release_summary`, and "collector" is still rejected in every AUXSAYS-authored field, so genuine
# implementation leakage in decision/consensus language remains a blocking defect.
BANNED_TERM_FIELD_EXEMPTIONS: dict[str, frozenset[str]] = {
    "collector": frozenset({"release_summary"}),
}
# Claims AUXSAYS must never make on a vendor's behalf. A build with no app-specific release note is
# not a build in which the app did not change -- and the official-notes body is scanned too, since
# that is where a fabricated vendor claim would actually live.
FORBIDDEN_ABSENCE_CLAIMS = (
    "no powerpoint changes",
    "no app-specific changes",
    "no changes for",
    "was unchanged",
    "were unchanged",
    "nothing changed",
    "no changes were made",
)
# AUXSAYS-authored text: a forbidden claim here is our own fabrication -> ERROR.
ABSENCE_CLAIM_SCANNED_FIELDS = (
    "official_summary",
    "release_summary",
    "summary",
    "description",
    "quick_verdict",
    "update_consensus_summary",
    "official_app_attribution_label",
)
# Vendor-captured text: the vendor may legitimately write any of these phrases about their own
# product. Flag it for review, but never fail the whole ingest run on somebody else's wording.
ABSENCE_CLAIM_WARN_FIELDS = ("official_patch_notes_body",)
# Vendor-attribution states an official record may declare (lib.write_update_record).
VALID_APP_ATTRIBUTION_STATES = {
    "app_named_by_source",
    "suite_wide_by_source",
    "app_named_and_suite_wide_by_source",
    "not_documented_by_source",
}

PUBLIC_TEXT_FIELDS = {
    "description",
    "update_consensus_summary",
    "quick_verdict",
    "update_decision_label",
    "update_decision_body",
    "source_freshness_note",
    "record_note",
    "official_summary",
    "release_summary",
    "consensus_report",
    "community_summary",
    "practical_recommendations",
    "complaint_themes",
    "status_events",
    "evidence_samples",
    "accepted_report_sources",
    "evidence_source_limitations",
}

PRIORITY_PRODUCTS = {
    "obs-studio",
    "blackmagic-davinci",
    "adobe-premiere-pro",
    "adobe-acrobat-reader",
    "adobe-acrobat-pro",
    "microsoft-windows-11",
    "elgato-stream-deck",
    "elgato-wave-link",
    "elgato-camera-hub",
    "elgato-4k-capture-utility",
    "adobe-photoshop",
    "openai-chatgpt",
    "microsoft-powerpoint",
    "microsoft-teams",
    "microsoft-365-apps",
}


def load_yaml(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return fallback if data is None else data


def front_matter(path: Path) -> dict[str, Any]:
    from lib.normalize import split_front_matter
    text = path.read_text(encoding="utf-8")
    front, _body = split_front_matter(text)
    if front is None:
        return {}
    data = yaml.safe_load(front)
    return data if isinstance(data, dict) else {}


def add(bucket: list[dict[str, str]], path: Path | str, code: str, message: str) -> None:
    if isinstance(path, Path) and path.is_absolute():
        try:
            file_value = str(path.relative_to(ROOT))
        except ValueError:
            file_value = str(path)  # fixture/temp path outside the repo (route-integrity tests)
    else:
        file_value = str(path)
    bucket.append({"file": file_value, "code": code, "message": message})


def looks_like_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def has_structured_evidence(data: dict[str, Any]) -> bool:
    evidence = data.get("consensus_evidence") or data.get("structured_evidence") or data.get("evidence_objects")
    return isinstance(evidence, list) and len(evidence) > 0 and all(isinstance(item, dict) for item in evidence)


def contains_public_static_sample(value: Any) -> bool:
    if isinstance(value, str):
        return ("static" + " sample") in value.lower()
    if isinstance(value, list):
        return any(contains_public_static_sample(item) for item in value)
    if isinstance(value, dict):
        return any(contains_public_static_sample(item) for item in value.values())
    return False


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    return ""


def public_record_text(data: dict[str, Any]) -> str:
    return " ".join(flatten_text(data.get(field)) for field in sorted(PUBLIC_TEXT_FIELDS))


def internal_term_findings(data: dict[str, Any], path: str) -> list[dict[str, Any]]:
    """Banned internal terms in public fields, checked FIELD BY FIELD.

    Field provenance matters twice over: it decides whether a per-term exemption applies (see
    BANNED_TERM_FIELD_EXEMPTIONS), and it tells whoever reads the failure which field to look at.
    The previous implementation flattened all PUBLIC_TEXT_FIELDS into one string before matching,
    so it could do neither -- a vendor's ordinary use of "collector" failed the run, and the error
    named no field.
    """
    findings: list[dict[str, Any]] = []
    for field in sorted(PUBLIC_TEXT_FIELDS):
        text = flatten_text(data.get(field)).lower()
        if not text:
            continue
        for term in sorted(BANNED_PUBLIC_TERMS):
            if term not in text:
                continue
            if field in BANNED_TERM_FIELD_EXEMPTIONS.get(term, frozenset()):
                continue
            findings.append({
                "path": path,
                "code": "public_internal_term",
                "message": (f"Public-facing field '{field}' contains internal term '{term}'."),
            })
    return findings


def load_counted_evidence_counts(
        records: list[dict[str, Any]]) -> dict[tuple[str, str, str], int]:
    # Delegates to the single authoritative predicate (lib.report_counts.counted_evidence_counts) so
    # this QA gate and the post-collection reconciliation count evidence IDENTICALLY and can never
    # diverge -- that shared definition is what makes update_report_count == final counted evidence.
    payload = load_yaml(EVIDENCE_PATH, [])
    rows = payload.get("evidence") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}
    # `records` supplies the Windows current-patch identities the canonical predicate gates on, and
    # is REQUIRED for the same reason the predicate requires them: defaulting it would make a
    # forgotten argument read 0 counted reports for every Windows patch, which this gate would then
    # "confirm" against a record. A Windows patch present in `records` but carrying no target
    # identity still fails closed -- excluded, not counted against an unknown identity.
    return counted_evidence_counts(
        rows, windows_targets=windows_targets_from_front_matter(records or []))


def scan_record(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    data = front_matter(path)
    if not data:
        add(errors, path, "missing_front_matter", "Generated record has no readable YAML front matter.")
        return errors, warnings

    title = str(data.get("title") or "").strip()
    summary = str(data.get("release_summary") or data.get("summary") or data.get("description") or "").strip()
    version = str(data.get("update_version") or data.get("version") or "").strip()
    detail_title = str(data.get("update_detail_title") or "").strip()
    evidence_state = str(data.get("evidence_state") or "").strip()
    source_type = str(data.get("official_patch_notes_source_type") or data.get("official_source_type") or "").strip()
    official_body = str(data.get("official_patch_notes_body") or "")
    report_count = int(data.get("update_report_count") or data.get("confirmed_patch_specific_report_count") or 0)

    # DOCTRINE GATE. "The vendor did not document a change for this app" and "the app did not
    # change" are different claims, and only the first is ours to make. A build ships shared Office
    # components, security fixes and installers whether or not the notes single an app out, so a
    # substantive-negative claim would assert something the vendor never said. Enforced here rather
    # than trusted, because prose is exactly what regresses quietly.
    for field in ABSENCE_CLAIM_SCANNED_FIELDS:
        text = str(data.get(field) or "").lower()
        for phrase in FORBIDDEN_ABSENCE_CLAIMS:
            if phrase in text:
                add(errors, path, "substantive_absence_claim",
                    f"{field} claims {phrase!r}. Absence of a documented note describes the notes, "
                    "not the software -- say the vendor did not document a change instead.")
    for field in ABSENCE_CLAIM_WARN_FIELDS:
        text = str(data.get(field) or "").lower()
        for phrase in FORBIDDEN_ABSENCE_CLAIMS:
            if phrase in text:
                add(warnings, path, "vendor_text_absence_claim",
                    f"{field} (vendor-captured) contains {phrase!r}. Confirm it is the vendor's "
                    "own wording and not AUXSAYS prose.")
    attribution = str(data.get("official_app_attribution") or "").strip()
    if attribution and attribution not in VALID_APP_ATTRIBUTION_STATES:
        add(errors, path, "unknown_app_attribution_state",
            f"official_app_attribution {attribution!r} is not one of {sorted(VALID_APP_ATTRIBUTION_STATES)}.")

    if not title:
        add(errors, path, "empty_title", "Generated record title is empty.")
    if not summary:
        add(warnings, path, "empty_summary", "Generated record has no useful summary/description.")

    if version and detail_title and len(re.findall(re.escape(version), detail_title, flags=re.I)) > 1:
        add(warnings, path, "duplicated_detail_title_version", f"Detail title appears to repeat version '{version}'.")
    if version and title and len(re.findall(re.escape(version), title, flags=re.I)) > 1:
        add(warnings, path, "duplicated_title_version", f"Title appears to repeat version '{version}'.")

    # STORED PUBLIC LABEL vs CANONICAL IDENTITY. `title` and `description` are the two public
    # strings no layout can reach: aux-base.html renders `{% seo %}`, and jekyll-seo-tag reads them
    # straight off the front matter for <title>, og:title, og:description and the meta description.
    # Every other headline derives its build at render time from `target_build`
    # (_includes/patch-public-label.html), so these two are the only ones that can silently keep a
    # stale, build-free label -- which is exactly what happened: they are baked once at record
    # CREATE time and refresh_existing_record never rewrites them, so 20 PowerPoint records shipped
    # a bare version beside a per-BUILD monitoring status. Repair with
    # `normalize_public_build_labels.py --apply`. Only ever checked when the record ALREADY states
    # its own build; a build-aware record with no build is an identity fault reported elsewhere and
    # never a licence to guess a label for it here.
    record_build = identity_build(data, data.get("product_id"))
    if is_build_aware(data.get("product_id")) and record_build:
        stale_label_fields = sorted(
            field for field in ("title", "description")
            if str(data.get(field) or "").strip() and record_build not in str(data.get(field)))
        if stale_label_fields:
            add(errors, path, "public_label_missing_build",
                f"{', '.join(stale_label_fields)} does not state build {record_build}. A sibling "
                "build under the same version would publish an identical public label.")

    if evidence_state == "official_only" and report_count > 0:
        add(errors, path, "official_only_with_reports", "Record has report_count > 0 but evidence_state is official_only.")
    if evidence_state == "consensus_live" and not has_structured_evidence(data):
        add(errors, path, "live_without_structured_evidence", "consensus_live requires structured evidence objects.")
    if evidence_state and evidence_state not in VALID_EVIDENCE_STATES:
        add(warnings, path, "unknown_evidence_state", f"Evidence state '{evidence_state}' is not in the normalized taxonomy.")
    if contains_public_static_sample(data):
        add(errors, path, "public_static_sample_wording", "Public-facing generated record data still contains obsolete sample wording. Use 'Verified reports' for the evidence-state label.")
    public_text = public_record_text(data)
    if ("Pilot" + " sample") in public_text or ("pilot" + " sample") in public_text:
        add(errors, path, "public_pilot_sample_wording", "Public-facing generated record data still contains obsolete pilot-sample wording. Use 'Verified reports' for the evidence-state label.")
    for finding in internal_term_findings(data, path):
        # Same error code as before so dashboards and workflow parsers need no vocabulary
        # migration; only the message gained the field name.
        add(errors, path, finding["code"], finding["message"])
    if re.search(r"https?://\S+;\s*https?://", public_text):
        add(errors, path, "raw_source_urls_in_public_prose", "Public-facing generated prose appears to dump raw source URLs; use source objects/lists instead.")

    if report_count > 0:
        if is_blank(data.get("update_consensus_summary")):
            add(errors, path, "report_count_without_consensus_summary", "Record has report_count > 0 but no update_consensus_summary.")
        if not isinstance(data.get("evidence_samples"), list) or len(data.get("evidence_samples") or []) == 0:
            add(errors, path, "report_count_without_evidence_samples", "Record has report_count > 0 but no representative evidence_samples.")
        if not isinstance(data.get("accepted_report_sources"), list) or len(data.get("accepted_report_sources") or []) == 0:
            add(warnings, path, "report_count_without_accepted_report_sources", "Record has report_count > 0 but no collapsed full accepted source list.")
        if isinstance(data.get("evidence_samples"), list) and len(data.get("evidence_samples") or []) > 5:
            add(errors, path, "too_many_representative_samples", "evidence_samples should contain no more than five representative items; put the full list in accepted_report_sources.")

    evidence_samples = data.get("evidence_samples")
    if evidence_samples is not None:
        if not isinstance(evidence_samples, list):
            add(errors, path, "evidence_samples_not_list", "evidence_samples must be a list of source objects.")
        else:
            for idx, item in enumerate(evidence_samples):
                if not isinstance(item, dict):
                    add(errors, path, "evidence_sample_item_not_object", f"evidence_samples[{idx}] must be an object.")
                    continue
                if not looks_like_url(item.get("source_url")):
                    add(errors, path, "evidence_sample_missing_source_url", f"evidence_samples[{idx}] is missing a valid source_url.")
                if item.get("counted") is True and item.get("patch_version_matched") is not True:
                    add(errors, path, "counted_evidence_without_patch_match", f"evidence_samples[{idx}] is counted but patch_version_matched is not true.")

    stage = str(data.get("intelligence_stage") or "").strip()
    if stage and stage not in VALID_INTELLIGENCE_STAGES:
        add(warnings, path, "unknown_intelligence_stage", f"Intelligence stage '{stage}' is not recognized.")

    for key in ("update_source_url", "official_patch_notes_source_url", "update_download_url"):
        value = data.get(key)
        if value not in (None, "") and not looks_like_url(value):
            add(warnings, path, "malformed_url", f"{key} does not look like a valid HTTP(S) URL.")

    if is_blank(data.get("patch_file_size")) and is_blank(data.get("patch_file_size_status")):
        add(warnings, path, "blank_file_size_without_status", "patch_file_size is blank and no patch_file_size_status explains why.")
    if is_blank(data.get("patch_file_size")) and not is_blank(data.get("patch_file_size_status")):
        valid_file_size_statuses = {"not_provided_by_source", "creative_cloud_managed", "pending_adapter_support"}
        if str(data.get("patch_file_size_status") or "").strip() not in valid_file_size_statuses:
            add(warnings, path, "unknown_file_size_status", "patch_file_size_status is present but not in the normalized status list.")
    if evidence_state == "official_only" and report_count == 0:
        if data.get("known_issues_present") is True:
            add(warnings, path, "official_only_zero_reports_known_issues_yes", "official_only record has 0 reports but known_issues_present is true; the UI may imply patch-specific user reports exist.")
        if data.get("complaint_themes"):
            add(warnings, path, "official_only_zero_reports_complaint_themes", "official_only record has 0 reports but complaint_themes are present; this can imply counted patch-specific user reports.")
        recommendation_text = " ".join(
            [
                str(data.get("quick_verdict") or ""),
                str(data.get("update_decision_label") or ""),
                str(data.get("update_decision_body") or ""),
                flatten_text(data.get("practical_recommendations")),
            ]
        ).lower()
        blocked_recommendation_terms = (
            "wait",
            "avoid",
            "safe enough",
            "production-stable",
            "production systems",
            "install guidance",
            "manual watch",
            "manual-watch",
        )
        if any(term in recommendation_text for term in blocked_recommendation_terms):
            add(warnings, path, "official_only_zero_reports_recommendation_language", "official_only record has 0 reports but still stores install-verdict recommendation language.")
    # Safety rule 3 — manual_watch + nonzero verified count
    # If intelligence_stage is manual_watch, verified report counts must be 0
    # unless a clearly separate legacy_manual_report_count field carries the value.
    if stage == "manual_watch" and report_count > 0:
        legacy_count = data.get("legacy_manual_report_count")
        legacy_is_separate = legacy_count not in (None, "")
        if not legacy_is_separate:
            add(
                errors,
                path,
                "manual_watch_nonzero_verified_count",
                f"intelligence_stage is manual_watch but update_report_count is {report_count}. "
                "User report counts must be 0 for manual_watch records unless a separate "
                "legacy_manual_report_count field preserves historical context.",
            )

    # Safety rule 4 — legacy_manual_report_count must not drive verified evidence
    # Warn if legacy_manual_report_count is nonzero AND the primary report_count
    # also equals it — this risks the legacy value being treated as evidence-backed.
    legacy_count_value = data.get("legacy_manual_report_count")
    if legacy_count_value not in (None, ""):
        try:
            legacy_int = int(legacy_count_value)
        except (TypeError, ValueError):
            legacy_int = 0
        if legacy_int > 0 and report_count == legacy_int and evidence_state in ("official_only", "insufficient_data", ""):
            add(
                warnings,
                path,
                "legacy_count_equals_report_count_no_evidence_state",
                f"legacy_manual_report_count ({legacy_int}) equals update_report_count but evidence_state "
                f"is '{evidence_state or 'not set'}'. If this count is historical-only, it must not match "
                "the live report_count — the live count should be 0 for records with no structured evidence.",
            )

    if str(data.get("official_checksums_capture_status") or "").strip() in {"captured", "present"} and is_blank(data.get("official_checksums_body")):
        add(errors, path, "checksum_status_without_body", "Checksum capture status says checksums are present but official_checksums_body is blank.")
    if is_blank(data.get("official_checksums_body")) and (data.get("show_checksum_section") is True or data.get("checksum_nav_enabled") is True):
        add(errors, path, "checksum_display_without_body", "Record enables checksum display but official_checksums_body is blank.")

    official_claim = " ".join([title, detail_title, official_body[:500]]).lower()
    if "patch notes" in official_claim and source_type in NON_PATCH_NOTE_SOURCE_TYPES:
        add(errors, path, "patch_notes_claim_from_non_patch_source", f"Source type '{source_type}' must not be labeled as patch notes.")
    if source_type in NON_PATCH_NOTE_SOURCE_TYPES and data.get("official_note_status") == "release_notes_captured":
        add(errors, path, "release_notes_status_mismatch", "Non-release source is marked release_notes_captured.")
    if source_type and source_type not in KNOWN_SOURCE_TYPES:
        add(warnings, path, "unknown_official_source_type", f"official source type '{source_type}' is not classified.")

    official_sources = data.get("official_sources")
    if official_sources is not None:
        if not isinstance(official_sources, list):
            add(warnings, path, "official_sources_not_list", "official_sources should be a list of source objects.")
        else:
            for idx, item in enumerate(official_sources):
                if not isinstance(item, dict):
                    add(warnings, path, "official_source_item_not_object", f"official_sources[{idx}] is not an object.")
                    continue
                if not looks_like_url(item.get("url")):
                    add(warnings, path, "official_source_item_bad_url", f"official_sources[{idx}] has a malformed URL.")
                if not item.get("source_type"):
                    add(warnings, path, "official_source_item_missing_type", f"official_sources[{idx}] is missing source_type.")

    return errors, warnings


def scan_update_layout_public_copy() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not UPDATE_LAYOUT_PATH.exists():
        add(errors, UPDATE_LAYOUT_PATH, "missing_update_layout", "aux-update.html is missing.")
        return errors, warnings

    text = UPDATE_LAYOUT_PATH.read_text(encoding="utf-8")
    forbidden_public_copy = {
        "Record Note": "Record notes must be folded into the verdict context, not rendered as a standalone card.",
        "Sample size": "Sample size should not render as a standalone public field.",
        "Evidence Status": "Evidence status should not render as a standalone public field.",
        "Official source captured": "Official-source capture state should stay out of the public patch-page card stack.",
        "Record updated": "Record update timestamps should stay out of public patch pages.",
        "Patch-specific user reports": "Patch-specific report counts should not be repeated outside the top evidence card.",
        "Community risk sample": "User reports should render as sources, not as a separate community-risk concept.",
        "Practical recommendation": "Use public heading 'Recommendation' instead.",
        "Evidence methodology details": "Use 'Evidence summary' for report-bearing pages and hide the large section for 0-report pages.",
        "Static" + " sample": "Public-facing evidence labels must use Verified reports.",
        "Pilot" + " sample": "Public-facing evidence labels must use Verified reports.",
        "pilot" + " sample": "Public-facing evidence labels must use Verified reports.",
        "Intel" + " Status": "Public-facing wording must use Evidence Status.",
        "Official sources are listed first": "Sources should render as concise citations without filler intro copy.",
        "Community bug reports are shown": "Sources should not repeat methodology filler.",
        "AUXSAYS counts a report only when": "Methodology details belong on the methodology page, not patch bodies.",
        "Official source content has not been captured into this AUXSAYS record yet": "Do not force a blank Official Source Summary block.",
        "deterministically accepted": "Backend evidence-gate wording must not render on public patch pages.",
        "source-backed": "Backend evidence-gate wording must not render on public patch pages.",
        "source_weight": "Backend evidence fields must not render on public patch pages.",
        "consensus_evidence.yml": "Repository implementation filenames must not render on public patch pages.",
        "promoted rows": "Backend evidence-row wording must not render on public patch pages.",
        "YAML": "Backend serialization wording must not render on public patch pages.",
        "writeback": "Backend pipeline wording must not render on public patch pages.",
        "collector": "Backend collection-worker wording must not render on public patch pages.",
        "candidate rows": "Backend evidence-row wording must not render on public patch pages.",
        "evidence state": "Internal evidence-state wording must not render on public patch pages.",
        "low confidence": "Methodology confidence shorthand belongs on the methodology page, not patch bodies.",
        "broad consensus": "Consensus claims must not be implied by patch-page boilerplate.",
    }
    for phrase, message in forbidden_public_copy.items():
        if phrase in text:
            add(errors, UPDATE_LAYOUT_PATH, "layout_public_copy_regression", message)

    if "{% assign evidence_state = 'User reports found' %}" in text:
        add(errors, UPDATE_LAYOUT_PATH, "layout_pilot_sample_label_stale", "pilot_sample must render as Verified reports, not User reports found.")
    if "{% assign evidence_state = 'Verified reports' %}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "layout_pilot_sample_label_missing", "Patch layout must normalize pilot_sample to Verified reports.")

    required_public_labels = [
        "Official Patch Notes",
        "Technical Details",
        "User Reports / Sources",
        "Verified reports",
        "Methodology",
        "AUXSAYS verdict",
        "Release date",
        "Last evidence checked",
    ]
    for phrase in required_public_labels:
        if phrase not in text:
            add(errors, UPDATE_LAYOUT_PATH, "layout_required_label_missing", f"Patch layout must render '{phrase}'.")

    if "checksum_body_clean" not in text or "{% if checksum_present %}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "checksum_render_not_guarded", "Checksum content must require stripped non-empty checksum content.")
    if "{{ checksum_body_clean | markdownify }}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "checksum_body_render_path_missing", "Checksum section should render stripped checksum content when present.")
    if "user report{% unless report_count == 1 %}s{% endunless %} counted" in text:
        add(errors, UPDATE_LAYOUT_PATH, "top_evidence_card_duplicate_data", "Top evidence card should use the concise found-count line, not old counted copy.")
    if "update-evidence-report-count" not in text or "user report{% unless report_count == 1 %}s{% endunless %} found" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "top_evidence_report_count_missing", "Top evidence card should show the counted user-report total once inside the evidence card.")
    if "consensus-chart-meta" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "top_chart_evidence_date_missing", "Top chart should retain the last evidence checked date inside the chart area.")
    if "update-evidence-meta-row" in text:
        add(errors, UPDATE_LAYOUT_PATH, "top_evidence_card_metadata_regression", "Release date and file size should render as top metadata pills, not inside the evidence card.")
    if "legacy_consensus_score_percent" in text or "page.consensus_score_percent" in text:
        add(errors, UPDATE_LAYOUT_PATH, "sentiment_marker_uses_legacy_score", "The top sentiment marker must follow the displayed evidence summary, not legacy score fields.")
    if "consensus-position-graph--{{ evidence_metric_class }}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "sentiment_marker_class_missing", "The top sentiment graph should carry the evidence summary class for visual state handling.")
    if "consensus-scale-labels--neutral" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "sentiment_neutral_state_missing", "Not-enough-report pages should use a neutral chart treatment.")
    if "update_platform_clean" in text or "platform_label_clean" in text or "update_type_clean" in text:
        add(errors, UPDATE_LAYOUT_PATH, "top_metadata_placeholder_pill_regression", "Top metadata should render only data-bearing product, version, channel, release date, and file-size pills.")
    if "file_size_pill_value" not in text or "{% if file_size_pill_value != blank %}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "file_size_pill_value_guard_missing", "The top file-size pill must render only when a stripped real value exists.")
    if "File size: {{ patch_file_size_clean" in text:
        add(errors, UPDATE_LAYOUT_PATH, "file_size_label_only_regression", "File-size metadata should use guarded label/value markup, not a label that can render without a value.")
    if "issue_cluster_first" not in text or "issue_label_first" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "verdict_issue_cluster_sanitize_missing", "Verdict issue cluster copy should strip leading punctuation before rendering.")
    official_notes_pos = text.find('id="official-patch-notes"')
    technical_details_pos = text.find('id="technical-details"')
    sources_pos = text.find('id="user-reports-sources"')
    checksum_pos = text.find('id="checksum"')
    if not (official_notes_pos != -1 and technical_details_pos != -1 and sources_pos != -1 and official_notes_pos < technical_details_pos < sources_pos):
        add(errors, UPDATE_LAYOUT_PATH, "technical_details_order_regression", "Technical Details must render after Official Patch Notes and before User Reports / Sources.")
    if checksum_pos != -1 and not (technical_details_pos != -1 and technical_details_pos < checksum_pos < sources_pos):
        add(errors, UPDATE_LAYOUT_PATH, "checksum_inside_official_notes", "Checksum must render inside Technical Details, not inside Official Patch Notes.")
    if "official_body_clean" not in text:
        add(warnings, UPDATE_LAYOUT_PATH, "official_summary_blank_guard_missing", "Official source summary should be guarded by stripped non-empty body content.")
    sources_disclosure = re.search(r"<details\b(?=[^>]*\bid=[\"']user-reports-sources[\"'])[^>]*>", text)
    if "accepted_report_sources" not in text or "user_report_source_count" not in text or "sources_collapsed_by_default" not in text or not sources_disclosure:
        add(errors, UPDATE_LAYOUT_PATH, "collapsible_sources_missing", "User Reports / Sources must render as a count-labeled details disclosure.")
    if "{% if user_report_source_count > 5 %}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "sources_collapse_threshold_missing", "User Reports / Sources should collapse by default only when more than five source items exist.")
    if "evidence_source_limitations" in text or "Source limitations" in text:
        add(warnings, UPDATE_LAYOUT_PATH, "source_limitations_public_copy_present", "Method limitations should live on the methodology page, not each patch page.")

    return errors, warnings


def scan_required_record_paths() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    obs_path = GENERATED_DIR / "2026-04-21-obs-studio-32-1-2.md"
    if obs_path.exists():
        data = front_matter(obs_path)
        if is_blank(data.get("official_checksums_body")):
            add(errors, obs_path, "obs_32_1_2_checksum_missing", "OBS Studio 32.1.2 should retain official_checksums_body content.")
    return errors, warnings


def scan_evidence_count_alignment(files: list[Path]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    # Read each record ONCE and reuse it for both the target map and the comparison below.
    loaded = [(path, front_matter(path)) for path in files]
    evidence_counts = load_counted_evidence_counts([data for _p, data in loaded])
    if not evidence_counts:
        return errors, warnings

    for path, data in loaded:
        # The count and the public source list are BOTH projections of one accepted-evidence
        # population -- `accepted_report_sources` is one entry per counted row, uncapped (the cap,
        # `evidence_sample_visible_limit`, applies to `evidence_samples` instead). So a record whose
        # list length differs from its own count is publishing two different populations, whatever
        # its count says. This is the drift the count comparison below structurally CANNOT see: that
        # one compares the record to the same predicate that wrote it, so it agrees by construction
        # even when the predicate is wrong. Windows 25H2 published count 32 beside 9 sources and 9
        # in its prose for three weeks with the count gate green. Checked only when a list exists,
        # and it is a length comparison -- no prose is parsed.
        sources = data.get("accepted_report_sources")
        if isinstance(sources, list) and sources:
            claimed = int(data.get("update_report_count")
                          or data.get("confirmed_patch_specific_report_count") or 0)
            if len(sources) != claimed:
                # WARNING, not an error, and deliberately so. Live it fires on three records: the
                # two Windows ones this change repairs, and obs-studio 32.2.2 (count 7, sources 3),
                # whose COUNT is already canonical -- only its projection is stale. That one is
                # pre-existing and documented in PR #69; repairing it means an obs-scoped
                # --write-all, and obs-studio DOES have a branch in _record_coherence_fields, so
                # that would rewrite its verdict prose. Blocking here would therefore halt the
                # writeback lane on a defect this change is scoped not to touch. Surfacing beats
                # both ignoring it and holding production hostage to it.
                add(warnings, path, "report_count_source_list_mismatch",
                    f"Record claims {claimed} user reports but lists {len(sources)} accepted "
                    f"report sources; both must project the same counted-evidence population.")
        product_id = str(data.get("product_id") or "").strip()
        version = str(data.get("update_version") or "").strip()
        if not product_id or not version:
            continue
        key = patch_key(product_id, version, data.get("target_build"))
        # An absent key means the canonical population for this exact patch is EMPTY. That is real
        # information: after a KB rollover a record can still claim reports for a patch with no
        # accepted evidence at all, and the count comparison below structurally cannot see it.
        #
        # It is a WARNING, never an error, and that is the whole point. `patch-ingest.yml` runs this
        # gate with NO reconcile step, and the rollover is exactly what that lane writes -- so
        # erroring fails the run that PERFORMS the rollover, its writeback never commits the new
        # target, and the rollover can never land. Verified: a permanent cross-lane wedge. Warning
        # keeps the signal AND lets the rollover land; the obs lane's reconcile corrects the count
        # within six hours. Measured zero false positives across all 905 live records.
        if key not in evidence_counts:
            claimed = int(data.get("update_report_count")
                          or data.get("confirmed_patch_specific_report_count") or 0)
            if claimed > 0:
                add(warnings, path, "report_count_for_empty_population",
                    f"Record claims {claimed} user reports, but the canonical counted-evidence "
                    f"population for this exact patch is empty.")
            continue
        expected = evidence_counts[key]
        actual = int(data.get("update_report_count") or data.get("confirmed_patch_specific_report_count") or 0)
        if actual != expected:
            add(
                errors,
                path,
                "generated_report_count_mismatch",
                f"Generated report count is {actual}, but structured counted evidence has {expected} rows.",
            )
    return errors, warnings


def scan_priority_source_coverage() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    products = load_yaml(PRODUCTS_PATH, [])
    sources = load_yaml(SOURCES_PATH, [])
    product_ids = {str(item.get("product_id") or item.get("id")) for item in products if isinstance(item, dict)}
    source_by_product = {str(item.get("product_id")): item for item in sources if isinstance(item, dict)}

    for product_id in sorted(PRIORITY_PRODUCTS):
        if product_id not in product_ids:
            add(warnings, PRODUCTS_PATH, "priority_product_missing_product_record", f"Priority product '{product_id}' has no patch_products.yml record.")
            continue
        source = source_by_product.get(product_id)
        if not source:
            add(warnings, SOURCES_PATH, "priority_product_missing_source_config", f"Priority product '{product_id}' has no source config entry.")
            continue
        ingestion = source.get("ingestion") if isinstance(source.get("ingestion"), dict) else {}
        official_url = ingestion.get("official_url")
        if not looks_like_url(official_url):
            code = "enabled_source_without_official_url" if source.get("enabled") else "staged_source_without_official_url"
            bucket = errors if source.get("enabled") else warnings
            add(bucket, SOURCES_PATH, code, f"Priority source '{product_id}' does not have a valid official_url.")
        source_type = str(ingestion.get("official_source_type") or ingestion.get("type") or "").strip()
        if source_type and source_type not in KNOWN_SOURCE_TYPES | {"html_release_notes", "github_releases", "help_center_release_notes", "html_changelog", "html_blog"}:
            add(warnings, SOURCES_PATH, "priority_product_unclassified_source_type", f"Priority source '{product_id}' uses unclassified source type '{source_type}'.")

    return errors, warnings


def _landing_route_source(updates_dir: Path, company_id: str, product_id: str) -> Path:
    """The repo-owned route source that emits the product landing page
    /updates/<company_id>/<product_id>/ — a hand-authored index.md (layout: aux-patch-product)."""
    return updates_dir / str(company_id) / str(product_id) / "index.md"


def scan_route_integrity(
    products: Any = None,
    record_fronts: list[dict[str, Any]] | None = None,
    updates_dir: Path | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Deterministic, blocking route-integrity QA.

    Product landing pages under /updates/<company>/<product>/ are emitted from explicit
    route-source files (updates/<company>/<product>/index.md). Product catalog rows and
    generated patch records do NOT create that route. This guards the class of bug where a
    product is activated (catalog + generated records) but its landing route source is
    missing, so the product page 404s in production (e.g. adobe-acrobat-pro after PR #21).

    Errors (blocking):
      - a product declaring a /updates/... landing route has no route-source index.md
      - a generated record references a product_id not present in the catalog
      - a generated record's parent product landing route has no route-source index.md
      - duplicate product_id in the catalog
      - duplicate landing-page permalink across route-source files
    Injectable paths/data make this unit-testable with fixtures.
    """
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if products is None:
        products = load_yaml(PRODUCTS_PATH, [])
    if updates_dir is None:
        updates_dir = UPDATES_DIR
    if record_fronts is None:
        record_fronts = []
        for path in sorted((updates_dir / "generated").glob("*.md")):
            fm = front_matter(path)
            fm = dict(fm) if isinstance(fm, dict) else {}
            fm["_path"] = path
            record_fronts.append(fm)

    # Catalog + duplicate product_id detection.
    catalog: dict[str, dict[str, Any]] = {}
    seen_pid: set[str] = set()
    for prod in products if isinstance(products, list) else []:
        if not isinstance(prod, dict):
            continue
        pid = str(prod.get("product_id") or prod.get("id") or "").strip()
        if not pid:
            continue
        if pid in seen_pid:
            add(errors, PRODUCTS_PATH, "duplicate_product_id", f"product_id '{pid}' appears more than once in the product catalog.")
        seen_pid.add(pid)
        catalog[pid] = prod

    # Every catalog product that declares a /updates/... landing route must have a route source.
    for pid, prod in catalog.items():
        product_url = str(prod.get("product_url") or "").strip()
        company_id = str(prod.get("company_id") or "").strip()
        if not product_url.startswith("/updates/"):
            continue
        if not company_id:
            add(errors, PRODUCTS_PATH, "product_route_missing_company", f"Product '{pid}' declares landing route '{product_url}' but has no company_id to resolve its route source.")
            continue
        src = _landing_route_source(updates_dir, company_id, pid)
        if not src.exists():
            add(errors, src, "product_landing_route_missing", f"Product '{pid}' ({company_id}) declares landing route {product_url} but no route source exists. Create updates/{company_id}/{pid}/index.md (layout: aux-patch-product) or /updates/{company_id}/{pid}/ will 404.")

    # Every generated record must map to a catalog product AND an emittable parent route.
    for fm in record_fronts:
        pid = str(fm.get("product_id") or "").strip()
        cid = str(fm.get("company_id") or "").strip()
        rpath = fm.get("_path") or PRODUCTS_PATH
        if not pid:
            continue
        if pid not in catalog:
            add(errors, rpath, "record_product_not_in_catalog", f"Generated record product_id '{pid}' is not present in the product catalog.")
            continue
        if cid and not _landing_route_source(updates_dir, cid, pid).exists():
            add(errors, rpath, "record_parent_route_missing", f"Generated record for '{pid}' has no parent product landing page (expected updates/{cid}/{pid}/index.md); its patch pages exist but /updates/{cid}/{pid}/ would 404.")

    # Duplicate landing-page permalinks across route sources.
    seen_permalinks: dict[str, Path] = {}
    for idx in sorted(updates_dir.glob("*/*/index.md")):
        permalink = str(front_matter(idx).get("permalink") or "").strip()
        if not permalink:
            continue
        if permalink in seen_permalinks:
            add(errors, idx, "duplicate_landing_permalink", f"Landing permalink '{permalink}' is emitted by multiple route sources ({seen_permalinks[permalink]} and {idx}).")
        seen_permalinks[permalink] = idx

    return errors, warnings


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(GENERATED_DIR.glob("*.md"))
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for path in files:
        e, w = scan_record(path)
        errors.extend(e)
        warnings.extend(w)

    e, w = scan_priority_source_coverage()
    errors.extend(e)
    warnings.extend(w)
    e, w = scan_evidence_count_alignment(files)
    errors.extend(e)
    warnings.extend(w)
    e, w = scan_update_layout_public_copy()
    errors.extend(e)
    warnings.extend(w)
    e, w = scan_required_record_paths()
    errors.extend(e)
    warnings.extend(w)
    e, w = scan_route_integrity()
    errors.extend(e)
    warnings.extend(w)

    status = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "blocking",
        "records_scanned": len(files),
        "priority_products_checked": len(PRIORITY_PRODUCTS),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    OUT_PATH.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"QA scanned {len(files)} generated records and {len(PRIORITY_PRODUCTS)} priority products: {len(errors)} errors, {len(warnings)} warnings")
    for item in warnings[:25]:
        print(f"::warning file={item['file']}::{item['code']}: {item['message']}")
    if len(warnings) > 25:
        print(f"::warning::{len(warnings) - 25} additional warnings omitted from log; see auxsays/_data/qa_status.json")
    for item in errors:
        print(f"::error file={item['file']}::{item['code']}: {item['message']}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
