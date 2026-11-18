#!/usr/bin/env python3
"""Coverage governance (AUX-102): AUXSAYS never claims to monitor what it does not monitor.

WHAT WAS WRONG. Catalog inclusion was decoupled from collection. Measured on main d6e691cc: 47 catalog
products, 30 with no enabled official lane, 18 of those Core, 29 of the 30 labelled "Monitoring active"
in the catalog, the NVIDIA company page saying "NVIDIA is tracked by AUXSAYS" and every no-record
product page saying it "is tracked for ... public release signals". Nothing could have produced a
record for GeForce 621.14 or 621.24 and nothing reported that. A switched-off lane writes no telemetry,
so its silence looked like a quiet product; a broken enabled lane alarmed nobody; 37 backfill rows sat
`queued` with no reader.

WHAT THIS PINS.
  [A] the coverage label per product, from the official and community capabilities, fail closed --
      including every representative case GPT's directive names (NVIDIA, ChatGPT, Premiere, OBS, a
      healthy lane with no new release, a stale or failed lane)
  [B] the company aggregate
  [C] the real projection and its deploy wiring (generated, git-ignored, before the build; the check
      after it; the assessment never able to stop a deploy)
  [D] the debt gate: a NEW Core product without coverage and without a debt entry is refused; existing
      debt and runtime impairment never are
  [E] the deploy check on synthetic built sites: a seeded contradiction is caught, a clean site passes
  [F] the shipped layouts render their coverage only from the projection (real Liquid renders)
  [G] the catalog carries no static coverage claim and no template reads one
  [H] the daily assessment: each flag fires on its case, and the no-false-alarm cases stay quiet
  [I] the product-level signal contract exists and is linked from the ledger

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_coverage_governance.py
"""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
for p in (_SCRIPTS, _SCRIPTS / "ci"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import yaml  # noqa: E402

import assess_coverage as assess  # noqa: E402
import build_coverage_projection as cov  # noqa: E402
import build_monitoring_projection as official  # noqa: E402
import verify_coverage_claims as gate  # noqa: E402

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
GPT_LABELS = ("Official updates monitored",
              "Official updates monitored; community reports not monitored",
              "Monitoring temporarily impaired",
              "Monitoring planned; not active",
              "Not currently monitored")

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + str(detail)[:600])
        _ERRORS.append(label)


# ------------------------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------------------------

def iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def product(pid: str, company: str = "acme", priority: str = "Core") -> dict:
    return {"id": pid, "product_id": pid, "company_id": company, "priority": priority,
            "product_name": pid.upper(), "product_url": f"/updates/{company}/{pid}/"}


def source(pid: str, enabled: bool = True, cadence: str = "12h",
           url: str = "https://vendor.example/release-notes") -> dict:
    return {"product_id": pid, "enabled": enabled,
            "ingestion": {"polling_frequency": cadence, "official_url": url, "adapter": "html_changelog"}}


def ingest(status: str = "healthy", success_hours: float | None = 1, checked_hours: float = 1, **extra) -> dict:
    st = {"status": status, "last_checked_at": iso(checked_hours)}
    if success_hours is not None:
        st["last_success_at"] = iso(success_hours)
    st.update(extra)
    return st


def method(pid: str, mid: str, status: str, hours_ago: float, version: str = "1.0") -> dict:
    return {"product_id": pid, "update_version": version, "method_id": mid, "status": status,
            "last_run": iso(hours_ago)}


def make_inputs(products, sources, states, methods=(), debt=(), companies=None) -> cov.Inputs:
    by_pid = {s["product_id"]: s for s in sources}
    official_rows = [{"product_id": p["product_id"],
                      "state": official.derive_state(by_pid.get(p["product_id"]), states.get(p["product_id"]),
                                                     now=NOW)} for p in products]
    companies = companies if companies is not None else \
        [{"id": c} for c in sorted({p["company_id"] for p in products})]
    return cov.Inputs(list(products), companies, list(sources), official_rows,
                      list(methods), list(debt), 14)


def coverage_of(pid: str, inputs: cov.Inputs) -> dict:
    rows, _c = cov.build(inputs, now=NOW)
    return next(r for r in rows if r["product_id"] == pid)


def debt_entry(pid: str, plan: str = "not_planned", **extra) -> dict:
    e = {"product_id": pid, "remediation_priority": "P1", "blocking_reason": "vendor_terms_unresolved",
         "next_action": "Decide the rights question, then build the adapter.", "plan": plan,
         "review_by": "2026-12-18", "ledger": "AUX-102"}
    e.update(extra)
    return e


# ------------------------------------------------------------------------------------------------
# [A] the coverage label per product
# ------------------------------------------------------------------------------------------------

