"""Keep stored third-party report text out of what a writer prints (G66).

WHY. The Actions run logs of this public repository can be read by any signed-in GitHub user and
are kept for 90 days. `apply_consensus_to_records.py` printed its whole JSON report on stdout, and
that report carries every counted report's stored title (`source_title`) three times over: once per
included row and twice more inside the record fields it proposes. Collection run 44609489525 printed
3,888 such lines, and on 2026-11-20 609 of the 683 retained runs of the two lanes that run it held
1,153,112 of them. Those titles are other people's words -- GitHub issue titles, forum and Q&A thread
titles -- and a log is not a place to republish them. What a reader of the log actually uses is the
row id, the source URL, the counts and the diagnostic categories, and those stay.

WHAT. `log_safe(value)` returns a copy of `value` with every key in THIRD_PARTY_TEXT_KEYS removed, at
any depth of mappings and lists. The input is never modified: the writer still writes the titles into
the record front matter it builds, and only the printed view loses them. The key is REMOVED rather
than blanked, so the absence is measurable -- a log that still contains `"source_title"` is a log that
still prints titles.

A CLOSED LIST, BY KEY. These are the fields that hold text taken from a report: the evidence store's
own (`report_title`, `parent_title`, `report_text_excerpt`, `matched_text`, `matched_context`,
`listing_card_title`), the record projections built from them (`source_title`), the update-linked
and recent-report files (`report_excerpt`) and the candidate shapes collectors pass around
(`thread_title`, `report_text`, `excerpt`, `observed_issue_summary`). A new field that holds report
text belongs here; test_log_title_hygiene drives the printing writers with a canary in every one.

Standard library only: the writers that use it run as bare scripts.
"""
from __future__ import annotations

from typing import Any

THIRD_PARTY_TEXT_KEYS = frozenset({
    "source_title",
    "report_title",
    "parent_title",
    "thread_title",
    "listing_card_title",
    "report_text",
    "report_text_excerpt",
    "report_excerpt",
    "excerpt",
    "matched_text",
    "matched_context",
    "observed_issue_summary",
})


def log_safe(value: Any) -> Any:
    """A copy of `value` without any THIRD_PARTY_TEXT_KEYS entry, at any depth. Never mutates."""
    if isinstance(value, dict):
        return {k: log_safe(v) for k, v in value.items() if k not in THIRD_PARTY_TEXT_KEYS}
    if isinstance(value, (list, tuple)):
        return [log_safe(v) for v in value]
    return value
