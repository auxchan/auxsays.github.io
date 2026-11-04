#!/usr/bin/env python3
"""AUX-068: the PowerPoint Learn Q&A collection budget is VISIBLE in the method-health note.

Every production run of the context-resolution stage ended `fetches=200` against a ceiling of 200
while the orchestrator already knew how many threads it had found and how many were worth a fetch.
That knowledge went to a receipt and nowhere a reader of the health file could see it, so "200"
could not be told apart from "all done". This suite drives the REAL `Pipeline.resolve_context`
over real schema.org QAPage fixtures with an injected transport (no network), through the REAL
`upsert_method_health` writer and a YAML round trip, and pins:

  * the note names attempted / max / successful / distinct / eligible / scope / exhausted;
  * attempted and successful are different counters (a blocked fetch is attempted, not successful);
  * the thread counts are RUN-WIDE (every patch target of the run), never a per-patch population;
  * exhaustion states that coverage was bounded, and a roomy budget does not;
  * the note survives the writer, and nothing but `notes` is touched (budget 200, counters, status).

Deterministic and offline. Temp dirs only.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_budget_telemetry.py
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import traceback
import types
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import orchestrate_evidence_run as orch  # noqa: E402
from lib import context_resolution as cr  # noqa: E402
from lib.orchestration import OrchestrationState  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import (  # noqa: E402
    PatchRecord, load_method_health, upsert_method_health,
)

PRODUCT = "microsoft-powerpoint"
VERSION = "2607"
BUILD_A = "20228.20110"
BUILD_B = "20228.20200"
RELEASE = "2026-07-23T00:00:00Z"
KEY_A = f"{PRODUCT}|{VERSION}|{BUILD_A}"
KEY_B = f"{PRODUCT}|{VERSION}|{BUILD_B}"
ISSUE = "PowerPoint crashes on save and the presentation window closes every time."

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


def thread_url(n: int) -> str:
    return f"https://learn.microsoft.com/en-us/answers/questions/{7000 + n}/powerpoint-crash"


def qapage(n: int) -> str:
    payload = {
        "@context": "https://schema.org", "@type": "QAPage",
        "mainEntity": {
            "@type": "Question", "@id": f"https://learn.microsoft.com/en-us/questions/{7000 + n}/x",
            "id": str(7000 + n), "name": "PowerPoint crash", "text": f"<p>{ISSUE}</p>",
            "answerCount": 0, "author": "Op", "authorId": "5eee431a-ba0c-439a-961f-fe3092adbd65",
            "acceptedAnswer": [], "suggestedAnswer": [], "moderatorRecommendedAnswers": [],
        },
    }
    return ('<html><head><script type="application/ld+json">' + json.dumps(payload)
            + '</script></head><body><div id="question">rendered</div></body></html>')


def row(url: str, reason: str = "missing_exact_build", text: str = ISSUE,
        title: str = f"PowerPoint Version {VERSION} crash") -> dict:
    return {"source_url": url, "exclusion_reason": reason, "report_text": text,
            "parent_title": title, "report_title": "",
            "source_date": "2026-08-14", "source_type": "microsoft_learn_qna",
            "source_name": "Microsoft Learn Q&A"}


def make_pipeline(max_fetches: int, transport):
    records = {k: PatchRecord(product_id=PRODUCT, update_version=VERSION, path=Path("x.md"),
                              update_published_at=RELEASE, update_status="current",
                              update_product="Microsoft PowerPoint", target_build=k.split("|")[2])
               for k in (KEY_A, KEY_B)}
    return types.SimpleNamespace(_records=records, _seen={}, context_fetch=transport,
                                 context_max_fetches=max_fetches,
                                 _persist_url_state=lambda *a, **k: None)


def drive(max_fetches: int, results: list[dict], transport):
    state = OrchestrationState()
    state.method_results = results
    me = make_pipeline(max_fetches, transport)
    st = orch.Pipeline.resolve_context(me, state)
    return st, [r["health_row"] for r in st.method_results if r.get("role") == "context_resolution"]


def note_fields(note: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in note.split(";")[1:]:
        if "=" in part:
            k, _, v = part.strip().partition("=")
            out[k] = v
    return out


def scenario_results() -> list[dict]:
    """Two patch targets. Threads: 1,2,3 are rank 0 (build gap), 4 is rank 2 (how-to), and thread 1
    is queued by BOTH targets (the same thread re-queued once per patch record)."""
    return [
        {"method_id": "m", "patch_key": KEY_A, "accepted_rows": [], "resolvable_rows": [
            row(thread_url(1)), row(thread_url(2)),
            row(thread_url(4), "missing_powerpoint_version", "How do I find the design tab",
                "Where is the design tab")]},
        {"method_id": "m", "patch_key": KEY_B, "accepted_rows": [], "resolvable_rows": [
            row(thread_url(1)), row(thread_url(3))]},
    ]


def run() -> int:
    print("=" * 76)
    print("AUX-068 POWERPOINT COLLECTION-BUDGET TELEMETRY")
    print("=" * 76)

    # ---- A: a budget that runs out, with a mix of fetch outcomes ----------------------------
    print("\n[A] budget of 2 over 4 distinct threads: one ok, one blocked, two never fetched")
    calls: list[str] = []

    def transport_a(url: str):
        calls.append(url)
        return ("", "blocked") if url == thread_url(2) else (qapage(int(url.split("/")[-2]) - 7000), "ok")

    # Rank order puts the rank-0 threads first by URL: 1, 2, 3 then 4.
    st, health = drive(2, scenario_results(), transport_a)
    check("A1 two context health rows, one per patch target", len(health) == 2, str(len(health)))
    notes = [h["notes"] for h in health]
    f = note_fields(notes[0])
    check("A2 the note names the budget it was spent against", f.get("max_fetches") == "2", notes[0])
    check("A3 attempted fetches equal the real transport calls (2)",
          len(calls) == 2 and re.search(r"fetches=2(;|$)", notes[0]) is not None, f"{calls} {notes[0]}")
    check("A4 successful fetches count only ok+parsed threads (1 of 2 attempted)",
          f.get("successful_fetches") == "1", notes[0])
    check("A5 attempted and successful are different counters when a fetch is blocked",
          f.get("successful_fetches") != str(len(calls)), notes[0])
    check("A6 distinct threads is 4 (thread 1 queued by both targets counts once)",
          f.get("distinct_threads") == "4", notes[0])
    check("A7 eligible threads is 3 (rank 0 or 1 only; the how-to thread is not)",
          f.get("eligible_threads") == "3", notes[0])
    check("A8 the thread counts declare a run-wide scope, not a per-patch one",
          f.get("thread_scope") == orch.THREAD_SCOPE == "all_patch_targets_of_this_run", notes[0])
    check("A9 the budget is reported exhausted", f.get("budget_exhausted") == "yes", notes[0])
    check("A10 exhaustion states that coverage was bounded", f.get("coverage_bounded") == "yes", notes[0])
    check("A11 threads the budget refused are counted (2: thread 3 and thread 4)",
          f.get("threads_refused_budget") == "2", notes[0])
    check("A12 both patch rows carry the SAME run-wide thread counts",
          {note_fields(n).get("distinct_threads") for n in notes} == {"4"}
          and {note_fields(n).get("eligible_threads") for n in notes} == {"3"}, str(notes))
    check("A13 the original leading text is preserved byte for byte",
          all(n.startswith("segment-scoped exact-build resolution; fetches=2") for n in notes), str(notes))

    # ---- B: a roomy budget -------------------------------------------------------------------
    print("\n[B] a budget of 200 that is not reached")
    calls_b: list[str] = []

    def transport_b(url: str):
        calls_b.append(url)
        return qapage(int(url.split("/")[-2]) - 7000), "ok"

    _st, health_b = drive(200, scenario_results(), transport_b)
    fb = note_fields(health_b[0]["notes"])
    check("B1 attempted 4 of max 200", re.search(r"; fetches=4;", health_b[0]["notes"]) is not None
          and fb.get("max_fetches") == "200", health_b[0]["notes"])
    check("B2 all four fetches succeeded", fb.get("successful_fetches") == "4", health_b[0]["notes"])
    check("B3 not exhausted and NOT labelled bounded",
          fb.get("budget_exhausted") == "no" and "coverage_bounded" not in fb, health_b[0]["notes"])
    check("B4 nothing refused", fb.get("threads_refused_budget") == "0", health_b[0]["notes"])

    # ---- C: a transport that raises counts as attempted, never successful ----------------------
    print("\n[C] a raising transport")

    def transport_c(url: str):
        raise OSError("boom")

    _st, health_c = drive(200, scenario_results(), transport_c)
    fc = note_fields(health_c[0]["notes"])
    check("C1 raising fetches are attempted (4) and none successful (0)",
          re.search(r"; fetches=4;", health_c[0]["notes"]) is not None and fc.get("successful_fetches") == "0",
          health_c[0]["notes"])

    # ---- D: the helper, in isolation --------------------------------------------------------
    print("\n[D] the helper reads counters, it does not invent them")
    b = cr.ResolutionBudget(max_fetches=5)
    b.fetched = 5
    b.threads = {"u1": (None, "blocked"), "u2": (None, "broken:status=500")}
    suffix = orch.budget_telemetry_suffix(b, 9, 7)
    check("D1 attempted==max reads exhausted even with zero successes",
          "budget_exhausted=yes" in suffix and "successful_fetches=0" in suffix, suffix)
    check("D2 distinct/eligible are passed through unchanged",
          "distinct_threads=9" in suffix and "eligible_threads=7" in suffix, suffix)
    b2 = cr.ResolutionBudget(max_fetches=5)
    check("D3 a fresh budget reads 0 successful, not exhausted",
          "successful_fetches=0" in orch.budget_telemetry_suffix(b2, 0, 0)
          and "budget_exhausted=no" in orch.budget_telemetry_suffix(b2, 0, 0), "")

    # ---- E: the note survives the existing writer -----------------------------------------------
    print("\n[E] the note survives upsert_method_health and a YAML round trip")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence_method_health.yml"
        changed, total, _ = upsert_method_health(health, path)
        check("E1 the writer stored both rows", changed == 2 and total == 2, f"{changed}/{total}")
        stored = load_method_health(path)
        check("E2 the stored notes equal the generated notes exactly",
              sorted(r["notes"] for r in stored) == sorted(notes), str([r["notes"] for r in stored]))
        check("E3 every telemetry field is readable from the stored note",
              all(k in note_fields(stored[0]["notes"]) for k in
                  ("max_fetches", "successful_fetches", "distinct_threads", "eligible_threads",
                   "thread_scope", "budget_exhausted", "threads_refused_budget", "coverage_bounded")),
              stored[0]["notes"])
        again, _t, _ = upsert_method_health(health, path)
        check("E4 re-writing the same rows changes nothing (idempotent)", again == 0, str(again))
        import validate_evidence_method_health as vh  # noqa: PLC0415
        errs: list[str] = []
        for i, hr in enumerate(stored, 1):
            vh._validate_counter_relationships(errs, row_index=i, row=hr)
        check("E5 the health validator still accepts the rows", not errs, str(errs))

    # ---- F: telemetry only; nothing else moved -------------------------------------------------
    print("\n[F] nothing but the note changed")
    defaults = orch.Pipeline.__init__.__kwdefaults__ or {}
    check("F1 the fetch budget default is still 200", defaults.get("context_max_fetches") == 200,
          str(defaults.get("context_max_fetches")))
    check("F2 statuses stay inside the existing vocabulary",
          {h["status"] for h in health} <= {"success", "partial", "blocked", "broken",
                                            "low_confidence"}, str({h["status"] for h in health}))
    check("F3 the blocked-reason field is untouched (context_fetch_blocked on a blocked thread)",
          all(h["blocked_reason"] == "context_fetch_blocked" for h in health[:1]),
          str([h["blocked_reason"] for h in health]))
    check("F4 per-patch counters and statuses are exactly what the unchanged stage produces",
          [(h["candidates_found"], h["status"], h["rejected_reports"]) for h in health]
          == [(3, "partial", 3), (2, "low_confidence", 2)],
          str([(h["candidates_found"], h["status"], h["rejected_reports"]) for h in health]))
    plan = st.method_plan.get("context_resolution") or {}
    check("F5 the run plan still reports the attempted fetches unchanged", plan.get("fetches") == 2,
          str(plan.get("fetches")))
    src = (_REPO / "auxsays" / "scripts" / "orchestrate_evidence_run.py").read_text(encoding="utf-8")
    check("F6 the notes field is built through the one helper",
          src.count("budget_telemetry_suffix(") == 2, str(src.count("budget_telemetry_suffix(")))
    check("F7 the pending-row order is still resolution_priority (discovery order untouched)",
          "pending.sort(key=lambda entry: resolution_priority(entry[1]))" in src)

    print()
    print("=" * 76)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 76)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
