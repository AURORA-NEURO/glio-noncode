"""Quality gate combining all module-fabric assurance surfaces."""

from __future__ import annotations

from .capability_registry import CapabilityRegistry, default_capability_registry
from .module_fabric_contracts import (
    MODULE_FABRIC_ARTIFACT_COUNT,
    MODULE_FABRIC_CHECK_COUNT,
    MODULE_FABRIC_GLOBAL_CHECK_COUNT,
    MODULE_FABRIC_STAGE_COUNT,
    FabricFixture,
    FabricQualityReport,
    FabricRole,
    FabricState,
    make_quality_check,
)
from .module_fabric_depth import audit_module_fabric_depth
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_lineage import build_module_fabric_lineage, verify_module_fabric_lineage
from .module_fabric_metrics import measure_module_fabric
from .module_fabric_public_data import audit_module_fabric_data, default_module_fabric_fixture
from .module_fabric_replay import replay_module_fabric
from .serialization import content_hash


def run_module_fabric_quality_gate(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
) -> FabricQualityReport:
    value = fixture or default_module_fabric_fixture(registry)
    catalog = registry or default_capability_registry()
    data = audit_module_fabric_data(value, catalog)
    evaluation = evaluate_module_fabric_fixture(value, catalog)
    depth = audit_module_fabric_depth(value, catalog)
    replay = replay_module_fabric(value, catalog)
    lineage = build_module_fabric_lineage(value, evaluation)
    metrics = measure_module_fabric(value, evaluation)
    checks = (
        make_quality_check("data", data.accepted, data.accepted, True, "public data boundary is accepted"),
        make_quality_check("evaluation", evaluation.accepted, evaluation.accepted, True, "all fixture rows pass expected states"),
        make_quality_check("depth", depth.accepted, depth.accepted, True, "all depth checks pass"),
        make_quality_check("replay", replay.accepted, replay.accepted, True, "deterministic replay passes"),
        make_quality_check("lineage", lineage.accepted and not verify_module_fabric_lineage(lineage), lineage.issues, (), "lineage graph is closed"),
        make_quality_check("record-conservation", metrics.record_count == len(value.records), metrics.record_count, len(value.records), "metrics conserve fixture records"),
        make_quality_check("domain-conservation", metrics.domain_count == 16, metrics.domain_count, 16, "metrics conserve all domains"),
        make_quality_check("positive-floor", metrics.accepted_count == 16, metrics.accepted_count, 16, "all positive rows are accepted"),
        make_quality_check("control-floor", metrics.review_count == 16, metrics.review_count, 16, "all controls are held"),
        make_quality_check("reference-closure", metrics.failed_reference_count == 0, metrics.failed_reference_count, 0, "no declared reference is unresolved"),
        make_quality_check("fixture-address", value.content_address.startswith("sha256:"), value.content_address[:7], "sha256:", "fixture address is stable"),
        make_quality_check("evaluation-address", evaluation.content_address.startswith("module-fabric-evaluation:"), evaluation.content_address[:24], "module-fabric-evaluation:", "evaluation address is stable"),
        make_quality_check("evaluation-check-denominator", len(evaluation.checks) == MODULE_FABRIC_CHECK_COUNT, len(evaluation.checks), MODULE_FABRIC_CHECK_COUNT, "record and global evaluation checks are closed"),
        make_quality_check("global-check-denominator", sum(item.record_id == "__fixture__" for item in evaluation.checks) == MODULE_FABRIC_GLOBAL_CHECK_COUNT, sum(item.record_id == "__fixture__" for item in evaluation.checks), MODULE_FABRIC_GLOBAL_CHECK_COUNT, "global evaluation checks are retained"),
        make_quality_check("depth-check-denominator", len(depth.checks) == 30 and depth.accepted, len(depth.checks), 30, "depth audit closes the expanded foundation surface"),
        make_quality_check("positive-role-state", all(item.role is FabricRole.POSITIVE and item.observed_state is FabricState.ACCEPTED for item in evaluation.executions if item.role is FabricRole.POSITIVE), 16, 16, "positive role rows are accepted"),
        make_quality_check("control-role-state", all(item.role is FabricRole.CONTROL and item.observed_state is FabricState.REVIEW for item in evaluation.executions if item.role is FabricRole.CONTROL), 16, 16, "control role rows remain review"),
        make_quality_check("artifact-denominator", MODULE_FABRIC_ARTIFACT_COUNT == 8, MODULE_FABRIC_ARTIFACT_COUNT, 8, "release materializes eight artifacts"),
        make_quality_check("stage-denominator", MODULE_FABRIC_STAGE_COUNT == 24, MODULE_FABRIC_STAGE_COUNT, 24, "runtime foundation denominator is twenty-four"),
        make_quality_check("source-addresses", all(item.content_address.startswith("sha256:") for item in value.sources), len(value.sources), 5, "all public sources are addressed"),
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": accepted}
    return FabricQualityReport(value.fixture_id, tuple(checks), accepted, content_hash(body, prefix="module-fabric-quality"))


__all__ = ["run_module_fabric_quality_gate"]
