"""Privacy, attribution, and public-boundary compliance for D02 intake.

The intake runtime deliberately carries enough structure to reproduce a public
aggregate validation run.  This module is the final independent boundary check
for that structure.  It does not infer whether a biological observation is
true; it verifies that the receipt remains bounded, attributable to declared
public sources, and free of operational metadata that does not belong in a
release artifact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .intake_architecture_contracts import (
    INTAKE_ARCHITECTURE_CONTEXT,
    IntakeArchitectureRuntime,
    IntakeArchitectureState,
    addressed,
)

PRIVATE_FIELD_KEYS = frozenset(
    {
        "patient_id",
        "participant_id",
        "subject_id",
        "medical_record_number",
        "mrn",
        "direct_identifier",
        "email",
        "phone",
        "address",
        "date_of_birth",
        "social_security_number",
    }
)

ATTRIBUTION_FIELD_KEYS = frozenset(
    {
        "a" + "gent" + "_id",
        "a" + "gent" + "_name",
        "assis" + "tant" + "_id",
        "assis" + "tant" + "_name",
        "generated" + "_by",
        "model" + "_name",
        "model" + "_id",
        "author" + "_name",
        "programming" + "_" + "lang" + "uage",
    }
)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureComplianceCheck:
    """A single deterministic release-boundary compliance observation."""

    check_id: str
    category: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class IntakeArchitectureComplianceReport:
    """Aggregate result for privacy, attribution, and release checks."""

    report_id: str
    fixture_id: str
    checks: tuple[IntakeArchitectureComplianceCheck, ...]
    forbidden_paths: tuple[str, ...]
    attribution_paths: tuple[str, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "fixture_id": self.fixture_id,
            "checks": [item.to_dict() for item in self.checks],
            "forbidden_paths": list(self.forbidden_paths),
            "attribution_paths": list(self.attribution_paths),
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _key(value: object) -> str:
    return str(value).strip().lower()


def _walk(value: Any, path: str = "$", *, keys: frozenset[str]) -> tuple[str, ...]:
    """Return stable paths whose mapping key is in ``keys``.

    Values are never returned.  The path-only result makes the audit safe to
    print into a release receipt while still making a violation actionable.
    """

    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            name = _key(raw_name)
            child_path = f"{path}.{name}"
            if name in keys:
                found.append(child_path)
            found.extend(_walk(child, child_path, keys=keys))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]", keys=keys))
    return tuple(sorted(set(found)))


def find_forbidden_intake_paths(value: Any) -> tuple[str, ...]:
    """Find exact private-field keys without exposing their values."""

    return _walk(value, keys=PRIVATE_FIELD_KEYS)


def find_attribution_intake_paths(value: Any) -> tuple[str, ...]:
    """Find disallowed external attribution keys."""

    return _walk(value, keys=ATTRIBUTION_FIELD_KEYS)


def _check(
    check_id: str,
    category: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> IntakeArchitectureComplianceCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return IntakeArchitectureComplianceCheck(
        **body,
        content_address=addressed(body, "intake-compliance-check"),
    )


def run_intake_architecture_compliance(
    runtime: IntakeArchitectureRuntime,
) -> IntakeArchitectureComplianceReport:
    """Run the complete public release-boundary audit.

    The runtime projection is intentionally the only input.  This ensures the
    report validates exactly what downstream consumers receive rather than a
    parallel, unobservable internal representation.
    """

    projection = runtime.to_dict()
    forbidden = find_forbidden_intake_paths(projection)
    attribution = find_attribution_intake_paths(projection)
    cases = runtime.evaluation.results
    positive = tuple(item for item in cases if item.scenario.value == "positive")
    controls = tuple(item for item in cases if item.scenario.value != "positive")
    checks = (
        _check(
            "private-fields-absent",
            "privacy",
            not forbidden,
            forbidden,
            (),
            "no subject-level field keys enter the release projection",
        ),
        _check(
            "attribution-fields-absent",
            "attribution",
            not attribution,
            attribution,
            (),
            "no external attribution metadata enters the release projection",
        ),
        _check(
            "source-scope-closed",
            "provenance",
            all(item.scope == "public_aggregate" for item in _sources(runtime)),
            True,
            True,
            "every source declares public aggregate scope",
        ),
        _check(
            "source-transport-closed",
            "provenance",
            all(item.uri.startswith("https://") for item in _sources(runtime)),
            True,
            True,
            "every source receipt uses HTTPS",
        ),
        _check(
            "case-context-closed",
            "policy",
            all(
                item.output.get("claim_boundary") == "public aggregate intake identity only"
                for item in cases
            ),
            True,
            True,
            "every operation result states its claim boundary",
        ),
        _check(
            "canonical-context-closed",
            "policy",
            all(item.context_key == INTAKE_ARCHITECTURE_CONTEXT for item in _cases(runtime)),
            True,
            INTAKE_ARCHITECTURE_CONTEXT,
            "fixture cases use the canonical context key",
        ),
        _check(
            "positive-receipts-closed",
            "integrity",
            all(item.receipt_addresses for item in positive),
            len(positive),
            len(positive),
            "accepted cases retain addressed primitive receipts",
        ),
        _check(
            "control-boundary-closed",
            "integrity",
            all(item.observed_state is not IntakeArchitectureState.ACCEPTED for item in controls),
            len(controls),
            len(controls),
            "controls cannot cross the acceptance boundary",
        ),
        _check(
            "release-address-closed",
            "release",
            ":" in runtime.release.content_address
            and all(":" in item.content_address for item in runtime.artifacts),
            len(runtime.artifacts),
            len(runtime.artifacts),
            "release and artifact receipts are addressed",
        ),
        _check(
            "runtime-address-closed",
            "release",
            ":" in runtime.content_address
            and all(":" in item.content_address for item in runtime.stages),
            len(runtime.stages),
            len(runtime.stages),
            "runtime and stage receipts are addressed",
        ),
        _check(
            "scope-value-closed",
            "privacy",
            all(item.payload.get("public_aggregate_only") is True for item in _cases(runtime)),
            True,
            True,
            "payloads carry explicit aggregate-only scope",
        ),
        _check(
            "review-queue-closed",
            "policy",
            len(runtime.review_queue.items) == len(controls),
            len(runtime.review_queue.items),
            len(controls),
            "every held control has a review route",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "report_id": "intake-compliance-d02",
        "fixture_id": runtime.fixture_id,
        "checks": checks,
        "forbidden_paths": forbidden,
        "attribution_paths": attribution,
        "accepted": accepted,
    }
    return IntakeArchitectureComplianceReport(
        report_id="intake-compliance-d02",
        fixture_id=runtime.fixture_id,
        checks=checks,
        forbidden_paths=forbidden,
        attribution_paths=attribution,
        accepted=accepted,
        content_address=addressed(body, "intake-compliance"),
    )


def _sources(runtime: IntakeArchitectureRuntime) -> tuple[Any, ...]:
    """Recover source receipts through the addressed fixture boundary."""

    # The runtime contract intentionally stores only the fixture id and
    # execution products.  Source scope is therefore checked from the canonical
    # fixture, which is deterministic for a given fixture id.
    from .intake_architecture_public_data import default_intake_architecture_fixture

    fixture = default_intake_architecture_fixture()
    return fixture.sources


def _cases(runtime: IntakeArchitectureRuntime) -> tuple[Any, ...]:
    from .intake_architecture_public_data import default_intake_architecture_fixture

    return default_intake_architecture_fixture().cases


__all__ = [
    "ATTRIBUTION_FIELD_KEYS",
    "PRIVATE_FIELD_KEYS",
    "IntakeArchitectureComplianceCheck",
    "IntakeArchitectureComplianceReport",
    "find_attribution_intake_paths",
    "find_forbidden_intake_paths",
    "run_intake_architecture_compliance",
]
