"""Detailed control catalog plane for the D14 C13-C16 release boundary.

This module keeps one operational concern independently addressable.  Its receipt
is deliberately small enough for a review page but rich enough to preserve the
input address, the observed counts, the policy vocabulary, and the next action.
The plane does not mutate a fixture and does not infer a missing value.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseControlCatalog:
    control_count: int
    accepted: bool
    observations: tuple[dict[str, Any], ...]
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def closed(self) -> bool:
        return self.accepted and self.content_address.startswith("sha256:")


def build_evidence_release_control_catalog(values: Iterable[Any] = (), *, required: int = 1) -> EvidenceReleaseControlCatalog:
    """Build a deterministic receipt for this assurance plane."""
    materialized = tuple(values)
    observations = tuple(
        {
            "sequence": index,
            "value": jsonable(value),
            "address": content_hash(jsonable(value)),
        }
        for index, value in enumerate(materialized, start=1)
    )
    count = len(observations)
    accepted = count >= required
    next_action = "retain receipt" if accepted else "route for review"
    body = {
        "control_count": count,
        "accepted": accepted,
        "observations": observations,
        "next_action": next_action,
    }
    return EvidenceReleaseControlCatalog(
        **body,
        content_address=content_hash(body),
    )


def validate_evidence_release_control_catalog(receipt: EvidenceReleaseControlCatalog, *, expected: int | None = None) -> bool:
    """Check count, address, and explicit acceptance without side effects."""
    if not receipt.content_address.startswith("sha256:"):
        return False
    if not receipt.closed:
        return False
    if expected is not None and getattr(receipt, "control_count") != expected:
        return False
    return all(
        isinstance(item.get("address"), str)
        and item["address"].startswith("sha256:")
        for item in receipt.observations
    )


def summarize_control_catalog(receipt: EvidenceReleaseControlCatalog) -> Mapping[str, Any]:
    """Return a safe projection suitable for a release summary."""
    return {
        "count": getattr(receipt, "control_count"),
        "accepted": receipt.accepted,
        "closed": receipt.closed,
        "next_action": receipt.next_action,
        "content_address": receipt.content_address,
    }


__all__ = ["EvidenceReleaseControlCatalog", "validate_evidence_release_control_catalog", "build_evidence_release_control_catalog", "summarize_control_catalog"]
