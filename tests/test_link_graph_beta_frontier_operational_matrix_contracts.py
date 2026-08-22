"""Contract-level checks for the beta operational matrix projection."""

from __future__ import annotations

import json

import pytest

from glio_noncode.link_graph_beta_frontier_operational_matrix import (
    LinkGraphBetaFrontierMatrixCell,
    LinkGraphBetaFrontierMatrixDimension,
    build_link_graph_beta_frontier_operational_matrix,
    compare_link_graph_beta_frontier_matrices,
    matrix_cells_as_rows,
    matrix_json,
    matrix_summary,
    render_matrix_markdown,
    select_link_graph_beta_frontier_matrix,
    verify_link_graph_beta_frontier_matrix,
)


def test_matrix_hash_is_stable_across_process_inputs():
    first = build_link_graph_beta_frontier_operational_matrix()
    second = build_link_graph_beta_frontier_operational_matrix()
    assert first.content_address == second.content_address
    assert first.to_dict(False) == second.to_dict(False)
    assert matrix_json(first) == matrix_json(second)


def test_matrix_summary_has_no_unbounded_counts():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    summary = matrix_summary(matrix)
    assert summary["cell_count"] == summary["expected_cell_count"]
    assert summary["passed_cell_count"] == summary["cell_count"]
    assert summary["failed_cell_count"] == 0
    assert sum(summary["operation_counts"].values()) == summary["cell_count"]
    assert sum(summary["dimension_counts"].values()) == summary["cell_count"]


def test_matrix_json_round_trip_preserves_public_keys():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    value = json.loads(matrix_json(matrix))
    assert set(value) == {
        "accepted",
        "cells",
        "content_address",
        "dimensions",
        "expected_cell_count",
        "failed_cells",
        "fixture_id",
        "operation_names",
        "passed_cell_count",
        "record_count",
        "version",
    }
    assert all(set(cell) == {
        "cell_id",
        "detail",
        "dimension",
        "expected",
        "observed",
        "operation",
        "passed",
        "record_id",
        "result_address",
        "source_addresses",
    } for cell in value["cells"])


def test_markdown_has_one_data_line_per_cell():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    lines = render_matrix_markdown(matrix).splitlines()
    data_lines = tuple(line for line in lines if line.startswith("| D10-"))
    assert len(data_lines) == len(matrix.cells)
    assert all(line.replace("\\|", "").count("|") == 7 for line in data_lines)


def test_rows_are_json_serializable_without_custom_hooks():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    rows = matrix_cells_as_rows(matrix)
    encoded = json.dumps(rows, sort_keys=True, default=str)
    decoded = json.loads(encoded)
    assert len(decoded) == 96
    assert decoded[0]["cell_id"] == rows[0]["cell_id"]
    assert decoded[-1]["result_address"].startswith("sha256:")


def test_record_slice_filters_before_dimension_slice():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    selected = select_link_graph_beta_frontier_matrix(
        matrix,
        record_id="D10-C05-P",
        dimension="state",
    )
    assert selected.selector == "dimension=state&record_id=D10-C05-P"
    assert len(selected.cells) == 1
    assert selected.cells[0].expected == "partial"


def test_operation_and_record_slice_can_be_empty():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    selected = select_link_graph_beta_frontier_matrix(
        matrix,
        operation="activity_by_contact",
        record_id="D10-C08-P",
    )
    assert selected.selector == "operation=activity_by_contact&record_id=D10-C08-P"
    assert selected.cells == ()
    assert selected.accepted is False


def test_each_matrix_cell_has_a_replay_result_address():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    assert len({item.result_address for item in matrix.cells}) == 16
    assert all(item.result_address.startswith("sha256:") for item in matrix.cells)


def test_each_record_reuses_one_replay_address_across_dimensions():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    for record_id in {item.record_id for item in matrix.cells}:
        addresses = {item.result_address for item in matrix.for_record(record_id)}
        assert len(addresses) == 1


def test_issue_cells_are_sorted_for_multi_issue_values():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    for cell in matrix.for_dimension("issue"):
        assert cell.observed == ",".join(sorted(cell.observed.split(",")))


def test_all_matrix_dimensions_have_required_contracts():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    for dimension in matrix.dimensions:
        assert isinstance(dimension, LinkGraphBetaFrontierMatrixDimension)
        assert dimension.required
        assert dimension.name in matrix.dimension_names
        assert dimension.comparison in {"exact", "set_contains"}


def test_matrix_cells_are_typed_contract_objects():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    assert all(isinstance(item, LinkGraphBetaFrontierMatrixCell) for item in matrix.cells)
    assert all(isinstance(item.expected, str) for item in matrix.cells)
    assert all(isinstance(item.observed, str) for item in matrix.cells)
    assert all(isinstance(item.passed, bool) for item in matrix.cells)


