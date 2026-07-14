"""A small Flask web UI wrapping the audit pipeline.

Audits run in a background thread so the browser stays responsive; the page
polls a status endpoint and links to the generated HTML report when finished.
This is a *local* control panel — bind it to localhost and do not expose it to
untrusted networks.
"""

from __future__ import annotations

import os
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

from ..config import Config
from ..logging_setup import get_logger

log = get_logger("web")


@dataclass
class Job:
    id: str
    domain: str
    status: str = "queued"          # queued | running | done | error
    message: str = ""
    output_dir: str = ""
    stats: dict = field(default_factory=dict)
    report_path: Optional[str] = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, domain: str, output_dir: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], domain=domain, output_dir=output_dir)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)


def _run_job(job: Job, cfg: Config) -> None:
    from ..pipeline import AuditPipeline  # lazy import
    job.status = "running"
    try:
        report = AuditPipeline(cfg).run(resume=False)
        job.stats = report.stats
        job.report_path = os.path.join(cfg.output_dir, "report.html")
        job.status = "done"
        job.message = "Audit complete."
    except Exception as exc:  # surface any failure to the UI
        log.error("Job %s failed: %s\n%s", job.id, exc, traceback.format_exc())
        job.status = "error"
        job.message = str(exc)


def create_app(base_output: str = "seo-audit-output") -> Flask:
    app = Flask(__name__)
    store = JobStore()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/run")
    def run():
        form = request.form
        domain = (form.get("domain") or "").strip()
        if not domain:
            return render_template("index.html", error="A domain is required."), 400
        if not form.get("authorized"):
            return render_template(
                "index.html",
                error="You must confirm you are authorised to audit this domain.",
            ), 400

        output_dir = os.path.join(base_output, domain.replace("/", "_"))
        cfg = Config(
            domain=domain,
            include_subdomains=bool(form.get("include_subdomains")),
            provider=form.get("provider", "manual"),
            manual_results_path=(form.get("manual_results") or None),
            keywords=[k.strip() for k in (form.get("keywords") or "").split(",") if k.strip()],
            seed_paths=[s.strip() for s in (form.get("seed_paths") or "").split(",") if s.strip()],
            max_dorks=int(form.get("max_dorks") or 40),
            max_pages=int(form.get("max_pages") or 100),
            rate_limit_rps=float(form.get("rate_limit") or 1.0),
            analyze_pages=bool(form.get("analyze_pages")),
            output_dir=output_dir,
            report_formats=["json", "html"],
            authorized=True,
        )
        job = store.create(domain, output_dir)
        threading.Thread(target=_run_job, args=(job, cfg), daemon=True).start()
        return redirect(url_for("job_page", job_id=job.id))

    @app.get("/jobs/<job_id>")
    def job_page(job_id: str):
        job = store.get(job_id)
        if not job:
            abort(404)
        return render_template("job.html", job=job)

    @app.get("/jobs/<job_id>/status")
    def job_status(job_id: str):
        job = store.get(job_id)
        if not job:
            abort(404)
        return jsonify({
            "id": job.id, "domain": job.domain, "status": job.status,
            "message": job.message, "stats": job.stats,
            "has_report": bool(job.report_path and os.path.exists(job.report_path)),
        })

    @app.get("/jobs/<job_id>/report")
    def job_report(job_id: str):
        job = store.get(job_id)
        if not job or not job.report_path or not os.path.exists(job.report_path):
            abort(404)
        return send_file(os.path.abspath(job.report_path))

    return app
