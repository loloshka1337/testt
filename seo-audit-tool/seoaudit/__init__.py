"""seoaudit — a white-hat SEO audit & search-visibility monitoring tool.

The package analyses how a *single, authorised* domain is represented in
search engines: it generates scoped search queries ("dorks"), collects and
parses results, deeply analyses the discovered pages for technical SEO
problems, then clusters the pages and produces prioritised recommendations
with human-friendly reports.

Design principles baked into the code:

* **Single-domain scoping.** Every collected result and every fetched page
  is validated against the one target domain. Anything off-domain is dropped.
* **White-hat by default.** Crawling of the owned domain respects
  ``robots.txt``; requests are rate-limited with jitter; concurrency and
  totals are capped. Search collection prefers official APIs.
* **Resumable & auditable.** Long runs checkpoint their state so they can be
  interrupted and resumed, and every action is logged.
"""

__all__ = [
    "__version__",
    "run_audit",
    "generate_dorks",
    "build_insights",
]
__version__ = "0.1.0"


def run_audit(config, resume: bool = True):
    """Запустить полный аудит по конфигурации и вернуть :class:`AuditReport`.

    Фасад над :class:`~seoaudit.pipeline.AuditPipeline` — единая точка входа для
    сквозного (автоматического) сценария: генерация → сбор → анализ →
    insights → отчёты.
    """
    from .pipeline import AuditPipeline

    return AuditPipeline(config).run(resume=resume)


def generate_dorks(domain, keywords=None, seed_paths=None,
                   categories=None, include_subdomains=True, limit=None):
    """Сгенерировать поисковые запросы для домена (отдельная функция)."""
    from .domain import DomainScope
    from .dorks import DorkGenerator

    scope = DomainScope(domain, include_subdomains=include_subdomains)
    return DorkGenerator(
        scope, keywords=keywords, seed_paths=seed_paths, categories=categories
    ).generate(limit=limit)


def build_insights(analyses, seed_paths=None, duplicate_similarity=0.9):
    """Собрать кластеры + дубликаты + рекомендации (отдельный этап)."""
    from .insights import build_insights as _build

    return _build(analyses, seed_paths=seed_paths,
                  duplicate_similarity=duplicate_similarity)
