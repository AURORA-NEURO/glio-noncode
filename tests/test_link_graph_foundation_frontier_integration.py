"""Integration checks for the public C01-C04 review and validation surfaces."""

from __future__ import annotations

import json

import pytest

from glio_noncode import (
    LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY,
    LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS,
    LinkGraphFoundationFrontierFixture,
    default_link_graph_foundation_frontier_fixture,
    run_link_graph_foundation_frontier_operation,
)
from glio_noncode.link_graph_foundation_frontier_cli import (
    run_link_graph_foundation_frontier_operation,
)
from glio_noncode.link_graph_foundation_frontier_public_data import (
    LinkGraphFoundationFrontierOperation,
)
from glio_noncode.link_graph_foundation_frontier_scenario_catalog import (
    build_link_graph_foundation_frontier_scenario_catalog,
    scenario_catalog_summary,
)
from glio_noncode.link_graph_foundation_frontier_traceability import (
    build_link_graph_foundation_frontier_traceability,
    traceability_summary,
)
from glio_noncode.link_graph_foundation_frontier_validation_orchestration import (
    run_link_graph_foundation_frontier_validation_orchestration,
    validation_orchestration_summary,
)
from glio_noncode.link_graph_foundation_frontier_public_data import (
    audit_link_graph_foundation_frontier_data,
)


@pytest.fixture(scope="module")
def fixture() -> LinkGraphFoundationFrontierFixture:
    return default_link_graph_foundation_frontier_fixture()


def test_root_exports_are_live(fixture):
    assert isinstance(fixture, LinkGraphFoundationFrontierFixture)
    assert fixture.boundary == LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY
    assert fixture.content_address.startswith("sha256:")
    assert len(fixture.records) == 16


def test_cli_command_set_is_closed():
    assert len(LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS) == 8
    assert len(set(LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS)) == 8
    assert LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[0].endswith("fixture")
    assert LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[-1].endswith("summary")


@pytest.mark.parametrize("command", LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS)
def test_each_root_command_returns_json(command):
    value = run_link_graph_foundation_frontier_operation(command)
    assert isinstance(value, dict)
    encoded = json.dumps(value, sort_keys=True)
    assert encoded.startswith("{")
    assert "content_address" in encoded or command.endswith("summary")


def test_summary_command_reports_public_boundary():
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-summary"
    )
    assert value["fixture_id"] == "link-graph-foundation-frontier-fixture"
    assert value["boundary"] == LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY
    assert value["record_count"] == 16
    assert value["source_count"] == 5
    assert value["positive_count"] == 4
    assert value["control_count"] == 12
    assert value["accepted"] is True


def test_summary_command_supports_all_operations():
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-summary"
    )
    assert set(value["operations"]) == {
        item.value for item in LinkGraphFoundationFrontierOperation
    }
    assert all(value["operation_counts"][item] == 4 for item in value["operations"])


def test_scenario_catalog_covers_each_fixture_row(fixture):
    catalog = build_link_graph_foundation_frontier_scenario_catalog(fixture)
    summary = scenario_catalog_summary(catalog)
    assert catalog.accepted
    assert len(catalog.definitions) == 16
    assert len(catalog.outcomes) == 16
    assert summary["positive_count"] == 4
    assert summary["control_count"] == 12
    assert not catalog.failed_scenarios


def test_scenario_outcomes_keep_boundary_states(fixture):
    catalog = build_link_graph_foundation_frontier_scenario_catalog(fixture)
    states = {definition.expected_state for definition in catalog.definitions}
    assert {"supported", "ambiguous", "absent", "out_of_domain"} <= states
    assert {"abstained", "partial", "contradictory"} <= states
    assert catalog.outcome("scenario-d10-c02-c2").observed_states == ("abstained",)
    assert catalog.outcome("scenario-d10-c04-c2").observed_states == ("contradictory",)


def test_traceability_is_complete(fixture):
    report = build_link_graph_foundation_frontier_traceability(fixture)
    summary = traceability_summary(report)
    assert report.accepted
    assert summary["item_count"] == 4
    assert summary["passed_count"] == 4
    assert summary["module_count"] >= 3
    assert summary["test_count"] == 2
    assert not report.failed_items


