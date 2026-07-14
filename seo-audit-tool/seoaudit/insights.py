"""Этап «insights»: кластеризация + поиск дубликатов + рекомендации.

Эти три шага тесно связаны и всегда выполняются вместе (рекомендации опираются
на кластеры и группы дубликатов), поэтому они объединены в один
автоматизированный этап конвейера. При этом низкоуровневые составляющие
(`Clusterer`, `RecommendationEngine`, `find_duplicate_groups`) остаются
самостоятельными функциями — их можно вызывать по отдельности.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .analyzer import find_duplicate_groups
from .cluster import Clusterer, RecommendationEngine
from .models import Cluster, PageAnalysis, Recommendation


@dataclass
class Insights:
    """Результат этапа анализа: кластеры, дубликаты и рекомендации."""

    clusters: List[Cluster]
    duplicate_groups: List[List[str]]
    recommendations: List[Recommendation]


def build_insights(
    analyses: List[PageAnalysis],
    seed_paths: Optional[List[str]] = None,
    duplicate_similarity: float = 0.9,
) -> Insights:
    """Собрать кластеры, группы дубликатов и рекомендации из анализа страниц."""
    clusters = Clusterer(seed_paths=seed_paths).cluster(analyses)
    duplicate_groups = find_duplicate_groups(analyses, threshold=duplicate_similarity)
    recommendations = RecommendationEngine(
        duplicate_groups=duplicate_groups
    ).generate(analyses, clusters)
    return Insights(
        clusters=clusters,
        duplicate_groups=duplicate_groups,
        recommendations=recommendations,
    )
