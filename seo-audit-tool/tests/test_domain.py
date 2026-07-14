from seoaudit.domain import DomainScope, canonicalize_url, registrable_domain


def test_registrable_domain_simple():
    assert registrable_domain("www.example.com") == "example.com"
    assert registrable_domain("a.b.example.com") == "example.com"


def test_registrable_domain_multi_label_suffix():
    assert registrable_domain("shop.example.co.uk") == "example.co.uk"
    assert registrable_domain("example.com.au") == "example.com.au"


def test_scope_includes_subdomains():
    scope = DomainScope("example.com", include_subdomains=True)
    assert scope.url_in_scope("https://blog.example.com/post")
    assert scope.url_in_scope("http://example.com/")
    assert not scope.url_in_scope("https://evil.com/example.com")
    assert not scope.url_in_scope("https://notexample.com/")


def test_scope_excludes_subdomains():
    scope = DomainScope("example.com", include_subdomains=False)
    assert scope.url_in_scope("https://example.com/x")
    assert not scope.url_in_scope("https://blog.example.com/x")


def test_canonicalize_url():
    assert canonicalize_url("https://www.Example.com/Path/") == "https://example.com/Path"
    assert canonicalize_url("HTTP://example.com") == "http://example.com/"
    assert canonicalize_url("ftp://example.com/x") is None
    # fragment dropped, query kept
    assert canonicalize_url("https://example.com/a?b=1#frag") == "https://example.com/a?b=1"
