"""Single-domain scoping — the safety core of the tool.

Everything the tool touches must belong to the one authorised target domain.
This module normalises URLs, derives the registrable domain, and answers the
question "is this URL in scope?". It deliberately has no network side effects.

The registrable-domain logic uses the Public Suffix List (ICANN *and* private
sections, e.g. ``com.ru``, ``co.uk``, ``github.io``) via ``tldextract``'s
bundled snapshot. No network fetch and no disk cache are used at runtime.
When a host has no registrable part (a bare public suffix such as ``com.ru``,
``localhost``, an IP address) the host itself is returned, so scope never
widens beyond what was explicitly given.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse

import tldextract

_extractor: Optional["tldextract.TLDExtract"] = None


def _get_extractor() -> "tldextract.TLDExtract":
    """Offline PSL extractor: bundled snapshot only, private suffixes included."""
    global _extractor
    if _extractor is None:
        _extractor = tldextract.TLDExtract(
            suffix_list_urls=(),  # never fetch the PSL over the network
            cache_dir=None,  # no on-disk cache writes
            include_psl_private_domains=True,  # github.io, blogspot.com, ...
        )
    return _extractor


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
    ``a.example.com`` -> ``example.com``;
    ``shop.example.com.ru`` -> ``example.com.ru``;
    ``user.github.io`` -> ``user.github.io``.
    """
    host = normalize_host(host)
    if not host or "." not in host:
        return host
    ext = _get_extractor()(host)
    registrable = getattr(ext, "top_domain_under_public_suffix", None)
    if registrable is None:  # tldextract < 5.3
        registrable = ext.registered_domain
    # No registrable part (bare public suffix, IP, unknown): stay on the exact
    # host rather than widening scope.
    return registrable or host


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
