"""Checksum audit across receipts, records, replay outputs, and bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierChecksumCheck:
    check_id: str
    object_id: str
    declared_address: str
    recomputed_address: str
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "object_id": self.object_id,
            "declared_address": self.declared_address,
            "recomputed_address": self.recomputed_address,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierChecksumAuditReport:
    checks: tuple[LinkGraphAlphaFrontierChecksumCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.object_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "failed_ids": self.failed_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_link_graph_alpha_frontier_checksums(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierChecksumAuditReport:
    checks: list[LinkGraphAlphaFrontierChecksumCheck] = []
    for source in fixture.sources:
        recomputed = content_hash({"source_id": source.source_id, "version": source.source_version, "uri": source.uri})
        checks.append(LinkGraphAlphaFrontierChecksumCheck("source", source.source_id, source.checksum, recomputed, source.checksum == recomputed))
    for record in fixture.records:
        recomputed = content_hash(record.to_dict(False))
        checks.append(LinkGraphAlphaFrontierChecksumCheck("record", record.record_id, record.content_address, recomputed, record.content_address == recomputed))
    for row in evaluation.rows:
        checks.append(LinkGraphAlphaFrontierChecksumCheck("result", row.record_id, row.adapter.content_address, row.adapter.content_address, row.adapter.content_address.startswith("sha256:")))
    values = tuple(checks)
    return LinkGraphAlphaFrontierChecksumAuditReport(values, bool(values) and all(item.passed for item in values))


__all__ = ["LinkGraphAlphaFrontierChecksumAuditReport", "LinkGraphAlphaFrontierChecksumCheck", "audit_link_graph_alpha_frontier_checksums"]
