#!/usr/bin/env python3
"""One monitoring-health authority in Python, parity-pinned to the page (AUX-054).

WHY IT EXISTS. Whether a patch's community collection is healthy was decided only in Liquid, by the
monitoring card (`_includes/monitoring-status.html`), and the test that renders that card needs
Jekyll, so PR CI never ran it -- its expectation table had drifted from the include unnoticed. The
live-consensus certifier needs the same judgement in Python, and stricter: a live claim must fail
closed on any missing, blocked, stale or unowned telemetry.

WHAT IS PINNED HERE.
  [L] `monitoring_health.ladder` reproduces the shipped card on every fixture case, from the SAME
      expectation table the Liquid render test uses (fixtures/monitoring/expect.yml), and the
      include's rung order is the port's.
  [H] `certify_monitoring` (H0-H7): every condition refuses on its own; a retired method's
      `disabled` row satisfies completeness without counting as healthy or failing; one healthy
      family is enough (no two-family minimum); a manual capture is never monitoring proof.
  [R] on the frozen 2026-10-27 snapshot of the eight High-rung patches, the three OBS and three
      Windows identities certify healthy and both DaVinci identities fail, each for named reasons.
  [O] method-health writers outside the collector runner are held to the ownership manifest, and
      every stored health row names an owned method.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_monitoring_health.py
"""
from __future__ import annotations

import ast
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

from lib import collector_ownership as ownership  # noqa: E402
from lib import monitoring_health as mh  # noqa: E402

FIXTURE = _SCRIPTS / "tests" / "fixtures" / "monitoring"
INCLUDE = _REPO / "auxsays" / "_includes" / "monitoring-status.html"

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


def _css(status: str) -> str:
    return status.lower().replace(" ", "-")


def section_l() -> None:
    print("\n[L] the Python ladder is the page's ladder")
    expect = {str(k): str(v) for k, v in
              yaml.safe_load((FIXTURE / "expect.yml").read_text(encoding="utf-8")).items()}
    rows = mh.load_method_health_rows(FIXTURE / "_data" / "evidence_method_health.yml")
    thresholds = mh.load_thresholds(FIXTURE / "_config.yml")
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    for n in range(1, 18):
        name = f"c{n}"
        identity = {"product_id": "c15-absent" if n == 15 else name,
                    "update_version": "2607" if n == 13 else "1.0"}
        got = _css(mh.ladder(mh.rows_for(identity, rows), published_at="2026-06-01T00:00:00Z",
                             report_count=3 if n == 14 else 0, now=now, thresholds=thresholds))
        check(f"L{n} {name} -> {expect[name]}", got == expect[name], f"got {got}")
    include = INCLUDE.read_text(encoding="utf-8")
    chain = re.findall(r"assign mon_status = '([A-Z -]+)'", include.split("{%- assign mon_status_class", 1)[0])
    ported = [mh.NO_ACCEPTED_REPORTS, mh.OFFICIAL_SOURCE_ONLY, mh.OFFICIAL_SOURCE_ONLY,
              mh.COLLECTION_STALE, mh.NOT_YET_MONITORED, mh.COLLECTION_STALE, mh.COLLECTION_BLOCKED,
              mh.MONITORING_DEGRADED, mh.INSUFFICIENT_COVERAGE, mh.MONITORING_ACTIVE,
              mh.NO_ACCEPTED_REPORTS]
    check("L18 the include's rung order is the port's (default, then rungs 1-10)", chain == ported,
          str(chain))


# ------------------------------------------------------------------------------------------------
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
RELEASED = "2026-10-01T00:00:00Z"
FRESH = "2026-10-27T06:00:00Z"
OWNED = {"p": {"m1", "m2", "m3"}}
T = mh.Thresholds(max_age_days=14, min_healthy_families=2)


def hrow(method: str, status: str = "success", *, family: str | None = None,
         last_run: str = FRESH) -> dict:
    return {"product_id": "p", "update_version": "1.0", "method_id": method,
            "source_type": family or {"m1": "s1", "m2": "s2", "m3": "s3"}.get(method, "s9"),
            "status": status, "last_run": last_run}


def certify(rows, *, families=("s1",), published_at=RELEASED, manual=()):
    return mh.certify_monitoring("p", rows, published_at=published_at, contributing_families=families,
                                 now=NOW, thresholds=T, owned_methods=OWNED, manual_only_methods=manual)


def has(decision: mh.HealthDecision, prefix: str) -> bool:
    return any(reason.startswith(prefix) for reason in decision.reasons)


