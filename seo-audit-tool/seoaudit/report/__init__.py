"""Report writers (JSON, HTML)."""

from __future__ import annotations

import os
from typing import List

from ..logging_setup import get_logger
from ..models import AuditReport
from .html_report import render_html
from .json_report import render_json

log = get_logger("report")


def write_reports(report: AuditReport, output_dir: str, formats: List[str]) -> List[str]:
    """Write the requested report formats and return the paths written."""
    os.makedirs(output_dir, exist_ok=True)
    written: List[str] = []
    for fmt in formats:
        fmt = fmt.lower().strip()
        if fmt == "json":
            path = os.path.join(output_dir, "report.json")
            render_json(report, path)
            written.append(path)
        elif fmt == "html":
            path = os.path.join(output_dir, "report.html")
            render_html(report, path)
            written.append(path)
        elif fmt == "pdf":
            path = os.path.join(output_dir, "report.pdf")
            if _try_pdf(report, path):
                written.append(path)
            else:
                log.warning(
                    "PDF output requested but no PDF engine available. "
                    "Install 'weasyprint' or open report.html and print to PDF."
                )
        else:
            log.warning("Unknown report format %r, skipping.", fmt)
    for p in written:
        log.info("Wrote %s", p)
    return written


def _try_pdf(report: AuditReport, path: str) -> bool:
    """Best-effort PDF via WeasyPrint if it happens to be installed."""
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return False
    html_str = render_html(report, None)
    HTML(string=html_str).write_pdf(path)
    return True
