#!/usr/bin/env python3
"""AUX-117 (G67): the PowerPoint Q&A tag lane's hydration cap is visible in the stored notes.

THE GAP. The tag lane hydrates at most 45 admitted questions a run (QNA_TAG_MAX_HYDRATIONS). When more
were admitted, the fact `hydration_cap_reached_45_of_N` went only into the run's in-memory error list:
the status stayed what it was and the notes said nothing, so a run that left admitted questions unread
was indistinguishable, in the committed health file, from one that read them all. A catch-up loss after
a missed run would be invisible. The cadence question this feeds (a once-a-day gate) is on HOLD until
there is telemetry to measure it with.

WHAT THIS SUITE PINS. Driving the REAL `run_qna_tag_method` with the transport stubbed (no network):
  T1  over the cap, the notes carry the admitted total and the overflow fact, with its count
  T2  under the cap, the notes carry the admitted total and no overflow fact
  T3  nothing but the notes moves: status, counters and blocked_reason equal a run with the new note
      suppressed (the pre-change notes), in every scenario, on the first record and on a cached one
  T4  the statuses are the pre-change ones, frozen literally (including the existing quirk that an
      accepted report beside the cap error reads `partial` on the record that ran the walk)
  T5  the cap and the walk are unchanged: 45 hydration requests exactly, the newest admitted first, the
      in-memory cap error still recorded, QNA_TAG_MAX_HYDRATIONS 45 and QNA_TAG_MAX_PAGES 8
  T6  the note survives the real writer and a YAML round trip

Deterministic and offline. Temp dirs only.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_hydration_cap_telemetry.py
"""
from __future__ import annotations

import socket
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

NET = [0]


class _NoNetSocket(socket.socket):
    def connect(self, *args, **kwargs):          # noqa: D102
        NET[0] += 1
        raise OSError("network refused by test_powerpoint_hydration_cap_telemetry")


def _no_dns(*args, **kwargs):
    NET[0] += 1
    raise OSError("DNS refused by test_powerpoint_hydration_cap_telemetry")


socket.socket = _NoNetSocket                     # type: ignore[misc]
socket.getaddrinfo = _no_dns                     # type: ignore[assignment]

from patch_collectors import microsoft_powerpoint as ppt                 # noqa: E402
from patch_collectors.base import (                                      # noqa: E402
    CollectorContext, PatchRecord, load_method_health, upsert_method_health,
)

SINCE = "2026-09-01"
CAPTURED = "2026-11-20T06:00:00Z"
CAP = 45

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def listing(admitted: int, noise: int = 7) -> list[dict]:
    """`admitted` symptom-titled questions inside the window, plus noise that must NOT be admitted:
    how-to titles in the window, and symptom titles from before it."""
    rows = []
    for i in range(admitted):
        day = 1 + (i % 28)
        rows.append({"question_id": str(10000 + i), "slug": f"q{i}", "title": f"PowerPoint crashes on save {i}",
                     "date": f"2026-10-{day:02d}", "asked": f"2026-10-{day:02d}"})
    for i in range(noise):
        rows.append({"question_id": str(90000 + i), "slug": f"h{i}", "title": f"How do I add speaker notes {i}",
                     "date": "2026-10-15", "asked": "2026-10-15"})
        rows.append({"question_id": str(95000 + i), "slug": f"o{i}", "title": f"PowerPoint crashes old {i}",
                     "date": "2026-08-01", "asked": "2026-08-01"})
    return rows


