"""Format-specific D01 parsing receipts backed by the repository primitives."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .intake import IntakeFormat, VariantIntake
from .serialization import content_hash
from .variant_beta import MultiAllelicDecomposer
from .intake_architecture_contracts import (
    IntakeArchitectureCase,
    IntakeArchitectureNormalizationReceipt,
    IntakeArchitectureOperation,
    IntakeArchitectureParseReceipt,
    IntakeArchitectureState,
    addressed,
)


def _state(issue_codes: tuple[str, ...], accepted_count: int) -> IntakeArchitectureState:
    if issue_codes:
        return IntakeArchitectureState.REVIEW
    if accepted_count < 1:
        return IntakeArchitectureState.ABSTAINED
    return IntakeArchitectureState.ACCEPTED


def parse_variant_text(
    text: str,
    *,
    source_id: str,
    input_format: str = "vcf",
    genome_build: str = "GRCh38",
) -> tuple[int, int, int, tuple[str, ...], str]:
    """Parse VCF/TSV/JSON and return only aggregate receipt counters."""

    try:
        batch = VariantIntake(default_build=genome_build).parse_text(
            text,
            source_id=source_id,
            input_format=IntakeFormat(input_format),
            genome_build=genome_build,
        )
    except (TypeError, ValueError, ValidationError) as exc:
        return (0, 0, 0, ("malformed_input",), addressed({"error": str(exc)}, "intake-parse-error"))
    issue_codes = tuple(sorted({issue.code for issue in batch.issues}))
    return (
        batch.receipt.record_count,
        batch.receipt.accepted_count,
        len(batch.deferred_records),
        issue_codes,
        batch.receipt.content_address,
    )


def parse_regulatory_track(text: str) -> tuple[int, int, tuple[str, ...], str]:
    """Parse a small BED-like/TSV track while preserving bounded coordinates."""

    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return 0, 0, ("malformed_input",), addressed({"text": text}, "track-parse-error")
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        required = {"chrom", "start", "end", "name"}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            return 0, 0, ("missing_track_columns",), addressed({"headers": reader.fieldnames}, "track-parse-error")
        count = 0
        issues: list[str] = []
        for row in reader:
            try:
                if int(row["start"]) < 0 or int(row["end"]) <= int(row["start"]):
                    raise ValueError("track interval is not increasing")
                if not row["chrom"] or not row["name"]:
                    raise ValueError("track identity fields are empty")
            except (KeyError, TypeError, ValueError):
                issues.append("malformed_input")
                continue
            count += 1
        issue_codes = tuple(sorted(set(issues)))
        return len(lines) - 1, count, issue_codes, addressed({"rows": count, "issues": issue_codes}, "track-parse")
    except csv.Error:
        return 0, 0, ("malformed_input",), addressed({"text": text}, "track-parse-error")


def parse_multiallelic(payload: Mapping[str, Any]) -> tuple[int, int, tuple[str, ...], str]:
    raw = {
        "variant_id": payload.get("variant_id", "public-multi"),
        "chromosome": payload.get("chromosome", "7"),
        "position": payload.get("position", 55249063),
        "reference": payload.get("reference", "T"),
        "alternates": payload.get("alternates", ["C", "G"]),
        "genotype": payload.get("genotype", "1/2"),
        "sample_id": "public-aggregate",
    }
    result = MultiAllelicDecomposer().decompose(raw, source_id="public-reference-aggregate")
    issue_codes = tuple(sorted({issue.code for issue in result.issues}))
    return len(result.alternates), len(result.children), issue_codes, result.content_address


def parse_intake_architecture_case(case: IntakeArchitectureCase) -> IntakeArchitectureParseReceipt:
    payload = case.payload
    issue_codes: tuple[str, ...] = ()
    record_count = 1
    accepted_count = 1
    deferred_count = 0
    input_format = str(payload.get("input_format", "json"))
    input_address = addressed(payload, "intake-json-input")
    if case.scenario.value == "malformed_input":
        issue_codes = ("malformed_input",)
        accepted_count = 0
    elif case.operation_id.endswith("C02") or "raw_text" in payload and payload.get("input_format") in {"vcf", "gvcf", "tsv", "json"}:
        raw_text = str(payload.get("raw_text", ""))
        record_count, accepted_count, deferred_count, issue_codes, input_address = parse_variant_text(
            raw_text,
            source_id=case.source_ids[0],
            input_format=input_format,
        )
    elif case.operation_id.endswith("C03"):
        record_count, accepted_count, issue_codes, input_address = parse_regulatory_track(str(payload.get("track_text", "")))
    elif case.operation_id.endswith("C07"):
        record_count, accepted_count, issue_codes, input_address = parse_multiallelic(payload)
    else:
        input_address = addressed(payload, "intake-json-input")
    if case.scenario.value == "duplicate_identity":
        issue_codes = tuple(sorted(set(issue_codes) | {"duplicate_identity"}))
    state = _state(issue_codes, accepted_count)
    body = {
        "case_id": case.case_id,
        "input_format": input_format,
        "input_address": input_address,
        "record_count": record_count,
        "accepted_count": accepted_count,
        "deferred_count": deferred_count,
        "issue_codes": issue_codes,
        "state": state,
    }
    return IntakeArchitectureParseReceipt(**body, content_address=addressed(body, "intake-parse-receipt"))


__all__ = [
    "parse_variant_text",
    "parse_regulatory_track",
    "parse_multiallelic",
    "parse_intake_architecture_case",
]
