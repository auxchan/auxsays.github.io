#!/usr/bin/env python3
"""Tests for fixture-only consensus evidence revalidation classification."""
from __future__ import annotations

import contextlib
import io
import json
import os
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


@contextlib.contextmanager
def patched_env(**updates: str | None) -> Any:
    keys = ("GITHUB_TOKEN", "GH_TOKEN")
    before = {key: os.environ.get(key) for key in keys}
    for key in keys:
        value = updates.get(key, before[key])
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def github_issue_api(number: int) -> str:
    return f"https://api.github.com/repos/obsproject/obs-studio/issues/{number}"


def github_comment_api(number: int) -> str:
    return f"https://api.github.com/repos/obsproject/obs-studio/issues/comments/{number}"


def creativecow_thread_url(slug: str) -> str:
    return f"https://creativecow.net/forums/thread/{slug}/"


def obs_evidence_fixture(row_count: int = 40, *, product_id: str = "obs-studio", version: str = "32.1.1") -> str:
    return fixture(*[
        row_yaml(
            id=f"obs-{number}",
            product_id=product_id,
            update_version=version,
            source_type="github_issue",
            source_url=f"https://github.com/obsproject/obs-studio/issues/{1000 + number}",
        )
        for number in range(1, row_count + 1)
    ])


def generated_record_text(
    *,
    product_id: str = "obs-studio",
    version: str = "32.1.1",
    update_report_count: int = 40,
    confirmed_count: int = 40,
    consensus_status: str = "pilot_initial_sample",
    evidence_state: str = "pilot_sample",
    evidence_last_checked: str = "2026-05-26T16:55:04Z",
) -> str:
    return (
        "---\n"
        f"product_id: {product_id}\n"
        f"update_version: {version}\n"
        f"update_report_count: {update_report_count}\n"
        f"confirmed_patch_specific_report_count: {confirmed_count}\n"
        f"consensus_collection_status: {consensus_status}\n"
        f"evidence_state: {evidence_state}\n"
        f"evidence_last_checked: '{evidence_last_checked}'\n"
        "---\n"
        "Fixture body must remain untouched.\n"
    )


def write_generated_case(base: Path, name: str, text: str | None = None) -> tuple[Path, Path]:
    generated_dir = base / name
    generated_dir.mkdir()
    record_path = generated_dir / revalidate_mod.EXPECTED_WRITEBACK_GENERATED_FILE
    record_path.write_text(text or generated_record_text(), encoding="utf-8")
    return generated_dir, record_path


