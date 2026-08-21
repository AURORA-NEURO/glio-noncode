"""Runtime orchestration for the Domain 04 C09–C12 evidence pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .reference_governance_bundle import ReferenceGovernanceBundleBuilder
from .reference_governance_fixture_eval import evaluate_reference_governance_fixture
from .reference_governance_lineage import build_reference_governance_lineage
from .reference_governance_public_data import (
    REFERENCE_GOVERNANCE_CONTEXT_KEY,
    audit_reference_governance_data,
    load_reference_governance_fixture,
)
from .reference_governance_quality_gate import evaluate_reference_governance_quality_gate
from .reference_governance_reconciliation import reconcile_reference_governance_views
from .reference_governance_replay import replay_reference_governance_evaluation
from .reference_governance_scenario_matrix import evaluate_reference_governance_scenarios
from .serialization import content_hash, jsonable


class ReferenceGovernanceRuntimeStage(StrEnum):
    """Ordered stages emitted by the runtime."""

    DATA = "data"
    EVALUATION = "evaluation"
    REPLAY = "replay"
    SCENARIOS = "scenarios"
    LINEAGE = "lineage"
    QUALITY_GATE = "quality_gate"
    RECONCILIATION = "reconciliation"
    BUNDLE = "bundle"
    CONTEXT = "context"


@dataclass(frozen=True, slots=True)
class ReferenceGovernancePipelineRequest:
    """Runtime request loaded from a descriptor without embedding payloads."""

    fixture: dict[str, Any]
    expected_context_key: str = REFERENCE_GOVERNANCE_CONTEXT_KEY
    accepted_only: bool = True

    @classmethod
    def from_file(cls, path: str | Path) -> ReferenceGovernancePipelineRequest:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValidationError("governance pipeline request must be an object")
        fixture = payload.get("fixture", payload)
        if not isinstance(fixture, dict):
            raise ValidationError("governance pipeline fixture must be an object")
        return cls(
            fixture,
            str(payload.get("expected_context_key", REFERENCE_GOVERNANCE_CONTEXT_KEY)),
            bool(payload.get("accepted_only", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceStageReceipt:
    """One runtime stage receipt with a bounded summary."""

    stage: ReferenceGovernanceRuntimeStage
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceRuntimeReport:
    """End-to-end C09–C12 runtime result."""

    fixture_id: str
    fixture_version: str
    context_key: str
    stages: tuple[ReferenceGovernanceStageReceipt, ...]
    evaluation_address: str
    quality_address: str
    bundle_address: str
    content_address: str

    @property
    def published(self) -> bool:
        return all(stage.passed for stage in self.stages)

    @property
    def failed_stages(self) -> tuple[str, ...]:
        return tuple(stage.stage.value for stage in self.stages if not stage.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "published": self.published,
            "failed_stages": list(self.failed_stages),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _stage(
    stage: ReferenceGovernanceRuntimeStage, passed: bool, detail: str
) -> ReferenceGovernanceStageReceipt:
    body = {"stage": stage, "passed": passed, "detail": detail}
    return ReferenceGovernanceStageReceipt(stage, passed, detail, _address(body))


def run_reference_governance_pipeline(
    request: ReferenceGovernancePipelineRequest,
) -> ReferenceGovernanceRuntimeReport:
    """Run data, execution, replay, scenario, lineage, quality, and bundle stages."""

    fixture = load_reference_governance_fixture(request.fixture)
    stages: list[ReferenceGovernanceStageReceipt] = []
    data = audit_reference_governance_data(fixture)
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.DATA,
            data.accepted,
            f"{len(data.checks)} data checks evaluated",
        )
    )
    evaluation = evaluate_reference_governance_fixture(fixture)
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.EVALUATION,
            evaluation.accepted,
            f"{len(evaluation.checks)} execution checks evaluated",
        )
    )
    replay = replay_reference_governance_evaluation(evaluation, fixture=fixture)
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.REPLAY,
            replay.accepted,
            f"{len(replay.checks)} replay checks evaluated",
        )
    )
    scenarios = evaluate_reference_governance_scenarios(fixture, report=evaluation)
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.SCENARIOS,
            scenarios.accepted,
            f"{len(scenarios.results)} state scenarios evaluated",
        )
    )
    lineage = build_reference_governance_lineage(evaluation, fixture=fixture)
    lineage_audit = lineage.audit(evaluation)
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.LINEAGE,
            lineage_audit.passed,
            f"{lineage_audit.node_count} nodes and {lineage_audit.edge_count} edges audited",
        )
    )
    quality = evaluate_reference_governance_quality_gate(fixture)
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.QUALITY_GATE,
            quality.accepted,
            f"{len(quality.checks)} quality checks evaluated",
        )
    )
    reconciliation = reconcile_reference_governance_views(
        fixture, data, evaluation, replay, scenarios, lineage
    )
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.RECONCILIATION,
            reconciliation.accepted,
            f"{len(reconciliation.checks)} reconciliation checks evaluated",
        )
    )
    bundle = ReferenceGovernanceBundleBuilder().build(
        evaluation, fixture=fixture, accepted_only=request.accepted_only
    )
    bundle_failures = ReferenceGovernanceBundleBuilder().verify(bundle)
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.BUNDLE,
            not bundle_failures,
            f"{len(bundle.entries)} bundle entries rendered",
        )
    )
    context_match = (
        fixture.context_key == request.expected_context_key == REFERENCE_GOVERNANCE_CONTEXT_KEY
    )
    stages.append(
        _stage(
            ReferenceGovernanceRuntimeStage.CONTEXT,
            context_match,
            "requested context matches the fixture context",
        )
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "stages": stages,
        "evaluation_address": evaluation.content_address,
        "quality_address": quality.content_address,
        "bundle_address": bundle.content_address,
    }
    return ReferenceGovernanceRuntimeReport(
        fixture.fixture_id,
        fixture.fixture_version,
        fixture.context_key,
        tuple(stages),
        evaluation.content_address,
        quality.content_address,
        bundle.content_address,
        _address(body),
    )


def run_reference_governance_pipeline_file(path: str | Path) -> ReferenceGovernanceRuntimeReport:
    """Run a descriptor loaded from disk."""

    return run_reference_governance_pipeline(ReferenceGovernancePipelineRequest.from_file(path))


__all__ = [
    "ReferenceGovernancePipelineRequest",
    "ReferenceGovernanceRuntimeReport",
    "ReferenceGovernanceRuntimeStage",
    "ReferenceGovernanceStageReceipt",
    "run_reference_governance_pipeline",
    "run_reference_governance_pipeline_file",
]
