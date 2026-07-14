"""A polite HTTP client used to fetch pages of the *owned* domain.

Features aimed at being a good web citizen:

* shared :class:`~seoaudit.ratelimit.RateLimiter` so all threads stay under the
  configured requests-per-second budget;
* optional, honest User-Agent rotation and an optional ``From:`` contact header;
* bounded retries with exponential backoff on transient errors;
* a cached ``robots.txt`` checker so the crawler respects the site's own rules.
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from .logging_setup import get_logger
from .ratelimit import RateLimiter

log = get_logger("http")


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    headers: Dict[str, str]
    text: str
    redirect_chain: List[str]
    content_type: str
    error: Optional[str] = None


class PoliteHTTPClient:
    def __init__(
        self,
        rate_limiter: RateLimiter,
        user_agents: List[str],
        rotate_user_agents: bool = True,
        timeout: float = 15.0,
        max_retries: int = 2,
        respect_robots: bool = True,
        contact_email: Optional[str] = None,
    ) -> None:
        self._rl = rate_limiter
        self._uas = list(user_agents) or ["seoaudit/0.1 (+https://example.invalid)"]
        self._rotate = rotate_user_agents
        self._ua_cycle = itertools.cycle(self._uas)
        self._timeout = timeout
        self._max_retries = max_retries
        self._respect_robots = respect_robots
        self._contact_email = contact_email
        self._session = requests.Session()
        self._robots: Dict[str, Optional[RobotFileParser]] = {}
        self._robots_lock = threading.Lock()

    def _next_ua(self) -> str:
        if self._rotate:
            return next(self._ua_cycle)
        return self._uas[0]

    def _headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self._next_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if self._contact_email:
            headers["From"] = self._contact_email
        return headers

    # -- robots.txt ---------------------------------------------------------

    def _robots_for(self, url: str) -> Optional[RobotFileParser]:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        with self._robots_lock:
            if base in self._robots:
                return self._robots[base]
        rp: Optional[RobotFileParser] = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            self._rl.acquire()
            resp = self._session.get(
                f"{base}/robots.txt", headers=self._headers(), timeout=self._timeout
            )
            if resp.status_code >= 400:
                rp.parse([])  # missing/forbidden robots => allow all
            else:
                rp.parse(resp.text.splitlines())
        except requests.RequestException as exc:
            log.warning("Could not fetch robots.txt for %s: %s", base, exc)
            rp = None  # unknown — treat as allowed but record it
        with self._robots_lock:
            self._robots[base] = rp
        return rp

    def allowed_by_robots(self, url: str) -> Optional[bool]:
        """Return True/False per robots.txt, or None if it couldn't be read."""
        if not self._respect_robots:
            return True
        rp = self._robots_for(url)
        if rp is None:
            return None
        return rp.can_fetch(self._next_ua() if not self._rotate else self._uas[0], url)

    # -- fetching -----------------------------------------------------------

    def get(self, url: str) -> FetchResult:
        last_error: Optional[str] = None
        for attempt in range(self._max_retries + 1):
            self._rl.acquire()
            try:
                resp = self._session.get(
                    url,
                    headers=self._headers(),
                    timeout=self._timeout,
                    allow_redirects=True,
                )
                chain = [h.url for h in resp.history] + [resp.url]
                return FetchResult(
                    url=url,
                    final_url=resp.url,
                    status_code=resp.status_code,
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    text=resp.text if "text" in resp.headers.get("Content-Type", "text")
                    or resp.headers.get("Content-Type", "").startswith("text")
                    else "",
                    redirect_chain=chain,
                    content_type=resp.headers.get("Content-Type", ""),
                )
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt < self._max_retries:
                    backoff = 2 ** attempt
                    log.warning("Fetch failed (%s), retrying in %ss: %s", url, backoff, exc)
                    time.sleep(backoff)
        return FetchResult(
            url=url,
            final_url=url,
            status_code=0,
            headers={},
            text="",
            redirect_chain=[url],
            content_type="",
            error=last_error or "unknown error",
        )

    def close(self) -> None:
        self._session.close()
