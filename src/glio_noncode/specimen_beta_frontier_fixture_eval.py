"""Deterministic execution and assertion layer for C05-C08 fixtures."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .models import VariantOrigin
from .serialization import content_hash, jsonable
from .specimen_beta import (
    CancerCellFractionEstimator,
    MosaicismPosteriorEstimator,
    SomaticGermlineOriginClassifier,
    SpecimenBetaState,
    SubcloneAssigner,
)
from .specimen_beta_frontier_public_data import (
    SpecimenBetaFrontierFixtureCatalog,
    SpecimenBetaFrontierFixtureRecord,
    SpecimenBetaFrontierFixtureState,
    SpecimenBetaFrontierOperation,
    audit_specimen_beta_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierFixtureCheck:
    """One deterministic assertion over an executed record."""

    check_id: str
    record_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierExecution:
    """Sanitized adapter result used by the fixture and release gates."""

    record_id: str
    operation: SpecimenBetaFrontierOperation
    fixture_state: SpecimenBetaFrontierFixtureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: Mapping[str, int]
    input_address: str
    output_address: str
    sanitized_output: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierOperationReceipt:
    """Receipt joining one input record, result, and six checks."""

    record_id: str
    operation: SpecimenBetaFrontierOperation
    fixture_state: SpecimenBetaFrontierFixtureState
    expected_result_state: str
    observed_result_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    expected_counts: Mapping[str, int]
    observed_counts: Mapping[str, int]
    input_address: str
    output_address: str
    checks: tuple[SpecimenBetaFrontierFixtureCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierFixtureEvaluationReport:
    """Complete evaluation report for the twelve-record aggregate fixture."""

    fixture_id: str
    context_key: str
    state: str
    receipts: tuple[SpecimenBetaFrontierOperationReceipt, ...]
    checks: tuple[SpecimenBetaFrontierFixtureCheck, ...]
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


class SpecimenBetaFrontierFixtureEvaluator:
    """Execute each beta adapter and compare it with its declared contract."""

    def evaluate(
        self,
        catalog: SpecimenBetaFrontierFixtureCatalog,
    ) -> SpecimenBetaFrontierFixtureEvaluationReport:
        data_audit = audit_specimen_beta_frontier_fixture(catalog)
        receipts: list[SpecimenBetaFrontierOperationReceipt] = []
        checks: list[SpecimenBetaFrontierFixtureCheck] = []
        for record in catalog.records:
            execution = self._execute(record)
            record_checks = _checks(record, execution)
            receipts.append(
                SpecimenBetaFrontierOperationReceipt(
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
        return SpecimenBetaFrontierFixtureEvaluationReport(
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
    def _execute(record: SpecimenBetaFrontierFixtureRecord) -> SpecimenBetaFrontierExecution:
        raw_records = record.payload.get("records", ())
        if not isinstance(raw_records, (list, tuple)):
            raise ValidationError(f"{record.record_id} records payload must be a sequence")
        parameters = dict(record.parameters)
        if record.operation == SpecimenBetaFrontierOperation.ORIGIN:
            result = SomaticGermlineOriginClassifier().classify(raw_records, **parameters)
            classifications = tuple(result.classifications)
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            counts = {
                "classifications": len(classifications),
                "somatic": sum(item.origin == VariantOrigin.SOMATIC for item in classifications),
                "germline": sum(item.origin == VariantOrigin.GERMLINE for item in classifications),
                "uncertain": sum(
                    item.origin == VariantOrigin.UNCERTAIN for item in classifications
                ),
                "issues": len(result.issues),
            }
            output = {
                "operation": record.operation.value,
                "state": result.state.value,
                "classifications": tuple(
                    {
                        "variant_id": item.variant_id,
                        "origin": item.origin.value,
                        "state": item.state.value,
                        "somatic_score": item.somatic_score,
                        "germline_score": item.germline_score,
                        "evidence_channels": item.evidence_channels,
                        "conflicting_observation_ids": item.conflicting_observation_ids,
                        "content_address": item.content_address,
                    }
                    for item in classifications
                ),
                "issue_codes": issue_codes,
                "counts": counts,
            }
            return _execution(record, result.state.value, issue_codes, counts, output)

        if record.operation == SpecimenBetaFrontierOperation.MOSAICISM:
            result = MosaicismPosteriorEstimator().estimate(raw_records, **parameters)
            estimates = tuple(result.estimates)
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            counts = {
                "estimates": len(estimates),
                "supporting_tissues": sum(len(item.supporting_tissues) for item in estimates),
                "low_fraction_observations": sum(
                    len(item.low_fraction_observations) for item in estimates
                ),
                "contamination_flags": sum(len(item.contamination_flags) for item in estimates),
                "issues": len(result.issues),
            }
            output = {
                "operation": record.operation.value,
                "state": result.state.value,
                "estimates": tuple(
                    {
                        "variant_id": item.variant_id,
                        "posterior_estimate": item.posterior_estimate,
                        "calibrated": item.calibrated,
                        "calibration_id": item.calibration_id,
                        "supporting_tissues": item.supporting_tissues,
                        "low_fraction_observations": item.low_fraction_observations,
                        "contamination_flags": item.contamination_flags,
                        "state": item.state.value,
                        "uncertainty": item.uncertainty,
                        "content_address": item.content_address,
                    }
                    for item in estimates
                ),
                "issue_codes": issue_codes,
                "counts": counts,
            }
            return _execution(record, result.state.value, issue_codes, counts, output)

        if record.operation == SpecimenBetaFrontierOperation.CANCER_CELL_FRACTION:
            result = CancerCellFractionEstimator().estimate(raw_records, **parameters)
            estimates = tuple(result.estimates)
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            counts = {
                "estimates": len(estimates),
                "supported": sum(item.state == SpecimenBetaState.SUPPORTED for item in estimates),
                "partial": sum(item.state == SpecimenBetaState.PARTIAL for item in estimates),
                "abstained": sum(item.state == SpecimenBetaState.ABSTAINED for item in estimates),
                "issues": len(result.issues),
            }
            output = {
                "operation": record.operation.value,
                "state": result.state.value,
                "estimates": tuple(
                    {
                        "variant_id": item.variant_id,
                        "sample_id": item.sample_id,
                        "estimated_ccf": item.estimated_ccf,
                        "raw_ccf": item.raw_ccf,
                        "ccf_lower": item.ccf_lower,
                        "ccf_upper": item.ccf_upper,
                        "state": item.state.value,
                        "evidence_channels": item.evidence_channels,
                        "content_address": item.content_address,
                    }
                    for item in estimates
                ),
                "issue_codes": issue_codes,
                "counts": counts,
            }
            return _execution(record, result.state.value, issue_codes, counts, output)

        if record.operation == SpecimenBetaFrontierOperation.SUBCLONE:
            result = SubcloneAssigner().assign(raw_records, **parameters)
            assignments = tuple(result.assignments)
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            counts = {
                "assignments": len(assignments),
                "clusters": len(result.cluster_means),
                "ambiguous": sum(
                    item.assignment_state == SpecimenBetaState.AMBIGUOUS for item in assignments
                ),
                "issues": len(result.issues),
            }
            output = {
                "operation": record.operation.value,
                "state": result.state.value,
                "assignments": tuple(
                    {
                        "sample_id": item.sample_id,
                        "variant_id": item.variant_id,
                        "subclone_id": item.subclone_id,
                        "cluster_mean_ccf": item.cluster_mean_ccf,
                        "estimated_ccf": item.estimated_ccf,
                        "distance_to_cluster_mean": item.distance_to_cluster_mean,
                        "assignment_state": item.assignment_state.value,
                        "content_address": item.content_address,
                    }
                    for item in assignments
                ),
                "cluster_means": dict(result.cluster_means),
                "issue_codes": issue_codes,
                "counts": counts,
            }
            return _execution(record, result.state.value, issue_codes, counts, output)

        raise ValidationError(f"unsupported beta frontier operation: {record.operation}")


def _execution(
    record: SpecimenBetaFrontierFixtureRecord,
    result_state: str,
    issue_codes: tuple[str, ...],
    counts: Mapping[str, int],
    output: Mapping[str, Any],
) -> SpecimenBetaFrontierExecution:
    sanitized = dict(output)
    return SpecimenBetaFrontierExecution(
        record_id=record.record_id,
        operation=record.operation,
        fixture_state=record.expected_fixture_state,
        observed_result_state=result_state,
        issue_codes=tuple(sorted(issue_codes)),
        counts=dict(counts),
        input_address=content_hash(record.payload),
        output_address=content_hash(sanitized),
        sanitized_output=sanitized,
    )


def _checks(
    record: SpecimenBetaFrontierFixtureRecord,
    execution: SpecimenBetaFrontierExecution,
) -> tuple[SpecimenBetaFrontierFixtureCheck, ...]:
    expected_counts = dict(record.expected_counts)
    observed_counts = dict(execution.counts)
    sensitive = _sensitive_keys(execution.sanitized_output)
    return (
        _check(
            "fixture-state",
            record,
            record.expected_fixture_state
            in {
                SpecimenBetaFrontierFixtureState.ACCEPTED,
                SpecimenBetaFrontierFixtureState.REVIEW,
            },
            record.expected_fixture_state.value,
            "accepted-or-review fixture state is declared",
        ),
        _check(
            "result-state",
            record,
            execution.observed_result_state == record.expected_result_state,
            execution.observed_result_state,
            record.expected_result_state,
        ),
        _check(
            "issue-codes",
            record,
            execution.issue_codes == tuple(sorted(record.expected_issue_codes)),
            execution.issue_codes,
            tuple(sorted(record.expected_issue_codes)),
        ),
        _check(
            "expected-counts",
            record,
            observed_counts == expected_counts,
            observed_counts,
            expected_counts,
        ),
        _check(
            "content-address",
            record,
            record.content_address.startswith("sha256:")
            and execution.input_address.startswith("sha256:")
            and execution.output_address.startswith("sha256:"),
            execution.output_address,
            "sha256-addressed input, output, and record",
        ),
        _check(
            "sanitized-output",
            record,
            not sensitive and "records" not in execution.sanitized_output,
            tuple(sorted(sensitive)),
            (),
        ),
    )


def _check(
    suffix: str,
    record: SpecimenBetaFrontierFixtureRecord,
    passed: bool,
    observed: Any,
    expected: Any,
) -> SpecimenBetaFrontierFixtureCheck:
    return SpecimenBetaFrontierFixtureCheck(
        check_id=f"{record.record_id}:{suffix}",
        record_id=record.record_id,
        passed=passed,
        observed=observed,
        expected=expected,
        message=("passed" if passed else f"{suffix} mismatch"),
    )


def _sensitive_keys(value: Any) -> set[str]:
    sensitive_names = {
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
    }
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).strip().lower() in sensitive_names:
                found.add(str(key).strip().lower())
            found.update(_sensitive_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_sensitive_keys(nested))
    return found


def evaluate_specimen_beta_frontier_fixture(
    catalog: SpecimenBetaFrontierFixtureCatalog,
) -> SpecimenBetaFrontierFixtureEvaluationReport:
    """Convenience function for CLI and downstream release tooling."""

    return SpecimenBetaFrontierFixtureEvaluator().evaluate(catalog)


__all__ = [
    "SpecimenBetaFrontierExecution",
    "SpecimenBetaFrontierFixtureCheck",
    "SpecimenBetaFrontierFixtureEvaluationReport",
    "SpecimenBetaFrontierFixtureEvaluator",
    "SpecimenBetaFrontierOperationReceipt",
    "evaluate_specimen_beta_frontier_fixture",
]
