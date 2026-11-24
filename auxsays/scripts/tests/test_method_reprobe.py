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
  V. SERVICE BOUNDS (review M1). A returned method runs under the request budget, spacing and
     robots.txt check its registry entry declares. The worst case is COUNTED through the real
     DaVinci record walk over the real live records with the transport replaced: 6, 12, 20, 30
     requests a run, where the unbounded path sent 1,127.
  R. RELAPSE (review M2, S3). A recovery the real run refuses takes the method out until a NEW
     probe answers, and each relapse lengthens the wait. Shown over simulated 6-hourly cycles.
  L. LOST CYCLES (review S1). Probe state survives a cycle that never reached main.
  H. HOST PIN (review S2). The floor reads the parsed host; the rights layer is pinned alone.
  X. VISIBLE FAILURE (review S5). A crashing step is in the log, the run summary and the health file.
  W. ONE STORE. Probe records live in the health file, written by the health writer; method rows and
     probe records never erase each other, and the validator refuses a record for a closed source.
  F. WORKFLOW. The scheduled collection workflow runs the step before collection, and cannot be
     failed by it.

Offline and deterministic: every response is injected; the only clock is the `now` passed in.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_method_reprobe.py
"""
from __future__ import annotations

import contextlib
import inspect
import io
import json
import os
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
        self.agents: list[str] = []

    def __call__(self, url: str, agent: str = "") -> tuple[int, dict[str, str], str]:
        self.log.append(url)
        self.agents.append(agent)
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
        loose = dict(original[MID]["service"], ramp_requests=[500, 600, 700], max_requests_per_run=5000,
                     max_requests_per_record=400, min_spacing_seconds=0.01)
        am.REPROBE[MID] = dict(original[MID], max_requests=50, cooldown_hours=1, service=loose)
        spec = am.reprobe_spec(MID)
        check("P5 a declaration cannot raise the request cap or shorten the cooldown below the floor",
              spec["max_requests"] == am.REPROBE_MAX_REQUESTS_PER_METHOD == 2
              and spec["cooldown_hours"] == am.REPROBE_COOLDOWN_HOURS_DEFAULT == 168, str(spec))
        check("P5b nor loosen the SERVICE bounds: run budget, ramp, per-record budget and spacing are clamped",
              spec["service"]["max_requests_per_run"] == 30 and spec["service"]["ramp_requests"] == [30, 30, 30]
              and spec["service"]["max_requests_per_record"] == 6
              and spec["service"]["min_spacing_seconds"] == 2.0, str(spec["service"]))
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


class Forum:
    """The Blackmagic forum, simulated at the collector's transport (`davinci.request_text`).

    `mode` decides what it answers: `answer` (robots.txt allows, searches list 30 threads each,
    threads are forum pages), `search_refused` (robots.txt allows, every search is an AWS WAF
    challenge), `robots_disallow` (robots.txt disallows /search.php for every agent),
    `robots_own_agent` (robots.txt disallows everything for the collector's own agent token only),
    `robots_html` (an HTML page is served as robots.txt), `crawl_delay` (robots.txt asks for 7 s),
    `robots_bom` (robots.txt starts with a UTF-8 byte-order mark and disallows everything),
    `search_maintenance` (robots.txt allows, every search answers 200 with a page that is not the
    forum: a maintenance notice).
    Every request is logged; anything off the forum's host answers an empty page."""

    def __init__(self, mode: str = "answer") -> None:
        self.mode = mode
        self.log: list[str] = []

    def __call__(self, url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        if parts.netloc != "forum.blackmagicdesign.com":
            return "<html></html>"
        self.log.append(url)
        if parts.path == "/robots.txt":
            if self.mode == "robots_disallow":
                return "User-agent: *\nDisallow: /search.php\n"
            if self.mode == "robots_own_agent":
                return "User-agent: *\nDisallow: /admin/\n\nUser-agent: AUXSAYS-DaVinci-Evidence-Collector\nDisallow: /\n"
            if self.mode == "robots_html":
                return "<!DOCTYPE html><html><body>Welcome</body></html>"
            if self.mode == "crawl_delay":
                return "User-agent: *\nCrawl-delay: 7\nDisallow: /admin/\n"
            if self.mode == "robots_bom":
                return "\ufeffUser-agent: *\nDisallow: /\n"
            return ROBOTS_OK
        if parts.path == "/search.php":
            if self.mode == "search_refused":
                raise dv.SourceAccessError("http_202_aws_waf_challenge", status=202)
            if self.mode == "search_maintenance":
                return "<html><body>We are down for scheduled maintenance. Back soon.</body></html>"
            seed = sum(ord(c) for c in parts.query) % 9000
            return "<html>phpbb search.php " + " ".join(
                f'<a href="viewtopic.php?f=21&t={seed + i}">t</a>' for i in range(30)) + "</html>"
        return "<html><title>DaVinci Resolve thread</title>viewtopic.php phpbb a post</html>"

    def paths(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for url in self.log:
            path = urllib.parse.urlsplit(url).path
            counts[path] = counts.get(path, 0) + 1
        return counts


_LIVE_RECORDS: list = []


def live_records() -> list:
    """The real live DaVinci records, newest first, read once (reading them costs seconds)."""
    if not _LIVE_RECORDS:
        _LIVE_RECORDS.extend(base.newest_first(base.generated_records(PID)))
    return list(_LIVE_RECORDS)


class Lane:
    """The scheduled lane, simulated end to end and offline: the re-probe step, then the real
    DaVinci record walk over the real live records with its transport replaced by a `Forum`, then
    the health writer. `main` is the health file on main; a cycle that is `lost` runs in full but
    never reaches main, exactly like a cycle whose writeback did not push."""

    def __init__(self, td: str, *, carry: bool = True) -> None:
        self.main = Path(td) / "main.yml"
        self.work = Path(td) / "work.yml"
        self.carry = (Path(td) / "carry" / "probes.json") if carry else None
        self.records = live_records()
        base.write_method_health_file(
            [disabled_row(MID, version=r.update_version) for r in self.records], self.main, probes=[])
        self.sleeps: list[float] = []
        self.probe_log: list[str] = []
        self.agents: list[str] = []

    def cycle(self, now: datetime, forum: Forum, probe_source: "Source", *, lost: bool = False,
              step_runs: bool = True) -> dict:
        self.work.write_bytes(self.main.read_bytes())
        summary: dict = {}
        if step_runs:
            before = len(probe_source.log)
            summary = rp.run(health_path=self.work, now=now, write=True, max_requests=4, fetch=probe_source,
                             sleep=no_sleep, carry_path=self.carry)
            self.probe_log += probe_source.log[before:]
        forum_before = len(forum.log)
        saved = (dv.request_text, dv.service_sleep, dv.utc_now, dv.reddit_access_authorized)
        dv.request_text = forum
        dv.service_sleep = self.sleeps.append
        dv.utc_now = lambda: mr.format_time(now + timedelta(minutes=30))
        dv.reddit_access_authorized = lambda: False
        try:
            services = dv.return_services(self.work, now=now + timedelta(minutes=1))
            results = dv.DavinciCollector()._collect_records(
                self.records, base.CollectorContext(write=False, since=None, max_pages=1), services)
        finally:
            dv.request_text, dv.service_sleep, dv.utc_now, dv.reddit_access_authorized = saved
        rows = [h for result in results for h in result["method_health"] if h["method_id"] == MID]
        base.upsert_method_health(rows, self.work)
        if not lost:
            self.main.write_bytes(self.work.read_bytes())
        return {"summary": summary, "served": MID in services, "forum_requests": len(forum.log) - forum_before,
                "statuses": sorted({h["status"] for h in rows}),
                "attempted": sum(1 for h in rows if h["status"] != "disabled"),
                "probe": (base.load_method_probes(self.work) or [{}])[0]}


def answering_probe() -> "Source":
    return Source((200, ROBOTS_OK), (200, FORUM_PAGE))


def at(hours: float) -> datetime:
    return T0 + timedelta(hours=hours)


def service_bound_checks() -> None:
    print("-- V. M1: a returned method runs under a declared budget, spacing and robots.txt")
    spec = am.reprobe_spec(MID)
    service = spec["service"]
    check("V1 the registry declares the service bounds, and they are within the module ceilings",
          service["ramp_requests"] == [6, 12, 20] and service["max_requests_per_run"] == 30
          == am.SERVICE_MAX_REQUESTS_PER_RUN and service["max_requests_per_record"] == 6
          and service["min_spacing_seconds"] >= 2.0, str(service))
    check("V2 the declared agent IS the agent the collector sends, and the probe URL is the method's own request",
          service["user_agent"] == dv.TEXT_HEADERS["User-Agent"]
          and service["robots_agent"] in service["user_agent"]
          and spec["url"].startswith(dv.FORUM_SEARCH + "?")
          and urllib.parse.urlsplit(dv.FORUM_SEARCH).hostname == spec["host"] == am.REPROBE_HOST_PINS[MID],
          f"{service['user_agent']} / {spec['url']}")
    probe = answering_probe()
    rp.run_probe(spec, probe, sleep=no_sleep)
    check("V3 the probe asks the search endpoint, with the method's own user agent on both requests",
          [urllib.parse.urlsplit(u).path for u in probe.log] == ["/robots.txt", "/search.php"]
          and probe.agents == [service["user_agent"]] * 2, f"{probe.log} {probe.agents}")
    robots_cases = [
        ("V4 robots.txt that disallows only /search.php is a refusal (the old probe said `recovered`)",
         "User-agent: *\nDisallow: /search.php\n", "still_refused", "robots_disallow"),
        ("V5 robots.txt that disallows only /viewtopic.php is a refusal: the method reads threads too",
         "User-agent: *\nDisallow: /viewtopic.php\n", "still_refused", "robots_disallow"),
        ("V6 robots.txt that addresses the collector's OWN agent token is obeyed",
         "User-agent: *\nDisallow: /admin/\n\nUser-agent: AUXSAYS-DaVinci-Evidence-Collector\nDisallow: /\n",
         "still_refused", "robots_disallow"),
        ("V7 a wildcard rule that covers the search query is obeyed",
         "User-agent: *\nDisallow: /*?keywords=\n", "still_refused", "robots_disallow"),
        ("V8 an HTML page served as robots.txt is NOT read as `nothing disallowed`",
         "<!DOCTYPE html><html><body>hello</body></html>", "inconclusive", "robots_not_a_robots_file"),
        ("V9 a Crawl-delay longer than the step may wait ends the probe after one request",
         "User-agent: *\nCrawl-delay: 120\n", "inconclusive", "crawl_delay_too_long"),
        ("V28 a robots.txt that starts with a UTF-8 byte-order mark is still read: `Disallow: /` refuses the probe",
         "\ufeffUser-agent: *\nDisallow: /\n", "still_refused", "robots_disallow"),
    ]
    for label, robots, result, reason in robots_cases:
        source = Source((200, robots), (200, FORUM_PAGE))
        outcome = rp.run_probe(spec, source, sleep=no_sleep)
        check(label, (outcome["result"], outcome["reason"], len(source.log)) == (result, reason, 1),
              f"{outcome} {source.log}")
    slept: list[float] = []
    rp.run_probe(spec, Source((200, "User-agent: *\nCrawl-delay: 9\n"), (200, FORUM_PAGE)), sleep=slept.append)
    check("V10 the probe waits out the source's Crawl-delay before its content request", slept == [9.0], str(slept))
    bom = mr.parse_robots("\ufeffUser-agent: *\nDisallow: /\n", service["robots_agent"])
    check("V29 the parser removes a leading byte-order mark: the `*` group and its rule are read, and nothing is allowed",
          bom["readable"] and bom["rules"] == [(False, "/")] and not mr.robots_allows(bom, spec["url"]), str(bom))

    # THE WORST CASE, COUNTED. The real record walk over the real live records; the forum answers
    # every request as generously as it can (30 threads per search). Four runs after one recovery.
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        forum = Forum("answer")
        runs = [lane.cycle(at(6 * n), forum, answering_probe()) for n in range(5)]
        counts = [r["forum_requests"] for r in runs]
        check("V11 the real walk covers the live records (the review counted 23)",
              len(lane.records) >= 20, str(len(lane.records)))
        check("V12 requests to the forum per run after ONE recovery: 6, 12, 20, 30, 30 -- never 1,127",
              counts == [6, 12, 20, 30, 30], str(counts))
        check("V13 the first run after a recovery sends the forum 2 probe requests and 6 collector requests",
              len(lane.probe_log) == 2 and counts[0] == 6 and runs[0]["summary"]["requests_made"] == 2,
              f"{lane.probe_log} {counts}")
        check("V14 every request after the first of a run waits the declared spacing (2 s at least)",
              len(lane.sleeps) == sum(counts) - len(runs) and min(lane.sleeps) >= 2.0,
              f"sleeps={len(lane.sleeps)} requests={sum(counts)}")
        first = [urllib.parse.urlsplit(u).path for u in forum.log[:6]]
        check("V15 each run reads robots.txt first; a record gets at most 6 requests, half of them searches",
              first == ["/robots.txt", "/search.php", "/search.php", "/search.php", "/viewtopic.php",
                        "/viewtopic.php"], str(first))
        check("V16 records the budget did not reach get a `disabled` row that says so; nothing is asked for them",
              runs[0]["attempted"] == 1 and runs[3]["attempted"] == 5
              and runs[0]["statuses"] == ["disabled", "no_results"], str(runs[0]))
        check("V17 the forum is never asked anything off the pinned host or outside the declared paths",
              set(forum.paths()) == {"/robots.txt", "/search.php", "/viewtopic.php"}, str(forum.paths()))
        check("V18 after the ramp nothing is probed again: one probe, two requests, in the whole sequence",
              len(lane.probe_log) == 2, str(lane.probe_log))

    for mode, label in (("robots_disallow", "V19 robots.txt disallowing /search.php at RUN time: one request, then the run stops"),
                        ("robots_own_agent", "V20 robots.txt addressing the collector's own agent at run time: one request, then stop"),
                        ("robots_html", "V21 an HTML page served as robots.txt at run time: one request, then stop"),
                        ("robots_bom", "V30 a byte-order-marked robots.txt disallowing everything at run time: one request, then stop")):
        with tempfile.TemporaryDirectory() as td:
            lane = Lane(td)
            forum = Forum(mode)
            run = lane.cycle(at(0), forum, answering_probe())
            check(label, run["served"] and run["forum_requests"] == 1 and forum.paths() == {"/robots.txt": 1}
                  and run["statuses"] == ["blocked", "disabled"] and run["attempted"] == 1, str(run))
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        lane.cycle(at(0), Forum("crawl_delay"), answering_probe())
        check("V22 a Crawl-delay in robots.txt raises the collector's spacing for that run",
              lane.sleeps and min(lane.sleeps) >= 7.0, str(lane.sleeps[:3]))

    # The gate itself.
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        rp.run(health_path=lane.main, now=at(0), write=True, max_requests=4, fetch=answering_probe(), sleep=no_sleep)
        forum = Forum("answer")
        saved = (dv.request_text, dv.service_sleep, dv.reddit_access_authorized)
        dv.request_text, dv.service_sleep, dv.reddit_access_authorized = forum, no_sleep, (lambda: False)
        try:
            ctx = base.CollectorContext(write=False, since=None, max_pages=1)
            rec = lane.records[0]
            _a, _r, bare = dv.collect_for_record(rec, ctx, returned=frozenset({MID}))
            row = next(h for h in bare if h["method_id"] == MID)
            check("V23 a bare set of method ids serves nothing: without its bounds the method is not run",
                  row["status"] == "disabled" and not forum.log, f"{row['status']} {forum.log}")
            services = dv.return_services(lane.main, now=at(0.1))
            check("V24 the collector is handed the granted budget, not the steady cap",
                  set(services) == {MID} and services[MID].budget == 6 and services[MID].spacing >= 2.0,
                  str({k: v.budget for k, v in services.items()}))
            original = dv.TEXT_HEADERS["User-Agent"]
            dv.TEXT_HEADERS["User-Agent"] = "SomethingElse/1.0"
            try:
                check("V25 if the collector's agent is not the agent the registry declares, nothing returns",
                      dv.return_services(lane.main, now=at(0.1)) == {})
            finally:
                dv.TEXT_HEADERS["User-Agent"] = original
            check("V26 a grant serves the run it was written for and no later one (no fresh grant, no service)",
                  dv.return_services(lane.main, now=at(6)) == {} and dv.returned_to_service(lane.main, now=at(6)) == frozenset())
            source = inspect.getsource(dv.DavinciCollector.collect)
            check("V27 a dry run serves no returned method (its outcome could not be recorded)",
                  "return_services() if context.write else {}" in source, source[-600:])
        finally:
            dv.request_text, dv.service_sleep, dv.reddit_access_authorized = saved


def relapse_checks() -> None:
    print("-- R. M2 / S3: a recovery the real run refuses is a relapse, and a flapping source backs off")
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        check("R1 before any probe the method is off and the collector's returned set is empty",
              dv.returned_to_service(lane.main, now=T0) == frozenset()
              and MID in mr.effective_plan(PID, base.load_method_health(lane.main), base.load_method_probes(lane.main),
                                           reprobe_refusal=am.reprobe_refusal, now=T0)["disabled"])
        forum = Forum("search_refused")
        probe = answering_probe()
        runs = [lane.cycle(at(6 * n), forum, probe) for n in range(8)]          # 48 hours
        served = [r["served"] for r in runs]
        check("R2 the probe answers but the search is still refused: the method runs in ONE of 8 cycles (was 4 of 8)",
              served == [True] + [False] * 7, str(served))
        check("R3 that one run sends 2 requests (robots.txt, one refused search) and stops; later cycles send 0",
              [r["forum_requests"] for r in runs] == [2, 0, 0, 0, 0, 0, 0, 0], str([r["forum_requests"] for r in runs]))
        record = runs[1]["probe"]
        check("R4 the next step records the RELAPSE: result, one relapse, the cooldown restarted from that moment",
              record["result"] == "relapsed" and record["relapses"] == 1 and record["reason"] == "service_run_refused"
              and record["next_probe_after"] == mr.format_time(at(6 + 168)) and not record.get("granted_at"), str(record))
        check("R5 a relapsed method cannot return on the old probe: 48 h later it is still out, with no new probe",
              len(lane.probe_log) == 2 and runs[7]["probe"]["result"] == "relapsed"
              and runs[7]["summary"]["skipped"] and any(s["method_id"] == MID and s["reason"] == "cooldown"
                                                        for s in runs[7]["summary"]["skipped"]), str(lane.probe_log))
        check("R6 its rows do not flap: after the relapse every row of the method reads `disabled` each cycle",
              all(r["statuses"] == ["disabled"] for r in runs[1:]), str([r["statuses"] for r in runs]))
        plan = mr.effective_plan(PID, base.load_method_health(lane.main), base.load_method_probes(lane.main),
                                 reprobe_refusal=am.reprobe_refusal, now=at(48))
        check("R7 routing lists it `disabled`, not a fallback", MID in plan["disabled"] and plan["fallback"] == []
              and plan["returned_to_service"] == [], str(plan))

        # S3. The source keeps flapping: every probe answers, every real run is refused.
        waits, hour = [], 6 + 168
        for _flap in range(4):
            run = lane.cycle(at(hour + 1), forum, probe)                         # cooldown over: probe + refused run
            after = lane.cycle(at(hour + 7), forum, probe)                       # the step settles the relapse
            waits.append(int((mr.parse_time(after["probe"]["next_probe_after"]) - at(hour + 7)).total_seconds() // 3600))
            hour = hour + 7 + waits[-1]
            if not run["served"]:
                waits.append(-1)
        check("S3a each answered probe is followed by ONE refused run, then a longer wait: 336, 672, 720, 720 h",
              waits == [336, 672, 720, 720], str(waits))
        record = base.load_method_probes(lane.main)[0]
        check("S3b the relapse count survives every answered probe (5 relapses, 5 probes, 10 probe requests)",
              record["relapses"] == 5 and record["total_requests"] == 10 and len(lane.probe_log) == 10, str(record))
        check("S3c a flapping source costs at most 4 requests per cooldown: 2 for the probe, 2 for the refused run",
              len(forum.log) == 10, str(len(forum.log)))

    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        forum = Forum("answer")
        probe = answering_probe()
        lane.cycle(at(0), Forum("search_refused"), probe)
        lane.cycle(at(6), forum, probe)                                          # relapse 1, wait 168 h
        check("S3d after one relapse the record holds it", base.load_method_probes(lane.main)[0]["relapses"] == 1)
        for n in range(4):                                                       # recovery that holds
            lane.cycle(at(6 + 169 + 6 * n), forum, probe)
        record = base.load_method_probes(lane.main)[0]
        check("S3e a relapse is forgiven only after the method has carried the whole ramp (3 answered runs)",
              record.get("relapses", 0) == 0 and record["service_runs"] == 3 and record["grant_requests"] == 30, str(record))

    # The path the review measured, with the re-probe step OUT of the picture: after the refused
    # run the step does not run at all (skipped, timed out, crashed). The collector alone must not
    # bring the method back, whatever its rows look like by then.
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        forum = Forum("search_refused")
        first = lane.cycle(at(0), forum, answering_probe())
        alone = [lane.cycle(at(6 * n), forum, answering_probe(), step_runs=False) for n in range(1, 8)]
        check("R13 with the re-probe step not running at all, the refused method still runs in 1 of 8 cycles: "
              "the collector serves nothing without a grant written by this run's step",
              first["served"] and [r["served"] for r in alone] == [False] * 7
              and len(forum.log) == 2 and base.load_method_probes(lane.main)[0]["result"] == "recovered",
              str([r["served"] for r in alone]) + str(len(forum.log)))

    # A search that answers 200 with a page that is not the forum (a maintenance notice). The
    # collector stops its run on that `low_confidence` result; the settlement must read it the same
    # way, as refused, not as an answer that climbs the ramp.
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        forum = Forum("search_maintenance")
        runs = [lane.cycle(at(6 * n), forum, answering_probe()) for n in range(8)]
        check("R14 a non-forum 200 page on the search is a relapse: the method runs in ONE of 8 cycles, 2 requests "
              "(the old settlement served it every cycle and climbed the ramp)",
              [r["served"] for r in runs] == [True] + [False] * 7
              and [r["forum_requests"] for r in runs] == [2, 0, 0, 0, 0, 0, 0, 0]
              and runs[0]["statuses"] == ["disabled", "low_confidence"],
              str([(r["served"], r["forum_requests"], r["statuses"]) for r in runs]))
        record = runs[1]["probe"]
        check("R15 the step records it as a refused run: `relapsed`, one relapse, the cooldown restarted",
              record["result"] == "relapsed" and record["relapses"] == 1 and record["reason"] == "service_run_refused"
              and record["next_probe_after"] == mr.format_time(at(6 + 168)), str(record))
    granted = {"product_id": PID, "method_id": MID, "result": "recovered", "granted_at": mr.format_time(T0),
               "grant_requests": 6, "service_runs": 0}
    row = {"product_id": PID, "method_id": MID, "status": "low_confidence",
           "last_run": mr.format_time(T0 + timedelta(hours=1))}
    service = am.reprobe_spec(MID)["service"]
    settled = {status: mr.advance_service(granted, [dict(row, status=status)], T0 + timedelta(hours=6),
                                          service=service, cooldown_hours=168, max_cooldown_hours=720)[1]
               for status in ("low_confidence", "success", "no_results", "partial", "blocked")}
    check("R16 the settlement: low_confidence and blocked relapse; success, no_results and partial answer",
          settled == {"low_confidence": "relapsed_refused", "success": "answered", "no_results": "answered",
                      "partial": "answered", "blocked": "relapsed_refused"}, str(settled))

    refused = Source((403, "denied"), (200, FORUM_PAGE))
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        probe = answering_probe()
        lane.cycle(at(0), Forum("search_refused"), probe)
        lane.cycle(at(6), Forum("search_refused"), probe)
        lane.cycle(at(6 + 169), Forum("search_refused"), refused)
        record = base.load_method_probes(lane.main)[0]
        check("R8 a refused probe after a relapse counts both: one relapse + one refusal = a 336 h wait",
              record["result"] == "still_refused" and record["consecutive_refusals"] == 1 and record["relapses"] == 1
              and record["next_probe_after"] == mr.format_time(at(6 + 169 + 336)), str(record))

    forged = [{"product_id": PID, "method_id": "reddit_search", "result": "recovered",
               "probed_at": mr.format_time(T0), "next_probe_after": mr.format_time(T0),
               "granted_at": mr.format_time(T0), "grant_requests": 30},
              {"product_id": PID, "method_id": "known_watchlist", "result": "recovered",
               "probed_at": mr.format_time(T0), "next_probe_after": mr.format_time(T0),
               "granted_at": mr.format_time(T0), "grant_requests": 30}]
    plan = mr.effective_plan(PID, [], forged, reprobe_refusal=am.reprobe_refusal, now=T0)
    check("R9 a `recovered` record for a closed method, however it got there, returns nothing to service",
          plan["fallback"] == [] and plan["returned_to_service"] == []
          and {"reddit_search", "known_watchlist"} <= set(plan["disabled"]), str(plan))
    check("R10 without the registry policy passed in, nothing is ever returned",
          mr.effective_plan(PID, [], forged, now=T0)["returned_to_service"] == [])
    real = {"product_id": PID, "method_id": MID, "result": "recovered", "probed_at": mr.format_time(T0),
            "next_probe_after": mr.format_time(T0), "granted_at": mr.format_time(T0), "grant_requests": 6}
    future = dict(real, probed_at="2099-01-01T00:00:00Z", granted_at="2099-01-01T00:00:00Z")
    ungranted = {k: v for k, v in real.items() if k not in ("granted_at", "grant_requests")}
    check("R11 a record dated in the future, or one with no grant, keeps nothing in service",
          mr.recovered_in_service(PID, MID, [], [real], now=T0)
          and not mr.recovered_in_service(PID, MID, [], [future], now=T0)
          and not mr.recovered_in_service(PID, MID, [], [ungranted], now=T0)
          and not mr.recovered_in_service(PID, MID, [], [dict(real, result="relapsed")], now=T0))
    graph = (_REPO / "auxsays/scripts/orchestrate_evidence_run.py").read_text(encoding="utf-8")
    check("R12 the orchestration graph, which has no request budget, never returns a method to service",
          "reprobe_refusal" not in graph and "effective_plan(product_id, load_method_health(self.health_path)" in graph)


def lost_cycle_checks() -> None:
    print("-- L. S1: cooldown and probe state survive a cycle that never reached main")
    refusing = Source((403, "denied"), (200, FORUM_PAGE))
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td, carry=False)
        for n in range(8):
            lane.cycle(at(6 * n), Forum("answer"), refusing, lost=True)
        check("L1 THE DEFECT, kept visible: without the carried copy, 8 lost cycles in 48 h probe 8 times",
              len(lane.probe_log) == 8, str(len(lane.probe_log)))
    refusing = Source((403, "denied"), (200, FORUM_PAGE))
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        runs = [lane.cycle(at(6 * n), Forum("answer"), refusing, lost=True) for n in range(8)]
        check("L2 with the carried copy, 8 lost cycles against a refusing forum send ONE probe request",
              len(lane.probe_log) == 1 and runs[1]["summary"]["carried_records_adopted"] == 1
              and any(s["method_id"] == MID and s["reason"] == "cooldown" for s in runs[7]["summary"]["skipped"]),
              str(lane.probe_log))
        check("L3 main never received a record, and the lane still knows its cooldown",
              base.load_method_probes(lane.main) == []
              and runs[7]["probe"]["next_probe_after"] == mr.format_time(at(168)), str(runs[7]["probe"]))
        ok = lane.cycle(at(48), Forum("answer"), refusing)
        check("L4 the first cycle that does reach main brings the carried record with it",
              len(base.load_method_probes(lane.main)) == 1 and len(lane.probe_log) == 1, str(ok["probe"]))
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        forum, probe = Forum("answer"), answering_probe()
        runs = [lane.cycle(at(6 * n), forum, probe, lost=True) for n in range(8)]
        check("L5 an ANSWERING forum and 8 lost cycles: one probe (2 requests), not 16",
              len(lane.probe_log) == 2, str(len(lane.probe_log)))
        check("L6 a granted run that leaves no row is unsettled; after two the recovery is withdrawn",
              [r["served"] for r in runs] == [True, True] + [False] * 6
              and runs[2]["probe"]["result"] == "relapsed" and runs[2]["probe"]["reason"] == "service_run_unsettled"
              and not runs[2]["probe"].get("relapses"), str([r["served"] for r in runs]) + str(runs[2]["probe"]))
        check("L7 the lost cycles sent the forum 12 collector requests in 48 h (2 runs of 6), then nothing",
              [r["forum_requests"] for r in runs] == [6, 6, 0, 0, 0, 0, 0, 0], str([r["forum_requests"] for r in runs]))
    with tempfile.TemporaryDirectory() as td:
        lane = Lane(td)
        hostile = [{"product_id": PID, "method_id": "reddit_search", "result": "recovered",
                    "probed_at": mr.format_time(T0), "next_probe_after": mr.format_time(T0),
                    "granted_at": mr.format_time(T0), "grant_requests": 30, "state_at": mr.format_time(T0)},
                   {"product_id": PID, "method_id": MID, "result": "recovered",
                    "probed_at": "2099-01-01T00:00:00Z", "next_probe_after": "2099-01-01T00:00:00Z",
                    "granted_at": "2099-01-01T00:00:00Z", "grant_requests": 30, "state_at": "2099-01-01T00:00:00Z"},
                   {"product_id": "obs-studio", "method_id": MID, "result": "recovered",
                    "probed_at": mr.format_time(T0), "next_probe_after": mr.format_time(T0),
                    "granted_at": mr.format_time(T0), "grant_requests": 30, "state_at": mr.format_time(T0)}]
        lane.carry.parent.mkdir(parents=True)
        lane.carry.write_text(json.dumps({"schema": 1, "probes": hostile}), encoding="utf-8")
        merged, adopted = rp.merge_carry([], rp.read_carry(lane.carry), T0)
        check("L8 a carried record for a closed method, another product, or dated in the future is ignored",
              adopted == 0 and merged == [], str(merged))
        lane.carry.write_text("{not json", encoding="utf-8")
        check("L9 a damaged carried copy is no carried copy", rp.read_carry(lane.carry) == [])
    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        died: list[str] = []

        def dies(url, agent=""):
            died.append(url)
            raise RuntimeError("the runner lost its network mid-request")

        try:
            rp.run(health_path=path, now=T0, write=True, max_requests=4, fetch=dies, sleep=no_sleep)
        except RuntimeError:
            pass
        record = (base.load_method_probes(path) or [{}])[0]
        check("L10 the cooldown is on file BEFORE the first request: a step that dies mid-probe has paid for it",
              len(died) == 1 and record.get("reason") == "probe_started"
              and record.get("next_probe_after") == mr.format_time(at(168)), str(record))
        again = rp.run(health_path=path, now=at(6), write=True, max_requests=4,
                       fetch=Source((403, "x"), (200, FORUM_PAGE)), sleep=no_sleep)
        check("L11 the run after that crash does not probe again", again["requests_made"] == 0, str(again["probed"]))


def host_pin_checks() -> None:
    print("-- H. S2: the floor pins the parsed host; the rights layer is pinned on its own")
    original, pins = dict(am.REPROBE), dict(am.REPROBE_HOST_PINS)
    base_spec = original[MID]

    def declared(method_id: str, host: str, *, robots_host: str | None = None, pin: str | None = None) -> str:
        am.REPROBE.clear()
        am.REPROBE.update(original)
        am.REPROBE_HOST_PINS.clear()
        am.REPROBE_HOST_PINS.update(pins)
        service = dict(base_spec["service"], robots_sample_urls=[f"https://{host}/search.php?keywords=x"])
        am.REPROBE[method_id] = dict(base_spec, url=f"https://{host}/search.php?keywords=x",
                                     robots_url=f"https://{robots_host or host}/robots.txt", service=service)
        if pin is not None:
            am.REPROBE_HOST_PINS[method_id] = pin
        return am.reprobe_refusal(method_id)

    try:
        check("H1 `web_search` declared allowed on https://redd.it/... is CLOSED (was open and due)",
              "reddit" in declared("web_search", "redd.it", pin="redd.it"), declared("web_search", "redd.it", pin="redd.it"))
        hosts = {"old.reddit.com": "reddit", "www.redditmedia.com": "reddit", "learn.microsoft.com": "learn",
                 "community.adobe.com": "adobe", "helpx.adobe.com": "adobe", "web.archive.org": "closed_source",
                 "api.search.brave.com": "paid"}
        wrong = {h: declared(MID, h, pin=h) for h, token in hosts.items() if token not in declared(MID, h, pin=h)}
        check("H2 a closed source's host, or any subdomain of it, is closed even when the pin is edited to match",
              not wrong, str(wrong))
        check("H3 a look-alike host is judged by what it IS: notreddit.com.example.org is not Reddit, and is not pinned",
              declared(MID, "notreddit.com.example.org") == "host_not_pinned")
        check("H4 a declaration naming a host other than the method's pinned host is refused",
              declared(MID, "example.org") == "host_not_pinned")
        check("H5 robots_url on a different host than the probe is refused",
              declared(MID, "forum.blackmagicdesign.com", robots_host="example.org") == "host_not_pinned"
              and "reddit" in declared(MID, "forum.blackmagicdesign.com", robots_host="www.reddit.com"))
        check("H6 a method with no pinned host is closed however complete its declaration "
              "(`creativecow_forum_index` on creativecow.net)",
              declared("creativecow_forum_index", "creativecow.net") == "no_host_pin")
        am.REPROBE.clear()
        am.REPROBE.update(original)
        am.REPROBE_HOST_PINS.clear()
        am.REPROBE_HOST_PINS.update(pins)
        for label, url in (("credentials", "https://user:pw@forum.blackmagicdesign.com/search.php"),
                           ("a port", "https://forum.blackmagicdesign.com:8443/search.php"),
                           ("plain http", "http://forum.blackmagicdesign.com/search.php")):
            am.REPROBE[MID] = dict(base_spec, url=url)
            check(f"H7 a probe URL with {label} is refused", am.reprobe_refusal(MID) == "probe_incomplete",
                  am.reprobe_refusal(MID))
        am.REPROBE[MID] = {k: v for k, v in base_spec.items() if k != "service"}
        check("H8 an allowed declaration with no service bounds is closed: nothing unbounded can be returned",
              am.reprobe_refusal(MID) == "service_bounds_missing" and am.reprobe_spec(MID) is None)
        am.REPROBE[MID] = dict(base_spec)
        check("H9 today exactly one host is pinned, the Blackmagic forum, and it is the collector's own",
              pins == {MID: "forum.blackmagicdesign.com"}
              and am.probe_host(dv.FORUM_SEARCH) == pins[MID] and not am.closed_host_reason(pins[MID]))
        # The rights layer. Every method with a recorded rights status today is ALSO closed by an
        # identity token, so removing the rights check changed nothing a test could see. Give the
        # one open method a rights status and nothing else: only that layer can close it.
        entry = am.by_id(MID)
        entry["rights_status"] = "unresolved"
        try:
            check("H10 a recorded rights status alone closes an otherwise open method",
                  am.reprobe_refusal(MID) == "rights_status_unresolved" and am.reprobe_spec(MID) is None,
                  am.reprobe_refusal(MID))
        finally:
            del entry["rights_status"]
        check("H11 and without it the method is open again (the check above was not vacuous)",
              am.reprobe_refusal(MID) == "")
        spec = dict(am.reprobe_spec(MID), host="example.org")
        source = Source((200, ROBOTS_OK), (200, FORUM_PAGE))
        outcome = rp.run_probe(spec, source, sleep=no_sleep)
        check("H12 the runner itself sends nothing when a probe's URLs are not on its pinned host",
              outcome["reason"] == "host_not_pinned" and not source.log, str(outcome))
    finally:
        am.REPROBE.clear()
        am.REPROBE.update(original)
        am.REPROBE_HOST_PINS.clear()
        am.REPROBE_HOST_PINS.update(pins)


def visible_failure_checks() -> None:
    print("-- X. S5: a failing re-probe step is visible in the log, the run summary and the health file")
    reached: list[str] = []

    def exploding(url, agent=""):
        reached.append(url)
        raise RuntimeError("boom at the socket")

    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        step_summary, step_output = Path(td) / "summary.md", Path(td) / "output.txt"
        step_summary.write_text("", encoding="utf-8")
        step_output.write_text("", encoding="utf-8")
        carry = Path(td) / "carry" / "probes.json"
        saved_env = {k: os.environ.get(k) for k in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT")}
        os.environ["GITHUB_STEP_SUMMARY"], os.environ["GITHUB_OUTPUT"] = str(step_summary), str(step_output)
        original = rp.default_fetch
        rp.default_fetch = exploding
        argv = ["--write", "--health-path", str(path), "--carry-path", str(carry)]
        try:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = rp.main(argv + ["--now", "2026-11-24T07:00:00Z"])
            check("X1 a crashing step exits 1 (under continue-on-error the job goes on, the step is not green)",
                  rc == 1, str(rc))
            check("X2 the log carries an ::error annotation naming the failure, and the traceback",
                  "::error title=Re-probe step failed::RuntimeError: boom at the socket" in out.getvalue()
                  and "Traceback" in err.getvalue(), out.getvalue()[-300:])
            check("X3 the run summary says FAILED",
                  "status: **FAILED** (`RuntimeError`)" in step_summary.read_text(encoding="utf-8"))
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            check("X4 the health file records the failure: probe_step.status error, the error type, a count of 1",
                  payload.get("probe_step") == {"status": "error", "at": "2026-11-24T07:00:00Z",
                                                "error": "RuntimeError", "consecutive_errors": 1},
                  str(payload.get("probe_step")))
            check("X5 the step outputs say error", "status=error" in step_output.read_text(encoding="utf-8"))
            vout = io.StringIO()
            with contextlib.redirect_stdout(vout):
                verdict = vh.validate(path, check_registry=True)
            check("X6 the health validator reports it as a warning and does not block the writeback",
                  verdict == 0 and "WARN re-probe step: its last run FAILED (RuntimeError)" in vout.getvalue(),
                  vout.getvalue()[-300:])
            check("X7 the crash happened after the cooldown was paid: the record and the carried copy both hold it",
                  len(reached) == 1 and payload["probes"][0]["reason"] == "probe_started"
                  and rp.read_carry(carry)[0]["next_probe_after"] == mr.format_time(at(168)), str(payload.get("probes")))
            base.upsert_method_health([disabled_row(MID, last_run="2026-11-24T07:30:00Z")], path)
            check("X8 the collectors' writer keeps the failure record when it rewrites the file",
                  base.load_probe_step(path).get("error") == "RuntimeError")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc2 = rp.main(argv + ["--now", "2026-11-24T13:00:00Z"])
            check("X9 a second failing run counts up... only if it fails: inside the cooldown the step runs clean",
                  rc2 == 0 and "probe_step" not in yaml.safe_load(path.read_text(encoding="utf-8")), str(rc2))
            check("X10 a clean run says ok in the summary and reports its request count",
                  "status: **ok** (write); requests made: **0**" in step_summary.read_text(encoding="utf-8")
                  and "requests_made=0" in step_output.read_text(encoding="utf-8"))
            check("X11 the command-line path uses the replaceable fetch (this suite cannot reach the network)",
                  len(reached) == 1 and reached[0].endswith("/robots.txt"), str(reached))
            path.write_text("schema_version: 1\nmethods: [\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc3 = rp.main(argv + ["--now", "2026-12-24T07:00:00Z"])
            check("X12 an unreadable health file: still exit 1, still annotated, and nothing is requested",
                  rc3 == 1 and "::error title=Re-probe step failed::" in out.getvalue() and len(reached) == 1,
                  out.getvalue()[-200:])
        finally:
            rp.default_fetch = original
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


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

    with tempfile.TemporaryDirectory() as td:
        path = fresh_health(td)
        rp.run(health_path=path, now=T0, write=True, max_requests=4, fetch=answering_probe(), sleep=no_sleep)
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        record = payload["probes"][0]
        check("W8 a recovered record holds its grant (6 requests) and passes the validator",
              record["result"] == "recovered" and record["grant_requests"] == 6
              and record["granted_at"] == mr.format_time(T0) and set(record) <= set(base.METHOD_PROBE_FIELDS)
              and vh.validate(path, check_registry=True) == 0, str(record))
        bad = Path(td) / "bad.yml"
        for label, change, needle in (
                ("W9 the validator refuses a grant above the per-run service cap", {"grant_requests": 31}, "the cap is 30"),
                ("W10 the validator refuses a grant on a record that is not `recovered`", {"result": "relapsed"},
                 "only a `recovered` record")):
            payload["probes"] = [dict(record, **change)]
            bad.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                verdict = vh.validate(bad, check_registry=True)
            check(label, verdict == 1 and needle in out.getvalue(), out.getvalue()[-200:])


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
    check("F3b it carries its state: a carry path under the runner's temp directory, never in the checkout",
          '--carry-path "$RUNNER_TEMP/reprobe-carry/probes.json"' in code and "id: reprobe" in code, code)
    restore = next((s for s in steps if s.startswith("Restore re-probe state carried from earlier runs")), "")
    save = next((s for s in steps if s.startswith("Save re-probe state for later runs")), "")
    check("F3c the carried copy is restored before the step and saved after it, with the pin pages.yml uses",
          names.index("Restore re-probe state carried from earlier runs")
          < names.index("Re-probe switched-off sources (bounded)")
          < names.index("Save re-probe state for later runs") < names.index("Collect patch evidence")
          and "uses: actions/cache/restore@v4" in restore and "uses: actions/cache/save@v4" in save
          and "restore-keys: |\n            reprobe-carry-v1-" in restore
          and restore.count("path: ${{ runner.temp }}/reprobe-carry") == 1
          and save.count("path: ${{ runner.temp }}/reprobe-carry") == 1
          and "actions/cache/restore@v4" in (_REPO / ".github/workflows/pages.yml").read_text(encoding="utf-8"),
          restore + save)
    check("F3d neither cache step can fail the job, and the save runs even when a later step failed",
          "continue-on-error: true" in restore and "continue-on-error: true" in save
          and "always()" in save and "steps.reprobe.outputs.carry_changed == 'true'" in save, save)
    check("F3e the pipeline summary names the step's outcome, so a failed step is on the run page",
          "REPROBE: ${{ steps.reprobe.outcome }}" in text
          and 'echo "- re-probe step: **${REPROBE:-skipped}**' in text)
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
    service_bound_checks()
    relapse_checks()
    lost_cycle_checks()
    host_pin_checks()
    store_checks()
    visible_failure_checks()
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
