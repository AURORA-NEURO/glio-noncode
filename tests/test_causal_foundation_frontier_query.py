"""Query and report rendering checks for the C01-C04 release plane."""

from __future__ import annotations

import json

import pytest

from glio_noncode.causal_foundation_frontier_fixture_eval import evaluate_causal_foundation_frontier_fixture
from glio_noncode.causal_foundation_frontier_public_data import default_causal_foundation_frontier_fixture
from glio_noncode.causal_foundation_frontier_query import (
    CausalFoundationFrontierQuery,
    query_causal_foundation_frontier,
    query_many_causal_foundation_frontier,
)
from glio_noncode.causal_foundation_frontier_report import (
    render_causal_foundation_frontier_report,
    render_causal_foundation_frontier_report_markdown,
)
from glio_noncode.causal_foundation_frontier_runtime import run_causal_foundation_frontier_runtime


@pytest.fixture(scope="module")
def fixture():
    return default_causal_foundation_frontier_fixture()


@pytest.fixture(scope="module")
def evaluation(fixture):
    return evaluate_causal_foundation_frontier_fixture(fixture)


def test_unfiltered_query_returns_all_rows(fixture, evaluation):
    result = query_causal_foundation_frontier(fixture, evaluation)
    assert result.accepted
    assert result.total_matches == 16
    assert result.record_ids[0] == "D11-C01-P"
    assert result.record_ids[-1] == "D11-C04-C3"
    assert not result.truncated


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (CausalFoundationFrontierQuery(operation="typed_hypothesis_object"), 4),
        (CausalFoundationFrontierQuery(operation="factor_graph_constructor"), 4),
        (CausalFoundationFrontierQuery(role="positive"), 4),
        (CausalFoundationFrontierQuery(role="control"), 12),
        (CausalFoundationFrontierQuery(state="supported"), 4),
        (CausalFoundationFrontierQuery(state="contradictory"), 3),
        (CausalFoundationFrontierQuery(issue_code="context_mismatch"), 4),
        (CausalFoundationFrontierQuery(record_prefix="D11-C03"), 4),
    ],
)
def test_query_filters_are_exact(fixture, evaluation, query, expected):
    result = query_causal_foundation_frontier(fixture, evaluation, query)
    assert result.accepted
    assert result.total_matches == expected
    assert len(result.rows) == expected
    assert all(result.record_ids)


def test_context_query_separates_foreign_rows(fixture, evaluation):
    result = query_causal_foundation_frontier(fixture, evaluation, CausalFoundationFrontierQuery(context_key=fixture.foreign_context_key))
    assert result.total_matches == 4
    assert all(item.record_id.endswith("-C3") for item in result.rows)
    assert all(item.observed_state == "out_of_domain" for item in result.rows)


def test_issue_and_operation_query_can_be_composed(fixture, evaluation):
    result = query_causal_foundation_frontier(fixture, evaluation, CausalFoundationFrontierQuery(operation="typed_hypothesis_object", issue_code="context_mismatch"))
    assert result.record_ids == ("D11-C01-C3",)
    assert result.rows[0].observed_issue_codes == ("context_mismatch",)


def test_limit_marks_result_as_truncated(fixture, evaluation):
    result = query_causal_foundation_frontier(fixture, evaluation, CausalFoundationFrontierQuery(role="control", limit=2))
    assert result.total_matches == 12
    assert len(result.rows) == 2
    assert result.truncated
    assert result.accepted


def test_query_many_preserves_query_order(fixture, evaluation):
    queries = (CausalFoundationFrontierQuery(state="supported"), CausalFoundationFrontierQuery(state="partial"), CausalFoundationFrontierQuery(state="out_of_domain"))
    values = query_many_causal_foundation_frontier(fixture, evaluation, queries)
    assert [item.total_matches for item in values] == [4, 2, 5]
    assert [item.query.state for item in values] == ["supported", "partial", "out_of_domain"]


def test_query_serialization_is_addressable(fixture, evaluation):
    result = query_causal_foundation_frontier(fixture, evaluation, CausalFoundationFrontierQuery(issue_code="missing_prior_feature"))
    value = json.loads(json.dumps(result.to_dict(), default=str))
    assert value["total_matches"] == 2
    assert value["content_address"].startswith("sha256:")
    assert value["query"]["issue_code"] == "missing_prior_feature"


def test_invalid_query_limit_is_rejected():
    with pytest.raises(ValueError):
        CausalFoundationFrontierQuery(limit=0)


def test_plain_report_contains_release_controls():
    runtime = run_causal_foundation_frontier_runtime(run_id="report-plain")
    text = render_causal_foundation_frontier_report(runtime)
    assert "accepted: True" in text
    assert "positive_rows: 4" in text
    assert "control_rows: 12" in text
    assert "blocked_or_abstained: 10" in text
    assert "release_state: ready" in text
    assert "foreign contexts remain quarantined" in text


def test_markdown_report_contains_operation_table():
    runtime = run_causal_foundation_frontier_runtime(run_id="report-markdown")
    text = render_causal_foundation_frontier_report_markdown(runtime)
    assert text.startswith("# Causal foundation release report")
    assert "| Operation | Rows | Positive | Controls | State exact | Issue exact |" in text
    assert text.count("| typed_hypothesis_object |") == 1
    assert text.count("| measurement_likelihood |") == 1
    assert "## Limitations" in text


def test_report_operation_metrics_are_exact():
    runtime = run_causal_foundation_frontier_runtime(run_id="report-metrics")
    text = render_causal_foundation_frontier_report_markdown(runtime)
    for operation in ("typed_hypothesis_object", "factor_graph_constructor", "context_conditioned_prior", "measurement_likelihood"):
        assert f"| {operation} | 4 | 1 | 3 | 4 | 4 |" in text
