"""Shared validation and state helpers for the C09-C12 release surface."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .causal_reasoning import CausalState
from .errors import ValidationError
from .serialization import content_hash


def require_context(context_key: str, expected: str) -> None:
    """Reject empty context coordinates and make comparison explicit."""

    if not str(context_key).strip() or not str(expected).strip():
        raise ValidationError("causal alpha frontier context is required")


def aggregate_state(states: Iterable[CausalState]) -> CausalState:
    """Combine row states using the strictest release ordering."""

    values = tuple(states)
    if not values:
        return CausalState.ABSTAINED
    precedence = {
        CausalState.OUT_OF_DOMAIN: 6,
        CausalState.CONTRADICTORY: 5,
        CausalState.MEASURED_NEGATIVE: 4,
        CausalState.PARTIAL: 3,
        CausalState.ABSTAINED: 2,
        CausalState.SUPPORTED: 1,
    }
    return max(values, key=lambda item: precedence.get(item, 0))


def stable_ids(values: Iterable[Any], key: str = "id") -> tuple[str, ...]:
    """Return deterministic IDs from mapping or object records."""

    output: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            candidate = value.get(key, value.get("evidence_id", value.get("record_id", "")))
        else:
            candidate = getattr(value, key, "")
        if str(candidate).strip():
            output.append(str(candidate))
    return tuple(sorted(dict.fromkeys(output)))


def issue_codes(output: Any) -> tuple[str, ...]:
    """Normalize issue objects and add an explicit mismatch code when needed."""

    values = {str(getattr(item, "code", item)) for item in getattr(output, "issues", ())}
    if getattr(output, "state", None) is CausalState.OUT_OF_DOMAIN:
        values.add("context_mismatch")
    return tuple(sorted(values))


def output_address(output: Any) -> str:
    """Use the operation address when available, otherwise hash its envelope."""

    address = getattr(output, "content_address", "")
    return str(address) if str(address).strip() else content_hash(output.to_dict())


def as_json_records(values: Iterable[Any]) -> tuple[dict[str, Any], ...]:
    """Normalize dataclass-like outputs for exports without mutable aliases."""

    return tuple(dict(value.to_dict()) for value in values)


__all__ = ["aggregate_state", "as_json_records", "issue_codes", "output_address", "require_context", "stable_ids"]
