#!/usr/bin/env python3
"""PowerPoint R2: deterministic exact-build context resolution.

Every case drives the REAL acceptance authority (``ppt.row_from_candidate``) before and after
resolution. The resolver only fetches more of the SAME thread and hands the source's own words
back; it never decides acceptance and never infers a build. Fixtures A-H from the R2 contract.

Deterministic and offline: the thread fetch is injected. No network, no repo mutation.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_context_resolution.py
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import context_resolution as cr  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import PatchRecord  # noqa: E402

PRODUCT = "microsoft-powerpoint"
VERSION = "2607"
BUILD = "20228.20110"
OTHER_BUILD = "20228.20200"
SIBLING_BUILD = "20228.20300"
RELEASE = "2026-07-23T00:00:00Z"
CAPTURED = "2026-08-01T00:00:00Z"
URL = "https://learn.microsoft.com/en-us/answers/questions/5975138/powerpoint-crash"

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


def target(build: str = BUILD) -> dict:
    return {"update_version": VERSION, "target_build": build,
            "target_release_date": RELEASE, "version_ambiguous": False}


def record(build: str = BUILD) -> PatchRecord:
    return PatchRecord(product_id=PRODUCT, update_version=VERSION, path=Path("x.md"),
                       update_published_at=RELEASE, update_status="current",
                       update_product="Microsoft PowerPoint", target_build=build)


def version_only_candidate(url: str = URL) -> dict:
    """A realistic search-RSS item: names PowerPoint + the exact YYMM, but no build."""
    title = f"PowerPoint Version {VERSION} crashes on save"
    return {"source_type": ppt.LEARN_QNA_SOURCE_TYPE, "source_name": ppt.LEARN_QNA_SOURCE_NAME,
            "source_url": url, "parent_title": title, "report_title": title,
            "report_text": (f"After installing PowerPoint Version {VERSION} on the Current Channel "
                            "it closes unexpectedly every time I save a deck. It worked before the "
                            "update and broke immediately after installing this update."),
            "source_date": "2026-08-01T00:00:00Z"}


def verdict(cand: dict, rec_build: str = BUILD) -> tuple:
    row = ppt.row_from_candidate(record(rec_build), target(rec_build), cand, CAPTURED)
    return row.get("counted"), row.get("exclusion_reason"), row.get("target_build")


def thread(text: str, status: str = "ok"):
    calls = {"n": 0, "urls": []}

    def fetch(url: str) -> tuple[str, str]:
        calls["n"] += 1
        calls["urls"].append(url)
        return text, status

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def run() -> int:  # noqa: PLR0915
    print("=" * 72)
    print("PowerPoint R2 -- deterministic exact-build context resolution (fixtures A-H)")
    print("=" * 72)

    # Baseline: the search item alone is correctly rejected.
    counted, reason, built = verdict(version_only_candidate())
    check("baseline: version-only search item is rejected missing_exact_build",
          counted is False and reason == cr.RESOLVABLE_REASON, f"{counted} {reason}")
    check("baseline: no build is stamped on the rejected row", not built, repr(built))

    # ---- A. thread contains no build -> stays uncounted ------------------------------------
    fetch = thread(f"PowerPoint Version {VERSION} keeps crashing for me too. Any fix? "
                   "I already repaired Office and restarted.")
    budget = cr.ResolutionBudget()
    out = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                               fetch_thread=fetch, budget=budget)
    check("A thread with no build -> no_explicit_build", out.resolution_result == cr.NO_EXPLICIT_BUILD,
          out.resolution_result)
    check("A no build was resolved", not out.explicit_build_found and not out.resolved_build)
    counted, reason, _ = verdict(cr.augmented_candidate(version_only_candidate(), out))
    check("A candidate REMAINS uncounted after a fruitless resolution",
          counted is False and reason == cr.RESOLVABLE_REASON, f"{counted} {reason}")

    # ---- B. thread explicitly names the exact build -> accepted ------------------------------
    fetch = thread(f"I hit this too. Help > About shows Microsoft PowerPoint Version {VERSION} "
                   f"(Build {BUILD} Click-to-Run). Saving fails every time since that update.")
    budget = cr.ResolutionBudget()
    out = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                               fetch_thread=fetch, budget=budget)
    check("B thread stating the build -> resolved_exact_build",
          out.resolution_result == cr.RESOLVED_EXACT_BUILD, out.resolution_result)
    check("B the resolved build is the one the SOURCE stated", out.resolved_build == BUILD,
          out.resolved_build)
    check("B provenance snippet carries the verbatim source text",
          BUILD in out.provenance_snippet and "About" in out.provenance_snippet,
          out.provenance_snippet)
    check("B match basis names the same-thread scope",
          out.resolution_match_basis == "explicit_build_in_same_thread"
          and out.resolution_source_scope == cr.SOURCE_SCOPE)
    check("B resolution source url is the candidate's OWN url (not a search)",
          out.resolution_source_url == URL and out.original_candidate_url == URL)
    counted, reason, built = verdict(cr.augmented_candidate(version_only_candidate(), out))
    check("B the UNCHANGED acceptance authority now ACCEPTS it",
          counted is True and reason is None, f"{counted} {reason}")
    check("B the accepted row carries the exact build", built == BUILD, repr(built))

    # ---- C. thread names the WRONG build -> rejected build_mismatch --------------------------
    fetch = thread(f"About shows Version {VERSION} (Build {OTHER_BUILD}). Crashes on save.")
    budget = cr.ResolutionBudget()
    out = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                               fetch_thread=fetch, budget=budget)
    check("C a wrong build still resolves as an explicit build", out.resolved_build == OTHER_BUILD)
    counted, reason, built = verdict(cr.augmented_candidate(version_only_candidate(), out))
    check("C the authority REJECTS it as build_mismatch (resolution is not acceptance)",
          counted is False and reason == "build_mismatch", f"{counted} {reason}")
    check("C no build is stamped on the rejected row", not built, repr(built))

    # ---- D. two conflicting builds -> unresolved -------------------------------------------
    fetch = thread(f"I'm on Version {VERSION} (Build {BUILD}) but my colleague on Build "
                   f"{OTHER_BUILD} sees it too.")
    budget = cr.ResolutionBudget()
    out = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                               fetch_thread=fetch, budget=budget)
    check("D two distinct builds -> conflicting_build",
          out.resolution_result == cr.CONFLICTING_BUILD, out.resolution_result)
    check("D no build is chosen from a conflict (choosing would be inference)",
          not out.resolved_build and not out.explicit_build_found, out.resolved_build)
    counted, reason, _ = verdict(cr.augmented_candidate(version_only_candidate(), out))
    check("D candidate remains uncounted", counted is False and reason == cr.RESOLVABLE_REASON,
          f"{counted} {reason}")

    # ---- E. fetch blocked / broken -> uncounted, honestly recorded ---------------------------
    budget = cr.ResolutionBudget()
    out = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                               fetch_thread=thread("", "blocked"), budget=budget)
    check("E blocked fetch -> fetch_blocked", out.resolution_result == cr.FETCH_BLOCKED,
          out.resolution_result)
    counted, reason, _ = verdict(cr.augmented_candidate(version_only_candidate(), out))
    check("E blocked fetch leaves the candidate uncounted",
          counted is False and reason == cr.RESOLVABLE_REASON)

    def boom(url: str):
        raise TimeoutError("simulated transport failure")

    budget = cr.ResolutionBudget()
    out = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                               fetch_thread=boom, budget=budget)
    check("E transport exception -> fetch_broken (telemetry, not a crash)",
          out.resolution_result == cr.FETCH_BROKEN and out.detail == "TimeoutError",
          f"{out.resolution_result} {out.detail}")

    # ---- F. restart: a URL is never fetched twice -------------------------------------------
    fetch = thread(f"Version {VERSION} (Build {BUILD}) crashes on save.")
    budget = cr.ResolutionBudget()
    first = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                                 fetch_thread=fetch, budget=budget)
    second = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                                  fetch_thread=fetch, budget=budget)
    check("F the same thread URL is fetched exactly once across attempts",
          fetch.calls["n"] == 1, f"fetches={fetch.calls['n']}")
    check("F the receipted outcome is returned identically on the second attempt",
          second.as_dict() == first.as_dict())
    check("F the receipt is keyed by canonical URL", URL in budget.receipts)

    # ---- G. sibling same-YYMM builds: only the exact match may receive it --------------------
    fetch = thread(f"About: Version {VERSION} (Build {BUILD}). Crashes on save.")
    budget = cr.ResolutionBudget()
    out = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                               fetch_thread=fetch, budget=budget)
    resolved = cr.augmented_candidate(version_only_candidate(), out)
    counted_a, reason_a, built_a = verdict(resolved, BUILD)
    counted_b, reason_b, built_b = verdict(resolved, SIBLING_BUILD)
    check("G the resolved report is accepted ONLY by its exact build record",
          counted_a is True and built_a == BUILD, f"{counted_a} {reason_a} {built_a}")
    check("G a sibling build under the SAME YYMM refuses it",
          counted_b is False and reason_b == "build_mismatch", f"{counted_b} {reason_b}")
    check("G no build leaks onto the sibling's rejected row", not built_b, repr(built_b))

    # ---- H. no AI credentials -> resolution path still works ---------------------------------
    ai_vars = [k for k in os.environ
               if any(t in k.upper() for t in ("OPENAI", "ANTHROPIC", "LANGCHAIN", "LANGSMITH",
                                               "GEMINI", "MISTRAL", "COHERE"))]
    saved = {k: os.environ.pop(k) for k in ai_vars}
    try:
        fetch = thread(f"Version {VERSION} (Build {BUILD}) crashes on save.")
        budget = cr.ResolutionBudget()
        out = cr.resolve_candidate(version_only_candidate(), cr.RESOLVABLE_REASON,
                                   fetch_thread=fetch, budget=budget)
        counted, reason, built = verdict(cr.augmented_candidate(version_only_candidate(), out))
        check("H full resolve -> accept works with zero AI environment",
              out.resolution_result == cr.RESOLVED_EXACT_BUILD and counted is True and built == BUILD,
              f"{out.resolution_result} {counted} {built}")
    finally:
        os.environ.update(saved)
    src = (_REPO / "auxsays" / "scripts" / "lib" / "context_resolution.py").read_text(encoding="utf-8")
    bad = [ln.strip() for ln in src.splitlines()
           if ln.strip().startswith(("import ", "from "))
           and any(t in ln for t in ("langchain", "langgraph", "openai", "anthropic"))]
    check("H the resolver imports no AI/provider packages", not bad, str(bad))

    # ---- doctrine guards --------------------------------------------------------------------
    for reason_in in ("product_not_powerpoint", "missing_powerpoint_version", "build_mismatch",
                      "channel_conflict", "date_before_release_or_undated"):
        out = cr.resolve_candidate(version_only_candidate(), reason_in,
                                   fetch_thread=thread("Build 20228.20110"),
                                   budget=cr.ResolutionBudget())
        check(f"doctrine: {reason_in} is NOT resolvable",
              out.resolution_result == cr.NOT_APPLICABLE and not out.resolution_attempted,
              out.resolution_result)
    budget = cr.ResolutionBudget(max_fetches=1)
    fetch = thread(f"Version {VERSION} (Build {BUILD}).")
    cr.resolve_candidate(version_only_candidate("https://learn.microsoft.com/en-us/answers/questions/1/a"),
                         cr.RESOLVABLE_REASON, fetch_thread=fetch, budget=budget)
    out = cr.resolve_candidate(version_only_candidate("https://learn.microsoft.com/en-us/answers/questions/2/b"),
                               cr.RESOLVABLE_REASON, fetch_thread=fetch, budget=budget)
    check("doctrine: the fetch budget bounds the work (no crawl)",
          out.resolution_result == cr.NOT_APPLICABLE and fetch.calls["n"] == 1,
          f"{out.resolution_result} fetches={fetch.calls['n']}")
    check("doctrine: an unresolved candidate never carries a build",
          not cr.augmented_candidate(version_only_candidate(),
                                     cr.ResolutionOutcome(resolution_result=cr.NO_EXPLICIT_BUILD)
                                     ).get("context_resolved_build"))

    print()
    print("=" * 72)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 72)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
