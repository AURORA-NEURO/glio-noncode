"""Operation adapters and capability wiring for public integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_contracts import default_reference_release_contracts
from .reference_release_frontier_public_data import ReferenceReleaseOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleaseAdapterSpec:
    """One local adapter declaration."""

    adapter_id: str
    capability_id: str
    operation: ReferenceReleaseOperation
    input_contract: str
    output_contract: str
    deterministic: bool
    network_required: bool
    mutation_scope: str
    boundary: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "adapter_id",
            "capability_id",
            "input_contract",
            "output_contract",
            "mutation_scope",
            "boundary",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.mutation_scope not in {"none", "metadata-only"}:
            raise ValueError("release adapter mutation scope is not allowed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseAdapterRegistry:
    """Validated operation-to-contract map."""

    adapters: tuple[ReferenceReleaseAdapterSpec, ...]
    content_address: str

    def by_operation(
        self, operation: ReferenceReleaseOperation | str
    ) -> ReferenceReleaseAdapterSpec:
        key = (
            operation
            if isinstance(operation, ReferenceReleaseOperation)
            else ReferenceReleaseOperation(operation)
        )
        return next(item for item in self.adapters if item.operation is key)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_reference_release_adapters() -> ReferenceReleaseAdapterRegistry:
    """Return four deterministic, network-free adapter declarations."""

    contracts = default_reference_release_contracts()
    adapters = tuple(
        ReferenceReleaseAdapterSpec(
            adapter_id=f"reference-release-adapter:{index:02d}",
            capability_id=contracts.by_operation(operation).capability_id,
            operation=operation,
            input_contract=contracts.by_operation(operation).content_address,
            output_contract=contracts.by_operation(operation).content_address,
            deterministic=True,
            network_required=False,
            mutation_scope="none",
            boundary="public_aggregate_non_patient",
            content_address=content_hash(
                {
                    "operation": operation,
                    "capability_id": contracts.by_operation(operation).capability_id,
                },
                prefix="adapter",
            ),
        )
        for index, operation in enumerate(ReferenceReleaseOperation, start=1)
    )
    body = {"adapters": adapters}
    return ReferenceReleaseAdapterRegistry(adapters, content_hash(body, prefix="adapter-registry"))


def verify_reference_release_adapters(registry: ReferenceReleaseAdapterRegistry) -> tuple[str, ...]:
    """Return adapter completeness and safety failures."""

    failures: list[str] = []
    if len(registry.adapters) != 4:
        failures.append("adapter-count")
    if {item.operation for item in registry.adapters} != set(ReferenceReleaseOperation):
        failures.append("operation-coverage")
    if any(not item.deterministic for item in registry.adapters):
        failures.append("nondeterministic-adapter")
    if any(item.network_required for item in registry.adapters):
        failures.append("network-adapter")
    if any(item.mutation_scope != "none" for item in registry.adapters):
        failures.append("mutation-scope")
    if any(not item.content_address.startswith("adapter:") for item in registry.adapters):
        failures.append("adapter-address")
    if not registry.content_address.startswith("adapter-registry:"):
        failures.append("registry-address")
    return tuple(failures)


__all__ = [
    "ReferenceReleaseAdapterRegistry",
    "ReferenceReleaseAdapterSpec",
    "default_reference_release_adapters",
    "verify_reference_release_adapters",
]
