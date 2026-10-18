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


def test_registrable_domain_russian_second_level_suffix():
    # Regression: example.com.ru used to collapse to com.ru.
    assert registrable_domain("example.com.ru") == "example.com.ru"
    assert registrable_domain("www.shop.example.com.ru") == "example.com.ru"


def test_registrable_domain_psl_multi_label():
    assert registrable_domain("sub.example.co.uk") == "example.co.uk"
    assert registrable_domain("a.b.example.com.au") == "example.com.au"


def test_registrable_domain_private_suffix_github_io():
    assert registrable_domain("user.github.io") == "user.github.io"
    assert registrable_domain("docs.user.github.io") == "user.github.io"


def test_registrable_domain_plain_unchanged():
    assert registrable_domain("example.com") == "example.com"


def test_registrable_domain_bare_suffix_does_not_widen():
    assert registrable_domain("com.ru") == "com.ru"
    assert registrable_domain("localhost") == "localhost"
    assert registrable_domain("192.168.1.10") == "192.168.1.10"


def test_scope_com_ru_does_not_spread():
    scope = DomainScope("example.com.ru", include_subdomains=True)
    assert scope.registrable == "example.com.ru"
    assert scope.site_operator_value == "example.com.ru"
    assert scope.url_in_scope("https://blog.example.com.ru/post")
    assert scope.url_in_scope("https://example.com.ru/")
    assert not scope.url_in_scope("https://foo.com.ru/")
    assert not scope.url_in_scope("https://com.ru/")


def test_scope_github_io_does_not_spread():
    scope = DomainScope("user.github.io", include_subdomains=True)
    assert scope.url_in_scope("https://user.github.io/repo/")
    assert not scope.url_in_scope("https://other.github.io/")
    assert not scope.url_in_scope("https://github.io/")


def test_scope_co_uk_does_not_spread():
    scope = DomainScope("example.co.uk", include_subdomains=True)
    assert scope.url_in_scope("https://shop.example.co.uk/")
    assert not scope.url_in_scope("https://other.co.uk/")
