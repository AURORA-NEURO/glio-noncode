"""Release manifest for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_quality_gate import SequenceFrontierQualityReport
from .sequence_frontier_runtime import SequenceFrontierRuntimeResult
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class SequenceFrontierReleaseManifest:
    release_id: str
    release_version: str
    fixture_id: str
    context_key: str
    operation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    bundle_address: str
    quality_address: str
    runtime_address: str
    status: str
    acceptance_statement: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "release_id",
            "release_version",
            "fixture_id",
            "context_key",
            "bundle_address",
            "quality_address",
            "runtime_address",
            "status",
            "acceptance_statement",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_sequence_frontier_release(
    quality: SequenceFrontierQualityReport, runtime: SequenceFrontierRuntimeResult
) -> SequenceFrontierReleaseManifest:
    bundle = quality.bundle
    body = {
        "release_id": "sequence-frontier-release",
        "release_version": "2026.08.d06-c13-c16.v1",
        "fixture_id": bundle.fixture.fixture_id,
        "context_key": bundle.fixture.context_key,
        "operation_ids": tuple(
            dict.fromkeys(item.operation.value for item in bundle.evaluation.receipts)
        ),
        "source_ids": tuple(item.source_id for item in bundle.fixture.sources),
        "bundle_address": bundle.content_address,
        "quality_address": quality.content_address,
        "runtime_address": runtime.content_address,
        "status": runtime.status if quality.accepted else "rejected",
        "acceptance_statement": "C13-C16 sequence and model outputs are released only with exact context, visible controls, deterministic replay, bounded uncertainty, sanitized receipts, and descriptive non-clinical interpretation.",
    }
    return SequenceFrontierReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["SequenceFrontierReleaseManifest", "build_sequence_frontier_release"]
