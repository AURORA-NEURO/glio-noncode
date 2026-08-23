"""Deterministic idempotency lock receipts for deployment runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_support import deployment_address
from .serialization import jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class DeploymentFrontierLockReceipt:
    run_id: str
    idempotency_key: str
    acquired: bool
    reused: bool
    scope: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def acquire_deployment_frontier_lock(run_id: str, idempotency_key: str, *, existing_keys: tuple[str, ...] = (), scope: str = "deployment-frontier") -> DeploymentFrontierLockReceipt:
    require_non_empty(run_id, "run_id")
    require_non_empty(idempotency_key, "idempotency_key")
    reused = idempotency_key in existing_keys
    body = {"run_id": run_id, "idempotency_key": idempotency_key, "acquired": not reused, "reused": reused, "scope": scope}
    return DeploymentFrontierLockReceipt(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierLockReceipt", "acquire_deployment_frontier_lock"]
