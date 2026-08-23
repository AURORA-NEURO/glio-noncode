"""Five-plane evaluation of every public evidence-release fixture row."""

from __future__ import annotations

from typing import Any

from .evidence_release_frontier_adapters import EvidenceReleaseAdapterRegistry, build_evidence_release_adapters, execute_evidence_release_adapter
from .evidence_release_frontier_contracts import EvidenceReleaseEvaluation, EvidenceReleaseExecution, EvidenceReleaseFixture, EvidenceReleaseRecord, EvidenceReleaseRole
from .evidence_release_frontier_operations import verify_signed_dossier
from .evidence_release_frontier_public_data import audit_evidence_release_frontier_data, default_evidence_release_frontier_fixture
from .evidence_release_frontier_support import contains_forbidden_marker
from .serialization import content_hash


def execute_evidence_release_record(record: EvidenceReleaseRecord, registry: EvidenceReleaseAdapterRegistry | None = None) -> EvidenceReleaseExecution:
    registry = registry or build_evidence_release_adapters()
    result = execute_evidence_release_adapter(registry, record.operation, record.payload)
    output = dict(result.output)
    if record.operation.value == "signed_dossier" and result.state.value == "signed":
        verification = verify_signed_dossier({"signed_dossier": output})
        output["verification_state"] = verification.output.get("verification_state")
        output["signature_verified"] = verification.state.value == "verified"
    body = {"record_id": record.record_id, "capability": record.capability, "operation": record.operation, "role": record.role, "expected_state": record.expected_state, "observed_state": result.state, "issue_codes": result.issue_codes, "output": output}
    return EvidenceReleaseExecution(**body, content_address=content_hash(body))


def _check(check_id: str, record: EvidenceReleaseRecord, plane: str, passed: bool, observed: Any, required: Any, detail: str):
    from .evidence_release_frontier_contracts import make_evidence_release_check
    return make_evidence_release_check(check_id, record.record_id, plane, passed, observed, required, detail)


def evaluate_evidence_release_fixture(fixture: EvidenceReleaseFixture | None = None) -> EvidenceReleaseEvaluation:
    fixture = fixture or default_evidence_release_frontier_fixture()
    registry = build_evidence_release_adapters()
    executions = tuple(execute_evidence_release_record(record, registry) for record in fixture.records)
    checks = []
    for execution, record in zip(executions, fixture.records, strict=True):
        checks.append(_check(f"{record.record_id}:state", record, "state", execution.observed_state == record.expected_state, execution.observed_state.value, record.expected_state.value, "operation state matches the declared fixture boundary"))
        checks.append(_check(f"{record.record_id}:issues", record, "issue", set(record.expected_issue_codes) <= set(execution.issue_codes), execution.issue_codes, record.expected_issue_codes, "control reasons remain visible"))
        checks.append(_check(f"{record.record_id}:role", record, "role", record.role == EvidenceReleaseRole.CONTROL or not record.expected_issue_codes, record.role.value, "positive has no issue" if record.role == EvidenceReleaseRole.POSITIVE else "control", "positive and control roles remain explicit"))
        checks.append(_check(f"{record.record_id}:address", record, "integrity", execution.content_address.startswith("sha256:"), execution.content_address[:7], "sha256:", "execution is content addressed"))
        checks.append(_check(f"{record.record_id}:safe-output", record, "safety", not contains_forbidden_marker(execution.output), "safe" if not contains_forbidden_marker(execution.output) else "forbidden", "safe", "output excludes credential-like markers"))
        if record.operation.value == "signed_dossier" and record.role == EvidenceReleaseRole.POSITIVE:
            checks.append(_check(f"{record.record_id}:verified", record, "verification", bool(execution.output.get("signature_verified")), True, True, "signed dossier is verified by recomputation"))
    passed = sum(1 for item in checks if item.passed)
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": passed == len(checks), "passed_checks": passed, "failed_checks": len(checks) - passed}
    return EvidenceReleaseEvaluation(**body, content_address=content_hash(body))


def audit_evidence_release_context(fixture: EvidenceReleaseFixture) -> tuple[str, ...]:
    return tuple(sorted({record.context_key for record in fixture.records if record.context_key not in {fixture.context_key}}))


def replay_evidence_release_fixture(fixture: EvidenceReleaseFixture | None = None) -> tuple[EvidenceReleaseExecution, ...]:
    return evaluate_evidence_release_fixture(fixture).executions


__all__ = ["audit_evidence_release_context", "evaluate_evidence_release_fixture", "execute_evidence_release_record", "replay_evidence_release_fixture"]
