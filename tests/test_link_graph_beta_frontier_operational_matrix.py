"""Deep matrix and export checks for Domain 10 C05-C08."""

from __future__ import annotations

import json

import pytest

from glio_noncode.link_graph_beta_frontier_fixture_eval import evaluate_link_graph_beta_frontier_fixture
from glio_noncode.link_graph_beta_frontier_operational_matrix import (
    OPERATIONAL_MATRIX_VERSION,
    LinkGraphBetaFrontierMatrixCell,
    LinkGraphBetaFrontierMatrixDimension,
    LinkGraphBetaFrontierMatrixSlice,
    LinkGraphBetaFrontierOperationalMatrix,
    build_link_graph_beta_frontier_operational_matrix,
    compare_link_graph_beta_frontier_matrices,
    default_link_graph_beta_frontier_matrix_dimensions,
    matrix_cells_as_rows,
    matrix_json,
    matrix_summary,
    render_matrix_markdown,
    select_link_graph_beta_frontier_matrix,
    verify_link_graph_beta_frontier_matrix,
)
from glio_noncode.link_graph_beta_frontier_public_data import (
    LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY,
    LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY,
    LinkGraphBetaFrontierOperation,
    default_link_graph_beta_frontier_fixture,
)


@pytest.fixture(scope="module")
def fixture():
    return default_link_graph_beta_frontier_fixture()


@pytest.fixture(scope="module")
def evaluation(fixture):
    return evaluate_link_graph_beta_frontier_fixture(fixture)


@pytest.fixture(scope="module")
def matrix(fixture, evaluation):
    return build_link_graph_beta_frontier_operational_matrix(fixture, evaluation)


def test_matrix_version_and_dimensions_are_stable(matrix):
    assert matrix.version == OPERATIONAL_MATRIX_VERSION
    assert matrix.dimension_names == (
        "role",
        "context",
        "state",
        "issue",
        "receipt",
        "measurement",
    )
    assert matrix.operation_names == tuple(item.value for item in LinkGraphBetaFrontierOperation)
    assert matrix.record_count == 16
    assert matrix.expected_cell_count == 96
    assert len(matrix.cells) == 96


def test_matrix_is_accepted_and_independently_verifiable(matrix):
    assert matrix.accepted
    assert verify_link_graph_beta_frontier_matrix(matrix)
    assert not matrix.failed_cells
    assert matrix.passed_cell_count == matrix.expected_cell_count
    assert matrix.content_address.startswith("sha256:")


def test_each_record_has_one_cell_per_dimension(matrix, fixture):
    assert {item.record_id for item in matrix.cells} == {item.record_id for item in fixture.records}
    for record in fixture.records:
        cells = matrix.for_record(record.record_id)
        assert len(cells) == 6
        assert {item.dimension for item in cells} == set(matrix.dimension_names)
        assert all(item.operation == record.operation.value for item in cells)
        assert all(item.record_id == record.record_id for item in cells)


@pytest.mark.parametrize(
    "operation",
    (
        "activity_by_contact",
        "coaccessibility",
        "molecular_qtl",
        "allele_specific",
    ),
)
def test_operation_slices_have_four_records_and_six_dimensions(matrix, operation):
    cells = matrix.for_operation(operation)
    assert len(cells) == 24
    assert {item.record_id for item in cells}.__len__() == 4
    assert {item.dimension for item in cells} == set(matrix.dimension_names)
    assert all(item.passed for item in cells)
    assert all(item.result_address.startswith("sha256:") for item in cells)


@pytest.mark.parametrize("dimension", ("role", "context", "state", "issue", "receipt", "measurement"))
def test_dimension_slices_cover_all_sixteen_records(matrix, fixture, dimension):
    cells = matrix.for_dimension(dimension)
    assert len(cells) == len(fixture.records) == 16
    assert {item.record_id for item in cells} == {item.record_id for item in fixture.records}
    assert all(item.dimension == dimension for item in cells)
    assert all(item.passed for item in cells)


