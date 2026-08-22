"""Diff cells for stable beta review projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .link_graph_beta_frontier_field_projection import project_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierProjectionDiffCell:
    record_id: str
    field: str
    left: Any
    right: Any
    equal: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierProjectionDiff:
    left_address: str
    right_address: str
    cells: tuple[LinkGraphBetaFrontierProjectionDiffCell, ...]
    equal: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def changed_record_ids(self) -> tuple[str, ...]:
        return tuple(sorted({item.record_id for item in self.cells if not item.equal}))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"left_address": self.left_address, "right_address": self.right_address, "cells": [item.to_dict() for item in self.cells], "changed_record_ids": self.changed_record_ids, "equal": self.equal}
        if include_address:
            value["content_address"] = self.content_address
        return value


def compare_link_graph_beta_frontier_projections(left: Mapping[str, Any], right: Mapping[str, Any], *, left_address: str = "", right_address: str = "") -> LinkGraphBetaFrontierProjectionDiff:
    left_rows = {str(row["record_id"]): row for row in left.get("rows", ())}
    right_rows = {str(row["record_id"]): row for row in right.get("rows", ())}
    cells = []
    for record_id in sorted(set(left_rows) | set(right_rows)):
        for field in sorted(set(left_rows.get(record_id, {})) | set(right_rows.get(record_id, {}))):
            left_value = left_rows.get(record_id, {}).get(field)
            right_value = right_rows.get(record_id, {}).get(field)
            cells.append(LinkGraphBetaFrontierProjectionDiffCell(record_id, field, left_value, right_value, left_value == right_value))
    values = tuple(cells)
    return LinkGraphBetaFrontierProjectionDiff(left_address, right_address, values, all(item.equal for item in values))


def compare_link_graph_beta_frontier_fixture_to_self(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierProjectionDiff:
    value = fixture or default_link_graph_beta_frontier_fixture()
    projection = project_link_graph_beta_frontier_fixture(value).to_dict()
    return compare_link_graph_beta_frontier_projections(projection, projection, left_address=value.content_address, right_address=value.content_address)


__all__ = ["LinkGraphBetaFrontierProjectionDiff", "LinkGraphBetaFrontierProjectionDiffCell", "compare_link_graph_beta_frontier_fixture_to_self", "compare_link_graph_beta_frontier_projections"]
