import json

from seoaudit.collector import Collector
from seoaudit.domain import DomainScope
from seoaudit.models import Dork
from seoaudit.search.manual import ManualProvider


def _write_results(tmp_path):
    data = [
        {"url": "https://example.com/a", "title": "A"},
        {"url": "https://example.com/a/", "title": "A dup slash"},
        {"url": "https://blog.example.com/b", "title": "B"},
        {"url": "https://off-domain.com/x", "title": "off"},
    ]
    p = tmp_path / "results.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_collector_scopes_and_dedupes(tmp_path):
    provider = ManualProvider(_write_results(tmp_path))
    scope = DomainScope("example.com", include_subdomains=True)
    collector = Collector(provider, scope, results_per_dork=50)
    dorks = [Dork("site:example.com", "coverage", "r")]
    results = collector.collect(dorks)
    urls = {r.url for r in results}
    # off-domain dropped; /a and /a/ collapse to one canonical entry
    assert "https://off-domain.com/x" not in urls
    assert any("blog.example.com/b" in u for u in urls)
    canonical = {u.rstrip("/") for u in urls}
    assert len([u for u in canonical if u.endswith("example.com/a")]) == 1


def test_collector_respects_done_queries(tmp_path):
    provider = ManualProvider(_write_results(tmp_path))
    scope = DomainScope("example.com")
    collector = Collector(provider, scope)
    dork = Dork("site:example.com", "coverage", "r")
    results = collector.collect([dork], done_queries={"site:example.com"})
    # Query already done and no seed -> nothing collected
    assert results == []
