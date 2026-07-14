"""Collect and parse search results for a set of dorks.

The collector runs each dork through the configured provider, drops anything
that isn't in-scope for the target domain, de-duplicates by canonical URL
(keeping the richest record), and reports progress via an optional callback so
long runs can be checkpointed.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional

from .domain import DomainScope, canonicalize_url
from .logging_setup import get_logger
from .models import Dork, SearchResult
from .search.base import SearchProvider

log = get_logger("collector")

ProgressCb = Callable[[int, int, Dork], None]


class Collector:
    def __init__(
        self,
        provider: SearchProvider,
        scope: DomainScope,
        results_per_dork: int = 20,
    ) -> None:
        self.provider = provider
        self.scope = scope
        self.results_per_dork = results_per_dork

    def _merge(self, existing: SearchResult, new: SearchResult) -> SearchResult:
        """Keep the more informative fields when the same URL reappears."""
        if not existing.title and new.title:
            existing.title = new.title
        if not existing.snippet and new.snippet:
            existing.snippet = new.snippet
        if not existing.indexed_date and new.indexed_date:
            existing.indexed_date = new.indexed_date
        return existing

    def collect(
        self,
        dorks: Iterable[Dork],
        seed: Optional[List[SearchResult]] = None,
        done_queries: Optional[set] = None,
        on_progress: Optional[ProgressCb] = None,
    ) -> List[SearchResult]:
        by_url: Dict[str, SearchResult] = {}
        for res in seed or []:
            key = canonicalize_url(res.url)
            if key:
                by_url[key] = res

        dorks = list(dorks)
        done = set(done_queries or set())
        total = len(dorks)
        dropped_off_scope = 0

        for i, dork in enumerate(dorks, start=1):
            if dork.query in done:
                log.debug("Skipping already-collected dork: %s", dork.query)
                if on_progress:
                    on_progress(i, total, dork)
                continue
            log.info("[%d/%d] Searching: %s", i, total, dork.query)
            try:
                results = self.provider.search(dork.query, self.results_per_dork)
            except Exception as exc:  # provider issues shouldn't kill the run
                log.error("Provider error for %r: %s", dork.query, exc)
                results = []
            for res in results:
                if not self.scope.url_in_scope(res.url):
                    dropped_off_scope += 1
                    continue
                key = canonicalize_url(res.url)
                if not key:
                    continue
                if key in by_url:
                    self._merge(by_url[key], res)
                else:
                    by_url[key] = res
            done.add(dork.query)
            if on_progress:
                on_progress(i, total, dork)

        if dropped_off_scope:
            log.info("Dropped %d off-scope results (not on %s).",
                     dropped_off_scope, self.scope.registrable)
        log.info("Collected %d unique in-scope URLs.", len(by_url))
        return list(by_url.values())
