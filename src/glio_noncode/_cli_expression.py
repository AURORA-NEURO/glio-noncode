"""Lightweight command surface for matched-tumour RNA evidence."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from ._cli_support import (
    DEFAULT_MAX_JSON_BYTES,
)
from ._cli_support import (
    read_mapping as _read_mapping,
)
from ._cli_support import (
    write_json as _write_json,
)

MAX_JSON_BYTES = DEFAULT_MAX_JSON_BYTES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode expression",
        description="Matched-tumour expression and allelic consequence evidence",
    )
    commands = parser.add_subparsers(dest="expression_command", required=True)

    outlier = commands.add_parser(
        "outlier", help="compare one expression observation with a matched reference batch"
    )
    outlier.add_argument("--target", required=True)
    outlier.add_argument("--references", required=True)
    outlier.add_argument("--expected-direction", choices=("gain", "loss", "unknown"))
    outlier.add_argument("--context-key")
    outlier.add_argument("--output", default="-")

    allelic = commands.add_parser(
        "allelic", help="run one phase- and baseline-gated exact allelic test"
    )
    allelic.add_argument("--input", required=True)
    allelic.add_argument("--expected-direction", choices=("gain", "loss", "unknown"))
    allelic.add_argument("--context-key")
    allelic.add_argument("--output", default="-")

    batch = commands.add_parser(
        "allelic-batch", help="run exact allelic tests with BH adjustment"
    )
    batch.add_argument("--input", required=True)
    batch.add_argument(
        "--expected-directions",
        help="JSON object mapping variant or feature IDs to gain, loss, or unknown",
    )
    batch.add_argument("--context-key")
    batch.add_argument("--output", default="-")

    integrate = commands.add_parser(
        "integrate", help="join a regulatory prediction to matched RNA results"
    )
    integrate.add_argument("--prediction", required=True)
    integrate.add_argument("--expression-result")
    integrate.add_argument("--allelic-result")
    integrate.add_argument("--output", default="-")

    claim = commands.add_parser(
        "claim", help="derive one native element-to-gene claim from an RNA consequence"
    )
    claim.add_argument("--evidence", required=True)
    claim.add_argument("--target", required=True)
    claim.add_argument("--output", default="-")

    claim_batch = commands.add_parser(
        "claim-batch", help="match RNA consequences to explicit element-gene targets"
    )
    claim_batch.add_argument("--input", required=True)
    claim_batch.add_argument("--output", default="-")

    schema = commands.add_parser("schema", help="print the RNA evidence schema")
    schema.add_argument("--include-private", action="store_true")
    schema.add_argument("--output", default="-")

    capabilities = commands.add_parser(
        "capabilities", help="print the RNA evidence capability declaration"
    )
    capabilities.add_argument("--output", default="-")

    claims_schema = commands.add_parser(
        "claims-schema", help="print the native RNA claim bridge schema"
    )
    claims_schema.add_argument("--output", default="-")

    claims_capabilities = commands.add_parser(
        "claims-capabilities", help="print the native RNA claim bridge capabilities"
    )
    claims_capabilities.add_argument("--output", default="-")
    return parser


def _batch_payload(results: Sequence[object]) -> dict[str, Any]:
    from .serialization import content_hash

    body: dict[str, Any] = {
        "schema_version": "1.0.0",
        "result_count": len(results),
        "results": [item.to_dict() for item in results],
    }
    return body | {"content_address": content_hash(body, prefix="allelic-imbalance-batch")}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from .errors import ValidationError
        from .expression_claims import (
            RNAElementGeneTarget,
            expression_claims_capabilities,
            expression_claims_schema,
            match_rna_consequences,
            rna_consequence_to_claim,
        )
        from .expression_claims import (
            public_projection as expression_claim_public_projection,
        )
        from .expression_evidence import (
            AllelicCountBatch,
            AllelicCountObservation,
            AllelicImbalanceAnalyzer,
            AllelicImbalanceResult,
            ExpressionBatch,
            ExpressionObservation,
            ExpressionOutlierResult,
            PredictedRegulatoryEffect,
            RNAConsequenceEvidence,
            RNAConsequenceIntegrator,
            RobustExpressionOutlierAnalyzer,
            expression_evidence_capabilities,
            expression_evidence_schema,
        )

        if args.expression_command == "outlier":
            result = RobustExpressionOutlierAnalyzer().analyze(
                ExpressionObservation.from_mapping(_read_mapping(args.target, "target")),
                ExpressionBatch.from_mapping(_read_mapping(args.references, "references")),
                expected_direction=args.expected_direction,
                expected_context_key=args.context_key,
            )
            _write_json(result.public_projection(), args.output)
            return 0
        if args.expression_command == "allelic":
            result = AllelicImbalanceAnalyzer().analyze(
                AllelicCountObservation.from_mapping(_read_mapping(args.input, "allelic input")),
                expected_direction=args.expected_direction,
                expected_context_key=args.context_key,
            )
            _write_json(result.public_projection(), args.output)
            return 0
        if args.expression_command == "allelic-batch":
            directions: Mapping[str, str] | None = None
            if args.expected_directions:
                raw_directions = _read_mapping(
                    args.expected_directions, "expected directions"
                )
                if any(not isinstance(value, str) for value in raw_directions.values()):
                    raise ValueError("expected direction values must be strings")
                directions = {str(key): str(value) for key, value in raw_directions.items()}
            results = AllelicImbalanceAnalyzer().analyze_batch(
                AllelicCountBatch.from_mapping(_read_mapping(args.input, "allelic batch")),
                expected_directions=directions,
                expected_context_key=args.context_key,
            )
            _write_json(_batch_payload(results), args.output)
            return 0
        if args.expression_command == "integrate":
            expression = (
                None
                if args.expression_result is None
                else ExpressionOutlierResult.from_mapping(
                    _read_mapping(args.expression_result, "expression result")
                )
            )
            allelic = (
                None
                if args.allelic_result is None
                else AllelicImbalanceResult.from_mapping(
                    _read_mapping(args.allelic_result, "allelic result")
                )
            )
            result = RNAConsequenceIntegrator().integrate(
                PredictedRegulatoryEffect.from_mapping(
                    _read_mapping(args.prediction, "prediction")
                ),
                expression=expression,
                allelic=allelic,
            )
            _write_json(result.public_projection(), args.output)
            return 0
        if args.expression_command == "claim":
            claim = rna_consequence_to_claim(
                RNAConsequenceEvidence.from_mapping(
                    _read_mapping(args.evidence, "RNA consequence")
                ),
                RNAElementGeneTarget.from_mapping(
                    _read_mapping(args.target, "element-gene target")
                ),
            )
            _write_json(expression_claim_public_projection(claim), args.output)
            return 0
        if args.expression_command == "claim-batch":
            request = _read_mapping(args.input, "RNA claim batch request")
            unknown = set(request) - {"evidence", "targets", "require_complete"}
            if unknown:
                raise ValueError(
                    f"RNA claim batch request contains unknown fields: {sorted(unknown)}"
                )
            evidence_raw = request.get("evidence")
            targets_raw = request.get("targets")
            require_complete = request.get("require_complete", False)
            if not isinstance(evidence_raw, Sequence) or isinstance(
                evidence_raw, (str, bytes, bytearray)
            ):
                raise ValueError("RNA claim batch evidence must be an array")
            if not isinstance(targets_raw, Sequence) or isinstance(
                targets_raw, (str, bytes, bytearray)
            ):
                raise ValueError("RNA claim batch targets must be an array")
            if type(require_complete) is not bool:
                raise ValueError("require_complete must be a boolean")
            if any(not isinstance(item, Mapping) for item in evidence_raw):
                raise ValueError("every RNA consequence must be an object")
            if any(not isinstance(item, Mapping) for item in targets_raw):
                raise ValueError("every element-gene target must be an object")
            result = match_rna_consequences(
                tuple(RNAConsequenceEvidence.from_mapping(item) for item in evidence_raw),
                tuple(RNAElementGeneTarget.from_mapping(item) for item in targets_raw),
                require_complete=require_complete,
            )
            _write_json(result.public_projection(), args.output)
            return 0
        if args.expression_command == "schema":
            _write_json(
                expression_evidence_schema(public=not args.include_private), args.output
            )
            return 0
        if args.expression_command == "capabilities":
            _write_json(expression_evidence_capabilities(), args.output)
            return 0
        if args.expression_command == "claims-schema":
            _write_json(expression_claims_schema(), args.output)
            return 0
        if args.expression_command == "claims-capabilities":
            _write_json(expression_claims_capabilities(), args.output)
            return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


__all__ = ["MAX_JSON_BYTES", "build_parser", "main"]
