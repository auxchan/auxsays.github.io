#!/usr/bin/env python3
"""The writers that print into public workflow logs never print a report's stored title or excerpt.

THE DEFECT (G66). Actions run logs of this public repository are readable by any signed-in GitHub
user and kept 90 days. `apply_consensus_to_records.py` -- run without --output by thirteen workflow
steps -- printed its whole JSON report on stdout, and that report carries every counted report's
stored title three times (`included_rows[].source_title`, and `source_title` inside the proposed
`accepted_report_sources` and `evidence_samples`). Collection run 44609489525 printed 3,888 such
lines; on 2026-11-20, 609 of the 683 retained runs of the two lanes that run it held 1,153,112.
A content scan of the stored titles against the latest run of every printing lane (collection,
the orchestrated PowerPoint job, ingestion, CI, Pages, the queue reaper) found them in that one
writer's steps and nowhere else.

WHAT THIS SUITE PINS, with a canary string in every stored text field:
  [R] lib.log_redaction.log_safe removes every listed key at any depth, keeps ids, URLs, counts and
      categories, never mutates its input, and its closed list covers every text-bearing field the
      live data files carry (a new one fails here until it is listed).
  [P] the promotion writer, end to end through its own main() over a temp tree: dry run, --write-all
      and --write print no canary on stdout or stderr, and --output writes none -- while the record
      it writes still stores the titles (only the printed view changes). Non-vacuity: the in-memory
      report demonstrably carries the canaries before it is printed.
  [C] the collection runner's printed payload drops a canary a collector returns, keeping the rest.
  [K] reconciliation's log lines and [Q] QA's messages over the same canary tree carry none.

Deterministic and offline: no network, no git, writes only inside a temp dir.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_log_title_hygiene.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
import qa_patch_records as qa  # noqa: E402
import run_patch_evidence_collection as rpec  # noqa: E402
from lib import log_redaction  # noqa: E402
from lib.log_redaction import THIRD_PARTY_TEXT_KEYS, log_safe  # noqa: E402
from lib.report_counts import format_maturity_transition, format_reconcile_detail, reconcile_record_counts  # noqa: E402

DAV = "blackmagic-davinci"
VERSION = "20.3.2"
NEWLINE = "\n"
DATA = _REPO / "auxsays" / "_data"

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
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


# ---------------------------------------------------------------- canaries

def canary(field: str, n: int) -> str:
    """A string no real data or template contains, unique per field and row."""
    return f"zq7canary {field} {n} xk"


def leaks(text: str) -> list[str]:
    return sorted(set(re.findall(r"zq7canary [a-z_]+ \d+ xk", text)))


def evidence_row(n: int) -> dict:
    """A DaVinci row shaped like the live corpus that passes every promotion gate, with a canary in
    every field that holds text taken from a report."""
    return {
        "id": f"{DAV}-{VERSION}-row-{n}",
        "product_id": DAV,
        "update_version": VERSION,
        "source_type": "blackmagic_forum",
        "source_name": "Blackmagic Design Community Forum",
        "source_url": f"https://forum.example.invalid/t/{VERSION}/{n}",
        "report_title": canary("report_title", n),
        "parent_title": canary("parent_title", n),
        "report_text_excerpt": canary("report_text_excerpt", n),
        "matched_text": canary("matched_text", n),
        "matched_context": canary("matched_context", n),
        "listing_card_title": canary("listing_card_title", n),
        "captured_at": "2026-09-01T00:00:00Z",
        "patch_version_matched": True,
        "matched_version": VERSION,
        "counted": True,
        "issue_theme": "playback_stutter",
        "severity": "high",
        "sentiment": "negative",
        "source_weight": 1,
    }


def write_record(path: Path, *, count: int) -> None:
    data = {
        "layout": "aux-update", "update_entry": True,
        "product_id": DAV, "update_version": VERSION, "update_product": "DaVinci Resolve",
        "update_report_count": count, "confirmed_patch_specific_report_count": count,
        # A stale projection that ALREADY carries canary titles, as a live record does.
        "accepted_report_sources": [{"source_url": f"https://forum.example.invalid/t/{VERSION}/{i}",
                                     "source_title": canary("source_title", i)} for i in range(count)],
        "evidence_samples": [{"source_url": f"https://forum.example.invalid/t/{VERSION}/0",
                              "source_title": canary("source_title", 0), "counted": True,
                              "patch_version_matched": False}],
        "update_consensus_summary": f"WAIT: DaVinci Resolve {VERSION} has {count} user reports found.",
        "consensus_report": f"{count} user reports found for DaVinci Resolve {VERSION}.",
        "quick_verdict": f"WAIT: DaVinci Resolve {VERSION} has {count} user reports found.",
    }
    path.write_text("---" + NEWLINE + yaml.safe_dump(data, sort_keys=False) + "---" + NEWLINE + "body" + NEWLINE,
                    encoding="utf-8")


def write_evidence(path: Path, rows: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "evidence": rows}, sort_keys=False), encoding="utf-8")


@contextlib.contextmanager
def pointed_at(tree: Path, evidence: Path):
    """Point the promotion writer's module paths at a temp tree (the layout mirrors the real one, so
    its ROOT-relative record paths round-trip; see test_davinci_projection_coherence.promote)."""
    saved = (acr.ROOT, acr.GENERATED_DIR, acr.DEFAULT_EVIDENCE_PATH, acr.METHOD_HEALTH_PATH)
    acr.ROOT = tree.parents[1]
    acr.GENERATED_DIR = tree
    acr.DEFAULT_EVIDENCE_PATH = evidence
    acr.METHOD_HEALTH_PATH = tree / "no-method-health.yml"
    try:
        yield
    finally:
        acr.ROOT, acr.GENERATED_DIR, acr.DEFAULT_EVIDENCE_PATH, acr.METHOD_HEALTH_PATH = saved


def run_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = acr.main(argv)
    return rc, out.getvalue(), err.getvalue()


def text_keys_in(path: Path) -> set[str]:
    """Every key name in a data file whose name says it holds report text."""
    if not path.exists():
        return set()
    names = set(re.findall(r"^[ \t-]*([a-z_]+):", path.read_text(encoding="utf-8"), flags=re.M))
    return {n for n in names if re.search(r"title|excerpt|context", n) or n in {"matched_text", "report_text"}}


# ---------------------------------------------------------------- the suite

def run() -> int:
    print("=" * 78)
    print("Log title hygiene: printing writers never print a stored report title or excerpt")
    print("=" * 78)

    # ---------- R: the redaction primitive ----------
    print(NEWLINE + "[R] lib.log_redaction.log_safe")
    nested = {
        "results": [{
            "id": "row-1", "source_url": "https://example.invalid/1", "count": 3, "issue": "render failures",
            **{k: canary(k, 1) for k in THIRD_PARTY_TEXT_KEYS},
            "proposed": {"accepted_report_sources": [{"source_url": "https://example.invalid/1",
                                                      "source_title": canary("source_title", 2)}],
                         "evidence_samples": ({"source_title": canary("source_title", 3), "counted": True},)},
        }],
        "total": 1,
    }
    before = copy.deepcopy(nested)
    safe = log_safe(nested)
    rendered = json.dumps(safe)
    check("R1 every listed key is removed at any depth (dicts in lists in dicts, and tuples)",
          leaks(rendered) == [] and not any(f'"{k}"' in rendered for k in THIRD_PARTY_TEXT_KEYS), rendered[:200])
    check("R2 ids, URLs, counts and categories are kept",
          safe["results"][0]["id"] == "row-1" and safe["results"][0]["source_url"] == "https://example.invalid/1"
          and safe["results"][0]["count"] == 3 and safe["results"][0]["issue"] == "render failures"
          and safe["total"] == 1
          and safe["results"][0]["proposed"]["accepted_report_sources"][0]["source_url"] == "https://example.invalid/1"
          and safe["results"][0]["proposed"]["evidence_samples"][0]["counted"] is True, rendered[:200])
    check("R3 the input is never modified (the writer still writes what it built)", nested == before)
    check("R4 scalars pass through unchanged", [log_safe(v) for v in (None, 0, "x", 1.5, True)] == [None, 0, "x", 1.5, True])
    live_text_keys = set()
    for name in ("consensus_evidence.yml", "update_linked_evidence.yml", "recent_powerpoint_reports.yml"):
        live_text_keys |= text_keys_in(DATA / name)
    record_keys = set()
    for path in sorted((_REPO / "auxsays" / "updates" / "generated").glob("*.md"))[:4000]:
        head = path.read_text(encoding="utf-8").split("\n---", 1)[0]
        record_keys |= {n for n in re.findall(r"^[ \t-]*([a-z_]+):", head, flags=re.M)
                        if re.search(r"(source|report|parent|thread)_title|excerpt", n)}
    uncovered = sorted((live_text_keys | record_keys) - THIRD_PARTY_TEXT_KEYS)
    check(f"R5 the closed list covers every report-text field the live data carries ({len(live_text_keys | record_keys)} found)",
          bool(live_text_keys) and "report_title" in live_text_keys and "source_title" in record_keys and uncovered == [],
          f"not in THIRD_PARTY_TEXT_KEYS: {uncovered}")

    with tempfile.TemporaryDirectory() as td:
        tree = Path(td) / "auxsays" / "updates" / "generated"
        tree.mkdir(parents=True)
        evidence = Path(td) / "auxsays" / "_data" / "consensus_evidence.yml"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        record = tree / f"2026-02-12-davinci-resolve-{VERSION.replace('.', '-')}.md"
        rows = [evidence_row(i) for i in range(5)]

        # ---------- P: the promotion writer, end to end ----------
        print(NEWLINE + "[P] apply_consensus_to_records prints ids and counts, never a stored title")
        write_record(record, count=3)
        write_evidence(evidence, rows)
        with pointed_at(tree, evidence):
            results = acr.run_dry_run(evidence_path=evidence, product_id_filter=DAV, is_candidate_mode=False,
                                      records_index=acr._index_generated_records())
            in_memory = json.dumps(results, ensure_ascii=False)
            check("P0 NON-VACUITY: the in-memory report carries the stored titles (what used to be printed)",
                  len(results) == 1 and results[0].get("included_candidate_count") == 5
                  and len(leaks(in_memory)) >= 5
                  and canary("report_title", 0) in in_memory, f"{len(results)} groups, {leaks(in_memory)[:3]}")

            rc, out, err = run_main(["--product-id", DAV])
            check("P1 dry run: stdout and stderr carry no stored title or excerpt",
                  rc == 0 and leaks(out + err) == [], f"rc={rc} leaked={leaks(out + err)[:4]}")
            payload = json.loads(out)
            group = (payload.get("results") or [{}])[0]
            check("P2 ...and the report still names every row by id and URL, with its counts and gates",
                  [r.get("id") for r in group.get("included_rows") or []] == [r["id"] for r in rows]
                  and [r.get("source_url") for r in group.get("included_rows") or []] == [r["source_url"] for r in rows]
                  and group.get("included_candidate_count") == 5 and bool(group.get("safety_gate_results"))
                  and all("source_url" in s for s in (group.get("proposed_fields_if_written") or {}).get("accepted_report_sources") or [])
                  and '"source_title"' not in out, str(group)[:300])

            out_file = Path(td) / "report.json"
            rc, out, err = run_main(["--product-id", DAV, "--output", str(out_file)])
            written = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
            check("P3 --output: the file written carries no stored title either, but keeps the row ids",
                  rc == 0 and written and leaks(written + out + err) == [] and rows[0]["id"] in written,
                  f"rc={rc} leaked={leaks(written + out + err)[:4]}")

            rc, out, err = run_main(["--product-id", DAV, "--write-all", "--confirm-write"])
            record_text = record.read_text(encoding="utf-8")
            check("P4 --write-all (what every workflow step runs): nothing printed carries a stored title",
                  rc == 0 and leaks(out + err) == [], f"rc={rc} leaked={leaks(out + err)[:4]}")
            check("P5 ...while the record it wrote STILL stores each counted report's title (only the printed view changed)",
                  all(canary("report_title", i) in record_text for i in range(5))
                  and "update_report_count: 5" in record_text, record_text[:300])

            write_record(record, count=3)
            rc, out, err = run_main(["--product-id", DAV, "--update-version", VERSION, "--write", "--confirm-write"])
            check("P6 --write (single record): nothing printed carries a stored title",
                  rc == 0 and leaks(out + err) == [] and '"write_result"' in out, f"rc={rc} leaked={leaks(out + err)[:4]}")

        # ---------- K: reconciliation log lines ----------
        print(NEWLINE + "[K] reconciliation's log lines")
        write_record(record, count=2)
        changed, details = reconcile_record_counts(rows, tree)
        lines = [format_reconcile_detail(d) for d in details] + [format_maturity_transition(d) or "" for d in details]
        check("K1 a reconciliation that moves a canary-bearing record prints its path, identity and counts only",
              changed >= 1 and leaks(NEWLINE.join(lines)) == [] and any("2 -> 5" in ln for ln in lines), str(lines)[:300])

        # ---------- Q: QA messages ----------
        print(NEWLINE + "[Q] QA's messages")
        write_record(record, count=7)      # disagrees with its 1-entry sample list and its evidence
        saved = qa.EVIDENCE_PATH
        qa.EVIDENCE_PATH = evidence
        try:
            errors, warnings = qa.scan_record(record)
            e2, w2 = qa.scan_evidence_count_alignment([record])
        finally:
            qa.EVIDENCE_PATH = saved
        messages = [str(i.get("message") or "") for i in list(errors) + list(warnings) + list(e2) + list(w2)]
        check("Q1 QA reports on a canary-bearing record without quoting a stored title",
              len(messages) >= 1 and leaks(NEWLINE.join(messages)) == [], f"{len(messages)} messages, {leaks(NEWLINE.join(messages))[:3]}")

    # ---------- C: the collection runner ----------
    print(NEWLINE + "[C] run_patch_evidence_collection's printed payload")

    class _CanaryCollector:
        def collect(self, ctx):
            return [{"product_id": "canary-product", "accepted_count": 1, "rejected_count": 1,
                     "accepted_urls": ["https://forum.example.invalid/t/c/1"],
                     "candidates": [{"id": "canary-row-1", "source_url": "https://forum.example.invalid/t/c/1",
                                     "thread_title": canary("thread_title", 1),
                                     "report_title": canary("report_title", 9),
                                     "excerpt": canary("excerpt", 1),
                                     "report_text": canary("report_text", 1),
                                     "rejection_reason": "missing_exact_version"}],
                     "method_health": []}]

    saved_build = rpec.build_collectors
    rpec.build_collectors = lambda env=None: {"canary-product": _CanaryCollector}
    outdir = tempfile.mkdtemp(prefix="loghyg-")
    saved_env = {k: os.environ.get(k) for k in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT")}
    os.environ["GITHUB_STEP_SUMMARY"] = os.path.join(outdir, "summary.md")
    os.environ["GITHUB_OUTPUT"] = os.path.join(outdir, "out.txt")
    buf, ebuf = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(ebuf):
            rc = rpec.main(["--product-id", "canary-product", "--dry-run"])
    finally:
        rpec.build_collectors = saved_build
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    printed = buf.getvalue()
    summary_text = Path(outdir, "summary.md").read_text(encoding="utf-8") if Path(outdir, "summary.md").exists() else ""
    check("C1 a collector's result carrying report text prints none of it (stdout, stderr, step summary)",
          rc == 0 and leaks(printed + ebuf.getvalue() + summary_text) == [], f"rc={rc} leaked={leaks(printed + ebuf.getvalue())}")
    try:
        cpayload = json.loads(printed[printed.index("{"):])
    except ValueError:
        cpayload = {}
    cand = (((cpayload.get("products") or [{}])[0].get("results") or [{}])[0].get("candidates") or [{}])[0]
    check("C2 ...and the same nested candidate is still printed with its id, URL and rejection category",
          cand.get("id") == "canary-row-1" and cand.get("source_url") == "https://forum.example.invalid/t/c/1"
          and cand.get("rejection_reason") == "missing_exact_version"
          and cpayload.get("accepted_count") == 1, str(cand)[:200])

    # Wiring: the two printers really route through log_safe (a module that stops importing it is a
    # module whose output is no longer redacted, however the tests above were set up).
    check("W1 both printing writers use the shared redaction (one list, not copies)",
          acr.log_safe is log_redaction.log_safe and rpec.log_safe is log_redaction.log_safe)

    print()
    print("=" * 78)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 78)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
