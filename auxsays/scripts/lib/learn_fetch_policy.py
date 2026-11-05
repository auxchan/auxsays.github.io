"""Same-origin fetch policy for Microsoft Learn Q&A pages and feeds.

THE DEFECT THIS CLOSES. Every production Learn Q&A fetcher opened its URL with urllib's default
``urlopen``, whose redirect handler follows a 30x to ANY http(s) host, and none of them checked
where the response finally came from. The callers then parse the body under the URL they ASKED for:
``lib/context_resolution`` hands it to ``parse_learn_qna_thread(url, page)``, Teams builds segment
candidates keyed on the requested thread URL, and the search-RSS lane turns each item into a
candidate. A page served by another host after a redirect would have been read as the Learn thread
this run discovered. The shelved Windows hydration branch (AUX-073) found and closed exactly this
class on its own new path; this module is that protection, extracted and shared, so the EXISTING
fetchers get it too.

WHAT A FETCH MAY TOUCH. A URL is acceptable only when all three hold:
  * the scheme is ``https`` (an ``http`` downgrade is refused);
  * the authority is exactly ``learn.microsoft.com`` -- no userinfo, no port other than 443, no
    lookalike such as ``learn.microsoft.com.example.net``;
  * the path has the shape the calling fetcher already uses (a question page, a tag page or the tag
    index, or the search-RSS endpoint). A question fetch that is redirected to a sign-in page or to a
    tag listing is refused even on the right host.

WHEN IT IS CHECKED. Three times, and the middle one is the point:
  1. the initial URL, before any request;
  2. every redirect destination, BEFORE the redirected request is made (``SameOriginRedirect``). A
     final-URL check alone cannot see a chain that leaves Learn and comes back, and by then the other
     host has already been asked;
  3. the final URL of the response, before a single byte of the body is read.

WHAT IT DOES NOT DO. It decides nothing about what a page means, adds no endpoint and no request, and
carries no cookies, credentials or challenge handling: the opener is urllib's default chain with the
redirect handler replaced, so a same-origin redirect (a renamed question slug, a retired tag sent to
the tag index) is followed exactly as before.

A refusal is a named failure, never an empty result: ``LearnFetchRefused.reason`` is one of
``REFUSAL_REASONS``, and each fetcher converts it into its own error type so its method health names
it. Standard library only -- every collector and the orchestrator run as bare scripts.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request

LEARN_SCHEME = "https"
LEARN_HOST = "learn.microsoft.com"
_DEFAULT_PORT = 443

# The page shapes the existing fetchers request. One family per fetch; a redirect must stay inside
# the family the fetch started in.
QUESTION_PAGE = "question_page"
TAG_PAGE = "tag_page"
SEARCH_RSS = "search_rss"

_LOCALE = r"(?:/[a-z]{2}-[a-z]{2})?"
FAMILY_PATHS: dict[str, re.Pattern[str]] = {
    # /en-us/answers/questions/<id>/<slug> -- the thread page every Q&A consumer hydrates. The slug
    # is optional (open-web discovery requests the id-only form) and may be renamed by a redirect.
    QUESTION_PAGE: re.compile(_LOCALE + r"/answers/questions/\d+(?:/[^/]*)?/?", re.I),
    # /en-us/answers/tags/<id>/<slug>/ and the tag index /en-us/answers/tags/, where a retired tag is
    # redirected with disclaimer=tag-not-found (the tag lane names that outcome itself).
    TAG_PAGE: re.compile(_LOCALE + r"/answers/tags(?:/\d+(?:/[^/]*)?)?/?", re.I),
    # /api/search/rss -- the search feed behind the Windows, PowerPoint and Teams discovery lanes.
    SEARCH_RSS: re.compile(r"/api/search/rss/?", re.I),
}

# Where in the fetch a URL was refused.
STAGE_URL = "url"
STAGE_REDIRECT = "redirect"
STAGE_FINAL = "final_url"
STAGES = (STAGE_URL, STAGE_REDIRECT, STAGE_FINAL)

# What was wrong with it.
NOT_HTTPS = "not_https"
OFF_HOST = "off_host"
PATH_NOT_ALLOWED = "path_not_allowed"
CHECKS = (NOT_HTTPS, OFF_HOST, PATH_NOT_ALLOWED)

# THE CLOSED VOCABULARY. Nine names, stage x check, e.g. ``redirect_off_host``. Consumers test
# membership with ``is_refusal`` -- never a substring -- so a reason cannot be half-recognised.
REFUSAL_REASONS = frozenset(f"{stage}_{check}" for stage in STAGES for check in CHECKS)


class LearnFetchRefused(Exception):
    """A Learn fetch AUXSAYS declined to make or to read. Deliberately NOT an ``OSError`` or a
    ``URLError``: the fetchers' transport handlers would otherwise swallow it as an ordinary network
    failure and lose the name."""

    def __init__(self, reason: str, *, url: str = "", status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.url = url
        self.status = status


def is_refusal(reason: object) -> bool:
    """True when ``reason`` names a policy refusal, alone or as one ``:``-separated component of a
    fetcher's composite reason (``learn_qna_search_fetch_failed:redirect_off_host``)."""
    return any(part in REFUSAL_REASONS for part in str(reason or "").split(":"))


