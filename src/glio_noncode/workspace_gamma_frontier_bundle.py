"""Research-use evidence bundle for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_public_data import GammaFrontierFixture
from .workspace_gamma_frontier_release import GammaFrontierReleaseManifest
from .workspace_gamma_frontier_runtime import GammaFrontierRuntimeReport


@dataclass(frozen=True, slots=True)
class GammaFrontierBundleEntry:
    """One named artifact address in the release bundle."""

    entry_id: str
    kind: str
    address: str
    required: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierEvidenceBundle:
    """Address-only bundle manifest with no embedded secrets."""

    bundle_id: str
    fixture_id: str
    entries: tuple[GammaFrontierBundleEntry, ...]
    release_state: str
    research_boundary: str
    accepted: bool
    content_address: str

    @property
    def required_entries(self) -> tuple[GammaFrontierBundleEntry, ...]:
        return tuple(item for item in self.entries if item.required)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "entry_count": len(self.entries),
            "required_entry_count": len(self.required_entries),
        }


def _entry(
    index: int, kind: str, address: str, required: bool, detail: str
) -> GammaFrontierBundleEntry:
    body = {
        "entry_id": f"gamma-bundle-entry-{index:03d}",
        "kind": kind,
        "address": address,
        "required": required,
        "detail": detail,
    }
    return GammaFrontierBundleEntry(
        **body, content_address=content_hash(body, prefix="bundle-entry")
    )


def assemble_gamma_frontier_bundle(
    fixture: GammaFrontierFixture,
    runtime: GammaFrontierRuntimeReport,
    release: GammaFrontierReleaseManifest | None = None,
    *,
    bundle_id: str = "workspace-gamma-frontier-c09-c12-bundle",
) -> GammaFrontierEvidenceBundle:
    """Assemble source, execution, policy, lineage, and release addresses."""

    entries = [
        _entry(1, "fixture", fixture.content_address, True, "public aggregate fixture"),
        _entry(2, "data-audit", runtime.data_audit.content_address, True, "source and count audit"),
        _entry(
            3,
            "evaluation",
            runtime.evaluation.content_address,
            True,
            "positive and control execution",
        ),
        _entry(4, "metrics", runtime.metrics.content_address, True, "transparent surface metrics"),
        _entry(5, "lineage", runtime.lineage.content_address, True, "source-to-output graph"),
        _entry(
            6,
            "reconciliation",
            runtime.reconciliation.content_address,
            True,
            "expected-versus-observed rows",
        ),
        _entry(
            7,
            "projection-audit",
            runtime.projection_audit.content_address,
            True,
            "serialized shape assertions",
        ),
        _entry(8, "quality-gate", runtime.quality.content_address, True, "quality gate"),
        _entry(9, "runtime", runtime.content_address, True, "runtime rehearsal"),
    ]
    if release is not None:
        entries.append(_entry(10, "release", release.content_address, True, "release decision"))
    boundary = fixture.evidence_boundary
    accepted = runtime.accepted and (release is None or release.state.value == "ready")
    body = {
        "bundle_id": bundle_id,
        "fixture_id": fixture.fixture_id,
        "entries": tuple(entries),
        "release_state": "unreleased" if release is None else release.state.value,
        "research_boundary": boundary,
        "accepted": accepted,
    }
    return GammaFrontierEvidenceBundle(**body, content_address=content_hash(body, prefix="bundle"))


__all__ = [
    "GammaFrontierBundleEntry",
    "GammaFrontierEvidenceBundle",
    "assemble_gamma_frontier_bundle",
]
