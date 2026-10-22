from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


SHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAX_WORKBOOK_BYTES = 2_000_000
MAX_ROWS = 2_000


class CrosswalkError(ValueError):
    pass


@dataclass(frozen=True)
class BeaNaicsMapping:
    bea_summary_code: str
    bea_summary_label: str
    naics_2017_code: str
    naics_2017_label: str
    mapping_type: str


@dataclass(frozen=True)
class CrosswalkEvidence:
    source_url: str
    sha256: str
    byte_length: int
    bea_classification_level: str
    naics_vintage: str
    mappings: tuple[BeaNaicsMapping, ...]
    formulas_present: bool
    macros_present: bool
    external_links_present: bool


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.findall(".//a:t", SHEET_NS)) for item in root.findall("a:si", SHEET_NS)]


def _rows(archive: zipfile.ZipFile) -> list[dict[str, str]]:
    strings = _shared_strings(archive)
    root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in root.findall(".//a:sheetData/a:row", SHEET_NS):
        values = {}
        for cell in row.findall("a:c", SHEET_NS):
            ref = cell.get("r") or ""
            column = re.match(r"[A-Z]+", ref)
            value = cell.find("a:v", SHEET_NS)
            if column is None or value is None:
                continue
            text = strings[int(value.text)] if cell.get("t") == "s" else (value.text or "")
            values[column.group(0)] = text.strip()
        rows.append(values)
    if len(rows) > MAX_ROWS:
        raise CrosswalkError("BEA concordance exceeds row bound")
    return rows


def inspect_bea_concordance(path: Path, *, source_url: str, allowed_summary_codes: set[str]) -> CrosswalkEvidence:
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_WORKBOOK_BYTES:
        raise CrosswalkError("BEA concordance is absent or exceeds size bound")
    digest = hashlib.sha256(payload).hexdigest()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        macros = any(name.casefold().endswith("vbaproject.bin") for name in names)
        external_links = any("externallink" in name.casefold() for name in names)
        formulas = any(b"<f" in archive.read(name) for name in names if name.startswith("xl/worksheets/") and name.endswith(".xml"))
        if macros or external_links or formulas:
            raise CrosswalkError("BEA concordance contains executable/formula/external-link content")
        rows = _rows(archive)
    if not rows or "2017 North American Industry Classification System" not in rows[1].get("A", ""):
        raise CrosswalkError("BEA concordance classification vintage is not the expected 2017 NAICS")
    if rows[4].get("C") != "Summary" or rows[4].get("L") != "Related 2017 NAICS Codes":
        raise CrosswalkError("BEA concordance headers drifted")
    mappings = []
    seen = set()
    for row in rows[5:]:
        summary_code = row.get("C", "")
        naics_code = row.get("L", "")
        if summary_code not in allowed_summary_codes or not naics_code:
            continue
        identity = (summary_code, naics_code)
        if identity in seen:
            continue
        seen.add(identity)
        mappings.append(BeaNaicsMapping(
            bea_summary_code=summary_code,
            bea_summary_label=row.get("D", ""),
            naics_2017_code=naics_code,
            naics_2017_label=row.get("M", ""),
            mapping_type="ONE_TO_ONE" if summary_code == naics_code else "ONE_TO_MANY_COMPONENT",
        ))
    if not mappings or not all(any(row.bea_summary_code == code for row in mappings) for code in allowed_summary_codes):
        raise CrosswalkError("BEA concordance lacks an approved summary code")
    return CrosswalkEvidence(
        source_url=source_url,
        sha256=digest,
        byte_length=len(payload),
        bea_classification_level="SUMMARY_71",
        naics_vintage="2017_NAICS",
        mappings=tuple(mappings),
        formulas_present=False,
        macros_present=False,
        external_links_present=False,
    )


def validate_downstream_484_bridge(evidence: CrosswalkEvidence, bridge: dict) -> dict:
    required = {
        "bridgeVersion", "sourceVintage", "targetVintage", "sourceCode",
        "targetCode", "mappingType", "authorityUrls", "reviewStatus",
    }
    if not required.issubset(bridge):
        raise CrosswalkError("NAICS bridge is incomplete")
    if bridge["sourceVintage"] != "2017_NAICS" or bridge["targetVintage"] != "2022_NAICS":
        raise CrosswalkError("NAICS bridge vintage is invalid")
    if bridge["sourceCode"] != "484" or bridge["targetCode"] != "484":
        raise CrosswalkError("downstream bridge must preserve approved aggregate 484")
    if bridge["mappingType"] != "ONE_TO_ONE_UNCHANGED_AGGREGATE" or bridge["reviewStatus"] != "VERIFIED":
        raise CrosswalkError("downstream bridge is not accepted")
    if not any(row.bea_summary_code == "484" and row.naics_2017_code == "484" for row in evidence.mappings):
        raise CrosswalkError("BEA workbook does not support summary 484 to NAICS 2017 484")
    allowed_authorities = ("bea.gov", "census.gov", "bls.gov")
    if not all(url.startswith("https://") and any(host in url for host in allowed_authorities) for url in bridge["authorityUrls"]):
        raise CrosswalkError("downstream bridge authority is invalid")
    return {
        "bridgeVersion": bridge["bridgeVersion"],
        "beaSummaryCode": "484",
        "beaNaicsVintage": "2017_NAICS",
        "employmentNaicsCode": "484",
        "employmentNaicsVintage": "2022_NAICS",
        "mappingType": bridge["mappingType"],
        "crosswalkSha256": evidence.sha256,
    }
