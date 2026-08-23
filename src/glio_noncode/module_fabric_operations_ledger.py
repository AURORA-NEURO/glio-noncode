"""Operational ledger and conservative recovery queue for module-fabric runs.

The ledger is deliberately narrower than the runtime report.  It preserves the
ordered execution surface, counters, state transitions, and content addresses
needed for an operator to reconcile a run without copying fixture payloads into
an operational record.  Recovery is also intentionally non-promotional: a
control row can be routed for review, but no recovery step can silently turn it
into an accepted result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability_registry import CapabilityRegistry
from .module_fabric_contracts import (
    FabricFixture,
    FabricRuntimeReport,
    FabricState,
)
from .module_fabric_public_data import default_module_fabric_fixture
from .module_fabric_runtime import ModuleFabricRuntimeOptions, run_module_fabric_runtime
from .serialization import content_hash, jsonable, require_non_empty


LEDGER_VERSION = "2026.08.module-fabric.ledger.v1"
RECOVERY_VERSION = "2026.08.module-fabric.recovery.v1"
LEDGER_BOUNDARY = "public_aggregate_operational_reconciliation"
RECOVERY_BOUNDARY = "public_aggregate_manual_review_routing"


@dataclass(frozen=True, slots=True)
class FabricLedgerEntry:
    """One sanitized, ordered operation receipt."""

    operation_id: str
    stage_id: str
    ordinal: int
    state: FabricState
    accepted_records: int
    review_records: int
    record_count: int
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "operation_id",
            "stage_id",
            "input_address",
            "output_address",
            "detail",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.ordinal < 1:
            raise ValueError("ledger ordinals must be positive")
        if min(self.accepted_records, self.review_records, self.record_count) < 0:
            raise ValueError("ledger counts cannot be negative")
        if ":" not in self.input_address or ":" not in self.output_address:
            raise ValueError("ledger stage addresses require an address prefix")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricOperationLedger:
    """Addressed operation sequence for one module-fabric runtime."""

    ledger_id: str
    version: str
    boundary: str
    run_id: str
    fixture_id: str
    entries: tuple[FabricLedgerEntry, ...]
    final_state: FabricState
    accepted_records: int
    review_records: int
    record_count: int
    content_address: str

    def __post_init__(self) -> None:
        for name in ("ledger_id", "version", "boundary", "run_id", "fixture_id", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != LEDGER_VERSION:
            raise ValueError("unsupported module-fabric ledger version")
        if self.boundary != LEDGER_BOUNDARY:
            raise ValueError("module-fabric ledger boundary is closed")
        if not self.entries:
            raise ValueError("module-fabric ledger requires operation entries")
        if self.record_count < 1:
            raise ValueError("module-fabric ledger requires records")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricLedgerCheck:
    """A named invariant retained in the ledger audit."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricLedgerAudit:
    """Reconciliation result for one operation ledger."""

    ledger_id: str
    checks: tuple[FabricLedgerCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def __post_init__(self) -> None:
        if self.passed_checks + self.failed_checks != len(self.checks):
            raise ValueError("ledger audit counts must conserve checks")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricRecoveryItem:
    """Manual review instruction for one held control row."""

    item_id: str
    record_id: str
    domain_id: str
    capability_id: str
    current_state: FabricState
    action: str
    required_evidence: tuple[str, ...]
    automatic_promotion: bool
    priority: int
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "item_id",
            "record_id",
            "domain_id",
            "capability_id",
            "action",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.current_state is FabricState.ACCEPTED:
            raise ValueError("accepted rows do not belong in recovery")
        if self.automatic_promotion:
            raise ValueError("recovery cannot automatically promote a held row")
        if not self.required_evidence or self.priority < 1:
            raise ValueError("recovery items require evidence and priority")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricRecoveryReport:
    """Conservative, addressed queue for unresolved or control rows."""

    recovery_id: str
    version: str
    boundary: str
    run_id: str
    items: tuple[FabricRecoveryItem, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("recovery_id", "version", "boundary", "run_id", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != RECOVERY_VERSION:
            raise ValueError("unsupported module-fabric recovery version")
        if self.boundary != RECOVERY_BOUNDARY:
            raise ValueError("module-fabric recovery boundary is closed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> FabricLedgerCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricLedgerCheck(**body, content_address=content_hash(body, prefix="module-fabric-ledger-check"))


def _runtime_for(
    fixture: FabricFixture | None,
    registry: CapabilityRegistry | None,
    run_id: str,
) -> FabricRuntimeReport:
    return run_module_fabric_runtime(
        fixture,
        registry,
        options=ModuleFabricRuntimeOptions(run_id=run_id),
    )


def build_module_fabric_operation_ledger(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
    *,
    run_id: str = "module-fabric-ledger",
) -> FabricOperationLedger:
    """Build a sanitized ordered ledger from the accepted runtime surface."""

    run = _runtime_for(fixture or default_module_fabric_fixture(registry), registry, run_id)
    require_non_empty(run_id, "run_id")
    entries: list[FabricLedgerEntry] = []
    for stage in run.stages:
        body = {
            "operation_id": f"MFO-{stage.ordinal:02d}-{stage.stage_id}",
            "stage_id": stage.stage_id,
            "ordinal": stage.ordinal,
            "state": stage.state,
            "accepted_records": run.metrics.accepted_count,
            "review_records": run.metrics.review_count,
            "record_count": run.metrics.record_count,
            "input_address": stage.input_address,
            "output_address": stage.output_address,
            "detail": stage.detail,
        }
        entries.append(FabricLedgerEntry(**body, content_address=content_hash(body, prefix="module-fabric-ledger-entry")))
    body = {
        "ledger_id": f"{run_id}:{run.run_id}",
        "version": LEDGER_VERSION,
        "boundary": LEDGER_BOUNDARY,
        "run_id": run_id,
        "fixture_id": run.evaluation.fixture_id,
        "entries": tuple(entries),
        "final_state": run.state,
        "accepted_records": run.metrics.accepted_count,
        "review_records": run.metrics.review_count,
        "record_count": run.metrics.record_count,
    }
    return FabricOperationLedger(
        **body,
        content_address=content_hash(body, prefix="module-fabric-ledger"),
    )


def audit_module_fabric_operation_ledger(
    ledger: FabricOperationLedger,
    runtime: FabricRuntimeReport | None = None,
) -> FabricLedgerAudit:
    """Verify ordering, conservation, addressing, and held-control behavior."""

    values = ledger.entries
    checks = (
        _check("entries-present", bool(values), len(values), 20, "runtime entries are retained"),
        _check("ordinals-contiguous", tuple(item.ordinal for item in values) == tuple(range(1, len(values) + 1)), tuple(item.ordinal for item in values), "1..N", "operation order is contiguous"),
        _check("operation-ids-unique", len({item.operation_id for item in values}) == len(values), len({item.operation_id for item in values}), len(values), "operation identifiers are unique"),
        _check("stage-ids-unique", len({item.stage_id for item in values}) == len(values), len({item.stage_id for item in values}), len(values), "stage identifiers are unique"),
        _check("entry-addresses-present", all(":" in item.content_address for item in values), sum(":" in item.content_address for item in values), len(values), "every entry is addressed"),
        _check("stage-input-addresses", all(":" in item.input_address for item in values), sum(":" in item.input_address for item in values), len(values), "stage inputs are addressed"),
        _check("stage-output-addresses", all(":" in item.output_address for item in values), sum(":" in item.output_address for item in values), len(values), "stage outputs are addressed"),
        _check("record-count-conserved", all(item.record_count == ledger.record_count for item in values), tuple(sorted({item.record_count for item in values})), ledger.record_count, "each stage carries the same record denominator"),
        _check("state-finalized", values[-1].state is ledger.final_state, values[-1].state, ledger.final_state, "final ledger entry matches final state"),
        _check("release-boundary-retained", any(item.stage_id == "release-decision" for item in values), tuple(item.stage_id for item in values), "release-decision", "release decision is retained"),
    )
    if runtime is not None:
        checks += (
            _check("runtime-address-matches", ledger.fixture_id == runtime.evaluation.fixture_id, ledger.fixture_id, runtime.evaluation.fixture_id, "ledger and runtime share fixture identity"),
            _check("runtime-state-matches", ledger.final_state is runtime.state, ledger.final_state, runtime.state, "ledger and runtime share final state"),
            _check("runtime-count-matches", ledger.record_count == runtime.metrics.record_count, ledger.record_count, runtime.metrics.record_count, "ledger and runtime conserve records"),
            _check("controls-remain-held", all(item.observed_state is not FabricState.ACCEPTED for item in runtime.evaluation.executions if item.role.value == "control"), tuple(item.observed_state.value for item in runtime.evaluation.executions if item.role.value == "control"), "no accepted controls", "control rows remain held"),
        )
    passed = sum(item.passed for item in checks)
    failed = len(checks) - passed
    body = {"ledger_id": ledger.ledger_id, "checks": checks, "accepted": failed == 0, "passed_checks": passed, "failed_checks": failed}
    return FabricLedgerAudit(ledger.ledger_id, checks, failed == 0, passed, failed, content_hash(body, prefix="module-fabric-ledger-audit"))


def build_module_fabric_recovery_report(
    fixture: FabricFixture | None = None,
    runtime: FabricRuntimeReport | None = None,
    *,
    run_id: str = "module-fabric-recovery",
) -> FabricRecoveryReport:
    """Route held controls into explicit manual review without promotion."""

    value = fixture or default_module_fabric_fixture()
    report = runtime or run_module_fabric_runtime(value)
    controls = tuple(item for item in report.evaluation.executions if item.role.value == "control")
    items: list[FabricRecoveryItem] = []
    for index, execution in enumerate(controls, start=1):
        body = {
            "item_id": f"MFR-{index:03d}",
            "record_id": execution.record_id,
            "domain_id": execution.domain_id,
            "capability_id": execution.capability_id,
            "current_state": execution.observed_state,
            "action": "review_context_domain_and_source_boundary",
            "required_evidence": ("context_key", "declared_domain_id", "public_source_scope"),
            "automatic_promotion": False,
            "priority": 1,
        }
        items.append(FabricRecoveryItem(**body, content_address=content_hash(body, prefix="module-fabric-recovery-item")))
    body = {
        "recovery_id": f"{run_id}:{report.run_id}",
        "version": RECOVERY_VERSION,
        "boundary": RECOVERY_BOUNDARY,
        "run_id": run_id,
        "items": items,
        "accepted": all(item.current_state is not FabricState.ACCEPTED and not item.automatic_promotion for item in items),
    }
    return FabricRecoveryReport(**body, content_address=content_hash(body, prefix="module-fabric-recovery"))


def module_fabric_operation_ledger_json(ledger: FabricOperationLedger) -> str:
    """Render an addressed ledger without raw fixture payloads."""

    import json

    return json.dumps(ledger.to_dict(), indent=2, sort_keys=True) + "\n"


def module_fabric_recovery_json(report: FabricRecoveryReport) -> str:
    """Render a review-only recovery queue."""

    import json

    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


__all__ = [
    "FabricLedgerEntry",
    "FabricOperationLedger",
    "FabricLedgerCheck",
    "FabricLedgerAudit",
    "FabricRecoveryItem",
    "FabricRecoveryReport",
    "LEDGER_VERSION",
    "RECOVERY_VERSION",
    "LEDGER_BOUNDARY",
    "RECOVERY_BOUNDARY",
    "build_module_fabric_operation_ledger",
    "audit_module_fabric_operation_ledger",
    "build_module_fabric_recovery_report",
    "module_fabric_operation_ledger_json",
    "module_fabric_recovery_json",
]
