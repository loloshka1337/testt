"""Core data models for the audit pipeline.

Plain dataclasses are used throughout so that every stage's output is trivially
serialisable to JSON (for the machine-readable report and for checkpointing).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_jsonable(value: Any) -> Any:
    """Recursively convert dataclasses / enums / datetimes into JSON types."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


class Severity(str, Enum):
    """Ranked so that ``max``/``sorted`` behave intuitively."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        return order[self.value]


class Action(str, Enum):
    """Recommended action for a page or cluster."""

    INDEX = "index"          # should be indexed but isn't / is blocked
    DEINDEX = "deindex"      # should be removed from the index
    IMPROVE = "improve"      # indexed but has fixable technical issues
    PROMOTE = "promote"      # healthy & valuable — invest in it
    REVIEW = "review"        # needs a human decision
    KEEP = "keep"            # healthy, no action needed


@dataclass
class Dork:
    """A single generated search query scoped to the target domain."""

    query: str
    category: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return _to_jsonable(self)


@dataclass
class SearchResult:
    """One result returned by a search provider for a given dork."""

    url: str
    title: str = ""
    snippet: str = ""
    position: Optional[int] = None
    provider: str = ""
    query: str = ""
    indexed_date: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return _to_jsonable(self)


@dataclass
class Issue:
    """A technical SEO issue found on a page."""

    code: str
    message: str
    severity: Severity = Severity.MEDIUM

    def to_dict(self) -> Dict[str, Any]:
        return _to_jsonable(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Issue":
        return cls(
            code=data.get("code", ""),
            message=data.get("message", ""),
            severity=Severity(data.get("severity", "medium")),
        )


@dataclass
class PageAnalysis:
    """Everything learned about a single discovered page."""

    url: str
    fetched: bool = False
    status_code: Optional[int] = None
    final_url: Optional[str] = None
    redirect_chain: List[str] = field(default_factory=list)
    title: str = ""
    meta_description: str = ""
    canonical: Optional[str] = None
    canonical_is_self: Optional[bool] = None
    robots_index: bool = True
    robots_follow: bool = True
    x_robots_tag: Optional[str] = None
    robots_txt_allowed: Optional[bool] = None
    word_count: int = 0
    content_hash: Optional[str] = None
    shingles: List[int] = field(default_factory=list)
    content_type: Optional[str] = None
    issues: List[Issue] = field(default_factory=list)
    leaks: List[Issue] = field(default_factory=list)
    error: Optional[str] = None
    fetched_at: str = field(default_factory=_now_iso)

    @property
    def indexable(self) -> bool:
        """Best-effort verdict on whether search engines *can* index the page."""
        if self.status_code is not None and self.status_code >= 400:
            return False
        if not self.robots_index:
            return False
        if self.robots_txt_allowed is False:
            return False
        if self.canonical_is_self is False:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        data = _to_jsonable(self)
        data["indexable"] = self.indexable
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageAnalysis":
        fields = {f.name for f in dataclasses.fields(cls)}
        clean = {k: v for k, v in data.items() if k in fields}
        clean["issues"] = [Issue.from_dict(i) for i in data.get("issues", [])]
        clean["leaks"] = [Issue.from_dict(i) for i in data.get("leaks", [])]
        return cls(**clean)


@dataclass
class Cluster:
    """A group of related pages sharing a page-type / URL pattern."""

    name: str
    page_type: str
    pattern: str
    urls: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = _to_jsonable(self)
        data["size"] = len(self.urls)
        return data


@dataclass
class Recommendation:
    """A prioritised, human-readable recommendation."""

    target: str                 # a URL or a cluster name
    scope: str                  # "page" | "cluster"
    action: Action
    severity: Severity
    title: str
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return _to_jsonable(self)


@dataclass
class AuditReport:
    """The complete, serialisable result of an audit run."""

    domain: str
    generated_at: str = field(default_factory=_now_iso)
    tool_version: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    dorks: List[Dork] = field(default_factory=list)
    results: List[SearchResult] = field(default_factory=list)
    analyses: List[PageAnalysis] = field(default_factory=list)
    clusters: List[Cluster] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return _to_jsonable(self)
