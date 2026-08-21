"""Runtime orchestration for the Domain 05 C05–C08 pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .molecular_atlas_bundle import MolecularAtlasBundleBuilder
from .molecular_atlas_fixture_eval import evaluate_molecular_atlas_fixture
from .molecular_atlas_lineage import build_molecular_atlas_lineage
from .molecular_atlas_public_data import (
    MOLECULAR_ATLAS_CONTEXT_KEY,
    audit_molecular_atlas_data,
    load_molecular_atlas_fixture,
)
from .molecular_atlas_quality_gate import evaluate_molecular_atlas_quality_gate
from .molecular_atlas_reconciliation import reconcile_molecular_atlas_views
from .molecular_atlas_replay import replay_molecular_atlas_evaluation
from .molecular_atlas_scenario_matrix import evaluate_molecular_atlas_scenarios
from .serialization import content_hash, jsonable


class MolecularAtlasRuntimeStage(StrEnum):
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
class MolecularAtlasPipelineRequest:
    """Descriptor that names a fixture and expected exact context."""

    fixture: dict[str, Any]
    expected_context_key: str = MOLECULAR_ATLAS_CONTEXT_KEY
    accepted_only: bool = True

    @classmethod
    def from_file(cls, path: str | Path) -> MolecularAtlasPipelineRequest:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValidationError("molecular atlas pipeline request must be an object")
        fixture = payload.get("fixture", payload)
        if isinstance(fixture, str):
            fixture = {"fixture": fixture}
        if not isinstance(fixture, dict):
            raise ValidationError("molecular atlas pipeline fixture must be an object")
        return cls(
            fixture,
            str(payload.get("expected_context_key", MOLECULAR_ATLAS_CONTEXT_KEY)),
            bool(payload.get("accepted_only", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasStageReceipt:
    """Bounded stage outcome."""

    stage: MolecularAtlasRuntimeStage
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasRuntimeReport:
    """End-to-end C05–C08 runtime result."""

    fixture_id: str
    fixture_version: str
    context_key: str
    stages: tuple[MolecularAtlasStageReceipt, ...]
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
    stage: MolecularAtlasRuntimeStage, passed: bool, detail: str
) -> MolecularAtlasStageReceipt:
    body = {"stage": stage, "passed": passed, "detail": detail}
    return MolecularAtlasStageReceipt(stage, passed, detail, _address(body))


def run_molecular_atlas_pipeline(
    request: MolecularAtlasPipelineRequest,
) -> MolecularAtlasRuntimeReport:
    """Run data, execution, replay, scenarios, lineage, quality, and bundle stages."""

    fixture = load_molecular_atlas_fixture(request.fixture)
    stages: list[MolecularAtlasStageReceipt] = []
    data = audit_molecular_atlas_data(fixture)
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.DATA,
            data.accepted,
            f"{len(data.checks)} data checks evaluated",
        )
    )
    evaluation = evaluate_molecular_atlas_fixture(fixture)
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.EVALUATION,
            evaluation.accepted,
            f"{len(evaluation.checks)} execution checks evaluated",
        )
    )
    replay = replay_molecular_atlas_evaluation(evaluation, fixture=fixture)
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.REPLAY,
            replay.accepted,
            f"{len(replay.checks)} replay checks evaluated",
        )
    )
    scenarios = evaluate_molecular_atlas_scenarios(fixture, report=evaluation)
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.SCENARIOS,
            scenarios.accepted,
            f"{len(scenarios.results)} state and histone scenarios evaluated",
        )
    )
    lineage = build_molecular_atlas_lineage(evaluation, fixture=fixture)
    lineage_audit = lineage.audit(evaluation)
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.LINEAGE,
            lineage_audit.passed,
            f"{lineage_audit.node_count} nodes and {lineage_audit.edge_count} edges audited",
        )
    )
    quality = evaluate_molecular_atlas_quality_gate(fixture)
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.QUALITY_GATE,
            quality.accepted,
            f"{len(quality.checks)} quality checks evaluated",
        )
    )
    reconciliation = reconcile_molecular_atlas_views(
        fixture, data, evaluation, replay, scenarios, lineage
    )
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.RECONCILIATION,
            reconciliation.accepted,
            f"{len(reconciliation.checks)} reconciliation checks evaluated",
        )
    )
    bundle = MolecularAtlasBundleBuilder().build(
        evaluation, fixture=fixture, accepted_only=request.accepted_only
    )
    bundle_failures = MolecularAtlasBundleBuilder().verify(bundle)
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.BUNDLE,
            not bundle_failures,
            f"{len(bundle.entries)} bundle entries rendered",
        )
    )
    context_match = (
        fixture.context_key == request.expected_context_key == MOLECULAR_ATLAS_CONTEXT_KEY
    )
    stages.append(
        _stage(
            MolecularAtlasRuntimeStage.CONTEXT,
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
    return MolecularAtlasRuntimeReport(
        fixture.fixture_id,
        fixture.fixture_version,
        fixture.context_key,
        tuple(stages),
        evaluation.content_address,
        quality.content_address,
        bundle.content_address,
        _address(body),
    )


def run_molecular_atlas_pipeline_file(path: str | Path) -> MolecularAtlasRuntimeReport:
    """Run a JSON descriptor loaded from disk."""

    return run_molecular_atlas_pipeline(MolecularAtlasPipelineRequest.from_file(path))


__all__ = [
    "MolecularAtlasPipelineRequest",
    "MolecularAtlasRuntimeReport",
    "MolecularAtlasRuntimeStage",
    "MolecularAtlasStageReceipt",
    "run_molecular_atlas_pipeline",
    "run_molecular_atlas_pipeline_file",
]
