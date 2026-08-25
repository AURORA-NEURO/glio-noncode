"""Independent certification domains for the D16 offline handoff."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .deployment_frontier_offline_audit import audit_deployment_frontier_offline_bundle
from .deployment_frontier_offline_boundary import deployment_frontier_offline_key_inventory
from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_CERTIFICATION_VERSION,
    DeploymentFrontierOfflineBundle,
)
from .deployment_frontier_offline_query import _payload, _rows
from .serialization import canonical_json, content_hash, jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineCertificationCheck:
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
class DeploymentFrontierOfflineCertificationDomain:
    domain_id: str
    title: str
    check_ids: tuple[str, ...]
    passed_count: int
    check_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineCertificationProjection:
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


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineCertificationReport:
    version: str
    bundle_id: str
    fixture_id: str
    artifact_count: int
    check_count: int
    passed_check_count: int
    failed_check_count: int
    coverage_percent: float
    domains: tuple[DeploymentFrontierOfflineCertificationDomain, ...]
    checks: tuple[DeploymentFrontierOfflineCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def accepted_domains(self) -> int:
        return sum(item.accepted for item in self.domains)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted_domains": self.accepted_domains,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _check(
    check_id: str,
    domain: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    evidence: tuple[str, ...] = (),
) -> DeploymentFrontierOfflineCertificationCheck:
    body = {
        "check_id": check_id,
        "domain": domain,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
        "evidence_artifact_ids": evidence,
    }
    return DeploymentFrontierOfflineCertificationCheck(
        **body,
        content_address=content_hash(
            body, prefix="deployment-frontier-offline-certification-check"
        ),
    )


def _build_checks(
    bundle: DeploymentFrontierOfflineBundle,
) -> tuple[DeploymentFrontierOfflineCertificationCheck, ...]:
    records = _rows(bundle, "fixture", "records")
    sources = _rows(bundle, "fixture", "sources")
    executions = _rows(bundle, "evaluation", "executions")
    evaluation_checks = _rows(bundle, "evaluation", "checks")
    stages = _rows(bundle, "runtime", "stages")
    denominator = _payload(bundle, "denominator-index") or {}
    stage_index = _payload(bundle, "stage-index") or {}
    operation_index = _payload(bundle, "operation-index") or {}
    key_index = _payload(bundle, "public-key-index") or {}
    issue_index = _payload(bundle, "issue-index") or {}
    state_index = _payload(bundle, "state-index") or {}
    accepted_components = tuple(
        artifact_id
        for artifact_id in (
            "audit",
            "evaluation",
            "quality",
            "integrity",
            "assurance",
            "release_checks",
            "trace",
        )
        if any(item.artifact_id == artifact_id for item in bundle.artifacts)
    )
    source_ids = tuple(str(item.get("source_id")) for item in sources)
    record_ids = tuple(str(item.get("record_id")) for item in records)
    execution_ids = tuple(str(item.get("record_id")) for item in executions)
    return (
        _check(
            "manifest-ready",
            "manifest",
            bundle.ready,
            bundle.state.value,
            "ready",
            "root manifest is ready",
            ("fixture", "runtime"),
        ),
        _check(
            "manifest-addressed",
            "manifest",
            bool(bundle.content_address),
            bundle.content_address,
            "address",
            "root manifest is addressed",
        ),
        _check(
            "manifest-inventory",
            "manifest",
            bundle.artifact_count == 51,
            bundle.artifact_count,
            51,
            "fifty-one artifacts are present",
            ("runtime",),
        ),
        _check(
            "manifest-checks",
            "manifest",
            bundle.failed_check_count == 0,
            bundle.failed_check_count,
            0,
            "root manifest has no failed build checks",
        ),
        _check(
            "source-count",
            "fixture",
            len(sources) == 5,
            len(sources),
            5,
            "five source receipts are present",
            ("fixture", "fixture-index"),
        ),
        _check(
            "source-https",
            "fixture",
            all(str(item.get("uri", "")).startswith("https://") for item in sources),
            True,
            True,
            "all source receipts use HTTPS",
            ("fixture",),
        ),
        _check(
            "source-unique",
            "fixture",
            len(source_ids) == len(set(source_ids)),
            source_ids,
            "unique source ids",
            "source identifiers are unique",
            ("fixture",),
        ),
        _check(
            "record-count",
            "fixture",
            len(records) == 16,
            len(records),
            16,
            "sixteen records are present",
            ("fixture", "fixture-index"),
        ),
        _check(
            "positive-count",
            "fixture",
            sum(item.get("role") == "positive" for item in records) == 4,
            sum(item.get("role") == "positive" for item in records),
            4,
            "four positive paths are present",
            ("fixture",),
        ),
        _check(
            "control-count",
            "fixture",
            sum(item.get("role") == "control" for item in records) == 12,
            sum(item.get("role") == "control" for item in records),
            12,
            "twelve controls are present",
            ("fixture",),
        ),
        _check(
            "operation-count",
            "fixture",
            len({item.get("operation") for item in records}) == 4,
            len({item.get("operation") for item in records}),
            4,
            "four operation families are present",
            ("fixture", "operation-index"),
        ),
        _check(
            "execution-count",
            "evaluation",
            len(executions) == 16 and execution_ids == record_ids,
            {"count": len(executions), "identity_match": execution_ids == record_ids},
            {"count": 16, "identity_match": True},
            "execution identities close fixture identities",
            ("evaluation",),
        ),
        _check(
            "evaluation-check-count",
            "evaluation",
            len(evaluation_checks) == 80,
            len(evaluation_checks),
            80,
            "eighty evaluation checks are present",
            ("evaluation",),
        ),
        _check(
            "evaluation-accepted",
            "evaluation",
            bool((_payload(bundle, "evaluation") or {}).get("accepted")),
            (_payload(bundle, "evaluation") or {}).get("accepted"),
            True,
            "evaluation accepts positive and control boundaries",
            ("evaluation",),
        ),
        _check(
            "execution-addresses",
            "evaluation",
            all(str(item.get("content_address", "")).startswith("sha256:") for item in executions),
            True,
            True,
            "execution receipts are addressed",
            ("evaluation",),
        ),
        _check(
            "runtime-count",
            "runtime",
            len(stages) == 38,
            len(stages),
            38,
            "thirty-eight ordered stages are present",
            ("runtime", "stage-index"),
        ),
        _check(
            "runtime-sequence",
            "runtime",
            [item.get("sequence") for item in stages] == list(range(1, 39)),
            [item.get("sequence") for item in stages],
            list(range(1, 39)),
            "runtime sequence is contiguous",
            ("runtime", "stage-index"),
        ),
        _check(
            "runtime-addresses",
            "runtime",
            all(str(item.get("content_address", "")).startswith("sha256:") for item in stages),
            True,
            True,
            "runtime stages are addressed",
            ("runtime",),
        ),
        _check(
            "stage-index",
            "runtime",
            stage_index.get("stage_count") == 38 and stage_index.get("ordered") is True,
            stage_index,
            {"stage_count": 38, "ordered": True},
            "stage index closes runtime",
            ("stage-index",),
        ),
        _check(
            "denominator-sources",
            "runtime",
            denominator.get("sources") == 5,
            denominator.get("sources"),
            5,
            "denominator index retains source count",
            ("denominator-index",),
        ),
        _check(
            "denominator-records",
            "runtime",
            denominator.get("records") == 16,
            denominator.get("records"),
            16,
            "denominator index retains record count",
            ("denominator-index",),
        ),
        _check(
            "denominator-evaluations",
            "runtime",
            denominator.get("evaluation_checks") == 80,
            denominator.get("evaluation_checks"),
            80,
            "denominator index retains evaluation count",
            ("denominator-index",),
        ),
        _check(
            "denominator-stages",
            "runtime",
            denominator.get("runtime_stages") == 38,
            denominator.get("runtime_stages"),
            38,
            "denominator index retains stage count",
            ("denominator-index",),
        ),
        _check(
            "operation-index",
            "indexes",
            operation_index.get("balanced") is True and operation_index.get("operation_count") == 4,
            operation_index,
            {"balanced": True, "operation_count": 4},
            "operation index is balanced",
            ("operation-index",),
        ),
        _check(
            "operation-record-coverage",
            "indexes",
            sum(len(value) for value in operation_index.get("operations", {}).values()) == 16,
            operation_index.get("operations"),
            16,
            "operation index covers every record",
            ("operation-index",),
        ),
        _check(
            "issue-index",
            "indexes",
            issue_index.get("issue_count") == 13,
            issue_index.get("issue_count"),
            13,
            "issue index covers all negative-control categories",
            ("issue-index",),
        ),
        _check(
            "state-index",
            "indexes",
            sum(state_index.get("state_counts", {}).values()) == 16,
            state_index.get("state_counts"),
            16,
            "state index covers every execution",
            ("state-index",),
        ),
        _check(
            "key-index",
            "security",
            key_index.get("accepted") is True and not key_index.get("forbidden_keys"),
            key_index.get("forbidden_keys"),
            (),
            "public key index is clean",
            ("public-key-index",),
        ),
        _check(
            "bundle-key-boundary",
            "security",
            not any(
                "agent" in str(item.to_dict()).casefold()
                or "model" in str(item.to_dict()).casefold()
                or "language" in str(item.to_dict()).casefold()
                for item in bundle.artifacts
            ),
            True,
            True,
            "artifact surfaces carry no prohibited attribution language",
            ("public-key-index",),
        ),
        _check(
            "component-coverage",
            "release",
            len(accepted_components) == 7,
            accepted_components,
            7,
            "release-critical component planes are present",
            accepted_components,
        ),
        _check(
            "bundle-release",
            "release",
            bool((_payload(bundle, "release") or {}).get("accepted")),
            (_payload(bundle, "release") or {}).get("accepted"),
            True,
            "release plane is accepted",
            ("release",),
        ),
        _check(
            "quality-release",
            "release",
            bool((_payload(bundle, "quality") or {}).get("accepted")),
            (_payload(bundle, "quality") or {}).get("accepted"),
            True,
            "quality gate is accepted",
            ("quality",),
        ),
        _check(
            "queue-routing",
            "release",
            len(_rows(bundle, "queue", "items")) == 12 or len(_rows(bundle, "queue", "rows")) == 12,
            len(_rows(bundle, "queue", "items")) or len(_rows(bundle, "queue", "rows")),
            12,
            "all twelve controls are routed for review",
            ("queue",),
        ),
        _check(
            "lineage-closure",
            "release",
            bool((_payload(bundle, "lineage") or {}).get("complete")),
            (_payload(bundle, "lineage") or {}).get("complete"),
            True,
            "lineage is complete",
            ("lineage",),
        ),
        _check(
            "trace-closure",
            "release",
            bool((_payload(bundle, "trace") or {}).get("accepted")),
            (_payload(bundle, "trace") or {}).get("accepted"),
            True,
            "observability trace is accepted",
            ("trace",),
        ),
        _check(
            "source-join",
            "release",
            all(set(item.get("source_ids", ())) <= set(source_ids) for item in records),
            True,
            True,
            "every record source reference resolves",
            ("fixture",),
        ),
        _check(
            "accepted-components",
            "release",
            len(accepted_components) == 7,
            len(accepted_components),
            7,
            "all seven release-critical components are inventoried",
            accepted_components,
        ),
    )


def _domains(
    checks: tuple[DeploymentFrontierOfflineCertificationCheck, ...],
) -> tuple[DeploymentFrontierOfflineCertificationDomain, ...]:
    titles = {
        "manifest": "Manifest and exact-byte inventory",
        "fixture": "Public fixture denominators",
        "evaluation": "Evaluation and negative controls",
        "runtime": "Ordered runtime and address closure",
        "indexes": "Address-only index closure",
        "security": "Public boundary and key safety",
        "release": "Release planes and reviewer routing",
    }
    result: list[DeploymentFrontierOfflineCertificationDomain] = []
    for domain, title in titles.items():
        selected = tuple(item for item in checks if item.domain == domain)
        body = {
            "domain_id": domain,
            "title": title,
            "check_ids": tuple(item.check_id for item in selected),
            "passed_count": sum(item.passed for item in selected),
            "check_count": len(selected),
            "accepted": bool(selected) and all(item.passed for item in selected),
        }
        result.append(
            DeploymentFrontierOfflineCertificationDomain(
                **body,
                content_address=content_hash(
                    body, prefix="deployment-frontier-offline-certification-domain"
                ),
            )
        )
    return tuple(result)


def certify_deployment_frontier_offline_bundle(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierOfflineCertificationReport:
    """Certify a supplied bundle without rebuilding or mutating it."""

    checks = _build_checks(bundle)
    domains = _domains(checks)
    passed = sum(item.passed for item in checks)
    body = {
        "version": DEPLOYMENT_FRONTIER_OFFLINE_CERTIFICATION_VERSION,
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
    return DeploymentFrontierOfflineCertificationReport(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-certification"),
    )


def audit_deployment_frontier_offline_certification(
    bundle: DeploymentFrontierOfflineBundle, report: DeploymentFrontierOfflineCertificationReport
) -> DeploymentFrontierOfflineCertificationReport:
    """Add independent source-audit receipts to a certification report."""

    source_audit = audit_deployment_frontier_offline_bundle(bundle)
    expected = certify_deployment_frontier_offline_bundle(bundle)
    inventory = deployment_frontier_offline_key_inventory(bundle)
    checks = tuple(report.checks) + (
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
            inventory["accepted"],
            inventory["forbidden_keys"],
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
            report.check_count == expected.check_count,
            report.check_count,
            expected.check_count,
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
    accepted = all(item.passed for item in checks)
    body = {
        "version": DEPLOYMENT_FRONTIER_OFFLINE_CERTIFICATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "fixture_id": bundle.fixture_id,
        "artifact_count": bundle.artifact_count,
        "check_count": len(checks),
        "passed_check_count": sum(item.passed for item in checks),
        "failed_check_count": sum(not item.passed for item in checks),
        "coverage_percent": round(100 * sum(item.passed for item in checks) / len(checks), 3),
        "domains": _domains(checks),
        "checks": checks,
        "accepted": accepted,
    }
    return DeploymentFrontierOfflineCertificationReport(
        **body,
        content_address=content_hash(
            body, prefix="deployment-frontier-offline-certification-audit"
        ),
    )


def deployment_frontier_offline_certification_projection(
    report: DeploymentFrontierOfflineCertificationReport,
) -> DeploymentFrontierOfflineCertificationProjection:
    body = {
        "bundle_id": report.bundle_id,
        "accepted": report.accepted,
        "coverage_percent": report.coverage_percent,
        "domain_count": len(report.domains),
        "accepted_domain_count": report.accepted_domains,
        "check_count": report.check_count,
        "failed_check_ids": report.failed_check_ids,
    }
    return DeploymentFrontierOfflineCertificationProjection(
        **body,
        content_address=content_hash(
            body, prefix="deployment-frontier-offline-certification-projection"
        ),
    )


def query_deployment_frontier_offline_certification(
    report: DeploymentFrontierOfflineCertificationReport,
    *,
    domain: str | None = None,
    failed_only: bool = False,
    text: str | None = None,
) -> tuple[DeploymentFrontierOfflineCertificationCheck, ...]:
    selected = tuple(
        item
        for item in report.checks
        if domain in (None, "", item.domain) and (not failed_only or not item.passed)
    )
    needle = (text or "").casefold().strip()
    return tuple(
        item
        for item in selected
        if not needle or needle in canonical_json(item.to_dict()).casefold()
    )


def export_deployment_frontier_offline_certification_csv(
    report: DeploymentFrontierOfflineCertificationReport,
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


def deployment_frontier_offline_certification_markdown(
    report: DeploymentFrontierOfflineCertificationReport,
) -> str:
    lines = [
        "# Deployment frontier offline certification",
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
    "DEPLOYMENT_FRONTIER_OFFLINE_CERTIFICATION_VERSION",
    "DeploymentFrontierOfflineCertificationCheck",
    "DeploymentFrontierOfflineCertificationDomain",
    "DeploymentFrontierOfflineCertificationProjection",
    "DeploymentFrontierOfflineCertificationReport",
    "audit_deployment_frontier_offline_certification",
    "certify_deployment_frontier_offline_bundle",
    "deployment_frontier_offline_certification_markdown",
    "deployment_frontier_offline_certification_projection",
    "export_deployment_frontier_offline_certification_csv",
    "query_deployment_frontier_offline_certification",
]
