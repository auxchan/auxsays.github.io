"""Normalization helpers for official patch records."""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    """Write text via a same-directory temp file + ``os.replace`` (atomic on one filesystem), so a
    crash or exception mid-write never leaves a half-written tracked record. Mirrors
    ``patch_collectors.base.atomic_write_text`` (kept per-package to avoid a lib->collectors import)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def split_front_matter(text: str) -> tuple[str | None, str]:
    """Split a Jekyll document into (front_matter_yaml_or_None, body). A delimiter is a line whose
    ENTIRE content is exactly ``---`` (trailing CR ignored) -- robust against ``-----`` rules,
    admonitions, and any ``---`` embedded in a serialized scalar, unlike ``text.split('---\\n')``.
    Mirrors ``patch_collectors.base.split_front_matter``. Returns (None, text) when no fence."""
    if not text.startswith("---"):
        return None, text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None, text
    for idx in range(1, len(lines)):
        if lines[idx].rstrip("\r\n") == "---":
            return "".join(lines[1:idx]), "".join(lines[idx + 1:])
    return None, text


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

# PRESENTATIONAL DATE TOKENS. Zendesk and most CMS templates render a machine date alongside a
# human one, and the human one is not a date at all -- it is a rendering instruction ("relative")
# or a relative phrase ("2 days ago"). `normalize_date` returns unparseable input VERBATIM, so any
# of these reaching it becomes a published date that looks real to every consumer downstream.
_NON_DATE_TOKENS = (
    "relative", "today", "yesterday", "tomorrow", "ago", "recently", "updated", "just now",
    "last week", "last month", "n/a", "na", "none", "null", "nil", "unknown", "tbd", "tba",
    "not available", "no date", "-", "--",
)

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_TEXT_DATE_RE = re.compile(
    r"\b(" + "|".join(_MONTH_NAMES) + r")\s+(\d{1,2}),\s*(\d{4})\b", re.I)


def strict_date(value: str | None) -> str:
    """Normalise a publication date, or return "" -- never a substitute, never a passthrough.

    `normalize_date` cannot be used for a publication date. It has two behaviours that are right
    for a feed timestamp and wrong for a release date: it returns unparseable text VERBATIM, and
    on empty input it returns `utc_now()` -- the COLLECTOR's runtime, presented as the moment the
    vendor shipped. The Office adapter already refuses it for exactly this reason
    (`_date_from_text` returns "" "not normalize_date('')... which would let a non-date table cell
    win"), and this is that rule made shareable rather than re-derived per adapter.

    Returns an ISO-8601 instant ending in Z, or "". Nothing else. A caller that cannot proceed
    without a date must reject its candidate; it must not invent one.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    # A presentational token is not a near-miss date; it is a different kind of thing.
    if lowered in _NON_DATE_TOKENS or any(
            lowered == t or lowered.endswith(" " + t) or lowered.startswith(t + " ")
            for t in ("ago", "today", "yesterday", "tomorrow", "relative")):
        return ""
    if any(tok in lowered for tok in (" ago", "ago ", "relative")):
        return ""
    # ISO 8601, with or without a zone. `fromisoformat` is used rather than a hand-rolled match
    # because an offset has to be APPLIED, not discarded: a hand-rolled parse that reads the
    # fields and ignores the trailing "+02:00" turns 16:58+02:00 into 16:58Z, which is a silent
    # two-hour error on a published date. Everything is converted to UTC; a naive value is taken
    # as already-UTC, which is what every source in this repo emits.
    iso_candidate = text.replace("Z", "+00:00") if text.endswith("Z") else text
    try:
        parsed = dt.datetime.fromisoformat(iso_candidate)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return parsed.replace(microsecond=0).isoformat() + "Z"
    # A date-shaped string fromisoformat refuses is an impossible calendar date, not a near miss.
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return ""
    # RFC 822, as feeds emit it.
    try:
        from email.utils import parsedate_to_datetime
        parsed = parsedate_to_datetime(text)
        if parsed is not None:
            if parsed.tzinfo:
                parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
            return parsed.replace(microsecond=0).isoformat() + "Z"
    except Exception:
        pass
    # "Month DD, YYYY", which vendors print in article bodies.
    m = _TEXT_DATE_RE.search(text)
    if m:
        try:
            return dt.datetime(int(m.group(3)), _MONTH_NAMES[m.group(1).lower()],
                               int(m.group(2))).isoformat() + "Z"
        except ValueError:
            return ""
    return ""


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
