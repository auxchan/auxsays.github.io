#!/usr/bin/env python3
"""Build a dry-run consensus status file from structured evidence.

This does not scrape communities and does not modify generated update records.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
OUT_PATH = ROOT / "_data" / "consensus_status.json"
VALID_SENTIMENTS = {"positive", "moderate", "negative"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
PRODUCT_LABELS = {
    "blackmagic-davinci": "DaVinci Resolve",
    "obs-studio": "OBS Studio",
    "adobe-premiere-pro": "Adobe Premiere Pro",
    "adobe-acrobat-reader": "Adobe Acrobat / Reader",
    "windows-11": "Windows 11",
    "elgato": "Elgato",
    "adobe-photoshop": "Adobe Photoshop",
    "chatgpt": "ChatGPT",
    "microsoft-powerpoint": "Microsoft PowerPoint",
    "microsoft-teams": "Microsoft Teams",
    "microsoft-365-apps": "Microsoft 365 Apps",
    "dji-mimo": "DJI Mimo",
}


def load_evidence() -> list[dict[str, Any]]:
    if not EVIDENCE_PATH.exists():
        return []
    payload = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        evidence = payload.get("evidence") or []
        return [item for item in evidence if isinstance(item, dict)]
    return []


def is_patch_specific(item: dict[str, Any]) -> bool:
    if item.get("patch_version_matched") is True:
        return True
    version = str(item.get("update_version") or "").strip().lower()
    text = " ".join([
        str(item.get("parent_title") or ""),
        str(item.get("report_title") or ""),
        str(item.get("report_text_excerpt") or ""),
    ]).lower()
    return bool(version and version in text)


def consensus_label(counts: Counter[str]) -> str:
    total = sum(counts.values())
    if total <= 0:
        return "Insufficient data"
    negative_ratio = counts["negative"] / total
    positive_ratio = counts["positive"] / total
    if negative_ratio >= 0.55:
        return "Negative"
    if positive_ratio >= 0.55 and counts["negative"] == 0:
        return "Positive"
    return "Moderate"


def confidence(total: int) -> str:
    if total >= 25:
        return "Medium"
    if total >= 8:
        return "Low-Medium"
    if total > 0:
        return "Low"
    return "Insufficient"


def evidence_state(total: int) -> str:
    if total <= 0:
        return "insufficient_data"
    # Phase A keeps low-volume verified rows in pilot_sample. consensus_live
    # should only be introduced after a higher-volume structured threshold and
    # page-level structured-evidence rendering are both in place.
    return "pilot_sample"


def clean_public_phrase(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = re.sub(r"[_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def product_label(product_id: str) -> str:
    return PRODUCT_LABELS.get(product_id, clean_public_phrase(product_id, fallback=product_id))


def join_public_list(items: list[str]) -> str:
    clean = [item for item in items if item]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return ", ".join(clean[:-1]) + f", and {clean[-1]}"


def top_theme_phrases(themes: Counter[str], *, limit: int = 3) -> list[str]:
    phrases: list[str] = []
    for theme, _count in themes.most_common():
        phrase = clean_public_phrase(theme).lower()
        if not phrase or phrase == "unspecified issue":
            continue
        if phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= limit:
            break
    return phrases


def sample_size_label(total: int) -> str:
    if total >= 25:
        return "larger"
    if total >= 8:
        return "meaningful pilot"
    if total > 0:
        return "small"
    return "no"


def version_is_beta(version: str) -> bool:
    return bool(re.search(r"\b(?:public\s+)?beta\b|b\d+\b", str(version or ""), flags=re.I))


def recommendation_prefix(product_id: str, version: str, label: str, total: int) -> str:
    label = label.lower()
    if total <= 0:
        return "INSUFFICIENT DATA"
    if product_id == "blackmagic-davinci" and version_is_beta(version) and label == "negative":
        return "AVOID for production"
    if label == "negative":
        return "WAIT"
    if label == "positive":
        return "SAFE ENOUGH to test"
    return "TEST FIRST"


def affected_workflow_sentence(product_id: str, version: str, label: str, themes: Counter[str]) -> str:
    label = label.lower()
    theme_words = " ".join(top_theme_phrases(themes, limit=5))
    if product_id == "blackmagic-davinci":
        if version_is_beta(version):
            return "Production editors should avoid it on active projects; test only in disposable or non-critical projects."
        if "export" in theme_words or "render" in theme_words:
            return "Production editors with active export deadlines should wait unless they need a specific fix."
        return "Production editors should test on copied projects before moving active work to this version."
    if product_id == "obs-studio":
        return "Streamers and recording setups with stable scenes, plugins, or capture devices should wait or test on a backup profile."
    if label == "negative":
        return "Users with fragile production workflows should wait unless they need a specific fix."
    if label == "positive":
        return "Most users can test the update, while critical workflows should still keep a rollback path."
    return "Users with fragile workflows should test first before upgrading production systems."


def source_limitation_sentence(items: list[dict[str, Any]], confidence_label: str) -> str:
    if not items:
        return "No patch-specific user reports have been counted yet."
    source_types = [str(item.get("source_type") or item.get("source_name") or "").lower() for item in items]
    reddit_count = sum(1 for value in source_types if "reddit" in value)
    if reddit_count and reddit_count / len(items) >= 0.6:
        return "Current evidence is Reddit-heavy, so treat this as a wait/test signal rather than broad consensus."
    if confidence_label.lower() in {"low", "insufficient"}:
        return "Evidence is still limited, so treat this as a wait/test signal rather than broad consensus."
    return "Evidence is still a verified-report sample, not broad live consensus."


def consensus_summary(product_id: str, version: str, items: list[dict[str, Any]], counts: Counter[str], themes: Counter[str]) -> str:
    total = len(items)
    label_name = product_label(product_id)
    if total <= 0:
        return (
            f"INSUFFICIENT DATA: {label_name} {version} has no confirmed patch-specific user reports yet. "
            "Use the official source only until accepted evidence is available."
        )
    label = consensus_label(counts).lower()
    confidence_label = confidence(total)
    theme_phrases = top_theme_phrases(themes)
    if theme_phrases:
        issue_sentence = f"Reported issues cluster around {join_public_list(theme_phrases)}."
    else:
        issue_sentence = "Reported issues are not yet specific enough to cluster cleanly."
    return " ".join([
        (
            f"{recommendation_prefix(product_id, version, label, total)}: {label_name} {version} has a "
            f"{sample_size_label(total)} {label} Verified reports set with {confidence_label} confidence."
        ),
        issue_sentence,
        f"{affected_workflow_sentence(product_id, version, label, themes)} {source_limitation_sentence(items, confidence_label)}",
    ])


def latest_captured_at(items: list[dict[str, Any]]) -> str:
    parsed: list[datetime] = []
    for item in items:
        value = str(item.get("captured_at") or "").strip()
        if not value:
            continue
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            captured = datetime.fromisoformat(value)
        except ValueError:
            continue
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        parsed.append(captured.astimezone(timezone.utc))
    if not parsed:
        return ""
    return max(parsed).isoformat().replace("+00:00", "Z")


def main() -> int:
    evidence = load_evidence()
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    excluded: list[dict[str, Any]] = []

    for item in evidence:
        product_id = str(item.get("product_id") or "").strip()
        version = str(item.get("update_version") or "").strip()
        sentiment = str(item.get("sentiment") or "").strip().lower()
        severity = str(item.get("severity") or "").strip().lower()
        if not product_id or not version:
            item["exclusion_reason"] = item.get("exclusion_reason") or "missing_product_or_version"
            excluded.append(item)
            continue
        if sentiment not in VALID_SENTIMENTS:
            item["exclusion_reason"] = item.get("exclusion_reason") or "invalid_sentiment"
            excluded.append(item)
            continue
        if severity and severity not in VALID_SEVERITIES:
            item["exclusion_reason"] = item.get("exclusion_reason") or "invalid_severity"
            excluded.append(item)
            continue
        if item.get("counted") is False or not is_patch_specific(item):
            item["exclusion_reason"] = item.get("exclusion_reason") or "not_confirmed_patch_specific"
            excluded.append(item)
            continue
        groups[(product_id, version)].append(item)

    aggregate = []
    for (product_id, version), items in sorted(groups.items()):
        sentiments = Counter(str(item.get("sentiment")).lower() for item in items)
        severities = Counter(str(item.get("severity") or "low").lower() for item in items)
        themes = Counter(str(item.get("issue_theme") or "unspecified") for item in items)
        aggregate.append({
            "product_id": product_id,
            "update_version": version,
            "report_count": len(items),
            "positive_count": sentiments["positive"],
            "moderate_count": sentiments["moderate"],
            "negative_count": sentiments["negative"],
            "issue_themes": dict(themes.most_common()),
            "severity_summary": dict(severities.most_common()),
            "consensus_label": consensus_label(sentiments),
            "confidence": confidence(len(items)),
            "evidence_state": evidence_state(len(items)),
            "consensus_summary": consensus_summary(product_id, version, items, sentiments, themes),
            "evidence_last_checked": latest_captured_at(items),
        })

    OUT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "dry_run_structured_evidence_only",
        "evidence_items_read": len(evidence),
        "aggregate_count": len(aggregate),
        "excluded_count": len(excluded),
        "aggregates": aggregate,
        "excluded": excluded,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Consensus dry run read {len(evidence)} evidence items; built {len(aggregate)} aggregate rows; excluded {len(excluded)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
