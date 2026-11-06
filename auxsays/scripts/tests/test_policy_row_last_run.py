#!/usr/bin/env python3
"""A never-run, policy-disabled method row on a NEW patch must validate (AUX-081).

Production incident 2026-11-05: the first new patch since the Reddit access policy (AUX-064),
DaVinci Resolve 21.2, made its collector emit a `reddit_search` row with status `disabled`, reason
`reddit_access_policy_unauthorised` and `last_run: ""`. The writer keeps the PRIOR row's last attempt
for a key that already exists, but a new key has no prior row, so the row was stored with an empty
last_run -- and `validate_evidence_method_health.py` required last_run on every row. The writeback
refused before committing, on every run, for every product.

The rule now: last_run may be empty ONLY on a policy-disabled row (`is_policy_disabled_row`: status
`disabled` AND exactly that reason -- not a reason that resembles it or contains it). Every other row
still needs it, and a non-empty value on a policy row must still look like a timestamp. Nothing stamps a
time on a row that made no attempt.

Offline and deterministic. Fixtures are frozen: section B/C use the five 21.2 rows exactly as the
failed run's receipt recorded them. Every store is a temp file; nothing under auxsays/_data is read
for writing or written.

  A  the validator rule, row shape by row shape
  B  the real writer (upsert_method_health) feeding the validator, in process
  C  writeback-shaped: the writer and the validator each run as a separate BARE-SCRIPT child process
  D  consumers of last_run: an empty value on a disabled row changes no monitoring or H0-H7 decision
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
SCRIPTS = ROOT / "scripts"
VALIDATOR = SCRIPTS / "validate_evidence_method_health.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml                                                      # noqa: E402
from validate_evidence_method_health import validate             # noqa: E402
from lib import reddit_access_policy as pol                      # noqa: E402
from lib import monitoring_health as mh                          # noqa: E402
from lib import collector_ownership                              # noqa: E402
from patch_collectors import base                                # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


# --- frozen fixtures ----------------------------------------------------------------------------
def _row(method_id: str, source_type: str, status: str, blocked_reason: str, last_run: str,
         notes: str, *, candidates: int = 0, rejected: int = 0, version: str = "21.2",
         product_id: str = "blackmagic-davinci") -> dict:
    return {
        "product_id": product_id, "update_version": version, "target_build": "",
        "method_id": method_id, "source_type": source_type, "status": status,
        "candidates_found": candidates, "accepted_candidates": 0, "duplicate_existing_evidence": 0,
        "evidence_rows_added": 0, "public_counted_reports": 0, "accepted_reports": 0,
        "rejected_reports": rejected, "blocked_reason": blocked_reason, "last_run": last_run,
        "notes": notes,
    }


# The five blackmagic-davinci 21.2 rows of run 42098340497's receipt, verbatim.
RUN_21_2 = (
    _row("known_watchlist", "curated_watchlist", "blocked",
         "probe_fetch_failed:http_202_aws_waf_challenge x6", "2026-11-05T20:37:26Z",
         "Temporary seed/calibration fallback. Specific known report URLs are fetched and passed "
         "through the same deterministic evidence gates, but this must not be the primary long-term "
         "DaVinci discovery method. Fetch failures: 6."),
    _row("reddit_search", "reddit_community_report", "disabled",
         "reddit_access_policy_unauthorised", "", pol.POLICY_NOTE),
    _row("creative_cow_forum_search", "creator_forum_report", "partial",
         "creative_cow_thread_fetch_failed:http_429_Too Many Requests x12", "2026-11-05T20:37:26Z",
         "Creative COW DaVinci Resolve forum listing discovers public thread URLs, fetches specific "
         "threads, and passes candidates through exact version/date/report gates. This is "
         "community/creator evidence, not official vendor evidence. Fetch failures: 12. Rejected "
         "candidates: missing_exact_patch_version_match=3.", candidates=3, rejected=3),
    _row("vendor_forum_search", "blackmagic_forum", "blocked",
         "vendor_forum_search_blocked_or_failed:http_202_aws_waf_challenge", "2026-11-05T20:37:26Z",
         "Blackmagic forum acquisition did not return usable forum content. No unusable source checks "
         "were counted as reports. vendor_forum_search_blocked_or_failed:http_202_aws_waf_challenge"),
    _row("web_search", "web_search", "disabled", "web_search_adapter_disabled_in_phase_a",
         "2026-11-05T20:37:26Z",
         "Reserved fallback discovery method; no adapter is configured in Phase A. Fetch failures: 1."),
)
POLICY_21_2 = RUN_21_2[1]

# A store that already holds an older DaVinci patch, so 21.2 is a NEW identity in it.
PRIOR_STORE = (
    _row("reddit_search", "reddit_community_report", "disabled",
         "reddit_access_policy_unauthorised", "2026-11-04T00:18:00Z", pol.POLICY_NOTE,
         version="21.1.2"),
    _row("known_watchlist", "curated_watchlist", "no_results", "", "2026-11-05T20:37:26Z",
         "Watchlist fixture.", version="21.1.2"),
)


def write_store(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "methods": [dict(r) for r in rows]}
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=1000),
                    encoding="utf-8")


def run_validator(path: Path) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = validate(path)
    return code, out.getvalue()


def one(rows, tmp: Path, name: str) -> tuple[int, str]:
    path = tmp / f"{name}.yml"
    write_store(path, rows)
    return run_validator(path)


def variant(row: dict, **over) -> dict:
    out = dict(row)
    out.update(over)
    return out


def refused_last_run(code: int, output: str, row_index: int = 1) -> bool:
    return code != 0 and f"FAIL row {row_index} field last_run: is required" in output


def run() -> int:
    print("=" * 60)
    print("Policy-disabled method row on a new patch: last_run (AUX-081)")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ---- A: the validator rule ---------------------------------------------------------------
        print("A. validator rule")
        code, out = one([POLICY_21_2], tmp, "a1")
        check("A.1 a new patch's policy-disabled row with an empty last_run passes", code == 0, out)

        code, out = one([variant(POLICY_21_2, blocked_reason="web_search_adapter_disabled_in_phase_a")],
                        tmp, "a2")
        check("A.2 a disabled row with ANOTHER reason and no last_run is still refused",
              refused_last_run(code, out), out)

        code, out = one([variant(POLICY_21_2, blocked_reason="")], tmp, "a3")
        check("A.3 a disabled row with NO reason and no last_run is still refused",
              refused_last_run(code, out), out)

        code, out = one([variant(POLICY_21_2, status="blocked")], tmp, "a4")
        check("A.4 a Reddit row carrying the policy reason but status `blocked` and no last_run is refused",
              refused_last_run(code, out), out)

        code, out = one([variant(POLICY_21_2, status="no_results", blocked_reason="")], tmp, "a5")
        check("A.5 a Reddit row reading `no_results` with no last_run is refused",
              refused_last_run(code, out), out)

        code, out = one([variant(RUN_21_2[0], status="success", blocked_reason="", last_run="")], tmp, "a6")
        check("A.6 an ordinary method row with no last_run is refused", refused_last_run(code, out), out)

        code, out = one([variant(POLICY_21_2, last_run="not-a-time")], tmp, "a7")
        check("A.7 a malformed non-empty last_run on a policy row is still refused",
              code != 0 and "field last_run: must look like a timestamp" in out, out)

        code, out = one([variant(POLICY_21_2, last_run="   ")], tmp, "a8")
        check("A.8 a whitespace-only last_run on a policy row is refused (empty means empty)",
              code != 0 and "field last_run: must look like a timestamp" in out, out)

        code, out = one([variant(POLICY_21_2, last_run="2026-11-04T00:18:00Z")], tmp, "a9")
        check("A.9 a policy row carrying a real prior attempt time passes", code == 0, out)

        no_key = dict(POLICY_21_2)
        del no_key["last_run"]
        code, out = one([no_key], tmp, "a10")
        check("A.10 a policy row with no last_run key passes (the rule's own meaning of empty)",
              code == 0, out)

        code, out = one([variant(POLICY_21_2, source_type="")], tmp, "a11")
        check("A.11 the exemption excuses last_run only: a policy row missing source_type is refused",
              code != 0 and "field source_type: is required" in out and "field last_run" not in out, out)

        mixed = [POLICY_21_2, variant(RUN_21_2[3], last_run="")]
        code, out = one(mixed, tmp, "a12")
        check("A.12 the exemption is per row: the policy row passes, its neighbour without last_run fails",
              refused_last_run(code, out, 2) and "row 1 field" not in out and "1 error(s)" in out, out)

        code, out = one(list(PRIOR_STORE) + list(RUN_21_2), tmp, "a13")
        check("A.13 the failed run's 21.2 rows beside an older patch validate", code == 0, out)

        # The policy reason is one exact token. A reason that only RESEMBLES it, or merely CONTAINS it,
        # names some other condition, and that row still needs last_run.
        def near_misses(reasons, name: str) -> list[str]:
            accepted = []
            for idx, reason in enumerate(reasons):
                code, out = one([variant(POLICY_21_2, blocked_reason=reason)], tmp, f"{name}_{idx}")
                if not refused_last_run(code, out):
                    accepted.append(reason)
            return accepted

        accepted = near_misses(("reddit_rate_limited", "reddit_access_policy_unauthorized",
                                pol.POLICY_REASON.upper()), "a14")
        check("A.14 a disabled row whose reason only RESEMBLES the policy reason (another Reddit reason, "
              "the US spelling, upper case) and no last_run is refused", not accepted, f"accepted: {accepted}")

        accepted = near_misses((f"{pol.POLICY_REASON} x2", f"probe_failed:{pol.POLICY_REASON}"), "a15")
        check("A.15 a disabled row whose reason merely CONTAINS the policy reason (a suffix, a prefix) and "
              "no last_run is refused", not accepted, f"accepted: {accepted}")

        # ---- B: the real writer feeding the validator --------------------------------------------
        print("B. writer -> validator")
        store = tmp / "b" / "evidence_method_health.yml"
        write_store(store, PRIOR_STORE)
        before_rows = base.load_method_health(store)
        changed, total, rows = base.upsert_method_health([dict(r) for r in RUN_21_2], store)
        check("B.1 a new identity's five rows are appended", changed == 5 and total == 7, f"{changed} {total}")
        stored_policy = [r for r in rows if r["update_version"] == "21.2" and r["method_id"] == "reddit_search"]
        check("B.2 the new policy row keeps an empty last_run: no run time is stamped on a row that made no attempt",
              len(stored_policy) == 1 and stored_policy[0]["last_run"] == "", str(stored_policy))
        code, out = run_validator(store)
        check("B.3 the validator passes over what the writer stored", code == 0, out)
        check("B.4 the rows already in the store are unchanged",
              base.load_method_health(store)[:2] == before_rows, "prior rows moved")
        changed2, _t, _r = base.upsert_method_health([dict(r) for r in RUN_21_2], store)
        check("B.5 re-running the same cycle changes nothing", changed2 == 0, str(changed2))

        inherit = tmp / "b2" / "evidence_method_health.yml"
        write_store(inherit, PRIOR_STORE)
        _c, _t, rows = base.upsert_method_health(
            [variant(POLICY_21_2, update_version="21.1.2")], inherit)
        got = [r for r in rows if r["update_version"] == "21.1.2" and r["method_id"] == "reddit_search"][0]
        check("B.6 an EXISTING policy key still keeps its prior real attempt (inheritance unchanged)",
              got["last_run"] == "2026-11-04T00:18:00Z", got["last_run"])
        code, out = run_validator(inherit)
        check("B.7 ... and validates", code == 0, out)

        _c, _t, rows = base.upsert_method_health(
            [variant(PRIOR_STORE[1], last_run="")], inherit)
        got = [r for r in rows if r["update_version"] == "21.1.2" and r["method_id"] == "known_watchlist"][0]
        code, out = run_validator(inherit)
        check("B.8 an existing ORDINARY key gets no carry-over, and its empty last_run is refused",
              got["last_run"] == "" and code != 0 and "field last_run: is required" in out, out)

        # ---- C: writeback-shaped, every step a bare-script child process -------------------------
        print("C. writeback-shaped run (child processes)")
        tree = tmp / "tree"
        tree_store = tree / "auxsays" / "_data" / "evidence_method_health.yml"
        write_store(tree_store, PRIOR_STORE)
        rows_file = tmp / "rows.json"
        rows_file.write_text(json.dumps([dict(r) for r in RUN_21_2]), encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        writer = (
            "import json, sys; from pathlib import Path\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "from patch_collectors.base import upsert_method_health\n"
            f"rows = json.loads(Path({str(rows_file)!r}).read_text(encoding='utf-8'))\n"
            f"changed, total, _ = upsert_method_health(rows, Path({str(tree_store)!r}))\n"
            "print(f'UPSERT changed={changed} total={total}')\n"
        )
        w = subprocess.run([sys.executable, "-c", writer], cwd=str(tree), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=300)
        check("C.1 the writer child appends the 21.2 rows", w.returncode == 0 and "UPSERT changed=5 total=7" in w.stdout,
              (w.stdout + w.stderr)[-600:])
        # Exactly the writeback's invocation: `python auxsays/scripts/validate_evidence_method_health.py`
        # from the tree root, default path, run as a bare script.
        v = subprocess.run([sys.executable, str(VALIDATOR)], cwd=str(tree), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=300)
        check("C.2 the validator, run as a bare script from the tree root on its default path, exits 0",
              v.returncode == 0 and "validation passed: 7 method rows checked" in v.stdout,
              (v.stdout + v.stderr)[-600:])
        bad_tree = tmp / "bad_tree"
        write_store(bad_tree / "auxsays" / "_data" / "evidence_method_health.yml",
                    list(PRIOR_STORE) + [variant(RUN_21_2[0], last_run="")])
        v2 = subprocess.run([sys.executable, str(VALIDATOR)], cwd=str(bad_tree), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env, timeout=300)
        check("C.3 the same bare-script run still exits 1 on an ordinary row without last_run",
              v2.returncode == 1 and "FAIL row 3 field last_run: is required" in v2.stdout,
              (v2.stdout + v2.stderr)[-600:])

        # ---- D: consumers of last_run --------------------------------------------------------------
        print("D. consumers of last_run")
        check("D.1 the monitoring authority reads an empty last_run as no time (None), not as a crash or 0",
              mh._epoch("") is None and mh._epoch(None) is None)
        now = datetime(2026, 11, 5, 22, 0, tzinfo=timezone.utc)
        thresholds = mh.Thresholds(max_age_days=14, min_healthy_families=2)
        stamped = [variant(r, last_run="2026-11-05T20:37:26Z") if r is POLICY_21_2 else dict(r) for r in RUN_21_2]
        old = [variant(r, last_run="2020-01-01T00:00:00Z") if r is POLICY_21_2 else dict(r) for r in RUN_21_2]
        future = [variant(r, last_run="2099-01-01T00:00:00Z") if r is POLICY_21_2 else dict(r) for r in RUN_21_2]
        as_run = [dict(r) for r in RUN_21_2]

        def card(rows):
            return mh.ladder(rows, published_at="2026-11-05", report_count=0, now=now, thresholds=thresholds)

        labels = {card(as_run), card(stamped), card(old), card(future)}
        check("D.2 the public monitoring card is the same whatever the disabled row's last_run holds",
              len(labels) == 1, str(labels))
        check("D.3 the policy row alone is never read as collection (OFFICIAL SOURCE ONLY)",
              card([dict(POLICY_21_2)]) == mh.OFFICIAL_SOURCE_ONLY
              == card([variant(POLICY_21_2, last_run="2026-11-05T20:37:26Z")]), card([dict(POLICY_21_2)]))

        def certify(rows):
            return mh.certify_monitoring(
                "blackmagic-davinci", rows, published_at="2026-11-05",
                contributing_families=set(), now=now, thresholds=thresholds,
                owned_methods=collector_ownership.ALLOWED_METHODS,
                manual_only_methods=collector_ownership.MANUAL_ONLY_METHODS)

        decisions = {certify(rows) for rows in (as_run, stamped, old, future)}
        check("D.4 H0-H7 decide the same, reasons and all, whatever the disabled row's last_run holds",
              len(decisions) == 1, str(decisions))
        reasons = certify(as_run).reasons
        check("D.5 no certification reason is about the policy row's timestamp, and it is not certified healthy",
              not any("reddit_search" in r for r in reasons) and not certify(as_run).healthy, str(reasons))

    print()
    print("=" * 60)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed tests:")
        for label in FAILURES:
            print(f"  - {label}")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
