"""Public D10 aggregate assembled from four link-graph family fixtures."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .link_frontier_fixture_eval import evaluate_link_frontier_fixture
from .link_frontier_public_data import default_link_frontier_fixture
from .link_graph_alpha_frontier_fixture_eval import evaluate_link_graph_alpha_frontier_fixture
from .link_graph_alpha_frontier_public_data import default_link_graph_alpha_frontier_fixture
from .link_graph_architecture_contracts import (
    LINK_GRAPH_ARCHITECTURE_BOUNDARY,
    LINK_GRAPH_ARCHITECTURE_CASE_COUNT,
    LINK_GRAPH_ARCHITECTURE_CASES_PER_OPERATION,
    LINK_GRAPH_ARCHITECTURE_CONTEXT,
    LINK_GRAPH_ARCHITECTURE_FOREIGN_CONTEXT,
    LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT,
    LINK_GRAPH_ARCHITECTURE_SOURCE_COUNT,
    LINK_GRAPH_ARCHITECTURE_VERSION,
    LinkGraphArchitectureCase,
    LinkGraphArchitectureCheck,
    LinkGraphArchitectureCheckKind,
    LinkGraphArchitectureDataAudit,
    LinkGraphArchitectureFamily,
    LinkGraphArchitectureFixture,
    LinkGraphArchitectureOperation,
    LinkGraphArchitectureOperationSpec,
    LinkGraphArchitecturePlane,
    LinkGraphArchitectureScenario,
    LinkGraphArchitectureSource,
    LinkGraphArchitectureState,
    addressed,
)
from .link_graph_beta_frontier_fixture_eval import evaluate_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_public_data import default_link_graph_beta_frontier_fixture
from .link_graph_foundation_frontier_fixture_eval import (
    evaluate_link_graph_foundation_frontier_fixture,
)
from .link_graph_foundation_frontier_public_data import (
    default_link_graph_foundation_frontier_fixture,
)
from .serialization import jsonable

_FAMILY_ORDER = (
    LinkGraphArchitectureFamily.FOUNDATION,
    LinkGraphArchitectureFamily.BETA,
    LinkGraphArchitectureFamily.ALPHA,
    LinkGraphArchitectureFamily.FRONTIER,
)
_FAMILY_PLANES = {
    LinkGraphArchitectureFamily.FOUNDATION: LinkGraphArchitecturePlane.FOUNDATION,
    LinkGraphArchitectureFamily.BETA: LinkGraphArchitecturePlane.BETA,
    LinkGraphArchitectureFamily.ALPHA: LinkGraphArchitecturePlane.ALPHA,
    LinkGraphArchitectureFamily.FRONTIER: LinkGraphArchitecturePlane.FRONTIER,
}
_FAMILY_PREFIXES = {
    LinkGraphArchitectureFamily.FOUNDATION: "foundation",
    LinkGraphArchitectureFamily.BETA: "beta",
    LinkGraphArchitectureFamily.ALPHA: "alpha",
    LinkGraphArchitectureFamily.FRONTIER: "frontier",
}
_OPERATIONS = tuple(LinkGraphArchitectureOperation)


def _family_fixture_map() -> dict[LinkGraphArchitectureFamily, Any]:
    return {
        LinkGraphArchitectureFamily.FOUNDATION: default_link_graph_foundation_frontier_fixture(),
        LinkGraphArchitectureFamily.BETA: default_link_graph_beta_frontier_fixture(),
        LinkGraphArchitectureFamily.ALPHA: default_link_graph_alpha_frontier_fixture(),
        LinkGraphArchitectureFamily.FRONTIER: default_link_frontier_fixture(),
    }


def _family_evaluation_map(
    fixtures: Mapping[LinkGraphArchitectureFamily, Any],
) -> dict[LinkGraphArchitectureFamily, Any]:
    return {
        LinkGraphArchitectureFamily.FOUNDATION: evaluate_link_graph_foundation_frontier_fixture(
            fixtures[LinkGraphArchitectureFamily.FOUNDATION]
        ),
        LinkGraphArchitectureFamily.BETA: evaluate_link_graph_beta_frontier_fixture(
            fixtures[LinkGraphArchitectureFamily.BETA]
        ),
        LinkGraphArchitectureFamily.ALPHA: evaluate_link_graph_alpha_frontier_fixture(
            fixtures[LinkGraphArchitectureFamily.ALPHA]
        ),
        LinkGraphArchitectureFamily.FRONTIER: evaluate_link_frontier_fixture(
            fixtures[LinkGraphArchitectureFamily.FRONTIER]
        ),
    }


def _rows(
    family: LinkGraphArchitectureFamily, fixture: Any, evaluation: Any
) -> tuple[dict[str, Any], ...]:
    records = {str(item.record_id): item for item in fixture.records}
    if family is LinkGraphArchitectureFamily.FRONTIER:
        executions = evaluation.execution_map()
        result = []
        for record in fixture.records:
            execution = executions[record.record_id]
            result.append(
                {
                    "record": record,
                    "role": record.role.value,
                    "operation": record.operation.value,
                    "state": execution.state,
                    "issue_codes": tuple(execution.issue_codes),
                    "output": execution.output,
                    "output_address": execution.content_address,
                }
            )
        return tuple(result)
    result = []
    for row in evaluation.rows:
        record = records[row.record_id]
        adapter = row.adapter
        result.append(
            {
                "record": record,
                "role": row.role,
                "operation": row.operation,
                "state": row.observed_state,
                "issue_codes": tuple(row.observed_issue_codes),
                "output": adapter.to_dict(),
                "output_address": addressed(adapter.to_dict(), "link-delegate-output"),
            }
        )
    return tuple(result)


def _source_records(
    fixtures: Mapping[LinkGraphArchitectureFamily, Any],
) -> tuple[LinkGraphArchitectureSource, ...]:
    sources: list[LinkGraphArchitectureSource] = []
    for family in _FAMILY_ORDER:
        prefix = _FAMILY_PREFIXES[family]
        for source in fixtures[family].sources:
            raw = source.to_dict()
            body = {
                "source_id": f"D10-{prefix}-{source.source_id}",
                "family": family,
                "source_kind": str(
                    raw.get("source_kind", raw.get("source_kind", "public_link_aggregate"))
                ),
                "source_version": str(raw.get("source_version", raw.get("release", "pinned"))),
                "uri": str(raw.get("uri", "https://data.example.org/links/aggregate")),
                "context_key": str(raw.get("context_key", LINK_GRAPH_ARCHITECTURE_CONTEXT)),
                "public_aggregate": True,
                "delegate_source_id": str(source.source_id),
            }
            sources.append(
                LinkGraphArchitectureSource(**body, content_address=addressed(body, "link-source"))
            )
    return tuple(sources)


def _operation_source_ids(
    sources: tuple[LinkGraphArchitectureSource, ...], family: LinkGraphArchitectureFamily
) -> tuple[str, ...]:
    return tuple(item.source_id for item in sources if item.family is family)


def _operations(
    sources: tuple[LinkGraphArchitectureSource, ...],
) -> tuple[LinkGraphArchitectureOperationSpec, ...]:
    operations: list[LinkGraphArchitectureOperationSpec] = []
    for ordinal, operation in enumerate(_OPERATIONS, start=1):
        family = _FAMILY_ORDER[(ordinal - 1) // 4]
        plane = _FAMILY_PLANES[family]
        body = {
            "operation_id": f"D10-C{ordinal:02d}",
            "capability_id": f"GNC-D10-C{ordinal:02d}",
            "ordinal": ordinal,
            "operation": operation,
            "family": family,
            "plane": plane,
            "input_contract": f"link_graph.{operation.value}.public_record.v1",
            "output_contract": f"link_graph.{operation.value}.receipt.v1",
            "dependencies": (f"D10-C{ordinal - 1:02d}",) if ordinal > 1 else (),
            "source_ids": _operation_source_ids(sources, family),
            "control_policy": (
                "retain every aggregate control outcome and require explicit "
                "source/context receipt coverage"
            ),
        }
        operations.append(
            LinkGraphArchitectureOperationSpec(
                **body, content_address=addressed(body, "link-operation")
            )
        )
    return tuple(operations)


def _cases(
    fixtures: Mapping[LinkGraphArchitectureFamily, Any],
    evaluations: Mapping[LinkGraphArchitectureFamily, Any],
    sources: tuple[LinkGraphArchitectureSource, ...],
    operations: tuple[LinkGraphArchitectureOperationSpec, ...],
) -> tuple[LinkGraphArchitectureCase, ...]:
    cases: list[LinkGraphArchitectureCase] = []
    for operation in operations:
        family = operation.family
        source_ids = operation.source_ids
        family_rows = tuple(
            row
            for row in _rows(family, fixtures[family], evaluations[family])
            if row["operation"] == _OPERATIONS[operation.ordinal - 1].value
        )
        if len(family_rows) != 4:
            raise ValueError(f"D10 delegate balance failed for {operation.operation_id}")
        for index, row in enumerate(family_rows):
            record = row["record"]
            scenario = tuple(LinkGraphArchitectureScenario)[index]
            case_id = f"{operation.operation_id}-{scenario.value}"
            expected_state = (
                LinkGraphArchitectureState.ACCEPTED
                if scenario is LinkGraphArchitectureScenario.POSITIVE
                else LinkGraphArchitectureState.REVIEW
            )
            delegate_payload = jsonable(record.payload)
            payload = {
                "delegate_family": family.value,
                "delegate_fixture_id": fixtures[family].fixture_id,
                "delegate_record_id": record.record_id,
                "delegate_operation": row["operation"],
                "delegate_role": row["role"],
                "delegate_payload": delegate_payload,
                "delegate_output_address": row["output_address"],
            }
            body = {
                "case_id": case_id,
                "operation_id": operation.operation_id,
                "family": family,
                "plane": operation.plane,
                "scenario": scenario,
                "context_key": LINK_GRAPH_ARCHITECTURE_CONTEXT,
                "source_ids": source_ids,
                "delegate_fixture_id": fixtures[family].fixture_id,
                "delegate_record_id": record.record_id,
                "delegate_context_key": str(record.context_key),
                "payload": payload,
                "expected_state": expected_state,
                "expected_result_state": row["state"],
                "expected_issue_codes": row["issue_codes"],
                "expected_counts": {"delegate_case": 1, "issue_count": len(row["issue_codes"])},
                "description": (
                    f"{family.value} public link record {record.record_id} "
                    f"retained as D10 {scenario.value}"
                ),
            }
            cases.append(
                LinkGraphArchitectureCase(**body, content_address=addressed(body, "link-case"))
            )
    return tuple(cases)


def default_link_graph_architecture_fixture(
    path: str | Path | None = None,
) -> LinkGraphArchitectureFixture:
    if path:
        return LinkGraphArchitectureFixture.from_file(path)
    fixtures = _family_fixture_map()
    sources = _source_records(fixtures)
    operations = _operations(sources)
    cases = _cases(fixtures, _family_evaluation_map(fixtures), sources, operations)
    body = {
        "fixture_id": "d10-link-graph-architecture-public-aggregate",
        "version": LINK_GRAPH_ARCHITECTURE_VERSION,
        "boundary": LINK_GRAPH_ARCHITECTURE_BOUNDARY,
        "context_key": LINK_GRAPH_ARCHITECTURE_CONTEXT,
        "foreign_context_key": LINK_GRAPH_ARCHITECTURE_FOREIGN_CONTEXT,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return LinkGraphArchitectureFixture(**body, content_address=addressed(body, "link-fixture"))


def link_graph_architecture_fixture_json(
    fixture: LinkGraphArchitectureFixture | None = None,
) -> str:
    return (
        json.dumps(
            (fixture or default_link_graph_architecture_fixture()).to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def load_link_graph_architecture_mapping(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("D10 fixture JSON must be an object")
    return dict(raw)


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: LinkGraphArchitectureCheckKind,
) -> LinkGraphArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return LinkGraphArchitectureCheck(**body, content_address=addressed(body, "link-check"))


def audit_link_graph_architecture_data(
    fixture: LinkGraphArchitectureFixture,
) -> LinkGraphArchitectureDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    checks = (
        _check(
            "fixture-boundary",
            fixture.boundary == LINK_GRAPH_ARCHITECTURE_BOUNDARY,
            fixture.boundary,
            LINK_GRAPH_ARCHITECTURE_BOUNDARY,
            "public non-patient boundary is pinned",
            LinkGraphArchitectureCheckKind.FIXTURE,
        ),
        _check(
            "fixture-context",
            fixture.context_key == LINK_GRAPH_ARCHITECTURE_CONTEXT,
            fixture.context_key,
            LINK_GRAPH_ARCHITECTURE_CONTEXT,
            "aggregate context is exact",
            LinkGraphArchitectureCheckKind.FIXTURE,
        ),
        _check(
            "source-count",
            len(fixture.sources) == LINK_GRAPH_ARCHITECTURE_SOURCE_COUNT,
            len(fixture.sources),
            LINK_GRAPH_ARCHITECTURE_SOURCE_COUNT,
            "four source families are closed",
            LinkGraphArchitectureCheckKind.SOURCE,
        ),
        _check(
            "operation-count",
            len(fixture.operations) == LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT,
            len(fixture.operations),
            LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT,
            "sixteen operations are present",
            LinkGraphArchitectureCheckKind.OPERATION,
        ),
        _check(
            "case-count",
            len(fixture.cases) == LINK_GRAPH_ARCHITECTURE_CASE_COUNT,
            len(fixture.cases),
            LINK_GRAPH_ARCHITECTURE_CASE_COUNT,
            "four cases exist for every operation",
            LinkGraphArchitectureCheckKind.CASE,
        ),
        _check(
            "source-joins",
            all(
                set(item.source_ids) <= source_ids for item in (*fixture.operations, *fixture.cases)
            ),
            True,
            True,
            "all source receipts resolve",
            LinkGraphArchitectureCheckKind.SOURCE,
        ),
        _check(
            "operation-joins",
            all(item.operation_id in operation_ids for item in fixture.cases),
            True,
            True,
            "all case operation joins resolve",
            LinkGraphArchitectureCheckKind.OPERATION,
        ),
        _check(
            "operation-balance",
            all(
                len(
                    tuple(
                        item
                        for item in fixture.cases
                        if item.operation_id == operation.operation_id
                    )
                )
                == LINK_GRAPH_ARCHITECTURE_CASES_PER_OPERATION
                for operation in fixture.operations
            ),
            True,
            True,
            "operation case balance is closed",
            LinkGraphArchitectureCheckKind.INVARIANT,
        ),
        _check(
            "scenario-balance",
            len(fixture.positive_cases) == 16 and len(fixture.control_cases) == 48,
            (len(fixture.positive_cases), len(fixture.control_cases)),
            (16, 48),
            "positive and control coverage is balanced",
            LinkGraphArchitectureCheckKind.CONTROL,
        ),
    )
    return LinkGraphArchitectureDataAudit(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(checks, "link-audit"),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("LINK_GRAPH_ARCHITECTURE")
    or name.startswith("LinkGraphArchitecture")
    or name.endswith("link_graph_architecture_fixture")
    or name.startswith(
        (
            "audit_link_graph_architecture",
            "default_link_graph_architecture",
            "link_graph_architecture_fixture_json",
            "load_link_graph_architecture",
        )
    )
]