def test_validation_orchestration_is_green(fixture):
    report = run_link_graph_foundation_frontier_validation_orchestration(fixture)
    summary = validation_orchestration_summary(report)
    assert report.accepted
    assert summary["check_count"] == 7
    assert summary["passed_count"] == 7
    assert not report.failed_checks
    assert report.audit.accepted
    assert report.evaluation.accepted
    assert report.fields.accepted
    assert report.conformance.accepted
    assert report.invariants.accepted
    assert report.assertions.accepted
    assert report.traceability.accepted


def test_validation_orchestration_has_distinct_addresses(fixture):
    report = run_link_graph_foundation_frontier_validation_orchestration(fixture)
    addresses = [check.source_address for check in report.checks]
    assert all(address.startswith("sha256:") for address in addresses)
    assert len(set(addresses)) == len(addresses)
    assert report.content_address.startswith("sha256:")


def test_record_and_source_contracts_are_preserved(fixture):
    audit = audit_link_graph_foundation_frontier_data(fixture)
    assert audit.accepted
    source_ids = {source.source_id for source in fixture.sources}
    assert all(set(record.source_ids) <= source_ids for record in fixture.records)
    assert all(record.expected_measurements for record in fixture.records)
    assert all(record.content_address.startswith("sha256:") for record in fixture.records)


def test_foreign_context_rows_remain_controls(fixture):
    foreign = tuple(record for record in fixture.records if record.context_key == fixture.foreign_context_key)
    assert len(foreign) == 4
    assert all(record.role.value == "control" for record in foreign)
    assert {record.expected_state for record in foreign} == {"out_of_domain", "abstained"}
    assert all("context_mismatch" in record.expected_issue_codes for record in foreign)


def test_operation_counts_are_exact(fixture):
    counts = {
        operation.value: len(fixture.operation_records(operation))
        for operation in LinkGraphFoundationFrontierOperation
    }
    assert counts == {
        "coordinate_overlap": 4,
        "nearest_gene": 4,
        "ccre_assignment": 4,
        "enhancer_gene_consensus": 4,
    }


def test_json_round_trip_preserves_summary(fixture):
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-summary"
    )
    round_trip = json.loads(json.dumps(value))
    assert round_trip == value
    assert round_trip["fixture_id"] == fixture.fixture_id


def test_cli_fixture_has_sanitized_payload():
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-fixture"
    )
    assert value["boundary"] == LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY
    assert len(value["fixture"]["records"]) == 16
    assert all("payload" in row for row in value["fixture"]["records"])
    assert all("source_ids" in row for row in value["fixture"]["records"])


def test_cli_release_has_release_address():
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-release"
    )
    assert value["publishable"] is True
    assert value["content_address"].startswith("sha256:")
    assert value["limitations"]


def test_cli_review_exposes_queue_and_projection():
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-review"
    )
    assert value["accepted"] is True
    assert len(value["entries"]) == 16
    assert value["content_address"].startswith("sha256:")


def test_source_registry_has_five_public_receipts():
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-contracts"
    )
    assert value["accepted"] is True
    assert len(value["contracts"]) == 4
    schema = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-schema"
    )
    assert schema["accepted"] is True
    assert len(schema["fields"]) >= 9


def test_metrics_command_has_per_operation_rows():
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-metrics"
    )
    assert value["accepted"] is True
    assert value["record_count"] == 16
    assert value["positive_count"] == 4
    assert value["control_count"] == 12
    assert len(value["operations"]) == 4


def test_evaluate_command_reports_full_replay():
    value = run_link_graph_foundation_frontier_operation(
        "link-graph-foundation-frontier-evaluate"
    )
    assert value["accepted"] is True
    assert value["state_match_count"] == 16
    assert value["issue_match_count"] == 16
    assert not value["failed_record_ids"]


def test_contract_state_is_explicit_in_fixture():
    fixture = default_link_graph_foundation_frontier_fixture()
    expected = {
        "D10-C01-P": "supported",
        "D10-C01-C1": "ambiguous",
        "D10-C01-C2": "absent",
        "D10-C01-C3": "out_of_domain",
        "D10-C02-P": "supported",
        "D10-C02-C1": "ambiguous",
        "D10-C02-C2": "abstained",
        "D10-C02-C3": "abstained",
        "D10-C03-P": "supported",
        "D10-C03-C1": "ambiguous",
        "D10-C03-C2": "absent",
        "D10-C03-C3": "out_of_domain",
        "D10-C04-P": "supported",
        "D10-C04-C1": "partial",
        "D10-C04-C2": "contradictory",
        "D10-C04-C3": "out_of_domain",
    }
    assert {record.record_id: record.expected_state for record in fixture.records} == expected