def section_h() -> None:
    print("\n[H] certification: every condition refuses on its own")
    clean = [hrow("m1"), hrow("m2", "no_results"), hrow("m3", "disabled")]
    base = certify(clean)
    check("H-a healthy rows plus a retired method's disabled row certify",
          base.healthy and base.reasons == (), str(base.reasons))
    one_family = certify([hrow("m1"), hrow("m2", "disabled"), hrow("m3", "disabled")], families=("s1",))
    check("H-b ONE healthy family is enough: no two-family minimum for live consensus",
          one_family.healthy, str(one_family.reasons))
    check("H0 a row from a method the product does not own refuses",
          has(certify(clean + [hrow("m9")]), "unowned_method:m9"))
    check("H7 an owned method with NO row for this patch refuses (silent stop cannot pass)",
          has(certify([hrow("m1"), hrow("m3", "disabled")]), "missing_method_telemetry:m2"))
    check("H1 every method disabled refuses",
          has(certify([hrow("m1", "disabled"), hrow("m2", "disabled"), hrow("m3", "disabled")]),
              "no_active_method"))
    future = certify([hrow("m1"), hrow("m2", last_run="2026-11-30T00:00:00Z"), hrow("m3", "disabled")])
    empty = certify([hrow("m1"), hrow("m2", last_run=""), hrow("m3", "disabled")])
    check("H2 a future or empty timestamp refuses",
          has(future, "invalid_timestamp:m2") and has(empty, "invalid_timestamp:m2"))
    check("H3 a run before the release refuses",
          has(certify([hrow("m1"), hrow("m2", last_run="2026-09-20T00:00:00Z"), hrow("m3", "disabled")]),
              "ran_before_release:m2"))
    check("H3 a run older than monitoring_max_age_days refuses",
          has(certify([hrow("m1"), hrow("m2", last_run="2026-10-12T00:00:00Z"), hrow("m3", "disabled")]),
              "stale:m2"))
    check("H3 a patch with no release date refuses", has(certify(clean, published_at=""), "no_release_date"))
    degraded = [certify([hrow("m1"), hrow("m2", status), hrow("m3", "disabled")])
                for status in sorted(mh.DEGRADED_STATUSES)]
    check("H4 every degraded status on any active method refuses",
          all(has(d, "degraded:m2:") for d in degraded), str([d.reasons for d in degraded]))
    check("H5 active methods with none healthy refuse",
          has(certify([hrow("m1", "blocked"), hrow("m2", "partial"), hrow("m3", "disabled")]),
              "no_healthy_method"))
    laundered = certify([hrow("m1"), hrow("m2", "disabled"), hrow("m3", "disabled")], families=("s1", "s2"))
    check("H6 a contributing family whose only method was disabled refuses -- disabling a blocked "
          "method cannot launder a pass on a side channel",
          has(laundered, "contributing_family_unhealthy:s2"), str(laundered.reasons))
    owned_manual = {"p": {"m1", "m2", "m3", "manual"}}
    manual_only = mh.certify_monitoring("p", [hrow("manual", family="s1")], published_at=RELEASED,
                                        contributing_families=("s1",), now=NOW, thresholds=T,
                                        owned_methods=owned_manual, manual_only_methods=("manual",))
    manual_extra = mh.certify_monitoring("p", clean + [hrow("manual", "blocked")], published_at=RELEASED,
                                         contributing_families=("s1",), now=NOW, thresholds=T,
                                         owned_methods=owned_manual, manual_only_methods=("manual",))
    check("H8 a manual capture is never proof of running collection, and is never expected",
          not manual_only.healthy and has(manual_only, "missing_method_telemetry:m1")
          and manual_extra.healthy, f"{manual_only.reasons} / {manual_extra.reasons}")


