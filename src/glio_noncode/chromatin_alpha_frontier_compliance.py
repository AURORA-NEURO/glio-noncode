"""Boundary compliance for C09-C12 aggregate chromatin evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierBoundaryCheck:
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
class ChromatinAlphaFrontierBoundaryReport:
    fixture_id: str
    checks: tuple[ChromatinAlphaFrontierBoundaryCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("boundary report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def blocking_failures(self) -> tuple[str, ...]:
        return tuple(
            check.check_id
            for check in self.checks
            if not check.passed and check.severity == "blocking"
        )

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "blocking_failures": list(self.blocking_failures),
            "passed_count": self.passed_count,
        }


def _check(
    index: int, passed: bool, severity: str, observed: Any, required: Any, detail: str
) -> ChromatinAlphaFrontierBoundaryCheck:
    return ChromatinAlphaFrontierBoundaryCheck(
        f"chromatin-alpha-boundary-{index:03d}", passed, severity, observed, required, detail
    )


def evaluate_chromatin_alpha_frontier_boundary(
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> ChromatinAlphaFrontierBoundaryReport:
    forbidden = {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
    payload_keys = tuple(str(key).lower() for record in fixture.records for key in record.payload)
    measurements = tuple(
        str(key).lower() for item in evaluation.records for key in item.adapter.measurements
    )
    checks = (
        _check(
            1,
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "blocking",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
            "boundary is explicit",
        ),
        _check(
            2,
            bool(fixture.context_key),
            "blocking",
            fixture.context_key,
            "locked context",
            "context is explicit",
        ),
        _check(
            3,
            all(source.uri.startswith("https://") for source in fixture.sources),
            "blocking",
            len(fixture.sources),
            "HTTPS receipts",
            "source URIs are secure",
        ),
        _check(
            4,
            all(source.release and source.content_address for source in fixture.sources),
            "blocking",
            len(fixture.sources),
            "versioned receipts",
            "source releases and addresses are retained",
        ),
        _check(
            5,
            not (set(payload_keys) & forbidden),
            "blocking",
            sorted(set(payload_keys) & forbidden),
            "no subject-level keys",
            "fixture payload keys remain aggregate",
        ),
        _check(
            6,
            not (set(measurements) & forbidden),
            "blocking",
            sorted(set(measurements) & forbidden),
            "no subject-level keys",
            "derived fields remain aggregate",
        ),
        _check(
            7,
            all(record.context_key == fixture.context_key for record in fixture.records),
            "blocking",
            len(fixture.records),
            len(fixture.records),
            "record context is locked",
        ),
        _check(
            8,
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "blocking",
            len(fixture.records),
            len(fixture.records),
            "record receipts are stable",
        ),
        _check(
            9,
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "blocking",
            len(evaluation.records),
            len(evaluation.records),
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
            any(item.observed_state == "out_of_domain" for item in evaluation.records),
            "advisory",
            True,
            True,
            "foreign-context behavior is visible",
        ),
        _check(
            12,
            any(item.observed_state == "ambiguous" for item in evaluation.records),
            "advisory",
            True,
            True,
            "mixed-signal behavior is visible",
        ),
        _check(
            13,
            any(item.observed_state == "partial" for item in evaluation.records),
            "advisory",
            True,
            True,
            "partial behavior is visible",
        ),
    )
    blocking = tuple(check for check in checks if check.severity == "blocking" and not check.passed)
    return ChromatinAlphaFrontierBoundaryReport(fixture.fixture_id, checks, not blocking)


__all__ = [
    "ChromatinAlphaFrontierBoundaryCheck",
    "ChromatinAlphaFrontierBoundaryReport",
    "evaluate_chromatin_alpha_frontier_boundary",
]