def test_matrix_verification_rejects_wrong_record_count():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    wrong = type(matrix)(
        matrix.fixture_id,
        matrix.version,
        matrix.dimensions,
        matrix.cells,
        matrix.record_count + 1,
        True,
    )
    assert verify_link_graph_beta_frontier_matrix(wrong) is False


def test_matrix_comparison_reports_addresses_and_counts():
    left = build_link_graph_beta_frontier_operational_matrix()
    right = build_link_graph_beta_frontier_operational_matrix()
    report = compare_link_graph_beta_frontier_matrices(left, right)
    assert report["left_address"] == left.content_address
    assert report["right_address"] == right.content_address
    assert report["cell_count"] == 96
    assert report["changed_count"] == 0
    assert report["equal"]


def test_matrix_comparison_handles_added_cell():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    extra = LinkGraphBetaFrontierMatrixCell(
        "extra:role",
        "extra",
        "activity_by_contact",
        "role",
        "control",
        "control",
        True,
        ("sha256:extra",),
        "sha256:extra-result",
        "synthetic comparison cell",
    )
    expanded = type(matrix)(
        matrix.fixture_id,
        matrix.version,
        matrix.dimensions,
        matrix.cells + (extra,),
        matrix.record_count,
        False,
    )
    report = compare_link_graph_beta_frontier_matrices(matrix, expanded)
    assert report["equal"] is False
    assert report["changed_count"] == 1
    assert report["changed_cell_ids"] == ("extra:role",)


def test_matrix_comparison_handles_removed_cell():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    reduced = type(matrix)(
        matrix.fixture_id,
        matrix.version,
        matrix.dimensions,
        matrix.cells[:-1],
        matrix.record_count,
        False,
    )
    report = compare_link_graph_beta_frontier_matrices(matrix, reduced)
    assert report["equal"] is False
    assert report["changed_count"] == 1
    assert report["changed_cell_ids"] == (matrix.cells[-1].cell_id,)


@pytest.mark.parametrize(
    ("operation", "record_id", "expected_count"),
    (
        ("activity_by_contact", "D10-C05-P", 6),
        ("coaccessibility", "D10-C06-P", 6),
        ("molecular_qtl", "D10-C07-P", 6),
        ("allele_specific", "D10-C08-P", 6),
    ),
)
def test_positive_operation_record_slices(operation, record_id, expected_count):
    matrix = build_link_graph_beta_frontier_operational_matrix()
    selected = select_link_graph_beta_frontier_matrix(matrix, operation=operation, record_id=record_id)
    assert len(selected.cells) == expected_count
    assert selected.accepted
    assert all(item.record_id == record_id for item in selected.cells)
    assert all(item.operation == operation for item in selected.cells)


@pytest.mark.parametrize(
    ("record_id", "state", "issue"),
    (
        ("D10-C05-C2", "abstained", "missing_evidence"),
        ("D10-C06-C2", "abstained", "missing_evidence"),
        ("D10-C07-C2", "abstained", "missing_evidence"),
        ("D10-C08-C1", "contradictory", "direction_conflict"),
    ),
)
def test_control_record_slices_keep_boundary_outcomes(record_id, state, issue):
    matrix = build_link_graph_beta_frontier_operational_matrix()
    state_cell = matrix.cell(f"{record_id}:state")
    issue_cell = matrix.cell(f"{record_id}:issue")
    assert state_cell.observed == state
    assert issue_cell.observed == issue
    assert state_cell.passed and issue_cell.passed


def test_foreign_record_slices_keep_context_and_quarantine_state():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    for record_id in ("D10-C05-C3", "D10-C06-C3", "D10-C07-C3", "D10-C08-C3"):
        selected = select_link_graph_beta_frontier_matrix(matrix, record_id=record_id)
        values = {item.dimension: item.observed for item in selected.cells}
        assert values["context"] != "GRCh38|glioma|adult|stem_like|core|unknown"
        assert values["state"] == "out_of_domain"
        assert values["issue"] == "context_mismatch"
        assert selected.accepted


def test_matrix_content_address_is_not_the_fixture_address():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    fixture = matrix.fixture_id
    assert matrix.content_address.startswith("sha256:")
    assert matrix.content_address != fixture


def test_matrix_output_is_bounded_to_declared_dimensions():
    matrix = build_link_graph_beta_frontier_operational_matrix()
    row_dimensions = {row["dimension"] for row in matrix_cells_as_rows(matrix)}
    assert row_dimensions == set(matrix.dimension_names)
    assert len(row_dimensions) == 6
