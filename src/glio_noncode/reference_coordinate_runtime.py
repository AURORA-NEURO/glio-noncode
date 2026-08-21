"""Deterministic runtime pipeline for Domain 04 reference-coordinate evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .reference_coordinate_bundle import (
    ReferenceCoordinateBundleBuilder,
    ReferenceCoordinateBundleFormat,
)
from .reference_coordinate_fixture_eval import evaluate_reference_coordinate_fixture
from .reference_coordinate_public_data import (
    ReferenceCoordinateFixtureCatalog,
    audit_reference_coordinate_data,
)
from .reference_coordinate_reconciliation import reconcile_reference_coordinate_views
from .reference_coordinate_replay import replay_reference_coordinate_fixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceCoordinatePipelineRequest:
    fixture_path: str
    context_key: str
    accepted_only: bool = True
    allow_review: bool = False
    output_format: ReferenceCoordinateBundleFormat = ReferenceCoordinateBundleFormat.JSON

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_path, "fixture path")
        require_non_empty(self.context_key, "pipeline context")

    @classmethod
    def from_mapping(
        cls, raw: dict[str, Any], *, base_path: Path | None = None
    ) -> ReferenceCoordinatePipelineRequest:
        fixture_path = str(raw.get("fixture_path", raw.get("input", ""))).strip()
        if base_path is not None and fixture_path and not Path(fixture_path).is_absolute():
            fixture_path = str((base_path / fixture_path).resolve())
        output_format = ReferenceCoordinateBundleFormat(str(raw.get("output_format", "json")))
        accepted_only = raw.get("accepted_only", True)
        allow_review = raw.get("allow_review", False)
        if not isinstance(accepted_only, bool) or not isinstance(allow_review, bool):
            raise ValidationError("pipeline flags must be boolean")
        return cls(
            fixture_path=fixture_path,
            context_key=str(raw.get("context_key", "")).strip(),
            accepted_only=accepted_only,
            allow_review=allow_review,
            output_format=output_format,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> ReferenceCoordinatePipelineRequest:
        request_path = Path(path)
        raw = json.loads(request_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValidationError("pipeline request must be an object")
        return cls.from_mapping(raw, base_path=request_path.parent)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateStageReceipt:
    stage_id: str
    state: str
    input_count: int
    output_count: int
    component_address: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.stage_id, "stage ID")
        if self.input_count < 0 or self.output_count < 0:
            raise ValidationError("stage counts must not be negative")
        if not self.component_address.startswith("sha256:"):
            raise ValidationError("stage component address is required")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("stage receipt must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinatePipelineReport:
    fixture_id: str
    context_key: str
    state: str
    published: bool
    stages: tuple[ReferenceCoordinateStageReceipt, ...]
    output_summary: dict[str, Any]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "published" and self.published

    @property
    def failed_stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.stage_id for stage in self.stages if stage.state != "accepted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "stage_count": len(self.stages),
            "failed_stage_ids": self.failed_stage_ids,
        }


class ReferenceCoordinateRuntime:
    """Run the release stages with count and context conservation."""

    def run(self, request: ReferenceCoordinatePipelineRequest) -> ReferenceCoordinatePipelineReport:
        catalog = ReferenceCoordinateFixtureCatalog.from_file(request.fixture_path)
        data_audit = audit_reference_coordinate_data(catalog)
        evaluation = evaluate_reference_coordinate_fixture(catalog)
        replay = replay_reference_coordinate_fixture(catalog)
        bundle = ReferenceCoordinateBundleBuilder().build(
            catalog,
            output_format=request.output_format,
            accepted_only=request.accepted_only,
            allow_review=request.allow_review,
        )
        reconciliation = reconcile_reference_coordinate_views(
            catalog,
            evaluation=evaluation,
            bundle=ReferenceCoordinateBundleBuilder().build(catalog),
        )

        stages = (
            self._stage(
                "public_data",
                data_audit.state,
                len(catalog.records),
                len(catalog.records),
                data_audit.content_address,
            ),
            self._stage(
                "fixture_evaluation",
                evaluation.state,
                len(catalog.records),
                len(evaluation.receipts),
                evaluation.content_address,
            ),
            self._stage(
                "replay",
                replay.state,
                len(catalog.records),
                len(evaluation.receipts),
                replay.content_address,
            ),
            self._stage(
                "reconciliation",
                reconciliation.state,
                len(evaluation.receipts),
                len(evaluation.receipts),
                reconciliation.content_address,
            ),
            self._stage(
                "bundle",
                bundle.state,
                len(evaluation.receipts),
                len(bundle.entries),
                bundle.content_address,
            ),
        )
        context_ok = request.context_key == catalog.context_key
        all_components = (
            data_audit.passed
            and evaluation.passed
            and replay.passed
            and reconciliation.passed
            and bundle.state == "accepted"
            and context_ok
        )
        published = bool(all_components and bundle.published)
        state = "published" if published else "review"
        output_summary = {
            "fixture_version": catalog.fixture_version,
            "request_context_matches": context_ok,
            "accepted_only": request.accepted_only,
            "bundle_format": request.output_format.value,
            "record_count": len(catalog.records),
            "receipt_count": len(evaluation.receipts),
            "bundle_entry_count": len(bundle.entries),
            "bundle_published": bundle.published,
            "data_audit_state": data_audit.state,
            "evaluation_state": evaluation.state,
            "replay_state": replay.state,
            "reconciliation_state": reconciliation.state,
            "component_addresses": {
                "data_audit": data_audit.content_address,
                "evaluation": evaluation.content_address,
                "replay": replay.content_address,
                "reconciliation": reconciliation.content_address,
                "bundle": bundle.content_address,
            },
        }
        body = {
            "fixture_id": catalog.fixture_id,
            "context_key": catalog.context_key,
            "state": state,
            "published": published,
            "stages": stages,
            "output_summary": output_summary,
        }
        return ReferenceCoordinatePipelineReport(
            fixture_id=catalog.fixture_id,
            context_key=catalog.context_key,
            state=state,
            published=published,
            stages=stages,
            output_summary=output_summary,
            content_address=content_hash(body),
        )

    @staticmethod
    def _stage(
        stage_id: str,
        state: str,
        input_count: int,
        output_count: int,
        component_address: str,
    ) -> ReferenceCoordinateStageReceipt:
        body = {
            "stage_id": stage_id,
            "state": state,
            "input_count": input_count,
            "output_count": output_count,
            "component_address": component_address,
        }
        return ReferenceCoordinateStageReceipt(
            stage_id=stage_id,
            state=state,
            input_count=input_count,
            output_count=output_count,
            component_address=component_address,
            content_address=content_hash(body),
        )


def run_reference_coordinate_pipeline(
    request: ReferenceCoordinatePipelineRequest,
) -> ReferenceCoordinatePipelineReport:
    return ReferenceCoordinateRuntime().run(request)


__all__ = [
    "ReferenceCoordinatePipelineReport",
    "ReferenceCoordinatePipelineRequest",
    "ReferenceCoordinateRuntime",
    "ReferenceCoordinateStageReceipt",
    "run_reference_coordinate_pipeline",
]