def test_role_cells_retain_positive_and_control_counts(matrix):
    cells = matrix.for_dimension("role")
    positive = tuple(item for item in cells if item.observed == "positive")
    controls = tuple(item for item in cells if item.observed == "control")
    assert len(positive) == 4
    assert len(controls) == 12
    assert {item.record_id for item in positive} == {
        "D10-C05-P",
        "D10-C06-P",
        "D10-C07-P",
        "D10-C08-P",
    }
    assert all(item.expected == item.observed for item in cells)


def test_context_cells_retain_target_and_foreign_partitions(matrix):
    cells = matrix.for_dimension("context")
    target = tuple(item for item in cells if item.observed == LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY)
    foreign = tuple(item for item in cells if item.observed == LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY)
    assert len(target) == 12
    assert len(foreign) == 4
    assert all(item.expected == item.observed for item in cells)
    assert all(item.record_id.endswith("-C3") for item in foreign)


def test_state_cells_expose_each_boundary_state(matrix):
    cells = matrix.for_dimension("state")
    by_state = {state: tuple(item for item in cells if item.observed == state) for state in {item.observed for item in cells}}
    assert {item.observed for item in cells} == {"partial", "abstained", "out_of_domain", "contradictory"}
    assert len(by_state["partial"]) == 7
    assert len(by_state["abstained"]) == 4
    assert len(by_state["out_of_domain"]) == 4
    assert len(by_state["contradictory"]) == 1
    assert all(item.expected == item.observed for item in cells)


def test_issue_cells_keep_issue_floor_semantics(matrix):
    cells = matrix.for_dimension("issue")
    assert len(cells) == 16
    assert all(item.expected == item.observed for item in cells)
    assert {item.observed for item in cells} == {
        "single_method",
        "replicate_pair",
        "missing_evidence",
        "context_mismatch",
        "alternative_gene",
        "weak_q_value",
        "single_direction",
        "direction_conflict",
    }
    assert matrix.cell("D10-C05-C1:issue").observed == "replicate_pair"
    assert matrix.cell("D10-C06-C1:issue").observed == "alternative_gene"
    assert matrix.cell("D10-C07-C1:issue").observed == "weak_q_value"
    assert matrix.cell("D10-C08-C1:issue").observed == "direction_conflict"


def test_receipt_cells_are_one_source_each(matrix, fixture):
    cells = matrix.for_dimension("receipt")
    assert all(item.expected == "1" for item in cells)
    assert all(item.observed == "1" for item in cells)
    assert all(len(item.source_addresses) == 1 for item in cells)
    assert all(item.source_addresses[0] == next(record.content_address for record in fixture.records if record.record_id == item.record_id) for item in cells)


def test_measurement_cells_quarantine_foreign_context(matrix):
    cells = matrix.for_dimension("measurement")
    foreign = tuple(item for item in cells if item.record_id.endswith("-C3"))
    target = tuple(item for item in cells if not item.record_id.endswith("-C3"))
    assert len(foreign) == 4
    assert len(target) == 12
    assert all(item.expected == item.observed == "absent" for item in foreign)
    assert all(item.expected == item.observed for item in target)


def test_cell_addresses_bind_result_and_value(matrix):
    for cell in matrix.cells:
        assert cell.result_address.startswith("sha256:")
        assert cell.source_addresses
        assert all(address.startswith("sha256:") for address in cell.source_addresses)
        assert cell.cell_id == f"{cell.record_id}:{cell.dimension}"
        assert cell.detail


def test_summary_counts_match_matrix_navigation(matrix):
    summary = matrix_summary(matrix)
    assert summary["fixture_id"] == matrix.fixture_id
    assert summary["version"] == matrix.version
    assert summary["record_count"] == 16
    assert summary["dimension_count"] == 6
    assert summary["cell_count"] == 96
    assert summary["expected_cell_count"] == 96
    assert summary["passed_cell_count"] == 96
    assert summary["failed_cell_count"] == 0
    assert summary["operation_counts"] == {
        "activity_by_contact": 24,
        "coaccessibility": 24,
        "molecular_qtl": 24,
        "allele_specific": 24,
    }
    assert summary["dimension_counts"] == {
        "role": 16,
        "context": 16,
        "state": 16,
        "issue": 16,
        "receipt": 16,
        "measurement": 16,
    }
    assert summary["accepted"] is True
    assert summary["content_address"] == matrix.content_address


