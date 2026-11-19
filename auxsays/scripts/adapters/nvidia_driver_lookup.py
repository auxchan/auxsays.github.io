"""NVIDIA desktop driver official ingestion from NVIDIA's public driver-lookup service.

WHAT IT READS. Two NVIDIA-operated JSON services, both behind nvidia.com's own driver search:

* the driver lookup (gfwsl.geforce.com ... DriverManualLookup), one fixed query per family: one
  current desktop GPU, Windows 11, English, DCH packages, stable only, the 12 newest drivers. The
  family is chosen by NVIDIA's own query parameter (upCRD 0 = Game Ready, 1 = Studio) and then
  checked again on every row, by NVIDIA's own name for it (lib.nvidia_driver_identity);
* the per-driver details record (www.nvidia.com ... getDownloadDetails), read ONLY for a driver
  this source has not verified before. It returns the same listing object by download id, so it is
  both the record body and an independent cross-check: a details record that disagrees with the
  lookup about the same id is not published.

Version, branch ("Release"), release date and driver page URL are all SUPPLIED by NVIDIA in each
row; none is inferred. NVIDIA gives a date only, so the record carries the date at day precision
(midnight UTC, the convention every date-only source here uses) and says so in its body.

WHAT IT NEVER DOES. No installer download (the driver page is the download link a reader sees), no
browser identity (an honest client name), no retry loop, no query outside the pinned one, no
collection from any host but the two above. Records are official_only: no reports, no consensus.

REQUEST BUDGET per family per run: one lookup, plus at most DETAILS_PER_RUN details reads, each for a
driver not verified before. A source with nothing new makes exactly one request.

STOP RULES (each fails closed: the run publishes nothing for that family):

* access refusal -- HTTP 401, 403, 429 or 451, a bot challenge, an HTML page where JSON was expected,
  or a body that refuses automated access -- raises ``AccessRefused``. The refusal is recorded in
  this source's persisted scan state and in this process, so the other family makes no request in
  this run and neither family makes one in any later run. It stays suspended until a reviewed config
  change sets ``ingestion.access_refusal_cleared_at`` to a time after the refusal. Its message
  contains "access refused", which lib.state.classify_error records as error type ``blocked``.
* schema integrity -- a changed envelope, a request echo that is not the pinned query, a missing or
  malformed identity field, a date whose weekday contradicts it -- raises ``SchemaIntegrityStop``.
  A listing whose rows exist but none belongs to the family returns nothing and reports an
  extraction mismatch, so the source reads broken immediately rather than quiet.
* source authority -- a configured URL that is not the pinned one, a redirect to another host, or a
  driver page outside nvidia.com -- raises ``SourceAuthorityStop``. A new host needs its ownership,
  restrictions and robots policy checked by a person before collection continues.

Disabling the source, or any stop, never removes a record already published.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
from datetime import date, datetime, timezone
from typing import Any

from lib import nvidia_driver_identity as identity
from lib.http import fetch_text
from lib.normalize import utc_now

ADAPTER_ID = "nvidia_driver_lookup"

LOOKUP_ORIGIN = "https://gfwsl.geforce.com"
LOOKUP_PATH = "/services_toolkit/services/com/nvidia/services/AjaxDriverService.php"
DETAILS_ORIGIN = "https://www.nvidia.com"
DETAILS_PATH = "/services/com.nvidia.services/AEMDriversContent/getDownloadDetails"
# Hosts this adapter may contact. Anything else is a source-authority stop, never a fetch.
FETCH_HOSTS = frozenset({"gfwsl.geforce.com", "www.nvidia.com"})
# Hosts a record may link to (driver page, release-notes PDF). A notes link elsewhere is dropped.
LINK_HOSTS = frozenset({"www.nvidia.com", "us.download.nvidia.com"})
DETAILS_URL_RE = re.compile(r"https://www\.nvidia\.com/en-us/drivers/details/(\d{5,8})/")

# The pinned lookup query, in NVIDIA's own parameter names, without the family parameter.
# psid 120 / pfid 929: one current GeForce desktop GPU, so every row is a desktop package for a GPU
# both families support. osID 135: Windows 11. dch 1: DCH packages. beta 0: no beta drivers.
# isWHQL 0 means "do not filter on WHQL" (Studio rows are not flagged WHQL; see the identity module).
LOOKUP_QUERY = (
    ("func", "DriverManualLookup"),
    ("psid", "120"),
    ("pfid", "929"),
    ("osID", "135"),
    ("languageCode", "1033"),
    ("beta", "0"),
    ("isWHQL", "0"),
    ("dltype", "-1"),
    ("dch", "1"),
    ("sort1", "0"),
    ("numberOfResults", "12"),
)
# What NVIDIA must echo back in `Request` for the response to be the query we asked.
REQUEST_ECHO = {"psid": "120", "pfid": "929", "osID": "135", "beta": "0", "theSystemIsDc": "1"}

# An honest client name: no browser identity and no personal contact details.
USER_AGENT = "AUXSAYS-Patch-Ingest/1.2 (+https://auxsays.com)"
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
TIMEOUT_SECONDS = 30
MAX_BYTES = 2_000_000

# New drivers verified per family per run. Equal to the runner's default per-run write limit, so a
# backfill of the 12 listed drivers is paced exactly as fast as records can be written anyway.
DETAILS_PER_RUN = 2
VERIFIED_RETENTION = 60

# Every row field that IS the driver's identity. A row missing any of them is a schema change.
IDENTITY_FIELDS = ("ID", "Name", "Version", "Release", "ReleaseDateTime", "IsBeta", "IsWHQL", "IsCRD",
                   "IsDC", "DetailsURL")
# Fields the details record must report exactly as the lookup did.
CROSS_CHECK_FIELDS = IDENTITY_FIELDS + ("DownloadURLFileSize",)

PROVENANCE_KEYS = ("source_origin", "collection_method", "collection_authorization")

ACCESS_REFUSAL_CODES = frozenset({401, 403, 429, 451})
# Read only when a response is NOT the expected envelope, so release-note text can never trip it.
_REJECTION_RE = re.compile(
    r"access denied|forbidden|not authori[sz]ed|unauthori[sz]ed|too many requests|rate[\s-]*limit"
    r"|captcha|are you a robot|automated (?:access|requests?|traffic|queries)|request blocked"
    r"|you have been blocked", re.I)
_DATE_RE = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
                      r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2}), (\d{4})$")
_MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}
_VERSION_RE = re.compile(r"^\d{3,4}\.\d{2}$")
_BRANCH_RE = re.compile(r"^\d{3,4}$")
_SIZE_RE = re.compile(r"^\d{1,4}(?:\.\d{1,2})? (?:KB|MB|GB)$")

# A refusal seen by THIS process. Both families run in one process and share the service, so the
# second family must not make a request after the first was refused.
_PROCESS_REFUSAL: dict[str, str] | None = None


class AccessRefused(RuntimeError):
    """NVIDIA refused automated access. Classified `blocked`; suspends the method."""


class SchemaIntegrityStop(RuntimeError):
    """The response is not the shape this adapter was built and tested against."""


class SourceAuthorityStop(RuntimeError):
    """A host or URL this adapter was not approved for."""


def reset_process_state() -> None:
    """Forget a refusal seen in this process. For tests only; production never calls it."""
    global _PROCESS_REFUSAL
    _PROCESS_REFUSAL = None


def lookup_url(product_id: str) -> str:
    spec = identity.family(product_id)
    if spec is None:
        raise SourceAuthorityStop(f"no NVIDIA driver family is defined for product {product_id!r}")
    query = urllib.parse.urlencode(LOOKUP_QUERY + (("upCRD", spec["up_crd"]),))
    return f"{LOOKUP_ORIGIN}{LOOKUP_PATH}?{query}"


def details_url(download_id: str) -> str:
    payload = json.dumps({"ddID": str(download_id)}, separators=(",", ":"))
    return f"{DETAILS_ORIGIN}{DETAILS_PATH}?{urllib.parse.quote(payload, safe='')}"


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""


def _refusal(scan_state: dict[str, Any] | None, detail: str) -> AccessRefused:
    """Record a refusal (process + persisted scan state) and return the exception to raise."""
    global _PROCESS_REFUSAL
    at = utc_now()
    _PROCESS_REFUSAL = {"at": at, "detail": detail}
    if isinstance(scan_state, dict):
        scan_state["access_refused"] = {"at": at, "detail": detail}
    return AccessRefused(f"Access refused by the official NVIDIA source ({detail}); collection is "
                         "suspended until a reviewed config change clears it")


def _parse_instant(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _check_suspension(scan_state: dict[str, Any] | None, ingestion: dict[str, Any]) -> None:
    global _PROCESS_REFUSAL
    stored = (scan_state or {}).get("access_refused") if isinstance(scan_state, dict) else None
    if isinstance(stored, dict) and stored.get("at"):
        refused_at = _parse_instant(stored.get("at"))
        cleared_at = _parse_instant(ingestion.get("access_refusal_cleared_at"))
        # Cleared only by an explicit, later, parseable timestamp. Anything else keeps it suspended.
        if refused_at is not None and cleared_at is not None and cleared_at > refused_at:
            scan_state.pop("access_refused", None)
        else:
            raise AccessRefused(
                f"Access refused by the official NVIDIA source on {str(stored.get('at'))[:10]} "
                f"({stored.get('detail') or 'refusal'}); collection stays suspended until a reviewed "
                "config change clears it")
    if _PROCESS_REFUSAL is not None:
        detail = f"refused earlier in this run: {_PROCESS_REFUSAL.get('detail')}"
        if isinstance(scan_state, dict):
            scan_state["access_refused"] = {"at": _PROCESS_REFUSAL.get("at") or utc_now(),
                                            "detail": detail}
        raise AccessRefused(f"Access refused by the official NVIDIA source ({detail}); no request "
                            "was made for this family")


def _get_json(url: str, scan_state: dict[str, Any] | None) -> Any:
    host = _host(url)
    if host not in FETCH_HOSTS:
        raise SourceAuthorityStop(f"refusing to contact unapproved host {host!r}")
    try:
        result = fetch_text(url, timeout=TIMEOUT_SECONDS, headers=REQUEST_HEADERS, retries=0,
                            max_bytes=MAX_BYTES)
    except RuntimeError as exc:
        message = str(exc)
        code = re.search(r"\bHTTP (\d{3})\b", message)
        if code and int(code.group(1)) in ACCESS_REFUSAL_CODES:
            raise _refusal(scan_state, f"HTTP {code.group(1)}") from None
        if "Browser challenge" in message:
            raise _refusal(scan_state, "bot challenge") from None
        raise
    final_host = _host(result.final_url or url)
    if final_host != host:
        raise SourceAuthorityStop(f"the NVIDIA service redirected from {host!r} to {final_host!r}")
    text = (result.text or "").lstrip("\ufeff").strip()
    if text.startswith("<"):
        raise _refusal(scan_state, "an HTML page was returned where JSON was expected")
    try:
        return json.loads(text)
    except ValueError:
        if _REJECTION_RE.search(text[:4000]):
            raise _refusal(scan_state, "the response refused automated access") from None
        raise SchemaIntegrityStop("the NVIDIA service returned a body that does not parse as JSON "
                                  "(parse stop)") from None


def _rejected(payload: Any) -> bool:
    try:
        return bool(_REJECTION_RE.search(json.dumps(payload)[:4000]))
    except (TypeError, ValueError):
        return False


def _decode(value: Any) -> str:
    return urllib.parse.unquote(str(value if value is not None else "")).strip()


def _decoded_info(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SchemaIntegrityStop("a listing row has no downloadInfo object (parse stop)")
    missing = [field for field in IDENTITY_FIELDS if field not in raw or raw.get(field) in (None, "")]
    if missing:
        raise SchemaIntegrityStop(f"a listing row is missing identity fields {missing} (parse stop)")
    info = dict(raw)
    for key in IDENTITY_FIELDS:
        info[key] = str(info[key]).strip()
    for key in ("Name", "OSName", "ReleaseNotes", "OtherNotes", "DownloadURLFileSize"):
        if key in info:
            info[key] = _decode(info.get(key))
    info["OSList"] = [_decode(item.get("OSName")) for item in (raw.get("OSList") or [])
                      if isinstance(item, dict) and item.get("OSName")]
    return info


def release_date(value: Any) -> date:
    """NVIDIA's 'Wed Nov 04, 2026' as a date. The weekday must agree with the date it names."""
    match = _DATE_RE.match(str(value or "").strip())
    if not match:
        raise SchemaIntegrityStop(f"release date {value!r} is not in NVIDIA's listing format (parse stop)")
    weekday, month, day, year = match.groups()
    try:
        parsed = date(int(year), _MONTHS[month], int(day))
    except ValueError:
        raise SchemaIntegrityStop(f"release date {value!r} is not a calendar date (parse stop)") from None
    if parsed.strftime("%a") != weekday:
        raise SchemaIntegrityStop(f"release date {value!r} names the wrong weekday (parse stop)")
    return parsed


