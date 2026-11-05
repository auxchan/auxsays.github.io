#!/usr/bin/env python3
"""Microsoft Learn fetches stay on Learn: the same-origin policy, driven through every production fetcher.

THE DEFECT. Each production Learn Q&A fetcher (the PowerPoint context resolver, the tag/question page
fetcher shared by PowerPoint and Teams, the search-RSS feed shared by Windows, PowerPoint, Teams and
open-web discovery) used urllib's default ``urlopen``. Its redirect handler follows a 30x to ANY host,
and nothing checked where the response came from, so a page served by another host after a redirect
was parsed as the Learn thread the run had discovered.

HOW THIS SUITE TESTS IT. Over REAL urllib and REAL HTTP on loopback servers only. The transport's
connection classes are routed so ``https://learn.microsoft.com``, ``http://learn.microsoft.com``,
``https://learn.microsoft.com:8443`` and ``https://evil.example.net`` each land on their own loopback
server, while the URLs, Host headers and Location headers stay exactly what production would see.
DNS is fenced: a lookup of anything but 127.0.0.1 is recorded and refused, so no third-party request
can leave this machine. Every refused case asserts three things: a NAMED refusal, ZERO requests at
the other host, and nothing parsed or stored. The other host always serves a page that WOULD count if
it were read, so a policy that stopped working changes a verdict, not just a number.

Sections: [P] the policy as pure functions; [L] loopback, per fetcher; [E] flag-free equivalence with
the pre-change transports (byte-identical output and request headers); [H] method health names the
refusal (Windows, PowerPoint, Teams, the context resolver), including a Teams write run against a
temp store and an orchestrated PowerPoint run; [A] the structural pin over the AST -- no production
Learn fetcher calls the default ``urlopen``; [B] the new imports resolve when the entry points run
as bare scripts.

Deterministic, offline (loopback only), no repo mutation.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_learn_fetch_same_origin.py
"""
from __future__ import annotations

import ast
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import orchestrate_evidence_run as orch  # noqa: E402
from lib import context_resolution as cr  # noqa: E402
from lib import learn_fetch_policy as lfp  # noqa: E402
from lib import patch_identity as pi  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import microsoft_learn_qna_source as learn_qna  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors import microsoft_qna_tags_source as qna_tags  # noqa: E402
from patch_collectors import microsoft_teams as teams  # noqa: E402
from patch_collectors import microsoft_windows as win  # noqa: E402
from patch_collectors import open_web_source  # noqa: E402

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


# ---------------------------------------------------------------------------------------------------
# Loopback world
# ---------------------------------------------------------------------------------------------------

class Server:
    """One loopback HTTP server standing in for one origin. Records every request it receives."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.routes: dict[str, tuple[int, list[tuple[str, str]], bytes]] = {}
        self.prefix_routes: dict[str, tuple[int, list[tuple[str, str]], bytes]] = {}
        self.requests: list[dict] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - http.server's name
                server.requests.append({"path": self.path, "headers": dict(self.headers.items())})
                route = server.routes.get(self.path)
                if route is None:
                    route = next((r for p, r in server.prefix_routes.items() if self.path.startswith(p)),
                                 (404, [("Content-Type", "text/plain")], b"not found"))
                status, headers, body = route
                self.send_response(status)
                for key, value in headers:
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):  # silence
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def reset(self) -> None:
        self.routes.clear()
        self.prefix_routes.clear()
        self.requests.clear()

    def page(self, path: str, body: str, ctype: str = "text/html; charset=utf-8", status: int = 200) -> None:
        self.routes[path] = (status, [("Content-Type", ctype)], body.encode("utf-8"))

    def redirect(self, path: str, location: str, status: int = 302) -> None:
        self.routes[path] = (status, [("Location", location)], b"")


LEARN = Server("learn")            # https://learn.microsoft.com
DOWNGRADE = Server("downgrade")    # http://learn.microsoft.com
PORT = Server("port")              # https://learn.microsoft.com:8443
EVIL = Server("evil")              # https://evil.example.net, the lookalike, and its http form
OTHERS = (DOWNGRADE, PORT, EVIL)

ROUTES = {
    ("https", "learn.microsoft.com"): LEARN, ("https", "learn.microsoft.com:443"): LEARN,
    ("http", "learn.microsoft.com"): DOWNGRADE,
    ("https", "learn.microsoft.com:8443"): PORT,
    ("https", "evil.example.net"): EVIL, ("http", "evil.example.net"): EVIL,
    ("https", "learn.microsoft.com.evil.example.net"): EVIL,
}
UNROUTED: list[tuple[str, str]] = []
DNS_ATTEMPTS: list[str] = []

_REAL = {
    "HTTPSHandler": urllib.request.HTTPSHandler, "HTTPHandler": urllib.request.HTTPHandler,
    "ProxyHandler": urllib.request.ProxyHandler, "urlopen": urllib.request.urlopen,
    "getaddrinfo": socket.getaddrinfo,
}


def _connection_for(scheme: str):
    def factory(host, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, **_kw):  # noqa: SLF001
        # A browser-like reading of a userinfo authority: the host after the '@' is the one asked.
        key = (scheme, str(host).rsplit("@", 1)[-1].lower())
        server = ROUTES.get(key)
        if server is None:
            UNROUTED.append(key)
            raise OSError(f"no loopback route for {key}")
        return http.client.HTTPConnection("127.0.0.1", server.port, timeout=timeout)
    return factory


class RoutedHTTPS(_REAL["HTTPSHandler"]):
    def https_open(self, req):
        return self.do_open(_connection_for("https"), req)


class RoutedHTTP(_REAL["HTTPHandler"]):
    def http_open(self, req):
        return self.do_open(_connection_for("http"), req)


class NoProxy(_REAL["ProxyHandler"]):
    def __init__(self, proxies=None):
        super().__init__({})


def fenced_getaddrinfo(host, *args, **kwargs):
    if str(host) not in ("127.0.0.1", "localhost"):
        DNS_ATTEMPTS.append(str(host))
        raise socket.gaierror(f"test fence: no lookup of {host}")
    return _REAL["getaddrinfo"](host, *args, **kwargs)


URLOPEN_CALLS = {"n": 0}


def urlopen_tripwire(*args, **kwargs):
    # No production Learn fetcher may reach urllib's default urlopen. A call is COUNTED and then
    # served, so a reverted transport changes this one number and the redirect verdicts.
    URLOPEN_CALLS["n"] += 1
    return _REAL["urlopen"](*args, **kwargs)


def install_loopback() -> None:
    urllib.request.HTTPSHandler = RoutedHTTPS
    urllib.request.HTTPHandler = RoutedHTTP
    urllib.request.ProxyHandler = NoProxy
    urllib.request.urlopen = urlopen_tripwire
    urllib.request._opener = None  # noqa: SLF001 - the old reference transport must be routed too
    socket.getaddrinfo = fenced_getaddrinfo


def remove_loopback() -> None:
    urllib.request.HTTPSHandler = _REAL["HTTPSHandler"]
    urllib.request.HTTPHandler = _REAL["HTTPHandler"]
    urllib.request.ProxyHandler = _REAL["ProxyHandler"]
    urllib.request.urlopen = _REAL["urlopen"]
    urllib.request._opener = None  # noqa: SLF001
    socket.getaddrinfo = _REAL["getaddrinfo"]


def reset_world() -> None:
    for server in (LEARN, *OTHERS):
        server.reset()


def other_host_requests() -> int:
    return sum(len(s.requests) for s in OTHERS)


# ---------------------------------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------------------------------

OP = ("Real Reporter", "5eee431a-ba0c-439a-961f-fe3092adbd65")


def qapage(qid: str, text: str, *, created: str = "2026-09-20T10:00:00Z") -> str:
    payload = {
        "@context": "https://schema.org", "@type": "QAPage",
        "mainEntity": {"@type": "Question", "id": qid, "name": "fixture question",
                       "text": f"<p>{text}</p>", "answerCount": 0, "dateCreated": created,
                       "author": OP[0], "authorId": OP[1], "acceptedAnswer": [],
                       "suggestedAnswer": [], "moderatorRecommendedAnswers": []},
    }
    return ("<html><head><title>fixture - Microsoft Q&amp;A</title>"
            '<script type="application/ld+json">' + json.dumps(payload) + "</script></head>"
            "<body>fixture</body></html>")


def rss(*links: str) -> str:
    items = "".join(
        f"<item><title>Teams crash after update {i}</title><link>{link}</link>"
        f"<pubDate>Sun, 20 Sep 2026 10:00:00 GMT</pubDate>"
        f"<description>Teams crashes since the update.</description></item>"
        for i, link in enumerate(links))
    return f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>'


Q_PATH = "/en-us/answers/questions/5990001/fixture-question/"
TAG_PATH = "/en-us/answers/tags/1464/m365-office-office-powerpoint-home-platform-windows/"
RSS_URL = learn_qna.learn_qna_search_url("KB5099999")
RSS_PATH = RSS_URL.split("learn.microsoft.com", 1)[1]
L = "https://learn.microsoft.com"


def tag_page_html() -> str:
    return ('<a href="/en-us/answers/questions/5990009/ppt-crash">PowerPoint crashes</a>'
            ' asked <local-time datetime="2026-09-20T10:00:00Z"></local-time>')


# One refused case: the Location the asked page answers with, and the refusal it must produce.
def refused_cases(ask_path: str) -> list[tuple[str, str, str]]:
    return [
        ("another host", "https://evil.example.net" + ask_path, "redirect_off_host"),
        ("an http downgrade", "http://learn.microsoft.com" + ask_path, "redirect_not_https"),
        ("a lookalike host", "https://learn.microsoft.com.evil.example.net" + ask_path, "redirect_off_host"),
        ("a userinfo authority", "https://learn.microsoft.com@evil.example.net" + ask_path, "redirect_off_host"),
        ("an explicit non-443 port", "https://learn.microsoft.com:8443" + ask_path, "redirect_off_host"),
        ("a scheme-relative Location", "//evil.example.net" + ask_path, "redirect_off_host"),
        ("a chain that leaves and returns", "https://evil.example.net/bounce", "redirect_off_host"),
        ("a same-host sign-in path", "/en-us/signin?returnUrl=" + ask_path, "redirect_path_not_allowed"),
    ]


def arm(ask_path: str, location: str, bait: str, bait_ctype: str = "text/html; charset=utf-8") -> None:
    """LEARN redirects the asked page; every other origin serves the bait at the same path, and the
    chain's /bounce returns to a Learn page that would be accepted if the chain were ever followed."""
    reset_world()
    LEARN.redirect(ask_path, location)
    for server in OTHERS:
        server.page(ask_path, bait, bait_ctype)
        server.redirect("/bounce", L + ask_path.rstrip("/") + "-returned/")
    LEARN.page(ask_path.rstrip("/") + "-returned/", bait, bait_ctype)
    LEARN.page("/en-us/signin?returnUrl=" + ask_path, bait, bait_ctype)


