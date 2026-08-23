"""Source registry and operation/case join checks for D07."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import ChromatinArchitectureFixture, addressed
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureSourceBinding:
    source_id: str
    family: str
    uri: str
    version: str
    operation_ids: tuple[str, ...]
    case_count: int
    public_aggregate: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureSourceRegistry:
    fixture_id: str
    bindings: tuple[ChromatinArchitectureSourceBinding, ...]
    checks: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_architecture_source_registry(
    fixture: ChromatinArchitectureFixture,
) -> ChromatinArchitectureSourceRegistry:
    bindings: list[ChromatinArchitectureSourceBinding] = []
    for source in fixture.sources:
        operation_ids = tuple(
            item.operation_id for item in fixture.operations if source.source_id in item.source_ids
        )
        case_count = sum(source.source_id in item.source_ids for item in fixture.cases)
        body = {
            "source_id": source.source_id,
            "family": source.family.value,
            "uri": source.uri,
            "version": source.version,
            "operation_ids": operation_ids,
            "case_count": case_count,
            "public_aggregate": source.scope == "public_aggregate",
        }
        bindings.append(
            ChromatinArchitectureSourceBinding(
                **body, content_address=addressed(body, "chromatin-source-binding")
            )
        )
    values = tuple(bindings)
    checks = (
        "nineteen source receipts are registered",
        "all URIs use HTTP(S)",
        "all sources are public aggregate",
        "every source joins at least one operation",
        "operational sources join cases while catalog receipts remain linked to operations",
        "source families are explicit",
        "source bindings are content addressed",
    )
    accepted = (
        len(values) == 19
        and all(item.uri.startswith(("https://", "http://")) for item in values)
        and all(item.public_aggregate for item in values)
        and all(item.operation_ids for item in values)
        and all(item.content_address.startswith("sha256:") for item in values)
    )
    return ChromatinArchitectureSourceRegistry(
        fixture.fixture_id,
        values,
        checks,
        accepted,
        addressed(
            {"fixture_id": fixture.fixture_id, "bindings": values, "checks": checks},
            "chromatin-source-registry",
        ),
    )


def chromatin_source_binding_for(
    registry: ChromatinArchitectureSourceRegistry, source_id: str
) -> ChromatinArchitectureSourceBinding:
    for binding in registry.bindings:
        if binding.source_id == source_id:
            return binding
    raise KeyError(source_id)


__all__ = [
    "ChromatinArchitectureSourceBinding",
    "ChromatinArchitectureSourceRegistry",
    "build_chromatin_architecture_source_registry",
    "chromatin_source_binding_for",
]
