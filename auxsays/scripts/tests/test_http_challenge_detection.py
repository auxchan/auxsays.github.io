#!/usr/bin/env python3
"""Browser-challenge detection for lib/http.py, on EVERY response-returning path.

WHAT BROKE. help.elgato.com sits behind Cloudflare. All four Elgato sources are
`enabled: true` and have produced 0 records and 0 evidence rows since 2026-08-18.
`patch_ingest_state.json` recorded `last_error_type: blocked` with a body that is a
"Just a moment..." interstitial -- not a 404, not an empty section. Cloudflare serves
that interstitial at 403 AND at 200, and at 200 the ingestion path had no way to tell
it from the real document: the adapter parsed the challenge, matched no product, counted
the article a NONMATCH, and the run booked itself `no_results`. A source actively
refusing us read, on the public page, as a source with nothing new to say.

WHY THIS SUITE EXISTS SEPARATELY FROM THE FIX. `lib/http.py` has TWO functions that
return a `FetchResult`: `fetch_text` (urllib) and `_curl_fetch_text` (the curl
fallback). The challenge guard was added to the first only. A gate that covers one of
two paths FAILS OPEN on the other, and the curl path is the easier one to miss because
curl reports exit 0 and the function hard-codes `status=200`. Measured before the fix:
`_curl_fetch_text` returned the recorded 478-byte interstitial as a 200 while
`looks_like_challenge` on that exact text already answered True.

The [X] mutants restore each half of the guard SEPARATELY and require a NAMED check to
fail for each, because reverting two halves of a fix together once let one half's test
stand in for both.

The fixture body is FROZEN INLINE, deliberately. Reading it from
`auxsays/_data/patch_ingest_state.json` would make this suite's result a function of
whatever the last scheduled run happened to write.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_http_challenge_detection.py
"""
from __future__ import annotations

import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lib import http as auxhttp                     # noqa: E402
from lib import state as auxstate                   # noqa: E402
from source_health_snapshot import friendly_error    # noqa: E402

_HTTP_PATH = _SCRIPTS / "lib" / "http.py"
_HEALTH_PATH = _SCRIPTS / "source_health_snapshot.py"
_PROBE_PATH = _SCRIPTS / "probe_photoshop_sources.py"

# The real recorded Elgato interstitial, as the error formatter truncated it. Only the
# title marker is present in it -- so this fixture proves the title marker alone is
# load-bearing in production, not merely the richer synthetic bodies below.
RECORDED_CHALLENGE = (
    '<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title>'
    '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
    '<meta http-equiv="X-UA-Compatible" content="IE=Edge">'
    '<meta name="robots" content="noindex,nofollow">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    '<meta http-equiv="content-security-policy" content="default-src none; '
    "script-src nonce-IhVzZcORThg89Twp2SMFPA unsafe-eval [source URL] script-s"
)

RECORDED_ERROR = "HTTP 403 while fetching official source - " + RECORDED_CHALLENGE

# A legitimate release note that happens to contain the phrase in running prose.
PROSE_NEGATIVE = (
    "<html><head><title>Wave Link 3.4 Release Notes</title></head><body>"
    "<p>Give the mixer just a moment to enumerate your devices after updating.</p>"
    "<p>Access denied errors when loading a scene were fixed.</p></body></html>"
)

CLEAN_DOC = (
    "<html><head><title>Elgato Wave Link 3.4 (Windows) Release Notes</title></head>"
    "<body><h1>Wave Link 3.4</h1><p>Fixed a crash on launch.</p></body></html>"
)

AKAMAI_REFUSAL = "<html><body>Access Denied. Reference 18.akamai</body></html>"

_PASS = 0
_FAIL = 0
_ERRORS: list = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + detail)
        _ERRORS.append(label)


