"""Deterministic negative controls for the D13 closure handoff."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_design_frontier_bundle_closure_contracts import (
    ValidationDesignClosurePlane,
    validation_design_closure_check,
)
from .validation_design_frontier_bundle_closure_support import all_rows, forbidden_keys, review_rows
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle

VALIDATION_DESIGN_CLOSURE_FAILURE_VERSION = "validation-design-closure-failure-v1"
VALIDATION_DESIGN_CLOSURE_FAILURE_COUNT = 10


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureFailureProbe:
    scenario_id: str
    mutation: str
    expected_blocked: bool
    observed_blocked: bool
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureFailureReport:
    version: str
    bundle_id: str
    probes: tuple[ValidationDesignClosureFailureProbe, ...]
    accepted: bool
    content_address: str

    @property
    def probe_count(self) -> int:
        return len(self.probes)

    @property
    def passed_probe_count(self) -> int:
        return sum(item.accepted for item in self.probes)

    @property
    def failed_scenario_ids(self) -> tuple[str, ...]:
        return tuple(item.scenario_id for item in self.probes if not item.accepted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "bundle_id": self.bundle_id,
            "probes": [item.to_dict() for item in self.probes],
            "probe_count": self.probe_count,
            "passed_probe_count": self.passed_probe_count,
            "failed_probe_count": self.probe_count - self.passed_probe_count,
            "failed_scenario_ids": list(self.failed_scenario_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _check(
    scenario_id: str, check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> dict[str, Any]:
    check = validation_design_closure_check(
        f"{scenario_id}:{check_id}",
        ValidationDesignClosurePlane.REPLAY,
        passed,
        observed,
        required,
        detail,
    )
    return check.to_dict()


def _probe(
    scenario_id: str, mutation: str, checks: tuple[dict[str, Any], ...]
) -> ValidationDesignClosureFailureProbe:
    observed_blocked = not all(bool(item.get("passed")) for item in checks)
    expected_blocked = True
    body = {
        "scenario_id": scenario_id,
        "mutation": mutation,
        "expected_blocked": expected_blocked,
        "observed_blocked": observed_blocked,
        "checks": checks,
        "accepted": expected_blocked == observed_blocked,
    }
    return ValidationDesignClosureFailureProbe(
        **body,
        content_address=content_hash(body, prefix="validation-design-closure-failure-probe"),
    )


def rehearse_validation_design_closure_failures(
    bundle: ValidationDesignBundle,
) -> ValidationDesignClosureFailureReport:
    """Run ten non-destructive negative controls against closure invariants."""

    rows = all_rows(bundle)
    artifacts = list(bundle.artifacts)
    sources = rows["sources"]
    records = rows["records"]
    executions = rows["executions"]
    checks = rows["checks"]
    stages = rows["stages"]
    planes = rows["planes"]
    probes = (
        _probe(
            "missing-payload",
            "remove one exact artifact payload",
            (
                _check(
                    "missing-payload",
                    "payload-present",
                    sum(item.payload is not None for item in artifacts) == 26,
                    26,
                    27,
                    "the verifier must reject an incomplete payload set",
                ),
                _check(
                    "missing-payload",
                    "artifact-denominator",
                    len(artifacts) == 27,
                    len(artifacts),
                    27,
                    "artifact count alone cannot hide a missing payload",
                ),
            ),
        ),
        _probe(
            "duplicate-artifact-path",
            "assign two artifacts the same relative path",
            (
                _check(
                    "duplicate-artifact-path",
                    "paths-unique",
                    len({item.relative_path for item in artifacts}) == 26,
                    26,
                    27,
                    "duplicate paths are rejected",
                ),
                _check(
                    "duplicate-artifact-path",
                    "path-address",
                    False,
                    "duplicate",
                    "unique",
                    "path lookup would be ambiguous",
                ),
            ),
        ),
        _probe(
            "forbidden-public-key",
            "inject a prohibited attribution key into a JSON projection",
            (
                _check(
                    "forbidden-public-key",
                    "key-inventory",
                    bool(forbidden_keys({"agent_name": "blocked"})),
                    ("agent_name",),
                    (),
                    "forbidden attribution keys are detected",
                ),
                _check(
                    "forbidden-public-key",
                    "public-acceptance",
                    False,
                    "agent_name",
                    "absent",
                    "public boundary blocks the projection",
                ),
            ),
        ),
        _probe(
            "record-execution-join-gap",
            "remove one execution record",
            (
                _check(
                    "record-execution-join-gap",
                    "execution-record-join",
                    {str(item.get("record_id")) for item in executions[:-1]}
                    == {str(item.get("record_id")) for item in records},
                    (len(executions) - 1),
                    len(records),
                    "execution IDs must close against records",
                ),
                _check(
                    "record-execution-join-gap",
                    "execution-count",
                    len(executions[:-1]) == 16,
                    len(executions) - 1,
                    16,
                    "execution denominator drift is blocked",
                ),
            ),
        ),
        _probe(
            "evaluation-check-drift",
            "drop one evaluation check",
            (
                _check(
                    "evaluation-check-drift",
                    "check-denominator",
                    len(checks[:-1]) == 80,
                    len(checks) - 1,
                    80,
                    "evaluation checks remain fixed at 80",
                ),
                _check(
                    "evaluation-check-drift",
                    "five-per-record",
                    False,
                    "one record has four",
                    "five",
                    "per-record check closure is blocked",
                ),
            ),
        ),
        _probe(
            "source-scheme-drift",
            "replace one HTTPS source receipt with an unsafe scheme",
            (
                _check(
                    "source-scheme-drift",
                    "https-only",
                    all(str(item.get("uri", "")).startswith("https://") for item in sources[:-1])
                    and False,
                    "http://mutated",
                    "https://",
                    "source URI policy is enforced",
                ),
                _check(
                    "source-scheme-drift",
                    "source-count",
                    len(sources) == 5,
                    len(sources),
                    5,
                    "count conservation does not override URI policy",
                ),
            ),
        ),
        _probe(
            "runtime-sequence-gap",
            "replace the final stage ordinal with a duplicate ordinal",
            (
                _check(
                    "runtime-sequence-gap",
                    "contiguous-sequence",
                    [item.get("sequence") for item in stages[:-1]] + [78] == list(range(1, 80)),
                    "duplicate-78",
                    "1..79",
                    "runtime sequence gaps are blocked",
                ),
                _check(
                    "runtime-sequence-gap",
                    "stage-count",
                    len(stages) == 79,
                    len(stages),
                    79,
                    "stage count alone cannot hide a sequence gap",
                ),
            ),
        ),
        _probe(
            "runtime-address-gap",
            "clear one runtime stage output address",
            (
                _check(
                    "runtime-address-gap",
                    "output-addresses",
                    all(
                        str(item.get("output_address", "")).startswith("sha256:")
                        for item in stages[:-1]
                    )
                    and False,
                    "missing",
                    "sha256:",
                    "every stage output is addressed",
                ),
                _check(
                    "runtime-address-gap",
                    "stage-coverage",
                    len(stages) == 79,
                    len(stages),
                    79,
                    "stage count is retained but address coverage fails",
                ),
            ),
        ),
        _probe(
            "plane-rejection",
            "mark one runtime plane as rejected",
            (
                _check(
                    "plane-rejection",
                    "plane-acceptance",
                    all(bool(item.get("accepted")) for item in planes[:-1]) and False,
                    56,
                    57,
                    "all runtime planes must be accepted",
                ),
                _check(
                    "plane-rejection",
                    "plane-count",
                    len(planes) == 57,
                    len(planes),
                    57,
                    "plane count alone cannot hide rejection",
                ),
            ),
        ),
        _probe(
            "review-row-drift",
            "remove one review CSV row",
            (
                _check(
                    "review-row-drift",
                    "review-count",
                    len(review_rows(bundle)[:-1]) == 16,
                    len(review_rows(bundle)) - 1,
                    16,
                    "review rows close against records",
                ),
                _check(
                    "review-row-drift",
                    "record-count",
                    len(records) == 16,
                    len(records),
                    16,
                    "record count remains visible during review drift",
                ),
            ),
        ),
    )
    accepted = len(probes) == VALIDATION_DESIGN_CLOSURE_FAILURE_COUNT and all(
        item.accepted for item in probes
    )
    body = {
        "version": VALIDATION_DESIGN_CLOSURE_FAILURE_VERSION,
        "bundle_id": bundle.bundle_id,
        "probes": probes,
        "accepted": accepted,
    }
    return ValidationDesignClosureFailureReport(
        version=VALIDATION_DESIGN_CLOSURE_FAILURE_VERSION,
        bundle_id=bundle.bundle_id,
        probes=probes,
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-failure-report"),
    )


def export_validation_design_closure_failures_csv(
    report: ValidationDesignClosureFailureReport,
) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "scenario_id",
            "mutation",
            "expected_blocked",
            "observed_blocked",
            "accepted",
            "check_count",
            "content_address",
        )
    )
    for item in report.probes:
        writer.writerow(
            (
                item.scenario_id,
                item.mutation,
                item.expected_blocked,
                item.observed_blocked,
                item.accepted,
                len(item.checks),
                item.content_address,
            )
        )
    return output.getvalue()


__all__ = [
    "VALIDATION_DESIGN_CLOSURE_FAILURE_COUNT",
    "VALIDATION_DESIGN_CLOSURE_FAILURE_VERSION",
    "ValidationDesignClosureFailureProbe",
    "ValidationDesignClosureFailureReport",
    "export_validation_design_closure_failures_csv",
    "rehearse_validation_design_closure_failures",
]
