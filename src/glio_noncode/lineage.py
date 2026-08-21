"""Pseudonymous sample-lineage records and acyclic relationship checks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SampleLineageRecord:
    """One declared sample relationship using project-local identifiers."""

    sample_id: str
    parent_sample_ids: tuple[str, ...]
    relationship: str
    timepoint: str
    source_id: str
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("sample_id", "relationship", "timepoint", "source_id"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"lineage {name} is required")
        if self.sample_id in self.parent_sample_ids:
            raise ValidationError("a sample cannot be its own lineage parent")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LineageResult:
    """Validated lineage graph with cycle and missing-parent diagnostics."""

    records: tuple[SampleLineageRecord, ...]
    edges: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    content_address: str

    @property
    def supported(self) -> bool:
        return bool(self.records) and not self.errors

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LineageResolver:
    """Build a deterministic graph without inferring undisclosed relationships."""

    def resolve(self, records: Iterable[SampleLineageRecord]) -> LineageResult:
        values = tuple(records)
        ids = [record.sample_id for record in values]
        errors: list[str] = []
        warnings: list[str] = []
        if len(ids) != len(set(ids)):
            errors.append("sample IDs must be unique")
        known = set(ids)
        edges = tuple(
            (parent_id, record.sample_id)
            for record in values
            for parent_id in record.parent_sample_ids
        )
        missing = sorted({parent for parent, _ in edges if parent not in known})
        if missing:
            warnings.append(
                "Parent samples are referenced but not included in this snapshot: "
                + ", ".join(missing)
            )
        if self._has_cycle(values):
            errors.append("lineage relationships contain a cycle")
        relationships = {record.relationship for record in values}
        if "tumor" in relationships and "normal" not in relationships:
            warnings.append("No normal sample was declared for a tumor lineage record.")
        if not values:
            warnings.append("No lineage records were supplied; origin cannot be transported.")
        payload = {
            "records": values,
            "edges": edges,
            "warnings": tuple(warnings),
            "errors": tuple(errors),
        }
        return LineageResult(
            records=values,
            edges=edges,
            warnings=tuple(dict.fromkeys(warnings)),
            errors=tuple(dict.fromkeys(errors)),
            content_address=content_hash(payload),
        )

    @staticmethod
    def _has_cycle(records: tuple[SampleLineageRecord, ...]) -> bool:
        parents = {record.sample_id: set(record.parent_sample_ids) for record in records}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(sample_id: str) -> bool:
            if sample_id in visiting:
                return True
            if sample_id in visited:
                return False
            visiting.add(sample_id)
            if any(
                visit(parent_id) for parent_id in parents.get(sample_id, ()) if parent_id in parents
            ):
                return True
            visiting.remove(sample_id)
            visited.add(sample_id)
            return False

        return any(visit(sample_id) for sample_id in parents)
