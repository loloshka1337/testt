import seoaudit
from seoaudit.insights import Insights, build_insights
from seoaudit.models import Action, Issue, PageAnalysis, Severity


def _page(url, **kw):
    pa = PageAnalysis(url=url, final_url=url, status_code=kw.pop("status", 200))
    for k, v in kw.items():
        setattr(pa, k, v)
    return pa


def test_build_insights_combines_stages():
    pages = [
        _page("https://example.com/blog/a", word_count=500),
        _page("https://example.com/admin/login"),
        _page("https://example.com/gone", status=404),
    ]
    ins = build_insights(pages, seed_paths=["blog"], duplicate_similarity=0.9)
    assert isinstance(ins, Insights)
    assert ins.clusters                # clustering ran
    assert ins.recommendations         # recommendations ran
    # duplicate detection ran (no dupes here -> empty list, but attribute present)
    assert isinstance(ins.duplicate_groups, list)
    # broken page yields a deindex recommendation
    assert any(r.action == Action.DEINDEX for r in ins.recommendations)


def test_package_facades_exposed():
    assert callable(seoaudit.run_audit)
    assert callable(seoaudit.generate_dorks)
    assert callable(seoaudit.build_insights)


def test_generate_dorks_facade():
    dorks = seoaudit.generate_dorks("example.com", keywords=["shoes"], limit=8)
    assert len(dorks) == 8
    assert all(d.query.startswith("site:example.com") for d in dorks)
