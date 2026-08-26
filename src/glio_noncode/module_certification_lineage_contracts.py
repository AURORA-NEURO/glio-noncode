"""Typed public contracts for certification evidence lineage.

The lineage layer explains where each static certification observation came
from.  It intentionally stores relative repository paths, digests, counts,
and relationships instead of source payloads or machine-specific locations.
That makes a lineage graph safe to publish, compare, cache, and replay in CI.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_CERTIFICATION_LINEAGE_VERSION = "module-certification-lineage-v1"
MODULE_CERTIFICATION_LINEAGE_BOUNDARY = "public_aggregate_module_certification_lineage"
MODULE_CERTIFICATION_LINEAGE_MAX_EVIDENCE = 200_000
MODULE_CERTIFICATION_LINEAGE_MAX_EDGES = 500_000
MODULE_CERTIFICATION_LINEAGE_MAX_LIMIT = 512
MODULE_CERTIFICATION_LINEAGE_DEFAULT_LIMIT = 50


class CertificationEvidenceKind(StrEnum):
    """Static resource class that can support a module contract."""

    SOURCE = "source"
    TEST = "test"
    DOCUMENTATION = "documentation"
    EXPORT = "export"


class CertificationLineageRelation(StrEnum):
    """Relationship vocabulary for module-to-evidence and module edges."""

    SUPPORTS = "supports"
    EXPORTS = "exports"
    DEPENDS_ON = "depends_on"


class CertificationLineageTargetKind(StrEnum):
    """Node class addressed by a lineage edge."""

    EVIDENCE = "evidence"
    MODULE = "module"


def _text(value: Any, field: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _non_negative(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    return value


def _safe_relative(value: str, field: str) -> None:
    _text(value, field)
    if value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} must use a relative forward-slash path")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValidationError(f"{field} contains an unsafe path segment")


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(set(values))) != values:
        raise ValidationError(f"{field} must be sorted and unique")


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ModuleCertificationEvidence:
    """One digest-addressed static artifact supporting a module."""

    evidence_id: str
    module_id: str
    kind: CertificationEvidenceKind
    relative_path: str
    relation: CertificationLineageRelation
    detail: str
    source_digest: str
    line_count: int
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "evidence_id",
            "module_id",
            "detail",
            "source_digest",
            "content_address",
        ):
            _text(getattr(self, field), field)
        _safe_relative(self.relative_path, "relative_path")
        _non_negative(self.line_count, "line_count")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationLineageEdge:
    """One resolved or unresolved relationship in the lineage graph."""

    source_module: str
    target_kind: CertificationLineageTargetKind
    target_id: str
    relation: CertificationLineageRelation
    resolved: bool
    evidence_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in ("source_module", "target_id", "content_address"):
            _text(getattr(self, field), field)
        if not isinstance(self.resolved, bool):
            raise ValidationError("lineage edge resolved must be boolean")
        _sorted_unique(self.evidence_ids, "evidence_ids")
        if self.target_kind is CertificationLineageTargetKind.EVIDENCE:
            if self.relation not in {
                CertificationLineageRelation.SUPPORTS,
                CertificationLineageRelation.EXPORTS,
            }:
                raise ValidationError("evidence edges require a support or export relation")
        elif self.relation is not CertificationLineageRelation.DEPENDS_ON:
            raise ValidationError("module edges require a dependency relation")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationLineage:
    """Complete bounded evidence graph for one certification matrix."""

    inventory_address: str
    matrix_address: str
    evidence: tuple[ModuleCertificationEvidence, ...]
    edges: tuple[ModuleCertificationLineageEdge, ...]
    module_count: int
    evidence_count: int
    edge_count: int
    covered_module_counts: Mapping[str, int]
    relation_counts: Mapping[str, int]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "inventory_address",
            "matrix_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        _non_negative(self.module_count, "module_count")
        if self.evidence_count != len(self.evidence) or self.edge_count != len(self.edges):
            raise ValidationError("lineage counts do not conserve records")
        if self.evidence_count > MODULE_CERTIFICATION_LINEAGE_MAX_EVIDENCE:
            raise ValidationError("lineage evidence limit exceeded")
        if self.edge_count > MODULE_CERTIFICATION_LINEAGE_MAX_EDGES:
            raise ValidationError("lineage edge limit exceeded")
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        if evidence_ids != tuple(sorted(evidence_ids)) or len(set(evidence_ids)) != len(
            evidence_ids
        ):
            raise ValidationError("lineage evidence must be sorted and unique")
        edge_keys = tuple(
            (item.source_module, item.target_kind.value, item.target_id, item.relation.value)
            for item in self.edges
        )
        if edge_keys != tuple(sorted(edge_keys)):
            raise ValidationError("lineage edges must be sorted")
        for mapping_name, mapping in (
            ("covered_module_counts", self.covered_module_counts),
            ("relation_counts", self.relation_counts),
        ):
            if any(not isinstance(key, str) or not key.strip() for key in mapping):
                raise ValidationError(f"{mapping_name} keys are required")
            if any(
                _non_negative(value, f"{mapping_name}.{key}") is None
                for key, value in mapping.items()
            ):
                raise AssertionError("unreachable")

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_CERTIFICATION_LINEAGE_VERSION,
            "boundary": MODULE_CERTIFICATION_LINEAGE_BOUNDARY,
            "inventory_address": self.inventory_address,
            "matrix_address": self.matrix_address,
            "module_count": self.module_count,
            "evidence_count": self.evidence_count,
            "edge_count": self.edge_count,
            "covered_module_counts": dict(sorted(self.covered_module_counts.items())),
            "relation_counts": dict(sorted(self.relation_counts.items())),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result["evidence"] = [item.to_dict() for item in self.evidence]
            result["edges"] = [item.to_dict() for item in self.edges]
        return result

    @property
    def source_count(self) -> int:
        return self.covered_module_counts.get(CertificationEvidenceKind.SOURCE.value, 0)

    @property
    def test_count(self) -> int:
        return self.covered_module_counts.get(CertificationEvidenceKind.TEST.value, 0)

    @property
    def documentation_count(self) -> int:
        return self.covered_module_counts.get(CertificationEvidenceKind.DOCUMENTATION.value, 0)

    @property
    def export_count(self) -> int:
        return self.covered_module_counts.get(CertificationEvidenceKind.EXPORT.value, 0)


def address_module_certification_evidence(value: ModuleCertificationEvidence) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return _address(body, "module-certification-evidence")


def address_module_certification_lineage_edge(value: ModuleCertificationLineageEdge) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return _address(body, "module-certification-lineage-edge")


__all__ = [
    "CertificationEvidenceKind",
    "CertificationLineageRelation",
    "CertificationLineageTargetKind",
    "MODULE_CERTIFICATION_LINEAGE_BOUNDARY",
    "MODULE_CERTIFICATION_LINEAGE_DEFAULT_LIMIT",
    "MODULE_CERTIFICATION_LINEAGE_MAX_EDGES",
    "MODULE_CERTIFICATION_LINEAGE_MAX_EVIDENCE",
    "MODULE_CERTIFICATION_LINEAGE_MAX_LIMIT",
    "MODULE_CERTIFICATION_LINEAGE_VERSION",
    "ModuleCertificationEvidence",
    "ModuleCertificationLineage",
    "ModuleCertificationLineageEdge",
    "address_module_certification_evidence",
    "address_module_certification_lineage_edge",
]
