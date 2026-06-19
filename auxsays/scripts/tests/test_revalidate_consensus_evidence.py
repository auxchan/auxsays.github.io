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