def _validate_identity(info: dict[str, Any]) -> None:
    """An accepted row's identity fields must be well formed; a malformed one is a schema change."""
    if not info["ID"].isdigit():
        raise SchemaIntegrityStop(f"download id {info['ID']!r} is not numeric (parse stop)")
    if not _VERSION_RE.match(info["Version"]):
        raise SchemaIntegrityStop(f"driver version {info['Version']!r} is not NNN.NN (parse stop)")
    if not _BRANCH_RE.match(info["Release"]):
        raise SchemaIntegrityStop(f"driver branch {info['Release']!r} is not numeric (parse stop)")
    release_date(info["ReleaseDateTime"])
    url = info["DetailsURL"]
    if _host(url) != "www.nvidia.com":
        raise SourceAuthorityStop(f"driver page for {info['ID']} is on host {_host(url)!r}, not www.nvidia.com")
    match = DETAILS_URL_RE.fullmatch(url)
    if not match or match.group(1) != info["ID"]:
        raise SchemaIntegrityStop(f"driver page {url!r} does not name download id {info['ID']} (parse stop)")


def _lookup_rows(payload: Any, product_id: str, scan_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("IDS"), list) \
            or not isinstance(payload.get("Request"), list):
        if _rejected(payload):
            raise _refusal(scan_state, "the lookup response refused automated access")
        raise SchemaIntegrityStop("the lookup response is not the expected Success/IDS/Request "
                                  "envelope (parse stop)")
    success = str(payload.get("Success") or "").strip()
    rows = payload["IDS"]
    if not success.isdigit() or int(success) != len(rows):
        raise SchemaIntegrityStop(f"the lookup says Success={success!r} but carries {len(rows)} rows "
                                  "(parse stop)")
    echo = payload["Request"][0] if payload["Request"] and isinstance(payload["Request"][0], dict) else {}
    expected = dict(REQUEST_ECHO, theUserRequestedCRD=identity.FAMILIES[product_id]["up_crd"])
    wrong = {key: echo.get(key) for key, value in expected.items() if str(echo.get(key)) != value}
    if wrong:
        raise SchemaIntegrityStop(f"the lookup did not answer the pinned query: {wrong} (parse stop)")
    return [_decoded_info((row or {}).get("downloadInfo") if isinstance(row, dict) else None)
            for row in rows]


