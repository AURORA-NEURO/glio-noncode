"""Composite deep audit for D13 architecture closure."""

from __future__ import annotations

from typing import Any

from .planning_architecture_compliance import assess_planning_architecture_compliance
from .planning_architecture_contract_matrix import planning_architecture_contract_matrix_summary
from .planning_architecture_contracts import PlanningArchitectureFixture, addressed
from .planning_architecture_controls import planning_architecture_control_summary
from .planning_architecture_lineage import planning_architecture_lineage_summary
from .planning_architecture_metrics import planning_architecture_metrics
from .planning_architecture_public_data import (
    audit_planning_architecture_data,
    default_planning_architecture_fixture,
)
from .planning_architecture_schema import (
    planning_architecture_schema_descriptor,
    validate_planning_architecture_fixture,
    validate_planning_architecture_mapping,
)


def deep_audit_planning_architecture(
    fixture: PlanningArchitectureFixture | None = None,
) -> dict[str, Any]:
    selected = fixture or default_planning_architecture_fixture()
    data_audit = audit_planning_architecture_data(selected)
    compliance = assess_planning_architecture_compliance(selected)
    schema_errors = validate_planning_architecture_mapping(selected.to_dict())
    validate_planning_architecture_fixture(selected)
    body = {
        "fixture_id": selected.fixture_id,
        "data_audit": data_audit.to_dict(),
        "compliance": compliance.to_dict(),
        "schema": planning_architecture_schema_descriptor(),
        "schema_errors": schema_errors,
        "lineage": planning_architecture_lineage_summary(selected),
        "controls": planning_architecture_control_summary(selected),
        "contract_matrix": planning_architecture_contract_matrix_summary(selected),
        "metrics": planning_architecture_metrics(selected),
    }
    accepted = (
        data_audit.accepted
        and compliance.accepted
        and not schema_errors
        and body["lineage"]["gap_count"] == 0
        and body["controls"]["balanced"]
    )
    return body | {
        "accepted": accepted,
        "content_address": addressed(body | {"accepted": accepted}, "planning-deep-audit"),
    }


def planning_architecture_audit_summary(
    audit: dict[str, Any],
) -> dict[str, object]:
    return {
        "fixture_id": audit["fixture_id"],
        "accepted": audit["accepted"],
        "schema_error_count": len(audit["schema_errors"]),
        "lineage_gap_count": audit["lineage"]["gap_count"],
        "compliance_accepted": audit["compliance"]["accepted"],
        "content_address": audit["content_address"],
    }


__all__ = ["deep_audit_planning_architecture", "planning_architecture_audit_summary"]
