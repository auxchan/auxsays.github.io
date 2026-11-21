#!/usr/bin/env python3
"""The one GitHub API transport, its callers, the open-web provider removal and the handle filter (G49).

Every AUXSAYS request to api.github.com now goes through lib/github_api.get_json. This suite drives
that function, and every production caller of it, over a FAKE WIRE (lib.github_api._urlopen), so each
claim is checked on the requests that would actually be sent:

  T   the transport: identity, origin, pacing, the three refusals told apart, Retry-After and
      x-ratelimit-reset honoured, the in-run stop with zero further requests, the pagination contract
  C   the callers: PowerPoint (OfficeDev), ComfyUI, OBS and the GitHub Releases adapter stop on a
      refusal, report it as `blocked`/`partial` in the existing health vocabulary, never as success,
      and leave stored evidence untouched; lib/http never sends GitHub a browser string
  P   the open-web federation no longer asks GitHub search, and every GitHub URL it used to return
      was discarded before any request -- the replay that proves nothing depended on it
  H   contributor handles leave release notes; changes, links and look-alikes stay; the stored
      corpus is migrated and the adapter agrees with the migration byte for byte

Offline: no network (the wire refuses anything unscripted), no repository writes (temp stores only).
"""
from __future__ import annotations

import ast
import email.message
import email.utils
import io
import json
import os
import re
import sys
import tempfile
import traceback
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import collect_obs_reports as obs  # noqa: E402
import migrate_strip_release_note_handles as migration  # noqa: E402
from adapters import github_releases  # noqa: E402
from lib import contributor_credits as cc  # noqa: E402
from lib import github_api  # noqa: E402
from lib import http as lib_http  # noqa: E402
from lib.normalize import split_front_matter  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import comfyui as comfy  # noqa: E402
from patch_collectors import github_officedev_source as gh  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors import obs as obs_adapter  # noqa: E402
from patch_collectors import open_web_source as ow  # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []
NOW = 1_800_000_000.0          # a fixed wall clock: 2027-01-15T08:00:00Z


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def section(title: str) -> None:
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)


