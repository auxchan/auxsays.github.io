"""Hosts no AUXSAYS ingestion lane may request, whatever a source config says (G66).

WHY. support.microsoft.com is Microsoft's support-article host. Its terms for automated collection
and publication are unresolved (the K1 ruling, from the 2026-11-10 Microsoft KB source assessment;
reaffirmed 2026-11-20: no support.microsoft.com collector until the terms are established). The
Teams lane still listed a support.microsoft.com page as its `secondary_official_url`, and the Office
adapter fetched every configured URL in order, so an unreachable or reshaped primary page would
have sent a production request there. This module is the one list of such hosts. The Office
adapter refuses them before any request, and validate_ingestion_sources.py refuses a source config
that names one, so the mistake fails the config check instead of waiting for a primary outage.

WHAT IS MATCHED. The parsed hostname: the host itself and every subdomain of it, on any path, any
scheme and any port, and through a userinfo prefix (``https://learn.microsoft.com@support.microsoft.com/``
contacts support.microsoft.com). Equality or a dot-boundary suffix, never a substring, so a host
that merely contains the name elsewhere is not swept up.

WHAT IS NOT. A plain deep LINK to a support article stays permitted (the 11-10 assessment rated a
link that lands on the originating page PERMITTED). This module is about requests a lane makes,
not about links a page shows.

Standard library only: the adapters and the config validator run as bare scripts.
"""
from __future__ import annotations

import urllib.parse

REFUSED_FETCH_HOSTS = frozenset({"support.microsoft.com"})


def hostname(url: object) -> str:
    """The lowercased hostname `url` would contact, without a trailing dot; "" if it has none."""
    try:
        host = urllib.parse.urlsplit(str(url or "").strip()).hostname or ""
    except ValueError:
        return ""
    return host.rstrip(".").lower()


def refused_host(url: object) -> str:
    """The refused host `url` would contact (the matched list entry), or "" when it names none."""
    host = hostname(url)
    if not host:
        return ""
    for refused in REFUSED_FETCH_HOSTS:
        if host == refused or host.endswith("." + refused):
            return refused
    return ""
