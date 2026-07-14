"""Command-line interface for seoaudit.

Subcommands:

  audit   run the full pipeline (generate → collect → analyse → report)
  dorks   just generate and print the search queries for a domain
  web     launch the local web interface

Run ``python -m seoaudit <subcommand> --help`` for details.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .config import Config
from .domain import DomainScope
from .dorks import ALL_CATEGORIES, DorkGenerator
from .logging_setup import setup_logging
from .search import AVAILABLE_PROVIDERS

_BANNER = f"seoaudit v{__version__} — «белый» аудит видимости в поиске для одного домена"


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("domain", help="Целевой домен, которым вы владеете / имеете право аудировать (напр. example.com)")
    p.add_argument("--config", help="Путь к JSON-файлу конфигурации (флаги CLI имеют приоритет).")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--no-subdomains", action="store_true",
                   help="Ограничить область точным хостом, без поддоменов.")


def _config_from_args(args: argparse.Namespace) -> Config:
    base = {}
    if getattr(args, "config", None):
        base = json.loads(open(args.config, encoding="utf-8").read())
    cfg = Config.from_dict(base)
    cfg.domain = args.domain
    if getattr(args, "no_subdomains", False):
        cfg.include_subdomains = False
    # Apply audit-specific overrides when present.
    for attr, key in [
        ("provider", "provider"), ("max_dorks", "max_dorks"),
        ("results_per_dork", "results_per_dork"), ("max_pages", "max_pages"),
        ("output", "output_dir"), ("rate_limit", "rate_limit_rps"),
        ("concurrency", "concurrency"), ("manual_results", "manual_results_path"),
        ("contact_email", "contact_email"),
    ]:
        val = getattr(args, attr, None)
        if val is not None:
            setattr(cfg, key, val)
    if getattr(args, "keywords", None):
        cfg.keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if getattr(args, "seed_paths", None):
        cfg.seed_paths = [p.strip() for p in args.seed_paths.split(",") if p.strip()]
    if getattr(args, "categories", None):
        cfg.dork_categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    if getattr(args, "formats", None):
        cfg.report_formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    if getattr(args, "no_analyze", False):
        cfg.analyze_pages = False
    if getattr(args, "no_robots", False):
        cfg.respect_robots_txt = False
    if getattr(args, "i_am_authorized", False):
        cfg.authorized = True
    # Re-run post-init to re-apply clamping / env fallbacks.
    cfg.__post_init__()
    return cfg


def cmd_audit(args: argparse.Namespace) -> int:
    from .pipeline import AuditPipeline  # lazy import (pulls requests/bs4)

    cfg = _config_from_args(args)
    log_file = os.path.join(cfg.output_dir, "audit.log")
    setup_logging(args.log_level, log_file=log_file)

    if not cfg.authorized:
        print("ОШИБКА: подтвердите разрешение флагом --i-am-authorized.\n"
              "Аудируйте только домены, которыми владеете или на которые есть явное разрешение.",
              file=sys.stderr)
        return 2
    try:
        pipeline = AuditPipeline(cfg)
    except (PermissionError, ValueError) as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 2

    report = pipeline.run(resume=not args.no_resume)
    print("\n" + "=" * 60)
    print(f"Аудит домена {report.domain} завершён.")
    for k, v in report.stats.items():
        if k != "reports":
            print(f"  {k:22s}: {v}")
    for path in report.stats.get("reports", []):
        print(f"  отчёт                 : {path}")
    print("=" * 60)
    return 0


def cmd_dorks(args: argparse.Namespace) -> int:
    setup_logging(args.log_level)
    scope = DomainScope(args.domain, include_subdomains=not args.no_subdomains)
    keywords = [k.strip() for k in (args.keywords or "").split(",") if k.strip()]
    seeds = [s.strip() for s in (args.seed_paths or "").split(",") if s.strip()]
    cats = [c.strip() for c in (args.categories or "").split(",") if c.strip()] or None
    gen = DorkGenerator(scope, keywords=keywords, seed_paths=seeds, categories=cats)
    dorks = gen.generate(limit=args.max_dorks)
    if args.json:
        print(json.dumps([d.to_dict() for d in dorks], ensure_ascii=False, indent=2))
    else:
        print(f"# {len(dorks)} запросов для {scope.registrable}\n")
        for d in dorks:
            print(f"[{d.category}] {d.query}")
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from .web.app import create_app  # lazy import (pulls flask)

    setup_logging(args.log_level)
    app = create_app()
    print(f"{_BANNER}\nВеб-интерфейс: http://{args.host}:{args.port}  (Ctrl-C для остановки)")
    app.run(host=args.host, port=args.port, debug=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seoaudit", description=_BANNER)
    parser.add_argument("--version", action="version", version=f"seoaudit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # audit
    a = sub.add_parser("audit", help="Запустить полный конвейер аудита.")
    _add_common(a)
    a.add_argument("--provider", choices=AVAILABLE_PROVIDERS,
                   help="Источник поиска (по умолчанию: manual/офлайн).")
    a.add_argument("--manual-results", help="JSON-файл результатов для --provider manual.")
    a.add_argument("--keywords", help="Ключевые слова через запятую.")
    a.add_argument("--seed-paths", help="Известные разделы сайта через запятую (напр. blog,shop).")
    a.add_argument("--categories", help=f"Категории запросов через запятую: {','.join(ALL_CATEGORIES)}")
    a.add_argument("--max-dorks", type=int, help="Макс. число поисковых запросов.")
    a.add_argument("--results-per-dork", type=int, help="Сколько результатов запрашивать на запрос.")
    a.add_argument("--max-pages", type=int, help="Макс. число загружаемых и анализируемых страниц.")
    a.add_argument("--rate-limit", type=float, dest="rate_limit",
                   help="Запросов в секунду к целевому домену (по умолчанию 1.0).")
    a.add_argument("--concurrency", type=int, help="Параллельных загрузок страниц (по умолчанию 4).")
    a.add_argument("--contact-email", help="Указать контактный адрес в заголовке From:.")
    a.add_argument("--formats", help="Форматы отчёта: json,html,pdf (по умолчанию json,html).")
    a.add_argument("--output", help="Каталог для результатов.")
    a.add_argument("--no-analyze", action="store_true", help="Только сбор; без анализа страниц.")
    a.add_argument("--no-robots", action="store_true",
                   help="Не загружать/не соблюдать robots.txt (только для своего сайта, осторожно).")
    a.add_argument("--no-resume", action="store_true", help="Игнорировать существующий чекпоинт.")
    a.add_argument("--i-am-authorized", action="store_true",
                   help="Подтвердить право на аудит этого домена (обязательно).")
    a.set_defaults(func=cmd_audit)

    # dorks
    d = sub.add_parser("dorks", help="Только сгенерировать и вывести поисковые запросы.")
    _add_common(d)
    d.add_argument("--keywords", help="Ключевые слова через запятую.")
    d.add_argument("--seed-paths", help="Известные разделы сайта через запятую.")
    d.add_argument("--categories", help=f"Категории через запятую: {','.join(ALL_CATEGORIES)}")
    d.add_argument("--max-dorks", type=int, default=60)
    d.add_argument("--json", action="store_true", help="Выводить JSON вместо текста.")
    d.set_defaults(func=cmd_dorks)

    # web
    w = sub.add_parser("web", help="Запустить локальный веб-интерфейс.")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8000)
    w.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    w.set_defaults(func=cmd_web)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
