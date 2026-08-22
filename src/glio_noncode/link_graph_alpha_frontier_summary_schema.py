"""Schema for the compact summary returned by the frontier CLI.

The fields keep the command response stable for local review and Actions.
"""

from __future__ import annotations

from typing import Any


LINK_GRAPH_ALPHA_FRONTIER_SUMMARY_FIELDS = (
    "fixture_id",
    "record_count",
    "source_count",
    "accepted",
    "state_accuracy",
    "issue_accuracy",
    "state_counts",
)


def validate_link_graph_alpha_frontier_summary(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if set(LINK_GRAPH_ALPHA_FRONTIER_SUMMARY_FIELDS) - set(value):
        return False
    return value["record_count"] == 16 and value["source_count"] == 5 and value["accepted"] is True


def project_link_graph_alpha_frontier_summary(value: dict[str, Any]) -> dict[str, Any]:
    return {field: value.get(field) for field in LINK_GRAPH_ALPHA_FRONTIER_SUMMARY_FIELDS}


def link_graph_alpha_frontier_summary_schema() -> dict[str, Any]:
    return {"fields": list(LINK_GRAPH_ALPHA_FRONTIER_SUMMARY_FIELDS), "required_count": len(LINK_GRAPH_ALPHA_FRONTIER_SUMMARY_FIELDS), "record_count": 16, "source_count": 5}


__all__ = ["LINK_GRAPH_ALPHA_FRONTIER_SUMMARY_FIELDS", "link_graph_alpha_frontier_summary_schema", "project_link_graph_alpha_frontier_summary", "validate_link_graph_alpha_frontier_summary"]
