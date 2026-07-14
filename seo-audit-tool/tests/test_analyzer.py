from seoaudit.analyzer import PageAnalyzer, find_duplicate_groups, jaccard
from seoaudit.domain import DomainScope
from seoaudit.http_client import FetchResult
from seoaudit.models import PageAnalysis


class FakeClient:
    """Stand-in for PoliteHTTPClient that serves canned responses."""

    def __init__(self, pages, robots=True):
        self.pages = pages          # url -> FetchResult
        self.robots = robots

    def allowed_by_robots(self, url):
        return self.robots

    def get(self, url):
        return self.pages[url]

    def close(self):
        pass


def _fr(url, status=200, html="", headers=None, final=None):
    return FetchResult(
        url=url, final_url=final or url, status_code=status,
        headers=headers or {}, text=html, redirect_chain=[url],
        content_type="text/html; charset=utf-8",
    )


def test_analyze_detects_noindex_and_missing_meta():
    html = """
    <html><head><title>Fine title for the page here</title>
    <meta name="robots" content="noindex,follow">
    </head><body><h1>Hi</h1><p>{}</p></body></html>
    """.format("word " * 200)
    scope = DomainScope("example.com")
    client = FakeClient({"https://example.com/x": _fr("https://example.com/x", html=html)})
    analyzer = PageAnalyzer(client, scope)
    pa = analyzer.analyze_one("https://example.com/x")
    assert pa.robots_index is False
    assert pa.indexable is False
    codes = {i.code for i in pa.issues}
    assert "meta_noindex" in codes
    assert "missing_meta_description" in codes


def test_analyze_flags_leak():
    html = "<html><head><title>Config page shown by mistake</title></head><body>" \
           "DB_PASSWORD=supersecret123</body></html>"
    scope = DomainScope("example.com")
    client = FakeClient({"https://example.com/c": _fr("https://example.com/c", html=html)})
    pa = PageAnalyzer(client, scope).analyze_one("https://example.com/c")
    leak_codes = {i.code for i in pa.leaks}
    assert "env_dump" in leak_codes or "password_assignment" in leak_codes


def test_analyze_robots_disallow_short_circuits():
    scope = DomainScope("example.com")
    client = FakeClient({}, robots=False)
    pa = PageAnalyzer(client, scope).analyze_one("https://example.com/blocked")
    assert pa.robots_txt_allowed is False
    assert pa.indexable is False
    assert any(i.code == "robots_txt_disallow" for i in pa.issues)


def test_off_scope_url_rejected():
    scope = DomainScope("example.com")
    pa = PageAnalyzer(FakeClient({}), scope).analyze_one("https://evil.com/x")
    assert pa.error is not None
    assert any(i.code == "off_scope" for i in pa.issues)


def test_duplicate_detection():
    body = "the quick brown fox jumps over the lazy dog " * 30
    a = PageAnalysis(url="https://example.com/1")
    b = PageAnalysis(url="https://example.com/2")
    from seoaudit.analyzer import _shingles
    a.shingles = _shingles(body)
    b.shingles = _shingles(body)
    a.content_hash = "same"
    b.content_hash = "same"
    groups = find_duplicate_groups([a, b], threshold=0.9)
    assert groups and set(groups[0]) == {"https://example.com/1", "https://example.com/2"}


def test_jaccard_bounds():
    assert jaccard([], [1]) == 0.0
    assert jaccard([1, 2, 3], [1, 2, 3]) == 1.0
