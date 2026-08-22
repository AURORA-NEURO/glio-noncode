"""Boundary compliance checks for public aggregate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_public_data import SequenceRegulationFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationBoundaryCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("boundary check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationBoundaryReport:
    checks: tuple[SequenceRegulationBoundaryCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("boundary report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_sequence_regulation_boundary(
    fixture: SequenceRegulationFixture,
) -> SequenceRegulationBoundaryReport:
    forbidden = {"patient", "subject", "sample_id", "donor_id", "participant_id"}
    checks = (
        SequenceRegulationBoundaryCheck(
            "public_aggregate",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "fixture has public aggregate boundary",
        ),
        SequenceRegulationBoundaryCheck(
            "source_flags",
            all(source.public_aggregate and not source.patient_level for source in fixture.sources),
            "source flags are aggregate",
        ),
        SequenceRegulationBoundaryCheck(
            "payload_keys",
            all(
                not forbidden & {str(key).lower() for key in record.payload}
                for record in fixture.records
            ),
            "payloads contain no subject fields",
        ),
        SequenceRegulationBoundaryCheck(
            "context_key", bool(fixture.context_key), "context key is present"
        ),
        SequenceRegulationBoundaryCheck(
            "record_context",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "record contexts are locked",
        ),
        SequenceRegulationBoundaryCheck(
            "source_uris",
            all(source.uri.startswith("https://") for source in fixture.sources),
            "source references use HTTPS",
        ),
    )
    return SequenceRegulationBoundaryReport(checks, all(check.passed for check in checks))


__all__ = [
    "SequenceRegulationBoundaryCheck",
    "SequenceRegulationBoundaryReport",
    "audit_sequence_regulation_boundary",
]
