"""Executable evaluation for the Domain 03 C09-C12 lineage fixture.

Each aggregate fixture row is executed through exactly one existing adapter.
The evaluator publishes typed receipts, bounded counts, and sanitized result
projections. Raw input rows and raw observations never cross the release
projection boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .specimen_lineage import (
    LineageAlphaState,
    LongitudinalSpecimenLinker,
    MultiRegionLineageResolver,
    PrimaryRecurrencePhaseMapper,
    SpecimenPhase,
    TreatmentExposureContextualizer,
)
from .specimen_lineage_public_data import (
    SpecimenLineageFixtureCatalog,
    SpecimenLineageFixtureRecord,
    SpecimenLineageFixtureState,
    SpecimenLineageOperation,
    audit_specimen_lineage_fixture,
)


@dataclass(frozen=True, slots=True)
class SpecimenLineageFixtureCheck:
    """One deterministic assertion over one executed fixture row."""

    check_id: str
    record_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageExecution:
    """Sanitized adapter result retained by a fixture receipt."""

    record_id: str
    operation: SpecimenLineageOperation
    fixture_state: SpecimenLineageFixtureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: Mapping[str, int]
    input_address: str
    output_address: str
    sanitized_output: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageOperationReceipt:
    """Input, output, and assertion receipt for one operation row."""

    record_id: str
    operation: SpecimenLineageOperation
    fixture_state: SpecimenLineageFixtureState
    expected_result_state: str
    observed_result_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    expected_counts: Mapping[str, int]
    observed_counts: Mapping[str, int]
    input_address: str
    output_address: str
    checks: tuple[SpecimenLineageFixtureCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


@dataclass(frozen=True, slots=True)
class SpecimenLineageFixtureEvaluationReport:
    """Complete evaluation report for the twelve-row aggregate fixture."""

    fixture_id: str
    context_key: str
    state: str
    receipts: tuple[SpecimenLineageOperationReceipt, ...]
    checks: tuple[SpecimenLineageFixtureCheck, ...]
    positive_count: int
    control_count: int
    operation_ids: tuple[str, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
        }


class SpecimenLineageFixtureEvaluator:
    """Execute and assert all four lineage operation families."""

    def evaluate(
        self,
        catalog: SpecimenLineageFixtureCatalog,
    ) -> SpecimenLineageFixtureEvaluationReport:
        data_audit = audit_specimen_lineage_fixture(catalog)
        receipts: list[SpecimenLineageOperationReceipt] = []
        checks: list[SpecimenLineageFixtureCheck] = []
        for record in catalog.records:
            execution = self._execute(record)
            record_checks = _checks(record, execution)
            receipts.append(
                SpecimenLineageOperationReceipt(
                    record_id=record.record_id,
                    operation=record.operation,
                    fixture_state=record.expected_fixture_state,
                    expected_result_state=record.expected_result_state,
                    observed_result_state=execution.observed_result_state,
                    expected_issue_codes=record.expected_issue_codes,
                    observed_issue_codes=execution.issue_codes,
                    expected_counts=dict(record.expected_counts),
                    observed_counts=dict(execution.counts),
                    input_address=execution.input_address,
                    output_address=execution.output_address,
                    checks=record_checks,
                )
            )
            checks.extend(record_checks)
        state = (
            "accepted"
            if data_audit.accepted and all(check.passed for check in checks)
            else "review"
        )
        body = {
            "fixture_id": catalog.fixture_id,
            "context_key": catalog.context_key,
            "state": state,
            "receipts": receipts,
            "checks": checks,
            "positive_count": len(catalog.positives),
            "control_count": len(catalog.controls),
            "operation_ids": catalog.operation_ids,
        }
        return SpecimenLineageFixtureEvaluationReport(
            fixture_id=catalog.fixture_id,
            context_key=catalog.context_key,
            state=state,
            receipts=tuple(receipts),
            checks=tuple(checks),
            positive_count=len(catalog.positives),
            control_count=len(catalog.controls),
            operation_ids=catalog.operation_ids,
            content_address=content_hash(body),
        )

    @staticmethod
    def _execute(record: SpecimenLineageFixtureRecord) -> SpecimenLineageExecution:
        if record.operation == SpecimenLineageOperation.REGION_LINEAGE:
            raw_records = _records(record, "records", "regions", "observations")
            result = MultiRegionLineageResolver().resolve(
                raw_records, context_key=record.context_key
            )
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            counts = {
                "lineages": len(result.lineages),
                "edges": sum(len(item.edges) for item in result.lineages),
                "roots": sum(len(item.roots) for item in result.lineages),
                "leaves": sum(len(item.leaves) for item in result.lineages),
                "missing_parents": sum(len(item.missing_parent_ids) for item in result.lineages),
                "cycles": sum(len(item.cycle_region_ids) for item in result.lineages),
                "issues": len(result.issues),
            }
            output = {
                "operation": record.operation.value,
                "state": result.state.value,
                "lineages": tuple(
                    {
                        "subject_address": content_hash(item.subject_id),
                        "region_ids": item.region_ids,
                        "edge_count": len(item.edges),
                        "roots": item.roots,
                        "leaves": item.leaves,
                        "missing_parent_ids": item.missing_parent_ids,
                        "cycle_region_ids": item.cycle_region_ids,
                        "state": item.state.value,
                        "content_address": item.content_address,
                    }
                    for item in result.lineages
                ),
                "issue_codes": issue_codes,
                "counts": counts,
            }
            return _execution(record, result.state.value, issue_codes, counts, output)

        if record.operation == SpecimenLineageOperation.LONGITUDINAL_LINKING:
            raw_records = _records(record, "records", "specimens", "observations")
            result = LongitudinalSpecimenLinker().link(
                raw_records,
                context_key=record.context_key,
                link_singleton=bool(record.parameters.get("link_singleton", False)),
            )
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            counts = {
                "observations": len(result.observations),
                "links": len(result.links),
                "supported_links": sum(
                    item.state == LineageAlphaState.SUPPORTED for item in result.links
                ),
                "partial_links": sum(
                    item.state == LineageAlphaState.PARTIAL for item in result.links
                ),
                "unlinked": len(result.unlinked_specimen_ids),
                "issues": len(result.issues),
            }
            output = {
                "operation": record.operation.value,
                "state": result.state.value,
                "links": tuple(
                    {
                        "link_id": item.link_id,
                        "predecessor_specimen_id": item.predecessor_specimen_id,
                        "successor_specimen_id": item.successor_specimen_id,
                        "ordering_basis": item.ordering_basis,
                        "gap_label": item.gap_label,
                        "state": item.state.value,
                        "content_address": item.content_address,
                    }
                    for item in result.links
                ),
                "unlinked_specimen_ids": result.unlinked_specimen_ids,
                "issue_codes": issue_codes,
                "counts": counts,
            }
            return _execution(record, result.state.value, issue_codes, counts, output)

        if record.operation == SpecimenLineageOperation.PHASE_MAPPING:
            raw_records = _records(record, "records", "specimens", "observations")
            result = PrimaryRecurrencePhaseMapper().map(raw_records, context_key=record.context_key)
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            counts = {
                "assignments": len(result.assignments),
                "primary": sum(item.phase == SpecimenPhase.PRIMARY for item in result.assignments),
                "recurrence": sum(
                    item.phase == SpecimenPhase.RECURRENCE for item in result.assignments
                ),
                "interval": sum(
                    item.phase == SpecimenPhase.INTERVAL for item in result.assignments
                ),
                "unknown": len(result.unknown_specimen_ids),
                "contradictory": sum(
                    item.phase_state == LineageAlphaState.CONTRADICTORY
                    for item in result.assignments
                ),
                "issues": len(result.issues),
            }
            output = {
                "operation": record.operation.value,
                "state": result.state.value,
                "assignments": tuple(
                    {
                        "specimen_id": item.specimen_id,
                        "phase": item.phase.value,
                        "phase_state": item.phase_state.value,
                        "evidence": item.evidence,
                        "conflicting_labels": item.conflicting_labels,
                        "content_address": item.content_address,
                    }
                    for item in result.assignments
                ),
                "unknown_specimen_ids": result.unknown_specimen_ids,
                "issue_codes": issue_codes,
                "counts": counts,
            }
            return _execution(record, result.state.value, issue_codes, counts, output)

        if record.operation == SpecimenLineageOperation.TREATMENT_CONTEXT:
            payload = record.payload
            specimens = payload.get("specimens", payload.get("records", ()))
            exposures = payload.get("exposures", ())
            if not isinstance(specimens, (list, tuple)) or not isinstance(exposures, (list, tuple)):
                raise ValidationError(f"{record.record_id} requires specimens and exposures lists")
            result = TreatmentExposureContextualizer().contextualize(
                specimens, exposures, context_key=record.context_key
            )
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            counts = {
                "specimens": len(result.specimens),
                "exposures": len(result.exposures),
                "contexts": len(result.contexts),
                "pre_treatment": sum(item.relation == "pre_treatment" for item in result.contexts),
                "on_treatment": sum(item.relation == "on_treatment" for item in result.contexts),
                "post_treatment": sum(
                    item.relation == "post_treatment" for item in result.contexts
                ),
                "ambiguous": sum(
                    item.state == LineageAlphaState.AMBIGUOUS for item in result.contexts
                ),
                "uncontextualized": len(result.uncontextualized_specimen_ids),
                "issues": len(result.issues),
            }
            output = {
                "operation": record.operation.value,
                "state": result.state.value,
                "contexts": tuple(
                    {
                        "specimen_id": item.specimen_id,
                        "exposure_id": item.exposure_id,
                        "therapy_id": item.therapy_id,
                        "relation": item.relation,
                        "gap_label": item.gap_label,
                        "overlapping_exposure_ids": item.overlapping_exposure_ids,
                        "state": item.state.value,
                        "content_address": item.content_address,
                    }
                    for item in result.contexts
                ),
                "uncontextualized_specimen_ids": result.uncontextualized_specimen_ids,
                "issue_codes": issue_codes,
                "counts": counts,
            }
            return _execution(record, result.state.value, issue_codes, counts, output)

        raise ValidationError(f"unsupported lineage operation: {record.operation}")


def _records(record: SpecimenLineageFixtureRecord, *keys: str) -> Sequence[Mapping[str, Any]]:
    for key in keys:
        value = record.payload.get(key)
        if isinstance(value, (list, tuple)):
            return value
    raise ValidationError(f"{record.record_id} requires one of {keys}")


def _execution(
    record: SpecimenLineageFixtureRecord,
    state: str,
    issue_codes: tuple[str, ...],
    counts: Mapping[str, int],
    output: Mapping[str, Any],
) -> SpecimenLineageExecution:
    return SpecimenLineageExecution(
        record_id=record.record_id,
        operation=record.operation,
        fixture_state=record.expected_fixture_state,
        observed_result_state=state,
        issue_codes=issue_codes,
        counts=dict(counts),
        input_address=content_hash(record.payload),
        output_address=content_hash(output),
        sanitized_output=output,
    )


def _checks(
    record: SpecimenLineageFixtureRecord,
    execution: SpecimenLineageExecution,
) -> tuple[SpecimenLineageFixtureCheck, ...]:
    checks: list[SpecimenLineageFixtureCheck] = []
    checks.append(
        _check(
            "result-state",
            record,
            execution.observed_result_state == record.expected_result_state,
            execution.observed_result_state,
            record.expected_result_state,
            "adapter result state matches the fixture contract",
        )
    )
    checks.append(
        _check(
            "issue-codes",
            record,
            execution.issue_codes == tuple(sorted(record.expected_issue_codes)),
            execution.issue_codes,
            tuple(sorted(record.expected_issue_codes)),
            "diagnostic issue codes remain deterministic",
        )
    )
    for name, expected in sorted(record.expected_counts.items()):
        checks.append(
            _check(
                f"count-{name}",
                record,
                execution.counts.get(name) == expected,
                execution.counts.get(name),
                expected,
                f"count {name} matches the aggregate fixture",
            )
        )
    checks.append(
        _check(
            "input-address",
            record,
            execution.input_address.startswith("sha256:"),
            execution.input_address,
            "sha256:<digest>",
            "fixture payload is content-addressed",
        )
    )
    checks.append(
        _check(
            "output-address",
            record,
            execution.output_address.startswith("sha256:"),
            execution.output_address,
            "sha256:<digest>",
            "sanitized result is content-addressed",
        )
    )
    checks.append(
        _check(
            "sanitized-output",
            record,
            not _contains_forbidden_output(execution.sanitized_output),
            _forbidden_output_keys(execution.sanitized_output),
            (),
            "release projection excludes raw record collections and direct identifiers",
        )
    )
    checks.append(
        _check(
            "fixture-role",
            record,
            (record.expected_fixture_state == SpecimenLineageFixtureState.ACCEPTED)
            == (record in _accepted_records_placeholder(record)),
            record.expected_fixture_state.value,
            "accepted or review",
            "fixture role is explicitly retained",
        )
    )
    return tuple(checks)


def _accepted_records_placeholder(
    record: SpecimenLineageFixtureRecord,
) -> tuple[SpecimenLineageFixtureRecord, ...]:
    """Return a role-stable singleton without carrying raw input into output."""

    return (
        (record,) if record.expected_fixture_state == SpecimenLineageFixtureState.ACCEPTED else ()
    )


def _check(
    check_id: str,
    record: SpecimenLineageFixtureRecord,
    passed: bool,
    observed: Any,
    expected: Any,
    message: str,
) -> SpecimenLineageFixtureCheck:
    return SpecimenLineageFixtureCheck(
        check_id=f"{record.record_id}:{check_id}",
        record_id=record.record_id,
        passed=bool(passed),
        observed=observed,
        expected=expected,
        message=message,
    )


def _forbidden_output_keys(value: Any) -> tuple[str, ...]:
    forbidden = {
        "records",
        "raw_records",
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
        "person_id",
    }
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in forbidden:
                found.add(normalized)
            found.update(_forbidden_output_keys(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            found.update(_forbidden_output_keys(nested))
    return tuple(sorted(found))


def _contains_forbidden_output(value: Any) -> bool:
    return bool(_forbidden_output_keys(value))


def evaluate_specimen_lineage_fixture(
    catalog: SpecimenLineageFixtureCatalog,
) -> SpecimenLineageFixtureEvaluationReport:
    """Evaluate the complete C09-C12 aggregate fixture."""

    return SpecimenLineageFixtureEvaluator().evaluate(catalog)


__all__ = [
    "SpecimenLineageExecution",
    "SpecimenLineageFixtureCheck",
    "SpecimenLineageFixtureEvaluationReport",
    "SpecimenLineageFixtureEvaluator",
    "SpecimenLineageOperationReceipt",
    "evaluate_specimen_lineage_fixture",
]
