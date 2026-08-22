"""Release manifest for Domain 08 cell-state frontier outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_state_frontier_quality_gate import CellStateFrontierQualityReport
from .cell_state_frontier_runtime import CellStateFrontierRuntimeResult
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CellStateFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    fixture_version: str
    run_id: str
    context_key: str
    evidence_boundary: str
    release_state: str
    quality_address: str
    bundle_address: str
    record_address: str
    source_ids: tuple[str, ...]
    operation_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("release_id", "fixture_id", "fixture_version", "run_id", "context_key", "evidence_boundary", "release_state", "quality_address", "bundle_address", "record_address", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.release_state not in {"ready", "blocked"}:
            raise ValueError("cell state release state must be ready or blocked")

    @property
    def accepted(self) -> bool:
        return self.release_state == "ready"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_cell_state_frontier_release(
    quality: CellStateFrontierQualityReport,
    runtime: CellStateFrontierRuntimeResult,
    *,
    run_id: str | None = None,
) -> CellStateFrontierReleaseManifest:
    bundle = quality.bundle
    selected_run_id = run_id or runtime.run_id
    state = "ready" if quality.accepted and runtime.accepted else "blocked"
    operation_ids = tuple(dict.fromkeys(item.operation.value for item in bundle.evaluation.receipts))
    body = {"fixture_id": bundle.fixture_id, "fixture_version": bundle.fixture_version, "run_id": selected_run_id, "context_key": bundle.context_key, "evidence_boundary": bundle.evidence_boundary, "release_state": state, "quality_address": quality.content_address, "bundle_address": bundle.bundle_address, "record_address": bundle.records_address, "source_ids": bundle.source_ids, "operation_ids": operation_ids}
    release_id = "cell-state-frontier-release:" + content_hash(body).split(":", 1)[1][:24]
    final_body = body | {"release_id": release_id}
    return CellStateFrontierReleaseManifest(release_id, bundle.fixture_id, bundle.fixture_version, selected_run_id, bundle.context_key, bundle.evidence_boundary, state, quality.content_address, bundle.bundle_address, bundle.records_address, bundle.source_ids, operation_ids, content_hash(final_body))


__all__ = ["CellStateFrontierReleaseManifest", "build_cell_state_frontier_release"]
