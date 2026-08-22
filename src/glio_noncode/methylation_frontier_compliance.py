"""Boundary and serialized-output compliance for methylation evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_public_data import MethylationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierBoundaryCheck:
    check_id: str
    passed: bool
    severity: str
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail or self.severity not in {"blocking", "advisory"}:
            raise ValidationError("boundary check is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierBoundaryReport:
    fixture_id: str
    checks: tuple[MethylationFrontierBoundaryCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("boundary report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    @property
    def blocking_failures(self) -> tuple[str, ...]:
        return tuple(
            check.check_id
            for check in self.checks
            if not check.passed and check.severity == "blocking"
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "blocking_failures": list(self.blocking_failures),
        }


def _check(
    index: int, passed: bool, severity: str, observed: Any, required: Any, detail: str
) -> MethylationFrontierBoundaryCheck:
    return MethylationFrontierBoundaryCheck(
        check_id=f"methylation-boundary-{index:03d}",
        passed=passed,
        severity=severity,
        observed=observed,
        required=required,
        detail=detail,
    )


def _mapping_keys(value: Any) -> tuple[str, ...]:
    return tuple(str(key).lower() for key in value) if isinstance(value, dict) else ()


def evaluate_methylation_frontier_boundary(
    fixture: MethylationFrontierFixture,
    evaluation: MethylationFrontierEvaluation,
) -> MethylationFrontierBoundaryReport:
    """Check public boundary, secure receipts, and absence of subject fields."""

    forbidden = {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
    output_keys = tuple(
        key for item in evaluation.records for key in _mapping_keys(item.adapter.measurements)
    )
    checks = (
        _check(
            1,
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "blocking",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
            "evidence boundary is explicit",
        ),
        _check(
            2,
            bool(fixture.context_key),
            "blocking",
            fixture.context_key,
            "non-empty context",
            "context is explicit",
        ),
        _check(
            3,
            all(source.uri.startswith("https://") for source in fixture.sources),
            "blocking",
            len(fixture.sources),
            "secure source URIs",
            "source receipts use secure URIs",
        ),
        _check(
            4,
            all(source.checksum and source.source_version for source in fixture.sources),
            "blocking",
            len(fixture.sources),
            "versioned checksums",
            "source identity is reproducible",
        ),
        _check(
            5,
            all(
                not (set(str(key).lower() for key in record.payload) & forbidden)
                for record in fixture.records
            ),
            "blocking",
            len(fixture.records),
            "no subject keys",
            "fixture payloads exclude subject-level fields",
        ),
        _check(
            6,
            not (set(output_keys) & forbidden),
            "blocking",
            sorted(set(output_keys)),
            "no subject keys",
            "derived measurements exclude subject-level fields",
        ),
        _check(
            7,
            all(record.context_key == fixture.context_key for record in fixture.records),
            "blocking",
            len(fixture.records),
            "locked context",
            "records retain the declared context",
        ),
        _check(
            8,
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "blocking",
            len(fixture.records),
            "content receipts",
            "record receipts are stable",
        ),
        _check(
            9,
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "blocking",
            len(evaluation.records),
            "result receipts",
            "result receipts are stable",
        ),
        _check(
            10,
            len(fixture.positive_records) == 4 and len(fixture.control_records) == 12,
            "blocking",
            (len(fixture.positive_records), len(fixture.control_records)),
            (4, 12),
            "positive and control balance is explicit",
        ),
        _check(
            11,
            any(item.observed_state.value == "out_of_domain" for item in evaluation.records),
            "advisory",
            True,
            True,
            "out-of-domain behavior remains visible",
        ),
        _check(
            12,
            any(item.observed_state.value == "abstained" for item in evaluation.records),
            "advisory",
            True,
            True,
            "abstention behavior remains visible",
        ),
    )
    blocking = tuple(check for check in checks if check.severity == "blocking" and not check.passed)
    return MethylationFrontierBoundaryReport(fixture.fixture_id, checks, not blocking)


__all__ = [
    "MethylationFrontierBoundaryCheck",
    "MethylationFrontierBoundaryReport",
    "evaluate_methylation_frontier_boundary",
]
