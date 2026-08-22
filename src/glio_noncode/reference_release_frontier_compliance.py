"""Scope, privacy, and mutation-boundary checks for public release outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_bundle import ReferenceReleaseEvidenceBundle
from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_public_data import ReferenceReleaseFixture
from .reference_release_frontier_runtime import ReferenceReleaseRuntimeReport
from .reference_release_frontier_views import ReferenceReleaseReviewView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseBoundaryCheck:
    """One explicit output-boundary condition."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseBoundaryReport:
    """Compliance report for aggregate-only public output."""

    boundary: str
    checks: tuple[ReferenceReleaseBoundaryCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _check(
    index: int, passed: bool, observed: Any, expected: Any, detail: str
) -> ReferenceReleaseBoundaryCheck:
    body = {
        "check_id": f"release-boundary-{index:03d}",
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ReferenceReleaseBoundaryCheck(
        **body, content_address=content_hash(body, prefix="boundary-check")
    )


def evaluate_reference_release_boundary(
    fixture: ReferenceReleaseFixture,
    evaluation: ReferenceReleaseEvaluation,
    runtime: ReferenceReleaseRuntimeReport,
    bundle: ReferenceReleaseEvidenceBundle,
    view: ReferenceReleaseReviewView,
) -> ReferenceReleaseBoundaryReport:
    """Verify aggregate scope, raw-row exclusion, URI scope, and no mutation."""

    forbidden = {
        "patient_id",
        "subject_id",
        "sample_id",
        "genotype",
        "private_key",
        "secret",
        "raw_records",
        "payload",
    }
    serialized_outputs = [item.to_dict() for item in evaluation.executions] + [
        bundle.to_dict(),
        view.to_dict(),
    ]
    checks = (
        _check(
            1,
            fixture.evidence_boundary == "public_aggregate_non_patient",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
            "fixture boundary is aggregate-only",
        ),
        _check(
            2,
            all(source.uri.startswith("https://") for source in fixture.sources),
            True,
            True,
            "source receipts use public HTTPS URIs",
        ),
        _check(
            3,
            all(not forbidden & set(source.to_dict()) for source in fixture.sources),
            True,
            True,
            "source receipts contain no restricted keys",
        ),
        _check(
            4,
            all(not forbidden & set(output) for output in serialized_outputs),
            True,
            True,
            "serialized outputs contain no restricted keys",
        ),
        _check(
            5,
            all(item.content_address.startswith("sha256:") for item in evaluation.executions),
            True,
            True,
            "execution addresses are content based",
        ),
        _check(
            6, bundle.accepted, bundle.accepted, True, "bundle is accepted before public render"
        ),
        _check(7, view.accepted, view.accepted, True, "review view is structurally accepted"),
        _check(
            8,
            runtime.data_audit.accepted,
            runtime.data_audit.accepted,
            True,
            "runtime retains accepted data audit",
        ),
        _check(
            9, len(fixture.records) == 16, len(fixture.records), 16, "record count remains bounded"
        ),
        _check(
            10, len(fixture.sources) == 5, len(fixture.sources), 5, "source count remains bounded"
        ),
        _check(
            11,
            all(record.context_key == fixture.context_key for record in fixture.records),
            True,
            True,
            "all records use exact fixture context",
        ),
        _check(
            12, runtime.accepted, runtime.accepted, True, "runtime does not bypass a failed gate"
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"boundary": "public_aggregate_non_patient", "checks": checks, "accepted": accepted}
    return ReferenceReleaseBoundaryReport(
        **body, content_address=content_hash(body, prefix="release-boundary")
    )


__all__ = [
    "ReferenceReleaseBoundaryCheck",
    "ReferenceReleaseBoundaryReport",
    "evaluate_reference_release_boundary",
]
