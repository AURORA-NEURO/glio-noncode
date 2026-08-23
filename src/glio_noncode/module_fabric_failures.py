"""Failure-injection probes for module-fabric boundary controls."""

from __future__ import annotations

from dataclasses import replace

from .capability_registry import default_capability_registry
from .module_fabric_contracts import FabricFailureProbe, FabricFailureReport, FabricRecord, FabricRole, FabricState
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_operations import evaluate_module_fabric_record
from .module_fabric_public_data import default_module_fabric_fixture
from .serialization import content_hash


def _probe(probe_id: str, expected: FabricState, observed: FabricState, issues: tuple[str, ...], detail: str) -> FabricFailureProbe:
    body = {"probe_id": probe_id, "expected_state": expected, "observed_state": observed, "issue_codes": issues, "passed": expected is observed, "detail": detail}
    return FabricFailureProbe(**body, content_address=content_hash(body, prefix="module-fabric-failure"))


def run_module_fabric_failure_injections() -> FabricFailureReport:
    fixture = default_module_fabric_fixture()
    registry = default_capability_registry()
    positive = fixture.positive_records[0]
    control = fixture.control_records[0]
    unknown = replace(positive, capability_id="GNC-D01-C16", payload={**positive.payload, "declared_capability_id": positive.capability_id})
    wrong_context = replace(positive, payload={**positive.payload, "declared_context_key": "foreign-context"})
    control_without_boundary = replace(control, payload={**control.payload, "declared_domain_id": control.domain_id, "declared_context_key": fixture.context_key})
    malformed = replace(positive, payload={**positive.payload, "required_capability_order": 99})
    probes = []
    for probe_id, record, expected, detail in (
        ("unknown-capability", unknown, FabricState.REVIEW, "unknown or mismatched capability is held"),
        ("foreign-context", wrong_context, FabricState.REVIEW, "foreign context is held"),
        ("control-boundary-removed", control_without_boundary, FabricState.REVIEW, "control without a blocker is still held rather than promoted"),
        ("order-drift", malformed, FabricState.REVIEW, "capability order drift is held"),
    ):
        result = evaluate_module_fabric_record(record, registry)
        probes.append(_probe(probe_id, expected, result.state, result.issue_codes, detail))
    accepted = all(item.passed for item in probes)
    body = {"probes": probes, "accepted": accepted}
    return FabricFailureReport(tuple(probes), accepted, content_hash(body, prefix="module-fabric-failure-report"))


__all__ = ["run_module_fabric_failure_injections"]
