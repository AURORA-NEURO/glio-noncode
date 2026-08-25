"""Cross-artifact reconciliation for the module-fabric offline bundle."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .module_fabric_bundle_contracts import (
    MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX,
    FabricBundle,
    FabricBundleArtifactKind,
)
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable

MODULE_FABRIC_BUNDLE_AUDIT_VERSION = "module-fabric-bundle-audit-v1"
MODULE_FABRIC_RECORD_COUNT = 32
MODULE_FABRIC_DOMAIN_COUNT = 16
MODULE_FABRIC_POSITIVE_COUNT = 16
MODULE_FABRIC_CONTROL_COUNT = 16
MODULE_FABRIC_EVALUATION_CHECK_COUNT = 394
MODULE_FABRIC_RUNTIME_STAGE_COUNT = 24
MODULE_FABRIC_COMPLIANCE_CHECK_COUNT = 12
MODULE_FABRIC_QUALITY_CHECK_COUNT = 20
MODULE_FABRIC_DEPTH_CHECK_COUNT = 30
MODULE_FABRIC_REPLAY_CHECK_COUNT = 8
MODULE_FABRIC_LINEAGE_NODE_COUNT = 478
MODULE_FABRIC_LINEAGE_EDGE_COUNT = 521
MODULE_FABRIC_SCHEMA_FIELD_COUNT = 16
MODULE_FABRIC_DICTIONARY_ENTRY_COUNT = 12
MODULE_FABRIC_SOURCE_COUNT = 5
MODULE_FABRIC_RELEASE_ARTIFACT_COUNT = 8


class FabricBundleAuditPlane(StrEnum):
    MANIFEST = "manifest"
    INVENTORY = "inventory"
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    RUNTIME = "runtime"
    RELEASE = "release"
    REPLAY = "replay"
    QUALITY = "quality"
    LINEAGE = "lineage"
    OBSERVABILITY = "observability"
    SCHEMA = "schema"
    PUBLIC_BOUNDARY = "public_boundary"
    CSV = "csv"
    CLOSURE = "closure"


@dataclass(frozen=True, slots=True)
class FabricBundleAuditCheck:
    check_id: str
    plane: FabricBundleAuditPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleFabricBundleAudit:
    bundle_id: str
    bundle_address: str
    checks: tuple[FabricBundleAuditCheck, ...]
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
            "version": MODULE_FABRIC_BUNDLE_AUDIT_VERSION,
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
    plane: FabricBundleAuditPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricBundleAuditCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricBundleAuditCheck(
        **body,
        content_address=content_hash(body, prefix="module-fabric-bundle-audit-check"),
    )


def _artifact_map(bundle: FabricBundle) -> dict[str, Any]:
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


def _addressed(values: list[Mapping[str, Any]], field: str, prefix: str) -> bool:
    addresses = [str(item.get(field, "")) for item in values]
    return bool(addresses) and len(addresses) == len(set(addresses)) and all(item.startswith(f"{prefix}:") for item in addresses)


def _inventory_checks(bundle: FabricBundle, artifacts: Mapping[str, Any]) -> list[FabricBundleAuditCheck]:
    expected = {
        "fixture": ("fixture.json", FabricBundleArtifactKind.FIXTURE.value, "application/json"),
        "evaluation": ("evaluation.json", FabricBundleArtifactKind.EVALUATION.value, "application/json"),
        "metrics": ("metrics.json", FabricBundleArtifactKind.METRICS.value, "application/json"),
        "depth": ("depth.json", FabricBundleArtifactKind.DEPTH.value, "application/json"),
        "lineage": ("lineage.json", FabricBundleArtifactKind.LINEAGE.value, "application/json"),
        "replay": ("replay.json", FabricBundleArtifactKind.REPLAY.value, "application/json"),
        "quality": ("quality.json", FabricBundleArtifactKind.QUALITY.value, "application/json"),
        "release": ("release.json", FabricBundleArtifactKind.RELEASE.value, "application/json"),
        "runtime": ("runtime.json", FabricBundleArtifactKind.RUNTIME.value, "application/json"),
        "compliance": ("compliance.json", FabricBundleArtifactKind.COMPLIANCE.value, "application/json"),
        "catalog": ("catalog.json", FabricBundleArtifactKind.CATALOG.value, "application/json"),
        "schema": ("schema.json", FabricBundleArtifactKind.SCHEMA.value, "application/json"),
        "dictionary": ("data-dictionary.json", FabricBundleArtifactKind.DICTIONARY.value, "application/json"),
        "sources": ("sources.json", FabricBundleArtifactKind.SOURCES.value, "application/json"),
        "summary": ("summary.json", FabricBundleArtifactKind.SUMMARY.value, "application/json"),
        "trace": ("observability.json", FabricBundleArtifactKind.REPORT.value, "application/json"),
        "report-summary": ("report-summary.json", FabricBundleArtifactKind.REPORT.value, "application/json"),
        "review": ("review.csv", FabricBundleArtifactKind.REVIEW.value, "text/csv"),
        "checks": ("checks.csv", FabricBundleArtifactKind.CHECKS.value, "text/csv"),
        "review-report": ("review-report.md", FabricBundleArtifactKind.REPORT.value, "text/markdown"),
        "runtime-report": ("runtime-report.md", FabricBundleArtifactKind.REPORT.value, "text/markdown"),
    }
    observed = {key: (item.relative_path, item.kind.value, item.media_type) for key, item in artifacts.items()}
    return [
        _check("artifact-count", FabricBundleAuditPlane.INVENTORY, len(artifacts) == len(expected), len(artifacts), len(expected), "the module-fabric inventory has the closed denominator"),
        _check("artifact-identities", FabricBundleAuditPlane.INVENTORY, len({item.artifact_id for item in bundle.artifacts}) == len(bundle.artifacts), len({item.artifact_id for item in bundle.artifacts}), len(bundle.artifacts), "artifact identifiers are unique"),
        _check("artifact-paths", FabricBundleAuditPlane.INVENTORY, len({item.relative_path for item in bundle.artifacts}) == len(bundle.artifacts), len({item.relative_path for item in bundle.artifacts}), len(bundle.artifacts), "artifact paths are unique"),
        _check("artifact-inventory", FabricBundleAuditPlane.INVENTORY, observed == expected, observed, expected, "artifact paths, kinds, and media types match the closed inventory"),
        _check("artifact-addresses", FabricBundleAuditPlane.INVENTORY, all(item.content_address.startswith(f"{MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX}:") for item in bundle.artifacts), True, True, "every artifact carries an exact-byte address"),
        _check("artifact-payloads", FabricBundleAuditPlane.INVENTORY, all(item.payload is not None for item in bundle.artifacts), sum(item.payload is not None for item in bundle.artifacts), len(bundle.artifacts), "every artifact is materializable"),
        _check("artifact-byte-counts", FabricBundleAuditPlane.INVENTORY, all(item.payload is not None and len(item.payload.encode("utf-8")) == item.byte_count for item in bundle.artifacts), True, True, "declared byte counts match UTF-8 payloads"),
        _check("artifact-line-counts", FabricBundleAuditPlane.INVENTORY, all(item.payload is not None and len(item.payload.splitlines()) == item.line_count for item in bundle.artifacts), True, True, "declared line counts match payloads"),
    ]


def _fixture_evaluation_checks(artifacts: Mapping[str, Any]) -> list[FabricBundleAuditCheck]:
    fixture, fixture_read = _json_artifact(artifacts, "fixture")
    evaluation, evaluation_read = _json_artifact(artifacts, "evaluation")
    records = fixture.get("records", []) if isinstance(fixture, Mapping) else []
    executions = evaluation.get("executions", []) if isinstance(evaluation, Mapping) else []
    record_ids = {str(item.get("record_id")) for item in records if isinstance(item, Mapping)}
    execution_ids = {str(item.get("record_id")) for item in executions if isinstance(item, Mapping)}
    positive = [item for item in records if isinstance(item, Mapping) and item.get("role") == "positive"]
    controls = [item for item in records if isinstance(item, Mapping) and item.get("role") == "control"]
    domains = {str(item.get("domain_id")) for item in records if isinstance(item, Mapping)}
    checks = evaluation.get("checks", []) if isinstance(evaluation, Mapping) else []
    return [
        _check("fixture-readable", FabricBundleAuditPlane.FIXTURE, fixture_read, bool(fixture_read), True, "fixture artifact parses as JSON"),
        _check("evaluation-readable", FabricBundleAuditPlane.EVALUATION, evaluation_read, bool(evaluation_read), True, "evaluation artifact parses as JSON"),
        _check("fixture-record-count", FabricBundleAuditPlane.FIXTURE, len(records) == MODULE_FABRIC_RECORD_COUNT, len(records), MODULE_FABRIC_RECORD_COUNT, "fixture contains two records per domain"),
        _check("fixture-domain-count", FabricBundleAuditPlane.FIXTURE, len(domains) == MODULE_FABRIC_DOMAIN_COUNT, len(domains), MODULE_FABRIC_DOMAIN_COUNT, "fixture spans all module-fabric domains"),
        _check("fixture-positive-count", FabricBundleAuditPlane.FIXTURE, len(positive) == MODULE_FABRIC_POSITIVE_COUNT, len(positive), MODULE_FABRIC_POSITIVE_COUNT, "fixture contains one positive row per domain"),
        _check("fixture-control-count", FabricBundleAuditPlane.FIXTURE, len(controls) == MODULE_FABRIC_CONTROL_COUNT, len(controls), MODULE_FABRIC_CONTROL_COUNT, "fixture contains one control row per domain"),
        _check("evaluation-record-identities", FabricBundleAuditPlane.EVALUATION, record_ids == execution_ids, {"records": len(record_ids), "executions": len(execution_ids)}, MODULE_FABRIC_RECORD_COUNT, "every fixture record executes exactly once"),
        _check("evaluation-check-count", FabricBundleAuditPlane.EVALUATION, len(checks) == MODULE_FABRIC_EVALUATION_CHECK_COUNT, len(checks), MODULE_FABRIC_EVALUATION_CHECK_COUNT, "evaluation retains the complete check denominator"),
        _check("evaluation-accepted", FabricBundleAuditPlane.EVALUATION, isinstance(evaluation, Mapping) and bool(evaluation.get("accepted")) and not evaluation.get("failed_checks"), {"accepted": evaluation.get("accepted") if isinstance(evaluation, Mapping) else None, "failed": evaluation.get("failed_checks") if isinstance(evaluation, Mapping) else None}, {"accepted": True, "failed": 0}, "all module-fabric evaluations pass"),
        _check("evaluation-check-addresses", FabricBundleAuditPlane.EVALUATION, _addressed([item for item in checks if isinstance(item, Mapping)], "content_address", "sha256"), True, True, "evaluation checks are addressed"),
    ]


def _runtime_link_checks(artifacts: Mapping[str, Any]) -> list[FabricBundleAuditCheck]:
    runtime, runtime_read = _json_artifact(artifacts, "runtime")
    release, release_read = _json_artifact(artifacts, "release")
    quality, quality_read = _json_artifact(artifacts, "quality")
    replay, replay_read = _json_artifact(artifacts, "replay")
    depth, depth_read = _json_artifact(artifacts, "depth")
    compliance, compliance_read = _json_artifact(artifacts, "compliance")
    lineage, lineage_read = _json_artifact(artifacts, "lineage")
    trace, trace_read = _json_artifact(artifacts, "trace")
    runtime_stages = runtime.get("stages", []) if isinstance(runtime, Mapping) else []
    quality_checks = quality.get("checks", []) if isinstance(quality, Mapping) else []
    depth_checks = depth.get("checks", []) if isinstance(depth, Mapping) else []
    replay_checks = replay.get("checks", []) if isinstance(replay, Mapping) else []
    compliance_checks = compliance.get("checks", []) if isinstance(compliance, Mapping) else []
    nodes = lineage.get("nodes", []) if isinstance(lineage, Mapping) else []
    edges = lineage.get("edges", []) if isinstance(lineage, Mapping) else []
    observations = trace.get("observations", []) if isinstance(trace, Mapping) else []
    return [
        _check("runtime-readable", FabricBundleAuditPlane.RUNTIME, runtime_read, bool(runtime_read), True, "runtime artifact parses as JSON"),
        _check("runtime-accepted", FabricBundleAuditPlane.RUNTIME, isinstance(runtime, Mapping) and runtime.get("state") == "accepted", runtime.get("state") if isinstance(runtime, Mapping) else None, "accepted", "runtime state is accepted"),
        _check("runtime-stage-count", FabricBundleAuditPlane.RUNTIME, len(runtime_stages) == MODULE_FABRIC_RUNTIME_STAGE_COUNT, len(runtime_stages), MODULE_FABRIC_RUNTIME_STAGE_COUNT, "runtime retains all ordered stages"),
        _check("runtime-stage-order", FabricBundleAuditPlane.RUNTIME, tuple(item.get("ordinal") for item in runtime_stages if isinstance(item, Mapping)) == tuple(range(1, MODULE_FABRIC_RUNTIME_STAGE_COUNT + 1)), tuple(item.get("ordinal") for item in runtime_stages if isinstance(item, Mapping)), tuple(range(1, MODULE_FABRIC_RUNTIME_STAGE_COUNT + 1)), "runtime stage ordinals are contiguous"),
        _check("quality-readable", FabricBundleAuditPlane.QUALITY, quality_read, bool(quality_read), True, "quality artifact parses as JSON"),
        _check("quality-accepted", FabricBundleAuditPlane.QUALITY, isinstance(quality, Mapping) and bool(quality.get("accepted")) and len(quality_checks) == MODULE_FABRIC_QUALITY_CHECK_COUNT and all(bool(item.get("passed")) for item in quality_checks if isinstance(item, Mapping)), {"accepted": quality.get("accepted") if isinstance(quality, Mapping) else None, "checks": len(quality_checks)}, {"accepted": True, "checks": MODULE_FABRIC_QUALITY_CHECK_COUNT}, "all module-fabric quality checks pass"),
        _check("depth-readable", FabricBundleAuditPlane.RUNTIME, depth_read, bool(depth_read), True, "depth artifact parses as JSON"),
        _check("depth-accepted", FabricBundleAuditPlane.RUNTIME, isinstance(depth, Mapping) and bool(depth.get("accepted")) and len(depth_checks) == MODULE_FABRIC_DEPTH_CHECK_COUNT and all(bool(item.get("passed")) for item in depth_checks if isinstance(item, Mapping)), {"accepted": depth.get("accepted") if isinstance(depth, Mapping) else None, "checks": len(depth_checks)}, {"accepted": True, "checks": MODULE_FABRIC_DEPTH_CHECK_COUNT}, "all module-fabric depth checks pass"),
        _check("replay-readable", FabricBundleAuditPlane.REPLAY, replay_read, bool(replay_read), True, "replay artifact parses as JSON"),
        _check("replay-accepted", FabricBundleAuditPlane.REPLAY, isinstance(replay, Mapping) and bool(replay.get("accepted")) and len(replay_checks) == MODULE_FABRIC_REPLAY_CHECK_COUNT and all(bool(item.get("passed")) for item in replay_checks if isinstance(item, Mapping)), {"accepted": replay.get("accepted") if isinstance(replay, Mapping) else None, "checks": len(replay_checks)}, {"accepted": True, "checks": MODULE_FABRIC_REPLAY_CHECK_COUNT}, "deterministic replay retains all passing controls"),
        _check("compliance-readable", FabricBundleAuditPlane.PUBLIC_BOUNDARY, compliance_read, bool(compliance_read), True, "compliance artifact parses as JSON"),
        _check("compliance-accepted", FabricBundleAuditPlane.PUBLIC_BOUNDARY, isinstance(compliance, Mapping) and bool(compliance.get("accepted")) and len(compliance_checks) == MODULE_FABRIC_COMPLIANCE_CHECK_COUNT and all(bool(item.get("passed")) for item in compliance_checks if isinstance(item, Mapping)), {"accepted": compliance.get("accepted") if isinstance(compliance, Mapping) else None, "checks": len(compliance_checks)}, {"accepted": True, "checks": MODULE_FABRIC_COMPLIANCE_CHECK_COUNT}, "public compliance checks all pass"),
        _check("lineage-readable", FabricBundleAuditPlane.LINEAGE, lineage_read, bool(lineage_read), True, "lineage artifact parses as JSON"),
        _check("lineage-closure", FabricBundleAuditPlane.LINEAGE, isinstance(lineage, Mapping) and bool(lineage.get("accepted")) and len(nodes) == MODULE_FABRIC_LINEAGE_NODE_COUNT and len(edges) == MODULE_FABRIC_LINEAGE_EDGE_COUNT, {"accepted": lineage.get("accepted") if isinstance(lineage, Mapping) else None, "nodes": len(nodes), "edges": len(edges)}, {"accepted": True, "nodes": MODULE_FABRIC_LINEAGE_NODE_COUNT, "edges": MODULE_FABRIC_LINEAGE_EDGE_COUNT}, "lineage graph retains its conserved node and edge closure"),
        _check("lineage-addresses", FabricBundleAuditPlane.LINEAGE, _addressed([item for item in nodes if isinstance(item, Mapping)], "content_address", "module-fabric-node") and _addressed([item for item in edges if isinstance(item, Mapping)], "content_address", "module-fabric-edge"), True, True, "lineage nodes and edges are independently addressed"),
        _check("trace-readable", FabricBundleAuditPlane.OBSERVABILITY, trace_read, bool(trace_read), True, "observability trace parses as JSON"),
        _check("trace-closure", FabricBundleAuditPlane.OBSERVABILITY, isinstance(trace, Mapping) and bool(trace.get("accepted")) and len(observations) == MODULE_FABRIC_RUNTIME_STAGE_COUNT and tuple(item.get("ordinal") for item in observations if isinstance(item, Mapping)) == tuple(range(1, MODULE_FABRIC_RUNTIME_STAGE_COUNT + 1)), {"accepted": trace.get("accepted") if isinstance(trace, Mapping) else None, "observations": len(observations)}, {"accepted": True, "observations": MODULE_FABRIC_RUNTIME_STAGE_COUNT}, "observability mirrors the complete runtime stage trace"),
        _check("release-readable", FabricBundleAuditPlane.RELEASE, release_read, bool(release_read), True, "release artifact parses as JSON"),
        _check("release-accepted", FabricBundleAuditPlane.RELEASE, isinstance(release, Mapping) and release.get("state") == "accepted" and len(release.get("artifacts", [])) == MODULE_FABRIC_RELEASE_ARTIFACT_COUNT and not release.get("blockers"), {"state": release.get("state") if isinstance(release, Mapping) else None, "artifacts": len(release.get("artifacts", [])) if isinstance(release, Mapping) else None, "blockers": release.get("blockers") if isinstance(release, Mapping) else None}, {"state": "accepted", "artifacts": MODULE_FABRIC_RELEASE_ARTIFACT_COUNT, "blockers": []}, "module-fabric release gate is accepted"),
    ]


def _projection_checks(artifacts: Mapping[str, Any]) -> list[FabricBundleAuditCheck]:
    metrics, metrics_read = _json_artifact(artifacts, "metrics")
    catalog, catalog_read = _json_artifact(artifacts, "catalog")
    schema, schema_read = _json_artifact(artifacts, "schema")
    dictionary, dictionary_read = _json_artifact(artifacts, "dictionary")
    sources, sources_read = _json_artifact(artifacts, "sources")
    summary, summary_read = _json_artifact(artifacts, "summary")
    report, report_read = _json_artifact(artifacts, "report-summary")
    domains = catalog.get("domains", []) if isinstance(catalog, Mapping) else []
    fields = schema.get("fields", []) if isinstance(schema, Mapping) else []
    entries = dictionary.get("entries", []) if isinstance(dictionary, Mapping) else []
    source_entries = sources.get("entries", []) if isinstance(sources, Mapping) else []
    return [
        _check("metrics-readable", FabricBundleAuditPlane.CLOSURE, metrics_read, bool(metrics_read), True, "metrics artifact parses as JSON"),
        _check("metrics-conservation", FabricBundleAuditPlane.CLOSURE, isinstance(metrics, Mapping) and metrics.get("record_count") == MODULE_FABRIC_RECORD_COUNT and metrics.get("domain_count") == MODULE_FABRIC_DOMAIN_COUNT and metrics.get("positive_count") == MODULE_FABRIC_POSITIVE_COUNT and metrics.get("control_count") == MODULE_FABRIC_CONTROL_COUNT, {key: metrics.get(key) if isinstance(metrics, Mapping) else None for key in ("record_count", "domain_count", "positive_count", "control_count")}, {"record_count": MODULE_FABRIC_RECORD_COUNT, "domain_count": MODULE_FABRIC_DOMAIN_COUNT, "positive_count": MODULE_FABRIC_POSITIVE_COUNT, "control_count": MODULE_FABRIC_CONTROL_COUNT}, "metrics conserve fixture denominators"),
        _check("catalog-readable", FabricBundleAuditPlane.CLOSURE, catalog_read, bool(catalog_read), True, "catalog artifact parses as JSON"),
        _check("catalog-conservation", FabricBundleAuditPlane.CLOSURE, isinstance(catalog, Mapping) and len(domains) == MODULE_FABRIC_DOMAIN_COUNT and all(item.get("capability_count") == 16 and item.get("mvp_count") == 4 for item in domains if isinstance(item, Mapping)), {"domains": len(domains), "rows": [item.get("capability_count") for item in domains if isinstance(item, Mapping)]}, {"domains": MODULE_FABRIC_DOMAIN_COUNT, "rows": 16}, "catalog domains conserve their 16-row and 4-MVP denominators"),
        _check("schema-readable", FabricBundleAuditPlane.SCHEMA, schema_read, bool(schema_read), True, "schema artifact parses as JSON"),
        _check("schema-closure", FabricBundleAuditPlane.SCHEMA, isinstance(schema, Mapping) and len(fields) == MODULE_FABRIC_SCHEMA_FIELD_COUNT and all((item.get("name") == "payload" and not item.get("public") and not item.get("required")) or (bool(item.get("public")) and bool(item.get("required"))) for item in fields if isinstance(item, Mapping)), {"fields": len(fields)}, {"fields": MODULE_FABRIC_SCHEMA_FIELD_COUNT, "payload": "private and optional"}, "schema retains the complete public field contract"),
        _check("dictionary-readable", FabricBundleAuditPlane.SCHEMA, dictionary_read, bool(dictionary_read), True, "data dictionary artifact parses as JSON"),
        _check("dictionary-closure", FabricBundleAuditPlane.SCHEMA, isinstance(dictionary, Mapping) and len(entries) == MODULE_FABRIC_DICTIONARY_ENTRY_COUNT and all(bool(item.get("required")) for item in entries if isinstance(item, Mapping)), len(entries), MODULE_FABRIC_DICTIONARY_ENTRY_COUNT, "data dictionary retains every required entry"),
        _check("sources-readable", FabricBundleAuditPlane.CLOSURE, sources_read, bool(sources_read), True, "source registry artifact parses as JSON"),
        _check("sources-closure", FabricBundleAuditPlane.CLOSURE, isinstance(sources, Mapping) and bool(sources.get("accepted")) and len(source_entries) == MODULE_FABRIC_SOURCE_COUNT and all(str(item.get("uri", "")).startswith("https://") and item.get("scope") == "public_aggregate" for item in source_entries if isinstance(item, Mapping)), {"accepted": sources.get("accepted") if isinstance(sources, Mapping) else None, "entries": len(source_entries)}, {"accepted": True, "entries": MODULE_FABRIC_SOURCE_COUNT}, "source receipts are public HTTPS references"),
        _check("summary-readable", FabricBundleAuditPlane.CLOSURE, summary_read, bool(summary_read), True, "summary artifact parses as JSON"),
        _check("summary-accepted", FabricBundleAuditPlane.CLOSURE, isinstance(summary, Mapping) and bool(summary.get("accepted")) and summary.get("record_count") == MODULE_FABRIC_RECORD_COUNT and summary.get("domain_count") == MODULE_FABRIC_DOMAIN_COUNT and summary.get("evaluation_check_count") == MODULE_FABRIC_EVALUATION_CHECK_COUNT, {key: summary.get(key) if isinstance(summary, Mapping) else None for key in ("accepted", "record_count", "domain_count", "evaluation_check_count")}, {"accepted": True, "record_count": MODULE_FABRIC_RECORD_COUNT, "domain_count": MODULE_FABRIC_DOMAIN_COUNT, "evaluation_check_count": MODULE_FABRIC_EVALUATION_CHECK_COUNT}, "summary conserves the evaluation handoff"),
        _check("report-summary-readable", FabricBundleAuditPlane.CLOSURE, report_read, bool(report_read), True, "report summary artifact parses as JSON"),
        _check("report-summary-closure", FabricBundleAuditPlane.CLOSURE, isinstance(report, Mapping) and report.get("state") == "accepted" and report.get("record_count") == MODULE_FABRIC_RECORD_COUNT and report.get("domain_count") == MODULE_FABRIC_DOMAIN_COUNT and report.get("stage_count") == MODULE_FABRIC_RUNTIME_STAGE_COUNT and report.get("evaluation_check_count") == MODULE_FABRIC_EVALUATION_CHECK_COUNT and report.get("compliance_check_count") == MODULE_FABRIC_COMPLIANCE_CHECK_COUNT and not report.get("schema_issues"), {key: report.get(key) if isinstance(report, Mapping) else None for key in ("state", "record_count", "domain_count", "stage_count", "evaluation_check_count", "compliance_check_count")}, {"state": "accepted", "record_count": MODULE_FABRIC_RECORD_COUNT, "domain_count": MODULE_FABRIC_DOMAIN_COUNT, "stage_count": MODULE_FABRIC_RUNTIME_STAGE_COUNT, "evaluation_check_count": MODULE_FABRIC_EVALUATION_CHECK_COUNT, "compliance_check_count": MODULE_FABRIC_COMPLIANCE_CHECK_COUNT}, "report summary conserves runtime and evidence denominators"),
    ]


def _csv_checks(artifacts: Mapping[str, Any]) -> list[FabricBundleAuditCheck]:
    review, review_read = _csv_artifact(artifacts, "review")
    checks, checks_read = _csv_artifact(artifacts, "checks")
    return [
        _check("review-csv-readable", FabricBundleAuditPlane.CSV, review_read, bool(review_read), True, "review CSV parses with a header"),
        _check("review-csv-count", FabricBundleAuditPlane.CSV, len(review) == MODULE_FABRIC_RECORD_COUNT, len(review), MODULE_FABRIC_RECORD_COUNT, "review CSV retains one row per fixture record"),
        _check("checks-csv-readable", FabricBundleAuditPlane.CSV, checks_read, bool(checks_read), True, "checks CSV parses with a header"),
        _check("checks-csv-count", FabricBundleAuditPlane.CSV, len(checks) == MODULE_FABRIC_EVALUATION_CHECK_COUNT, len(checks), MODULE_FABRIC_EVALUATION_CHECK_COUNT, "checks CSV retains the full evaluation denominator"),
        _check("checks-csv-addresses", FabricBundleAuditPlane.CSV, all(str(item.get("content_address", "")).startswith("sha256:") for item in checks), True, True, "checks CSV rows retain source addresses"),
    ]


def audit_module_fabric_bundle(bundle: FabricBundle) -> ModuleFabricBundleAudit:
    """Reconcile all 21 module-fabric artifacts and conserved denominators."""

    artifacts = _artifact_map(bundle)
    checks: list[FabricBundleAuditCheck] = [
        _check("manifest-address", FabricBundleAuditPlane.MANIFEST, content_hash(bundle.manifest_dict(include_payloads=False), prefix="module-fabric-bundle") == bundle.content_address, bundle.content_address, "module-fabric-bundle:<digest>", "bundle manifest address reconstructs"),
        _check("manifest-public-boundary", FabricBundleAuditPlane.PUBLIC_BOUNDARY, _public(bundle.to_dict(include_payloads=False)), True, True, "manifest contains no private or attribution keys"),
        _check("bundle-ready", FabricBundleAuditPlane.MANIFEST, bundle.ready, {"accepted": bundle.accepted, "state": bundle.state.value}, {"accepted": True, "state": "ready"}, "bundle state is ready"),
    ]
    checks.extend(_inventory_checks(bundle, artifacts))
    checks.extend(_fixture_evaluation_checks(artifacts))
    checks.extend(_runtime_link_checks(artifacts))
    checks.extend(_projection_checks(artifacts))
    checks.extend(_csv_checks(artifacts))
    checks.extend(
        (
            _check("public-json-artifacts", FabricBundleAuditPlane.PUBLIC_BOUNDARY, _public_json_artifacts(artifacts), True, True, "every JSON artifact remains public-safe"),
            _check("review-markdown-present", FabricBundleAuditPlane.CLOSURE, bool(artifacts.get("review-report") and (artifacts["review-report"].payload or "").startswith("#")), bool(artifacts.get("review-report")), True, "review Markdown is materialized"),
            _check("runtime-markdown-present", FabricBundleAuditPlane.CLOSURE, bool(artifacts.get("runtime-report") and (artifacts["runtime-report"].payload or "").startswith("#")), bool(artifacts.get("runtime-report")), True, "runtime Markdown is materialized"),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {
        "bundle_id": bundle.bundle_id,
        "bundle_address": bundle.content_address,
        "checks": checks,
        "accepted": accepted,
    }
    return ModuleFabricBundleAudit(
        bundle_id=bundle.bundle_id,
        bundle_address=bundle.content_address,
        checks=tuple(checks),
        accepted=accepted,
        content_address=content_hash(body, prefix="module-fabric-bundle-audit"),
    )


__all__ = [
    "MODULE_FABRIC_BUNDLE_AUDIT_VERSION",
    "MODULE_FABRIC_COMPLIANCE_CHECK_COUNT",
    "MODULE_FABRIC_DEPTH_CHECK_COUNT",
    "MODULE_FABRIC_EVALUATION_CHECK_COUNT",
    "MODULE_FABRIC_LINEAGE_EDGE_COUNT",
    "MODULE_FABRIC_LINEAGE_NODE_COUNT",
    "MODULE_FABRIC_QUALITY_CHECK_COUNT",
    "MODULE_FABRIC_REPLAY_CHECK_COUNT",
    "MODULE_FABRIC_RUNTIME_STAGE_COUNT",
    "ModuleFabricBundleAudit",
    "FabricBundleAuditCheck",
    "FabricBundleAuditPlane",
    "audit_module_fabric_bundle",
]
