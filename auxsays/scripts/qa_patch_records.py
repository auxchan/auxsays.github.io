#!/usr/bin/env python3
"""Warning-first QA for generated AUXSAYS update records and priority source coverage."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from lib import maturity, patch_decision, verdict_projection, verdict_reasons
from lib.patch_identity import patch_display_label, patch_key
# The dedup identity the append path itself applies (base.evidence_key uses it), imported rather
# than re-derived. A hand-rolled canonicaliser was measured against the corpus first and was WRONG:
# stripping query strings collapsed six genuinely distinct Blackmagic forum threads
# (viewtopic.php?t=...) onto one path and falsely reported duplicate evidence. "Distinct" here means
# exactly what it meant when the row was accepted.
# `normalize_url` is the CITATION spelling (exact correspondence with the accepted population);
# `report_url_key` is the REPORT identity the append guard dedups on, which differs from it only for
# Microsoft Learn Q&A, where two title slugs of one question are one report (AUX-078).
from patch_collectors.base import normalize_url, report_url_key, row_is_counted

from lib.report_counts import (counted_evidence_counts, counted_evidence_rows,
                               windows_targets_from_front_matter)

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"
UPDATES_DIR = ROOT / "updates"
OUT_PATH = ROOT / "_data" / "qa_status.json"
PRODUCTS_PATH = ROOT / "_data" / "patch_products.yml"
SOURCES_PATH = ROOT / "_data" / "patch_ingestion_sources.yml"
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
UPDATE_LAYOUT_PATH = ROOT / "_layouts" / "aux-update.html"
REASONS_PATH = ROOT / "_data" / "verdict_reasons.yml"
LIFECYCLE_PATH = ROOT / "_data" / "patch_lifecycle.yml"
# Built at deploy by build_verdict_projection.py, never committed: the only source the verdict gate
# publishes a WAIT / TEST FIRST from. Present, it must equal the authority over this tree.
PROJECTION_PATH = ROOT / "_data" / verdict_projection.PROJECTION_NAME
# The patch page's maturity rung and decision ladder live in these two includes, which aux-update.html
# renders (and the homepage renders too). Their text is the layout's text for the public-copy scan:
# a phrase moved into one of them is still on every patch page.
UPDATE_LAYOUT_INCLUDES = (ROOT / "_includes" / "patch-evidence-state.html", ROOT / "_includes" / "patch-decision.html")

# The maturity vocabulary is owned by lib.maturity (canonical words plus the legacy words a stored
# record may still carry); QA reads it rather than keeping a fourth copy.
VALID_EVIDENCE_STATES = set(maturity.VALID_EVIDENCE_STATES)
VALID_INTELLIGENCE_STAGES = set(maturity.VALID_INTELLIGENCE_STAGES)
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


# `has_structured_evidence` was REMOVED, not reworked. It required front-matter
# `consensus_evidence`, `structured_evidence` or `evidence_objects`, and the `consensus_live` gate
# refused any record lacking one. Measured: 0 of 1316 generated records carried any of the three,
# nothing writes them and no template reads them -- and all three are ABSENT from
# `apply_consensus_to_records.WRITEABLE_FIELDS`, whose else-branch is
# `raise RuntimeError("Refusing to write unapproved field")`. So the precondition was unsatisfiable
# by data AND by the approved write path, which is why `consensus_live` has consumers and no
# producer.
#
# Deleted rather than left unused: a helper that names three fields nothing produces is an
# invitation to satisfy it by inventing a fourth representation, when the exhaustive one
# (`accepted_report_sources`) already ships and already renders.


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


def load_evidence_rows() -> list[Any]:
    """The evidence store's rows; [] when it is absent or malformed (QA reports, it does not refuse
    -- a live claim against an empty population fails its own checks). Read through `load_yaml` on
    every call, deliberately uncached: tests substitute `load_yaml` to feed a population, and a cache
    would serve the real store past that seam."""
    payload = load_yaml(EVIDENCE_PATH, [])
    rows = payload.get("evidence") if isinstance(payload, dict) else payload
    return rows if isinstance(rows, list) else []


def load_counted_evidence_counts(
        records: list[dict[str, Any]]) -> dict[tuple[str, str, str], int]:
    # Delegates to the single authoritative predicate (lib.report_counts.counted_evidence_counts) so
    # this QA gate and the post-collection reconciliation count evidence IDENTICALLY and can never
    # diverge -- that shared definition is what makes update_report_count == final counted evidence.
    rows = load_evidence_rows()
    if not rows:
        return {}
    # `records` supplies the Windows current-patch identities the canonical predicate gates on, and
    # is REQUIRED for the same reason the predicate requires them: defaulting it would make a
    # forgotten argument read 0 counted reports for every Windows patch, which this gate would then
    # "confirm" against a record. A Windows patch present in `records` but carrying no target
    # identity still fails closed -- excluded, not counted against an unknown identity.
    return counted_evidence_counts(
        rows, windows_targets=windows_targets_from_front_matter(records or []))


def load_counted_accepted_urls(
        records: list[dict[str, Any]]) -> dict[tuple[str, str, str], set[str]]:
    """The normalised source URLs of the authoritative accepted rows, per patch identity.

    Same predicate, same single read as `load_counted_evidence_counts` -- `counted_evidence_counts`
    is literally `len()` of these groups. A live claim must cite reports that are IN this
    population; matching its SIZE is not the same thing, and a projection of the right cardinality
    carrying one fabricated or superseded citation is invisible to a length comparison.
    """
    rows = load_evidence_rows()
    if not rows:
        return {}
    groups = counted_evidence_rows(
        rows, windows_targets=windows_targets_from_front_matter(records or []))
    return {key: {normalize_url(str(row.get("source_url") or "")) for row in group}
            for key, group in groups.items()}


# verdict_policy_drift's last sentence, ONE copy (G35-04 review 1, LOW-4). The record writers
# (apply_consensus_to_records.py, build_consensus_from_evidence.py) read REVIEWED reasons only, so a
# difference that comes from a reason-producer candidate never reaches the stored prose: said so.
DRIFT_CATCH_UP = ("The stored prose catches up when a record writer next promotes this page, unless the "
                  "difference comes from a reason-producer candidate: the writers read reviewed reasons only, "
                  "so that drift stays until they read the producer's reasons too.")


def scan_verdict_policy(files: list[Path]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """GROWTH-3: the two reviewed fact files, what each page RENDERS against what the authority
    decides, and each report-bearing record's stored verdict against the policy.

    ERRORS (both modes):
      * verdict_reasons_invalid / patch_lifecycle_invalid -- a malformed fact file. They change only
        by reviewed pull request, so a structural problem is a defect in that PR, never lane drift.
      * verdict_render_disagrees -- a page whose rendered verdict, scope, line, panel or
        recommendations would differ from lib/patch_decision.decide over this tree. The gate
        publishes EVERY verdict -- AVOID and SECURITY UPDATE included (review 2, LOW-1) -- only from
        the deploy-time verdict projection (_data/verdict_projection.yml), and every surface (patch
        page, homepage, tables, feed, My Patch Stack, search title) prints the gate, so this compares
        what the gate will READ for every page with what Python decides: a stale, forged, partial or
        failed projection is caught here, before Jekyll builds anything (review 1, D2). With no
        projection on disk (a writer lane, PR-time CI) the deploy builds it from this same tree, so
        the gate will read exactly the authority's rows.
      * verdict_projection_invalid / verdict_projection_failed -- the projection a deploy built is
        unreadable, or its builder could not decide: pages would fall back where the authority
        gives a verdict.

    PUBLICATION ERROR (a warning for the writeback lane, an ERROR under --publish-strict):
      * windows_update_type_malformed -- a Windows record whose stored release type is shaped like
        "YYYY-MM B / D / OOB" but is not one (review 2's "2026-3x B", "2026-+3 B", "2026-1  B").
        `decide` cannot classify it, so the page fails closed to INSUFFICIENT DATA and a security
        classification would vanish without a word; this says so. The value is collector-written,
        so, like record_names_conflicting_actions (AUX-009), one bad row must not discard a whole
        evidence run, and the deploy must not publish the page silently without its classification.
      * record_identity_unicode_padding -- a record whose product_id, update_version or target_build
        carries leading/trailing Unicode whitespace (U+00A0, U+2009, U+3000, U+0085, ...) that
        Liquid's strip keeps and Python's removes (PR-A2 review, LOW-1, probe P5). The page and
        `decide` agree on the padded key, but the page matches none of its reasons or counted rows,
        so a verdict would vanish without a word. Collector-written, so the same two severities.
      * patch_lifecycle_build_unmatched -- a build listed in a lifecycle entry that no record carries
        (scan_lifecycle_builds, its own corpus-wide scan; PR-A2 review, LOW-3, probe P4).

    WARNINGS, never writer-blocking and never promoted for publication:
      * verdict_reason_unsupported -- an entry whose cited rows no longer all count on its page (an
        audited withdrawal, a re-attribution), that lost its second reporter, or whose official
        confirmation is no longer in the named record's notes. The page has already fallen back --
        the projection is decided from the same evidence -- and the message names what it renders.
      * verdict_policy_drift -- a report-bearing record whose stored verdict or stored summary lead
        differs from what the policy decides now. Every surface prints the gate's verdict, so the
        page and the feed are already right. The stored prose catches up when a record writer next
        promotes the page -- EXCEPT where the difference comes from a reason-producer candidate
        (lib/verdict_reason_producer, only while its switch is on): the writers read reviewed reasons
        only, so that drift does not clear (G35-04 review 1, LOW-4; a recorded follow-up).
      * patch_lifecycle_unmatched -- a lifecycle entry no record carries.
    """
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    try:
        reasons = verdict_reasons.load_reasons(REASONS_PATH)
    except verdict_reasons.FactFileError as exc:
        add(errors, REASONS_PATH, "verdict_reasons_invalid", str(exc))
        reasons = []
    try:
        lifecycle = verdict_reasons.load_lifecycle(LIFECYCLE_PATH)
    except verdict_reasons.FactFileError as exc:
        add(errors, LIFECYCLE_PATH, "patch_lifecycle_invalid", str(exc))
        lifecycle = []
    reason_problems = verdict_reasons.schema_errors(reasons)
    for message in reason_problems:
        add(errors, REASONS_PATH, "verdict_reasons_invalid", message)
    lifecycle_problems = verdict_reasons.lifecycle_errors(lifecycle)
    for message in lifecycle_problems:
        add(errors, LIFECYCLE_PATH, "patch_lifecycle_invalid", message)
    if reason_problems:
        reasons = []
    if lifecycle_problems:
        lifecycle = []
    records = [(path, front_matter(path)) for path in files]
    entries = [(path, data) for path, data in records if data.get("update_entry") is True]
    fronts = [data for _path, data in entries]
    groups = counted_evidence_rows(load_evidence_rows(),
                                   windows_targets=windows_targets_from_front_matter(fronts))
    # The reasons decide reads -- reviewed entries, plus the reason producer's candidates only while its
    # (temporary, owner-gated) activation switch is on: the same function the projection builder uses.
    valid, unsupported = verdict_projection.supported_reasons(fronts, groups, reasons)
    expected, _unsupported = verdict_projection.project(fronts, groups, reasons, lifecycle)
    want_rows = expected["pages"]

    # What the gate will READ. Absent: the deploy builds it from this tree, i.e. the authority's rows.
    try:
        disk = verdict_projection.load(PROJECTION_PATH)
    except verdict_projection.ProjectionError as exc:
        add(errors, PROJECTION_PATH, "verdict_projection_invalid",
            f"{exc}. The verdict gate cannot read it, so every page the authority gives a verdict "
            "would render INSUFFICIENT DATA.")
        disk = {"schema_version": verdict_projection.SCHEMA_VERSION, "pages": {}}
    if disk is not None and disk.get("error"):
        add(errors, PROJECTION_PATH, "verdict_projection_failed",
            f"the verdict projection builder could not decide ({disk.get('error')}); pages render "
            "INSUFFICIENT DATA where the authority gives a verdict.")
    rows = want_rows if disk is None else dict(disk.get("pages") or {})
    source = "the deploy's verdict projection" if disk is not None else "this tree's verdict projection"

    record_keys = set()
    for path, data in entries:
        key = verdict_projection.page_key(data)
        record_keys.add(key)
        release_problem = patch_decision.release_type_problem(data)
        if release_problem:
            add(warnings, path, "windows_update_type_malformed",
                f"{release_problem}. lib/patch_decision.decide cannot read Microsoft's classification from "
                "it, so this page renders no SECURITY UPDATE; correct the stored value.")
        for padding in verdict_reasons.identity_padding_problems(data):
            add(warnings, path, "record_identity_unicode_padding",
                f"{padding}. The page key keeps it, so this page matches none of its reason entries or "
                "counted reports and can lose its verdict silently; correct the stored value.")
        want = patch_decision.decide(data, valid_reasons=valid.get(verdict_reasons.record_identity(data), []),
                                     lifecycle=lifecycle)
        got_verdict, got_scope = verdict_projection.rendered_verdict(data, rows, lifecycle)
        got_row, want_row = rows.get(key), want_rows.get(key)
        if (got_verdict, got_scope) != (want.verdict, want.scope):
            add(errors, path, "verdict_render_disagrees",
                f"the page renders {verdict_projection.phrase(got_verdict, got_scope)!r} from {source}, "
                f"but lib/patch_decision.decide gives {patch_decision.verdict_phrase(want)!r} for this tree.")
        elif got_row != want_row:
            differs = sorted(k for k in verdict_projection.ROW_KEYS
                             if (got_row or {}).get(k) != (want_row or {}).get(k))
            add(errors, path, "verdict_render_disagrees",
                f"{source} differs from lib/patch_decision.decide in {differs}; the page would print "
                "a line, panel or recommendation the authority did not write.")
    for key in sorted(set(rows) - record_keys):
        add(errors, PROJECTION_PATH, "verdict_render_disagrees",
            f"{source} holds a row for {key!r}, which no record carries and the authority did not decide.")

    pages_by_identity: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for data in fronts:
        pages_by_identity.setdefault(verdict_reasons.record_identity(data), []).append(data)
    entry_identity = {str(e.get("id") or ""): verdict_reasons.reason_identity(e) for e in reasons}
    for reason_id, problems in sorted(unsupported.items()):
        pages = pages_by_identity.get(entry_identity.get(reason_id, ("", "", "")), [])
        if pages:
            shown = sorted({verdict_projection.phrase(*verdict_projection.rendered_verdict(d, rows, lifecycle))
                            for d in pages})
            renders = f"The page no longer rests on it and renders {' / '.join(repr(s) for s in shown)}"
        else:
            renders = "No record carries this page identity, so it supports nothing"
        add(warnings, REASONS_PATH, "verdict_reason_unsupported",
            f"{reason_id}: {'; '.join(problems)}. {renders}; re-read the entry and correct or remove it.")
    for entry in lifecycle:
        if not any(patch_decision.lifecycle_for(data, [entry]) for data in fronts):
            add(warnings, LIFECYCLE_PATH, "patch_lifecycle_unmatched",
                f"{entry.get('id')}: no record carries this KB and build.")
    for path, data in entries:
        if int(data.get("update_report_count") or 0) <= 0:
            continue
        decision = patch_decision.decide(
            data, valid_reasons=valid.get(verdict_reasons.record_identity(data), []), lifecycle=lifecycle)
        expected_phrase = patch_decision.verdict_phrase(decision)
        stored = (patch_decision.action_of(data.get("update_decision_label"))
                  or patch_decision.action_of(patch_decision.leading_decision(data.get("update_consensus_summary"))))
        summary = str(data.get("update_consensus_summary") or "")
        stored_lead = summary.split(":", 1)[0].strip() if patch_decision.leading_decision(summary) else ""
        count = int(data.get("update_report_count") or 0)
        identity = (f"{str(data.get('update_product') or data.get('product_id') or '').strip()} "
                    f"{patch_display_label(data.get('update_version'), data.get('target_build'), data.get('product_id'))}")
        expected_summary = patch_decision.summary_line(decision, data, count, identity=identity)
        if (stored and stored != decision.verdict) or (stored_lead and stored_lead != expected_phrase):
            add(warnings, path, "verdict_policy_drift",
                f"stored verdict {stored!r} (summary opens {stored_lead or '(none)'!r}) but the verdict "
                f"policy decides {expected_phrase!r}; every surface renders {expected_phrase!r}. "
                + DRIFT_CATCH_UP)
        elif summary and summary != expected_summary:
            add(warnings, path, "verdict_policy_drift",
                "the stored summary is not the policy's line (lib/patch_decision.summary_line); the feed "
                f"card still leads with {expected_phrase!r} and the page's own line (it prints stored text "
                "only where it matches them). " + DRIFT_CATCH_UP)
    return errors, warnings


def scan_lifecycle_builds(files: list[Path]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """PR-A2 review, LOW-3 (probe P4): every OS build a lifecycle entry lists is carried by a record.

    `patch_lifecycle_unmatched` (scan_verdict_policy) fires only when an entry matches NO page, so an
    entry whose second build was mistyped -- or followed by an invisible character -- still matched
    the first page and the withdrawal vanished from the second without a word. Checked per build;
    a publication error (`patch_lifecycle_build_unmatched`, promoted by --publish-strict). Its own
    scan because it is corpus-wide: a one-record QA fixture carries only one of the two builds."""
    warnings: list[dict[str, str]] = []
    try:
        lifecycle = verdict_reasons.load_lifecycle(LIFECYCLE_PATH)
    except verdict_reasons.FactFileError:
        return [], []  # scan_verdict_policy reports the malformed file (patch_lifecycle_invalid)
    if verdict_reasons.lifecycle_errors(lifecycle):
        return [], []  # refused: it supports nothing, and scan_verdict_policy errors on it
    fronts = [data for data in (front_matter(path) for path in files) if data.get("update_entry") is True]
    for entry in lifecycle:
        for build in entry.get("builds") or []:
            if not any(patch_decision.lifecycle_for(data, [dict(entry, builds=[build])]) for data in fronts):
                add(warnings, LIFECYCLE_PATH, "patch_lifecycle_build_unmatched",
                    f"{entry.get('id')}: no record carries {entry.get('kb')} with OS build {build!r}, so the "
                    "withdrawal applies to no page for that build; correct the build or the record.")
    return [], warnings


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

    if evidence_state == "official_only" and report_count > 0:
        add(errors, path, "official_only_with_reports", "Record has report_count > 0 but evidence_state is official_only.")
    # The `consensus_live` precondition is NOT checked here. It needs the authoritative counted
    # evidence population, which is record-relative (the Windows gate depends on which cumulative
    # update a record currently targets), so it cannot be decided from one record's front matter.
    # It lives in `scan_live_consensus_claims`, which runs with that authority in hand.
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

    # The HEADLINE is a count projection too, on any product whose coherence branch writes a
    # number into it (obs-studio does: "has N user reports found"). Checked separately from the
    # source list because the two fail apart: at a canonical zero the source list is RETRACTED,
    # so the mismatch check below goes quiet by construction while the verdict can still be
    # publishing a stale number. This check has no such blind spot, and it would have caught the
    # original obs 32.2.2 defect at the most-read field rather than at the source list.
    # Matched on content, so a hand-written verdict naming no number is never flagged.
    verdict = str(data.get("quick_verdict") or "")
    stated = re.search(r"(\d+)\s+user report", verdict)
    if stated:
        claimed_total = int(data.get("update_report_count")
                            or data.get("confirmed_patch_specific_report_count") or 0)
        if int(stated.group(1)) != claimed_total:
            add(warnings, path, "quick_verdict_count_mismatch",
                f"Headline verdict states {stated.group(1)} user reports but the record's "
                f"count is {claimed_total}; both must state the same counted population.")

    if report_count > 0:
        if is_blank(data.get("update_consensus_summary")):
            add(errors, path, "report_count_without_consensus_summary", "Record has report_count > 0 but no update_consensus_summary.")
        if not isinstance(data.get("evidence_samples"), list) or len(data.get("evidence_samples") or []) == 0:
            add(errors, path, "report_count_without_evidence_samples", "Record has report_count > 0 but no representative evidence_samples.")
        if not isinstance(data.get("accepted_report_sources"), list) or len(data.get("accepted_report_sources") or []) == 0:
            add(warnings, path, "report_count_without_accepted_report_sources", "Record has report_count > 0 but no collapsed full accepted source list.")
        if isinstance(data.get("evidence_samples"), list) and len(data.get("evidence_samples") or []) > 5:
            add(errors, path, "too_many_representative_samples", "evidence_samples should contain no more than five representative items; put the full list in accepted_report_sources.")

        # ONE ACTION PER RECORD. The writer can no longer produce two, but until now nothing looked
        # at what was already ON DISK -- which is why `2026-04-14-davinci-resolve-21-public-beta-1`
        # published "WAIT for production systems" as its verdict beside "AVOID for production" as
        # its summary, the first reader-visible on the patch page and the second on the feed, and
        # no check anywhere failed. Ten records corpus-wide carried more than one phrase.
        #
        # Compares ACTIONS, not phrasings: "WAIT" and "WAIT for production systems" are one
        # instruction in two registers, and reporting those would bury the real conflicts.
        #
        # A WARNING, deliberately. This scanner runs in the scheduled lane AFTER the promotions and
        # BEFORE the writeback, and `main` exits non-zero only on errors. An error here would wedge
        # the lane and discard every product's evidence for that cycle whenever a promotion was
        # skipped -- the failure mode that killed three runs in August. A warning surfaces the drift
        # without holding the evidence hostage.
        actions = {
            patch_decision.action_of(data.get("update_decision_label")),
            patch_decision.action_of(patch_decision.leading_decision(data.get("quick_verdict"))),
            patch_decision.action_of(
                patch_decision.leading_decision(data.get("update_consensus_summary"))),
        }
        # A STORED label must be a verdict the authority recognises. Without this the vocabulary
        # is only enforced at render time, by the two template fail-safes -- so a record could sit
        # in the corpus naming a decision nothing classified, and the site would quietly publish
        # INSUFFICIENT DATA for it instead of saying the record is wrong. `is_canonical` existed
        # after AUX-029's first pass with no production caller at all; this is that caller.
        stored = str(data.get("update_decision_label") or "").strip()
        if stored and patch_decision.action_of(stored) not in patch_decision.CANONICAL_DECISIONS:
            add(warnings, path, "record_names_unknown_verdict",
                f"update_decision_label {stored!r} is not a canonical verdict and is not a "
                "recognised legacy phrasing. One patch publishes one decision, from the eight in "
                "lib/patch_decision.RISK_ORDER; an unvetted label is not a decision.")

        actions.discard("")
        if len(actions) > 1:
            add(warnings, path, "record_names_conflicting_actions",
                "Record names more than one action ("
                + ", ".join(sorted(actions))
                + f"): verdict {str(data.get('update_decision_label') or '(none)')!r}, summary "
                f"opens {patch_decision.leading_decision(data.get('update_consensus_summary')) or '(none)'!r}. "
                "One patch publishes one decision; supporting prose may qualify it, not replace it.")

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
    collection_status = str(data.get("consensus_collection_status") or "").strip()
    if collection_status and collection_status not in maturity.VALID_COLLECTION_STATUSES:
        add(warnings, path, "unknown_consensus_collection_status",
            f"Consensus collection status '{collection_status}' is not recognized.")
    state_label = str(data.get("evidence_state_label") or "").strip()
    if state_label and state_label not in maturity.VALID_EVIDENCE_STATE_LABELS:
        add(warnings, path, "unknown_evidence_state_label",
            f"Evidence state label '{state_label}' is not recognized.")
    # THE FOUR AXES MUST AGREE. Each surface reads a different one, so a record whose axes disagree
    # shows readers different maturities on different pages -- and the homepage prints the stage
    # beside the label. Live claims are validated as ERRORS by `scan_live_consensus_claims` (with
    # the evidence in hand); this is the non-live half, a WARNING on purpose: it compares against
    # the record's own stored count, and an in-lane error here would discard a whole cycle's evidence
    # over a presentation field. Reconciliation writes all four axes, so it converges on its own.
    if not maturity.claims_live(data):
        differing = maturity.contradictions(data, report_count)
        if differing:
            # Clamped like `contradictions`: a malformed negative count must produce this warning,
            # not an exception that aborts QA in every lane.
            expected = maturity.maturity_for(max(report_count, 0)).axes()
            add(warnings, path, "maturity_axes_inconsistent",
                f"Maturity axes disagree with the {report_count}-report record: "
                + ", ".join(f"{axis}={data.get(axis)!r} (expected {expected[axis]!r})"
                            for axis in differing) + ".")

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
    for include in UPDATE_LAYOUT_INCLUDES:
        if not include.exists():
            add(errors, include, "missing_update_layout_include", f"{include.name}, rendered by aux-update.html, is missing.")
            continue
        text += "\n" + include.read_text(encoding="utf-8")
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
        "Newest accepted report captured",
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
    # The job here is that a page with no counted reports must not be given a sentiment chart. It
    # used to be enforced by requiring a NEUTRAL variant of the chart; Wave A satisfies the same
    # requirement more strongly by rendering no scale at all below one report, so requiring the
    # neutral class would now forbid the better treatment. What is checked instead is the property:
    # the three-zone scale must be gated on the report count, and the zero-report page must still
    # make the not-established statement in words.
    if "consensus-scale-labels" in text and "{% if report_count > 0 %}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "sentiment_scale_not_gated_on_reports",
            "The three-zone sentiment scale must render only where counted reports exist.")
    if "Community consensus not established" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "sentiment_neutral_state_missing",
            "A page without established consensus must say so in words, chart or no chart.")
    if "update_platform_clean" in text or "platform_label_clean" in text or "update_type_clean" in text:
        add(errors, UPDATE_LAYOUT_PATH, "top_metadata_placeholder_pill_regression", "Top metadata should render only data-bearing product, version, channel, release date, and file-size pills.")
    # This demanded the literal spelling `!= blank`, which in this stack does not gate at all:
    # Liquid 4 resolves `blank` through a MethodLiteral that sends :blank? to the value, :blank?
    # is ActiveSupport's, and Jekyll does not load ActiveSupport -- so the comparison was ALWAYS
    # true and the pill rendered its label over an empty value on 1,274 records. The check was
    # therefore enforcing the very defect its message describes. AUX-030 repaired the guard to
    # compare the stripped value against '', which is what "a stripped real value exists" means.
    # The old spelling is now rejected rather than required.
    if "file_size_pill_value" not in text or "{% if file_size_pill_value != '' %}" not in text:
        add(errors, UPDATE_LAYOUT_PATH, "file_size_pill_value_guard_missing", "The top file-size pill must render only when a stripped real value exists.")
    if "file_size_pill_value != blank" in text:
        add(errors, UPDATE_LAYOUT_PATH, "file_size_pill_value_guard_inert", "The file-size pill guard uses `!= blank`, which never gates in this stack; compare the stripped value against ''.")
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


#: The accepted-report volume a live consensus claim must have behind it -- the High rung of the
#: published strength ladder. Owned by lib.maturity; re-exported under the name callers already use.
LIVE_MIN_ACCEPTED_REPORTS = maturity.LIVE_MIN_ACCEPTED_REPORTS

LIVE_EVIDENCE_STATE = maturity.CONSENSUS_LIVE.evidence_state
#: `live_consensus` is the legacy word order, accepted on READ only because aux-update.html:89 tests
#: both. Nothing writes it.
LIVE_COLLECTION_STATUSES = maturity.LIVE_COLLECTION_STATUSES


def scan_live_consensus_claims(
        loaded: list[tuple[Path, dict[str, Any]]],
        evidence_counts: dict[tuple[str, str, str], int],
        accepted_urls: dict[tuple[str, str, str], set[str]] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Every record claiming mature consensus, checked against the AUTHORITATIVE population.

    This replaces a precondition that could never be met. The old gate demanded front-matter
    `consensus_evidence` / `structured_evidence` / `evidence_objects`; 0 of 1316 records carry any
    of them, no template reads them, and all three are absent from the consensus writer's
    `WRITEABLE_FIELDS` allow-list -- so the one sanctioned way to satisfy it raised
    `RuntimeError: Refusing to write unapproved field`.

    WHY THE AUTHORITY AND NOT THE RECORD. `accepted_report_sources` once carried
    `patch_version_matched: True` as a hardcoded literal; AUX-043 made the writer earn it from the
    row, but a projection is still the writer's own account of itself, and believing it would make
    this check only as strong as the writer it exists to audit. Patch-matching is therefore
    established upstream, by
    `lib.report_counts.counted_evidence_counts` applying the real per-row predicate
    (`counted is not False` AND `patch_version_matched is True` AND, for Windows, the record-relative
    current-patch gate) to the canonical evidence rows at this exact product/version/build identity.
    Nothing below reads the projection's own matched flag.

    FAIL CLOSED, and as ERRORS. The sibling length check in `scan_evidence_count_alignment` is
    deliberately a WARNING because it fires in the legitimate window between reconciliation writing
    a count and promotion rebuilding the projection. That tolerance is right for a pilot record
    mid-cycle and wrong for a published claim of mature consensus: a live claim the evidence does
    not support must not reach a reader, so here an unsupported claim blocks.

    THE PAIR IS CHECKED TOGETHER because one field is enough to make a claim.
    Every surface reads maturity through `_includes/maturity-state.html`, which treats a live word in
    EITHER `evidence_state` or `consensus_collection_status` as a live claim. So a record live in one
    field and pilot in the other publishes a claim the other field denies, and that is not visible
    from either field alone.

    EXCLUSIVITY. A live claim also needs at least the High rung of accepted report URLs that no other
    identity's accepted population contains -- the condition `live_eligibility.evaluate` promotes on.
    A thread counted for two versions is evidence about neither in particular. Judged from
    `accepted_urls` (every identity, every product); no clock is read here, so monitoring freshness
    stays the certifier's and the deploy projection's to judge.
    """
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    # How many identities' accepted populations hold each URL -- once, over the whole population.
    url_owners: dict[str, int] = {}
    for urls in (accepted_urls or {}).values():
        for url in urls:
            if url:
                url_owners[url] = url_owners.get(url, 0) + 1
    for path, data in loaded:
        state_live = str(data.get("evidence_state") or "").strip() == LIVE_EVIDENCE_STATE
        status_live = (str(data.get("consensus_collection_status") or "").strip()
                       in LIVE_COLLECTION_STATUSES)
        if not (state_live or status_live or maturity.claims_live(data)):
            continue

        # ALL FOUR AXES, not just the pair. Each surface reads a different axis -- the patch page
        # the collection status, the feed and My Patch Stack the evidence state, the homepage the
        # label beside the intelligence stage -- so a claim on any one reaches a reader, and a
        # pair-only promotion rendered "Live consensus · Early reports" on the homepage while
        # passing every check here. A live claim must be the exact canonical live tuple, in the
        # canonical spelling (the legacy `live_consensus` word is read, never accepted as a claim).
        differing = [axis for axis in maturity.AXES
                     if maturity.stored_axes(data)[axis] != maturity.CONSENSUS_LIVE.axes()[axis]]
        if differing:
            add(errors, path, "maturity_live_axes_inconsistent",
                f"Record claims live consensus on at least one maturity axis but these axes are "
                f"not the canonical live value: {', '.join(differing)}; a live claim must set "
                f"{maturity.CONSENSUS_LIVE.axes()} together.")

        if state_live != status_live:
            add(errors, path, "live_state_pair_inconsistent",
                f"Record claims live consensus in one field but not the other "
                f"(evidence_state={data.get('evidence_state')!r}, "
                f"consensus_collection_status={data.get('consensus_collection_status')!r}); "
                "every surface reads a live word in either field as a live claim, so a half-claim "
                "publishes a maturity claim the other field denies.")

        product_id = str(data.get("product_id") or "").strip()
        version = str(data.get("update_version") or "").strip()
        if not product_id or not version:
            add(errors, path, "live_without_canonical_identity",
                "Record claims live consensus but carries no product_id/update_version, so no "
                "accepted-evidence population can be attributed to it.")
            continue

        authoritative = int(evidence_counts.get(patch_key(product_id, version,
                                                          data.get("target_build"))) or 0)
        if authoritative < LIVE_MIN_ACCEPTED_REPORTS:
            add(errors, path, "live_without_sufficient_accepted_evidence",
                f"Record claims live consensus with {authoritative} accepted patch-specific "
                f"reports in the authoritative population; {LIVE_MIN_ACCEPTED_REPORTS} is the "
                "published High evidence-strength rung.")
        if accepted_urls is not None:
            own_urls = accepted_urls.get(patch_key(product_id, version, data.get("target_build")), set())
            exclusive = sum(1 for url in own_urls if url and url_owners.get(url) == 1)
            # A WARNING, not an error. Exclusivity is a property of the WHOLE population, so a
            # scoped lane (the PowerPoint graph, the DaVinci dispatch) can lower another product's
            # count without revisiting -- and without being allowed to write -- that product's
            # record. As an error, that blocked the scoped lane every cycle: only the unscoped lane
            # can revoke the claim, and it never saw the rows. The claim still cannot publish: the
            # deploy-time projection re-runs the same evaluation and renders it Verified reports,
            # and the next unscoped reconcile revokes the stored claim.
            if exclusive < LIVE_MIN_ACCEPTED_REPORTS:
                add(warnings, path, "live_exclusive_below_high_rung",
                    f"Record claims live consensus but only {exclusive} of its accepted report URLs "
                    f"are counted on no other patch identity; {LIVE_MIN_ACCEPTED_REPORTS} is the "
                    "published High evidence-strength rung, and a report counted for several "
                    "patches cannot carry a claim of mature consensus about one of them.")

        claimed = int(data.get("update_report_count")
                      or data.get("confirmed_patch_specific_report_count") or 0)
        if claimed != authoritative:
            add(errors, path, "live_count_disagrees_with_evidence",
                f"Record claims live consensus and publishes {claimed} user reports, but the "
                f"authoritative accepted-evidence population for this exact patch identity is "
                f"{authoritative}.")

        sources = data.get("accepted_report_sources")
        if not isinstance(sources, list) or not sources:
            add(errors, path, "live_without_accepted_report_sources",
                "Record claims live consensus but publishes no accepted report sources, so a "
                "reader cannot reach the evidence the claim rests on.")
            continue
        if not all(isinstance(item, dict) for item in sources):
            add(errors, path, "live_sources_malformed",
                "Record claims live consensus but accepted_report_sources contains a non-mapping "
                "entry.")
            continue

        if len(sources) != authoritative:
            add(errors, path, "live_sources_not_exhaustive",
                f"Record claims live consensus and lists {len(sources)} accepted report sources "
                f"against an authoritative population of {authoritative}; this list is the "
                "exhaustive projection, not a sample, so the two must agree exactly.")

        urls = [str(item.get("source_url") or item.get("url") or "").strip() for item in sources]
        if any(not url.lower().startswith(("http://", "https://")) for url in urls):
            add(errors, path, "live_source_without_valid_url",
                "Record claims live consensus but at least one accepted report source carries no "
                "usable http(s) URL, so that report cannot be verified by a reader.")
        normalized = {normalize_url(url) for url in urls if url}
        distinct_reports = {report_url_key(url) for url in urls if url}
        if len(distinct_reports) != len(sources):
            add(errors, path, "live_sources_not_distinct",
                f"Record claims live consensus from {len(sources)} sources that resolve to "
                f"{len(distinct_reports)} distinct reports; repeated discoveries or cross-posts of one "
                "report are not independent corroboration.")

        # THE CONTENTS, not just the shape. Every check above compares the projection's SIZE to the
        # authoritative population; none of them looks at WHICH reports it names. A projection of
        # the right cardinality carrying one fabricated or superseded citation passes all of them:
        # 34 accepted rows, a list of 33 real ones plus one invention, count 34 against authority
        # 34, all distinct, all valid. That is the same failure as the precondition this gate
        # replaced -- a check that appears to validate evidence while never comparing against the
        # thing that decides.
        if accepted_urls is not None:
            population = accepted_urls.get(
                patch_key(product_id, version, data.get("target_build")), set())
            unsupported = sorted(normalized - population)
            omitted = sorted(population - normalized)
            if unsupported:
                add(errors, path, "live_source_not_in_accepted_population",
                    f"Record claims live consensus citing {len(unsupported)} report(s) that are "
                    f"not in the authoritative accepted-evidence population for this patch "
                    f"identity, e.g. {unsupported[0]}; a citation the evidence does not support "
                    "cannot help establish consensus.")
            # EXACT CORRESPONDENCE, not containment. With the length and distinctness checks above
            # this is implied -- a set of N distinct citations drawn from an N-report population IS
            # that population -- but a property that holds only as a consequence of three other
            # checks is one refactor away from not holding, and nothing in the code would say so.
            # Stated directly, it also names what a maintainer must fix: a substitution reports the
            # invented citation AND the real report it displaced, where a length mismatch reports
            # neither.
            if omitted:
                add(errors, path, "live_accepted_report_omitted",
                    f"Record claims live consensus but omits {len(omitted)} accepted report(s) "
                    f"from its published citations, e.g. {omitted[0]}; the published list is the "
                    "exhaustive projection of the accepted population, so an omission means the "
                    "page is citing a different set of reports than the one it counted.")

    return errors, warnings


# Vendors that publish one version's notes PER PLATFORM. Their records say whose notes they hold
# (`official_notes_platform`), but no community-counting path compares a report's platform with it
# yet, so a report about one OS could be counted toward another OS's notes. Until a platform-aware
# acceptance rule exists, these companies may not publish community reports or consensus at all.
# Company-wide on purpose: an UNLABELLED version of the same product is no safer.
PLATFORM_UNGATED_COMPANIES = frozenset({"elgato"})


def scan_platform_scoped_consensus(
        loaded: list[tuple[Path, dict[str, Any]]],
        evidence_counts: dict[tuple[str, str, str], int],
) -> list[dict[str, str]]:
    """Block community reports and consensus for per-platform-notes vendors, record AND evidence.

    Both halves, because either alone can be bypassed: the record's own fields could still read
    official-only while counted rows accumulate in the evidence store (the authority), and the
    store could be empty while a record was hand-promoted. Errors, so the publish path and every
    writeback lane's validate-before-commit refuse rather than publish.
    """
    errors: list[dict[str, str]] = []
    reason = ("publishes per-platform release notes and no platform-aware acceptance rule exists, so "
              "a report about one OS could be counted toward another OS's notes. Add platform-aware "
              "acceptance before enabling community counting for this company (AUX-049).")
    company_of: dict[str, str] = {}
    for path, data in loaded:
        company = str(data.get("company_id") or "").strip()
        company_of[str(data.get("product_id") or "").strip()] = company
        if company not in PLATFORM_UNGATED_COMPANIES:
            continue
        claimed = max(int(data.get("update_report_count") or 0),
                      int(data.get("confirmed_patch_specific_report_count") or 0))
        state = str(data.get("evidence_state") or "").strip()
        # The patch page keys its report hero on the COLLECTION STATUS and falls back to
        # evidence_samples for its citations, so each is a claim in its own right: a zero-count,
        # official-only record could still show "Verified reports" or community sources.
        status = str(data.get("consensus_collection_status") or "").strip()
        if (claimed > 0 or state not in ("", "official_only")
                or status not in ("", "deferred_official_only")
                or data.get("accepted_report_sources") or data.get("evidence_samples")):
            add(errors, path, "platform_scoped_report_claimed",
                f"Record claims community reports or consensus (reports={claimed}, "
                f"evidence_state={state!r}, consensus_collection_status={status!r}), "
                f"but {company} {reason}")
    for (product_id, version, build), count in sorted(evidence_counts.items()):
        company = company_of.get(product_id) or product_id.split("-", 1)[0]
        if count > 0 and company in PLATFORM_UNGATED_COMPANIES:
            add(errors, f"{product_id} {version} {build}".strip(), "platform_scoped_evidence_counted",
                f"{count} counted evidence row(s) exist for this patch, but {company} {reason}")
    return errors


def scan_unconfigured_platform_split(files: list[Path]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Surface a product whose records hold ONE platform's notes but which is not flagged as such.

    My Patch Stack compares per platform only for products flagged `official_notes_by_platform` in the
    catalogue -- a label appearing on an unflagged product deliberately changes no comparison. So the
    label is reported here instead, as a WARNING: the product's update advice may cross platforms
    until someone decides whether to flag it. `windows_macos` alone does not indicate per-platform
    notes, so it is not reported.
    """
    flagged = {str(p.get("id") or p.get("product_id") or ""): bool(p.get("official_notes_by_platform"))
               for p in (load_yaml(PRODUCTS_PATH, []) or []) if isinstance(p, dict)}
    seen: dict[str, Path] = {}
    for path in files:
        data = front_matter(path)
        product_id = str(data.get("product_id") or "").strip()
        if str(data.get("official_notes_platform") or "") in ("windows", "macos") and not flagged.get(product_id):
            seen.setdefault(product_id, path)
    warnings: list[dict[str, str]] = []
    for product_id, path in sorted(seen.items()):
        add(warnings, path, "platform_split_product_unconfigured",
            f"{product_id} has records holding one platform's release notes but is not flagged "
            "official_notes_by_platform, so My Patch Stack may still compare across platforms for it "
            "(AUX-050). Flag it in patch_products.yml if its vendor publishes notes per platform.")
    return [], warnings


#: The vocabularies the consensus writer projects a counted row through. A counted row outside them
#: is refused by its `gate_11` / `gate_17` rather than silently dropped from the count.
COUNTED_ROW_SENTIMENTS = frozenset({"positive", "moderate", "negative"})
COUNTED_ROW_SEVERITIES = frozenset({"low", "medium", "high", "critical"})


def scan_counted_row_classification(rows: list[Any]) -> list[dict[str, str]]:
    """Counted rows the consensus writer cannot project: no source URL, or a sentiment or severity
    outside its vocabulary.

    Such a row still COUNTS -- reconciliation publishes the authoritative number -- but the writer
    now refuses that identity's projection write (gate_11 / gate_17) instead of quietly publishing a
    smaller count, so the record's sources and prose stop refreshing until the row is fixed. This
    names the row. A WARNING: the write refusal already prevents a wrong publication, and an error
    here would discard every product's evidence for the cycle over one malformed row."""
    warnings: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict) or not row_is_counted(row):
            continue
        problems = []
        if not str(row.get("source_url") or "").strip():
            problems.append("no source_url")
        if str(row.get("sentiment") or "").strip().lower() not in COUNTED_ROW_SENTIMENTS:
            problems.append(f"sentiment {row.get('sentiment')!r}")
        if (str(row.get("severity") or "").strip().lower() or "low") not in COUNTED_ROW_SEVERITIES:
            problems.append(f"severity {row.get('severity')!r}")
        if problems:
            label = f"{row.get('product_id')} {row.get('update_version')} {row.get('id') or row.get('source_url')}"
            add(warnings, Path(str(EVIDENCE_PATH)), "counted_row_unclassified",
                f"Counted evidence row {label} cannot be projected ({'; '.join(problems)}); the "
                "consensus writer will refuse this patch's write until it is classified.")
    return warnings


def scan_evidence_count_alignment(files: list[Path]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    # Read each record ONCE and reuse it for both the target map and the comparison below.
    loaded = [(path, front_matter(path)) for path in files]
    evidence_counts = load_counted_evidence_counts([data for _p, data in loaded])
    # Live claims are validated against the SAME authority, from the same single read of the
    # evidence store. Deliberately before the empty-map early return below: if the store is
    # unreadable or empty, every live claim is unsupported and must say so rather than be waved
    # through -- a missing evidence store is the one condition under which this gate matters most.
    live_errors, live_warnings = scan_live_consensus_claims(
        loaded, evidence_counts,
        load_counted_accepted_urls([data for _p, data in loaded]))
    errors.extend(live_errors)
    warnings.extend(live_warnings)
    errors.extend(scan_platform_scoped_consensus(loaded, evidence_counts))
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
                # WARNING, not an error, and deliberately so: this fires during the normal lane,
                # in the window between reconciliation writing the count and the scoped promotion
                # rebuilding the projection. Blocking there would fail the run that is on its way to
                # fixing the very thing being flagged. It also fires in `patch-ingest.yml`, which
                # runs QA with no reconcile or promotion step at all and so can never clear it.
                #
                # It found obs-studio 32.2.2 (count 7, sources 3), which is now repaired by that
                # product's own promotion step. Note the blind spot this check has and the headline
                # check above does not: it is guarded on a NON-EMPTY source list, and at a canonical
                # zero the list is retracted, so it goes quiet exactly when a stale verdict could
                # still be publishing a number.
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


# Codes that are a WARNING for the evidence/writeback lane and an ERROR for publication.
#
# The split is deliberate rather than an oversight. The writeback lane must not throw away a whole
# collection run because one stale record names two actions -- the evidence is good, the record is
# old, and discarding real evidence to punish old prose is the worse failure. But Pages publishes
# that record to readers, and a page naming two decisions has no verdict at all.
#
# Same check, two consequences, selected by an EXPLICIT flag. Not by sniffing CI environment
# variables: an implicit rule is one nobody can exercise from a command line, which is how a
# publication gate quietly stops gating.
PUBLICATION_BLOCKING_CODES = frozenset({"record_names_conflicting_actions",
                                        "record_names_unknown_verdict",
                                        # GROWTH-3 review 2 (LOW-1): a release type decide cannot read.
                                        "windows_update_type_malformed",
                                        # PR-A2 review (LOW-1 / LOW-3): an identity Liquid and Python
                                        # strip differently; a lifecycle build no page carries.
                                        "record_identity_unicode_padding",
                                        "patch_lifecycle_build_unmatched"})


def promote_for_publication(
    errors: list[dict[str, str]], warnings: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Move publication-blocking warnings into the error list.

    Only codes named in PUBLICATION_BLOCKING_CODES move. Every other warning keeps its severity,
    so turning on publication mode cannot silently promote an unrelated advisory into a deploy
    blocker.
    """
    kept: list[dict[str, str]] = []
    promoted: list[dict[str, str]] = []
    for item in warnings:
        if str(item.get("code") or "") in PUBLICATION_BLOCKING_CODES:
            promoted.append(item)
        else:
            kept.append(item)
    return errors + promoted, kept


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish-strict", action="store_true",
        help="Publication mode: treat a record that names more than one action as an ERROR and "
             "exit non-zero, so the site cannot deploy a patch page with two decisions. The "
             "writeback lane runs WITHOUT this flag, where the same finding stays a warning.")
    parser.add_argument(
        "--read-only", action="store_true",
        help="Run every check and report normally, but write nothing. This exists so PR-time CI "
             "can execute THIS implementation rather than a copy of it: the suite was excluded "
             "from ci-integrity solely because the run wrote _data/qa_status.json, and a "
             "re-implementation validated in CI while production ran different code is the "
             "two-authorities defect these gates exist to prevent. The flag suppresses the two "
             "write statements below and NOTHING else -- every scan, the publish-strict "
             "promotion and the exit code are the production codepath, unchanged.")
    args = parser.parse_args(argv)

    if not args.read_only:
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
    warnings.extend(scan_counted_row_classification(load_evidence_rows()))
    e, w = scan_verdict_policy(files)
    errors.extend(e)
    warnings.extend(w)
    e, w = scan_lifecycle_builds(files)
    errors.extend(e)
    warnings.extend(w)
    e, w = scan_unconfigured_platform_split(files)
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

    if args.publish_strict:
        errors, warnings = promote_for_publication(errors, warnings)

    status = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "publish-strict" if args.publish_strict else "blocking",
        "records_scanned": len(files),
        "priority_products_checked": len(PRIORITY_PRODUCTS),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if not args.read_only:
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
