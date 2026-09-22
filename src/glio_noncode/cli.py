"""Lightweight command-line dispatch with complete legacy compatibility."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any

_REFERENCE_BLOCK_QUERY_MAX_SOURCE_BYTES = 128 * 1024 * 1024
_REFERENCE_BLOCK_QUERY_MAX_TEXT_BYTES = 256 * 1024 * 1024

_TOP_LEVEL_HELP = """\
usage: glio-noncode COMMAND [ARGS]...

Inspectable research hypothesis runtime.

Focused commands:
  case                 prepare and run a case from source manifests
  expression           analyze expression and allele-specific RNA evidence
  cohort-recurrence    compare a locus with callable-subject-matched controls
  geo-outlier          compare one GEO expression feature with explicit references
  geo-count-outlier    compare a gene row across a GEO supplementary count matrix
  geo-count-contrast   compare paired groups across a GEO supplementary count matrix
  geo-count-design     preflight a paired GEO count design without testing features
  geo-count-metadata   inspect GEO supplementary count-matrix sample metadata
  reference-block-query query one sample's gVCF reference-confidence intervals
  geo-qc               summarize sample coverage and matrix quality before analysis
  geo-metadata         inventory GEO sample characteristics before contrast design
  geo-design           check GEO cohort selection and contrast estimability
  geo-consistency      compare tested and FDR-significant directions across GEO contrasts
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


