# seoaudit

«Белый» инструмент SEO-аудита и мониторинга видимости в поиске для **одного домена**.

Полный проект находится в каталоге [`seo-audit-tool/`](seo-audit-tool/) — см. его
[README](seo-audit-tool/README.md) с описанием возможностей, установки и использования.

```bash
cd seo-audit-tool
pip install -r requirements.txt
python -m seoaudit audit example.com \
  --provider manual --manual-results examples/sample_results.json \
  --i-am-authorized
```

## Лицензия

Apache-2.0 — см. [LICENSE](LICENSE).
