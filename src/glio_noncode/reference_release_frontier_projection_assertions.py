"""Independent assertions over serialized C13-C16 output projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_contracts import default_reference_release_contracts
from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_schema import default_reference_release_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseProjectionCheck:
    """One projection invariant with observed and required values."""

    check_id: str
    record_id: str | None
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseProjectionAudit:
    """Projection audit with per-record and aggregate failures."""

    checks: tuple[ReferenceReleaseProjectionCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _check(
    index: int, record_id: str | None, passed: bool, observed: Any, required: Any, detail: str
) -> ReferenceReleaseProjectionCheck:
    body = {
        "check_id": f"release-projection-{index:03d}",
        "record_id": record_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceReleaseProjectionCheck(
        **body, content_address=content_hash(body, prefix="projection-check")
    )


def audit_reference_release_projections(
    evaluation: ReferenceReleaseEvaluation,
) -> ReferenceReleaseProjectionAudit:
    """Check output fields, state vocabulary, addresses, and payload redaction."""

    contracts = default_reference_release_contracts()
    schemas = default_reference_release_schema()
    checks: list[ReferenceReleaseProjectionCheck] = []
    index = 1
    forbidden_global = {"records", "previous", "current", "raw_records", "private_keys"}
    for execution in evaluation.executions:
        contract = contracts.by_operation(execution.operation)
        schema = schemas.by_operation(execution.operation)
        checks.append(
            _check(
                index,
                execution.record_id,
                execution.state in set(contract.accepted_states) | set(contract.review_states),
                execution.state,
                tuple(sorted(set(contract.accepted_states) | set(contract.review_states))),
                "state belongs to the declared contract vocabulary",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                execution.record_id,
                not (set(execution.output) & forbidden_global),
                sorted(set(execution.output) & forbidden_global),
                [],
                "raw input fields are not projected",
            )
        )
        index += 1
        projected = schema.project_output(execution.output)
        checks.append(
            _check(
                index,
                execution.record_id,
                set(projected) <= {field.name for field in schema.output_fields},
                sorted(projected),
                sorted(field.name for field in schema.output_fields),
                "output fields remain inside the operation schema",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                execution.record_id,
                execution.content_address.startswith("sha256:"),
                execution.content_address,
                "sha256:",
                "execution address uses canonical hashing",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                execution.record_id,
                set(execution.issue_codes) <= set(contract.issue_codes),
                sorted(set(execution.issue_codes) - set(contract.issue_codes)),
                [],
                "issue codes are declared by the contract",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                execution.record_id,
                execution.accepted == (execution.state in {"accepted", "published"}),
                execution.accepted,
                execution.state in {"accepted", "published"},
                "accepted flag follows state",
            )
        )
        index += 1
    checks.append(
        _check(
            index,
            None,
            len(evaluation.executions) == 16,
            len(evaluation.executions),
            16,
            "all fixture executions are represented",
        )
    )
    index += 1
    checks.append(
        _check(
            index,
            None,
            evaluation.positive_count == 4,
            evaluation.positive_count,
            4,
            "positive role count is retained",
        )
    )
    index += 1
    checks.append(
        _check(
            index,
            None,
            evaluation.control_count == 12,
            evaluation.control_count,
            12,
            "control role count is retained",
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"checks": tuple(checks), "accepted": accepted}
    return ReferenceReleaseProjectionAudit(
        **body, content_address=content_hash(body, prefix="projection-audit")
    )


__all__ = [
    "ReferenceReleaseProjectionAudit",
    "ReferenceReleaseProjectionCheck",
    "audit_reference_release_projections",
]
