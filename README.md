# seoaudit

A white-hat, **single-domain** SEO audit & search-visibility monitoring tool.

The full project lives in [`seo-audit-tool/`](seo-audit-tool/) — see its
[README](seo-audit-tool/README.md) for features, installation and usage.

```bash
cd seo-audit-tool
pip install -r requirements.txt
python -m seoaudit audit example.com \
  --provider manual --manual-results examples/sample_results.json \
  --i-am-authorized
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
