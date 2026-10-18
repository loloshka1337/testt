# seoaudit

«Белый» инструмент SEO-аудита и мониторинга видимости в поиске для **одного домена**
(Python). Работает только с сайтами, которыми вы владеете или на аудит которых есть
разрешение.

Полный проект находится в каталоге [`seo-audit-tool/`](seo-audit-tool/) — см. его
[README](seo-audit-tool/README.md) с описанием возможностей, установки и использования.

```bash
cd seo-audit-tool
pip install -r requirements.txt
python -m seoaudit audit example.com \
  --provider manual --manual-results examples/sample_results.json \
  --i-am-authorized
```

Тесты: `cd seo-audit-tool && python -m pytest -q` (запускаются и в CI —
`.github/workflows/python-tests.yml`).

> Примечание: репозиторий изначально был форком jadx (Dex → Java). Код
> декомпилятора удалён; сейчас здесь только SEO-инструмент. История сохранена в git.

## Лицензия

Apache-2.0 — см. [LICENSE](LICENSE).
