"""Composite deep audit for D14 architecture closure."""

from __future__ import annotations

from typing import Any

from .evidence_architecture_compliance import assess_evidence_architecture_compliance
from .evidence_architecture_contract_matrix import evidence_architecture_contract_matrix_summary
from .evidence_architecture_contracts import EvidenceArchitectureFixture, addressed
from .evidence_architecture_controls import evidence_architecture_control_summary
from .evidence_architecture_lineage import evidence_architecture_lineage_summary
from .evidence_architecture_metrics import evidence_architecture_metrics
from .evidence_architecture_public_data import (
    audit_evidence_architecture_data,
    default_evidence_architecture_fixture,
)
from .evidence_architecture_schema import (
    evidence_architecture_schema_descriptor,
    validate_evidence_architecture_fixture,
    validate_evidence_architecture_mapping,
)


def deep_audit_evidence_architecture(
    fixture: EvidenceArchitectureFixture | None = None,
) -> dict[str, Any]:
    selected = fixture or default_evidence_architecture_fixture()
    data_audit = audit_evidence_architecture_data(selected)
    compliance = assess_evidence_architecture_compliance(selected)
    schema_errors = validate_evidence_architecture_mapping(selected.to_dict())
    validate_evidence_architecture_fixture(selected)
    body = {
        "fixture_id": selected.fixture_id,
        "data_audit": data_audit.to_dict(),
        "compliance": compliance.to_dict(),
        "schema": evidence_architecture_schema_descriptor(),
        "schema_errors": schema_errors,
        "lineage": evidence_architecture_lineage_summary(selected),
        "controls": evidence_architecture_control_summary(selected),
        "contract_matrix": evidence_architecture_contract_matrix_summary(selected),
        "metrics": evidence_architecture_metrics(selected),
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
        "content_address": addressed(
            body | {"accepted": accepted}, "evidence-architecture-deep-audit"
        ),
    }


def evidence_architecture_audit_summary(audit: dict[str, Any]) -> dict[str, object]:
    return {
        "fixture_id": audit["fixture_id"],
        "accepted": audit["accepted"],
        "schema_error_count": len(audit["schema_errors"]),
        "lineage_gap_count": audit["lineage"]["gap_count"],
        "compliance_accepted": audit["compliance"]["accepted"],
        "content_address": audit["content_address"],
    }


__all__ = ["deep_audit_evidence_architecture", "evidence_architecture_audit_summary"]
