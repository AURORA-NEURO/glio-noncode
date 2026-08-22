"""CLI and root integration tests for the D10 link plane."""

from __future__ import annotations

import json

from glio_noncode import LINK_GRAPH_ALPHA_FRONTIER_COMMANDS, run_link_graph_alpha_frontier_operation


def test_all_frontier_commands_return_objects():
    for command in LINK_GRAPH_ALPHA_FRONTIER_COMMANDS:
        result = run_link_graph_alpha_frontier_operation(command)
        assert isinstance(result, dict)
        assert result


def test_cli_summary_shape():
    result = run_link_graph_alpha_frontier_operation("link-graph-alpha-frontier-summary")
    assert result["fixture_id"] == "link-graph-alpha-frontier-fixture"
    assert result["record_count"] == 16
    assert result["source_count"] == 5
    assert result["accepted"] is True


def test_cli_evaluation_is_json_safe():
    result = run_link_graph_alpha_frontier_operation("link-graph-alpha-frontier-evaluate")
    assert result["accepted"] is True
    assert len(result["rows"]) == 16
    json.dumps(result)


def test_cli_fixture_contains_sources_and_controls():
    result = run_link_graph_alpha_frontier_operation("link-graph-alpha-frontier-fixture")
    assert result["audit"]["accepted"] is True
    assert len(result["fixture"]["sources"]) == 5
    assert len(result["fixture"]["records"]) == 16


def test_cli_release_and_manifest():
    release = run_link_graph_alpha_frontier_operation("link-graph-alpha-frontier-release")
    manifest = run_link_graph_alpha_frontier_operation("link-graph-alpha-frontier-manifest")
    assert release["publishable"] is True
    assert "fixture" in manifest["manifest"]
