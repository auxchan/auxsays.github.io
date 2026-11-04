#!/usr/bin/env python3
"""AUXSAYS D2: automated Reddit collection is OFF unless written data-access authorisation is recorded.

Offline. Every transport is replaced by a counter that records the URL and then refuses, so a path
that reaches the network is a failed assertion rather than a request. Covers:

  A  the policy authority itself (default off, what counts as authorisation, host matching)
  B  every Reddit transport refuses BEFORE a socket is opened
  C  the shared module (reddit_source) returns nothing and calls nothing
  D  DaVinci: reddit_search ladder + watchlist hydration, and a truthful `disabled` row
  E  PowerPoint, Acrobat (including its re-enable flag) and Premiere (whatever role routing gives)
  F  the writer keeps the REAL last attempt and is idempotent
  G  certification is not softened: a disabled Reddit family is never healthy
  H  the authorisation switch is reachable (the gate is not vacuous), and no workflow sets it
  I  the manual DaVinci seed tool makes no Reddit request either
"""
from __future__ import annotations

import os
import sys
import tempfile
import types
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml                                                      # noqa: E402
from lib import reddit_access_policy as pol                      # noqa: E402
from lib import monitoring_health as mh                          # noqa: E402
import patch_collectors.reddit_source as rs                      # noqa: E402
import patch_collectors.davinci as dv                            # noqa: E402
import patch_collectors.microsoft_powerpoint as ppt              # noqa: E402
import patch_collectors.adobe_acrobat_community as ac            # noqa: E402
import patch_collectors.adobe_premiere as pr                     # noqa: E402
from patch_collectors import base                                # noqa: E402
from patch_collectors.base import CollectorContext, PatchRecord, generated_records  # noqa: E402

ENV = pol.AUTHORIZATION_ENV
REASON = pol.POLICY_REASON
PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


class Refused(urllib.error.URLError):
    def __init__(self, msg: str = "blocked") -> None:
        super().__init__(msg)


