#!/usr/bin/env python3
"""Windows Learn Q&A opening-post hydration (L1 + B3 §12, AUX-073): default off, enrichment only.

A Windows patch the shipped certifier refuses ONLY for being short of reports, inside a 90-day window,
may have the Learn Q&A questions THIS RUN's search rejected on their excerpt re-judged from the full
opening post. This suite pins that it changes nothing while disabled, that it can never make the
search method's health lie, and that every hydrated report still goes through the unchanged authority.

HERMETIC. Collector-level sections run in a SANDBOX: a temporary copy of auxsays/scripts (tests
excluded) beside a fixture site (eight Windows records, a fixture evidence store, an empty health
store), driven in a subprocess with sockets refused and every transport stubbed. Nothing reads or
writes the live `_data`, a live record, or the network; no count of the live corpus is pinned.

    A  default off           zero sockets, byte-identical output for every disabled flag spelling,
                             the pass and the extra store read never run
    B  scope and dedup       only the two excerpt-explainable reasons; never live, outside the window,
                             claimed, stored in any state, or Tech Community; a shared URL fetched once
    C  segment and date      opening post only (never an answer or a comment), the RSS title kept, the
                             page's own date with no fallback, identity of the page enforced
    D  attribution           newest-first sibling wins, the other gets cross_patch_duplicate; discovery
                             URL kept; same family; one URL one row
    E  isolation (E2)        seven failure kinds leave status, counters and Tech Community identical to
                             flag-off apart from notes; accepted+failed is success; 840-case property
    F  live fixtures         7462 / 7623 / 7840 still certify through the shipped evaluate
    G  budgets               45/run, 30/identity, pace, 429 circuit, 5-failure circuit, headroom and
                             deadline skips, the D3 reserve end to end
    H  write path            ownership, ALLOWED_* unchanged, append-only, finalize counters validate,
                             vocabulary that reconciliation and the Windows writer both count
    I  seam                  rss_out never passed while off; the RSS lane's own lists; the SAME errors
                             object; the RSS row found by method_id
    J  R1 flags              dry run only; rollback role; sibling-revision filter; write emits none
    K  registry              the two Windows failure_modes clauses
    T  telemetry (D2)        structured block, run event, notes say optional/separately budgeted and
                             never claim complete inspection, run warning, an aborted pass changes nothing
    W  workflow              the dispatch input is boolean, default false; the flag is exported only for
                             a dry-run dispatch that asked for it (the run: scalar is EXECUTED)

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_windows_underfill_hydration.py
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

from lib import collector_ownership as co  # noqa: E402
from lib import acquisition_methods as am  # noqa: E402
from lib.evidence_classification import VALID_SENTIMENTS, VALID_SEVERITIES  # noqa: E402
from patch_collectors import microsoft_qna_tags_source as qna_tags  # noqa: E402
from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors.base import EVIDENCE_FIELDS, PatchRecord  # noqa: E402
import lib.write_update_record as wur  # noqa: E402

NEWLINE = chr(10)
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
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


# =====================================================================================================
# fixtures
# =====================================================================================================
NOW = "2026-11-05T02:54:57Z"
CAPTURED = "2026-11-05T01:00:00Z"
Q = "https://learn.microsoft.com/en-us/answers/questions"
WIN = mw.PRODUCT_ID

# name -> (version, build, kb, published, stored counted rows)
IDS: dict[str, tuple[str, str, str, str, int]] = {
    "L7462": ("25H2", "26200.7462", "KB5072033", "2026-01-08T00:00:00Z", 35),
    "L7623": ("25H2", "26200.7623", "KB5074109", "2026-02-12T00:00:00Z", 35),
    "L7840": ("25H2", "26200.7840", "KB5077181", "2026-03-12T00:00:00Z", 35),
    "U9457": ("25H2", "26200.9457", "KB5124001", "2026-09-14T00:00:00Z", 27),
    "N9711": ("26H2", "26300.9711", "KB5127648", "2026-10-13T00:00:00Z", 20),
    "S9711": ("25H2", "26200.9711", "KB5127648", "2026-10-13T00:00:00Z", 9),
    "C9818": ("26H2", "26300.9818", "KB5130001", "2026-10-28T00:00:00Z", 13),
    "OLD": ("24H2", "26100.8737", "KB5095093", "2026-06-23T00:00:00Z", 10),
}
LIVE = ("L7462", "L7623", "L7840")


def feature(name: str) -> str:
    return IDS[name][0]


def target(name: str) -> dict:
    version, build, kb, published, _n = IDS[name]
    return {"target_feature_version": version, "target_kb": kb, "target_os_build": build,
            "target_release_date": published, "update_version": version}


def patch_record(name: str, path: Path | None = None) -> PatchRecord:
    version, build, _kb, published, _n = IDS[name]
    return PatchRecord(WIN, version, path or Path(f"/nonexistent/{name}.md"), published, "current",
                       "Windows 11", build)


def key(name: str) -> tuple[str, str, str]:
    return (WIN, IDS[name][0], IDS[name][1])


def url(qid: int, slug: str = "fixture") -> str:
    return f"{Q}/{qid}/{slug}"


def day(published: str, plus: int) -> str:
    return (datetime.fromisoformat(published.replace("Z", "+00:00")) + timedelta(days=plus)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def page_html(qid: int, title: str, body: str, *, date: str | None = "2026-10-20T09:00:00Z",
              answers: tuple[str, ...] = (), comments: tuple[str, ...] = (), ld_id: str | None = None,
              machine: bool = False, main_type: str = "Question", ld: bool = True,
              broken_answers: bool = False) -> str:
    question = {"@type": main_type, "id": ld_id if ld_id is not None else str(qid), "name": title,
                "text": f"<p>{body}</p>",
                "author": "AI answer" if machine else "Reporter",
                "authorId": "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1" if machine else "11111111-2222-3333-4444-555555555555",
                "suggestedAnswer": 5 if broken_answers else [
                    {"@type": "Answer", "id": str(900 + i), "text": f"<p>{a}</p>", "author": "Helper",
                     "authorId": "99999999-8888-7777-6666-555555555555"} for i, a in enumerate(answers)]}
    block = json.dumps({"@context": "https://schema.org", "@type": "QAPage", "mainEntity": question})
    head = f'<script type="application/ld+json">{block}</script>' if ld else ""
    stamp = f'<local-time datetime="{date}">asked</local-time>' if date else ""
    notes = "".join(
        f'<ul><li data-test-id="comment-{7000 + i}"><a href="/en-us/users/na/?userid=99999999-8888-7777-'
        f'6666-555555555555">x</a> {c} <local-time datetime="2026-10-30T10:00:00Z"></local-time></li></ul>'
        for i, c in enumerate(comments))
    return f"<html><head>{head}</head><body><h1>{title}</h1>{stamp}{notes}</body></html>"


def rss(qid: int, title: str, desc: str, *, date: str = "2026-11-01T10:00:00Z") -> dict:
    return {"source_url": url(qid), "parent_title": title, "report_title": title,
            "report_text": f"{title} {desc}", "source_date": date}


def accepting_post(name: str) -> str:
    version, build, _kb, _p, _n = IDS[name]
    return (f"I am on Windows 11 {version} build {build}. After installing the update the printer "
            "stopped working and nothing prints.")


ELIGIBLE_TITLE = "Printer stopped working after the update"
ELIGIBLE_DESC = "Since yesterday nothing prints at all."


def stored_rows() -> list[dict]:
    """Counted rows built by the SHIPPED authority (so they pass the Windows identity gate exactly as
    production rows do), one unique URL each, plus one audited withdrawal."""
    rows: list[dict] = []
    for index, (name, (version, build, kb, published, n)) in enumerate(IDS.items()):
        for i in range(n):
            qid = 6_000_000 + index * 1000 + i
            if name == "N9711" and i == 0:
                qid = 7_200_001                          # X: counted on N9711, rediscovered elsewhere
            cand = {"source_url": url(qid, "stored"), "source_type": mw.SOURCE_TYPE,
                    "source_name": mw.SOURCE_NAME, "parent_title": f"Printer broke after {kb}",
                    "report_title": f"Printer broke after {kb} on {build}",
                    "report_text": f"After installing {kb} the printer stopped working on {build}.",
                    "source_date": day(published, 2)}
            row = mw.row_from_candidate(patch_record(name), target(name), cand, "2026-10-01T00:00:00Z")
            assert row["counted"] is True, (name, row["exclusion_reason"])
            rows.append(row)
    withdrawn = dict(next(r for r in rows if r["target_build"] == IDS["S9711"][1]))
    withdrawn.update({"id": "microsoft-windows-11-25h2-withdrawn-7100001", "source_url": url(7_100_001, "stored"),
                      "counted": False, "exclusion_reason": "foreign_product_subject_not_windows_patch",
                      "evidence_valid_for_current_patch": False})
    rows.append(withdrawn)
    return rows


HELD_U9457 = url(6_000_000 + 3 * 1000 + 0, "stored")   # U9457's own first counted row


def discovery() -> tuple[dict, list, dict]:
    """(search term -> RSS candidates, Tech Community pool candidates, url -> page behaviour)."""
    terms: dict[str, list[dict]] = {}
    pages: dict[str, dict] = {}

    def add(term: str, cand: dict, behaviour: dict | None = None) -> None:
        terms.setdefault(term, []).append(cand)
        if behaviour is not None:
            pages[cand["source_url"]] = behaviour

    u = IDS["U9457"]
    for i in range(1, 5):
        add(u[2], rss(8_001_000 + i, ELIGIBLE_TITLE, ELIGIBLE_DESC),
            {"html": page_html(8_001_000 + i, ELIGIBLE_TITLE, accepting_post("U9457"), date=day(u[3], 3))})
    add(u[2], rss(8_001_005, "Explorer crashes", f"Running {u[1]}, File Explorer crashes when I open a folder."),
        {"html": page_html(8_001_005, "Explorer crashes",
                           f"Running {u[1]}, File Explorer crashes when I open a folder. It started right "
                           "after installing the update.", date=day(u[3], 4))})
    add(u[2], rss(8_001_006, ELIGIBLE_TITLE, ELIGIBLE_DESC),
        {"html": page_html(8_001_006, ELIGIBLE_TITLE, "My printer stopped after the update. Any ideas?",
                           answers=(f"I am on {u[1]} and after installing the update mine broke too.",),
                           date=day(u[3], 3))})
    add(u[2], rss(8_001_007, ELIGIBLE_TITLE, ELIGIBLE_DESC),
        {"html": page_html(8_001_007, ELIGIBLE_TITLE, "My printer stopped after the update. Any ideas?",
                           comments=(f"Same here on {u[1]} after installing the update.",), date=day(u[3], 3))})
    add(u[2], rss(8_001_008, ELIGIBLE_TITLE, ELIGIBLE_DESC),
        {"html": page_html(8_001_008, ELIGIBLE_TITLE, accepting_post("U9457"), date=None)})
    add(u[2], rss(8_001_009, ELIGIBLE_TITLE, ELIGIBLE_DESC),
        {"html": page_html(8_001_009, ELIGIBLE_TITLE, accepting_post("U9457"), ld_id="1234567")})
    add(u[2], rss(8_001_101, "How do I change the wallpaper", "Where is the personalisation setting?"),
        {"html": page_html(8_001_101, "x", accepting_post("U9457"))})
    add(u[2], rss(8_001_102, "Printer broken after KB5999999", "Nothing prints since that update."),
        {"html": page_html(8_001_102, "x", accepting_post("U9457"))})
    add(u[2], rss(8_001_201, f"Printer broke after installing {u[2]} on {u[1]}",
                  "After installing the update the printer stopped working."))
    add(u[2], {**rss(0, ELIGIBLE_TITLE, ELIGIBLE_DESC), "source_url": HELD_U9457})
    add(u[2], {**rss(0, ELIGIBLE_TITLE, ELIGIBLE_DESC), "source_url": url(7_200_001, "stored")})

    n, s = IDS["N9711"], IDS["S9711"]
    add(n[2], rss(8_002_001, ELIGIBLE_TITLE, ELIGIBLE_DESC),
        {"html": page_html(8_002_001, ELIGIBLE_TITLE,
                           f"Same problem on two PCs, {n[1]} and {s[1]}. After installing the update the "
                           "printer stopped working.", date=day(n[3], 2)),
         "final_url": url(8_002_001, "renamed-slug")})
    add(n[2], rss(8_002_002, ELIGIBLE_TITLE, ELIGIBLE_DESC),
        {"html": page_html(8_002_002, ELIGIBLE_TITLE, accepting_post("N9711"), date=day(n[3], 2))})
    add(n[2], {**rss(0, ELIGIBLE_TITLE, ELIGIBLE_DESC), "source_url": url(7_100_001, "stored")})
    add(n[2], {**rss(0, ELIGIBLE_TITLE, ELIGIBLE_DESC), "source_url": url(7_200_001, "stored")})

    c = IDS["C9818"]
    add(c[2], rss(8_003_001, ELIGIBLE_TITLE, ELIGIBLE_DESC),
        {"html": page_html(8_003_001, ELIGIBLE_TITLE, accepting_post("C9818"), date=day(c[3], 1))})
    for i in range(2, 6):
        add(c[2], rss(8_003_000 + i, ELIGIBLE_TITLE, ELIGIBLE_DESC), {"http": 503})

    o = IDS["OLD"]
    for i in range(1, 3):
        add(o[2], rss(8_004_000 + i, ELIGIBLE_TITLE, ELIGIBLE_DESC),
            {"html": page_html(8_004_000 + i, ELIGIBLE_TITLE, accepting_post("OLD"), date=day(o[3], 2))})
    for index, name in enumerate(LIVE):
        live = IDS[name]
        for i in range(1, 3):
            qid = 8_005_000 + index * 10 + i
            add(live[2], rss(qid, ELIGIBLE_TITLE, ELIGIBLE_DESC),
                {"html": page_html(qid, ELIGIBLE_TITLE, accepting_post(name), date=day(live[3], 2))})
    tc = [{"source_type": mw.TECHCOMMUNITY_SOURCE_TYPE, "source_name": mw.TECHCOMMUNITY_SOURCE_NAME,
           "source_url": "https://techcommunity.microsoft.com/discussions/windows11/printer-stopped/4600001",
           "parent_title": ELIGIBLE_TITLE, "report_title": ELIGIBLE_TITLE,
           "report_text": f"{ELIGIBLE_TITLE} {ELIGIBLE_DESC}", "source_date": "2026-10-30"}]
    return terms, tc, pages


GENERIC_PAGE = page_html(0, ELIGIBLE_TITLE, "Nothing prints since the update.", date="2026-10-29T09:00:00Z",
                         ld_id="{qid}").replace('"0"', '"{qid}"')


def bulk_rss(counts: dict[str, int]) -> dict:
    terms: dict[str, list[dict]] = {}
    for index, (name, count) in enumerate(counts.items()):
        for i in range(count):
            terms.setdefault(IDS[name][2], []).append(rss(8_100_000 + index * 1000 + i, ELIGIBLE_TITLE,
                                                          ELIGIBLE_DESC))
    return terms


# =====================================================================================================
# the sandbox
# =====================================================================================================
DRIVER = r'''
import contextlib, io, json, os, socket, sys, urllib.error, urllib.request
from datetime import datetime
from pathlib import Path

SANDBOX = Path(__file__).resolve().parent
sys.path.insert(0, str(SANDBOX / "auxsays" / "scripts"))
SOCKETS = {"n": 0}


def _refuse(*a, **k):
    SOCKETS["n"] += 1
    raise OSError("network refused by the underfill test driver")


socket.socket.connect = _refuse
socket.create_connection = _refuse

from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors import microsoft_qna_tags_source as qna_tags  # noqa: E402
from patch_collectors import runtime_budget as rb  # noqa: E402
from patch_collectors.base import (CollectorContext, EVIDENCE_PATH, GENERATED_DIR,  # noqa: E402
                                   METHOD_HEALTH_PATH, load_front_matter_and_body, upsert_method_health)
from lib import collector_ownership as co  # noqa: E402
from lib import live_eligibility as le  # noqa: E402
from lib import monitoring_health as mh  # noqa: E402
from lib.patch_identity import key_from  # noqa: E402
from lib.report_counts import (counted_evidence_rows, load_evidence_store,  # noqa: E402
                               windows_targets_from_front_matter)
import validate_evidence_method_health as vemh  # noqa: E402

spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(spec["now"].replace("Z", "+00:00"))
CLOCK = {"t": 1000.0}
STATE = {}


class FakeResp:
    def __init__(self, final, body, behaviour):
        self.final, self.body, self.behaviour, self.pos = final, body, behaviour, 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def geturl(self):
        return self.final

    def read1(self, n=-1):
        n = len(self.body) - self.pos if n is None or n < 0 else n
        chunk = self.body[self.pos:self.pos + n]
        self.pos += len(chunk)
        return chunk

    def read(self, n=-1):
        return self.read1(n)

    def close(self):
        pass


def fake_urlopen(request, timeout=None):
    target = getattr(request, "full_url", request)
    STATE["urlopen"].append(target)
    CLOCK["t"] += STATE["advance"]
    b = STATE["pages"].get(target) or STATE["default"] or {"http": 404}
    if "http" in b:
        raise urllib.error.HTTPError(target, int(b["http"]), "fixture", {}, None)
    if b.get("urlerror"):
        raise urllib.error.URLError("fixture: unreachable")
    if b.get("timeout"):
        raise socket.timeout("fixture: timed out")
    html = b.get("html") or ""
    if b.get("generic"):
        html = spec["generic_page"].replace("{qid}", target.rstrip("/").split("/")[-2])
    return FakeResp(b.get("final_url") or target, html.encode("utf-8"), b)


urllib.request.urlopen = fake_urlopen
_real_bounded_read = rb.bounded_read


def fake_bounded_read(resp, *, budget=None, endpoint_family="", max_bytes=None):
    b = getattr(resp, "behaviour", {}) or {}
    if b.get("deadline"):
        raise rb.RequestDeadlineExceeded(endpoint_family, 30.0)
    if b.get("budget"):
        raise rb.BudgetError("network_ConnectionResetError", reason="network", health="broken")
    return _real_bounded_read(resp, budget=budget, endpoint_family=endpoint_family, max_bytes=max_bytes)


rb.bounded_read = fake_bounded_read


def fake_pace():
    STATE["pace"] += 1


qna_tags._pace = fake_pace


def fake_rss(*, queries, context, errors, source_type, source_name):
    out, seen = [], set()
    for q in queries:
        if q in STATE["rss_errors"]:
            errors.append({"query": q, "source_url": "https://learn.microsoft.com/api/search/rss?search=" + q,
                           "reason": "learn_qna_search_fetch_failed:" + STATE["rss_errors"][q],
                           "blocked_signature": "network"})
            continue
        for c in STATE["rss"].get(q, []):
            if c["source_url"].lower() in seen:
                continue
            seen.add(c["source_url"].lower())
            out.append({**c, "source_type": source_type, "source_name": source_name, "matched_query": q})
    return out


mw.learn_qna.collect_learn_qna_candidates = fake_rss
_tc = spec.get("tc") or []
mw.build_techcommunity_pool = lambda context: mw.TechCommunityPool(
    candidates=[dict(c) for c in _tc],
    telemetry={"listed": len(_tc), "unique_slugs": len(_tc), "hydrated": len(_tc), "attempted": len(_tc),
               "sitemap_errors": 0, "hydration_errors": 0, "truncated": False}, errors=[])
mw.utc_now = lambda: spec["captured_at"]
mw._underfill_now = lambda: NOW
REAL = {"cfr": mw.collect_for_record, "hfm": mw.health_for_method, "evaluate": le.evaluate,
        "pass": mw._underfill_pass, "cas": mw.claims_and_stored_urls}


def evaluate_keys(results, names):
    fronts = [load_front_matter_and_body(p)[0] for p in sorted(GENERATED_DIR.glob("*.md"))]
    groups = counted_evidence_rows(load_evidence_store(EVIDENCE_PATH),
                                   windows_targets=windows_targets_from_front_matter(fronts))
    rows = [h for r in results for h in r.get("method_health") or []]
    th = mh.load_thresholds(SANDBOX / "auxsays" / "_config.yml")
    out = {}
    for front in fronts:
        k = "|".join(key_from(front))
        if k in names:
            d = REAL["evaluate"](front, groups, emh_rows=rows, now=NOW, thresholds=th)
            out[k] = {"live": d.live, "reasons": list(d.reasons)}
    return out


def one_run(run):
    STATE.update(urlopen=[], pace=0, pages=run.get("pages") or spec.get("pages") or {},
                 default=run.get("default_page"), advance=float(run.get("advance_per_get") or 0),
                 rss_errors=run.get("rss_errors") or {}, rss=run.get("rss") or spec["rss"])
    SOCKETS["n"] = 0
    flag = run.get("flag")
    if flag is None:
        os.environ.pop(mw.UNDERFILL_ENABLE_ENV, None)
    else:
        os.environ[mw.UNDERFILL_ENABLE_ENV] = flag
    budget = None
    if run.get("budget") is not None:
        b = run["budget"]
        cfg = rb.BudgetConfig(collector_deadline=float(b) + 30.0, collector_finalize_reserve=30.0,
                              run_collection_deadline=100000.0, method_deadline=180.0,
                              max_requests_per_method=60)
        budget = rb.RuntimeBudget(cfg, clock=lambda: CLOCK["t"])
        budget.start_collector(mw.PRODUCT_ID)
    rb.set_run_budget(budget)
    events = []
    real_emit = rb.emit

    def capture(event, *, url=None, **fields):
        row = {"event": event}
        if url is not None:
            row["url"] = url
        row.update({k: v for k, v in fields.items() if isinstance(v, (str, int, float, bool)) or v is None})
        events.append(row)

    rb.emit = capture
    probe = {"calls": [], "rss": {}, "pass_called": 0, "cas_called": 0}

    def spy_pass(*a, **k):
        probe["pass_called"] += 1
        return REAL["pass"](*a, **k)

    def spy_cas():
        probe["cas_called"] += 1
        return REAL["cas"]()

    mw._underfill_pass, mw.claims_and_stored_urls = spy_pass, spy_cas
    mode = run.get("probe") or ""
    if mode == "strict_stub":
        def strict(record, context, claims=None, pool=None):
            return REAL["cfr"](record, context, claims, pool)
        mw.collect_for_record = strict
    elif mode == "reverse_health":
        def reverse(*a, **k):
            acc, rej, health = REAL["cfr"](*a, **k)
            health.reverse()
            return acc, rej, health
        mw.collect_for_record = reverse
    elif mode == "capture_rebuild":
        def cap_cfr(*a, **k):
            out = REAL["cfr"](*a, **k)
            if "rss_out" in k:
                probe["rss"][a[0].target_build] = [id(k["rss_out"]["errors"]), len(k["rss_out"]["errors"])]
            return out

        def cap_hfm(record, target, captured_at, candidates, accepted, rejected, errors, query_terms):
            probe["calls"].append([record.target_build, id(errors), len(errors)])
            return REAL["hfm"](record, target, captured_at, candidates, accepted, rejected, errors, query_terms)
        mw.collect_for_record, mw.health_for_method = cap_cfr, cap_hfm
    elif mode == "abort":
        def boom(*a, **k):
            raise RuntimeError("fixture abort")
        le.evaluate = boom
    before = EVIDENCE_PATH.read_text(encoding="utf-8")
    stdout = io.StringIO()
    error = None
    results = []
    try:
        with contextlib.redirect_stdout(stdout):
            results = mw.WindowsLearnQnaCollector().collect(CollectorContext(
                write=bool(run.get("write")), since=None, max_pages=1, target_versions=None, budget=budget))
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    finally:
        rb.emit = real_emit
        rb.set_run_budget(None)
        mw.collect_for_record, mw.health_for_method = REAL["cfr"], REAL["hfm"]
        mw._underfill_pass, mw.claims_and_stored_urls = REAL["pass"], REAL["cas"]
        le.evaluate = REAL["evaluate"]
    out = {"name": run["name"], "results": results, "error": error, "sockets": SOCKETS["n"],
           "urlopen": list(STATE["urlopen"]), "pace": STATE["pace"], "events": events,
           "stdout": stdout.getvalue(), "probe": probe}
    if run.get("evaluate"):
        out["evaluate"] = evaluate_keys(results, set(run["evaluate"]))
    if run.get("write"):
        after = EVIDENCE_PATH.read_text(encoding="utf-8")
        rows = [h for r in results for h in r.get("method_health") or []]
        checks = {}
        for name, fn in (("method_health", lambda: co.validate_method_health(mw.PRODUCT_ID, rows)),
                         ("evidence", lambda: co.validate_evidence(mw.PRODUCT_ID, before, after))):
            try:
                fn()
                checks[name] = "ok"
            except Exception as exc:  # noqa: BLE001
                checks[name] = f"{type(exc).__name__}: {getattr(exc, 'code', exc)}"
        upsert_method_health(rows)
        with contextlib.redirect_stdout(io.StringIO()):
            checks["emh_validate_rc"] = vemh.validate(METHOD_HEALTH_PATH)
        checks["prefix"] = after.startswith(before.rstrip("\n"))
        out["validations"] = checks
        out["evidence_after"] = after
        out["evidence_before"] = before
    return out


outputs = [one_run(run) for run in spec["runs"]]
Path(sys.argv[2]).write_text(json.dumps(outputs, default=str), encoding="utf-8")
'''


def record_text(name: str) -> str:
    version, build, kb, published, _n = IDS[name]
    return wur._dump_record(wur.build_front_matter({
        "company_id": "microsoft", "product_id": WIN, "company": "Microsoft", "software": "Windows 11",
        "version": version, "published_at": published,
        "source_url": "https://learn.microsoft.com/en-us/windows/release-health/",
        "body": f"Windows 11 {version}.", "official_summary": f"Windows 11 {version}.",
        "target_feature_version": version, "target_kb": kb, "target_os_build": build, "target_build": build,
        "target_release_date": published,
    }))


def build_sandbox(root: Path) -> Path:
    aux = root / "auxsays"
    shutil.copytree(_SCRIPTS, aux / "scripts",
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    (aux / "_data").mkdir(parents=True)
    gen = aux / "updates" / "generated"
    gen.mkdir(parents=True)
    (aux / "_config.yml").write_text("monitoring_min_healthy_methods: 2\nmonitoring_max_age_days: 14\n",
                                     encoding="utf-8")
    for name, (version, build, _kb, published, _n) in IDS.items():
        (gen / f"{published[:10]}-windows-11-{version.lower()}-{build.replace('.', '-')}.md").write_text(
            record_text(name), encoding="utf-8")
    (aux / "_data" / "consensus_evidence.yml").write_text(
        yaml.safe_dump({"schema_version": 1, "evidence": stored_rows()}, sort_keys=False,
                       allow_unicode=True, width=1000), encoding="utf-8")
    (aux / "_data" / "evidence_method_health.yml").write_text(
        yaml.safe_dump({"schema_version": 1, "methods": []}), encoding="utf-8")
    (root / "driver.py").write_text(DRIVER, encoding="utf-8")
    return root


def drive(sandbox: Path, runs: list[dict], **spec_extra) -> dict[str, dict]:
    terms, tc, pages = discovery()
    spec = {"now": NOW, "captured_at": CAPTURED, "rss": terms, "tc": tc, "pages": pages,
            "generic_page": GENERIC_PAGE, "runs": runs, **spec_extra}
    spec_path, out_path = sandbox / "spec.json", sandbox / "out.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != mw.UNDERFILL_ENABLE_ENV}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, str(sandbox / "driver.py"), str(spec_path), str(out_path)],
                          cwd=str(sandbox), capture_output=True, text=True, env=env, timeout=900)
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"driver failed rc={proc.returncode}: {proc.stderr[-3000:]}")
    return {o["name"]: o for o in json.loads(out_path.read_text(encoding="utf-8"))}


def by_build(out: dict) -> dict[str, dict]:
    return {r["method_health"][0]["target_build"]: r for r in out["results"] if r.get("method_health")}


def health_of(result: dict, method: str = mw.METHOD_ID) -> dict:
    rows = [h for h in result["method_health"] if h["method_id"] == method]
    return rows[0] if len(rows) == 1 else {}


def strip_underfill(results: list[dict], queued_builds: set[str]) -> list[dict]:
    """Results with the hydration-only differences removed: the result block, and the notes of the RSS
    row of a queued patch. Everything else must be byte-identical to the flag-off run."""
    out = []
    for r in results:
        r = {k: v for k, v in r.items() if k != "underfill_hydration"}
        rows = []
        for h in r["method_health"]:
            h = dict(h)
            if h["method_id"] == mw.METHOD_ID and h["target_build"] in queued_builds:
                h.pop("notes", None)
            rows.append(h)
        r["method_health"] = rows
        out.append(r)
    return out


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


# =====================================================================================================
# sections
# =====================================================================================================
def section_pure() -> None:
    print(NEWLINE + "[C] segment and date: the opening post, judged by the unchanged authority")
    u = IDS["U9457"]
    rec, tgt = patch_record("U9457"), target("U9457")
    rss_cand = rss(8_009_001, ELIGIBLE_TITLE, ELIGIBLE_DESC)

    def judge(html: str, *, title: str = ELIGIBLE_TITLE, final: str | None = None, qid: int = 8_009_001):
        cand_in = {**rss_cand, "source_url": url(qid), "parent_title": title, "report_title": title}
        cand, refusal = mw._hydrated_candidate(url(qid), cand_in, final or url(qid), html)
        if cand is None:
            return None, refusal
        acc, rej = mw.evaluate_candidates(rec, tgt, [cand], CAPTURED, {})
        return (acc + rej)[0], ""

    row, _ = judge(page_html(8_009_001, "page title", accepting_post("U9457"), date=day(u[3], 3)))
    check("C1 build only in the OPENING POST: the authority accepts it (exact_os_build)",
          bool(row) and row["counted"] is True and row["match_basis"] == "exact_os_build", str(row and row["exclusion_reason"]))
    row, _ = judge(page_html(8_009_001, "t", "My printer stopped after the update.",
                             answers=(f"I am on {u[1]}; after installing the update mine broke too.",),
                             date=day(u[3], 3)))
    check("C2 build only in an ANSWER: never read, still rejected", bool(row) and row["counted"] is False
          and row["exclusion_reason"] == "missing_kb_or_build", str(row and row["exclusion_reason"]))
    row, _ = judge(page_html(8_009_001, "t", "My printer stopped after the update.",
                             comments=(f"Same on {u[1]} after installing the update.",), date=day(u[3], 3)))
    check("C3 build only in a COMMENT: never read, still rejected", bool(row) and row["counted"] is False
          and row["exclusion_reason"] == "missing_kb_or_build", str(row and row["exclusion_reason"]))
    row, _ = judge(page_html(8_009_001, "t", f"Printer does not print. Edition: Windows 11 Pro, OS build: {u[1]}",
                             date=day(u[3], 3)), title="Printer does not print")
    check("C4 build only in system specs: build_only_in_system_specs, as on any other row",
          bool(row) and row["exclusion_reason"] == "build_only_in_system_specs", str(row and row["exclusion_reason"]))
    row, _ = judge(page_html(8_009_001, "t", accepting_post("U9457"), date=day(u[3], 3)),
                   title="KB5130001 breaks printing")
    check("C5 the RSS title names another KB: identity_not_the_subject (C1b sees the RSS title)",
          bool(row) and row["exclusion_reason"] == "identity_not_the_subject", str(row and row["exclusion_reason"]))
    row, _ = judge(page_html(8_009_001, "t", accepting_post("U9457"), date=day(u[3], -20)))
    check("C6 the opening post predates the release: date_before_release (the reply date cannot rescue it)",
          bool(row) and row["exclusion_reason"] == "date_before_release" and row["source_date"] == day(u[3], -20)[:10],
          str(row and (row["exclusion_reason"], row["source_date"])))
    _, refusal = judge(page_html(8_009_001, "t", accepting_post("U9457"), date=None))
    check("C7 an undated page is refused and NOT re-judged (no fallback to the RSS date)", refusal == "undated")
    _, r_id = judge(page_html(8_009_001, "t", accepting_post("U9457"), ld_id="1234567"))
    _, r_redirect = judge(page_html(8_009_001, "t", accepting_post("U9457")), final=url(8_009_999, "other"))
    _, r_slug = judge(page_html(8_009_001, "t", accepting_post("U9457"), date=day(u[3], 3)),
                      final=url(8_009_001, "renamed"))
    check("C8 a JSON-LD id mismatch and a redirect to another question are refused; a slug rename is not",
          r_id == "id_mismatch" and r_redirect == "redirect" and r_slug == "", f"{r_id} {r_redirect} {r_slug}")
    _, r_machine = judge(page_html(8_009_001, "t", accepting_post("U9457"), machine=True))
    check("C9 a machine-generated question segment is refused", r_machine == "machine_generated")
    _, r_noqa = judge(page_html(8_009_001, "t", accepting_post("U9457"), ld=False))
    _, r_shape = judge(page_html(8_009_001, "t", accepting_post("U9457"), main_type="Answer"))
    check("C10 no QAPage block / a mainEntity that is not a Question: refused",
          r_noqa == "no_qapage" and r_shape == "not_a_question", f"{r_noqa} {r_shape}")
    cand, _ = mw._hydrated_candidate(url(8_009_001), {**rss_cand, "source_date": "2026-11-01T10:00:00Z"},
                                     url(8_009_001), page_html(8_009_001, "A different page title",
                                                               accepting_post("U9457"), date=day(u[3], 3)))
    check("C11 the candidate keeps the RSS title and the discovery URL, and its text is that title plus "
          "the asker's own post",
          cand["report_title"] == ELIGIBLE_TITLE and cand["parent_title"] == ELIGIBLE_TITLE
          and cand["source_url"] == url(8_009_001) and cand["report_text"].startswith(ELIGIBLE_TITLE)
          and accepting_post("U9457") in cand["report_text"] and cand["source_type"] == mw.SOURCE_TYPE)
    check("C12 the date is the page's own, never the RSS last-activity date",
          cand["source_date"] == day(u[3], 3)[:10] and cand["source_date"] != "2026-11-01")

    print(NEWLINE + "[E9/G3] the status property and the pace")
    from lib import monitoring_health as mh_mod  # noqa: PLC0415
    shapes = {"none": [], "network": [{"reason": "x", "blocked_signature": "network"}],
              "blocked": [{"reason": "y", "blocked_signature": "blocked"}],
              "broken": [{"reason": "learn_qna_search_fetch_failed:feed_parse_failed:ParseError",
                          "blocked_signature": "broken"}]}
    cases = degraded = other = 0
    for n in range(7):
        for a in range(n + 1):
            r = n - a
            for errs in shapes.values():
                before = mw.learn_qna_method_status([{}] * n, [{}] * a, [{}] * r, list(errs))
                for k in range(r + 1):
                    for _f in range(r - k + 1):
                        cases += 1
                        after = mw.learn_qna_method_status([{}] * n, [{}] * (a + k), [{}] * (r - k), list(errs))
                        if before in mh_mod.HEALTHY_STATUSES and after in mh_mod.DEGRADED_STATUSES:
                            degraded += 1
                        if before != after and (before, after) != ("no_results", "success"):
                            other += 1
    check("E9 840 cases of the SHIPPED status function: moving rows rejected->accepted with the error "
          "list untouched never turns healthy into degraded, and only no_results->success ever changes",
          cases == 840 and degraded == 0 and other == 0, f"cases {cases} degraded {degraded} other {other}")
    stamps: list[float] = []
    real = (qna_tags.time.monotonic, qna_tags.time.sleep, qna_tags._last_request_at)
    clock = {"t": 50.0}
    try:
        qna_tags.time.monotonic = lambda: clock["t"]
        qna_tags.time.sleep = lambda s: (stamps.append(s), clock.__setitem__("t", clock["t"] + s))
        qna_tags._last_request_at = 0.0
        qna_tags._pace()
        clock["t"] += 0.1
        qna_tags._pace()
    finally:
        qna_tags.time.monotonic, qna_tags.time.sleep, qna_tags._last_request_at = real
    src = Path(qna_tags.__file__).read_text(encoding="utf-8")
    body = src.split("def fetch_bounded(")[1].split("\ndef ")[0]
    check("G3 every bounded GET is paced by the module's own 0.35 s interval (fetch_bounded calls _pace)",
          qna_tags._MIN_REQUEST_INTERVAL == 0.35 and len(stamps) == 1 and abs(stamps[0] - 0.25) < 1e-9
          and body.count("_pace()") == 1 and body.index("_pace()") < body.index("urlopen("), str(stamps))


def section_workflow() -> None:
    print(NEWLINE + "[W] the dispatch input, executed")
    wf_path = _REPO / ".github" / "workflows" / "obs-evidence-collection.yml"
    wf = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    inputs = wf[True]["workflow_dispatch"]["inputs"]
    spec = inputs.get("windows_underfill_hydration") or {}
    check("W1 the input exists, is boolean, defaults to false and is not required",
          spec.get("type") == "boolean" and spec.get("default") is False and spec.get("required") is False,
          str(spec))
    step = next(s for s in wf["jobs"]["collect"]["steps"] if s.get("name") == "Collect patch evidence")
    others = "".join(p.read_text(encoding="utf-8") for p in (_REPO / ".github" / "workflows").glob("*.yml")
                     if p.name != wf_path.name)
    check("W2 no step env and no other workflow sets the flag; the reaper re-dispatch passes no inputs",
          mw.UNDERFILL_ENABLE_ENV not in str(step.get("env") or {})
          and mw.UNDERFILL_ENABLE_ENV not in others and "windows_underfill_hydration" not in others
          and "gh workflow run \"${wf}\" --ref main --repo \"${REPO}\"" in others)
    import re  # noqa: PLC0415

    def render(script: str, inputs_ctx: dict) -> str:
        def one(match):
            expr = match.group(1).strip()
            if not re.fullmatch(r"github\.event\.inputs\.[a-z_]+", expr):
                raise ValueError(f"unsupported expression {expr!r}")
            return str(inputs_ctx.get(expr.rsplit(".", 1)[1], ""))
        return re.sub(r"\$\{\{(.*?)\}\}", one, script)

    fake_py = "#!/usr/bin/env bash\necho \"ARGS $*\" >> \"$SIM_LOG\"\necho \"FLAG=${AUXSAYS_ENABLE_WINDOWS_UNDERFILL_HYDRATION:-unset}\" >> \"$SIM_LOG\"\n"
    outcomes: dict[str, tuple[int, str]] = {}
    shapes = {
        # schedule: no inputs at all; the reaper's no-input dispatch: booleans at their default.
        "schedule": {},
        "reaper": {"dry_run": "false", "windows_underfill_hydration": "false"},
        "dispatch_dry_flag": {"dry_run": "true", "windows_underfill_hydration": "true",
                              "product_id": "microsoft-windows-11"},
        "dispatch_write_flag": {"dry_run": "false", "windows_underfill_hydration": "true"},
        "dispatch_dry_noflag": {"dry_run": "true", "windows_underfill_hydration": "false"},
    }
    bash = shutil.which("bash")
    if bash is None:
        check("W3 bash is required to execute the run: scalar", False, "bash not on PATH")
        return
    for label, ctx in shapes.items():
        tmp = Path(tempfile.mkdtemp())
        try:
            py = tmp / "python"
            py.write_text(fake_py, newline="\n")
            py.chmod(py.stat().st_mode | stat.S_IEXEC)
            sh = tmp / "step.sh"
            sh.write_text(render(step["run"], ctx), newline="\n")
            log = tmp / "calls.log"
            log.write_text("", newline="\n")
            env = {k: v for k, v in os.environ.items() if k != mw.UNDERFILL_ENABLE_ENV}
            env.update({"PATH": str(tmp) + os.pathsep + env.get("PATH", ""), "SIM_LOG": str(log)})
            # GitHub's default `run:` shell on ubuntu: bash -e, WITHOUT pipefail.
            proc = subprocess.run([bash, "--noprofile", "--norc", "-e", str(sh)], capture_output=True,
                                  text=True, env=env)
            outcomes[label] = (proc.returncode, log.read_text())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    exported = {label: "FLAG=true" in text for label, (_rc, text) in outcomes.items()}
    check("W3 the run: scalar executes cleanly for every event shape",
          all(rc == 0 and "ARGS" in text for rc, text in outcomes.values()),
          str({k: v[0] for k, v in outcomes.items()}))
    check("W4 the flag is exported ONLY for a dispatch that is a dry run AND asked for it",
          exported == {"schedule": False, "reaper": False, "dispatch_dry_flag": True,
                       "dispatch_write_flag": False, "dispatch_dry_noflag": False}, str(exported))
    check("W5 the scheduled and reaper paths keep their exact arguments (routine --write horizon)",
          "ARGS auxsays/scripts/run_patch_evidence_collection.py --since-days 45 --max-pages 5 --write"
          in outcomes["schedule"][1].splitlines()
          and "ARGS auxsays/scripts/run_patch_evidence_collection.py --since-days 45 --max-pages 5 --write"
          in outcomes["reaper"][1].splitlines()
          and "--dry-run" in outcomes["dispatch_dry_flag"][1], outcomes["schedule"][1])


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Windows Learn Q&A opening-post hydration (AUX-073): default off, enrichment only")
    print("=" * 78)
    section_pure()
    section_workflow()

    print(NEWLINE + "[A] default off")
    flag = mw.UNDERFILL_ENABLE_ENV
    disabled = ["", "false", "0", "1", "yes", "on", "enabled"]
    check("A1 the gate is true-only: absent and 7 other spellings are off; 'true' and ' TRUE ' are on",
          not mw.windows_underfill_hydration_enabled({})
          and not any(mw.windows_underfill_hydration_enabled({flag: v}) for v in disabled)
          and mw.windows_underfill_hydration_enabled({flag: "true"})
          and mw.windows_underfill_hydration_enabled({flag: " TRUE "}))

    every = [k for k in IDS]
    tmp = Path(tempfile.mkdtemp(prefix="underfill-"))
    try:
        sandbox = build_sandbox(tmp / "dry")
        fail_kinds = {"http_503": {"http": 503}, "http_429": {"http": 429}, "urlerror": {"urlerror": 1},
                      "timeout": {"timeout": 1}, "deadline": {"deadline": 1, "html": "x"},
                      "budget": {"budget": 1, "html": "x"},
                      "parse": {"generic": 1, "broken": 1}}
        runs = [{"name": "off", "flag": None, "evaluate": ["|".join(key(n)) for n in every]}]
        runs += [{"name": f"off_{i}", "flag": v} for i, v in enumerate(disabled)]
        runs += [{"name": "on", "flag": "true", "evaluate": ["|".join(key(n)) for n in every]}]
        for kind, behaviour in fail_kinds.items():
            if kind == "parse":
                continue  # driven below, against a page the parser raises on
            runs.append({"name": f"fail_{kind}", "flag": "true", "pages": {"__none__": {}},
                         "default_page": behaviour, "evaluate": ["|".join(key(n)) for n in LIVE]})
        runs += [
            {"name": "strict_off", "flag": None, "probe": "strict_stub"},
            {"name": "strict_on", "flag": "true", "probe": "strict_stub"},
            {"name": "reverse", "flag": "true", "probe": "reverse_health"},
            {"name": "rebuild", "flag": "true", "probe": "capture_rebuild", "pages": {"__none__": {}},
             "default_page": {"http": 503}},
            {"name": "abort", "flag": "true", "probe": "abort"},
            {"name": "headroom", "flag": "true", "budget": 45},
            {"name": "expired", "flag": "true", "budget": 0},
            {"name": "deadline", "flag": "true", "budget": 100, "advance_per_get": 25,
             "pages": {"__none__": {}}, "default_page": {"generic": 1}},
            {"name": "rss_error", "flag": "true", "rss_errors": {IDS["C9818"][1]: "network_URLError"}},
            {"name": "bulk_one", "flag": "true", "rss": bulk_rss({"U9457": 40}), "pages": {"__none__": {}},
             "default_page": {"generic": 1}},
            {"name": "bulk_all", "flag": "true", "rss": bulk_rss({"U9457": 40, "N9711": 20, "C9818": 10}),
             "pages": {"__none__": {}}, "default_page": {"generic": 1}},
        ]
        # The parse failure: a page whose QAPage carries a non-list answer bucket makes the parser raise.
        out = drive(sandbox, runs, generic_page=GENERIC_PAGE)
        broken_page = page_html(0, ELIGIBLE_TITLE, "x", broken_answers=True).replace('"0"', '"{qid}"')
        out.update(drive(sandbox, [{"name": "fail_parse", "flag": "true", "pages": {"__none__": {}},
                                    "default_page": {"generic": 1},
                                    "evaluate": ["|".join(key(n)) for n in LIVE]}],
                         generic_page=broken_page))
        wsandbox = build_sandbox(tmp / "write")
        wout = drive(wsandbox, [{"name": "write_on", "flag": "true", "write": True}])["write_on"]
        rsandbox = build_sandbox(tmp / "r1")
        r1_pages = discovery()[2]
        u = IDS["U9457"]
        r1_pages[url(8_001_001)] = {"html": page_html(
            8_001_001, ELIGIBLE_TITLE,
            f"After installing KB5130001 the printer broke, so I rolled back to {u[1]} and it works again. "
            f"My other PC on 26100.9457 and the one on 26200.9278 are fine.", date=day(u[3], 3))}
        r1 = drive(rsandbox, [{"name": "r1_dry", "flag": "true", "pages": r1_pages},
                              {"name": "r1_write", "flag": "true", "pages": r1_pages, "write": True}])

        off, on = out["off"], out["on"]
        off_dump = dumps(off["results"])
        check("A2 flag off: zero sockets, zero page requests, zero paced GETs",
              all(out[n]["sockets"] == 0 and not out[n]["urlopen"] and out[n]["pace"] == 0
                  for n in ["off", *(f"off_{i}" for i in range(len(disabled)))]))
        check("A3 the lane produced real output to compare (this is not vacuous)",
              len(off["results"]) == len(IDS) and off_dump.count(mw.METHOD_ID) == len(IDS)
              and sum(r["rejected_count"] for r in off["results"]) > 20)
        check("A4 byte-identical result JSON for absent and all seven disabled spellings",
              all(dumps(out[f"off_{i}"]["results"]) == off_dump for i in range(len(disabled))))
        check("A5 flag off: the pass is never entered and the extra store read never happens",
              all(out[n]["probe"]["pass_called"] == 0 and out[n]["probe"]["cas_called"] == 0
                  for n in ["off", *(f"off_{i}" for i in range(len(disabled)))])
              and on["probe"]["pass_called"] == 1 and on["probe"]["cas_called"] == 1)
        check("A6 flag off: no result carries a hydration block and no RSS note mentions hydration",
              "underfill_hydration" not in off_dump and "Opening-post hydration" not in off_dump
              and "windows_underfill" not in dumps(off["events"]))
        check("A7 flag on with the same fixtures DOES change the output (the comparison can fail)",
              dumps(on["results"]) != off_dump and on["urlopen"])

        # ---------------------------------------------------------------- B. scope and dedup
        print(NEWLINE + "[B] scope and dedup")
        fetched = set(on["urlopen"])
        ob = by_build(on)
        blocks = {b: r.get("underfill_hydration") or {} for b, r in ob.items()}
        check("B1 only the two excerpt-explainable reasons are queued: generic_support_request and "
              "wrong_kb_for_current_patch rejects are never fetched",
              url(8_001_101) not in fetched and url(8_001_102) not in fetched
              and url(8_001_001) in fetched and url(8_001_005) in fetched)
        check("B2 live identities are never queued or fetched",
              all(blocks[IDS[n][1]].get("decision") == "live" for n in LIVE)
              and not any(f"/{8_005_000 + i * 10 + j}/" in u_ for i in range(3) for j in (1, 2) for u_ in fetched))
        check("B3 an identity outside the 90-day window is never queued or fetched",
              blocks[IDS["OLD"][1]].get("decision") == "outside_recency_window"
              and url(8_004_001) not in fetched and url(8_004_002) not in fetched)
        check("B4 a URL a stored counted row holds is never fetched (held for its own patch, claimed for "
              "another)",
              url(7_200_001, "stored") not in fetched and HELD_U9457 not in fetched
              and blocks[IDS["U9457"][1]].get("held") == 1
              and blocks[IDS["U9457"][1]]["skipped"].get("claimed_by_another_patch") == 1
              and blocks[IDS["N9711"][1]].get("held") == 1)
        check("B5 a stored WITHDRAWN (counted: false) URL is never fetched, on any sibling",
              url(7_100_001, "stored") not in fetched
              and blocks[IDS["N9711"][1]]["skipped"].get("stored_in_any_state") == 1
              and blocks[IDS["S9711"][1]]["skipped"].get("stored_in_any_state") == 1)
        check("B6 Tech Community rows are never hydrated",
              not any("techcommunity" in u_ for u_ in on["urlopen"]))
        check("B7 a URL two siblings queued is fetched ONCE; the second is served from the memo",
              on["urlopen"].count(url(8_002_001)) == 1 and len(on["urlopen"]) == len(set(on["urlopen"]))
              and blocks[IDS["S9711"][1]].get("cache_hits") == 2 and blocks[IDS["S9711"][1]].get("attempts") == 0)

        # ---------------------------------------------------------------- D. attribution
        print(NEWLINE + "[D] attribution")
        n_block, s_block = blocks[IDS["N9711"][1]], blocks[IDS["S9711"][1]]
        check("D1 newest-first: 26H2 (walked first) takes the shared report, the 25H2 sibling gets "
              "cross_patch_duplicate",
              url(8_002_001) in n_block.get("accepted_urls", [])
              and s_block.get("still_rejected_reasons", {}).get("cross_patch_duplicate") == 1
              and s_block.get("accepted") == 0, f"{n_block.get('accepted_urls')} {s_block.get('still_rejected_reasons')}")
        stored = (yaml.safe_load(wout["evidence_after"]) or {})["evidence"]
        added = stored[len((yaml.safe_load(wout["evidence_before"]) or {})["evidence"]):]
        check("D2 the row is stored under the DISCOVERY URL even when the page answered on a renamed slug",
              any(r["source_url"] == url(8_002_001) for r in added)
              and not any("renamed-slug" in r["source_url"] for r in added))
        check("D3 every hydrated row is microsoft_learn_qna: no second family",
              bool(added) and {r["source_type"] for r in added} == {mw.SOURCE_TYPE})
        urls_all = [r["source_url"] for r in stored if r.get("counted") is not False]
        check("D4 one URL, one counted row: the shared report exists exactly once in the store",
              urls_all.count(url(8_002_001)) == 1 and len(added) == len({r["source_url"] for r in added}))

        # ---------------------------------------------------------------- E. isolation
        print(NEWLINE + "[E] isolation: an enrichment failure never touches the method's health")
        queued = {b for b, blk in blocks.items() if blk.get("decision") == "underfilled"}
        off_stripped = dumps(strip_underfill(off["results"], queued))
        for kind in fail_kinds:
            res = out[f"fail_{kind}"]
            got = by_build(res)
            failures = sum(int((r.get("underfill_hydration") or {}).get("failures") or 0)
                           + int((r.get("underfill_hydration") or {}).get("refused") or 0)
                           for r in res["results"])
            check(f"E {kind}: status, counters and Tech Community rows are identical to flag-off; "
                  "only the RSS notes differ",
                  dumps(strip_underfill(res["results"], queued)) == off_stripped and failures >= 1
                  and all(health_of(got[b])["status"] == health_of(by_build(off)[b])["status"] for b in got),
                  f"failures {failures}")
        c_on, c_off = health_of(ob[IDS["C9818"][1]]), health_of(by_build(off)[IDS["C9818"][1]])
        check("E8 accepted + failed hydrations on one patch give success, never partial",
              c_off["status"] == "no_results" and c_on["status"] == "success"
              and blocks[IDS["C9818"][1]].get("accepted") == 1 and blocks[IDS["C9818"][1]].get("failures") == 4,
              f"{c_off['status']} -> {c_on['status']}")
        rs = by_build(out["rss_error"])
        check("E10 a genuinely failed primary RSS query keeps the row degraded: the patch is "
              "certifier_unreachable, nothing is fetched for it, and it never reads success",
              health_of(rs[IDS["C9818"][1]])["status"] == "partial"
              and (rs[IDS["C9818"][1]].get("underfill_hydration") or {}).get("decision") == "certifier_unreachable"
              and not any(f"/{8_003_000 + i}/" in u_ for i in range(1, 6) for u_ in out["rss_error"]["urlopen"]))

        # ---------------------------------------------------------------- F. live fixtures
        print(NEWLINE + "[F] the live fixtures certify after an all-fail pass")
        for name in LIVE:
            k = "|".join(key(name))
            check(f"F {name}: live through the shipped evaluate after every hydration failed, as with the "
                  "flag off",
                  all(out[f"fail_{kind}"]["evaluate"][k]["live"] for kind in fail_kinds)
                  and off["evaluate"][k]["live"] and on["evaluate"][k]["live"],
                  str({kind: out[f"fail_{kind}"]["evaluate"][k]["reasons"] for kind in fail_kinds}))

        # ---------------------------------------------------------------- G. budgets
        print(NEWLINE + "[G] budgets")
        one, allb = out["bulk_one"], out["bulk_all"]
        check("G1 at most 45 real GETs per run, every one distinct",
              len(allb["urlopen"]) == 45 and len(set(allb["urlopen"])) == 45, str(len(allb["urlopen"])))
        check("G2 at most 30 real GETs per identity", len(one["urlopen"]) == 30
              and (by_build(one)[IDS["U9457"][1]].get("underfill_hydration") or {}).get("not_reached") == 10,
              str(len(one["urlopen"])))
        check("G4 a 429 opens the circuit at once: one GET, everything else not reached [circuit]",
              len(out["fail_http_429"]["urlopen"]) == 1
              and any((r.get("underfill_hydration") or {}).get("not_reached_reasons", {}).get("circuit")
                      for r in out["fail_http_429"]["results"]))
        check("G5 five consecutive transport failures open the circuit",
              len(out["fail_http_503"]["urlopen"]) == 5 and len(out["fail_urlerror"]["urlopen"]) == 5
              and any("open:consecutive_failures" == (r.get("underfill_hydration") or {}).get("circuit_breaker")
                      for r in out["fail_http_503"]["results"]))
        ev = {e["reason"] for n in ("headroom", "expired") for e in out[n]["events"] if e["event"] == "windows_underfill"}
        check("G6 no headroom (finalize already expired, or under 60 s left): skipped with ZERO requests",
              not out["headroom"]["urlopen"] and not out["expired"]["urlopen"]
              and ev == {"insufficient_headroom", "collector_finalize_expired"}, str(ev))
        dl = out["deadline"]
        check("G7 the pass stops requesting once less than the writeback reserve remains",
              len(dl["urlopen"]) == 3 and any((r.get("underfill_hydration") or {}).get("not_reached_reasons", {})
                                              .get("deadline") for r in dl["results"]), str(len(dl["urlopen"])))
        c_attempts = (by_build(allb)[IDS["C9818"][1]].get("underfill_hydration") or {}).get("attempts")
        check("G8 D3 end to end: the newest patch is fetched even though older closable patches could "
              "absorb all 45, and it is fetched FIRST",
              c_attempts == 5 and all(f"/{8_102_000 + i}/" in allb["urlopen"][i] for i in range(5)),
              f"{c_attempts} {allb['urlopen'][:5]}")

        # ---------------------------------------------------------------- H. write path
        print(NEWLINE + "[H] the write path uses only the existing writers")
        v = wout["validations"]
        check("H1 ownership.validate_method_health passes on the run's rows", v["method_health"] == "ok", str(v))
        check("H2 ALLOWED_METHODS is unchanged and does not own the hydration adapter",
              co.ALLOWED_METHODS[WIN] == {"learn_qna_search_rss", "techcommunity_windows_sitemap"}
              and mw.HYDRATION_ADAPTER_ID not in set().union(*co.ALLOWED_METHODS.values())
              and not any(h["method_id"] == mw.HYDRATION_ADAPTER_ID for r in wout["results"]
                          for h in r["method_health"]))
        check("H3 no new source type: the manifest is unchanged and every appended row is in it",
              co.ALLOWED_SOURCE_TYPES[WIN] == {"microsoft_learn_qna", "microsoft_tech_community"}
              and {r["source_type"] for r in added} <= co.ALLOWED_SOURCE_TYPES[WIN])
        check("H4 stored rows are append-only: validate_evidence passes and the old bytes are a prefix",
              v["evidence"] == "ok" and v["prefix"] is True and len(added) == 9, f"{v} added {len(added)}")
        wb = by_build(wout)
        u_row = health_of(wb[IDS["U9457"][1]])
        check("H5 the re-finalized counters validate: evidence_rows_added counts the loop's AND the pass's "
              "rows, and the health file passes validate_evidence_method_health",
              v["emh_validate_rc"] == 0 and u_row["evidence_rows_added"] == 6
              and u_row["accepted_candidates"] == 6 and u_row["evidence_rows_added"] <= u_row["accepted_candidates"]
              and wb[IDS["U9457"][1]]["evidence_rows_added"] == 6, str(u_row))
        check("H6 hydrated rows carry a sentiment and severity BOTH reconciliation and the Windows writer count",
              all(str(r["sentiment"]).lower() in VALID_SENTIMENTS and str(r["severity"]).lower() in VALID_SEVERITIES
                  for r in added))

        # ---------------------------------------------------------------- I. seam
        print(NEWLINE + "[I] the rss_out seam")
        check("I1 flag off: collect() never passes rss_out (a stub that rejects the keyword runs clean); "
              "the same stub fails with the flag on, so the tripwire is real",
              out["strict_off"]["error"] is None and len(out["strict_off"]["results"]) == len(IDS)
              and "rss_out" in str(out["strict_on"]["error"]), str(out["strict_on"]["error"]))
        rss_cap = {}
        records = sorted(Path(sandbox / "auxsays" / "updates" / "generated").glob("*.md"))
        rec_path = next(p for p in records if "26200-9457" in p.name)
        saved = (mw.learn_qna.collect_learn_qna_candidates, mw.utc_now)
        try:
            terms = discovery()[0]
            mw.learn_qna.collect_learn_qna_candidates = lambda **k: [
                {**c, "source_type": mw.SOURCE_TYPE, "source_name": mw.SOURCE_NAME}
                for c in terms[IDS["U9457"][2]]]
            mw.utc_now = lambda: CAPTURED
            pool = mw.TechCommunityPool(candidates=discovery()[1], telemetry={}, errors=[])
            acc, rej, health = mw.collect_for_record(patch_record("U9457", rec_path), None, {}, pool,
                                                     rss_out=rss_cap)
        finally:
            mw.learn_qna.collect_learn_qna_candidates, mw.utc_now = saved
        lane = rss_cap.get("accepted", []) + rss_cap.get("rejected", [])
        check("I2 rss_out holds the RSS lane's OWN lists: no Tech Community row in accepted or rejected, "
              "while the merged return value has it",
              lane and all(r["source_type"] == mw.SOURCE_TYPE for r in lane)
              and any(r["source_type"] == mw.TECHCOMMUNITY_SOURCE_TYPE for r in acc + rej)
              and set(rss_cap) == {"candidates", "accepted", "rejected", "errors", "query_terms", "target",
                                   "captured_at"})
        probe = out["rebuild"]["probe"]
        rebuilt = [c for c in probe["calls"] if c[0] in probe["rss"]]
        same = all(c[1] == probe["rss"][c[0]][0] and c[2] == probe["rss"][c[0]][1] for c in rebuilt)
        twice = {b for b in {c[0] for c in rebuilt} if sum(1 for c in rebuilt if c[0] == b) == 2}
        check("I3 the rebuild hands health_for_method the SAME errors object, and an all-fail pass leaves "
              "its length unchanged",
              same and twice >= {IDS["U9457"][1], IDS["N9711"][1], IDS["C9818"][1]}, f"{rebuilt[:6]}")
        rv = by_build(out["reverse"])
        u_rev = rv[IDS["U9457"][1]]["method_health"]
        check("I4 the RSS row is found by method_id: with Tech Community first, the right row is rebuilt",
              u_rev[0]["method_id"] == mw.TECHCOMMUNITY_METHOD_ID
              and "Opening-post hydration" in u_rev[1]["notes"] and "Opening-post hydration" not in u_rev[0]["notes"]
              and health_of(rv[IDS["U9457"][1]])["accepted_candidates"] == health_of(ob[IDS["U9457"][1]])["accepted_candidates"])

        # ---------------------------------------------------------------- J. R1 flags
        print(NEWLINE + "[J] AUX-067 R1 flags (dry run only)")
        rows = (by_build(r1["r1_dry"])[IDS["U9457"][1]].get("underfill_hydration") or {}).get("would_be_rows", [])
        flagged = next((r for r in rows if r["url"] == url(8_001_001)), {})
        claim = (flagged.get("r1") or {}).get("matched_build_claim") or {}
        check("J1 an opening post that says 'rolled back to <target build>' is accepted AND flagged with role "
              "rollback_previous (the R1 gate's S1 signal)",
              claim.get("role") == "rollback_previous" and flagged.get("original_date") == day(u[3], 3)[:10]
              and flagged.get("rss_date") == "2026-11-01T10:00:00Z", str(flagged))
        check("J2 a same-revision build on a sibling train is not competing; a different revision is",
              (flagged.get("r1") or {}).get("competing_builds") == ["26200.9278"]
              and (flagged.get("r1") or {}).get("competing_kbs") == ["KB5130001"], str(flagged.get("r1")))
        w_blob = dumps(r1["r1_write"]["results"])
        w_added = (yaml.safe_load(r1["r1_write"]["evidence_after"]) or {})["evidence"][
            len((yaml.safe_load(r1["r1_write"]["evidence_before"]) or {})["evidence"]):]
        check("J3 write mode emits no flag fields and no before/after rows; stored rows carry only schema fields",
              "would_be_rows" not in w_blob and "rss_row_before" not in w_blob and "matched_build_claim" not in w_blob
              and w_added and all(set(r) <= set(EVIDENCE_FIELDS) for r in w_added))

        # ---------------------------------------------------------------- K. registry
        print(NEWLINE + "[K] registry")
        entry = next(m for m in am.METHODS if m["method_id"] == mw.HYDRATION_ADAPTER_ID)
        modes = " ".join(entry["failure_modes"])
        check("K1 the registry's two Windows failure_modes clauses are present, PowerPoint's text kept",
              "On Windows (L1) this is enrichment inside learn_qna_search_rss" in modes
              and "never appended to that lane's error list" in modes
              and "On Windows (L1) source_date is the opening post's own date from the page, with no fallback" in modes
              and "every transport failure is appended to the owning lane's error list" in modes
              and entry["proven_on"] == ["microsoft-powerpoint"])

        # ---------------------------------------------------------------- T. telemetry (D2)
        print(NEWLINE + "[T] structured telemetry and truthful notes (D2)")
        ub = blocks[IDS["U9457"][1]]
        required = {"attempts", "successes", "failures", "accepted", "skipped", "circuit_breaker", "queued",
                    "not_reached", "cache_hits", "undated", "refused", "still_rejected", "decision"}
        check("T1 each queued patch carries a structured block: attempts, successes, failures, accepted, "
              "skipped and the circuit-breaker outcome",
              required <= set(ub) and ub["queued"] == 9 and ub["accepted"] == 5 and ub["undated"] == 1
              and ub["refused"] == 1 and ub["still_rejected"] == 2 and ub["circuit_breaker"] == "closed",
              str({k: ub.get(k) for k in sorted(required)}))
        summary = [e for e in on["events"] if e["event"] == "windows_underfill"]
        s = summary[0] if len(summary) == 1 else {}
        check("T2 one run-level windows_underfill event: the trigger histogram and the totals",
              s.get("outcome") == "ran" and s.get("decision_live") == 3 and s.get("decision_underfilled") == 4
              and s.get("decision_outside_recency_window") == 1 and s.get("attempts") == len(on["urlopen"])
              and s.get("failures") == 4 and s.get("total_accepted") == 8
              and sum(1 for e in on["events"] if e["event"] == "windows_hydration_failure") == 4, str(s))
        notes = health_of(ob[IDS["U9457"][1]])["notes"]
        all_notes = [health_of(r)["notes"] for o in out.values() for r in o["results"] if health_of(r)]
        check("T3 the notes say the step is optional, separately budgeted and never sets the status; an "
              "incomplete pass says so; no note ever claims a complete inspection",
              "optional enrichment" in notes and "separately budgeted" in notes
              and "never sets this method's status" in notes and "Hydration incomplete: 7 of 9" in notes
              and all(n.count("complete inspection") == n.count("not a complete inspection") for n in all_notes))
        check("T4 a run warning when at least one fetch in five failed or the circuit opened, and none on a "
              "clean run",
              "::warning title=Windows opening-post hydration::" in on["stdout"]
              and "::warning" in out["fail_http_429"]["stdout"] and "::warning" not in one["stdout"])
        ab = out["abort"]
        ab_event = next((e for e in ab["events"] if e["event"] == "windows_underfill"), {})
        check("T5 an exception inside the pass discards it: health identical to flag-off, the reason "
              "recorded, a warning raised, no exception escapes the collector",
              ab["error"] is None and ab_event.get("outcome") == "aborted"
              and ab_event.get("reason") == "hydration_aborted:RuntimeError"
              and dumps(strip_underfill(ab["results"], set())) == dumps(strip_underfill(off["results"], set()))
              and all((r.get("underfill_hydration") or {}).get("pass") == "aborted" for r in ab["results"])
              and "::warning" in ab["stdout"], str(ab_event))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("=" * 78)
    for err in _ERRORS:
        print(f"  - {err}")
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
