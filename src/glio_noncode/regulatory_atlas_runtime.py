"""Runtime orchestration for the Domain 05 regulatory atlas pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .regulatory_atlas_bundle import RegulatoryAtlasBundleBuilder
from .regulatory_atlas_fixture_eval import evaluate_regulatory_atlas_fixture
from .regulatory_atlas_lineage import build_regulatory_atlas_lineage
from .regulatory_atlas_public_data import (
    REGULATORY_ATLAS_CONTEXT_KEY,
    audit_regulatory_atlas_data,
    load_regulatory_atlas_fixture,
)
from .regulatory_atlas_quality_gate import evaluate_regulatory_atlas_quality_gate
from .regulatory_atlas_reconciliation import reconcile_regulatory_atlas_views
from .regulatory_atlas_replay import replay_regulatory_atlas_evaluation
from .regulatory_atlas_scenario_matrix import evaluate_regulatory_atlas_scenarios
from .serialization import content_hash, jsonable


class RegulatoryAtlasRuntimeStage(StrEnum):
    """Ordered runtime stage identities."""

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
class RegulatoryAtlasPipelineRequest:
    """Descriptor that names a fixture and expected exact context."""

    fixture: dict[str, Any]
    expected_context_key: str = REGULATORY_ATLAS_CONTEXT_KEY
    accepted_only: bool = True

    @classmethod
    def from_file(cls, path: str | Path) -> RegulatoryAtlasPipelineRequest:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValidationError("regulatory atlas pipeline request must be an object")
        fixture = payload.get("fixture", payload)
        if isinstance(fixture, str):
            fixture = {"fixture": fixture}
        if not isinstance(fixture, dict):
            raise ValidationError("regulatory atlas pipeline fixture must be an object")
        return cls(
            fixture,
            str(payload.get("expected_context_key", REGULATORY_ATLAS_CONTEXT_KEY)),
            bool(payload.get("accepted_only", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasStageReceipt:
    """Bounded stage outcome."""

    stage: RegulatoryAtlasRuntimeStage
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasRuntimeReport:
    """End-to-end C01–C04 runtime result."""

    fixture_id: str
    fixture_version: str
    context_key: str
    stages: tuple[RegulatoryAtlasStageReceipt, ...]
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
    stage: RegulatoryAtlasRuntimeStage, passed: bool, detail: str
) -> RegulatoryAtlasStageReceipt:
    body = {"stage": stage, "passed": passed, "detail": detail}
    return RegulatoryAtlasStageReceipt(stage, passed, detail, _address(body))


def run_regulatory_atlas_pipeline(
    request: RegulatoryAtlasPipelineRequest,
) -> RegulatoryAtlasRuntimeReport:
    """Run data, execution, replay, scenarios, lineage, quality, and bundle stages."""

    fixture = load_regulatory_atlas_fixture(request.fixture)
    stages: list[RegulatoryAtlasStageReceipt] = []
    data = audit_regulatory_atlas_data(fixture)
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.DATA,
            data.accepted,
            f"{len(data.checks)} data checks evaluated",
        )
    )
    evaluation = evaluate_regulatory_atlas_fixture(fixture)
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.EVALUATION,
            evaluation.accepted,
            f"{len(evaluation.checks)} execution checks evaluated",
        )
    )
    replay = replay_regulatory_atlas_evaluation(evaluation, fixture=fixture)
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.REPLAY,
            replay.accepted,
            f"{len(replay.checks)} replay checks evaluated",
        )
    )
    scenarios = evaluate_regulatory_atlas_scenarios(fixture, report=evaluation)
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.SCENARIOS,
            scenarios.accepted,
            f"{len(scenarios.results)} state scenarios evaluated",
        )
    )
    lineage = build_regulatory_atlas_lineage(evaluation, fixture=fixture)
    lineage_audit = lineage.audit(evaluation)
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.LINEAGE,
            lineage_audit.passed,
            f"{lineage_audit.node_count} nodes and {lineage_audit.edge_count} edges audited",
        )
    )
    quality = evaluate_regulatory_atlas_quality_gate(fixture)
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.QUALITY_GATE,
            quality.accepted,
            f"{len(quality.checks)} quality checks evaluated",
        )
    )
    reconciliation = reconcile_regulatory_atlas_views(
        fixture, data, evaluation, replay, scenarios, lineage
    )
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.RECONCILIATION,
            reconciliation.accepted,
            f"{len(reconciliation.checks)} reconciliation checks evaluated",
        )
    )
    bundle = RegulatoryAtlasBundleBuilder().build(
        evaluation, fixture=fixture, accepted_only=request.accepted_only
    )
    bundle_failures = RegulatoryAtlasBundleBuilder().verify(bundle)
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.BUNDLE,
            not bundle_failures,
            f"{len(bundle.entries)} bundle entries rendered",
        )
    )
    context_match = (
        fixture.context_key == request.expected_context_key == REGULATORY_ATLAS_CONTEXT_KEY
    )
    stages.append(
        _stage(
            RegulatoryAtlasRuntimeStage.CONTEXT,
            context_match,
            "requested context matches fixture context",
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
    return RegulatoryAtlasRuntimeReport(
        fixture.fixture_id,
        fixture.fixture_version,
        fixture.context_key,
        tuple(stages),
        evaluation.content_address,
        quality.content_address,
        bundle.content_address,
        _address(body),
    )


def run_regulatory_atlas_pipeline_file(path: str | Path) -> RegulatoryAtlasRuntimeReport:
    """Run a JSON descriptor loaded from disk."""

    return run_regulatory_atlas_pipeline(RegulatoryAtlasPipelineRequest.from_file(path))


__all__ = [
    "RegulatoryAtlasPipelineRequest",
    "RegulatoryAtlasRuntimeReport",
    "RegulatoryAtlasRuntimeStage",
    "RegulatoryAtlasStageReceipt",
    "run_regulatory_atlas_pipeline",
    "run_regulatory_atlas_pipeline_file",
]
