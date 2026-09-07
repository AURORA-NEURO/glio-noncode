"""Lightweight command surface for bounded, addressed dossier reports."""

from __future__ import annotations

import argparse
import sys

from ._cli_support import write_json

REPORT_COMMANDS = ("report-capabilities", "run-report")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode",
        description="Build bounded, audience-aware reports from replay-verified runs",
    )
    commands = parser.add_subparsers(dest="report_command", required=True)

    capabilities = commands.add_parser(
        "report-capabilities",
        help="emit deterministic dossier report capabilities",
    )
    capabilities.add_argument("--output", default="-")

    run_report = commands.add_parser(
        "run-report",
        help="reopen one persisted run and emit an addressed dossier report",
    )
    run_report.add_argument("run_id")
    run_report.add_argument("--data-root", default=".glio")
    run_report.add_argument(
        "--audience",
        choices=("review", "public"),
        default="public",
    )
    run_report.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    run_report.add_argument("--output", default="-")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from .errors import GlioError
        from .reports import build_report, render_report, report_capabilities

        if args.report_command == "report-capabilities":
            write_json(report_capabilities(), args.output)
            return 0
        if args.report_command == "run-report":
            from .runtime import CaseRuntime

            snapshot = CaseRuntime(args.data_root).load_run_snapshot(args.run_id)
            report = build_report(snapshot.dossier, audience=args.audience)
            rendered = render_report(report, format=args.format)
            write_json(rendered.to_dict(), args.output)
            return 0
    except (GlioError, OSError, UnicodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


__all__ = ["REPORT_COMMANDS", "build_parser", "main"]
