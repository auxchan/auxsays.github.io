#!/usr/bin/env python3
"""Validate AUXSAYS ingestion source configuration.

This is a guardrail against source-map contamination. It intentionally checks
the problems that have already cost time:

- cross-company Adobe HelpX URLs on non-Adobe products
- malformed URLs with trailing punctuation
- enabled sources without official URLs
- invalid YAML shapes that silently move fields into the wrong place
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

DEFAULT_CONFIG = Path("auxsays/_data/patch_ingestion_sources.yml")
URL_FIELDS = ("official_url", "secondary_official_url", "feed_url", "api_url")
TRAILING_URL_PUNCTUATION = (":", ";", ",")


def _load_sources(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing ingestion config: {path}")

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a YAML list of source entries")

    bad_items = [idx for idx, item in enumerate(payload) if not isinstance(item, dict)]
    if bad_items:
        raise ValueError(f"{path} contains non-object entries at indexes: {bad_items}")

    return payload


def _host(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").lower().removeprefix("www.")


def _validate_url_shape(
    errors: list[str],
    *,
    entry_label: str,
    field: str,
    value: Any,
) -> None:
    if value in (None, ""):
        return

    if not isinstance(value, str):
        errors.append(f"{entry_label}: ingestion.{field} must be a string or null")
        return

    url = value.strip()
    if url != value:
        errors.append(f"{entry_label}: ingestion.{field} has leading/trailing whitespace")

    if url.endswith(TRAILING_URL_PUNCTUATION):
        errors.append(f"{entry_label}: ingestion.{field} ends with malformed punctuation: {url!r}")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{entry_label}: ingestion.{field} is not a valid absolute HTTP(S) URL: {url!r}")


def _validate_entry(errors: list[str], warnings: list[str], source: dict[str, Any]) -> None:
    company_id = str(source.get("company_id") or "").strip()
    product_id = str(source.get("product_id") or "").strip()
    label = f"{company_id or '<missing-company>'}/{product_id or '<missing-product>'}"

    if not company_id:
        errors.append(f"{label}: missing company_id")
    if not product_id:
        errors.append(f"{label}: missing product_id")

    ingestion = source.get("ingestion")
    if not isinstance(ingestion, dict):
        errors.append(f"{label}: ingestion must be an object")
        return

    adapter = ingestion.get("adapter")
    ingestion_type = ingestion.get("type")
    if not adapter:
        errors.append(f"{label}: ingestion.adapter is required")
    if not ingestion_type:
        errors.append(f"{label}: ingestion.type is required")

    official_url = ingestion.get("official_url")
    if source.get("enabled") and not official_url:
        errors.append(f"{label}: enabled source requires ingestion.official_url")

    keywords = ingestion.get("keywords")
    if keywords is not None:
        if not isinstance(keywords, list) or not all(isinstance(item, str) for item in keywords):
            errors.append(f"{label}: ingestion.keywords must be null or a list of strings")

    request = ingestion.get("request")
    if request is not None and not isinstance(request, dict):
        errors.append(f"{label}: ingestion.request must be an object when present")

    for field in URL_FIELDS:
        value = ingestion.get(field)
        _validate_url_shape(errors, entry_label=label, field=field, value=value)

        if isinstance(value, str) and "adobe.com" in _host(value) and company_id != "adobe":
            errors.append(
                f"{label}: ingestion.{field} points to Adobe domain on non-Adobe source: {value}"
            )

    # High-signal warning: duplicated official/secondary URL is not always wrong,
    # but it usually means the secondary field is not providing real fallback value.
    secondary_url = ingestion.get("secondary_official_url")
    if official_url and secondary_url and official_url == secondary_url:
        warnings.append(f"{label}: secondary_official_url duplicates official_url")


def validate(path: Path) -> int:
    sources = _load_sources(path)
    errors: list[str] = []
    warnings: list[str] = []

    seen_products: set[str] = set()
    for source in sources:
        product_id = str(source.get("product_id") or "").strip()
        if product_id:
            if product_id in seen_products:
                errors.append(f"duplicate product_id: {product_id}")
            seen_products.add(product_id)

        _validate_entry(errors, warnings, source)

    if warnings:
        print("Source config warnings:")
        for warning in warnings:
            print(f"  WARN: {warning}")

    if errors:
        print("Source config validation failed:")
        for error in errors:
            print(f"  ERROR: {error}")
        return 1

    print(f"Source config validation passed: {len(sources)} entries checked.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    return validate(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
