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
                                 captured_at: str, is_concrete=None,
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

    url = str(rejected_row.get("source_url") or "").strip()
    if not url or not url.startswith("http"):
        return None

    product = str(rejected_row.get("product_id") or "")
    identity = report_identity(product, url)
    canonical = url.rstrip("/").lower()
    if exclude_urls and canonical in exclude_urls:
        return None

    day = str(rejected_row.get("source_date") or "")[:10]
    window = window_for_date(day, windows)
    if window is None:
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
    return ordered, stats


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
