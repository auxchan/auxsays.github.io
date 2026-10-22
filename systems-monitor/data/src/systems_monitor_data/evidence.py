from __future__ import annotations

from typing import Any


SERIES_HUMAN_EVIDENCE_URLS = {
    "CES0000000001": "https://data.bls.gov/timeseries/CES0000000001",
    "LNS14000000": "https://data.bls.gov/timeseries/LNS14000000",
    "LNS11300000": "https://data.bls.gov/timeseries/LNS11300000",
    "JTS000000000000000JOL": "https://data.bls.gov/timeseries/JTS000000000000000JOL",
    "JTS000000000000000HIL": "https://data.bls.gov/timeseries/JTS000000000000000HIL",
    "DOL-UI-SA-INITIAL": "https://www.dol.gov/ui/data.pdf",
}


SOURCE_METHODOLOGY_URLS = {
    "bls-ces": "https://www.bls.gov/opub/hom/ces/home.htm",
    "bls-cps": "https://www.bls.gov/opub/hom/cps/calculation.htm",
    "bls-jolts": "https://www.bls.gov/opub/hom/jlt/presentation.htm",
    "dol-ui-claims": "https://oui.doleta.gov/unemploy/claims.asp",
}


def evidence_links(source_id: str, series_id: str, acquisition_url: str) -> dict[str, Any]:
    evidence_url = SERIES_HUMAN_EVIDENCE_URLS.get(series_id)
    methodology_url = SOURCE_METHODOLOGY_URLS.get(source_id)
    if evidence_url is None or methodology_url is None:
        raise ValueError("unregistered evidence or methodology mapping")
    if not acquisition_url.startswith("https://"):
        raise ValueError("acquisition provenance must use HTTPS")
    if source_id.startswith("bls-") and evidence_url == acquisition_url:
        raise ValueError("generic BLS acquisition endpoint cannot be human series evidence")
    return {
        "acquisitionProvenanceUrl": acquisition_url,
        "evidenceUrl": evidence_url,
        "methodologyUrl": methodology_url,
    }