def section_a() -> None:
    print("\n[A] coverage is derived from what collection did, fail closed")
    obs = make_inputs([product("obs")], [source("obs", cadence="6h")], {"obs": ingest()},
                      [method("obs", "github_issues", "no_results", 3), method("obs", "obs_forum", "success", 3)])
    r = coverage_of("obs", obs)
    check("A1 OBS: official and community operating -> 'Official updates monitored'",
          (r["state"], r["label"], r["official"], r["community"])
          == ("full", "Official updates monitored", "healthy", "operating"), r)

    elg = make_inputs([product("elgato")], [source("elgato")], {"elgato": ingest()})
    r = coverage_of("elgato", elg)
    check("A2 official-only product says community reports are NOT monitored",
          (r["state"], r["label"]) == ("official_only",
                                       "Official updates monitored; community reports not monitored"), r)

    nv = make_inputs([product("nvidia", "nvidia")], [source("nvidia", enabled=False)], {})
    r = coverage_of("nvidia", nv)
    check("A3 NVIDIA: catalogued, zero records, ingest disabled -> 'Not currently monitored'",
          (r["state"], r["label"], r["official"]) == ("not_monitored", "Not currently monitored", "disabled"), r)
    nvp = make_inputs([product("nvidia", "nvidia")], [source("nvidia", enabled=False)], {},
                      debt=[debt_entry("nvidia", plan="planned")])
    r = coverage_of("nvidia", nvp)
    check("A4 NVIDIA with a reviewed plan -> 'Monitoring planned; not active', never monitored",
          (r["state"], r["label"]) == ("planned", "Monitoring planned; not active"), r)

    # ChatGPT: an official URL is configured, the lane is off. A frozen healthy state row (left over
    # from a lane that was switched off) must not make it read as monitored either.
    gpt = make_inputs([product("chatgpt", "openai")],
                      [source("chatgpt", enabled=False, url="https://help.vendor.example/release-notes")],
                      {"chatgpt": ingest()})
    r = coverage_of("chatgpt", gpt)
    check("A5 ChatGPT: a configured official URL with ingest disabled is not monitoring",
          r["state"] == "not_monitored" and r["official"] == "disabled", r)

    prem = make_inputs([product("premiere", "adobe")], [source("premiere", cadence="24h")],
                       {"premiere": ingest("partial", primary_source_error_type="blocked",
                                           primary_last_success_at="")},
                       [method("premiere", "adobe_community_algolia_search", "success", 5)])
    r = coverage_of("premiere", prem)
    check("A6 Premiere: records and community evidence exist, official source blocked -> impaired, not current",
          (r["state"], r["label"], r["official"]) == ("impaired", "Monitoring temporarily impaired", "blocked"), r)

    # A healthy lane that found nothing new for months is HEALTHY: no release is not a failure.
    quiet = make_inputs([product("quiet")], [source("quiet")],
                        {"quiet": ingest(last_records_written=0, last_records_fetched=0)})
    r = coverage_of("quiet", quiet)
    check("A7 a healthy check that found no new release reads monitored",
          r["state"] == "official_only" and r["official"] == "healthy", r)

    stale = make_inputs([product("stale")], [source("stale", cadence="12h")],
                        {"stale": ingest(success_hours=24 * 10, checked_hours=1)})
    failed = make_inputs([product("failed")], [source("failed")],
                         {"failed": ingest("failing", success_hours=24 * 30, last_error_type="timeout")})
    rs, rf = coverage_of("stale", stale), coverage_of("failed", failed)
    check("A8 an enabled lane gone stale, or failing, reads impaired",
          (rs["state"], rs["official"], rf["state"], rf["official"])
          == ("impaired", "stale", "impaired", "unreachable"), (rs, rf))

    never = make_inputs([product("new")], [source("new")], {})
    r = coverage_of("new", never)
    check("A9 an enabled lane with no recorded run is never affirmative",
          r["state"] == "impaired" and r["official"] == "unverified", r)

    frozen = make_inputs([product("ps", "adobe")], [source("ps", enabled=False, cadence="24h")],
                         {"ps": ingest("failing", success_hours=None, consecutive_failures=2,
                                       last_error_type="timeout")})
    r = coverage_of("ps", frozen)
    check("A10 a switched-off lane with a frozen 'failing' row is not monitored, not broken",
          r["state"] == "not_monitored" and r["official"] == "disabled", r)

    off_comm = make_inputs([product("x")], [source("x", enabled=False)], {},
                           [method("x", "forum", "success", 2)])
    check("A11 official off but community operating -> impaired, never monitored or 'not monitored'",
          coverage_of("x", off_comm)["state"] == "impaired")
    comm_bad = make_inputs([product("y")], [source("y")], {"y": ingest()},
                           [method("y", "forum", "blocked", 2), method("y", "search", "broken", 2)])
    check("A12 official healthy but every community method failing -> impaired",
          coverage_of("y", comm_bad)["state"] == "impaired")

    cs = lambda rows: cov.community_state(rows, now=NOW, max_age_days=14)  # noqa: E731
    check("A13 only disabled community methods -> absent",
          cs([method("z", "reddit", "disabled", 1)]) == "absent")
    check("A14 active community methods that ran too long ago -> impaired",
          cs([method("z", "forum", "success", 24 * 20)]) == "impaired")
    check("A15 a community run dated in the future is not fresh",
          cs([method("z", "forum", "success", -48)]) == "impaired")
    check("A16 only degraded community statuses (partial, low_confidence) -> impaired",
          cs([method("z", "a", "partial", 2), method("z", "b", "low_confidence", 2)]) == "impaired")
    check("A17 a method's NEWEST row decides: an old success superseded by a fresh refusal -> impaired",
          cs([method("z", "forum", "success", 200, "1.0"), method("z", "forum", "blocked", 2, "1.1")])
          == "impaired")

    check("A18 the label vocabulary is exactly the five plain-language labels",
          tuple(cov.COVERAGE_LABELS.values()) == GPT_LABELS, list(cov.COVERAGE_LABELS.values()))
    grid = {cov.derive_coverage(o, c, planned=p)
            for o in official.PUBLIC_STATES + ("something_new",)
            for c in cov.COMMUNITY_STATES for p in (True, False)}
    affirmative_from = {o for o in official.PUBLIC_STATES + ("something_new",)
                        for c in cov.COMMUNITY_STATES for p in (True, False)
                        if cov.derive_coverage(o, c, planned=p) in cov.OPERATING_STATES}
    check("A19 every derived state is in the vocabulary, and only a healthy official lane is monitored",
          grid <= set(cov.COVERAGE_STATES) and affirmative_from == {"healthy"}
          and cov.UNKNOWN_LABEL not in cov.COVERAGE_LABELS.values(), (grid, affirmative_from))


# ------------------------------------------------------------------------------------------------
# [B] company aggregate
# ------------------------------------------------------------------------------------------------