def test_select_all_returns_complete_slice(matrix):
    selected = select_link_graph_beta_frontier_matrix(matrix)
    assert isinstance(selected, LinkGraphBetaFrontierMatrixSlice)
    assert selected.selector == "all"
    assert len(selected.cells) == 96
    assert selected.accepted
    assert not selected.failed_cells
    assert selected.content_address.startswith("sha256:")


def test_select_operation_returns_only_operation_cells(matrix):
    selected = select_link_graph_beta_frontier_matrix(matrix, operation="coaccessibility")
    assert selected.selector == "operation=coaccessibility"
    assert len(selected.cells) == 24
    assert {item.operation for item in selected.cells} == {"coaccessibility"}
    assert {item.dimension for item in selected.cells} == set(matrix.dimension_names)
    assert selected.accepted


def test_select_dimension_returns_only_dimension_cells(matrix):
    selected = select_link_graph_beta_frontier_matrix(matrix, dimension="issue")
    assert selected.selector == "dimension=issue"
    assert len(selected.cells) == 16
    assert {item.dimension for item in selected.cells} == {"issue"}
    assert len({item.record_id for item in selected.cells}) == 16
    assert selected.accepted


def test_select_record_returns_six_cells(matrix):
    selected = select_link_graph_beta_frontier_matrix(matrix, record_id="D10-C08-C1")
    assert selected.selector == "record_id=D10-C08-C1"
    assert len(selected.cells) == 6
    assert {item.record_id for item in selected.cells} == {"D10-C08-C1"}
    assert {item.dimension for item in selected.cells} == set(matrix.dimension_names)
    assert selected.accepted


def test_select_combined_filters_preserves_selector_order(matrix):
    selected = select_link_graph_beta_frontier_matrix(
        matrix,
        operation="allele_specific",
        dimension="issue",
        record_id="D10-C08-C1",
    )
    assert selected.selector == "operation=allele_specific&dimension=issue&record_id=D10-C08-C1"
    assert len(selected.cells) == 1
    assert selected.cells[0].cell_id == "D10-C08-C1:issue"
    assert selected.cells[0].observed == "direction_conflict"
    assert selected.accepted


def test_select_empty_record_is_not_accepted(matrix):
    selected = select_link_graph_beta_frontier_matrix(matrix, record_id="missing-record")
    assert selected.selector == "record_id=missing-record"
    assert selected.cells == ()
    assert selected.failed_cells == ()
    assert not selected.accepted


@pytest.mark.parametrize("operation", ("bad", "", "ACTIVITY_BY_CONTACT"))
def test_select_rejects_unknown_operation(matrix, operation):
    with pytest.raises(ValueError, match="unknown beta operation"):
        select_link_graph_beta_frontier_matrix(matrix, operation=operation)


@pytest.mark.parametrize("dimension", ("bad", "", "STATE"))
def test_select_rejects_unknown_dimension(matrix, dimension):
    with pytest.raises(ValueError, match="unknown beta dimension"):
        select_link_graph_beta_frontier_matrix(matrix, dimension=dimension)


def test_row_projection_has_one_row_per_cell(matrix):
    rows = matrix_cells_as_rows(matrix)
    assert len(rows) == len(matrix.cells) == 96
    assert all(set(row) == {
        "cell_id",
        "record_id",
        "operation",
        "dimension",
        "expected",
        "observed",
        "passed",
        "source_addresses",
        "result_address",
        "detail",
    } for row in rows)
    assert rows[0]["cell_id"] == matrix.cells[0].cell_id
    assert rows[-1]["cell_id"] == matrix.cells[-1].cell_id
    assert all(row["passed"] is True for row in rows)


def test_row_projection_is_stable(matrix):
    assert matrix_cells_as_rows(matrix) == matrix_cells_as_rows(matrix)
    assert matrix_cells_as_rows(matrix)[0]["record_id"] == "D10-C05-P"
    assert matrix_cells_as_rows(matrix)[0]["dimension"] == "role"
    assert matrix_cells_as_rows(matrix)[5]["dimension"] == "measurement"
    assert matrix_cells_as_rows(matrix)[6]["record_id"] == "D10-C05-C1"


