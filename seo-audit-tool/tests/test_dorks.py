from seoaudit.domain import DomainScope
from seoaudit.dorks import DorkGenerator


def _scope():
    return DomainScope("example.com", include_subdomains=True)


def test_all_dorks_scoped_to_site():
    gen = DorkGenerator(_scope(), keywords=["pricing"], seed_paths=["blog"])
    dorks = gen.generate()
    assert dorks
    for d in dorks:
        assert d.query.startswith("site:example.com"), d.query


def test_dork_limit_and_variety():
    gen = DorkGenerator(_scope(), keywords=["a", "b"], seed_paths=["shop"])
    dorks = gen.generate(limit=10)
    assert len(dorks) == 10
    # Round-robin interleave should surface more than one category early.
    cats = {d.category for d in dorks}
    assert len(cats) >= 2


def test_dorks_are_unique_and_deterministic():
    gen = DorkGenerator(_scope(), keywords=["x"])
    first = [d.query for d in gen.generate()]
    second = [d.query for d in gen.generate()]
    assert first == second
    assert len(first) == len(set(first))


def test_keyword_dorks_present():
    gen = DorkGenerator(_scope(), keywords=["running shoes"], categories=["content"])
    queries = [d.query for d in gen.generate()]
    assert any('intitle:"running shoes"' in q for q in queries)
