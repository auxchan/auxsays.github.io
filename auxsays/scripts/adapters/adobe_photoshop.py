"""Dedicated Adobe Photoshop (desktop) official release-notes adapter.

Photoshop desktop is versioned on its own track (26.0 for the 2025 line, 27.0 for
2026, monthly minors such as 26.11, and occasional dot-dot bugfix builds such as
26.10.1). Attribution and identity are extracted deterministically from the official
Adobe HelpX "Photoshop desktop release notes" page; nothing is inferred.

This is a *narrowly scoped* Photoshop adapter, deliberately separate from the
Premiere-oriented ``adobe_release_notes`` adapter (which hard-codes Premiere version
patterns and canned Premiere bodies) and from the Acrobat DC adapter. Keeping it
separate means this work cannot alter Premiere or Acrobat behaviour.

Fail-closed contract (a release becomes a record ONLY when all hold):

- Explicit **desktop Photoshop** attribution. A release heading must name Photoshop
  and carry a Photoshop-family desktop version. Notes whose subject is another
  product (Premiere, After Effects, Lightroom, Illustrator, InDesign, Acrobat,
  Firefly, Bridge, a Camera-Raw-only note, the generic Creative Cloud desktop app),
  or a non-desktop Photoshop variant (Photoshop on the web / on iPad / Elements /
  Express), never produce a Photoshop desktop record.
- **Exact stable version.** Two- or three-component desktop version (``2X.Y`` /
  ``2X.Y.Z``). Year-only ("2025"), bare-major ("26"), marketing ("latest"), and any
  beta / prerelease / technology-preview / release-candidate build are rejected.
- **Deterministic official release date.** A full date ("October 14, 2025" / ISO) or,
  at Adobe's canonical Photoshop granularity, a month + year ("October 2025"). A
  release whose date cannot be established is skipped -- never dated by inference.
- **Ambiguity fails closed.** A heading that names more than one distinct version, or
  a release whose identity cannot be pinned, is skipped rather than guessed.
- **Official ingestion only.** Records never carry consensus / community-report
  fields, so ``write_update_record`` derives ``evidence_state=official_only``. No
  consensus language, no fabricated user evidence, report count stays zero.

The adapter exposes the standard ``fetch(source, limit)`` contract and returns at most
``limit`` records, newest-first as the page presents them. It raises when every
configured official URL fails transport, so source health reflects an unreachable
source (the current state of the HelpX page from datacenter / CI egress) rather than
silently reporting "no records".
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from lib.http import fetch_text
from lib.normalize import strip_tags, first_nonempty

PRODUCT_ID = "adobe-photoshop"
SOFTWARE_LABEL = "Adobe Photoshop"

# Desktop Photoshop versions: 2X.Y or 2X.Y.Z (26.0, 26.11, 26.10.1, 27.0, ...). The
# leading 2X (20-29) is the desktop app major line and deliberately excludes bare
# four-digit years (no interior dot) and single majors.
_VERSION_CORE = r"2[0-9]\.\d{1,2}(?:\.\d{1,2})?"
STABLE_VERSION_RE = re.compile(rf"^{_VERSION_CORE}$")

# Version anchored explicitly to Photoshop (strongest signal).
PS_ANCHORED_VERSION_RE = re.compile(
    rf"Photoshop\s+(?:desktop\s+)?(?:version\s+)?({_VERSION_CORE})\b", re.I
)
# Version anchored to a generic "version"/"v" token (used only inside an
# already-Photoshop-attributed section).
GENERIC_VERSION_RE = re.compile(rf"(?:\bversion\s+|\bv\.?\s*)({_VERSION_CORE})\b", re.I)
# A bare desktop-family version token (used only inside a Photoshop-attributed heading).
BARE_VERSION_RE = re.compile(rf"\b({_VERSION_CORE})\b")

PS_ATTRIB_RE = re.compile(r"\bPhotoshop\b", re.I)
# Non-desktop / non-Photoshop-desktop variants -> never a desktop record.
PS_NON_DESKTOP_RE = re.compile(
    r"\bPhotoshop\s+(?:on\s+the\s+web|on\s+iPad|for\s+iPad|web|Elements|Express|Beta|\(beta\))\b",
    re.I,
)
# Other Adobe products; a heading about one of these (without Photoshop) is skipped.
OTHER_PRODUCT_RE = re.compile(
    r"\b(?:Premiere(?:\s+Pro)?|After\s+Effects|Lightroom(?:\s+Classic)?|Illustrator|"
    r"InDesign|Acrobat|Firefly|Bridge|Animate|Audition|Dreamweaver|Camera\s+Raw|"
    r"Substance|Fresco|Adobe\s+XD|Media\s+Encoder|Character\s+Animator|Dimension)\b",
    re.I,
)
# Beta / prerelease markers -> stable-only, so these headings are rejected.
BETA_RE = re.compile(
    r"\b(?:beta|prerelease|pre-release|tech(?:nology)?\s+preview|release\s+candidate|rc\d?)\b",
    re.I,
)

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
}
_MONTH_ALT = "|".join(MONTHS)
DATE_FULL_RE = re.compile(rf"\b({_MONTH_ALT})\s+(\d{{1,2}}),\s+(20\d{{2}})\b", re.I)
DATE_ISO_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
DATE_MONTH_YEAR_RE = re.compile(rf"\b({_MONTH_ALT})\s+(20\d{{2}})\b", re.I)

# Headings set / clear release context; table rows and list items carry the date/detail.
SECTION_TOKEN_RE = re.compile(
    r"<h[1-6]\b[^>]*>(?P<heading>.*?)</h[1-6]>"
    r"|<tr\b[^>]*>(?P<row>.*?)</tr>"
    r"|<li\b[^>]*>(?P<li>.*?)</li>"
    r"|<p\b[^>]*>(?P<p>.*?)</p>",
    re.I | re.S,
)

# Process-lifetime fetch cache so a run never double-fetches the (slow) Adobe page.
_FETCH_CACHE: dict[str, str] = {}


def _clean(html_fragment: str) -> str:
    return re.sub(r"\s+", " ", strip_tags(html_fragment or "")).strip()


def _request_options(source: dict[str, Any]) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    request = ingestion.get("request", {}) or {}
    headers = request.get("headers") or {}
    return {
        "timeout": int(request.get("timeout_seconds") or 30),
        "retries": int(request.get("retries") or 1),
        "backoff_seconds": float(request.get("backoff_seconds") or 2.5),
        "max_bytes": int(request.get("max_bytes") or 750_000),
        "headers": headers if isinstance(headers, dict) else {},
    }


def _source_candidates(source: dict[str, Any]) -> list[str]:
    ingestion = source.get("ingestion", {}) or {}
    clean: list[str] = []
    for url in (ingestion.get("official_url"), ingestion.get("secondary_official_url")):
        if isinstance(url, str) and url.strip() and url.strip() not in clean:
            clean.append(url.strip())
    return clean


def _release_date(text: str) -> tuple[str, str]:
    """Return ``(iso_datetime, precision)`` for the first deterministic date, else
    ``("", "")``. ``precision`` is ``"day"`` for a full/ISO date, ``"month"`` for a
    month+year date (Adobe's canonical Photoshop granularity). A month+year is
    normalised to the first of the month; the ``"month"`` precision flag records that
    the day was not stated (so downstream text never implies a false day)."""
    text = text or ""
    full = DATE_FULL_RE.search(text)
    if full:
        month = MONTHS.get(full.group(1).lower(), "01")
        return f"{full.group(3)}-{month}-{int(full.group(2)):02d}T00:00:00Z", "day"
    iso = DATE_ISO_RE.search(text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}T00:00:00Z", "day"
    my = DATE_MONTH_YEAR_RE.search(text)
    if my:
        month = MONTHS.get(my.group(1).lower(), "01")
        return f"{my.group(2)}-{month}-01T00:00:00Z", "month"
    return "", ""


def _heading_version(htext: str) -> str | None:
    """Extract the single Photoshop desktop version a release heading establishes.

    Returns the version string, or ``None`` if the heading is not an unambiguous
    Photoshop desktop release heading (wrong/absent attribution, a non-desktop
    variant, a beta/prerelease marker, no desktop version, or more than one distinct
    version named -> fail closed)."""
    if not PS_ATTRIB_RE.search(htext):
        return None
    if PS_NON_DESKTOP_RE.search(htext) or BETA_RE.search(htext):
        return None

    anchored = {m.group(1) for m in PS_ANCHORED_VERSION_RE.finditer(htext)}
    if len(anchored) == 1:
        candidate = next(iter(anchored))
        # Reject if the heading names an additional distinct desktop version elsewhere.
        others = {v for v in (m.group(1) for m in BARE_VERSION_RE.finditer(htext)) if v != candidate}
        return candidate if not others else None
    if anchored:  # more than one Photoshop-anchored version -> ambiguous
        return None

    bare = {m.group(1) for m in BARE_VERSION_RE.finditer(htext)}
    if len(bare) == 1:
        return next(iter(bare))
    return None


def _record(
    source: dict[str, Any],
    source_url: str,
    version: str,
    published: str,
    date_precision: str,
) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    software = source.get("software") and f"Adobe {source['software']}" or SOFTWARE_LABEL
    if str(source.get("software") or "").strip().lower() == "photoshop":
        software = SOFTWARE_LABEL
    digest = hashlib.sha256(
        (source_url + PRODUCT_ID + version + published).encode("utf-8")
    ).hexdigest()[:16]

    date_str = published[:10] if published else ""
    if date_precision == "month" and published:
        # Honest month-granularity phrasing; never implies a specific day.
        month_names = {v: k.title() for k, v in MONTHS.items()}
        month_label = f"{month_names.get(published[5:7], '')} {published[0:4]}".strip()
    else:
        month_label = ""

    official_sources = []
    for label, url in (
        ("Adobe Photoshop desktop release notes", ingestion.get("official_url")),
        ("Adobe Photoshop release notes (archive)", ingestion.get("secondary_official_url")),
    ):
        if isinstance(url, str) and url.strip():
            official_sources.append({
                "label": label,
                "url": url.strip(),
                "source_type": "release_notes",
                "trust_level": "official",
                "extraction_status": "summary_captured" if url.strip() == source_url else "reference_only",
            })

    if date_precision == "day" and date_str:
        date_clause = f" Release date {date_str}."
        summary_date = f" ({date_str})."
    elif date_precision == "month" and month_label:
        date_clause = f" Released {month_label}."
        summary_date = f" (released {month_label})."
    else:
        date_clause = ""
        summary_date = "."

    body = (
        f"{SOFTWARE_LABEL} {version} (desktop)."
        + date_clause
        + " Official Adobe Photoshop desktop release note; applies to Adobe Photoshop (desktop)."
    )
    official_summary = (
        f"Adobe released {SOFTWARE_LABEL} {version} for desktop"
        + summary_date
    )

    return {
        "record_id": f"adobe:{PRODUCT_ID}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": PRODUCT_ID,
        "company": source["company"],
        "software": SOFTWARE_LABEL,
        "category": source.get("public_category"),
        "version": version,
        "title": first_nonempty(f"{SOFTWARE_LABEL} {version}", SOFTWARE_LABEL),
        "published_at": published,
        "source_url": source_url,
        "official_url": source_url,
        "download_url": "",
        "file_size": "",
        "file_size_status": "not_provided_by_source",
        "file_size_note": (
            "Adobe Photoshop updates are Adobe-managed (Creative Cloud desktop app); "
            "the release notes do not expose standalone installer/package size metadata."
        ),
        "body": body,
        "checksums_body": "",
        "summary": "",
        "source_type": "release_notes",
        "official_source_type": "release_notes",
        "official_note_status": "release_notes_captured",
        "official_note_label": "Official Photoshop release notes",
        "official_sources": official_sources,
        "capture_status": "captured-from-official-adobe-photoshop-release-notes",
        "official_summary": official_summary,
        # Structured, non-inferred identity.
        "target_version": version,
        "target_platform": "Windows, macOS",
        "date_precision": date_precision,
        "applicability": [PRODUCT_ID],
        "applies_to_label": SOFTWARE_LABEL,
    }


def _records_from_photoshop_release_notes(
    source: dict[str, Any],
    source_url: str,
    html: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Pure parser (no network): Adobe Photoshop desktop release notes -> official-only
    records. Heading-driven: each Photoshop desktop release heading opens a candidate
    whose date is completed from the heading or the following blocks; a candidate is
    emitted only when version + date are both established. Returns [] on DOM-miss (no
    fabrication)."""
    html = html or ""
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    cap = max(1, int(limit))

    pending: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        candidate, pending = pending, None
        version = candidate["version"]
        published = candidate["published"]
        precision = candidate["precision"]
        if not (version and published and STABLE_VERSION_RE.match(version)):
            return  # fail closed: incomplete or malformed identity
        if version in seen:
            return
        seen.add(version)
        records.append(_record(source, source_url, version, published, precision))

    for token in SECTION_TOKEN_RE.finditer(html):
        if len(records) >= cap:
            break
        heading = token.group("heading")
        if heading is not None:
            htext = _clean(heading)
            if not htext:
                continue
            version = _heading_version(htext)
            if version is not None:
                # A new, unambiguous Photoshop desktop release heading.
                flush()
                if len(records) >= cap:
                    break
                published, precision = _release_date(htext)
                pending = {"version": version, "published": published, "precision": precision}
            elif OTHER_PRODUCT_RE.search(htext) and not PS_ATTRIB_RE.search(htext):
                # Left Photoshop context for another product -> close any open release.
                flush()
            # Otherwise a subsection heading ("What's new", "Fixed issues") -> keep pending.
            continue

        block = token.group("row") or token.group("li") or token.group("p") or ""
        text = _clean(block)
        if not text or pending is None:
            continue
        # Complete a still-undated release from its body, and upgrade a heading's
        # month-granularity date to an exact day when the body states one. Never
        # downgrade or overwrite an already-established day date.
        published, precision = _release_date(text)
        if not published:
            continue
        current = pending.get("published")
        if not current or (pending.get("precision") == "month" and precision == "day"):
            pending["published"] = published
            pending["precision"] = precision

    flush()
    return records[:cap]


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    product_id = str(source.get("product_id") or "").strip()
    if product_id != PRODUCT_ID:
        return []  # dedicated to Photoshop desktop; never drives another product

    options = _request_options(source)
    candidates = _source_candidates(source)
    fetch_errors: list[str] = []

    for url in candidates:
        html = _FETCH_CACHE.get(url)
        final_url = url
        if html is None:
            try:
                result = fetch_text(url, **options)
            except Exception as exc:  # noqa: BLE001 - surface transport failures below
                fetch_errors.append(f"{url}: {exc}")
                continue
            html = result.text or ""
            final_url = result.final_url or url
            if not html.strip():
                fetch_errors.append(f"{url}: empty response")
                continue
            _FETCH_CACHE[url] = html
        records = _records_from_photoshop_release_notes(source, final_url, html, limit)
        if records:
            return records
        # Fetched OK but nothing parsed: try the next official URL.

    # Every candidate failed transport -> raise so source health reflects it. A
    # fetched-but-unparseable page returns [] (graceful, no fabrication).
    if candidates and len(fetch_errors) == len(candidates):
        raise RuntimeError("; ".join(fetch_errors[-2:]) or "adobe photoshop fetch failed")
    return []
