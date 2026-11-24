#!/usr/bin/env python3
"""Method selection adapts to measured history. What is ACCEPTED does not.

WHAT THIS GUARDS.

  H. HISTORY. `upsert_method_health` carries measured history on the row a method already owns:
     attempts, last good, last accepted, failure and zero-accept streaks. An attempt is counted
     once, a switched-off method makes none, and a row no run touches is not rewritten. Cost and
     rejection reasons are stored only when a collector measured them -- never as a flattering 0.
  D. DISCOVERY METHOD. A new evidence row names the method that found it only when that is
     established; a row two methods could both have found is stored unstamped. The stamp is
     provenance: the counting predicate and the dedupe key never read it.
  O. ORDER. `order_methods` is a deterministic permutation driven by stored history; with no
     history it is the declared order. A fallback chain is bounded by declaration.
  A. ACCEPTANCE INVARIANCE, through the real orchestration graph, the real acceptance authority
     and the real append: two opposite histories give two different method orders and exactly the
     same accepted evidence. The only field that differs is which method is credited with a
     report both of them found.
  C. DAVINCI. The Creative COW board is fetched once per collector run, not once per record.

Offline and deterministic: no network, temp directories only.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_adaptive_method_routing.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

import yaml

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import orchestrate_evidence_run as orch  # noqa: E402
from lib import acquisition_methods as am  # noqa: E402
from lib import method_routing as mr  # noqa: E402
from lib import patch_identity as pi  # noqa: E402
from lib.orchestration import DONE  # noqa: E402
from lib.report_counts import counted_evidence_counts  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import davinci as dv  # noqa: E402
from tests import test_orchestration_r1 as r1  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

PRODUCT, VERSION, BUILD = r1.PRODUCT, r1.VERSION, r1.BUILD_A


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def health(method_id: str, status: str, last_run: str, *, accepted: int = 0, candidates: int = 0,
           product: str = "obs-studio", version: str = "32.0.2", source_type: str = "github_issue",
           build: str = "", **extra) -> dict:
    return base.method_health_row(
        product_id=product, update_version=version, target_build=build, method_id=method_id,
        source_type=source_type, status=status, candidates_found=max(candidates, accepted),
        accepted_reports=accepted, rejected_reports=max(candidates, accepted) - accepted,
        blocked_reason="refused" if status in ("blocked", "broken") else None,
        last_run=last_run, notes="fixture", **extra)


def stored(path: Path, method_id: str) -> dict:
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))["methods"]
    return next(r for r in rows if r["method_id"] == method_id)


def history_checks() -> None:
    print("-- H. measured history is carried by the existing writer")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "health.yml"
        base.upsert_method_health([health("github_issues", "success", "2026-11-01T00:00:00Z", accepted=2)], path)
        row = stored(path, "github_issues")
        check("H1 a first successful attempt records attempts=1, last good and last accepted",
              row.get("attempts") == 1 and row.get("last_good_at") == "2026-11-01T00:00:00Z"
              and row.get("last_accepted_at") == "2026-11-01T00:00:00Z", str(row))
        check("H2 a healthy row carries no failure or zero-accept streak",
              "consecutive_failures" not in row and "consecutive_zero_accept_runs" not in row, str(row))

        base.upsert_method_health([health("github_issues", "blocked", "2026-11-02T00:00:00Z")], path)
        row = stored(path, "github_issues")
        check("H3 a refused attempt counts, starts both streaks, and keeps the last-good time",
              row.get("attempts") == 2 and row.get("consecutive_failures") == 1
              and row.get("consecutive_zero_accept_runs") == 1
              and row.get("last_good_at") == "2026-11-01T00:00:00Z"
              and row.get("last_accepted_at") == "2026-11-01T00:00:00Z", str(row))

        base.upsert_method_health([health("github_issues", "blocked", "2026-11-02T00:00:00Z")], path)
        check("H4 the same run written twice is one attempt, not two",
              stored(path, "github_issues").get("attempts") == 2, str(stored(path, "github_issues")))

        base.upsert_method_health([health("github_issues", "disabled", "2026-11-03T00:00:00Z")], path)
        row = stored(path, "github_issues")
        check("H5 a switched-off method makes no attempt and keeps its history",
              row.get("attempts") == 2 and row.get("consecutive_failures") == 1
              and row.get("last_good_at") == "2026-11-01T00:00:00Z" and row["status"] == "disabled", str(row))

        base.upsert_method_health([health("github_issues", "no_results", "2026-11-04T00:00:00Z")], path)
        row = stored(path, "github_issues")
        check("H6 an answer with nothing accepted clears the failure streak and extends the zero-accept one",
              row.get("attempts") == 3 and "consecutive_failures" not in row
              and row.get("consecutive_zero_accept_runs") == 2
              and row.get("last_good_at") == "2026-11-04T00:00:00Z", str(row))

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "health.yml"
        legacy = {"product_id": "obs-studio", "update_version": "32.0.2", "target_build": "",
                  "method_id": "obs_forum", "source_type": "obs_forum_thread", "status": "success",
                  "candidates_found": 3, "accepted_candidates": 1, "duplicate_existing_evidence": 0,
                  "evidence_rows_added": 1, "public_counted_reports": 1, "accepted_reports": 1,
                  "rejected_reports": 2, "blocked_reason": "", "last_run": "2026-10-01T00:00:00Z",
                  "notes": "legacy"}
        untouched = dict(legacy, method_id="github_issues", source_type="github_issue")
        text = yaml.safe_dump({"schema_version": 1, "methods": [legacy, untouched]},
                              sort_keys=False, allow_unicode=True, width=1000)
        path.write_text(text, encoding="utf-8")
        check("H7 a file written before the history fields loads and re-serializes to the same bytes",
              yaml.safe_dump({"schema_version": 1, "methods": base.load_method_health(path)},
                             sort_keys=False, allow_unicode=True, width=1000) == text)
        base.upsert_method_health([health("obs_forum", "blocked", "2026-11-02T00:00:00Z",
                                          source_type="obs_forum_thread")], path)
        row = stored(path, "obs_forum")
        check("H8 a pre-existing row is read for the one attempt it records, never back-filled further",
              row.get("attempts") == 2 and row.get("last_good_at") == "2026-10-01T00:00:00Z"
              and row.get("last_accepted_at") == "2026-10-01T00:00:00Z"
              and row.get("consecutive_failures") == 1, str(row))
        check("H9 a row the run did not emit is left exactly as it was stored",
              stored(path, "github_issues") == untouched, str(stored(path, "github_issues")))

    plain = health("github_issues", "success", "2026-11-01T00:00:00Z", accepted=1)
    check("H10 cost and rejection reasons are ABSENT unless a collector measured them",
          not ({"duration_ms", "requests", "rejection_reasons"} & set(plain)), str(sorted(plain)))
    measured = health("github_issues", "partial", "2026-11-01T00:00:00Z", accepted=1, candidates=4,
                      duration_ms=1234, requests=0,
                      rejection_reasons={"missing_exact_patch_version_match": 2, "not_a_real_issue_report": 1,
                                         "zero": 0})
    check("H11 measured cost is stored as given, including a measured zero; empty reason counts are dropped",
          measured.get("duration_ms") == 1234 and measured.get("requests") == 0
          and measured.get("rejection_reasons") == {"missing_exact_patch_version_match": 2,
                                                    "not_a_real_issue_report": 1}, str(measured))
    check("H12 rejection reasons are counted from the rows' own exclusion codes",
          base.rejection_reason_counts([{"exclusion_reason": "a"}, {"exclusion_reason": "a"},
                                        {"exclusion_reason": "b"}, {}]) == {"a": 2, "b": 1, "unspecified": 1})
    raw = yaml.safe_load(base.METHOD_HEALTH_PATH.read_text(encoding="utf-8"))["methods"]
    check("H13 every stored health row survives a load unchanged (corpus round trip)",
          base.load_method_health() == raw and len(raw) > 1000, str(len(raw)))


def evidence_row(url: str, source_type: str = "github_issue", **extra) -> dict:
    row = base.make_evidence_row(
        product_id="obs-studio", update_version="32.0.2", source_type=source_type, source_name="fixture",
        source_url=url, parent_title="OBS 32.0.2 crashes", report_title="OBS 32.0.2 crashes",
        report_text="OBS 32.0.2 crashes when I start recording.", captured_at="2026-11-05T00:00:00Z",
        source_date="2026-11-04", target_release_date="2026-10-29", patch_version_matched=True,
        matched_version="32.0.2", match_basis="body", counted=True, exclusion_reason=None,
        issue_theme="crash", workflow_area="recording", platform="windows", severity="high",
        sentiment="negative")
    row.update(extra)
    return row


def discovery_checks() -> None:
    print("-- D. new evidence rows name their discovery method only when it is established")
    one = [health("github_issues", "success", "2026-11-05T00:00:00Z", accepted=1)]
    two = one + [health("obs_forum", "success", "2026-11-05T00:00:00Z", accepted=1,
                        source_type="github_issue")]
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.yml"
        base.append_evidence_rows([evidence_row("https://github.com/obsproject/obs-studio/issues/1")], path)
        first_bytes = path.read_bytes()
        rows = base.load_evidence(path)
        check("D1 without the run's health rows nothing is stamped",
              "discovery_method_id" not in rows[0], str(sorted(rows[0])))

        base.append_evidence_rows([evidence_row("https://github.com/obsproject/obs-studio/issues/2")],
                                  path, method_health=one)
        rows = base.load_evidence(path)
        check("D2 one method accepted for that patch and source type: the row names it",
              rows[1].get("discovery_method_id") == "github_issues", str(rows[1].get("discovery_method_id")))
        check("D3 the row stored earlier is never restamped (its bytes are a prefix of the file)",
              path.read_bytes().startswith(first_bytes) and "discovery_method_id" not in rows[0])
        keys = list(rows[1])
        check("D4 the stamp sits with the identity fields, before the matched-span and fact fields",
              keys.index("discovery_method_id") < keys.index("matched_text")
              if "matched_text" in keys else keys.index("discovery_method_id") < len(keys) - 1, str(keys))

        base.append_evidence_rows([evidence_row("https://github.com/obsproject/obs-studio/issues/3")],
                                  path, method_health=two)
        rows = base.load_evidence(path)
        check("D5 two methods could have found it: stored unstamped, not credited to a guess",
              "discovery_method_id" not in rows[2], str(rows[2].get("discovery_method_id")))

        base.append_evidence_rows(
            [evidence_row("https://github.com/obsproject/obs-studio/issues/4", discovery_method_id="obs_forum")],
            path, method_health=two)
        base.append_evidence_rows(
            [evidence_row("https://github.com/obsproject/obs-studio/issues/5", discovery_method_id="reddit_search")],
            path, method_health=two)
        base.append_evidence_rows(
            [evidence_row("https://github.com/obsproject/obs-studio/issues/6", discovery_method_id="obs_forum")],
            path)
        rows = base.load_evidence(path)
        check("D6 a collector's own stamp is kept when that method has a health row for the patch",
              rows[3].get("discovery_method_id") == "obs_forum")
        check("D7 a stamp naming a method that did not run for the patch is dropped",
              "discovery_method_id" not in rows[4] and "discovery_method_id" not in rows[5],
              f"{rows[4].get('discovery_method_id')} {rows[5].get('discovery_method_id')}")
        check("D8 all six rows count the same, stamped or not",
              sum(counted_evidence_counts(rows, windows_targets={}).values()) == 6
              and all(base.row_is_counted(r) for r in rows))
    a = evidence_row("https://github.com/obsproject/obs-studio/issues/9")
    b = dict(a, discovery_method_id="github_issues")
    check("D9 the dedupe identity ignores the stamp",
          base.evidence_key(a, "id") == base.evidence_key(b, "id")
          and base.evidence_key(a, "source_url") == base.evidence_key(b, "source_url"))
    off = [health("github_issues", "disabled", "2026-11-05T00:00:00Z", accepted=0)]
    check("D10 a method that did not run, or accepted nothing, is never named",
          base.discovery_method_for(a, off) == ""
          and base.discovery_method_for(a, [health("github_issues", "no_results", "2026-11-05T00:00:00Z")]) == "")
    other_patch = [health("github_issues", "success", "2026-11-05T00:00:00Z", accepted=1, version="32.0.1")]
    check("D11 a method's success on ANOTHER patch names nothing here",
          base.discovery_method_for(a, other_patch) == "")


def order_checks() -> None:
    print("-- O. order is a deterministic permutation driven by stored history")
    declared = ["m_a", "m_b", "m_c", "m_d"]
    check("O1 with no history the declared order is returned unchanged",
          mr.order_methods(declared, {}) == declared and mr.order_methods(declared, None) == declared)
    rows = [
        health("m_a", "blocked", "2026-11-20T00:00:00Z", product="p"),
        health("m_b", "success", "2026-11-20T00:00:00Z", accepted=1, product="p"),
        health("m_c", "success", "2026-11-20T00:00:00Z", accepted=5, product="p"),
        health("m_d", "no_results", "2026-11-20T00:00:00Z", product="p"),
    ]
    hist = mr.method_history(rows, "p")
    check("O2 same-time acceptors: more accepted first; never-accepted next; a refused method last",
          mr.order_methods(declared, hist) == ["m_c", "m_b", "m_d", "m_a"], str(mr.order_methods(declared, hist)))
    rows2 = [
        health("m_a", "success", "2026-11-10T00:00:00Z", accepted=9, product="p"),
        health("m_b", "success", "2026-11-21T00:00:00Z", accepted=1, product="p"),
    ]
    check("O3 the most RECENTLY productive method leads, ahead of a larger but older yield",
          mr.order_methods(["m_a", "m_b"], mr.method_history(rows2, "p")) == ["m_b", "m_a"])
    rows3 = [
        health("m_a", "success", "2026-11-21T00:00:00Z", accepted=1, product="p", duration_ms=9000),
        health("m_b", "success", "2026-11-21T00:00:00Z", accepted=1, product="p", duration_ms=40),
        health("m_c", "success", "2026-11-21T00:00:00Z", accepted=1, product="p"),
    ]
    check("O4 equal yield: the measured-cheaper method first, an unmeasured cost last",
          mr.order_methods(["m_a", "m_b", "m_c"], mr.method_history(rows3, "p")) == ["m_b", "m_a", "m_c"])
    for name, history in (("mixed", hist), ("recency", mr.method_history(rows2, "p")), ("empty", {})):
        ordered = mr.order_methods(declared + ["m_a"], history)
        check(f"O5 the result is a permutation: nothing dropped, added or repeated ({name})",
              sorted(ordered) == sorted(declared), str(ordered))
    check("O6 ordering is stable across calls (deterministic)",
          all(mr.order_methods(declared, hist) == mr.order_methods(declared, hist) for _ in range(5)))
    mixed = rows + [health("m_a", "success", "2026-11-20T01:00:00Z", product="p", version="32.0.1")]
    check("O7 a method is 'refused' only when NO row of its newest pass answered",
          not mr.latest_pass_failed(mr.method_history(mixed, "p")["m_a"])
          and mr.latest_pass_failed(hist["m_a"]))

    original = mr.METHOD_PLANS.get("obs-studio")
    try:
        mr.METHOD_PLANS["obs-studio"] = {"primary": ["github_issues"],
                                         "fallback": ["f1", "f2", "f3", "f4"]}
        refused = False
        try:
            mr.plan_methods("obs-studio")
        except ValueError as exc:
            refused = "bound" in str(exc)
        check("O8 a fallback chain longer than the declared bound is refused", refused)
        mr.METHOD_PLANS["obs-studio"] = {"primary": ["github_issues"], "fallback": ["f1", "f2", "f3"]}
        check("O9 a chain at the bound is accepted", len(mr.plan_methods("obs-studio")["fallback"]) == 3)
    finally:
        if original is None:
            mr.METHOD_PLANS.pop("obs-studio", None)
        else:
            mr.METHOD_PLANS["obs-studio"] = original

    corpus = base.load_method_health()
    drift = []
    for product_id in mr.METHOD_PLANS:
        declared_plan = mr.plan_methods(product_id)
        effective = mr.effective_plan(product_id, corpus, base.load_method_probes(),
                                      reprobe_refusal=am.reprobe_refusal)
        for role in ("primary", "fallback", "probe_only", "disabled"):
            if sorted(effective[role]) != sorted(declared_plan[role]):
                drift.append(f"{product_id}.{role}")
    check("O10 over the stored corpus every product's effective plan holds exactly its declared methods",
          not drift and len(mr.METHOD_PLANS) >= 5, str(drift))
    check("O11 without rows or probes the effective plan IS the declared plan",
          all({k: v for k, v in mr.effective_plan(p).items() if k != "returned_to_service"}
              == mr.plan_methods(p) for p in mr.METHOD_PLANS))
    ppt_order = mr.effective_plan(PRODUCT, corpus, [], reprobe_refusal=am.reprobe_refusal)["primary"]
    check("O12 the PowerPoint lane's stored history actually reorders its primaries (the rule is not vacuous)",
          ppt_order != mr.plan_methods(PRODUCT)["primary"]
          and sorted(ppt_order) == sorted(mr.plan_methods(PRODUCT)["primary"]), str(ppt_order))


RSS, TAGS = "learn_qna_search_rss", "learn_qna_powerpoint_tags"
U1 = "https://learn.microsoft.com/en-us/answers/questions/5975101/ppt-crash-one"
U2 = "https://learn.microsoft.com/en-us/answers/questions/5975102/ppt-crash-two"
SHARED = "https://learn.microsoft.com/en-us/answers/questions/5975103/ppt-crash-shared"


def run_with_history(tmp: Path, favoured: str, *, adaptive: str = "1") -> tuple[list[str], list[dict], dict]:
    """One write run of the real graph. `favoured` is the method the seeded history says accepted
    most recently. Returns (method call order, stored evidence rows, counted-per-patch)."""
    repo = r1.make_fixture_repo(tmp, [BUILD])
    health_path = repo / "auxsays" / "_data" / "evidence_method_health.yml"
    other = TAGS if favoured == RSS else RSS
    seed = [
        health(favoured, "success", "2026-11-20T00:00:00Z", accepted=2, product=PRODUCT, version=VERSION,
               build=BUILD, source_type="microsoft_learn_qna"),
        health(other, "no_results", "2026-11-20T00:00:00Z", product=PRODUCT, version=VERSION,
               build=BUILD, source_type="microsoft_learn_qna"),
    ]
    base.upsert_method_health(seed, health_path)
    r1.g(repo, "add", "-A")
    r1.g(repo, "commit", "-m", "seed history")
    order: list[str] = []

    class Recording(r1.FakeMethod):
        def __call__(self, *args, **kwargs):
            order.append(self.method_id)
            return super().__call__(*args, **kwargs)

    methods = {
        RSS: Recording(RSS, "microsoft_learn_qna",
                       {BUILD: [r1.report_candidate(BUILD, U1), r1.report_candidate(BUILD, SHARED)]}),
        TAGS: Recording(TAGS, "microsoft_learn_qna",
                        {BUILD: [r1.report_candidate(BUILD, U2), r1.report_candidate(BUILD, SHARED)]}),
    }
    previous = os.environ.get("AUXSAYS_ADAPTIVE_ROUTING")
    os.environ["AUXSAYS_ADAPTIVE_ROUTING"] = adaptive
    try:
        pipeline = orch.Pipeline(
            repo, [PRODUCT], write=True, checkpoint_dir=tmp / "ckpt",
            evidence_path=repo / "auxsays" / "_data" / "consensus_evidence.yml",
            health_path=health_path, generated_dir=repo / "auxsays" / "updates" / "generated",
            methods=methods,
            authorities={"promote": lambda: {"rc": 0}, "qa": lambda: {"rc": 0}, "audit": lambda: {"rc": 0}},
            capability={"reddit_search": False},
            allow_patterns=["auxsays/_data/*", "auxsays/updates/generated/*powerpoint*.md"],
            writeback=lambda: {"outcome": "push_success_first_attempt", "pages_dispatched": True},
            context=SimpleNamespace(write=True, since=None, max_pages=1, target_versions=None))
        state = pipeline.run()
    finally:
        if previous is None:
            os.environ.pop("AUXSAYS_ADAPTIVE_ROUTING", None)
        else:
            os.environ["AUXSAYS_ADAPTIVE_ROUTING"] = previous
    assert state.terminal == DONE, state.failures
    rows = base.load_evidence(repo / "auxsays" / "_data" / "consensus_evidence.yml")
    return order, rows, dict(state.accepted_counts)


def comparable(rows: list[dict]) -> list[dict]:
    """A stored row without the two fields that legitimately differ between two runs: when it was
    captured, and which method is credited with finding it."""
    return sorted(({k: v for k, v in row.items() if k not in ("captured_at", "discovery_method_id")}
                   for row in rows), key=lambda r: r["source_url"])


def acceptance_invariance_checks() -> None:
    print("-- A. opposite histories: different order, identical accepted evidence (real graph)")
    with tempfile.TemporaryDirectory() as td:
        order_rss, rows_rss, counts_rss = run_with_history(Path(td) / "a", RSS)
        order_tags, rows_tags, counts_tags = run_with_history(Path(td) / "b", TAGS)
        order_off, rows_off, _counts_off = run_with_history(Path(td) / "c", TAGS, adaptive="0")
    check("A1 the favoured method is tried first in each run (history drives the order)",
          order_rss[:2] == [RSS, TAGS] and order_tags[:2] == [TAGS, RSS], f"{order_rss} / {order_tags}")
    check("A2 both runs store the same three reports", len(rows_rss) == 3 and len(rows_tags) == 3,
          f"{len(rows_rss)} / {len(rows_tags)}")
    check("A3 every stored field that states WHAT was accepted is identical across the two orders",
          comparable(rows_rss) == comparable(rows_tags))
    check("A4 the counted population per patch is identical",
          counts_rss == counts_tags and list(counts_rss.values()) == [3], f"{counts_rss} / {counts_tags}")
    check("A5 the canonical counting predicate agrees on both stores",
          counted_evidence_counts(rows_rss, windows_targets={})
          == counted_evidence_counts(rows_tags, windows_targets={})
          and sum(counted_evidence_counts(rows_rss, windows_targets={}).values()) == 3)
    by_url = lambda rows: {r["source_url"]: r.get("discovery_method_id") for r in rows}  # noqa: E731
    check("A6 the ONLY difference is which method is credited with the report both found",
          by_url(rows_rss) == {U1: RSS, U2: TAGS, SHARED: RSS}
          and by_url(rows_tags) == {U1: RSS, U2: TAGS, SHARED: TAGS},
          f"{by_url(rows_rss)} / {by_url(rows_tags)}")
    check("A7 AUXSAYS_ADAPTIVE_ROUTING=0 restores the declared order, with the same accepted evidence",
          order_off[:2] == [RSS, TAGS] and comparable(rows_off) == comparable(rows_rss), str(order_off))


def davinci_checks() -> None:
    print("-- C. DaVinci fetches the Creative COW board once per run")
    listing = '<a href="https://creativecow.net/forums/thread/resolve-20-2-3-crash/">t1</a>' \
              '<a href="https://creativecow.net/forums/thread/render-queue-stalls/">t2</a>'
    thread = "<html><head><title>Thread - Creative COW</title></head><body><h1>Thread</h1>" \
             "<p>DaVinci Resolve crashes on export.</p></body></html>"
    calls: list[str] = []

    def fake_request(url: str) -> str:
        calls.append(url)
        return listing if "/forums/forum/" in url else thread

    ctx = base.CollectorContext(write=False, since=None, max_pages=2)
    records = [base.PatchRecord(dv.PRODUCT_ID, v, Path("auxsays/updates/generated") / f"{v}.md",
                                "2026-01-01T00:00:00Z", "current",
                                "DaVinci Resolve") for v in ("20.2.3", "20.2.2", "20.2.1")]
    original_request, original_cache = dv.request_text, dv._CREATIVE_COW_RUN_CACHE
    try:
        dv.request_text = fake_request
        links = dv.creative_cow_thread_links(listing)
        per_pass = 2 + len(links)
        check("C0 the fixture listing yields thread links (the test is not vacuous)", len(links) >= 1, str(links))

        dv._CREATIVE_COW_RUN_CACHE = None
        calls.clear()
        for record in records:
            dv.creative_cow_forum_search_candidates(record, ctx, [])
        check("C1 outside a collector run every call fetches (direct callers are unchanged)",
              len(calls) == per_pass * len(records), f"{len(calls)} vs {per_pass * len(records)}")

        dv._CREATIVE_COW_RUN_CACHE = {}
        calls.clear()
        results = [dv.creative_cow_forum_search_candidates(record, ctx, []) for record in records]
        check("C2 inside a run the board is fetched ONCE for all records",
              len(calls) == per_pass, f"{len(calls)} requests for {len(records)} records")
        check("C3 every record is given the same candidates",
              all(r == results[0] for r in results) and len(results[0]) == len(links))
        results[0][0]["report_text"] = "mutated"
        check("C4 a record's candidates are its own copies",
              dv.creative_cow_forum_search_candidates(records[1], ctx, [])[0]["report_text"] != "mutated")

        def failing_request(url: str) -> str:
            calls.append(url)
            raise dv.SourceAccessError("http_429_Too Many Requests", status=429)

        dv.request_text = failing_request
        dv._CREATIVE_COW_RUN_CACHE = {}
        calls.clear()
        errors_by_record = []
        for record in records:
            errors: list[dict] = []
            dv.creative_cow_forum_search_candidates(record, ctx, errors)
            errors_by_record.append(errors)
        check("C5 a refused pass is made once, and every record it served reports that refusal",
              len(calls) == 2 and all(len(e) == 2 for e in errors_by_record),
              f"{len(calls)} requests, errors {[len(e) for e in errors_by_record]}")

        dv.request_text = fake_request
        dv._CREATIVE_COW_RUN_CACHE = None
        calls.clear()
        original_records, original_newest = dv.generated_records, dv.newest_first
        dv.generated_records = lambda *a, **k: list(records)
        dv.newest_first = lambda rs: list(rs)
        try:
            out = dv.DavinciCollector().collect(ctx)
        finally:
            dv.generated_records, dv.newest_first = original_records, original_newest
        cow_rows = [h for result in out for h in result["method_health"]
                    if h["method_id"] == "creative_cow_forum_search"]
        check("C6 a whole collector run over three records makes one board pass",
              len(calls) == per_pass and len(out) == 3, f"{len(calls)} requests, {len(out)} results")
        check("C7 the run cache is cleared when the run ends", dv._CREATIVE_COW_RUN_CACHE is None)
        check("C8 each record's row states the requests IT caused: the pass on the first, none after",
              [h.get("requests") for h in cow_rows] == [per_pass, 0, 0]
              and all(isinstance(h.get("duration_ms"), int) for h in cow_rows),
              str([(h.get("requests"), h.get("duration_ms")) for h in cow_rows]))
        off = [h for result in out for h in result["method_health"] if h["method_id"] == "vendor_forum_search"]
        check("C9 with no recovery record the Blackmagic forum method stays off and asks nothing",
              all(h["status"] == "disabled" for h in off) and len(off) == 3
              and not any("blackmagicdesign" in url for url in calls))
    finally:
        dv.request_text, dv._CREATIVE_COW_RUN_CACHE = original_request, original_cache


def run() -> int:
    print("=" * 78)
    print("Adaptive method routing: history, discovery method, order, acceptance invariance")
    print("=" * 78)
    history_checks()
    discovery_checks()
    order_checks()
    acceptance_invariance_checks()
    davinci_checks()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed:", ", ".join(_ERRORS))
    print("=" * 78)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
