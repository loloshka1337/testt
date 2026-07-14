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
    ("home", "Главная / корень", re.compile(r"^/?$")),
    ("admin", "Админка / бэк-офис", re.compile(r"/(wp-admin|admin|administrator|backend|dashboard)(/|$)")),
    ("auth", "Вход / личный кабинет", re.compile(r"/(login|signin|sign-in|account|profile|register|signup)(/|$)")),
    ("cart", "Корзина / оформление", re.compile(r"/(cart|basket|checkout|order|payment)(/|$)")),
    ("api", "API-эндпоинты", re.compile(r"/(api|graphql|rest|v\d+)(/|$)")),
    ("search", "Внутренний поиск", re.compile(r"/(search|find)(/|$)|[?&](q|s|query|search)=")),
    ("blog", "Блог / статьи", re.compile(r"/(blog|news|article|articles|post|posts|story|stories)(/|$)")),
    ("product", "Товары", re.compile(r"/(product|products|item|shop|store|p)(/|$)")),
    ("category", "Категории / листинги", re.compile(r"/(category|categories|collection|collections|tag|tags|topic)(/|$)")),
    ("author", "Авторы / пользователи", re.compile(r"/(author|user|member|team)(/|$)")),
    ("media", "Медиа / документы", re.compile(r"\.(pdf|docx?|xlsx?|pptx?|csv|zip|jpg|jpeg|png|gif|svg|mp4)$")),
    ("feed", "Фиды / карты сайта", re.compile(r"/(feed|rss|atom|sitemap[^/]*\.xml|sitemap)(/|$)|\.rss$")),
]

_PARAM_RE = re.compile(r"[?&]")


class Clusterer:
    def __init__(self, seed_paths: Optional[List[str]] = None) -> None:
        self.seed_rules = []
        for sp in seed_paths or []:
            slug = sp.strip("/ ")
            if slug:
                self.seed_rules.append(
                    (f"seed:{slug}", f"Раздел: /{slug}", re.compile(rf"/{re.escape(slug)}(/|$)"))
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
            return "parameterised", "URL с параметрами"
        return "content", "Прочие контентные страницы"

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
                title=f"Объединить {len(group)} почти дублирующихся страниц",
                detail=("Эти страницы содержат почти идентичный контент и конкурируют между собой. "
                        "Выберите каноническую версию и добавьте rel=canonical / редирект для остальных:\n  - "
                        + "\n  - ".join(group)),
            ))

        # Паттерн тонкого контента на уровне кластера.
        for c in clusters:
            thin = [u for u in c.urls
                    if by_url.get(u) and any(i.code == "thin_content" for i in by_url[u].issues)]
            if len(thin) >= 3:
                recs.append(Recommendation(
                    target=c.name,
                    scope="cluster",
                    action=Action.IMPROVE,
                    severity=Severity.MEDIUM,
                    title=f"{len(thin)} тонких страниц в разделе «{c.name}»",
                    detail=("В этом разделе много страниц с очень малым объёмом текста — их могут счесть "
                            "низкокачественными. Расширьте контент либо объедините/закройте в noindex."),
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
                title="Раскрыта чувствительная информация",
                detail=("Похоже, страница раскрывает чувствительные данные ("
                        + ", ".join(sorted({i.code for i in a.leaks}))
                        + "). Уберите контент, защитите ресурс и запросите удаление "
                          "из индекса."),
            ))
            return recs  # утекающую страницу нужно убрать — это приоритетное действие

        # 2. Нерабочая, но проиндексированная.
        if a.status_code and a.status_code >= 400:
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.DEINDEX,
                severity=Severity.HIGH,
                title=f"Проиндексированная страница возвращает {a.status_code}",
                detail="Нерабочая страница доступна в поиске. Почините её либо верните 410 / редирект.",
            ))
            return recs

        # 3. Типы страниц, которые не должны индексироваться, но индексируемы.
        if page_type in _SHOULD_NOT_INDEX and a.indexable:
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.DEINDEX,
                severity=Severity.MEDIUM,
                title=f"Служебная страница типа «{page_type}» индексируема",
                detail=("Такие служебные страницы редко нужны в индексе. Добавьте noindex или "
                        "закройте в robots.txt, чтобы сберечь краулинговый бюджет и не плодить малоценные результаты."),
            ))

        # 4. Ценная страница, закрытая от индексации.
        if not a.indexable and page_type not in _SHOULD_NOT_INDEX:
            reason = []
            if not a.robots_index:
                reason.append("директива noindex")
            if a.robots_txt_allowed is False:
                reason.append("запрет в robots.txt")
            if a.canonical_is_self is False:
                reason.append("canonical ведёт на другую страницу")
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.INDEX,
                severity=Severity.HIGH,
                title="Контентная страница закрыта от индексации",
                detail=("Похоже, эту страницу стоило бы находить в поиске, но сейчас она не индексируема ("
                        + ", ".join(reason or ["причина неизвестна"]) + "). Уберите блокировку, если она должна ранжироваться."),
            ))
            return recs

        # 5. Исправимые on-page проблемы.
        fixable = [i for i in a.issues
                   if i.code in {"missing_title", "missing_meta_description", "thin_content",
                                 "long_title", "redirect_chain", "no_https", "multiple_h1",
                                 "missing_h1", "missing_canonical"}]
        if fixable:
            worst = max(fixable, key=lambda i: i.severity.rank)
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.IMPROVE,
                severity=worst.severity,
                title=f"On-page проблем к исправлению: {len(fixable)}",
                detail="; ".join(f"{i.code}: {i.message}" for i in fixable),
            ))
            return recs

        # 6. Здоровая и ценная -> продвигать или оставить.
        if a.indexable and a.word_count >= 300 and page_type in {"blog", "product", "content", "category"}:
            recs.append(Recommendation(
                target=a.url, scope="page", action=Action.PROMOTE,
                severity=Severity.INFO,
                title="Здоровая страница — кандидат на продвижение",
                detail=("Технически корректна и наполнена контентом. Рассмотрите внутренние ссылки, "
                        "обновление контента или внешние ссылки для роста видимости."),
            ))
        return recs