class _Server(BaseHTTPRequestHandler):
    """Serves a configurable body/status/headers so the urllib path runs on the wire."""

    body = ""
    status = 200
    extra_headers: dict = {}

    def do_GET(self) -> None:  # noqa: N802
        payload = _Server.body.encode("utf-8")
        self.send_response(_Server.status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        for key, value in _Server.extra_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        return


class _Proc:
    """Stands in for the subprocess result so the curl path can be driven offline."""

    returncode = 0
    stderr = b""

    def __init__(self, payload: str) -> None:
        self.stdout = payload.encode("utf-8")


def _curl_returning(payload: str):
    return lambda *a, **k: _Proc(payload)


_MUTANT_N = [0]


def _mutant_seq() -> int:
    _MUTANT_N[0] += 1
    return _MUTANT_N[0]


def _mutant(transform):
    """Compile lib/http.py with a source transform applied. None when it did not apply."""
    src = _HTTP_PATH.read_text(encoding="utf-8")
    mutated = transform(src)
    if mutated == src:
        return None
    name = "mutant_http_%d" % _mutant_seq()
    mod = types.ModuleType(name)
    mod.__file__ = str(_HTTP_PATH)
    mod.__package__ = "lib"
    # Registered in sys.modules BEFORE exec: lib/http.py defines a @dataclass, and
    # dataclasses resolves cls.__module__ through sys.modules to look up type names.
    # An unregistered synthetic module makes that lookup return None and the decorator
    # raises AttributeError -- which would have been recorded as a mutant "caught" when
    # in fact nothing was tested. A crash is not a catch.
    sys.modules[name] = mod
    try:
        exec(compile(mutated, str(_HTTP_PATH), "exec"), mod.__dict__)  # noqa: S102
    finally:
        sys.modules.pop(name, None)
    return mod


def _curl_raises(module, payload: str) -> bool:
    """True when the module curl path refuses payload as a challenge."""
    real = module.subprocess.run
    module.subprocess.run = _curl_returning(payload)
    try:
        module._curl_fetch_text("https://help.elgato.com/hc/en-us/sections/1", 5, None)
        return False
    except Exception:  # noqa: BLE001
        return True
    finally:
        module.subprocess.run = real


def _urllib_raises(module, base: str, payload: str, status: int = 200,
                   headers: dict = None) -> bool:
    _Server.body = payload
    _Server.status = status
    _Server.extra_headers = headers or {}
    try:
        module.fetch_text(base, timeout=5)
        return False
    except Exception:  # noqa: BLE001
        return True


def section_a() -> None:
    print("")
    print("[A] looks_like_challenge -- the transport authority")
    detect = auxhttp.looks_like_challenge
    check("A1 the real recorded Elgato interstitial is a challenge",
          detect(RECORDED_CHALLENGE) is True)
    check("A2 a release note carrying the phrase in PROSE is not a challenge",
          detect(PROSE_NEGATIVE) is False,
          "the title marker must require the phrase inside a title element")
    check("A3 a cf-mitigated challenge header with a clean body is a challenge",
          detect(CLEAN_DOC, {"cf-mitigated": "challenge"}) is True)
    check("A4 cf-mitigated none is NOT a challenge",
          detect(CLEAN_DOC, {"cf-mitigated": "none"}) is False,
          "none is Cloudflare saying it did not mitigate; a hit here would refuse every "
          "page served through Cloudflare")
    check("A5 cf-chl-bypass is a challenge",
          detect(CLEAN_DOC, {"cf-chl-bypass": "1"}) is True)
    check("A6 an empty body with no headers is not a challenge", detect("", None) is False)
    check("A7 the Turnstile script marker is a challenge",
          detect('<html><body><script src="/turnstile/v0/api.js"></script>') is True)
    check("A8 the challenge-platform path marker is a challenge",
          detect('<html><body><script src="/cdn-cgi/challenge-platform/h/b/x">') is True)
    padded = ("<!-- " + ("x" * auxhttp._CHALLENGE_SCAN_BYTES) + " -->"
              + '<script src="/cdn-cgi/challenge-platform/h/b/x"></script>')
    check("A9 a marker past the scan bound is MISSED, which is the documented bound",
          detect(padded) is False,
          "if this fails the scan bound changed and the comment in http.py must change too")
    check("A10 Akamai wording is NOT this authority's business",
          detect(AKAMAI_REFUSAL) is False,
          "widening the RAISING path to match akamai would fire on akamaihd.net asset "
          "URLs; the Photoshop probe owns that broader heuristic deliberately")


def section_b(base: str) -> None:
    print("")
    print("[B] BOTH FetchResult paths refuse a challenge")
    check("B1 the urllib path raises on a 200-served challenge",
          _urllib_raises(auxhttp, base, RECORDED_CHALLENGE) is True)
    check("B2 the CURL path raises on a 200-served challenge",
          _curl_raises(auxhttp, RECORDED_CHALLENGE) is True,
          "this is the branch the guard originally missed: curl exits 0 and the function "
          "hard-codes status 200, so an unguarded return looks exactly like success")

    _Server.body = RECORDED_CHALLENGE
    _Server.status = 200
    _Server.extra_headers = {}
    kept = auxhttp.fetch_text(base, timeout=5, raise_on_challenge=False)
    check("B3 the urllib path honours raise_on_challenge False",
          kept.text == RECORDED_CHALLENGE,
          "probe_photoshop_sources needs the body to characterise HOW a host refuses us")

    real = auxhttp.subprocess.run
    auxhttp.subprocess.run = _curl_returning(RECORDED_CHALLENGE)
    try:
        kept2 = auxhttp._curl_fetch_text(
            "https://helpx.adobe.com/x.html", 5, None, raise_on_challenge=False)
        held = kept2.text == RECORDED_CHALLENGE
    finally:
        auxhttp.subprocess.run = real
    check("B4 the curl path honours raise_on_challenge False", held)

    _Server.body = RECORDED_CHALLENGE
    _Server.status = 200
    _Server.extra_headers = {}
    raised = ""
    try:
        auxhttp.fetch_text(base, timeout=5)
    except Exception as exc:  # noqa: BLE001
        raised = str(exc)
    check("B5 the raised error classifies as challenged, not blocked",
          auxstate.classify_error(raised) == "challenged",
          "classify_error returned " + repr(auxstate.classify_error(raised)))

    _Server.body = CLEAN_DOC
    good = auxhttp.fetch_text(base, timeout=5)
    check("B6 a clean document still returns on the urllib path",
          good.text == CLEAN_DOC and good.status == 200)

    real = auxhttp.subprocess.run
    auxhttp.subprocess.run = _curl_returning(CLEAN_DOC)
    try:
        good2 = auxhttp._curl_fetch_text("https://helpx.adobe.com/x.html", 5, None)
        passed = good2.text == CLEAN_DOC
    finally:
        auxhttp.subprocess.run = real
    check("B7 a clean document still returns on the curl path", passed)


def section_c() -> None:
    print("")
    print("[C] the curl fallback is restricted to the host the docstring promises")
    reached: list = []
    real_curl = auxhttp._curl_fetch_text
    real_opener = auxhttp._OPENER
    real_run = auxhttp.subprocess.run

    class _Dead:
        def open(self, req, timeout=None):
            raise auxhttp.urllib.error.URLError("simulated")

    def spy(url, timeout, headers, **kw):
        reached.append(url)
        return real_curl(url, timeout, headers, **kw)

    auxhttp._curl_fetch_text = spy
    auxhttp._OPENER = _Dead()
    auxhttp.subprocess.run = _curl_returning(CLEAN_DOC)
    try:
        cases = (
            ("C1 a NON-adobe host with curl_fallback set does NOT reach the fallback",
             "https://help.elgato.com/hc/en-us/sections/1", True, False),
            ("C2 an adobe host with curl_fallback set DOES reach the fallback",
             "https://helpx.adobe.com/photoshop/x.html", True, True),
            ("C3 an adobe host without curl_fallback does NOT reach the fallback",
             "https://helpx.adobe.com/photoshop/x.html", False, False),
        )
        for label, url, flag, expect in cases:
            reached.clear()
            try:
                auxhttp.fetch_text(url, timeout=5, curl_fallback=flag)
            except Exception:  # noqa: BLE001
                pass
            detail = ""
            if not expect:
                detail = "A or (host and A) reduces to A, so the clause restricted nothing"
            check(label, bool(reached) is expect, detail)
    finally:
        auxhttp._curl_fetch_text = real_curl
        auxhttp._OPENER = real_opener
        auxhttp.subprocess.run = real_run


def section_d() -> None:
    print("")
    print("[D] the state reaches the one reader-facing surface")
    check("D1 the recorded Elgato error classifies as challenged",
          auxstate.classify_error(RECORDED_ERROR) == "challenged")
    check("D2 a plain 403 still classifies as blocked",
          auxstate.classify_error("HTTP 403 forbidden while fetching") == "blocked",
          "the challenge branch must not swallow ordinary refusals")
    check("D3 the recorded Elgato error renders as a bot check, not as a refusal",
          friendly_error(RECORDED_ERROR) == "Automated bot check blocked the last check",
          "got " + repr(friendly_error(RECORDED_ERROR)) + "; before the fix a challenged "
          "source rendered as Blocked or forbidden by source")
    check("D4 a plain 403 still renders as blocked",
          friendly_error("HTTP 403 forbidden") == "Blocked or forbidden by source")
    check("D5 the challenge branch precedes the 403 branch in BOTH classifiers",
          auxstate.classify_error(RECORDED_ERROR) == "challenged"
          and friendly_error(RECORDED_ERROR) != "Blocked or forbidden by source",
          "Cloudflare serves the interstitial AT 403, so a substring test on 403 placed "
          "first would claim it and the distinct state would be unreachable in production")


def section_e() -> None:
    print("")
    print("[E] the Photoshop probe keeps its broader diagnostic net")
    import probe_photoshop_sources as probe
    check("E1 the probe heuristic still catches an Akamai refusal",
          bool(probe.EDGE_BLOCK_HEURISTIC_RE.search(AKAMAI_REFUSAL)) is True,
          "Photoshop's blocker is an Akamai edge filter that emits none of Cloudflare's "
          "structural markers, so the probe must not rely on the narrow authority alone")
    check("E2 the probe defers to lib.http for the structural markers",
          probe.looks_like_challenge is auxhttp.looks_like_challenge,
          "one authority for the thing that raises in production")
    src = _PROBE_PATH.read_text(encoding="utf-8")
    check("E3 the probe fetches without letting the transport raise",
          "raise_on_challenge=False" in src,
          "otherwise fetch_text raises and the probe's one real finding collapses into "
          "a generic RuntimeError, contradicting every-failure-mode-is-data")


def section_x(base: str) -> None:
    print("")
    print("[X] mutants -- each half of the guard pinned by a NAMED check")

    def drop_curl_guard(src: str) -> str:
        start = src.find("    if raise_on_challenge and looks_like_challenge(text, None):")
        if start < 0:
            return src
        end = src.find("return FetchResult(url=url, status=200", start)
        if end <= start:
            return src
        return src[:start] + "    " + src[end:]

    def drop_urllib_guard(src: str) -> str:
        old = ("                if raise_on_challenge and "
               "looks_like_challenge(text, resp_headers):")
        return src.replace(old, "                if False:", 1)

    def restore_inoperative_should_curl(src: str) -> str:
        old = 'should_curl = bool(curl_fallback) and "adobe.com" in _domain(url)'
        new = ('should_curl = bool(curl_fallback) or ("adobe.com" in _domain(url) '
               "and bool(curl_fallback))")
        return src.replace(old, new, 1)

    m1 = _mutant(drop_curl_guard)
    check("X1 removing ONLY the curl guard is caught by B2, while B1 still passes",
          m1 is not None
          and _curl_raises(m1, RECORDED_CHALLENGE) is False
          and _urllib_raises(m1, base, RECORDED_CHALLENGE) is True,
          "the curl half must be pinned by a curl check, not covered by the urllib one")

    m2 = _mutant(drop_urllib_guard)
    check("X2 removing ONLY the urllib guard is caught by B1, while B2 still passes",
          m2 is not None
          and _urllib_raises(m2, base, RECORDED_CHALLENGE) is False
          and _curl_raises(m2, RECORDED_CHALLENGE) is True,
          "and symmetrically: the urllib half is not covered by the curl check")

    m3 = _mutant(restore_inoperative_should_curl)
    reached: list = []
    regressed = False
    if m3 is not None:
        real_curl = m3._curl_fetch_text

        class _Dead:
            def open(self, req, timeout=None):
                raise m3.urllib.error.URLError("simulated")

        def spy(url, timeout, headers, **kw):
            reached.append(url)
            return real_curl(url, timeout, headers, **kw)

        m3._curl_fetch_text = spy
        m3._OPENER = _Dead()
        m3.subprocess.run = _curl_returning(CLEAN_DOC)
        try:
            m3.fetch_text("https://help.elgato.com/x", timeout=5, curl_fallback=True)
        except Exception:  # noqa: BLE001
            pass
        regressed = bool(reached)
    check("X3 restoring the inoperative host clause is caught by C1",
          regressed is True,
          "the mutant must let a non-adobe host reach the fallback again")

    health_src = _HEALTH_PATH.read_text(encoding="utf-8")
    mutated = health_src.replace(
        'return "Automated bot check blocked the last check"',
        'return "Blocked or forbidden by source"', 1)
    collapsed = False
    if mutated != health_src:
        mod = types.ModuleType("mutant_health")
        mod.__file__ = str(_HEALTH_PATH)
        sys.modules["mutant_health"] = mod
        try:
            exec(compile(mutated, mod.__file__, "exec"), mod.__dict__)  # noqa: S102
        finally:
            sys.modules.pop("mutant_health", None)
        collapsed = mod.friendly_error(RECORDED_ERROR) == "Blocked or forbidden by source"
    check("X4 collapsing the public challenge label back into blocked is caught by D3",
          collapsed is True)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:" + str(server.server_address[1]) + "/release-notes"
    try:
        section_a()
        section_b(base)
        section_c()
        section_d()
        section_e()
        section_x(base)
    finally:
        server.shutdown()

    print("")
    print("=" * 60)
    total = _PASS + _FAIL
    print("Results: " + str(_PASS) + "/" + str(total) + " passed, " + str(_FAIL) + " failed")
    for item in _ERRORS:
        print("  - " + item)
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