def test_matrix_json_is_deterministic_and_parseable(matrix):
    encoded = matrix_json(matrix)
    assert encoded == matrix_json(matrix)
    decoded = json.loads(encoded)
    assert decoded["fixture_id"] == matrix.fixture_id
    assert decoded["version"] == OPERATIONAL_MATRIX_VERSION
    assert len(decoded["cells"]) == 96
    assert decoded["accepted"] is True
    assert decoded["content_address"] == matrix.content_address
    assert encoded.index('"cells"') < encoded.index('"dimensions"')


def test_markdown_render_contains_header_and_all_rows(matrix):
    rendered = render_matrix_markdown(matrix)
    lines = rendered.splitlines()
    assert lines[0] == "# link-graph-beta-frontier-fixture operational matrix"
    assert "Accepted: `true`" in rendered
    assert "Cells: `96` / `96`" in rendered
    assert "| Record | Operation | Dimension | Expected | Observed | Pass |" in rendered
    assert rendered.count("| D10-") == 96
    assert "| D10-C05-P | activity_by_contact | role | positive | positive | true |" in rendered
    assert "| D10-C08-C1 | allele_specific | issue | direction_conflict | direction_conflict | true |" in rendered
    assert lines[-1].endswith("| true |")


def test_matrix_compare_self_is_equal(matrix):
    report = compare_link_graph_beta_frontier_matrices(matrix, matrix)
    assert report["left_address"] == matrix.content_address
    assert report["right_address"] == matrix.content_address
    assert report["cell_count"] == 96
    assert report["changed_count"] == 0
    assert report["changed_cell_ids"] == ()
    assert report["equal"] is True


def test_matrix_compare_rebuilt_value_is_equal(fixture, evaluation, matrix):
    rebuilt = build_link_graph_beta_frontier_operational_matrix(fixture, evaluation)
    report = compare_link_graph_beta_frontier_matrices(matrix, rebuilt)
    assert rebuilt.to_dict(False) == matrix.to_dict(False)
    assert report["equal"] is True
    assert report["changed_count"] == 0


def test_matrix_compare_detects_changed_cell():
    original = build_link_graph_beta_frontier_operational_matrix()
    changed = tuple(
        LinkGraphBetaFrontierMatrixCell(
            item.cell_id,
            item.record_id,
            item.operation,
            item.dimension,
            "altered" if item.cell_id == "D10-C05-P:state" else item.expected,
            item.observed,
            False if item.cell_id == "D10-C05-P:state" else item.passed,
            item.source_addresses,
            item.result_address,
            item.detail,
        )
        for item in original.cells
    )
    replacement = LinkGraphBetaFrontierOperationalMatrix(
        original.fixture_id,
        original.version,
        original.dimensions,
        changed,
        original.record_count,
        False,
    )
    report = compare_link_graph_beta_frontier_matrices(original, replacement)
    assert report["equal"] is False
    assert report["changed_count"] == 1
    assert report["changed_cell_ids"] == ("D10-C05-P:state",)


def test_matrix_from_default_fixture_is_same_as_explicit_inputs(fixture, evaluation):
    implicit = build_link_graph_beta_frontier_operational_matrix()
    explicit = build_link_graph_beta_frontier_operational_matrix(fixture, evaluation)
    assert implicit.to_dict(False) == explicit.to_dict(False)
    assert implicit.content_address == explicit.content_address


def test_matrix_with_default_evaluation_is_accepted(fixture):
    value = build_link_graph_beta_frontier_operational_matrix(fixture)
    assert value.accepted
    assert value.record_count == len(fixture.records)
    assert len(value.cells) == len(fixture.records) * 6


def test_dimension_definitions_have_complete_comparison_rules():
    dimensions = default_link_graph_beta_frontier_matrix_dimensions()
    assert len(dimensions) == 6
    assert all(item.name and item.description and item.comparison for item in dimensions)
    assert all(item.required for item in dimensions)
    assert {item.comparison for item in dimensions} == {"exact", "set_contains"}
    assert [item.name for item in dimensions] == [
        "role",
        "context",
        "state",
        "issue",
        "receipt",
        "measurement",
    ]


