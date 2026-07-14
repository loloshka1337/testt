"""Search-provider abstraction.

A provider takes a query string and returns :class:`SearchResult` objects. The
pipeline is provider-agnostic; concrete providers wrap official search APIs
(preferred, ToS-friendly) or load previously-exported results from disk.
"""

from __future__ import annotations

import abc
from typing import List

from ..models import SearchResult


class SearchProvider(abc.ABC):
    """Base class for all search back-ends."""

    #: short identifier stored on each result
    name: str = "base"

    @abc.abstractmethod
    def search(self, query: str, num: int) -> List[SearchResult]:
        """Return up to ``num`` results for ``query``.

        Implementations should raise :class:`ProviderError` on unrecoverable
        configuration/credential problems, and return an empty list on merely
        empty result sets.
        """
        raise NotImplementedError


class ProviderError(RuntimeError):
    """Raised when a provider cannot run (missing credentials, bad config…)."""
