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

# Version anchored explicitly to Photoshop (the ONLY accepted signal). The version must
# immediately follow "Photoshop" (optionally "desktop"/"version"). Attribution is therefore
# POSITIVE -- a release is trusted because it is a Photoshop-anchored version, never merely
# because no denied product name happened to appear (a deny-list can never be exhaustive).
PS_ANCHORED_VERSION_RE = re.compile(
    rf"Photoshop\s+(?:desktop\s+)?(?:version\s+)?({_VERSION_CORE})\b", re.I
)
# A bare desktop-family version token, used ONLY to detect a *second, ambiguous* version in
# the same heading (never as an acceptance path).
BARE_VERSION_RE = re.compile(rf"\b({_VERSION_CORE})\b")

PS_ATTRIB_RE = re.compile(r"\bPhotoshop\b", re.I)
# Non-desktop Photoshop editions -> never a desktop record. The whole heading is screened
# (not just Photoshop-adjacent text): a non-desktop platform edition named ANYWHERE, or a
# parenthetical platform tag, disqualifies it. Feature prose ("adds web export", "iPad file
# compatibility") is NOT matched because the platform word must attach to the product via a
# leading "Photoshop [version] [on/for [the]]" run, an edition word, or parentheses.
PS_NON_DESKTOP_RE = re.compile(
    r"\bPhotoshop\s+(?:desktop\s+)?(?:\d[\d.]*\s+)?(?:(?:on|for)\s+(?:the\s+)?)?"
    r"(?:web(?:\s+app)?|browser|iPad(?:OS)?|Android|iOS|mobile|Chromebook|Chrome\s?OS)\b"
    r"|\bPhotoshop\s+(?:Elements|Express)\b"
    r"|\(\s*(?:web(?:\s+app)?|iPad(?:OS)?|Android|mobile)\b",
    re.I,
)
# Beta / prerelease markers -> stable-only, so these headings are rejected. Word separators
# are a class ([\s._-]+) so hyphenated / underscored / re-spaced spellings do not slip past
# (Unicode dashes are normalised to ASCII in _clean first). A bare "preview" is deliberately
# NOT a marker (it is a common feature word -- "AI preview", "preview panel"); only qualified
# prerelease forms count ("technology preview", "preview build", "preview release", ...).
BETA_RE = re.compile(
    r"\b(?:"
    r"beta|alpha|nightly|canary|insider|experimental|"
    r"pre[\s._-]*release(?:s)?|prerelease(?:s)?|"
    r"release[\s._-]+candidate(?:s)?|rc\d?|"
    r"(?:tech(?:nology)?|developer|dev)[\s._-]+preview(?:s)?|"
    r"preview[\s._-]+(?:build|release)s?|in[\s._-]+preview\b|"
    r"sneak[\s._-]+peek(?:s)?|"
    r"early[\s._-]+access|dev[\s._-]+build"
    r")\b",
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

# Release identity comes exclusively from the release HEADING (version AND date co-located),
# so a bundled dependency's / another product's / an older release's date in the surrounding
# prose can never be attributed to this release. A heading with no date fails closed.
HEADING_RE = re.compile(
    r"<h[1-6]\b[^>]*>(?P<heading>.*?)</h[1-6]>",
    re.I | re.S,
)

# Process-lifetime fetch cache so a run never double-fetches the (slow) Adobe page.
_FETCH_CACHE: dict[str, str] = {}


# Unicode hyphen/dash variants normalised to ASCII "-" so a non-breaking or typographic
# hyphen cannot smuggle a prerelease term past BETA_RE (e.g. "release‑candidate").
_DASH_TABLE = {cp: "-" for cp in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212)}