def _details_info(payload: Any, download_id: str, scan_state: dict[str, Any] | None) -> dict[str, Any]:
    details = payload.get("driverDetails") if isinstance(payload, dict) else None
    rows = details.get("IDS") if isinstance(details, dict) else None
    if not isinstance(rows, list):
        if _rejected(payload):
            raise _refusal(scan_state, "the details response refused automated access")
        raise SchemaIntegrityStop("the details response is not the expected driverDetails/IDS "
                                  "envelope (parse stop)")
    if str(details.get("Success") or "").strip() != "1" or len(rows) != 1:
        raise SchemaIntegrityStop(f"the details response for {download_id} does not hold exactly one "
                                  "driver (parse stop)")
    info = _decoded_info((rows[0] or {}).get("downloadInfo") if isinstance(rows[0], dict) else None)
    if info["ID"] != str(download_id):
        raise SchemaIntegrityStop(f"asked for download id {download_id}, got {info['ID']} (parse stop)")
    return info


def _provenance(source: dict[str, Any]) -> dict[str, str]:
    block = (source.get("ingestion") or {}).get("provenance")
    values = {key: str((block or {}).get(key) or "").strip() for key in PROVENANCE_KEYS} \
        if isinstance(block, dict) else {}
    missing = [key for key in PROVENANCE_KEYS if not values.get(key)]
    if missing:
        # No record may be written without its provenance.
        raise SchemaIntegrityStop(f"source config is missing provenance {missing} (config parse stop)")
    return values


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


