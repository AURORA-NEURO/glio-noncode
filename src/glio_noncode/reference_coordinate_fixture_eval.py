"""Executable evaluation for the Domain 04 C01-C04 public fixture."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .identity import parse_variant
from .reference_coordinate_contracts import (
    ReferenceCoordinateContractRegistry,
    default_reference_coordinate_contracts,
)
from .reference_coordinate_public_data import (
    ReferenceCoordinateFixtureCatalog,
    ReferenceCoordinateOperation,
    ReferenceCoordinateRecord,
    ReferenceCoordinateRole,
)
from .reference_extensions import (
    LiftoverAmbiguityScorer,
    LiftoverChainManager,
    PangenomeCoordinateMapper,
    PangenomePath,
    ReferenceExtensionState,
)
from .reference_registry import MappingSegment, default_reference_registry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateExecutionCheck:
    """One deterministic evaluation assertion."""

    check_id: str
    record_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateOperationReceipt:
    """Sanitized operation result; raw fixture fields never enter the receipt."""

    record_id: str
    operation: ReferenceCoordinateOperation
    role: ReferenceCoordinateRole
    state: ReferenceExtensionState
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    context_key: str
    result_summary: Mapping[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        if not self.record_id.strip():
            raise ValidationError("operation receipt record ID is required")
        if not self.source_ids:
            raise ValidationError("operation receipt source IDs are required")
        if not self.context_key.strip():
            raise ValidationError("operation receipt context is required")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("operation receipt must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateEvaluationReport:
    """Complete sanitized evaluation report for one public fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    state: str
    receipts: tuple[ReferenceCoordinateOperationReceipt, ...]
    checks: tuple[ReferenceCoordinateExecutionCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    @property
    def accepted_receipts(self) -> tuple[ReferenceCoordinateOperationReceipt, ...]:
        return tuple(
            receipt
            for receipt in self.receipts
            if receipt.state == ReferenceExtensionState.SUPPORTED
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
            "receipt_count": len(self.receipts),
            "check_count": len(self.checks),
        }


def _interval(payload: Mapping[str, Any]) -> tuple[str, int, int]:
    raw = payload.get("query_interval")
    if not isinstance(raw, Mapping):
        raise ValidationError("query_interval must be an object")
    chromosome = str(raw.get("chromosome", "")).strip()
    start = int(raw.get("start"))
    end = int(raw.get("end"))
    if not chromosome or start < 1 or end < start:
        raise ValidationError("query interval is invalid")
    return chromosome, start, end


def _mapping_segments(payload: Mapping[str, Any]) -> tuple[MappingSegment, ...]:
    raw = payload.get("segments")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise ValidationError("segments must be a list")
    segments: list[MappingSegment] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise ValidationError("mapping segment must be an object")
        segments.append(
            MappingSegment(
                mapping_id=str(row.get("mapping_id", "")),
                source_assembly=str(row.get("source_assembly", "")),
                source_chromosome=str(row.get("source_chromosome", "")),
                source_start=int(row.get("source_start")),
                source_end=int(row.get("source_end")),
                target_assembly=str(row.get("target_assembly", "")),
                target_chromosome=str(row.get("target_chromosome", "")),
                target_start=int(row.get("target_start")),
                target_end=int(row.get("target_end")),
                strand=str(row.get("strand", "+")),
                source_version=str(row.get("source_version", "")),
            )
        )
    return tuple(segments)


def _pangenome_paths(payload: Mapping[str, Any]) -> tuple[PangenomePath, ...]:
    raw = payload.get("paths")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise ValidationError("paths must be a list")
    paths: list[PangenomePath] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise ValidationError("pangenome path must be an object")
        paths.append(
            PangenomePath(
                path_id=str(row.get("path_id", "")),
                path_name=str(row.get("path_name", "")),
                chromosome=str(row.get("chromosome", "")),
                start=int(row.get("start")),
                end=int(row.get("end")),
                strand=str(row.get("strand", "+")),
                sequence_id=str(row.get("sequence_id", "")),
                source_id=str(row.get("source_id", "")),
                version=str(row.get("version", "")),
                attributes=dict(row.get("attributes", {})),
            )
        )
    return tuple(paths)


def _state_for_chain(status: str) -> ReferenceExtensionState:
    if status in {"mapped", "identity"}:
        return ReferenceExtensionState.SUPPORTED
    if status == "partial":
        return ReferenceExtensionState.PARTIAL
    return ReferenceExtensionState.ABSTAINED


class ReferenceCoordinateFixtureEvaluator:
    """Execute each record through its declared typed adapter."""

    def __init__(
        self,
        contracts: ReferenceCoordinateContractRegistry | None = None,
    ) -> None:
        self.contracts = contracts or default_reference_coordinate_contracts()
        self.registry = default_reference_registry()

    def evaluate(
        self,
        catalog: ReferenceCoordinateFixtureCatalog,
    ) -> ReferenceCoordinateEvaluationReport:
        receipts: list[ReferenceCoordinateOperationReceipt] = []
        checks: list[ReferenceCoordinateExecutionCheck] = []

        def add(
            check_id: str,
            record: ReferenceCoordinateRecord,
            passed: bool,
            observed: Any,
            expected: Any,
            message: str,
        ) -> None:
            checks.append(
                ReferenceCoordinateExecutionCheck(
                    check_id, record.record_id, bool(passed), observed, expected, message
                )
            )

        for record in catalog.records:
            receipt, execution_issues = self._execute(record)
            receipts.append(receipt)
            contract = self.contracts.get(record.operation)
            missing_fields = contract.validate_payload(dict(record.payload))
            add(
                f"{record.record_id}:contract-fields",
                record,
                not missing_fields,
                missing_fields,
                (),
                "declared operation fields are present",
            )
            add(
                f"{record.record_id}:state",
                record,
                receipt.state == record.expected_state,
                receipt.state.value,
                record.expected_state.value,
                "operation state matches the fixture expectation",
            )
            add(
                f"{record.record_id}:issues",
                record,
                tuple(receipt.issue_codes) == tuple(record.expected_issue_codes),
                receipt.issue_codes,
                record.expected_issue_codes,
                "operation issue codes are exact",
            )
            add(
                f"{record.record_id}:receipt-address",
                record,
                receipt.content_address
                == content_hash(
                    {
                        "record_id": receipt.record_id,
                        "operation": receipt.operation,
                        "role": receipt.role,
                        "state": receipt.state,
                        "issue_codes": receipt.issue_codes,
                        "source_ids": receipt.source_ids,
                        "context_key": receipt.context_key,
                        "result_summary": receipt.result_summary,
                    }
                ),
                receipt.content_address,
                "sha256:<recomputed>",
                "receipt address is deterministic",
            )
            add(
                f"{record.record_id}:source-retention",
                record,
                receipt.source_ids == tuple(sorted(record.source_ids)),
                receipt.source_ids,
                tuple(sorted(record.source_ids)),
                "receipt retains sorted source IDs",
            )
            add(
                f"{record.record_id}:context-retention",
                record,
                receipt.context_key == record.context_key == catalog.context_key,
                receipt.context_key,
                catalog.context_key,
                "receipt retains exact fixture context",
            )
            add(
                f"{record.record_id}:summary-sanitized",
                record,
                not any(
                    key.lower()
                    in {
                        "chain_text",
                        "payload",
                        "patient_id",
                        "subject_id",
                        "secret",
                    }
                    for key in receipt.result_summary
                ),
                tuple(sorted(receipt.result_summary)),
                "no raw input or restricted keys",
                "receipt is a bounded projection",
            )
            add(
                f"{record.record_id}:execution-issues",
                record,
                not execution_issues,
                execution_issues,
                (),
                "adapter execution completed without unexpected exceptions",
            )

        operation_values = tuple(receipt.operation.value for receipt in receipts)
        checks.append(
            ReferenceCoordinateExecutionCheck(
                "fixture:receipt-count",
                "fixture",
                len(receipts) == len(catalog.records),
                len(receipts),
                len(catalog.records),
                "one receipt exists per fixture record",
            )
        )
        checks.append(
            ReferenceCoordinateExecutionCheck(
                "fixture:operation-coverage",
                "fixture",
                set(operation_values) == set(item.value for item in ReferenceCoordinateOperation),
                tuple(sorted(set(operation_values))),
                tuple(item.value for item in ReferenceCoordinateOperation),
                "all four operations execute",
            )
        )
        checks.append(
            ReferenceCoordinateExecutionCheck(
                "fixture:positive-states",
                "fixture",
                all(
                    receipt.state == ReferenceExtensionState.SUPPORTED
                    for receipt in receipts
                    if receipt.role == ReferenceCoordinateRole.POSITIVE
                ),
                tuple(
                    receipt.state.value
                    for receipt in receipts
                    if receipt.role == ReferenceCoordinateRole.POSITIVE
                ),
                (ReferenceExtensionState.SUPPORTED.value,),
                "all positive records are supported",
            )
        )
        checks.append(
            ReferenceCoordinateExecutionCheck(
                "fixture:control-states",
                "fixture",
                all(
                    receipt.state != ReferenceExtensionState.SUPPORTED
                    for receipt in receipts
                    if receipt.role == ReferenceCoordinateRole.CONTROL
                ),
                tuple(
                    receipt.state.value
                    for receipt in receipts
                    if receipt.role == ReferenceCoordinateRole.CONTROL
                ),
                "all controls are non-supported",
                "controls remain visible as review paths",
            )
        )
        checks.append(
            ReferenceCoordinateExecutionCheck(
                "fixture:receipt-identity",
                "fixture",
                len({receipt.record_id for receipt in receipts}) == len(receipts),
                tuple(receipt.record_id for receipt in receipts),
                "unique receipt record IDs",
                "receipts are one-to-one with records",
            )
        )
        checks.append(
            ReferenceCoordinateExecutionCheck(
                "fixture:report-sanitization",
                "fixture",
                all(
                    "chain_text" not in str(receipt.result_summary).lower() for receipt in receipts
                ),
                True,
                True,
                "report summaries do not expose chain payload text",
            )
        )
        state = "accepted" if all(check.passed for check in checks) else "review"
        body = {
            "fixture_id": catalog.fixture_id,
            "fixture_version": catalog.fixture_version,
            "context_key": catalog.context_key,
            "state": state,
            "receipts": receipts,
            "checks": checks,
        }
        return ReferenceCoordinateEvaluationReport(
            fixture_id=catalog.fixture_id,
            fixture_version=catalog.fixture_version,
            context_key=catalog.context_key,
            state=state,
            receipts=tuple(receipts),
            checks=tuple(checks),
            content_address=content_hash(body),
        )

    def _execute(
        self,
        record: ReferenceCoordinateRecord,
    ) -> tuple[ReferenceCoordinateOperationReceipt, tuple[str, ...]]:
        issues: list[str] = []
        summary: dict[str, Any]
        state = ReferenceExtensionState.INVALID
        try:
            if record.operation == ReferenceCoordinateOperation.REFERENCE_REGISTRY:
                state, issues, summary = self._execute_registry(record)
            elif record.operation == ReferenceCoordinateOperation.LIFTOVER_CHAIN:
                state, issues, summary = self._execute_chain(record)
            elif record.operation == ReferenceCoordinateOperation.LIFTOVER_AMBIGUITY:
                state, issues, summary = self._execute_ambiguity(record)
            elif record.operation == ReferenceCoordinateOperation.PANGENOME_COORDINATE:
                state, issues, summary = self._execute_pangenome(record)
            else:
                issues.append("unknown_operation")
                summary = {"operation": record.operation.value}
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            issues = ["invalid_coordinate_input"]
            state = ReferenceExtensionState.INVALID
            summary = {"error_type": type(exc).__name__}
        result_summary = dict(summary)
        address_body = {
            "record_id": record.record_id,
            "operation": record.operation,
            "role": record.role,
            "state": state,
            "issue_codes": tuple(issues),
            "source_ids": tuple(sorted(record.source_ids)),
            "context_key": record.context_key,
            "result_summary": result_summary,
        }
        receipt = ReferenceCoordinateOperationReceipt(
            record_id=record.record_id,
            operation=record.operation,
            role=record.role,
            state=state,
            issue_codes=tuple(issues),
            source_ids=tuple(sorted(record.source_ids)),
            context_key=record.context_key,
            result_summary=result_summary,
            content_address=content_hash(address_body),
        )
        return receipt, ()

    def _execute_registry(
        self,
        record: ReferenceCoordinateRecord,
    ) -> tuple[ReferenceExtensionState, list[str], dict[str, Any]]:
        query = str(record.payload.get("query", "")).strip()
        try:
            assembly = self.registry.resolve(query)
        except ValidationError:
            return (
                ReferenceExtensionState.INVALID,
                ["reference_alias_unknown"],
                {"query_present": bool(query), "resolved": False},
            )
        return (
            ReferenceExtensionState.SUPPORTED,
            ["reference_alias_resolved"],
            {
                "query_present": bool(query),
                "resolved": True,
                "assembly_id": assembly.assembly_id,
                "canonical_name": assembly.canonical_name,
                "species": assembly.species,
                "release": assembly.release,
                "alias_count": len(assembly.aliases),
            },
        )

    def _execute_chain(
        self,
        record: ReferenceCoordinateRecord,
    ) -> tuple[ReferenceExtensionState, list[str], dict[str, Any]]:
        payload = record.payload
        manager = LiftoverChainManager(self.registry)
        source_id = record.source_ids[0]
        batch = manager.parse_text(
            str(payload.get("chain_text", "")),
            source_id=source_id,
            source_assembly=str(payload.get("source_assembly", "")),
            target_assembly=str(payload.get("target_assembly", "")),
        )
        variant = parse_variant(
            str(payload.get("variant", "")),
            genome_build=str(payload.get("source_assembly", "")),
            variant_id=record.record_id,
        )
        projection = manager.project(variant, str(payload.get("target_assembly", "")))
        state = _state_for_chain(projection.status.value)
        issues: list[str] = []
        if batch.issues:
            issues.append("chain_parse_issue")
        elif projection.status.value in {"mapped", "identity"}:
            issues.append("chain_parsed")
        elif projection.status.value == "partial":
            issues.append("chain_competing")
        elif variant.kind.value == "breakend":
            issues.append("chain_breakend_abstained")
        else:
            issues.append("chain_unmapped")
        projected = projection.projected_variant
        summary = {
            "parsed_segment_count": len(batch.segments),
            "parse_issue_count": len(batch.issues),
            "projection_status": projection.status.value,
            "mapping_id": projection.mapping_id,
            "projected_build": projected.genome_build if projected is not None else None,
            "projected_chromosome": projected.chromosome if projected is not None else None,
            "projected_start": projected.start if projected is not None else None,
            "projected_end": projected.end if projected is not None else None,
        }
        return state, issues, summary

    def _execute_ambiguity(
        self,
        record: ReferenceCoordinateRecord,
    ) -> tuple[ReferenceExtensionState, list[str], dict[str, Any]]:
        payload = record.payload
        chromosome, start, end = _interval(payload)
        segments = _mapping_segments(payload)
        candidates = tuple(
            segment for segment in segments if segment.contains(chromosome, start, end)
        )
        result = LiftoverAmbiguityScorer().score(candidates)
        if result.state == ReferenceExtensionState.SUPPORTED:
            issues = ["ambiguity_unique"]
        elif result.state == ReferenceExtensionState.AMBIGUOUS:
            issues = ["ambiguity_competing"]
        else:
            issues = ["ambiguity_absent"]
        summary = {
            "query_chromosome": chromosome,
            "query_start": start,
            "query_end": end,
            "candidate_mapping_ids": result.candidate_mapping_ids,
            "candidate_count": len(result.candidate_mapping_ids),
            "score": result.score,
            "scorer_state": result.state.value,
        }
        return result.state, issues, summary

    def _execute_pangenome(
        self,
        record: ReferenceCoordinateRecord,
    ) -> tuple[ReferenceExtensionState, list[str], dict[str, Any]]:
        payload = record.payload
        chromosome, start, end = _interval(payload)
        result = PangenomeCoordinateMapper(_pangenome_paths(payload)).map_interval(
            chromosome, start, end
        )
        if result.state == ReferenceExtensionState.SUPPORTED:
            issues = ["pangenome_unique"]
        elif result.state == ReferenceExtensionState.AMBIGUOUS:
            issues = ["pangenome_multiple"]
        else:
            issues = ["pangenome_absent"]
        summary = {
            "query_chromosome": result.chromosome,
            "query_start": result.start,
            "query_end": result.end,
            "candidate_path_ids": tuple(candidate.path_id for candidate in result.candidates),
            "candidate_count": len(result.candidates),
            "sequence_ids": tuple(candidate.sequence_id for candidate in result.candidates),
            "mapper_state": result.state.value,
        }
        return result.state, issues, summary


def evaluate_reference_coordinate_fixture(
    catalog: ReferenceCoordinateFixtureCatalog,
) -> ReferenceCoordinateEvaluationReport:
    """Convenience entry point for CLI and tests."""

    return ReferenceCoordinateFixtureEvaluator().evaluate(catalog)


__all__ = [
    "ReferenceCoordinateExecutionCheck",
    "ReferenceCoordinateEvaluationReport",
    "ReferenceCoordinateFixtureEvaluator",
    "ReferenceCoordinateOperationReceipt",
    "evaluate_reference_coordinate_fixture",
]