def _clean(html_fragment: str) -> str:
    text = re.sub(r"\s+", " ", strip_tags(html_fragment or "")).strip()
    return text.translate(_DASH_TABLE)


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
    """Return ``(iso_datetime, precision)`` for the release date a heading states, else
    ``("", "")``.

    Every date token in the heading is collected (full "Month DD, YYYY", ISO, and
    month+year). The result is deterministic and fails closed on ambiguity:

    - no date                                        -> ("", "")   (undated -> dropped)
    - exactly one calendar month across all tokens   -> that month, at ``"day"`` precision
      if a single day is stated for it, else ``"month"``;
    - more than one distinct (year, month), or conflicting days within the one month
      -> ("", "")   (ambiguous, e.g. a co-located historical/superseded date -> dropped).

    So a stray "fixes issue introduced March 3, 2024" or "supersedes the July 2, 2024
    build" next to the real "(May 2025 release)" can never win: the two distinct months
    make the date ambiguous and the release is dropped rather than mis-dated."""
    text = text or ""
    day_dates: set[tuple[str, str, str]] = set()   # (YYYY, MM, DD)
    month_dates: set[tuple[str, str]] = set()      # (YYYY, MM)
    for m in DATE_FULL_RE.finditer(text):
        month = MONTHS.get(m.group(1).lower(), "01")
        day_dates.add((m.group(3), month, f"{int(m.group(2)):02d}"))
    for m in DATE_ISO_RE.finditer(text):
        day_dates.add((m.group(1), m.group(2), m.group(3)))
    for m in DATE_MONTH_YEAR_RE.finditer(text):
        month = MONTHS.get(m.group(1).lower(), "01")
        month_dates.add((m.group(2), month))

    months = {(y, mo) for (y, mo, _d) in day_dates} | month_dates
    if len(months) != 1:
        return "", ""  # zero dates -> undated; >1 distinct month -> ambiguous
    year, month = next(iter(months))
    days = {d for (y, mo, d) in day_dates if (y, mo) == (year, month)}
    if len(days) > 1:
        return "", ""  # same month, conflicting days -> ambiguous
    if days:
        return f"{year}-{month}-{next(iter(days))}T00:00:00Z", "day"
    return f"{year}-{month}-01T00:00:00Z", "month"


def _heading_version(htext: str) -> str | None:
    """Extract the single Photoshop desktop version a release heading establishes, else
    ``None``.

    Acceptance is POSITIVE and fails closed. A version is returned only when:

    - the heading mentions Photoshop and is not a non-desktop edition or a beta/prerelease;
    - exactly one version is anchored directly to "Photoshop" (``PS_ANCHORED_VERSION_RE``);
    - no *other* distinct 2X.Y token appears in the heading (a second version -> ambiguous).

    A version that is NOT anchored to "Photoshop" is never accepted, even if it is the only
    version token present: that is how another product's version (InCopy 26.0, Aero 26.x, a
    Premiere/Illustrator interop mention, ...) is kept out without depending on an
    unmaintainable list of competitor names."""
    if not PS_ATTRIB_RE.search(htext):
        return None
    if PS_NON_DESKTOP_RE.search(htext) or BETA_RE.search(htext):
        return None

    anchored = {m.group(1) for m in PS_ANCHORED_VERSION_RE.finditer(htext)}
    if len(anchored) != 1:
        return None  # zero anchored -> not a Photoshop version; >1 -> ambiguous
    candidate = next(iter(anchored))
    # Reject if the heading also names a different distinct desktop version anywhere.
    others = {v for v in (m.group(1) for m in BARE_VERSION_RE.finditer(htext)) if v != candidate}
    return candidate if not others else None


def _record(
    source: dict[str, Any],
    source_url: str,
    version: str,
    published: str,
    date_precision: str,
) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
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
    records. Strictly heading-driven: a record is emitted ONLY from a release heading that
    establishes, in the heading text itself, an unambiguous desktop-Photoshop version AND a
    release date. Surrounding prose (feature notes, fixed-issues, dependency/system-
    requirement lines, references to other products or older releases) is never used to
    supply or upgrade a date, so a foreign or historical date can never be attributed to a
    release. Returns [] on DOM-miss (no fabrication)."""
    html = html or ""
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    cap = max(1, int(limit))

    for token in HEADING_RE.finditer(html):
        htext = _clean(token.group("heading"))
        if not htext:
            continue
        version = _heading_version(htext)
        if version is None or not STABLE_VERSION_RE.match(version):
            continue
        published, precision = _release_date(htext)
        if not published:
            continue  # fail closed: a release heading that states no date is dropped
        if version in seen:
            continue
        seen.add(version)
        records.append(_record(source, source_url, version, published, precision))
        if len(records) >= cap:
            break

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
