"""Shared receipts for editing-design assurance planes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignReceipt:
    name: str
    accepted: bool
    values: Mapping[str, Any]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def receipt(name: str, accepted: bool, values: Mapping[str, Any]) -> EditingDesignReceipt:
    body = {"name": name, "accepted": bool(accepted), "values": jsonable(values)}; return EditingDesignReceipt(**body, content_address=content_hash(body))

def state_counts(evaluation: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in evaluation.executions: counts[row.observed_state.value] = counts.get(row.observed_state.value, 0) + 1
    return dict(sorted(counts.items()))

def operation_counts(evaluation: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in evaluation.executions: counts[row.operation.value] = counts.get(row.operation.value, 0) + 1
    return dict(sorted(counts.items()))

def issue_counts(evaluation: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in evaluation.executions:
        for issue in row.issue_codes: counts[issue] = counts.get(issue, 0) + 1
    return dict(sorted(counts.items()))

def addresses_closed(values: Iterable[Any]) -> bool: return all(str(getattr(value, "content_address", "")).startswith("sha256:") for value in values)

__all__ = ["EditingDesignReceipt", "addresses_closed", "issue_counts", "operation_counts", "receipt", "state_counts"]