def section_b() -> None:
    print("\n[B] a company summarises its products without overstating them")
    cc = cov.company_coverage
    check("B1 uniform products -> that label", cc([("official_only", "healthy")] * 4)
          == ("official_only", GPT_LABELS[1]))
    check("B2 all official lanes monitored, community on some -> says so with a count",
          cc([("full", "healthy")] * 3 + [("official_only", "healthy")])
          == ("mixed", "Official updates monitored; community reports monitored for 3 of 4 products"))
    check("B3 some products monitored -> a count of official lanes",
          cc([("full", "healthy")] * 2 + [("impaired", "blocked")] + [("not_monitored", "disabled")] * 4)
          == ("mixed", "Official updates monitored for 2 of 7 products"))
    check("B4 nothing monitored and something impaired -> impaired",
          cc([("impaired", "broken"), ("not_monitored", "disabled")])[0] == "impaired")
    check("B5 a company with no products -> not monitored", cc([])[0] == "not_monitored")


# ------------------------------------------------------------------------------------------------
# [C] the real projection and its deploy wiring
# ------------------------------------------------------------------------------------------------

def _run_lines(step: dict) -> list[str]:
    return [ln.strip() for ln in str(step.get("run") or "").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def section_c() -> None:
    print("\n[C] the projection is generated at deploy, before the build, and checked after it")
    repo_copy = _AUX / "_data" / "coverage_state.yml"
    before = repo_copy.stat().st_mtime_ns if repo_copy.exists() else None
    with tempfile.TemporaryDirectory() as td, io.StringIO() as sink:
        out = Path(td) / "coverage_state.yml"
        saved, sys.stdout = sys.stdout, sink
        try:
            rc = cov.main(["--output", str(out)])
        except Exception as exc:  # noqa: BLE001 -- fail C1 by name
            rc = f"raised {exc!r}"
        finally:
            sys.stdout = saved
        data = yaml.safe_load(out.read_text(encoding="utf-8")) if out.exists() else {}
    after = repo_copy.stat().st_mtime_ns if repo_copy.exists() else None
    products = [p for p in yaml.safe_load((_AUX / "_data" / "patch_products.yml").read_text(encoding="utf-8"))]
    companies = [c for c in yaml.safe_load((_AUX / "_data" / "patch_companies.yml").read_text(encoding="utf-8"))]
    rows = {r["product_id"]: r for r in (data or {}).get("products") or []}
    crows = {r["company_id"]: r for r in (data or {}).get("companies") or []}
    check("C1 the real projection has one valid row per catalog product and company, written elsewhere",
          rc == 0 and set(rows) == {cov.product_id_of(p) for p in products}
          and set(crows) == {c["id"] for c in companies} and before == after
          and not gate.check_projection(set(rows), set(crows), rows, crows),
          f"rc={rc} rows={len(rows)} companies={len(crows)} repo touched={before != after}")
    sources = {s["product_id"]: s for s in yaml.safe_load(
        (_AUX / "_data" / "patch_ingestion_sources.yml").read_text(encoding="utf-8"))}
    wrong = sorted(pid for pid, r in rows.items()
                   if not (sources.get(pid) or {}).get("enabled") and r["state"] in cov.OPERATING_STATES)
    check("C2 no product whose ingestion source is switched off reads monitored", not wrong and rows, wrong)

    tracked = subprocess.run(["git", "ls-files", "--", str(repo_copy)], capture_output=True, text=True,
                             cwd=_REPO)
    ignored = subprocess.run(["git", "check-ignore", "-q", "--no-index", str(repo_copy)], cwd=_REPO)
    check("C3 the projection is git-ignored and untracked",
          tracked.returncode == 0 and tracked.stdout.strip() == "" and ignored.returncode == 0,
          f"tracked={tracked.stdout.strip()!r} ignored_rc={ignored.returncode}")

    wf = yaml.safe_load((_REPO / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["build"]["steps"]

    def index(pred) -> int:
        return next((i for i, s in enumerate(steps) if pred(s)), -1)

    checkout = index(lambda s: str(s.get("uses") or "").startswith("actions/checkout"))
    gen = index(lambda s: any("build_coverage_projection.py" in ln for ln in _run_lines(s)))
    build = index(lambda s: any("jekyll build" in ln for ln in _run_lines(s)))
    verify = index(lambda s: any("verify_coverage_claims.py" in ln for ln in _run_lines(s)))
    upload = index(lambda s: str(s.get("uses") or "").startswith("actions/upload-pages-artifact"))
    check("C4 pages.yml builds the projection after checkout and BEFORE jekyll build",
          -1 < checkout < gen < build, (checkout, gen, build))
    check("C5 pages.yml runs the coverage check after the build, before the upload, and it can fail the deploy",
          -1 < build < verify < upload and not steps[verify].get("continue-on-error")
          and not steps[verify].get("if"), (build, verify, upload, steps[verify] if verify > -1 else None))
    assess_i = index(lambda s: any("assess_coverage.py" in ln for ln in _run_lines(s)))
    keep = index(lambda s: str(s.get("uses") or "").startswith("actions/upload-artifact")
                 and "coverage_assessment.json" in str((s.get("with") or {}).get("path") or ""))
    check("C6 the assessment writes a job summary and a kept artifact, and can never stop a deploy",
          assess_i > -1 and steps[assess_i].get("continue-on-error") is True
          and "$GITHUB_STEP_SUMMARY" in " ".join(_run_lines(steps[assess_i]))
          and keep > assess_i and steps[keep].get("continue-on-error") is True
          and str((steps[keep].get("with") or {}).get("retention-days")) == "90",
          (assess_i, keep))
    triggers = wf.get("on") or wf.get(True) or {}
    check("C7 the workflow that runs the assessment is scheduled daily",
          any(str(c.get("cron", "")).split()[2:5] == ["*", "*", "*"] for c in triggers.get("schedule") or []),
          triggers.get("schedule"))
    import run_integrity_tests as runner
    check("C8 the integrity runner watches the git-ignored projection for writes",
          "auxsays/_data/coverage_state.yml" in runner.WATCHED_IGNORED)


# ------------------------------------------------------------------------------------------------
# [D] the debt gate
# ------------------------------------------------------------------------------------------------

def write_source(root: Path, products, companies, debt) -> Path:
    data = root / "_data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "patch_products.yml").write_text(yaml.safe_dump(products), encoding="utf-8")
    (data / "patch_companies.yml").write_text(yaml.safe_dump(companies), encoding="utf-8")
    (data / "coverage_debt.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": debt}),
                                            encoding="utf-8")
    return root


def section_d() -> None:
    print("\n[D] a NEW coverage gap is refused; existing debt and runtime impairment never are")
    real_errors, _w = gate.check_data(_AUX, _real_projection()[0])
    check("D1 the real catalog passes the gate: every switched-off Core product has a debt entry",
          not real_errors, real_errors[:5])
    with tempfile.TemporaryDirectory() as td:
        base = [product("live"), product("added")]
        comps = [{"id": "acme"}]
        proj = {"live": {"state": "full", "official": "healthy"},
                "added": {"state": "not_monitored", "official": "disabled"}}
        errs, _w = gate.check_data(write_source(Path(td) / "a", base, comps, []), proj)
        check("D2 a Core product added with its lane switched off and no debt entry is refused by name",
              any("added" in e and e.startswith("DEBT Core product") for e in errs), errs)
        proj_unc = dict(proj, added={"state": "not_monitored", "official": "unconfigured"})
        errs_unc, _w = gate.check_data(write_source(Path(td) / "a2", base, comps, []), proj_unc)
        check("D3 ... and so is one with no ingestion source at all",
              any("added" in e for e in errs_unc), errs_unc)
        ok, _w = gate.check_data(write_source(Path(td) / "b", base, comps, [debt_entry("added")]), proj)
        check("D4 the same gap with a reviewed debt entry is baselined, not refused", not ok, ok)
        runtime = dict(proj, added={"state": "impaired", "official": "blocked"})
        rt, _w = gate.check_data(write_source(Path(td) / "c", base, comps, []), runtime)
        check("D5 a Core lane failing at RUNTIME with no debt entry never blocks a deploy", not rt, rt)
        bad, _w = gate.check_data(write_source(Path(td) / "d", base, comps,
                                               [debt_entry("added"), debt_entry("ghost"),
                                                debt_entry("live", blocking_reason="because")]), proj)
        check("D6 debt for an unknown product, or with an unknown blocking reason, is refused",
              any("ghost" in e and "not a catalog product" in e for e in bad)
              and any("blocking_reason" in e for e in bad), bad)
        errs_w, warns = gate.check_data(write_source(Path(td) / "e", base, comps,
                                                     [debt_entry("added"), debt_entry("live")]), proj)
        check("D7 debt for a product that now operates only warns", not errs_w and any("live" in w for w in warns),
              (errs_w, warns))
        claim = [dict(product("live"), coverage_status_label="Monitoring active"), product("added")]
        ce, _w = gate.check_data(write_source(Path(td) / "f", claim, comps, [debt_entry("added")]), proj)
        check("D8 a static coverage field back in the catalog is refused",
              any(e.startswith("CATALOG product live") for e in ce), ce)
    entries = cov.load_debt()
    catalog = {cov.product_id_of(p) for p in yaml.safe_load(
        (_AUX / "_data" / "patch_products.yml").read_text(encoding="utf-8"))}
    nvidia = next((e for e in entries if e.get("product_id") == "nvidia"), {})
    check("D9 the reviewed debt file is valid, and the NVIDIA gap carries its plan and verified releases",
          not cov.debt_errors(entries, catalog) and nvidia.get("plan") == "planned"
          and {r.get("version") for r in nvidia.get("observed_official_releases") or []} >= {"621.14", "621.24"},
          cov.debt_errors(entries, catalog)[:3])


_REAL: dict = {}


def _real_projection() -> tuple[dict, dict]:
    if not _REAL:
        inputs = cov.load_inputs(now=datetime.now(timezone.utc))
        rows, crows = cov.build(inputs, now=datetime.now(timezone.utc))
        _REAL["p"] = {r["product_id"]: r for r in rows}
        _REAL["c"] = {r["company_id"]: r for r in crows}
    return _REAL["p"], _REAL["c"]


# ------------------------------------------------------------------------------------------------
# [E] the deploy check on synthetic built sites
# ------------------------------------------------------------------------------------------------

def pill(kind: str, ident: str, state: str, label: str) -> str:
    return (f'<span class="patch-coverage-pill patch-coverage-pill--coverage-{state}" '
            f'data-coverage-{kind}="{ident}">{label}</span>')


def synthetic_site(root: Path, mutate=None) -> tuple[Path, Path, Path]:
    """A tiny deploy: two products, two companies, a hub, and the projection that describes them."""
    products = [product("watched", "acme"), product("dark", "darkco")]
    companies = [{"id": "acme", "company_url": "/updates/acme/"},
                 {"id": "darkco", "company_url": "/updates/darkco/"}]
    source = write_source(root / "src", products, companies, [debt_entry("dark")])
    proj_rows = {"products": [
        {"product_id": "watched", "state": "full", "label": GPT_LABELS[0], "official": "healthy",
         "community": "operating"},
        {"product_id": "dark", "state": "not_monitored", "label": GPT_LABELS[4], "official": "disabled",
         "community": "absent"}],
        "companies": [
        {"company_id": "acme", "state": "full", "label": GPT_LABELS[0], "official_monitored": 1, "total": 1},
        {"company_id": "darkco", "state": "not_monitored", "label": GPT_LABELS[4], "official_monitored": 0,
         "total": 1}]}
    projection = source / "_data" / "coverage_state.yml"
    projection.write_text(yaml.safe_dump(proj_rows), encoding="utf-8")
    site = root / "site"
    pages = {
        "index.html": "<html><body>home</body></html>",
        "updates/index.html": "<html><body><em>companies</em> <em>software products</em></body></html>",
        "updates/acme/index.html": "<html><body>" + pill("company", "acme", "full", GPT_LABELS[0])
        + pill("product", "watched", "full", GPT_LABELS[0]) + "</body></html>",
        "updates/acme/watched/index.html": "<html><body><p>AUXSAYS monitors WATCHED official updates.</p>"
        + pill("product", "watched", "full", GPT_LABELS[0]) + "</body></html>",
        "updates/darkco/index.html": "<html><body>" + pill("company", "darkco", "not_monitored", GPT_LABELS[4])
        + "<p>DARKCO is in the AUXSAYS catalog but its official updates are not currently monitored.</p>"
        + pill("product", "dark", "not_monitored", GPT_LABELS[4]) + "</body></html>",
        "updates/darkco/dark/index.html": "<html><body><p>DARK is in the AUXSAYS catalog but is not currently"
        " monitored.</p>" + pill("product", "dark", "not_monitored", GPT_LABELS[4]) + "</body></html>",
    }
    if mutate:
        mutate(pages)
    for rel, text in pages.items():
        path = site / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return site, source, projection


def run_gate(mutate=None, drop_projection=False) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        site, source, projection = synthetic_site(Path(td), mutate)
        if drop_projection:
            projection.unlink()
        errors, _w, _s = gate.verify(site, source, projection)
        return errors


def section_e() -> None:
    print("\n[E] the deploy check refuses a seeded contradiction and passes a clean site")
    clean = run_gate()
    check("E1 a clean synthetic deploy passes", not clean, clean)

    def lie(pages):
        pages["updates/darkco/dark/index.html"] = pages["updates/darkco/dark/index.html"].replace(
            pill("product", "dark", "not_monitored", GPT_LABELS[4]), pill("product", "dark", "full", GPT_LABELS[0]))
    errs = run_gate(lie)
    check("E2 a seeded contradiction (an unmonitored product's pill says monitored) is refused",
          any(e.startswith("PILLS updates/darkco/dark/index.html") and "dark" in e for e in errs), errs)

    def company_lie(pages):
        pages["updates/darkco/index.html"] = pages["updates/darkco/index.html"].replace(
            pill("company", "darkco", "not_monitored", GPT_LABELS[4]), pill("company", "darkco", "full", GPT_LABELS[0]))
    check("E3 a company pill that disagrees with the projection is refused",
          any("company darkco" in e for e in run_gate(company_lie)))

    def fallback(pages):
        pages["updates/acme/watched/index.html"] += pill("product", "watched", "unknown", cov.UNKNOWN_LABEL)
    check("E4 the 'Coverage status unknown' fallback on a deploy build is refused",
          any("fallback" in e for e in run_gate(fallback)))

    def no_pill(pages):
        pages["updates/darkco/dark/index.html"] = "<html><body>no pill</body></html>"
    check("E5 a product page with no coverage pill of its own is refused",
          any("carries no coverage pill" in e for e in run_gate(no_pill)))

    def prose(pages):
        pages["updates/darkco/index.html"] += "<p>DARKCO is tracked by AUXSAYS for changes that matter.</p>"
    def prose_ok(pages):
        pages["updates/acme/watched/index.html"] += "<p>WATCHED is tracked for workflow stability.</p>"
    def stat(pages):
        pages["updates/darkco/dark/index.html"] += "<span>STAGED</span><em>official source mapped</em>"
    check("E6 a retired claim phrase on an unmonitored company page is refused",
          any(e.startswith("PROSE updates/darkco/index.html") for e in run_gate(prose)))
    check("E7 ... and the retired stat card on an unmonitored product page",
          any(e.startswith("PROSE updates/darkco/dark/index.html") for e in run_gate(stat)))
    check("E8 the phrase rule applies only to products that are not monitored",
          not run_gate(prose_ok), run_gate(prose_ok))

    def hub(pages):
        pages["updates/index.html"] = "<html><body><em>tracked software</em></body></html>"
    check("E9 the hub calling catalogued software 'tracked' is refused",
          any("hub" in e for e in run_gate(hub)))
    check("E10 a deploy without the projection is refused, never passed",
          any(e.startswith("PROJECTION") for e in run_gate(drop_projection=True)))

    def stranger(pages):
        pages["updates/acme/index.html"] += pill("product", "ghost", "full", GPT_LABELS[0])
    check("E11 a pill for a product the projection does not know is refused",
          any("ghost" in e for e in run_gate(stranger)))


# ------------------------------------------------------------------------------------------------
# [F] real Liquid renders of the shipped layouts
# ------------------------------------------------------------------------------------------------

_RENDER_RB = r"""
require 'liquid'
require 'json'
module JekyllShims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def where(input, property, value)
    input = input.values if input.is_a?(Hash)
    return input unless input.respond_to?(:select)
    input.select { |item| item.is_a?(Hash) && item[property].to_s == value.to_s }
  end
end
Liquid::Template.register_filter(JekyllShims)
payload = JSON.parse(File.read(ARGV[0]))
print Liquid::Template.parse(payload['layout']).render!(payload['assigns'])
"""


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[-1]
    return re.sub(r"\{%-?\s*include\s.*?-?%\}", "", text, flags=re.S)


def render(path: Path, assigns: dict) -> str | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload = Path(td) / "p.json"
        payload.write_text(json.dumps({"layout": _body(path), "assigns": assigns}, default=str), encoding="utf-8")
        out = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=180)
    if out.returncode != 0:
        if "cannot load such file -- liquid" in (out.stderr or ""):
            return None
        raise RuntimeError(out.stderr[-400:])
    return out.stdout


