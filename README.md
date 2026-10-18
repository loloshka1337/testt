# seoaudit

«Белый» инструмент SEO-аудита и мониторинга видимости в поиске для **одного домена**
(Python). Работает только с сайтами, которыми вы владеете или на аудит которых есть
разрешение: без флага `--i-am-authorized` аудит не запускается.

**EN:** White-hat, single-domain SEO audit & search-visibility monitoring tool
(Python ≥ 3.9). It generates `site:`-scoped search queries, collects results via
official APIs (Google Programmable Search, SerpApi) or an offline JSON export,
analyses in-scope pages and writes prioritised HTML/JSON (optional PDF) reports.

Полный проект находится в каталоге [`seo-audit-tool/`](seo-audit-tool/) — см. его
[README](seo-audit-tool/README.md) с подробным описанием возможностей, установки и
использования.

## Что внутри

- `seo-audit-tool/seoaudit/` — Python-пакет `seoaudit` (v0.1.0):
  генерация запросов (`dorks.py`), сбор и дедупликация результатов (`collector.py`),
  анализ страниц (`analyzer.py`), кластеризация (`cluster.py`), рекомендации
  (`insights.py`), конвейер с возобновлением по чекпоинту (`pipeline.py`, `state.py`),
  вежливый HTTP-клиент с учётом `robots.txt` и ограничением частоты
  (`http_client.py`, `ratelimit.py`).
- `seoaudit/search/` — провайдеры поиска: `manual` (офлайн JSON, по умолчанию),
  `google_cse`, `serpapi`.
- `seoaudit/report/` — отчёты JSON и HTML (Jinja2), PDF — опционально (WeasyPrint).
- `seoaudit/web/` — локальный веб-интерфейс на Flask.
- `seo-audit-tool/tests/` — офлайн-тесты pytest; `examples/` — пример конфига и
  результатов.

## Быстрый старт

```bash
cd seo-audit-tool
pip install -r requirements.txt          # или: pip install -e ".[web,dev]"
python -m seoaudit audit example.com \
  --provider manual --manual-results examples/sample_results.json \
  --i-am-authorized
```

Команды CLI (`python -m seoaudit …` или `seoaudit …` после `pip install -e .`):

| Команда | Назначение |
|---|---|
| `audit <domain>` | полный конвейер: запросы → сбор → анализ → отчёт |
| `dorks <domain>` | только сгенерировать и вывести поисковые запросы (`--json`) |
| `web` | локальный веб-интерфейс (по умолчанию `http://127.0.0.1:8000`) |

Ключи API для живого поиска берутся из переменных окружения
`SEOAUDIT_GOOGLE_API_KEY`, `SEOAUDIT_GOOGLE_CSE_ID`, `SEOAUDIT_SERPAPI_KEY`
(или из JSON-конфига, `--config`).

## Тесты

```bash
cd seo-audit-tool
pip install -r requirements.txt pytest
python -m pytest -q
```

Тесты запускаются и в CI — `.github/workflows/python-tests.yml` (Python 3.9 / 3.11 / 3.12).

> Примечание: репозиторий изначально был форком jadx (Dex → Java). Код
> декомпилятора удалён; сейчас здесь только SEO-инструмент. История сохранена в git.

## Лицензия

Apache-2.0 — см. [LICENSE](LICENSE).
