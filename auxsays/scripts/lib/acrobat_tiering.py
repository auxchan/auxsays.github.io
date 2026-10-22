#!/usr/bin/env python3
"""Acrobat Levels 2 and 3 -- an adapter over the product-neutral tiering primitives.

WHY AN ADAPTER AND NOT THE POWERPOINT PATH. The three-level model itself is generic: release
windows, the joined non-numeric window key, the stable report identity, the merge/eviction rules
and the file writers all live in `tier2_evidence` / `recent_reports` and are reused here unchanged.
What is NOT generic is the vocabulary. Three concrete blocks made the PowerPoint path unusable for
Acrobat as-is:

  * Acrobat's exclusion-reason tokens have zero overlap with `PROMOTABLE_REJECTIONS`, and the
    mismatch fails SILENTLY -- every builder just returns None, indistinguishable from "no reports".
  * `update_linkage` names `acrobat` as a FOREIGN application in its Office lexicon, so Acrobat's
    own attribution sentences are vetoed by the module meant to detect them.
  * `recent_reports._FOREIGN_PLATFORM_RE` discards macOS, which is right for a Windows
    Click-to-Run build and wrong for Acrobat -- Adobe ships the same DC build to macOS.

WHAT THIS DOES NOT DO. It does not weaken any Phase-A rule. Edition authority, the Acrobat Standard
exclusion, concreteness, vendor authority and URL specificity are imported from the collector and
re-applied here. Only the IDENTITY refusal -- "you did not name the exact build" -- is what these
levels are allowed to recover from.

THE ONE THAT IS NOT A RE-RUN. Phase A's role and multi-build vetoes sit BELOW its identity gate in
an `elif` chain, so for a patch whose build a report does not name they never execute and their
refusals are invisible here. Re-running them would test the wrong build. Instead the tiers refuse
any report that names a tracked build AT ALL (`names_any_tracked_build`): a reporter who names
builds has told us which ones they mean, and placing their report on a different build by date
overrides them. That closes the hole a live row went through -- a thread refused at Level 1 twice
as `multiple_builds_named_target_not_blamed` was published at Level 2 against a third build.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .recent_reports import (
    ATTRIBUTION_NOT_ESTABLISHED,
    LEVEL_RECENT_REPORT,
    RecentReport,
    merge_recent_reports,
    release_window_key,
    window_for_date,
)
from .tier2_evidence import (
    TIER_UPDATE_LINKED,
    ReleaseWindow,
    Tier2Row,
    build_release_windows,
    load_tier2,
    merge_tier2_rows,
    normalise_text,
    patch_join_key,
    report_identity,
    source_family,
    write_tier2,
)

__all__ = [
    "ACROBAT_NEVER_TIER",
    "ACROBAT_TIERABLE_REJECTIONS",
    "acrobat_recent_from_rejection",
    "acrobat_update_linked_from_rejection",
    "build_release_windows",
    "load_tier2",
    "merge_recent_reports",
    "merge_tier2_rows",
    "update_causality",
    "write_tier2",
]

# The ONE refusal these levels may recover from: the reporter described a real Acrobat problem on a
# tracked edition but never wrote the exact DC build. Everything else in Phase A's vocabulary is a
# SAFETY refusal and stays refused.
ACROBAT_TIERABLE_REJECTIONS = frozenset({"missing_exact_patch_version_match"})

# Named explicitly rather than implied by omission, so a reason added later fails closed instead of
# silently becoming tierable.
ACROBAT_NEVER_TIER = frozenset({
    "missing_product_attribution",          # no Acrobat in the text at all
    "wrong_product",                        # the OTHER tracked edition
    "acrobat_standard_edition_not_tracked",  # a third edition; neither tracked surface
    "generic_acrobat_without_edition",      # no record declared shared applicability
    "not_a_real_issue_report",              # how-to, feature request, pricing, announcement
    "source_url_not_specific_report",       # a board or search page, not a thread
    "source_date_before_or_unverified_against_release",
    "vendor_release_announcement",
    "version_named_but_working",            # the reporter said this build is FINE
    "version_named_but_rollback_target",    # they went BACK to it
    "version_named_but_fixed_in_target",    # it is the fix, not the fault
    "multiple_builds_named_target_not_blamed",
})

# --- update causality (Level 2) ------------------------------------------------------------------
# Acrobat's own grammar, not Office's. A Level-2 row asserts the reporter BLAMED AN UPDATE without
# saying which build, so the sentence has to actually make that claim.
_UPDATE_NOUN = (r"(?:adobe\s+)?(?:acrobat|reader)?[\s-]*"
                r"(?:update|updated|updating|upgrade|upgraded|patch|patched|new\s+version)")

# What can sit between the preposition and the update noun. Measured against the real corpus: the
# first version of this allowed one word from a short list and missed most genuine attributions,
# because people write "after SILENT Reader update", "21208 UPDATE breaks", "the NEWEST Adobe
# Acrobat update". A bounded run of determiners, adjectives and build-ish tokens covers those
# without becoming a wildcard.
_DET = (r"(?:(?:the|this|that|a|an|last|latest|recent|recently|newest|new|my|our|its|"
        r"silent|silently|automatic|automatically|auto|forced|enterprise|monthly|"
        r"yesterday'?s?|today'?s?|adobe|acrobat|reader|dc|"
        r"january|february|march|april|may|june|july|august|september|october|november|december|"
        r"\d[\w.]*)[\s-]+){0,4}")

_CAUSAL_RE = re.compile(
    # "after the latest Acrobat update, printing stopped working"
    rf"\b(?:after|since|following|once|until)\s+{_DET}{_UPDATE_NOUN}\b"
    # "Acrobat updated and now it crashes"; "Reader (free version) auto updated to 26.x".
    # The bounded gap is what real posts put between the product and the verb.
    rf"|\b(?:acrobat|reader)\b(?:[^.\n]{{0,40}}?)\b(?:auto[\s-]?)?(?:updated|upgraded|patched)\b"
    # "my Acrobat was recently updated, and now ..." -- the passive form.
    rf"|\b(?:was|were|got|has\s+been|have\s+been|had\s+been)\s+"
    rf"(?:recently\s+|automatically\s+|silently\s+|just\s+|auto[\s-]?)*"
    rf"(?:updated|upgraded|patched)\b"
    # "21208 update breaks Acrobat Reader" / "the latest patch broke signing"
    rf"|\b{_DET}{_UPDATE_NOUN}\s+(?:broke|breaks|breaking|has\s+broken|caused|causes|"
    rf"introduced|killed|disabled|removed)\b"
    # "stopped working after the silent Reader update" / "fails to launch after updating"
    rf"|\b(?:broke|broken|stopped\s+work\w*|no\s+longer\s+work\w*|crash\w*|fail\w*|regress\w*)\b"
    rf"[^.\n]{{0,60}}?\b(?:after|since|following)\s+{_DET}{_UPDATE_NOUN}\b"
    # "we upgraded Reader from 25.1.20813 to 25.1.20982. After that, most clients crash."
    rf"|\b(?:upgrad\w*|updat\w*)\b[^.\n]{{0,60}}?\bfrom\s+[\d.]+\s+to\s+[\d.]+[^\n]{{0,40}}?"
    rf"\bafter\s+(?:that|this|which)\b",
    re.I,
)

# REMEDY / ADVICE. The same words appear when somebody is telling you to update, or reporting that
# updating did NOT help. Those are not attributions and must never become Level 2.
_REMEDY_RE = re.compile(
    # IMPERATIVE only. "update Acrobat" is advice at the start of a clause and a plain noun phrase
    # after a determiner -- "since the August update Acrobat will not print" is an ATTRIBUTION, and
    # matching it as advice silently discarded exactly the reports Level 2 exists to hold. So the
    # imperative has to sit at a sentence/clause boundary or behind an advice cue.
    r"(?:^|[.!?;:\n]\s*|\b(?:please|try|just|first|maybe|simply|kindly)\s+)"
    r"updat(?:e|ing)\s+(?:to\s+)?(?:acrobat|reader|adobe|it|the\s+app|the\s+latest)\b"
    r"|\b(?:you|u|they|he|she)\s+(?:should|need\s+to|must|can|could|might\s+want\s+to)\s+updat\w*"
    r"|\bmake\s+sure\s+(?:you\s+)?(?:are\s+|you'?re\s+)?(?:on|running|updated)\b"
    # "I updated but it still crashes" -- the update is explicitly NOT the cause.
    r"|\b(?:i|we)\s+(?:have\s+)?(?:already\s+)?updat\w*[^.\n]{0,40}?\b(?:but|and)\b"
    r"[^.\n]{0,40}?\bstill\b"
    r"|\bstill\s+(?:crash\w*|happen\w*|fail\w*|occur\w*|broken)\b[^.\n]{0,40}?\bafter\s+updat\w*"
    r"|\breinstall\w*\s+(?:or\s+)?updat\w*"
    r"|\bupdat\w*\s+did\s*n[o']?t\s+(?:help|fix|work|change)\b",
    re.I,
)


@dataclass(frozen=True)
class Causality:
    """Whether the reporter blamed an update, and the words that say so."""

    linked: bool
    basis: str
    excerpt: str


def update_causality(text: str) -> Causality:
    """Did the reporter attribute their problem to an Acrobat/Adobe product update?

    Remedy and advice are checked FIRST and win. "Update Acrobat to the latest version" and "I
    updated Acrobat but it still crashes" both contain the causal words and both mean the opposite
    of an attribution -- one is instructing somebody, the other is ruling the update out.
    """
    body = str(text or "")
    remedy = _REMEDY_RE.search(body)
    if remedy:
        return Causality(False, "remedy_or_advice", remedy.group(0)[:120])
    hit = _CAUSAL_RE.search(body)
    if hit:
        return Causality(True, "update_named_as_cause", hit.group(0)[:120])
    return Causality(False, "no_update_attribution", "")


# --- shared admission ----------------------------------------------------------------------------

# An Acrobat DC version as Adobe writes it anywhere: 26.001.21745, 2026.001.21745, 25.1.20982.
# Bounded to the real shape so an ordinary number, a date or an error code cannot match.
# `generated_records` re-reads ~160 markdown files per call. This is invoked once per candidate
# per patch, so without a cache one run does tens of thousands of file reads.
_TRACKED_VERSIONS: dict[str, tuple[str, ...]] = {}


def _tracked_versions(product_id: str, safety) -> tuple[str, ...]:
    cached = _TRACKED_VERSIONS.get(product_id)
    if cached is None:
        cached = tuple(sorted({str(r.update_version or "").strip()
                               for r in safety.generated_records(product_id)
                               if str(r.update_version or "").strip()}))
        _TRACKED_VERSIONS[product_id] = cached
    return cached


_ACROBAT_VERSION_RE = re.compile(r"(?<![\d.])(?:20)?\d{2}\.\d{1,3}\.\d{4,5}(?![\d])")


def names_any_tracked_build(text: str, product_id: str, safety) -> str:
    """The first tracked build of this product that the report names, in ANY spelling, or "".

    WHY THIS EXISTS. Phase A's gate chain is an `elif`: for a patch whose build the report does not
    name, it returns `missing_exact_patch_version_match` and never reaches the multi-build or
    working/rollback vetoes below it. Those refusals are therefore invisible to the tiers, and a
    report that Level 1 safety-vetoed for patch X arrived here labelled "identity unknown" for
    patch Y. One did: a thread naming 26.001.21563 and 26.001.21651 was refused at Level 1 for both
    and published at Level 2 against 26.001.21662.

    The rule is structural rather than a re-run of those vetoes. A reporter who names builds has
    told us which builds they mean; assigning their report to a different build BY DATE overrides
    them. So if the report names any tracked build at all, the tiers decline it -- either the
    authority can resolve it (Level 1) or nobody should place it by date.

    Spelling-tolerant on purpose, and deliberately over-inclusive: this is a REFUSAL, so a false
    match costs one context row while a miss publishes a claim the reporter contradicts. Adobe's
    own strings vary -- "26.001.21789", "2026.001.21789" (Help > About), "25.1.20982.0" (the
    installer), and bare "21208" (how people write it in a title).
    """
    body = str(text or "")
    # Any Acrobat-shaped version at all, tracked or not. A post written in May can paste an April
    # crash log -- applicationVersion="26.001.21462" -- and post-date containment will happily place
    # it on May's window, which the reporter's own log contradicts. 21462 is not a tracked record,
    # so a tracked-only scan cannot see it.
    generic = _ACROBAT_VERSION_RE.search(body)
    if generic:
        return generic.group(0)

    for version in _tracked_versions(product_id, safety):
        parts = version.split(".")
        if len(parts) != 3:
            continue
        major, mid, tail = parts
        spellings = {
            version,                              # 25.001.21208  release notes
            f"20{major}.{mid}.{tail}",            # 2025.001.21208  Help > About
            f"{major}.{int(mid)}.{tail}",         # 25.1.21208  installer / file version
            f"{major}{mid}{tail}",                # 2500121208  AUSST / deployment paths
            tail,                                 # 21208  how people write it in a title
        }
        for spelling in spellings:
            if re.search(rf"(?<![\d.]){re.escape(spelling)}(?![\d])", body):
                return version
    return ""


def _authority_refusal(rejected_row: dict[str, Any], text: str, *,
                       product_id: str, safety) -> str:
    """Re-apply Phase A's SAFETY rules. Returns a refusal reason, or "" when clear.

    `safety` is the collector module, injected so this library never imports a collector (and so a
    test can prove the rules are the collector's own rather than a second copy of them).
    """
    reason = str(rejected_row.get("exclusion_reason") or "")
    if reason in ACROBAT_NEVER_TIER or reason not in ACROBAT_TIERABLE_REJECTIONS:
        return reason or "unknown_exclusion_reason"

    # Acrobat Standard is a third edition. It reads as licensing language to the tier rule, which
    # is exactly how it reached live Reader pages in Phase A. Check it explicitly, both levels.
    if safety._STANDARD_PRODUCT_RE.search(text):
        return "acrobat_standard_edition_not_tracked"

    # Edition authority, unchanged: Reader text counts for Reader, Pro for Pro, and a bare-Acrobat
    # report only where the record itself declares a shared DC build.
    attributed, _alias, _appl, edition_reason = safety.acrobat_edition_attribution(text, product_id)
    if not attributed and edition_reason != "generic_acrobat_without_edition":
        return edition_reason or "missing_product_attribution"

    # A concrete, user-facing problem -- not a how-to, feature request or announcement.
    if not safety.acrobat_strong_issue_match(text):
        return "not_a_real_issue_report"
    if safety.acrobat_vendor_authority(str(rejected_row.get("report_title") or ""), text):
        return "vendor_release_announcement"

    url = str(rejected_row.get("source_url") or "")
    if not safety.acrobat_url_is_specific(url):
        return "source_url_not_specific_report"

    # The reporter named a build. Placing their report on a window by DATE would override what they
    # actually said, and it is how a Level-1 safety veto leaked into Level 2. See the docstring on
    # names_any_tracked_build.
    named = names_any_tracked_build(text, product_id, safety)
    if named:
        return f"names_tracked_build_{named}"
    return ""


def _shared_edition_ok(text: str, product_id: str, *, safety, applicability) -> bool:
    """True when this edition may carry the report at all."""
    attributed, _a, _b, edition_reason = safety.acrobat_edition_attribution(text, product_id)
    if attributed:
        return True
    return edition_reason == "generic_acrobat_without_edition" and product_id in (applicability or ())


def acrobat_update_linked_from_rejection(rejected_row: dict[str, Any], *,
                                         windows: list[ReleaseWindow], captured_at: str,
                                         safety, applicability=(), exclude_urls=None
                                         ) -> Tier2Row | None:
    """LEVEL 2 -- the reporter blamed an update but never named the build.

    Every gate can refuse alone: Phase A's safety rules, an explicit update attribution that is not
    remedy or advice, an original post date, a window containing that date, and not already visible
    at Level 1.
    """
    text = str(rejected_row.get("tier2_full_text") or rejected_row.get("report_text") or "")
    product_id = str(rejected_row.get("product_id") or "")
    if _authority_refusal(rejected_row, text, product_id=product_id, safety=safety):
        return None
    if not _shared_edition_ok(text, product_id, safety=safety, applicability=applicability):
        return None

    causality = update_causality(text)
    if not causality.linked:
        return None

    url = str(rejected_row.get("source_url") or "").strip()
    if not url.startswith("http"):
        return None
    canonical = url.rstrip("/").lower()
    if exclude_urls and canonical in exclude_urls:
        return None

    day = str(rejected_row.get("original_post_date") or "")[:10]
    window = window_for_date(day, [w for w in windows if w.product_id == product_id])
    if window is None:
        return None

    title = str(rejected_row.get("report_title") or rejected_row.get("parent_title") or "").strip()
    excerpt = str(rejected_row.get("report_text_excerpt") or "").strip()
    if not title and not excerpt:
        return None

    return Tier2Row(
        report_id=report_identity(product_id, url),
        product_id=product_id,
        source_family=source_family(str(rejected_row.get("source_type") or "")),
        source_type=str(rejected_row.get("source_type") or ""),
        source_url=url,
        source_report_id=str(rejected_row.get("source_report_id") or ""),
        report_date=day,
        report_title=normalise_text(title)[:300],
        report_excerpt=normalise_text(excerpt)[:400],
        update_link_signal="explicit_update_attribution",
        update_link_reason=causality.basis,
        update_link_evidence=normalise_text(causality.excerpt)[:200],
        associated_update_version=window.update_version,
        associated_target_build=window.target_build,
        associated_patch_key=patch_join_key(product_id, window.update_version, window.target_build),
        association_basis="release_window_containment",
        # Empty, not "no": the template prints this field AS the build, so a sentinel here
        # rendered the literal words "Exact build: no" on every Level-2 card. The intended
        # fallback -- "Not supplied by the reporter." -- is what an empty value produces.
        exact_build_known="",
        classification=TIER_UPDATE_LINKED,
        confirmation_state="not_confirmed",
        promotion_eligible=True,
        strict_exclusion_reason=str(rejected_row.get("exclusion_reason") or ""),
        captured_at=captured_at)


def acrobat_recent_from_rejection(rejected_row: dict[str, Any], *,
                                  windows: list[ReleaseWindow], captured_at: str,
                                  safety, applicability=(), exclude_urls=None
                                  ) -> RecentReport | None:
    """LEVEL 3 -- a concrete Acrobat problem reported while this release was current.

    It claims NOTHING about causality. The reporter did not identify any update as the cause, and
    the row carries no field that could be read as saying they did.
    """
    text = str(rejected_row.get("tier2_full_text") or rejected_row.get("report_text") or "")
    product_id = str(rejected_row.get("product_id") or "")
    if _authority_refusal(rejected_row, text, product_id=product_id, safety=safety):
        return None
    if not _shared_edition_ok(text, product_id, safety=safety, applicability=applicability):
        return None

    # A report that DOES blame an update belongs at Level 2, not here. Remedy/advice is not an
    # attribution, so those stay eligible for Level 3 only if they describe a real problem -- which
    # `_authority_refusal` has already required.
    if update_causality(text).linked:
        return None

    url = str(rejected_row.get("source_url") or "").strip()
    if not url.startswith("http"):
        return None
    canonical = url.rstrip("/").lower()
    if exclude_urls and canonical in exclude_urls:
        return None

    day = str(rejected_row.get("original_post_date") or "")[:10]
    window = window_for_date(day, [w for w in windows if w.product_id == product_id])
    if window is None:
        return None

    title = str(rejected_row.get("report_title") or rejected_row.get("parent_title") or "").strip()
    excerpt = str(rejected_row.get("report_text_excerpt") or "").strip()
    if not title and not excerpt:
        return None

    return RecentReport(
        report_id=report_identity(product_id, url),
        product_id=product_id,
        source_family=source_family(str(rejected_row.get("source_type") or "")),
        source_type=str(rejected_row.get("source_type") or ""),
        source_url=url,
        source_report_id=str(rejected_row.get("source_report_id") or ""),
        report_date=day,
        report_title=normalise_text(title)[:300],
        report_excerpt=normalise_text(excerpt)[:400],
        release_window_key=release_window_key(product_id, window.update_version,
                                              window.target_build),
        window_version=window.update_version,
        window_build=window.target_build,
        window_start=window.released_on,
        window_end=window.superseded_on,
        attribution_state=ATTRIBUTION_NOT_ESTABLISHED,
        classification=LEVEL_RECENT_REPORT,
        promotion_eligible=True,
        strict_exclusion_reason=str(rejected_row.get("exclusion_reason") or ""),
        captured_at=captured_at)
