#!/usr/bin/env python3
"""LEVEL 3 -- recent PowerPoint reports: situational context, explicitly NOT patch evidence.

WHAT THIS IS. Concrete, user-authored PowerPoint problems that were reported while a release was
current. Measured across the nine-month corpus, 299 unique candidates yielded only 4 with genuine
update attribution -- users overwhelmingly describe a problem without claiming an update caused it.
Those reports are real and useful, and discarding them left ten patch pages looking empty.

WHAT THIS IS EMPHATICALLY NOT. It is not causal. A report here says "this was reported while that
release was current" and nothing more. It is not "linked to", "suspected of", "likely caused by" or
"evidence against" the build. The reporters did not identify the update as the cause, and this layer
must never let volume imply that they did: thirty complaints in a window are thirty complaints in a
window, not thirty complaints about a patch.

WHY A RELEASE WINDOW AND NOT A PATCH. The field names carry the semantics deliberately --
`release_window_key`, `window_start`, `window_end`. There is no `associated_patch`, no
`linked_patch`, no `suspected_patch`, because none of those relationships has been established and
a field name is the first place a false claim creeps in.

ISOLATION IS STRUCTURAL. Level 3 is written to its OWN data file, which nothing that computes a
count, a percentage, a verdict or a consensus state reads. A Level-3 row cannot reach consensus by
any code path, including one written later by someone who never heard of levels.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .tier2_evidence import (
    NEVER_PROMOTE,
    PROMOTABLE_REJECTIONS,
    ReleaseWindow,
    _source_report_id,
    normalise_text,
    report_identity,
    source_family,
)

LEVEL_RECENT_REPORT = "recent_report"
ATTRIBUTION_NOT_ESTABLISHED = "not_established"

# --- admission vetoes ---------------------------------------------------------------------------
# Level 3 makes exactly one factual claim: a concrete problem with THIS product, on THIS platform,
# was reported while THIS release was current. Every veto below exists because a row was published
# for which some part of that sentence was not true. A veto is cheap; a false public claim is not.

# The release windows are Windows Click-to-Run Microsoft 365 builds. A report about the web app,
# the file-hosting service or the Copilot service is not about the desktop build at all, so even
# "reported during this window" invites a reader to connect two unrelated things.
_SERVICE_SURFACE_RE = re.compile(
    r"\b(?:power\s?point\s+online|office\.com|officeapps\.live|view\.officeapps|"
    r"web\s+(?:app|version|browser)\s+of\s+power\s?point|power\s?point\s+for\s+the\s+web|"
    r"onedrive\s+embed|embedded\s+(?:in|via)\s+onedrive|sharepoint\s+online\s+viewer)\b",
    re.I,
)

# A different platform is a different product line with its own release train.
_FOREIGN_PLATFORM_RE = re.compile(
    r"\b(?:mac\s?os|macos|osx|os\s+x|on\s+(?:a\s+)?mac\b|for\s+mac\b|macbook|"
    r"ipad|iphone|ios\b|android|chromebook|linux)\b",
    re.I,
)

# Perpetual editions ship on their own cadence and never receive a Current Channel build.
_PERPETUAL_EDITION_RE = re.compile(
    r"\bpower\s?point\s*(?:20(?:07|10|13|16|19|21|24))\b|\boffice\s*(?:20(?:07|10|13|16|19|21|24))\b",
    re.I,
)

# A defect in someone else's library that happens to write .pptx is not a PowerPoint defect.
_THIRD_PARTY_LIB_RE = re.compile(
    r"\b(?:apache\s+poi|python-?pptx|aspose|docx4j|syncfusion|gembox|npoi|openxml\s+sdk|"
    r"spire\.presentation|unoconv|libre\s?office|open\s?office|google\s+slides|wps\s+office)\b",
    re.I,
)

# The public sentence. Kept here, beside the data, so the storage layer and the page cannot drift
# into saying different things about what a Level-3 row means.
PUBLIC_QUALIFIER = "Not attributed to this update."
PUBLIC_EXPLANATION = ("These issues were reported while this release was current. "
                      "The reporters did not identify this update as the cause.")


def release_window_key(product_id: str, update_version: str, target_build: str) -> str:
    """Identity of the WINDOW a report fell inside -- never a claim about the patch.

    Joined rather than numeric on purpose: Jekyll's `where` filter runs a property through
    parse_sort_input, which coerces a numeric-looking string to a Float and silently drops a
    trailing zero, so a bare build like "20326.20100" stops matching its own page.
    """
    return "|".join([str(product_id or ""), str(update_version or ""), str(target_build or "")])


@dataclass
class RecentReport:
    """One concrete PowerPoint problem reported inside a release window."""

    report_id: str = ""
    product_id: str = ""
    source_family: str = ""
    source_type: str = ""
    source_url: str = ""
    source_report_id: str = ""
    report_date: str = ""
    report_title: str = ""
    report_excerpt: str = ""
    release_window_key: str = ""
    window_version: str = ""
    window_build: str = ""
    window_start: str = ""
    window_end: str = ""
    attribution_state: str = ATTRIBUTION_NOT_ESTABLISHED
    classification: str = LEVEL_RECENT_REPORT
    promotion_eligible: bool = True
    strict_exclusion_reason: str = ""
    captured_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = {
            "report_id": self.report_id,
            "product_id": self.product_id,
            "source_family": self.source_family,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_report_id": self.source_report_id,
            "report_date": self.report_date,
            "report_title": self.report_title,
            "report_excerpt": self.report_excerpt,
            "release_window_key": self.release_window_key,
            "window_version": self.window_version,
            "window_build": self.window_build,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "attribution_state": self.attribution_state,
            "classification": self.classification,
            "promotion_eligible": self.promotion_eligible,
            "strict_exclusion_reason": self.strict_exclusion_reason,
            "captured_at": self.captured_at,
        }
        return {k: v for k, v in data.items() if v not in ("", None)}


def window_for_date(report_date: str, windows: list[ReleaseWindow]) -> ReleaseWindow | None:
    """The window whose span CONTAINS this date, or none.

    Containment only -- never "the newest window". A March complaint belongs to March's release
    window; assigning it to August because August is newest would invent the very association this
    layer exists to avoid.
    """
    day = str(report_date or "")[:10]
    if not day:
        return None
    for window in windows:
        if window.contains(day):
            return window
    return None


def recent_report_from_rejection(rejected_row: dict[str, Any], *, windows: list[ReleaseWindow],
                                 captured_at: str, is_concrete=None, states_problem=None,
                                 states_target_build=None,
                                 exclude_urls: set[str] | None = None) -> RecentReport | None:
    """One strict-authority rejection -> one Level-3 row, or None.

    Every gate can refuse alone. The report must be a PowerPoint problem the authority merely could
    not pin to a build -- not a wrong-product row, an announcement, or a how-to -- it must carry a
    usable date, it must land inside a real window, and it must not already be visible at a higher
    level, because one report may occupy exactly one level at a time.
    """
    reason = str(rejected_row.get("exclusion_reason") or "")
    if reason in NEVER_PROMOTE or reason not in PROMOTABLE_REJECTIONS:
        return None

    text = str(rejected_row.get("tier2_full_text") or "")
    if is_concrete is not None and not is_concrete(text):
        return None

    # `concrete_issue` accepts a feature-location question backed by regression evidence, which is
    # right for evidence but wrong here: with no patch attribution to supply that evidence, the
    # weak path let "How do I get video to play?" and "Changing the tabbing order of objects"
    # publish under a heading that promises reports of problems. Level 3 demands the strong signal.
    if states_problem is not None and not states_problem(text):
        return None

    for veto in (_SERVICE_SURFACE_RE, _FOREIGN_PLATFORM_RE, _PERPETUAL_EDITION_RE,
                 _THIRD_PARTY_LIB_RE):
        if veto.search(text):
            return None

    url = str(rejected_row.get("source_url") or "").strip()
    if not url or not url.startswith("http"):
        return None

    product = str(rejected_row.get("product_id") or "")
    identity = report_identity(product, url)
    canonical = url.rstrip("/").lower()
    if exclude_urls and canonical in exclude_urls:
        return None

    # The ORIGINAL post date, never the feed's last-activity stamp -- see lib/post_dates. A reply
    # bumping a nine-month-old question once carried it forward five windows, and in one case onto
    # the page of a build that had not yet shipped when the report was written. No fallback: if the
    # lane cannot establish when the report was written, the window cannot be asserted.
    day = str(rejected_row.get("original_post_date") or "")[:10]
    window = window_for_date(day, windows)
    if window is None:
        return None

    # A report that names this window's exact build, in a failing role, is making an attribution.
    # Publishing it here would print "the reporters did not identify this update as the cause"
    # directly above their words doing exactly that. It belongs at Level 1; refuse it either way.
    if states_target_build is not None and states_target_build(text, window.target_build):
        return None

    title = str(rejected_row.get("parent_title") or rejected_row.get("report_title") or "").strip()
    excerpt = str(rejected_row.get("report_text_excerpt") or "").strip()
    if not title and not excerpt:
        return None

    return RecentReport(
        report_id=identity,
        product_id=product,
        source_family=source_family(str(rejected_row.get("source_type") or "")),
        source_type=str(rejected_row.get("source_type") or ""),
        source_url=url,
        source_report_id=_source_report_id(url),
        report_date=day,
        report_title=normalise_text(title)[:300],
        report_excerpt=normalise_text(excerpt)[:400],
        release_window_key=release_window_key(product, window.update_version, window.target_build),
        window_version=window.update_version,
        window_build=window.target_build,
        window_start=window.released_on,
        window_end=window.superseded_on,
        attribution_state=ATTRIBUTION_NOT_ESTABLISHED,
        classification=LEVEL_RECENT_REPORT,
        promotion_eligible=True,
        strict_exclusion_reason=reason,
        captured_at=captured_at)


def merge_recent_reports(existing: list[dict[str, Any]], fresh: list[dict[str, Any]],
                         *, promoted_urls: set[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge a run's Level-3 rows, evicting any report that now exists at a higher level.

    Eviction is what makes promotion a state change rather than a second card: a report that has
    since become update-linked or confirmed must disappear from here, or a reader counts the same
    complaint twice on the same page.
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
    canonical = {str(u).strip().rstrip("/").lower() for u in promoted_urls}
    for rid, row in list(by_id.items()):
        if str(row.get("source_url") or "").strip().rstrip("/").lower() in canonical:
            del by_id[rid]
            stats["promoted_out"] += 1
    ordered = sorted(by_id.values(),
                     key=lambda r: (str(r.get("report_date") or ""), str(r.get("report_id") or "")),
                     reverse=True)

    # One incident, one card. The identity hashes product|url, so the same person cross-posting the
    # same problem to Q&A and to Super User mints two ids and the window's heading counts two
    # reports where there was one. Same window and same title is that case; keep the earliest
    # telling, which is the one that was actually written first.
    seen_content: dict[tuple[str, str], dict[str, Any]] = {}
    deduped: list[dict[str, Any]] = []
    for row in sorted(ordered, key=lambda r: str(r.get("report_date") or "")):
        key = (str(row.get("release_window_key") or ""),
               " ".join(str(row.get("report_title") or "").lower().split())[:80])
        if key[1] and key in seen_content:
            stats["cross_post_merged"] = stats.get("cross_post_merged", 0) + 1
            continue
        seen_content[key] = row
        deduped.append(row)
    deduped.sort(key=lambda r: (str(r.get("report_date") or ""), str(r.get("report_id") or "")),
                 reverse=True)
    return deduped, stats


SCHEMA_VERSION = 1


def load_recent(path) -> list[dict[str, Any]]:
    import yaml  # noqa: PLC0415

    from pathlib import Path as _Path  # noqa: PLC0415

    target = _Path(path)
    if not target.exists():
        return []
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    rows = data.get("reports") if isinstance(data, dict) else data
    return [r for r in (rows or []) if isinstance(r, dict)]


def write_recent(rows: list[dict[str, Any]], path) -> None:
    import yaml  # noqa: PLC0415

    from pathlib import Path as _Path  # noqa: PLC0415

    target = _Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "note": ("Concrete PowerPoint problems reported while a release was current. These are "
                 "situational context ONLY. The reporters did not identify any update as the "
                 "cause, no patch attribution has been established, and these rows are excluded "
                 "from every consensus calculation."),
        "reports": [dict(sorted(r.items())) for r in rows],
    }
    target.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
                      encoding="utf-8")
