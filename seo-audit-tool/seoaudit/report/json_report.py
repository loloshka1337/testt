"""Machine-readable JSON report."""

from __future__ import annotations

import json

from ..models import AuditReport


def render_json(report: AuditReport, path: str) -> str:
    data = report.to_dict()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text
