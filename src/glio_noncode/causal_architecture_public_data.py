"""Public D11 aggregate built from foundation, beta, alpha, and frontier data."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from .causal_alpha_frontier_public_data import default_causal_alpha_frontier_fixture
from .causal_architecture_contracts import (
    CAUSAL_ARCHITECTURE_BOUNDARY,
    CAUSAL_ARCHITECTURE_CONTEXT,
    CAUSAL_ARCHITECTURE_FOREIGN_CONTEXT,
    CAUSAL_ARCHITECTURE_VERSION,
    CausalArchitectureCase,
    CausalArchitectureCheck,
    CausalArchitectureCheckKind,
    CausalArchitectureDataAudit,
    CausalArchitectureFamily,
    CausalArchitectureFixture,
    CausalArchitectureOperation,
    CausalArchitectureOperationSpec,
    CausalArchitecturePlane,
    CausalArchitectureScenario,
    CausalArchitectureSource,
    CausalArchitectureState,
    addressed,
)
from .causal_beta_frontier_fixture_eval import evaluate_causal_beta_frontier_fixture
from .causal_beta_frontier_public_data import default_causal_beta_frontier_fixture
from .causal_foundation_frontier_fixture_eval import evaluate_causal_foundation_frontier_fixture
from .causal_foundation_frontier_public_data import default_causal_foundation_frontier_fixture
from .causal_frontier_fixture_eval import evaluate_causal_frontier_fixture
from .causal_frontier_public_data import default_causal_frontier_fixture
from .serialization import jsonable

_FAMILIES = (
    CausalArchitectureFamily.FOUNDATION,
    CausalArchitectureFamily.BETA,
    CausalArchitectureFamily.ALPHA,
    CausalArchitectureFamily.FRONTIER,
)
_PREFIXES = {
    CausalArchitectureFamily.FOUNDATION: "foundation",
    CausalArchitectureFamily.BETA: "beta",
    CausalArchitectureFamily.ALPHA: "alpha",
    CausalArchitectureFamily.FRONTIER: "frontier",
}
_PLANES = {
    CausalArchitectureFamily.FOUNDATION: CausalArchitecturePlane.FOUNDATION,
    CausalArchitectureFamily.BETA: CausalArchitecturePlane.BETA,
    CausalArchitectureFamily.ALPHA: CausalArchitecturePlane.ALPHA,
    CausalArchitectureFamily.FRONTIER: CausalArchitecturePlane.FRONTIER,
}
_OPERATIONS = tuple(CausalArchitectureOperation)


def _family_fixture_map() -> dict[CausalArchitectureFamily, Any]:
    return {
        CausalArchitectureFamily.FOUNDATION: default_causal_foundation_frontier_fixture(),
        CausalArchitectureFamily.BETA: default_causal_beta_frontier_fixture(),
        CausalArchitectureFamily.ALPHA: default_causal_alpha_frontier_fixture(),
        CausalArchitectureFamily.FRONTIER: default_causal_frontier_fixture(),
    }


def _family_evaluation_map(
    fixtures: Mapping[CausalArchitectureFamily, Any],
) -> dict[CausalArchitectureFamily, Any]:
    return {
        CausalArchitectureFamily.FOUNDATION: evaluate_causal_foundation_frontier_fixture(
            fixtures[CausalArchitectureFamily.FOUNDATION]
        ),
        CausalArchitectureFamily.BETA: evaluate_causal_beta_frontier_fixture(
            fixtures[CausalArchitectureFamily.BETA]
        ),
        CausalArchitectureFamily.ALPHA: evaluate_causal_alpha_frontier_fixture_deep(
            fixtures[CausalArchitectureFamily.ALPHA]
        ),
        CausalArchitectureFamily.FRONTIER: evaluate_causal_frontier_fixture(
            fixtures[CausalArchitectureFamily.FRONTIER]
        ),
    }


def _rows(
    family: CausalArchitectureFamily, fixture: Any, evaluation: Any
) -> tuple[dict[str, Any], ...]:
    records = {str(item.record_id): item for item in fixture.records}
    if family is CausalArchitectureFamily.FRONTIER:
        return tuple(
            {
                "record": records[record_id],
                "operation": execution.operation.value,
                "role": records[record_id].role.value,
                "state": execution.state,
                "issue_codes": tuple(execution.issue_codes),
                "output": execution.output,
                "output_address": execution.content_address,
            }
            for record_id, execution in evaluation.execution_map().items()
        )
    if family is CausalArchitectureFamily.ALPHA:
        results = evaluation.evaluation.results
        return tuple(
            {
                "record": records[row.record_id],
                "operation": row.operation.value,
                "role": records[row.record_id].role.value,
                "state": row.observed_state.value,
                "issue_codes": tuple(row.observed_issue_codes),
                "output": row.output,
                "output_address": row.content_address,
            }
            for row in results
        )
    return tuple(
        {
            "record": records[row.record_id],
            "operation": row.operation.value
            if hasattr(row.operation, "value")
            else str(row.operation),
            "role": row.role.value if hasattr(row.role, "value") else str(row.role),
            "state": row.observed_state.value
            if hasattr(row.observed_state, "value")
            else str(row.observed_state),
            "issue_codes": tuple(row.observed_issue_codes),
            "output": row.adapter.to_dict(),
            "output_address": addressed(row.adapter.to_dict(), "causal-delegate-output"),
        }
        for row in evaluation.rows
    )


def _source_records(
    fixtures: Mapping[CausalArchitectureFamily, Any],
) -> tuple[CausalArchitectureSource, ...]:
    sources = []
    for family in _FAMILIES:
        prefix = _PREFIXES[family]
        for source in fixtures[family].sources:
            raw = source.to_dict()
            body = {
                "source_id": f"D11-{prefix}-{source.source_id}",
                "family": family,
                "source_kind": str(raw.get("source_kind", "causal_public_aggregate")),
                "source_version": str(
                    raw.get("source_version", raw.get("release", raw.get("version", "pinned")))
                ),
                "uri": str(raw.get("uri", "https://data.example.org/causal/aggregate")),
                "context_key": str(raw.get("context_key", CAUSAL_ARCHITECTURE_CONTEXT)),
                "public_aggregate": True,
                "delegate_source_id": str(source.source_id),
            }
            sources.append(
                CausalArchitectureSource(**body, content_address=addressed(body, "causal-source"))
            )
    return tuple(sources)


def _operations(
    sources: tuple[CausalArchitectureSource, ...],
) -> tuple[CausalArchitectureOperationSpec, ...]:
    operations = []
    for ordinal, operation in enumerate(_OPERATIONS, start=1):
        family = _FAMILIES[(ordinal - 1) // 4]
        body = {
            "operation_id": f"D11-C{ordinal:02d}",
            "capability_id": f"GNC-D11-C{ordinal:02d}",
            "ordinal": ordinal,
            "operation": operation,
            "family": family,
            "plane": _PLANES[family],
            "input_contract": f"causal.{operation.value}.public_record.v1",
            "output_contract": f"causal.{operation.value}.receipt.v1",
            "dependencies": (f"D11-C{ordinal - 1:02d}",) if ordinal > 1 else (),
            "source_ids": tuple(item.source_id for item in sources if item.family is family),
            "control_policy": (
                "retain causal evidence as a bounded research proxy with exact context, "
                "source lineage, and explicit review states"
            ),
        }
        operations.append(
            CausalArchitectureOperationSpec(
                **body, content_address=addressed(body, "causal-operation")
            )
        )
    return tuple(operations)


def _cases(
    fixtures: Mapping[CausalArchitectureFamily, Any],
    evaluations: Mapping[CausalArchitectureFamily, Any],
    operations: tuple[CausalArchitectureOperationSpec, ...],
) -> tuple[CausalArchitectureCase, ...]:
    cases = []
    scenarios = tuple(CausalArchitectureScenario)
    for operation in operations:
        family = operation.family
        rows = tuple(
            row
            for row in _rows(family, fixtures[family], evaluations[family])
            if row["operation"] == _OPERATIONS[operation.ordinal - 1].value
        )
        if len(rows) != 4:
            raise ValueError(f"D11 delegate balance failed for {operation.operation_id}")
        for index, row in enumerate(rows):
            record = row["record"]
            scenario = scenarios[index]
            body = {
                "case_id": f"{operation.operation_id}-{scenario.value}",
                "operation_id": operation.operation_id,
                "family": family,
                "plane": operation.plane,
                "scenario": scenario,
                "context_key": CAUSAL_ARCHITECTURE_CONTEXT,
                "source_ids": operation.source_ids,
                "delegate_fixture_id": fixtures[family].fixture_id,
                "delegate_record_id": record.record_id,
                "delegate_context_key": str(record.context_key),
                "payload": {
                    "delegate_family": family.value,
                    "delegate_fixture_id": fixtures[family].fixture_id,
                    "delegate_record_id": record.record_id,
                    "delegate_operation": row["operation"],
                    "delegate_role": row["role"],
                    "delegate_payload": jsonable(record.payload),
                    "delegate_output_address": row["output_address"],
                },
                "expected_state": CausalArchitectureState.ACCEPTED
                if scenario is CausalArchitectureScenario.POSITIVE
                else CausalArchitectureState.REVIEW,
                "expected_result_state": row["state"],
                "expected_issue_codes": row["issue_codes"],
                "expected_counts": {"delegate_case": 1, "issue_count": len(row["issue_codes"])},
                "description": (
                    f"{family.value} public record {record.record_id} retained "
                    f"as D11 {scenario.value}"
                ),
            }
            cases.append(
                CausalArchitectureCase(**body, content_address=addressed(body, "causal-case"))
            )
    return tuple(cases)


def default_causal_architecture_fixture(
    path: str | Path | None = None,
) -> CausalArchitectureFixture:
    if path:
        return CausalArchitectureFixture.from_file(path)
    fixtures = _family_fixture_map()
    sources = _source_records(fixtures)
    operations = _operations(sources)
    cases = _cases(fixtures, _family_evaluation_map(fixtures), operations)
    body = {
        "fixture_id": "d11-causal-architecture-public-aggregate",
        "version": CAUSAL_ARCHITECTURE_VERSION,
        "boundary": CAUSAL_ARCHITECTURE_BOUNDARY,
        "context_key": CAUSAL_ARCHITECTURE_CONTEXT,
        "foreign_context_key": CAUSAL_ARCHITECTURE_FOREIGN_CONTEXT,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return CausalArchitectureFixture(**body, content_address=addressed(body, "causal-fixture"))


def causal_architecture_fixture_json(fixture: CausalArchitectureFixture | None = None) -> str:
    return (
        json.dumps(
            (fixture or default_causal_architecture_fixture()).to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def load_causal_architecture_mapping(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("D11 fixture JSON must be an object")
    return dict(raw)


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: CausalArchitectureCheckKind,
) -> CausalArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CausalArchitectureCheck(**body, content_address=addressed(body, "causal-check"))


def audit_causal_architecture_data(
    fixture: CausalArchitectureFixture,
) -> CausalArchitectureDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    checks = (
        _check(
            "fixture-boundary",
            fixture.boundary == CAUSAL_ARCHITECTURE_BOUNDARY,
            fixture.boundary,
            CAUSAL_ARCHITECTURE_BOUNDARY,
            "public non-patient boundary is pinned",
            CausalArchitectureCheckKind.FIXTURE,
        ),
        _check(
            "fixture-context",
            fixture.context_key == CAUSAL_ARCHITECTURE_CONTEXT,
            fixture.context_key,
            CAUSAL_ARCHITECTURE_CONTEXT,
            "exact causal context is pinned",
            CausalArchitectureCheckKind.FIXTURE,
        ),
        _check(
            "source-count",
            len(fixture.sources) == 20,
            len(fixture.sources),
            20,
            "four families contribute five source receipts",
            CausalArchitectureCheckKind.SOURCE,
        ),
        _check(
            "operation-count",
            len(fixture.operations) == 16,
            len(fixture.operations),
            16,
            "sixteen causal operations are present",
            CausalArchitectureCheckKind.OPERATION,
        ),
        _check(
            "case-count",
            len(fixture.cases) == 64,
            len(fixture.cases),
            64,
            "four cases exist per operation",
            CausalArchitectureCheckKind.CASE,
        ),
        _check(
            "source-joins",
            all(
                set(item.source_ids) <= source_ids for item in (*fixture.operations, *fixture.cases)
            ),
            True,
            True,
            "source joins resolve",
            CausalArchitectureCheckKind.SOURCE,
        ),
        _check(
            "operation-joins",
            all(item.operation_id in operation_ids for item in fixture.cases),
            True,
            True,
            "operation joins resolve",
            CausalArchitectureCheckKind.OPERATION,
        ),
        _check(
            "operation-balance",
            all(
                sum(item.operation_id == operation.operation_id for item in fixture.cases) == 4
                for operation in fixture.operations
            ),
            True,
            True,
            "operation balance is closed",
            CausalArchitectureCheckKind.INVARIANT,
        ),
        _check(
            "scenario-balance",
            len(fixture.positive_cases) == 16 and len(fixture.control_cases) == 48,
            (len(fixture.positive_cases), len(fixture.control_cases)),
            (16, 48),
            "positive/control balance is closed",
            CausalArchitectureCheckKind.CONTROL,
        ),
    )
    return CausalArchitectureDataAudit(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(checks, "causal-audit"),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("CAUSAL_ARCHITECTURE")
    or name.startswith("CausalArchitecture")
    or name.startswith(
        (
            "audit_causal_architecture",
            "causal_architecture_fixture_json",
            "default_causal_architecture",
            "load_causal_architecture",
        )
    )
]
