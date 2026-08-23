"""Source-to-operation registry and provenance closure for D05."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_architecture_contracts import (
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureFixture,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class AtlasArchitectureSourceBinding:
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
class AtlasArchitectureSourceRegistry:
    fixture_id: str
    bindings: tuple[AtlasArchitectureSourceBinding, ...]
    checks: tuple[AtlasArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"binding_count": len(self.bindings)}


def build_atlas_architecture_source_registry(
    fixture: AtlasArchitectureFixture,
) -> AtlasArchitectureSourceRegistry:
    """Build source joins from operation declarations and all case scenarios."""

    operation_by_source: dict[str, set[str]] = {item.source_id: set() for item in fixture.sources}
    case_by_source: dict[str, list[Any]] = {item.source_id: [] for item in fixture.sources}
    for operation in fixture.operations:
        for source_id in operation.source_ids:
            operation_by_source.setdefault(source_id, set()).add(operation.operation_id)
    for case in fixture.cases:
        for source_id in case.source_ids:
            case_by_source.setdefault(source_id, []).append(case)
    family_by_source = {item.source_id: item.family.value for item in fixture.sources}
    bindings = tuple(
        _binding(
            source_id,
            family_by_source[source_id],
            tuple(sorted(operation_by_source[source_id])),
            tuple(case_by_source[source_id]),
        )
        for source_id in sorted(family_by_source)
    )
    checks = (
        _check(
            "source-registry-cardinality",
            len(bindings) == len(fixture.sources),
            len(bindings),
            len(fixture.sources),
            "every public source has one registry binding",
        ),
        _check(
            "source-registry-operation-joins",
            all(item.operation_ids for item in bindings),
            sum(bool(item.operation_ids) for item in bindings),
            len(bindings),
            "every source joins at least one declared operation",
        ),
        _check(
            "source-registry-case-joins",
            all(item.case_count for item in bindings),
            sum(bool(item.case_count) for item in bindings),
            len(bindings),
            "every source joins at least one case",
        ),
        _check(
            "source-registry-public-families",
            all(item.family for item in bindings),
            sum(bool(item.family) for item in bindings),
            len(bindings),
            "every source retains a family provenance label",
        ),
        _check(
            "source-registry-case-conservation",
            sum(item.case_count for item in bindings) >= len(fixture.cases),
            sum(item.case_count for item in bindings),
            f">={len(fixture.cases)}",
            "source joins conserve the case population, including multi-source cases",
        ),
        _check(
            "source-registry-control-conservation",
            sum(item.control_case_count for item in bindings) >= len(fixture.control_cases),
            sum(item.control_case_count for item in bindings),
            f">={len(fixture.control_cases)}",
            "source joins retain control-case provenance",
        ),
        _check(
            "source-registry-addresses",
            all(item.content_address.startswith("sha256:") for item in bindings),
            sum(item.content_address.startswith("sha256:") for item in bindings),
            len(bindings),
            "every source binding is content addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "bindings": bindings, "checks": checks}
    return AtlasArchitectureSourceRegistry(
        fixture_id=fixture.fixture_id,
        bindings=bindings,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "atlas-source-registry"),
    )


def source_binding_for(
    registry: AtlasArchitectureSourceRegistry,
    source_id: str,
) -> AtlasArchitectureSourceBinding:
    """Return one binding and fail clearly when a source is outside the fixture."""

    for binding in registry.bindings:
        if binding.source_id == source_id:
            return binding
    raise KeyError(f"unknown D05 source binding: {source_id}")


def _binding(
    source_id: str,
    family: str,
    operation_ids: tuple[str, ...],
    cases: tuple[Any, ...],
) -> AtlasArchitectureSourceBinding:
    body = {
        "source_id": source_id,
        "family": family,
        "operation_ids": operation_ids,
        "case_count": len(cases),
        "positive_case_count": sum(item.scenario.value == "positive" for item in cases),
        "control_case_count": sum(item.scenario.value != "positive" for item in cases),
    }
    return AtlasArchitectureSourceBinding(
        **body,
        content_address=addressed(body, "atlas-source-binding"),
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.SOURCE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id=check_id,
        kind=AtlasArchitectureCheckKind.SOURCE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "atlas-source-check"),
    )


__all__ = [
    "AtlasArchitectureSourceBinding",
    "AtlasArchitectureSourceRegistry",
    "build_atlas_architecture_source_registry",
    "source_binding_for",
]
