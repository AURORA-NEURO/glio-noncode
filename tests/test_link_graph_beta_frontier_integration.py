"""Integration checks for the public C05-C08 beta review and release surfaces."""

from __future__ import annotations

import json

import pytest

from glio_noncode import (
    LINK_GRAPH_BETA_FRONTIER_BOUNDARY,
    LINK_GRAPH_BETA_FRONTIER_COMMANDS,
    LinkGraphBetaFrontierFixture,
    default_link_graph_beta_frontier_fixture,
    run_link_graph_beta_frontier_operation,
)
from glio_noncode.link_graph_beta_frontier_adapters import build_link_graph_beta_frontier_adapters
from glio_noncode.link_graph_beta_frontier_cli import run_link_graph_beta_frontier_operation as run_cli_operation
from glio_noncode.link_graph_beta_frontier_fixture_eval import evaluate_link_graph_beta_frontier_fixture
from glio_noncode.link_graph_beta_frontier_public_data import LinkGraphBetaFrontierOperation, audit_link_graph_beta_frontier_data
from glio_noncode.link_graph_beta_frontier_runtime import (
    LinkGraphBetaFrontierRuntimeOptions,
    run_link_graph_beta_frontier_runtime,
)
from glio_noncode.link_graph_beta_frontier_scenario_catalog import build_link_graph_beta_frontier_scenario_catalog
from glio_noncode.link_graph_beta_frontier_traceability import build_link_graph_beta_frontier_traceability
from glio_noncode.link_graph_beta_frontier_validation_orchestration import (
    run_link_graph_beta_frontier_validation_orchestration,
)


@pytest.fixture(scope="module")
def fixture() -> LinkGraphBetaFrontierFixture:
    return default_link_graph_beta_frontier_fixture()


def test_root_exports_are_live(fixture):
    assert isinstance(fixture, LinkGraphBetaFrontierFixture)
    assert fixture.boundary == LINK_GRAPH_BETA_FRONTIER_BOUNDARY
    assert fixture.content_address.startswith("sha256:")
    assert len(fixture.records) == 16
    assert len(fixture.sources) == 4


def test_root_operation_enum_is_closed():
    assert tuple(item.value for item in LinkGraphBetaFrontierOperation) == (
        "activity_by_contact",
        "coaccessibility",
        "molecular_qtl",
        "allele_specific",
    )


def test_cli_command_set_is_closed():
    assert len(LINK_GRAPH_BETA_FRONTIER_COMMANDS) == 8
    assert len(set(LINK_GRAPH_BETA_FRONTIER_COMMANDS)) == 8
    assert LINK_GRAPH_BETA_FRONTIER_COMMANDS[0].endswith("fixture")
    assert LINK_GRAPH_BETA_FRONTIER_COMMANDS[-1].endswith("summary")


@pytest.mark.parametrize("command", LINK_GRAPH_BETA_FRONTIER_COMMANDS)
def test_each_root_command_returns_json(command):
    value = run_link_graph_beta_frontier_operation(command)
    assert isinstance(value, dict)
    encoded = json.dumps(value, sort_keys=True)
    assert encoded.startswith("{")
    assert command.endswith("summary") or "content_address" in encoded


def test_direct_cli_and_root_dispatch_match():
    for command in LINK_GRAPH_BETA_FRONTIER_COMMANDS:
        assert run_cli_operation(command) == run_link_graph_beta_frontier_operation(command)


def test_summary_reports_public_boundary_and_counts():
    value = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-summary")
    assert value["fixture_id"] == "link-graph-beta-frontier-fixture"
    assert value["boundary"] == LINK_GRAPH_BETA_FRONTIER_BOUNDARY
    assert value["record_count"] == 16
    assert value["source_count"] == 4
    assert value["positive_count"] == 4
    assert value["control_count"] == 12
    assert value["accepted"] is True
    assert value["operations"] == [item.value for item in LinkGraphBetaFrontierOperation]


def test_summary_operation_counts_are_balanced():
    value = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-summary")
    assert value["operation_counts"] == {
        "activity_by_contact": 4,
        "coaccessibility": 4,
        "molecular_qtl": 4,
        "allele_specific": 4,
    }


def test_runtime_supports_payload_projection():
    with_payload = run_link_graph_beta_frontier_runtime(LinkGraphBetaFrontierRuntimeOptions(include_payload=True))
    without_payload = run_link_graph_beta_frontier_runtime(LinkGraphBetaFrontierRuntimeOptions(include_payload=False))
    assert with_payload.accepted
    assert without_payload.accepted
    assert with_payload.payload
    assert set(without_payload.payload) == {"failed_stages", "state_accuracy", "release"}
    assert with_payload.content_address != without_payload.content_address


def test_runtime_limits_rows_without_changing_acceptance():
    result = run_link_graph_beta_frontier_runtime(LinkGraphBetaFrontierRuntimeOptions(max_rows=3, include_payload=True))
    assert result.accepted
    assert result.row_count == 3
    assert len(result.payload["evaluation"]["rows"]) == 3
    assert result.payload["evaluation"]["accepted"] is True


def test_runtime_rejects_invalid_row_limit():
    with pytest.raises(ValueError, match="max_rows"):
        run_link_graph_beta_frontier_runtime(LinkGraphBetaFrontierRuntimeOptions(max_rows=0))