class NetWatch:
    """Replace urlopen with a recorder that refuses. Anything that reaches it is a request."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def __enter__(self):
        self._orig = urllib.request.urlopen

        def fake(req, *a, **k):
            self.urls.append(getattr(req, "full_url", str(req)))
            raise Refused("network blocked by test")

        urllib.request.urlopen = fake
        return self

    def __exit__(self, *exc):
        urllib.request.urlopen = self._orig
        return False

    @property
    def reddit(self) -> list[str]:
        return [u for u in self.urls if pol.is_reddit_url(u)]


class Env:
    """Set/clear the authorisation reference for a block, restoring it after."""

    def __init__(self, value: str | None) -> None:
        self.value = value

    def __enter__(self):
        self._old = os.environ.get(ENV)
        if self.value is None:
            os.environ.pop(ENV, None)
        else:
            os.environ[ENV] = self.value
        return self

    def __exit__(self, *exc):
        if self._old is None:
            os.environ.pop(ENV, None)
        else:
            os.environ[ENV] = self._old
        return False


def raises_policy(fn, *a, **k) -> bool:
    try:
        fn(*a, **k)
    except pol.RedditAccessPolicyError:
        return True
    except Exception:
        return False
    return False


def davinci_record() -> PatchRecord:
    return PatchRecord(product_id="blackmagic-davinci", update_version="21",
                       path=Path("auxsays/updates/generated/2026-04-14-davinci-resolve-21.md"),
                       update_published_at="2026-04-14", update_status="current",
                       update_product="DaVinci Resolve")


def ctx(**kw) -> CollectorContext:
    return CollectorContext(write=False, since="2026-01-01", max_pages=2, target_versions=None, **kw)


def run_suite() -> int:
    # ---- A: the policy authority --------------------------------------------------------
    print("A. policy authority")
    with Env(None):
        check("A.1 default is NOT authorised", pol.reddit_access_authorized() is False)
    for bad in ("", "0", "false", "no", "off", "none", "  "):
        check(f"A.2 {bad!r} is not an authorisation", pol.reddit_access_authorized({ENV: bad}) is False)
    check("A.3 a recorded reference authorises", pol.reddit_access_authorized({ENV: "agreement-ref-1"}) is True)
    check("A.4 a client id / bearer token is NOT authorisation",
          pol.reddit_access_authorized({"REDDIT_BEARER_TOKEN": "x", "REDDIT_CLIENT_ID": "y",
                                        "AUXSAYS_REDDIT_USER_AGENT": "z"}) is False)
    check("A.5 reddit hosts are recognised (www, old, oauth, redd.it)",
          all(pol.is_reddit_url(u) for u in ("https://www.reddit.com/r/x", "https://old.reddit.com/r/x/.rss",
                                             "https://oauth.reddit.com/r/x/new", "https://redd.it/abc")))
    check("A.6 look-alike hosts are not reddit",
          not any(pol.is_reddit_url(u) for u in ("https://notreddit.com/", "https://reddit.com.evil.io/",
                                                 "https://forum.blackmagicdesign.com/viewtopic.php?t=1", "")))
    check("A.7 the policy reason is the one the handoff names", REASON == "reddit_access_policy_unauthorised")
    check("A.8 the public note names no repository path or module",
          not any(t in pol.POLICY_NOTE for t in ("lib/", ".py", "auxsays/", "reddit_source")))

    # ---- B: transports refuse before a socket ----------------------------------------------
    print("B. transports refuse before any socket")
    with Env(None), NetWatch() as net:
        att = [("reddit_json", "https://www.reddit.com/r/x/search.json")]
        check("B.1 davinci.request_json", raises_policy(dv.request_json, att[0][1]))
        check("B.2 davinci.request_reddit_json_with_fallback", raises_policy(dv.request_reddit_json_with_fallback, att))
        check("B.3 davinci.request_reddit_feed", raises_policy(dv.request_reddit_feed, "https://www.reddit.com/r/x/.rss", endpoint_family="f"))
        check("B.4 davinci.request_reddit_feed_with_fallback", raises_policy(dv.request_reddit_feed_with_fallback, att))
        check("B.5 reddit_source.request_json", raises_policy(rs.request_json, att[0][1]))
        check("B.6 reddit_source.request_reddit_json_with_fallback (no budget)", raises_policy(rs.request_reddit_json_with_fallback, att))
        check("B.7 reddit_source.request_reddit_feed (no budget)",
              raises_policy(rs.request_reddit_feed, "https://www.reddit.com/r/x/.rss", endpoint_family="f", source_type="t", source_name="n"))

        class Budget:  # the bounded paths must refuse before they even count a request
            noted = 0

            def note_request(self):
                Budget.noted += 1

        check("B.8 reddit_source._bounded_json refuses before counting a request",
              raises_policy(rs._bounded_json, att[0][1], budget=Budget(), endpoint_family="f") and Budget.noted == 0)
        check("B.9 reddit_source._bounded_feed refuses before counting a request",
              raises_policy(rs._bounded_feed, att[0][1], budget=Budget(), endpoint_family="f", source_type="t", source_name="n")
              and Budget.noted == 0)
        check("B.10 no request of any kind was made", not net.urls, str(net.urls))

    # ---- C: the shared module ---------------------------------------------------------------
    print("C. shared module")
    with Env(None), NetWatch() as net:
        errors: list = []
        out = rs.collect_reddit_candidates(subreddits=["davinciresolve", "premierepro"], queries=["x 1.0"],
                                           context=ctx(), errors=errors, version_hints=["1.0"])
        check("C.1 collect_reddit_candidates returns nothing", out == [])
        check("C.2 ...records no error (it is not a failure) and makes no request", errors == [] and not net.urls)
    calls: list[str] = []
    saved = (rs._collect_search, rs._collect_listing, rs._collect_feed)
    rs._collect_search = lambda *a, **k: calls.append("search")
    rs._collect_listing = lambda *a, **k: calls.append("listing")
    rs._collect_feed = lambda *a, **k: calls.append("feed")
    try:
        with Env(None):
            rs.collect_reddit_candidates(subreddits=["x"], queries=["q"], context=ctx(), errors=[])
        check("C.3 unauthorised: search, listing and feed are all skipped", calls == [])
        with Env("agreement-ref-1"):
            rs.collect_reddit_candidates(subreddits=["x"], queries=["q"], context=ctx(), errors=[])
        check("C.4 authorised: all three discovery paths run (the gate is not vacuous)",
              calls == ["search", "listing", "feed"], str(calls))
    finally:
        rs._collect_search, rs._collect_listing, rs._collect_feed = saved

    # ---- D: DaVinci ------------------------------------------------------------------------
    print("D. DaVinci")
    seen_text: list[str] = []

    def fake_text(url: str) -> str:
        seen_text.append(url)
        raise dv.SourceAccessError("blocked_by_test", status=403)

    saved_dv = {n: getattr(dv, n) for n in ("request_text", "creative_cow_forum_search_candidates",
                                            "vendor_forum_search_candidates", "reddit_search_candidates")}
    dv.request_text = fake_text
    dv.creative_cow_forum_search_candidates = lambda r, c, e: []
    dv.vendor_forum_search_candidates = lambda r, c, e: []
    try:
        with Env(None), NetWatch() as net:
            accepted, rejected, health = dv.collect_for_record(davinci_record(), ctx())
            by = {h["method_id"]: h for h in health}
            rd = by["reddit_search"]
            check("D.1 reddit_search row is `disabled`", rd["status"] == "disabled", rd["status"])
            check("D.2 ...with the policy reason, not no_results/success", rd["blocked_reason"] == REASON)
            check("D.3 ...and carries no timestamp of its own (the writer keeps the real last attempt)", rd["last_run"] == "")
            check("D.4 ...with zero counters", (rd["candidates_found"], rd["accepted_reports"], rd["rejected_reports"]) == (0, 0, 0))
            check("D.5 ...and public-safe notes", rd["notes"] == pol.POLICY_NOTE)
            check("D.6 no Reddit request via any path (JSON, OAuth, RSS, hydration)", not net.reddit, str(net.reddit))
            check("D.7 watchlist hydration skipped the Reddit post, still probed the forum",
                  not any(pol.is_reddit_url(u) for u in seen_text) and any("blackmagicdesign" in u for u in seen_text),
                  str(seen_text))
            check("D.7b ...and the skipped Reddit probe is not recorded as a fetch failure of the watchlist row",
                  "reddit" not in str(by["known_watchlist"]["blocked_reason"]).lower(), str(by["known_watchlist"]["blocked_reason"]))
            check("D.8 the other methods still emit rows (nothing else switched off)",
                  {"known_watchlist", "creative_cow_forum_search", "vendor_forum_search", "web_search"} <= set(by))
            check("D.9 nothing is accepted or rejected from Reddit", accepted == [] and rejected == [])
            check("D.10 the five-method stack is unchanged", list(by) == ["known_watchlist", "reddit_search",
                  "creative_cow_forum_search", "vendor_forum_search", "web_search"], str(list(by)))
        called: list[str] = []
        dv.reddit_search_candidates = lambda r, c, e: called.append("reddit") or []
        with Env("agreement-ref-1"), NetWatch():
            _a, _r, health2 = dv.collect_for_record(davinci_record(), ctx())
        by2 = {h["method_id"]: h for h in health2}
        check("D.11 authorised: the Reddit method runs again and reports its own status",
              called == ["reddit"] and by2["reddit_search"]["status"] != "disabled" and by2["reddit_search"]["blocked_reason"] != REASON)
    finally:
        for n, v in saved_dv.items():
            setattr(dv, n, v)
    with Env(None), NetWatch() as net:
        check("D.12 the module-level backstop returns [] with no request",
              dv.reddit_search_candidates(davinci_record(), ctx(), []) == [] and not net.urls)

    # ---- E: other products -----------------------------------------------------------------
    print("E. PowerPoint / Acrobat / Premiere")
    ppt_record = PatchRecord(product_id="microsoft-powerpoint", update_version="2603", path=Path("x.md"),
                             update_published_at="2026-03-01", update_status="current",
                             update_product="PowerPoint", target_build="19231.20000")
    target = {"update_version": "2603"}
    with Env(None):
        check("E.1 PowerPoint: the opt-in flag alone no longer enables Reddit",
              ppt.reddit_fallback_enabled({ppt.REDDIT_FALLBACK_ENV: "true"}) is False)
        with NetWatch() as net:
            _a, _r, row = ppt.run_fallback_method(ppt_record, target, ctx(), set(), None, "2026-11-04T00:00:00Z", True)
        check("E.2 PowerPoint: even attempted=True yields a policy `disabled` row",
              row["status"] == "disabled" and row["blocked_reason"] == REASON and row["last_run"] == "", str(row))
        check("E.3 PowerPoint: build identity kept on the row", row["target_build"] == "19231.20000")
        check("E.4 PowerPoint: no request", not net.urls)
    with Env("agreement-ref-1"):
        both = {ENV: "agreement-ref-1", ppt.REDDIT_FALLBACK_ENV: "true"}
        check("E.5 PowerPoint: authorisation + flag enables it", ppt.reddit_fallback_enabled(both) is True)
        check("E.6 PowerPoint: authorisation without the flag stays off", ppt.reddit_fallback_enabled({ENV: "agreement-ref-1"}) is False)

    def acrobat_rows(product_id: str, flag: str) -> dict[str, dict]:
        before = os.environ.get("AUXSAYS_ACROBAT_RETIRED_METHODS")
        os.environ["AUXSAYS_ACROBAT_RETIRED_METHODS"] = flag
        saved_ac = {n: getattr(ac, n) for n in ("adobe_community_algolia_search_candidates",
                                                "adobe_community_search_candidates", "reddit_search_candidates")}
        for n in saved_ac:
            setattr(ac, n, lambda edition, record, context, errors: [])
        try:
            rec = generated_records(product_id, [], include_archived=False)[0]
            _a, _r, h = ac.AdobeAcrobatCollector(product_id).collect_for_record(rec, ctx(), "2026-11-04T00:00:00Z")
            return {x["method_id"]: x for x in h}
        finally:
            for n, v in saved_ac.items():
                setattr(ac, n, v)
            if before is None:
                os.environ.pop("AUXSAYS_ACROBAT_RETIRED_METHODS", None)
            else:
                os.environ["AUXSAYS_ACROBAT_RETIRED_METHODS"] = before

    for pid in ("adobe-acrobat-pro", "adobe-acrobat-reader"):
        with Env(None):
            off = acrobat_rows(pid, "")
            on = acrobat_rows(pid, "1")
        check(f"E.7 {pid}: reddit stays retired and `disabled` for POLICY by default",
              off["reddit_search"]["status"] == "disabled" and off["reddit_search"]["blocked_reason"] == REASON
              and off["reddit_search"]["last_run"] == "")
        check(f"E.8 {pid}: the re-enable flag restores Adobe Community but NEVER Reddit",
              on["adobe_community_search"]["status"] != "disabled"
              and on["reddit_search"]["status"] == "disabled" and on["reddit_search"]["blocked_reason"] == REASON,
              str({k: v["status"] for k, v in on.items()}))
        with Env("agreement-ref-1"):
            auth_on = acrobat_rows(pid, "1")
        check(f"E.9 {pid}: authorisation + flag restores Reddit (switch is reachable)",
              auth_on["reddit_search"]["status"] != "disabled")
        check(f"E.10 {pid}: the Adobe Community retired row is unchanged (no policy reason, real timestamp)",
              off["adobe_community_search"]["blocked_reason"] == "" and off["adobe_community_search"]["last_run"] != "")

    prem_rec = generated_records("adobe-premiere-pro", [], include_archived=False)[0]
    ran: list[str] = []
    saved_methods = dict(pr.PREMIERE_METHODS)
    saved_plan = pr.plan_methods
    pr.PREMIERE_METHODS.clear()
    pr.PREMIERE_METHODS.update({
        "adobe_community_algolia_search": lambda r, c, e: ran.append("algolia") or [],
        "reddit_search": lambda r, c, e: ran.append("reddit") or [],
    })
    try:
        with Env(None), NetWatch() as net:
            _a, _r, h = pr.collect_for_record(prem_rec, ctx())
        rows = {x["method_id"]: x for x in h}
        check("E.11 Premiere default plan: reddit row is a policy `disabled`",
              rows["reddit_search"]["status"] == "disabled" and rows["reddit_search"]["blocked_reason"] == REASON
              and rows["reddit_search"]["last_run"] == "", str(rows.get("reddit_search")))
        check("E.12 Premiere default plan: reddit never executed", "reddit" not in ran, str(ran))
        for role in ("primary", "fallback"):
            def plan(product_id, _role=role):
                p = {"primary": ["adobe_community_algolia_search"], "fallback": [], "fallback_when": ["no_accepted_reports"],
                     "probe_only": [], "disabled": []}
                p[_role] = p[_role] + ["reddit_search"]
                return p
            pr.plan_methods = plan
            ran.clear()
            with Env(None), NetWatch():
                _a, _r, h = pr.collect_for_record(prem_rec, ctx())
            rows = {x["method_id"]: x for x in h}
            check(f"E.13 Premiere: reddit routed as {role} is still never executed and reports policy",
                  "reddit" not in ran and rows["reddit_search"]["blocked_reason"] == REASON, f"ran={ran}")
        pr.plan_methods = lambda product_id: {"primary": [], "fallback": [], "fallback_when": [], "probe_only": [], "disabled": []}
        ran.clear()
        with Env(None), NetWatch():
            _a, _r, h = pr.collect_for_record(prem_rec, ctx())
        rows = {x["method_id"]: x for x in h}
        check("E.14 Premiere: the run-the-whole-catalogue branch skips reddit and still reports it",
              "reddit" not in ran and rows["reddit_search"]["blocked_reason"] == REASON, f"ran={ran}")
        pr.plan_methods = saved_plan
        ran.clear()
        pr.plan_methods = lambda product_id: {"primary": ["adobe_community_algolia_search", "reddit_search"], "fallback": [],
                                              "fallback_when": [], "probe_only": [], "disabled": []}
        with Env("agreement-ref-1"), NetWatch():
            pr.collect_for_record(prem_rec, ctx())
        check("E.15 Premiere: authorised, a primary reddit runs (switch is reachable)", "reddit" in ran, str(ran))
    finally:
        pr.plan_methods = saved_plan
        pr.PREMIERE_METHODS.clear()
        pr.PREMIERE_METHODS.update(saved_methods)

    # ---- F: the writer ------------------------------------------------------------------------
    print("F. writer keeps the real last attempt")
    def policy_row(version: str = "21", method: str = "reddit_search", **over) -> dict:
        row = base.method_health_row(
            product_id="blackmagic-davinci", update_version=version, method_id=method,
            source_type="reddit_community_report", status="disabled", candidates_found=0, accepted_reports=0,
            rejected_reports=0, blocked_reason=REASON, last_run="", notes=pol.POLICY_NOTE)
        row.update(over)
        return row

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "emh.yml"
        real = base.method_health_row(
            product_id="blackmagic-davinci", update_version="21", method_id="reddit_search",
            source_type="reddit_community_report", status="blocked", candidates_found=0, accepted_reports=0,
            rejected_reports=0, blocked_reason="http_403_Blocked", last_run="2026-11-04T00:18:00Z", notes="old")
        base.upsert_method_health([real], path)
        changed, _t, rows = base.upsert_method_health([policy_row()], path)
        got = [r for r in rows if r["method_id"] == "reddit_search"][0]
        check("F.1 the prior real last attempt survives the policy row", got["last_run"] == "2026-11-04T00:18:00Z", got["last_run"])
        check("F.2 status/reason/notes are the policy's", (got["status"], got["blocked_reason"], got["notes"]) == ("disabled", REASON, pol.POLICY_NOTE))
        changed2, _t, rows2 = base.upsert_method_health([policy_row()], path)
        check("F.3 idempotent: a second identical run changes nothing", changed2 == 0)
        check("F.4 stored file round-trips with the same last_run",
              [r for r in base.load_method_health(path) if r["method_id"] == "reddit_search"][0]["last_run"] == "2026-11-04T00:18:00Z")
        changed3, _t, rows3 = base.upsert_method_health([policy_row("22")], path)
        check("F.5 a patch never attempted gets an empty timestamp, not a made-up one",
              [r for r in rows3 if r["update_version"] == "22"][0]["last_run"] == "")
        other = policy_row(blocked_reason="", last_run="")
        other["method_id"] = "web_search"
        base.upsert_method_health([base.method_health_row(
            product_id="blackmagic-davinci", update_version="21", method_id="web_search", source_type="web_search",
            status="success", candidates_found=0, accepted_reports=0, rejected_reports=0, blocked_reason="",
            last_run="2026-10-01T00:00:00Z", notes="")], path)
        _c, _t, rows4 = base.upsert_method_health([other], path)
        check("F.6 the carry-over is for POLICY rows only: any other disabled row is written as given",
              [r for r in rows4 if r["method_id"] == "web_search"][0]["last_run"] == "")
        live = base.method_health_row(
            product_id="blackmagic-davinci", update_version="21", method_id="reddit_search",
            source_type="reddit_community_report", status="no_results", candidates_found=0, accepted_reports=0,
            rejected_reports=0, blocked_reason="", last_run="2027-01-01T00:00:00Z", notes="live")
        _c, _t, rows5 = base.upsert_method_health([live], path)
        check("F.7 once authorised, a real row replaces the policy row with its own fresh timestamp",
              [r for r in rows5 if r["method_id"] == "reddit_search" and r["update_version"] == "21"][0]["last_run"] == "2027-01-01T00:00:00Z")
        check("F.8 is_policy_disabled_row requires BOTH disabled and the reason",
              pol.is_policy_disabled_row(policy_row()) and not pol.is_policy_disabled_row(policy_row(status="blocked"))
              and not pol.is_policy_disabled_row(policy_row(blocked_reason="")))

    # ---- G: certification is not softened -------------------------------------------------------
    print("G. certification")
    now = datetime(2026, 11, 5, tzinfo=timezone.utc)
    th = mh.Thresholds(max_age_days=14, min_healthy_families=2)

    def row(method: str, family: str, status: str, last_run: str) -> dict:
        return {"product_id": "blackmagic-davinci", "update_version": "21", "target_build": "", "method_id": method,
                "source_type": family, "status": status, "last_run": last_run}

    healthy = [row("known_watchlist", "curated_watchlist", "success", "2026-11-04T12:00:00Z"),
               row("vendor_forum_search", "blackmagic_forum", "no_results", "2026-11-04T12:00:00Z")]
    disabled_reddit = row("reddit_search", "reddit_community_report", "disabled", "")
    owned = {"blackmagic-davinci": ["known_watchlist", "vendor_forum_search", "reddit_search"]}
    d = mh.certify_monitoring("blackmagic-davinci", healthy + [disabled_reddit], published_at="2026-04-14T00:00:00Z",
                              contributing_families=["reddit_community_report", "blackmagic_forum"], now=now,
                              thresholds=th, owned_methods=owned)
    check("G.1 a patch whose counted evidence is Reddit is NOT certified while Reddit is disabled",
          (not d.healthy) and "contributing_family_unhealthy:reddit_community_report" in d.reasons, str(d.reasons))
    d2 = mh.certify_monitoring("blackmagic-davinci", healthy + [disabled_reddit], published_at="2026-04-14T00:00:00Z",
                               contributing_families=["blackmagic_forum"], now=now, thresholds=th, owned_methods=owned)
    check("G.2 the disabled row satisfies H7 (it is not a missing method) and adds no failure", d2.healthy, str(d2.reasons))
    blocked_reddit = row("reddit_search", "reddit_community_report", "blocked", "2026-11-04T00:18:00Z")
    before = mh.ladder(healthy + [blocked_reddit], published_at="2026-04-14T00:00:00Z", report_count=75, now=now, thresholds=th)
    after = mh.ladder(healthy + [disabled_reddit], published_at="2026-04-14T00:00:00Z", report_count=75, now=now, thresholds=th)
    check("G.3 public label before (blocked Reddit row beside healthy families) is MONITORING DEGRADED", before == mh.MONITORING_DEGRADED, before)
    check("G.4 public label after is MONITORING ACTIVE only because the active families still meet the floor", after == mh.MONITORING_ACTIVE, after)
    only_reddit_healthy = [row("reddit_search", "reddit_community_report", "success", "2026-11-04T12:00:00Z")]
    one_other = [row("known_watchlist", "curated_watchlist", "success", "2026-11-04T12:00:00Z")]
    lab = mh.ladder(one_other + [disabled_reddit], published_at="2026-04-14T00:00:00Z", report_count=75, now=now, thresholds=th)
    check("G.5 a disabled Reddit family never counts toward the healthy-family floor", lab == mh.INSUFFICIENT_COVERAGE, lab)
    lab_all = mh.ladder([disabled_reddit], published_at="2026-04-14T00:00:00Z", report_count=75, now=now, thresholds=th)
    check("G.6 only-Reddit patches read OFFICIAL SOURCE ONLY (never active)", lab_all == mh.OFFICIAL_SOURCE_ONLY, lab_all)
    check("G.7 (control) a healthy Reddit row WOULD count as a family, so G.5 is not vacuous",
          mh.ladder(one_other + only_reddit_healthy, published_at="2026-04-14T00:00:00Z", report_count=75, now=now,
                    thresholds=th) == mh.MONITORING_ACTIVE)

    # ---- H: reachability + workflows -----------------------------------------------------------
    print("H. switch reachability and workflow configuration")
    wf_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in (REPO / ".github").rglob("*.yml"))
    check("H.1 no workflow sets the authorisation reference", ENV not in wf_text)
    check("H.2 no workflow turns the PowerPoint Reddit fallback on", "AUXSAYS_POWERPOINT_REDDIT_FALLBACK" not in wf_text)
    check("H.3 no workflow sets a Reddit bearer token / client secret",
          "REDDIT_BEARER_TOKEN" not in wf_text and "REDDIT_CLIENT" not in wf_text)
    for name, mod in (("davinci", dv), ("reddit_source", rs)):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for fn in ("request_json", "request_reddit_feed"):
            start = src.index(f"def {fn}(")
            check(f"H.4 {name}.{fn} opens with the access guard", "require_reddit_access()" in src[start:start + 400])

    # ---- I: manual seed tool ---------------------------------------------------------------------
    print("I. manual DaVinci seed tool")
    import collect_davinci_candidates as cdc                      # noqa: E402
    s = cdc.Seed(source_url="https://www.reddit.com/r/davinciresolve/comments/1/x/",
                 source_type="reddit_community_report", source_title="t",
                 candidate_update_version_raw="21", issue_summary="", evidence_category="", severity="")
    real_cdc0 = cdc.urlopen
    cdc.urlopen = lambda *a, **k: (_ for _ in ()).throw(Refused("network blocked by test"))
    try:
        with Env(None):
            out = cdc.fetch_source(s)
    finally:
        cdc.urlopen = real_cdc0
    check("I.1 an unauthorised Reddit seed is not fetched", out["access_status"] == REASON, str(out))
    # The seed tool imported urlopen by name, so the NetWatch patch of urllib.request does not reach it.
    seen_cdc: list[str] = []

    def fake_cdc_urlopen(req, *a, **k):
        seen_cdc.append(getattr(req, "full_url", str(req)))
        raise Refused("network blocked by test")

    real_cdc = cdc.urlopen
    cdc.urlopen = fake_cdc_urlopen
    try:
        with Env(None):
            cdc.fetch_source(s)
        unauth_calls = len(seen_cdc)
        with Env("agreement-ref-1"):
            cdc.fetch_source(s)
    finally:
        cdc.urlopen = real_cdc
    net = types.SimpleNamespace(urls=seen_cdc, reddit=[u for u in seen_cdc if pol.is_reddit_url(u)])
    check("I.1b the unauthorised call reached urlopen zero times", unauth_calls == 0, str(seen_cdc))
    check("I.2 authorised, the same seed is requested (switch is reachable)", len(net.reddit) == 1, str(net.urls))

    print()
    print("=" * 92)
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")  # LAST line of stdout (runner contract)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