def first_refusal(errors: list[dict] | None) -> str:
    """The first error reason in ``errors`` that names a refusal, or ``""``."""
    for error in errors or []:
        reason = str((error or {}).get("reason") or "")
        if is_refusal(reason):
            return reason
    return ""


def _authority_is_learn(parts: urllib.parse.SplitResult) -> bool:
    """Exactly learn.microsoft.com on the default https port: no userinfo, no other port, no lookalike."""
    if "@" in parts.netloc or parts.username is not None or parts.password is not None:
        return False
    try:
        port = parts.port
    except ValueError:
        return False
    if port not in (None, _DEFAULT_PORT):
        return False
    return (parts.hostname or "") == LEARN_HOST


def refusal(url: str, family: str, stage: str) -> str:
    """The refusal reason for fetching ``url`` as ``family`` at ``stage``, or ``""`` when it is allowed.

    An unknown family refuses everything (``path_not_allowed``): a fetcher that has not said what it
    is fetching is not allowed to fetch."""
    parts = urllib.parse.urlsplit(str(url or "").strip())
    if parts.scheme.lower() != LEARN_SCHEME:
        return f"{stage}_{NOT_HTTPS}"
    if not _authority_is_learn(parts):
        return f"{stage}_{OFF_HOST}"
    shape = FAMILY_PATHS.get(family)
    if shape is None or not shape.fullmatch(parts.path or "/"):
        return f"{stage}_{PATH_NOT_ALLOWED}"
    return ""


def page_family(url: str, allowed: tuple[str, ...]) -> str:
    """The first family in ``allowed`` whose path shape ``url`` has, or ``""``.

    For a fetcher that serves more than one page shape (``qna_tags.fetch`` reads tag pages AND
    question pages): the INITIAL url decides the family, and every redirect must then stay in it."""
    path = urllib.parse.urlsplit(str(url or "").strip()).path or "/"
    for family in allowed:
        shape = FAMILY_PATHS.get(family)
        if shape is not None and shape.fullmatch(path):
            return family
    return ""


def _close(fp) -> None:
    if fp is None:
        return
    try:
        fp.close()
    except Exception:  # noqa: BLE001 - best effort; the refusal is what matters
        pass


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to a URL the same policy would have allowed as the first request.

    urllib resolves a relative ``Location`` against the request before calling ``redirect_request``,
    so ``newurl`` is always absolute here. A refused hop raises BEFORE the redirected request is built,
    so no request ever reaches the destination."""

    def __init__(self, family: str) -> None:
        super().__init__()
        self.family = family

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0913 - urllib's signature
        reason = refusal(newurl, self.family, STAGE_REDIRECT)
        if reason:
            _close(fp)
            raise LearnFetchRefused(reason, url=newurl, status=code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_opener(family: str) -> urllib.request.OpenerDirector:
    """urllib's default handler chain with ONE change: the redirect handler is ``SameOriginRedirect``.

    No cookie processor and no auth handler -- the same as ``urlopen``'s own opener."""
    return urllib.request.build_opener(SameOriginRedirect(family))


def open_url(request: urllib.request.Request, *, family: str, timeout: float):
    """Open ``request`` under the policy and return the response, ready to read.

    Raises ``LearnFetchRefused`` for a refused initial URL, redirect or final URL; everything else
    (``HTTPError``, ``URLError``, timeouts) propagates exactly as ``urlopen`` raises it, so each
    fetcher's existing error mapping is unchanged."""
    url = request.full_url
    reason = refusal(url, family, STAGE_URL)
    if reason:
        raise LearnFetchRefused(reason, url=url)
    response = build_opener(family).open(request, timeout=timeout)
    final = str(response.geturl() or "")
    reason = refusal(final, family, STAGE_FINAL)
    if reason:
        status = getattr(response, "status", None)
        _close(response)
        raise LearnFetchRefused(reason, url=final, status=status)
    return response
