"""Reproducibility receipt for the complete aggregate run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationReproducibilityReceipt:
    receipt_id: str
    fixture_version: str
    fixture_address: str
    stage_addresses: tuple[str, ...]
    commands: tuple[str, ...]
    pinned_timestamp: str
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_reproducibility_receipt(fixture_version: str, fixture_address: str, stages: Iterable[Any], *, pinned_timestamp: str = "2026-08-22T00:00:00+00:00") -> CohortFoundationReproducibilityReceipt:
    addresses = tuple(item.output_address for item in stages)
    commands = tuple(f"python -m glio_noncode cohort-foundation-frontier-{item.stage_id}" for item in stages)
    body = {"fixture_version": fixture_version, "fixture_address": fixture_address, "stages": addresses, "commands": commands, "timestamp": pinned_timestamp}
    return CohortFoundationReproducibilityReceipt(content_hash((fixture_version, fixture_address, addresses), prefix="repro"), fixture_version, fixture_address, addresses, commands, pinned_timestamp, bool(addresses) and len(addresses) == len(commands), content_hash(body))


__all__ = ["CohortFoundationReproducibilityReceipt", "build_cohort_foundation_frontier_reproducibility_receipt"]
