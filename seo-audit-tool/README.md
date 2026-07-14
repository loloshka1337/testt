# seoaudit — SEO visibility audit & monitoring

A white-hat, **single-domain** tool for analysing how a site you own (or are
authorised to audit) is represented in search engines. It generates scoped
search queries, collects and parses the results, deeply analyses the discovered
pages for technical SEO problems, clusters them by type, and produces
prioritised recommendations with clean HTML/JSON (optionally PDF) reports.

> ⚠️ **Authorised use only.** Every stage is locked to one target domain and the
> tool refuses to run without an explicit authorisation flag. Use it exclusively
> on properties you own or have written permission to audit.

---

## Why this design is "white-hat"

These safeguards are enforced in code, not just documentation:

| Safeguard | Where |
|---|---|
| **Single-domain scoping** — every collected result and fetched page is validated against the one target domain; anything off-domain is dropped | `domain.py`, `collector.py`, `analyzer.py` |
| **Explicit authorisation gate** — the pipeline raises unless `authorized=True` / `--i-am-authorized` | `pipeline.py`, `cli.py` |
| **`robots.txt` respected** when crawling the owned domain | `http_client.py` |
| **Polite rate limiting** with jitter, bounded concurrency, and hard page caps | `ratelimit.py`, `config.py` |
| **API-first result collection** (Google Programmable Search / SerpApi / offline export) instead of scraping search engines | `search/` |
| **Secrets never logged or embedded** in reports | `config.py` |

User-Agent rotation and request pacing are here to spread load and present an
honest browser identity to *your own* server — not to defeat anti-abuse systems.

---

## The four modules from the spec

1. **Intelligent query ("dork") generation** — `dorks.py` builds a diverse,
   deduplicated, reproducible set of `site:`-anchored queries across five
   categories: `coverage`, `page_types`, `content`, `duplication`, `exposure`.
   Categories are interleaved so even a small `--max-dorks` yields variety.
2. **Collection & parsing** — `collector.py` runs each query through a pluggable
   provider (`search/`), keeping URL, title, snippet, position and index date,
   then scope-filters and de-duplicates by canonical URL.
3. **Deep page analysis** — `analyzer.py` fetches each in-scope page and checks
   HTTP status & redirect chains, `meta robots` / `X-Robots-Tag`, canonical
   targets, thin content, on-page basics, near-duplicate fingerprints, and
   scans for accidental information leaks.
4. **Clustering, prioritisation & recommendations** — `cluster.py` groups pages
   by type and emits a ranked action list: what to **index**, **deindex**,
   **improve**, or **promote**.

Plus: HTML + JSON (+ optional PDF) reports, a CLI, a local web UI, full logging,
and resumable checkpointing so long runs survive interruption.

---

## Install

```bash
cd seo-audit-tool
pip install -r requirements.txt      # or: pip install .
```

Requires Python 3.9+. Core deps: `requests`, `beautifulsoup4`, `jinja2`.
The web UI additionally needs `flask`; PDF output optionally needs `weasyprint`.

---

## Quick start (fully offline, no API keys)

The `manual` provider reads results you exported yourself (e.g. from Google
Search Console's Pages export) — the safest, 100% ToS-clean way to run it.

```bash
python -m seoaudit audit example.com \
  --provider manual \
  --manual-results examples/sample_results.json \
  --keywords "example,docs" \
  --seed-paths "blog,docs" \
  --i-am-authorized
```

Just preview the generated queries:

```bash
python -m seoaudit dorks example.com --keywords "running shoes" --seed-paths blog,shop
```

Launch the web interface:

```bash
python -m seoaudit web           # then open http://127.0.0.1:8000
```

Reports land in `--output` (default `seo-audit-output/`): `report.html`,
`report.json`, plus `audit.log` and a `state.json` checkpoint.

---

## Live search collection (optional)

Prefer an official API — it's reliable and Terms-of-Service-friendly:

**Google Programmable Search (Custom Search JSON API)**
```bash
export SEOAUDIT_GOOGLE_API_KEY=...      # from Google Cloud
export SEOAUDIT_GOOGLE_CSE_ID=...       # from programmablesearchengine.google.com
python -m seoaudit audit example.com --provider google_cse --i-am-authorized
```

**SerpApi**
```bash
export SEOAUDIT_SERPAPI_KEY=...
python -m seoaudit audit example.com --provider serpapi --i-am-authorized
```

Credentials are read from the environment and never written to logs or reports.

---

## Configuration file

Anything settable via flags can live in a JSON config (see
`examples/config.example.json`). CLI flags override file values.

```bash
python -m seoaudit audit example.com --config examples/config.example.json --i-am-authorized
```

Key options: `rate_limit_rps`, `concurrency`, `max_pages`, `max_dorks`,
`respect_robots_txt`, `include_subdomains`, `duplicate_similarity`,
`report_formats`, `contact_email`.

---

## Interrupt & resume

State is checkpointed atomically after each stage and periodically during
analysis. Press **Ctrl-C** to stop gracefully; re-run the same command to resume
from where it left off (or add `--no-resume` to start fresh).

---

## Reports

- **`report.json`** — complete machine-readable output (dorks, results, per-page
  analyses, clusters, recommendations, stats).
- **`report.html`** — a self-contained, dark/light-aware dashboard: summary
  tiles, prioritised recommendations, clusters, common issues, and an
  expandable per-page breakdown.
- **`report.pdf`** — written if `weasyprint` is installed (`--formats pdf`);
  otherwise open the HTML report and "Print to PDF".

---

## Architecture

```
seoaudit/
├── cli.py            # argparse CLI (audit | dorks | web)
├── pipeline.py       # orchestrates stages + resume + interruption
├── config.py         # Config dataclass, polite defaults, secret redaction
├── domain.py         # single-domain scoping (the safety core)
├── dorks.py          # query generation
├── collector.py      # run queries → scope-filter → dedupe
├── analyzer.py       # fetch + parse + issue/leak/duplicate detection
├── cluster.py        # clustering + recommendation engine
├── http_client.py    # polite HTTP client (robots, UA rotation, retries)
├── ratelimit.py      # token-bucket rate limiter
├── state.py          # resumable checkpoint
├── report/           # JSON + HTML (+ PDF) writers & template
├── search/           # provider interface + google_cse / serpapi / manual
└── web/              # Flask control panel
```

---

## Development

```bash
pip install pytest
python -m pytest -q
```

The suite runs fully offline (no network, no API keys), covering domain scoping,
dork generation, collection/dedupe, page analysis (via a fake HTTP client),
duplicate detection, clustering, recommendations, and an end-to-end pipeline run.

---

## Responsible-use note

This tool is for auditing your own web properties or clients' properties with
explicit permission. It deliberately cannot target multiple domains, honours
`robots.txt`, and rate-limits itself. Do not use it against sites you are not
authorised to test.

## License

Apache-2.0 (consistent with the surrounding repository).
