"""Release manifest for the C09-C12 evidence tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_bundle import AtlasAlphaEvidenceBundle
from .atlas_alpha_evidence_quality_gate import AtlasAlphaEvidenceQualityReport
from .atlas_alpha_evidence_runtime import AtlasAlphaEvidenceRuntimeResult
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceReleaseManifest:
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


def build_atlas_alpha_evidence_release(
    quality: AtlasAlphaEvidenceQualityReport, runtime: AtlasAlphaEvidenceRuntimeResult
) -> AtlasAlphaEvidenceReleaseManifest:
    """Build an explicit release receipt from a completed quality gate."""

    bundle: AtlasAlphaEvidenceBundle = quality.bundle
    body = {
        "release_id": "atlas-alpha-evidence-release",
        "release_version": "2026.08.d05-c09-c12.v1",
        "fixture_id": bundle.fixture.fixture_id,
        "context_key": bundle.fixture.context_key,
        "operation_ids": tuple(item.operation.value for item in bundle.evaluation.receipts),
        "source_ids": tuple(bundle.data_audit.to_dict().get("source_ids", ())),
        "bundle_address": bundle.content_address,
        "quality_address": quality.content_address,
        "runtime_address": runtime.content_address,
        "status": runtime.status if quality.accepted else "rejected",
        "acceptance_statement": "Public aggregate evidence adapters are released only with visible controls, replay floors, source closure, and non-causal interpretation boundaries.",
    }
    operation_ids = tuple(
        dict.fromkeys(item.operation.value for item in bundle.evaluation.receipts)
    )
    source_ids = tuple(source.source_id for source in bundle.fixture.sources)
    body["operation_ids"] = operation_ids
    body["source_ids"] = source_ids
    return AtlasAlphaEvidenceReleaseManifest(**body, content_address=content_hash(body))


def write_atlas_alpha_evidence_release(
    manifest: AtlasAlphaEvidenceReleaseManifest, path: str
) -> None:
    """Write the release manifest as stable JSON."""

    from pathlib import Path

    Path(path).write_text(
        __import__("json").dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "AtlasAlphaEvidenceReleaseManifest",
    "build_atlas_alpha_evidence_release",
    "write_atlas_alpha_evidence_release",
]
