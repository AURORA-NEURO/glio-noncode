"""Shared deterministic receipts for validation-design assurance planes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignReceipt:
    name: str
    accepted: bool
    values: Mapping[str, Any]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def receipt(name: str, accepted: bool, values: Mapping[str, Any]) -> ValidationDesignReceipt:
    body = {"name": name, "accepted": bool(accepted), "values": jsonable(values)}
    return ValidationDesignReceipt(**body, content_address=content_hash(body))

def state_counts(evaluation: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in evaluation.executions:
        value = row.observed_state.value
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))

def operation_counts(evaluation: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in evaluation.executions:
        value = row.operation.value
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))

def issue_counts(evaluation: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in evaluation.executions:
        for issue in row.issue_codes:
            counts[issue] = counts.get(issue, 0) + 1
    return dict(sorted(counts.items()))

def addresses(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(getattr(value, "content_address", "")) for value in values)

def addresses_closed(values: Iterable[Any]) -> bool:
    return all(value.startswith("sha256:") for value in addresses(values))

def public_only(fixture: Any) -> bool:
    return fixture.evidence_boundary == "public_aggregate_validation_design_planning" and all(source.uri.startswith("https://") for source in fixture.sources)

__all__ = ["ValidationDesignReceipt", "addresses", "addresses_closed", "issue_counts", "operation_counts", "public_only", "receipt", "state_counts"]
