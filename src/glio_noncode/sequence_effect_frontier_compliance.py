"""Data-boundary compliance report for sequence-effect surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .sequence_effect_frontier_runtime import SequenceEffectRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectBoundaryReport:
    accepted: bool
    checks: tuple[dict[str, Any], ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"accepted": self.accepted, "checks": self.checks}),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_sequence_effect_boundary(
    fixture: SequenceEffectFixture, runtime: SequenceEffectRuntimeReport
) -> SequenceEffectBoundaryReport:
    checks = tuple(
        {"check_id": check_id, "passed": passed, "detail": detail}
        for check_id, passed, detail in (
            (
                "boundary-name",
                fixture.evidence_boundary == "public_aggregate_non_patient",
                "public aggregate boundary is exact",
            ),
            (
                "source-public",
                all(
                    source.public_aggregate and not source.patient_level
                    for source in fixture.sources
                ),
                "sources are public aggregate",
            ),
            (
                "record-context",
                all(item.context_key == fixture.context_key for item in fixture.records),
                "record context is exact",
            ),
            (
                "runtime-context",
                runtime.stages[0].status == "accepted",
                "runtime data boundary accepted",
            ),
            (
                "no-raw-subject-field",
                all(
                    not any(
                        key.lower() in {"subject", "patient", "sample_id", "donor_id"}
                        for key in item.payload
                    )
                    for item in fixture.records
                ),
                "subject fields are absent",
            ),
            (
                "addressed-sources",
                all(source.content_address.startswith("sha256:") for source in fixture.sources),
                "sources are addressed",
            ),
        )
    )
    return SequenceEffectBoundaryReport(all(item["passed"] for item in checks), checks)


__all__ = ["SequenceEffectBoundaryReport", "audit_sequence_effect_boundary"]
