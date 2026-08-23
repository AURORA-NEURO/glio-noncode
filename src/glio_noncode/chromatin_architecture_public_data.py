"""Public aggregate fixture composing every D07 C01-C16 tranche."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import evaluate_chromatin_alpha_frontier_fixture
from .chromatin_alpha_frontier_public_data import default_chromatin_alpha_frontier_fixture
from .chromatin_architecture_contracts import (
    CHROMATIN_ARCHITECTURE_BOUNDARY,
    CHROMATIN_ARCHITECTURE_CONTEXT,
    CHROMATIN_ARCHITECTURE_FOREIGN_CONTEXT,
    CHROMATIN_ARCHITECTURE_VERSION,
    ChromatinArchitectureCase,
    ChromatinArchitectureCheck,
    ChromatinArchitectureCheckKind,
    ChromatinArchitectureDataAudit,
    ChromatinArchitectureFamily,
    ChromatinArchitectureFixture,
    ChromatinArchitectureOperation,
    ChromatinArchitectureOperationSpec,
    ChromatinArchitecturePlane,
    ChromatinArchitectureScenario,
    ChromatinArchitectureSource,
    ChromatinArchitectureState,
    addressed,
)
from .chromatin_context_frontier_fixture_eval import evaluate_chromatin_context_frontier_fixture
from .chromatin_context_frontier_public_data import default_chromatin_context_frontier_fixture
from .chromatin_frontier_fixture_eval import evaluate_chromatin_frontier_fixture
from .chromatin_frontier_public_data import default_chromatin_frontier_fixture
from .methylation_frontier_fixture_eval import evaluate_methylation_frontier_fixture
from .methylation_frontier_public_data import default_methylation_frontier_fixture
from .serialization import jsonable

CHROMATIN_ARCHITECTURE_FIXTURE_FILE = "chromatin-architecture-public-aggregate.json"

_FAMILY_ORDER = (
    ChromatinArchitectureFamily.CONTEXT,
    ChromatinArchitectureFamily.METHYLATION,
    ChromatinArchitectureFamily.ALPHA,
    ChromatinArchitectureFamily.FRONTIER,
)
_FAMILY_PLANES = {
    ChromatinArchitectureFamily.CONTEXT: ChromatinArchitecturePlane.ACCESSIBILITY,
    ChromatinArchitectureFamily.METHYLATION: ChromatinArchitecturePlane.METHYLATION,
    ChromatinArchitectureFamily.ALPHA: ChromatinArchitecturePlane.CHROMATIN_STATE,
    ChromatinArchitectureFamily.FRONTIER: ChromatinArchitecturePlane.CROSS_ASSAY,
}
_FAMILY_OPERATIONS = {
    ChromatinArchitectureFamily.CONTEXT: (
        ChromatinArchitectureOperation.TRACK_RETRIEVAL,
        ChromatinArchitectureOperation.ACCESSIBILITY_DELTA,
        ChromatinArchitectureOperation.HISTONE_CONTEXT,
        ChromatinArchitectureOperation.H3K27AC_ACTIVITY,
    ),
    ChromatinArchitectureFamily.METHYLATION: (
        ChromatinArchitectureOperation.METHYLATION_CONTEXT,
        ChromatinArchitectureOperation.CPG_CHANGE,
        ChromatinArchitectureOperation.SENSITIVE_MOTIF,
        ChromatinArchitectureOperation.IDH_CONTEXT,
    ),
    ChromatinArchitectureFamily.ALPHA: (
        ChromatinArchitectureOperation.STATE_SEGMENTATION,
        ChromatinArchitectureOperation.ALLELE_SPECIFIC,
        ChromatinArchitectureOperation.PURITY,
        ChromatinArchitectureOperation.COMPOSITION_CORRECTION,
    ),
    ChromatinArchitectureFamily.FRONTIER: (
        ChromatinArchitectureOperation.CONTEXT_IMPUTATION,
        ChromatinArchitectureOperation.ASSAY_COVERAGE,
        ChromatinArchitectureOperation.ASSAY_CONCORDANCE,
        ChromatinArchitectureOperation.EVIDENCE_PUBLISH,
    ),
}


def _family_fixture_map() -> dict[ChromatinArchitectureFamily, Any]:
    return {
        ChromatinArchitectureFamily.CONTEXT: default_chromatin_context_frontier_fixture(),
        ChromatinArchitectureFamily.METHYLATION: default_methylation_frontier_fixture(),
        ChromatinArchitectureFamily.ALPHA: default_chromatin_alpha_frontier_fixture(),
        ChromatinArchitectureFamily.FRONTIER: default_chromatin_frontier_fixture(),
    }


def _family_evaluation_map(
    fixtures: Mapping[ChromatinArchitectureFamily, Any],
) -> dict[ChromatinArchitectureFamily, Any]:
    return {
        ChromatinArchitectureFamily.CONTEXT: evaluate_chromatin_context_frontier_fixture(
            fixtures[ChromatinArchitectureFamily.CONTEXT]
        ),
        ChromatinArchitectureFamily.METHYLATION: evaluate_methylation_frontier_fixture(
            fixtures[ChromatinArchitectureFamily.METHYLATION]
        ),
        ChromatinArchitectureFamily.ALPHA: evaluate_chromatin_alpha_frontier_fixture(
            fixtures[ChromatinArchitectureFamily.ALPHA]
        ),
        ChromatinArchitectureFamily.FRONTIER: evaluate_chromatin_frontier_fixture(
            fixtures[ChromatinArchitectureFamily.FRONTIER]
        ),
    }


def _record_dict(record: Any) -> dict[str, Any]:
    try:
        return dict(record.to_dict(include_payload=True))
    except TypeError:
        return dict(record.to_dict())


def _sources(
    fixtures: Mapping[ChromatinArchitectureFamily, Any],
) -> tuple[
    tuple[ChromatinArchitectureSource, ...], dict[tuple[ChromatinArchitectureFamily, str], str]
]:
    result: list[ChromatinArchitectureSource] = []
    mapping: dict[tuple[ChromatinArchitectureFamily, str], str] = {}
    for family in _FAMILY_ORDER:
        for source in fixtures[family].sources:
            raw = jsonable(source)
            original_id = str(raw["source_id"])
            source_id = f"{family.value}:{original_id}"
            mapping[(family, original_id)] = source_id
            body = {
                "source_id": source_id,
                "family": family,
                "title": str(raw.get("title", original_id)),
                "uri": str(raw.get("uri", "https://example.org/public-source")),
                "version": str(
                    raw.get("source_version", raw.get("release", raw.get("version", "public")))
                ),
                "scope": "public_aggregate",
                "license": "public source receipt",
            }
            result.append(
                ChromatinArchitectureSource(
                    **body,
                    content_address=addressed(body, "chromatin-source"),
                )
            )
    return tuple(result), mapping


def _operation_specs(
    fixtures: Mapping[ChromatinArchitectureFamily, Any],
    source_maps: Mapping[tuple[ChromatinArchitectureFamily, str], str],
) -> tuple[ChromatinArchitectureOperationSpec, ...]:
    operations: list[ChromatinArchitectureOperationSpec] = []
    ordinal = 0
    for family in _FAMILY_ORDER:
        source_ids = tuple(
            sorted(
                source_maps[(family, str(source.source_id))] for source in fixtures[family].sources
            )
        )
        for operation in _FAMILY_OPERATIONS[family]:
            ordinal += 1
            operation_id = f"D07-C{ordinal:02d}"
            body = {
                "operation_id": operation_id,
                "capability_id": f"GNC-D07-C{ordinal:02d}",
                "ordinal": ordinal,
                "operation": operation,
                "family": family,
                "plane": _FAMILY_PLANES[family],
                "input_contract": f"chromatin.{operation.value}.public_record.v1",
                "output_contract": f"chromatin.{operation.value}.receipt.v1",
                "dependencies": (f"D07-C{ordinal - 1:02d}",) if ordinal > 1 else (),
                "source_ids": source_ids,
                "control_policy": (
                    "hold foreign context, malformed input, and identity conflict before "
                    "family delegation; preserve cross-assay uncertainty"
                ),
            }
            operations.append(
                ChromatinArchitectureOperationSpec(
                    **body,
                    content_address=addressed(body, "chromatin-operation"),
                )
            )
    return tuple(operations)


def _evaluation_rows(evaluation: Any) -> tuple[Any, ...]:
    return tuple(
        getattr(evaluation, "executions", None)
        or getattr(evaluation, "records", None)
        or getattr(evaluation, "receipts", None)
        or ()
    )


def _positive_metadata(
    evaluations: Mapping[ChromatinArchitectureFamily, Any],
) -> dict[tuple[ChromatinArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]]:
    result: dict[
        tuple[ChromatinArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]
    ] = {}
    for family in _FAMILY_ORDER:
        for row in _evaluation_rows(evaluations[family]):
            role = getattr(row, "role", None)
            role_value = str(getattr(role, "value", role))
            if role_value != "positive":
                continue
            adapter = getattr(row, "adapter", row)
            state = (
                getattr(adapter, "state", None)
                or getattr(row, "adapter_state", None)
                or getattr(row, "observed_state", None)
            )
            issues = getattr(adapter, "issue_codes", None) or getattr(
                row, "observed_issue_codes", ()
            )
            result[(family, str(row.record_id))] = (
                str(getattr(state, "value", state)),
                tuple(str(item) for item in issues),
                _sanitize(jsonable(row)),
            )
    return result


def _frontier_operation_payload(ordinal: int) -> dict[str, Any]:
    if ordinal == 13:
        return {
            "records": [
                {
                    "feature_id": "chr7:100-140",
                    "value": 0.84,
                    "context_key": CHROMATIN_ARCHITECTURE_CONTEXT,
                },
                {
                    "feature_id": "chr7:180-220",
                    "value": None,
                    "context_key": CHROMATIN_ARCHITECTURE_CONTEXT,
                },
            ],
            "prior_values": {"chr7:180-220": 0.71},
            "prior_confidence": {"chr7:180-220": 0.91},
            "minimum_confidence": 0.7,
        }
    if ordinal == 14:
        return {
            "records": [
                {
                    "feature_id": "chr7:100-140",
                    "observed_assays": ["ATAC", "DNase", "H3K27ac"],
                    "context_key": CHROMATIN_ARCHITECTURE_CONTEXT,
                }
            ],
            "required_assays": ["ATAC", "DNase", "H3K27ac"],
            "minimum_coverage": 0.75,
        }
    if ordinal == 15:
        return {
            "records": [
                {
                    "feature_id": "chr7:100-140",
                    "observations": {"ATAC": "up", "H3K27ac": "up", "methylation": "up"},
                    "context_key": CHROMATIN_ARCHITECTURE_CONTEXT,
                }
            ],
            "minimum_concordance": 0.75,
        }
    return {
        "records": [
            {"feature_id": "chr7:100-140", "context_key": CHROMATIN_ARCHITECTURE_CONTEXT},
            {"feature_id": "chr7:180-220", "context_key": CHROMATIN_ARCHITECTURE_CONTEXT},
        ],
        "bundle_id": "d07-public-chromatin-release",
        "assay_ids": ["ATAC", "DNase", "H3K27ac", "methylation"],
    }


def _sanitize(value: Any) -> Any:
    forbidden = {"payload", "input_text", "track_text", "raw_text", "records_text"}
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize(item) for key, item in value.items() if str(key) not in forbidden
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _cases(
    fixtures: Mapping[ChromatinArchitectureFamily, Any],
    operations: tuple[ChromatinArchitectureOperationSpec, ...],
    source_maps: Mapping[tuple[ChromatinArchitectureFamily, str], str],
    positive_meta: Mapping[
        tuple[ChromatinArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]
    ],
) -> tuple[ChromatinArchitectureCase, ...]:
    cases: list[ChromatinArchitectureCase] = []
    for operation in operations:
        family = operation.family
        family_records = fixtures[family].positive_records
        record = next(
            item
            for item in family_records
            if int(operation.ordinal - _FAMILY_ORDER.index(family) * 4)
            == list(family_records).index(item) + 1
        )
        record_payload = _record_dict(record)
        source_ids = tuple(source_maps[(family, str(source_id))] for source_id in record.source_ids)
        result_state, issue_codes, summary = positive_meta[(family, str(record.record_id))]
        if family is ChromatinArchitectureFamily.FRONTIER:
            result_state = "published" if operation.ordinal == 16 else "accepted"
            issue_codes = ()
        positive_payload = {
            "family_record_id": str(record.record_id),
            "family_context_key": str(
                getattr(record, "context_key", CHROMATIN_ARCHITECTURE_CONTEXT)
            ),
            "family_record": record_payload,
            "family_summary": summary,
            "operation_payload": _frontier_operation_payload(operation.ordinal)
            if family is ChromatinArchitectureFamily.FRONTIER
            else record_payload.get("payload", record_payload),
        }
        cases.append(
            _make_case(
                operation,
                ChromatinArchitectureScenario.POSITIVE,
                CHROMATIN_ARCHITECTURE_CONTEXT,
                source_ids,
                positive_payload,
                ChromatinArchitectureState.ACCEPTED,
                result_state,
                issue_codes,
                {"primary": 1, "secondary": 1},
                f"public aggregate positive path for {operation.capability_id}",
            )
        )
        controls = (
            (
                ChromatinArchitectureScenario.FOREIGN_CONTEXT,
                CHROMATIN_ARCHITECTURE_FOREIGN_CONTEXT,
                "out_of_domain",
                ("context_mismatch",),
                "foreign context is held before family execution",
            ),
            (
                ChromatinArchitectureScenario.MALFORMED_INPUT,
                CHROMATIN_ARCHITECTURE_CONTEXT,
                "invalid",
                ("malformed_input",),
                "malformed aggregate input is held before family execution",
            ),
            (
                ChromatinArchitectureScenario.IDENTITY_CONFLICT,
                CHROMATIN_ARCHITECTURE_CONTEXT,
                "contradictory",
                ("identity_conflict",),
                "identity conflict is held before family execution",
            ),
        )
        for scenario, context, state, codes, description in controls:
            control_payload = {
                "family_record_id": str(record.record_id),
                "operation_payload": positive_payload["operation_payload"],
                "control": scenario.value,
                "malformed": scenario is ChromatinArchitectureScenario.MALFORMED_INPUT,
                "identity_conflict": scenario is ChromatinArchitectureScenario.IDENTITY_CONFLICT,
            }
            cases.append(
                _make_case(
                    operation,
                    scenario,
                    context,
                    source_ids,
                    control_payload,
                    ChromatinArchitectureState.REVIEW,
                    state,
                    codes,
                    {"primary": 0, "secondary": 0},
                    description,
                )
            )
    return tuple(cases)


def _make_case(
    operation: ChromatinArchitectureOperationSpec,
    scenario: ChromatinArchitectureScenario,
    context_key: str,
    source_ids: tuple[str, ...],
    payload: dict[str, Any],
    expected_state: ChromatinArchitectureState,
    expected_result_state: str,
    expected_issue_codes: tuple[str, ...],
    expected_counts: dict[str, int],
    description: str,
) -> ChromatinArchitectureCase:
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
        "expected_state": expected_state,
        "expected_result_state": expected_result_state,
        "expected_issue_codes": expected_issue_codes,
        "expected_counts": expected_counts,
        "description": description,
    }
    return ChromatinArchitectureCase(**body, content_address=addressed(body, "chromatin-case"))


def default_chromatin_architecture_fixture(
    path: str | Path | None = None,
) -> ChromatinArchitectureFixture:
    if path is not None:
        return ChromatinArchitectureFixture.from_file(path)
    fixtures = _family_fixture_map()
    evaluations = _family_evaluation_map(fixtures)
    sources, source_maps = _sources(fixtures)
    operations = _operation_specs(fixtures, source_maps)
    cases = _cases(fixtures, operations, source_maps, _positive_metadata(evaluations))
    body = {
        "fixture_id": "d07-chromatin-architecture-public-aggregate",
        "version": CHROMATIN_ARCHITECTURE_VERSION,
        "boundary": CHROMATIN_ARCHITECTURE_BOUNDARY,
        "context_key": CHROMATIN_ARCHITECTURE_CONTEXT,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return ChromatinArchitectureFixture(
        **body, content_address=addressed(body, "chromatin-fixture")
    )


def load_chromatin_architecture_mapping(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("D07 chromatin architecture JSON must be an object")
    return dict(raw)


def chromatin_architecture_fixture_json(fixture: ChromatinArchitectureFixture | None = None) -> str:
    selected = fixture or default_chromatin_architecture_fixture()
    return json.dumps(selected.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> ChromatinArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ChromatinArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ChromatinArchitectureCheck(**body, content_address=addressed(body, "chromatin-check"))


def _scenario_counts(fixture: ChromatinArchitectureFixture) -> dict[str, int]:
    return {
        scenario.value: sum(item.scenario is scenario for item in fixture.cases)
        for scenario in ChromatinArchitectureScenario
    }


def audit_chromatin_architecture_data(
    fixture: ChromatinArchitectureFixture,
) -> ChromatinArchitectureDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    checks = (
        _check(
            "fixture-version",
            fixture.version == CHROMATIN_ARCHITECTURE_VERSION,
            fixture.version,
            CHROMATIN_ARCHITECTURE_VERSION,
            "D07 version is pinned",
        ),
        _check(
            "fixture-boundary",
            fixture.boundary == CHROMATIN_ARCHITECTURE_BOUNDARY,
            fixture.boundary,
            CHROMATIN_ARCHITECTURE_BOUNDARY,
            "D07 is public aggregate chromatin data",
        ),
        _check(
            "fixture-context",
            fixture.context_key == CHROMATIN_ARCHITECTURE_CONTEXT,
            fixture.context_key,
            CHROMATIN_ARCHITECTURE_CONTEXT,
            "aggregate context is exact",
        ),
        _check(
            "source-count",
            len(fixture.sources) == 19,
            len(fixture.sources),
            19,
            "four family registries conserve nineteen sources",
        ),
        _check(
            "operation-count",
            len(fixture.operations) == 16,
            len(fixture.operations),
            16,
            "all D07 capabilities have operation specifications",
        ),
        _check(
            "case-count",
            len(fixture.cases) == 64,
            len(fixture.cases),
            64,
            "four cases are present for every operation",
        ),
        _check(
            "source-joins",
            all(
                set(item.source_ids) <= source_ids for item in (*fixture.operations, *fixture.cases)
            ),
            sum(
                set(item.source_ids) <= source_ids for item in (*fixture.operations, *fixture.cases)
            ),
            80,
            "source joins resolve for operations and cases",
        ),
        _check(
            "operation-uniqueness",
            len(operation_ids) == 16,
            len(operation_ids),
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
            "positive and control paths are explicit",
        ),
        _check(
            "scenario-balance",
            _scenario_counts(fixture)
            == {scenario.value: 16 for scenario in ChromatinArchitectureScenario},
            _scenario_counts(fixture),
            {scenario.value: 16 for scenario in ChromatinArchitectureScenario},
            "each operation has one positive and three controls",
        ),
        _check(
            "source-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            sum(item.content_address.startswith("sha256:") for item in fixture.sources),
            19,
            "public source receipts are addressed",
        ),
        _check(
            "operation-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.operations),
            sum(item.content_address.startswith("sha256:") for item in fixture.operations),
            16,
            "operation contracts are addressed",
        ),
        _check(
            "case-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.cases),
            sum(item.content_address.startswith("sha256:") for item in fixture.cases),
            64,
            "case contracts are addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return ChromatinArchitectureDataAudit(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "chromatin-audit"),
    )


__all__ = [
    "CHROMATIN_ARCHITECTURE_FIXTURE_FILE",
    "audit_chromatin_architecture_data",
    "chromatin_architecture_fixture_json",
    "default_chromatin_architecture_fixture",
    "load_chromatin_architecture_mapping",
]
