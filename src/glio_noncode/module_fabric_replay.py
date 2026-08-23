"""Deterministic replay checks for the module-fabric evaluation."""

from __future__ import annotations

from .capability_registry import CapabilityRegistry, default_capability_registry
from .module_fabric_contracts import FabricFixture, FabricReplayReport, make_replay_check
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_public_data import default_module_fabric_fixture
from .serialization import content_hash


def replay_module_fabric(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
) -> FabricReplayReport:
    value = fixture or default_module_fabric_fixture(registry)
    first = evaluate_module_fabric_fixture(value, registry)
    second = evaluate_module_fabric_fixture(value, registry)
    checks = (
        make_replay_check("fixture_id", first.fixture_id == value.fixture_id, first.fixture_id, value.fixture_id, "fixture identity is retained"),
        make_replay_check("evaluation_address", first.content_address == second.content_address, first.content_address, second.content_address, "same inputs produce the same evaluation address"),
        make_replay_check("execution_count", len(first.executions) == len(value.records), len(first.executions), len(value.records), "every record replays once"),
        make_replay_check("check_count", len(first.checks) == len(second.checks), len(first.checks), len(second.checks), "replay preserves check cardinality"),
        make_replay_check("accepted_state", first.accepted == second.accepted, first.accepted, second.accepted, "replay preserves acceptance"),
        make_replay_check("execution_addresses", tuple(item.content_address for item in first.executions) == tuple(item.content_address for item in second.executions), True, True, "execution receipts are deterministic"),
        make_replay_check("reference_addresses", tuple(receipt.content_address for item in first.executions for receipt in (*item.implementation_receipts, *item.test_receipts)) == tuple(receipt.content_address for item in second.executions for receipt in (*item.implementation_receipts, *item.test_receipts)), True, True, "reference receipts are deterministic"),
        make_replay_check("control_visibility", sum(item.role.value == "control" for item in first.executions) == len(value.control_records), sum(item.role.value == "control" for item in first.executions), len(value.control_records), "controls remain visible during replay"),
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": accepted}
    return FabricReplayReport(value.fixture_id, tuple(checks), accepted, content_hash(body, prefix="module-fabric-replay"))


__all__ = ["replay_module_fabric"]