class Transport:
    """Stubs the tag source at its three entry points and counts every hydration request."""

    def __init__(self, admitted: int, accept_first: bool = False) -> None:
        self.rows = listing(admitted)
        self.accept_first = accept_first
        self.fetched: list[str] = []

    def __enter__(self):
        tags = ppt.qna_tags
        self.saved = (tags.enumerate_tag, tags.fetch, tags.question_candidate, ppt.evaluate_candidates)
        first_tag = ppt.qna_tags.POWERPOINT_TAGS[0][0]

        def enumerate_tag(tag_id, slug, *, since, max_pages, errors):
            # The whole listing lives under the first tag; the others are walked and empty.
            return ([dict(r) for r in self.rows] if tag_id == first_tag else []), 1

        def fetch(url):
            self.fetched.append(url)
            return "<html></html>"

        def question_candidate(question_id, slug, *, title, date, page_html, source_type, source_name,
                               parse_thread):
            return {"source_type": source_type, "source_name": source_name,
                    "source_url": f"https://learn.microsoft.com/en-us/answers/questions/{question_id}/{slug}",
                    "parent_title": title, "report_title": title, "report_text": title, "source_date": date,
                    "qna_question_id": question_id}

        real_eval = self.saved[3]

        def evaluate(record, target, candidates, captured_at, seen=None, run_accepted_urls=None):
            if self.accept_first and candidates:
                return [dict(candidates[0], counted=True)], [dict(c, exclusion_reason="missing_powerpoint_version")
                                                            for c in candidates[1:]]
            return real_eval(record, target, candidates, captured_at, seen, run_accepted_urls)
        tags.enumerate_tag, tags.fetch, tags.question_candidate = enumerate_tag, fetch, question_candidate
        ppt.evaluate_candidates = evaluate
        ppt.reset_symptom_cache()
        return self

    def __exit__(self, *exc):
        tags = ppt.qna_tags
        tags.enumerate_tag, tags.fetch, tags.question_candidate, ppt.evaluate_candidates = self.saved
        ppt.reset_symptom_cache()
        return False


def rec(build: str) -> tuple[PatchRecord, dict]:
    record = PatchRecord(product_id="microsoft-powerpoint", update_version="2610", path=Path("x.md"),
                         update_published_at="2026-10-14T00:00:00Z", update_status="current",
                         update_product="PowerPoint", target_build=build)
    return record, {"update_version": "2610", "target_build": build}


def run_two_records(admitted: int, *, accept_first: bool = False, suppress_note: bool = False):
    """Two records of one run: the first runs the walk, the second is served from the run cache."""
    ctx = CollectorContext(write=False, since=SINCE, max_pages=1, target_versions=None)
    saved_note = ppt.qna_tag_hydration_note
    if suppress_note:
        ppt.qna_tag_hydration_note = lambda enumerated, since: ""
    try:
        with Transport(admitted, accept_first=accept_first) as transport:
            rows = []
            for build in ("19328.20000", "19328.20100"):
                record, target = rec(build)
                _a, _r, row = ppt.run_qna_tag_method(record, target, ctx, set(), {}, CAPTURED)
                rows.append(row)
    finally:
        ppt.qna_tag_hydration_note = saved_note
    return rows, transport


def comparable(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "notes"}


