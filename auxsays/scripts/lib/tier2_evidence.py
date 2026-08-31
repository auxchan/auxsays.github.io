#!/usr/bin/env python3
"""TIER 2 -- update-linked reports: real community intelligence, deliberately outside consensus.

TWO TIERS, ONE CORPUS. Tier 1 is the unchanged strict class: exact product, exact build, valid date,
concrete problem, attributed author, correct build role, no duplicate. It alone drives report
counts, percentages, verdicts and labels. Tier 2 is everything that is demonstrably a real user
report about a PowerPoint update but whose exact build was never stated -- 94% of the live corpus.
Those were being discarded from public view, which is why a page could read "0 reports" after 806
threads were examined.

ISOLATION IS STRUCTURAL, NOT POLICY. Tier 2 is written to its OWN data file. Nine scripts read
consensus_evidence.yml; none of them read this one. A Tier-2 row therefore cannot reach a consensus
count by any code path, including ones written later by someone who has never heard of tiers -- the
guarantee does not depend on a predicate being remembered.

ASSOCIATION IS TO A RELEASE WINDOW, NEVER TO A BUILD. A report is attached to the build whose
release window CONTAINS the report date, which is not the same as the newest build. An August 20
complaint belongs to the window open on August 20; it cannot become evidence about a build that
shipped on August 26. When the reporter names a version or build family, that has to agree as well.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from .update_linkage import LinkageOutcome, classify_update_linkage

TIER_CONFIRMED = "confirmed_patch_specific"
TIER_UPDATE_LINKED = "update_linked"
TIER_UNRESOLVED = "unresolved"

# A Tier-2 row is only ever built from a candidate the strict authority refused for a reason that
# means "identity not established" -- never for a reason that means "this is not a user report about
# this product". Promoting a wrong-product or announcement row would launder a rejection into
# visibility, which is the whole thing this class must not become.
PROMOTABLE_REJECTIONS = frozenset({
    "missing_powerpoint_version",
    "missing_exact_build",
    "ambiguous_version_needs_build",
    "bare_version_no_context",
    # The strict authority's own name for "the reporter says LATEST UPDATE and nothing more".
    # That is precisely an update-linked report: strong attribution, no identity.
    "vague_latest_update",
})

# Reasons that must NEVER become Tier 2, listed explicitly so the refusal is auditable rather than
# implied by omission.
NEVER_PROMOTE = frozenset({
    "product_not_powerpoint",
    "official_announcement_not_user_report",
    "not_a_concrete_powerpoint_issue",
    "date_before_release_or_undated",
    "different_version_not_target",
    "build_mismatch",
    "channel_conflict",
    "working_build_not_failing",
    "rollback_build_not_failing",
    "unclassified_build_present",
    "duplicate_report",
    "evidence_existing_row_modified",
})

# A full Click-to-Run build token as written in prose, e.g. "20228.20110" or "16.0.20228.20110".
FULL_BUILD_RE = re.compile(r"(?<![\d.])(?:16\.0\.)?(\d{5}\.\d{4,5})(?![\d.])")

WINDOW_BASIS_STATED_FAMILY = "stated_version_family_matches_window"
WINDOW_BASIS_DATE_IN_WINDOW = "report_date_inside_release_window"
WINDOW_BASIS_NONE = "no_release_window_matches"


@dataclass
class ReleaseWindow:
    """One patch and the span during which it was the update a user would have received."""

    product_id: str
    update_version: str
    target_build: str
    released_on: str
    superseded_on: str = ""     # the next release date; empty means still current

    def contains(self, day: str) -> bool:
        if not day or not self.released_on or day < self.released_on:
            return False
        return not self.superseded_on or day < self.superseded_on

    @property
    def build_family(self) -> str:
        return self.target_build.split(".")[0] if "." in self.target_build else ""


def build_release_windows(patches: list[dict[str, str]]) -> list[ReleaseWindow]:
    """Order patches by release date and close each window where the next one opens.

    Windows are per PRODUCT. Closing a window at the next release is what stops a report from being
    attached to a build that had not shipped when it was written, and equally stops an old complaint
    drifting forward onto the newest patch.
    """
    rows = [p for p in patches if str(p.get("released_on") or "").strip()]
    rows.sort(key=lambda p: (str(p.get("product_id") or ""), str(p.get("released_on") or "")))
    windows: list[ReleaseWindow] = []
    for index, patch in enumerate(rows):
        nxt = ""
        for later in rows[index + 1:]:
            if later.get("product_id") == patch.get("product_id"):
                nxt = str(later.get("released_on") or "")[:10]
                break
        windows.append(ReleaseWindow(
            product_id=str(patch.get("product_id") or ""),
            update_version=str(patch.get("update_version") or ""),
            target_build=str(patch.get("target_build") or ""),
            released_on=str(patch.get("released_on") or "")[:10],
            superseded_on=nxt))
    return windows


def associate_window(report_date: str, windows: list[ReleaseWindow],
                     linkage: LinkageOutcome) -> tuple[ReleaseWindow | None, str]:
    """Pick the release window this report belongs to, or none.

    The date decides the window; a stated version or build family must then AGREE with it. A
    reporter who names 2607 while writing inside the 2608 window is talking about something the
    window does not cover, and guessing which of the two they meant is exactly the fabrication this
    tier exists to avoid.
    """
    day = str(report_date or "")[:10]
    if not day:
        return None, WINDOW_BASIS_NONE
    inside = [w for w in windows if w.contains(day)]
    if not inside:
        return None, WINDOW_BASIS_NONE
    window = inside[0]
    stated_version = linkage.version_family
    stated_family = linkage.build_family
    if stated_version and stated_version != window.update_version:
        return None, WINDOW_BASIS_NONE
    if stated_family and stated_family != window.build_family:
        return None, WINDOW_BASIS_NONE
    if stated_version or stated_family:
        return window, WINDOW_BASIS_STATED_FAMILY
    return window, WINDOW_BASIS_DATE_IN_WINDOW


def patch_join_key(product_id: str, update_version: str, target_build: str) -> str:
    """The key a TEMPLATE filters on. Deliberately NOT numeric-looking.

    Jekyll's `where` filter passes the property through `parse_sort_input`, which coerces any
    numeric-looking string to a Float. A build like "20326.20100" therefore becomes 20326.201 --
    the trailing zero is silently lost -- and the comparison against the original string fails.
    Measured: .20100 and .20110 break, .20158 and .20096 survive, which is why the defect looked
    arbitrary and why every direct `==` test passed. Joining product, version and build with a
    separator makes the value non-numeric, so no coercion can apply.
    """
    return "|".join([str(product_id or ""), str(update_version or ""), str(target_build or "")])


def report_identity(product_id: str, source_url: str) -> str:
    """A STABLE id for one report, independent of tier.

    Deliberately keyed on the report itself and not on the build, the tier, or the run, so that when
    a reporter later supplies the exact build the same row is PROMOTED rather than a second row
    appearing beside it. Promotion must never look like a new report.
    """
    canonical = str(source_url or "").strip().rstrip("/").lower()
    digest = hashlib.sha256(f"{product_id}|{canonical}".encode("utf-8")).hexdigest()[:16]
    return f"{product_id}:{digest}"


@dataclass
class Tier2Row:
    """One update-linked report, in the shape written to disk."""

    report_id: str = ""
    product_id: str = ""
    source_family: str = ""
    source_type: str = ""
    source_url: str = ""
    source_report_id: str = ""
    author_id: str = ""
    report_date: str = ""
    report_title: str = ""
    report_excerpt: str = ""
    issue_summary: str = ""
    update_link_signal: str = ""
    update_link_reason: str = ""
    update_link_evidence: str = ""
    associated_update_version: str = ""
    associated_target_build: str = ""
    associated_patch_key: str = ""
    association_basis: str = ""
    stated_version_family: str = ""
    stated_build_family: str = ""
    exact_version_known: str = ""
    exact_build_known: str = ""
    classification: str = TIER_UPDATE_LINKED
    confirmation_state: str = "not_confirmed"
    promotion_eligible: bool = True
    strict_exclusion_reason: str = ""
    captured_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = {
            "report_id": self.report_id,
            "product_id": self.product_id,
            "source_family": self.source_family,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_report_id": self.source_report_id,
            "author_id": self.author_id,
            "report_date": self.report_date,
            "report_title": self.report_title,
            "report_excerpt": self.report_excerpt,
            "issue_summary": self.issue_summary,
            "update_link_signal": self.update_link_signal,
            "update_link_reason": self.update_link_reason,
            "update_link_evidence": self.update_link_evidence,
            "associated_update_version": self.associated_update_version,
            "associated_target_build": self.associated_target_build,
            "associated_patch_key": self.associated_patch_key,
            "association_basis": self.association_basis,
            "stated_version_family": self.stated_version_family,
            "stated_build_family": self.stated_build_family,
            "exact_version_known": self.exact_version_known,
            "exact_build_known": self.exact_build_known,
            "classification": self.classification,
            "confirmation_state": self.confirmation_state,
            "promotion_eligible": self.promotion_eligible,
            "strict_exclusion_reason": self.strict_exclusion_reason,
            "captured_at": self.captured_at,
        }
        return {k: v for k, v in data.items() if v not in ("", None)}


_SOURCE_FAMILIES = {
    "microsoft_learn_qna": "Microsoft Q&A",
    "microsoft_tech_community": "Microsoft Tech Community",
    "stack_exchange_question": "Super User / Stack Exchange",
    "github_officedev_issue": "OfficeDev GitHub issues",
    "reddit_community_report": "Reddit",
}


# Source titles arrive full of typographic punctuation and HTML entities. Both have already caused
# trouble downstream -- an entity that was escaped twice showed readers a literal "&amp;amp;" -- and
# they add a variable to every string comparison and template render for no reader benefit. Titles
# and excerpts are normalised once, here, where they are stored.
_SMART_PUNCTUATION = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "‒": "-", "―": "-",
    "…": "...", " ": " ", "​": "", "﻿": "",
}


def normalise_text(value: str) -> str:
    """Plain, single-escaped, ASCII-punctuation text for storage and display."""
    import html as _html  # noqa: PLC0415

    # Bounded loop, not a single pass: source titles reach us DOUBLE-encoded ("&amp;amp;"), so one
    # unescape leaves "&amp;" and a reader still sees an entity. Three passes converge on every
    # real case and cannot loop on text that contains a literal ampersand.
    text = str(value or "")
    for _ in range(3):
        decoded = _html.unescape(text)
        if decoded == text:
            break
        text = decoded
    for fancy, plain in _SMART_PUNCTUATION.items():
        text = text.replace(fancy, plain)
    return " ".join(text.split())


def source_family(source_type: str) -> str:
    return _SOURCE_FAMILIES.get(str(source_type or ""), str(source_type or "").replace("_", " "))


def _source_report_id(source_url: str) -> str:
    tail = [part for part in str(source_url or "").rstrip("/").split("/") if part]
    for part in reversed(tail):
        if re.fullmatch(r"\d{3,}", part):
            return part
    return tail[-1] if tail else ""


def unresolved_row_from_rejection(rejected_row: dict[str, Any], *, captured_at: str,
                                  is_concrete=None) -> Tier2Row | None:
    """A real, concrete PowerPoint complaint that attributes itself to NOTHING.

    Measured on the live corpus: of 299 unique candidates only 4 carry genuine update attribution.
    The rest are ordinary complaints -- no build, and no claim that an update caused them. They are
    not patch evidence and must never be shown as such, because associating them would be the
    date-alone inference this tier exists to forbid. They are RETAINED so a future run can rehydrate
    the thread: reporters routinely add "this started after the August update" when a moderator
    asks, and at that point the same stable identity is promoted rather than rediscovered.

    Deliberately carries NO associated_patch_key, which is what the templates filter on -- so an
    unresolved row is structurally incapable of rendering on a patch page.
    """
    reason = str(rejected_row.get("exclusion_reason") or "")
    if reason in NEVER_PROMOTE or reason not in PROMOTABLE_REJECTIONS:
        return None
    text = str(rejected_row.get("tier2_full_text") or "")
    if is_concrete is not None and not is_concrete(text):
        return None
    url = str(rejected_row.get("source_url") or "")
    if not url:
        return None
    product = str(rejected_row.get("product_id") or "")
    title = str(rejected_row.get("parent_title") or rejected_row.get("report_title") or "").strip()
    excerpt = str(rejected_row.get("report_text_excerpt") or "").strip()
    return Tier2Row(
        report_id=report_identity(product, url), product_id=product,
        source_family=source_family(str(rejected_row.get("source_type") or "")),
        source_type=str(rejected_row.get("source_type") or ""), source_url=url,
        source_report_id=_source_report_id(url),
        report_date=str(rejected_row.get("source_date") or "")[:10],
        report_title=normalise_text(title)[:300], report_excerpt=normalise_text(excerpt)[:400],
        classification=TIER_UNRESOLVED, confirmation_state="not_confirmed",
        promotion_eligible=True, strict_exclusion_reason=reason, captured_at=captured_at)


def tier2_row_from_rejection(rejected_row: dict[str, Any], *, windows: list[ReleaseWindow],
                             captured_at: str, is_concrete=None) -> Tier2Row | None:
    """One strict-authority rejection -> one Tier-2 row, or None.

    Four independent conditions, all required and each able to refuse alone: the strict reason must
    mean "identity unproven" rather than "not a report"; the reporter must have attributed the
    problem to an Office update in their own words; the report must carry a date; and that date must
    fall inside a release window the stated version family (if any) agrees with.
    """
    reason = str(rejected_row.get("exclusion_reason") or "")
    if reason in NEVER_PROMOTE or reason not in PROMOTABLE_REJECTIONS:
        return None

    text = str(rejected_row.get("tier2_full_text") or "") or " ".join(
        str(rejected_row.get(field_name) or "") for field_name in
        ("parent_title", "report_title", "report_text", "report_text_excerpt"))
    linkage = classify_update_linkage(text)
    if not linkage.linked:
        return None

    # CONCRETENESS IS CHECKED HERE, not assumed from the rejection reason. The strict authority
    # evaluates the version gate BEFORE the concreteness gate, so a report that fails on version
    # never reaches the concreteness test at all -- measured, not_a_concrete_powerpoint_issue fires
    # ZERO times across 2328 rejections. Listing it in NEVER_PROMOTE therefore blocks nothing, and
    # how-to questions, feature requests and "I like the new icons" were becoming Tier 2.
    if is_concrete is not None and not is_concrete(text):
        return None

    day = str(rejected_row.get("source_date") or "")[:10]
    window, basis = associate_window(day, windows, linkage)
    if window is None:
        return None

    # An EXACT build stated in the text outranks the date. If the reporter named a full build and it
    # is not this window's, the report is about something else -- and it must not be filed here
    # merely because its date landed in this span. This is also what stops a report naming a build
    # as WORKING from being attached to that build.
    stated_builds = {token for token in FULL_BUILD_RE.findall(text)}
    if stated_builds and window.target_build not in stated_builds:
        return None

    # BUILD ROLES APPLY HERE TOO. A reporter who names this window's build as the one that WORKS,
    # or the one they rolled back TO, has said the opposite of a complaint about it. Tier 1 has
    # vetoed that since #79; without the same veto Tier 2 would publish "X is broken" sourced from
    # a post saying "X is fine". The shared primitive decides the role -- never a second opinion.
    if stated_builds:
        from .build_claims import ROLE_CURRENT_FAILING, extract_build_claims  # noqa: PLC0415

        for claim in extract_build_claims(text):
            if claim.build == window.target_build and claim.role != ROLE_CURRENT_FAILING:
                return None

    url = str(rejected_row.get("source_url") or "")
    product = str(rejected_row.get("product_id") or window.product_id)
    title = str(rejected_row.get("parent_title") or rejected_row.get("report_title") or "").strip()
    excerpt = str(rejected_row.get("report_text_excerpt")
                  or rejected_row.get("report_text") or "").strip()
    return Tier2Row(
        report_id=report_identity(product, url),
        product_id=product,
        source_family=source_family(str(rejected_row.get("source_type") or "")),
        source_type=str(rejected_row.get("source_type") or ""),
        source_url=url,
        source_report_id=_source_report_id(url),
        author_id=str(rejected_row.get("author_id") or rejected_row.get("qna_author_id") or ""),
        report_date=day,
        report_title=normalise_text(title)[:300],
        report_excerpt=normalise_text(excerpt)[:400],
        issue_summary=str(rejected_row.get("issue_theme") or "").strip(),
        update_link_signal=linkage.signal,
        update_link_reason=linkage.reason,
        update_link_evidence=linkage.evidence_phrase,
        associated_update_version=window.update_version,
        associated_target_build=window.target_build,
        associated_patch_key=patch_join_key(product, window.update_version, window.target_build),
        association_basis=basis,
        stated_version_family=linkage.version_family,
        stated_build_family=linkage.build_family,
        classification=TIER_UPDATE_LINKED,
        confirmation_state="not_confirmed",
        promotion_eligible=True,
        strict_exclusion_reason=reason,
        captured_at=captured_at)


def merge_tier2_rows(existing: list[dict[str, Any]], fresh: list[dict[str, Any]],
                     *, confirmed_urls: set[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge a run's Tier-2 rows into the stored set, keyed on the stable report id.

    A report that has since been CONFIRMED is removed here rather than left alongside its Tier-1
    row: the same report must never be visible in both tiers at once, or a reader counts it twice.
    That is what makes promotion a state change instead of a second row.
    """
    by_id: dict[str, dict[str, Any]] = {str(r.get("report_id")): dict(r) for r in existing
                                        if r.get("report_id")}
    stats = {"added": 0, "updated": 0, "promoted_out": 0, "unchanged": 0}
    for row in fresh:
        rid = str(row.get("report_id") or "")
        if not rid:
            continue
        if rid in by_id:
            merged = {**by_id[rid], **row}
            stats["updated" if merged != by_id[rid] else "unchanged"] += 1
            by_id[rid] = merged
        else:
            by_id[rid] = dict(row)
            stats["added"] += 1
    canonical_confirmed = {str(u).strip().rstrip("/").lower() for u in confirmed_urls}
    for rid, row in list(by_id.items()):
        if str(row.get("source_url") or "").strip().rstrip("/").lower() in canonical_confirmed:
            del by_id[rid]
            stats["promoted_out"] += 1
    ordered = sorted(by_id.values(),
                     key=lambda r: (str(r.get("report_date") or ""), str(r.get("report_id") or "")),
                     reverse=True)
    return ordered, stats


SCHEMA_VERSION = 1


def load_tier2(path) -> list[dict[str, Any]]:
    """Stored update-linked rows, or an empty list when the file does not exist yet."""
    import yaml  # noqa: PLC0415

    from pathlib import Path as _Path  # noqa: PLC0415

    target = _Path(path)
    if not target.exists():
        return []
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    rows = data.get("reports") if isinstance(data, dict) else data
    return [r for r in (rows or []) if isinstance(r, dict)]


def write_tier2(rows: list[dict[str, Any]], path) -> None:
    """Write the update-linked set, newest first, with a stable key order.

    Sorted and key-ordered deterministically so an unchanged corpus produces an unchanged file and
    a run that found nothing new leaves no diff to review.
    """
    import yaml  # noqa: PLC0415

    from pathlib import Path as _Path  # noqa: PLC0415

    target = _Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION,
               "note": ("Update-linked user reports. These are REAL community reports about a "
                        "PowerPoint update whose exact build was never stated. They are shown to "
                        "readers and are deliberately NOT counted toward consensus."),
               "reports": [dict(sorted(r.items())) for r in rows]}
    target.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
                      encoding="utf-8")