def _reference_block_query_main(argv: list[str]) -> int:
    """Parse one bounded gVCF/BCF input and emit a sample-specific interval query."""

    import argparse
    import gzip
    import hashlib
    import io
    import json
    from pathlib import Path

    from ._safe_persistence import atomic_write_text, read_bytes
    from .errors import GlioError
    from .intake import IntakeFormat, ReferenceBlockIndex, VariantIntake

    parser = argparse.ArgumentParser(
        prog="glio-noncode reference-block-query",
        description=(
            "partition one sample's gVCF reference-confidence intervals over a "
            "zero-based half-open interval or canonical variant span"
        ),
    )
    parser.add_argument("input", help="uncompressed/gzipped VCF or BCF file")
    parser.add_argument("--source-id", default=None)
    parser.add_argument("--format", choices=("gvcf", "bcf"), default=None)
    parser.add_argument("--genome-build", default="GRCh38")
    parser.add_argument("--sample-id", required=True)
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument(
        "--variant",
        dest="variant_notation",
        help="canonical CHROM:POS:REF>ALT or CHROM-POS-REF-ALT notation (1-based)",
    )
    query_group.add_argument(
        "--chromosome",
        help="query contig for an explicit zero-based half-open interval",
    )
    parser.add_argument("--start", type=int, default=None, help="zero-based inclusive start")
    parser.add_argument("--end", type=int, default=None, help="exclusive end")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    from .identity import parse_variant

    if args.variant_notation is None:
        if args.start is None or args.end is None:
            parser.error("--start and --end are required with --chromosome")
        query_variant = None
        query = {
            "mode": "interval",
            "coordinate_system": "zero_based_half_open",
            "genome_build": args.genome_build,
            "chromosome": args.chromosome,
            "start": args.start,
            "end": args.end,
        }
    else:
        if args.start is not None or args.end is not None:
            parser.error("--start and --end cannot be combined with --variant")
        try:
            query_variant = parse_variant(
                args.variant_notation,
                genome_build=args.genome_build,
            )
        except (GlioError, ValueError, OverflowError) as error:
            parser.error(str(error))
        query = {
            "mode": "variant_reference_span",
            "coordinate_conversion": "one_based_closed_to_zero_based_half_open",
            "variant": query_variant.to_dict(),
        }

    def write_json(payload: dict[str, Any]) -> None:
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            atomic_write_text(args.output, rendered, field="CLI JSON output path")
        else:
            sys.stdout.write(rendered)

    try:
        input_path = Path(args.input)
        input_bytes = read_bytes(
            input_path,
            field="reference-block query input",
            max_bytes=_REFERENCE_BLOCK_QUERY_MAX_SOURCE_BYTES,
        )
        input_name = input_path.name.casefold()
        is_bcf_name = input_name.endswith((".bcf", ".bcf.gz", ".bcf.bgz"))
        input_format = args.format or ("bcf" if is_bcf_name else "gvcf")
        source_id = args.source_id or input_path.name.removesuffix(".gz")
        intake_engine = VariantIntake(default_build=args.genome_build)
        if input_format == "bcf":
            batch = intake_engine.parse_bytes(
                input_bytes,
                source_id=source_id,
                genome_build=args.genome_build,
                sample_id=args.sample_id,
            )
            decoded_bytes = len(input_bytes)
        else:
            text_bytes = input_bytes
            if text_bytes.startswith(b"\x1f\x8b"):
                with gzip.GzipFile(fileobj=io.BytesIO(text_bytes), mode="rb") as compressed:
                    text_bytes = compressed.read(_REFERENCE_BLOCK_QUERY_MAX_TEXT_BYTES + 1)
                if len(text_bytes) > _REFERENCE_BLOCK_QUERY_MAX_TEXT_BYTES:
                    raise ValueError("decompressed gVCF exceeds the 256 MiB input ceiling")
            text = text_bytes.decode("utf-8")
            decoded_bytes = len(text_bytes)
            batch = intake_engine.parse_text(
                text,
                source_id=source_id,
                input_format=IntakeFormat.GVCF,
                genome_build=args.genome_build,
                sample_id=args.sample_id,
            )

        source = {
            "source_id": source_id,
            "input_format": batch.input_format.value,
            "genome_build": args.genome_build,
            "sample_id": args.sample_id,
            "compressed_or_source_bytes": len(input_bytes),
            "decoded_bytes": decoded_bytes,
            "file_sha256": f"sha256:{hashlib.sha256(input_bytes).hexdigest()}",
            "receipt_address": batch.receipt.content_address,
            "input_content_address": batch.receipt.input_hash,
            "reference_block_count": len(batch.reference_blocks),
            "reference_block_address": batch.reference_block_address,
        }
        issues = [issue.to_dict() for issue in batch.issues]
        if batch.has_errors or not batch.reference_blocks:
            report: dict[str, Any] = {
                "schema": "glio-noncode.reference-block-query.v1",
                "status": "blocked",
                "failure_code": "intake_errors" if batch.has_errors else "no_reference_blocks",
                "source": source,
                "query": query,
                "intake_issues": issues,
                "coverage": None,
            }
            write_json(report)
            return 2

        index = ReferenceBlockIndex(batch.reference_blocks)
        if query_variant is None:
            result = index.coverage(
                args.genome_build,
                args.chromosome,
                args.start,
                args.end,
                sample_id=args.sample_id,
            )
        else:
            result = index.coverage_for_variant(query_variant, sample_id=args.sample_id)
        write_json(
            {
                "schema": "glio-noncode.reference-block-query.v1",
                "status": "completed",
                "source": source,
                "query": query,
                "intake_issues": issues,
                "coverage": result.to_dict(),
            }
        )
        return 0
    except (GlioError, OSError, EOFError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


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
    if command == "reference-block-query":
        return _reference_block_query_main(command_argv)
    if command == "case":
        return importlib.import_module(f"{__package__}._cli_case").main(command_argv)
    if command == "expression":
        return importlib.import_module(f"{__package__}._cli_expression").main(command_argv)
    if command == "cohort-recurrence":
        return importlib.import_module(f"{__package__}._cli_cohort_recurrence").main(command_argv)
    if command == "geo-outlier":
        return importlib.import_module(f"{__package__}._cli_geo").main(command_argv)
    if command == "geo-count-outlier":
        return importlib.import_module(f"{__package__}._cli_geo").count_main(command_argv)
    if command == "geo-count-contrast":
        return importlib.import_module(f"{__package__}._cli_geo_count_contrast").main(command_argv)
    if command == "geo-count-design":
        return importlib.import_module(f"{__package__}._cli_geo_count_contrast").design_main(
            command_argv
        )
    if command == "geo-count-metadata":
        return importlib.import_module(f"{__package__}._cli_geo_count_metadata").main(command_argv)
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
