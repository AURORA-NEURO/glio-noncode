"""Replay and controlled-failure checks for capability certification."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .capability_certification import certify_capability_catalog
from .capability_certification_contracts import CapabilityCertificationState
from .capability_registry import CapabilityRecord, CapabilityRegistry, default_capability_registry
from .module_fabric_contracts import FabricReferenceKind
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CapabilityCertificationReplayReport:
    """Determinism receipt for two independent certification passes."""

    first_address: str
    second_address: str
    first_catalog_address: str
    second_catalog_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CapabilityCertificationFailureProbe:
    """One negative control proving that a missing evidence plane is visible."""

    probe_id: str
    capability_id: str
    removed_surface: str
    observed_state: CapabilityCertificationState
    expected_state: CapabilityCertificationState
    failed_check_ids: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CapabilityCertificationFailureReport:
    """Collection of deterministic certification negative controls."""

    probes: tuple[CapabilityCertificationFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "probes": [item.to_dict() for item in self.probes],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_capability_certification(
    registry: CapabilityRegistry | None = None,
) -> CapabilityCertificationReplayReport:
    """Run the same catalog certification twice and compare all addresses."""

    catalog = registry or default_capability_registry()
    first = certify_capability_catalog(catalog)
    second = certify_capability_catalog(catalog)
    body = {
        "first_address": first.content_address,
        "second_address": second.content_address,
        "first_catalog_address": first.catalog_address,
        "second_catalog_address": second.catalog_address,
        "accepted": first.content_address == second.content_address and first.catalog_address == second.catalog_address,
    }
    return CapabilityCertificationReplayReport(**body, content_address=content_hash(body, prefix="capability-certification-replay"))


def replay_is_deterministic(report: CapabilityCertificationReplayReport) -> bool:
    """Return whether the replay receipt closes both report and catalog identity."""

    return report.accepted and report.first_address == report.second_address and report.first_catalog_address == report.second_catalog_address


def _mutated_registry(registry: CapabilityRegistry, capability_id: str, surface: str) -> CapabilityRegistry:
    records: list[CapabilityRecord] = []
    for record in registry.records():
        if record.spec.capability_id != capability_id:
            records.append(record)
            continue
        if surface == FabricReferenceKind.IMPLEMENTATION.value:
            records.append(replace(record, implementation_modules=()))
        elif surface == FabricReferenceKind.TEST.value:
            records.append(replace(record, test_modules=()))
        else:
            records.append(replace(record, implementation_modules=("missing.certification.surface",)))
    return CapabilityRegistry(records)


def run_capability_certification_failure_injections(
    registry: CapabilityRegistry | None = None,
) -> CapabilityCertificationFailureReport:
    """Prove missing implementation and test planes produce review states."""

    catalog = registry or default_capability_registry()
    probes: list[CapabilityCertificationFailureProbe] = []
    for probe_id, capability_id, surface in (
        ("missing-implementation", "GNC-D01-C01", FabricReferenceKind.IMPLEMENTATION.value),
        ("missing-test", "GNC-D08-C01", FabricReferenceKind.TEST.value),
    ):
        report = certify_capability_catalog(_mutated_registry(catalog, capability_id, surface))
        certificate = next(item for item in report.certificates if item.capability_id == capability_id)
        failed = tuple(item.check_id for item in certificate.checks if not item.passed)
        passed = (
            certificate.state is CapabilityCertificationState.REVIEW
            and report.state is CapabilityCertificationState.REVIEW
            and bool(failed)
            and any(surface in item or (surface == FabricReferenceKind.IMPLEMENTATION.value and "implementation" in item) for item in failed)
        )
        body = {
            "probe_id": probe_id,
            "capability_id": capability_id,
            "removed_surface": surface,
            "observed_state": certificate.state,
            "expected_state": CapabilityCertificationState.REVIEW,
            "failed_check_ids": failed,
            "passed": passed,
        }
        probes.append(CapabilityCertificationFailureProbe(**body, content_address=content_hash(body, prefix="capability-certification-probe")))
    body = {"probes": tuple(probes), "accepted": all(item.passed for item in probes)}
    return CapabilityCertificationFailureReport(**body, content_address=content_hash(body, prefix="capability-certification-failures"))


__all__ = [
    "CapabilityCertificationFailureProbe",
    "CapabilityCertificationFailureReport",
    "CapabilityCertificationReplayReport",
    "replay_capability_certification",
    "replay_is_deterministic",
    "run_capability_certification_failure_injections",
]
