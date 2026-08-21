"""Four-stage runtime composition for the C13-C16 specimen release plane."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_preanalytic_fixture_eval import evaluate_specimen_preanalytic_fixture
from .specimen_preanalytic_lineage import build_specimen_preanalytic_lineage
from .specimen_preanalytic_public_data import (
    SpecimenPreanalyticFixtureCatalog,
    SpecimenPreanalyticOperation,
)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticPipelineRequest:
    request_id: str
    fixture_path: str
    context_key: str
    publish_mode: str

    def __post_init__(self) -> None:
        for field in ("request_id", "fixture_path", "context_key", "publish_mode"):
            require_non_empty(str(getattr(self, field)), f"pipeline {field}")
        if self.publish_mode not in {"accepted_only", "allow_review"}:
            raise ValueError("publish_mode must be accepted_only or allow_review")

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> SpecimenPreanalyticPipelineRequest:
        return cls(
            request_id=require_non_empty(str(raw.get("request_id", "")), "request_id"),
            fixture_path=require_non_empty(str(raw.get("fixture_path", "")), "fixture_path"),
            context_key=require_non_empty(str(raw.get("context_key", "")), "context_key"),
            publish_mode=str(raw.get("publish_mode", "accepted_only")),
        )

    @classmethod
    def from_file(
        cls, path: str | Path
    ) -> tuple[SpecimenPreanalyticPipelineRequest, SpecimenPreanalyticFixtureCatalog]:
        source = Path(path)
        raw = json.loads(source.read_text(encoding="utf-8"))
        request = cls.from_mapping(raw)
        fixture_path = Path(request.fixture_path)
        if not fixture_path.is_absolute():
            fixture_path = source.parent / fixture_path
        return request, SpecimenPreanalyticFixtureCatalog.from_file(fixture_path)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticStageReceipt:
    stage_id: str
    operation: str
    input_count: int
    output_count: int
    state: str
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticPipelineReport:
    request_id: str
    fixture_id: str
    context_key: str
    state: str
    published: bool
    stage_receipts: tuple[SpecimenPreanalyticStageReceipt, ...]
    evaluation_address: str
    lineage_address: str
    manifest_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "stage_count": len(self.stage_receipts),
            "published": self.published,
        }


def run_specimen_preanalytic_pipeline(
    request: SpecimenPreanalyticPipelineRequest,
    catalog: SpecimenPreanalyticFixtureCatalog,
) -> SpecimenPreanalyticPipelineReport:
    """Execute quality, lineage, identity, and publication stages."""

    if request.context_key != catalog.context_key:
        raise ValueError("pipeline context does not match fixture context")
    evaluation = evaluate_specimen_preanalytic_fixture(catalog)
    lineage = build_specimen_preanalytic_lineage(catalog)
    stages: list[SpecimenPreanalyticStageReceipt] = []
    for operation in SpecimenPreanalyticOperation:
        receipts = tuple(
            receipt for receipt in evaluation.receipts if receipt.operation == operation.value
        )
        issues = tuple(sorted({issue for receipt in receipts for issue in receipt.issue_codes}))
        stage_state = (
            "accepted" if receipts and all(receipt.passed for receipt in receipts) else "review"
        )
        body = {
            "stage_id": f"stage:{operation.value}",
            "operation": operation.value,
            "input_count": len(receipts),
            "output_count": len(receipts),
            "state": stage_state,
            "issue_codes": issues,
        }
        stages.append(
            SpecimenPreanalyticStageReceipt(
                body["stage_id"],
                operation.value,
                len(receipts),
                len(receipts),
                stage_state,
                issues,
                content_hash(body),
            )
        )
    published = (
        evaluation.passed
        and all(stage.state == "accepted" for stage in stages)
        and request.publish_mode in {"accepted_only", "allow_review"}
    )
    state = "published" if published else "review"
    manifest = {
        "request_id": request.request_id,
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "published": published,
        "stage_receipts": stages,
        "evaluation_address": evaluation.content_address,
        "lineage_address": lineage.content_address,
    }
    manifest_address = content_hash(manifest)
    report_body = manifest | {"manifest_address": manifest_address}
    return SpecimenPreanalyticPipelineReport(
        request.request_id,
        catalog.fixture_id,
        catalog.context_key,
        state,
        published,
        tuple(stages),
        evaluation.content_address,
        lineage.content_address,
        manifest_address,
        content_hash(report_body),
    )


__all__ = [
    "SpecimenPreanalyticPipelineReport",
    "SpecimenPreanalyticPipelineRequest",
    "SpecimenPreanalyticStageReceipt",
    "run_specimen_preanalytic_pipeline",
]
