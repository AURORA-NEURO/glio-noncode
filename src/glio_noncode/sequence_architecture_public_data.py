"""Public aggregate D06 fixture composed from the four sequence family tranches."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .sequence_architecture_contracts import (
    SEQUENCE_ARCHITECTURE_BOUNDARY,
    SEQUENCE_ARCHITECTURE_CONTEXT,
    SEQUENCE_ARCHITECTURE_FOREIGN_CONTEXT,
    SEQUENCE_ARCHITECTURE_VERSION,
    SequenceArchitectureCase,
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureFamily,
    SequenceArchitectureFixture,
    SequenceArchitectureOperation,
    SequenceArchitectureOperationSpec,
    SequenceArchitecturePlane,
    SequenceArchitectureScenario,
    SequenceArchitectureSource,
    SequenceArchitectureState,
    addressed,
)
from .sequence_effect_frontier_fixture_eval import evaluate_sequence_effect_fixture
from .sequence_effect_frontier_public_data import default_sequence_effect_fixture
from .sequence_frontier_fixture_eval import evaluate_sequence_frontier_fixture
from .sequence_frontier_public_data import default_sequence_frontier_fixture
from .sequence_grammar_frontier_fixture_eval import evaluate_sequence_grammar_fixture
from .sequence_grammar_frontier_public_data import default_sequence_grammar_fixture
from .sequence_regulation_frontier_fixture_eval import evaluate_sequence_regulation_fixture
from .sequence_regulation_frontier_public_data import default_sequence_regulation_fixture
from .serialization import jsonable

SEQUENCE_ARCHITECTURE_FIXTURE_FILE = "sequence-architecture-public-aggregate.json"

_FAMILY_ORDER = (
    SequenceArchitectureFamily.EFFECT,
    SequenceArchitectureFamily.GRAMMAR,
    SequenceArchitectureFamily.REGULATION,
    SequenceArchitectureFamily.FRONTIER,
)
_FAMILY_PLANES = {
    SequenceArchitectureFamily.EFFECT: SequenceArchitecturePlane.EFFECT,
    SequenceArchitectureFamily.GRAMMAR: SequenceArchitecturePlane.GRAMMAR,
    SequenceArchitectureFamily.REGULATION: SequenceArchitecturePlane.REGULATION,
    SequenceArchitectureFamily.FRONTIER: SequenceArchitecturePlane.FRONTIER,
}


def default_sequence_architecture_fixture(
    path: str | Path | None = None,
) -> SequenceArchitectureFixture:
    if path is not None:
        return SequenceArchitectureFixture.from_file(path)
    return _build_default_fixture()


def load_sequence_architecture_mapping(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("D06 sequence architecture JSON must be an object")
    return dict(raw)


def sequence_architecture_fixture_json(
    fixture: SequenceArchitectureFixture | None = None,
) -> str:
    selected = fixture or default_sequence_architecture_fixture()
    return json.dumps(selected.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def audit_sequence_architecture_data(
    fixture: SequenceArchitectureFixture,
) -> Any:
    checks = (
        _check(
            "fixture-version",
            fixture.version == SEQUENCE_ARCHITECTURE_VERSION,
            fixture.version,
            SEQUENCE_ARCHITECTURE_VERSION,
            "D06 version is pinned",
        ),
        _check(
            "fixture-boundary",
            fixture.boundary == SEQUENCE_ARCHITECTURE_BOUNDARY,
            fixture.boundary,
            SEQUENCE_ARCHITECTURE_BOUNDARY,
            "D06 is public aggregate sequence data",
        ),
        _check(
            "fixture-context",
            fixture.context_key == SEQUENCE_ARCHITECTURE_CONTEXT,
            fixture.context_key,
            SEQUENCE_ARCHITECTURE_CONTEXT,
            "aggregate context is exact",
        ),
        _check(
            "source-count",
            len(fixture.sources) == 17,
            len(fixture.sources),
            17,
            "four family catalogs conserve seventeen sources",
        ),
        _check(
            "operation-count",
            len(fixture.operations) == 16,
            len(fixture.operations),
            16,
            "all D06 capabilities have operation specs",
        ),
        _check(
            "case-count",
            len(fixture.cases) == 64,
            len(fixture.cases),
            64,
            "four cases are present for each operation",
        ),
        _check(
            "source-joins",
            all(
                set(item.source_ids) <= {source.source_id for source in fixture.sources}
                for item in fixture.operations
            ),
            sum(
                set(item.source_ids) <= {source.source_id for source in fixture.sources}
                for item in fixture.operations
            ),
            16,
            "operation source joins resolve",
        ),
        _check(
            "case-joins",
            all(
                set(item.source_ids) <= {source.source_id for source in fixture.sources}
                for item in fixture.cases
            ),
            sum(
                set(item.source_ids) <= {source.source_id for source in fixture.sources}
                for item in fixture.cases
            ),
            64,
            "case source joins resolve",
        ),
        _check(
            "operation-uniqueness",
            len({item.operation_id for item in fixture.operations}) == 16,
            len({item.operation_id for item in fixture.operations}),
            16,
            "operation IDs are unique",
        ),
        _check(
            "case-uniqueness",
            len({item.case_id for item in fixture.cases}) == 64,
            len({item.case_id for item in fixture.cases}),
            64,
            "case IDs are unique",
        ),
        _check(
            "positive-control-balance",
            (len(fixture.positive_cases), len(fixture.control_cases)) == (16, 48),
            (len(fixture.positive_cases), len(fixture.control_cases)),
            (16, 48),
            "positive and controls are explicit",
        ),
        _check(
            "scenario-balance",
            _scenario_balance(fixture),
            _scenario_counts(fixture),
            {scenario.value: 16 for scenario in SequenceArchitectureScenario},
            "every operation has one positive and three controls",
        ),
        _check(
            "source-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            sum(item.content_address.startswith("sha256:") for item in fixture.sources),
            17,
            "public source receipts are addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    from .sequence_architecture_contracts import SequenceArchitectureDataAudit

    return SequenceArchitectureDataAudit(
        fixture_id=fixture.fixture_id,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-data-audit"),
    )


def _build_default_fixture() -> SequenceArchitectureFixture:
    family_fixtures = {
        SequenceArchitectureFamily.EFFECT: default_sequence_effect_fixture(),
        SequenceArchitectureFamily.GRAMMAR: default_sequence_grammar_fixture(),
        SequenceArchitectureFamily.REGULATION: default_sequence_regulation_fixture(),
        SequenceArchitectureFamily.FRONTIER: default_sequence_frontier_fixture(),
    }
    family_results = {
        SequenceArchitectureFamily.EFFECT: evaluate_sequence_effect_fixture(
            family_fixtures[SequenceArchitectureFamily.EFFECT]
        ),
        SequenceArchitectureFamily.GRAMMAR: evaluate_sequence_grammar_fixture(
            family_fixtures[SequenceArchitectureFamily.GRAMMAR]
        ),
        SequenceArchitectureFamily.REGULATION: evaluate_sequence_regulation_fixture(
            family_fixtures[SequenceArchitectureFamily.REGULATION]
        ),
        SequenceArchitectureFamily.FRONTIER: evaluate_sequence_frontier_fixture(
            family_fixtures[SequenceArchitectureFamily.FRONTIER]
        ),
    }
    sources, source_maps = _sources(family_fixtures)
    operations = _operation_specs(family_fixtures, source_maps)
    positive_meta = _positive_metadata(family_fixtures, family_results)
    cases = _cases(family_fixtures, operations, source_maps, positive_meta)
    body = {
        "fixture_id": "sequence-grammar-variant-effect-public-aggregate",
        "version": SEQUENCE_ARCHITECTURE_VERSION,
        "boundary": SEQUENCE_ARCHITECTURE_BOUNDARY,
        "context_key": SEQUENCE_ARCHITECTURE_CONTEXT,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return SequenceArchitectureFixture(**body, content_address=addressed(body, "sequence-fixture"))


def _sources(
    fixtures: Mapping[SequenceArchitectureFamily, Any],
) -> tuple[
    tuple[SequenceArchitectureSource, ...], dict[tuple[SequenceArchitectureFamily, str], str]
]:
    result: list[SequenceArchitectureSource] = []
    mappings: dict[tuple[SequenceArchitectureFamily, str], str] = {}
    for family in _FAMILY_ORDER:
        for source in fixtures[family].sources:
            raw = jsonable(source)
            original_id = str(raw["source_id"])
            source_id = f"{family.value}:{original_id}"
            mappings[(family, original_id)] = source_id
            title = str(raw.get("title", original_id))
            uri = str(raw["uri"])
            version = str(raw.get("source_version", raw.get("release", "public")))
            scope = "public_aggregate"
            license_label = "public source receipt"
            body = {
                "source_id": source_id,
                "family": family,
                "title": title,
                "uri": uri,
                "version": version,
                "scope": scope,
                "license": license_label,
            }
            result.append(
                SequenceArchitectureSource(
                    **body, content_address=addressed(body, "sequence-source")
                )
            )
    return tuple(result), mappings


def _operation_specs(
    fixtures: Mapping[SequenceArchitectureFamily, Any],
    source_maps: Mapping[tuple[SequenceArchitectureFamily, str], str],
) -> tuple[SequenceArchitectureOperationSpec, ...]:
    operations: list[SequenceArchitectureOperationSpec] = []
    ordinal = 0
    for family in _FAMILY_ORDER:
        records = fixtures[family].positive_records
        source_ids = tuple(
            sorted(source_maps[(family, source.source_id)] for source in fixtures[family].sources)
        )
        for record in records:
            ordinal += 1
            operation = SequenceArchitectureOperation(str(record.operation))
            operation_id = f"D06-C{ordinal:02d}"
            dependencies = (f"D06-C{ordinal - 1:02d}",) if ordinal > 1 else ()
            body = {
                "operation_id": operation_id,
                "capability_id": f"GNC-D06-C{ordinal:02d}",
                "ordinal": ordinal,
                "operation": operation,
                "family": family,
                "plane": _FAMILY_PLANES[family],
                "input_contract": f"sequence.{operation.value}.public_record.v1",
                "output_contract": f"sequence.{operation.value}.receipt.v1",
                "dependencies": dependencies,
                "source_ids": source_ids,
                "control_policy": (
                    "hold foreign context, malformed input, and identity conflict "
                    "before family delegation"
                ),
            }
            operations.append(
                SequenceArchitectureOperationSpec(
                    **body, content_address=addressed(body, "sequence-operation")
                )
            )
    return tuple(operations)


def _positive_metadata(
    fixtures: Mapping[SequenceArchitectureFamily, Any],
    evaluations: Mapping[SequenceArchitectureFamily, Any],
) -> dict[tuple[SequenceArchitectureFamily, str], tuple[str, tuple[str, ...]]]:
    result: dict[tuple[SequenceArchitectureFamily, str], tuple[str, tuple[str, ...]]] = {}
    for family in _FAMILY_ORDER:
        evaluation = evaluations[family]
        rows = (
            getattr(evaluation, "executions", None)
            or getattr(evaluation, "records", None)
            or getattr(evaluation, "receipts", None)
        )
        for row in rows:
            if str(getattr(row, "role", "")) != "positive":
                continue
            state = getattr(row, "adapter_state", None) or getattr(row, "observed_state", None)
            issues = getattr(row, "issue_codes", None) or getattr(row, "observed_issue_codes", ())
            result[(family, str(row.record_id))] = (
                str(getattr(state, "value", state)),
                tuple(str(item) for item in issues),
            )
    return result


def _cases(
    fixtures: Mapping[SequenceArchitectureFamily, Any],
    operations: tuple[SequenceArchitectureOperationSpec, ...],
    source_maps: Mapping[tuple[SequenceArchitectureFamily, str], str],
    positive_meta: Mapping[tuple[SequenceArchitectureFamily, str], tuple[str, tuple[str, ...]]],
) -> tuple[SequenceArchitectureCase, ...]:
    cases: list[SequenceArchitectureCase] = []
    for operation in operations:
        family = operation.family
        record = next(
            item
            for item in fixtures[family].positive_records
            if str(item.operation) == operation.operation.value
        )
        record_payload = (
            record.to_dict(include_payload=True)
            if family is SequenceArchitectureFamily.EFFECT
            else record.to_dict()
        )
        source_ids = tuple(source_maps[(family, source_id)] for source_id in record.source_ids)
        result_state, issue_codes = positive_meta[(family, record.record_id)]
        positive_payload = {
            "record_id": record.record_id,
            "family_record": jsonable(record_payload),
        }
        cases.append(
            _case(
                operation,
                SequenceArchitectureScenario.POSITIVE,
                SEQUENCE_ARCHITECTURE_CONTEXT,
                source_ids,
                positive_payload,
                result_state,
                issue_codes,
                {"primary": 1, "secondary": 1},
                f"public positive {operation.operation.value} family record",
            )
        )
        controls = (
            (
                SequenceArchitectureScenario.FOREIGN_CONTEXT,
                SEQUENCE_ARCHITECTURE_FOREIGN_CONTEXT,
                "out_of_domain",
                ("context_mismatch",),
                {
                    "context_key": SEQUENCE_ARCHITECTURE_FOREIGN_CONTEXT,
                    "record_id": record.record_id,
                },
            ),
            (
                SequenceArchitectureScenario.MALFORMED_INPUT,
                SEQUENCE_ARCHITECTURE_CONTEXT,
                "invalid",
                ("malformed_input",),
                {
                    "context_key": SEQUENCE_ARCHITECTURE_CONTEXT,
                    "record_id": record.record_id,
                    "malformed": True,
                },
            ),
            (
                SequenceArchitectureScenario.IDENTITY_CONFLICT,
                SEQUENCE_ARCHITECTURE_CONTEXT,
                "contradictory",
                ("identity_conflict",),
                {
                    "context_key": SEQUENCE_ARCHITECTURE_CONTEXT,
                    "record_id": record.record_id,
                    "declared_operation": "different_operation",
                    "identity_conflict": True,
                },
            ),
        )
        for scenario, context_key, result, issues, payload in controls:
            cases.append(
                _case(
                    operation,
                    scenario,
                    context_key,
                    source_ids,
                    payload,
                    result,
                    issues,
                    {"primary": 0, "secondary": 0},
                    f"aggregate boundary control for {operation.operation.value}",
                )
            )
    return tuple(cases)


def _case(
    operation: SequenceArchitectureOperationSpec,
    scenario: SequenceArchitectureScenario,
    context_key: str,
    source_ids: tuple[str, ...],
    payload: dict[str, Any],
    result_state: str,
    issue_codes: tuple[str, ...],
    counts: dict[str, int],
    description: str,
) -> SequenceArchitectureCase:
    body = {
        "case_id": f"{operation.operation_id}-{scenario.value}",
        "operation_id": operation.operation_id,
        "capability_id": operation.capability_id,
        "operation": operation.operation,
        "family": operation.family,
        "plane": operation.plane,
        "scenario": scenario,
        "context_key": context_key,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": SequenceArchitectureState.ACCEPTED
        if scenario is SequenceArchitectureScenario.POSITIVE
        else SequenceArchitectureState.REVIEW,
        "expected_result_state": result_state,
        "expected_issue_codes": issue_codes,
        "expected_counts": counts,
        "description": description,
    }
    return SequenceArchitectureCase(**body, content_address=addressed(body, "sequence-case"))


def _scenario_counts(fixture: SequenceArchitectureFixture) -> dict[str, int]:
    return {
        scenario.value: sum(item.scenario is scenario for item in fixture.cases)
        for scenario in SequenceArchitectureScenario
    }


def _scenario_balance(fixture: SequenceArchitectureFixture) -> bool:
    return _scenario_counts(fixture) == {
        scenario.value: 16 for scenario in SequenceArchitectureScenario
    }


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.FIXTURE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-data-check"),
    )


__all__ = [
    "SEQUENCE_ARCHITECTURE_FIXTURE_FILE",
    "audit_sequence_architecture_data",
    "default_sequence_architecture_fixture",
    "load_sequence_architecture_mapping",
    "sequence_architecture_fixture_json",
]
