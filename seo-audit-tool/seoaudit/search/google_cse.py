"""Google Programmable Search (Custom Search JSON API) provider.

This is the recommended, Terms-of-Service-friendly way to collect results
programmatically. It requires an API key and a Custom Search Engine ID, both
free to create. Docs: https://developers.google.com/custom-search/v1/overview
"""

from __future__ import annotations

from typing import List

import requests

from ..logging_setup import get_logger
from ..models import SearchResult
from .base import ProviderError, SearchProvider

log = get_logger("search.google_cse")

_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


class GoogleCSEProvider(SearchProvider):
    name = "google_cse"

    def __init__(self, api_key: str, cse_id: str, timeout: float = 15.0) -> None:
        if not api_key or not cse_id:
            raise ProviderError(
                "Google CSE provider needs both an API key (SEOAUDIT_GOOGLE_API_KEY) "
                "and a search-engine ID (SEOAUDIT_GOOGLE_CSE_ID)."
            )
        self._api_key = api_key
        self._cse_id = cse_id
        self._timeout = timeout
        self._session = requests.Session()

    def search(self, query: str, num: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        # The API returns max 10 per call; paginate with the `start` param.
        start = 1
        while len(results) < num and start <= 91:
            page_size = min(10, num - len(results))
            params = {
                "key": self._api_key,
                "cx": self._cse_id,
                "q": query,
                "num": page_size,
                "start": start,
            }
            try:
                resp = self._session.get(_ENDPOINT, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                log.warning("Google CSE request failed for %r: %s", query, exc)
                break
            if resp.status_code == 429:
                log.warning("Google CSE quota/rate limit hit; stopping early.")
                break
            if resp.status_code >= 400:
                log.warning("Google CSE returned %s for %r: %s",
                            resp.status_code, query, resp.text[:200])
                break
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break
            for i, item in enumerate(items):
                results.append(
                    SearchResult(
                        url=item.get("link", ""),
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        position=start + i,
                        provider=self.name,
                        query=query,
                        raw={"displayLink": item.get("displayLink", "")},
                    )
                )
            start += page_size
            if len(items) < page_size:
                break
        return results
