"""Lightweight command surface for deterministic case preparation and execution."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from ._cli_support import read_json, read_mapping, write_json

_PREPARE_FIELDS = frozenset(
    {
        "case_id",
        "subject_id",
        "context",
        "variant_source",
        "regulatory_tracks",
        "tracks",
        "metadata",
        "requested_by",
        "live_reference",
    }
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode case",
        description="Prepare and execute a fail-closed noncoding case workflow",
    )
    commands = parser.add_subparsers(dest="case_command", required=True)

    prepare = commands.add_parser(
        "prepare", help="build a canonical case manifest from inline source payloads"
    )
    prepare.add_argument("--request", required=True, help="request JSON path or - for stdin")
    prepare.add_argument("--summary", action="store_true")
    prepare.add_argument("--output", default="-")

    run = commands.add_parser(
        "run", help="execute an accepted prepared case and verify persisted replay"
    )
    run.add_argument("--prepared", required=True, help="prepared-case JSON path or -")
    run.add_argument(
        "--rna-consequences",
        help="optional JSON array of canonical RNA consequence evidence",
    )
    run.add_argument("--data-root", default=".glio")
    run.add_argument("--summary", action="store_true")
    run.add_argument("--output", default="-")

    schema = commands.add_parser("schema", help="print one case-workflow schema")
    schema.add_argument(
        "--component",
        choices=(
            "workflow",
            "prepare-request",
            "run-request",
            "variant-source",
            "regulatory-track",
            "prepared",
            "run-result",
        ),
        default="workflow",
    )
    schema.add_argument("--output", default="-")

    capabilities = commands.add_parser(
        "capabilities", help="print the case-workflow capability declaration"
    )
    capabilities.add_argument("--output", default="-")
    return parser


def _prepare_request(raw: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(raw) - _PREPARE_FIELDS
    if unknown:
        raise ValueError(f"case preparation request contains unknown fields: {sorted(unknown)}")
    required = {"case_id", "subject_id", "context", "variant_source"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"case preparation request is missing fields: {sorted(missing)}")
    if "tracks" in raw and "regulatory_tracks" in raw:
        raise ValueError("use tracks or regulatory_tracks, not both")
    return dict(raw)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from .case_workflow import (
            PreparedCase,
            capabilities,
            case_workflow_schema,
            prepare_case,
            prepare_request_schema,
            prepared_case_schema,
            regulatory_track_source_schema,
            run_case,
            run_request_schema,
            run_result_schema,
            variant_source_schema,
        )
        from .errors import ValidationError

        if args.case_command == "prepare":
            request = _prepare_request(read_mapping(args.request, "case request"))
            result = prepare_case(**request)
            write_json(result.public_summary() if args.summary else result.to_dict(), args.output)
            return 0 if result.accepted else 2
        if args.case_command == "run":
            prepared = PreparedCase.from_mapping(
                read_mapping(args.prepared, "prepared case")
            )
            rna_consequences: Sequence[Mapping[str, Any]] = ()
            if args.rna_consequences is not None:
                raw_rna = read_json(args.rna_consequences, "RNA consequences")
                if not isinstance(raw_rna, Sequence) or isinstance(
                    raw_rna, (str, bytes, bytearray)
                ):
                    raise ValueError("RNA consequences must be a JSON array")
                if any(not isinstance(item, Mapping) for item in raw_rna):
                    raise ValueError("every RNA consequence must be a JSON object")
                rna_consequences = raw_rna
            result = run_case(
                prepared,
                data_root=args.data_root,
                rna_consequences=rna_consequences,
            )
            write_json(result.public_summary() if args.summary else result.to_dict(), args.output)
            return 0 if result.accepted else 2
        if args.case_command == "schema":
            factories = {
                "workflow": case_workflow_schema,
                "prepare-request": prepare_request_schema,
                "run-request": run_request_schema,
                "variant-source": variant_source_schema,
                "regulatory-track": regulatory_track_source_schema,
                "prepared": prepared_case_schema,
                "run-result": run_result_schema,
            }
            write_json(factories[args.component](), args.output)
            return 0
        if args.case_command == "capabilities":
            write_json(capabilities(), args.output)
            return 0
    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


__all__ = ["build_parser", "main"]
