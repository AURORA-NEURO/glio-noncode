"""Source-to-operation provenance registry for the D06 aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureFixture,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureSourceBinding:
    source_id: str
    family: str
    operation_ids: tuple[str, ...]
    case_count: int
    positive_case_count: int
    control_case_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureSourceRegistry:
    fixture_id: str
    bindings: tuple[SequenceArchitectureSourceBinding, ...]
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"binding_count": len(self.bindings)}


def build_sequence_architecture_source_registry(
    fixture: SequenceArchitectureFixture,
) -> SequenceArchitectureSourceRegistry:
    operation_by_source: dict[str, set[str]] = {item.source_id: set() for item in fixture.sources}
    cases_by_source: dict[str, list[Any]] = {item.source_id: [] for item in fixture.sources}
    for operation in fixture.operations:
        for source_id in operation.source_ids:
            operation_by_source[source_id].add(operation.operation_id)
    for case in fixture.cases:
        for source_id in case.source_ids:
            cases_by_source[source_id].append(case)
    families = {item.source_id: item.family.value for item in fixture.sources}
    bindings = tuple(
        _binding(
            source_id,
            families[source_id],
            tuple(sorted(operation_by_source[source_id])),
            tuple(cases_by_source[source_id]),
        )
        for source_id in sorted(families)
    )
    checks = (
        _check(
            "source-binding-count",
            len(bindings) == 17,
            len(bindings),
            17,
            "all source receipts have bindings",
        ),
        _check(
            "source-operation-joins",
            all(item.operation_ids for item in bindings),
            sum(bool(item.operation_ids) for item in bindings),
            17,
            "every source joins an operation",
        ),
        _check(
            "source-case-joins",
            sum(bool(item.case_count) for item in bindings) == 16,
            sum(bool(item.case_count) for item in bindings),
            16,
            "all operational sources join cases; catalog-only receipts remain visible",
        ),
        _check(
            "source-family-labels",
            all(item.family for item in bindings),
            sum(bool(item.family) for item in bindings),
            17,
            "family labels are retained",
        ),
        _check(
            "source-case-conservation",
            sum(item.case_count for item in bindings) >= 64,
            sum(item.case_count for item in bindings),
            ">=64",
            "multi-source case joins conserve records",
        ),
        _check(
            "source-control-conservation",
            sum(item.control_case_count for item in bindings) >= 48,
            sum(item.control_case_count for item in bindings),
            ">=48",
            "control provenance is retained",
        ),
        _check(
            "source-addresses",
            all(item.content_address.startswith("sha256:") for item in bindings),
            sum(item.content_address.startswith("sha256:") for item in bindings),
            17,
            "bindings are addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "bindings": bindings, "checks": checks}
    return SequenceArchitectureSourceRegistry(
        fixture_id=fixture.fixture_id,
        bindings=bindings,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-source-registry"),
    )


def sequence_source_binding_for(
    registry: SequenceArchitectureSourceRegistry, source_id: str
) -> SequenceArchitectureSourceBinding:
    for item in registry.bindings:
        if item.source_id == source_id:
            return item
    raise KeyError(f"unknown D06 source: {source_id}")


def _binding(
    source_id: str, family: str, operation_ids: tuple[str, ...], cases: tuple[Any, ...]
) -> SequenceArchitectureSourceBinding:
    body = {
        "source_id": source_id,
        "family": family,
        "operation_ids": operation_ids,
        "case_count": len(cases),
        "positive_case_count": sum(item.scenario.value == "positive" for item in cases),
        "control_case_count": sum(item.scenario.value != "positive" for item in cases),
    }
    return SequenceArchitectureSourceBinding(
        **body, content_address=addressed(body, "sequence-source-binding")
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.SOURCE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.SOURCE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-source-check"),
    )


__all__ = [
    "SequenceArchitectureSourceBinding",
    "SequenceArchitectureSourceRegistry",
    "build_sequence_architecture_source_registry",
    "sequence_source_binding_for",
]
