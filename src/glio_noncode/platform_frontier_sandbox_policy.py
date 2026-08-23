"""Independent admission audit for local execution isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mission_runtime import SandboxAdmission, SandboxIsolation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierSandboxPolicyCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierSandboxPolicyReport:
    checks: tuple[PlatformFrontierSandboxPolicyCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_platform_frontier_sandbox_policy(admission: SandboxAdmission, isolation: SandboxIsolation) -> PlatformFrontierSandboxPolicyReport:
    values = (("admission-address", admission.content_address.startswith("sha256:"), True), ("workspace", bool(isolation.workspace_root), True), ("dynamic-imports", isolation.allow_dynamic_imports, False), ("external-processes", isolation.allow_external_processes, False), ("network-list", not isolation.allow_network or bool(isolation.allowed_source_ids), True), ("reason", bool(admission.reason), True))
    checks = []
    for check_id, observed, required in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required}
        checks.append(PlatformFrontierSandboxPolicyCheck(**body, content_address=content_hash(body)))
    return PlatformFrontierSandboxPolicyReport(tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["PlatformFrontierSandboxPolicyCheck", "PlatformFrontierSandboxPolicyReport", "audit_platform_frontier_sandbox_policy"]
