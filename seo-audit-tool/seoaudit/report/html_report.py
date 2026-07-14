"""Human-friendly, self-contained HTML report (inline CSS, no external assets)."""

from __future__ import annotations

import os
from collections import Counter
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import AuditReport

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    return env


def _build_context(report: AuditReport) -> dict:
    analyses = report.analyses
    total = len(analyses)
    indexable = sum(1 for a in analyses if a.indexable)
    with_issues = sum(1 for a in analyses if a.issues)
    with_leaks = sum(1 for a in analyses if a.leaks)

    issue_counter: Counter = Counter()
    for a in analyses:
        for i in a.issues:
            issue_counter[i.code] += 1

    action_counter: Counter = Counter(r.action.value for r in report.recommendations)
    sev_counter: Counter = Counter(r.severity.value for r in report.recommendations)

    return {
        "report": report,
        "total_pages": total,
        "indexable": indexable,
        "not_indexable": total - indexable,
        "with_issues": with_issues,
        "with_leaks": with_leaks,
        "top_issues": issue_counter.most_common(12),
        "action_counter": action_counter,
        "sev_counter": sev_counter,
        "severity_order": _SEVERITY_ORDER,
    }


def render_html(report: AuditReport, path: Optional[str]) -> str:
    template = _env().get_template("report.html.j2")
    html = template.render(**_build_context(report))
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
    return html
