"""Shared typed receipts used by the evidence-release operational modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseReceipt:
    name: str
    accepted: bool
    values: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def receipt(name: str, accepted: bool, values: Mapping[str, Any]) -> EvidenceReleaseReceipt:
    body = {"name": name, "accepted": bool(accepted), "values": jsonable(values)}
    return EvidenceReleaseReceipt(**body, content_address=content_hash(body))


def issue_counts(evaluation: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for execution in evaluation.executions:
        for issue in execution.issue_codes:
            counts[issue] = counts.get(issue, 0) + 1
    return dict(sorted(counts.items()))


def state_counts(evaluation: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for execution in evaluation.executions:
        value = execution.observed_state.value
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def row_ids(evaluation: Any) -> tuple[str, ...]:
    return tuple(execution.record_id for execution in evaluation.executions)


def all_addresses(values: Iterable[Any]) -> bool:
    return all(isinstance(getattr(value, "content_address", None), str) and value.content_address.startswith("sha256:") for value in values)


__all__ = ["EvidenceReleaseReceipt", "all_addresses", "issue_counts", "receipt", "row_ids", "state_counts"]
