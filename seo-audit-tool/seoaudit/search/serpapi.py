"""SerpApi provider.

SerpApi (https://serpapi.com) is a paid service that legally proxies search
results and handles the engine interaction for you — a ToS-friendly alternative
to scraping. Requires an API key (SEOAUDIT_SERPAPI_KEY).
"""

from __future__ import annotations

from typing import List

import requests

from ..logging_setup import get_logger
from ..models import SearchResult
from .base import ProviderError, SearchProvider

log = get_logger("search.serpapi")

_ENDPOINT = "https://serpapi.com/search.json"


class SerpApiProvider(SearchProvider):
    name = "serpapi"

    def __init__(self, api_key: str, engine: str = "google", timeout: float = 20.0) -> None:
        if not api_key:
            raise ProviderError("SerpApi provider needs an API key (SEOAUDIT_SERPAPI_KEY).")
        self._api_key = api_key
        self._engine = engine
        self._timeout = timeout
        self._session = requests.Session()

    def search(self, query: str, num: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        start = 0
        while len(results) < num:
            params = {
                "api_key": self._api_key,
                "engine": self._engine,
                "q": query,
                "num": min(20, num - len(results)),
                "start": start,
            }
            try:
                resp = self._session.get(_ENDPOINT, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                log.warning("SerpApi request failed for %r: %s", query, exc)
                break
            if resp.status_code >= 400:
                log.warning("SerpApi returned %s for %r: %s",
                            resp.status_code, query, resp.text[:200])
                break
            data = resp.json()
            organic = data.get("organic_results", [])
            if not organic:
                break
            for item in organic:
                results.append(
                    SearchResult(
                        url=item.get("link", ""),
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        position=item.get("position"),
                        provider=self.name,
                        query=query,
                        indexed_date=item.get("date"),
                        raw={"source": item.get("source", "")},
                    )
                )
            start += len(organic)
            if len(organic) < params["num"]:
                break
        return results[:num]
