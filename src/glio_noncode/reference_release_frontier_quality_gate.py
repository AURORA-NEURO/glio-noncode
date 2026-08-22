"""Release-quality gate combining the independent C13-C16 evidence views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_contracts import ReferenceReleaseContractRegistry
from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_lineage import ReferenceReleaseLineageGraph
from .reference_release_frontier_policy import ReferenceReleasePolicyReport
from .reference_release_frontier_projection_assertions import ReferenceReleaseProjectionAudit
from .reference_release_frontier_public_data import (
    ReferenceReleaseDataAudit,
    ReferenceReleaseFixture,
)
from .reference_release_frontier_reconciliation import ReferenceReleaseReconciliation
from .reference_release_frontier_schema import ReferenceReleaseSchemaRegistry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseQualityCheck:
    """One named release gate condition."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseQualityGate:
    """Complete quality result with a stable 25-condition gate."""

    fixture_id: str
    checks: tuple[ReferenceReleaseQualityCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _check(
    index: int, passed: bool, observed: Any, expected: Any, detail: str
) -> ReferenceReleaseQualityCheck:
    body = {
        "check_id": f"release-quality-{index:03d}",
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ReferenceReleaseQualityCheck(
        **body, content_address=content_hash(body, prefix="quality-check")
    )


def evaluate_reference_release_quality(
    fixture: ReferenceReleaseFixture,
    data_audit: ReferenceReleaseDataAudit,
    evaluation: ReferenceReleaseEvaluation,
    contracts: ReferenceReleaseContractRegistry,
    schema: ReferenceReleaseSchemaRegistry,
    lineage: ReferenceReleaseLineageGraph,
    reconciliation: ReferenceReleaseReconciliation,
    projection: ReferenceReleaseProjectionAudit,
    policy: ReferenceReleasePolicyReport,
) -> ReferenceReleaseQualityGate:
    """Run the complete quality gate without suppressing failed conditions."""

    contract_issue_codes = {code for item in contracts.contracts for code in item.issue_codes}
    schema_validation: list[tuple[str, ...]] = []
    for record in fixture.records:
        payload = dict(record.payload)
        payload["context_key"] = fixture.context_key
        schema_validation.append(schema.by_operation(record.operation).validate_input(payload))
    graph_audit = lineage.audit(evaluation)
    checks = (
        _check(
            1, data_audit.accepted, data_audit.accepted, True, "source and fixture audit accepted"
        ),
        _check(
            2, evaluation.accepted, evaluation.accepted, True, "all expected executions accepted"
        ),
        _check(
            3, projection.accepted, projection.accepted, True, "serialized projections accepted"
        ),
        _check(4, policy.accepted, policy.accepted, True, "policy report accepted"),
        _check(
            5,
            reconciliation.accepted,
            reconciliation.accepted,
            True,
            "cross-view reconciliation accepted",
        ),
        _check(6, graph_audit.passed, graph_audit.passed, True, "lineage graph accepted"),
        _check(
            7,
            len(contracts.contracts) == 4,
            len(contracts.contracts),
            4,
            "four operation contracts exist",
        ),
        _check(8, len(schema.schemas) == 4, len(schema.schemas), 4, "four operation schemas exist"),
        _check(
            9,
            all(item.content_address.startswith("sha256:") for item in contracts.contracts),
            True,
            True,
            "contract addresses are canonical",
        ),
        _check(
            10,
            all(item.content_address.startswith("sha256:") for item in schema.schemas),
            True,
            True,
            "schema addresses are canonical",
        ),
        _check(
            11,
            all(
                len({field.name for field in item.input_fields}) == len(item.input_fields)
                for item in schema.schemas
            ),
            True,
            True,
            "input fields are unique",
        ),
        _check(
            12,
            fixture.evidence_boundary == "public_aggregate_non_patient",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
            "aggregate boundary is explicit",
        ),
        _check(
            13,
            len(fixture.positive_records) == 4,
            len(fixture.positive_records),
            4,
            "positive fixture count is exact",
        ),
        _check(
            14,
            len(fixture.control_records) == 12,
            len(fixture.control_records),
            12,
            "control fixture count is exact",
        ),
        _check(
            15,
            all(record.source_ids for record in fixture.records),
            True,
            True,
            "every record carries source receipt IDs",
        ),
        _check(
            16,
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            True,
            True,
            "fixture records are addressed",
        ),
        _check(
            17,
            all(
                execution.content_address.startswith("sha256:")
                for execution in evaluation.executions
            ),
            True,
            True,
            "execution receipts are addressed",
        ),
        _check(
            18,
            {record.operation for record in fixture.records}
            == {item.operation for item in schema.schemas},
            True,
            True,
            "fixture operations match schemas",
        ),
        _check(
            19,
            all(
                set(execution.issue_codes) <= contract_issue_codes
                for execution in evaluation.executions
            ),
            True,
            True,
            "observed issue codes are declared",
        ),
        _check(
            20,
            all(
                not {"records", "previous", "current", "raw_records"} & set(execution.output)
                for execution in evaluation.executions
            ),
            True,
            True,
            "outputs do not contain raw rows",
        ),
        _check(
            21,
            all(execution.state for execution in evaluation.executions),
            True,
            True,
            "every execution has a state",
        ),
        _check(
            22,
            all(not failures for failures in schema_validation),
            schema_validation,
            "all inputs satisfy schemas",
            "all inputs satisfy schemas",
        ),
        _check(
            23,
            bool(contract_issue_codes),
            len(contract_issue_codes),
            ">0",
            "declared issue vocabulary is non-empty",
        ),
        _check(
            24,
            not graph_audit.failed_check_ids,
            graph_audit.failed_check_ids,
            (),
            "lineage graph has no failed audit checks",
        ),
        _check(
            25,
            fixture.context_key == data_audit.context_key == fixture.records[0].context_key,
            fixture.context_key,
            data_audit.context_key,
            "fixture, audit, and record context agree",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": accepted}
    return ReferenceReleaseQualityGate(
        **body, content_address=content_hash(body, prefix="release-quality-gate")
    )


__all__ = [
    "ReferenceReleaseQualityCheck",
    "ReferenceReleaseQualityGate",
    "evaluate_reference_release_quality",
]
