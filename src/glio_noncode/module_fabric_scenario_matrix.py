"""Positive/control scenario matrix for all sixteen module domains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_contracts import FabricEvaluation, FabricFixture, FabricState
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_public_data import default_module_fabric_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FabricScenarioCell:
    scenario_id: str
    domain_id: str
    capability_id: str
    role: str
    expected_state: FabricState
    observed_state: FabricState
    passed: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricScenarioMatrix:
    fixture_id: str
    cells: tuple[FabricScenarioCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_module_fabric_scenarios(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
) -> FabricScenarioMatrix:
    value = fixture or default_module_fabric_fixture()
    report = evaluation or evaluate_module_fabric_fixture(value)
    cells = []
    for record, execution in zip(value.records, report.executions, strict=True):
        body = {
            "scenario_id": record.record_id,
            "domain_id": record.domain_id,
            "capability_id": record.capability_id,
            "role": record.role.value,
            "expected_state": record.expected_state,
            "observed_state": execution.observed_state,
            "passed": execution.observed_state is record.expected_state,
            "issue_codes": execution.issue_codes,
        }
        cells.append(FabricScenarioCell(**body, content_address=content_hash(body, prefix="module-fabric-scenario")))
    accepted = all(item.passed for item in cells)
    body = {"fixture_id": value.fixture_id, "cells": cells, "accepted": accepted}
    return FabricScenarioMatrix(value.fixture_id, tuple(cells), accepted, content_hash(body, prefix="module-fabric-scenario-matrix"))


__all__ = ["FabricScenarioCell", "FabricScenarioMatrix", "evaluate_module_fabric_scenarios"]
