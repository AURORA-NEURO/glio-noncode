"""Release manifest and artifact inventory for the module fabric."""

from __future__ import annotations

from .capability_registry import CapabilityRegistry, default_capability_registry
from .module_fabric_contracts import FabricFixture, FabricReleaseArtifact, FabricReleaseManifest, FabricState
from .module_fabric_depth import audit_module_fabric_depth
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_lineage import build_module_fabric_lineage
from .module_fabric_metrics import measure_module_fabric
from .module_fabric_public_data import audit_module_fabric_data, default_module_fabric_fixture
from .module_fabric_quality_gate import run_module_fabric_quality_gate
from .module_fabric_replay import replay_module_fabric
from .serialization import content_hash


def build_module_fabric_release(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
    *,
    release_id: str = "module-fabric-release",
) -> FabricReleaseManifest:
    value = fixture or default_module_fabric_fixture(registry)
    catalog = registry or default_capability_registry()
    data = audit_module_fabric_data(value, catalog)
    evaluation = evaluate_module_fabric_fixture(value, catalog)
    depth = audit_module_fabric_depth(value, catalog)
    replay = replay_module_fabric(value, catalog)
    quality = run_module_fabric_quality_gate(value, catalog)
    lineage = build_module_fabric_lineage(value, evaluation)
    metrics = measure_module_fabric(value, evaluation)
    artifacts = tuple(
        FabricReleaseArtifact(item[0], item[1], item[2], item[3])
        for item in (
            ("fixture", "public_fixture", value.content_address, "public aggregate fixture"),
            ("data-audit", "data_audit", data.content_address, "scope and source audit"),
            ("evaluation", "fixture_evaluation", evaluation.content_address, "record execution and checks"),
            ("metrics", "metrics", metrics.content_address, "conserved domain and reference counts"),
            ("depth", "depth_audit", depth.content_address, "repository-wide coverage audit"),
            ("lineage", "lineage_graph", lineage.content_address, "closed fixture-to-reference graph"),
            ("replay", "replay_report", replay.content_address, "deterministic replay report"),
            ("quality", "quality_gate", quality.content_address, "combined quality gate"),
        )
    )
    blockers = tuple(
        item
        for item, passed in (
            ("data_audit_failed", data.accepted),
            ("evaluation_failed", evaluation.accepted),
            ("depth_failed", depth.accepted),
            ("replay_failed", replay.accepted),
            ("quality_failed", quality.accepted),
            ("lineage_failed", lineage.accepted),
        )
        if not passed
    )
    state = FabricState.ACCEPTED if not blockers else FabricState.REVIEW
    body = {"release_id": release_id, "fixture_id": value.fixture_id, "state": state, "artifacts": artifacts, "blockers": blockers}
    return FabricReleaseManifest(release_id, value.fixture_id, state, artifacts, blockers, content_hash(body, prefix="module-fabric-release"))


def verify_module_fabric_release(manifest: FabricReleaseManifest) -> tuple[str, ...]:
    issues: list[str] = []
    if not manifest.artifacts:
        issues.append("missing_artifacts")
    if len({item.artifact_id for item in manifest.artifacts}) != len(manifest.artifacts):
        issues.append("duplicate_artifact_id")
    if any(not item.content_address for item in manifest.artifacts):
        issues.append("missing_artifact_address")
    if manifest.state is FabricState.ACCEPTED and manifest.blockers:
        issues.append("accepted_release_has_blockers")
    return tuple(issues)


__all__ = ["build_module_fabric_release", "verify_module_fabric_release"]
