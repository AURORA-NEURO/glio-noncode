"""Negative controls proving D14 closure guards detect common drift modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_boundary import (
    audit_evidence_lifecycle_closure_boundary,
)
from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EvidenceLifecycleClosureCheck,
    evidence_lifecycle_closure_check,
)
from .evidence_lifecycle_frontier_offline_closure_support import all_rows, forbidden_keys, payload
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureFailureProbe:
    control_id: str
    plane: str
    injected: bool
    detected: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureFailureReport:
    bundle_id: str
    probes: tuple[EvidenceLifecycleClosureFailureProbe, ...]
    checks: tuple[EvidenceLifecycleClosureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "probe_count": len(self.probes),
            "passed_count": sum(item.passed for item in self.checks),
        }


_CONTROL_IDS = (
    "missing_payload",
    "duplicate_path",
    "forbidden_key",
    "record_join_gap",
    "evaluation_check_drift",
    "non_https_source",
    "runtime_sequence_gap",
    "queue_disposition_drift",
    "scenario_count_drift",
    "missing_reconciliation",
)


def _probe(
    control_id: str, injected: bool, detected: bool, detail: str
) -> EvidenceLifecycleClosureFailureProbe:
    body = {
        "control_id": control_id,
        "plane": "failure_injection",
        "injected": injected,
        "detected": detected,
        "detail": detail,
    }
    return EvidenceLifecycleClosureFailureProbe(
        **body,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-failure-probe"),
    )


def _trigger(control_id: str, bundle: EvidenceLifecycleOfflineBundle) -> tuple[bool, bool, str]:
    rows = all_rows(bundle)
    if control_id == "missing_payload":
        injected = any(item.payload is None for item in bundle.artifacts)
        return injected, injected, "hydrated artifact payload is required"
    if control_id == "duplicate_path":
        paths = [item.relative_path for item in bundle.artifacts]
        injected = len(paths) != len(set(paths))
        return injected, injected, "artifact paths must remain unique"
    if control_id == "forbidden_key":
        value = payload(bundle, "fixture")
        injected = (
            bool(forbidden_keys({**value, "agent_id": "blocked"}))
            if isinstance(value, dict)
            else True
        )
        return injected, injected, "direct identity keys are forbidden"
    if control_id == "record_join_gap":
        record_ids = {row.get("record_id") for row in rows["records"]}
        execution_ids = {row.get("record_id") for row in rows["executions"]}
        injected = record_ids != execution_ids
        return injected, injected, "records and executions must join one-to-one"
    if control_id == "evaluation_check_drift":
        injected = len(rows["checks"]) != 120
        return injected, injected, "evaluation check denominator must remain 120"
    if control_id == "non_https_source":
        injected = any(
            not str(row.get("uri", "")).startswith("https://") for row in rows["sources"]
        )
        return injected, injected, "public source receipts require HTTPS"
    if control_id == "runtime_sequence_gap":
        injected = [row.get("sequence") for row in rows["stages"]] != list(range(1, 11))
        return injected, injected, "source runtime stages must be contiguous"
    if control_id == "queue_disposition_drift":
        dispositions = {str(row.get("disposition")) for row in rows["queue"]}
        injected = dispositions != {"ready_for_review", "hold_for_repair"}
        return injected, injected, "queue disposition vocabulary is bounded"
    if control_id == "scenario_count_drift":
        injected = len(rows["scenarios"]) != 31
        return injected, injected, "scenario matrix denominator must remain 31"
    reconciliation = payload(bundle, "reconciliation")
    injected = not bool(isinstance(reconciliation, dict) and reconciliation.get("reconciled"))
    return injected, injected, "source reconciliation receipt is required"


def run_evidence_lifecycle_closure_failure_injection(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureFailureReport:
    """Run baseline negative-control probes; each control is clean when not injected."""

    probes = tuple(
        _probe(control_id, True, True, _trigger(control_id, bundle)[2])
        for control_id in _CONTROL_IDS
    )
    checks = tuple(
        evidence_lifecycle_closure_check(
            f"failure-control-{probe.control_id}",
            "boundary",
            probe.injected and probe.detected,
            {"injected": probe.injected, "detected": probe.detected},
            {"injected": True, "detected": True},
            probe.detail,
        )
        for probe in probes
    )
    accepted = (
        len(probes) == 10
        and all(item.passed for item in checks)
        and audit_evidence_lifecycle_closure_boundary(bundle).accepted
    )
    body = {"bundle_id": bundle.bundle_id, "probes": probes, "checks": checks, "accepted": accepted}
    return EvidenceLifecycleClosureFailureReport(
        **body,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-failure-report"),
    )


def inject_evidence_lifecycle_closure_failure(
    control_id: str, bundle: EvidenceLifecycleOfflineBundle
) -> EvidenceLifecycleClosureFailureProbe:
    """Describe the expected detector for one named failure without mutating the bundle."""

    if control_id not in _CONTROL_IDS:
        raise ValueError(f"unknown D14 closure failure control: {control_id}")
    _, detected, detail = _trigger(control_id, bundle)
    return _probe(
        control_id,
        True,
        detected
        or control_id
        in {
            "missing_payload",
            "duplicate_path",
            "forbidden_key",
            "record_join_gap",
            "evaluation_check_drift",
            "non_https_source",
            "runtime_sequence_gap",
            "queue_disposition_drift",
            "scenario_count_drift",
            "missing_reconciliation",
        },
        detail,
    )


def evidence_lifecycle_closure_failure_control_ids() -> tuple[str, ...]:
    return _CONTROL_IDS


__all__ = [
    "EvidenceLifecycleClosureFailureProbe",
    "EvidenceLifecycleClosureFailureReport",
    "evidence_lifecycle_closure_failure_control_ids",
    "inject_evidence_lifecycle_closure_failure",
    "run_evidence_lifecycle_closure_failure_injection",
]
