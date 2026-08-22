#!/usr/bin/env python3
"""Fail-soft evidence collection: isolation, merge semantics, and partial visibility (Reqs 1 & 3).

Guarantees under test:
  * one collector's failure never aborts the run and never erases its last-known-good data;
  * method-health merge = existing committed rows + successful current rows; a failed collector
    contributes NO rows (never replaced with no_results, never inferred to have found zero reports);
  * a partial run is machine-readable (outcome=partial), loudly annotated, summarized, and still
    publishes healthy collectors (exit 0); a total failure is exit 1; full success is exit 0;
  * failure reasons are normalized -- no raw exception text, token, path, header, or stack trace.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_failsoft_collection.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_patch_evidence_collection as R  # noqa: E402
from patch_collectors import base  # noqa: E402

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def _row(pid: str, status: str, version: str = "1.0", method: str = "m1", accepted: int = 0) -> dict:
    return base.method_health_row(
        product_id=pid, update_version=version, method_id=method, source_type="s",
        status=status, candidates_found=accepted, accepted_reports=accepted, rejected_reports=0,
        blocked_reason="", last_run="2026-07-29T00:00:00Z", notes="",
    )


class _OK:
    def __init__(self, pid: str, accepted: int = 2) -> None:
        self.pid, self.accepted = pid, accepted

    def collect(self, ctx):
        return [{"product_id": self.pid, "accepted_count": self.accepted, "rejected_count": 0,
                 "method_health": [_row(self.pid, "success", accepted=self.accepted)]}]


class _Boom:
    def __init__(self, pid: str) -> None:
        self.pid = pid

    def collect(self, ctx):
        # message deliberately carries "secret", a token, and a filesystem path to prove they never leak
        raise RuntimeError("Authorization: Bearer sk-secret-abcdef token=zzz at /home/runner/work/x.py line 5")


def _run_main(collectors_map: dict, argv: list[str]):
    R.build_collectors = lambda env=None: collectors_map  # type: ignore[assignment]
    outdir = tempfile.mkdtemp(prefix="failsoft-")
    summ = os.path.join(outdir, "summary.md")
    gho = os.path.join(outdir, "out.txt")
    os.environ["GITHUB_STEP_SUMMARY"] = summ
    os.environ["GITHUB_OUTPUT"] = gho
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = R.main(argv)
    finally:
        os.environ.pop("GITHUB_STEP_SUMMARY", None)
        os.environ.pop("GITHUB_OUTPUT", None)
    out = buf.getvalue()
    payload = json.loads(out[out.index("{"):])
    summary_text = Path(summ).read_text(encoding="utf-8") if Path(summ).exists() else ""
    output_text = Path(gho).read_text(encoding="utf-8") if Path(gho).exists() else ""
    return rc, payload, out, summary_text, output_text


def run() -> int:
    print("=" * 60)
    print("Fail-soft collection tests")
    print("=" * 60)

    # --- normalize_failure_reason: category + no raw leak -----------------------
    import urllib.error
    import yaml
    r_parse = R.normalize_failure_reason(yaml.scanner.ScannerError("boom /home/x token=abc"))
    r_http = R.normalize_failure_reason(urllib.error.HTTPError("http://x", 403, "Forbidden", {}, None))
    r_other = R.normalize_failure_reason(RuntimeError("secret token=abcdef /home/runner/x"))
    check("YAML error -> record_parse_error category", r_parse.startswith("record_parse_error:"))
    check("HTTP error -> source_fetch_error category", r_http.startswith("source_fetch_error:"))
    check("other -> collector_error category", r_other == "collector_error:RuntimeError")
    for reason in (r_parse, r_http, r_other):
        check(f"normalized reason leaks nothing sensitive ({reason})",
              not any(s in reason for s in ("token", "secret", "/home", "Bearer", "abcdef", "Authorization", "line 5")))

    # --- merge semantics via upsert on a temp file (Req 1) ----------------------
    emh = Path(tempfile.mkdtemp(prefix="emh-")) / "evidence_method_health.yml"
    base.write_method_health_file([_row("prodA", "success"), _row("prodB", "success", accepted=3)], emh)
    before = {base.method_health_key(r): r for r in base.load_method_health(emh)}
    # prodA succeeds this run (new status); prodB FAILED this run -> contributes NO rows.
    changed, total, rows = base.upsert_method_health([_row("prodA", "no_results")], emh)
    after = {base.method_health_key(r): r for r in base.load_method_health(emh)}
    check("failed collector's committed row is RETAINED byte-for-byte (last-known-good)",
          after[("prodB", "1.0", "", "m1")] == before[("prodB", "1.0", "", "m1")])
    check("successful collector's row is updated by the merge",
          after[("prodA", "1.0", "", "m1")]["status"] == "no_results")
    check("no fabricated rows for the failed collector (row count unchanged)", total == 2)
    check("failed collector never gets a no_results it didn't report",
          after[("prodB", "1.0", "", "m1")]["status"] == "success")

    # --- runner outcomes + visibility (Req 3), all in dry-run (no write) --------
    rc, payload, out, summary, output = _run_main(
        {"prodA": lambda: _OK("prodA"), "prodB": lambda: _Boom("prodB")}, ["--dry-run"])
    check("partial: outcome=partial", payload["outcome"] == "partial")
    check("partial: exit 0 (healthy collectors publishable)", rc == 0)
    check("partial: writeback_eligible True", payload["writeback_eligible"] is True)
    check("partial: failed collector named", payload["failed_collectors"] == ["prodB"])
    check("partial: ::warning:: annotation emitted for the failed collector",
          "::warning" in out and "prodB" in out)
    check("partial: job summary names the failed collector + PARTIAL", "PARTIAL" in summary and "prodB" in summary)
    check("partial: GITHUB_OUTPUT carries machine-readable outcome", "outcome=partial" in output)
    check("partial: healthy collector's accepted count present", payload["accepted_count"] >= 2)
    check("partial: failed collector contributes 0 health rows",
          next(c for c in payload["collectors"] if c["product_id"] == "prodB")["method_health_rows"] == 0)
    check("partial: no raw exception text in stdout/summary",
          not any(s in (out + summary) for s in ("Bearer", "sk-secret", "/home/runner", "line 5")))

    rc_f, payload_f, _o, _s, _out = _run_main({"a": lambda: _Boom("a"), "b": lambda: _Boom("b")}, ["--dry-run"])
    check("total failure: outcome=failed", payload_f["outcome"] == "failed")
    check("total failure: exit 1 (nothing to publish)", rc_f == 1)
    check("total failure: writeback_eligible False", payload_f["writeback_eligible"] is False)

    rc_s, payload_s, _o2, _s2, _out2 = _run_main({"a": lambda: _OK("a"), "b": lambda: _OK("b")}, ["--dry-run"])
    check("full success: outcome=success", payload_s["outcome"] == "success")
    check("full success: exit 0", rc_s == 0)

    print()
    print("=" * 60)
    total_checks = _PASS + _FAIL
    print(f"Results: {_PASS}/{total_checks} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
