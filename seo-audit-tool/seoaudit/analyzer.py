"""Deep per-page SEO analysis of the *owned* domain.

For each in-scope URL the analyzer fetches the page (politely, respecting
``robots.txt``) and extracts everything needed to judge its search visibility:
HTTP status & redirect chain, ``<title>`` / meta description, meta-robots and
``X-Robots-Tag`` directives, canonical target, a content fingerprint for
near-duplicate detection, and a scan for accidental information leaks that an
owner would want to know about.

Concurrency is bounded and all fetches share one rate limiter, so the target is
never hammered.
"""

from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup

from .domain import DomainScope, canonicalize_url
from .http_client import PoliteHTTPClient
from .logging_setup import get_logger
from .models import Issue, PageAnalysis, Severity

log = get_logger("analyzer")

_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Heuristic patterns for accidental exposure. These are intentionally
# conservative to keep false positives low; every hit is reported as something
# for the *owner* to review, never acted upon.
_LEAK_PATTERNS: List[Tuple[str, str, Severity, re.Pattern]] = [
    ("private_ip", "Internal/private IP address exposed in page",
     Severity.MEDIUM, re.compile(r"\b(?:10|127|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")),
    ("aws_key", "Possible AWS access key ID",
     Severity.CRITICAL, re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", "Private key block",
     Severity.CRITICAL, re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("password_assignment", "Hard-coded password/secret assignment",
     Severity.HIGH, re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\s*[=:]\s*['\"][^'\"]{4,}")),
    ("stack_trace", "Server stack trace / debug output",
     Severity.HIGH, re.compile(r"(?i)(?:traceback \(most recent call last\)|stack trace:|fatal error:|exception in thread)")),
    ("sql_error", "Database error message leaking internals",
     Severity.MEDIUM, re.compile(r"(?i)(?:sql syntax|mysql_fetch|ORA-\d{5}|psql:|SQLSTATE\[)")),
    ("directory_listing", "Open directory listing",
     Severity.MEDIUM, re.compile(r"(?i)index of /")),
    ("env_dump", "Environment/config dump",
     Severity.HIGH, re.compile(r"(?i)(?:DB_PASSWORD|DB_USERNAME|SECRET_KEY|AWS_SECRET_ACCESS_KEY)\s*=")),
]


def _shingles(text: str, k: int = 4, cap: int = 400) -> List[int]:
    """Hash the k-word shingles of ``text`` into a bounded fingerprint set.

    Used for Jaccard near-duplicate detection. ``cap`` limits memory for very
    long pages while preserving comparability.
    """
    words = _WORD_RE.findall(text.lower())
    if len(words) < k:
        if not words:
            return []
        joined = " ".join(words)
        return [int(hashlib.md5(joined.encode()).hexdigest()[:8], 16)]
    grams = set()
    for i in range(len(words) - k + 1):
        gram = " ".join(words[i:i + k])
        grams.add(int(hashlib.md5(gram.encode()).hexdigest()[:8], 16))
    ordered = sorted(grams)
    if len(ordered) > cap:
        # Keep a deterministic, evenly-spread subset.
        step = len(ordered) / cap
        ordered = [ordered[int(i * step)] for i in range(cap)]
    return ordered


def jaccard(a: List[int], b: List[int]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


class PageAnalyzer:
    def __init__(
        self,
        client: PoliteHTTPClient,
        scope: DomainScope,
        concurrency: int = 4,
    ) -> None:
        self.client = client
        self.scope = scope
        self.concurrency = concurrency

    # -- single page --------------------------------------------------------

    def analyze_one(self, url: str) -> PageAnalysis:
        pa = PageAnalysis(url=url)
        if not self.scope.url_in_scope(url):
            pa.error = "URL is not in scope for the target domain"
            pa.issues.append(Issue("off_scope", pa.error, Severity.CRITICAL))
            return pa

        allowed = self.client.allowed_by_robots(url)
        pa.robots_txt_allowed = allowed
        if allowed is False:
            pa.issues.append(Issue(
                "robots_txt_disallow",
                "URL is disallowed by robots.txt, so it will not be respected/crawled.",
                Severity.HIGH,
            ))
            # Still record the state, but don't fetch a disallowed URL.
            return pa

        res = self.client.get(url)
        pa.fetched = res.error is None
        pa.status_code = res.status_code or None
        pa.final_url = res.final_url
        pa.redirect_chain = res.redirect_chain
        pa.content_type = res.content_type
        pa.x_robots_tag = res.headers.get("x-robots-tag")

        if res.error:
            pa.error = res.error
            pa.issues.append(Issue("fetch_error", f"Could not fetch page: {res.error}", Severity.HIGH))
            return pa

        self._analyze_http(pa, res)
        if res.text and "html" in (res.content_type or "").lower():
            self._analyze_html(pa, res.text)
        return pa

    def _analyze_http(self, pa: PageAnalysis, res) -> None:
        code = res.status_code
        if code >= 500:
            pa.issues.append(Issue("http_5xx", f"Server error {code}.", Severity.CRITICAL))
        elif code >= 400:
            pa.issues.append(Issue("http_4xx", f"Client error {code} — page indexed but broken.", Severity.HIGH))
        elif 300 <= code < 400 or len(res.redirect_chain) > 1:
            if len(res.redirect_chain) > 2:
                pa.issues.append(Issue(
                    "redirect_chain",
                    f"Redirect chain of {len(res.redirect_chain) - 1} hops wastes crawl budget.",
                    Severity.MEDIUM,
                ))
        # Downgrade http->https check
        if res.final_url.startswith("http://"):
            pa.issues.append(Issue("no_https", "Final URL is served over plain HTTP.", Severity.MEDIUM))

        # X-Robots-Tag header directives
        xrt = (pa.x_robots_tag or "").lower()
        if "noindex" in xrt:
            pa.robots_index = False
            pa.issues.append(Issue("xrobots_noindex", "X-Robots-Tag header sets noindex.", Severity.HIGH))
        if "nofollow" in xrt:
            pa.robots_follow = False

    def _analyze_html(self, pa: PageAnalysis, html: str) -> None:
        soup = BeautifulSoup(html, "html.parser")

        # Title
        if soup.title and soup.title.string:
            pa.title = soup.title.string.strip()
        if not pa.title:
            pa.issues.append(Issue("missing_title", "Page has no <title>.", Severity.HIGH))
        elif len(pa.title) > 65:
            pa.issues.append(Issue("long_title", f"Title is {len(pa.title)} chars (may be truncated in SERPs).", Severity.LOW))
        elif len(pa.title) < 15:
            pa.issues.append(Issue("short_title", "Title is very short.", Severity.LOW))

        # Meta description
        md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        if md and md.get("content"):
            pa.meta_description = md["content"].strip()
        if not pa.meta_description:
            pa.issues.append(Issue("missing_meta_description", "No meta description.", Severity.MEDIUM))
        elif len(pa.meta_description) > 165:
            pa.issues.append(Issue("long_meta_description", "Meta description likely truncated in SERPs.", Severity.LOW))

        # Meta robots
        mr = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
        if mr and mr.get("content"):
            content = mr["content"].lower()
            if "noindex" in content:
                pa.robots_index = False
                pa.issues.append(Issue("meta_noindex", "Page has meta robots noindex.", Severity.HIGH))
            if "nofollow" in content:
                pa.robots_follow = False
                pa.issues.append(Issue("meta_nofollow", "Page has meta robots nofollow.", Severity.LOW))

        # Canonical
        link_canon = soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
        if link_canon and link_canon.get("href"):
            canon = link_canon["href"].strip()
            pa.canonical = canon
            can_key = canonicalize_url(canon)
            self_key = canonicalize_url(pa.final_url or pa.url)
            pa.canonical_is_self = (can_key == self_key) if can_key and self_key else None
            if pa.canonical_is_self is False:
                pa.issues.append(Issue(
                    "canonical_elsewhere",
                    f"Canonical points to a different URL ({canon}); this page defers indexing to it.",
                    Severity.MEDIUM,
                ))
            if can_key and not self.scope.url_in_scope(canon):
                pa.issues.append(Issue(
                    "canonical_offsite",
                    f"Canonical points off the target domain: {canon}.",
                    Severity.HIGH,
                ))
        else:
            pa.issues.append(Issue("missing_canonical", "No canonical link element.", Severity.LOW))

        # H1s
        h1s = soup.find_all("h1")
        if len(h1s) == 0:
            pa.issues.append(Issue("missing_h1", "No <h1> heading.", Severity.LOW))
        elif len(h1s) > 1:
            pa.issues.append(Issue("multiple_h1", f"{len(h1s)} <h1> headings (should usually be one).", Severity.LOW))

        # Visible text -> word count, fingerprint, thin-content check
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        words = _WORD_RE.findall(text)
        pa.word_count = len(words)
        pa.content_hash = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
        pa.shingles = _shingles(text)
        if pa.word_count < 120:
            pa.issues.append(Issue("thin_content", f"Only {pa.word_count} words of text (thin content).", Severity.MEDIUM))

        self._scan_leaks(pa, html)

    def _scan_leaks(self, pa: PageAnalysis, html: str) -> None:
        for code, message, severity, pattern in _LEAK_PATTERNS:
            if pattern.search(html):
                pa.leaks.append(Issue(code, message, severity))

    # -- batch --------------------------------------------------------------

    def analyze_many(
        self,
        urls: List[str],
        already_done: Optional[Set[str]] = None,
        on_result: Optional[Callable[[PageAnalysis], None]] = None,
    ) -> List[PageAnalysis]:
        done = set(already_done or set())
        todo = [u for u in urls if canonicalize_url(u) not in done]
        analyses: List[PageAnalysis] = []
        log.info("Analyzing %d pages (%d already done) with concurrency=%d",
                 len(todo), len(done), self.concurrency)

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = {pool.submit(self.analyze_one, url): url for url in todo}
            for fut in as_completed(futures):
                url = futures[fut]
                try:
                    pa = fut.result()
                except Exception as exc:  # never let one page kill the batch
                    log.error("Unexpected error analyzing %s: %s", url, exc)
                    pa = PageAnalysis(url=url, error=str(exc))
                    pa.issues.append(Issue("analyzer_error", str(exc), Severity.HIGH))
                analyses.append(pa)
                if on_result:
                    on_result(pa)
        return analyses


def find_duplicate_groups(
    analyses: List[PageAnalysis], threshold: float = 0.9
) -> List[List[str]]:
    """Group near-duplicate pages by content fingerprint (Jaccard >= threshold)."""
    # Exact duplicates first (same content hash), then near-dupes via shingles.
    groups: List[List[str]] = []
    by_hash: Dict[str, List[str]] = {}
    fingerprinted = [a for a in analyses if a.shingles]
    for a in fingerprinted:
        if a.content_hash:
            by_hash.setdefault(a.content_hash, []).append(a.url)

    assigned: Set[str] = set()
    for urls in by_hash.values():
        if len(urls) > 1:
            groups.append(sorted(urls))
            assigned.update(urls)

    remaining = [a for a in fingerprinted if a.url not in assigned]
    for i, a in enumerate(remaining):
        if a.url in assigned:
            continue
        group = [a.url]
        for b in remaining[i + 1:]:
            if b.url in assigned:
                continue
            if jaccard(a.shingles, b.shingles) >= threshold:
                group.append(b.url)
                assigned.add(b.url)
        if len(group) > 1:
            assigned.add(a.url)
            groups.append(sorted(group))
    return groups
