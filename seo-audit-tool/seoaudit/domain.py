"""Single-domain scoping — the safety core of the tool.

Everything the tool touches must belong to the one authorised target domain.
This module normalises URLs, derives the registrable domain, and answers the
question "is this URL in scope?". It deliberately has no network side effects.

The registrable-domain logic uses a small built-in list of common multi-label
public suffixes (``co.uk`` etc.). It is a heuristic — for exhaustive coverage a
full Public Suffix List could be plugged in — but it is conservative: when in
doubt it treats fewer things as "same site", which is the safe direction for a
scoping guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse

# Common two-label public suffixes. Not exhaustive by design; extend as needed.
_MULTI_LABEL_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "me.uk",
    "com.au", "net.au", "org.au", "gov.au", "edu.au",
    "co.nz", "com.br", "com.mx", "co.jp", "co.kr", "co.in",
    "com.cn", "com.sg", "com.tr", "com.ua", "co.za",
}


def normalize_host(host: str) -> str:
    host = (host or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    # Strip a trailing dot (fully-qualified form) and any port.
    host = host.rstrip(".")
    if ":" in host:
        host = host.split(":", 1)[0]
    return host


def registrable_domain(host: str) -> str:
    """Return the registrable ("apex") domain for a hostname.

    ``blog.shop.example.co.uk`` -> ``example.co.uk``;
    ``a.example.com`` -> ``example.com``.
    """
    host = normalize_host(host)
    if not host or "." not in host:
        return host
    labels = host.split(".")
    last_two = ".".join(labels[-2:])
    if last_two in _MULTI_LABEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def canonicalize_url(url: str) -> Optional[str]:
    """Normalise a URL for de-duplication.

    Lower-cases the host, drops fragments and default ports, and strips a
    trailing slash from non-root paths. Returns ``None`` for non-http(s) URLs.
    """
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    host = normalize_host(parsed.netloc)
    if not host:
        return None
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((parsed.scheme, host, path, "", parsed.query, ""))


@dataclass
class DomainScope:
    """Decides whether URLs belong to the authorised target."""

    domain: str
    include_subdomains: bool = True

    def __post_init__(self) -> None:
        self.registrable = registrable_domain(self.domain)
        self.exact_host = normalize_host(self.domain)
        if not self.registrable:
            raise ValueError(f"Invalid target domain: {self.domain!r}")

    def host_in_scope(self, host: str) -> bool:
        host = normalize_host(host)
        if not host:
            return False
        if self.include_subdomains:
            return registrable_domain(host) == self.registrable
        return host == self.exact_host or host == self.registrable

    def url_in_scope(self, url: str) -> bool:
        if not url:
            return False
        if "://" not in url:
            url = "http://" + url
        try:
            host = urlparse(url).netloc
        except ValueError:
            return False
        return self.host_in_scope(host)

    @property
    def site_operator_value(self) -> str:
        """Value to use with the ``site:`` search operator."""
        return self.registrable if self.include_subdomains else self.exact_host