def verified_issue_fetch(version: str = "32.1.1", *, missing_issue_number: int | None = None) -> Any:
    def fake_fetch(url: str) -> Any:
        issue_number = int(url.rstrip("/").split("/")[-1])
        if missing_issue_number is not None and issue_number == missing_issue_number:
            return {"title": "OBS issue without exact version", "body": "No matching patch here."}
        return {"title": f"OBS Studio {version} exact patch report", "body": "Fixture body."}
    return fake_fetch


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

        creativecow_fixture_path = tmp_path / "creativecow_fixture.yml"
        creativecow_fixture_path.write_text(
            fixture(
                row_yaml(
                    id="creativecow-direct-thread",
                    source_type="creator_forum_report",
                    source_url=creativecow_thread_url("ai-magic-mask-not-rendering"),
                ),
                row_yaml(
                    id="creativecow-listing-url",
                    source_type="creator_forum_report",
                    source_url="https://creativecow.net/forums/forum/davinci-resolve/",
                ),
            ),
            encoding="utf-8",
        )
        creativecow_fixture_result = revalidate_mod.revalidate(creativecow_fixture_path, "fixture-product", "1.2.3")
        creativecow_fixture_rows = {row["id"]: row for row in creativecow_fixture_result["rows"]}
        check(
            "Creative COW direct thread is a revalidation candidate without live fetch",
            creativecow_fixture_rows["creativecow-direct-thread"]["classification"] == "candidate_for_revalidation",
            json.dumps(creativecow_fixture_result, indent=2),
        )
        check(
            "Creative COW non-thread URL remains pending without live fetch",
            creativecow_fixture_rows["creativecow-listing-url"]["classification"] == "pending_source_adapter",
            json.dumps(creativecow_fixture_result, indent=2),
        )

        original_urlopen = revalidate_mod.urllib.request.urlopen
        captured_authorizations: list[str | None] = []

        def fake_urlopen(req: Any, timeout: int = 30) -> FakeResponse:
            headers = dict(req.header_items())
            captured_authorizations.append(headers.get("Authorization"))
            return FakeResponse({"ok": True})

        try:
            revalidate_mod.urllib.request.urlopen = fake_urlopen
            with patched_env(GITHUB_TOKEN="primary-secret-token", GH_TOKEN="fallback-secret-token"):
                revalidate_mod.request_json("https://api.github.test/repos/example/repo/issues/1")
            with patched_env(GITHUB_TOKEN=None, GH_TOKEN="fallback-secret-token"):
                revalidate_mod.request_json("https://api.github.test/repos/example/repo/issues/2")
            with patched_env(GITHUB_TOKEN=None, GH_TOKEN=None):
                revalidate_mod.request_json("https://api.github.test/repos/example/repo/issues/3")
        finally:
            revalidate_mod.urllib.request.urlopen = original_urlopen

        check("GITHUB_TOKEN authorization header is preferred", captured_authorizations[0] == "Bearer primary-secret-token", json.dumps(captured_authorizations))
        check("GH_TOKEN authorization header fallback works", captured_authorizations[1] == "Bearer fallback-secret-token", json.dumps(captured_authorizations))
        check("no token keeps unauthenticated request", captured_authorizations[2] is None, json.dumps(captured_authorizations))

        def fake_rate_limited_urlopen(req: Any, timeout: int = 30) -> FakeResponse:
            raise revalidate_mod.HTTPError(
                req.full_url,
                403,
                "Forbidden",
                {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1234567890"},
                None,
            )

        try:
            revalidate_mod.urllib.request.urlopen = fake_rate_limited_urlopen
            with patched_env(GITHUB_TOKEN="secret-token-never-print", GH_TOKEN=None):
                try:
                    revalidate_mod.request_json("https://api.github.test/repos/example/repo/issues/4")
                except revalidate_mod.SourceFetchError as exc:
                    rate_limit_reason = exc.reason
                else:
                    rate_limit_reason = "no_error"
        finally:
            revalidate_mod.urllib.request.urlopen = original_urlopen

        check(
            "rate-limit diagnostic is sanitized",
            rate_limit_reason == "github_rate_limited_until_1234567890"
            and "secret-token-never-print" not in rate_limit_reason,
            rate_limit_reason,
        )

        live_path = tmp_path / "live_consensus_evidence_fixture.yml"
        live_text = fixture(
            row_yaml(id="title-match", source_url="https://github.com/obsproject/obs-studio/issues/1"),
            row_yaml(id="body-match", source_url="https://github.com/obsproject/obs-studio/issues/2"),
            row_yaml(id="comment-match", source_url="https://github.com/obsproject/obs-studio/issues/3#issuecomment-300"),
            row_yaml(id="fetch-failed", source_url="https://github.com/obsproject/obs-studio/issues/4"),
            row_yaml(id="blocked", source_url="https://github.com/obsproject/obs-studio/issues/5"),
            row_yaml(id="blocked-429", source_url="https://github.com/obsproject/obs-studio/issues/7"),
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
            github_issue_api(7): revalidate_mod.SourceFetchError("github_rate_limited_until_1234567890", status=429),
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
        check("403 or 429 is blocked", live_rows["blocked"]["classification"] == "blocked" and live_rows["blocked-429"]["classification"] == "blocked", json.dumps(live_result, indent=2))
        check("missing exact version in fetched content fails", live_rows["no-version"]["classification"] == "exact_version_failed", json.dumps(live_result, indent=2))
        check("unsupported live source stays unsupported", live_rows["unsupported-live"]["classification"] == "unsupported_source_type", json.dumps(live_result, indent=2))
        check("live summary includes verified and failure counts", live_counts["verified"] == 3 and live_counts["exact_version_failed"] == 1 and live_counts["fetch_failed"] == 1 and live_counts["blocked"] == 2, json.dumps(live_counts))
        check("comment URL fetches parent issue and comment", github_issue_api(3) in requested_urls and github_comment_api(300) in requested_urls, json.dumps(requested_urls))

        live_summary = io.StringIO()
        with contextlib.redirect_stdout(live_summary):
            revalidate_mod.print_summary(live_result)
        summary_text = live_summary.getvalue()
        check("live summary output includes verified/failure counts", all(text in summary_text for text in ("verified: 3", "exact version failed: 1", "fetch failed: 1", "blocked: 2", "Live fetch enabled. No files written.")), summary_text)
        secret_output = summary_text + json.dumps(live_result, indent=2)
        check("token value never appears in output", "secret-token-never-print" not in secret_output, secret_output)

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

        creativecow_live_path = tmp_path / "creativecow_live_fixture.yml"
        creativecow_live_text = fixture(
            row_yaml(
                id="creativecow-title-match",
                source_type="creator_forum_report",
                source_url=creativecow_thread_url("title-match"),
            ),
            row_yaml(
                id="creativecow-body-match",
                source_type="creator_forum_report",
                source_url="https://www.creativecow.net/forums/thread/body-match",
            ),
            row_yaml(
                id="creativecow-no-version",
                source_type="creator_forum_report",
                source_url=creativecow_thread_url("no-version"),
            ),
            row_yaml(
                id="creativecow-fetch-failed",
                source_type="creator_forum_report",
                source_url=creativecow_thread_url("fetch-failed"),
            ),
            row_yaml(
                id="creativecow-blocked-http",
                source_type="creator_forum_report",
                source_url=creativecow_thread_url("blocked-http"),
            ),
            row_yaml(
                id="creativecow-blocked-challenge",
                source_type="creator_forum_report",
                source_url=creativecow_thread_url("blocked-challenge"),
            ),
            row_yaml(
                id="creativecow-malformed-url",
                source_type="creator_forum_report",
                source_url="https://creativecow.net/forums/forum/davinci-resolve/",
            ),
        )
        creativecow_live_path.write_text(creativecow_live_text, encoding="utf-8")
        creativecow_live_before = creativecow_live_path.read_text(encoding="utf-8")
        creativecow_responses: dict[str, Any] = {
            creativecow_thread_url("title-match"): "<html><title>DaVinci Resolve 1.2.3 render issue</title><body>No extra body.</body></html>",
            creativecow_thread_url("body-match"): "<html><title>DaVinci Resolve thread</title><body>Magic Mask failed after updating to 1.2.3.</body></html>",
            creativecow_thread_url("no-version"): "<html><title>DaVinci Resolve thread</title><body>This mentions 1.2.30 but not the target patch.</body></html>",
            creativecow_thread_url("fetch-failed"): revalidate_mod.SourceFetchError("http_500", status=500),
            creativecow_thread_url("blocked-http"): revalidate_mod.SourceFetchError("http_403", status=403),
            creativecow_thread_url("blocked-challenge"): "<html><title>Just a moment</title><body>Verify you are human before continuing.</body></html>",
        }
        creativecow_requested_urls: list[str] = []

        def fake_fetch_text(url: str) -> str:
            creativecow_requested_urls.append(url)
            value = creativecow_responses[url]
            if isinstance(value, Exception):
                raise value
            return value

        creativecow_live_result = revalidate_mod.revalidate(
            creativecow_live_path,
            "fixture-product",
            "1.2.3",
            live_fetch=True,
            fetch_text=fake_fetch_text,
        )
        creativecow_counts = creativecow_live_result["classification_counts"]
        creativecow_rows = {row["id"]: row for row in creativecow_live_result["rows"]}
        check(
            "Creative COW title contains target version verifies",
            creativecow_rows["creativecow-title-match"]["classification"] == "verified"
            and creativecow_rows["creativecow-title-match"].get("live_match_basis") == "creativecow_thread_title",
            json.dumps(creativecow_live_result, indent=2),
        )
        check(
            "Creative COW body contains target version verifies",
            creativecow_rows["creativecow-body-match"]["classification"] == "verified"
            and creativecow_rows["creativecow-body-match"].get("live_match_basis") == "creativecow_thread_text",
            json.dumps(creativecow_live_result, indent=2),
        )
        check(
            "Creative COW missing exact version fails",
            creativecow_rows["creativecow-no-version"]["classification"] == "exact_version_failed",
            json.dumps(creativecow_live_result, indent=2),
        )
        check(
            "Creative COW HTTP failure is fetch_failed",
            creativecow_rows["creativecow-fetch-failed"]["classification"] == "fetch_failed",
            json.dumps(creativecow_live_result, indent=2),
        )
        check(
            "Creative COW HTTP block or challenge is blocked",
            creativecow_rows["creativecow-blocked-http"]["classification"] == "blocked"
            and creativecow_rows["creativecow-blocked-challenge"]["classification"] == "blocked",
            json.dumps(creativecow_live_result, indent=2),
        )
        check(
            "Creative COW non-thread URL is malformed in live fetch",
            creativecow_rows["creativecow-malformed-url"]["classification"] == "malformed_row",
            json.dumps(creativecow_live_result, indent=2),
        )
        check(
            "Creative COW live counts are reported",
            creativecow_counts["verified"] == 2
            and creativecow_counts["exact_version_failed"] == 1
            and creativecow_counts["fetch_failed"] == 1
            and creativecow_counts["blocked"] == 2
            and creativecow_counts["malformed_row"] == 1,
            json.dumps(creativecow_counts),
        )
        check(
            "Creative COW www URLs are canonicalized before fetch",
            creativecow_thread_url("body-match") in creativecow_requested_urls,
            json.dumps(creativecow_requested_urls),
        )
        check("Creative COW live fixture file remains unchanged", creativecow_live_path.read_text(encoding="utf-8") == creativecow_live_before, creativecow_live_path.read_text(encoding="utf-8"))

        writeback_path = tmp_path / "obs_writeback_evidence.yml"
        writeback_path.write_text(obs_evidence_fixture(), encoding="utf-8")
        writeback_evidence_before = writeback_path.read_text(encoding="utf-8")
        generated_dir, record_path = write_generated_case(tmp_path, "generated_success")
        sibling_path = generated_dir / "unrelated-record.md"
        sibling_path.write_text(generated_record_text(product_id="other-product", version="9.9.9"), encoding="utf-8")
        sibling_before = sibling_path.read_text(encoding="utf-8")

        writeback_result = revalidate_mod.revalidate(
            writeback_path,
            "obs-studio",
            "32.1.1",
            live_fetch=True,
            fetch_json=verified_issue_fetch(),
        )
        writeback = revalidate_mod.guarded_generated_freshness_writeback(
            writeback_result,
            generated_dir=generated_dir,
            confirm_product="obs-studio",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        record_after = record_path.read_text(encoding="utf-8")
        check(
            "all verified rows update fixture generated record",
            writeback["success"] is True
            and "evidence_last_checked: '2099-01-02T03:04:05Z'" in record_after
            and writeback_result["writes_files"] is True
            and writeback_result["mode"] == revalidate_mod.WRITEBACK_MODE,
            json.dumps(writeback, indent=2),
        )
        check("writeback leaves evidence fixture unchanged", writeback_path.read_text(encoding="utf-8") == writeback_evidence_before, writeback_path.read_text(encoding="utf-8"))
        check("writeback mutates only intended temp generated record", sibling_path.read_text(encoding="utf-8") == sibling_before, sibling_path.read_text(encoding="utf-8"))

        failed_generated_dir, failed_record_path = write_generated_case(tmp_path, "generated_failed_row")
        failed_record_before = failed_record_path.read_text(encoding="utf-8")
        one_failed_result = revalidate_mod.revalidate(
            writeback_path,
            "obs-studio",
            "32.1.1",
            live_fetch=True,
            fetch_json=verified_issue_fetch(missing_issue_number=1007),
        )
        one_failed_writeback = revalidate_mod.guarded_generated_freshness_writeback(
            one_failed_result,
            generated_dir=failed_generated_dir,
            confirm_product="obs-studio",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        check(
            "one failed row blocks writeback",
            one_failed_writeback["success"] is False
            and failed_record_path.read_text(encoding="utf-8") == failed_record_before
            and any("exact_version_failed=1" in reason for reason in one_failed_writeback["guard_failures"]),
            json.dumps(one_failed_writeback, indent=2),
        )

        count_mismatch_path = tmp_path / "obs_writeback_39.yml"
        count_mismatch_path.write_text(obs_evidence_fixture(row_count=39), encoding="utf-8")
        count_generated_dir, count_record_path = write_generated_case(tmp_path, "generated_count_mismatch")
        count_record_before = count_record_path.read_text(encoding="utf-8")
        count_result = revalidate_mod.revalidate(
            count_mismatch_path,
            "obs-studio",
            "32.1.1",
            live_fetch=True,
            fetch_json=verified_issue_fetch(),
        )
        count_writeback = revalidate_mod.guarded_generated_freshness_writeback(
            count_result,
            generated_dir=count_generated_dir,
            confirm_product="obs-studio",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        check(
            "count mismatch blocks writeback",
            count_writeback["success"] is False
            and count_record_path.read_text(encoding="utf-8") == count_record_before
            and any("selected counted rows must total exactly 40" in reason for reason in count_writeback["guard_failures"]),
            json.dumps(count_writeback, indent=2),
        )

        wrong_product_path = tmp_path / "obs_writeback_wrong_product.yml"
        wrong_product_path.write_text(obs_evidence_fixture(product_id="not-obs"), encoding="utf-8")
        wrong_product_dir, wrong_product_record = write_generated_case(tmp_path, "generated_wrong_product")
        wrong_product_before = wrong_product_record.read_text(encoding="utf-8")
        wrong_product_result = revalidate_mod.revalidate(
            wrong_product_path,
            "not-obs",
            "32.1.1",
            live_fetch=True,
            fetch_json=verified_issue_fetch(),
        )
        wrong_product_writeback = revalidate_mod.guarded_generated_freshness_writeback(
            wrong_product_result,
            generated_dir=wrong_product_dir,
            confirm_product="not-obs",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        check(
            "wrong product/version blocks writeback",
            wrong_product_writeback["success"] is False
            and wrong_product_record.read_text(encoding="utf-8") == wrong_product_before
            and any("product must be exactly obs-studio" in reason for reason in wrong_product_writeback["guard_failures"])
            and any("--confirm-product must be exactly obs-studio" in reason for reason in wrong_product_writeback["guard_failures"]),
            json.dumps(wrong_product_writeback, indent=2),
        )

        missing_record_dir = tmp_path / "generated_missing_record"
        missing_record_dir.mkdir()
        missing_record_result = revalidate_mod.revalidate(
            writeback_path,
            "obs-studio",
            "32.1.1",
            live_fetch=True,
            fetch_json=verified_issue_fetch(),
        )
        missing_record_writeback = revalidate_mod.guarded_generated_freshness_writeback(
            missing_record_result,
            generated_dir=missing_record_dir,
            confirm_product="obs-studio",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        check(
            "wrong generated file/path blocks writeback",
            missing_record_writeback["success"] is False
            and any("expected generated record does not exist" in reason for reason in missing_record_writeback["guard_failures"]),
            json.dumps(missing_record_writeback, indent=2),
        )

        report_count_dir, report_count_record = write_generated_case(
            tmp_path,
            "generated_report_count_mismatch",
            generated_record_text(update_report_count=39, confirmed_count=39),
        )
        report_count_before = report_count_record.read_text(encoding="utf-8")
        report_count_result = revalidate_mod.revalidate(
            writeback_path,
            "obs-studio",
            "32.1.1",
            live_fetch=True,
            fetch_json=verified_issue_fetch(),
        )
        report_count_writeback = revalidate_mod.guarded_generated_freshness_writeback(
            report_count_result,
            generated_dir=report_count_dir,
            confirm_product="obs-studio",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        check(
            "report count mismatch blocks writeback",
            report_count_writeback["success"] is False
            and report_count_record.read_text(encoding="utf-8") == report_count_before
            and any("generated record report counts must still be 40" in reason for reason in report_count_writeback["guard_failures"]),
            json.dumps(report_count_writeback, indent=2),
        )

        evidence_state_dir, evidence_state_record = write_generated_case(
            tmp_path,
            "generated_evidence_state_mismatch",
            generated_record_text(evidence_state="official_only"),
        )
        evidence_state_before = evidence_state_record.read_text(encoding="utf-8")
        evidence_state_result = revalidate_mod.revalidate(
            writeback_path,
            "obs-studio",
            "32.1.1",
            live_fetch=True,
            fetch_json=verified_issue_fetch(),
        )
        evidence_state_writeback = revalidate_mod.guarded_generated_freshness_writeback(
            evidence_state_result,
            generated_dir=evidence_state_dir,
            confirm_product="obs-studio",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        check(
            "evidence_state not pilot_sample blocks writeback",
            evidence_state_writeback["success"] is False
            and evidence_state_record.read_text(encoding="utf-8") == evidence_state_before
            and any("evidence_state must remain pilot_sample" in reason for reason in evidence_state_writeback["guard_failures"]),
            json.dumps(evidence_state_writeback, indent=2),
        )

        consensus_status_dir, consensus_status_record = write_generated_case(
            tmp_path,
            "generated_consensus_status_mismatch",
            generated_record_text(consensus_status="consensus_live"),
        )
        consensus_status_before = consensus_status_record.read_text(encoding="utf-8")
        consensus_status_result = revalidate_mod.revalidate(
            writeback_path,
            "obs-studio",
            "32.1.1",
            live_fetch=True,
            fetch_json=verified_issue_fetch(),
        )
        consensus_status_writeback = revalidate_mod.guarded_generated_freshness_writeback(
            consensus_status_result,
            generated_dir=consensus_status_dir,
            confirm_product="obs-studio",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        check(
            "consensus_collection_status not pilot blocks writeback",
            consensus_status_writeback["success"] is False
            and consensus_status_record.read_text(encoding="utf-8") == consensus_status_before
            and any("consensus_collection_status must remain pilot_initial_sample" in reason for reason in consensus_status_writeback["guard_failures"]),
            json.dumps(consensus_status_writeback, indent=2),
        )

        no_live_dir, no_live_record = write_generated_case(tmp_path, "generated_no_live")
        no_live_before = no_live_record.read_text(encoding="utf-8")
        no_live_result = revalidate_mod.revalidate(writeback_path, "obs-studio", "32.1.1")
        no_live_writeback = revalidate_mod.guarded_generated_freshness_writeback(
            no_live_result,
            generated_dir=no_live_dir,
            confirm_product="obs-studio",
            confirm_version="32.1.1",
            timestamp="2099-01-02T03:04:05Z",
        )
        check(
            "no --live-fetch blocks writeback",
            no_live_writeback["success"] is False
            and no_live_record.read_text(encoding="utf-8") == no_live_before
            and any("--live-fetch is required" in reason for reason in no_live_writeback["guard_failures"]),
            json.dumps(no_live_writeback, indent=2),
        )

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
