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
    clean = re.sub(r"\s+", " ", strip_tags(text or "")).strip()
    if not clean:
        return "Official release notes were detected, but no summary has been generated yet."
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:") + "."
