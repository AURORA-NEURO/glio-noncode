"""Cross-artifact reconciliation for capability certification bundles.

The directory verifier proves that files have not changed.  This module proves
that the files agree with one another: report counts reconcile with CSV rows,
runtime and quality receipts point at the same report, replay points at the
same address, and observability describes the materialized inventory.  Keeping
this plane separate makes it useful to callers that already hold an in-memory
bundle and prevents the filesystem verifier from becoming the only source of
release confidence.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .capability_certification import (
    CAPABILITIES_PER_DOMAIN,
    CATALOG_CAPABILITY_COUNT,
    CATALOG_DOMAIN_COUNT,
    CATALOG_MVP_COUNT,
    CHECKS_PER_CAPABILITY,
    GLOBAL_CHECK_COUNT,
)
from .capability_certification_bundle_contracts import (
    CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX,
    CapabilityCertificationBundle,
    CertificationBundleArtifactKind,
)
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable

CAPABILITY_CERTIFICATION_BUNDLE_AUDIT_VERSION = "capability-certification-bundle-audit-v1"
CAPABILITY_CERTIFICATION_BUNDLE_QUALITY_CHECK_COUNT = 18
CAPABILITY_CERTIFICATION_BUNDLE_FAILURE_PROBE_COUNT = 2


class CertificationBundleAuditPlane(StrEnum):
    MANIFEST = "manifest"
    INVENTORY = "inventory"
    REPORT = "report"
    CSV = "csv"
    RUNTIME = "runtime"
    REPLAY = "replay"
    FAILURE_CONTROLS = "failure_controls"
    OBSERVABILITY = "observability"
    PUBLIC_BOUNDARY = "public_boundary"
    CLOSURE = "closure"


@dataclass(frozen=True, slots=True)
class CertificationBundleAuditCheck:
    check_id: str
    plane: CertificationBundleAuditPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CapabilityCertificationBundleAudit:
    bundle_id: str
    bundle_address: str
    checks: tuple[CertificationBundleAuditCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return len(self.checks) - self.passed_check_count

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CAPABILITY_CERTIFICATION_BUNDLE_AUDIT_VERSION,
            "bundle_id": self.bundle_id,
            "bundle_address": self.bundle_address,
            "checks": [item.to_dict() for item in self.checks],
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "failed_check_ids": list(self.failed_check_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _check(
    check_id: str,
    plane: CertificationBundleAuditPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> CertificationBundleAuditCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CertificationBundleAuditCheck(
        **body,
        content_address=content_hash(body, prefix="capability-certification-bundle-audit-check"),
    )


def _artifact_map(bundle: CapabilityCertificationBundle) -> dict[str, Any]:
    return {item.artifact_id: item for item in bundle.artifacts}


def _json_artifact(artifacts: Mapping[str, Any], artifact_id: str) -> tuple[Any, bool]:
    artifact = artifacts.get(artifact_id)
    if artifact is None or artifact.payload is None:
        return None, False
    try:
        return json.loads(artifact.payload), True
    except json.JSONDecodeError:
        return None, False


def _csv_artifact(artifacts: Mapping[str, Any], artifact_id: str) -> tuple[list[dict[str, str]], bool]:
    artifact = artifacts.get(artifact_id)
    if artifact is None or artifact.payload is None:
        return [], False
    try:
        reader = csv.DictReader(io.StringIO(artifact.payload, newline=""))
        return [dict(row) for row in reader], reader.fieldnames is not None
    except (csv.Error, TypeError):
        return [], False


def _public(value: Any) -> bool:
    return not _has_forbidden_key(value) and not contains_private_key(value)


def _public_json_artifacts(artifacts: Mapping[str, Any]) -> bool:
    for artifact in artifacts.values():
        if artifact.media_type != "application/json" or artifact.payload is None:
            continue
        try:
            if not _public(json.loads(artifact.payload)):
                return False
        except json.JSONDecodeError:
            return False
    return True


def _address_set(values: list[Mapping[str, Any]], field: str, prefix: str) -> bool:
    addresses = [str(item.get(field, "")) for item in values]
    return len(addresses) == len(set(addresses)) and all(item.startswith(f"{prefix}:") for item in addresses)


def _artifact_inventory_checks(bundle: CapabilityCertificationBundle, artifacts: Mapping[str, Any]) -> list[CertificationBundleAuditCheck]:
    expected = {
        "report": ("report.json", CertificationBundleArtifactKind.REPORT.value, "application/json"),
        "summary": ("summary.json", CertificationBundleArtifactKind.SUMMARY.value, "application/json"),
        "certificates": ("certificates.csv", CertificationBundleArtifactKind.CERTIFICATES.value, "text/csv"),
        "checks": ("checks.csv", CertificationBundleArtifactKind.CHECKS.value, "text/csv"),
        "domains": ("domains.csv", CertificationBundleArtifactKind.DOMAINS.value, "text/csv"),
        "runtime": ("runtime.json", CertificationBundleArtifactKind.RUNTIME.value, "application/json"),
        "quality": ("quality.json", CertificationBundleArtifactKind.QUALITY.value, "application/json"),
        "replay": ("replay.json", CertificationBundleArtifactKind.REPLAY.value, "application/json"),
        "failures": ("failures.json", CertificationBundleArtifactKind.FAILURES.value, "application/json"),
        "catalog": ("catalog.json", CertificationBundleArtifactKind.CATALOG.value, "application/json"),
        "report-markdown": ("report.md", CertificationBundleArtifactKind.MARKDOWN.value, "text/markdown"),
        "observability": ("observability.json", CertificationBundleArtifactKind.OBSERVABILITY.value, "application/json"),
    }
    observed = {
        key: (item.relative_path, item.kind.value, item.media_type)
        for key, item in artifacts.items()
    }
    return [
        _check("artifact-count", CertificationBundleAuditPlane.INVENTORY, len(artifacts) == len(expected), len(artifacts), len(expected), "the public artifact inventory has the closed denominator"),
        _check("artifact-identities", CertificationBundleAuditPlane.INVENTORY, len({item.artifact_id for item in bundle.artifacts}) == len(bundle.artifacts), len({item.artifact_id for item in bundle.artifacts}), len(bundle.artifacts), "artifact identifiers are unique"),
        _check("artifact-paths", CertificationBundleAuditPlane.INVENTORY, len({item.relative_path for item in bundle.artifacts}) == len(bundle.artifacts), len({item.relative_path for item in bundle.artifacts}), len(bundle.artifacts), "artifact paths are unique"),
        _check("artifact-inventory", CertificationBundleAuditPlane.INVENTORY, observed == expected, observed, expected, "artifact paths, kinds, and media types match the closed inventory"),
        _check("artifact-address-prefixes", CertificationBundleAuditPlane.INVENTORY, all(item.content_address.startswith(f"{CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX}:") for item in bundle.artifacts), tuple(item.content_address for item in bundle.artifacts), f"{CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX}:<digest>", "every artifact carries a bundle artifact address"),
        _check("artifact-check-addresses", CertificationBundleAuditPlane.INVENTORY, all(item.content_address for item in bundle.checks), len(bundle.checks), len(bundle.checks), "every bundle closure check carries an address"),
        _check("artifact-payloads", CertificationBundleAuditPlane.INVENTORY, all(item.payload is not None for item in bundle.artifacts), sum(item.payload is not None for item in bundle.artifacts), len(bundle.artifacts), "every artifact is available for reconciliation"),
        _check("artifact-byte-counts", CertificationBundleAuditPlane.INVENTORY, all(item.payload is not None and len(item.payload.encode("utf-8")) == item.byte_count for item in bundle.artifacts), True, True, "declared byte counts match UTF-8 payloads"),
        _check("artifact-line-counts", CertificationBundleAuditPlane.INVENTORY, all(item.payload is not None and len(item.payload.splitlines()) == item.line_count for item in bundle.artifacts), True, True, "declared line counts match payloads"),
    ]


def _report_checks(report: Mapping[str, Any]) -> list[CertificationBundleAuditCheck]:
    certificates = report.get("certificates", [])
    domains = report.get("domain_summaries", [])
    global_checks = report.get("checks", [])
    certificate_rows = [item for item in certificates if isinstance(item, Mapping)]
    domain_rows = [item for item in domains if isinstance(item, Mapping)]
    global_rows = [item for item in global_checks if isinstance(item, Mapping)]
    mvp_count = sum(bool(item.get("mvp_64")) for item in certificate_rows)
    total_row_checks = sum(len(item.get("checks", [])) for item in certificate_rows)
    all_row_checks_pass = all(bool(check.get("passed")) for item in certificate_rows for check in item.get("checks", []) if isinstance(check, Mapping))
    return [
        _check("report-public-boundary", CertificationBundleAuditPlane.PUBLIC_BOUNDARY, _public(report), True, True, "the complete report remains public-safe"),
        _check("report-accepted", CertificationBundleAuditPlane.REPORT, bool(report.get("accepted")) and report.get("state") == "accepted", {"accepted": report.get("accepted"), "state": report.get("state")}, {"accepted": True, "state": "accepted"}, "the certification report is accepted"),
        _check("report-capability-denominator", CertificationBundleAuditPlane.REPORT, report.get("capability_count") == CATALOG_CAPABILITY_COUNT == len(certificate_rows), {"declared": report.get("capability_count"), "rows": len(certificate_rows)}, CATALOG_CAPABILITY_COUNT, "the report contains every catalog capability"),
        _check("report-domain-denominator", CertificationBundleAuditPlane.REPORT, len(domain_rows) == CATALOG_DOMAIN_COUNT, len(domain_rows), CATALOG_DOMAIN_COUNT, "the report contains every catalog domain"),
        _check("report-mvp-denominator", CertificationBundleAuditPlane.REPORT, mvp_count == CATALOG_MVP_COUNT, mvp_count, CATALOG_MVP_COUNT, "the MVP denominator reconciles from certificate rows"),
        _check("report-domain-balance", CertificationBundleAuditPlane.REPORT, all(item.get("capability_count") == CAPABILITIES_PER_DOMAIN for item in domain_rows), {item.get("domain_id"): item.get("capability_count") for item in domain_rows}, CAPABILITIES_PER_DOMAIN, "every domain carries the closed row denominator"),
        _check("report-domain-identities", CertificationBundleAuditPlane.REPORT, {item.get("domain_id") for item in domain_rows} == {f"D{index:02d}" for index in range(1, CATALOG_DOMAIN_COUNT + 1)}, sorted(str(item.get("domain_id")) for item in domain_rows), [f"D{index:02d}" for index in range(1, CATALOG_DOMAIN_COUNT + 1)], "domain identifiers are complete and unique"),
        _check("report-certificate-identities", CertificationBundleAuditPlane.REPORT, len({item.get("capability_id") for item in certificate_rows}) == CATALOG_CAPABILITY_COUNT, len({item.get("capability_id") for item in certificate_rows}), CATALOG_CAPABILITY_COUNT, "capability identifiers are unique"),
        _check("report-row-check-denominator", CertificationBundleAuditPlane.REPORT, all(len(item.get("checks", [])) == CHECKS_PER_CAPABILITY for item in certificate_rows), {item.get("capability_id"): len(item.get("checks", [])) for item in certificate_rows if len(item.get("checks", [])) != CHECKS_PER_CAPABILITY}, CHECKS_PER_CAPABILITY, "every certificate has the complete row check plane"),
        _check("report-global-check-denominator", CertificationBundleAuditPlane.REPORT, len(global_rows) == GLOBAL_CHECK_COUNT, len(global_rows), GLOBAL_CHECK_COUNT, "global checks retain their fixed denominator"),
        _check("report-check-denominator", CertificationBundleAuditPlane.REPORT, report.get("total_checks") == total_row_checks + len(global_rows) == CATALOG_CAPABILITY_COUNT * CHECKS_PER_CAPABILITY + GLOBAL_CHECK_COUNT, {"declared": report.get("total_checks"), "rows": total_row_checks, "global": len(global_rows)}, CATALOG_CAPABILITY_COUNT * CHECKS_PER_CAPABILITY + GLOBAL_CHECK_COUNT, "row and global checks reconcile to the complete denominator"),
        _check("report-row-checks-pass", CertificationBundleAuditPlane.REPORT, all_row_checks_pass, all(bool(check.get("passed")) for item in certificate_rows for check in item.get("checks", []) if isinstance(check, Mapping)), True, "every row-level check passes"),
        _check("report-global-checks-pass", CertificationBundleAuditPlane.REPORT, all(bool(item.get("passed")) for item in global_rows), sum(bool(item.get("passed")) for item in global_rows), len(global_rows), "every global check passes"),
        _check("report-certificate-addresses", CertificationBundleAuditPlane.REPORT, _address_set(certificate_rows, "content_address", "capability-certificate"), True, True, "certificate rows are independently addressed"),
        _check("report-domain-addresses", CertificationBundleAuditPlane.REPORT, _address_set(domain_rows, "content_address", "capability-domain-summary"), True, True, "domain summaries are independently addressed"),
        _check("report-check-addresses", CertificationBundleAuditPlane.REPORT, _address_set([item for item in global_rows if isinstance(item, Mapping)], "content_address", "capability-certification-check") and all(_address_set([check for check in item.get("checks", []) if isinstance(check, Mapping)], "content_address", "capability-certification-check") for item in certificate_rows), True, True, "all report checks are independently addressed"),
    ]


def _csv_checks(
    artifacts: Mapping[str, Any],
    report: Mapping[str, Any],
) -> list[CertificationBundleAuditCheck]:
    certificate_rows, certificates_read = _csv_artifact(artifacts, "certificates")
    check_rows, checks_read = _csv_artifact(artifacts, "checks")
    domain_rows, domains_read = _csv_artifact(artifacts, "domains")
    report_certificates = report.get("certificates", []) if isinstance(report, Mapping) else []
    report_domains = report.get("domain_summaries", []) if isinstance(report, Mapping) else []
    expected_ids = {str(item.get("capability_id")) for item in report_certificates if isinstance(item, Mapping)}
    csv_ids = {str(item.get("capability_id")) for item in certificate_rows}
    return [
        _check("certificates-csv-readable", CertificationBundleAuditPlane.CSV, certificates_read, bool(certificates_read), True, "certificate CSV has a header and parses"),
        _check("certificates-csv-count", CertificationBundleAuditPlane.CSV, len(certificate_rows) == CATALOG_CAPABILITY_COUNT, len(certificate_rows), CATALOG_CAPABILITY_COUNT, "certificate CSV retains one row per capability"),
        _check("certificates-csv-identities", CertificationBundleAuditPlane.CSV, csv_ids == expected_ids, len(csv_ids), len(expected_ids), "certificate CSV identifiers reconcile with the report"),
        _check("checks-csv-readable", CertificationBundleAuditPlane.CSV, checks_read, bool(checks_read), True, "check CSV has a header and parses"),
        _check("checks-csv-count", CertificationBundleAuditPlane.CSV, len(check_rows) == CATALOG_CAPABILITY_COUNT * CHECKS_PER_CAPABILITY + GLOBAL_CHECK_COUNT, len(check_rows), CATALOG_CAPABILITY_COUNT * CHECKS_PER_CAPABILITY + GLOBAL_CHECK_COUNT, "check CSV retains the complete check denominator"),
        _check("checks-csv-addresses", CertificationBundleAuditPlane.CSV, all(str(item.get("content_address", "")).startswith("capability-certification-check:") for item in check_rows), True, True, "check CSV rows remain addressed"),
        _check("domains-csv-readable", CertificationBundleAuditPlane.CSV, domains_read, bool(domains_read), True, "domain CSV has a header and parses"),
        _check("domains-csv-count", CertificationBundleAuditPlane.CSV, len(domain_rows) == CATALOG_DOMAIN_COUNT, len(domain_rows), CATALOG_DOMAIN_COUNT, "domain CSV retains one row per domain"),
        _check("domains-csv-identities", CertificationBundleAuditPlane.CSV, {str(item.get("domain_id")) for item in domain_rows} == {str(item.get("domain_id")) for item in report_domains if isinstance(item, Mapping)}, len(domain_rows), len(report_domains), "domain CSV identifiers reconcile with the report"),
    ]


def _runtime_checks(artifacts: Mapping[str, Any], report: Mapping[str, Any]) -> list[CertificationBundleAuditCheck]:
    runtime, runtime_read = _json_artifact(artifacts, "runtime")
    quality, quality_read = _json_artifact(artifacts, "quality")
    replay, replay_read = _json_artifact(artifacts, "replay")
    failures, failures_read = _json_artifact(artifacts, "failures")
    runtime_stages = runtime.get("stages", []) if isinstance(runtime, Mapping) else []
    quality_checks = quality.get("checks", []) if isinstance(quality, Mapping) else []
    probes = failures.get("probes", []) if isinstance(failures, Mapping) else []
    report_address = report.get("content_address") if isinstance(report, Mapping) else None
    return [
        _check("runtime-readable", CertificationBundleAuditPlane.RUNTIME, runtime_read, bool(runtime_read), True, "runtime receipt parses as JSON"),
        _check("runtime-accepted", CertificationBundleAuditPlane.RUNTIME, isinstance(runtime, Mapping) and bool(runtime.get("accepted")) and runtime.get("state") == "accepted", {"accepted": runtime.get("accepted") if isinstance(runtime, Mapping) else None, "state": runtime.get("state") if isinstance(runtime, Mapping) else None}, {"accepted": True, "state": "accepted"}, "runtime receipt is accepted"),
        _check("runtime-report-link", CertificationBundleAuditPlane.RUNTIME, isinstance(runtime, Mapping) and isinstance(runtime.get("report"), Mapping) and runtime["report"].get("content_address") == report_address, runtime.get("report", {}).get("content_address") if isinstance(runtime, Mapping) and isinstance(runtime.get("report"), Mapping) else None, report_address, "runtime points at the bundled report"),
        _check("runtime-stage-denominator", CertificationBundleAuditPlane.RUNTIME, len(runtime_stages) == 12, len(runtime_stages), 12, "runtime retains all twelve certification stages"),
        _check("runtime-stage-order", CertificationBundleAuditPlane.RUNTIME, tuple(item.get("ordinal") for item in runtime_stages if isinstance(item, Mapping)) == tuple(range(1, 13)), tuple(item.get("ordinal") for item in runtime_stages if isinstance(item, Mapping)), tuple(range(1, 13)), "runtime stage ordinals are contiguous"),
        _check("quality-readable", CertificationBundleAuditPlane.RUNTIME, quality_read, bool(quality_read), True, "quality receipt parses as JSON"),
        _check("quality-accepted", CertificationBundleAuditPlane.RUNTIME, isinstance(quality, Mapping) and bool(quality.get("accepted")), quality.get("accepted") if isinstance(quality, Mapping) else None, True, "independent quality receipt is accepted"),
        _check("quality-check-denominator", CertificationBundleAuditPlane.RUNTIME, len(quality_checks) == CAPABILITY_CERTIFICATION_BUNDLE_QUALITY_CHECK_COUNT, len(quality_checks), CAPABILITY_CERTIFICATION_BUNDLE_QUALITY_CHECK_COUNT, "quality receipt retains all eighteen checks"),
        _check("quality-checks-pass", CertificationBundleAuditPlane.RUNTIME, all(bool(item.get("passed")) for item in quality_checks if isinstance(item, Mapping)), sum(bool(item.get("passed")) for item in quality_checks if isinstance(item, Mapping)), len(quality_checks), "all quality checks pass"),
        _check("replay-readable", CertificationBundleAuditPlane.REPLAY, replay_read, bool(replay_read), True, "replay receipt parses as JSON"),
        _check("replay-accepted", CertificationBundleAuditPlane.REPLAY, isinstance(replay, Mapping) and bool(replay.get("accepted")) and replay.get("first_address") == replay.get("second_address") == report_address, {"accepted": replay.get("accepted") if isinstance(replay, Mapping) else None, "first": replay.get("first_address") if isinstance(replay, Mapping) else None, "second": replay.get("second_address") if isinstance(replay, Mapping) else None}, {"accepted": True, "address": report_address}, "replay receipt points at one stable report"),
        _check("failure-controls-readable", CertificationBundleAuditPlane.FAILURE_CONTROLS, failures_read, bool(failures_read), True, "failure-control receipt parses as JSON"),
        _check("failure-controls-accepted", CertificationBundleAuditPlane.FAILURE_CONTROLS, isinstance(failures, Mapping) and bool(failures.get("accepted")) and len(probes) == CAPABILITY_CERTIFICATION_BUNDLE_FAILURE_PROBE_COUNT and all(bool(item.get("passed")) for item in probes if isinstance(item, Mapping)), {"accepted": failures.get("accepted") if isinstance(failures, Mapping) else None, "probes": len(probes)}, {"accepted": True, "probes": CAPABILITY_CERTIFICATION_BUNDLE_FAILURE_PROBE_COUNT}, "negative controls retain their two expected probes"),
    ]


def _observability_checks(bundle: CapabilityCertificationBundle, artifacts: Mapping[str, Any]) -> list[CertificationBundleAuditCheck]:
    observation, readable = _json_artifact(artifacts, "observability")
    events = observation.get("events", []) if isinstance(observation, Mapping) else []
    metrics = observation.get("metrics", []) if isinstance(observation, Mapping) else []
    metric_map = {str(item.get("metric_id")): item.get("value") for item in metrics if isinstance(item, Mapping)}
    required_metrics = {"capability_count", "domain_count", "total_checks", "artifact_count", "artifact_bytes", "certification_percent", "release_accepted"}
    return [
        _check("observability-readable", CertificationBundleAuditPlane.OBSERVABILITY, readable, bool(readable), True, "observability receipt parses as JSON"),
        _check("observability-accepted", CertificationBundleAuditPlane.OBSERVABILITY, isinstance(observation, Mapping) and bool(observation.get("accepted")), observation.get("accepted") if isinstance(observation, Mapping) else None, True, "observability receipt is accepted"),
        _check("observability-event-order", CertificationBundleAuditPlane.OBSERVABILITY, tuple(item.get("ordinal") for item in events if isinstance(item, Mapping)) == tuple(range(1, len(events) + 1)), tuple(item.get("ordinal") for item in events if isinstance(item, Mapping)), tuple(range(1, len(events) + 1)), "observability events are ordered without gaps"),
        _check("observability-event-addresses", CertificationBundleAuditPlane.OBSERVABILITY, all(str(item.get("content_address", "")).startswith("capability-certification-bundle-event:") for item in events if isinstance(item, Mapping)), True, True, "observability events are addressed"),
        _check("observability-metric-addresses", CertificationBundleAuditPlane.OBSERVABILITY, all(str(item.get("content_address", "")).startswith("capability-certification-bundle-metric:") for item in metrics if isinstance(item, Mapping)), True, True, "observability metrics are addressed"),
        _check("observability-metric-inventory", CertificationBundleAuditPlane.OBSERVABILITY, required_metrics.issubset(metric_map), sorted(required_metrics.intersection(metric_map)), sorted(required_metrics), "observability carries the required release metrics"),
        _check("observability-counts", CertificationBundleAuditPlane.OBSERVABILITY, metric_map.get("capability_count") == bundle.certificate_count and metric_map.get("domain_count") == bundle.domain_count and metric_map.get("total_checks") == bundle.total_checks and metric_map.get("artifact_count") == bundle.artifact_count and metric_map.get("artifact_bytes") == sum(item.byte_count for item in bundle.artifacts), {key: metric_map.get(key) for key in ("capability_count", "domain_count", "total_checks", "artifact_count", "artifact_bytes")}, {"capability_count": bundle.certificate_count, "domain_count": bundle.domain_count, "total_checks": bundle.total_checks, "artifact_count": bundle.artifact_count, "artifact_bytes": sum(item.byte_count for item in bundle.artifacts)}, "observability counts reconcile with the materialized bundle"),
    ]


def audit_capability_certification_bundle(bundle: CapabilityCertificationBundle) -> CapabilityCertificationBundleAudit:
    """Reconcile report, CSV, runtime, replay, failure, and observability artifacts."""

    artifacts = _artifact_map(bundle)
    checks: list[CertificationBundleAuditCheck] = [
        _check("manifest-address", CertificationBundleAuditPlane.MANIFEST, content_hash(bundle.manifest_dict(), prefix="capability-certification-bundle") == bundle.content_address, bundle.content_address, "capability-certification-bundle:<digest>", "bundle manifest address reconstructs"),
        _check("manifest-public-boundary", CertificationBundleAuditPlane.PUBLIC_BOUNDARY, _public(bundle.to_dict(include_payloads=False)), True, True, "bundle manifest contains no private or attribution keys"),
        _check("bundle-accepted", CertificationBundleAuditPlane.MANIFEST, bundle.accepted and bundle.ready, {"accepted": bundle.accepted, "state": bundle.state.value}, {"accepted": True, "state": "ready"}, "bundle release state is ready"),
    ]
    checks.extend(_artifact_inventory_checks(bundle, artifacts))
    report, report_read = _json_artifact(artifacts, "report")
    checks.append(_check("report-readable", CertificationBundleAuditPlane.REPORT, report_read, bool(report_read), True, "complete report artifact parses as JSON"))
    if isinstance(report, Mapping):
        checks.extend(_report_checks(report))
        checks.extend(_csv_checks(artifacts, report))
        checks.extend(_runtime_checks(artifacts, report))
    else:
        checks.extend(
            (
                _check("report-structure", CertificationBundleAuditPlane.REPORT, False, type(report).__name__, "object", "report artifact must be an object"),
                _check("csv-reconciliation", CertificationBundleAuditPlane.CSV, False, False, True, "CSV projections cannot reconcile without a report"),
                _check("runtime-reconciliation", CertificationBundleAuditPlane.RUNTIME, False, False, True, "runtime projections cannot reconcile without a report"),
            )
        )
    checks.extend(_observability_checks(bundle, artifacts))
    checks.append(_check("markdown-present", CertificationBundleAuditPlane.CLOSURE, bool(artifacts.get("report-markdown") and artifacts["report-markdown"].payload and artifacts["report-markdown"].payload.startswith("# Capability certification")), bool(artifacts.get("report-markdown")), True, "Markdown report is materialized with its stable heading"))
    checks.append(_check("public-json-artifacts", CertificationBundleAuditPlane.PUBLIC_BOUNDARY, _public_json_artifacts(artifacts), True, True, "every JSON artifact remains inside the public boundary"))
    accepted = all(item.passed for item in checks)
    body = {
        "bundle_id": bundle.bundle_id,
        "bundle_address": bundle.content_address,
        "checks": checks,
        "accepted": accepted,
    }
    return CapabilityCertificationBundleAudit(
        bundle_id=bundle.bundle_id,
        bundle_address=bundle.content_address,
        checks=tuple(checks),
        accepted=accepted,
        content_address=content_hash(body, prefix="capability-certification-bundle-audit"),
    )


__all__ = [
    "CAPABILITY_CERTIFICATION_BUNDLE_AUDIT_VERSION",
    "CAPABILITY_CERTIFICATION_BUNDLE_FAILURE_PROBE_COUNT",
    "CAPABILITY_CERTIFICATION_BUNDLE_QUALITY_CHECK_COUNT",
    "CapabilityCertificationBundleAudit",
    "CertificationBundleAuditCheck",
    "CertificationBundleAuditPlane",
    "audit_capability_certification_bundle",
]