# ---------------------------------------------------------------------------------------------------
# Fetcher drivers -> (refusal reason or "", body or None)
# ---------------------------------------------------------------------------------------------------

CONTEXT_FETCH = orch.default_context_fetch()


# Every driver reports an exception the fetcher's callers would NOT handle as "unexpected:<type>", so a
# fetcher that leaks the policy's own exception fails a named check instead of crashing the suite.

def drive_context(url: str) -> tuple[str, str | None]:
    try:
        page, status = CONTEXT_FETCH(url)
    except Exception as exc:  # noqa: BLE001
        return f"unexpected:{type(exc).__name__}", None
    if str(status).startswith(cr.FETCH_REFUSED_PREFIX):
        return status[len(cr.FETCH_REFUSED_PREFIX):], None
    return ("" if status == "ok" else f"status:{status}"), (page or None)


def drive_qna(url: str) -> tuple[str, str | None]:
    try:
        return "", qna_tags.fetch(url)
    except qna_tags.QnaTagError as exc:
        return exc.reason, None
    except Exception as exc:  # noqa: BLE001
        return f"unexpected:{type(exc).__name__}", None


def drive_rss(url: str) -> tuple[str, str | None]:
    try:
        _status, _ctype, text = learn_qna._fetch_feed_text(url)  # noqa: SLF001
        return "", text
    except learn_qna.LearnQnaAccessError as exc:
        return exc.reason, None
    except Exception as exc:  # noqa: BLE001
        return f"unexpected:{type(exc).__name__}", None


def attempt(fn, *args, **kwargs):
    """(result, None) or (None, exception): a health check that crashes must still fail by name."""
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001
        return None, exc


# ---------------------------------------------------------------------------------------------------
# The pre-change transports, frozen verbatim except that urlopen is called by its saved reference.
# ---------------------------------------------------------------------------------------------------

