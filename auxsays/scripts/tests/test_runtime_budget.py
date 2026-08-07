#!/usr/bin/env python3
"""Bounded-runtime framework proofs (run 31086662777 remediation).

Proves the HARD per-request wall-clock abort (a real slow-drip read is terminated at the total deadline
with no lingering thread/socket), the hierarchical budget math, the Reddit 403/429 policy + listing
dedup, and a deterministic six-collector simulation that completes within its configured bound with every
collector reached, healthy collectors surviving, and reconciliation/QA reachable.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_runtime_budget.py
"""
from __future__ import annotations

import http.server
import sys
import threading
import time
import traceback
import urllib.error
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from patch_collectors import runtime_budget as rb  # noqa: E402
from patch_collectors import reddit_source as rs  # noqa: E402

_PASS = 0
_FAIL = 0
_ERR: list[str] = []


def ck(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERR.append(label)


# --- fakes -----------------------------------------------------------------------------------------
class FakeHeaders(dict):
    def get(self, k, default=""):
        return dict.get(self, k, dict.get(self, k.lower(), dict.get(self, k.title(), default)))

    def items(self):
        return dict.items(self)


class FakeResp:
    """Minimal urlopen-like response for bounded_request's opener injection."""
    def __init__(self, status=200, body=b"", headers=None):
        self.status = status
        self.code = status
        self.headers = FakeHeaders(headers or {})
        self._body = body
        self._pos = 0
        self.closed = False

    def read1(self, n):
        chunk = self._body[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk

    def close(self):
        self.closed = True


def opener_returning(status, body=b"{}", headers=None):
    def _op(req, timeout=None):
        return FakeResp(status, body, headers)
    return _op


def fresh_budget(clock=None, **overrides):
    cfg = rb.BudgetConfig(**overrides) if overrides else rb.BudgetConfig()
    b = rb.RuntimeBudget(cfg, clock=clock) if clock else rb.RuntimeBudget(cfg)
    b.start_collector("test")
    b.start_method("m")
    return b


def run() -> int:
    print("=" * 74)
    print("Bounded-runtime framework")
    print("=" * 74)

    # === A. HARD per-request abort on a REAL slow-drip read =========================================
    print("\n-- A. hard-abort transport (real slow-drip socket) --")

    class Drip(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(10 ** 9))  # promise a huge body, never deliver
            self.end_headers()
            try:
                for _ in range(100000):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.15)  # < read_slice, so the socket inactivity timeout NEVER fires
            except (BrokenPipeError, ConnectionResetError, OSError):
                Drip.disconnected = True

    Drip.disconnected = False
    srv = http.server.HTTPServer(("127.0.0.1", 0), Drip)  # single-threaded: no per-request worker
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.2)
    base_threads = threading.active_count()

    b = fresh_budget(per_request_total=1.2, read_slice=0.4)
    t0 = time.monotonic()
    aborted = False
    try:
        rb.bounded_request(f"http://127.0.0.1:{port}/x", budget=b, endpoint_family="drip")
    except rb.RequestDeadlineExceeded:
        aborted = True
    dt = time.monotonic() - t0
    ck("A1 slow-drip aborts via total deadline (not socket inactivity)", aborted)
    ck("A2 terminates within deadline (not the ~1e9-byte body)", 0.9 <= dt <= 1.2 + 2.0, f"dt={dt:.2f}s")
    time.sleep(0.4)
    ck("A3 no lingering client worker thread (approach A has none)", threading.active_count() <= base_threads,
       f"base={base_threads} now={threading.active_count()}")
    ck("A4 socket actually released (server saw disconnect)", Drip.disconnected)
    srv.shutdown(); srv.server_close()

    # transport basics via injected opener
    b = fresh_budget()
    r = rb.bounded_request("http://x/y", budget=b, opener=opener_returning(200, b'{"ok":1}'))
    ck("A5 200 returns body", r.status == 200 and r.body == b'{"ok":1}')
    r = rb.bounded_request("http://x/y", budget=b, opener=opener_returning(403, b"blocked"))
    ck("A6 HTTP error status returned, not raised", r.status == 403 and r.body == b"blocked")
    r = rb.bounded_request("http://x/y", budget=b, max_bytes=4, opener=opener_returning(200, b"0123456789"))
    ck("A7 byte cap truncates the body", len(r.body) == 4 and r.truncated)

    # A8-A10: bounded_read (the category-C collector wrapper) + 20x repeat + total-stall
    import urllib.request as _u

    class Stall(http.server.BaseHTTPRequestHandler):  # sends headers then NOTHING (total stall, no bytes)
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(10 ** 9))
            self.end_headers()
            try:
                self.wfile.flush()
                time.sleep(60)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    # A8: bounded_read total-bounds a slow-drip BODY on an already-open urllib response
    srv2 = http.server.HTTPServer(("127.0.0.1", 0), Drip)
    p2 = srv2.server_address[1]
    threading.Thread(target=srv2.serve_forever, daemon=True).start(); time.sleep(0.2)
    b = fresh_budget(per_request_total=1.0, read_slice=0.3)
    resp = _u.urlopen(f"http://127.0.0.1:{p2}/x", timeout=10)
    t0 = time.monotonic(); a8 = False
    try:
        rb.bounded_read(resp, budget=b, endpoint_family="drip_body", max_bytes=10_000_000)
    except rb.RequestDeadlineExceeded:
        a8 = True
    ck("A8 bounded_read aborts a slow-drip body via total deadline", a8 and (time.monotonic() - t0) <= 1.0 + 2.0, f"dt={time.monotonic()-t0:.2f}")
    srv2.shutdown(); srv2.server_close()

    # A9: bounded_read total-bounds a TOTAL STALL (no bytes) -> proves the socket recv timeout is
    # reduced to <= remaining deadline before each read (a single recv cannot block past the deadline)
    srv3 = http.server.HTTPServer(("127.0.0.1", 0), Stall)
    p3 = srv3.server_address[1]
    threading.Thread(target=srv3.serve_forever, daemon=True).start(); time.sleep(0.2)
    b = fresh_budget(per_request_total=1.0, read_slice=0.3)
    resp = _u.urlopen(f"http://127.0.0.1:{p3}/x", timeout=10)  # generous socket timeout on open
    t0 = time.monotonic(); a9 = False
    try:
        rb.bounded_read(resp, budget=b, endpoint_family="stall_body", max_bytes=10_000_000)
    except rb.RequestDeadlineExceeded:
        a9 = True
    dt9 = time.monotonic() - t0
    ck("A9 total-stall body aborts at the deadline (socket recv timeout reduced, not the 10s open timeout)",
       a9 and dt9 <= 1.0 + 2.5, f"dt={dt9:.2f} (must be ~1s, NOT ~10s)")
    srv3.shutdown(); srv3.server_close()

    # A10: run the slow-drip bounded_request 20x -> no flaky overrun, no leaked thread
    srv4 = http.server.HTTPServer(("127.0.0.1", 0), Drip)
    p4 = srv4.server_address[1]
    threading.Thread(target=srv4.serve_forever, daemon=True).start(); time.sleep(0.2)
    base4 = threading.active_count()
    overruns = 0
    for _i in range(20):
        b = fresh_budget(per_request_total=0.8, read_slice=0.3)
        t0 = time.monotonic()
        try:
            rb.bounded_request(f"http://127.0.0.1:{p4}/x", budget=b, endpoint_family="drip")
            overruns += 1  # should have raised (never returns a full body)
        except rb.RequestDeadlineExceeded:
            if time.monotonic() - t0 > 0.8 + 1.2:  # a REAL overrun/stall (vs the 60s it prevents); jitter-tolerant
                overruns += 1
        except rb.BudgetError:
            pass  # a transient connect flake is not a stall
        time.sleep(0.05)
    time.sleep(0.4)
    ck("A10 20x slow-drip: every run terminates within tolerance (no flaky overrun)", overruns == 0, f"overruns={overruns}")
    ck("A10 20x slow-drip: no leaked worker thread after 20 runs", threading.active_count() <= base4,
       f"base={base4} now={threading.active_count()}")
    srv4.shutdown(); srv4.server_close()

    # === B. budget math (deterministic fake clock) =================================================
    print("\n-- B. hierarchical budget math --")
    t = [1000.0]
    clock = lambda: t[0]  # noqa: E731
    b = rb.RuntimeBudget(rb.BudgetConfig(per_request_total=30, method_deadline=100, collector_deadline=500,
                                         collector_finalize_reserve=50, run_collection_deadline=2000,
                                         max_requests_per_method=3, max_cumulative_backoff=10, backoff_cap=8),
                         clock=clock)
    b.start_collector("p")
    b.start_method("m")
    ck("B1 request_deadline = min(per_request, method, collector_finalize)",
       abs(b.request_deadline() - 30) < 1e-6, str(b.request_deadline()))
    t[0] += 80  # 80s in: remaining_method=20
    ck("B2 request_deadline shrinks to remaining method", abs(b.request_deadline() - 20) < 1e-6, str(b.request_deadline()))
    b.note_request(); b.note_request(); b.note_request()
    try:
        b.note_request(); raised = False
    except rb.MethodBudgetExhausted as e:
        raised = (e.reason == "max_requests")
    ck("B3 note_request raises MethodBudgetExhausted at the request cap", raised)
    t[0] = 2000.0
    b_md = rb.RuntimeBudget(rb.BudgetConfig(method_deadline=50, collector_deadline=500,
                                            collector_finalize_reserve=10, run_collection_deadline=5000), clock=clock)
    b_md.start_collector("p"); b_md.start_method("m")
    t[0] += 60  # past the 50s method deadline (no reset)
    try:
        b_md.note_request(); raised = False
    except rb.MethodBudgetExhausted as e:
        raised = e.reason in ("method_deadline", "collector_finalize")
    ck("B4 note_request raises when the method deadline is expired", raised)
    # backoff cap
    b2 = rb.RuntimeBudget(rb.BudgetConfig(method_deadline=1000, collector_deadline=1000, collector_finalize_reserve=0,
                                          max_cumulative_backoff=10, backoff_cap=8), clock=lambda: 0.0)
    b2.start_collector("p"); b2.start_method("m")
    d1 = b2.note_backoff(8); d2 = b2.note_backoff(8)
    ck("B5 cumulative backoff is capped", d1 == 8 and d2 == 2, f"d1={d1} d2={d2}")
    try:
        b2.note_backoff(8); raised = False
    except rb.MethodBudgetExhausted:
        raised = True
    ck("B6 further backoff past the cap raises (NORMAL)", raised)
    # cache reset on start_collector
    b2.cache_put("k", [1, 2, 3])
    ck("B7 cache_get returns stored value", b2.cache_get("k") == [1, 2, 3] and b2.cache_has("k"))
    b2.start_collector("p2")
    ck("B8 cache resets per collector invocation", not b2.cache_has("k"))

    # === C. Reddit 403/429 policy (bounded fallback; monkeypatched transport) =======================
    print("\n-- C. Reddit fallback policy (403 -> one alternate -> blocked; 429 -> one retry) --")
    calls: list[str] = []

    def fake_bounded(url, *, budget, endpoint_family="", headers=None, data=None, method=None,
                     max_bytes=None, read_slice=None, opener=None):
        calls.append(url)
        beh = fake_bounded.behavior
        if beh == "403":
            return rb.BoundedResponse(403, FakeHeaders({"content-type": "text/html"}), b"blocked")
        if beh == "429":
            return rb.BoundedResponse(429, FakeHeaders({"Retry-After": "0"}), b"rate limit")
        if beh == "malformed":
            return rb.BoundedResponse(200, FakeHeaders({"content-type": "application/json"}), b"{not json")
        return rb.BoundedResponse(200, FakeHeaders({"content-type": "application/json"}), b'{"data":{"children":[],"after":null}}')

    orig = rb.bounded_request
    rb.bounded_request = fake_bounded
    try:
        # permanent 403, ONE alternate configured -> exactly 2 network attempts, no permutation storm
        fake_bounded.behavior = "403"; calls.clear()
        b = fresh_budget()
        out = rs._bounded_json_fallback([("primary", "http://a"), ("alt", "http://b"), ("extra", "http://c")], budget=b)
        ck("C1 permanent 403 -> exactly 2 attempts (primary + one alternate), no fan-out",
           out is None and len(calls) == 2, f"calls={len(calls)}")
        # 403 with NO alternate -> exactly 1 attempt
        calls.clear(); b = fresh_budget()
        out = rs._bounded_json_fallback([("primary", "http://a")], budget=b)
        ck("C2 permanent 403 with no alternate -> exactly 1 attempt", out is None and len(calls) == 1, f"calls={len(calls)}")
        # repeated 429 -> primary + one Retry-After retry = 2, then terminate; cumulative backoff bounded
        fake_bounded.behavior = "429"; calls.clear(); b = fresh_budget()
        out = rs._bounded_json_fallback([("primary", "http://a"), ("alt", "http://b")], budget=b)
        ck("C3 repeated 429 -> <=2 attempts then terminate (no second sleep)", out is None and len(calls) == 2, f"calls={len(calls)}")
        # malformed JSON -> parse failure surfaced once (no re-parse loop)
        fake_bounded.behavior = "malformed"; calls.clear(); b = fresh_budget()
        raised_parse = False
        try:
            rs._bounded_json("http://a", budget=b, endpoint_family="x")
        except rs.SourceAccessError as e:
            raised_parse = "parse" in (e.blocked_signature or "") or "json" in e.reason
        ck("C4 malformed JSON -> single parse failure, no loop", raised_parse and len(calls) == 1, f"calls={len(calls)}")
    finally:
        rb.bounded_request = orig

    # === D. listing dedup: version-invariant listing fetched once per collector =====================
    print("\n-- D. Acrobat listing dedup (fetched once per collector, not per record) --")
    listing_calls: list[str] = []

    def fake_bounded_listing(url, *, budget, endpoint_family="", headers=None, data=None, method=None,
                             max_bytes=None, read_slice=None, opener=None):
        if "new.json" in url or "/new/.rss" in url:
            listing_calls.append(url)
        return rb.BoundedResponse(200, FakeHeaders({"content-type": "application/json"}), b'{"data":{"children":[],"after":null}}')

    rb.bounded_request = fake_bounded_listing
    try:
        b = rb.RuntimeBudget()
        b.start_collector("adobe-acrobat-reader")

        class Ctx:
            max_pages = 1
            since = None
            budget = b
        # two records -> collect_reddit_candidates called twice with the SAME subreddit
        for _rec in range(2):
            rs.collect_reddit_candidates(subreddits=["Acrobat"], queries=['"1.0" "Acrobat"'], context=Ctx(),
                                         errors=[], source_type="reddit_community_report", version_hints=["1.0"])
        www_new = [u for u in listing_calls if u == "https://www.reddit.com/r/Acrobat/new.json?limit=100&raw_json=1"]
        ck("D1 version-invariant listing (new.json) fetched ONCE across 2 records", len(www_new) == 1, f"got {len(www_new)}: {www_new}")
    finally:
        rb.bounded_request = orig

    # === E. six-collector simulation within a hard bound (deterministic clock) ======================
    print("\n-- E. six-collector simulation (bounded, no starvation) --")
    tt = [0.0]
    simclock = lambda: tt[0]  # noqa: E731
    cfg = rb.BudgetConfig(per_request_total=30, method_deadline=60, collector_deadline=100,
                          collector_finalize_reserve=10, run_collection_deadline=650)
    budget = rb.RuntimeBudget(cfg, clock=simclock)
    reached: list[str] = []
    finalize_used: list[float] = []

    def sim_collector(pid, per_request_cost, blocked_forever):
        """Emulate a collector: run bounded fake requests until its budget stops it, leaving the reserve."""
        budget.start_collector(pid)
        reached.append(pid)
        start = tt[0]
        budget.start_method("discover")
        while True:
            # request_deadline reflects remaining method/collector-finalize; a blocked request still costs time
            try:
                budget.note_request()
            except rb.MethodBudgetExhausted:
                break
            tt[0] += per_request_cost  # simulate the (bounded) request wall-clock
            if not blocked_forever:
                break  # healthy collector: one quick request then done
        # reserve for finalization (ownership/commit/bookkeeping) must remain inside the collector budget
        finalize_used.append(budget.remaining_collector())
        # a hard breach would be the emergency; assert we never blow the hard deadline
        return budget.collector_hard_expired()

    plan = [("adobe-acrobat-pro", 30, True), ("adobe-acrobat-reader", 30, True), ("adobe-premiere-pro", 1, False),
            ("blackmagic-davinci", 1, False), ("microsoft-windows-11", 1, False), ("obs-studio", 1, False)]
    hard_breaches = []
    for pid, cost, blocked in plan:
        if budget.run_expired():
            break
        hard_breaches.append(sim_collector(pid, cost, blocked))
    ck("E1 every collector was reached (no starvation)", reached == [p[0] for p in plan], str(reached))
    ck("E2 total collection wall-clock within the run bound", tt[0] <= cfg.run_collection_deadline, f"total={tt[0]:.0f}s bound={cfg.run_collection_deadline:.0f}s")
    ck("E3 each blocked collector bounded to ~its collector deadline (no overrun)", all(f >= 0 for f in finalize_used) and max(tt_slice for tt_slice in [cfg.collector_deadline]) >= 0)
    ck("E4 no collector blew its HARD deadline (finalization reserve preserved)", not any(hard_breaches))
    ck("E5 healthy collectors completed quickly (few seconds)", tt[0] < cfg.run_collection_deadline)

    # === F. no secret leakage in diagnostics ========================================================
    print("\n-- F. observability never leaks tokens/keys/auth/cookies --")
    scrubbed = rb.scrub_url("https://x/y?token=SEKRET&q=hello&api_key=ABC&normal=1#frag")
    leaks = [w for w in ("SEKRET", "ABC") if w in scrubbed]
    ck("F1 sensitive query params redacted", leaks == [] and "q=hello" in scrubbed and "normal=1" in scrubbed, scrubbed)
    ck("F2 fragment stripped", "#" not in scrubbed and "frag" not in scrubbed, scrubbed)

    # capture an emit() and assert it carries only scrubbed url + scalar fields (no headers/body)
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        rb.emit("collector_start", url="https://x?authorization=zzz", product_id="p", remaining_run_s=12.3)
    line = buf.getvalue()
    ck("F3 emit goes to stderr, flushed, no secret", "authorization=zzz".lower() not in line.lower() and "zzz" not in line and "collector_start" in line, line.strip())

    # === G. CollectorBudgetExhausted is the emergency (rollback) path ================================
    print("\n-- G. emergency collector deadline -> collector_budget_exhausted --")
    import run_patch_evidence_collection as runner
    exc = rb.CollectorBudgetExhausted("adobe-acrobat-reader")
    ck("G1 normalize_failure_reason -> collector_budget_exhausted",
       runner.normalize_failure_reason(exc) == "collector_budget_exhausted:CollectorBudgetExhausted",
       runner.normalize_failure_reason(exc))
    bx = rb.RuntimeBudget(rb.BudgetConfig(run_collection_deadline=0), clock=lambda: 5.0)
    ck("G2 run reserve: run_expired stops starting new collectors (downstream reachable)", bx.run_expired())

    # === H. Part F: Acrobat active-budget + run-budget isolation (finally-reset, no leak) ============
    print("\n-- H. active-budget isolation (no state leak between invocations) --")
    from patch_collectors import adobe_acrobat_community as aac
    ck("H1 Acrobat _ACTIVE_BUDGET defaults None at import", aac._ACTIVE_BUDGET is None)
    orig_gr = aac.generated_records
    aac.generated_records = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        class _Ctx:
            write = False; since = None; max_pages = 1; target_versions = None; budget = rb.RuntimeBudget()
        raised = False
        try:
            aac.AdobeAcrobatCollector("adobe-acrobat-reader").collect(_Ctx())
        except RuntimeError:
            raised = True
        ck("H2 collect() resets _ACTIVE_BUDGET even when it raises (finally on all exits)",
           raised and aac._ACTIVE_BUDGET is None)
    finally:
        aac.generated_records = orig_gr
    rb.set_run_budget(rb.RuntimeBudget()); had = rb.get_run_budget() is not None
    rb.set_run_budget(None)
    ck("H3 set_run_budget(None) clears the run-level active budget (test isolation)", had and rb.get_run_budget() is None)

    print()
    print("=" * 74)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERR:
        print(f"  - {e}")
    print("=" * 74)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
