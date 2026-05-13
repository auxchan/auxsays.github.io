#!/usr/bin/env python3
"""Collect DaVinci Resolve evidence candidates for fallback manual review.

Production evidence collection lives in patch_collectors/davinci.py and is run
through run_patch_evidence_collection.py. This conservative staging tool remains
only for rejected or ambiguous candidates that fail deterministic gates. It does
not write consensus_evidence.yml, does not write generated records, does not
schedule workflows, does not require credentials, and does not bypass blocked
sources.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.normalize_davinci_version import normalize_davinci_version  # noqa: E402

PRODUCT_ID = "blackmagic-davinci"
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
GENERATED_DIR = ROOT / "updates" / "generated"
DEFAULT_OUTPUT = ROOT.parent / ".project-control" / "evidence-staging" / "phase1g-davinci-candidates.yml"
DEFAULT_RESULT_OUTPUT = ROOT.parent / ".project-control" / "probe-output" / "phase1g" / "davinci-candidate-collector-result.json"

CURRENT_RECORDS = {
    "stable": "21",
    "beta": "21 Public Beta 1",
}

CURRENT_RECORD_PATHS = {
    "stable": GENERATED_DIR / "2026-04-14-davinci-resolve-21.md",
    "beta": GENERATED_DIR / "2026-04-14-davinci-resolve-21-public-beta-1.md",
}


@dataclass(frozen=True)
class Seed:
    source_url: str
    source_type: str
    source_title: str
    candidate_update_version_raw: str
    issue_summary: str
    evidence_category: str
    severity: str
    target_hint: str | None = None
    manual_user_verified: bool = False
    source_published_at: str = ""
    fetch: bool = True


SEEDS: list[Seed] = [
    Seed(
        "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235117",
        "blackmagic_forum",
        "Blackmagic forum thread t=235117",
        "",
        "Blackmagic forum seed requires manual body review before it can count as evidence.",
        "issue_report_candidate",
        "medium",
    ),
    Seed(
        "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235536",
        "blackmagic_forum",
        "Blackmagic forum thread t=235536",
        "",
        "Blackmagic forum seed requires manual body review before it can count as evidence.",
        "issue_report_candidate",
        "medium",
    ),
    Seed(
        "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235458",
        "blackmagic_forum",
        "Blackmagic forum thread t=235458",
        "",
        "Blackmagic forum seed requires manual body review before it can count as evidence.",
        "issue_report_candidate",
        "medium",
    ),
    Seed(
        "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235208",
        "blackmagic_forum",
        "Blackmagic forum thread t=235208",
        "",
        "Blackmagic forum seed requires manual body review before it can count as evidence.",
        "issue_report_candidate",
        "medium",
    ),
    Seed(
        "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=234870",
        "blackmagic_forum",
        "Blackmagic forum thread t=234870",
        "",
        "Blackmagic forum seed requires manual body review before it can count as evidence.",
        "issue_report_candidate",
        "medium",
    ),
    Seed(
        "https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235179",
        "blackmagic_forum",
        "Resolve Studio 21.0B Build 20 crashes when creating Magic Mask",
        "21 Public Beta 1",
        "Magic Mask crash report already promoted in Phase 1F.",
        "issue_report",
        "high",
        target_hint="beta",
        manual_user_verified=True,
    ),
    Seed(
        "https://www.reddit.com/r/davinciresolve/comments/1sl3sqn/davinci_resolve_21_crashes_instantly_on_macbook/",
        "reddit_community_report",
        "DaVinci Resolve 21 crashes instantly on MacBook",
        "DaVinci Resolve 21",
        "Potential stable 21 startup crash report; body must be reviewed before promotion.",
        "issue_report_candidate",
        "high",
        target_hint="stable",
    ),
    Seed(
        "https://www.reddit.com/r/davinciresolve/comments/1skz03l/davinci_resolve_21_problem/",
        "reddit_community_report",
        "DaVinci Resolve 21 problem",
        "DaVinci Resolve 21",
        "Potential stable 21 problem report; body must be reviewed before promotion.",
        "issue_report_candidate",
        "medium",
        target_hint="stable",
    ),
    Seed(
        "https://www.reddit.com/r/davinciresolve/comments/1sn39qf/davinci_resolve_failed_to_decode_video_frame_when/",
        "reddit_community_report",
        "DaVinci Resolve failed to decode video frame when rendering / public beta 21",
        "21 Public Beta 1",
        "Decode/render failure already promoted in Phase 1F.",
        "issue_report",
        "medium",
        target_hint="beta",
        manual_user_verified=True,
    ),
    Seed(
        "https://www.reddit.com/r/davinciresolve/comments/1sy9fi3/release_of_davinci_resolve_210b2/",
        "reddit_community_report",
        "Release of DaVinci Resolve 21.0b2",
        "DaVinci Resolve 21.0b2",
        "Beta 2 discussion is a future update for AUXSAYS until a matching generated record exists.",
        "release_discussion",
        "low",
        target_hint="future",
    ),
    Seed(
        "https://www.liftgammagain.com/forum/index.php?forums/davinci-resolve.36/",
        "community_discovery",
        "Lift Gamma Gain DaVinci Resolve forum discovery source",
        "",
        "Discovery source for manual review; not report evidence without a specific body-reviewed thread.",
        "discovery_source",
        "low",
        target_hint="ambiguous",
        fetch=False,
    ),
    Seed(
        "https://creativecow.net/forums/forum/davinci-resolve/",
        "community_discovery",
        "Creative COW DaVinci Resolve forum discovery source",
        "",
        "Discovery source for manual review; not report evidence without a specific body-reviewed thread.",
        "discovery_source",
        "low",
        target_hint="ambiguous",
        fetch=False,
    ),
    Seed(
        "https://www.dpreview.com/forums",
        "community_discovery",
        "DPReview DaVinci Resolve Beta 21 discussion discovery source",
        "DaVinci Resolve Beta 21",
        "Discovery source only; a specific body-reviewed discussion URL is needed before counting evidence.",
        "discovery_source",
        "low",
        target_hint="ambiguous",
        fetch=False,
    ),
    Seed(
        "https://www.videohelp.com/software/DaVinci-Resolve/version-history",
        "release_metadata",
        "VideoHelp DaVinci Resolve version history",
        "",
        "Release metadata source only; not user issue report evidence.",
        "release_metadata",
        "low",
        target_hint="ambiguous",
        fetch=False,
    ),
]


def yaml_quote(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return "''"
    if re.fullmatch(r"[A-Za-z0-9_./:#?=&%+\- ]+", text) and not text.startswith((" ", "-", "{", "[", "!", "&", "*")):
        lowered = text.lower()
        if lowered not in {"true", "false", "null", "yes", "no", "on", "off"} and ": " not in text:
            return text
    return json.dumps(text, ensure_ascii=False)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for subkey, subval in item.items():
                        prefix = "- " if first else "  "
                        lines.append(f"{prefix}{subkey}: {yaml_quote(subval)}")
                        first = False
                else:
                    lines.append(f"- {yaml_quote(item)}")
        elif isinstance(value, dict):
            lines.append(f"{key}:")
            for subkey, subval in value.items():
                lines.append(f"  {subkey}: {yaml_quote(subval)}")
        else:
            lines.append(f"{key}: {yaml_quote(value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def simple_yaml_items(path: Path, list_key: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_list = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == f"{list_key}:":
            in_list = True
            continue
        if not in_list:
            continue
        if stripped.startswith("- "):
            if current:
                items.append(current)
            current = {}
            rest = stripped[2:]
            if ":" in rest:
                key, value = rest.split(":", 1)
                current[key.strip()] = parse_scalar(value)
            continue
        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = parse_scalar(value)
    if current:
        items.append(current)
    return items


def front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    data: dict[str, Any] = {}
    for raw_line in parts[1].splitlines():
        if raw_line.startswith((" ", "-")) or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    return data


def current_generated_versions() -> set[str]:
    versions: set[str] = set()
    for path in GENERATED_DIR.glob("*.md"):
        data = front_matter(path)
        if str(data.get("product_id") or "") == PRODUCT_ID and data.get("update_version"):
            versions.add(str(data["update_version"]))
    return versions


def current_record_release_dates() -> dict[str, str]:
    dates: dict[str, str] = {}
    for target, path in CURRENT_RECORD_PATHS.items():
        data = front_matter(path)
        published = str(data.get("update_published_at") or "").strip().strip("'\"")
        if published:
            dates[target] = published[:10]
    return dates


def existing_evidence_urls() -> set[str]:
    urls: set[str] = set()
    for row in simple_yaml_items(EVIDENCE_PATH, "evidence"):
        if str(row.get("product_id") or "") != PRODUCT_ID:
            continue
        url = normalize_url(str(row.get("source_url") or ""))
        if url:
            urls.add(url)
    return urls


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def fetch_source(seed: Seed) -> dict[str, Any]:
    if not seed.fetch:
        return {
            "access_status": "not_fetched_discovery_or_metadata_source",
            "body_accessed": False,
            "source_title": seed.source_title,
            "text_sample": "",
            "http_status": None,
        }
    request = Request(
        seed.source_url,
        headers={
            "User-Agent": "AUXSAYS Phase 1G manual candidate review; no credentials; no bypass",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8,*/*;q=0.5",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=12) as response:
            status = int(getattr(response, "status", 0) or 0)
            content_type = response.headers.get("content-type", "")
            raw = response.read(500_000)
    except HTTPError as exc:
        return {
            "access_status": f"http_{exc.code}_blocked_or_inaccessible",
            "body_accessed": False,
            "source_title": seed.source_title,
            "text_sample": "",
            "http_status": exc.code,
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "access_status": f"fetch_error_{type(exc).__name__}",
            "body_accessed": False,
            "source_title": seed.source_title,
            "text_sample": "",
            "http_status": None,
        }

    if status != 200:
        return {
            "access_status": f"http_{status}_inaccessible",
            "body_accessed": False,
            "source_title": seed.source_title,
            "text_sample": "",
            "http_status": status,
        }

    charset = "utf-8"
    charset_match = re.search(r"charset=([A-Za-z0-9_\-]+)", content_type)
    if charset_match:
        charset = charset_match.group(1)
    text = raw.decode(charset, errors="replace")
    title = extract_title(text) or seed.source_title
    clean = clean_text(text)
    if len(clean) < 200:
        return {
            "access_status": "http_200_body_too_short_for_verification",
            "body_accessed": False,
            "source_title": title,
            "text_sample": clean[:500],
            "http_status": status,
        }
    return {
        "access_status": "http_200_body_accessed",
        "body_accessed": True,
        "source_title": title,
        "text_sample": clean[:1200],
        "http_status": status,
    }


def extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    if not match:
        return ""
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()


def clean_text(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def infer_raw_version(seed: Seed, fetched: dict[str, Any]) -> str:
    if seed.candidate_update_version_raw:
        return seed.candidate_update_version_raw
    haystack = " ".join([str(fetched.get("source_title") or ""), str(fetched.get("text_sample") or "")])
    patterns = [
        r"DaVinci Resolve(?: Studio)?\s+21\.0\s*(?:Public\s*)?Beta\s*1",
        r"DaVinci Resolve(?: Studio)?\s+21\.0b1",
        r"Resolve(?: Studio)?\s+21\.0B\s*Build\s*20",
        r"DaVinci Resolve(?: Studio)?\s+21\.0b2",
        r"DaVinci Resolve(?: Studio)?\s+21\s*(?:Public\s*)?Beta\s*2",
        r"DaVinci Resolve(?: Studio)?\s+21\s*(?:Public\s*)?Beta\s*1",
        r"Resolve(?: Studio)?\s+21\s*(?:Public\s*)?Beta\s*1",
        r"DaVinci Resolve(?: Studio)?\s+21\b",
        r"Resolve(?: Studio)?\s+21\b",
        r"\b21\.0b2\b",
        r"\b21\.0b1\b",
        r"\b21\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, haystack, flags=re.I)
        if match:
            raw = match.group(0)
            if re.search(r"21\.0B\s*Build\s*20", raw, flags=re.I):
                return "21 Public Beta 1"
            return raw
    return ""


def target_for(raw_version: str, target_hint: str | None, generated_versions: set[str]) -> tuple[str, str, bool, str]:
    if target_hint == "future":
        norm = normalize_davinci_version(raw_version)
        proposed = str(norm.get("canonical_update_version") or "")
        return "future", proposed, False, "seed_identified_future_update"
    if not raw_version:
        return target_hint or "ambiguous", "", False, "no_version_in_seed_or_accessed_body"

    normalized = normalize_davinci_version(raw_version)
    if normalized.get("rejected"):
        return "ambiguous", "", False, str(normalized.get("rejection_reason") or "normalizer_rejected")

    proposed = str(normalized["canonical_update_version"])
    if normalized.get("is_beta") and int(normalized.get("beta_number") or 0) > 1 and proposed not in generated_versions:
        return "future", proposed, False, "later_beta_without_matching_generated_record"
    if proposed == CURRENT_RECORDS["stable"]:
        return "stable", proposed, True, "normalizer_exact_stable_21"
    if proposed == CURRENT_RECORDS["beta"]:
        return "beta", proposed, True, "normalizer_exact_public_beta_1"
    if proposed in generated_versions:
        return "future", proposed, False, "matching_generated_record_exists_but_not_phase1g_target"
    return "future", proposed, False, "normalized_version_not_current_phase1g_record"


def date_gate(seed: Seed, target_record: str, release_dates: dict[str, str]) -> tuple[bool | None, str, str]:
    if target_record not in release_dates:
        return None, "", "no_current_record_release_date_gate"
    release_date = release_dates[target_record]
    if not seed.source_published_at:
        return None, release_date, "source_published_at_missing_manual_review_required"
    if seed.source_published_at < release_date:
        return False, release_date, "source_published_before_patch_release"
    return True, release_date, "source_published_on_or_after_patch_release"


def issue_like(seed: Seed, fetched: dict[str, Any]) -> bool:
    text = " ".join([seed.source_title, seed.issue_summary, str(fetched.get("source_title") or ""), str(fetched.get("text_sample") or "")]).lower()
    return any(term in text for term in ("crash", "failed", "failure", "problem", "error", "decode", "issue", "hang", "broken"))


def promotion_blocker(
    *,
    seed: Seed,
    target_record: str,
    exact_version_match: bool,
    body_accessed: bool,
    body_verified: bool,
    duplicate: bool,
    issue_report: bool,
    release_date_gate_passed: bool | None,
) -> tuple[bool, str]:
    if duplicate:
        return False, "duplicate_existing_evidence"
    if target_record == "future":
        return False, "future_update_not_current_record"
    if not body_accessed and not body_verified and seed.evidence_category == "issue_report_candidate":
        return False, "needs_user_verification"
    if target_record == "ambiguous" or not exact_version_match:
        return False, "ambiguous_or_non_exact_version"
    if seed.evidence_category in {"release_metadata", "discovery_source", "release_discussion"}:
        return False, "not_user_issue_report_evidence"
    if release_date_gate_passed is False:
        return False, "source_published_before_patch_release"
    if release_date_gate_passed is None:
        return False, "source_date_unverified"
    if not issue_report:
        return False, "not_an_actual_issue_report"
    if not body_accessed and not body_verified:
        return False, "needs_user_verification"
    if not body_verified:
        return False, "manual_review_required_before_promotion"
    return True, ""


def candidate_from_seed(seed: Seed, generated_versions: set[str], existing_urls: set[str], release_dates: dict[str, str]) -> dict[str, Any]:
    fetched = fetch_source(seed)
    raw_version = infer_raw_version(seed, fetched)
    target_record, proposed, exact_match, match_basis = target_for(raw_version, seed.target_hint, generated_versions)
    release_date_gate_passed, target_release_date, release_date_gate_reason = date_gate(seed, target_record, release_dates)
    duplicate = normalize_url(seed.source_url) in existing_urls
    body_accessed = bool(fetched["body_accessed"])
    body_verified = seed.manual_user_verified or (body_accessed and duplicate)
    issue_report = issue_like(seed, fetched)
    include, blocker = promotion_blocker(
        seed=seed,
        target_record=target_record,
        exact_version_match=exact_match,
        body_accessed=body_accessed,
        body_verified=body_verified,
        duplicate=duplicate,
        issue_report=issue_report,
        release_date_gate_passed=release_date_gate_passed,
    )
    confidence = "high" if body_verified and exact_match else ("medium" if body_accessed and exact_match else "low")
    return {
        "product_id": PRODUCT_ID,
        "source_url": seed.source_url,
        "source_type": seed.source_type,
        "source_title": fetched["source_title"],
        "access_status": fetched["access_status"],
        "body_accessed": body_accessed,
        "body_verified": body_verified,
        "candidate_update_version_raw": raw_version,
        "proposed_update_version": proposed,
        "target_record": target_record,
        "exact_version_match": exact_match,
        "match_basis": match_basis,
        "source_published_at": seed.source_published_at,
        "target_release_date": target_release_date,
        "release_date_gate_passed": release_date_gate_passed,
        "release_date_gate_reason": release_date_gate_reason,
        "issue_summary": seed.issue_summary,
        "evidence_category": seed.evidence_category,
        "severity": seed.severity,
        "confidence": confidence,
        "duplicate_existing_evidence": duplicate,
        "include_for_promotion": include,
        "promotion_blocker": blocker,
    }


def filter_target(candidates: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    if target == "both":
        return candidates
    return [item for item in candidates if item["target_record"] == target]


def decision_for(candidate: dict[str, Any]) -> str:
    if candidate["include_for_promotion"] is True:
        return "promote_now"
    blocker = str(candidate.get("promotion_blocker") or "")
    if blocker == "duplicate_existing_evidence":
        return "duplicate_existing_evidence"
    if candidate["target_record"] == "future":
        return "future_update_not_current_record"
    if blocker in {"needs_user_verification", "manual_review_required_before_promotion", "source_date_unverified"}:
        return "needs_user_verification"
    if candidate["target_record"] == "ambiguous" or blocker == "ambiguous_or_non_exact_version":
        return "ambiguous_version"
    return "reject"


def write_result(path: Path, candidates: list[dict[str, Any]], target: str, output: Path) -> None:
    decisions: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_target: dict[str, int] = {}
    for item in candidates:
        decisions[decision_for(item)] = decisions.get(decision_for(item), 0) + 1
        by_source[item["source_type"]] = by_source.get(item["source_type"], 0) + 1
        by_target[item["target_record"]] = by_target.get(item["target_record"], 0) + 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "dry_run_manual_candidate_collection",
        "target": target,
        "candidate_output": str(output.relative_to(ROOT.parent) if output.is_relative_to(ROOT.parent) else output),
        "candidate_count": len(candidates),
        "candidate_count_by_source": by_source,
        "candidate_count_by_target_record": by_target,
        "decision_counts": decisions,
        "promote_now_count": decisions.get("promote_now", 0),
        "duplicates_detected": decisions.get("duplicate_existing_evidence", 0),
        "writes_production_files": False,
        "requires_credentials": False,
        "bypasses_blocked_sites": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect DaVinci evidence candidates for manual review.")
    parser.add_argument("--dry-run", action="store_true", help="Required; only staging/probe outputs are written.")
    parser.add_argument("--target", choices=("stable", "beta", "both"), default="both")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--result-output", default=str(DEFAULT_RESULT_OUTPUT))
    args = parser.parse_args(argv)

    if not args.dry_run:
        print("ERROR: collect_davinci_candidates.py requires --dry-run.", file=sys.stderr)
        return 2

    generated_versions = current_generated_versions()
    existing_urls = existing_evidence_urls()
    release_dates = current_record_release_dates()
    all_candidates = [candidate_from_seed(seed, generated_versions, existing_urls, release_dates) for seed in SEEDS]
    candidates = filter_target(all_candidates, args.target)

    output = Path(args.output)
    if not output.is_absolute():
        output = Path.cwd() / output
    result_output = Path(args.result_output)
    if not result_output.is_absolute():
        result_output = Path.cwd() / result_output

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "dry_run_manual_candidate_collection",
        "target": args.target,
        "candidate_policy": "manual_review_only_no_consensus_or_record_writes",
        "candidates": candidates,
    }
    write_yaml(output, payload)
    write_result(result_output, candidates, args.target, output)
    print(f"Collected {len(candidates)} DaVinci candidate(s) for target={args.target}.")
    print(f"Candidate staging written to: {output}")
    print(f"Collector result written to: {result_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
