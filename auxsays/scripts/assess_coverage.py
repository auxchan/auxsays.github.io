#!/usr/bin/env python3
"""The daily coverage assessment (AUX-102): what AUXSAYS is NOT monitoring, said out loud.

WHY IT EXISTS. On 2026-11-18 two news stories about defects in updates AUXSAYS catalogues (NVIDIA
GeForce 621.14 / 621.24) arrived with nothing on the site, and nothing inside the repository had
noticed: a switched-off ingestion lane produces no telemetry at all, so its silence looked exactly like
a quiet product; a broken enabled lane (Netlify, 233 empty extractions) was labelled correctly and
alarmed nobody; and a backfill queue of 37 `queued` rows had no reader. This assessment turns those
silences into a report.

WHAT IT IS AND IS NOT. Deterministic and offline: it reads the same files the coverage projection
reads, plus the patch records, the accepted-evidence store and the backfill queue, at an injectable
clock. It writes a compact GitHub Actions job summary and a JSON artifact OUTSIDE the repository;
`pages.yml` uploads the JSON as a run artifact. It never commits, never fails a deploy and never
changes a page -- production does not depend on anyone reading it. Gaps that must BLOCK (a new Core
product with no coverage and no debt entry) are `ci/verify_coverage_claims.py`'s job.

FIVE QUESTIONS, KEPT APART (a single "monitoring" word hid every one of them):
  last successful check            is collection operating?
  last confirmed release           is the product publishing? (newest record)
  latest known vs latest ingested  is collection missing updates? (needs an independent, permitted
                                   official reference: today only releases a person verified and
                                   wrote into the coverage debt file)
  last accepted community report   is user evidence arriving?
  current source health            are discovery methods blocked, broken, stale or working?

NO FALSE ALARMS. A healthy check that found no new release is healthy, however long the product has
been quiet. A switched-off lane is reported as a coverage gap, never as a broken collector, even when
its frozen state row still says `failing`.

Run:  python auxsays/scripts/assess_coverage.py [--summary FILE] [--output FILE] [--now ISO]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

import build_coverage_projection as cov  # noqa: E402
import build_monitoring_projection as official  # noqa: E402

ROOT = cov.ROOT
REPO = ROOT.parent
RECORDS_DIR = ROOT / "updates" / "generated"
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
BACKFILL_PATH = ROOT / "_data" / "patch_backfill_queue.yml"
WORKFLOWS_DIR = REPO / ".github" / "workflows"
SCHEMA = "auxsays-coverage-assessment/1"

# Flag codes, in report order. Each names one way a coverage gap can hide.
FLAG_ORDER = (
    "core_gap",                  # a Core product with no operating official lane
    "core_gap_undocumented",     # ... and no reviewed debt entry
    "enabled_lane_impaired",     # an enabled official lane that is stale, refused, broken or unknown
    "execution_missing",         # a scheduled lane that has not run recently enough
    "known_release_missing",     # an independently verified official release the store does not hold
    "community_unsupported",     # community methods configured, none working
    "backfill_queued",           # remediation rows queued with nothing that executes them
    "debt_review_due",           # a debt entry past its review date
    "debt_resolved",             # a debt entry for a product whose lane now operates
)

_TOP_KEY = re.compile(r"^(update_entry|product_id|update_version|update_published_at):[ \t]*(.*)$", re.M)


def _iso(dt: datetime | None) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def _scalar(text: str) -> Any:
    try:
        return yaml.safe_load(text) if text.strip() else None
    except yaml.YAMLError:
        return text.strip()


def load_records(records_dir: Path = RECORDS_DIR) -> dict[str, list[dict]]:
    """product_id -> [{version, published}] for every patch record, from top-level front matter keys.

    Only four top-level scalars are read, so the bodies (which can hold anything) are never parsed.
    """
    out: dict[str, list[dict]] = {}
    for path in sorted(records_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        front = text[3:end] if end > 0 else ""
        fields = {k: _scalar(v) for k, v in _TOP_KEY.findall(front)}
        if fields.get("update_entry") is not True:
            continue
        pid = str(fields.get("product_id") or "").strip()
        if not pid:
            continue
        out.setdefault(pid, []).append({
            "version": str(fields.get("update_version") or "").strip(),
            "published": official.parse_instant(fields.get("update_published_at")),
        })
    return out


def load_last_accepted(path: Path = EVIDENCE_PATH) -> dict[str, datetime] | None:
    """product_id -> newest capture time of a COUNTED evidence row; None when the store is unreadable."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- informational only; the report says it is unavailable
        return None
    rows = payload.get("evidence") if isinstance(payload, dict) else payload
    out: dict[str, datetime] = {}
    for row in rows or []:
        if not isinstance(row, dict) or row.get("counted") is not True:
            continue
        at = official.parse_instant(row.get("captured_at"))
        pid = str(row.get("product_id") or "")
        if at and (pid not in out or at > out[pid]):
            out[pid] = at
    return out


