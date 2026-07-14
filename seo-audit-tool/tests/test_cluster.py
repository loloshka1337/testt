from seoaudit.cluster import Clusterer, RecommendationEngine
from seoaudit.models import Action, Issue, PageAnalysis, Severity


def _page(url, **kw):
    pa = PageAnalysis(url=url, final_url=url, status_code=kw.pop("status", 200))
    for k, v in kw.items():
        setattr(pa, k, v)
    return pa


def test_clusterer_assigns_types():
    analyses = [
        _page("https://example.com/"),
        _page("https://example.com/blog/post-1"),
        _page("https://example.com/admin/login"),
        _page("https://example.com/products/shoe"),
        _page("https://example.com/x?utm_source=a"),
    ]
    clusters = {c.page_type: c for c in Clusterer().cluster(analyses)}
    assert "home" in clusters
    assert "blog" in clusters
    assert "admin" in clusters
    assert "product" in clusters


def test_seed_paths_take_priority():
    analyses = [_page("https://example.com/docs/api")]
    clusters = Clusterer(seed_paths=["docs"]).cluster(analyses)
    assert clusters[0].page_type == "seed:docs"


def test_recommend_deindex_for_leak():
    pa = _page("https://example.com/config")
    pa.leaks = [Issue("env_dump", "leak", Severity.CRITICAL)]
    clusters = Clusterer().cluster([pa])
    recs = RecommendationEngine().generate([pa], clusters)
    assert any(r.action == Action.DEINDEX and r.severity == Severity.CRITICAL for r in recs)


def test_recommend_deindex_broken_page():
    pa = _page("https://example.com/gone", status=404)
    clusters = Clusterer().cluster([pa])
    recs = RecommendationEngine().generate([pa], clusters)
    assert any(r.action == Action.DEINDEX and "404" in r.title for r in recs)


def test_recommend_deindex_admin_indexable():
    pa = _page("https://example.com/admin/settings")
    clusters = Clusterer().cluster([pa])
    recs = RecommendationEngine().generate([pa], clusters)
    assert any(r.action == Action.DEINDEX for r in recs)


def test_recommend_index_blocked_content():
    pa = _page("https://example.com/blog/good", robots_index=False)
    clusters = Clusterer().cluster([pa])
    recs = RecommendationEngine().generate([pa], clusters)
    assert any(r.action == Action.INDEX for r in recs)
