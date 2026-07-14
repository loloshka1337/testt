"""The end-to-end audit pipeline.

Wires the stages together — dork generation → collection → analysis →
clustering → recommendations → reporting — while persisting a resumable
checkpoint after each stage and handling graceful interruption (Ctrl-C).
"""

from __future__ import annotations

import signal
from typing import List, Optional

from . import __version__
from .analyzer import PageAnalyzer, find_duplicate_groups
from .cluster import Clusterer, RecommendationEngine
from .collector import Collector
from .config import Config
from .domain import DomainScope
from .dorks import DorkGenerator
from .http_client import PoliteHTTPClient
from .logging_setup import get_logger
from .models import AuditReport, PageAnalysis
from .ratelimit import RateLimiter
from .report import write_reports
from .search import build_provider
from .state import AuditState

log = get_logger("pipeline")


class AuditPipeline:
    def __init__(self, config: Config) -> None:
        if not config.domain:
            raise ValueError("A target domain is required.")
        if not config.authorized:
            raise PermissionError(
                "Refusing to run: config.authorized is False. This tool may only be "
                "used on a domain you own or are explicitly authorised to audit. "
                "Set authorized=True (CLI: --i-am-authorized) to confirm."
            )
        self.config = config
        self.scope = DomainScope(config.domain, config.include_subdomains)
        self._interrupted = False
        self._state: Optional[AuditState] = None

    # -- interruption -------------------------------------------------------

    def _install_signal_handler(self) -> None:
        def handler(signum, frame):  # noqa: ARG001
            log.warning("Interrupt received — finishing current item and checkpointing…")
            self._interrupted = True
        try:
            signal.signal(signal.SIGINT, handler)
        except ValueError:
            # Not in the main thread (e.g. web server) — skip; caller controls lifecycle.
            pass

    # -- stages -------------------------------------------------------------

    def run(self, resume: bool = True) -> AuditReport:
        cfg = self.config
        self._install_signal_handler()

        state = AuditState.load(cfg.state_file) if resume else None
        if state and state.domain and state.domain != self.scope.registrable:
            log.warning("State file is for a different domain (%s); ignoring it.", state.domain)
            state = None
        if state is None:
            state = AuditState(cfg.state_file)
            state.domain = self.scope.registrable
        self._state = state

        # 1. Dorks -----------------------------------------------------------
        generator = DorkGenerator(
            self.scope, keywords=cfg.keywords, seed_paths=cfg.seed_paths,
            categories=cfg.dork_categories,
        )
        dorks = generator.generate(limit=cfg.max_dorks)
        log.info("Generated %d dorks.", len(dorks))

        # 2. Collection ------------------------------------------------------
        provider = build_provider(cfg)
        collector = Collector(provider, self.scope, results_per_dork=cfg.results_per_dork)

        def on_collect(i, total, dork):
            state.done_queries = sorted(set(state.done_queries) | {dork.query})
            if i % 5 == 0 or i == total:
                state.stage = "collecting"
                state.save()

        seed_results = state.results_as_models() if state.results else None
        results = collector.collect(
            dorks,
            seed=seed_results,
            done_queries=set(state.done_queries),
            on_progress=on_collect,
        )
        state.set_results(results)
        state.stage = "collected"
        state.save()

        # 3. Analysis --------------------------------------------------------
        analyses: List[PageAnalysis] = [
            PageAnalysis.from_dict(a) for a in state.analyses
        ] if state.analyses else []

        if cfg.analyze_pages and not self._interrupted:
            urls = [r.url for r in results][: cfg.max_pages]
            limiter = RateLimiter(cfg.rate_limit_rps, cfg.jitter)
            client = PoliteHTTPClient(
                limiter,
                user_agents=cfg.user_agents,
                rotate_user_agents=cfg.rotate_user_agents,
                timeout=cfg.request_timeout,
                max_retries=cfg.max_retries,
                respect_robots=cfg.respect_robots_txt,
                contact_email=cfg.contact_email,
            )
            analyzer = PageAnalyzer(client, self.scope, concurrency=cfg.concurrency)

            done_urls = set(state.done_urls)
            saved_counter = {"n": 0}

            def on_result(pa: PageAnalysis):
                state.add_analysis(pa)
                saved_counter["n"] += 1
                if saved_counter["n"] % 10 == 0:
                    state.stage = "analyzing"
                    state.save()

            new = analyzer.analyze_many(urls, already_done=done_urls, on_result=on_result)
            analyses.extend(new)
            client.close()
            state.stage = "analyzed"
            state.save()
        else:
            log.info("Page analysis skipped (analyze_pages=%s, interrupted=%s).",
                     cfg.analyze_pages, self._interrupted)

        # 4. Clustering ------------------------------------------------------
        clusterer = Clusterer(seed_paths=cfg.seed_paths)
        clusters = clusterer.cluster(analyses)

        # 5. Duplicates + recommendations -----------------------------------
        dup_groups = find_duplicate_groups(analyses, threshold=cfg.duplicate_similarity)
        engine = RecommendationEngine(duplicate_groups=dup_groups)
        recommendations = engine.generate(analyses, clusters)

        # 6. Assemble report -------------------------------------------------
        report = AuditReport(
            domain=self.scope.registrable,
            tool_version=__version__,
            config=cfg.redacted_dict(),
            dorks=dorks,
            results=results,
            analyses=analyses,
            clusters=clusters,
            recommendations=recommendations,
            stats={
                "dorks": len(dorks),
                "urls_discovered": len(results),
                "pages_analyzed": len(analyses),
                "indexable": sum(1 for a in analyses if a.indexable),
                "pages_with_issues": sum(1 for a in analyses if a.issues),
                "pages_with_leaks": sum(1 for a in analyses if a.leaks),
                "duplicate_groups": len(dup_groups),
                "recommendations": len(recommendations),
                "interrupted": self._interrupted,
            },
        )

        written = write_reports(report, cfg.output_dir, cfg.report_formats)
        report.stats["reports"] = written
        state.stage = "done"
        state.save()
        log.info("Audit complete. %s", report.stats)
        return report
