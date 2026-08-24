"""Control-case projections and balance checks for D14."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .evidence_architecture_contracts import (
    EvidenceArchitectureFixture,
    EvidenceArchitectureScenario,
    addressed,
)
from .evidence_architecture_public_data import default_evidence_architecture_fixture


def evidence_architecture_control_rows(
    fixture: EvidenceArchitectureFixture | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = fixture or default_evidence_architecture_fixture()
    rows = []
    for case in selected.control_cases:
        body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "family": case.family,
            "plane": case.plane,
            "scenario": case.scenario,
            "expected_state": case.expected_state,
            "expected_issue_codes": case.expected_issue_codes,
            "delegate_context_key": case.delegate_context_key,
            "description": case.description,
        }
        rows.append(body | {"content_address": addressed(body, "evidence-architecture-control")})
    return tuple(rows)


def evidence_architecture_control_summary(
    fixture: EvidenceArchitectureFixture | None = None,
) -> dict[str, object]:
    selected = fixture or default_evidence_architecture_fixture()
    counts = Counter(item.scenario.value for item in selected.cases)
    states = Counter(item.expected_state.value for item in selected.control_cases)
    return {
        "fixture_id": selected.fixture_id,
        "positive_count": counts[EvidenceArchitectureScenario.POSITIVE.value],
        "control_count": len(selected.control_cases),
        "scenario_counts": dict(sorted(counts.items())),
        "control_state_counts": dict(sorted(states.items())),
        "balanced": counts == Counter({item.value: 16 for item in EvidenceArchitectureScenario}),
        "control_address_count": len(evidence_architecture_control_rows(selected)),
    }


__all__ = ["evidence_architecture_control_rows", "evidence_architecture_control_summary"]
