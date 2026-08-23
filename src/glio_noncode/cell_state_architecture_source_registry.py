"""Source registry projections for D08 public aggregate receipts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .cell_state_architecture_contracts import CellStateArchitectureFixture, addressed


def build_cell_state_architecture_source_registry(
    fixture: CellStateArchitectureFixture,
) -> dict[str, Any]:
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in fixture.sources:
        families[source.family.value].append(
            {
                "source_id": source.source_id,
                "title": source.title,
                "uri": source.uri,
                "version": source.version,
                "scope": source.scope,
                "license": source.license,
                "content_address": source.content_address,
            }
        )
    registry = {
        "fixture_id": fixture.fixture_id,
        "source_count": len(fixture.sources),
        "families": {
            key: sorted(value, key=lambda item: item["source_id"])
            for key, value in sorted(families.items())
        },
        "all_addresses": [item.content_address for item in fixture.sources],
    }
    return registry | {"content_address": addressed(registry, "cell-state-source-registry")}


def source_lookup(fixture: CellStateArchitectureFixture, source_id: str) -> dict[str, Any] | None:
    return next((item.to_dict() for item in fixture.sources if item.source_id == source_id), None)


__all__ = ["build_cell_state_architecture_source_registry", "source_lookup"]
