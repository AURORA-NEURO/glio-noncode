"""Invariant checks for record identity, state routing, and release closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_bundle import ReferenceReleaseEvidenceBundle
from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_public_data import ReferenceReleaseFixture
from .reference_release_frontier_release import ReferenceReleaseManifest
from .reference_release_frontier_views import ReferenceReleaseReviewView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseInvariantCheck:
    """One invariant result."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseInvariantReport:
    """Invariant result across fixture, evaluation, manifest, bundle, and view."""

    checks: tuple[ReferenceReleaseInvariantCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _check(
    index: int, passed: bool, observed: Any, expected: Any, detail: str
) -> ReferenceReleaseInvariantCheck:
    body = {
        "check_id": f"release-invariant-{index:03d}",
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ReferenceReleaseInvariantCheck(
        **body, content_address=content_hash(body, prefix="invariant-check")
    )


def run_reference_release_invariants(
    fixture: ReferenceReleaseFixture,
    evaluation: ReferenceReleaseEvaluation,
    manifest: ReferenceReleaseManifest,
    bundle: ReferenceReleaseEvidenceBundle,
    view: ReferenceReleaseReviewView,
) -> ReferenceReleaseInvariantReport:
    """Run 16 deterministic invariants across all primary release objects."""

    accepted_ids = {item.record_id for item in evaluation.executions if item.accepted}
    bundle_ids = {item.record_id for item in bundle.entries}
    checks = (
        _check(1, len(fixture.records) == 16, len(fixture.records), 16, "fixture record count"),
        _check(2, len(fixture.sources) == 5, len(fixture.sources), 5, "fixture source count"),
        _check(
            3,
            len({item.record_id for item in fixture.records}) == 16,
            True,
            True,
            "fixture record IDs unique",
        ),
        _check(
            4,
            len({item.record_id for item in evaluation.executions}) == 16,
            True,
            True,
            "execution IDs unique",
        ),
        _check(
            5,
            {item.record_id for item in fixture.records}
            == {item.record_id for item in evaluation.executions},
            True,
            True,
            "execution closes over fixture",
        ),
        _check(
            6,
            all(
                item.state == fixture.record_map()[item.record_id].expected_state
                for item in evaluation.executions
            ),
            True,
            True,
            "states equal expected state",
        ),
        _check(
            7,
            all(item.content_address.startswith("sha256:") for item in evaluation.executions),
            True,
            True,
            "execution addresses",
        ),
        _check(
            8,
            accepted_ids == bundle_ids,
            sorted(bundle_ids),
            sorted(accepted_ids),
            "bundle contains accepted executions only",
        ),
        _check(9, len(bundle.entries) == 5, len(bundle.entries), 5, "accepted bundle entry count"),
        _check(10, manifest.ready, manifest.state.value, "ready", "manifest is ready"),
        _check(
            11,
            not manifest.failed_check_ids,
            manifest.failed_check_ids,
            (),
            "manifest has no failed checks",
        ),
        _check(12, len(view.rows) == 16, len(view.rows), 16, "review view row count"),
        _check(
            13,
            all(
                row.record_id in {item.record_id for item in evaluation.executions}
                for row in view.rows
            ),
            True,
            True,
            "review rows close over executions",
        ),
        _check(
            14,
            all(item.content_address.startswith("bundle-entry:") for item in bundle.entries),
            True,
            True,
            "bundle entry addresses",
        ),
        _check(
            15,
            bundle.context_key == fixture.context_key,
            bundle.context_key,
            fixture.context_key,
            "bundle context",
        ),
        _check(
            16, view.content_address.startswith("review-view:"), True, True, "review view address"
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"checks": checks, "accepted": accepted}
    return ReferenceReleaseInvariantReport(
        **body, content_address=content_hash(body, prefix="invariant-report")
    )


__all__ = [
    "ReferenceReleaseInvariantCheck",
    "ReferenceReleaseInvariantReport",
    "run_reference_release_invariants",
]
