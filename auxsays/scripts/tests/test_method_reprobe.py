#!/usr/bin/env python3
"""Bounded automatic re-probe of switched-off methods, against a SIMULATED source.

WHAT THIS GUARDS.

  P. POLICY. A source the owner or its terms closed is never re-probed: Reddit, Microsoft Learn Q&A,
     Adobe, the paid search API. The floor is evaluated before any declaration, so declaring such a
     method `allowed` opens nothing; and the runner never sends one of those hosts a request.
  S. THE PROBE. robots.txt is read first. A refusal is a property of the RESPONSE: a 403, a challenge
     page served at 200, a robots disallow, a page without the expected marker are all not-recovered.
     Never more than two requests.
  B. BOUNDS. A hard per-run request cap, a cooldown that doubles after each refusal up to a ceiling,
     and nothing at all in a dry run.
  R. RETURN TO SERVICE. A `recovered` record returns the method as a bounded fallback; the method's
     own fresh health rows keep it there or take it out again. Shown through the real DaVinci
     collector path with its transports stubbed.
  W. ONE STORE. Probe records live in the health file, written by the health writer; method rows and
     probe records never erase each other, and the validator refuses a record for a closed source.
  F. WORKFLOW. The scheduled collection workflow runs the step before collection, and cannot be
     failed by it.

Offline and deterministic: every response is injected; the only clock is the `now` passed in.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_method_reprobe.py
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import traceback
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import reprobe_methods as rp  # noqa: E402
import validate_evidence_method_health as vh  # noqa: E402
from lib import acquisition_methods as am  # noqa: E402
from lib import method_routing as mr  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import davinci as dv  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

T0 = datetime(2026, 11, 24, 7, 0, tzinfo=timezone.utc)
PID, MID = "blackmagic-davinci", "vendor_forum_search"
ROBOTS_OK = "User-agent: *\nDisallow: /admin/\n"
ROBOTS_BLOCK = "User-agent: *\nDisallow: /\n"
FORUM_PAGE = '<html><body><a href="./viewtopic.php?f=21&t=1">DaVinci Resolve 21.2 crash</a></body></html>'
CHALLENGE = '<html><head><script>window.gokuProps = {};</script></head><body>awsWaf</body></html>'
LOGIN_WALL = "<html><body><form>Please sign in to continue</form></body></html>"


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


class Source:
    """A simulated source: a scripted (status, headers, body) per URL kind, and a log of every
    request it was sent."""

    def __init__(self, robots: tuple[int, str], content: tuple[int, str]) -> None:
        self.robots, self.content = robots, content
        self.log: list[str] = []

    def __call__(self, url: str) -> tuple[int, dict[str, str], str]:
        self.log.append(url)
        status, body = self.robots if url.endswith("/robots.txt") else self.content
        return status, {}, body

    def hosts(self) -> set[str]:
        return {urllib.parse.urlsplit(u).netloc for u in self.log}


def no_sleep(_seconds: float) -> None:
    return None


def disabled_row(method_id: str, last_run: str = "2026-11-24T00:40:44Z", status: str = "disabled",
                 version: str = "21.2") -> dict:
    return base.method_health_row(
        product_id=PID, update_version=version, method_id=method_id, source_type="blackmagic_forum",
        status=status, candidates_found=0, accepted_reports=0, rejected_reports=0,
        blocked_reason="blackmagic_forum_refuses_automated_requests" if status != "success" else None,
        last_run=last_run, notes="fixture")


def fresh_health(td: str) -> Path:
    path = Path(td) / "evidence_method_health.yml"
    base.write_method_health_file([disabled_row(MID), disabled_row("known_watchlist"),
                                   disabled_row("reddit_search"), disabled_row("web_search")], path, probes=[])
    return path


def policy_checks() -> None:
    print("-- P. closed sources are never re-probed")
    closed = {
        "reddit_search": "reddit", "reddit_listing_enumeration": "reddit", "reddit_feed_fallback": "reddit",
        "learn_qna_search_rss": "learn", "learn_qna_powerpoint_tags": "learn",
        "learn_qna_question_hydration": "learn", "adobe_community_search": "adobe",
        "adobe_community_bug_tab_index": "adobe", "adobe_community_algolia_search": "adobe",
        "wayback_snapshot_recheck": "adobe", "adobe_helpx_release_history_direct_fetch": "adobe",
        "brave_search_api": "", "creativecow_brave_search": "paid",
    }
    wrong = {m: am.reprobe_refusal(m) for m, token in closed.items()
             if not am.reprobe_refusal(m) or (token and token not in am.reprobe_refusal(m))}
    check("P1 Reddit, Microsoft Learn Q&A, Adobe and paid-search methods are refused, each for its own reason",
          not wrong and len(closed) == 13, str(wrong))
    check("P2 a refused method has no probe at all", all(am.reprobe_spec(m) is None for m in closed))

    full_spec = {"policy": "allowed", "basis": "edited", "robots_url": "https://example.org/robots.txt",
                 "url": "https://example.org/listing", "expect_any": ["x"], "max_requests": 2,
                 "cooldown_hours": 168}
    original = dict(am.REPROBE)
    try:
        for method_id in closed:
            am.REPROBE[method_id] = dict(full_spec)
        still = [m for m in closed if not am.reprobe_refusal(m) or am.reprobe_spec(m) is not None]
        check("P3 declaring a closed method `allowed`, with a complete probe, opens nothing (floor first)",
              not still, str(still))
        am.REPROBE[MID] = dict(am.REPROBE[MID], url="https://www.reddit.com/r/davinciresolve/new")
        check("P4 an allowed method whose probe URL points at a closed source is refused",
              "reddit" in am.reprobe_refusal(MID), am.reprobe_refusal(MID))
        am.REPROBE[MID] = dict(original[MID], max_requests=50, cooldown_hours=1)
        spec = am.reprobe_spec(MID)
        check("P5 a declaration cannot raise the request cap or shorten the cooldown below the floor",
              spec["max_requests"] == am.REPROBE_MAX_REQUESTS_PER_METHOD == 2
              and spec["cooldown_hours"] == am.REPROBE_COOLDOWN_HOURS_DEFAULT == 168, str(spec))
    finally:
        am.REPROBE.clear()
        am.REPROBE.update(original)
    check("P6 an id the registry does not know is refused", am.reprobe_refusal("made_up_method") == "not_in_registry")
    check("P7 a method with no declaration is refused (fail closed)",
          am.reprobe_refusal("nvidia_forum_default_views") == "no_reprobe_declared")
    allowed = sorted(m["method_id"] for m in am.METHODS if not am.reprobe_refusal(m["method_id"]))
    check("P8 exactly one method is re-probable today: the Blackmagic forum search",
          allowed == [MID], str(allowed))
    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        source = Source((200, ROBOTS_OK), (200, FORUM_PAGE))
        summary = rp.run(health_path=path, now=T0, write=True, max_requests=4, fetch=source, sleep=no_sleep)
        skipped = {(s["product_id"], s["method_id"]): s["reason"] for s in summary["skipped"]}
        check("P9 a run asks only the allowed source; every closed method is listed as skipped with its reason",
              source.hosts() == {"forum.blackmagicdesign.com"}
              and "reddit" in skipped[(PID, "reddit_search")]
              and "reddit" in skipped[("adobe-premiere-pro", "reddit_search")]
              and "adobe" in skipped[("adobe-premiere-pro", "adobe_community_search")]
              and len(skipped) >= 10, f"{source.hosts()} {len(skipped)}")


def probe_checks() -> None:
    print("-- S. the probe: robots.txt first; a refusal is a property of the response")
    spec = am.reprobe_spec(MID)
    cases = [
        ("S1 robots.txt refused with 403: still refused after ONE request",
         Source((403, "<h1>403 Forbidden</h1>"), (200, FORUM_PAGE)), "still_refused", "http_403", 1),
        ("S2 a challenge page served at HTTP 200 on robots.txt is a refusal, not an answer",
         Source((200, CHALLENGE), (200, FORUM_PAGE)), "still_refused", "access_challenge", 1),
        ("S3 robots.txt disallows the listing: stop there, the content is never requested",
         Source((200, ROBOTS_BLOCK), (200, FORUM_PAGE)), "still_refused", "robots_disallow", 1),
        ("S4 robots allows, the listing is a challenge page at 200: still refused",
         Source((200, ROBOTS_OK), (200, CHALLENGE)), "still_refused", "access_challenge", 2),
        ("S5 robots allows, the listing answers 429: still refused",
         Source((200, ROBOTS_OK), (429, "slow down")), "still_refused", "http_429", 2),
        ("S6 a login wall at 200 is not a recovery: the expected marker is missing",
         Source((200, ROBOTS_OK), (200, LOGIN_WALL)), "inconclusive", "expected_marker_missing", 2),
        ("S7 no HTTP answer at all is inconclusive, never a recovery",
         Source((0, ""), (200, FORUM_PAGE)), "inconclusive", "network_error", 1),
        ("S8 robots allows and the listing returns forum content: recovered",
         Source((200, ROBOTS_OK), (200, FORUM_PAGE)), "recovered", "content_answered", 2),
        ("S9 no robots.txt (404) disallows nothing; content decides",
         Source((404, ""), (200, FORUM_PAGE)), "recovered", "content_answered", 2),
    ]
    for label, source, result, reason, requests in cases:
        outcome = rp.run_probe(spec, source, sleep=no_sleep)
        check(label, (outcome["result"], outcome["reason"], outcome["requests"], len(source.log))
              == (result, reason, requests, requests), f"{outcome} log={source.log}")
    source = Source((200, ROBOTS_OK), (200, FORUM_PAGE))
    rp.run_probe(spec, source, sleep=no_sleep)
    check("S10 the first request of every probe is robots.txt, the second the declared listing",
          source.log == [spec["robots_url"], spec["url"]], str(source.log))
    one = dict(spec, max_requests=1)
    source = Source((200, ROBOTS_OK), (200, FORUM_PAGE))
    outcome = rp.run_probe(one, source, sleep=no_sleep)
    check("S11 with a one-request budget the probe stops after robots.txt and claims nothing",
          outcome["result"] == "inconclusive" and len(source.log) == 1, str(outcome))
    slept: list[float] = []
    rp.run_probe(spec, Source((200, ROBOTS_OK), (200, FORUM_PAGE)), sleep=slept.append)
    check("S12 the two requests of a probe are at least one second apart", slept == [rp.REQUEST_SPACING_SECONDS]
          and rp.REQUEST_SPACING_SECONDS >= 1.0, str(slept))


def bounds_checks() -> None:
    print("-- B. cooldown, back-off and the hard per-run cap")
    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        before = path.read_bytes()
        source = Source((403, "denied"), (200, FORUM_PAGE))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = rp.main(["--dry-run", "--health-path", str(path), "--now", "2026-11-24T07:00:00Z"])
        dry = json.loads(buffer.getvalue())
        check("B1 a dry run names what is due, makes no request and writes nothing",
              rc == 0 and dry["requests_made"] == 0 and path.read_bytes() == before
              and [p["method_id"] for p in dry["probed"]] == [MID] and dry["probed"][0]["result"] == "would_probe",
              str(dry["probed"]))

        capped = rp.run(health_path=path, now=T0, write=True, max_requests=1, fetch=source, sleep=no_sleep)
        check("B2 a run cap smaller than the probe needs: nothing is sent, the method is skipped as run_cap",
              capped["requests_made"] == 0 and not source.log
              and any(s["method_id"] == MID and s["reason"] == "run_cap" for s in capped["skipped"]), str(capped))
        huge = rp.run(health_path=path, now=T0, write=False, max_requests=10_000, fetch=source, sleep=no_sleep)
        check("B3 a requested cap above the ceiling is clamped to the ceiling",
              huge["request_cap"] == mr.MAX_REPROBE_REQUESTS_PER_RUN == 4, str(huge["request_cap"]))

        first = rp.run(health_path=path, now=T0, write=True, max_requests=4, fetch=source, sleep=no_sleep)
        record = base.load_method_probes(path)[0]
        check("B4 a refused probe is recorded: result, reason, one request, a week's cooldown",
              first["requests_made"] == 1 and record["result"] == "still_refused" and record["reason"] == "http_403"
              and record["consecutive_refusals"] == 1 and record["requests"] == 1 and record["total_requests"] == 1
              and record["next_probe_after"] == mr.format_time(T0 + timedelta(hours=168)), str(record))

        source.log.clear()
        early = rp.run(health_path=path, now=T0 + timedelta(hours=6), write=True, max_requests=4,
                       fetch=source, sleep=no_sleep)
        check("B5 the next scheduled run, six hours later, is inside the cooldown: no request",
              early["requests_made"] == 0 and not source.log
              and any(s["method_id"] == MID and s["reason"] == "cooldown" for s in early["skipped"]), str(early))
        sent = 0
        for cycle in range(1, 28):                      # a week of 6-hourly scheduled runs
            sent += rp.run(health_path=path, now=T0 + timedelta(hours=6 * cycle), write=True, max_requests=4,
                           fetch=source, sleep=no_sleep)["requests_made"]
        check("B6 across a week of 6-hourly runs the refusing source is asked nothing more",
              sent == 0 and not source.log, f"sent={sent}")

        second = rp.run(health_path=path, now=T0 + timedelta(hours=169), write=True, max_requests=4,
                        fetch=source, sleep=no_sleep)
        record = base.load_method_probes(path)[0]
        check("B7 after the cooldown it is probed again; a second refusal doubles the wait to two weeks",
              second["requests_made"] == 1 and record["consecutive_refusals"] == 2 and record["total_requests"] == 2
              and record["next_probe_after"] == mr.format_time(T0 + timedelta(hours=169 + 336)), str(record))
    check("B8 the back-off doubles and stops at the 30-day ceiling",
          [mr.probe_cooldown_hours(168, n, 720) for n in (0, 1, 2, 3, 4, 9)] == [168, 168, 336, 672, 720, 720])
    year = 0
    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        source = Source((403, "denied"), (200, FORUM_PAGE))
        for cycle in range(0, 4 * 365):                 # a year of 6-hourly scheduled runs
            year += rp.run(health_path=path, now=T0 + timedelta(hours=6 * cycle), write=True, max_requests=4,
                           fetch=source, sleep=no_sleep)["requests_made"]
    check("B9 a source that refuses for a whole year receives at most 15 requests in that year",
          0 < year <= 15, f"requests in a year: {year}")


def return_to_service_checks() -> None:
    print("-- R. a recovered method returns as a bounded fallback; its own rows keep or remove it")
    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        check("R1 before any probe the method is off and the collector's returned set is empty",
              dv.returned_to_service(path) == frozenset()
              and MID in mr.effective_plan(PID, base.load_method_health(path), base.load_method_probes(path),
                                           reprobe_refusal=am.reprobe_refusal)["disabled"])
        source = Source((200, ROBOTS_OK), (200, FORUM_PAGE))
        done = rp.run(health_path=path, now=T0, write=True, max_requests=4, fetch=source, sleep=no_sleep)
        record = base.load_method_probes(path)[0]
        check("R2 the simulated source recovers: the probe records `recovered` in two requests",
              done["requests_made"] == 2 and record["result"] == "recovered" and record["consecutive_refusals"] == 0,
              str(record))
        plan = mr.effective_plan(PID, base.load_method_health(path), base.load_method_probes(path),
                                 reprobe_refusal=am.reprobe_refusal)
        check("R3 routing returns it as a FALLBACK (never a primary) and removes it from `disabled`",
              plan["fallback"] == [MID] and MID not in plan["disabled"] and plan["primary"] == ["creative_cow_forum_search"]
              and plan["returned_to_service"] == [MID], str(plan))
        check("R4 the DaVinci collector reads the same answer", dv.returned_to_service(path) == frozenset({MID}))
        again = rp.run(health_path=path, now=T0 + timedelta(hours=400), write=True, max_requests=4,
                       fetch=source, sleep=no_sleep)
        check("R5 a method that is back in service is not probed again",
              again["requests_made"] == 0
              and any(s["method_id"] == MID and s["reason"] == "in_service" for s in again["skipped"]), str(again))

        # The real collector path for one record, transports stubbed.
        calls = {"vendor": 0, "cow": 0}
        saved = (dv.vendor_forum_search_candidates, dv.creative_cow_forum_search_candidates, dv.web_search_candidates)

        def vendor(record, context, errors):
            calls["vendor"] += 1
            return []

        def cow(record, context, errors):
            calls["cow"] += 1
            return []

        dv.vendor_forum_search_candidates, dv.creative_cow_forum_search_candidates = vendor, cow
        dv.web_search_candidates = lambda record, context, errors: []
        try:
            rec = base.PatchRecord(PID, "21.2", Path("auxsays/updates/generated/x.md"),
                                   "2026-10-01T00:00:00Z", "current", "DaVinci Resolve")
            ctx = base.CollectorContext(write=False, since=None, max_pages=1)
            _a, _r, off = dv.collect_for_record(rec, ctx)
            off_row = next(h for h in off if h["method_id"] == MID)
            check("R6 without a recovery the collector does not call the forum adapter and writes `disabled`",
                  calls["vendor"] == 0 and off_row["status"] == "disabled", str(off_row["status"]))
            _a, _r, on = dv.collect_for_record(rec, ctx, returned=dv.returned_to_service(path))
            on_row = next(h for h in on if h["method_id"] == MID)
            check("R7 with the recovery the collector RUNS it and the method writes its own fresh row",
                  calls["vendor"] == 1 and on_row["status"] != "disabled" and on_row["last_run"], str(on_row))
            watch = next(h for h in on if h["method_id"] == "known_watchlist")
            check("R8 the other refused method, which policy does not allow back, stays off",
                  watch["status"] == "disabled")
        finally:
            dv.vendor_forum_search_candidates, dv.creative_cow_forum_search_candidates, dv.web_search_candidates = saved

        # Its own next rows decide. First a healthy row, then a refused one.
        later = mr.format_time(T0 + timedelta(hours=6))
        base.upsert_method_health([disabled_row(MID, last_run=later, status="no_results")], path)
        check("R9 an answering row after the probe keeps it in service", dv.returned_to_service(path) == frozenset({MID}))
        check("R10 the method rows were upserted without erasing the probe record",
              len(base.load_method_probes(path)) == 1 and base.load_method_probes(path)[0]["result"] == "recovered")
        relapse = mr.format_time(T0 + timedelta(hours=12))
        base.upsert_method_health([disabled_row(MID, last_run=relapse, status="blocked")], path)
        check("R11 when its own rows since the probe are all refused it is out of service again",
              dv.returned_to_service(path) == frozenset()
              and MID in mr.effective_plan(PID, base.load_method_health(path), base.load_method_probes(path),
                                           reprobe_refusal=am.reprobe_refusal)["disabled"])
        waiting = rp.run(health_path=path, now=T0 + timedelta(hours=18), write=True, max_requests=4,
                         fetch=source, sleep=no_sleep)
        check("R12 a relapse does not trigger an immediate re-probe: the cooldown still holds",
              waiting["requests_made"] == 0, str(waiting))
        refused = Source((403, "denied"), (200, FORUM_PAGE))
        rp.run(health_path=path, now=T0 + timedelta(hours=200), write=True, max_requests=4,
               fetch=refused, sleep=no_sleep)
        record = base.load_method_probes(path)[0]
        check("R13 the probe after a relapse counts the relapse: the wait is already doubled",
              record["result"] == "still_refused" and record["consecutive_refusals"] == 2
              and record["next_probe_after"] == mr.format_time(T0 + timedelta(hours=200 + 336)), str(record))

    forged = [{"product_id": PID, "method_id": "reddit_search", "result": "recovered",
               "probed_at": mr.format_time(T0), "next_probe_after": mr.format_time(T0)},
              {"product_id": PID, "method_id": "known_watchlist", "result": "recovered",
               "probed_at": mr.format_time(T0), "next_probe_after": mr.format_time(T0)}]
    plan = mr.effective_plan(PID, [], forged, reprobe_refusal=am.reprobe_refusal)
    check("R14 a `recovered` record for a closed method, however it got there, returns nothing to service",
          plan["fallback"] == [] and plan["returned_to_service"] == []
          and {"reddit_search", "known_watchlist"} <= set(plan["disabled"]), str(plan))
    check("R15 without the registry policy passed in, nothing is ever returned",
          mr.effective_plan(PID, [], forged)["returned_to_service"] == [])


def store_checks() -> None:
    print("-- W. one store: the health file holds both, and neither write erases the other")
    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        text_before = path.read_text(encoding="utf-8")
        check("W1 a file with no probe record has no `probes` key (its bytes are what they always were)",
              "probes" not in yaml.safe_load(text_before))
        rp.run(health_path=path, now=T0, write=True, max_requests=4,
               fetch=Source((403, "denied"), (200, FORUM_PAGE)), sleep=no_sleep)
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        check("W2 the probe record is written into the SAME file, and the method rows are unchanged",
              payload["methods"] == yaml.safe_load(text_before)["methods"] and len(payload["probes"]) == 1)
        check("W3 a probe record holds no page content: only the declared small fields",
              set(payload["probes"][0]) <= set(base.METHOD_PROBE_FIELDS), str(sorted(payload["probes"][0])))
        with contextlib.redirect_stdout(io.StringIO()):
            ok = vh.validate(path, check_registry=True)
        check("W4 the validator accepts the file with its probe record", ok == 0)
        payload["probes"].append({"product_id": PID, "method_id": "reddit_search", "result": "recovered",
                                  "probed_at": "2026-11-24T07:00:00Z", "next_probe_after": "2026-12-01T07:00:00Z",
                                  "consecutive_refusals": 0, "requests": 1, "total_requests": 1, "reason": "x"})
        bad = Path(td) / "bad.yml"
        bad.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            refused = vh.validate(bad, check_registry=True)
        check("W5 the validator REFUSES a probe record for a closed source (Reddit)",
              refused == 1 and "may not be re-probed" in out.getvalue(), out.getvalue()[-300:])
        payload["probes"] = [dict(payload["probes"][0], requests=3)]
        bad.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            over = vh.validate(bad, check_registry=True)
        check("W6 the validator refuses a probe record claiming more requests than the per-method cap",
              over == 1 and "cap" in out.getvalue())
    with contextlib.redirect_stdout(io.StringIO()):
        live = vh.validate(base.METHOD_HEALTH_PATH)
    check("W7 the committed health file passes the validator with the registry join on", live == 0)

    reached: list[str] = []

    def exploding(url):
        reached.append(url)
        raise RuntimeError("boom")

    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        original = rp.default_fetch
        rp.default_fetch = exploding
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = rp.main(["--write", "--health-path", str(path), "--now", "2026-11-24T07:00:00Z"])
        finally:
            rp.default_fetch = original
        check("W8 the step exits 0 whatever happens inside it (it cannot fail the collection)",
              rc == 0 and "re-probe skipped" in out.getvalue(), out.getvalue())
        check("W9 the command-line path uses the replaceable fetch (this suite cannot reach the network)",
              len(reached) == 1 and reached[0].endswith("/robots.txt"), str(reached))


def workflow_checks() -> None:
    print("-- F. the scheduled workflow runs the step, before collection, and cannot be failed by it")
    text = (_REPO / ".github" / "workflows" / "obs-evidence-collection.yml").read_text(encoding="utf-8")
    steps = re.split(r"\n      - name: ", text)
    names = [s.split("\n", 1)[0].strip() for s in steps[1:]]
    probe = next((s for s in steps if s.startswith("Re-probe switched-off sources")), "")
    check("F1 the collection workflow has the re-probe step", bool(probe), str(names[:6]))
    check("F2 it runs before the collect step",
          names.index("Re-probe switched-off sources (bounded)") < names.index("Collect patch evidence"))
    code = "\n".join(line for line in probe.splitlines() if not line.strip().startswith("#"))
    check("F3 it invokes the script in write mode, exactly once",
          code.count("python auxsays/scripts/reprobe_methods.py --write") == 1, code)
    check("F4 it cannot fail the job and is time-boxed",
          "continue-on-error: true" in code and re.search(r"timeout-minutes: [1-5]\b", code) is not None, code)
    check("F5 it is skipped on a dry-run dispatch", "github.event.inputs.dry_run != 'true'" in code)
    check("F6 the health file it writes is on the writeback allow-list, so the record reaches main",
          "--allow auxsays/_data/evidence_method_health.yml" in text
          and "--validate 'python auxsays/scripts/validate_evidence_method_health.py'" in text)
    check("F7 the script has no network client other than the injected fetch (one urlopen site)",
          (_REPO / "auxsays/scripts/reprobe_methods.py").read_text(encoding="utf-8").count("opener.open(") == 1)


def run() -> int:
    print("=" * 78)
    print("Bounded re-probe of switched-off methods (simulated source)")
    print("=" * 78)
    policy_checks()
    probe_checks()
    bounds_checks()
    return_to_service_checks()
    store_checks()
    workflow_checks()
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