# --- record body: facts and links only ------------------------------------------------------------

_LINK_RE = re.compile(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>", re.I)
_SECTION_RE = re.compile(r"<(?:b|strong)>(.*?)</(?:b|strong)>(.*?)(?=<(?:b|strong)>|$)", re.I | re.S)
_ITEM_RE = re.compile(r"<li\b[^>]*>(.*?)</li>", re.I | re.S)


def _text(fragment: str) -> str:
    value = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def fixed_issues(notes_html: str) -> list[str]:
    """The items NVIDIA lists under its own "Fixed ... Bugs" headings, as plain text. 'N/A' dropped."""
    items: list[str] = []
    for heading, block in _SECTION_RE.findall(notes_html or ""):
        if not re.match(r"\s*fixed\b.*\bbugs?\b", _text(heading), re.I):
            continue
        for item in _ITEM_RE.findall(block):
            text = _text(item)
            if text and text.upper() != "N/A" and text not in items:
                items.append(text)
    return items


def game_ready_titles(notes_html: str) -> str:
    """The titles NVIDIA names in its own "Game Ready for ..." heading, or ''."""
    for heading, _block in _SECTION_RE.findall(notes_html or ""):
        match = re.match(r"\s*Game Ready for\s+(.+)$", _text(heading), re.I)
        if match:
            return match.group(1).strip()
    return ""


def release_notes_pdf(other_notes_html: str, version: str) -> str:
    """NVIDIA's release-notes PDF link for this version, on an NVIDIA host, or ''."""
    for href in _LINK_RE.findall(other_notes_html or ""):
        if _host(href) in LINK_HOSTS and href.lower().endswith(".pdf") and f"/{version}/" in href:
            return href
    return ""


def _record(source: dict[str, Any], product_id: str, info: dict[str, Any], prov: dict[str, str]) -> dict[str, Any]:
    spec = identity.FAMILIES[product_id]
    version, download_id, branch = info["Version"], info["ID"], info["Release"]
    released = release_date(info["ReleaseDateTime"]).isoformat()
    page = info["DetailsURL"]
    software = str(source.get("software") or spec["listing_name"])
    notes_pdf = release_notes_pdf(str(info.get("OtherNotes") or ""), version)
    fixes = fixed_issues(str(info.get("ReleaseNotes") or ""))
    game_ready_for = game_ready_titles(str(info.get("ReleaseNotes") or "")) if product_id == identity.GAME_READY else ""
    size = str(info.get("DownloadURLFileSize") or "").strip()
    size = size if _SIZE_RE.match(size) else ""
    whql = str(info.get("IsWHQL") or "").strip() == "1"
    systems = ", ".join(info.get("OSList") or []) or str(info.get("OSName") or "")

    lines = [f"NVIDIA driver listing: {spec['listing_name']} {version}", "",
             f"- Driver family: {spec['label']} (as named by NVIDIA)",
             f"- Driver branch: R{branch}",
             f"- Release date: {released} (NVIDIA lists the date only, no time of day)",
             f"- WHQL: {'certified' if whql else 'not flagged in NVIDIA listing'}",
             f"- Package: desktop, DCH{', for ' + systems if systems else ''}"]
    if size:
        lines.append(f"- Installer size: {size}")
    if game_ready_for:
        lines.append(f"- NVIDIA lists it as Game Ready for: {game_ready_for}")
    if fixes:
        lines += ["", "Fixed issues NVIDIA lists for this driver:"] + [f"- {item}" for item in fixes]
    lines += ["", f"Official driver page: {page}"]
    if notes_pdf:
        lines.append(f"Official release notes (PDF): {notes_pdf}")
    lines += ["", "AUXSAYS note: this is official NVIDIA driver metadata, not community consensus. "
                  "Game Ready and Studio drivers that share a version number are separate records."]

    official_sources = [{
        "label": "NVIDIA driver page",
        "url": page,
        "source_type": "download_portal",
        "trust_level": "official",
        "extraction_status": "version_metadata_captured",
    }]
    if notes_pdf:
        official_sources.append({
            "label": "NVIDIA release notes (PDF)",
            "url": notes_pdf,
            "source_type": "release_notes",
            "trust_level": "official",
            "extraction_status": "linked_not_captured",
        })
    return {
        # Identity is (product_id, update_version); the download id is provenance, not identity.
        "record_id": f"{ADAPTER_ID}:{product_id}:{version}",
        "company_id": source["company_id"],
        "product_id": product_id,
        "company": source.get("company") or "NVIDIA",
        "software": software,
        "category": source.get("public_category"),
        "version": version,
        "title": f"{software} {version}",
        "logo_text": spec["badge"],
        "published_at": f"{released}T00:00:00Z",
        "source_url": page,
        "official_url": page,
        "official_patch_notes_source_url": page,
        "download_url": page,
        "file_size": size,
        "file_size_note": ("Installer size as NVIDIA lists it for the Windows desktop DCH package."
                           if size else "NVIDIA's listing did not state an installer size."),
        "file_size_status": "captured" if size else "not_provided_by_source",
        "body": "\n".join(lines),
        "checksums_body": "",
        "summary": (f"NVIDIA lists {spec['listing_name']} {version} (branch R{branch}) for Windows "
                    f"desktop, released {released}."),
        "source_type": "download_portal",
        "official_source_type": "download_portal",
        "official_note_status": "official_source_captured",
        "official_note_label": "Official driver listing",
        "capture_status": "captured-from-official-nvidia-driver-listing",
        "official_summary": f"NVIDIA published {spec['listing_name']} {version} on {released}.",
        "official_source_classification_note": (
            "NVIDIA's driver listing is treated as an official download-portal source. It confirms "
            "the driver family, version, branch and release date; community evidence remains separate."),
        "official_sources": official_sources,
        "driver_family": spec["label"],
        "driver_branch": f"R{branch}",
        "nvidia_download_id": download_id,
        "release_date_precision": "day",
        **prov,
    }


def fetch(source: dict[str, Any], limit: int = 12, scan_state: dict[str, Any] | None = None,
          probe: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    product_id = str(source.get("product_id") or "").strip()
    if product_id not in identity.DRIVER_PRODUCTS:
        raise SourceAuthorityStop(f"{product_id!r} is not an NVIDIA driver family product")
    ingestion = source.get("ingestion") or {}
    prov = _provenance(source)
    url = lookup_url(product_id)
    configured = str(ingestion.get("api_url") or "").strip()
    if configured != url:
        raise SourceAuthorityStop("ingestion.api_url is not the pinned NVIDIA lookup query for this "
                                  "family; a changed host or query needs review before collection")
    _check_suspension(scan_state, ingestion)

    rows = _lookup_rows(_get_json(url, scan_state), product_id, scan_state)
    counts: dict[str, int] = {}
    accepted: list[dict[str, Any]] = []
    for info in rows:
        ok, reason = identity.listing_matches(product_id, info)
        if not ok:
            counts[reason] = counts.get(reason, 0) + 1
            continue
        _validate_identity(info)
        accepted.append(info)

    # One version, two download ids in one family: ambiguous, so neither is published.
    by_version: dict[str, list[dict[str, Any]]] = {}
    for info in accepted:
        by_version.setdefault(info["Version"], []).append(info)
    ambiguous = {version for version, infos in by_version.items() if len({i["ID"] for i in infos}) > 1}
    if ambiguous:
        counts["ambiguous_version"] = sum(len(by_version[v]) for v in ambiguous)
    unique: dict[str, dict[str, Any]] = {}
    for info in accepted:
        if info["Version"] not in ambiguous:
            unique.setdefault(info["Version"], info)
    ordered = sorted(unique.values(), key=lambda i: (release_date(i["ReleaseDateTime"]),
                                                     _version_key(i["Version"]), int(i["ID"])),
                     reverse=True)

    verified = scan_state.setdefault("details_verified", []) if isinstance(scan_state, dict) else []
    budget = DETAILS_PER_RUN
    records: list[dict[str, Any]] = []
    withheld = 0
    for info in ordered:
        if len(records) >= max(1, int(limit or 1)):
            break
        body_info = info
        if info["ID"] not in verified:
            if budget <= 0:
                withheld += 1
                continue
            budget -= 1
            details = _details_info(_get_json(details_url(info["ID"]), scan_state), info["ID"], scan_state)
            disagree = [field for field in CROSS_CHECK_FIELDS
                        if str(details.get(field) or "") != str(info.get(field) or "")]
            if disagree:
                counts["details_disagree"] = counts.get("details_disagree", 0) + 1
                continue
            verified.insert(0, info["ID"])
            del verified[VERIFIED_RETENTION:]
            body_info = details
        records.append(_record(source, product_id, body_info, prov))

    if probe is not None:
        probe["upstream_candidates"] = len(rows)
        # Rows were listed and none could be published: the extractor no longer fits the source.
        probe["extraction_mismatch"] = bool(rows) and not records
        probe["nvidia"] = {"listed": len(rows), "accepted": len(ordered), "withheld_for_next_run": withheld,
                           "skipped": dict(sorted(counts.items())),
                           "details_requests": DETAILS_PER_RUN - budget}
    return records
