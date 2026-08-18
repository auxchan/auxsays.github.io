from __future__ import annotations

import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ALLOWED_HOSTS = {"api.bls.gov", "www.dol.gov", "oui.doleta.gov"}
SECRET_KEYS = {"registrationkey", "api_key", "apikey", "token", "key", "authorization"}


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, "REDACTED" if key.lower() in SECRET_KEYS else value) for key, value in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def redact_mapping(values: dict[str, str]) -> dict[str, str]:
    return {key: ("REDACTED" if key.lower() in SECRET_KEYS else value) for key, value in values.items()}


def validate_url(url: str, resolver=socket.getaddrinfo) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("only credential-free HTTPS URLs on port 443 are allowed")
    hostname = (parts.hostname or "").lower().rstrip(".")
    if hostname not in ALLOWED_HOSTS:
        raise ValueError("host is not allowlisted")
    addresses = {result[4][0] for result in resolver(hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses:
        raise ValueError("host did not resolve")
    for raw in addresses:
        address = ipaddress.ip_address(raw)
        if not address.is_global:
            raise ValueError("resolved address is not globally routable")
    return sanitize_url(url)
