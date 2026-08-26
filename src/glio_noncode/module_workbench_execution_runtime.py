"""Run, query, export, and verify the module execution handoff."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_contracts import ModuleWorkbenchReport
from .module_workbench_execution import (
    apply_module_workbench_execution_commands,
    build_module_workbench_execution,
)
from .module_workbench_execution_audit import audit_module_workbench_execution
from .module_workbench_execution_audit_contracts import ModuleWorkbenchExecutionAudit
from .module_workbench_execution_contracts import (
    ModuleWorkbenchExecutionCommand,
    ModuleWorkbenchExecutionLedger,
)
from .module_workbench_execution_policy import (
    default_module_workbench_execution_policy,
    evaluate_module_workbench_execution_policy,
)
from .module_workbench_execution_policy_contracts import (
    ModuleWorkbenchExecutionPolicy,
    ModuleWorkbenchExecutionPolicyGate,
)
from .module_workbench_execution_runtime_contracts import (
    MODULE_WORKBENCH_EXECUTION_RUNTIME_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_RUNTIME_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_RUNTIME_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_RUNTIME_VERSION,
    ModuleWorkbenchExecutionRuntime,
    ModuleWorkbenchExecutionRuntimeStage,
    ModuleWorkbenchExecutionRuntimeStageKind,
    ModuleWorkbenchExecutionRuntimeStageState,
    address_module_workbench_execution_runtime,
    address_module_workbench_execution_runtime_stage,
)
from .module_workbench_portfolio import build_module_workbench_portfolio
from .module_workbench_portfolio_contracts import ModuleWorkbenchPortfolio
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _stage(
    kind: ModuleWorkbenchExecutionRuntimeStageKind,
    accepted: bool,
    artifact_address: str,
    detail: str,
) -> ModuleWorkbenchExecutionRuntimeStage:
    body = {
        "kind": kind,
        "state": (
            ModuleWorkbenchExecutionRuntimeStageState.COMPLETED
            if accepted
            else ModuleWorkbenchExecutionRuntimeStageState.BLOCKED
        ),
        "accepted": accepted,
        "artifact_address": artifact_address,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionRuntimeStage(**body, content_address="pending")
    return ModuleWorkbenchExecutionRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_runtime_stage(provisional),
    )


def _runtime(
    report: ModuleWorkbenchReport,
    initial: ModuleWorkbenchExecutionLedger,
    current: ModuleWorkbenchExecutionLedger,
    policy: ModuleWorkbenchExecutionPolicy,
    gate: ModuleWorkbenchExecutionPolicyGate,
    audit: ModuleWorkbenchExecutionAudit,
    portfolio: ModuleWorkbenchPortfolio,
) -> ModuleWorkbenchExecutionRuntime:
    accepted = report.accepted and portfolio.accepted and audit.accepted and gate.accepted
    stages = (
        _stage(
            ModuleWorkbenchExecutionRuntimeStageKind.PORTFOLIO,
            portfolio.accepted,
            portfolio.content_address,
            f"selected {len(portfolio.selected_tasks)} bounded implementation tasks",
        ),
        _stage(
            ModuleWorkbenchExecutionRuntimeStageKind.PLAN,
            initial.accepted,
            initial.content_address,
            f"derived {initial.total_task_count} tasks and prerequisite edges",
        ),
        _stage(
            ModuleWorkbenchExecutionRuntimeStageKind.REPLAY,
            current.accepted,
            current.content_address,
            f"replayed {len(current.events)} ordered execution events",
        ),
        _stage(
            ModuleWorkbenchExecutionRuntimeStageKind.POLICY,
            gate.accepted,
            gate.content_address,
            f"evaluated execution policy {policy.policy_id}",
        ),
        _stage(
            ModuleWorkbenchExecutionRuntimeStageKind.AUDIT,
            audit.accepted,
            audit.content_address,
            f"ran {audit.check_count} independent execution checks",
        ),
        _stage(
            ModuleWorkbenchExecutionRuntimeStageKind.HANDOFF,
            accepted,
            current.content_address,
            "retained report, portfolio, ledger, policy, gate, and audit addresses",
        ),
    )
    body = {
        "report_address": report.content_address,
        "portfolio_address": portfolio.content_address,
        "initial_ledger_address": initial.content_address,
        "ledger_address": current.content_address,
        "policy_address": policy.content_address,
        "gate_address": gate.content_address,
        "audit_address": audit.content_address,
        "stages": stages,
        "accepted": accepted and all(item.accepted for item in stages),
    }
    provisional = ModuleWorkbenchExecutionRuntime(**body, content_address="pending")
    return ModuleWorkbenchExecutionRuntime(
        **body,
        content_address=address_module_workbench_execution_runtime(provisional),
    )


def run_module_workbench_execution(
    report: ModuleWorkbenchReport,
    portfolio: ModuleWorkbenchPortfolio | None = None,
    commands: Iterable[ModuleWorkbenchExecutionCommand] = (),
    policy: ModuleWorkbenchExecutionPolicy | None = None,
) -> ModuleWorkbenchExecutionRuntime:
    """Run portfolio selection, plan creation, command replay, policy, and audit."""

    if not isinstance(report, ModuleWorkbenchReport):
        raise ValidationError("execution runtime requires a typed workbench report")
    selected_portfolio = portfolio
    if selected_portfolio is None:
        selected_portfolio = build_module_workbench_portfolio(report)
    if not isinstance(selected_portfolio, ModuleWorkbenchPortfolio):
        raise ValidationError("execution runtime portfolio must be typed")
    initial = build_module_workbench_execution(report, selected_portfolio)
    current = apply_module_workbench_execution_commands(initial, commands)
    audit = audit_module_workbench_execution(current)
    selected_policy = policy or default_module_workbench_execution_policy()
    gate = evaluate_module_workbench_execution_policy(current, selected_policy, audit)
    return _runtime(report, initial, current, selected_policy, gate, audit, selected_portfolio)


def verify_module_workbench_execution_runtime(
    value: ModuleWorkbenchExecutionRuntime,
) -> ModuleWorkbenchExecutionRuntime:
    """Verify stage addresses and the aggregate runtime address."""

    if not isinstance(value, ModuleWorkbenchExecutionRuntime):
        raise ValidationError("execution runtime verification requires a typed runtime")
    for stage in value.stages:
        if address_module_workbench_execution_runtime_stage(stage) != stage.content_address:
            raise ValidationError(f"execution runtime stage address mismatch: {stage.kind.value}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-execution-runtime") != value.content_address:
        raise ValidationError("execution runtime address mismatch")
    return value


def query_module_workbench_execution_runtime(
    value: ModuleWorkbenchExecutionRuntime,
    *,
    resource: str = "stages",
    state: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_RUNTIME_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded stage or summary page."""

    if not isinstance(value, ModuleWorkbenchExecutionRuntime):
        raise ValidationError("execution runtime query requires a typed runtime")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_RUNTIME_MAX_LIMIT:
        raise ValidationError("execution runtime paging is invalid")
    if resource == "stages":
        rows = [item.to_dict() for item in value.stages]
    elif resource == "summary":
        rows = [value.to_dict(include_stages=False)]
    else:
        raise ValidationError("execution runtime resource must be stages or summary")
    if state:
        rows = [item for item in rows if item.get("state") == state]
    if accepted is not None:
        rows = [item for item in rows if item.get("accepted") is accepted]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "runtime_address": value.content_address,
        "query": {"resource": resource, "state": state, "accepted": accepted, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-execution-runtime-query")}


def module_workbench_execution_runtime_json(
    value: ModuleWorkbenchExecutionRuntime,
) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_runtime_csv(
    value: ModuleWorkbenchExecutionRuntime,
) -> str:
    output = io.StringIO(newline="")
    fields = ("kind", "state", "accepted", "artifact_address", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for stage in value.stages:
        writer.writerow(stage.to_dict())
    return output.getvalue()


def module_workbench_execution_runtime_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_EXECUTION_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_RUNTIME_BOUNDARY,
        "stage_order": [stage.value for stage in ModuleWorkbenchExecutionRuntimeStageKind],
        "stage_states": [state.value for state in ModuleWorkbenchExecutionRuntimeStageState],
        "resources": ["stages", "summary"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_runtime_capabilities() -> dict[str, Any]:
    operations = (
        "select_portfolio",
        "build_execution_plan",
        "replay_commands",
        "evaluate_policy",
        "audit_ledger",
        "retain_handoff_addresses",
        "query_stages",
        "summarize_runtime",
        "export_json",
        "export_csv",
        "verify_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_RUNTIME_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "ordered_stages": True,
    }


__all__ = [
    "module_workbench_execution_runtime_capabilities",
    "module_workbench_execution_runtime_csv",
    "module_workbench_execution_runtime_json",
    "module_workbench_execution_runtime_schema",
    "query_module_workbench_execution_runtime",
    "run_module_workbench_execution",
    "verify_module_workbench_execution_runtime",
]
