"""Lightweight command-line dispatch with complete legacy compatibility."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any

_TOP_LEVEL_HELP = """\
usage: glio-noncode COMMAND [ARGS]...

Inspectable research hypothesis runtime.

Focused commands:
  case                 prepare and run a case from source manifests
  expression           analyze expression and allele-specific RNA evidence
  cohort-recurrence    compare a locus with callable-subject-matched controls
  geo-outlier          compare one GEO expression feature with explicit references
  geo-qc               summarize sample coverage and matrix quality before analysis
  geo-metadata         inventory GEO sample characteristics before contrast design
  geo-design           check GEO cohort selection and contrast estimability
  geo-consistency      compare exact feature directions across GEO contrasts
  geo-contrast         screen GEO groups, optionally joining platform annotations
  verify-release-evidence  verify a portable release-evidence ZIP
  report-capabilities  inspect supported report audiences, formats, and limits
  assessment-capabilities  inspect verified-run assessment contracts and limits
  run-report           render one replay-verified persisted run
  run-assessment       build one replay, quality, report, and rendering closure
  commands list        list every available command
  commands search TERM search command names and summaries
  commands show NAME   show the summary for one command

Every legacy command remains available and is loaded only when selected.
Run 'glio-noncode commands search TERM' to discover the compatibility surface.
"""

_COMMANDS_HELP = """\
usage: glio-noncode commands {list,search,show} [VALUE]

Inspect the static command index without loading the legacy runtime:
  list                 print all command names and summaries
  search TERM [...]    find commands matching every search term
  show NAME            print one exact command name and summary
"""


def _distribution_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("glio-noncode")
    except PackageNotFoundError:
        return "0.1.0"


def _legacy_module() -> ModuleType:
    return importlib.import_module(f"{__package__}._legacy_cli")


def _print_command_rows(rows: tuple[tuple[str, str], ...]) -> None:
    for name, help_text in rows:
        print(f"{name}\t{help_text}" if help_text else name)


def _command_index_main(argv: list[str]) -> int:
    from ._cli_index import COMMAND_BY_NAME, COMMANDS

    if not argv or argv[0] in {"-h", "--help"}:
        print(_COMMANDS_HELP, end="")
        return 0

    operation, *values = argv
    if operation == "list" and not values:
        _print_command_rows(COMMANDS)
        return 0
    if operation == "search" and values:
        terms = tuple(value.casefold() for value in values)
        matches = tuple(
            row
            for row in COMMANDS
            if all(term in f"{row[0]}\t{row[1]}".casefold() for term in terms)
        )
        _print_command_rows(matches)
        return 0 if matches else 1
    if operation == "show" and len(values) == 1:
        name = values[0]
        help_text = COMMAND_BY_NAME.get(name)
        if help_text is None:
            print(f"error: command is not present in the static index: {name}", file=sys.stderr)
            return 1
        _print_command_rows(((name, help_text),))
        return 0

    print(_COMMANDS_HELP, file=sys.stderr, end="")
    return 2


def build_parser() -> Any:
    """Build and return the complete compatibility parser.

    This explicitly opts into the expensive legacy import. Fast dispatch paths do
    not call this function.
    """

    return _legacy_module().build_parser()


def main(argv: list[str] | None = None) -> int:
    """Dispatch focused commands quickly and preserve every legacy command."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help"}:
        print(_TOP_LEVEL_HELP, end="")
        return 0
    if arguments == ["--version"]:
        print(f"glio-noncode {_distribution_version()}")
        return 0

    command, *command_argv = arguments
    if command == "commands":
        return _command_index_main(command_argv)
    if command == "case":
        return importlib.import_module(f"{__package__}._cli_case").main(command_argv)
    if command == "expression":
        return importlib.import_module(f"{__package__}._cli_expression").main(command_argv)
    if command == "cohort-recurrence":
        return importlib.import_module(f"{__package__}._cli_cohort_recurrence").main(command_argv)
    if command == "geo-outlier":
        return importlib.import_module(f"{__package__}._cli_geo").main(command_argv)
    if command == "geo-qc":
        return importlib.import_module(f"{__package__}._cli_geo_qc").main(command_argv)
    if command == "geo-metadata":
        return importlib.import_module(f"{__package__}._cli_geo_metadata").main(command_argv)
    if command == "geo-design":
        return importlib.import_module(f"{__package__}._cli_geo_design").main(command_argv)
    if command == "geo-consistency":
        return importlib.import_module(f"{__package__}._cli_geo_consistency").main(command_argv)
    if command == "geo-contrast":
        return importlib.import_module(f"{__package__}._cli_geo_contrast").main(command_argv)
    if command == "verify-release-evidence":
        return importlib.import_module(f"{__package__}._cli_evidence").main(command_argv)
    if command in {
        "assessment-capabilities",
        "report-capabilities",
        "run-assessment",
        "run-report",
    }:
        return importlib.import_module(f"{__package__}._cli_report").main(arguments)

    # The generated index is intentionally not an allowlist. An unindexed token
    # always reaches the compatibility parser so index lag cannot remove commands.
    return _legacy_module().main(arguments)


def __getattr__(name: str) -> Any:
    """Lazily expose non-entry-point helpers retained by the legacy module."""

    if name.startswith("__"):
        raise AttributeError(name)
    try:
        value = getattr(_legacy_module(), name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    globals()[name] = value
    return value


MAX_JSON_BYTES: int
__all__ = ["MAX_JSON_BYTES", "build_parser", "main"]
