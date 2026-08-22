"""Cross-operation matrix for the Domain 10 C05-C08 beta release plane.

The matrix is a compact, deterministic view over the same fixture and replay
objects used by the pipeline. It makes six dimensions queryable for every
record: role, context, state, issue, receipt, and measurement availability.
Each cell carries the declared value, the replay value, a pass bit, and the
addresses needed to trace it back to the source and adapter result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .link_graph_beta_frontier_fixture_eval import (
    LinkGraphBetaFrontierEvaluation,
    LinkGraphBetaFrontierEvaluationRow,
    evaluate_link_graph_beta_frontier_fixture,
)
from .link_graph_beta_frontier_public_data import (
    LinkGraphBetaFrontierFixture,
    LinkGraphBetaFrontierOperation,
    LinkGraphBetaFrontierRecord,
    default_link_graph_beta_frontier_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


OPERATIONAL_MATRIX_VERSION = "2026.08.d10-c05-c08.matrix.v1"


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierMatrixDimension:
    name: str
    description: str
    comparison: str
    required: bool = True

    def __post_init__(self) -> None:
        require_non_empty(self.name, "dimension name")
        require_non_empty(self.description, "dimension description")
        require_non_empty(self.comparison, "dimension comparison")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierMatrixCell:
    cell_id: str
    record_id: str
    operation: str
    dimension: str
    expected: str
    observed: str
    passed: bool
    source_addresses: tuple[str, ...]
    result_address: str
    detail: str

    def __post_init__(self) -> None:
        for name in (
            "cell_id",
            "record_id",
            "operation",
            "dimension",
            "expected",
            "observed",
            "detail",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.result_address.startswith("sha256:"):
            raise ValueError("matrix result addresses must be content hashes")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierMatrixSlice:
    selector: str
    cells: tuple[LinkGraphBetaFrontierMatrixCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.selector, "matrix selector")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_cells(self) -> tuple[str, ...]:
        return tuple(item.cell_id for item in self.cells if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "selector": self.selector,
            "cells": [item.to_dict() for item in self.cells],
            "failed_cells": self.failed_cells,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierOperationalMatrix:
    fixture_id: str
    version: str
    dimensions: tuple[LinkGraphBetaFrontierMatrixDimension, ...]
    cells: tuple[LinkGraphBetaFrontierMatrixCell, ...]
    record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")
        require_non_empty(self.version, "matrix version")
        if self.record_count < 0:
            raise ValueError("record_count cannot be negative")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def dimension_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.dimensions)

    @property
    def operation_names(self) -> tuple[str, ...]:
        return tuple(item.value for item in LinkGraphBetaFrontierOperation)

    @property
    def expected_cell_count(self) -> int:
        return self.record_count * len(self.dimensions)

    @property
    def failed_cells(self) -> tuple[str, ...]:
        return tuple(item.cell_id for item in self.cells if not item.passed)

    @property
    def passed_cell_count(self) -> int:
        return sum(item.passed for item in self.cells)

    def for_operation(self, operation: str) -> tuple[LinkGraphBetaFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def for_dimension(self, dimension: str) -> tuple[LinkGraphBetaFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if item.dimension == dimension)

    def for_record(self, record_id: str) -> tuple[LinkGraphBetaFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if item.record_id == record_id)

    def cell(self, cell_id: str) -> LinkGraphBetaFrontierMatrixCell:
        return next(item for item in self.cells if item.cell_id == cell_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "version": self.version,
            "dimensions": [item.to_dict() for item in self.dimensions],
            "cells": [item.to_dict() for item in self.cells],
            "record_count": self.record_count,
            "expected_cell_count": self.expected_cell_count,
            "passed_cell_count": self.passed_cell_count,
            "failed_cells": self.failed_cells,
            "operation_names": self.operation_names,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_beta_frontier_matrix_dimensions() -> tuple[LinkGraphBetaFrontierMatrixDimension, ...]:
    """Return the stable dimensions used by the beta review matrix."""

    return (
        LinkGraphBetaFrontierMatrixDimension(
            "role",
            "positive or control role declared by the fixture",
            "exact",
        ),
        LinkGraphBetaFrontierMatrixDimension(
            "context",
            "reference context carried by the record",
            "exact",
        ),
        LinkGraphBetaFrontierMatrixDimension(
            "state",
            "expected state compared with typed replay state",
            "exact",
        ),
        LinkGraphBetaFrontierMatrixDimension(
            "issue",
            "expected issue floor compared with typed replay issues",
            "set_contains",
        ),
        LinkGraphBetaFrontierMatrixDimension(
            "receipt",
            "source receipt count compared with emitted sources",
            "exact",
        ),
        LinkGraphBetaFrontierMatrixDimension(
            "measurement",
            "declared measurement availability compared with adapter output",
            "exact",
        ),
    )


def _row_index(evaluation: LinkGraphBetaFrontierEvaluation) -> dict[str, LinkGraphBetaFrontierEvaluationRow]:
    return {item.record_id: item for item in evaluation.rows}


def _issue_value(values: Iterable[str]) -> str:
    return ",".join(sorted(set(values))) or "none"


def _measurement_presence(values: Mapping[str, Any]) -> str:
    if not values:
        return "absent"
    if values.get("observation_count") == 0:
        return "absent"
    return "present"


def _dimension_values(
    record: LinkGraphBetaFrontierRecord,
    row: LinkGraphBetaFrontierEvaluationRow,
    dimension: str,
) -> tuple[str, str, str]:
    """Return declared value, replay value, and a human-readable cell detail."""

    if dimension == "role":
        expected = record.role.value
        observed = row.role
        return expected, observed, "fixture role is preserved by replay"
    if dimension == "context":
        expected = record.context_key
        observed = record.context_key
        return expected, observed, "context is carried into adapter routing"
    if dimension == "state":
        expected = record.expected_state
        observed = row.observed_state
        return expected, observed, "expected state equals typed adapter state"
    if dimension == "issue":
        expected = _issue_value(record.expected_issue_codes)
        observed = _issue_value(row.observed_issue_codes)
        return expected, observed, "expected issue floor is contained in replay issues"
    if dimension == "receipt":
        expected = str(len(record.source_ids))
        observed = str(len(row.adapter.source_ids))
        return expected, observed, "source receipt cardinality is preserved"
    if dimension == "measurement":
        expected = _measurement_presence(record.expected_measurements)
        observed = "absent" if row.observed_state == "out_of_domain" else _measurement_presence(row.adapter.measurements)
        return expected, observed, "measurement availability remains explicit"
    raise KeyError(dimension)


def _cell_passed(dimension: str, expected: str, observed: str) -> bool:
    if dimension == "issue":
        expected_values = set(expected.split(",")) - {"none"}
        observed_values = set(observed.split(",")) - {"none"}
        return expected_values <= observed_values
    return expected == observed


def _build_cells(
    fixture: LinkGraphBetaFrontierFixture,
    evaluation: LinkGraphBetaFrontierEvaluation,
    dimensions: tuple[LinkGraphBetaFrontierMatrixDimension, ...],
) -> tuple[LinkGraphBetaFrontierMatrixCell, ...]:
    rows = _row_index(evaluation)
    cells: list[LinkGraphBetaFrontierMatrixCell] = []
    for record in fixture.records:
        row = rows[record.record_id]
        for dimension in dimensions:
            expected, observed, detail = _dimension_values(record, row, dimension.name)
            cell_id = f"{record.record_id}:{dimension.name}"
            address = content_hash(
                {
                    "cell_id": cell_id,
                    "expected": expected,
                    "observed": observed,
                    "result_address": row.adapter.content_address,
                }
            )
            cells.append(
                LinkGraphBetaFrontierMatrixCell(
                    cell_id,
                    record.record_id,
                    record.operation.value,
                    dimension.name,
                    expected,
                    observed,
                    _cell_passed(dimension.name, expected, observed),
                    tuple(record.content_address for _ in record.source_ids),
                    row.adapter.content_address,
                    detail,
                )
            )
    return tuple(cells)


def build_link_graph_beta_frontier_operational_matrix(
    fixture: LinkGraphBetaFrontierFixture | None = None,
    evaluation: LinkGraphBetaFrontierEvaluation | None = None,
) -> LinkGraphBetaFrontierOperationalMatrix:
    """Build the complete record-by-dimension matrix."""

    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or evaluate_link_graph_beta_frontier_fixture(value)
    dimensions = default_link_graph_beta_frontier_matrix_dimensions()
    cells = _build_cells(value, replay, dimensions)
    accepted = (
        replay.accepted
        and len(replay.rows) == len(value.records)
        and len(cells) == len(value.records) * len(dimensions)
        and all(item.passed for item in cells)
    )
    return LinkGraphBetaFrontierOperationalMatrix(
        value.fixture_id,
        OPERATIONAL_MATRIX_VERSION,
        dimensions,
        cells,
        len(value.records),
        accepted,
    )


def matrix_summary(matrix: LinkGraphBetaFrontierOperationalMatrix) -> dict[str, Any]:
    """Return stable counts for dashboards and release assertions."""

    return {
        "fixture_id": matrix.fixture_id,
        "version": matrix.version,
        "record_count": matrix.record_count,
        "dimension_count": len(matrix.dimensions),
        "cell_count": len(matrix.cells),
        "expected_cell_count": matrix.expected_cell_count,
        "passed_cell_count": matrix.passed_cell_count,
        "failed_cell_count": len(matrix.failed_cells),
        "operation_counts": {
            operation: len(matrix.for_operation(operation))
            for operation in matrix.operation_names
        },
        "dimension_counts": {
            dimension: len(matrix.for_dimension(dimension))
            for dimension in matrix.dimension_names
        },
        "accepted": matrix.accepted,
        "content_address": matrix.content_address,
    }


def select_link_graph_beta_frontier_matrix(
    matrix: LinkGraphBetaFrontierOperationalMatrix,
    *,
    operation: str | None = None,
    dimension: str | None = None,
    record_id: str | None = None,
) -> LinkGraphBetaFrontierMatrixSlice:
    """Select a deterministic matrix slice using optional exact filters."""

    selected = matrix.cells
    selector_parts: list[str] = []
    if operation is not None:
        if operation not in matrix.operation_names:
            raise ValueError(f"unknown beta operation: {operation}")
        selected = tuple(item for item in selected if item.operation == operation)
        selector_parts.append(f"operation={operation}")
    if dimension is not None:
        if dimension not in matrix.dimension_names:
            raise ValueError(f"unknown beta dimension: {dimension}")
        selected = tuple(item for item in selected if item.dimension == dimension)
        selector_parts.append(f"dimension={dimension}")
    if record_id is not None:
        selected = tuple(item for item in selected if item.record_id == record_id)
        selector_parts.append(f"record_id={record_id}")
    selector = "&".join(selector_parts) or "all"
    return LinkGraphBetaFrontierMatrixSlice(selector, selected, bool(selected) and all(item.passed for item in selected))


def matrix_cells_as_rows(
    matrix: LinkGraphBetaFrontierOperationalMatrix,
) -> tuple[dict[str, Any], ...]:
    """Project cells into stable row dictionaries for tabular exports."""

    return tuple(
        {
            "cell_id": item.cell_id,
            "record_id": item.record_id,
            "operation": item.operation,
            "dimension": item.dimension,
            "expected": item.expected,
            "observed": item.observed,
            "passed": item.passed,
            "source_addresses": item.source_addresses,
            "result_address": item.result_address,
            "detail": item.detail,
        }
        for item in matrix.cells
    )


def matrix_json(matrix: LinkGraphBetaFrontierOperationalMatrix) -> str:
    """Serialize the complete matrix with deterministic key ordering."""

    return json.dumps(matrix.to_dict(), sort_keys=True, separators=(",", ":"), default=str)


def render_matrix_markdown(matrix: LinkGraphBetaFrontierOperationalMatrix) -> str:
    """Render a compact review table without dropping evidence addresses."""

    def markdown_value(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    lines = [
        f"# {matrix.fixture_id} operational matrix",
        "",
        f"Version: `{matrix.version}`  ",
        f"Accepted: `{str(matrix.accepted).lower()}`  ",
        f"Cells: `{len(matrix.cells)}` / `{matrix.expected_cell_count}`",
        "",
        "| Record | Operation | Dimension | Expected | Observed | Pass |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {markdown_value(item.record_id)} | {markdown_value(item.operation)} | {markdown_value(item.dimension)} | {markdown_value(item.expected)} | {markdown_value(item.observed)} | {str(item.passed).lower()} |"
        for item in matrix.cells
    )
    return "\n".join(lines) + "\n"


def verify_link_graph_beta_frontier_matrix(matrix: LinkGraphBetaFrontierOperationalMatrix) -> bool:
    """Recheck structural invariants independently from matrix construction."""

    return (
        matrix.accepted
        and len(matrix.cells) == matrix.expected_cell_count
        and set(matrix.dimension_names) == {"role", "context", "state", "issue", "receipt", "measurement"}
        and all(len(matrix.for_operation(operation)) == matrix.record_count // 4 * len(matrix.dimensions) for operation in matrix.operation_names)
        and all(item.passed and item.result_address.startswith("sha256:") for item in matrix.cells)
    )


def compare_link_graph_beta_frontier_matrices(
    left: LinkGraphBetaFrontierOperationalMatrix,
    right: LinkGraphBetaFrontierOperationalMatrix,
) -> dict[str, Any]:
    """Compare matrices by cell ID and report all changed values."""

    left_by_id = {item.cell_id: item for item in left.cells}
    right_by_id = {item.cell_id: item for item in right.cells}
    ids = tuple(sorted(set(left_by_id) | set(right_by_id)))
    changes = []
    for cell_id in ids:
        left_cell = left_by_id.get(cell_id)
        right_cell = right_by_id.get(cell_id)
        left_value = None if left_cell is None else (left_cell.expected, left_cell.observed, left_cell.passed)
        right_value = None if right_cell is None else (right_cell.expected, right_cell.observed, right_cell.passed)
        changes.append({"cell_id": cell_id, "left": left_value, "right": right_value, "equal": left_value == right_value})
    unequal = tuple(item for item in changes if not item["equal"])
    return {
        "left_address": left.content_address,
        "right_address": right.content_address,
        "cell_count": len(changes),
        "changed_count": len(unequal),
        "changed_cell_ids": tuple(item["cell_id"] for item in unequal),
        "equal": not unequal,
    }


__all__ = [
    "OPERATIONAL_MATRIX_VERSION",
    "LinkGraphBetaFrontierMatrixCell",
    "LinkGraphBetaFrontierMatrixDimension",
    "LinkGraphBetaFrontierMatrixSlice",
    "LinkGraphBetaFrontierOperationalMatrix",
    "build_link_graph_beta_frontier_operational_matrix",
    "compare_link_graph_beta_frontier_matrices",
    "default_link_graph_beta_frontier_matrix_dimensions",
    "matrix_cells_as_rows",
    "matrix_json",
    "matrix_summary",
    "render_matrix_markdown",
    "select_link_graph_beta_frontier_matrix",
    "verify_link_graph_beta_frontier_matrix",
]