def pills_in(text: str) -> list[tuple[str, str, str, str]]:
    found = []
    for attrs, kind, ident, label in gate._PILL.findall(text):
        m = gate._STATE_CLASS.search(attrs)
        found.append((kind, ident, m.group(1) if m else "", " ".join(label.split())))
    return found


PRODUCT_LAYOUT = _AUX / "_layouts" / "aux-patch-product.html"
COMPANY_LAYOUT = _AUX / "_layouts" / "aux-patch-company.html"
LATEST_INCLUDE = _AUX / "_includes" / "patch-latest-signals.html"


def _site(coverage: dict | None, products, companies, monitoring=None) -> dict:
    data = {"patch_products": products, "patch_companies": companies}
    if coverage is not None:
        data["coverage_state"] = coverage
    if monitoring is not None:
        data["monitoring_state"] = monitoring
    return {"data": data, "pages": []}


def section_f() -> None:
    print("\n[F] the shipped layouts take every coverage word from the projection")
    prod = lambda pid, cid: dict(product(pid, cid), product_name=pid.upper(),  # noqa: E731
                                 consensus_method=["Community reports are grouped by recurring theme."])
    products = [prod("nv", "nvco"), prod("gpt", "oai"), prod("elg", "elco"), prod("net", "netco")]
    companies = [{"id": c, "company_name": c.upper(), "company_url": f"/updates/{c}/"}
                 for c in ("nvco", "oai", "elco", "netco")]
    rows = [{"product_id": "nv", "state": "planned", "label": GPT_LABELS[3], "official": "disabled", "community": "absent"},
            {"product_id": "gpt", "state": "not_monitored", "label": GPT_LABELS[4], "official": "disabled", "community": "absent"},
            {"product_id": "elg", "state": "official_only", "label": GPT_LABELS[1], "official": "healthy", "community": "absent"},
            {"product_id": "net", "state": "impaired", "label": GPT_LABELS[2], "official": "broken", "community": "absent"}]
    company_of = {"nv": "nvco", "gpt": "oai", "elg": "elco", "net": "netco"}
    crows = [{"company_id": company_of[r["product_id"]], "state": r["state"], "label": r["label"],
              "official_monitored": 0, "total": 1} for r in rows]
    coverage = {"products": rows, "companies": crows}
    monitoring = [{"product_id": "net", "state": "broken", "label": official.STATE_LABELS["broken"],
                   "last_success": "", "last_checked": ""}]
    site = _site(coverage, products, companies, monitoring)

    out = {pid: render(PRODUCT_LAYOUT, {"site": site, "page": {"product_id": pid, "company_id": cid}})
           for pid, cid in (("nv", "nvco"), ("gpt", "oai"), ("elg", "elco"), ("net", "netco"))}
    if out["nv"] is None:
        for n in range(1, 9):
            check(f"F{n} could not render: ruby/liquid unavailable", False, "install ruby and the liquid gem")
        return
    text = {k: gate.page_text(v) for k, v in out.items()}
    claims = {k: [p for p in gate.CLAIM_PHRASES if p in v] for k, v in text.items()}
    check("F1 an unmonitored product page: projection pill, no claim phrase, honest stat card and community line",
          ("product", "gpt", "not_monitored", GPT_LABELS[4]) in pills_in(out["gpt"]) and not claims["gpt"]
          and "NOT MONITORED" in text["gpt"] and "is not currently monitored" in text["gpt"]
          and "Community reports not monitored for GPT" in text["gpt"]
          and "grouped by recurring theme" not in text["gpt"], (pills_in(out["gpt"]), claims["gpt"]))
    check("F2 a planned product page says planned, not active, and claims nothing",
          ("product", "nv", "planned", GPT_LABELS[3]) in pills_in(out["nv"]) and not claims["nv"]
          and "Monitoring is planned but not active" in text["nv"] and "PLANNED" in text["nv"],
          (pills_in(out["nv"]), claims["nv"]))
    check("F3 an official-only product with no records yet reads monitored and awaiting a record",
          ("product", "elg", "official_only", GPT_LABELS[1]) in pills_in(out["elg"])
          and "OFFICIAL SOURCE ACTIVE" in text["elg"] and "AUXSAYS monitors ELG official updates" in text["elg"])
    check("F4 an impaired product page discloses the impairment and its official detail",
          ("product", "net", "impaired", GPT_LABELS[2]) in pills_in(out["net"]) and not claims["net"]
          and "IMPAIRED" in text["net"] and "official source responded but could not be read" in text["net"],
          text["net"][:400])
    absent = render(PRODUCT_LAYOUT, {"site": _site(None, products, companies),
                                     "page": {"product_id": "elg", "company_id": "elco"}})
    got = pills_in(absent)
    check("F5 with NO projection the product page reads 'Coverage status unknown', never monitored",
          got == [("product", "elg", "unknown", cov.UNKNOWN_LABEL)]
          and not any(lbl in gate.page_text(absent) for lbl in GPT_LABELS[:2]), got)

    comp = render(COMPANY_LAYOUT, {"site": site, "page": {"company_id": "oai"}})
    ctext = gate.page_text(comp)
    got = pills_in(comp)
    check("F6 an unmonitored company page: company pill and product cards from the projection, no claim",
          got[:1] == [("company", "oai", "not_monitored", GPT_LABELS[4])]
          and ("product", "gpt", "not_monitored", GPT_LABELS[4]) in got
          and not [p for p in gate.CLAIM_PHRASES if p in ctext] and "1 software product" in ctext
          and "tracked software" not in ctext, (got, ctext[:300]))
    nvco = render(COMPANY_LAYOUT, {"site": site, "page": {"company_id": "nvco"}})
    check("F7 a planned company page says planned, not tracked",
          "Monitoring is planned but not active" in gate.page_text(nvco)
          and "is tracked by AUXSAYS" not in gate.page_text(nvco))

    latest = render(LATEST_INCLUDE, {"site": site, "include": {"updates": [], "products": products,
                                                                 "show_product": True}})
    got = pills_in(latest)
    want = [("product", r["product_id"], r["state"], r["label"]) for r in rows]
    check("F8 the company 'latest signals' list shows each no-record product's projection pill",
          got == want and "not yet monitoring" not in latest and "awaiting first record" not in latest,
          (got, want))


