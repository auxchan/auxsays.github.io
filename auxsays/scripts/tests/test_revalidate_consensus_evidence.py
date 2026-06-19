#!/usr/bin/env python3
"""Tests for fixture-only consensus evidence revalidation classification."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import revalidate_consensus_evidence as revalidate_mod

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def row_yaml(**overrides: Any) -> str:
    fields: dict[str, Any] = {
        "id": "fixture-row",
        "product_id": "fixture-product",
        "update_version": "1.2.3",
        "source_type": "github_issue",
        "source_name": "Fixture Source",
        "source_url": "https://example.test/report",
        "captured_at": "2099-01-01T00:00:00Z",
        "patch_version_matched": True,
        "counted": True,
        "source_weight": 1,
    }
    fields.update(overrides)
    lines = []
    first = True
    for key, value in fields.items():
        if value == "__omit__":
            continue
        prefix = "- " if first else "  "
        lines.append(f"{prefix}{key}: {yaml_value(value)}")
        first = False
    return "\n".join(lines) + "\n"


def fixture(*rows: str) -> str:
    return "schema_version: 1\nevidence:\n" + "".join(rows)


def run_cli(args: list[str]) -> tuple[int, str]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = revalidate_mod.main(args)
    return code, output.getvalue()


def github_issue_api(number: int) -> str:
    return f"https://api.github.com/repos/obsproject/obs-studio/issues/{number}"


def github_comment_api(number: int) -> str:
    return f"https://api.github.com/repos/obsproject/obs-studio/issues/comments/{number}"


def run() -> int:
    print("=" * 60)
    print("Consensus evidence revalidation fixture tests")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fixture_path = tmp_path / "consensus_evidence_fixture.yml"
        fixture_text = fixture(
            row_yaml(id="candidate-row", source_type="github_issue", source_url="https://example.test/github/1"),
            row_yaml(id="missing-url-row", source_type="github_issue", source_url=""),
            row_yaml(id="unsupported-row", source_type="mystery_forum", source_url="https://example.test/mystery/1"),
            row_yaml(id="pending-row", source_type="reddit_community_report", source_url="https://example.test/reddit/1"),
            row_yaml(id="malformed-row", source_type="__omit__", source_url="https://example.test/malformed/1"),
            row_yaml(id="uncounted-row", source_type="github_issue", source_url="https://example.test/github/2", counted=False),
            row_yaml(id="other-product-row", product_id="other-product", source_type="github_issue", source_url="https://example.test/github/3"),
        )
        fixture_path.write_text(fixture_text, encoding="utf-8")
        before = fixture_path.read_text(encoding="utf-8")

        result = revalidate_mod.revalidate(fixture_path, "fixture-product", "1.2.3")
        counts = result["classification_counts"]
        ids_by_class = {row["classification"]: row["id"] for row in result["rows"]}

        check("selection is scoped by product/version", result["matching_rows"] == 6, json.dumps(result, indent=2))
        check("only counted rows are classified", result["counted_rows_selected"] == 5 and result["non_counted_rows_skipped"] == 1, json.dumps(result, indent=2))
        check("missing URL classification", counts["missing_url"] == 1 and ids_by_class["missing_url"] == "missing-url-row", json.dumps(result, indent=2))
        check("unsupported source classification", counts["unsupported_source_type"] == 1 and ids_by_class["unsupported_source_type"] == "unsupported-row", json.dumps(result, indent=2))
        check("pending source adapter classification", counts["pending_source_adapter"] == 1 and ids_by_class["pending_source_adapter"] == "pending-row", json.dumps(result, indent=2))
        check("malformed row classification", counts["malformed_row"] == 1 and ids_by_class["malformed_row"] == "malformed-row", json.dumps(result, indent=2))
        check("candidate for revalidation classification", counts["candidate_for_revalidation"] == 1 and ids_by_class["candidate_for_revalidation"] == "candidate-row", json.dumps(result, indent=2))

        code, summary = run_cli([
            "--evidence-file",
            str(fixture_path),
            "--product",
            "fixture-product",
            "--version",
            "1.2.3",
            "--summary",
        ])
        check("summary output", code == 0 and "No URLs fetched. No files written." in summary and "candidate for revalidation: 1" in summary, summary)

        code, json_output = run_cli([
            "--evidence-file",
            str(fixture_path),
            "--product",
            "fixture-product",
            "--version",
            "1.2.3",
            "--json",
        ])
        payload = json.loads(json_output)
        check("JSON output", code == 0 and payload["fetches_urls"] is False and payload["writes_files"] is False and payload["classification_counts"]["candidate_for_revalidation"] == 1, json_output)

        after = fixture_path.read_text(encoding="utf-8")
        check("fixture file remains unchanged", before == after, after)

        live_path = tmp_path / "live_consensus_evidence_fixture.yml"
        live_text = fixture(
            row_yaml(id="title-match", source_url="https://github.com/obsproject/obs-studio/issues/1"),
            row_yaml(id="body-match", source_url="https://github.com/obsproject/obs-studio/issues/2"),
            row_yaml(id="comment-match", source_url="https://github.com/obsproject/obs-studio/issues/3#issuecomment-300"),
            row_yaml(id="fetch-failed", source_url="https://github.com/obsproject/obs-studio/issues/4"),
            row_yaml(id="blocked", source_url="https://github.com/obsproject/obs-studio/issues/5"),
            row_yaml(id="no-version", source_url="https://github.com/obsproject/obs-studio/issues/6"),
            row_yaml(id="unsupported-live", source_type="reddit_community_report", source_url="https://example.test/reddit/1"),
        )
        live_path.write_text(live_text, encoding="utf-8")
        live_before = live_path.read_text(encoding="utf-8")

        responses: dict[str, Any] = {
            github_issue_api(1): {"title": "OBS Studio 1.2.3 crash on capture", "body": "No extra body."},
            github_issue_api(2): {"title": "Capture issue", "body": "Regression confirmed on OBS Studio 1.2.3 release."},
            github_issue_api(3): {"title": "Parent context without version", "body": "No version here."},
            github_comment_api(300): {"body": "I can reproduce this on 1.2.3 with the same source."},
            github_issue_api(4): revalidate_mod.SourceFetchError("http_500", status=500),
            github_issue_api(5): revalidate_mod.SourceFetchError("http_403", status=403),
            github_issue_api(6): {"title": "Capture issue", "body": "No exact version in fetched content."},
        }
        requested_urls: list[str] = []

        def fake_fetch(url: str) -> Any:
            requested_urls.append(url)
            value = responses[url]
            if isinstance(value, Exception):
                raise value
            return value

        live_result = revalidate_mod.revalidate(
            live_path,
            "fixture-product",
            "1.2.3",
            live_fetch=True,
            fetch_json=fake_fetch,
        )
        live_counts = live_result["classification_counts"]
        live_rows = {row["id"]: row for row in live_result["rows"]}
        check("GitHub issue title contains target version verifies", live_rows["title-match"]["classification"] == "verified" and live_rows["title-match"].get("live_match_basis") == "issue_title", json.dumps(live_result, indent=2))
        check("GitHub issue body contains target version verifies", live_rows["body-match"]["classification"] == "verified" and live_rows["body-match"].get("live_match_basis") == "issue_body", json.dumps(live_result, indent=2))
        check("GitHub comment body contains target version verifies", live_rows["comment-match"]["classification"] == "verified" and live_rows["comment-match"].get("live_match_basis") == "comment_body", json.dumps(live_result, indent=2))
        check("HTTP failure is fetch_failed", live_rows["fetch-failed"]["classification"] == "fetch_failed", json.dumps(live_result, indent=2))
        check("403 or 429 is blocked", live_rows["blocked"]["classification"] == "blocked", json.dumps(live_result, indent=2))
        check("missing exact version in fetched content fails", live_rows["no-version"]["classification"] == "exact_version_failed", json.dumps(live_result, indent=2))
        check("unsupported live source stays unsupported", live_rows["unsupported-live"]["classification"] == "unsupported_source_type", json.dumps(live_result, indent=2))
        check("live summary includes verified and failure counts", live_counts["verified"] == 3 and live_counts["exact_version_failed"] == 1 and live_counts["fetch_failed"] == 1 and live_counts["blocked"] == 1, json.dumps(live_counts))
        check("comment URL fetches parent issue and comment", github_issue_api(3) in requested_urls and github_comment_api(300) in requested_urls, json.dumps(requested_urls))

        live_summary = io.StringIO()
        with contextlib.redirect_stdout(live_summary):
            revalidate_mod.print_summary(live_result)
        summary_text = live_summary.getvalue()
        check("live summary output includes verified/failure counts", all(text in summary_text for text in ("verified: 3", "exact version failed: 1", "fetch failed: 1", "blocked: 1", "Live fetch enabled. No files written.")), summary_text)

        original_request_json = revalidate_mod.request_json
        try:
            revalidate_mod.request_json = fake_fetch
            code, live_json_output = run_cli([
                "--evidence-file",
                str(live_path),
                "--product",
                "fixture-product",
                "--version",
                "1.2.3",
                "--json",
                "--live-fetch",
            ])
        finally:
            revalidate_mod.request_json = original_request_json
        live_payload = json.loads(live_json_output)
        check("live JSON output is valid", code == 0 and live_payload["fetches_urls"] is True and live_payload["classification_counts"]["verified"] == 3, live_json_output)

        live_after = live_path.read_text(encoding="utf-8")
        check("live fixture file remains unchanged", live_before == live_after, live_after)

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
