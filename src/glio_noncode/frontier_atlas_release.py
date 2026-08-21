"""Release manifest for Domain 05 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontier_atlas_quality_gate import FrontierAtlasQualityReport
from .frontier_atlas_runtime import FrontierAtlasRuntimeResult
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class FrontierAtlasReleaseManifest:
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


def build_frontier_atlas_release(
    quality: FrontierAtlasQualityReport, runtime: FrontierAtlasRuntimeResult
) -> FrontierAtlasReleaseManifest:
    bundle = quality.bundle
    body = {
        "release_id": "frontier-atlas-release",
        "release_version": "2026.08.d05-c13-c16.v1",
        "fixture_id": bundle.fixture.fixture_id,
        "context_key": bundle.fixture.context_key,
        "operation_ids": tuple(
            dict.fromkeys(item.operation.value for item in bundle.evaluation.receipts)
        ),
        "source_ids": tuple(source.source_id for source in bundle.fixture.sources),
        "bundle_address": bundle.content_address,
        "quality_address": quality.content_address,
        "runtime_address": runtime.content_address,
        "status": runtime.status if quality.accepted else "rejected",
        "acceptance_statement": "C13-C16 frontier atlas outputs are released only with source closure, visible controls, deterministic replay, context gates, and descriptive non-clinical interpretation.",
    }
    return FrontierAtlasReleaseManifest(**body, content_address=content_hash(body))


def write_frontier_atlas_release(manifest: FrontierAtlasReleaseManifest, path: str) -> None:
    from pathlib import Path

    Path(path).write_text(
        __import__("json").dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "FrontierAtlasReleaseManifest",
    "build_frontier_atlas_release",
    "write_frontier_atlas_release",
]
