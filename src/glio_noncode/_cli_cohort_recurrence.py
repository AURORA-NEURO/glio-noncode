"""Run a callable-subject matched recurrence summary from a bounded JSON file."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from typing import Any

from ._cli_support import read_mapping, write_json
from .cohort import (
    DEFAULT_MATCHED_CONTROL_LOCI,
    MAX_COHORT_OBSERVATIONS,
    MAX_MATCHED_CONTROL_LOCI,
    CohortObservation,
    RecurrenceModel,
)
from .errors import ValidationError

MAX_COHORT_JSON_BYTES = 128 * 1024 * 1024
INPUT_SCHEMA = "glio.cohort-observations.v1"


def _control_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("control limit must be an integer") from error
    if not 1 <= limit <= MAX_MATCHED_CONTROL_LOCI:
        raise argparse.ArgumentTypeError(
            f"control limit must be between 1 and {MAX_MATCHED_CONTROL_LOCI}"
        )
    return limit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode cohort-recurrence",
        description=(
            "Compare one target locus with callable-subject-matched control loci. "
            "Reports descriptive estimates, not p-values or clinical claims."
        ),
    )
    parser.add_argument(
        "input", metavar="OBSERVATIONS.json", help="versioned cohort observation file"
    )
    parser.add_argument(
        "--control-limit",
        type=_control_limit,
        default=DEFAULT_MATCHED_CONTROL_LOCI,
        help=(
            "maximum number of matched control loci to select "
            f"(1-{MAX_MATCHED_CONTROL_LOCI}; default: {DEFAULT_MATCHED_CONTROL_LOCI})"
        ),
    )
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    return parser


def _invalid_report(code: str) -> dict[str, Any]:
    return {
        "schema_version": "glio.cohort-recurrence-cli.v1",
        "status": "invalid",
        "error": {
            "code": code,
            "message": "The cohort input could not be validated or analyzed.",
        },
    }


def _parse_observations(document: Mapping[str, Any]) -> tuple[str, tuple[CohortObservation, ...]]:
    allowed = {"schema", "locus_id", "observations"}
    if set(document) != allowed:
        raise ValueError("cohort input must contain only schema, locus_id, and observations")
    if document["schema"] != INPUT_SCHEMA:
        raise ValueError("unsupported cohort input schema")
    locus_id = document["locus_id"]
    if type(locus_id) is not str or not locus_id.strip():
        raise ValueError("locus_id must be a non-empty string")
    rows = document["observations"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("observations must be a non-empty array")
    if len(rows) > MAX_COHORT_OBSERVATIONS:
        raise ValueError(f"observations exceeds the {MAX_COHORT_OBSERVATIONS}-row limit")
    observations = tuple(
        CohortObservation.from_dict(row) for row in rows if isinstance(row, Mapping)
    )
    if len(observations) != len(rows):
        raise ValueError("every observation must be an object")
    return locus_id.strip(), observations


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = read_mapping(
            args.input,
            "cohort input",
            max_bytes=MAX_COHORT_JSON_BYTES,
        )
        locus_id, observations = _parse_observations(document)
        result = RecurrenceModel().evaluate(
            observations,
            locus_id,
            control_limit=args.control_limit,
        )
        report = result.to_dict()
    except (OSError, KeyError, TypeError, ValueError, ValidationError):
        report = _invalid_report("invalid_or_unreadable_cohort_input")

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: cohort recurrence report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") in {"estimated", "not_estimable"} else 2


__all__ = ["INPUT_SCHEMA", "MAX_COHORT_JSON_BYTES", "build_parser", "main"]
