import json
import os

import pytest

from seoaudit.config import Config
from seoaudit.pipeline import AuditPipeline
from seoaudit.state import AuditState


def _cfg(tmp_path, **over):
    results = [
        {"url": "https://example.com/", "title": "Home"},
        {"url": "https://example.com/blog/post", "title": "Post"},
        {"url": "https://off.com/x", "title": "off"},
    ]
    rp = tmp_path / "results.json"
    rp.write_text(json.dumps(results), encoding="utf-8")
    base = dict(
        domain="example.com",
        provider="manual",
        manual_results_path=str(rp),
        analyze_pages=False,       # keep the test offline
        output_dir=str(tmp_path / "out"),
        report_formats=["json", "html"],
        authorized=True,
    )
    base.update(over)
    return Config(**base)


def test_pipeline_requires_authorization(tmp_path):
    cfg = _cfg(tmp_path, authorized=False)
    with pytest.raises(PermissionError):
        AuditPipeline(cfg)


def test_pipeline_offline_run(tmp_path):
    cfg = _cfg(tmp_path)
    report = AuditPipeline(cfg).run(resume=False)
    assert report.domain == "example.com"
    # off-domain result dropped
    assert all("off.com" not in r.url for r in report.results)
    assert report.stats["urls_discovered"] == 2
    # reports written
    assert os.path.exists(os.path.join(cfg.output_dir, "report.json"))
    assert os.path.exists(os.path.join(cfg.output_dir, "report.html"))
    # dorks generated and scoped
    assert report.dorks and all(d.query.startswith("site:example.com") for d in report.dorks)


def test_pipeline_state_saved_and_resumable(tmp_path):
    cfg = _cfg(tmp_path)
    AuditPipeline(cfg).run(resume=False)
    st = AuditState.load(cfg.state_file)
    assert st is not None
    assert st.stage == "done"
    assert st.domain == "example.com"
    assert len(st.results) == 2


def test_html_report_contains_domain(tmp_path):
    cfg = _cfg(tmp_path)
    AuditPipeline(cfg).run(resume=False)
    html = open(os.path.join(cfg.output_dir, "report.html"), encoding="utf-8").read()
    assert "example.com" in html
    assert "Аудит видимости в поиске" in html
