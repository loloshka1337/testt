"""Offline / manual results provider.

Lets an operator feed the pipeline results they exported themselves — e.g. from
Google Search Console's "Pages" export, a Bing Webmaster export, or results
copied by hand — with no live search API involved at all. This is the safest,
fully-ToS-clean way to run the tool, and it's what the test-suite and examples
use.

Accepted JSON shapes (auto-detected):

1. ``{"query string": [ {result}, ... ], ...}`` — results grouped per query.
2. ``[ {result}, ... ]`` — a flat list; each result may carry a ``"query"``
   field. When a queried lookup finds no query-specific matches, the whole list
   is returned (deduplicated downstream).

A ``{result}`` is ``{"url": ..., "title": ..., "snippet": ...,
"position": ..., "indexed_date": ...}`` (only ``url`` is required).
"""

from __future__ import annotations

import json
from typing import Dict, List

from ..logging_setup import get_logger
from ..models import SearchResult
from .base import ProviderError, SearchProvider

log = get_logger("search.manual")


class ManualProvider(SearchProvider):
    name = "manual"

    def __init__(self, results_path: str) -> None:
        if not results_path:
            raise ProviderError(
                "Manual provider needs a results file (config.manual_results_path)."
            )
        try:
            with open(results_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Could not read manual results {results_path!r}: {exc}")

        self._by_query: Dict[str, List[dict]] = {}
        self._flat: List[dict] = []
        if isinstance(data, dict):
            self._by_query = {str(k): list(v) for k, v in data.items()}
            for items in self._by_query.values():
                self._flat.extend(items)
        elif isinstance(data, list):
            self._flat = list(data)
        else:
            raise ProviderError("Manual results file must be a JSON object or array.")
        log.info("Loaded %d manual results (%d queries) from %s",
                 len(self._flat), len(self._by_query), results_path)

    @staticmethod
    def _mk(item: dict, query: str) -> SearchResult:
        return SearchResult(
            url=item.get("url", ""),
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
            position=item.get("position"),
            provider="manual",
            query=item.get("query", query),
            indexed_date=item.get("indexed_date"),
            raw={k: v for k, v in item.items()
                 if k not in {"url", "title", "snippet", "position", "query", "indexed_date"}},
        )

    def search(self, query: str, num: int) -> List[SearchResult]:
        items = self._by_query.get(query)
        if items is None:
            # Fall back to any flat items tagged with this query…
            items = [it for it in self._flat if it.get("query") == query]
        if not items:
            # …otherwise return the whole corpus (deduped later by the collector).
            items = self._flat
        return [self._mk(it, query) for it in items[:num] if it.get("url")]
