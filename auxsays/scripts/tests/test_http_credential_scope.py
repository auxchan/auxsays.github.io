#!/usr/bin/env python3
"""Credential-scope regression for lib/http.py.

`_headers()` used to default to ``include_auth=True``, so EVERY fetch_text/fetch_json call
attached ``Authorization: Bearer $GITHUB_TOKEN`` whenever the variable existed -- and the
production workflows put it in the job environment. Adobe, community.adobe.com, Reddit and
any config-driven third party therefore received the repository token.

These tests pin the corrected contract with a real loopback HTTP server that records the
headers it actually received, so the assertions cover the wire, not just the helper's
return value:

  * generic vendor fetches are unauthenticated even with a token in the environment;
  * only an EXACT approved host may receive the token (no substring/suffix tricks);
  * a redirect off an approved host strips Authorization;
  * no token value appears in raised errors.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_http_credential_scope.py
"""
from __future__ import annotations

import inspect
import os
import sys
import threading
import traceback
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lib import http as auxhttp  # noqa: E402

TOKEN = "ghs_TESTONLY_NOT_A_REAL_TOKEN_0123456789"

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


class _Recorder(BaseHTTPRequestHandler):
    received: list[dict] = []
    redirect_to: str = ""

    def do_GET(self):  # noqa: N802
        _Recorder.received.append({
            "path": self.path,
            "host_header": self.headers.get("Host", ""),
            "authorization": self.headers.get("Authorization"),
        })
        if self.path.startswith("/redirect") and _Recorder.redirect_to:
            self.send_response(302)
            self.send_header("Location", _Recorder.redirect_to)
            self.end_headers()
            return
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence
        return


