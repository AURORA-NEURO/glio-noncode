"""Repository-wide public-boundary audit for published service projections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Any

from .capability_certification_bundle import build_capability_certification_bundle
from .capability_certification_bundle_schema import capability_certification_bundle_schema
from .module_fabric_bundle import build_module_fabric_bundle
from .module_fabric_bundle_schema import module_fabric_bundle_schema
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .schema import schema_document
from .serialization import content_hash, jsonable
from .service_surface import (
    ServiceSurfaceSnapshot,
    build_service_surface_closure,
    build_service_surface_snapshot,
    service_capability_projection,
    service_diff_projection,
    service_operational_projection,
    service_program_projection,
    service_surface_status,
)
from .validation_design_frontier_bundle_schema import validation_design_bundle_schema
from .validation_design_frontier_offline_bundle import build_validation_design_offline_bundle
from .evidence_lifecycle_frontier_offline_bundle import build_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_schema import evidence_lifecycle_offline_bundle_schema
from .workbench_release_frontier_offline_bundle import build_workbench_release_offline_bundle
from .workbench_release_frontier_offline_schema import workbench_release_offline_bundle_schema
from .deployment_frontier_offline_bundle import build_deployment_frontier_offline_bundle
from .deployment_frontier_offline_schema import deployment_frontier_offline_bundle_schema
from .deployment_profiles import build_deployment_profile, deployment_profile_schema
from .reference_manifest import build_default_reference_manifest, reference_manifest_schema
from .reference_interval_index import (
    reference_interval_index_capabilities,
    reference_interval_index_schema,
)
from .reference_track_adapters import (
    reference_track_adapter_capabilities,
    reference_track_adapter_schema,
)
from .cohort_benchmarks import cohort_benchmark_capabilities, cohort_benchmark_schema
from .review_workspace import review_workspace_capabilities, review_workspace_schema
from .review_workspace_plan import review_workspace_plan_capabilities, review_workspace_plan_schema
from .review_workspace_execution import review_workspace_execution_capabilities, review_workspace_execution_schema
from .review_workspace_execution_release import (
    review_workspace_execution_release_capabilities,
    review_workspace_execution_release_schema,
)
from .review_workspace_execution_transitions import (
    review_workspace_execution_transitions_capabilities,
    review_workspace_execution_transitions_diff_capabilities,
    review_workspace_execution_transitions_diff_schema,
    review_workspace_execution_transitions_schema,
)
from .review_workspace_execution_simulation import (
    review_workspace_execution_simulation_capabilities,
    review_workspace_execution_simulation_schema,
)
from .review_workspace_execution_batch import (
    review_workspace_execution_batch_capabilities,
    review_workspace_execution_batch_schema,
)
from .review_workspace_execution_audit import (
    review_workspace_execution_audit_capabilities,
    review_workspace_execution_audit_schema,
)
from .mission_runtime_public import (
    mission_plan_public_capabilities,
    mission_plan_public_schema,
)
from .mission_plan_release import (
    mission_plan_release_capabilities,
    mission_plan_release_schema,
)
from .mission_plan_release_query import (
    mission_plan_release_query_capabilities,
    mission_plan_release_query_schema,
)
from .mission_plan_release_diff import (
    mission_plan_release_diff_capabilities,
    mission_plan_release_diff_schema,
)
from .mission_plan_release_runtime import (
    mission_plan_release_runtime_capabilities,
    mission_plan_release_runtime_schema,
)
from .mission_plan_release_observability import (
    mission_plan_release_observability_capabilities,
    mission_plan_release_observability_schema,
)
from .mission_plan_release_lineage import (
    mission_plan_release_lineage_capabilities,
    mission_plan_release_lineage_schema,
)
from .mission_plan_release_policy import (
    mission_plan_release_policy_capabilities,
    mission_plan_release_policy_schema,
)
from .mission_plan_release_catalog import (
    mission_plan_release_catalog_capabilities,
    mission_plan_release_catalog_schema,
)
from .mission_plan_release_catalog_query import (
    mission_plan_release_catalog_query_capabilities,
    mission_plan_release_catalog_query_schema,
)
from .mission_plan_release_catalog_diff import (
    mission_plan_release_catalog_diff_capabilities,
    mission_plan_release_catalog_diff_schema,
)
from .mission_plan_release_catalog_audit import (
    mission_plan_release_catalog_audit_capabilities,
    mission_plan_release_catalog_audit_schema,
)
from .mission_plan_release_catalog_report import (
    mission_plan_release_catalog_report_capabilities,
    mission_plan_release_catalog_report_schema,
)
from .mission_plan_release_catalog_gate import (
    mission_plan_release_catalog_gate_capabilities,
    mission_plan_release_catalog_gate_schema,
)
from .mission_plan_release_catalog_gate_runtime import (
    mission_plan_release_catalog_gate_runtime_capabilities,
    mission_plan_release_catalog_gate_runtime_schema,
)
from .mission_plan_release_catalog_gate_packet import (
    mission_plan_release_catalog_gate_packet_capabilities,
    mission_plan_release_catalog_gate_packet_schema,
)
from .mission_plan_release_catalog_gate_query import (
    mission_plan_release_catalog_gate_query_capabilities,
    mission_plan_release_catalog_gate_query_schema,
)
from .mission_plan_release_catalog_gate_diff import (
    mission_plan_release_catalog_gate_diff_capabilities,
    mission_plan_release_catalog_gate_diff_schema,
)
from .mission_plan_release_catalog_gate_observability import (
    mission_plan_release_catalog_gate_observability_capabilities,
    mission_plan_release_catalog_gate_observability_schema,
)
from .mission_plan_public_conformance import (
    mission_plan_public_conformance_capabilities,
    mission_plan_public_conformance_schema,
    mission_plan_public_replay_capabilities,
    mission_plan_public_replay_schema,
)
from .variant_stream import (
    breakend_normalization_schema,
    streaming_intake_capabilities,
    streaming_intake_schema,
)
from .service_release_bundle import build_service_release_snapshot
from .service_release_handoff import build_service_release_handoff
from .service_release_query import query_service_release
from .service_release_runtime import run_service_release
from .service_release_schema import service_release_schema
from .module_inventory import module_inventory_capabilities, module_inventory_schema
from .module_inventory_audit import module_inventory_audit_capabilities, module_inventory_audit_schema
from .module_inventory_depth import module_inventory_depth_capabilities, module_inventory_depth_schema
from .module_inventory_graph import module_inventory_graph_capabilities, module_inventory_graph_schema
from .module_inventory_observability import module_inventory_observability_capabilities, module_inventory_observability_schema
from .module_inventory_packet import module_inventory_packet_capabilities, module_inventory_packet_schema
from .module_inventory_packet_query import module_inventory_packet_query_capabilities, module_inventory_packet_query_schema
from .module_inventory_review import module_inventory_review_capabilities, module_inventory_review_schema
from .module_inventory_runtime import module_inventory_runtime_capabilities, module_inventory_runtime_schema
from .module_impact_audit import module_impact_audit_capabilities, module_impact_audit_schema
from .module_impact_observability import module_impact_observability_capabilities, module_impact_observability_schema
from .module_impact_packet import module_impact_packet_capabilities, module_impact_packet_schema
from .module_impact_packet_query import module_impact_packet_query_capabilities, module_impact_packet_query_schema
from .module_impact_policy import module_impact_policy_capabilities, module_impact_policy_schema
from .module_impact_runtime import module_impact_runtime_capabilities, module_impact_runtime_schema
from .module_impact_schema import default_module_impact_schema, module_impact_schema_capabilities
from .module_impact_verification import module_impact_verification_capabilities, module_impact_verification_schema
from .module_certification import module_certification_capabilities, module_certification_schema
from .module_certification_audit import module_certification_audit_capabilities, module_certification_audit_schema
from .module_certification_observability import module_certification_observability_capabilities, module_certification_observability_schema
from .module_certification_packet import module_certification_packet_capabilities, module_certification_packet_schema
from .module_certification_packet_query import module_certification_packet_query_capabilities, module_certification_packet_query_schema
from .module_certification_policy import module_certification_policy_capabilities, module_certification_policy_schema
from .module_certification_runtime import module_certification_runtime_capabilities, module_certification_runtime_schema
from .module_certification_tasks import module_certification_tasks_capabilities, module_certification_tasks_schema
from .module_certification_diff import module_certification_diff_capabilities, module_certification_diff_schema
from .module_certification_review import module_certification_review_capabilities, module_certification_review_schema
from .module_certification_schema import module_certification_schema_capabilities, module_certification_schema_report_schema
from .module_certification_lineage import module_certification_lineage_capabilities, module_certification_lineage_schema
from .module_certification_quality import module_certification_quality_capabilities, module_certification_quality_schema
from .module_certification_lineage_audit import module_certification_lineage_audit_capabilities, module_certification_lineage_audit_schema
from .module_certification_release import module_certification_release_capabilities, module_certification_release_schema
from .module_certification_quality_policy import module_certification_quality_policy_capabilities, module_certification_quality_policy_schema
from .module_workbench import module_workbench_capabilities, module_workbench_schema
from .module_workbench_audit import module_workbench_audit_capabilities, module_workbench_audit_schema
from .module_workbench_diff import module_workbench_diff_capabilities, module_workbench_diff_schema
from .module_workbench_policy import module_workbench_policy_capabilities, module_workbench_policy_schema
from .module_workbench_runtime import module_workbench_runtime_capabilities, module_workbench_runtime_schema
from .module_workbench_portfolio import module_workbench_portfolio_capabilities, module_workbench_portfolio_schema
from .module_workbench_execution import module_workbench_execution_capabilities, module_workbench_execution_schema
from .module_workbench_execution_audit import module_workbench_execution_audit_capabilities, module_workbench_execution_audit_schema
from .module_workbench_execution_diff import module_workbench_execution_diff_capabilities, module_workbench_execution_diff_schema
from .module_workbench_execution_policy import module_workbench_execution_policy_capabilities, module_workbench_execution_policy_schema
from .module_workbench_execution_runtime import module_workbench_execution_runtime_capabilities, module_workbench_execution_runtime_schema
from .module_workbench_execution_review import module_workbench_execution_review_capabilities, module_workbench_execution_review_schema
from .module_workbench_execution_packet import module_workbench_execution_packet_capabilities, module_workbench_execution_packet_schema
from .module_workbench_execution_packet_query import module_workbench_execution_packet_query_capabilities, module_workbench_execution_packet_query_schema
from .module_workbench_execution_packet_release import module_workbench_execution_packet_release_capabilities, module_workbench_execution_packet_release_schema
from .module_workbench_execution_packet_runtime import module_workbench_execution_packet_runtime_capabilities, module_workbench_execution_packet_runtime_schema
from .module_workbench_execution_packet_inspection import module_workbench_execution_packet_inspection_capabilities, module_workbench_execution_packet_inspection_schema
from .module_workbench_execution_packet_archive import module_workbench_execution_packet_archive_capabilities, module_workbench_execution_packet_archive_schema
from .module_workbench_execution_packet_archive_query import module_workbench_execution_packet_archive_transfer_capabilities, module_workbench_execution_packet_archive_transfer_schema
from .module_workbench_execution_packet_archive_runtime import module_workbench_execution_packet_archive_runtime_capabilities, module_workbench_execution_packet_archive_runtime_schema
from .module_workbench_execution_packet_archive_diff import module_workbench_execution_packet_archive_diff_capabilities, module_workbench_execution_packet_archive_diff_schema
from .module_workbench_execution_packet_archive_index import module_workbench_execution_packet_archive_index_capabilities, module_workbench_execution_packet_archive_index_schema
from .module_workbench_execution_packet_archive_store_query import module_workbench_execution_packet_archive_store_capabilities, module_workbench_execution_packet_archive_store_schema
from .module_workbench_execution_packet_archive_store_runtime import module_workbench_execution_packet_archive_store_runtime_capabilities, module_workbench_execution_packet_archive_store_runtime_schema
from .module_workbench_execution_packet_archive_store_checkpoint import module_workbench_execution_packet_archive_store_checkpoint_capabilities, module_workbench_execution_packet_archive_store_checkpoint_schema
from .module_workbench_execution_packet_archive_store_recovery import module_workbench_execution_packet_archive_store_recovery_capabilities, module_workbench_execution_packet_archive_store_recovery_schema
from .module_workbench_execution_packet_archive_store_replication_contracts import module_workbench_execution_packet_archive_store_replication_capabilities, module_workbench_execution_packet_archive_store_replication_schema
from .module_workbench_execution_packet_archive_store_replication_query import module_workbench_execution_packet_archive_store_replication_query_capabilities, module_workbench_execution_packet_archive_store_replication_query_schema
from .module_workbench_execution_packet_archive_store_replication_runtime_contracts import module_workbench_execution_packet_archive_store_replication_runtime_capabilities, module_workbench_execution_packet_archive_store_replication_runtime_schema
from .module_workbench_execution_packet_archive_store_replication_packet import module_workbench_execution_packet_archive_store_replication_packet_capabilities, module_workbench_execution_packet_archive_store_replication_packet_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_query_schema, module_workbench_execution_packet_archive_store_replication_packet_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_contracts import module_workbench_execution_packet_archive_store_replication_packet_diff_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_query import module_workbench_execution_packet_archive_store_replication_packet_diff_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_query_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_assurance import module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_batch import module_workbench_execution_packet_archive_store_replication_packet_diff_batch_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_batch_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_schema
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_capabilities, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_schema, module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_schema

PUBLIC_SURFACE_AUDIT_VERSION = "public-surface-audit-v1"
PUBLIC_SURFACE_EXPECTED_COUNT = 320

_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "email",
        "generated_by",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant_id",
        "patient_id",
        "phone",
        "primary_agent",
        "primary_agent_id",
        "programming_language",
        "produced_by",
        "sample_id",
        "subject_id",
    })

_PRIVATE_INPUT_SCHEMA_KEYS = frozenset({"individual_id", "medical_record_number", "participant_id", "patient_id", "phone", "sample_id", "subject_id"})


class PublicSurfaceAuditPlane(StrEnum):
    SERVICE = "service"
    BUNDLE = "bundle"
    SCHEMA = "schema"
    CLOSURE = "closure"


@dataclass(frozen=True, slots=True)
class PublicSurfaceAuditCheck:
    surface_id: str
    plane: PublicSurfaceAuditPlane
    accepted: bool
    violation_paths: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PublicSurfaceAudit:
    version: str
    checks: tuple[PublicSurfaceAuditCheck, ...]
    accepted: bool
    content_address: str

    @property
    def surface_count(self) -> int:
        return len(self.checks)

    @property
    def passed_surface_count(self) -> int:
        return sum(item.accepted for item in self.checks)

    @property
    def failed_surface_count(self) -> int:
        return self.surface_count - self.passed_surface_count

    @property
    def failed_surface_ids(self) -> tuple[str, ...]:
        return tuple(item.surface_id for item in self.checks if not item.accepted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "checks": [item.to_dict() for item in self.checks],
            "surface_count": self.surface_count,
            "passed_surface_count": self.passed_surface_count,
            "failed_surface_count": self.failed_surface_count,
            "failed_surface_ids": list(self.failed_surface_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _violation_paths(value: Any, path: str = "$") -> tuple[str, ...]:
    value = jsonable(value)
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            key_path = f"{path}.{key_text}"
            normalized = key_text.casefold()
            if normalized in _FORBIDDEN_PUBLIC_KEYS:
                paths.append(key_path)
            paths.extend(_violation_paths(item, key_path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            paths.extend(_violation_paths(item, f"{path}[{index}]"))
    return tuple(paths)


def _audit_surface(surface_id: str, plane: PublicSurfaceAuditPlane, value: Any) -> PublicSurfaceAuditCheck:
    projected = jsonable(value)
    violations = _violation_paths(projected)
    if plane is PublicSurfaceAuditPlane.SCHEMA:
        violations = tuple(
            item
            for item in violations
            if not any(item.casefold().endswith(f".{key}") for key in _PRIVATE_INPUT_SCHEMA_KEYS)
        )
    violations = tuple(item for item in violations if item)
    if plane is not PublicSurfaceAuditPlane.SCHEMA:
        if _has_forbidden_key(projected) and "$" not in violations:
            violations = (*violations, "$")
        if contains_private_key(projected) and "$" not in violations:
            violations = (*violations, "$private-key")
    body = {
        "surface_id": surface_id,
        "plane": plane,
        "accepted": not violations,
        "violation_paths": violations,
    }
    return PublicSurfaceAuditCheck(
        **body,
        content_address=content_hash(body, prefix="public-surface-audit-check"),
    )


def build_public_surface_audit(surfaces: Mapping[str, Any]) -> PublicSurfaceAudit:
    """Audit an explicit named set of public projections."""

    checks = tuple(
        _audit_surface(
            str(surface_id),
            PublicSurfaceAuditPlane.SCHEMA if "schema" in str(surface_id) else PublicSurfaceAuditPlane.BUNDLE if "bundle" in str(surface_id) else PublicSurfaceAuditPlane.CLOSURE if "closure" in str(surface_id) else PublicSurfaceAuditPlane.SERVICE,
            value,
        )
        for surface_id, value in sorted(surfaces.items(), key=lambda item: str(item[0]))
    )
    accepted = bool(checks) and len(checks) == PUBLIC_SURFACE_EXPECTED_COUNT and all(item.accepted for item in checks)
    body = {"version": PUBLIC_SURFACE_AUDIT_VERSION, "checks": checks, "accepted": accepted}
    return PublicSurfaceAudit(
        version=PUBLIC_SURFACE_AUDIT_VERSION,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="public-surface-audit"),
    )


def default_public_surface_inventory(
    *,
    snapshot: ServiceSurfaceSnapshot | None = None,
    capability_bundle: Any | None = None,
    module_fabric_bundle: Any | None = None,
    validation_design_bundle: Any | None = None,
    evidence_lifecycle_bundle: Any | None = None,
    workbench_release_bundle: Any | None = None,
    deployment_frontier_bundle: Any | None = None,
    deployment_profile: Any | None = None,
    service_release_handoff: Any | None = None,
) -> dict[str, Any]:
    """Build the stable inventory of service, bundle, schema, and closure views."""

    from .release_assurance_attestation import release_assurance_attestation_capabilities, release_assurance_attestation_schema
    from .release_assurance_attestation_runtime import release_assurance_attestation_runtime_capabilities
    from .release_assurance_attestation_packet import release_assurance_attestation_packet_capabilities, release_assurance_attestation_packet_schema
    from .release_assurance_attestation_query import release_assurance_attestation_query_capabilities, release_assurance_attestation_query_schema
    from .release_assurance_attestation_diff import release_assurance_attestation_diff_capabilities, release_assurance_attestation_diff_schema
    from .release_assurance_attestation_observability import release_assurance_attestation_observability_capabilities, release_assurance_attestation_observability_schema
    from .release_assurance_attestation_review import release_assurance_attestation_review_capabilities, release_assurance_attestation_review_schema
    from .release_assurance_attestation_registry import release_assurance_attestation_registry_capabilities, release_assurance_attestation_registry_schema
    from .release_assurance_attestation_registry_packet import release_assurance_attestation_registry_packet_capabilities, release_assurance_attestation_registry_packet_schema
    from .release_assurance_attestation_registry_store import release_assurance_attestation_registry_store_capabilities, release_assurance_attestation_registry_store_schema
    from .release_assurance_attestation_registry_store_packet import release_assurance_attestation_registry_store_packet_capabilities, release_assurance_attestation_registry_store_packet_schema
    from .release_assurance_attestation_registry_store_gate import release_assurance_attestation_registry_store_gate_capabilities, release_assurance_attestation_registry_store_gate_schema
    from .release_assurance_attestation_registry_store_gate_packet import release_assurance_attestation_registry_store_gate_packet_capabilities, release_assurance_attestation_registry_store_gate_packet_schema
    from .storage_maintenance import storage_maintenance_capabilities, storage_maintenance_schema
    from .storage_maintenance_packet import storage_maintenance_packet_capabilities, storage_maintenance_packet_schema
    from .storage_maintenance_observability import storage_maintenance_observability_capabilities, storage_maintenance_observability_schema
    from .storage_maintenance_review import storage_maintenance_review_capabilities, storage_maintenance_review_schema
    from .storage_lineage import storage_lineage_capabilities, storage_lineage_schema
    from .storage_lineage_observability import storage_lineage_observability_capabilities, storage_lineage_observability_schema
    from .storage_lineage_review import storage_lineage_review_capabilities, storage_lineage_review_schema
    from .storage_lineage_packet import storage_lineage_packet_capabilities, storage_lineage_packet_schema
    from .storage_catalog import storage_catalog_capabilities, storage_catalog_schema
    from .storage_catalog_observability import storage_catalog_observability_capabilities, storage_catalog_observability_schema
    from .storage_catalog_packet import storage_catalog_packet_capabilities, storage_catalog_packet_schema

    selected = snapshot or build_service_surface_snapshot()
    capability_value = capability_bundle or build_capability_certification_bundle()
    module_value = module_fabric_bundle or build_module_fabric_bundle()
    validation_design_value = validation_design_bundle or build_validation_design_offline_bundle()
    evidence_lifecycle_value = evidence_lifecycle_bundle or build_evidence_lifecycle_offline_bundle()
    workbench_release_value = workbench_release_bundle or build_workbench_release_offline_bundle()
    deployment_frontier_value = deployment_frontier_bundle or build_deployment_frontier_offline_bundle()
    deployment_profile_value = deployment_profile or build_deployment_profile()
    service_release_value = build_service_release_snapshot(selected)
    service_release_runtime = run_service_release(
        selected,
        bundle_id="glio-noncode-public-surface-service-release",
        run_id="glio-noncode-public-surface-service-release-run",
    )
    service_release_handoff_value = service_release_handoff or build_service_release_handoff(
        service_release_runtime,
        selected,
    )
    reference_manifest_value = build_default_reference_manifest()
    return {
        "capability-certification-bundle-manifest": capability_value.to_dict(include_payloads=False),
        "capability-certification-bundle-schema": capability_certification_bundle_schema(),
        "module-fabric-bundle-manifest": module_value.to_dict(include_payloads=False),
        "module-fabric-bundle-schema": module_fabric_bundle_schema(),
        "validation-design-bundle-manifest": validation_design_value.to_dict(include_payloads=False),
        "validation-design-bundle-schema": validation_design_bundle_schema(),
        "evidence-lifecycle-bundle-manifest": evidence_lifecycle_value.to_dict(include_payloads=False),
        "evidence-lifecycle-bundle-schema": evidence_lifecycle_offline_bundle_schema(),
        "workbench-release-bundle-manifest": workbench_release_value.to_dict(include_payloads=False),
        "workbench-release-bundle-schema": workbench_release_offline_bundle_schema(),
        "deployment-frontier-bundle-manifest": deployment_frontier_value.to_dict(include_payloads=False),
        "deployment-frontier-bundle-schema": deployment_frontier_offline_bundle_schema(),
        "deployment-profile": deployment_profile_value,
        "deployment-profile-schema": deployment_profile_schema(),
        "reference-manifest": reference_manifest_value,
        "reference-manifest-schema": reference_manifest_schema(),
        "streaming-intake-schema": streaming_intake_schema(),
        "streaming-intake-capabilities": streaming_intake_capabilities(),
        "breakend-normalization-schema": breakend_normalization_schema(),
        "reference-index-schema": reference_interval_index_schema(),
        "reference-index-capabilities": reference_interval_index_capabilities(),
        "reference-adapter-schema": reference_track_adapter_schema(),
        "reference-adapter-capabilities": reference_track_adapter_capabilities(),
        "cohort-benchmark-schema": cohort_benchmark_schema(),
        "cohort-benchmark-capabilities": cohort_benchmark_capabilities(),
        "review-workspace-schema": review_workspace_schema(),
        "review-workspace-capabilities": review_workspace_capabilities(),
        "review-workspace-plan-schema": review_workspace_plan_schema(),
        "review-workspace-plan-capabilities": review_workspace_plan_capabilities(),
        "review-workspace-plan-execution-schema": review_workspace_execution_schema(),
        "review-workspace-plan-execution-capabilities": review_workspace_execution_capabilities(),
        "review-workspace-plan-execution-release-schema": review_workspace_execution_release_schema(),
        "review-workspace-plan-execution-release-capabilities": review_workspace_execution_release_capabilities(),
        "review-workspace-plan-execution-transitions-schema": review_workspace_execution_transitions_schema(),
        "review-workspace-plan-execution-transitions-capabilities": review_workspace_execution_transitions_capabilities(),
        "review-workspace-plan-execution-transitions-diff-schema": review_workspace_execution_transitions_diff_schema(),
        "review-workspace-plan-execution-transitions-diff-capabilities": review_workspace_execution_transitions_diff_capabilities(),
        "review-workspace-plan-execution-simulation-schema": review_workspace_execution_simulation_schema(),
        "review-workspace-plan-execution-simulation-capabilities": review_workspace_execution_simulation_capabilities(),
        "review-workspace-plan-execution-batch-schema": review_workspace_execution_batch_schema(),
        "review-workspace-plan-execution-batch-capabilities": review_workspace_execution_batch_capabilities(),
        "review-workspace-plan-execution-audit-schema": review_workspace_execution_audit_schema(),
        "review-workspace-plan-execution-audit-capabilities": review_workspace_execution_audit_capabilities(),
        "mission-plan-schema": mission_plan_public_schema(),
        "mission-plan-capabilities": mission_plan_public_capabilities(),
        "mission-plan-release-schema": mission_plan_release_schema(),
        "mission-plan-release-capabilities": mission_plan_release_capabilities(),
        "mission-plan-release-query-schema": mission_plan_release_query_schema(),
        "mission-plan-release-query-capabilities": mission_plan_release_query_capabilities(),
        "mission-plan-release-diff-schema": mission_plan_release_diff_schema(),
        "mission-plan-release-diff-capabilities": mission_plan_release_diff_capabilities(),
        "mission-plan-release-runtime-schema": mission_plan_release_runtime_schema(),
        "mission-plan-release-runtime-capabilities": mission_plan_release_runtime_capabilities(),
        "mission-plan-release-observability-schema": mission_plan_release_observability_schema(),
        "mission-plan-release-observability-capabilities": mission_plan_release_observability_capabilities(),
        "mission-plan-release-lineage-schema": mission_plan_release_lineage_schema(),
        "mission-plan-release-lineage-capabilities": mission_plan_release_lineage_capabilities(),
        "mission-plan-release-policy-schema": mission_plan_release_policy_schema(),
        "mission-plan-release-policy-capabilities": mission_plan_release_policy_capabilities(),
        "mission-plan-release-catalog-schema": mission_plan_release_catalog_schema(),
        "mission-plan-release-catalog-capabilities": mission_plan_release_catalog_capabilities(),
        "mission-plan-release-catalog-query-schema": mission_plan_release_catalog_query_schema(),
        "mission-plan-release-catalog-query-capabilities": mission_plan_release_catalog_query_capabilities(),
        "mission-plan-release-catalog-diff-schema": mission_plan_release_catalog_diff_schema(),
        "mission-plan-release-catalog-diff-capabilities": mission_plan_release_catalog_diff_capabilities(),
        "mission-plan-release-catalog-audit-schema": mission_plan_release_catalog_audit_schema(),
        "mission-plan-release-catalog-audit-capabilities": mission_plan_release_catalog_audit_capabilities(),
        "mission-plan-release-catalog-report-schema": mission_plan_release_catalog_report_schema(),
        "mission-plan-release-catalog-report-capabilities": mission_plan_release_catalog_report_capabilities(),
        "mission-plan-release-catalog-gate-schema": mission_plan_release_catalog_gate_schema(),
        "mission-plan-release-catalog-gate-capabilities": mission_plan_release_catalog_gate_capabilities(),
        "mission-plan-release-catalog-gate-runtime-schema": mission_plan_release_catalog_gate_runtime_schema(),
        "mission-plan-release-catalog-gate-runtime-capabilities": mission_plan_release_catalog_gate_runtime_capabilities(),
        "mission-plan-release-catalog-gate-packet-schema": mission_plan_release_catalog_gate_packet_schema(),
        "mission-plan-release-catalog-gate-packet-capabilities": mission_plan_release_catalog_gate_packet_capabilities(),
        "mission-plan-release-catalog-gate-query-schema": mission_plan_release_catalog_gate_query_schema(),
        "mission-plan-release-catalog-gate-query-capabilities": mission_plan_release_catalog_gate_query_capabilities(),
        "mission-plan-release-catalog-gate-diff-schema": mission_plan_release_catalog_gate_diff_schema(),
        "mission-plan-release-catalog-gate-diff-capabilities": mission_plan_release_catalog_gate_diff_capabilities(),
        "mission-plan-release-catalog-gate-observability-schema": mission_plan_release_catalog_gate_observability_schema(),
        "mission-plan-release-catalog-gate-observability-capabilities": mission_plan_release_catalog_gate_observability_capabilities(),
        "release-assurance-attestation-schema": release_assurance_attestation_schema(),
        "release-assurance-attestation-capabilities": release_assurance_attestation_capabilities(),
        "release-assurance-attestation-runtime-capabilities": release_assurance_attestation_runtime_capabilities(),
        "release-assurance-attestation-packet-schema": release_assurance_attestation_packet_schema(),
        "release-assurance-attestation-packet-capabilities": release_assurance_attestation_packet_capabilities(),
        "release-assurance-attestation-query-schema": release_assurance_attestation_query_schema(),
        "release-assurance-attestation-query-capabilities": release_assurance_attestation_query_capabilities(),
        "release-assurance-attestation-diff-schema": release_assurance_attestation_diff_schema(),
        "release-assurance-attestation-diff-capabilities": release_assurance_attestation_diff_capabilities(),
        "release-assurance-attestation-observability-schema": release_assurance_attestation_observability_schema(),
        "release-assurance-attestation-observability-capabilities": release_assurance_attestation_observability_capabilities(),
        "release-assurance-attestation-review-schema": release_assurance_attestation_review_schema(),
        "release-assurance-attestation-review-capabilities": release_assurance_attestation_review_capabilities(),
        "release-assurance-attestation-registry-schema": release_assurance_attestation_registry_schema(),
        "release-assurance-attestation-registry-capabilities": release_assurance_attestation_registry_capabilities(),
        "release-assurance-attestation-registry-packet-schema": release_assurance_attestation_registry_packet_schema(),
        "release-assurance-attestation-registry-packet-capabilities": release_assurance_attestation_registry_packet_capabilities(),
        "release-assurance-attestation-registry-store-schema": release_assurance_attestation_registry_store_schema(),
        "release-assurance-attestation-registry-store-capabilities": release_assurance_attestation_registry_store_capabilities(),
        "release-assurance-attestation-registry-store-packet-schema": release_assurance_attestation_registry_store_packet_schema(),
        "release-assurance-attestation-registry-store-packet-capabilities": release_assurance_attestation_registry_store_packet_capabilities(),
        "release-assurance-attestation-registry-store-gate-schema": release_assurance_attestation_registry_store_gate_schema(),
        "release-assurance-attestation-registry-store-gate-capabilities": release_assurance_attestation_registry_store_gate_capabilities(),
        "release-assurance-attestation-registry-store-gate-packet-schema": release_assurance_attestation_registry_store_gate_packet_schema(),
        "release-assurance-attestation-registry-store-gate-packet-capabilities": release_assurance_attestation_registry_store_gate_packet_capabilities(),
        "storage-maintenance-schema": storage_maintenance_schema(),
        "storage-maintenance-capabilities": storage_maintenance_capabilities(),
        "storage-maintenance-packet-schema": storage_maintenance_packet_schema(),
        "storage-maintenance-packet-capabilities": storage_maintenance_packet_capabilities(),
        "storage-maintenance-observability-schema": storage_maintenance_observability_schema(),
        "storage-maintenance-observability-capabilities": storage_maintenance_observability_capabilities(),
        "storage-maintenance-review-schema": storage_maintenance_review_schema(),
        "storage-maintenance-review-capabilities": storage_maintenance_review_capabilities(),
        "storage-lineage-schema": storage_lineage_schema(),
        "storage-lineage-capabilities": storage_lineage_capabilities(),
        "storage-lineage-observability-schema": storage_lineage_observability_schema(),
        "storage-lineage-observability-capabilities": storage_lineage_observability_capabilities(),
        "storage-lineage-review-schema": storage_lineage_review_schema(),
        "storage-lineage-review-capabilities": storage_lineage_review_capabilities(),
        "storage-lineage-packet-schema": storage_lineage_packet_schema(),
        "storage-lineage-packet-capabilities": storage_lineage_packet_capabilities(),
        "storage-catalog-schema": storage_catalog_schema(),
        "storage-catalog-capabilities": storage_catalog_capabilities(),
        "storage-catalog-observability-schema": storage_catalog_observability_schema(),
        "storage-catalog-observability-capabilities": storage_catalog_observability_capabilities(),
        "storage-catalog-packet-schema": storage_catalog_packet_schema(),
        "storage-catalog-packet-capabilities": storage_catalog_packet_capabilities(),
        "mission-plan-conformance-schema": mission_plan_public_conformance_schema(),
        "mission-plan-conformance-capabilities": mission_plan_public_conformance_capabilities(),
        "mission-plan-replay-schema": mission_plan_public_replay_schema(),
        "mission-plan-replay-capabilities": mission_plan_public_replay_capabilities(),
        "module-inventory-schema": module_inventory_schema(),
        "module-inventory-capabilities": module_inventory_capabilities(),
        "module-inventory-audit-schema": module_inventory_audit_schema(),
        "module-inventory-audit-capabilities": module_inventory_audit_capabilities(),
        "module-inventory-depth-schema": module_inventory_depth_schema(),
        "module-inventory-depth-capabilities": module_inventory_depth_capabilities(),
        "module-inventory-graph-schema": module_inventory_graph_schema(),
        "module-inventory-graph-capabilities": module_inventory_graph_capabilities(),
        "module-inventory-observability-schema": module_inventory_observability_schema(),
        "module-inventory-observability-capabilities": module_inventory_observability_capabilities(),
        "module-inventory-packet-schema": module_inventory_packet_schema(),
        "module-inventory-packet-capabilities": module_inventory_packet_capabilities(),
        "module-inventory-packet-query-schema": module_inventory_packet_query_schema(),
        "module-inventory-packet-query-capabilities": module_inventory_packet_query_capabilities(),
        "module-inventory-review-schema": module_inventory_review_schema(),
        "module-inventory-review-capabilities": module_inventory_review_capabilities(),
        "module-inventory-runtime-schema": module_inventory_runtime_schema(),
        "module-inventory-runtime-capabilities": module_inventory_runtime_capabilities(),
        "module-impact-schema": default_module_impact_schema(),
        "module-impact-capabilities": module_impact_schema_capabilities(),
        "module-impact-audit-schema": module_impact_audit_schema(),
        "module-impact-audit-capabilities": module_impact_audit_capabilities(),
        "module-impact-policy-schema": module_impact_policy_schema(),
        "module-impact-policy-capabilities": module_impact_policy_capabilities(),
        "module-impact-verification-schema": module_impact_verification_schema(),
        "module-impact-verification-capabilities": module_impact_verification_capabilities(),
        "module-impact-runtime-schema": module_impact_runtime_schema(),
        "module-impact-runtime-capabilities": module_impact_runtime_capabilities(),
        "module-impact-observability-schema": module_impact_observability_schema(),
        "module-impact-observability-capabilities": module_impact_observability_capabilities(),
        "module-impact-packet-schema": module_impact_packet_schema(),
        "module-impact-packet-capabilities": module_impact_packet_capabilities(),
        "module-impact-packet-query-schema": module_impact_packet_query_schema(),
        "module-impact-packet-query-capabilities": module_impact_packet_query_capabilities(),
        "module-certification-schema": module_certification_schema(),
        "module-certification-capabilities": module_certification_capabilities(),
        "module-certification-audit-schema": module_certification_audit_schema(),
        "module-certification-audit-capabilities": module_certification_audit_capabilities(),
        "module-certification-policy-schema": module_certification_policy_schema(),
        "module-certification-policy-capabilities": module_certification_policy_capabilities(),
        "module-certification-tasks-schema": module_certification_tasks_schema(),
        "module-certification-tasks-capabilities": module_certification_tasks_capabilities(),
        "module-certification-runtime-schema": module_certification_runtime_schema(),
        "module-certification-runtime-capabilities": module_certification_runtime_capabilities(),
        "module-certification-observability-schema": module_certification_observability_schema(),
        "module-certification-observability-capabilities": module_certification_observability_capabilities(),
        "module-certification-packet-schema": module_certification_packet_schema(),
        "module-certification-packet-capabilities": module_certification_packet_capabilities(),
        "module-certification-packet-query-schema": module_certification_packet_query_schema(),
        "module-certification-packet-query-capabilities": module_certification_packet_query_capabilities(),
        "module-certification-diff-schema": module_certification_diff_schema(),
        "module-certification-diff-capabilities": module_certification_diff_capabilities(),
        "module-certification-review-schema": module_certification_review_schema(),
        "module-certification-review-capabilities": module_certification_review_capabilities(),
        "module-certification-schema-capabilities": module_certification_schema_capabilities(),
        "module-certification-schema-report-schema": module_certification_schema_report_schema(),
        "module-certification-lineage-schema": module_certification_lineage_schema(),
        "module-certification-lineage-capabilities": module_certification_lineage_capabilities(),
        "module-certification-quality-schema": module_certification_quality_schema(),
        "module-certification-quality-capabilities": module_certification_quality_capabilities(),
        "module-certification-lineage-audit-schema": module_certification_lineage_audit_schema(),
        "module-certification-lineage-audit-capabilities": module_certification_lineage_audit_capabilities(),
        "module-certification-release-schema": module_certification_release_schema(),
        "module-certification-release-capabilities": module_certification_release_capabilities(),
        "module-certification-quality-policy-schema": module_certification_quality_policy_schema(),
        "module-certification-quality-policy-capabilities": module_certification_quality_policy_capabilities(),
        "module-workbench-schema": module_workbench_schema(),
        "module-workbench-capabilities": module_workbench_capabilities(),
        "module-workbench-policy-schema": module_workbench_policy_schema(),
        "module-workbench-policy-capabilities": module_workbench_policy_capabilities(),
        "module-workbench-audit-schema": module_workbench_audit_schema(),
        "module-workbench-audit-capabilities": module_workbench_audit_capabilities(),
        "module-workbench-diff-schema": module_workbench_diff_schema(),
        "module-workbench-diff-capabilities": module_workbench_diff_capabilities(),
        "module-workbench-runtime-schema": module_workbench_runtime_schema(),
        "module-workbench-runtime-capabilities": module_workbench_runtime_capabilities(),
        "module-workbench-portfolio-schema": module_workbench_portfolio_schema(),
        "module-workbench-portfolio-capabilities": module_workbench_portfolio_capabilities(),
        "module-workbench-execution-schema": module_workbench_execution_schema(),
        "module-workbench-execution-capabilities": module_workbench_execution_capabilities(),
        "module-workbench-execution-audit-schema": module_workbench_execution_audit_schema(),
        "module-workbench-execution-audit-capabilities": module_workbench_execution_audit_capabilities(),
        "module-workbench-execution-diff-schema": module_workbench_execution_diff_schema(),
        "module-workbench-execution-diff-capabilities": module_workbench_execution_diff_capabilities(),
        "module-workbench-execution-policy-schema": module_workbench_execution_policy_schema(),
        "module-workbench-execution-policy-capabilities": module_workbench_execution_policy_capabilities(),
        "module-workbench-execution-runtime-schema": module_workbench_execution_runtime_schema(),
        "module-workbench-execution-runtime-capabilities": module_workbench_execution_runtime_capabilities(),
        "module-workbench-execution-review-schema": module_workbench_execution_review_schema(),
        "module-workbench-execution-review-capabilities": module_workbench_execution_review_capabilities(),
        "module-workbench-execution-packet-schema": module_workbench_execution_packet_schema(),
        "module-workbench-execution-packet-capabilities": module_workbench_execution_packet_capabilities(),
        "module-workbench-execution-packet-query-schema": module_workbench_execution_packet_query_schema(),
        "module-workbench-execution-packet-query-capabilities": module_workbench_execution_packet_query_capabilities(),
        "module-workbench-execution-packet-release-schema": module_workbench_execution_packet_release_schema(),
        "module-workbench-execution-packet-release-capabilities": module_workbench_execution_packet_release_capabilities(),
        "module-workbench-execution-packet-runtime-schema": module_workbench_execution_packet_runtime_schema(),
        "module-workbench-execution-packet-runtime-capabilities": module_workbench_execution_packet_runtime_capabilities(),
        "module-workbench-execution-packet-inspection-schema": module_workbench_execution_packet_inspection_schema(),
        "module-workbench-execution-packet-inspection-capabilities": module_workbench_execution_packet_inspection_capabilities(),
        "module-workbench-execution-packet-archive-schema": module_workbench_execution_packet_archive_schema(),
        "module-workbench-execution-packet-archive-capabilities": module_workbench_execution_packet_archive_capabilities(),
        "module-workbench-execution-packet-archive-transfer-schema": module_workbench_execution_packet_archive_transfer_schema(),
        "module-workbench-execution-packet-archive-transfer-capabilities": module_workbench_execution_packet_archive_transfer_capabilities(),
        "module-workbench-execution-packet-archive-runtime-schema": module_workbench_execution_packet_archive_runtime_schema(),
        "module-workbench-execution-packet-archive-runtime-capabilities": module_workbench_execution_packet_archive_runtime_capabilities(),
        "module-workbench-execution-packet-archive-diff-schema": module_workbench_execution_packet_archive_diff_schema(),
        "module-workbench-execution-packet-archive-diff-capabilities": module_workbench_execution_packet_archive_diff_capabilities(),
        "module-workbench-execution-packet-archive-index-schema": module_workbench_execution_packet_archive_index_schema(),
        "module-workbench-execution-packet-archive-index-capabilities": module_workbench_execution_packet_archive_index_capabilities(),
        "module-workbench-execution-packet-archive-store-schema": module_workbench_execution_packet_archive_store_schema(),
        "module-workbench-execution-packet-archive-store-capabilities": module_workbench_execution_packet_archive_store_capabilities(),
        "module-workbench-execution-packet-archive-store-runtime-schema": module_workbench_execution_packet_archive_store_runtime_schema(),
        "module-workbench-execution-packet-archive-store-runtime-capabilities": module_workbench_execution_packet_archive_store_runtime_capabilities(),
        "module-workbench-execution-packet-archive-store-checkpoint-schema": module_workbench_execution_packet_archive_store_checkpoint_schema(),
        "module-workbench-execution-packet-archive-store-checkpoint-capabilities": module_workbench_execution_packet_archive_store_checkpoint_capabilities(),
        "module-workbench-execution-packet-archive-store-recovery-schema": module_workbench_execution_packet_archive_store_recovery_schema(),
        "module-workbench-execution-packet-archive-store-recovery-capabilities": module_workbench_execution_packet_archive_store_recovery_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-schema": module_workbench_execution_packet_archive_store_replication_schema(),
        "module-workbench-execution-packet-archive-store-replication-capabilities": module_workbench_execution_packet_archive_store_replication_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-query-schema": module_workbench_execution_packet_archive_store_replication_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-query-capabilities": module_workbench_execution_packet_archive_store_replication_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-runtime-schema": module_workbench_execution_packet_archive_store_replication_runtime_schema(),
        "module-workbench-execution-packet-archive-store-replication-runtime-capabilities": module_workbench_execution_packet_archive_store_replication_runtime_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-schema": module_workbench_execution_packet_archive_store_replication_packet_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-capabilities": module_workbench_execution_packet_archive_store_replication_packet_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-query-schema": module_workbench_execution_packet_archive_store_replication_packet_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-runtime-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-runtime-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_batch_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_batch_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-diff-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-diff-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_capabilities(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-diff-query-schema": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_schema(),
        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-diff-query-capabilities": module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_capabilities(),
        "service-capabilities": service_capability_projection(selected),
        "service-closure": build_service_surface_closure(selected),
        "service-diff-none": service_diff_projection(selected, "none"),
        "service-mvp-capabilities": service_capability_projection(selected, mvp_only=True),
        "service-operational": service_operational_projection(selected),
        "service-program": service_program_projection(selected),
        "service-program-accepted": service_program_projection(selected, accepted_only=True),
        "service-schema": schema_document(),
        "service-status": service_surface_status(selected),
        "service-snapshot": selected,
        "service-release-snapshot": service_release_value,
        "service-release-schema": service_release_schema(),
        "service-release-query": query_service_release(service_release_value),
        "service-release-handoff": service_release_handoff_value,
    }


def build_default_public_surface_audit(
    *,
    snapshot: ServiceSurfaceSnapshot | None = None,
    capability_bundle: Any | None = None,
    module_fabric_bundle: Any | None = None,
    validation_design_bundle: Any | None = None,
    evidence_lifecycle_bundle: Any | None = None,
    workbench_release_bundle: Any | None = None,
    deployment_frontier_bundle: Any | None = None,
    deployment_profile: Any | None = None,
    service_release_handoff: Any | None = None,
) -> PublicSurfaceAudit:
    """Execute and audit all default public service and handoff projections."""

    if all(
        value is None
        for value in (
            snapshot,
            capability_bundle,
            module_fabric_bundle,
            validation_design_bundle,
            evidence_lifecycle_bundle,
            workbench_release_bundle,
            deployment_frontier_bundle,
            deployment_profile,
            service_release_handoff,
        )
    ):
        return _cached_default_public_surface_audit()
    return build_public_surface_audit(
        default_public_surface_inventory(
            snapshot=snapshot,
            capability_bundle=capability_bundle,
            module_fabric_bundle=module_fabric_bundle,
            validation_design_bundle=validation_design_bundle,
            evidence_lifecycle_bundle=evidence_lifecycle_bundle,
            workbench_release_bundle=workbench_release_bundle,
            deployment_frontier_bundle=deployment_frontier_bundle,
            deployment_profile=deployment_profile,
            service_release_handoff=service_release_handoff,
        )
    )


@lru_cache(maxsize=1)
def _cached_default_public_surface_audit() -> PublicSurfaceAudit:
    """Reuse the immutable default projection for repeated local/API reads."""

    return build_public_surface_audit(default_public_surface_inventory())


__all__ = [
    "PUBLIC_SURFACE_AUDIT_VERSION",
    "PUBLIC_SURFACE_EXPECTED_COUNT",
    "PublicSurfaceAudit",
    "PublicSurfaceAuditCheck",
    "PublicSurfaceAuditPlane",
    "build_default_public_surface_audit",
    "build_public_surface_audit",
    "default_public_surface_inventory",
]
