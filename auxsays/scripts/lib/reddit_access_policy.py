"""Reddit data-access policy: the one authority for whether AUXSAYS may collect from Reddit.

Automated collection of Reddit content for commercial use needs the platform's explicit written
permission. A configured OAuth client id, a polite User-Agent, a request delay and a run of
successful responses are NOT that permission, and neither is the absence of a block.

Default: NOT authorised. Every Reddit path (JSON search, JSON listing, OAuth, RSS/Atom, single-post
hydration) is switched off, for every product, until a written authorisation exists and its
reference is recorded in `AUXSAYS_REDDIT_ACCESS_AUTHORIZATION_REF`. That variable holds a
REFERENCE (a document or ticket identifier), never a credential. This module never reads or
prints any secret.

What this module does and does not change:
  * it stops NEW requests to Reddit hosts, and makes every Reddit method report a truthful
    `disabled` row whose reason is POLICY_REASON, never `no_results` or `success`;
  * it does not touch stored evidence, counted status, identities, URLs, counts, dates or
    verdicts, and it does not make a disabled family count as healthy (a `disabled` row is
    neither healthy nor failing, exactly as the monitoring ledger defines it).

Stdlib only, so it is safe to import from collectors that run as bare scripts.
"""
from __future__ import annotations

import os
from typing import Any, Mapping
from urllib.parse import urlparse

POLICY_REASON = "reddit_access_policy_unauthorised"
AUTHORIZATION_ENV = "AUXSAYS_REDDIT_ACCESS_AUTHORIZATION_REF"

# PUBLIC COPY: the methodology page prints a health row's `notes`. No paths, no module names.
POLICY_NOTE = (
    "Not run. Automated collection from this source is switched off while written data-access "
    "authorisation is outstanding. Reports recorded earlier are unchanged and are subject to "
    "a separate review."
)

_FALSEY = {"", "0", "false", "no", "off", "none", "null", "n/a", "na"}
_REDDIT_HOSTS = ("reddit.com", "redd.it", "redditmedia.com")


class RedditAccessPolicyError(RuntimeError):
    """Raised by a transport that was asked to reach Reddit without authorisation."""

    def __init__(self, message: str = POLICY_REASON) -> None:
        super().__init__(message)
        self.reason = POLICY_REASON


def reddit_access_authorized(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(AUTHORIZATION_ENV, "") or "").strip().lower() not in _FALSEY


def require_reddit_access(env: Mapping[str, str] | None = None) -> None:
    """Transport-level backstop: refuse BEFORE any socket is opened."""
    if not reddit_access_authorized(env):
        raise RedditAccessPolicyError()


def is_reddit_url(url: Any) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _REDDIT_HOSTS)


def is_policy_disabled_row(row: Mapping[str, Any]) -> bool:
    """A method-health row emitted by this policy (and so safe to carry the prior attempt time)."""
    return (str(row.get("status") or "").strip().lower() == "disabled"
            and str(row.get("blocked_reason") or "").strip() == POLICY_REASON)
