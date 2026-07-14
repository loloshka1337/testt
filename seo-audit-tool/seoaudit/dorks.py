"""Intelligent, domain-scoped search-query ("dork") generation.

Every query produced here is anchored with a ``site:`` operator pointing at the
one authorised target domain, so the tool only ever asks a search engine *"what
of MINE is indexed?"*. The generator combines search operators with the site's
own keywords, known page types (seed paths) and file extensions to produce a
diverse, non-repetitive set of queries covering:

* **coverage**   — overall / per-section indexation;
* **page_types** — sectioning by URL path and file type;
* **content**    — title/body keyword presence & thin-content probes;
* **duplication**— parameterised / paginated / print variants;
* **exposure**   — accidental exposure of files an owner would want to find
  (backups, dumps, configs). Scoped to the owner's own site, this is standard
  audit hygiene, not reconnaissance of third parties.

Determinism is preserved (given the same config the same dorks come out, in the
same order) so runs are reproducible and resumable.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .domain import DomainScope
from .models import Dork

# File extensions worth checking for accidental indexing/exposure on one's own
# site. Documents may be legitimately indexed; archives/dumps/configs usually
# should not be.
_DOC_EXTS = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "csv"]
_SENSITIVE_EXTS = ["sql", "bak", "old", "zip", "tar", "gz", "env", "log", "json", "yml", "ini", "conf"]

# Common URL fragments that often indicate distinct page types.
_TYPE_HINTS = [
    "blog", "news", "product", "products", "category", "tag", "author",
    "search", "cart", "checkout", "account", "login", "admin", "api",
    "wp-admin", "wp-content", "feed", "sitemap", "amp", "print",
]

# Query fragments that surface duplicate / low-value variants.
_DUPLICATE_HINTS = [
    "inurl:?", "inurl:&", "inurl:sessionid", "inurl:sort=", "inurl:page=",
    "inurl:utm_", "inurl:replytocom", "inurl:print", "inurl:amp",
]

# Fragments that hint at accidental exposure the *owner* should review.
_EXPOSURE_HINTS = [
    'intitle:"index of"', 'intext:"index of /"', "inurl:backup", "inurl:old",
    "inurl:tmp", "inurl:config", "inurl:.git", "inurl:phpinfo",
    'intext:"sql dump"',
]

ALL_CATEGORIES = ["coverage", "page_types", "content", "duplication", "exposure"]


class DorkGenerator:
    def __init__(
        self,
        scope: DomainScope,
        keywords: Optional[List[str]] = None,
        seed_paths: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> None:
        self.scope = scope
        self.site = scope.site_operator_value
        self.keywords = [k.strip() for k in (keywords or []) if k.strip()]
        self.seed_paths = [p.strip("/ ") for p in (seed_paths or []) if p.strip("/ ")]
        self.categories = categories or list(ALL_CATEGORIES)

    def _site(self) -> str:
        return f"site:{self.site}"

    # -- category builders --------------------------------------------------

    def _coverage(self) -> List[Dork]:
        s = self._site()
        out = [
            Dork(s, "coverage", "Базовый охват: всё, что поисковик проиндексировал по сайту."),
            Dork(f"{s} -inurl:https", "coverage",
                 "Найти страницы, всё ещё индексируемые по обычному HTTP."),
            Dork(f"{s} inurl:https", "coverage", "Проиндексированные страницы только по HTTPS."),
        ]
        if self.scope.include_subdomains:
            out.append(Dork(f"{s} -inurl:www", "coverage",
                            "Проиндексированные страницы на поддоменах / не-www."))
        return out

    def _page_types(self) -> List[Dork]:
        s = self._site()
        out: List[Dork] = []
        hints = list(dict.fromkeys(self.seed_paths + _TYPE_HINTS))
        for hint in hints:
            out.append(Dork(f"{s} inurl:{hint}", "page_types",
                            f"Перечислить проиндексированные страницы раздела «{hint}»."))
        for ext in _DOC_EXTS:
            out.append(Dork(f"{s} filetype:{ext}", "page_types",
                            f"Проиндексированные документы {ext.upper()}."))
        return out

    def _content(self) -> List[Dork]:
        s = self._site()
        out: List[Dork] = []
        for kw in self.keywords:
            phrase = f'"{kw}"' if " " in kw else kw
            out.append(Dork(f"{s} intitle:{phrase}", "content",
                            f"Страницы, чей заголовок нацелен на «{kw}»."))
            out.append(Dork(f"{s} intext:{phrase} -intitle:{phrase}", "content",
                            f"Страницы с «{kw}» в тексте, но не в заголовке (упущение оптимизации)."))
        # Проверки на «тонкий» / заглушечный контент.
        for probe in ['intitle:"untitled"', 'intext:"lorem ipsum"',
                      'intitle:"page not found"', 'intext:"coming soon"']:
            out.append(Dork(f"{s} {probe}", "content",
                            "Поиск тонкого/заглушечного/ошибочного контента, который не должен ранжироваться."))
        return out

    def _duplication(self) -> List[Dork]:
        s = self._site()
        return [
            Dork(f"{s} {hint}", "duplication",
                 "Найти параметрические/дублирующиеся варианты URL, размывающие краулинговый бюджет.")
            for hint in _DUPLICATE_HINTS
        ]

    def _exposure(self) -> List[Dork]:
        s = self._site()
        out = [
            Dork(f"{s} {hint}", "exposure",
                 "Проверка гигиены владельцем: найти случайно проиндексированные чувствительные артефакты.")
            for hint in _EXPOSURE_HINTS
        ]
        for ext in _SENSITIVE_EXTS:
            out.append(Dork(f"{s} filetype:{ext}", "exposure",
                            f"Проверить проиндексированные файлы {ext}, которые вряд ли должны быть публичными."))
        return out

    # -- public API ---------------------------------------------------------

    def generate(self, limit: Optional[int] = None) -> List[Dork]:
        builders: Dict[str, "callable"] = {
            "coverage": self._coverage,
            "page_types": self._page_types,
            "content": self._content,
            "duplication": self._duplication,
            "exposure": self._exposure,
        }
        # Interleave categories round-robin so a low limit still yields variety.
        per_cat: Dict[str, List[Dork]] = {
            cat: builders[cat]() for cat in self.categories if cat in builders
        }
        ordered: List[Dork] = []
        seen = set()
        idx = 0
        while any(idx < len(v) for v in per_cat.values()):
            for cat in self.categories:
                lst = per_cat.get(cat, [])
                if idx < len(lst):
                    dork = lst[idx]
                    if dork.query not in seen:
                        seen.add(dork.query)
                        ordered.append(dork)
            idx += 1
        if limit is not None:
            ordered = ordered[:limit]
        return ordered
