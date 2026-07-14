"""Runtime configuration for an audit run.

Configuration can be supplied programmatically, from a JSON/YAML-ish file, or
from CLI flags. Sensible, *polite* defaults are chosen so the tool behaves as a
good web citizen out of the box.
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# A small pool of realistic, current desktop User-Agent strings. Rotation here
# is about spreading load and presenting an honest browser identity — not about
# defeating anti-abuse systems. Keep it modest.
DEFAULT_USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


@dataclass
class Config:
    """All knobs for a single audit run."""

    # --- Target ------------------------------------------------------------
    domain: str = ""
    include_subdomains: bool = True

    # --- Search collection -------------------------------------------------
    provider: str = "manual"           # manual | google_cse | serpapi
    max_dorks: int = 60
    results_per_dork: int = 20
    dork_categories: Optional[List[str]] = None  # None => all categories
    keywords: List[str] = field(default_factory=list)
    seed_paths: List[str] = field(default_factory=list)  # known page types
    # Provider credentials (never logged). Read from env if unset.
    google_api_key: Optional[str] = None
    google_cse_id: Optional[str] = None
    serpapi_key: Optional[str] = None
    manual_results_path: Optional[str] = None  # offline results for provider=manual

    # --- Page analysis / crawling politeness -------------------------------
    analyze_pages: bool = True
    max_pages: int = 300
    request_timeout: float = 15.0
    respect_robots_txt: bool = True
    rate_limit_rps: float = 1.0        # requests/second to the target domain
    jitter: float = 0.4               # +/- fraction randomly added to delays
    max_retries: int = 2
    concurrency: int = 4
    rotate_user_agents: bool = True
    user_agents: List[str] = field(default_factory=lambda: list(DEFAULT_USER_AGENTS))
    contact_email: Optional[str] = None  # advertised in a From: header if set

    # --- Duplicate detection ----------------------------------------------
    duplicate_similarity: float = 0.9  # Jaccard threshold on content shingles

    # --- Output ------------------------------------------------------------
    output_dir: str = "seo-audit-output"
    report_formats: List[str] = field(default_factory=lambda: ["json", "html"])
    state_file: Optional[str] = None   # defaults to <output_dir>/state.json

    # --- Safety ------------------------------------------------------------
    # Explicit acknowledgement that the operator is authorised to audit the
    # target. Enforced by the CLI/pipeline; keeps the tool white-hat.
    authorized: bool = False

    def __post_init__(self) -> None:
        # Fall back to environment variables for secrets so they never need to
        # live in a config file.
        self.google_api_key = self.google_api_key or os.getenv("SEOAUDIT_GOOGLE_API_KEY")
        self.google_cse_id = self.google_cse_id or os.getenv("SEOAUDIT_GOOGLE_CSE_ID")
        self.serpapi_key = self.serpapi_key or os.getenv("SEOAUDIT_SERPAPI_KEY")
        if self.state_file is None:
            self.state_file = os.path.join(self.output_dir, "state.json")
        # Clamp obviously unsafe values to keep the tool polite.
        self.rate_limit_rps = max(0.05, min(self.rate_limit_rps, 10.0))
        self.concurrency = max(1, min(self.concurrency, 16))
        self.jitter = max(0.0, min(self.jitter, 1.0))

    # -- (de)serialisation --------------------------------------------------

    def redacted_dict(self) -> Dict[str, Any]:
        """Config as a dict with secrets removed — safe to log / embed in reports."""
        data = dataclasses.asdict(self)
        for secret in ("google_api_key", "google_cse_id", "serpapi_key"):
            if data.get(secret):
                data[secret] = "***set***"
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        fields = {f.name for f in dataclasses.fields(cls)}
        clean = {k: v for k, v in data.items() if k in fields}
        return cls(**clean)

    @classmethod
    def from_file(cls, path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))
