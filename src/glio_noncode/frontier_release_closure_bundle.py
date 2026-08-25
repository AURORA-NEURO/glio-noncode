"""Materialization of the cross-domain D13-D16 release snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from .deployment_frontier_offline_closure_runtime import (
    run_deployment_frontier_closure_runtime,
)
from .evidence_lifecycle_frontier_offline_closure_runtime import (
    run_evidence_lifecycle_closure_runtime,
)
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_BOUNDARY,
    FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
    FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
    FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
    FrontierReleaseArtifact,
    FrontierReleaseDependency,
    FrontierReleaseDomain,
    FrontierReleaseGate,
)
from .serialization import content_hash, jsonable, require_non_empty
from .validation_design_frontier_bundle_closure_runtime import (
    run_validation_design_closure_runtime,
)
from .workbench_release_frontier_offline_closure_runtime import (
    run_workbench_release_closure_runtime,
)


_DOMAIN_NAMES = dict(
    zip(
        FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
        (
            "validation_design",
            "evidence_lifecycle",
            "workbench_release",
            "deployment_frontier",
        ),
        strict=True,
    )
)
_DOMAIN_BUNDLE_IDS = dict(
    zip(
        FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
        (
            "validation-design-public-bundle",
            "evidence-lifecycle-public-bundle",
            "workbench-release-public-bundle",
            "deployment-frontier-public-bundle",
        ),
        strict=True,
    )
)
_DOMAIN_RUNTIME_FACTORIES = {
    "D13": run_validation_design_closure_runtime,
    "D14": run_evidence_lifecycle_closure_runtime,
    "D15": run_workbench_release_closure_runtime,
    "D16": run_deployment_frontier_closure_runtime,
}


def _counter_map(summary: Any) -> dict[str, int | float]:
    value = getattr(summary, "counters", ())
    if isinstance(value, dict):
        return {str(key): number for key, number in value.items()}
    return {str(pair[0]): pair[1] for pair in value if isinstance(pair, (list, tuple))}


def _counter(counters: dict[str, int | float], *names: str) -> int:
    for name in names:
        value = counters.get(name)
        if value is not None:
            return int(value)
    return 0


def _artifact_dict(artifact: Any) -> dict[str, Any]:
    for keyword in ("include_payload", "include_payloads"):
        try:
            value = artifact.to_dict(**{keyword: False})
            if isinstance(value, dict):
                return jsonable(value)
        except TypeError:
            continue
    value = artifact.to_dict() if hasattr(artifact, "to_dict") else artifact
    return jsonable(value)


def _artifact_identity(value: dict[str, Any], ordinal: int) -> tuple[str, str, str, str]:
    artifact_id = str(
        value.get("artifact_id")
        or value.get("artifact_name")
        or value.get("name")
        or value.get("id")
        or f"artifact-{ordinal:03d}"
    )
    relative_path = str(value.get("relative_path") or value.get("path") or artifact_id)
    media_type = str(value.get("media_type") or value.get("content_type") or "application/json")
    address = str(value.get("content_address") or value.get("address") or "")
    return artifact_id, relative_path, media_type, address


def _domain_from_runtime(domain_id: str, runtime: Any) -> FrontierReleaseDomain:
    bundle = runtime.bundle
    counters = _counter_map(runtime.summary)
    certification = runtime.certification
    reconciliation = runtime.reconciliation
    graph = getattr(runtime, "graph", None)
    replay = runtime.replay
    cert_count = int(getattr(certification, "check_count", 0))
    cert_passed = int(
        getattr(certification, "passed_check_count", getattr(certification, "passed_count", 0))
    )
    recon_checks = tuple(getattr(reconciliation, "checks", ()))
    graph_nodes = len(getattr(graph, "nodes", ())) if graph is not None else 0
    graph_edges = len(getattr(graph, "edges", ())) if graph is not None else 0
    graph_components = (
        int(getattr(graph, "connected_component_count", 0)) if graph is not None else 0
    )
    body = {
        "domain_id": domain_id,
        "name": _DOMAIN_NAMES[domain_id],
        "bundle_id": str(getattr(bundle, "bundle_id", _DOMAIN_BUNDLE_IDS[domain_id])),
        "bundle_version": str(getattr(bundle, "version", "")),
        "boundary": str(getattr(bundle, "boundary", "")),
        "bundle_content_address": str(getattr(bundle, "content_address", "")),
        "runtime_content_address": str(getattr(runtime, "content_address", "")),
        "artifact_count": len(getattr(bundle, "artifacts", ())),
        "source_count": _counter(counters, "sources", "source_count"),
        "record_count": _counter(counters, "records", "record_count"),
        "evaluation_check_count": _counter(
            counters, "checks", "evaluation_check_count", "evaluation_checks"
        ),
        "source_stage_count": _counter(
            counters, "stages", "source_runtime_stage_count", "runtime_stage_count"
        ),
        "closure_stage_count": len(getattr(runtime, "stages", ())),
        "certification_check_count": cert_count,
        "certification_passed_count": cert_passed,
        "certification_coverage_percent": float(getattr(certification, "coverage_percent", 0.0)),
        "reconciliation_check_count": len(recon_checks),
        "reconciliation_passed_count": sum(bool(item.passed) for item in recon_checks),
        "graph_node_count": graph_nodes,
        "graph_edge_count": graph_edges,
        "graph_component_count": graph_components,
        "deterministic_replay": bool(getattr(replay, "deterministic", False)),
        "accepted": bool(
            getattr(runtime, "accepted", False) and getattr(bundle, "accepted", False)
        ),
    }
    return FrontierReleaseDomain(
        **body,
        content_address=content_hash(body, prefix="frontier-release-domain"),
    )


def build_frontier_release_domain_runtimes(
    *,
    run_id: str = "frontier-release-closure-runtime",
) -> tuple[Any, ...]:
    require_non_empty(run_id, "run_id")
    return tuple(
        _DOMAIN_RUNTIME_FACTORIES[domain_id](
            bundle_id=_DOMAIN_BUNDLE_IDS[domain_id],
            run_id=f"{run_id}:{domain_id.lower()}",
        )
        for domain_id in FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS
    )


def build_frontier_release_domains(
    runtimes: tuple[Any, ...],
) -> tuple[FrontierReleaseDomain, ...]:
    if len(runtimes) != len(FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS):
        raise ValueError("frontier release requires exactly four domain runtimes")
    return tuple(
        _domain_from_runtime(domain_id, runtime)
        for domain_id, runtime in zip(FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS, runtimes, strict=True)
    )


def build_frontier_release_artifacts(
    runtimes: tuple[Any, ...],
) -> tuple[FrontierReleaseArtifact, ...]:
    rows: list[FrontierReleaseArtifact] = []
    for domain_id, runtime in zip(FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS, runtimes, strict=True):
        for ordinal, artifact in enumerate(getattr(runtime.bundle, "artifacts", ()), 1):
            value = _artifact_dict(artifact)
            artifact_id, relative_path, media_type, source_address = _artifact_identity(
                value, ordinal
            )
            body = {
                "artifact_ref": f"{domain_id}:{artifact_id}",
                "domain_id": domain_id,
                "artifact_id": artifact_id,
                "relative_path": relative_path,
                "media_type": media_type,
                "source_content_address": source_address,
            }
            rows.append(
                FrontierReleaseArtifact(
                    **body,
                    content_address=content_hash(body, prefix="frontier-release-artifact"),
                )
            )
    return tuple(sorted(rows, key=lambda item: (item.domain_id, item.artifact_id)))


def build_frontier_release_dependencies() -> tuple[FrontierReleaseDependency, ...]:
    rows: list[FrontierReleaseDependency] = []
    for ordinal, (source, target) in enumerate(
        combinations(FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS, 2), 1
    ):
        body = {
            "dependency_id": f"release-order:{source}->{target}",
            "source_domain_id": source,
            "target_domain_id": target,
            "relation": "release_precedes",
            "ordinal": ordinal,
            "required": True,
        }
        rows.append(
            FrontierReleaseDependency(
                **body,
                content_address=content_hash(body, prefix="frontier-release-dependency"),
            )
        )
    return tuple(rows)


def _gate(
    domain_id: str,
    gate_type: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> FrontierReleaseGate:
    body = {
        "gate_id": f"{domain_id}:{gate_type}",
        "domain_id": domain_id,
        "gate_type": gate_type,
        "passed": bool(passed),
        "observed": jsonable(observed),
        "expected": jsonable(expected),
        "detail": detail,
    }
    return FrontierReleaseGate(
        **body,
        content_address=content_hash(body, prefix="frontier-release-gate"),
    )


def build_frontier_release_gates(
    domains: tuple[FrontierReleaseDomain, ...],
) -> tuple[FrontierReleaseGate, ...]:
    gates: list[FrontierReleaseGate] = []
    for domain in domains:
        gates.extend(
            (
                _gate(
                    domain.domain_id,
                    "bundle_accepted",
                    domain.accepted,
                    domain.accepted,
                    True,
                    "source domain bundle and closure runtime are accepted",
                ),
                _gate(
                    domain.domain_id,
                    "artifact_manifest",
                    domain.artifact_count > 0,
                    domain.artifact_count,
                    ">0",
                    "source artifact manifest is non-empty",
                ),
                _gate(
                    domain.domain_id,
                    "certification_coverage",
                    domain.certification_coverage_percent == 100.0,
                    domain.certification_coverage_percent,
                    100.0,
                    "domain certification has complete local coverage",
                ),
                _gate(
                    domain.domain_id,
                    "reconciliation",
                    domain.reconciliation_check_count == domain.reconciliation_passed_count,
                    domain.reconciliation_passed_count,
                    domain.reconciliation_check_count,
                    "all domain reconciliation checks pass",
                ),
                _gate(
                    domain.domain_id,
                    "deterministic_replay",
                    domain.deterministic_replay,
                    domain.deterministic_replay,
                    True,
                    "domain source replay is deterministic",
                ),
                _gate(
                    domain.domain_id,
                    "runtime_depth",
                    domain.closure_stage_count >= 10,
                    domain.closure_stage_count,
                    ">=10",
                    "domain closure contains a substantive ordered runtime",
                ),
            )
        )
    return tuple(gates)


@dataclass(frozen=True, slots=True)
class FrontierReleaseSnapshot:
    bundle_id: str
    run_id: str
    domains: tuple[FrontierReleaseDomain, ...]
    artifacts: tuple[FrontierReleaseArtifact, ...]
    dependencies: tuple[FrontierReleaseDependency, ...]
    gates: tuple[FrontierReleaseGate, ...]
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return FRONTIER_RELEASE_CLOSURE_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"boundary": self.boundary}

    @property
    def domain_map(self) -> dict[str, FrontierReleaseDomain]:
        return {item.domain_id: item for item in self.domains}


def build_frontier_release_snapshot(
    *,
    run_id: str = "frontier-release-closure-runtime",
    bundle_id: str = "frontier-release-public-bundle",
) -> FrontierReleaseSnapshot:
    require_non_empty(run_id, "run_id")
    require_non_empty(bundle_id, "bundle_id")
    runtimes = build_frontier_release_domain_runtimes(run_id=run_id)
    domains = build_frontier_release_domains(runtimes)
    artifacts = build_frontier_release_artifacts(runtimes)
    dependencies = build_frontier_release_dependencies()
    gates = build_frontier_release_gates(domains)
    accepted = bool(
        len(domains) == len(FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS)
        and len(dependencies) == FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT
        and len(gates) == FRONTIER_RELEASE_CLOSURE_GATE_COUNT
        and all(item.accepted for item in domains)
        and all(item.passed for item in gates)
    )
    body = {
        "bundle_id": bundle_id,
        "run_id": run_id,
        "domains": domains,
        "artifacts": artifacts,
        "dependencies": dependencies,
        "gates": gates,
        "accepted": accepted,
    }
    return FrontierReleaseSnapshot(
        **body,
        content_address=content_hash(body, prefix="frontier-release-snapshot"),
    )


def frontier_release_snapshot_counts(snapshot: FrontierReleaseSnapshot) -> dict[str, int]:
    return {
        "domain_count": len(snapshot.domains),
        "artifact_count": len(snapshot.artifacts),
        "dependency_count": len(snapshot.dependencies),
        "gate_count": len(snapshot.gates),
        "accepted_domain_count": sum(item.accepted for item in snapshot.domains),
        "passed_gate_count": sum(item.passed for item in snapshot.gates),
        "source_count": sum(item.source_count for item in snapshot.domains),
        "record_count": sum(item.record_count for item in snapshot.domains),
        "evaluation_check_count": sum(item.evaluation_check_count for item in snapshot.domains),
        "closure_stage_count": sum(item.closure_stage_count for item in snapshot.domains),
        "certification_check_count": sum(
            item.certification_check_count for item in snapshot.domains
        ),
        "reconciliation_check_count": sum(
            item.reconciliation_check_count for item in snapshot.domains
        ),
        "graph_node_count": sum(item.graph_node_count for item in snapshot.domains),
        "graph_edge_count": sum(item.graph_edge_count for item in snapshot.domains),
    }


__all__ = [
    "FrontierReleaseSnapshot",
    "build_frontier_release_artifacts",
    "build_frontier_release_dependencies",
    "build_frontier_release_domain_runtimes",
    "build_frontier_release_domains",
    "build_frontier_release_gates",
    "build_frontier_release_snapshot",
    "frontier_release_snapshot_counts",
]
