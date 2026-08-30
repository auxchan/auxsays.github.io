from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXPECTED_SOURCES = {"bls-ces", "bls-cps", "bls-jolts", "dol-ui-claims"}
EXPECTED_INDICATORS = {
    "US_LABOR_TOTAL_NONFARM_PAYROLLS",
    "US_LABOR_U3_UNEMPLOYMENT_RATE",
    "US_LABOR_FORCE_PARTICIPATION_RATE",
    "US_LABOR_INITIAL_UI_CLAIMS",
    "US_LABOR_JOB_OPENINGS",
    "US_LABOR_HIRES",
    "US_PRICES_CPI_U_ALL_ITEMS",
    "US_OUTPUT_REAL_GDP",
}
FORBIDDEN = ("fr" + "ed", "al" + "fr" + "ed")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class Registry:
    def __init__(self, config_root: Path):
        self.sources = load_json(config_root / "sources" / "sources.json")["sources"]
        self.indicators = load_json(config_root / "indicators" / "indicators.json")["indicators"]
        self.rights = load_json(config_root / "rights" / "rights.json")
        self.mappings = load_json(config_root / "mappings" / "mappings.json")
        self.validate()

    def validate(self) -> None:
        source_ids = {row["source_id"] for row in self.sources if row["enabled"]}
        if source_ids != EXPECTED_SOURCES:
            raise ValueError(f"enabled source scope mismatch: {source_ids}")
        indicator_ids = {row["indicator_id"] for row in self.indicators}
        if indicator_ids != EXPECTED_INDICATORS or len(self.indicators) != 8:
            raise ValueError("indicator registry must contain the exact eight approved entries")
        enabled = [row for row in self.indicators if row["enabled"]]
        if len(enabled) != 6 or any(row["source_id"] not in source_ids for row in enabled):
            raise ValueError("exactly six first-slice indicators must be enabled")
        disabled = {row["indicator_id"] for row in self.indicators if not row["enabled"]}
        if disabled != {"US_PRICES_CPI_U_ALL_ITEMS", "US_OUTPUT_REAL_GDP"}:
            raise ValueError("CPI and GDP must be the only disabled follow-on indicators")
        serialized = json.dumps([self.sources, self.indicators, self.mappings]).lower()
        if any(word in serialized for word in FORBIDDEN):
            raise ValueError("forbidden aggregator reference in registry")
        required_source = {"endpoint", "operational_limits", "terms_reviewed_at", "next_terms_recheck", "parser_version", "health_policy"}
        for source in self.sources:
            if not required_source.issubset(source):
                raise ValueError(f"incomplete source metadata: {source['source_id']}")
            if not source["endpoint"].startswith("https://"):
                raise ValueError("source endpoint must be HTTPS")
        mapping_ids = {row["indicator_id"] for row in self.mappings["series_mappings"]}
        if mapping_ids != {row["indicator_id"] for row in enabled}:
            raise ValueError("mapping registry must cover exactly the enabled slice")

    def enabled_indicators(self) -> list[dict[str, Any]]:
        return [row for row in self.indicators if row["enabled"]]

    def source(self, source_id: str) -> dict[str, Any]:
        return next(row for row in self.sources if row["source_id"] == source_id)
