"""Construct the public D01-D16 aggregate release snapshot.

This module is the single source of truth for the aggregate projection.  It
does not execute domain runtimes itself.  A caller may pass the already built
offline handoff, which makes API requests, replay, and export verification
reuse one immutable source bundle instead of rebuilding sixteen runtimes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .program_release_closure_contracts import (
    PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT,
    PROGRAM_RELEASE_CLOSURE_ARTIFACT_PREFIX,
    PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
    PROGRAM_RELEASE_CLOSURE_DOMAIN_IDS,
    PROGRAM_RELEASE_CLOSURE_GATE_COUNT,
    PROGRAM_RELEASE_CLOSURE_GATE_TYPES,
    PROGRAM_RELEASE_CLOSURE_VERSION,
    ProgramReleaseArtifact,
    ProgramReleaseDependency,
    ProgramReleaseDomain,
    ProgramReleaseGate,
    ProgramReleaseSnapshot,
)
from .program_release_closure_support import (
    as_bool,
    as_int,
    content_addressed,
    forbidden_keys,
    public_manifest,
    source_report,
    source_rows,
)
from .program_runtime_offline_bundle import build_program_runtime_offline_bundle
from .program_runtime_offline_contracts import ProgramRuntimeOfflineBundle
from .serialization import jsonable, require_non_empty


def _domain_rows(source_bundle: ProgramRuntimeOfflineBundle) -> list[dict[str, Any]]:
    value = source_rows(source_bundle, "operations")
    if not isinstance(value, list):
        raise ValidationError("source operations projection must be a list")
    rows = [dict(row) for row in value if isinstance(row, Mapping)]
    rows.sort(key=lambda row: str(row.get("domain_id", "")))
    return rows


def _make_domain(
    source_bundle: ProgramRuntimeOfflineBundle,
    row: Mapping[str, Any],
    ordinal: int,
) -> ProgramReleaseDomain:
    domain_id = str(row.get("domain_id", "")).strip()
    body = {
        "domain_id": domain_id,
        "domain": str(row.get("domain", "")),
        "dependency_order": ordinal,
        "source_bundle_id": source_bundle.bundle_id,
        "source_runtime_address": str(row.get("runtime_address", "")),
        "source_receipt_address": str(row.get("content_address", "")),
        "runtime_state": str(row.get("runtime_state", "")),
        "stage_count": as_int(row.get("stage_count")),
        "evaluation_check_count": as_int(row.get("evaluation_check_count")),
        "source_artifact_count": as_int(row.get("artifact_count")),
        "accepted": as_bool(row.get("accepted")),
    }
    return ProgramReleaseDomain(
        **body, content_address=content_addressed(body, "program-release-domain")
    )


def _make_artifacts(
    source_bundle: ProgramRuntimeOfflineBundle,
) -> tuple[ProgramReleaseArtifact, ...]:
    values: list[ProgramReleaseArtifact] = []
    for source in sorted(source_bundle.artifacts, key=lambda item: item.artifact_id):
        body = {
            "artifact_ref": f"program:{source.artifact_id}",
            "artifact_id": source.artifact_id,
            "domain_id": "__program__",
            "relative_path": source.relative_path,
            "media_type": source.media_type,
            "source_address": source.content_address,
            "byte_count": source.byte_count,
            "line_count": source.line_count,
        }
        values.append(
            ProgramReleaseArtifact(
                **body,
                content_address=content_addressed(body, PROGRAM_RELEASE_CLOSURE_ARTIFACT_PREFIX),
            )
        )
    return tuple(values)


def _make_dependencies(
    domains: tuple[ProgramReleaseDomain, ...],
) -> tuple[ProgramReleaseDependency, ...]:
    values: list[ProgramReleaseDependency] = []
    for source in domains:
        for target in domains:
            if source.dependency_order >= target.dependency_order:
                continue
            body = {
                "dependency_id": f"dependency:{source.domain_id}:{target.domain_id}",
                "source_domain_id": source.domain_id,
                "target_domain_id": target.domain_id,
                "relation": "release_precedes",
                "source_order": source.dependency_order,
                "target_order": target.dependency_order,
            }
            values.append(
                ProgramReleaseDependency(
                    **body,
                    content_address=content_addressed(body, "program-release-dependency"),
                )
            )
    return tuple(values)


def _gate_value(domain: ProgramReleaseDomain, gate_type: str) -> tuple[Any, Any]:
    if gate_type == "bundle_accepted":
        return domain.accepted, True
    if gate_type == "runtime_address":
        return bool(domain.source_runtime_address), True
    if gate_type == "runtime_depth":
        return domain.stage_count, ">0"
    if gate_type == "evaluation_checks":
        return domain.evaluation_check_count, ">0"
    if gate_type == "artifact_contribution":
        return domain.source_artifact_count, ">0"
    return domain.runtime_state, ("accepted", "published")


def _make_gates(domains: tuple[ProgramReleaseDomain, ...]) -> tuple[ProgramReleaseGate, ...]:
    values: list[ProgramReleaseGate] = []
    for domain in domains:
        for gate_type in PROGRAM_RELEASE_CLOSURE_GATE_TYPES:
            observed, expected = _gate_value(domain, gate_type)
            passed = (
                bool(observed)
                if expected is True
                else observed > 0
                if expected == ">0"
                else observed in expected
            )
            body = {
                "gate_id": f"gate:{domain.domain_id}:{gate_type}",
                "domain_id": domain.domain_id,
                "gate_type": gate_type,
                "passed": passed,
                "observed": observed,
                "expected": expected,
                "source_address": domain.content_address,
            }
            values.append(
                ProgramReleaseGate(
                    **body,
                    content_address=content_addressed(body, "program-release-gate"),
                )
            )
    return tuple(values)


def build_program_release_snapshot(
    source_bundle: ProgramRuntimeOfflineBundle | None = None,
    *,
    bundle_id: str = "glio-noncode-program-release-closure",
    run_id: str = "glio-noncode-program-release-closure-run",
) -> ProgramReleaseSnapshot:
    """Project the accepted architecture-program handoff into D01-D16 closure."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    source = source_bundle or build_program_runtime_offline_bundle(
        bundle_id=bundle_id, run_id=run_id
    )
    rows = _domain_rows(source)
    domains = tuple(_make_domain(source, row, ordinal) for ordinal, row in enumerate(rows, start=1))
    artifacts = _make_artifacts(source)
    dependencies = _make_dependencies(domains)
    gates = _make_gates(domains)
    report = source_report(source)
    source_manifest = public_manifest(source)
    source_bundle_address = str(source.content_address)
    body = {
        "bundle_id": bundle_id,
        "run_id": run_id,
        "source_bundle_id": source.bundle_id,
        "source_bundle_address": source_bundle_address,
        "domains": domains,
        "artifacts": artifacts,
        "dependencies": dependencies,
        "gates": gates,
        "source_manifest_address": content_addressed(
            source_manifest, "program-release-source-manifest"
        ),
        "source_report_address": str(report.get("report_address", "")),
    }
    accepted = (
        source.ready
        and len(domains) == PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT
        and tuple(item.domain_id for item in domains) == PROGRAM_RELEASE_CLOSURE_DOMAIN_IDS
        and len(artifacts) == PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT
        and len(dependencies) == 120
        and len(gates) == PROGRAM_RELEASE_CLOSURE_GATE_COUNT
        and not forbidden_keys(jsonable(body))
        and all(item.accepted for item in domains)
        and all(item.passed for item in gates)
    )
    return ProgramReleaseSnapshot(
        bundle_id=bundle_id,
        run_id=run_id,
        source_bundle_id=source.bundle_id,
        source_bundle_address=source_bundle_address,
        domains=domains,
        artifacts=artifacts,
        dependencies=dependencies,
        gates=gates,
        accepted=accepted,
        content_address=content_addressed(
            body | {"accepted": accepted}, PROGRAM_RELEASE_CLOSURE_VERSION
        ),
    )


def program_release_snapshot_counts(snapshot: ProgramReleaseSnapshot) -> dict[str, int | bool]:
    """Return the conserved aggregate denominator map."""

    return {
        "domain_count": len(snapshot.domains),
        "artifact_count": len(snapshot.artifacts),
        "dependency_count": len(snapshot.dependencies),
        "gate_count": len(snapshot.gates),
        "accepted_domain_count": sum(item.accepted for item in snapshot.domains),
        "passed_gate_count": sum(item.passed for item in snapshot.gates),
        "accepted": snapshot.accepted,
    }


def program_release_snapshot_rows(
    snapshot: ProgramReleaseSnapshot,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "domains": [item.to_dict() for item in snapshot.domains],
        "artifacts": [item.to_dict() for item in snapshot.artifacts],
        "dependencies": [item.to_dict() for item in snapshot.dependencies],
        "gates": [item.to_dict() for item in snapshot.gates],
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE")
    or name.startswith("ProgramRelease")
    or name.startswith("build_program_release")
    or name.startswith("program_release_snapshot")
]
