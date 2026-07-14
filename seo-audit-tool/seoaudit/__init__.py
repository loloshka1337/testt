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

__all__ = ["__version__"]
__version__ = "0.1.0"
