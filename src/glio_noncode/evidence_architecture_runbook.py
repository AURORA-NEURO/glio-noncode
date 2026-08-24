"""Operational runbook and deterministic checks for D14."""

from __future__ import annotations

from .evidence_architecture_contracts import EvidenceArchitectureFixture
from .evidence_architecture_public_data import default_evidence_architecture_fixture


def evidence_architecture_runbook(
    fixture: EvidenceArchitectureFixture | None = None,
) -> tuple[dict[str, object], ...]:
    selected = fixture or default_evidence_architecture_fixture()
    return (
        {
            "step": 1,
            "name": "load",
            "action": "load the checked-in public aggregate fixture",
            "fixture_id": selected.fixture_id,
        },
        {
            "step": 2,
            "name": "audit",
            "action": "audit source, operation, case, context, and address joins",
        },
        {
            "step": 3,
            "name": "plan",
            "action": "compile the sixteen dependency-safe operation nodes",
        },
        {
            "step": 4,
            "name": "execute",
            "action": "evaluate all positive and control delegate cases",
        },
        {"step": 5, "name": "route", "action": "route held states and controls to review"},
        {
            "step": 6,
            "name": "release",
            "action": "publish only after quality, replay, and boundary checks close",
        },
    )


def evidence_architecture_runbook_summary(
    fixture: EvidenceArchitectureFixture | None = None,
) -> dict[str, object]:
    selected = fixture or default_evidence_architecture_fixture()
    steps = evidence_architecture_runbook(selected)
    return {
        "fixture_id": selected.fixture_id,
        "step_count": len(steps),
        "step_names": [item["name"] for item in steps],
    }


__all__ = ["evidence_architecture_runbook", "evidence_architecture_runbook_summary"]
