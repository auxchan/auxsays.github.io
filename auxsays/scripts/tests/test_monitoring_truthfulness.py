#!/usr/bin/env python3
"""A monitoring claim must describe what collection actually did.

WHAT WAS WRONG. `coverage_status_label` is a static editorial string in
`_data/patch_companies.yml` and `_data/patch_products.yml`. Three render sites published it as a
monitoring claim: the product page pill, the product card on a company page, and the
company-level pill. It tracks nothing.

Measured before the fix, across 47 products and 35 companies:
  * 29 products publicly claimed "Monitoring active" with NO enabled ingestion source;
  * 27 companies claimed it with ZERO healthy products, `netlify` among them while its only
    product's recorded state was `broken`;
  * two products claimed "Source map staged" while enabled, healthy and producing records that
    same day -- so the field was not even conservative, it was decoupled;
  * four ENABLED products sat at 226, 226, 146 and 102 consecutive failures with last successes
    between 2026-08-18 and 2026-09-21, and said nothing about it.

WHY FAIL-CLOSED IS THE PROPERTY UNDER TEST. Two earlier attempts at this repair each produced a
DIFFERENT false claim: one derived the state from `coverage_state` (an editorial enum) and one
from the source's `enabled` flag. Neither tracks whether collection WORKS -- `enabled` only says
a source is switched on, and five enabled sources have produced nothing. So `healthy` is the only
affirmative state, it is checked last, and it must be earned: enabled, recorded healthy, AND a
success recent enough for the source's own cadence. Everything else resolves to a non-affirmative
state, and anything unestablished resolves to `unverified`.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_monitoring_truthfulness.py
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import build_monitoring_projection as proj  # noqa: E402

PRODUCT_PROJECTION = _AUX / "_data" / "monitoring_state.yml"
COMPANY_PROJECTION = _AUX / "_data" / "monitoring_company_state.yml"
TEMPLATES = (_AUX / "_layouts" / "aux-patch-product.html",
             _AUX / "_layouts" / "aux-patch-company.html")

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)

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
            print("        " + detail)
        _ERRORS.append(label)


def src(enabled=True, cadence="12h", **extra) -> dict:
    s = {"enabled": enabled, "ingestion": {"polling_frequency": cadence}}
    s["ingestion"].update(extra)
    return s


def state(status="healthy", success_hours_ago=1, error_type=None) -> dict:
    st = {"status": status}
    if success_hours_ago is not None:
        st["last_success_at"] = (NOW - timedelta(hours=success_hours_ago)).isoformat()
    if error_type:
        st["last_error_type"] = error_type
    return st


def section_a_fail_closed() -> None:
    print("\n[A] healthy is EARNED; everything unestablished is not affirmative")
    d = lambda s, st: proj.derive_state(s, st, now=NOW)

    check("A1 no ingestion source at all -> unconfigured", d(None, None) == "unconfigured")
    check("A2 a source switched off -> disabled", d(src(enabled=False), state()) == "disabled")
    check("A3 enabled with NO recorded run -> unverified", d(src(), None) == "unverified",
          "this is the case `enabled` alone would have called active")
    check("A4 enabled with an EMPTY state -> unverified", d(src(), {}) == "unverified")
    check("A5 a status this code does not recognise -> unverified",
          d(src(), {"status": "something_new", "last_success_at": NOW.isoformat()}) == "unverified",
          "an unrecognised status must never render as working")
    check("A6 recorded healthy but NO success timestamp -> unverified",
          d(src(), {"status": "healthy"}) == "unverified")
    check("A7 recorded healthy with a RECENT success -> healthy",
          d(src(), state(success_hours_ago=2)) == "healthy")
    check("A8 recorded healthy with a STALE success -> stale, not healthy",
          d(src(cadence="12h"), state(success_hours_ago=200)) == "stale",
          "enabled + healthy status is not enough; the success has to be recent")
    check("A9 a manual source is not active monitoring",
          d(src(cadence="manual"), state(success_hours_ago=1)) == "disabled")


def section_b_distinct_failures() -> None:
    print("\n[B] refused, unanswered and unreadable are DIFFERENT facts")
    d = lambda s, st: proj.derive_state(s, st, now=NOW)
    check("B1 a refusal is blocked",
          d(src(), state("failing", 500, "blocked")) == "blocked")
    check("B2 no answer is unreachable, not blocked",
          d(src(), state("failing", 500, "timeout")) == "unreachable",
          "a timeout is not a refusal; collapsing them tells the reader something untrue")
    check("B3 an unreadable response is broken, not blocked or stale",
          d(src(), state("broken", 1)) == "broken",
          "a source we reached but could not parse is a third, separate condition")
    check("B4 failing for an unrecognised reason -> unverified",
          d(src(), state("failing", 500, "something_else")) == "unverified")
    states = {d(src(), state("failing", 500, "blocked")),
              d(src(), state("failing", 500, "timeout")),
              d(src(), state("broken", 1))}
    check("B5 those three do not collapse into one label", len(states) == 3, f"got {states}")


def section_c_cadence_recency() -> None:
    print("\n[C] the recency window follows the source's own cadence")
    w = proj.recency_window
    six = w(timedelta(hours=6))
    check("C1 the fastest lane gets the 48-hour floor, not 24",
          six == timedelta(hours=48), f"got {six}")
    check("C2 a slower cadence gets a proportionally wider window",
          w(timedelta(hours=24)) == timedelta(hours=96), f"got {w(timedelta(hours=24))}")
    check("C3 the window is capped so nothing is 'healthy' indefinitely",
          w(timedelta(days=30)) == proj.RECENCY_CEILING)
    check("C4 no schedule means recency cannot be judged", w(None) is None)
    check("C5 a per-source override is honoured",
          w(timedelta(hours=6), override_hours=10) == timedelta(hours=10))
    check("C6 an UNPARSEABLE override falls back rather than widening the window",
          w(timedelta(hours=6), override_hours="soon") == timedelta(hours=48),
          "a typo must not silently make a stale source look healthy")


def section_d_vocabulary_is_closed() -> None:
    print("\n[D] the published vocabulary is closed, and the live projection obeys it")
    import yaml
    rows = yaml.safe_load(PRODUCT_PROJECTION.read_text(encoding="utf-8")) or []
    crows = yaml.safe_load(COMPANY_PROJECTION.read_text(encoding="utf-8")) or []
    check("D1 the product projection is non-empty", len(rows) >= 40, f"{len(rows)} rows")
    outside = sorted({r["state"] for r in rows} - set(proj.PUBLIC_STATES))
    check("D2 every product state is an approved member", not outside, f"outside: {outside}")
    coutside = sorted({r["state"] for r in crows} - set(proj.COMPANY_STATES))
    check("D3 every company state is an approved member", not coutside, f"outside: {coutside}")
    labels_ok = all(r.get("label") for r in rows + crows)
    check("D4 every row carries reader-facing text", labels_ok)
    # The projection must carry NOTHING operational. The richer source_health.yml holds 24 fields
    # including last_error, adapter_type and consecutive_failures; none of that belongs here.
    allowed_product = {"product_id", "state", "label", "last_success", "last_checked"}
    extra = sorted({k for r in rows for k in r} - allowed_product)
    check("D5 the product projection carries no operational field", not extra, f"extra: {extra}")
    allowed_company = {"company_id", "state", "label", "monitored", "total"}
    cextra = sorted({k for r in crows for k in r} - allowed_company)
    check("D6 the company projection carries no operational field", not cextra, f"extra: {cextra}")


def section_e_company_aggregate() -> None:
    print("\n[E] a company summarises its products honestly")
    cs = proj.company_state
    check("E1 all products healthy -> active", cs(["healthy", "healthy"])[0] == "healthy")
    check("E2 some healthy -> a COUNT, not an adjective",
          cs(["healthy", "disabled", "disabled"]) == ("partial", "Monitoring 1 of 3"),
          "27 companies claimed 'Monitoring active' with zero healthy products")
    check("E3 none healthy but something failing -> says checks are failing",
          cs(["blocked", "blocked"])[0] == "failing")
    check("E4 none healthy and nothing configured -> not monitored",
          cs(["disabled", "disabled"])[0] == "disabled")
    check("E5 a company with no products -> unconfigured", cs([])[0] == "unconfigured")
    check("E6 'not monitored' and 'checks failing' are different labels",
          cs(["disabled"])[1] != cs(["broken"])[1])
    check("E7 one broken product does not read as monitored",
          cs(["broken"])[0] == "failing",
          "netlify claimed active while its only product was broken")


def section_f_raw_state_not_in_templates() -> None:
    print("\n[F] no template reads the raw ingest state")
    # INTERIM CONTAINMENT. patch_ingest_state.json sits in _data, so Jekyll loads it into
    # site.data for every template whether or not one references it, and it carries raw error
    # bodies, adapter names and failure counters. Relocating it is 27 files across all four
    # committing workflows and is tracked separately; until then, nothing may read it.
    offenders = []
    for path in list((_AUX / "_layouts").glob("*.html")) + \
                list((_AUX / "_includes").glob("*.html")) + \
                list((_AUX / "updates").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "",
                          text, flags=re.S)
        if "patch_ingest_state" in stripped:
            offenders.append(path.name)
    check("F1 no layout, include or page reads site.data.patch_ingest_state", not offenders,
          f"offenders: {offenders}")
    for path in TEMPLATES:
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "",
                          text, flags=re.S)
        rendered_label = [ln for ln in stripped.splitlines()
                          if "coverage_status_label" in ln and "{{" in ln]
        check(f"F2 {path.name} no longer renders the editorial label as a claim",
              not rendered_label, f"{rendered_label[:1]}")
        check(f"F3 {path.name} uses '' rather than the inert `blank`",
              not re.search(r"[!=]=\s*blank", stripped))


def section_g_projection_is_current() -> None:
    print("\n[G] the committed projection matches what the generator produces")
    # The deploy regenerates this before building, so a stale committed copy is not published --
    # but a stale copy in the repository makes every local render and every review misleading.
    out = subprocess.run([sys.executable, str(_SCRIPTS / "build_monitoring_projection.py"),
                          "--check"], capture_output=True, text=True, timeout=300)
    check("G1 --check reports the committed projection current", out.returncode == 0,
          (out.stdout + out.stderr).strip()[:200])

    # And prove --check actually detects staleness, rather than always passing.
    with tempfile.TemporaryDirectory() as td:
        backup = PRODUCT_PROJECTION.read_text(encoding="utf-8")
        Path(td, "backup.yml").write_text(backup, encoding="utf-8")
        try:
            PRODUCT_PROJECTION.write_text(backup + "\n# tampered\n", encoding="utf-8")
            out2 = subprocess.run([sys.executable,
                                   str(_SCRIPTS / "build_monitoring_projection.py"), "--check"],
                                  capture_output=True, text=True, timeout=300)
            check("G2 --check FAILS on a tampered projection", out2.returncode != 0,
                  "a check that always passes is not a check")
        finally:
            PRODUCT_PROJECTION.write_text(backup, encoding="utf-8")
    check("G3 the projection was restored after the tamper test",
          PRODUCT_PROJECTION.read_text(encoding="utf-8") == backup)


def run() -> int:
    section_a_fail_closed()
    section_b_distinct_failures()
    section_c_cadence_recency()
    section_d_vocabulary_is_closed()
    section_e_company_aggregate()
    section_f_raw_state_not_in_templates()
    section_g_projection_is_current()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