def load_backfill(path: Path = BACKFILL_PATH) -> list[dict]:
    data = cov.load_yaml(path) or []
    return [r for r in data if isinstance(r, dict)]


def backfill_has_executor(workflows_dir: Path = WORKFLOWS_DIR, name: str = BACKFILL_PATH.name) -> bool:
    """Whether any workflow's executable run lines mention the queue file (comments stripped)."""
    for wf in sorted(workflows_dir.glob("*.y*ml")):
        try:
            doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        for job in (doc.get("jobs") or {}).values():
            for step in (job or {}).get("steps") or []:
                for line in str((step or {}).get("run") or "").splitlines():
                    if name in line.split("#", 1)[0]:
                        return True
    return False


def _flag(code: str, product: str | None, detail: str, **extra: Any) -> dict:
    row = {"code": code, "product_id": product or "", "detail": detail}
    row.update(extra)
    return row


def assess(*, now: datetime, inputs: cov.Inputs | None = None, state: Mapping | None = None,
           records: dict[str, list[dict]] | None = None,
           last_accepted: dict[str, datetime] | None = None, backfill: list[dict] | None = None,
           backfill_executor: bool | None = None) -> dict:
    """The whole assessment as one JSON-able dict. Every input is injectable for tests."""
    inputs = inputs or cov.load_inputs(now=now)
    if state is None:
        state = json.loads(official.STATE_PATH.read_text(encoding="utf-8")) \
            if official.STATE_PATH.exists() else {}
    records = load_records() if records is None else records
    if last_accepted is None:
        last_accepted = load_last_accepted()
    backfill = load_backfill() if backfill is None else backfill
    if backfill_executor is None:
        backfill_executor = backfill_has_executor()

    product_rows, company_rows = cov.build(inputs, now=now)
    coverage = {r["product_id"]: r for r in product_rows}
    sources = {str(s.get("product_id")): s for s in inputs.sources if s.get("product_id")}
    states = (state or {}).get("sources") or {}
    debt = {str(e.get("product_id")): e for e in inputs.debt}
    methods: dict[str, list[dict]] = {}
    for row in inputs.method_rows or []:
        methods.setdefault(str(row.get("product_id") or ""), []).append(row)

    flags: list[dict] = []
    products = []
    for product in inputs.products:
        pid = cov.product_id_of(product)
        if not pid:
            continue
        row = coverage[pid]
        src = sources.get(pid) or {}
        ingestion = src.get("ingestion") or {}
        st = states.get(pid) or {}
        recs = records.get(pid, [])
        dated = [r for r in recs if r["published"]]
        newest = max(dated, key=lambda r: r["published"]) if dated else None
        held = {r["version"] for r in recs}
        entry = debt.get(pid)
        observed = [r for r in (entry or {}).get("observed_official_releases") or [] if isinstance(r, dict)]
        missing = [str(r.get("version")) for r in observed if str(r.get("version")) not in held]
        latest_known = max(observed, key=lambda r: str(r.get("released") or "")) if observed else None
        success_field = st.get("primary_last_success_at") if str(st.get("status")) == "partial" \
            else st.get("last_success_at")
        newest_method: dict[str, dict] = {}
        for m in methods.get(pid, []):
            mid = str(m.get("method_id") or "")
            if mid and str(m.get("last_run") or "") >= str(newest_method.get(mid, {}).get("last_run") or ""):
                newest_method[mid] = m
        facts = {
            "product_id": pid,
            "product_name": product.get("product_name") or pid,
            "priority": product.get("priority") or "",
            "coverage": row["state"],
            "label": row["label"],
            "official": row["official"],
            "community": row["community"],
            "official_lane": {
                "enabled": bool(src.get("enabled")),
                "adapter": ingestion.get("adapter") or "",
                "declared_cadence": ingestion.get("polling_frequency") or "",
                "last_successful_check": str(success_field or ""),
                "last_checked": str(st.get("last_checked_at") or ""),
                "recorded_status": str(st.get("status") or ""),
                "consecutive_failures": st.get("consecutive_failures"),
                "consecutive_empty_extractions": st.get("consecutive_empty_extractions"),
            },
            "last_confirmed_release": ({"version": newest["version"], "published": _iso(newest["published"])}
                                       if newest else None),
            "records": len(recs),
            "latest_known_release": ({"version": str(latest_known.get("version")),
                                      "released": str(latest_known.get("released") or ""),
                                      "reference": str(latest_known.get("reference") or "")}
                                     if latest_known else None),
            "known_releases_missing": missing,
            "last_accepted_community_report": _iso((last_accepted or {}).get(pid)),
            "community_methods": {mid: {"status": m.get("status"), "last_run": str(m.get("last_run") or "")}
                                  for mid, m in sorted(newest_method.items())},
            "debt": ({k: entry.get(k) for k in ("remediation_priority", "blocking_reason", "next_action",
                                                 "plan", "review_by", "ledger")} if entry else None),
        }
        for k in ("review_by",):
            if facts["debt"] and facts["debt"].get(k) is not None:
                facts["debt"][k] = str(facts["debt"][k])
        products.append(facts)

        operating = row["state"] in cov.OPERATING_STATES
        if facts["priority"] == "Core" and row["official"] != "healthy":
            if entry:
                flags.append(_flag("core_gap", pid, cov.BLOCKING_REASONS.get(entry.get("blocking_reason"), ""),
                                   remediation_priority=entry.get("remediation_priority"),
                                   blocking_reason=entry.get("blocking_reason"),
                                   next_action=" ".join(str(entry.get("next_action") or "").split()),
                                   coverage=row["state"]))
            else:
                flags.append(_flag("core_gap_undocumented", pid,
                                   "Core product with no operating official lane and no coverage debt entry",
                                   coverage=row["state"]))
        if src.get("enabled") and row["official"] not in ("healthy",) + cov.OFFICIAL_OFF:
            flags.append(_flag("enabled_lane_impaired", pid,
                               f"official lane is {row['official']}",
                               last_successful_check=facts["official_lane"]["last_successful_check"],
                               consecutive_failures=st.get("consecutive_failures"),
                               consecutive_empty_extractions=st.get("consecutive_empty_extractions")))
        if src.get("enabled") and row["official"] != "unconfigured":
            window = official.recency_window(official.parse_cadence(ingestion.get("polling_frequency")),
                                             ingestion.get("monitoring_recency_hours"))
            checked = official.parse_instant(st.get("last_checked_at"))
            if window is not None and (checked is None or now - checked > window):
                flags.append(_flag("execution_missing", pid,
                                   "enabled official lane has not been checked within its recency window",
                                   last_checked=facts["official_lane"]["last_checked"]))
        if missing:
            flags.append(_flag("known_release_missing", pid,
                               f"{len(missing)} verified official release(s) not in the patch store",
                               versions=missing))
        if row["community"] == "impaired":
            flags.append(_flag("community_unsupported", pid,
                               "community methods are configured but none is working",
                               methods={k: v["status"] for k, v in facts["community_methods"].items()}))
        if entry:
            review = official.parse_instant(entry.get("review_by"))
            if review and now > review:
                flags.append(_flag("debt_review_due", pid, f"debt entry review date {entry.get('review_by')} has passed"))
            if operating:
                flags.append(_flag("debt_resolved", pid,
                                   "the official lane now operates; remove or close this debt entry"))

    # Run-level scheduled execution. The ingest workflow has no schedule of its own (the evidence
    # collection lane dispatches it), so a stopped chain shows up only here.
    finished = official.parse_instant((state or {}).get("last_run_finished_at"))
    if finished is None or now - finished > official.RECENCY_FLOOR:
        flags.append(_flag("execution_missing", None, "official ingest has not completed a run recently",
                           last_run_finished=_iso(finished)))
    runs = [official.parse_instant(r.get("last_run")) for r in inputs.method_rows or []]
    runs = [r for r in runs if r and r <= now]
    newest_run = max(runs) if runs else None
    if inputs.method_rows is not None and (newest_run is None or now - newest_run > official.RECENCY_FLOOR):
        flags.append(_flag("execution_missing", None, "community evidence collection has not run recently",
                           newest_method_run=_iso(newest_run)))

    queued = [r for r in backfill if str(r.get("backfill_status") or "") == "queued"]
    if queued and not backfill_executor:
        flags.append(_flag("backfill_queued", None,
                           f"{len(queued)} backfill rows are queued and no workflow executes the queue",
                           products=sorted(str(r.get("product_id")) for r in queued)))

    counts: dict[str, int] = {}
    for r in product_rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    flag_counts = {code: sum(1 for f in flags if f["code"] == code) for code in FLAG_ORDER}
    reference_count = sum(1 for p in products if p["latest_known_release"])
    return {
        "schema": SCHEMA,
        "generated_at": _iso(now),
        "products_total": len(products),
        "coverage_counts": dict(sorted(counts.items())),
        "flag_counts": flag_counts,
        "independent_reference_products": reference_count,
        "flags": sorted(flags, key=lambda f: (FLAG_ORDER.index(f["code"]), f["product_id"])),
        "products": products,
        "companies": company_rows,
    }


