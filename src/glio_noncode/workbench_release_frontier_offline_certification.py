"""Independent certification and export plane for D15 offline handoffs.

The bundle audit proves that artifacts can be loaded and joined.  This module
adds a reviewer-facing certification receipt with explicit domains, evidence
artifact references, coverage scoring, and machine-readable exports.  It does
not promote a held row or infer a scientific conclusion; it certifies only the
technical closure of the supplied public aggregate handoff.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, jsonable
from .workbench_release_frontier_offline_audit import audit_workbench_release_offline_bundle
from .workbench_release_frontier_offline_boundary import workbench_release_offline_key_inventory
from .workbench_release_frontier_offline_contracts import (
    WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
    WORKBENCH_RELEASE_OFFLINE_BUNDLE_VERSION,
    WorkbenchReleaseOfflineBundle,
)
from .workbench_release_frontier_offline_query import _payload, _rows

WORKBENCH_RELEASE_OFFLINE_CERTIFICATION_VERSION = "workbench-release-offline-certification-v1"


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineCertificationCheck:
    """One certifiable technical invariant and its supporting artifacts."""

    check_id: str
    domain: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    evidence_artifact_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineCertificationDomain:
    """A named group of checks used by release reviewers."""

    domain_id: str
    title: str
    check_ids: tuple[str, ...]
    passed_count: int
    check_count: int
    accepted: bool
    content_address: str

    @property
    def pass_rate(self) -> float:
        return 0.0 if self.check_count == 0 else round(self.passed_count / self.check_count, 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"pass_rate": self.pass_rate}


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineCertificationReport:
    """Addressed certification report for a single offline bundle."""

    version: str
    bundle_id: str
    fixture_id: str
    artifact_count: int
    check_count: int
    passed_check_count: int
    failed_check_count: int
    coverage_percent: float
    domains: tuple[WorkbenchReleaseOfflineCertificationDomain, ...]
    checks: tuple[WorkbenchReleaseOfflineCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    @property
    def accepted_domains(self) -> int:
        return sum(item.accepted for item in self.domains)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": list(self.failed_check_ids),
            "accepted_domains": self.accepted_domains,
        }


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineCertificationProjection:
    """Compact projection suitable for API dashboards and release notes."""

    bundle_id: str
    accepted: bool
    coverage_percent: float
    domain_count: int
    accepted_domain_count: int
    check_count: int
    failed_check_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _check(
    check_id: str,
    domain: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    evidence: Iterable[str],
) -> WorkbenchReleaseOfflineCertificationCheck:
    body = {
        "check_id": check_id,
        "domain": domain,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
        "evidence_artifact_ids": tuple(evidence),
    }
    return WorkbenchReleaseOfflineCertificationCheck(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-certification-check"),
    )


def _artifact_ids(bundle: WorkbenchReleaseOfflineBundle, *values: str) -> tuple[str, ...]:
    known = {item.artifact_id for item in bundle.artifacts}
    return tuple(value for value in values if value in known)


def _payload_mapping(bundle: WorkbenchReleaseOfflineBundle, artifact_id: str) -> Mapping[str, Any]:
    value = _payload(bundle, artifact_id)
    return value if isinstance(value, Mapping) else {}


def _build_checks(
    bundle: WorkbenchReleaseOfflineBundle,
) -> tuple[WorkbenchReleaseOfflineCertificationCheck, ...]:
    evaluation = _payload_mapping(bundle, "evaluation")
    runtime = _payload_mapping(bundle, "runtime")
    stage_index = _payload_mapping(bundle, "stage-index")
    denominator = _payload_mapping(bundle, "denominator-index")
    operation_index = _payload_mapping(bundle, "operation-index")
    fixture_index = _payload_mapping(bundle, "fixture-index")
    public_keys = _payload_mapping(bundle, "public-key-index")
    records = _rows(bundle, "fixture", "records")
    sources = _rows(bundle, "fixture", "sources")
    executions = _rows(bundle, "evaluation", "executions")
    evaluations = _rows(bundle, "evaluation", "checks")
    stages = _rows(bundle, "runtime", "stages")
    states = tuple(sorted({str(item.get("observed_state")) for item in executions}))
    operations = tuple(sorted({str(item.get("operation")) for item in records}))
    issue_codes = tuple(
        sorted({str(code) for item in executions for code in item.get("issue_codes", ())})
    )
    component_ids = _artifact_ids(
        bundle,
        "data-audit",
        "adapters",
        "schema",
        "metrics",
        "policy",
        "lineage",
        "reconciliation",
        "quality",
        "replay",
        "view",
        "review-queue",
        "handoff",
        "integrity",
        "depth",
        "controls",
        "validation",
        "evidence",
        "access",
        "failure-injection",
        "diagnostics",
        "artifacts",
        "release",
        "summary",
    )
    return (
        _check(
            "root-ready",
            "manifest",
            bundle.ready,
            bundle.accepted,
            True,
            "root manifest is ready",
            ("fixture", "runtime"),
        ),
        _check(
            "root-version",
            "manifest",
            bundle.version == WORKBENCH_RELEASE_OFFLINE_BUNDLE_VERSION,
            bundle.version,
            WORKBENCH_RELEASE_OFFLINE_BUNDLE_VERSION,
            "root version is supported",
            (),
        ),
        _check(
            "artifact-denominator",
            "manifest",
            bundle.artifact_count == WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
            bundle.artifact_count,
            WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
            "all exact-byte artifacts are present",
            ("fixture-index", "stage-index", "denominator-index"),
        ),
        _check(
            "artifact-identities",
            "manifest",
            len({item.artifact_id for item in bundle.artifacts}) == bundle.artifact_count,
            len({item.artifact_id for item in bundle.artifacts}),
            bundle.artifact_count,
            "artifact identities are unique",
            ("fixture-index",),
        ),
        _check(
            "artifact-paths",
            "manifest",
            len({item.relative_path for item in bundle.artifacts}) == bundle.artifact_count,
            len({item.relative_path for item in bundle.artifacts}),
            bundle.artifact_count,
            "artifact paths are unique",
            ("fixture-index",),
        ),
        _check(
            "artifact-addresses",
            "manifest",
            all(
                item.content_address.startswith("workbench-release-bundle-artifact:")
                for item in bundle.artifacts
            ),
            bundle.artifact_count,
            bundle.artifact_count,
            "every artifact is exact-byte addressed",
            component_ids,
        ),
        _check(
            "fixture-source-count",
            "fixture",
            len(sources) == 5,
            len(sources),
            5,
            "five public source receipts are conserved",
            ("fixture", "fixture-index"),
        ),
        _check(
            "fixture-record-count",
            "fixture",
            len(records) == 16,
            len(records),
            16,
            "sixteen records are conserved",
            ("fixture", "fixture-index"),
        ),
        _check(
            "fixture-positive-count",
            "fixture",
            sum(item.get("role") == "positive" for item in records) == 4,
            sum(item.get("role") == "positive" for item in records),
            4,
            "four positive records are conserved",
            ("fixture",),
        ),
        _check(
            "fixture-control-count",
            "fixture",
            sum(item.get("role") == "control" for item in records) == 12,
            sum(item.get("role") == "control" for item in records),
            12,
            "twelve controls are conserved",
            ("fixture",),
        ),
        _check(
            "fixture-operation-count",
            "fixture",
            len(operations) == 4,
            len(operations),
            4,
            "four operation families are retained",
            ("fixture", "operation-index"),
        ),
        _check(
            "fixture-operation-balance",
            "fixture",
            all(
                sum(item.get("operation") == operation for item in records) == 4
                for operation in operations
            ),
            {
                operation: sum(item.get("operation") == operation for item in records)
                for operation in operations
            },
            "four each",
            "operation families are balanced",
            ("fixture", "operation-index"),
        ),
        _check(
            "fixture-https",
            "fixture",
            all(str(item.get("uri", "")).startswith("https://") for item in sources),
            True,
            True,
            "source receipts use HTTPS",
            ("fixture",),
        ),
        _check(
            "fixture-index-join",
            "fixture",
            fixture_index.get("record_count") == 16 and fixture_index.get("source_count") == 5,
            fixture_index,
            {"record_count": 16, "source_count": 5},
            "fixture index joins source and record denominators",
            ("fixture-index",),
        ),
        _check(
            "evaluation-execution-count",
            "evaluation",
            len(executions) == 16,
            len(executions),
            16,
            "every record has one execution",
            ("evaluation",),
        ),
        _check(
            "evaluation-check-count",
            "evaluation",
            len(evaluations) == 80,
            len(evaluations),
            80,
            "evaluation checks are conserved",
            ("evaluation",),
        ),
        _check(
            "evaluation-accepted",
            "evaluation",
            bool(evaluation.get("accepted")),
            evaluation.get("accepted"),
            True,
            "evaluation is accepted",
            ("evaluation", "quality"),
        ),
        _check(
            "evaluation-addresses",
            "evaluation",
            all(str(item.get("content_address", "")).startswith("sha256:") for item in executions),
            True,
            True,
            "executions are content addressed",
            ("evaluation",),
        ),
        _check(
            "evaluation-issue-vocabulary",
            "evaluation",
            len(issue_codes) == 8,
            issue_codes,
            8,
            "negative controls retain eight issue categories",
            ("evaluation", "diagnostics"),
        ),
        _check(
            "runtime-stage-count",
            "runtime",
            len(stages) == 49,
            len(stages),
            49,
            "runtime contains 49 stages",
            ("runtime", "stage-index"),
        ),
        _check(
            "runtime-stage-sequence",
            "runtime",
            [item.get("sequence") for item in stages] == list(range(1, 50)),
            len(stages),
            49,
            "runtime stage sequence is contiguous",
            ("runtime", "stage-index"),
        ),
        _check(
            "runtime-stage-addresses",
            "runtime",
            all(str(item.get("content_address", "")).startswith("sha256:") for item in stages),
            True,
            True,
            "runtime stage addresses are retained",
            ("runtime",),
        ),
        _check(
            "runtime-root-join",
            "runtime",
            runtime.get("content_address") == bundle.runtime_address,
            runtime.get("content_address"),
            bundle.runtime_address,
            "runtime address joins root",
            ("runtime",),
        ),
        _check(
            "stage-index-join",
            "runtime",
            stage_index.get("stage_count") == 49 and stage_index.get("ordered") is True,
            stage_index,
            {"stage_count": 49, "ordered": True},
            "stage index closes runtime order",
            ("stage-index",),
        ),
        _check(
            "denominator-index-join",
            "indexes",
            all(
                denominator.get(key) == value
                for key, value in (
                    ("sources", 5),
                    ("records", 16),
                    ("positive_records", 4),
                    ("control_records", 12),
                    ("operations", 4),
                    ("executions", 16),
                    ("evaluation_checks", 80),
                    ("runtime_stages", 49),
                )
            ),
            denominator,
            "D15 denominators",
            "denominator index closes every count",
            ("denominator-index",),
        ),
        _check(
            "operation-index-join",
            "indexes",
            operation_index.get("balanced") is True
            and len(operation_index.get("operations", {})) == 4,
            operation_index,
            {"balanced": True, "operation_count": 4},
            "operation index is balanced",
            ("operation-index",),
        ),
        _check(
            "public-key-join",
            "security",
            public_keys.get("accepted") is True and public_keys.get("forbidden_keys") == [],
            public_keys.get("forbidden_keys"),
            [],
            "public-key index has no forbidden fields",
            ("public-key-index",),
        ),
        _check(
            "public-boundary-manifest",
            "security",
            not _has_forbidden_key(bundle.manifest_dict())
            and not contains_private_key(bundle.manifest_dict()),
            True,
            True,
            "root manifest is public",
            (),
        ),
        _check(
            "public-boundary-payloads",
            "security",
            not any(
                _has_forbidden_key(item.to_dict()) or contains_private_key(item.to_dict())
                for item in bundle.artifacts
            ),
            True,
            True,
            "artifact metadata is public",
            ("fixture", "runtime"),
        ),
        _check(
            "source-registry",
            "release",
            bool(_payload_mapping(bundle, "source-registry").get("accepted")),
            _payload_mapping(bundle, "source-registry").get("accepted"),
            True,
            "source registry is accepted",
            ("source-registry",),
        ),
        _check(
            "compatibility",
            "release",
            bool(_payload_mapping(bundle, "compatibility").get("accepted")),
            _payload_mapping(bundle, "compatibility").get("accepted"),
            True,
            "schema and adapter compatibility is accepted",
            ("compatibility",),
        ),
        _check(
            "release-checks",
            "release",
            bool(_payload_mapping(bundle, "release-checks").get("accepted")),
            _payload_mapping(bundle, "release-checks").get("accepted"),
            True,
            "release checks are accepted",
            ("release-checks",),
        ),
        _check(
            "release-plane",
            "release",
            bool(_payload_mapping(bundle, "release").get("accepted")),
            _payload_mapping(bundle, "release").get("accepted"),
            True,
            "release plane is accepted",
            ("release",),
        ),
        _check(
            "summary-plane",
            "release",
            bool(_payload_mapping(bundle, "summary").get("accepted")),
            _payload_mapping(bundle, "summary").get("accepted"),
            True,
            "summary plane is accepted",
            ("summary",),
        ),
        _check(
            "queue-coverage",
            "release",
            len(_rows(bundle, "review-queue", "rows")) == 12,
            len(_rows(bundle, "review-queue", "rows")),
            12,
            "twelve held controls are routed to review",
            ("review-queue", "view"),
        ),
        _check(
            "view-coverage",
            "release",
            len(_rows(bundle, "view", "rows")) == 16,
            len(_rows(bundle, "view", "rows")),
            16,
            "review view preserves every record",
            ("view",),
        ),
        _check(
            "lineage-coverage",
            "release",
            bool(_payload_mapping(bundle, "lineage").get("closed")),
            _payload_mapping(bundle, "lineage").get("closed"),
            True,
            "lineage is closed",
            ("lineage", "evidence"),
        ),
        _check(
            "quality-coverage",
            "release",
            bool(_payload_mapping(bundle, "quality").get("accepted")),
            _payload_mapping(bundle, "quality").get("accepted"),
            True,
            "quality gate is accepted",
            ("quality",),
        ),
        _check(
            "replay-coverage",
            "release",
            bool(_payload_mapping(bundle, "replay").get("deterministic")),
            _payload_mapping(bundle, "replay").get("deterministic"),
            True,
            "source runtime replay is deterministic",
            ("replay",),
        ),
        _check(
            "component-plane-count",
            "release",
            len(component_ids) == 23,
            len(component_ids),
            23,
            "major assurance planes are covered",
            component_ids,
        ),
        _check(
            "state-coverage",
            "release",
            states
            == ("blocked", "exported", "passed", "rejected", "review", "reviewed", "searched"),
            states,
            "all D15 states",
            "state coverage is explicit",
            ("evaluation", "view"),
        ),
    )


def _domains(
    checks: tuple[WorkbenchReleaseOfflineCertificationCheck, ...],
) -> tuple[WorkbenchReleaseOfflineCertificationDomain, ...]:
    titles = {
        "manifest": "Manifest and exact-byte inventory",
        "fixture": "Fixture denominators and public source boundary",
        "evaluation": "Evaluation and negative-control closure",
        "runtime": "Ordered runtime and deterministic addresses",
        "indexes": "Address-only index closure",
        "security": "Public boundary and key safety",
        "release": "Release planes and reviewer routing",
    }
    result: list[WorkbenchReleaseOfflineCertificationDomain] = []
    for domain in titles:
        selected = tuple(item for item in checks if item.domain == domain)
        body = {
            "domain_id": domain,
            "title": titles[domain],
            "check_ids": tuple(item.check_id for item in selected),
            "passed_count": sum(item.passed for item in selected),
            "check_count": len(selected),
            "accepted": bool(selected) and all(item.passed for item in selected),
        }
        result.append(
            WorkbenchReleaseOfflineCertificationDomain(
                **body,
                content_address=content_hash(
                    body, prefix="workbench-release-offline-certification-domain"
                ),
            )
        )
    return tuple(result)


def certify_workbench_release_offline_bundle(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseOfflineCertificationReport:
    """Certify a supplied bundle without rebuilding or mutating it."""

    checks = _build_checks(bundle)
    domains = _domains(checks)
    passed = sum(item.passed for item in checks)
    body = {
        "version": WORKBENCH_RELEASE_OFFLINE_CERTIFICATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "fixture_id": bundle.fixture_id,
        "artifact_count": bundle.artifact_count,
        "check_count": len(checks),
        "passed_check_count": passed,
        "failed_check_count": len(checks) - passed,
        "coverage_percent": round(100 * passed / len(checks), 3) if checks else 0.0,
        "domains": domains,
        "checks": checks,
        "accepted": bundle.ready and bool(checks) and all(item.passed for item in checks),
    }
    return WorkbenchReleaseOfflineCertificationReport(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-certification"),
    )


def audit_workbench_release_offline_certification(
    bundle: WorkbenchReleaseOfflineBundle,
    report: WorkbenchReleaseOfflineCertificationReport,
) -> WorkbenchReleaseOfflineCertificationReport:
    """Independently confirm report identity and the source bundle audit."""

    source_audit = audit_workbench_release_offline_bundle(bundle)
    key_inventory = workbench_release_offline_key_inventory(bundle)
    expected = certify_workbench_release_offline_bundle(bundle)
    checks = list(report.checks)
    checks.extend(
        (
            _check(
                "audit-source-bundle",
                "audit",
                source_audit.accepted,
                source_audit.accepted,
                True,
                "independent bundle audit is accepted",
                ("fixture", "evaluation", "runtime"),
            ),
            _check(
                "audit-key-inventory",
                "audit",
                key_inventory["accepted"],
                key_inventory["forbidden_keys"],
                (),
                "independent key inventory is accepted",
                ("public-key-index",),
            ),
            _check(
                "audit-report-address",
                "audit",
                report.content_address == expected.content_address,
                report.content_address,
                expected.content_address,
                "certification report address reconstructs",
                (),
            ),
            _check(
                "audit-report-count",
                "audit",
                report.check_count == len(expected.checks),
                report.check_count,
                len(expected.checks),
                "certification check count is stable",
                (),
            ),
            _check(
                "audit-report-accepted",
                "audit",
                report.accepted == expected.accepted,
                report.accepted,
                expected.accepted,
                "certification state matches source evaluation",
                (),
            ),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {
        "version": WORKBENCH_RELEASE_OFFLINE_CERTIFICATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "fixture_id": bundle.fixture_id,
        "artifact_count": bundle.artifact_count,
        "check_count": len(checks),
        "passed_check_count": sum(item.passed for item in checks),
        "failed_check_count": sum(not item.passed for item in checks),
        "coverage_percent": round(100 * sum(item.passed for item in checks) / len(checks), 3),
        "domains": _domains(tuple(checks)),
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return WorkbenchReleaseOfflineCertificationReport(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-certification-audit"),
    )


def workbench_release_offline_certification_projection(
    report: WorkbenchReleaseOfflineCertificationReport,
) -> WorkbenchReleaseOfflineCertificationProjection:
    body = {
        "bundle_id": report.bundle_id,
        "accepted": report.accepted,
        "coverage_percent": report.coverage_percent,
        "domain_count": len(report.domains),
        "accepted_domain_count": report.accepted_domains,
        "check_count": report.check_count,
        "failed_check_ids": report.failed_check_ids,
    }
    return WorkbenchReleaseOfflineCertificationProjection(
        **body,
        content_address=content_hash(
            body, prefix="workbench-release-offline-certification-projection"
        ),
    )


def query_workbench_release_offline_certification(
    report: WorkbenchReleaseOfflineCertificationReport,
    *,
    domain: str | None = None,
    failed_only: bool = False,
    text: str | None = None,
) -> tuple[WorkbenchReleaseOfflineCertificationCheck, ...]:
    """Return bounded certification checks for a reviewer or dashboard."""

    selected = tuple(
        item
        for item in report.checks
        if domain in (None, "", item.domain) and (not failed_only or not item.passed)
    )
    needle = (text or "").casefold().strip()
    if needle:
        selected = tuple(
            item for item in selected if needle in canonical_json(item.to_dict()).casefold()
        )
    return selected


def export_workbench_release_offline_certification_csv(
    report: WorkbenchReleaseOfflineCertificationReport,
) -> str:
    stream = io.StringIO()
    fields = (
        "check_id",
        "domain",
        "passed",
        "observed",
        "required",
        "detail",
        "evidence_artifact_ids",
        "content_address",
    )
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in report.checks:
        writer.writerow(
            {
                "check_id": item.check_id,
                "domain": item.domain,
                "passed": item.passed,
                "observed": canonical_json(item.observed),
                "required": canonical_json(item.required),
                "detail": item.detail,
                "evidence_artifact_ids": "|".join(item.evidence_artifact_ids),
                "content_address": item.content_address,
            }
        )
    return stream.getvalue()


def workbench_release_offline_certification_markdown(
    report: WorkbenchReleaseOfflineCertificationReport,
) -> str:
    lines = [
        "# Workbench release offline certification",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        f"Coverage: `{report.passed_check_count}/{report.check_count}` "
        f"({report.coverage_percent}%)",
        "",
        "| Domain | Passed | Checks | State |",
        "| --- | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| `{item.domain_id}` | {item.passed_count} | {item.check_count} | "
        f"`{('pass' if item.accepted else 'hold')}` |"
        for item in report.domains
    )
    lines.extend(
        ("", "## Checks", "", "| Check | Domain | State | Detail |", "| --- | --- | --- | --- |")
    )
    lines.extend(
        f"| `{item.check_id}` | `{item.domain}` | "
        f"`{('pass' if item.passed else 'hold')}` | {item.detail} |"
        for item in report.checks
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "WORKBENCH_RELEASE_OFFLINE_CERTIFICATION_VERSION",
    "WorkbenchReleaseOfflineCertificationCheck",
    "WorkbenchReleaseOfflineCertificationDomain",
    "WorkbenchReleaseOfflineCertificationProjection",
    "WorkbenchReleaseOfflineCertificationReport",
    "audit_workbench_release_offline_certification",
    "certify_workbench_release_offline_bundle",
    "export_workbench_release_offline_certification_csv",
    "query_workbench_release_offline_certification",
    "workbench_release_offline_certification_markdown",
    "workbench_release_offline_certification_projection",
]
