"""Five-stage runtime composition for the C05–C08 annotation evidence plane."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .reference_annotation_bundle import (
    ReferenceAnnotationBundleBuilder,
    ReferenceAnnotationBundleFormat,
)
from .reference_annotation_fixture_eval import evaluate_reference_annotation_fixture
from .reference_annotation_lineage import build_reference_annotation_lineage
from .reference_annotation_public_data import (
    ReferenceAnnotationFixture,
    load_reference_annotation_fixture,
)
from .reference_annotation_quality_gate import evaluate_reference_annotation_quality_gate
from .reference_annotation_reconciliation import reconcile_reference_annotation_views
from .reference_annotation_replay import replay_reference_annotation_evaluation
from .reference_annotation_scenario_matrix import evaluate_reference_annotation_scenarios
from .serialization import content_hash, jsonable


class ReferenceAnnotationRuntimeStage(StrEnum):
    PUBLIC_DATA = "public_data"
    FIXTURE_EVALUATION = "fixture_evaluation"
    REPLAY = "replay"
    RECONCILIATION = "reconciliation"
    QUALITY_GATE = "quality_gate"
    BUNDLE = "bundle"


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationRuntimeRequest:
    fixture_path: str
    context_key: str | None = None
    accepted_only: bool = True
    output_format: ReferenceAnnotationBundleFormat = ReferenceAnnotationBundleFormat.JSON

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationStageReceipt:
    stage: ReferenceAnnotationRuntimeStage
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationRuntimeReport:
    fixture_id: str
    fixture_version: str
    context_key: str
    published: bool
    stage_receipts: tuple[ReferenceAnnotationStageReceipt, ...]
    bundle: dict[str, Any]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(receipt.accepted for receipt in self.stage_receipts)

    @property
    def failed_stages(self) -> tuple[str, ...]:
        return tuple(receipt.stage.value for receipt in self.stage_receipts if not receipt.accepted)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_stages": list(self.failed_stages),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _stage(
    stage: ReferenceAnnotationRuntimeStage, accepted: bool, detail: str
) -> ReferenceAnnotationStageReceipt:
    body = {"stage": stage, "accepted": accepted, "detail": detail}
    return ReferenceAnnotationStageReceipt(stage, accepted, detail, _address(body))


def run_reference_annotation_pipeline(
    request: ReferenceAnnotationRuntimeRequest,
    *,
    fixture: ReferenceAnnotationFixture | None = None,
) -> ReferenceAnnotationRuntimeReport:
    """Run the staged annotation pipeline and publish only an accepted projection."""

    selected = fixture
    if selected is None:
        with Path(request.fixture_path).open("r", encoding="utf-8") as handle:
            selected = load_reference_annotation_fixture(json.load(handle))
    context_match = request.context_key is None or request.context_key == selected.context_key
    receipts = [
        _stage(
            ReferenceAnnotationRuntimeStage.PUBLIC_DATA,
            context_match,
            "public fixture loaded and context checked",
        )
    ]
    evaluation = evaluate_reference_annotation_fixture(selected)
    receipts.append(
        _stage(
            ReferenceAnnotationRuntimeStage.FIXTURE_EVALUATION,
            evaluation.accepted,
            f"{len(evaluation.receipts)} records and {len(evaluation.checks)} checks evaluated",
        )
    )
    replay = replay_reference_annotation_evaluation(
        evaluation, expected_context_key=request.context_key or selected.context_key
    )
    receipts.append(
        _stage(
            ReferenceAnnotationRuntimeStage.REPLAY,
            replay.accepted,
            f"{len(replay.checks)} replay checks evaluated",
        )
    )
    scenarios = evaluate_reference_annotation_scenarios(selected, report=evaluation)
    builder = ReferenceAnnotationBundleBuilder()
    bundle = builder.build(
        evaluation, fixture=selected, accepted_only=request.accepted_only and context_match
    )
    lineage = build_reference_annotation_lineage(evaluation, fixture=selected)
    reconciliation = reconcile_reference_annotation_views(
        evaluation, bundle, lineage, fixture=selected
    )
    receipts.append(
        _stage(
            ReferenceAnnotationRuntimeStage.RECONCILIATION,
            reconciliation.accepted and context_match,
            f"{len(reconciliation.checks)} cross-view checks evaluated",
        )
    )
    quality = evaluate_reference_annotation_quality_gate(selected)
    receipts.append(
        _stage(
            ReferenceAnnotationRuntimeStage.QUALITY_GATE,
            quality.accepted and context_match,
            f"{len(quality.checks)} integrated checks evaluated",
        )
    )
    bundle_failures = builder.verify(bundle)
    receipts.append(
        _stage(
            ReferenceAnnotationRuntimeStage.BUNDLE,
            not bundle_failures and bundle.published and context_match,
            f"{len(bundle.entries)} entries projected",
        )
    )
    published = bool(
        context_match
        and evaluation.accepted
        and replay.accepted
        and scenarios.accepted
        and reconciliation.accepted
        and quality.accepted
        and not bundle_failures
        and bundle.published
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "published": published,
        "stage_receipts": receipts,
        "bundle": bundle.to_dict(),
    }
    return ReferenceAnnotationRuntimeReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        published,
        tuple(receipts),
        bundle.to_dict(),
        _address(body),
    )


def run_reference_annotation_pipeline_file(
    path: str | Path,
    *,
    context_key: str | None = None,
    accepted_only: bool = True,
    output_format: ReferenceAnnotationBundleFormat | str = ReferenceAnnotationBundleFormat.JSON,
) -> ReferenceAnnotationRuntimeReport:
    """Run a JSON request document or a fixture path directly."""

    request_path = Path(path)
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    if "fixture_path" in payload:
        request = ReferenceAnnotationRuntimeRequest(
            fixture_path=str(payload["fixture_path"]),
            context_key=payload.get("context_key", context_key),
            accepted_only=bool(payload.get("accepted_only", accepted_only)),
            output_format=ReferenceAnnotationBundleFormat(
                payload.get("output_format", output_format)
            ),
        )
    else:
        request = ReferenceAnnotationRuntimeRequest(
            fixture_path=str(request_path),
            context_key=context_key,
            accepted_only=accepted_only,
            output_format=ReferenceAnnotationBundleFormat(output_format),
        )
    return run_reference_annotation_pipeline(request)


__all__ = [
    "ReferenceAnnotationRuntimeReport",
    "ReferenceAnnotationRuntimeRequest",
    "ReferenceAnnotationRuntimeStage",
    "ReferenceAnnotationStageReceipt",
    "run_reference_annotation_pipeline",
    "run_reference_annotation_pipeline_file",
]