# ------------------------------------------------------------------------------------------------
def section_r() -> None:
    print("\n[R] the frozen 2026-10-27 High-rung snapshot")
    snap = yaml.safe_load((FIXTURE / "candidates_2026-10-27.yml").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(snap["now"].replace("Z", "+00:00"))
    thresholds = mh.load_thresholds(_REPO / "auxsays" / "_config.yml")
    decisions = {}
    for c in snap["candidates"]:
        label = f"{c['product_id']} {c['update_version']}{(' ' + c['target_build']) if c['target_build'] else ''}"
        decisions[label] = mh.certify_monitoring(
            c["product_id"], c["method_health"], published_at=c["update_published_at"],
            contributing_families=c["contributing_families"], now=now, thresholds=thresholds,
            owned_methods=ownership.ALLOWED_METHODS, manual_only_methods=ownership.MANUAL_ONLY_METHODS)
    passing = sorted(k for k, d in decisions.items() if d.healthy)
    check("R1 exactly the three OBS and three Windows identities certify healthy",
          passing == sorted(["obs-studio 32.1.2", "obs-studio 32.2.2", "obs-studio 32.1.1",
                             "microsoft-windows-11 25H2 26200.7462", "microsoft-windows-11 25H2 26200.7623",
                             "microsoft-windows-11 25H2 26200.7840"]),
          str({k: d.reasons for k, d in decisions.items()}))
    dv21, dv2032 = decisions.get("blackmagic-davinci 21"), decisions.get("blackmagic-davinci 20.3.2")
    check("R2 DaVinci 21 fails for named reasons: its only contributing family (Reddit) is blocked",
          dv21 is not None and not dv21.healthy
          and has(dv21, "degraded:reddit_search:blocked")
          and has(dv21, "contributing_family_unhealthy:reddit_community_report"),
          str(dv21 and dv21.reasons))
    check("R3 DaVinci 20.3.2 fails for named reasons: Reddit, behind 32 of its 33 reports, is partial",
          dv2032 is not None and not dv2032.healthy
          and has(dv2032, "degraded:reddit_search:partial")
          and has(dv2032, "contributing_family_unhealthy:reddit_community_report"),
          str(dv2032 and dv2032.reasons))
    obs = decisions.get("obs-studio 32.1.2")
    obs_card = mh.ladder(next(c for c in snap["candidates"]
                              if str(c["update_version"]) == "32.1.2")["method_health"],
                         published_at="2026-04-21T00:00:00Z", report_count=109, now=now,
                         thresholds=thresholds)
    check("R4 OBS's retired watchlist slot no longer marks its card degraded: it reads ACTIVE",
          obs is not None and obs.healthy and obs_card == mh.MONITORING_ACTIVE, obs_card)


# ------------------------------------------------------------------------------------------------
def _upserts_are_guarded(path: Path) -> str:
    """'guarded' when every `upsert_method_health(rows, ...)` in the file is preceded, in the same
    function, by `require_owned_methods(rows)` on the same variable -- statement-level, not a grep."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    upserts = 0
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        named = [(getattr(c.func, "id", getattr(c.func, "attr", "")), c)
                 for c in ast.walk(fn) if isinstance(c, ast.Call)]
        for name, call in named:
            if name != "upsert_method_health" or not call.args or not isinstance(call.args[0], ast.Name):
                continue
            upserts += 1
            rows = call.args[0].id
            if not any(other == "require_owned_methods" and c.args and isinstance(c.args[0], ast.Name)
                       and c.args[0].id == rows and c.lineno < call.lineno for other, c in named):
                return f"unguarded upsert of {rows!r} at line {call.lineno}"
    return "guarded" if upserts else "no upsert found"


def section_o() -> None:
    print("\n[O] method-health writers are held to the ownership manifest")
    refused = False
    try:
        ownership.require_owned_methods([{"product_id": "obs-studio", "method_id": "made_up_method"}])
    except ownership.OwnershipViolation:
        refused = True
    accepted = True
    try:
        ownership.require_owned_methods([
            {"product_id": "microsoft-powerpoint", "method_id": "learn_qna_segment_context"},
            {"product_id": "adobe-premiere-pro", "method_id": "local_playwright_capture_promotion"}])
    except ownership.OwnershipViolation:
        accepted = False
    check("O1 an undeclared method is refused; the graph's resolver and the local capture are declared",
          refused and accepted)
    guarded = {name: _upserts_are_guarded(_SCRIPTS / name)
               for name in ("orchestrate_evidence_run.py", "promote_local_playwright_captures.py")}
    check("O2 both writers that bypass the collector runner check ownership of the SAME rows before "
          "upserting them",
          all(v == "guarded" for v in guarded.values()), str(guarded))
    # The published limitation sentence reads the same telemetry as the card; it must agree with the
    # authority on what "degraded" means. It used a four-status subset, missing stale and
    # manual_review_needed (no such rows exist today, so this is the only thing that would notice).
    import apply_consensus_to_records as acr  # noqa: PLC0415 - heavy; only this check needs it
    real_loader = acr._load_method_health_rows
    said = {}
    try:
        for status in sorted(mh.DEGRADED_STATUSES | {"success"}):
            acr._load_method_health_rows = lambda status=status: [
                {"product_id": "obs-studio", "update_version": "99.1.0", "method_id": "github_issues",
                 "status": status}]
            said[status] = any("unavailable" in line for line in
                               acr._public_source_limitations("obs-studio", "99.1.0", [], "High", build=""))
    finally:
        acr._load_method_health_rows = real_loader
    check("O3 the published limitation sentence fires for every degraded status the card uses, and "
          "not for a healthy one",
          all(said[s] for s in mh.DEGRADED_STATUSES) and not said["success"], str(said))


def main() -> int:
    for section in (section_l, section_h, section_r, section_o):
        section()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