# --------------------------------------------------------------------------- the fake wire
class _Response:
    def __init__(self, payload, headers: dict[str, str]):
        self._raw = json.dumps(payload).encode("utf-8")
        self.headers = _headers(headers)

    def read(self, n: int | None = None) -> bytes:
        return self._raw if n is None else self._raw[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _headers(values: dict[str, str]) -> email.message.Message:
    msg = email.message.Message()
    for key, value in (values or {}).items():
        msg[key] = value
    return msg


def ok(payload, headers: dict[str, str] | None = None):
    return ("ok", payload, headers or {})


def refuse(status: int, body: str = "", headers: dict[str, str] | None = None):
    return ("http", status, body, headers or {})


class Wire:
    """Scripted responses, in order, for requests whose URL contains a key. Anything unscripted is a
    test failure and raises, so no request can quietly reach the real network."""

    def __init__(self, script: list[tuple[str, tuple]]):
        self.script = list(script)
        self.requests: list[dict] = []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.requests.append({
            "url": url,
            "user_agent": request.get_header("User-agent"),
            "accept": request.get_header("Accept"),
            "plain_auth": request.headers.get("Authorization"),
            "unredirected_auth": request.unredirected_hdrs.get("Authorization"),
        })
        for index, (key, answer) in enumerate(self.script):
            if key in url:
                del self.script[index]
                if answer[0] == "ok":
                    return _Response(answer[1], answer[2])
                _kind, status, body, headers = answer
                raise urllib.error.HTTPError(url, status, "refused", _headers(headers),
                                             io.BytesIO(body.encode("utf-8")))
        raise AssertionError(f"unscripted request: {url}")


class Harness:
    """Installs a wire and a fake clock on the transport, and restores everything on exit."""

    def __init__(self, script, token: str | None = None):
        self.wire = Wire(script)
        self.sleeps: list[float] = []
        self.clock = [100.0]
        self.token = token

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(round(seconds, 3))
        self.clock[0] += seconds

    def __enter__(self):
        self.saved = (github_api._urlopen, github_api._sleep, github_api._monotonic, github_api._wall,
                      os.environ.get("GITHUB_TOKEN"), os.environ.get("GH_TOKEN"))
        github_api.reset_run_state()
        github_api._urlopen = self.wire
        github_api._sleep = self._sleep
        github_api._monotonic = lambda: self.clock[0]
        github_api._wall = lambda: NOW
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GH_TOKEN", None)
        if self.token:
            os.environ["GITHUB_TOKEN"] = self.token
        return self

    def __exit__(self, *exc):
        (github_api._urlopen, github_api._sleep, github_api._monotonic, github_api._wall,
         token, gh_token) = self.saved
        for name, value in (("GITHUB_TOKEN", token), ("GH_TOKEN", gh_token)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        github_api.reset_run_state()
        return False


API = "https://api.github.com"
SEARCH = f"{API}/search/issues?q=x"


def iso(epoch: float) -> str:
    return github_api._iso(epoch)


def raised(fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        return exc
    return None


# =========================================================================== T: the transport
def section_transport() -> None:
    section("T  the transport: identity, origin, pacing, refusals, Retry-After/reset, in-run stop")

    with Harness([("/a", ok({"items": []})), ("/b", ok({"items": []}))], token="tok-test") as h:
        github_api.get_json(f"{API}/a")
        github_api.get_json(f"{API}/b")
        first = h.wire.requests[0]
        check("T1.1 every request names AUXSAYS and where to reach it",
              all(r["user_agent"] == "AUXSAYS-patch-evidence/1.0 (+https://auxsays.com)"
                  for r in h.wire.requests), str([r["user_agent"] for r in h.wire.requests]))
        check("T1.2 no browser string is ever sent to GitHub",
              not any("Mozilla" in str(r["user_agent"]) for r in h.wire.requests))
        check("T1.3 GitHub's JSON media type is requested", first["accept"] == "application/vnd.github+json")
        check("T1.4 the token rides as an UNREDIRECTED header only (never follows a redirect)",
              first["unredirected_auth"] == "Bearer tok-test" and first["plain_auth"] is None, str(first))
        check("T1.5 requests are serial and paced at MIN_INTERVAL (one wait before the second)",
              h.sleeps == [github_api.MIN_INTERVAL], str(h.sleeps))
        check("T1.6 the pace stays under GitHub's 30 searches a minute",
              60.0 / github_api.MIN_INTERVAL < 30.0, str(github_api.MIN_INTERVAL))
        check("T1.7 requests_sent counts what was actually sent", github_api.requests_sent() == 2)

    for bad in ("https://api.github.com.evil.example/x", "http://api.github.com/x",
                "https://api.github.com:444/x", "https://user:pw@api.github.com/x", "https://github.com/x"):
        with Harness([], token="tok-test") as h:
            exc = raised(lambda: github_api.get_json(bad))
            check(f"T2 off-origin URL refused before sending (token never leaves): {bad}",
                  isinstance(exc, github_api.GitHubError) and exc.reason == github_api.OFF_ORIGIN
                  and exc.sent is False and h.wire.requests == [], repr(exc))

    cases = (
        ("T3.1 429 is rate limiting", refuse(429, "Too many requests"), github_api.RATE_LIMITED),
        ("T3.2 403 with x-ratelimit-remaining 0 is rate limiting",
         refuse(403, "forbidden", {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(NOW) + 1800)}),
         github_api.RATE_LIMITED),
        ("T3.3 403 with a secondary-rate-limit body is rate limiting",
         refuse(403, '{"message": "You have exceeded a secondary rate limit. Please wait a few minutes."}'),
         github_api.RATE_LIMITED),
        ("T3.4 403 with a retry-after header is rate limiting",
         refuse(403, "", {"retry-after": "120"}), github_api.RATE_LIMITED),
        ("T3.5 401 is an access denial", refuse(401, '{"message": "Bad credentials"}'), github_api.ACCESS_DENIED),
        ("T3.6 403 whose body refuses the credentials' permissions is an access denial",
         refuse(403, '{"message": "Resource not accessible by integration"}'), github_api.ACCESS_DENIED),
        ("T3.7 any other 403 is its own reason, not rate limiting and not an access denial",
         refuse(403, '{"message": "Repository access blocked"}'), github_api.FORBIDDEN),
    )
    for label, answer, expected in cases:
        with Harness([("/s", answer), ("/next", ok({}))]) as h:
            exc = raised(lambda: github_api.get_json(f"{API}/s"))
            check(label, isinstance(exc, github_api.GitHubError) and exc.reason == expected
                  and exc.sent is True, repr(getattr(exc, "reason", exc)))
            later = raised(lambda: github_api.get_json(f"{API}/next"))
            check(f"{label.split()[0]}b ...and it STOPS the run: the next call sends nothing",
                  len(h.wire.requests) == 1 and isinstance(later, github_api.GitHubError)
                  and later.reason == expected and later.sent is False,
                  f"{len(h.wire.requests)} sent, {later!r}")
            check(f"{label.split()[0]}c ...and the stop is visible to health telemetry",
                  (github_api.stop_state() or {}).get("reason") == expected
                  and github_api.is_stop(expected) and expected in github_api.stop_note())

    with Harness([("/s", refuse(403, "", {"x-ratelimit-remaining": "0",
                                          "x-ratelimit-reset": str(int(NOW) + 1800)}))]):
        exc = raised(lambda: github_api.get_json(f"{API}/s"))
        check("T4.1 x-ratelimit-reset is honoured: the earliest retry is the reset time",
              exc.retry_at == iso(NOW + 1800) and github_api.stop_state()["retry_at"] == iso(NOW + 1800),
              exc.retry_at)
    with Harness([("/s", refuse(429, "", {"retry-after": "300"}))]):
        exc = raised(lambda: github_api.get_json(f"{API}/s"))
        check("T4.2 Retry-After (seconds) is honoured", exc.retry_at == iso(NOW + 300), exc.retry_at)
    when = email.utils.formatdate(NOW + 900, usegmt=True)
    with Harness([("/s", refuse(429, "", {"retry-after": when}))]):
        exc = raised(lambda: github_api.get_json(f"{API}/s"))
        check("T4.3 Retry-After (HTTP date) is honoured", exc.retry_at == iso(NOW + 900), exc.retry_at)
    with Harness([("/s", refuse(429, "", {"retry-after": "5"}))]):
        exc = raised(lambda: github_api.get_json(f"{API}/s"))
        check("T4.4 never sooner than the minimum backoff (GitHub: at least a minute)",
              exc.retry_at == iso(NOW + github_api.MIN_BACKOFF_SECONDS), exc.retry_at)
    with Harness([("/s", refuse(403, "You have exceeded a secondary rate limit"))]):
        exc = raised(lambda: github_api.get_json(f"{API}/s"))
        check("T4.5 a refusal naming no time waits the minimum backoff",
              exc.retry_at == iso(NOW + github_api.MIN_BACKOFF_SECONDS), exc.retry_at)

    with Harness([("/missing", refuse(404, "Not Found")), ("/after", ok({"items": []})),
                  ("/broken", refuse(502, "Bad gateway")), ("/after2", ok({"items": []}))]) as h:
        exc = raised(lambda: github_api.get_json(f"{API}/missing"))
        github_api.get_json(f"{API}/after")
        exc2 = raised(lambda: github_api.get_json(f"{API}/broken"))
        github_api.get_json(f"{API}/after2")
        check("T5.1 a 404 or 5xx is an ordinary error, not a stop: later requests still go out",
              exc.reason == "http_404_error" and exc2.reason == "http_502_error"
              and len(h.wire.requests) == 4 and github_api.stop_state() is None,
              f"{exc!r} {exc2!r} {len(h.wire.requests)}")

    meta_next = {"Link": f'<{API}/search/issues?page=2>; rel="next", <{API}/search/issues?page=4>; rel="last"'}
    full = {"total_count": 999, "items": [{"n": 1}]}
    check("T6.1 Link rel=next means another page",
          github_api.has_next_page(meta_next, full, page=1, per_page=100))
    check("T6.2 a Link header without rel=next means the last page, whatever the page size",
          not github_api.has_next_page({"Link": f'<{API}/x?page=1>; rel="first"'},
                                       {"total_count": 999, "items": [{}] * 100}, page=2, per_page=100))
    check("T6.3 no Link header from GitHub (meta Link '') means a single page",
          not github_api.has_next_page({"Link": ""}, {"total_count": 999, "items": [{}] * 100},
                                       page=1, per_page=100))
    check("T6.4 without transport headers, total_count decides (not the page size)",
          github_api.has_next_page({}, {"total_count": 150, "items": [{}] * 40}, page=1, per_page=100)
          and not github_api.has_next_page({}, {"total_count": 40, "items": [{}] * 40}, page=1, per_page=100))
    check("T6.5 an empty page always ends the walk",
          not github_api.has_next_page(meta_next, {"total_count": 999, "items": []}, page=1, per_page=100))
    with Harness([("/p", ok({"items": []}, {"Link": f'<{API}/p?page=2>; rel="next"', "X-RateLimit-Remaining": "29"}))]):
        _payload, meta = github_api.get_json(f"{API}/p")
        check("T6.6 the transport hands back Link and the rate headers",
              "next" in github_api.links(meta) and meta.get("X-RateLimit-Remaining") == "29", str(meta))
    with Harness([("/p", ok({"items": []}))]):
        _payload, meta = github_api.get_json(f"{API}/p")
        check("T6.7 Link is always present in transport metadata, empty when GitHub sent none",
              meta.get("Link") == "", str(meta))


# =========================================================================== C: the callers
def _ppt_record() -> base.PatchRecord:
    return base.PatchRecord(product_id="microsoft-powerpoint", update_version="2607",
                            path=Path("synthetic-2607.md"), update_published_at="2026-07-29T00:00:00Z",
                            update_status="current", update_product="Microsoft PowerPoint",
                            target_build="20228.20124")


def section_callers() -> None:
    section("C  callers stop on a refusal, report it truthfully, and never mark it success")

    # --- PowerPoint / OfficeDev -----------------------------------------------------------------
    errors: list[dict] = []
    with Harness([("search/issues", refuse(403, "You have exceeded a secondary rate limit"))]) as h:
        found, tel = gh.collect_officedev_candidates(queries=["q1", "q2", "q3"], errors=errors, max_requests=3)
        check("C1.1 OfficeDev: the first refusal ends the query loop -- one request, not three",
              len(h.wire.requests) == 1 and tel["requests"] == 1 and tel["queries"] == 1,
              f"{len(h.wire.requests)} sent, {tel}")
        check("C1.2 ...and the refusal is recorded with its reason",
              [e["reason"] for e in errors] == ["rate_limited"], str(errors))

    ctx = base.CollectorContext(write=False, since=None, max_pages=5)
    target = {"update_version": "2607", "target_build": "20228.20124", "target_app_version": "2607",
              "target_channel": "", "target_release_date": "2026-07-29T00:00:00Z"}
    record = _ppt_record()
    ppt.reset_symptom_cache()
    with Harness([("search/issues", refuse(429, "slow down", {"retry-after": "90"}))]) as h:
        _a, _r, row1 = ppt.run_github_method(record, target, ctx, set(), {}, "2026-11-19T00:00:00Z")
        sent_after_first = len(h.wire.requests)
        _a, _r, row2 = ppt.run_github_method(record, {**target, "target_build": ""}, ctx, set(), {},
                                             "2026-11-19T00:00:01Z")
        check("C1.3 PowerPoint health after a refusal is `blocked`, naming rate_limited",
              row1["status"] == "blocked" and "rate_limited" in row1["blocked_reason"], str(row1))
        check("C1.4 a later record whose ONLY GitHub input is the cached symptom route is not a "
              "complete collection: `blocked`, never no_results/success",
              row2["status"] == "blocked" and "rate_limited" in row2["blocked_reason"], str(row2))
        check("C1.5 ...and that later record sent no GitHub request at all",
              len(h.wire.requests) == sent_after_first == 1, f"{len(h.wire.requests)}")
        check("C1.6 the health note says GitHub refused and names the earliest retry",
              "no further GitHub request was sent" in row1["notes"] and iso(NOW + 90) in row1["notes"],
              row1["notes"][-200:])
    ppt.reset_symptom_cache()
    for reason in ("access_denied", "http_403_error"):
        check(f"C1.7 PowerPoint status: a stop for {reason} is `blocked` too, not broken",
              ppt.github_method_status([], [], [], [{"reason": reason}]) == "blocked")
    check("C1.8 an ordinary error alone is still `broken`",
          ppt.github_method_status([], [], [], [{"reason": "http_502_error"}]) == "broken")

    # --- ComfyUI ---------------------------------------------------------------------------------
    page1 = [{"number": 20000 - i, "html_url": f"{comfy.ISSUE_URL_PREFIX}{20000 - i}", "title": "t",
              "body": "b", "created_at": "2026-11-10T00:00:00Z"} for i in range(comfy.PER_PAGE)]
    with Harness([("page=1", ok({"total_count": 75, "items": page1},
                                {"Link": f'<{API}/search/issues?page=2>; rel="next"'})),
                  ("page=2", refuse(403, "", {"x-ratelimit-remaining": "0",
                                               "x-ratelimit-reset": str(int(NOW) + 600)}))]) as h:
        errs: list[dict] = []
        issues, tel = comfy.enumerate_issues("2026-10-01", errs)
        status = comfy.method_status(errs, tel, 0)
        check("C2.1 ComfyUI: a refusal mid-walk keeps what was read and stops",
              len(issues) == comfy.PER_PAGE and len(h.wire.requests) == 2, f"{len(issues)} {len(h.wire.requests)}")
        check("C2.2 ...and an incomplete walk is `partial`, never success or no_results",
              status == "partial" and errs[0]["reason"] == "rate_limited", f"{status} {errs}")
        before = len(h.wire.requests)
        errs2: list[dict] = []
        _issues2, tel2 = comfy.enumerate_issues("2026-10-01", errs2)
        check("C2.3 a second walk in the same run sends nothing and reads `blocked`",
              len(h.wire.requests) == before and comfy.method_status(errs2, tel2, 0) == "blocked",
              f"{len(h.wire.requests)} {errs2}")
    with Harness([("page=1", ok({"total_count": 999, "items": page1}, {"Link": ""}))]) as h:
        issues, tel = comfy.enumerate_issues("2026-10-01", [])
        check("C2.4 ComfyUI pages by the Link contract: a full page without rel=next is the last",
              len(h.wire.requests) == 1 and tel["pages"] == 1, f"{len(h.wire.requests)}")
    check("C2.5 ComfyUI: a walk refused before any page is `blocked` for every stop reason",
          all(comfy.method_status([{"reason": r}], {"pages": 0}, 0) == "blocked"
              for r in ("rate_limited", "access_denied", "http_403_error")))

    # --- OBS -------------------------------------------------------------------------------------
    items = [{"url": f"{API}/repos/obsproject/obs-studio/issues/{n}", "number": n,
              "html_url": f"https://github.com/obsproject/obs-studio/issues/{n}", "title": "x", "body": "y",
              "created_at": "2026-11-01T00:00:00Z"} for n in (101, 102, 103)]
    with Harness([("search/issues", ok({"total_count": 3, "items": items}, {"Link": ""}))]) as h:
        found: list = []
        exc = raised(lambda: found.extend(obs.search_issues("32.1.2", None, 5)))
        check("C3.1 OBS: a version with fewer hits than a page costs ONE search (no empty page 2)",
              exc is None and len(found) == 3 and len(h.wire.requests) == 1, f"{len(h.wire.requests)} {exc!r}")
    with Harness([("page=1", ok({"total_count": 4, "items": items}, {"Link": f'<{API}/x?page=2>; rel="next"'})),
                  ("page=2", ok({"total_count": 4, "items": [{**items[0], "url": items[0]["url"] + "9"}]},
                                {"Link": ""}))]) as h:
        found = []
        exc = raised(lambda: found.extend(obs.search_issues("32.1.2", None, 5)))
        check("C3.2 OBS follows rel=next and stops where GitHub says the results end",
              exc is None and len(found) == 4 and len(h.wire.requests) == 2,
              f"{len(found)} {len(h.wire.requests)} {exc!r}")
    check("C3.3 OBS no longer has its own transport or browser/beta User-Agent",
          "AUXSAYS-OBS-Report-Beta" not in (SCRIPTS / "collect_obs_reports.py").read_text(encoding="utf-8")
          and "urlopen" not in (SCRIPTS / "collect_obs_reports.py").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        store.write_text(yaml.safe_dump({"schema_version": 1, "evidence": [
            {"id": "obs-studio-32-1-2-github-issue-1", "product_id": "obs-studio", "update_version": "32.1.2",
             "source_url": "https://github.com/obsproject/obs-studio/issues/1", "counted": True,
             "patch_version_matched": True}]}, sort_keys=False), encoding="utf-8")
        before = store.read_bytes()
        saved = obs.EVIDENCE_PATH
        obs.EVIDENCE_PATH = store
        try:
            with Harness([("search/issues", ok({"total_count": 3, "items": items}, {"Link": ""})),
                          ("issues/101", ok(items[0])),
                          ("issues/102", refuse(403, "You have exceeded a secondary rate limit"))]) as h:
                status, result = obs.collect_one("32.1.2", None, None, 5, True)
                sent = len(h.wire.requests)
                health, reason = obs_adapter.github_health(status, result)
                check("C3.4 OBS: a refusal while fetching issues aborts the version (not evaluated "
                      "from a cut-short set)", status == 1 and result.get("github_status") == "failed"
                      and result.get("error") == "rate_limited", str(result))
                check("C3.5 ...its health is `blocked` naming rate_limited, never success",
                      health == "blocked" and reason == "rate_limited", f"{health} {reason}")
                check("C3.6 ...and the stored evidence is byte-identical (a stop drops nothing)",
                      store.read_bytes() == before)
                check("C3.7 ...and no request followed the refusal (103 was never fetched)",
                      sent == 3 and not any("issues/103" in r["url"] for r in h.wire.requests), str(sent))
                status2, result2 = obs.collect_one("32.2.0", None, None, 5, True)
                check("C3.8 the next OBS version in the same run sends nothing and is `blocked`",
                      len(h.wire.requests) == sent
                      and obs_adapter.github_health(status2, result2)[0] == "blocked", str(result2))
            with Harness([("search/issues", ok({"total_count": 1, "items": items[:1]}, {"Link": ""})),
                          ("issues/101", refuse(404, "Not Found"))]) as h:
                status3, result3 = obs.collect_one("32.1.2", None, None, 5, False)
                check("C3.9 an ordinary fetch failure (404) still falls back to the search item, as before",
                      status3 == 0 and result3.get("github_status") == "ok"
                      and result3.get("candidates_reviewed") == 1, str(result3))
        finally:
            obs.EVIDENCE_PATH = saved
    check("C3.10 OBS: an ordinary GitHub failure is still `broken`, not blocked",
          obs_adapter.github_health(1, {"github_status": "failed", "github_error": "http_502_error"})[0] == "broken")

    # --- GitHub Releases official adapter ----------------------------------------------------------
    source = {"product_id": "comfyui", "company_id": "comfyui", "company": "ComfyUI", "software": "ComfyUI",
              "ingestion": {"api_url": f"{API}/repos/Comfy-Org/ComfyUI/releases"}}
    release = {"id": 1, "tag_name": "v9.9.9", "name": "v9.9.9", "published_at": "2026-11-18T00:00:00Z",
               "html_url": "https://github.com/Comfy-Org/ComfyUI/releases/tag/v9.9.9", "assets": [],
               "body": ("## What's Changed\r\n* Fix a crash by @someone in "
                        "https://github.com/Comfy-Org/ComfyUI/pull/1\r\n\r\n## New Contributors\r\n"
                        "* @someone made their first contribution in https://github.com/Comfy-Org/ComfyUI/pull/1"
                        "\r\n\r\n**Full Changelog**: https://github.com/Comfy-Org/ComfyUI/compare/v9.9.8...v9.9.9")}
    with Harness([("releases", ok([release]))]) as h:
        records = github_releases.fetch(source)
        body = records[0]["body"]
        check("C4.1 the official Releases adapter uses the shared transport (truthful UA)",
              len(h.wire.requests) == 1 and h.wire.requests[0]["user_agent"] == github_api.USER_AGENT)
        check("C4.2 ...and stores the release body without the contributor's handle",
              "@someone" not in body and "([PR #1](https://github.com/Comfy-Org/ComfyUI/pull/1))" in body
              and "New Contributors" not in body and "[Full changelog](" in body, repr(body))
    with Harness([("releases", refuse(403, "", {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(NOW) + 60)})),
                  ("other", ok([]))]) as h:
        exc = raised(lambda: github_releases.fetch(source))
        exc2 = raised(lambda: github_releases.fetch({**source, "ingestion": {"api_url": f"{API}/repos/o/other/releases"}}))
        check("C4.3 a refusal reads like every other official failure and names the reason",
              isinstance(exc, RuntimeError)
              and str(exc) == "HTTP 403 while fetching official GitHub source — rate_limited", str(exc))
        check("C4.4 the next GitHub release source in the same ingestion run sends nothing",
              isinstance(exc2, RuntimeError) and len(h.wire.requests) == 1, f"{exc2} {len(h.wire.requests)}")

    # --- lib/http never sends GitHub a browser string -------------------------------------------------
    seen: list[str] = []

    class _Resp:
        status = 200
        headers = _headers({"Content-Type": "application/json"})

        def read(self, n=None):
            return b"[]"

        def geturl(self):
            return "https://api.github.com/x"

        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False

    saved_open = lib_http._OPENER.open
    lib_http._OPENER.open = lambda req, timeout=None: (seen.append(req.get_header("User-agent")), _Resp())[1]
    try:
        lib_http.fetch_text("https://api.github.com/repos/o/r/releases")
        lib_http.fetch_text("https://vendor.example/notes")
    finally:
        lib_http._OPENER.open = saved_open
    check("C5.1 lib/http sends api.github.com the truthful AUXSAYS User-Agent",
          seen[0] == lib_http.GITHUB_API_USER_AGENT and "Mozilla" not in seen[0], str(seen))
    check("C5.2 ...and vendor documentation requests are unchanged", seen[1] == lib_http.USER_AGENT, str(seen))


# =========================================================================== P: provider removal
def section_provider_removal() -> None:
    section("P  the open-web lane no longer asks GitHub search, and nothing depended on it")
    names = [name for name, _fn in ow.PROVIDERS]
    check("P1.1 github_search is not a provider", "github_search" not in names, str(names))
    tree = ast.parse((SCRIPTS / "patch_collectors" / "open_web_source.py").read_text(encoding="utf-8"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports |= {a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
    funcs = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    check("P1.2 the federation neither imports a GitHub transport nor defines a GitHub search",
          not any("github" in m for m in imports) and "search_github" not in funcs
          and "github_officedev_source" not in ast.dump(tree), f"{imports} {funcs}")

    calls: dict[str, int] = {"learn": 0, "se": 0}

    def learn(query):
        calls["learn"] += 1
        return [f"https://learn.microsoft.com/en-us/answers/questions/{len(query)}/"]

    def stack(query):
        calls["se"] += 1
        return []

    saved = ow.PROVIDERS
    ow.PROVIDERS = (("learn_qna_search", learn), ("stack_exchange_search", stack))
    try:
        with Harness([]) as h:
            queries = ow.build_queries(version="2607", build="20228.20124", max_queries=ppt.OPEN_WEB_MAX_QUERIES)
            ow.discover_urls(queries, errors=[], max_requests=ppt.OPEN_WEB_MAX_REQUESTS)
            check("P2.1 an open-web discovery run sends ZERO requests to api.github.com",
                  h.wire.requests == [] and github_api.requests_sent() == 0)
    finally:
        ow.PROVIDERS = saved
    # Before G49: 3 providers x 8 queries = the 24-request budget. After: the same 8 queries.
    check("P2.2 Learn and Stack Exchange are asked exactly as often as before (8 queries each)",
          calls == {"learn": 8, "se": 8}, str(calls))

    with Harness([]) as h:
        dropped = ppt.hydrate_discovered_url({"source_type": "github_officedev_issue",
                                              "source_url": "https://github.com/OfficeDev/office-js/issues/7054"})
        check("P3.1 REPLAY of the old path: every GitHub URL open-web discovery returned was "
              "discarded at hydration (None) without a single request",
              dropped is None and h.wire.requests == [], repr(dropped))
    src = (SCRIPTS / "patch_collectors" / "microsoft_powerpoint.py").read_text(encoding="utf-8")
    hydrate = src.split("def hydrate_discovered_url", 1)[1].split("\ndef ", 1)[0]
    check("P3.2 ...because hydration has no GitHub branch at all (the code path the hits died in)",
          "github" not in hydrate.lower() and hydrate.rstrip().endswith("return None"))
    check("P3.3 OfficeDev issues keep their own native lane in the PowerPoint method plan",
          ppt.GITHUB_METHOD_ID == "github_officedev_issues" and "run_github_method(" in src)


# =========================================================================== H: handles
def section_handles() -> None:
    section("H  contributor handles leave release notes; meaning, links and look-alikes stay")
    norm = github_releases.release_body
    cases_dropped = (
        ("H1.1 GitHub's raw credit becomes a bare PR link",
         "* Fix crash by @alice in https://github.com/o/r/pull/12",
         "* Fix crash ([PR #12](https://github.com/o/r/pull/12))"),
        ("H1.2 the normalised credit form",
         "* Fix crash by @alice ([PR #12](https://github.com/o/r/pull/12))",
         "* Fix crash ([PR #12](https://github.com/o/r/pull/12))"),
        ("H1.3 several credited accounts",
         "* Add node by @alice and @bob-2 ([PR #3](https://github.com/o/r/pull/3))",
         "* Add node ([PR #3](https://github.com/o/r/pull/3))"),
        ("H1.4 a bot account", "* Bump x to 1.2 by @comfy-pr-bot ([PR #4](https://github.com/o/r/pull/4))",
         "* Bump x to 1.2 ([PR #4](https://github.com/o/r/pull/4))"),
        ("H1.5 a credit at the end of a line keeps the full stop", "Faster on Windows by @rattus128.",
         "Faster on Windows."),
    )
    for label, given, expected in cases_dropped:
        got = norm(given)
        check(label, got == expected, repr(got))
    given = ("## Changes\r\n* Fix it by @alice ([PR #1](https://github.com/o/r/pull/1))\r\n\r\n"
             "## New Contributors\r\n* @alice made their first contribution in https://github.com/o/r/pull/1\r\n"
             "* @bob made their first contribution in https://github.com/o/r/pull/2\r\n\r\n"
             "[Full changelog](https://github.com/o/r/compare/v1...v2)")
    got = cc.strip_contributor_credits(given)
    check("H2.1 New Contributors lines and their emptied heading go; the changelog link stays; CRLF kept",
          got == ("## Changes\r\n* Fix it ([PR #1](https://github.com/o/r/pull/1))\r\n\r\n"
                  "[Full changelog](https://github.com/o/r/compare/v1...v2)"), repr(got))
    kept_list = "## New Contributors\n* @alice made their first contribution in https://x/pull/1\n* Docs moved to /docs\n"
    check("H2.2 the heading stays when a list item that is not a handle line remains under it",
          cc.strip_contributor_credits(kept_list) == "## New Contributors\n* Docs moved to /docs\n",
          repr(cc.strip_contributor_credits(kept_list)))
    check("H2.3 a New Contributors heading that headed no handle lines is left alone",
          cc.strip_contributor_credits("## New Contributors\n\nThanks, everyone. @team\n")
          == "## New Contributors\n\nThanks, everyone. @team\n")
    kept = (
        ("H3.1 a scoped package is not a handle", "* Bump @comfyorg/frontend to 1.2 ([PR #5](https://x/pull/5))"),
        ("H3.2 a ref is not a handle", "* Merge from cloud@7c470f0 ([PR #6](https://x/pull/6))"),
        ("H3.3 an action pin is not a handle", "* Use actions/checkout@v4 in CI"),
        ("H3.4 an e-mail address is not a handle", "* Report to security@example.com"),
        ("H3.5 a handle that is the SUBJECT of the line stays", "* Mention @alice in the docs"),
        ("H3.6 a vendor's own thanks is attribution and stays", "Thank you to @wiggin15 for the feedback."),
        ("H3.7 a decorator stays", "* Support @torch.compile on the sampler"),
        ("H3.8 'by' + a package is not a credit", "* Replaced by @scope/pkg in the loader"),
        ("H3.10 a handle right before a PR link is a credit only after 'by'",
         "* Thank @alice ([PR #9](https://x/pull/9))"),
    )
    for label, text in kept:
        check(label, cc.strip_contributor_credits(text) == text, repr(cc.strip_contributor_credits(text)))
    mixed = "* Merge from cloud@7c470f0 by @comfy-pr-bot ([PR #7](https://x/pull/7))"
    check("H3.9 in one line: the ref stays, the credit goes",
          cc.strip_contributor_credits(mixed) == "* Merge from cloud@7c470f0 ([PR #7](https://x/pull/7))",
          repr(cc.strip_contributor_credits(mixed)))
    summary = ("Changes Fix by @a (PR #1) Add node. by @b-c (PR #2) Faster by @d. "
               "New Contributors @e made their first contribution in https://x/pull/2 Full changelog")
    check("H4.1 the one-line summary form loses credits and New Contributors handles, keeps PR numbers",
          cc.strip_contributor_credits_from_summary(summary)
          == "Changes Fix (PR #1) Add node. (PR #2) Faster. Full changelog",
          repr(cc.strip_contributor_credits_from_summary(summary)))
    check("H4.2 a summary truncated inside New Contributors",
          cc.strip_contributor_credits_from_summary("Node (PR #13435) New Contributors @jkyamog.")
          == "Node (PR #13435).")
    once = cc.strip_contributor_credits(given)
    check("H5.1 the filter is idempotent", cc.strip_contributor_credits(once) == once)

    # The stored corpus, after the migration in this change.
    files = migration.selected_files()
    report = migration.run(write=False)
    check("H6.1 the migration finds GitHub-release records and is a no-op on the migrated corpus "
          "(idempotent: 0 changed, 0 refused)",
          report["scanned"] == len(files) > 0 and not report["changed"] and not report["refused"],
          json.dumps({k: report[k] for k in ("scanned", "unchanged")}))
    credit = re.compile(r"\bby @[A-Za-z0-9]|made their first contribution")
    leftovers, disagree = [], []
    for path in files:
        front = yaml.safe_load(split_front_matter(path.read_bytes().decode("utf-8"))[0]) or {}
        for field in migration.FIELDS:
            if credit.search(str(front.get(field) or "")):
                leftovers.append((path.name, field))
        body = str(front.get("official_patch_notes_body") or "")
        if body and github_releases.release_body(body) != body:
            disagree.append(path.name)
    check("H6.2 no stored GitHub-release record carries a contributor credit any more",
          not leftovers, str(leftovers[:5]))
    check("H6.3 the adapter and the migration agree byte for byte on every stored body "
          "(a later refresh from GitHub changes nothing)", not disagree, str(disagree[:5]))
    tree = ast.parse((SCRIPTS / "migrate_strip_release_note_handles.py").read_text(encoding="utf-8"))
    mods = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    mods |= {a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
    check("H6.4 the migration is zero-network by construction (no network module imported)",
          not ({"urllib", "urllib.request", "http", "http.client", "requests", "socket", "lib.http",
                "lib.github_api"} & mods) and not any(m.startswith(("urllib", "http")) for m in mods), str(mods))
    writes = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute)
              and node.attr in ("write_text", "write_bytes", "replace", "unlink", "rename")]
    check("H6.5 the migration writes only through its one guarded path (write_bytes + replace)",
          sorted(n.attr for n in writes) == ["replace", "write_bytes"], str([n.attr for n in writes]))


def run() -> int:
    section_transport()
    section_callers()
    section_provider_removal()
    section_handles()
    print()
    print("=" * 96)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + "; ".join(FAILURES))
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