def test_dimension_objects_serialize_without_hashes():
    dimensions = default_link_graph_beta_frontier_matrix_dimensions()
    for dimension in dimensions:
        value = dimension.to_dict()
        assert value["name"] == dimension.name
        assert value["description"] == dimension.description
        assert value["comparison"] == dimension.comparison
        assert value["required"] is True


def test_matrix_cell_requires_content_address():
    with pytest.raises(ValueError, match="content hashes"):
        LinkGraphBetaFrontierMatrixCell(
            "x",
            "r",
            "activity_by_contact",
            "role",
            "positive",
            "positive",
            True,
            (),
            "not-addressed",
            "test",
        )


def test_matrix_slice_address_changes_with_selector(matrix):
    all_slice = select_link_graph_beta_frontier_matrix(matrix)
    issue_slice = select_link_graph_beta_frontier_matrix(matrix, dimension="issue")
    record_slice = select_link_graph_beta_frontier_matrix(matrix, record_id="D10-C05-P")
    assert all_slice.content_address != issue_slice.content_address
    assert issue_slice.content_address != record_slice.content_address
    assert all(address.startswith("sha256:") for address in (
        all_slice.content_address,
        issue_slice.content_address,
        record_slice.content_address,
    ))


def test_matrix_slice_to_dict_includes_failure_projection(matrix):
    selected = select_link_graph_beta_frontier_matrix(matrix, operation="activity_by_contact")
    value = selected.to_dict()
    assert value["selector"] == "operation=activity_by_contact"
    assert len(value["cells"]) == 24
    assert value["failed_cells"] == ()
    assert value["accepted"] is True
    assert value["content_address"] == selected.content_address


def test_matrix_report_to_dict_includes_rollups(matrix):
    value = matrix.to_dict()
    assert value["fixture_id"] == matrix.fixture_id
    assert value["record_count"] == 16
    assert value["expected_cell_count"] == 96
    assert value["passed_cell_count"] == 96
    assert value["failed_cells"] == ()
    assert value["operation_names"] == matrix.operation_names
    assert value["accepted"] is True
    assert value["content_address"] == matrix.content_address


def test_foreign_context_state_and_measurement_cells_are_aligned(matrix):
    for record_id in ("D10-C05-C3", "D10-C06-C3", "D10-C07-C3", "D10-C08-C3"):
        state = matrix.cell(f"{record_id}:state")
        context = matrix.cell(f"{record_id}:context")
        measurement = matrix.cell(f"{record_id}:measurement")
        assert context.observed == LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY
        assert state.observed == "out_of_domain"
        assert measurement.observed == "absent"
        assert state.passed and context.passed and measurement.passed


def test_positive_rows_remain_partial_and_measured(matrix):
    for record_id in ("D10-C05-P", "D10-C06-P", "D10-C07-P", "D10-C08-P"):
        state = matrix.cell(f"{record_id}:state")
        role = matrix.cell(f"{record_id}:role")
        measurement = matrix.cell(f"{record_id}:measurement")
        assert state.observed == "partial"
        assert role.observed == "positive"
        assert measurement.observed == "present"


def test_control_rows_remain_non_positive_in_role_dimension(matrix):
    positive_ids = {"D10-C05-P", "D10-C06-P", "D10-C07-P", "D10-C08-P"}
    role_cells = matrix.for_dimension("role")
    assert all(item.observed == "positive" for item in role_cells if item.record_id in positive_ids)
    assert all(item.observed == "control" for item in role_cells if item.record_id not in positive_ids)


def test_issue_dimension_has_one_cell_per_control_reason(matrix):
    issue_cells = matrix.for_dimension("issue")
    for issue in (
        "replicate_pair",
        "alternative_gene",
        "weak_q_value",
        "direction_conflict",
        "missing_evidence",
        "context_mismatch",
    ):
        assert any(item.observed == issue for item in issue_cells)


def test_matrix_navigation_returns_immutable_tuples(matrix):
    assert isinstance(matrix.cells, tuple)
    assert isinstance(matrix.dimensions, tuple)
    assert isinstance(matrix.for_operation("activity_by_contact"), tuple)
    assert isinstance(matrix.for_dimension("state"), tuple)
    assert isinstance(matrix.for_record("D10-C05-P"), tuple)
    assert isinstance(select_link_graph_beta_frontier_matrix(matrix).cells, tuple)
