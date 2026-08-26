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

PUBLIC_SURFACE_AUDIT_VERSION = "public-surface-audit-v1"
PUBLIC_SURFACE_EXPECTED_COUNT = 87

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
        "mission-plan-conformance-schema": mission_plan_public_conformance_schema(),
        "mission-plan-conformance-capabilities": mission_plan_public_conformance_capabilities(),
        "mission-plan-replay-schema": mission_plan_public_replay_schema(),
        "mission-plan-replay-capabilities": mission_plan_public_replay_capabilities(),
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
