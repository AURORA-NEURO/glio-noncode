"""Deterministic comparison of module certification matrices."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import ModuleCertificationMatrix
from .serialization import canonical_json, content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ModuleCertificationRowDiff:
    """Change record for one module certification row."""

    module_id: str
    change: str
    left_state: str | None
    right_state: str | None
    left_score: float | None
    right_score: float | None
    score_delta: float
    left_public_symbol_count: int
    right_public_symbol_count: int
    line_delta: int
    left_gap_count: int
    right_gap_count: int
    changed_check_kinds: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if (
            not self.module_id.strip()
            or not self.change.strip()
            or not self.content_address.strip()
        ):
            raise ValidationError("certification diff row identifiers are required")
        if self.change not in {"added", "removed", "changed", "unchanged"}:
            raise ValidationError("certification diff row change is unsupported")
        if self.left_gap_count < 0 or self.right_gap_count < 0:
            raise ValidationError("certification diff gap counts cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationDiff:
    """Full matrix comparison with conserved module and aggregate deltas."""

    left_matrix_address: str
    right_matrix_address: str
    rows: tuple[ModuleCertificationRowDiff, ...]
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    left_gap_count: int
    right_gap_count: int
    score_delta: float
    changed_check_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.left_matrix_address.strip() or not self.right_matrix_address.strip():
            raise ValidationError("certification diff requires matrix addresses")
        if tuple(item.module_id for item in self.rows) != tuple(
            sorted(item.module_id for item in self.rows)
        ):
            raise ValidationError("certification diff rows must be sorted")
        if sum(
            (self.added_count, self.removed_count, self.changed_count, self.unchanged_count)
        ) != len(self.rows):
            raise ValidationError("certification diff row counts do not conserve rows")

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result = {
            "version": "module-certification-diff-v1",
            "left_matrix_address": self.left_matrix_address,
            "right_matrix_address": self.right_matrix_address,
            "row_count": self.row_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "unchanged_count": self.unchanged_count,
            "left_gap_count": self.left_gap_count,
            "right_gap_count": self.right_gap_count,
            "score_delta": self.score_delta,
            "changed_check_count": self.changed_check_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result["rows"] = [item.to_dict() for item in self.rows]
        return result


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _check_map(row: Any) -> dict[str, str]:
    return {item.kind.value: item.state.value for item in row.checks}


def _row_diff(module_id: str, left: Any | None, right: Any | None) -> ModuleCertificationRowDiff:
    if left is None:
        change = "added"
    elif right is None:
        change = "removed"
    else:
        change = "unchanged"
        if (
            left.state != right.state
            or left.score != right.score
            or left.public_symbol_count != right.public_symbol_count
            or left.physical_lines != right.physical_lines
            or left.gap_count != right.gap_count
            or _check_map(left) != _check_map(right)
        ):
            change = "changed"
    left_checks = _check_map(left) if left is not None else {}
    right_checks = _check_map(right) if right is not None else {}
    changed_checks = tuple(
        sorted(
            kind
            for kind in set(left_checks) | set(right_checks)
            if left_checks.get(kind) != right_checks.get(kind)
        )
    )
    left_score = left.score if left is not None else None
    right_score = right.score if right is not None else None
    body = {
        "module_id": module_id,
        "change": change,
        "left_state": left.state.value if left is not None else None,
        "right_state": right.state.value if right is not None else None,
        "left_score": left_score,
        "right_score": right_score,
        "score_delta": round((right_score or 0.0) - (left_score or 0.0), 6),
        "left_public_symbol_count": left.public_symbol_count if left is not None else 0,
        "right_public_symbol_count": right.public_symbol_count if right is not None else 0,
        "line_delta": (right.physical_lines if right is not None else 0)
        - (left.physical_lines if left is not None else 0),
        "left_gap_count": left.gap_count if left is not None else 0,
        "right_gap_count": right.gap_count if right is not None else 0,
        "changed_check_kinds": changed_checks,
    }
    return ModuleCertificationRowDiff(
        **body, content_address=_address(body, "module-certification-row-diff")
    )


def build_module_certification_diff(
    left: ModuleCertificationMatrix,
    right: ModuleCertificationMatrix,
) -> ModuleCertificationDiff:
    """Compare module state, scores, gaps, and check states."""

    if not isinstance(left, ModuleCertificationMatrix) or not isinstance(
        right, ModuleCertificationMatrix
    ):
        raise ValidationError("certification diff requires typed matrices")
    left_map = {item.module_id: item for item in left.rows}
    right_map = {item.module_id: item for item in right.rows}
    rows = tuple(
        _row_diff(module_id, left_map.get(module_id), right_map.get(module_id))
        for module_id in sorted(set(left_map) | set(right_map))
    )
    body = {
        "left_matrix_address": left.content_address,
        "right_matrix_address": right.content_address,
        "rows": rows,
        "added_count": sum(item.change == "added" for item in rows),
        "removed_count": sum(item.change == "removed" for item in rows),
        "changed_count": sum(item.change == "changed" for item in rows),
        "unchanged_count": sum(item.change == "unchanged" for item in rows),
        "left_gap_count": left.gap_count,
        "right_gap_count": right.gap_count,
        "score_delta": round(right.overall_score - left.overall_score, 6),
        "changed_check_count": sum(len(item.changed_check_kinds) for item in rows),
        "accepted": left.accepted and right.accepted,
    }
    return ModuleCertificationDiff(
        **body, content_address=_address(body, "module-certification-diff")
    )


def query_module_certification_diff(
    value: ModuleCertificationDiff,
    *,
    change: str | None = None,
    module_id: str | None = None,
    check_kind: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded page over matrix changes."""

    if not isinstance(value, ModuleCertificationDiff):
        raise ValidationError("certification diff query requires a typed diff")
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("certification diff pagination is invalid")
    rows = list(value.rows)
    if change is not None:
        rows = [item for item in rows if item.change == change]
    if module_id is not None:
        rows = [item for item in rows if item.module_id == module_id]
    if check_kind is not None:
        rows = [item for item in rows if check_kind in item.changed_check_kinds]
    body = {
        "resource": "rows",
        "query": {
            "change": change,
            "module_id": module_id,
            "check_kind": check_kind,
            "offset": offset,
            "limit": limit,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": tuple(rows[offset : offset + limit]),
        "diff_address": value.content_address,
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-certification-diff-query")}


def module_certification_diff_json(value: ModuleCertificationDiff) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_certification_diff_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-diff-v1",
        "boundary": "public_aggregate_module_certification_diff",
        "row_fields": [
            "module_id",
            "change",
            "left_state",
            "right_state",
            "left_score",
            "right_score",
            "score_delta",
            "left_public_symbol_count",
            "right_public_symbol_count",
            "line_delta",
            "left_gap_count",
            "right_gap_count",
            "changed_check_kinds",
            "content_address",
        ],
        "changes": ["added", "removed", "changed", "unchanged"],
        "filters": ["change", "module_id", "check_kind"],
        "ordering": "module_id",
    }


def module_certification_diff_capabilities() -> dict[str, Any]:
    operations = (
        "compare_module_sets",
        "compare_module_states",
        "compare_module_scores",
        "compare_gap_counts",
        "compare_check_states",
        "compute_score_delta",
        "compute_changed_check_count",
        "query_rows",
        "render_json",
    )
    return {
        "version": "module-certification-diff-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
    }


__all__ = [
    "ModuleCertificationDiff",
    "ModuleCertificationRowDiff",
    "build_module_certification_diff",
    "module_certification_diff_capabilities",
    "module_certification_diff_json",
    "module_certification_diff_schema",
    "query_module_certification_diff",
]
