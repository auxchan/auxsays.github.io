#!/usr/bin/env python3
"""Tests for per-source record-limit resolution in patch_ingest.

`patch_ingest.resolve_record_limit` lets a single source cap its own adapter
output via `ingestion.record_limit`, while every other source keeps the global
`--limit` default. These tests prove:
  - a per-source `record_limit` overrides the global limit,
  - its absence falls back to the global limit,
  - invalid / non-positive values fall back to the global limit,
  - against the real config: only microsoft-windows-11 overrides (to 6), while
    microsoft-365-apps and microsoft-teams fall back to the global default.
No network or filesystem writes: the helper is pure, and the config is read-only.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import yaml

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import patch_ingest
from lib import state as state_mod  # module alias; run() uses a local `state` dict

_CONFIG = _REPO / "auxsays" / "_data" / "patch_ingestion_sources.yml"

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


def args(limit: int = 2) -> SimpleNamespace:
    # Minimal stand-in for the argparse.Namespace used by patch_ingest.
    return SimpleNamespace(limit=limit)


def src(record_limit: object = "__absent__") -> dict[str, object]:
    ingestion: dict[str, object] = {"adapter": "x"}
    if record_limit != "__absent__":
        ingestion["record_limit"] = record_limit
    return {"product_id": "p", "ingestion": ingestion}


def load_config_source(product_id: str) -> dict[str, object]:
    rows = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    return next(r for r in rows if r.get("product_id") == product_id)


def run() -> int:
    print("=" * 60)
    print("patch_ingest per-source record_limit tests")
    print("=" * 60)

    resolve = patch_ingest.resolve_record_limit

    # --- helper semantics ----------------------------------------------------
    check("per-source record_limit overrides the global limit (6 > 2)", resolve(src(6), args(2)) == 6, str(resolve(src(6), args(2))))
    check("global default applies when record_limit is absent", resolve(src(), args(2)) == 2, str(resolve(src(), args(2))))
    check("global default applies when record_limit is null/None", resolve(src(None), args(2)) == 2, str(resolve(src(None), args(2))))
    check("record_limit can also lower below the global (1 < 2)", resolve(src(1), args(2)) == 1, str(resolve(src(1), args(2))))
    check("string-numeric record_limit is coerced to int", resolve(src("6"), args(2)) == 6, str(resolve(src("6"), args(2))))
    check("non-numeric record_limit falls back to the global limit", resolve(src("lots"), args(2)) == 2, str(resolve(src("lots"), args(2))))
    check("zero record_limit falls back to the global limit", resolve(src(0), args(2)) == 2, str(resolve(src(0), args(2))))
    check("negative record_limit falls back to the global limit", resolve(src(-3), args(2)) == 2, str(resolve(src(-3), args(2))))
    check("missing ingestion block falls back to the global limit", resolve({"product_id": "p"}, args(2)) == 2, "no ingestion key")
    check("override is honored regardless of the global default value", resolve(src(6), args(5)) == 6 and resolve(src(), args(5)) == 5, "global=5")

    # --- against the real config --------------------------------------------
    win = load_config_source("microsoft-windows-11")
    check("config: microsoft-windows-11 declares record_limit: 6", (win.get("ingestion") or {}).get("record_limit") == 6, str((win.get("ingestion") or {}).get("record_limit")))
    check("config: windows-11 resolves to 6 even with global --limit 2", resolve(win, args(2)) == 6, str(resolve(win, args(2))))

    m365 = load_config_source("microsoft-365-apps")
    check("config: microsoft-365-apps has NO record_limit (regression guard)", "record_limit" not in (m365.get("ingestion") or {}), str((m365.get("ingestion") or {}).get("record_limit")))
    check("config: microsoft-365-apps falls back to global limit (2)", resolve(m365, args(2)) == 2, str(resolve(m365, args(2))))

    teams = load_config_source("microsoft-teams")
    check("config: microsoft-teams has NO record_limit (regression guard)", "record_limit" not in (teams.get("ingestion") or {}), str((teams.get("ingestion") or {}).get("record_limit")))
    check("config: microsoft-teams falls back to global limit (2)", resolve(teams, args(2)) == 2, str(resolve(teams, args(2))))

    # --- no other source unexpectedly grew a record_limit -------------------
    rows = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    with_override = [r.get("product_id") for r in rows if isinstance(r.get("ingestion"), dict) and "record_limit" in r["ingestion"]]
    check("only microsoft-windows-11 sets a record_limit in the whole config", with_override == ["microsoft-windows-11"], str(with_override))

    # === progressive backfill: a per-run limit must ADVANCE, not repeat the newest N =====
    # A source with more history than the per-run limit must be ingested across scheduled runs
    # (run_source scans a wider window and creates at most `per_run_limit` NEW records per run).
    import tempfile
    from adapters import microsoft_office_updates as mso
    check("resolve_scan_limit widens the fetch window beyond the per-run write limit",
          patch_ingest.resolve_scan_limit(src(), args(2)) >= patch_ingest.BACKFILL_SCAN_LIMIT > 2)

    PP = {"company_id": "microsoft", "product_id": "microsoft-powerpoint", "company": "Microsoft",
          "software": "Microsoft PowerPoint",
          "ingestion": {"adapter": "microsoft_office_updates", "parser_profile": "microsoft_365_powerpoint_release_notes",
                        "target_app": "powerpoint", "channel": "Current Channel",
                        "official_url": "https://learn.microsoft.com/en-us/officeupdates/current-channel"}}
    canned = "".join(
        f'<h3>Version {v}: {mo}</h3><p>Version {v} (Build {b})</p>'
        f'<h4>Resolved issues</h4><ul><li>PowerPoint: fix for {v}.</li></ul>'
        for v, b, mo in (("2607", "20200.20100", "August 11"), ("2606", "20131.20154", "July 14"),
                         ("2605", "20026.20076", "May 20"), ("2604", "19950.20050", "April 8"),
                         ("2603", "19822.20182", "March 4")))
    parsed = mso._records_from_office_app_release_notes(PP, PP["ingestion"]["official_url"], canned, 50)
    check("backfill fixture: 5 unique PowerPoint records parsed", len(parsed) == 5, str([r.get("version") for r in parsed]))

    class _FakeAdapter:
        @staticmethod
        def fetch(source, limit=3):
            return [dict(r) for r in parsed[:max(1, int(limit))]]

    orig_adapter_module = patch_ingest.adapter_module
    patch_ingest.adapter_module = lambda name: _FakeAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            a = SimpleNamespace(limit=2, output=Path(td) / "generated", overwrite_existing=False)
            a.output.mkdir(parents=True, exist_ok=True)
            state = {"schema_version": 1, "sources": {}, "seen": {}}
            per_run = [[Path(p).name for p in patch_ingest.run_source(PP, a, state).get("written", [])] for _ in range(6)]
            all_created = [n for run in per_run for n in run]
            distinct = set(all_created)
            check("backfill: run 1 creates the per-run limit (2) newest records", len(per_run[0]) == 2, str(per_run[0]))
            check("backfill: run 2 advances to 2 DIFFERENT records (no repeat of newest)",
                  len(per_run[1]) == 2 and not (set(per_run[1]) & set(per_run[0])), str(per_run[:2]))
            check("backfill: no record is created twice across runs", len(all_created) == len(distinct), str(all_created))
            check("backfill: all 5 records eventually created", distinct and len(distinct) == 5, str(sorted(distinct)))
            check("backfill: a later run once exhausted creates 0 new records", per_run[-1] == [], str(per_run[-1]))
            files = list((a.output).glob("*.md"))
            check("backfill: exactly 5 generated files on disk (idempotent rerun does not duplicate)", len(files) == 5, str(len(files)))
    finally:
        patch_ingest.adapter_module = orig_adapter_module

    # === source-specific scan_limit contract (Part A) ============================
    rscan = patch_ingest.resolve_scan_limit

    def src_scan(scan_limit: object = "__absent__", record_limit: object = "__absent__") -> dict[str, object]:
        ingestion: dict[str, object] = {"adapter": "microsoft_office_updates"}
        if record_limit != "__absent__":
            ingestion["record_limit"] = record_limit
        if scan_limit != "__absent__":
            ingestion["scan_limit"] = scan_limit
        return {"product_id": "p", "ingestion": ingestion}

    # 1. default (no scan_limit): record_limit 2, scan_limit 200
    check("scan_limit absent -> default window max(record_limit, 200) = 200", rscan(src_scan(), args(2)) == 200, str(rscan(src_scan(), args(2))))
    check("record_limit stays 2 by default", resolve(src_scan(), args(2)) == 2)
    # 2. override lower than 200 but >= record_limit is honored
    check("scan_limit=8 override honored (narrows the 200 default)", rscan(src_scan(8), args(2)) == 8, str(rscan(src_scan(8), args(2))))
    check("scan_limit == record_limit (2) is honored", rscan(src_scan(2), args(2)) == 2)
    check("scan_limit == SEEN_RETENTION upper bound is honored", rscan(src_scan(state_mod.SEEN_RETENTION), args(2)) == state_mod.SEEN_RETENTION)
    # 3. scan_limit below record_limit -> conservative record_limit, NEVER 200 (no broadening)
    check("scan_limit(1) below record_limit(2) resolves conservatively to 2", rscan(src_scan(1), args(2)) == 2, str(rscan(src_scan(1), args(2))))
    check("scan_limit(3) below record_limit(6) resolves to 6, not 200", rscan(src_scan(3, 6), args(2)) == 6, str(rscan(src_scan(3, 6), args(2))))
    # 4. invalid values -> conservative record_limit, never broaden network activity
    check("scan_limit non-integer resolves conservatively to record_limit", rscan(src_scan("lots"), args(2)) == 2, str(rscan(src_scan("lots"), args(2))))
    check("scan_limit zero resolves conservatively to record_limit", rscan(src_scan(0), args(2)) == 2)
    check("scan_limit negative resolves conservatively to record_limit", rscan(src_scan(-5), args(2)) == 2)
    check("scan_limit above SEEN_RETENTION resolves conservatively (not widened past retention)", rscan(src_scan(state_mod.SEEN_RETENTION + 50), args(2)) == 2, str(rscan(src_scan(state_mod.SEEN_RETENTION + 50), args(2))))
    check("any resolved scan_limit is <= SEEN_RETENTION (retention always covers the window)", all(rscan(s, args(2)) <= state_mod.SEEN_RETENTION for s in (src_scan(), src_scan(8), src_scan(1), src_scan("x"))))

    # 15. real config: every enabled Elgato source declares scan_limit 8 and resolves to 8
    rows = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    elgato_rows = [r for r in rows if (r.get("ingestion") or {}).get("adapter") == "elgato_help_center"]
    check("config: 4 enabled Elgato sources use the help-center adapter", len(elgato_rows) == 4, str(len(elgato_rows)))
    check("config: every Elgato source declares scan_limit 8", all((r.get("ingestion") or {}).get("scan_limit") == 8 for r in elgato_rows), str([(r.get("product_id"), (r.get("ingestion") or {}).get("scan_limit")) for r in elgato_rows]))
    check("config: Elgato scan_limit resolves to 8 even under the global 200 backfill default", all(rscan(r, args(2)) == 8 for r in elgato_rows))
    check("config: no non-Elgato source silently gained a scan_limit", [r.get("product_id") for r in rows if "scan_limit" in (r.get("ingestion") or {})] == [r.get("product_id") for r in elgato_rows], str([r.get("product_id") for r in rows if "scan_limit" in (r.get("ingestion") or {})]))

    # === seen-history retention alignment (Part D) ================================
    # 8. retention covers the full default scan window
    check("SEEN_RETENTION >= BACKFILL_SCAN_LIMIT (ledger covers default scan window)", state_mod.SEEN_RETENTION >= patch_ingest.BACKFILL_SCAN_LIMIT, f"{state_mod.SEEN_RETENTION} vs {patch_ingest.BACKFILL_SCAN_LIMIT}")
    check("SEEN_RETENTION is the retention constant patch_ingest asserts against", state_mod.SEEN_RETENTION >= 200)
    # 9. >100 identities are NOT prematurely evicted inside a 200 window (old cap was 100)
    st_bulk: dict[str, object] = {"schema_version": 1, "sources": {}, "seen": {}}
    for i in range(150):
        state_mod.mark_seen(st_bulk, "bulk", f"id-{i:04d}")
    seen_bulk = st_bulk["sources"]["bulk"]["seen"]
    check("150 distinct identities all retained (would have evicted 50 at the old 100 cap)", len(seen_bulk) == 150 and all(state_mod.is_seen(st_bulk, "bulk", f"id-{i:04d}") for i in range(150)), str(len(seen_bulk)))
    check("mark_seen preserves most-recent-first ordering", seen_bulk[0] == "id-0149" and seen_bulk[-1] == "id-0000")
    for i in range(150, 260):
        state_mod.mark_seen(st_bulk, "bulk", f"id-{i:04d}")
    check("seen ledger stays BOUNDED at SEEN_RETENTION (not unbounded)", len(st_bulk["sources"]["bulk"]["seen"]) == state_mod.SEEN_RETENTION, str(len(st_bulk["sources"]["bulk"]["seen"])))
    check("re-marking an existing identity does not duplicate or grow the ledger", (lambda before: (state_mod.mark_seen(st_bulk, "bulk", st_bulk["sources"]["bulk"]["seen"][10]), len(st_bulk["sources"]["bulk"]["seen"]) == before)[1])(len(st_bulk["sources"]["bulk"]["seen"])))

    # === progressive backfill honors a narrowed scan_limit (Parts A/E/F) =========
    canned9 = "".join(
        f'<h3>Version {v}: {mo}</h3><p>Version {v} (Build {b})</p>'
        f'<h4>Resolved issues</h4><ul><li>PowerPoint: fix {v}.</li></ul>'
        for v, b, mo in (("2610", "20500.10000", "October 6"), ("2609", "20400.10000", "September 8"),
                         ("2608", "20300.10000", "August 4"), ("2607", "20200.20100", "July 7"),
                         ("2606", "20131.20154", "June 2"), ("2605", "20026.20076", "May 20"),
                         ("2604", "19950.20050", "April 8"), ("2603", "19822.20182", "March 4"),
                         ("2602", "19750.20100", "February 3")))
    PP2 = {"company_id": "microsoft", "product_id": "microsoft-powerpoint", "company": "Microsoft",
           "software": "Microsoft PowerPoint",
           "ingestion": {"adapter": "microsoft_office_updates", "parser_profile": "microsoft_365_powerpoint_release_notes",
                         "target_app": "powerpoint", "channel": "Current Channel",
                         "official_url": "https://learn.microsoft.com/en-us/officeupdates/current-channel",
                         "scan_limit": 5}}
    parsed9 = mso._records_from_office_app_release_notes(PP2, PP2["ingestion"]["official_url"], canned9, 50)
    check("scan_limit backfill fixture: 9 unique records parsed", len(parsed9) == 9, str([r.get("version") for r in parsed9]))

    class _ScanAdapter:
        calls: list[int] = []

        @staticmethod
        def fetch(source, limit=3):
            _ScanAdapter.calls.append(int(limit))
            return [dict(r) for r in parsed9[:max(1, int(limit))]]

    orig_mod = patch_ingest.adapter_module
    patch_ingest.adapter_module = lambda name: _ScanAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            a = SimpleNamespace(limit=2, output=Path(td) / "generated", overwrite_existing=False)
            a.output.mkdir(parents=True, exist_ok=True)
            st2 = {"schema_version": 1, "sources": {}, "seen": {}}
            r1 = patch_ingest.run_source(PP2, a, st2)
            check("scan_limit passed to adapter is the resolved 5 (not the 200 default)", _ScanAdapter.calls[-1] == 5, str(_ScanAdapter.calls))
            check("run diagnostics report resolved record_limit=2 and scan_limit=5", r1["record_limit"] == 2 and r1["scan_limit"] == 5, str((r1.get("record_limit"), r1.get("scan_limit"))))
            check("candidate_count reflects the narrowed window (5, not 9)", r1["candidate_count"] == 5, str(r1["candidate_count"]))
            check("run 1 creates record_limit(2) and defers the remaining in-window candidates", r1["created"] == 2 and r1["deferred_count"] == 3, str((r1["created"], r1["deferred_count"])))
            names1 = [Path(p).name for p in r1["written"]]
            r2 = patch_ingest.run_source(PP2, a, st2)
            names2 = [Path(p).name for p in r2["written"]]
            check("existing records do NOT consume the write budget (run 2 still creates 2 NEW)", r2["created"] == 2, str(r2["created"]))
            check("deferred records remain eligible (run 2 advances to 2 different records)", set(names1).isdisjoint(names2) and len(names2) == 2, str((names1, names2)))
            patch_ingest.run_source(PP2, a, st2)  # run 3 drains the last in-window record
            r4 = patch_ingest.run_source(PP2, a, st2)
            files = list(a.output.glob("*.md"))
            check("narrowed window converges to exactly its 5 newest records (6-9 are out of window)", len(files) == 5, str(sorted(f.name for f in files)))
            check("final run after window exhaustion creates 0 new records", r4["created"] == 0 and r4["deferred_count"] == 0, str((r4["created"], r4["deferred_count"])))
    finally:
        patch_ingest.adapter_module = orig_mod

    # 10. a failed write does NOT advance seen-state for that record
    orig_write = patch_ingest.write_record
    patch_ingest.adapter_module = lambda name: _ScanAdapter
    write_calls = {"n": 0}

    def failing_write(output, record, overwrite_existing=False):
        write_calls["n"] += 1
        if write_calls["n"] == 2:
            raise RuntimeError("simulated write failure")
        return orig_write(output, record, overwrite_existing=overwrite_existing)

    try:
        with tempfile.TemporaryDirectory() as td:
            a = SimpleNamespace(limit=2, output=Path(td) / "generated", overwrite_existing=False)
            a.output.mkdir(parents=True, exist_ok=True)
            st3 = {"schema_version": 1, "sources": {}, "seen": {}}
            patch_ingest.write_record = failing_write
            raised = False
            try:
                patch_ingest.run_source(PP2, a, st3)
            except RuntimeError:
                raised = True
            check("a write failure propagates out of run_source (fail-loud, not swallowed)", raised)
            seen3 = st3.get("sources", {}).get("microsoft-powerpoint", {}).get("seen", [])
            check("the record whose write FAILED is NOT marked seen (only the successful one is)", len(seen3) == 1, str(seen3))
            check("exactly one record file exists from the pre-failure write", len(list(a.output.glob("*.md"))) == 1, str(list(a.output.glob("*.md"))))
    finally:
        patch_ingest.write_record = orig_write
        patch_ingest.adapter_module = orig_mod

    # 12. dry-run and production resolve the SAME scan_limit; dry-run writes nothing, changes no state
    patch_ingest.adapter_module = lambda name: _ScanAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            a = SimpleNamespace(limit=2, output=Path(td) / "generated", overwrite_existing=False)
            a.output.mkdir(parents=True, exist_ok=True)
            st_dry = {"schema_version": 1, "sources": {}, "seen": {}}
            rd = patch_ingest.run_source(PP2, a, st_dry, write=False)
            check("dry-run resolves the SAME scan_limit as production (5)", rd["scan_limit"] == 5, str(rd["scan_limit"]))
            check("dry-run reports would_create within the write budget and flags dry_run", rd["created"] == 2 and rd.get("dry_run") is True and len(rd["would_create"]) == 2, str(rd.get("would_create")))
            check("dry-run writes NO generated files", list(a.output.glob("*.md")) == [], str(list(a.output.glob("*.md"))))
            check("dry-run marks NO seen-state", st_dry.get("sources", {}).get("microsoft-powerpoint", {}).get("seen", []) == [])
            st_prod = {"schema_version": 1, "sources": {}, "seen": {}}
            rp = patch_ingest.run_source(PP2, a, st_prod, write=True)
            check("production run resolves the identical scan_limit as the dry-run", rp["scan_limit"] == rd["scan_limit"])
            check("dry-run would_create count matches production created count", rd["created"] == rp["created"])
    finally:
        patch_ingest.adapter_module = orig_mod

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