# ------------------------------------------------------------------------------------------------
# [G] no static coverage claim in the catalog or the templates
# ------------------------------------------------------------------------------------------------

_COMMENT = re.compile(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", re.S)


def section_g() -> None:
    print("\n[G] coverage is never written by hand, and no template reads a hand-written claim")
    products = yaml.safe_load((_AUX / "_data" / "patch_products.yml").read_text(encoding="utf-8"))
    companies = yaml.safe_load((_AUX / "_data" / "patch_companies.yml").read_text(encoding="utf-8"))
    leftover = sorted({f"{row.get('id')}.{k}" for row in products + companies for k in gate.FORBIDDEN_CATALOG_KEYS
                       if k in row})
    check("G1 the catalog carries none of the retired static coverage fields", not leftover, leftover[:6])
    readers, phrases = [], []
    for path in sorted(list((_AUX / "_layouts").glob("*.html")) + list((_AUX / "_includes").glob("*.html"))):
        live = _COMMENT.sub("", path.read_text(encoding="utf-8", errors="replace"))
        for key in gate.FORBIDDEN_CATALOG_KEYS:
            # `site.data.coverage_state` is the deploy projection, not the retired catalog field.
            if re.search(r"(?<!data)\." + key + r"\b", live):
                readers.append(f"{path.name}:{key}")
        # "OFFICIAL SOURCE ACTIVE" is left out: the product layout prints it for an OPERATING lane only,
        # which [F] renders; the deploy check refuses it on an unmonitored page.
        for phrase in [p for p in gate.CLAIM_PHRASES if p != "OFFICIAL SOURCE ACTIVE"] + [
                "tracked companies", "tracked software item", "Tracked software and"]:
            if phrase in live:
                phrases.append(f"{path.name}:{phrase}")
    check("G2 no layout or include reads a retired catalog coverage field", not readers, readers)
    check("G3 no layout or include carries a retired coverage claim phrase", not phrases, phrases)
    summaries = [c["id"] for c in companies if re.search(r"\b(tracked|tracking|monitor\w*)\b",
                                                         str(c.get("summary") or ""), re.I)]
    check("G4 company summaries describe why a company matters, never whether it is monitored",
          not summaries, summaries)


# ------------------------------------------------------------------------------------------------
# [H] the daily assessment
# ------------------------------------------------------------------------------------------------

def fleet():
    products = [product("obs", "obs"), product("quiet", "q"), product("stale", "s"), product("nvidia", "nv"),
                product("undocumented", "u"), product("ps", "adobe"), product("comm", "c"),
                product("exp", "e", priority="Expansion")]
    sources = [source("obs", cadence="6h"), source("quiet"), source("stale"), source("nvidia", enabled=False),
               source("undocumented", enabled=False), source("ps", enabled=False), source("comm"),
               source("exp", enabled=False)]
    states = {"obs": ingest(), "quiet": ingest(last_records_written=0),
              "stale": ingest(success_hours=24 * 9, checked_hours=24 * 9),
              "ps": ingest("failing", success_hours=None, last_error_type="timeout", consecutive_failures=2),
              "comm": ingest()}
    methods = [method("obs", "forum", "success", 2), method("comm", "forum", "blocked", 3)]
    debt = [debt_entry("nvidia", plan="planned",
                       observed_official_releases=[{"version": "621.14", "released": "2026-11-04", "reference": "r1"},
                                                   {"version": "621.24", "released": "2026-11-12", "reference": "r2"}]),
            debt_entry("ps", blocking_reason="source_blocks_automation", remediation_priority="P2"),
            debt_entry("stale", review_by="2026-11-01")]
    return make_inputs(products, sources, states, methods, debt), states


def run_assess(records=None, finished_hours=2, backfill=None, executor=False, mutate_inputs=None):
    inputs, states = fleet()
    if mutate_inputs:
        inputs = mutate_inputs(inputs)
    state = {"sources": states, "last_run_finished_at": iso(finished_hours)}
    records = records if records is not None else {
        "obs": [{"version": "33.0.1", "published": NOW - timedelta(days=20)}],
        "quiet": [{"version": "2.0", "published": NOW - timedelta(days=200)}]}
    backfill = backfill if backfill is not None else [{"product_id": "nvidia", "backfill_status": "queued"}]
    return assess.assess(now=NOW, inputs=inputs, state=state, records=records,
                         last_accepted={"obs": NOW - timedelta(days=1)}, backfill=backfill,
                         backfill_executor=executor)


def codes(report, pid=None):
    return {f["code"] for f in report["flags"] if pid is None or f["product_id"] == (pid or "")}


def section_h() -> None:
    print("\n[H] the assessment names every gap and raises no false alarm")
    rep = run_assess()
    nv = next((f for f in rep["flags"] if f["code"] == "core_gap" and f["product_id"] == "nvidia"), {})
    check("H1 a Core gap carries its remediation priority, blocking reason and next action",
          nv.get("remediation_priority") == "P1" and nv.get("blocking_reason") == "vendor_terms_unresolved"
          and nv.get("next_action") and nv.get("coverage") == "planned", nv)
    check("H2 a Core gap with no debt entry is named as undocumented",
          "core_gap_undocumented" in codes(rep, "undocumented"), codes(rep, "undocumented"))
    check("H3 an enabled lane gone stale is flagged as impaired",
          "enabled_lane_impaired" in codes(rep, "stale"))
    check("H4 a healthy lane that found no new release in 200 days raises nothing",
          not codes(rep, "quiet"), codes(rep, "quiet"))
    check("H5 a switched-off lane with a frozen failing row is a coverage gap, not a broken collector",
          "core_gap" in codes(rep, "ps") and "enabled_lane_impaired" not in codes(rep, "ps")
          and "execution_missing" not in codes(rep, "ps"), codes(rep, "ps"))
    check("H6 an enabled lane not checked within its window is missing execution; a fresh one is not",
          "execution_missing" in codes(rep, "stale") and "execution_missing" not in codes(rep, "obs"))
    late = run_assess(finished_hours=24 * 5)
    check("H7 an ingest chain that stopped running is flagged at run level",
          any(f["code"] == "execution_missing" and not f["product_id"] and "ingest" in f["detail"]
              for f in late["flags"]) and not any(f["code"] == "execution_missing" and not f["product_id"]
                                                  for f in rep["flags"]))
    miss = next((f for f in rep["flags"] if f["code"] == "known_release_missing"), {})
    held = run_assess(records={"nvidia": [{"version": "621.14", "published": NOW - timedelta(days=14)}]})
    miss_held = next((f for f in held["flags"] if f["code"] == "known_release_missing"), {})
    check("H8 verified official releases missing from the store are named, and a held one is not",
          miss.get("versions") == ["621.14", "621.24"] and miss_held.get("versions") == ["621.24"],
          (miss, miss_held))
    check("H9 community methods configured and none working are flagged",
          "community_unsupported" in codes(rep, "comm"))
    check("H10 a queued backfill nothing executes is flagged; with an executor it is not",
          "backfill_queued" in codes(rep, None) and "backfill_queued" not in codes(run_assess(executor=True), None))
    check("H11 a debt entry past its review date is flagged",
          "debt_review_due" in codes(rep, "stale"))

    def heal(inputs):
        rows = [dict(r, state="healthy") if r["product_id"] == "ps" else r for r in inputs.official_rows]
        srcs = [dict(s, enabled=True) if s["product_id"] == "ps" else s for s in inputs.sources]
        return cov.Inputs(inputs.products, inputs.companies, srcs, rows, inputs.method_rows, inputs.debt, 14)
    check("H12 debt for a product whose lane now operates is flagged for closing",
          "debt_resolved" in codes(run_assess(mutate_inputs=heal), "ps"))
    facts = {p["product_id"]: p for p in rep["products"]}
    o = facts["obs"]
    check("H13 each product reports the five distinctions separately",
          o["official_lane"]["last_successful_check"] and o["last_confirmed_release"]["version"] == "33.0.1"
          and facts["nvidia"]["latest_known_release"]["version"] == "621.24"
          and facts["nvidia"]["known_releases_missing"] == ["621.14", "621.24"]
          and o["last_accepted_community_report"] and o["community_methods"]["forum"]["status"] == "success",
          json.dumps(o, default=str)[:400])
    md = assess.summary_markdown(rep)
    check("H14 the job summary is compact and names the Core gaps and the counts",
          md.count("\n") < 60 and "| nvidia | planned | P1 |" in md and "core_gap_undocumented" in md, md[:400])

    # The real CLI, on the real tree: exits 0, writes outside the repository, and says nothing raw.
    status_before = subprocess.run(["git", "status", "--porcelain", "-uall"], capture_output=True, text=True,
                                   cwd=_REPO).stdout
    with tempfile.TemporaryDirectory() as td, io.StringIO() as sink:
        out, summ = Path(td) / "a.json", Path(td) / "s.md"
        saved, sys.stdout = sys.stdout, sink
        try:
            rc = assess.main(["--output", str(out), "--summary", str(summ)])
        except Exception as exc:  # noqa: BLE001 -- fail H15 by name
            rc = f"raised {exc!r}"
        finally:
            sys.stdout = saved
        body = out.read_text(encoding="utf-8") if out.exists() else ""
        report = json.loads(body) if body else {}
    status_after = subprocess.run(["git", "status", "--porcelain", "-uall"], capture_output=True, text=True,
                                  cwd=_REPO).stdout
    check("H15 the real assessment exits 0, writes only where told, and covers every catalog product",
          rc == 0 and report.get("schema") == assess.SCHEMA and report.get("products_total", 0) >= 40
          and status_before == status_after, f"rc={rc} tree changed={status_before != status_after}")
    check("H16 the assessment carries no raw error text from the sources",
          body and not re.search(r"Access Denied|<HTML|last_error\"|primary_source_error\"", body))


# ------------------------------------------------------------------------------------------------
# [I] the product-level signal contract
# ------------------------------------------------------------------------------------------------

def section_i() -> None:
    print("\n[I] the product-level early-warning contract is defined and linked")
    doc = _REPO / "docs" / "PRODUCT_LEVEL_SIGNALS_CONTRACT.md"
    text = doc.read_text(encoding="utf-8") if doc.exists() else ""
    numbered = re.findall(r"^(\d)\. \*\*", text, re.M)
    text = " ".join(text.split())
    check("I1 the contract states its nine requirements and the no-silent-promotion rule",
          numbered == [str(i) for i in range(1, 10)]
          and "can never silently become a patch-specific report" in text, numbered)
    ledger = (_REPO / "docs" / "ENGINEERING_LEDGER.md").read_text(encoding="utf-8")
    check("I2 the ledger carries AUX-102 and links the contract",
          "### AUX-102" in ledger and "PRODUCT_LEVEL_SIGNALS_CONTRACT.md" in ledger)


def run() -> int:
    for section in (section_a, section_b, section_c, section_d, section_e, section_f, section_g, section_h,
                    section_i):
        try:
            section()
        except Exception as exc:  # noqa: BLE001 -- a crashing section FAILS by name
            check(f"{section.__name__} crashed", False, f"{exc!r}\n{traceback.format_exc()[-800:]}")
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
