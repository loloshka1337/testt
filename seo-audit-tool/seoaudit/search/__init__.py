"""Search providers and a factory that builds the right one from config."""

from __future__ import annotations

from ..config import Config
from .base import ProviderError, SearchProvider
from .google_cse import GoogleCSEProvider
from .manual import ManualProvider
from .serpapi import SerpApiProvider

__all__ = [
    "SearchProvider",
    "ProviderError",
    "GoogleCSEProvider",
    "SerpApiProvider",
    "ManualProvider",
    "build_provider",
    "AVAILABLE_PROVIDERS",
]

AVAILABLE_PROVIDERS = ["manual", "google_cse", "serpapi"]


def build_provider(config: Config) -> SearchProvider:
    """Instantiate the provider named by ``config.provider``."""
    name = (config.provider or "manual").lower()
    if name == "manual":
        return ManualProvider(config.manual_results_path)
    if name == "google_cse":
        return GoogleCSEProvider(
            config.google_api_key, config.google_cse_id, timeout=config.request_timeout
        )
    if name == "serpapi":
        return SerpApiProvider(config.serpapi_key, timeout=config.request_timeout)
    raise ProviderError(
        f"Unknown provider {name!r}. Choose one of: {', '.join(AVAILABLE_PROVIDERS)}."
    )
