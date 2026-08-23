"""Replay and determinism checks for the D01 evaluation surface."""

from __future__ import annotations

from .intake_architecture_contracts import IntakeArchitectureEvaluation, addressed
from .intake_architecture_operations import evaluate_intake_architecture_fixture
from .intake_architecture_public_data import default_intake_architecture_fixture


def replay_intake_architecture(fixture=None) -> dict[str, object]:
    value = fixture or default_intake_architecture_fixture()
    first = evaluate_intake_architecture_fixture(value)
    second = evaluate_intake_architecture_fixture(value)
    equal = first.content_address == second.content_address and first.to_dict() == second.to_dict()
    body = {"fixture_id": value.fixture_id, "first_address": first.content_address, "second_address": second.content_address, "deterministic": equal, "accepted": equal}
    return body | {"content_address": addressed(body, "intake-replay")}


__all__ = ["replay_intake_architecture"]