def run() -> int:
    net0 = NET[0]
    print("T1/T2  the notes carry the admitted total, and the overflow fact when the cap cut the list short")
    over, t_over = run_two_records(60)
    under, t_under = run_two_records(30)
    exact, _t = run_two_records(CAP)
    token = f"hydration_cap_reached_{CAP}_of_60"
    check("T1.1 over the cap: the admitted total is in the notes",
          all(f"Admitted for hydration 60 (cap {CAP} a run)." in r["notes"] for r in over), over[0]["notes"][:300])
    check("T1.2 over the cap: the overflow token and the unread count are in the notes",
          all(f"{token}: 15 admitted questions were not hydrated this run." in r["notes"] for r in over))
    check("T1.3 the cached record of the same run carries the same product-level fact",
          over[0]["notes"] == over[1]["notes"] and over[0]["target_build"] != over[1]["target_build"])
    check("T2.1 under the cap: the admitted total, and no overflow fact",
          all("Admitted for hydration 30 (cap 45 a run)." in r["notes"] and "hydration_cap_reached" not in r["notes"]
              for r in under))
    check("T2.2 exactly at the cap is not an overflow",
          all("Admitted for hydration 45 (cap 45 a run)." in r["notes"] and "hydration_cap_reached" not in r["notes"]
              for r in exact))
    check("T2.3 noise is not admitted: how-to titles and out-of-window questions are not counted",
          len(ppt.qna_tag_admitted(listing(60), SINCE)) == 60)

    print("T3  nothing but the notes moves")
    for label, admitted, accept in (("over", 60, False), ("under", 30, False), ("over+accepted", 60, True)):
        new, _ = run_two_records(admitted, accept_first=accept)
        old, _ = run_two_records(admitted, accept_first=accept, suppress_note=True)
        same = all(comparable(a) == comparable(b) for a, b in zip(new, old))
        note = ppt.qna_tag_hydration_note(listing(admitted), SINCE)
        inserted = bool(note) and all(
            a["notes"] == b["notes"].replace(f"rejected {b['rejected_reports']}. ",
                                             f"rejected {b['rejected_reports']}. {note}", 1)
            and a["notes"] != b["notes"] for a, b in zip(new, old))
        check(f"T3 {label}: status, counters and blocked_reason equal the pre-change run; the note is inserted",
              same and inserted, f"{[r['status'] for r in new]} vs {[r['status'] for r in old]}")

    print("T4  the statuses are the pre-change ones, frozen")
    acc, _ = run_two_records(60, accept_first=True)
    check("T4.1 over the cap, all rejected: no_results on both records", [r["status"] for r in over]
          == ["no_results", "no_results"], str([r["status"] for r in over]))
    check("T4.2 under the cap, all rejected: no_results on both records", [r["status"] for r in under]
          == ["no_results", "no_results"], str([r["status"] for r in under]))
    check("T4.3 an accepted report beside the in-memory cap error: partial on the walking record, success on "
          "the cached one (unchanged quirk)", [r["status"] for r in acc] == ["partial", "success"],
          str([r["status"] for r in acc]))
    check("T4.4 the overflow never becomes a blocked_reason", all(not r["blocked_reason"] for r in over + acc))

    print("T5  the cap and the walk are unchanged")
    check("T5.1 the constants: 45 hydrations a run, 8 pages a tag",
          ppt.QNA_TAG_MAX_HYDRATIONS == CAP and ppt.QNA_TAG_MAX_PAGES == 8)
    check("T5.2 over the cap, exactly 45 hydration requests were made for the whole run",
          len(t_over.fetched) == CAP, str(len(t_over.fetched)))
    admitted_rows = ppt.qna_tag_admitted(listing(60), SINCE)
    newest = [ppt.qna_tags.question_url(r["question_id"], r["slug"]) for r in admitted_rows[:CAP]]
    check("T5.3 ...and they are the 45 newest admitted questions, in order, from the list the note counts",
          t_over.fetched == newest and all(admitted_rows[i]["date"] >= admitted_rows[i + 1]["date"]
                                           for i in range(len(admitted_rows) - 1)),
          str(t_over.fetched[:2]))
    check("T5.4 under the cap, every admitted question was hydrated (30)", len(t_under.fetched) == 30)
    errors: list[dict] = []
    real_status = ppt.qna_tag_method_status

    def spy(candidates, accepted, rejected, errs, *, enumerated):
        errors.extend(errs)
        return real_status(candidates, accepted, rejected, errs, enumerated=enumerated)
    with Transport(60):
        ppt.qna_tag_method_status = spy
        try:
            record, target = rec("19328.20000")
            ppt.run_qna_tag_method(record, target,
                                   CollectorContext(write=False, since=SINCE, max_pages=1, target_versions=None),
                                   set(), {}, CAPTURED)
        finally:
            ppt.qna_tag_method_status = real_status
    check("T5.5 the in-memory cap error is still recorded and still reaches the status function",
          any(e.get("reason") == token for e in errors), str(errors[:3]))

    print("T6  the note survives the real writer")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "emh.yml"
        upsert_method_health(over, path)
        stored = load_method_health(path)
    check("T6.1 both rows are stored with the admitted total and the overflow fact",
          len(stored) == 2 and all(token in r["notes"] and "Admitted for hydration 60" in r["notes"] for r in stored))
    check("T6.2 no network was attempted by any of the above", NET[0] == net0, str(NET[0] - net0))

    print()
    print("=" * 96)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 96)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
