"""Public contract catalog for module-fabric execution and release surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability_registry import CapabilityRegistry, default_capability_registry
from .module_fabric_contracts import MODULE_FABRIC_DOMAIN_NAMES, MODULE_FABRIC_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FabricDomainContract:
    domain_id: str
    domain_name: str
    capability_count: int
    mvp_count: int
    implementation_reference_count: int
    test_reference_count: int
    release_order: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricContractCatalog:
    version: str
    domains: tuple[FabricDomainContract, ...]
    operation_names: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_module_fabric_catalog(registry: CapabilityRegistry | None = None) -> FabricContractCatalog:
    catalog = registry or default_capability_registry()
    domains = []
    for index, domain_id in enumerate(sorted(MODULE_FABRIC_DOMAIN_NAMES), start=1):
        records = catalog.by_domain(domain_id)
        domains.append(
            FabricDomainContract(
                domain_id=domain_id,
                domain_name=MODULE_FABRIC_DOMAIN_NAMES[domain_id],
                capability_count=len(records),
                mvp_count=sum(item.spec.mvp_64 for item in records),
                implementation_reference_count=sum(len(item.implementation_modules) for item in records),
                test_reference_count=sum(len(item.test_modules) for item in records),
                release_order=index,
            )
        )
    body = {
        "version": MODULE_FABRIC_VERSION,
        "domains": domains,
        "operation_names": ("resolve_capability_references", "module_fabric_audit"),
    }
    return FabricContractCatalog(**body, content_address=content_hash(body, prefix="module-fabric-catalog"))


def validate_module_fabric_catalog(catalog: FabricContractCatalog | None = None) -> tuple[str, ...]:
    value = catalog or default_module_fabric_catalog()
    issues: list[str] = []
    if len(value.domains) != 16:
        issues.append("domain_count")
    if any(item.capability_count != 16 for item in value.domains):
        issues.append("capability_balance")
    if tuple(item.release_order for item in value.domains) != tuple(range(1, 17)):
        issues.append("release_order")
    if not value.operation_names:
        issues.append("operation_names")
    return tuple(issues)


__all__ = ["FabricContractCatalog", "FabricDomainContract", "default_module_fabric_catalog", "validate_module_fabric_catalog"]
