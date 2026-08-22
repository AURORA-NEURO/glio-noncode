"""Stable projections for tables and compact API responses."""

from __future__ import annotations

from typing import Any, Iterable


def project_link_graph_alpha_frontier_record(record: Any, fields: Iterable[str]) -> dict[str, Any]:
    payload = record.to_dict() if hasattr(record, "to_dict") else dict(record)
    return {field: payload.get(field) for field in fields}


def project_link_graph_alpha_frontier_evaluation_row(row: Any, fields: Iterable[str]) -> dict[str, Any]:
    payload = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    return {field: payload.get(field) for field in fields}


def project_link_graph_alpha_frontier_rows(rows: Iterable[Any], fields: Iterable[str]) -> tuple[dict[str, Any], ...]:
    selected = tuple(fields)
    return tuple(project_link_graph_alpha_frontier_evaluation_row(row, selected) for row in rows)


__all__ = ["project_link_graph_alpha_frontier_evaluation_row", "project_link_graph_alpha_frontier_record", "project_link_graph_alpha_frontier_rows"]
