"""Deterministic lock and idempotency receipts for platform runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class PlatformFrontierLockReceipt:
    run_id: str
    idempotency_key: str
    lock_scope: str
    acquired: bool
    reused: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def acquire_platform_frontier_lock(run_id: str, idempotency_key: str, *, existing_keys: tuple[str, ...] = (), lock_scope: str = "platform-frontier") -> PlatformFrontierLockReceipt:
    require_non_empty(run_id, "run_id")
    require_non_empty(idempotency_key, "idempotency_key")
    reused = idempotency_key in existing_keys
    body = {"run_id": run_id, "idempotency_key": idempotency_key, "lock_scope": lock_scope, "acquired": not reused, "reused": reused, "reason": "idempotent replay" if reused else "new run admitted"}
    return PlatformFrontierLockReceipt(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierLockReceipt", "acquire_platform_frontier_lock"]