def old_context_fetch(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": learn_qna.LEARN_QNA_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with _REAL["urlopen"](req, timeout=30) as resp:
            body = resp.read(1_500_000).decode("utf-8", errors="replace")
            if resp.status != 200:
                return "", "broken"
            low = body.lower()
            if "captcha" in low or "access denied" in low or "request blocked" in low:
                return "", "blocked"
            return body, "ok"
    except urllib.error.HTTPError as exc:
        return "", "blocked" if exc.code in (401, 403, 429) else "broken"
    except Exception:  # noqa: BLE001
        return "", "broken"


def old_qna_fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": qna_tags.USER_AGENT,
                                                   "Accept": "text/html,application/xhtml+xml"})
    try:
        with _REAL["urlopen"](request, timeout=qna_tags.REQUEST_TIMEOUT) as response:
            final = response.geturl()
            raw = response.read(qna_tags.MAX_BYTES)
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 503):
            raise qna_tags.QnaTagError("rate_limited", status=exc.code) from exc
        raise qna_tags.QnaTagError(f"http_{exc.code}_error", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise qna_tags.QnaTagError("network_unreachable") from exc
    if "disclaimer=tag-not-found" in final:
        raise qna_tags.QnaTagError("tag_not_found", status=200)
    return raw.decode("utf-8", "replace")


def old_feed_fetch(url: str, *, timeout: int = 30, max_bytes: int = 1_500_000):
    rb = learn_qna.rb
    request = urllib.request.Request(url, headers=learn_qna.FEED_HEADERS)
    try:
        with _REAL["urlopen"](request, timeout=rb.request_timeout(rb.get_run_budget(), timeout)) as response:
            raw = rb.bounded_read(response, budget=rb.get_run_budget(), endpoint_family="windows_learn",
                                  max_bytes=max_bytes)
            status = int(getattr(response, "status", 200) or 200)
            content_type = response.headers.get("content-type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            return status, content_type, raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(8000).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        signature = learn_qna.blocked_signature(body, status=exc.code, content_type=content_type)
        raise learn_qna.LearnQnaAccessError(
            f"http_{exc.code}_{signature}",
            status=exc.code,
            content_type=content_type,
            signature="blocked" if signature not in {"none", "empty_body"} or exc.code in {401, 403, 429} else "broken",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise learn_qna.LearnQnaAccessError(f"network_{type(exc).__name__}", signature="network") from exc


def outcome_of(fn, *args):
    try:
        return ("ok", fn(*args))
    except Exception as exc:  # noqa: BLE001 - the comparison is of outcomes
        return ("raised", type(exc).__name__, getattr(exc, "reason", str(exc)))


# ---------------------------------------------------------------------------------------------------
# [P] the policy
# ---------------------------------------------------------------------------------------------------

def section_policy() -> None:
    print("\n[P] the policy as pure functions")
    production_urls = {
        lfp.QUESTION_PAGE: [L + "/en-us/answers/questions/5975101/ppt-crash",
                            L + "/en-us/answers/questions/5975101/ppt-crash/",
                            L + "/en-us/answers/questions/5975101/", L + "/answers/questions/5975101",
                            qna_tags.question_url("5975101", "ppt-crash")],
        lfp.TAG_PAGE: [qna_tags.tag_page_url("m365-office-office-powerpoint-home-platform-windows", "1464", 1),
                       qna_tags.tag_page_url("m365-office-office-powerpoint-home-platform-windows", "1464", 3),
                       qna_tags.TAGS_INDEX, qna_tags.TAGS_INDEX + "?disclaimer=tag-not-found"],
        lfp.SEARCH_RSS: [RSS_URL, learn_qna.learn_qna_search_url("26100.8737")],
    }
    bad = {(fam, u, stage): lfp.refusal(u, fam, stage) for fam, urls in production_urls.items()
           for u in urls for stage in lfp.STAGES if lfp.refusal(u, fam, stage)}
    check("P1 every URL shape the production fetchers request is allowed at every stage", not bad, str(bad))

    path = "/en-us/answers/questions/5975101/ppt-crash"
    matrix = {
        "http://learn.microsoft.com" + path: "not_https",
        "https://evil.example.net" + path: "off_host",
        "https://learn.microsoft.com.evil.example.net" + path: "off_host",
        "https://learn.microsoft.com@evil.example.net" + path: "off_host",
        "https://user:pw@learn.microsoft.com" + path: "off_host",
        "https://learn.microsoft.com:8443" + path: "off_host",
        "https://learn.microsoft.com:notaport" + path: "off_host",
        "https://learn.microsoft.com." + path: "off_host",
        "https://learn.microsoft.com/en-us/signin": "path_not_allowed",
        "https://learn.microsoft.com/en-us/answers/tags/": "path_not_allowed",
        "https://learn.microsoft.com/en-us/answers/questions/5975101/a/b": "path_not_allowed",
        "": "not_https",
    }
    got = {u: lfp.refusal(u, lfp.QUESTION_PAGE, lfp.STAGE_REDIRECT) for u in matrix}
    want = {u: f"redirect_{c}" for u, c in matrix.items()}
    check("P2 another scheme, host, port, userinfo, lookalike or trailing-dot host, and a non-question "
          "path are each refused with their own name", got == want,
          str({u: (got[u], want[u]) for u in matrix if got[u] != want[u]}))
    check("P3 an explicit :443 and an upper-case host are the same origin, not a refusal",
          lfp.refusal("https://learn.microsoft.com:443" + path, lfp.QUESTION_PAGE, lfp.STAGE_FINAL) == ""
          and lfp.refusal("https://LEARN.Microsoft.com" + path, lfp.QUESTION_PAGE, lfp.STAGE_FINAL) == "")
    check("P4 an unknown family refuses everything rather than allowing anything",
          lfp.refusal(L + path, "no_such_family", lfp.STAGE_URL) == "url_path_not_allowed")
    check("P5 the closed vocabulary is exactly stage x check, nine names",
          lfp.REFUSAL_REASONS == {f"{s}_{c}" for s in ("url", "redirect", "final_url")
                                  for c in ("not_https", "off_host", "path_not_allowed")}
          and len(lfp.REFUSAL_REASONS) == 9, str(sorted(lfp.REFUSAL_REASONS)))
    yes = ["redirect_off_host", "learn_qna_search_fetch_failed:redirect_off_host",
           "context_fetch_refused:final_url_off_host", "url_path_not_allowed"]
    no = ["", "http_403_error", "tag_not_found", "rate_limited", "network_unreachable",
          "learn_qna_search_fetch_failed:http_403_blocked", "xredirect_off_hostx", "redirect_off_host_extra",
          "context_fetch_blocked", "QnaTagError"]
    check("P6 is_refusal matches a whole ':'-component of the closed vocabulary, never a substring",
          all(lfp.is_refusal(r) for r in yes) and not any(lfp.is_refusal(r) for r in no),
          str([r for r in yes if not lfp.is_refusal(r)] + [r for r in no if lfp.is_refusal(r)]))
    check("P7 first_refusal returns the first refusal, skipping other errors",
          lfp.first_refusal([{"reason": "network_unreachable"}, {"reason": "redirect_not_https"},
                             {"reason": "redirect_off_host"}]) == "redirect_not_https"
          and lfp.first_refusal([{"reason": "http_404_error"}]) == "" and lfp.first_refusal(None) == "")
    check("P8 the initial URL decides the page family (qna_tags.fetch serves two)",
          lfp.page_family(L + Q_PATH, (lfp.QUESTION_PAGE, lfp.TAG_PAGE)) == lfp.QUESTION_PAGE
          and lfp.page_family(L + TAG_PATH, (lfp.QUESTION_PAGE, lfp.TAG_PAGE)) == lfp.TAG_PAGE
          and lfp.page_family(L + "/en-us/windows/release-health/", (lfp.QUESTION_PAGE, lfp.TAG_PAGE)) == "")
    opener = lfp.build_opener(lfp.QUESTION_PAGE)
    redirectors = [h for h in opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
    forbidden = [type(h).__name__ for h in opener.handlers
                 if isinstance(h, (urllib.request.HTTPCookieProcessor, urllib.request.AbstractBasicAuthHandler,
                                   urllib.request.AbstractDigestAuthHandler))]
    check("P9 the opener is urllib's default chain with exactly one redirect handler, the same-origin "
          "one for this family, and no cookie or auth handler",
          len(redirectors) == 1 and isinstance(redirectors[0], lfp.SameOriginRedirect)
          and redirectors[0].family == lfp.QUESTION_PAGE and not forbidden, f"{redirectors} {forbidden}")


# ---------------------------------------------------------------------------------------------------
# [L] loopback, per fetcher
# ---------------------------------------------------------------------------------------------------

BAIT_Q = qapage("5990001", "PowerPoint Version 2603 (Build 19822.20182) crashes on save every time since the update.")


def section_loopback() -> None:
    print("\n[L] every production fetcher over real urllib and loopback HTTP")
    fetchers = [
        ("context", drive_context, Q_PATH, BAIT_Q, "text/html; charset=utf-8"),
        ("qna_tags.question", drive_qna, Q_PATH, BAIT_Q, "text/html; charset=utf-8"),
        ("qna_tags.tag", drive_qna, TAG_PATH, tag_page_html(), "text/html; charset=utf-8"),
        ("rss", drive_rss, RSS_PATH, rss(L + "/en-us/answers/questions/5990001/x"), "application/rss+xml"),
    ]
    for name, drive, ask, bait, ctype in fetchers:
        results = {}
        for label, location, expected in refused_cases(ask):
            arm(ask, location, bait, ctype)
            reason, body = drive(L + ask)
            results[label] = (reason, body is None, other_host_requests(), len(LEARN.requests), expected)
        for label, (reason, nobody, others, learn_hits, expected) in results.items():
            check(f"L[{name}] {label}: refused BEFORE it is followed as {expected}; the other host "
                  "is never asked and no body is returned",
                  reason == expected and nobody and others == 0 and learn_hits == 1,
                  f"reason={reason!r} body_none={nobody} other_host_requests={others} learn_hits={learn_hits}")

    print("\n[L] the initial URL is validated before any request")
    for name, drive, ask in (("context", drive_context, Q_PATH), ("qna_tags", drive_qna, Q_PATH),
                             ("rss", drive_rss, RSS_PATH)):
        cases = {"https://learn.microsoft.com.evil.example.net" + ask: "url_off_host",
                 "http://learn.microsoft.com" + ask: "url_not_https",
                 L + "/en-us/windows/release-health/": "url_path_not_allowed"}
        reset_world()
        for server in (LEARN, *OTHERS):
            server.page(ask, BAIT_Q)
        got = {u: drive(u)[0] for u in cases}
        hits = len(LEARN.requests) + other_host_requests()
        check(f"I[{name}] a lookalike host, an http URL and a non-Learn-Q&A path are refused with no "
              "request made anywhere", got == cases and hits == 0, f"{got} hits={hits}")

    print("\n[L] same-origin behaviour is unchanged")
    reset_world()
    LEARN.redirect(Q_PATH, "/en-us/answers/questions/5990001/renamed-slug/", 301)
    LEARN.page("/en-us/answers/questions/5990001/renamed-slug/", BAIT_Q)
    renamed = {n: d(L + Q_PATH) for n, d in (("context", drive_context), ("qna_tags", drive_qna))}
    check("S1 a same-host slug rename (301, absolute path) is followed by the context and page fetchers",
          all(r == ("", BAIT_Q) for r in renamed.values()) and other_host_requests() == 0,
          str({k: (v[0], (v[1] or "")[:40]) for k, v in renamed.items()}))
    reset_world()
    LEARN.redirect("/en-us/answers/questions/5990001/old", "renamed-relative", 302)
    LEARN.redirect("/en-us/answers/questions/5990001/renamed-relative", "/en-us/answers/questions/5990001/final", 302)
    LEARN.page("/en-us/answers/questions/5990001/final", BAIT_Q)
    rel = drive_context(L + "/en-us/answers/questions/5990001/old")
    hops = [r["path"] for r in LEARN.requests]
    check("S2 a relative Location is resolved against the request and followed, hop by hop, while it stays "
          "on a question page", rel == ("", BAIT_Q) and len(hops) == 3 and other_host_requests() == 0,
          f"{rel[0]!r} hops={hops}")
    reset_world()
    LEARN.redirect(TAG_PATH, "/en-us/answers/tags/?disclaimer=tag-not-found", 302)
    LEARN.page("/en-us/answers/tags/?disclaimer=tag-not-found", "<html>tag index</html>")
    check("S3 a retired tag redirected to the tag index is still followed and still named tag_not_found",
          drive_qna(L + TAG_PATH) == ("tag_not_found", None) and other_host_requests() == 0,
          str(drive_qna(L + TAG_PATH)))
    reset_world()
    LEARN.redirect(RSS_PATH, RSS_PATH + "&page=1", 302)
    LEARN.page(RSS_PATH + "&page=1", rss(L + "/en-us/answers/questions/5990001/x"), "application/rss+xml")
    feed = drive_rss(L + RSS_PATH)
    check("S4 a same-endpoint feed redirect (query change only) is followed",
          feed[0] == "" and "5990001" in (feed[1] or ""), str(feed[0]))

    print("\n[L] the final URL is verified before the body is read")
    real_build = lfp.build_opener
    for final, expected in (("https://evil.example.net" + Q_PATH, "final_url_off_host"),
                            ("http://learn.microsoft.com" + Q_PATH, "final_url_not_https"),
                            (L + "/en-us/signin", "final_url_path_not_allowed")):
        reads = {"n": 0, "closed": 0}

        class Resp:
            status = 200
            headers = http.client.HTTPMessage()

            def geturl(self, _f=final):
                return _f

            def read(self, *_a):
                reads["n"] += 1
                return BAIT_Q.encode("utf-8")

            read1 = read

            def close(self):
                reads["closed"] += 1

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                self.close()

        lfp.build_opener = lambda family, _r=Resp: SimpleNamespace(open=lambda req, timeout=None: _r())
        try:
            got = {"context": drive_context(L + Q_PATH)[0], "qna_tags": drive_qna(L + Q_PATH)[0]}
        finally:
            lfp.build_opener = real_build
        check(f"F[{expected}] a response whose final URL is {final.split('/en-us')[0] or final} is refused "
              "by every fetcher before one byte of its body is read, and the response is closed",
              set(got.values()) == {expected} and reads["n"] == 0 and reads["closed"] >= 2,
              f"{got} reads={reads}")


# ---------------------------------------------------------------------------------------------------
# [E] flag-free equivalence
# ---------------------------------------------------------------------------------------------------

def section_equivalence() -> None:
    print("\n[E] same-host fetches are byte-identical to the pre-change transports")

    def both(old, new, url):
        LEARN.requests.clear()
        a = outcome_of(old, url)
        old_requests = [(r["path"], r["headers"]) for r in LEARN.requests]
        LEARN.requests.clear()
        b = outcome_of(new, url)
        new_requests = [(r["path"], r["headers"]) for r in LEARN.requests]
        return a, b, old_requests, new_requests

    reset_world()
    LEARN.page(Q_PATH, BAIT_Q)
    LEARN.page(TAG_PATH, tag_page_html())
    LEARN.page(RSS_PATH, rss(L + "/en-us/answers/questions/5990001/x"), "application/rss+xml; charset=utf-8")
    LEARN.redirect("/en-us/answers/questions/5990001/old-slug/", Q_PATH, 301)
    LEARN.redirect(TAG_PATH + "?page=2", "/en-us/answers/tags/?disclaimer=tag-not-found", 302)
    LEARN.page("/en-us/answers/tags/?disclaimer=tag-not-found", "<html>index</html>")
    LEARN.routes["/en-us/answers/questions/5990404/gone/"] = (404, [("Content-Type", "text/html")], b"gone")
    LEARN.routes["/en-us/answers/questions/5990403/no/"] = (403, [("Content-Type", "text/html")], b"no")
    pairs = [
        ("E1 context fetch, a question page", old_context_fetch, CONTEXT_FETCH, L + Q_PATH),
        ("E2 context fetch, a same-host slug rename", old_context_fetch, CONTEXT_FETCH,
         L + "/en-us/answers/questions/5990001/old-slug/"),
        ("E3 context fetch, a 404 and a 403", old_context_fetch, CONTEXT_FETCH,
         L + "/en-us/answers/questions/5990404/gone/"),
        ("E4 qna_tags.fetch, a question page", old_qna_fetch, qna_tags.fetch, L + Q_PATH),
        ("E5 qna_tags.fetch, a tag page", old_qna_fetch, qna_tags.fetch, L + TAG_PATH),
        ("E6 qna_tags.fetch, a retired tag (tag_not_found)", old_qna_fetch, qna_tags.fetch, L + TAG_PATH + "?page=2"),
        ("E7 qna_tags.fetch, a slug rename and a 403", old_qna_fetch, qna_tags.fetch,
         L + "/en-us/answers/questions/5990001/old-slug/"),
        ("E8 the search-RSS feed", old_feed_fetch, learn_qna._fetch_feed_text, RSS_URL),  # noqa: SLF001
    ]
    for label, old, new, url in pairs:
        a, b, ha, hb = both(old, new, url)
        extra = True
        if label.startswith("E3"):
            a2, b2, _, _ = both(old, new, L + "/en-us/answers/questions/5990403/no/")
            extra = a2 == b2 and a2 == ("ok", ("", "blocked"))
        if label.startswith("E7"):
            a2, b2, _, _ = both(old, new, L + "/en-us/answers/questions/5990403/no/")
            extra = a2 == b2 and a2[0] == "raised" and a2[2] == "http_403_error"
        check(f"{label}: identical output, and the server saw the identical requests (path and headers, "
              "every hop)", a == b and ha == hb and len(ha) >= 1 and extra,
              f"old={str(a)[:120]} new={str(b)[:120]} headers_equal={ha == hb} extra={extra}")


# ---------------------------------------------------------------------------------------------------
# [H] method health names the refusal; nothing is parsed or stored
# ---------------------------------------------------------------------------------------------------

TEAMS_BUILD = "26198.304.4946.9672"
TEAMS_RELEASE = "2026-08-03T00:00:00Z"
TEAMS_RECORD = base.PatchRecord(
    product_id="microsoft-teams", update_version=TEAMS_BUILD, path=Path("teams.md"),
    update_published_at=TEAMS_RELEASE, update_status="current", update_product="Microsoft Teams")
GONE_Q = "/en-us/answers/questions/5990000/teams-gone/"          # 404s: an ordinary failure, listed first
REFUSED_Q = "/en-us/answers/questions/5990001/teams-crash-refused/"
READ_Q = "/en-us/answers/questions/5990002/teams-question-read/"
COUNTABLE_TEAMS = qapage("5990001", "Teams crashes every time I join a meeting since the update. "
                         "I am on Windows 11, Teams version " + TEAMS_BUILD + ".")
UNCOUNTABLE_TEAMS = qapage("5990002", "How do I change my Teams background?")


def arm_teams() -> None:
    reset_world()
    LEARN.prefix_routes["/api/search/rss?"] = (200, [("Content-Type", "application/rss+xml")],
                                               rss(L + GONE_Q.rstrip("/"), L + REFUSED_Q.rstrip("/"),
                                                   L + READ_Q.rstrip("/")).encode())
    LEARN.redirect(REFUSED_Q, "https://evil.example.net" + REFUSED_Q)
    EVIL.page(REFUSED_Q, COUNTABLE_TEAMS)
    LEARN.page(READ_Q, UNCOUNTABLE_TEAMS)


def section_health() -> None:
    print("\n[H] the refusal is named in method health, and nothing is parsed or stored")
    # --- Windows and PowerPoint primary: the shared search-RSS lane -------------------------------
    reset_world()
    LEARN.prefix_routes["/api/search/rss?"] = (302, [("Location", "https://evil.example.net/api/search/rss")], b"")
    EVIL.prefix_routes["/api/search/rss"] = (200, [("Content-Type", "application/rss+xml")],
                                             rss(L + "/en-us/answers/questions/5990001/x").encode())
    errors: list = []
    found, crash = attempt(learn_qna.collect_learn_qna_candidates, queries=["KB5099999"],
                           context=SimpleNamespace(since=None), errors=errors)
    check("H1 a refused feed redirect is a named error, not a crash and not an empty success",
          crash is None and found == [] and len(errors) == 1
          and errors[0]["reason"] == "learn_qna_search_fetch_failed:redirect_off_host"
          and errors[0]["blocked_signature"] == "blocked" and other_host_requests() == 0, f"{errors} crash={crash!r}")
    check("H2 Windows publishes it as blocked, with the refusal as its blocked_reason",
          win.learn_qna_method_status([], [], [], errors) == "blocked"
          and win.blocked_reason_from_errors(errors) == "learn_qna_search_fetch_failed:redirect_off_host")
    check("H3 PowerPoint's search-RSS lane publishes it as blocked, with the refusal named",
          ppt.learn_qna_method_status([], [], [], errors) == "blocked"
          and ppt.blocked_reason_from_errors(errors) == "learn_qna_search_fetch_failed:redirect_off_host")

    # --- PowerPoint tag lane and open-web hydration ----------------------------------------------
    arm(TAG_PATH, "https://evil.example.net" + TAG_PATH, tag_page_html())
    tag_errors: list = []
    rows, pages = qna_tags.enumerate_tag("1464", "m365-office-office-powerpoint-home-platform-windows",
                                         since="2026-01-01", max_pages=2, errors=tag_errors)
    check("H4 a refused tag page yields no rows and a named error",
          rows == [] and pages == 0 and [e["reason"] for e in tag_errors] == ["redirect_off_host"], str(tag_errors))
    status = ppt.qna_tag_method_status([], [], [], tag_errors, enumerated=0)
    check("H5 the tag lane publishes a refused enumeration as blocked, naming the refusal",
          status == "blocked" and ppt.qna_lane_blocked_reason(status, tag_errors) == "redirect_off_host", status)
    one = [{"source_url": "x"}]
    mixed = [{"reason": "http_404_error"}, {"reason": "redirect_off_host"}]
    status = ppt.qna_tag_method_status(one, [], [{"exclusion_reason": "missing_exact_build"}], mixed, enumerated=40)
    check("H6 a refusal among pages that WERE read is blocked, not the no_results it used to fall through to",
          status == "blocked", status)
    check("H7 the blocked_reason is the refusal even when another error came first, and even beside "
          "accepted reports (where the status is partial)",
          ppt.qna_lane_blocked_reason("blocked", mixed) == "redirect_off_host"
          and ppt.qna_tag_method_status(one, [{"a": 1}], [], mixed, enumerated=40) == "partial"
          and ppt.qna_lane_blocked_reason("partial", mixed) == "redirect_off_host")
    check("H8 a lane with no refusal keeps its old blocked_reason rule exactly",
          ppt.qna_lane_blocked_reason("blocked", [{"reason": "rate_limited"}]) == "rate_limited"
          and ppt.qna_lane_blocked_reason("partial", [{"reason": "http_404_error"}]) is None
          and ppt.qna_lane_blocked_reason("no_results", []) is None)
    parsed = {"n": 0}
    real_parse = ppt.parse_learn_qna_thread
    ppt.parse_learn_qna_thread = lambda *a, **k: (parsed.__setitem__("n", parsed["n"] + 1), real_parse(*a, **k))[1]
    try:
        arm("/en-us/answers/questions/5990003/x/", "https://evil.example.net/en-us/answers/questions/5990003/x/", BAIT_Q)
        try:
            hydrated = ppt.hydrate_discovered_url({"source_url": L + "/en-us/answers/questions/5990003/x",
                                                   "source_type": ppt.LEARN_QNA_SOURCE_TYPE})
            reason = ""
        except Exception as exc:  # noqa: BLE001 - run_open_web_method's own handling
            hydrated, reason = None, open_web_source.error_reason(exc)
    finally:
        ppt.parse_learn_qna_thread = real_parse
    check("H9 open-web hydration of a refused question raises a named failure and parses nothing",
          hydrated is None and reason == "redirect_off_host" and parsed["n"] == 0 and other_host_requests() == 0,
          f"reason={reason!r} parsed={parsed['n']}")

    # --- Teams: discovery, status, and a write run against a temp store --------------------------
    real = {"parse": teams.source_segments.parse_learn_qna_thread, "sleep": learn_qna.learn_qna_sleep,
            "records": base.generated_records, "tc": teams.discover_tech_community,
            "append": base.append_evidence_rows, "writeback": teams.apply_consensus_writeback}
    parsed_urls: list[str] = []

    def spy_parse(url, page):
        parsed_urls.append(url)
        return real["parse"](url, page)

    teams.source_segments.parse_learn_qna_thread = spy_parse
    learn_qna.learn_qna_sleep = lambda _s: None
    try:
        arm_teams()
        t_errors: list = []
        cands, crash = attempt(teams.discover_learn_qna, TEAMS_RECORD, SimpleNamespace(since=None, max_pages=1),
                               t_errors)
        cands = cands or []
        refused_url = L + REFUSED_Q.rstrip("/")
        check("H10 Teams: the refused thread yields no candidate and is never parsed; the read thread is",
              all(not str(c["source_url"]).startswith(refused_url) for c in cands)
              and any(str(c["source_url"]).startswith(L + READ_Q.rstrip("/")) for c in cands)
              and all(not u.startswith(refused_url) for u in parsed_urls) and other_host_requests() == 0
              and crash is None,
              f"cands={[c['source_url'] for c in cands]} parsed={parsed_urls} evil={len(EVIL.requests)} "
              f"crash={crash!r}")
        reasons = [e["reason"] for e in t_errors]
        check("H11 Teams names the refusal itself (the RSS module's error_reason would have reported the "
              "page fetcher's QnaTagError by its class name)",
              len(reasons) == 2 and reasons[1] == "redirect_off_host" and not lfp.is_refusal(reasons[0]),
              str(t_errors))
        check("H12 Teams publishes a refusal as blocked even with other candidates read",
              teams.method_status(cands, t_errors, 0) == "blocked", teams.method_status(cands, t_errors, 0))
        others = [qna_tags.QnaTagError("http_403_error"), qna_tags.QnaTagError("rate_limited"),
                  learn_qna.LearnQnaAccessError("blocked:rate_limited"), RuntimeError("x")]
        check("H13 a Teams page failure that is not a refusal is reported exactly as before",
              all(teams.page_error_reason(e) == teams.qna_source.error_reason(e) for e in others))

        with tempfile.TemporaryDirectory() as td:
            store = Path(td) / "consensus_evidence.yml"
            store.write_text("schema_version: 1\nevidence: []\n", encoding="utf-8")
            base.generated_records = lambda *_a, **_k: [TEAMS_RECORD]
            teams.discover_tech_community = lambda _ctx, _errs, **_k: []
            teams.apply_consensus_writeback = lambda *_a, **_k: False
            base.append_evidence_rows = lambda rows, *a, **k: real["append"](rows, store, **k)
            arm_teams()
            out, _crash = attempt(teams.TeamsCommunityCollector().collect,
                                  SimpleNamespace(write=True, since=None, max_pages=1, target_versions=None))
            stored = base.load_evidence(store)
        health = {r["method_id"]: r for r in (out[0]["method_health"] if out else [])}
        qna_row = health.get(teams.QNA_METHOD_ID) or {}
        check("H14 Teams write run: the Learn health row is blocked and its blocked_reason is the refusal",
              qna_row.get("status") == "blocked" and qna_row.get("blocked_reason") == "redirect_off_host",
              f"{qna_row.get('status')} {qna_row.get('blocked_reason')!r}")
        check("H15 Teams write run: the store holds the thread that was read and nothing from the refused "
              "one, whose off-site page would have COUNTED",
              any(str(r.get("source_url") or "").startswith(L + READ_Q.rstrip("/")) for r in stored)
              and not any(str(r.get("source_url") or "").startswith(refused_url) for r in stored)
              and not any(r.get("counted") for r in stored) and len(EVIL.requests) == 0,
              f"stored={[(r.get('source_url'), r.get('counted')) for r in stored]}")
    finally:
        teams.source_segments.parse_learn_qna_thread = real["parse"]
        learn_qna.learn_qna_sleep = real["sleep"]
        base.generated_records = real["records"]
        teams.discover_tech_community = real["tc"]
        base.append_evidence_rows = real["append"]
        teams.apply_consensus_writeback = real["writeback"]

    # --- PowerPoint context resolution: the resolver and the orchestrated run -------------------
    cparsed = {"n": 0}
    real_cparse = cr.parse_learn_qna_thread
    cr.parse_learn_qna_thread = lambda *a, **k: (cparsed.__setitem__("n", cparsed["n"] + 1), real_cparse(*a, **k))[1]
    try:
        url = L + "/en-us/answers/questions/5975101/ppt-crash"
        arm("/en-us/answers/questions/5975101/ppt-crash", "https://evil.example.net/en-us/answers/questions/5975101/ppt-crash",
            qapage("5975101", "PowerPoint Version 2603 (Build 19822.20182) crashes on save every time since the update."))
        budget = cr.ResolutionBudget()
        out = cr.resolve_candidate({"source_url": url, "report_text": "PowerPoint 2603 crashes"},
                                   cr.RESOLVABLE_REASON, fetch_thread=CONTEXT_FETCH, budget=budget)
    finally:
        cr.parse_learn_qna_thread = real_cparse
    check("H16 the resolver records a refused thread as fetch_blocked naming the refusal, and never parses it",
          out.resolution_result == cr.FETCH_BLOCKED and out.detail == "refused:redirect_off_host"
          and out.resolution_result in cr.RESOLUTION_RESULTS and cparsed["n"] == 0
          and budget.threads[url] == (None, "refused:redirect_off_host") and other_host_requests() == 0,
          f"{out.resolution_result} {out.detail!r} parsed={cparsed['n']}")

    with tempfile.TemporaryDirectory() as td:
        ran, crash = attempt(run_orchestrated_refusal, Path(td))
    state, evil_hits = ran if ran else (SimpleNamespace(method_results=[], method_plan={}), -1)
    if crash is not None:
        print(f"        orchestrated run raised {crash!r}")
    rows = [r for r in state.method_results if r.get("role") == "context_resolution"]
    hr = rows[0]["health_row"] if rows else {}
    outcomes = (state.method_plan.get("context_resolution") or {}).get("outcomes") or []
    check("H17 orchestrated PowerPoint run: the context stage is blocked and its health names the refusal",
          len(rows) == 1 and hr.get("status") == "blocked"
          and hr.get("blocked_reason") == "context_fetch_refused:redirect_off_host"
          and lfp.is_refusal(hr.get("blocked_reason")),
          f"rows={len(rows)} status={hr.get('status')} reason={hr.get('blocked_reason')!r}")
    check("H18 orchestrated PowerPoint run: nothing resolved, nothing counted, the other host never asked",
          outcomes and outcomes[0]["resolution_result"] == cr.FETCH_BLOCKED
          and not any(r["accepted_rows"] for r in rows) and evil_hits == 0,
          f"{[o.get('resolution_result') for o in outcomes]} evil={evil_hits}")

    print("\n[G] the default urlopen was never reached by a production fetcher")
    check("G1 zero calls to urllib.request.urlopen across every new-fetcher run above "
          "(the frozen pre-change references call it by a saved name)", URLOPEN_CALLS["n"] == 0,
          str(URLOPEN_CALLS))
    check("G2 no lookup of any non-loopback name was attempted, and every connection had a loopback route",
          DNS_ATTEMPTS == [] and UNROUTED == [], f"dns={DNS_ATTEMPTS} unrouted={UNROUTED}")


PPT = "microsoft-powerpoint"
PPT_VERSION = "2603"
PPT_BUILD = "19822.20182"


def run_orchestrated_refusal(tmp: Path):
    repo = tmp / "repo"
    gen = repo / "auxsays" / "updates" / "generated"
    data = repo / "auxsays" / "_data"
    gen.mkdir(parents=True)
    data.mkdir(parents=True)
    name = f"2026-04-14-{PPT}-{pi.record_version_slug(PPT_VERSION, PPT_BUILD, PPT)}.md"
    (gen / name).write_text("\n".join([
        "---", "layout: aux-update", "update_entry: true", f"product_id: {PPT}",
        f"update_version: '{PPT_VERSION}'", f"target_build: '{PPT_BUILD}'",
        f"permalink: {pi.permalink_path('microsoft', PPT, PPT_VERSION, PPT_BUILD)}",
        "update_report_count: 0", "confirmed_patch_specific_report_count: 0",
        "evidence_state: official_only", "update_published_at: '2026-04-14T00:00:00Z'",
        "update_status: current", "update_product: Microsoft PowerPoint", "---", "", "body", ""]),
        encoding="utf-8")
    (data / ".gitkeep").write_text("", encoding="utf-8")
    for args in (["init", "-b", "main"], ["config", "user.name", "fixture"], ["config", "user.email", "f@x"],
                 ["add", "-A"], ["commit", "-m", "fixture"]):
        subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    url = L + "/en-us/answers/questions/5975101/ppt-crash"
    title = f"PowerPoint Version {PPT_VERSION} crashes on save"
    candidate = {"source_type": ppt.LEARN_QNA_SOURCE_TYPE, "source_name": ppt.LEARN_QNA_SOURCE_NAME,
                 "source_url": url, "parent_title": title, "report_title": title,
                 "report_text": (f"After installing PowerPoint Version {PPT_VERSION} on the Current Channel "
                                 "it crashes every time I save. It worked before the update."),
                 "source_date": "2026-04-20T00:00:00Z"}

    def method(rows):
        def _m(record, target, context, seen, run_urls, captured_at, attempted=True):
            cands = rows if attempted else []
            accepted, rejected = ppt.evaluate_candidates(record, dict(target), cands, captured_at, seen, run_urls)
            status = "disabled" if not attempted else "low_confidence" if rejected else "no_results"
            row = base.method_health_row(product_id=PPT, update_version=PPT_VERSION,
                                         target_build=str(target.get("target_build") or ""),
                                         method_id="learn_qna_search_rss", source_type="microsoft_learn_qna",
                                         status=status, candidates_found=len(cands), accepted_reports=len(accepted),
                                         rejected_reports=len(rejected), blocked_reason=None,
                                         last_run=captured_at, notes="fixture")
            return accepted, rejected, row
        return _m

    arm("/en-us/answers/questions/5975101/ppt-crash", "https://evil.example.net/en-us/answers/questions/5975101/ppt-crash",
        qapage("5975101", f"PowerPoint Version {PPT_VERSION} (Build {PPT_BUILD}) crashes on save every time since the update."))
    pipeline = orch.Pipeline(
        repo, [PPT], write=False, checkpoint_dir=tmp / "ckpt",
        evidence_path=data / "consensus_evidence.yml", health_path=data / "evidence_method_health.yml",
        generated_dir=gen, methods={"learn_qna_search_rss": method([candidate]), "reddit_search": method([])},
        authorities={"promote": lambda: {"rc": 0}, "qa": lambda: {"rc": 0}, "audit": lambda: {"rc": 0}},
        capability={"reddit_search": True}, allow_patterns=["auxsays/_data/*"], writeback=None,
        context_fetch=orch.default_context_fetch(),
        context=SimpleNamespace(write=False, since=None, max_pages=1, target_versions=None))
    state = pipeline.run()
    return state, len(EVIL.requests)


# ---------------------------------------------------------------------------------------------------
# [A] the structural pin
# ---------------------------------------------------------------------------------------------------

def _dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def default_transport_uses(tree: ast.AST) -> list[str]:
    """Every CALL of urlopen / build_opener / OpenerDirector and every import of urlopen, by AST --
    docstrings, comments and string literals that merely mention them are not code."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name.split(".")[-1] in ("urlopen", "build_opener", "OpenerDirector"):
                found.append(f"call {name} @{node.lineno}")
        elif isinstance(node, ast.ImportFrom) and node.module == "urllib.request":
            found += [f"import {a.name} @{node.lineno}" for a in node.names if a.name in ("urlopen", "build_opener", "*")]
    return found


def _function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    return next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), None)


def _calls(node: ast.AST, suffix: str) -> int:
    return sum(1 for n in ast.walk(node) if isinstance(n, ast.Call) and _dotted(n.func).endswith(suffix))


def _catches(node: ast.AST, suffix: str) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.ExceptHandler) and n.type is not None:
            types = n.type.elts if isinstance(n.type, ast.Tuple) else [n.type]
            if any(_dotted(t).endswith(suffix) for t in types):
                return True
    return False


LEARN_MODULES = (
    "patch_collectors/microsoft_qna_tags_source.py", "patch_collectors/microsoft_learn_qna_source.py",
    "patch_collectors/microsoft_teams.py", "patch_collectors/microsoft_powerpoint.py",
    "patch_collectors/microsoft_windows.py", "lib/context_resolution.py", "orchestrate_evidence_run.py",
)
FETCHERS = (
    ("patch_collectors/microsoft_qna_tags_source.py", "fetch"),
    ("patch_collectors/microsoft_learn_qna_source.py", "_fetch_feed_text"),
    ("orchestrate_evidence_run.py", "default_context_fetch"),
)


def section_structure() -> None:
    print("\n[A] the structural pin, over the AST")
    decoy = ('"""urllib.request.urlopen(url) is what this used to call."""\n'
             "# urllib.request.urlopen(req)\n"
             "def f(r):\n    note = 'urlopen(' \n    return note\n")
    real_call = "import urllib.request\ndef f(r):\n    return urllib.request.urlopen(r)\n"
    aliased = "from urllib.request import urlopen as u\ndef f(r):\n    return u(r)\n"
    check("A1 the checker ignores prose and string literals and catches a real call and an aliased import",
          default_transport_uses(ast.parse(decoy)) == [] and len(default_transport_uses(ast.parse(real_call))) == 1
          and len(default_transport_uses(ast.parse(aliased))) == 1,
          f"{default_transport_uses(ast.parse(decoy))} {default_transport_uses(ast.parse(aliased))}")
    trees = {m: ast.parse((_SCRIPTS / m).read_text(encoding="utf-8")) for m in LEARN_MODULES}
    uses = {m: default_transport_uses(t) for m, t in trees.items() if default_transport_uses(t)}
    check("A2 no Learn fetcher or Learn consumer module calls urlopen or builds its own opener",
          not uses, str(uses))
    for module, function in FETCHERS:
        tree = ast.parse((_SCRIPTS / module).read_text(encoding="utf-8"))
        fn = _function(tree, function)
        check(f"A3 {module}:{function} opens through learn_fetch_policy.open_url exactly once and converts "
              "LearnFetchRefused into its own named failure",
              fn is not None and _calls(fn, "learn_fetch_policy.open_url") == 1
              and _catches(fn, "learn_fetch_policy.LearnFetchRefused") and default_transport_uses(fn) == [],
              f"open_url={_calls(fn, 'learn_fetch_policy.open_url') if fn else None}")
    policy = ast.parse((_SCRIPTS / "lib" / "learn_fetch_policy.py").read_text(encoding="utf-8"))
    imports = set()
    for n in ast.walk(policy):
        if isinstance(n, ast.Import):
            imports |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imports.add(n.module or "")
    # Its own build_opener(family) is called by open_url; only urllib's may construct an opener.
    builders = [u for u in default_transport_uses(policy) if "urllib" in u or "urlopen" in u]
    check("A4 the policy module is standard-library only, never calls urlopen, and constructs exactly one "
          "urllib opener, inside build_opener", imports <= {"__future__", "re", "urllib.parse", "urllib.request"}
          and len(builders) == 1 and _calls(_function(policy, "build_opener"), "urllib.request.build_opener") == 1
          and _calls(_function(policy, "open_url"), "build_opener") == 1,
          f"{sorted(imports)} {builders}")
    ow = ast.parse((_SCRIPTS / "patch_collectors" / "open_web_source.py").read_text(encoding="utf-8"))
    search = _function(ow, "search_learn_qna")
    unused = sum(1 for n in ast.walk(ow) if isinstance(n, ast.Name) and n.id == "_fetch"
                 and isinstance(n.ctx, ast.Load))
    elsewhere = []
    for path in sorted(_SCRIPTS.rglob("*.py")):
        if "tests" in path.relative_to(_SCRIPTS).parts:
            continue
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Attribute) and n.attr == "_fetch" and "open_web" in _dotted(n.value):
                elsewhere.append(str(path.relative_to(_SCRIPTS)))
    check("A5 open-web's Learn search goes through the protected feed fetcher, and its generic "
          "default-urlopen _fetch has no caller anywhere in production",
          search is not None and _calls(search, "learn_qna._fetch_feed_text") == 1
          and default_transport_uses(search) == [] and unused == 0 and elsewhere == [],
          f"unused_refs={unused} elsewhere={elsewhere}")


# ---------------------------------------------------------------------------------------------------
# [B] bare-script imports
# ---------------------------------------------------------------------------------------------------

def section_bare_scripts() -> None:
    print("\n[B] the new imports resolve when the entry points run as bare scripts")
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory() as td:
        for script in ("orchestrate_evidence_run.py", "run_patch_evidence_collection.py"):
            proc = subprocess.run([sys.executable, str(_SCRIPTS / script), "--help"], capture_output=True,
                                  text=True, cwd=td, env=env, timeout=120)
            check(f"B1 {script} --help runs as a bare script from outside the repo",
                  proc.returncode == 0, proc.stderr.strip()[-300:])
        # The child fences DNS and TCP BEFORE importing anything, so even a broken policy (a mutant
        # that stops refusing http) can only fail this check -- it can never reach the real host.
        probe = ("import socket, sys\n"
                 "tried = []\n"
                 "def fence(*a, **k):\n"
                 "    tried.append(a[0] if a else '')\n"
                 "    raise OSError('test fence: no network')\n"
                 "socket.getaddrinfo = fence\n"
                 "socket.create_connection = fence\n"
                 "sys.path.insert(0, sys.argv[1])\n"
                 "import orchestrate_evidence_run as o\n"
                 "from patch_collectors import microsoft_qna_tags_source as q, microsoft_learn_qna_source as s\n"
                 "from patch_collectors import microsoft_teams, microsoft_powerpoint, microsoft_windows\n"
                 "print(o.default_context_fetch()('http://learn.microsoft.com/en-us/answers/questions/1/x'))\n"
                 "print('network attempts', len(tried))\n")
        proc = subprocess.run([sys.executable, "-c", probe, str(_SCRIPTS)], capture_output=True, text=True,
                              cwd=td, env=env, timeout=120)
        check("B2 in a fresh interpreter with only the scripts directory on sys.path, the deferred import in "
              "default_context_fetch resolves and refuses an http URL before any network attempt",
              proc.returncode == 0 and "('', 'refused:url_not_https')" in proc.stdout
              and "network attempts 0" in proc.stdout, (proc.stdout + proc.stderr).strip()[-400:])


def run() -> int:
    print("=" * 78)
    print("Microsoft Learn fetches stay on Learn (same-origin policy)")
    print("=" * 78)
    real_pace = qna_tags._pace  # noqa: SLF001
    qna_tags._pace = lambda: None  # noqa: SLF001 - no wall-clock pacing in a loopback suite
    install_loopback()
    try:
        section_policy()
        section_loopback()
        section_equivalence()
        section_health()
    finally:
        remove_loopback()
        qna_tags._pace = real_pace  # noqa: SLF001
    section_structure()
    section_bare_scripts()
    for server in (LEARN, *OTHERS):
        server.httpd.shutdown()
        server.httpd.server_close()

    print()
    print("=" * 78)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 78)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
