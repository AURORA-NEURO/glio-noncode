"""Source-to-case-to-receipt lineage for D07."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureLineageLink:
    link_id: str
    source_id: str
    operation_id: str
    case_id: str
    receipt_address: str
    family: str
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureLineage:
    fixture_id: str
    links: tuple[ChromatinArchitectureLineageLink, ...]
    source_count: int
    case_count: int
    receipt_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_architecture_lineage(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitectureLineage:
    receipt_map = {item.case_id: item for item in evaluation.receipts}
    links: list[ChromatinArchitectureLineageLink] = []
    for case in fixture.cases:
        receipt = receipt_map[case.case_id]
        for source_id in case.source_ids:
            body = {
                "source_id": source_id,
                "operation_id": case.operation_id,
                "case_id": case.case_id,
                "receipt_address": receipt.content_address,
                "family": case.family,
                "context_key": case.context_key,
            }
            links.append(
                ChromatinArchitectureLineageLink(
                    link_id=f"{case.case_id}:{source_id}",
                    **body,
                    content_address=addressed(body, "chromatin-lineage-link"),
                )
            )
    values = tuple(links)
    body = {"fixture_id": fixture.fixture_id, "links": values}
    return ChromatinArchitectureLineage(
        fixture_id=fixture.fixture_id,
        links=values,
        source_count=len(fixture.sources),
        case_count=len(fixture.cases),
        receipt_count=len(evaluation.receipts),
        accepted=bool(values)
        and all(item.content_address.startswith("sha256:") for item in values),
        content_address=addressed(body, "chromatin-lineage"),
    )


def verify_chromatin_architecture_lineage(
    lineage: ChromatinArchitectureLineage,
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
) -> bool:
    source_ids = {item.source_id for item in fixture.sources}
    case_ids = {item.case_id for item in fixture.cases}
    receipt_addresses = {item.content_address for item in evaluation.receipts}
    return (
        lineage.accepted
        and lineage.source_count == len(source_ids)
        and lineage.case_count == len(case_ids)
        and lineage.receipt_count == len(evaluation.receipts)
        and all(item.source_id in source_ids for item in lineage.links)
        and all(item.case_id in case_ids for item in lineage.links)
        and all(item.receipt_address in receipt_addresses for item in lineage.links)
    )


__all__ = [
    "ChromatinArchitectureLineage",
    "ChromatinArchitectureLineageLink",
    "build_chromatin_architecture_lineage",
    "verify_chromatin_architecture_lineage",
]
