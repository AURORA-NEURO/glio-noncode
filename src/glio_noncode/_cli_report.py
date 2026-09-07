"""Lightweight command surface for bounded, addressed dossier reports."""

from __future__ import annotations

import argparse
import sys

from ._cli_support import write_json

REPORT_COMMANDS = (
    "assessment-capabilities",
    "report-capabilities",
    "run-assessment",
    "run-report",
)


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("run_id")
    parser.add_argument("--data-root", default=".glio")
    parser.add_argument(
        "--audience",
        choices=("review", "public"),
        default="public",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    parser.add_argument("--output", default="-")


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

    assessment_capabilities_parser = commands.add_parser(
        "assessment-capabilities",
        help="emit deterministic verified-run assessment capabilities",
    )
    assessment_capabilities_parser.add_argument("--output", default="-")

    run_report = commands.add_parser(
        "run-report",
        help="reopen one persisted run and emit an addressed dossier report",
    )
    _add_run_options(run_report)

    run_assessment = commands.add_parser(
        "run-assessment",
        help="reopen one persisted run and emit its quality-and-report closure",
    )
    _add_run_options(run_assessment)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from .assessments import assessment_capabilities, build_run_assessment
        from .errors import GlioError
        from .reports import report_capabilities

        if args.report_command == "report-capabilities":
            write_json(report_capabilities(), args.output)
            return 0
        if args.report_command == "assessment-capabilities":
            write_json(assessment_capabilities(), args.output)
            return 0
        if args.report_command in {"run-report", "run-assessment"}:
            from .runtime import CaseRuntime

            runtime = CaseRuntime(args.data_root)
            assessment = build_run_assessment(
                runtime,
                args.run_id,
                audience=args.audience,
                format=args.format,
            )
            payload = (
                assessment.rendered_report.to_dict()
                if args.report_command == "run-report"
                else assessment.to_dict()
            )
            write_json(payload, args.output)
            return 0
    except (GlioError, OSError, UnicodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


__all__ = ["REPORT_COMMANDS", "build_parser", "main"]
