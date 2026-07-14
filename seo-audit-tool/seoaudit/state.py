"""Checkpointing so long audits can be interrupted and resumed.

The pipeline persists its progress (which dorks have been searched, which pages
analysed, plus the collected data) to a JSON state file after each stage and
periodically during analysis. On restart the pipeline reloads the file and
skips work already done.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from .logging_setup import get_logger
from .models import PageAnalysis, SearchResult

log = get_logger("state")


class AuditState:
    def __init__(self, path: str) -> None:
        self.path = path
        self.domain: str = ""
        self.done_queries: List[str] = []
        self.results: List[Dict[str, Any]] = []
        self.done_urls: List[str] = []
        self.analyses: List[Dict[str, Any]] = []
        self.stage: str = "init"

    # -- persistence --------------------------------------------------------

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        payload = {
            "domain": self.domain,
            "stage": self.stage,
            "done_queries": self.done_queries,
            "results": self.results,
            "done_urls": self.done_urls,
            "analyses": self.analyses,
        }
        # Atomic write so an interrupt mid-save can't corrupt the checkpoint.
        directory = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    @classmethod
    def load(cls, path: str) -> Optional["AuditState"]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not load state %s (%s); starting fresh.", path, exc)
            return None
        st = cls(path)
        st.domain = data.get("domain", "")
        st.stage = data.get("stage", "init")
        st.done_queries = list(data.get("done_queries", []))
        st.results = list(data.get("results", []))
        st.done_urls = list(data.get("done_urls", []))
        st.analyses = list(data.get("analyses", []))
        log.info("Resumed state: stage=%s, %d queries, %d results, %d analyses.",
                 st.stage, len(st.done_queries), len(st.results), len(st.analyses))
        return st

    # -- typed accessors ----------------------------------------------------

    def results_as_models(self) -> List[SearchResult]:
        return [SearchResult(**{k: v for k, v in r.items()
                                if k in SearchResult.__dataclass_fields__})
                for r in self.results]

    def set_results(self, results: List[SearchResult]) -> None:
        self.results = [r.to_dict() for r in results]

    def set_analyses(self, analyses: List[PageAnalysis]) -> None:
        self.analyses = [a.to_dict() for a in analyses]

    def add_analysis(self, analysis: PageAnalysis) -> None:
        self.analyses.append(analysis.to_dict())
        self.done_urls.append(analysis.url)
