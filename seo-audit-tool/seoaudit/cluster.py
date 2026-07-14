"""Clustering, prioritisation and recommendation generation.

Two responsibilities:

* :class:`Clusterer` groups discovered pages by page-type (using URL structure
  plus any operator-supplied seed paths).
* :class:`RecommendationEngine` turns the per-page analyses, duplicate groups
  and clusters into a prioritised, human-readable action list — telling the
  owner what to index, de-index, improve, or actively promote.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .models import Action, Cluster, PageAnalysis, Recommendation, Severity

# Ordered rules: first match wins. Each is (page_type, label, url-regex).
_TYPE_RULES = [
    ("home", "Home / root", re.compile(r"^/?$")),
    ("admin", "Admin / back-office", re.compile(r"/(wp-admin|admin|administrator|backend|dashboard)(/|$)")),
    ("auth", "Login / account", re.compile(r"/(login|signin|sign-in|account|profile|register|signup)(/|$)")),
    ("cart", "Cart / checkout", re.compile(r"/(cart|basket|checkout|order|payment)(/|$)")),
    ("api", "API endpoints", re.compile(r"/(api|graphql|rest|v\d+)(/|$)")),
    ("search", "Internal search results", re.compile(r"/(search|find)(/|$)|[?&](q|s|query|search)=")),
    ("blog", "Blog / articles", re.compile(r"/(blog|news|article|articles|post|posts|story|stories)(/|$)")),
    ("product", "Products", re.compile(r"/(product|products|item|shop|store|p)(/|$)")),
    ("category", "Categories / listings", re.compile(r"/(category|categories|collection|collections|tag|tags|topic)(/|$)")),
    ("author", "Author / user pages", re.compile(r"/(author|user|member|team)(/|$)")),
    ("media", "Media / documents", re.compile(r"\.(pdf|docx?|xlsx?|pptx?|csv|zip|jpg|jpeg|png|gif|svg|mp4)$")),
    ("feed", "Feeds / sitemaps", re.compile(r"/(feed|rss|atom|sitemap[^/]*\.xml|sitemap)(/|$)|\.rss$")),
]

_PARAM_RE = re.compile(r"[?&]")


class Clusterer:
    def __init__(self, seed_paths: Optional[List[str]] = None) -> None:
        self.seed_rules = []
        for sp in seed_paths or []:
            slug = sp.strip("/ ")
            if slug:
                self.seed_rules.append(
                    (f"seed:{slug}", f"Section: /{slug}", re.compile(rf"/{re.escape(slug)}(/|$)"))
                )

    def _classify(self, url: str) -> tuple:
        path = urlparse(url).path or "/"
        for page_type, label, rx in self.seed_rules:
            if rx.search(path):
                return page_type, label
        for page_type, label, rx in _TYPE_RULES:
            if rx.search(path) or rx.search(url):
                return page_type, label
        if _PARAM_RE.search(url):
            return "parameterised", "Parameterised URLs"
        return "content", "General content pages"

    def cluster(self, analyses: List[PageAnalysis]) -> List[Cluster]:
        buckets: Dict[str, Cluster] = {}
        for a in analyses:
            page_type, label = self._classify(a.final_url or a.url)
            cluster = buckets.get(page_type)
            if cluster is None:
                pattern = self.seed_pattern(page_type)
                cluster = Cluster(name=label, page_type=page_type, pattern=pattern)
                buckets[page_type] = cluster
            cluster.urls.append(a.url)
        # Largest clusters first for report readability.
        return sorted(buckets.values(), key=lambda c: len(c.urls), reverse=True)

    @staticmethod
    def seed_pattern(page_type: str) -> str:
        if page_type.startswith("seed:"):
            return f"/{page_type.split(':', 1)[1]}/*"
        return page_type


# Page types that should almost never appear in a public search index.
_SHOULD_NOT_INDEX = {"admin", "auth", "cart", "search", "api"}


class RecommendationEngine:
    def __init__(self, duplicate_groups: Optional[List[List[str]]] = None) -> None:
        self.duplicate_groups = duplicate_groups or []

    def _page_type_of(self, url: str, clusters: List[Cluster]) -> str:
        for c in clusters:
            if url in c.urls:
                return c.page_type
        return "content"

    def generate(
        self, analyses: List[PageAnalysis], clusters: List[Cluster]
    ) -> List[Recommendation]:
        recs: List[Recommendation] = []
        by_url = {a.url: a for a in analyses}

        for a in analyses:
            page_type = self._page_type_of(a.url, clusters)
            recs.extend(self._page_recs(a, page_type))

        # Duplicate-content consolidation.
        for group in self.duplicate_groups:
            recs.append(Recommendation(
                target=group[0],
                scope="cluster",
                action=Action.IMPROVE,
                severity=Severity.MEDIUM,
                title=f"Consolidate {len(group)} near-duplicate pages",
                detail=("These pages share near-identical content and compete with each other. "
                        "Pick a canonical version and add rel=canonical / redirect the rest:\n  - "
                        + "\n  - ".join(group)),
            ))

        # Cluster-level thin-content pattern.
        for c in clusters:
            thin = [u for u in c.urls
                    if by_url.get(u) and any(i.code == "thin_content" for i in by_url[u].issues)]
            if len(thin) >= 3:
                recs.append(Recommendation(
                    target=c.name,
                    scope="cluster",
                    action=Action.IMPROVE,
                    severity=Severity.MEDIUM,
                    title=f"{len(thin)} thin pages in '{c.name}'",
                    detail=("Multiple pages in this section have very little text and may be "
                            "seen as low-quality. Expand them or consolidate/noindex."),
                ))

        # Sort: highest severity first, then de-index/index actions to the top.
        action_priority = {
            Action.DEINDEX: 0, Action.INDEX: 1, Action.IMPROVE: 2,
            Action.REVIEW: 3, Action.PROMOTE: 4, Action.KEEP: 5,
        }
        recs.sort(key=lambda r: (-r.severity.rank, action_priority.get(r.action, 9)))
        return recs

    def _page_recs(self, a: PageAnalysis, page_type: str) -> List[Recommendation]:
        recs: List[Recommendation] = []

        # 1. Exposure leaks — highest priority.
        if a.leaks:
            worst = max(a.leaks, key=lambda i: i.severity.rank)
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.DEINDEX,
                severity=worst.severity,
                title="Sensitive information exposed",
                detail=("This page appears to leak sensitive data ("
                        + ", ".join(sorted({i.code for i in a.leaks}))
                        + "). Remove the content, secure the resource, and request removal "
                          "from the index."),
            ))
            return recs  # a leaking page should be removed — that's the priority action

        # 2. Broken but indexed.
        if a.status_code and a.status_code >= 400:
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.DEINDEX,
                severity=Severity.HIGH,
                title=f"Indexed page returns {a.status_code}",
                detail="A broken page is discoverable in search. Fix it or return 410/redirect it.",
            ))
            return recs

        # 3. Page types that shouldn't be indexed but are indexable.
        if page_type in _SHOULD_NOT_INDEX and a.indexable:
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.DEINDEX,
                severity=Severity.MEDIUM,
                title=f"'{page_type}' page is indexable",
                detail=("Utility pages like this rarely belong in the index. Add noindex or "
                        "block via robots.txt to protect crawl budget and avoid low-value listings."),
            ))

        # 4. Valuable page blocked from indexing.
        if not a.indexable and page_type not in _SHOULD_NOT_INDEX:
            reason = []
            if not a.robots_index:
                reason.append("noindex directive")
            if a.robots_txt_allowed is False:
                reason.append("robots.txt disallow")
            if a.canonical_is_self is False:
                reason.append("canonical points elsewhere")
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.INDEX,
                severity=Severity.HIGH,
                title="Content page is blocked from indexing",
                detail=("This looks like a page you'd want found, but it's currently not indexable ("
                        + ", ".join(reason or ["unknown"]) + "). Remove the blocker if it should rank."),
            ))
            return recs

        # 5. Fixable on-page issues.
        fixable = [i for i in a.issues
                   if i.code in {"missing_title", "missing_meta_description", "thin_content",
                                 "long_title", "redirect_chain", "no_https", "multiple_h1",
                                 "missing_h1", "missing_canonical"}]
        if fixable:
            worst = max(fixable, key=lambda i: i.severity.rank)
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.IMPROVE,
                severity=worst.severity,
                title=f"{len(fixable)} on-page issue(s) to fix",
                detail="; ".join(f"{i.code}: {i.message}" for i in fixable),
            ))
            return recs

        # 6. Healthy & valuable -> promote or keep.
        if a.indexable and a.word_count >= 300 and page_type in {"blog", "product", "content", "category"}:
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.PROMOTE,
                severity=Severity.INFO,
                title="Healthy page — candidate for promotion",
                detail=("Technically sound and content-rich. Consider internal links, refreshed "
                        "content, or backlinks to grow its visibility."),
            ))
        return recs
