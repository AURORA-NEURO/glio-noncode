"""Context dimension matrix and mismatch diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PLANNING_FRONTIER_CONTEXT_KEY, PLANNING_FRONTIER_FOREIGN_CONTEXT
from .serialization import content_hash, jsonable


CONTEXT_DIMENSIONS = ("genome_build", "disease", "age_group", "cell_state", "territory", "treatment_phase")


@dataclass(frozen=True, slots=True)
class ContextMatrixRow:
    context_key: str
    dimensions: dict[str, str]
    exact_match: bool
    mismatch_dimensions: tuple[str, ...]
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextMatrix:
    required_context: str
    rows: tuple[ContextMatrixRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _parts(context_key: str) -> tuple[str, ...]:
    return tuple(str(context_key).split("|"))


def build_context_matrix(context_keys: tuple[str, ...] = (PLANNING_FRONTIER_CONTEXT_KEY, PLANNING_FRONTIER_FOREIGN_CONTEXT), *, required_context: str = PLANNING_FRONTIER_CONTEXT_KEY) -> ContextMatrix:
    required = _parts(required_context)
    rows = []
    for context_key in context_keys:
        parts = _parts(context_key)
        mismatch = tuple(dimension for index, dimension in enumerate(CONTEXT_DIMENSIONS) if index >= len(parts) or index >= len(required) or parts[index] != required[index])
        dimensions = {dimension: parts[index] if index < len(parts) else "" for index, dimension in enumerate(CONTEXT_DIMENSIONS)}
        exact = not mismatch and len(parts) == len(required)
        body = {"context_key": context_key, "dimensions": dimensions, "exact_match": exact, "mismatch_dimensions": mismatch, "disposition": "accepted" if exact else "blocked"}
        rows.append(ContextMatrixRow(**body, content_address=content_hash(body, prefix="context-matrix-row")))
    accepted = bool(rows and any(row.exact_match for row in rows) and any(not row.exact_match for row in rows))
    body = {"required_context": required_context, "rows": tuple(rows), "accepted": accepted}
    return ContextMatrix(required_context, tuple(rows), accepted, content_hash(body, prefix="context-matrix"))


def context_dimension_index(matrix: ContextMatrix) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {dimension: [] for dimension in CONTEXT_DIMENSIONS}
    for row in matrix.rows:
        for dimension, value in row.dimensions.items():
            if value and value not in result[dimension]:
                result[dimension].append(value)
    return {dimension: tuple(values) for dimension, values in result.items()}


__all__ = ["CONTEXT_DIMENSIONS", "ContextMatrix", "ContextMatrixRow", "build_context_matrix", "context_dimension_index"]
