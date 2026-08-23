"""Idempotency lock receipts for replay-safe runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleaseLockReceipt:
    run_id: str
    lock_key: str
    acquired: bool
    reused: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def acquire_validation_release_lock(run_id: str, lock_key: str, existing_keys: tuple[str, ...] = ()) -> ValidationReleaseLockReceipt:
    reused = lock_key in existing_keys
    body = {"run_id": run_id, "lock_key": lock_key, "acquired": True, "reused": reused}
    return ValidationReleaseLockReceipt(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseLockReceipt", "acquire_validation_release_lock"]