_PRI = {"P1": 0, "P2": 1, "P3": 2}


def summary_markdown(report: dict) -> str:
    """A compact job summary: the counts, the Core gaps with their next step, then everything else."""
    c = report["coverage_counts"]
    fc = report["flag_counts"]
    lines = [f"## Coverage assessment, {report['generated_at']}", "",
             f"{report['products_total']} catalog products: "
             f"{c.get('full', 0)} official and community monitored, "
             f"{c.get('official_only', 0)} official only, {c.get('impaired', 0)} impaired, "
             f"{c.get('planned', 0)} planned, {c.get('not_monitored', 0)} not monitored.", "",
             "| Flag | Count |", "|---|---|"]
    lines += [f"| {code} | {fc.get(code, 0)} |" for code in FLAG_ORDER]
    gaps = [f for f in report["flags"] if f["code"] in ("core_gap", "core_gap_undocumented")]
    gaps.sort(key=lambda f: (_PRI.get(f.get("remediation_priority"), 9), f["product_id"]))
    if gaps:
        lines += ["", "### Core products with no operating official lane", "",
                  "| Product | Coverage | Priority | Blocking reason | Next action |", "|---|---|---|---|---|"]
        for f in gaps:
            action = f.get("next_action") or "NO DEBT ENTRY: add one to _data/coverage_debt.yml"
            if len(action) > 160:
                action = action[:157] + "..."
            lines.append(f"| {f['product_id']} | {f.get('coverage', '')} | {f.get('remediation_priority') or '-'} "
                         f"| {f.get('blocking_reason') or '-'} | {action} |")
    rest = [f for f in report["flags"] if f["code"] not in ("core_gap", "core_gap_undocumented")]
    if rest:
        lines += ["", "### Other findings", ""]
        for f in rest:
            extra = ""
            if f.get("versions"):
                extra = f" ({', '.join(f['versions'])})"
            elif f.get("products"):
                extra = f" ({len(f['products'])} products)"
            lines.append(f"- `{f['code']}` {f['product_id'] or 'all'}: {f['detail']}{extra}")
    lines += ["", f"Release-gap check: {report['independent_reference_products']} product(s) have an "
                  "independent official reference; for the rest, missing updates cannot be measured yet.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--summary", type=Path, help="append the markdown summary to this file")
    ap.add_argument("--output", type=Path, help="write the JSON report to this file")
    ap.add_argument("--now", help="ISO time to assess at (default: now)")
    args = ap.parse_args(argv)
    now = official.parse_instant(args.now) if args.now else datetime.now(timezone.utc)
    report = assess(now=now)
    text = summary_markdown(report)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8", newline="") as fh:
            fh.write(text)
    else:
        print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            json.dump(report, fh, indent=1, sort_keys=False, default=str)
            fh.write("\n")
    print(f"coverage assessment: {report['products_total']} products, "
          + ", ".join(f"{k} {v}" for k, v in report["flag_counts"].items() if v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
