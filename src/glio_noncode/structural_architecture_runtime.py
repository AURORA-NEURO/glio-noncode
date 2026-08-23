"""Twenty-stage end-to-end runtime for the composed D02 architecture."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash
from .structural_architecture_access import build_structural_architecture_access_manifest
from .structural_architecture_bundle import (
    build_structural_architecture_artifacts,
    build_structural_architecture_release,
)
from .structural_architecture_contracts import (
    StructuralArchitectureFixture,
    StructuralArchitectureRuntime,
    StructuralArchitectureRuntimeStage,
    StructuralArchitectureState,
    addressed,
)
from .structural_architecture_failures import run_structural_architecture_failure_probes
from .structural_architecture_lineage import build_structural_architecture_ledger
from .structural_architecture_metrics import measure_structural_architecture
from .structural_architecture_observability import observe_structural_architecture
from .structural_architecture_operations import evaluate_structural_architecture_fixture
from .structural_architecture_plan import compile_structural_architecture_plan
from .structural_architecture_policy import evaluate_structural_architecture_policies
from .structural_architecture_public_data import (
    audit_structural_architecture_data,
    default_structural_architecture_fixture,
)
from .structural_architecture_replay import replay_structural_architecture
from .structural_architecture_review import build_structural_architecture_review_queue
from .structural_architecture_runbook import build_structural_architecture_runbook
from .structural_architecture_schema import (
    default_structural_architecture_schema,
    validate_structural_architecture_schema,
)
from .structural_architecture_validation import build_structural_architecture_validation_matrix


def run_structural_architecture(
    fixture: StructuralArchitectureFixture | None = None,
    *,
    run_id: str = "structural-architecture-runtime",
) -> StructuralArchitectureRuntime:
    """Run ingestion, all four operation families, controls, and release."""

    value = fixture or default_structural_architecture_fixture()
    stages: list[StructuralArchitectureRuntimeStage] = []
    audit = audit_structural_architecture_data(value)
    _add_stage(
        stages,
        "fixture-loaded",
        StructuralArchitectureState.ACCEPTED,
        {},
        value.to_dict(),
        "load public aggregate fixture",
    )
    _add_stage(
        stages,
        "sources-audited",
        _state(audit.accepted),
        value.to_dict(),
        audit.to_dict(),
        "audit public HTTPS receipts and payload scope",
    )
    plan = compile_structural_architecture_plan(value)
    _add_stage(
        stages,
        "plan-compiled",
        _state(plan.accepted),
        value.to_dict(),
        plan.to_dict(),
        "compile sixteen operation dependencies",
    )
    policies = evaluate_structural_architecture_policies(value.fixture_id, value.cases)
    _add_stage(
        stages,
        "policy-scored",
        _state(policies.accepted),
        value.context_key,
        policies.to_dict(),
        "score context, source, and control policy",
    )
    _add_stage(
        stages,
        "ingestion-closed",
        _state(len(value.cases) == 64),
        value.fixture_id,
        {"case_count": len(value.cases)},
        "admit all bounded case envelopes",
    )
    _add_stage(
        stages,
        "core-family-ready",
        _state(_family_case_count(value, "core") == 16),
        value.fixture_id,
        {"family": "core", "case_count": _family_case_count(value, "core")},
        "close reconstruction and consensus family",
    )
    _add_stage(
        stages,
        "beta-family-ready",
        _state(_family_case_count(value, "beta") == 16),
        value.fixture_id,
        {"family": "beta", "case_count": _family_case_count(value, "beta")},
        "close focal, cluster, circle, and bridge family",
    )
    _add_stage(
        stages,
        "haplotype-family-ready",
        _state(_family_case_count(value, "haplotype") == 16),
        value.fixture_id,
        {"family": "haplotype", "case_count": _family_case_count(value, "haplotype")},
        "close phased, allele, graph, and repeat family",
    )
    _add_stage(
        stages,
        "frontier-family-ready",
        _state(_family_case_count(value, "frontier") == 16),
        value.fixture_id,
        {"family": "frontier", "case_count": _family_case_count(value, "frontier")},
        "close repeat, compound, uncertainty, and export family",
    )
    evaluation = evaluate_structural_architecture_fixture(value)
    _add_stage(
        stages,
        "cases-executed",
        _state(evaluation.accepted),
        value.to_dict(),
        evaluation.to_dict(),
        "execute all sixteen adapters and controls",
    )
    review_queue = build_structural_architecture_review_queue(evaluation)
    _add_stage(
        stages,
        "review-routed",
        _state(review_queue.accepted),
        evaluation.to_dict(),
        review_queue.to_dict(),
        "route every held control",
    )
    ledger = build_structural_architecture_ledger(value, evaluation)
    _add_stage(
        stages,
        "lineage-linked",
        _state(ledger.accepted),
        evaluation.to_dict(),
        ledger.to_dict(),
        "hash-link every case receipt",
    )
    metrics = measure_structural_architecture(value, evaluation)
    _add_stage(
        stages,
        StructuralArchitectureState.ACCEPTED.value + "-metrics",
        StructuralArchitectureState.ACCEPTED,
        evaluation.to_dict(),
        metrics.to_dict(),
        "materialize operation and plane metrics",
    )
    validation = build_structural_architecture_validation_matrix(value, evaluation)
    _add_stage(
        stages,
        "validation-matrix-closed",
        _state(validation.accepted),
        evaluation.to_dict(),
        validation.to_dict(),
        "close seven validation planes",
    )
    schema = default_structural_architecture_schema()
    schema_check = validate_structural_architecture_schema(value)
    _add_stage(
        stages,
        "schema-closed",
        _state(schema.accepted and schema_check.accepted),
        {},
        {"schema": schema.to_dict(), "validation": schema_check.to_dict()},
        "close aggregate export schema",
    )
    artifacts = build_structural_architecture_artifacts(value, evaluation, ledger)
    _add_stage(
        stages,
        "artifacts-materialized",
        _state(len(artifacts) == 6),
        {},
        tuple(item.to_dict() for item in artifacts),
        "materialize six offline artifacts",
    )
    access = build_structural_architecture_access_manifest(artifacts)
    _add_stage(
        stages,
        "access-closed",
        _state(access.accepted),
        tuple(item.artifact_id for item in artifacts),
        access.to_dict(),
        "close export allow-list",
    )
    replay = replay_structural_architecture(value)
    _add_stage(
        stages,
        "replay-closed",
        _state(replay.deterministic and replay.accepted),
        evaluation.to_dict(),
        replay.to_dict(),
        "verify deterministic replay",
    )
    release = build_structural_architecture_release(value, artifacts, evaluation, ledger)
    _add_stage(
        stages,
        "release-gated",
        release.state,
        tuple(item.to_dict() for item in artifacts),
        release.to_dict(),
        "publish only after all quality checks",
    )
    failure_probes = run_structural_architecture_failure_probes(value)
    runbook = build_structural_architecture_runbook()
    final_state = (
        StructuralArchitectureState.PUBLISHED
        if release.published and failure_probes.accepted and runbook.executable
        else StructuralArchitectureState.REVIEW
    )
    _add_stage(
        stages,
        "runtime-finalized",
        final_state,
        {"stage_count": len(stages)},
        {
            "state": final_state.value,
            "failure_probes": failure_probes.to_dict(),
            "runbook": runbook.to_dict(),
        },
        "finalize addressed runtime",
    )
    body = {
        "run_id": run_id,
        "fixture_id": value.fixture_id,
        "state": final_state,
        "stages": tuple(stages),
        "evaluation": evaluation,
        "plan": plan,
        "review_queue": review_queue,
        "ledger": ledger,
        "artifacts": artifacts,
        "release": release,
    }
    runtime = StructuralArchitectureRuntime(
        **body, content_address=addressed(body, "structural-runtime")
    )
    # The observability projection is intentionally computed after runtime
    # construction so it cannot influence the release state.
    observe_structural_architecture(runtime)
    return runtime


def run_structural_architecture_from_mapping(raw: dict[str, Any]) -> StructuralArchitectureRuntime:
    """Run a fixture mapping supplied by a caller."""

    return run_structural_architecture(StructuralArchitectureFixture.from_mapping(raw))


def _add_stage(
    stages: list[StructuralArchitectureRuntimeStage],
    stage_id: str,
    state: StructuralArchitectureState,
    input_value: Any,
    output_value: Any,
    detail: str,
) -> None:
    ordinal = len(stages) + 1
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": content_hash(input_value),
        "output_address": content_hash(output_value),
        "detail": detail,
    }
    stages.append(
        StructuralArchitectureRuntimeStage(
            **body, content_address=addressed(body, "structural-stage")
        )
    )


def _state(accepted: bool) -> StructuralArchitectureState:
    return StructuralArchitectureState.ACCEPTED if accepted else StructuralArchitectureState.REVIEW


def _family_case_count(fixture: StructuralArchitectureFixture, family: str) -> int:
    return sum(item.family == family for item in fixture.operations) * 4


__all__ = ["run_structural_architecture", "run_structural_architecture_from_mapping"]