def run() -> int:  # noqa: PLR0915
    print("=" * 60)
    print("lib/http.py credential-scope tests")
    print("=" * 60)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    prior_token = os.environ.get("GITHUB_TOKEN")
    prior_hosts = auxhttp.GITHUB_AUTH_HOSTS
    os.environ["GITHUB_TOKEN"] = TOKEN
    try:
        # --- PERMANENT INVARIANT: the generic builder cannot mint credentials ----
        # Stronger than "defaults to off": _headers() has no access to the token at all, so a
        # future caller cannot re-enable the original leak through this primitive.
        check("_headers() contains NO Authorization with GITHUB_TOKEN in the environment",
              "Authorization" not in auxhttp._headers(),
              str(sorted(auxhttp._headers())))
        check("no argument can make _headers() attach a credential (no include_auth parameter)",
              "include_auth" not in inspect.signature(auxhttp._headers).parameters,
              str(inspect.signature(auxhttp._headers)))
        # Assert on the COMPILED code object, not the source text: a docstring that merely
        # explains the old defect must not satisfy or break this invariant.
        _code = auxhttp._headers.__code__
        check("_headers() cannot read the environment (no getenv/os in its code object)",
              "getenv" not in _code.co_names and "os" not in _code.co_names,
              f"co_names={_code.co_names}")
        # co_consts[0] is the docstring, which legitimately explains the old defect; exclude it
        # so the invariant tests executable constants only.
        _doc = auxhttp._headers.__doc__ or ""
        _live_consts = [c for c in _code.co_consts if isinstance(c, str) and c != _doc]
        check("_headers() has no GITHUB_TOKEN constant among its executable constants",
              not any("GITHUB_TOKEN" in c for c in _live_consts),
              f"consts={_live_consts[:6]}")
        check("_headers() cannot fabricate Authorization for ANY extra-header input",
              all("Authorization" not in auxhttp._headers(extra)
                  for extra in ({}, {"Accept": "text/html"}, {"X-Thing": "1"})))
        check("only fetch_text reads the token, and only after the destination gate",
              (lambda src: "GITHUB_TOKEN" in src and src.index("_github_auth_allowed") < src.index("GITHUB_TOKEN"))
              (inspect.getsource(auxhttp.fetch_text)))
        check("the origin gate reads no environment variable (cannot consult the token)",
              "getenv" not in auxhttp._github_auth_allowed.__code__.co_names
              and "environ" not in auxhttp._github_auth_allowed.__code__.co_names,
              f"co_names={auxhttp._github_auth_allowed.__code__.co_names}")
        check("the gate authorizes from parsed URL components, not a normalized netloc string",
              (lambda src: "urlsplit" in src
               and all(w in src for w in ("hostname", "username", "password", "port"))
               and "_netloc" not in src)(inspect.getsource(auxhttp._github_auth_allowed)),
              "gate must not approve a host after discarding userinfo/port")
        check("an explicitly supplied Authorization is the caller's own value, still not fabricated",
              auxhttp._headers({"Authorization": "Bearer CALLER-SUPPLIED"}).get("Authorization")
              == "Bearer CALLER-SUPPLIED")

        # --- exact host matching -----------------------------------------
        for url, allowed, why in (
            ("https://api.github.com/repos/x/y/releases", True, "the real approved host"),
            ("https://helpx.adobe.com/media-encoder/release-notes.html", False, "Adobe"),
            ("https://community.adobe.com/search/getTopics", False, "community.adobe.com"),
            ("https://www.reddit.com/r/x/search.json", False, "Reddit"),
            ("https://attacker.example/collect", False, "arbitrary third party"),
            ("https://api.github.com.evil.example/x", False, "suffix-appended lookalike"),
            ("https://github.com/owner/repo/releases", False, "github.com is not the API host"),
            ("https://evil.example/?u=api.github.com", False, "host in query string"),
            ("http://api.github.com/x", False, "plain http is refused"),
            ("https://API.GITHUB.COM/x", True, "case-insensitive host"),
            ("https://api.github.com:443/x", True, "explicit default port"),
            ("https://user@api.github.com/x", False, "userinfo is a noncanonical authority"),
        ):
            check(f"github auth {'allowed' if allowed else 'refused'} for {why}",
                  auxhttp._github_auth_allowed(url) is allowed, url)

        # --- exact APPROVED HTTPS ORIGIN, not merely an approved hostname -
        # The gate decides whether a repository-scoped token may leave the process, so it must
        # authorize a canonical origin (https + api.github.com + no userinfo + default port).
        # Discarding userinfo or a nondefault port and then approving the surviving hostname is
        # too permissive: :444 and user@ are different destinations from the approved one.
        for url, allowed, why in (
            ("https://api.github.com/x", True, "canonical origin"),
            ("https://api.github.com:443/x", True, "explicit default port 443"),
            ("https://API.GITHUB.COM/x", True, "case-insensitive host"),
            ("https://api.github.com:444/x", False, "nondefault port 444"),
            ("https://api.github.com:12345/x", False, "nondefault port 12345"),
            ("https://api.github.com:65535/x", False, "nondefault port 65535"),
            ("https://api.github.com:0/x", False, "port 0"),
            ("https://user@api.github.com/x", False, "userinfo"),
            ("https://user:password@api.github.com/x", False, "userinfo with password"),
            ("https://:password@api.github.com/x", False, "password-only userinfo"),
            ("https://user@api.github.com:444/x", False, "userinfo AND nondefault port"),
            ("https://api.github.com.evil.example/x", False, "suffix-appended lookalike"),
            ("http://api.github.com/x", False, "plain http"),
        ):
            try:
                verdict = auxhttp._github_auth_allowed(url)
                escaped = ""
            except Exception as exc:  # noqa: BLE001 - a raising gate is itself the defect
                verdict, escaped = None, f"{type(exc).__name__}: {exc}"
            check(f"exact-origin gate {'ALLOWS' if allowed else 'REFUSES'} {why}",
                  verdict is allowed, f"{url} -> {verdict!r} {escaped}")

        # A malformed port must fail closed WITHOUT an exception escaping the gate: callers
        # treat a raise as a crash, not as a refusal.
        for bad in ("https://api.github.com:notaport/x", "https://api.github.com:-1/x",
                    "https://api.github.com:99999999999999/x", "https://api.github.com:44 4/x"):
            try:
                verdict = auxhttp._github_auth_allowed(bad)
                raised = False
            except Exception:  # noqa: BLE001
                verdict, raised = None, True
            check(f"malformed port fails closed with no exception escape: {bad.split('//')[1][:34]}",
                  verdict is False and not raised, f"verdict={verdict!r} raised={raised}")

        # --- the redirect gate must be the SAME rule, not a parallel one ---
        def _redirect_keeps_auth(newurl: str):
            """True when the redirected request still carries Authorization anywhere."""
            handler = auxhttp._AuthStrippingRedirectHandler()
            req = urllib.request.Request("https://api.github.com/start")
            # add_header (not add_unredirected_header) so stock urllib WOULD forward it; this
            # isolates our handler's stripping instead of measuring urllib's own behaviour.
            req.add_header("Authorization", "Bearer REDIRECT-PROBE")
            new = handler.redirect_request(req, None, 302, "Found", {}, newurl)
            if new is None:
                return False
            keys = [str(k).lower() for k in list(new.headers) + list(new.unredirected_hdrs)]
            return "authorization" in keys

        check("redirect to a third party STRIPS Authorization",
              _redirect_keeps_auth("https://attacker.example/collect") is False)
        check("redirect to api.github.com:444 STRIPS Authorization (same origin rule)",
              _redirect_keeps_auth("https://api.github.com:444/x") is False)
        check("redirect to a userinfo authority STRIPS Authorization",
              _redirect_keeps_auth("https://user@api.github.com/x") is False)
        check("redirect to http://api.github.com STRIPS Authorization",
              _redirect_keeps_auth("http://api.github.com/x") is False)
        check("redirect to the canonical origin may KEEP Authorization",
              _redirect_keeps_auth("https://api.github.com/next") is True)
        check("redirect to the explicit default port may KEEP Authorization",
              _redirect_keeps_auth("https://api.github.com:443/next") is True)
        check("the redirect handler calls the one shared gate (no parallel rule)",
              "_github_auth_allowed" in
              inspect.getsource(auxhttp._AuthStrippingRedirectHandler.redirect_request))

        # --- on the wire: generic fetch is unauthenticated ----------------
        _Recorder.received.clear()
        auxhttp.fetch_text(f"{base}/vendor-page")
        got = _Recorder.received[-1]
        check("fetch_text() sends NO Authorization to a generic host (wire-verified)",
              got["authorization"] is None, f"got {got['authorization']!r}")

        _Recorder.received.clear()
        auxhttp.fetch_text(f"{base}/vendor-page", authenticate=True)
        got = _Recorder.received[-1]
        check("authenticate=True is REFUSED for a non-approved host (wire-verified)",
              got["authorization"] is None, f"got {got['authorization']!r}")

        # --- wire proof: approved HOSTNAME is not enough ------------------
        # The loopback server listens on http and a nondefault port. With its hostname added to
        # the approved set and the REAL gate in force, authenticate=True must still send nothing:
        # a fail-closed origin check, measured on the wire rather than asserted about the helper.
        auxhttp.GITHUB_AUTH_HOSTS = frozenset({"127.0.0.1"})
        try:
            _Recorder.received.clear()
            auxhttp.fetch_json(f"{base}/repos/x/y/releases")
            got = _Recorder.received[-1]
            check("approved hostname on a NONDEFAULT PORT gets no token (wire-verified)",
                  got["authorization"] is None, f"got {got['authorization']!r}")
        finally:
            auxhttp.GITHUB_AUTH_HOSTS = prior_hosts

        # --- on the wire: approved host does receive it -------------------
        auxhttp.GITHUB_AUTH_HOSTS = frozenset({"127.0.0.1"})
        # https is required by the real gate; relax only the scheme check for the loopback test
        real_gate = auxhttp._github_auth_allowed
        auxhttp._github_auth_allowed = (
            lambda u: urllib.parse.urlsplit(u).hostname in auxhttp.GITHUB_AUTH_HOSTS)
        try:
            _Recorder.received.clear()
            auxhttp.fetch_json(f"{base}/repos/x/y/releases")
            got = _Recorder.received[-1]
            check("fetch_json() DOES authenticate an approved host (wire-verified)",
                  got["authorization"] == f"Bearer {TOKEN}",
                  f"got {got['authorization']!r}")

            _Recorder.received.clear()
            auxhttp.fetch_text(f"{base}/vendor-page")
            check("a plain fetch_text to the same approved host stays unauthenticated",
                  _Recorder.received[-1]["authorization"] is None)

            # --- redirect off the approved host strips the token ----------
            second = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
            second_port = second.server_address[1]
            threading.Thread(target=second.serve_forever, daemon=True).start()
            # "localhost" is a DIFFERENT netloc string than "127.0.0.1", so it is not approved
            _Recorder.redirect_to = f"http://localhost:{second_port}/external-target"
            _Recorder.received.clear()
            try:
                auxhttp.fetch_json(f"{base}/redirect-me")
            except Exception:  # noqa: BLE001 - only the recorded headers matter
                pass
            hops = _Recorder.received
            first_hop = next((h for h in hops if h["path"].startswith("/redirect")), None)
            target_hop = next((h for h in hops if h["path"] == "/external-target"), None)
            check("redirect hop was actually followed (test is meaningful)",
                  first_hop is not None and target_hop is not None,
                  f"hops={[h['path'] for h in hops]}")
            check("approved host received the token on the FIRST hop",
                  bool(first_hop) and first_hop["authorization"] == f"Bearer {TOKEN}")
            check("Authorization is STRIPPED on redirect to a non-approved host",
                  bool(target_hop) and target_hop["authorization"] is None,
                  f"got {target_hop['authorization'] if target_hop else 'no hop'!r}")
            _Recorder.redirect_to = ""
            second.shutdown()
        finally:
            auxhttp._github_auth_allowed = real_gate
            auxhttp.GITHUB_AUTH_HOSTS = prior_hosts

        # --- no secret in errors -----------------------------------------
        try:
            auxhttp.fetch_text(f"http://127.0.0.1:{port}/nope", timeout=2)
            err_text = ""
        except Exception as exc:  # noqa: BLE001
            err_text = str(exc)
        try:
            auxhttp.fetch_text("http://127.0.0.1:1/closed", timeout=2)
        except Exception as exc:  # noqa: BLE001
            err_text += " " + str(exc)
        check("no token value appears in raised error text", TOKEN not in err_text)
        check("the curl fallback path never forwards Authorization",
              "if key.lower() == \"authorization\":"
              in (_SCRIPTS / "lib" / "http.py").read_text(encoding="utf-8"))
    finally:
        if prior_token is None:
            os.environ.pop("GITHUB_TOKEN", None)
        else:
            os.environ["GITHUB_TOKEN"] = prior_token
        auxhttp.GITHUB_AUTH_HOSTS = prior_hosts
        server.shutdown()

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