def test_public_data_and_evaluation_share_addresses(fixture):
    audit = audit_link_graph_beta_frontier_data(fixture)
    evaluation = evaluate_link_graph_beta_frontier_fixture(fixture)
    assert audit.accepted
    assert evaluation.accepted
    assert evaluation.fixture_id == fixture.fixture_id
    assert evaluation.content_address.startswith("sha256:")
    assert all(row.record_id for row in evaluation.rows)
    assert all(row.adapter.content_address.startswith("sha256:") for row in evaluation.rows)


def test_adapter_registry_uses_four_typed_operations():
    registry = build_link_graph_beta_frontier_adapters()
    assert registry.accepted
    assert len(registry.specs) == 4
    assert {item.operation for item in registry.specs} == {item.value for item in LinkGraphBetaFrontierOperation}
    assert all(item.adapter_id and item.input_fields and item.output_fields for item in registry.specs)
    assert all(item.limitation for item in registry.specs)


def test_scenario_catalog_uses_record_ids_as_stable_keys(fixture):
    evaluation = evaluate_link_graph_beta_frontier_fixture(fixture)
    catalog = build_link_graph_beta_frontier_scenario_catalog(fixture, evaluation)
    assert catalog.accepted
    assert len(catalog.definitions) == len(catalog.outcomes) == 16
    assert {item.scenario_id.removeprefix("scenario-").upper() for item in catalog.definitions} == {item.record_id for item in fixture.records}
    assert {item.scenario_id.removeprefix("scenario-").upper() for item in catalog.outcomes} == {item.record_id for item in fixture.records}


def test_control_rows_never_promote_to_positive_claims(fixture):
    evaluation = evaluate_link_graph_beta_frontier_fixture(fixture)
    control_ids = {item.record_id for item in fixture.records if item.role.value == "control"}
    control_rows = tuple(item for item in evaluation.rows if item.record_id in control_ids)
    assert len(control_rows) == 12
    assert all(item.observed_state != "supported" for item in control_rows)
    assert all(item.observed_state in {"partial", "abstained", "contradictory", "out_of_domain"} for item in control_rows)


def test_foreign_context_controls_remain_out_of_domain(fixture):
    evaluation = evaluate_link_graph_beta_frontier_fixture(fixture)
    foreign_ids = {item.record_id for item in fixture.records if item.context_key == fixture.foreign_context_key}
    foreign_rows = tuple(item for item in evaluation.rows if item.record_id in foreign_ids)
    assert len(foreign_rows) == 4
    assert all(item.observed_state == "out_of_domain" for item in foreign_rows)
    assert all(item.observed_issue_codes == ("context_mismatch",) for item in foreign_rows)


def test_traceability_connects_operations_to_public_modules(fixture):
    report = build_link_graph_beta_frontier_traceability(fixture)
    assert report.accepted
    assert len(report.items) == 4
    assert {item.operation for item in report.items} == {item.value for item in LinkGraphBetaFrontierOperation}
    assert all(item.implementation_modules for item in report.items)
    assert all(item.test_modules for item in report.items)


def test_validation_orchestration_is_json_safe(fixture):
    report = run_link_graph_beta_frontier_validation_orchestration(fixture)
    encoded = json.dumps(report.to_dict())
    assert report.accepted
    assert json.loads(encoded)["accepted"] is True
    assert len(report.checks) == 7
    assert all(item.passed for item in report.checks)


def test_operation_specific_commands_return_expected_shapes():
    fixture = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-fixture")
    evaluation = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-evaluate")
    contracts = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-contracts")
    schema = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-schema")
    metrics = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-metrics")
    review = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-review")
    release = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-release")
    assert fixture["fixture"]["fixture_id"] == "link-graph-beta-frontier-fixture"
    assert len(fixture["fixture"]["records"]) == 16
    assert len(evaluation["rows"]) == 16
    assert evaluation["state_match_count"] == 16
    assert len(contracts["contracts"]) == 4
    assert len(schema["fields"]) == 9
    assert metrics["state_accuracy"] == 1.0
    assert review["entry_count"] == 16
    assert release["publishable"] is True


def test_fixture_audit_matches_summary(fixture):
    value = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-summary")
    audit = audit_link_graph_beta_frontier_data(fixture)
    assert value["record_count"] == audit.record_count
    assert value["source_count"] == audit.source_count
    assert value["positive_count"] == audit.positive_count
    assert value["control_count"] == audit.control_count
    assert value["accepted"] == audit.accepted


def test_root_surface_does_not_leak_mutable_fixture_rows(fixture):
    first = default_link_graph_beta_frontier_fixture()
    second = default_link_graph_beta_frontier_fixture()
    assert first.to_dict(False) == second.to_dict(False)
    assert first.records is not second.records
    assert first.sources is not second.sources


def test_boundary_is_consistent_across_fixture_audit_and_summary(fixture):
    audit = audit_link_graph_beta_frontier_data(fixture)
    summary = run_link_graph_beta_frontier_operation("link-graph-beta-frontier-summary")
    assert fixture.boundary == summary["boundary"] == "public_aggregate_non_patient"
    assert audit.accepted
