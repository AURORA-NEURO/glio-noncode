"""Index of content addresses across fixture, result, and policy objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAddressEntry:
    object_id: str
    object_type: str
    address: str
    parent_addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAddressIndex:
    entries: tuple[CohortAlphaFrontierAddressEntry, ...]
    unique_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_address_index(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierAddressIndex:
    entries = [
        CohortAlphaFrontierAddressEntry(
            fixture.fixture_id,
            "fixture",
            fixture.content_address,
            tuple(source.content_address for source in fixture.sources),
            content_hash({"id": fixture.fixture_id, "type": "fixture", "address": fixture.content_address}, prefix="alpha-address-entry"),
        )
    ]
    for row in evaluation.rows:
        decision = policy.for_record(row.record_id)
        entries.append(
            CohortAlphaFrontierAddressEntry(
                row.record_id,
                "result",
                row.content_address,
                (fixture.content_address,),
                content_hash({"id": row.record_id, "type": "result", "address": row.content_address, "policy": decision.content_address}, prefix="alpha-address-entry"),
            )
        )
    values = tuple(entries)
    addresses = tuple(item.address for item in values)
    return CohortAlphaFrontierAddressIndex(
        values,
        len(set(addresses)),
        len(values) == 17 and len(set(addresses)) == len(values) and all(item.address for item in values),
        content_hash(values, prefix="alpha-address-index"),
    )


__all__ = ["CohortAlphaFrontierAddressEntry", "CohortAlphaFrontierAddressIndex", "build_cohort_alpha_frontier_address_index"]
