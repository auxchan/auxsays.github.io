"""Normalization helpers for official patch records."""
from __future__ import annotations

import datetime as dt
import html
import re
from typing import Any

def utc_now() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def slugify(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"&[a-z0-9#]+;", "-", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"

def strip_tags(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value or "", flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", value)).strip()

def first_nonempty(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""

def normalize_date(value: str | None) -> str:
    if not value:
        return utc_now()
    text = str(value).strip()
    if text.endswith("Z") and "T" in text:
        return text
    # RSS often returns RFC 822 date strings. Keep parse attempts conservative.
    try:
        from email.utils import parsedate_to_datetime
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo:
            parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return parsed.replace(microsecond=0).isoformat() + "Z"
    except Exception:
        pass
    # YYYY-MM-DD fallback
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1) + "T00:00:00Z"
    return text

def format_asset_size(size_bytes: int | str | None) -> str:
    try:
        size = float(size_bytes or 0)
    except (TypeError, ValueError):
        return ""
    if size <= 0:
        return ""
    units = ["B", "KB", "MB", "GB"]
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    if idx < 2:
        return f"{size:.0f} {units[idx]}"
    return f"{size:.0f} {units[idx]}" if size >= 100 else f"{size:.1f} {units[idx]}"

def summarize(text: str, max_chars: int = 420) -> str:
    clean = strip_markdown_for_summary(text or "")
    if not clean:
        return "Official release notes were detected, but no summary has been generated yet."
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:") + "."

def normalize_release_notes_body(text: str) -> str:
    """Normalize vendor/repository release notes for readable AUXSAYS display.

    GitHub auto-generated release notes are useful, but raw release bodies often
    include headings such as "What's Changed" and full PR URLs in every bullet.
    This helper preserves the evidence while making the rendered patch page more
    readable and less visually noisy.
    """
    value = str(text or "")
    # GitHub auto-generated release notes commonly start with "What's Changed".
    # In display typography this heading can render awkwardly as "What’ s".
    value = re.sub(r"(?im)^([#]{1,6})\s+What['’]s Changed\s*$", r"\1 Changes", value)

    # Convert raw GitHub PR URLs inside bullets into compact Markdown links.
    # Example: "by @name in https://github.com/org/repo/pull/123"
    # becomes: "by @name ([PR #123](https://github.com/org/repo/pull/123))".
    value = re.sub(
        r"\s+by\s+(@[A-Za-z0-9_.-]+)\s+in\s+(https://github\.com/[^\s)]+/pull/(\d+))",
        r" by \1 ([PR #\3](\2))",
        value,
    )
    value = re.sub(
        r"(?im)^\*\*Full Changelog\*\*:\s*(https://github\.com/[^\s]+)\s*$",
        r"[Full changelog](\1)",
        value,
    )
    return value

def strip_markdown_for_summary(text: str) -> str:
    """Create a compact plain-text summary from Markdown-ish release bodies."""
    clean = strip_tags(text or "")
    clean = normalize_release_notes_body(clean)
    clean = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", clean)
    clean = re.sub(r"(?m)^\s*[-*+]\s+", "", clean)
    clean = re.sub(r"`([^`]+)`", r"\1", clean)
    clean = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean
