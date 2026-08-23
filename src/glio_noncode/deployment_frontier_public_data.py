"""Public aggregate fixtures for D16 C13-C16 deployment governance.

The fixture uses public portal receipts as provenance anchors and synthetic
operational measurements. It deliberately contains no patient-level payload,
secrets, access tokens, or raw site data. Positive and control rows are kept
side by side so every accepted path has an explicit denial boundary.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .deployment_frontier_contracts import (
    DEPLOYMENT_FRONTIER_BOUNDARY,
    DEPLOYMENT_FRONTIER_CONTEXT_KEY,
    DEPLOYMENT_FRONTIER_VERSION,
    DeploymentFrontierFixture,
    DeploymentFrontierOperation,
    DeploymentFrontierRecord,
    DeploymentFrontierRole,
    DeploymentFrontierSourceReceipt,
    DeploymentFrontierState,
)
from .serialization import content_hash, jsonable, require_non_empty


DEPLOYMENT_FRONTIER_SOURCE_COUNT = 5
DEPLOYMENT_FRONTIER_RECORD_COUNT = 16
DEPLOYMENT_FRONTIER_POSITIVE_COUNT = 4
DEPLOYMENT_FRONTIER_CONTROL_COUNT = 12


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDataAudit:
    fixture_id: str
    checks: tuple[DeploymentFrontierDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, uri: str, scope: str, version: str) -> DeploymentFrontierSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "scope": scope, "version": version}
    return DeploymentFrontierSourceReceipt(**body, content_address=content_hash(body))


def _source_receipts() -> tuple[DeploymentFrontierSourceReceipt, ...]:
    return (
        _source("gdc", "NCI Genomic Data Commons", "https://gdc.cancer.gov/", "public aggregate cohort portal", "current portal"),
        _source("encode", "ENCODE functional genomics portal", "https://www.encodeproject.org/", "public assay and annotation portal", "current portal"),
        _source("four-d", "4D Nucleome data portal", "https://data.4dnucleome.org/", "public genome-organization portal", "current portal"),
        _source("depmap", "DepMap public portal", "https://depmap.org/portal/", "public aggregate comparator portal", "current portal"),
        _source("ga4gh", "GA4GH standards portal", "https://www.ga4gh.org/", "public interoperability vocabulary", "current portal"),
    )


def _record(
    record_id: str,
    operation: DeploymentFrontierOperation,
    role: DeploymentFrontierRole,
    payload: Mapping[str, Any],
    expected_state: DeploymentFrontierState,
    expected_issue_codes: tuple[str, ...],
    notes: str,
    source_ids: tuple[str, ...],
) -> DeploymentFrontierRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": DEPLOYMENT_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": dict(payload),
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "notes": notes,
    }
    return DeploymentFrontierRecord(**body, content_address=content_hash(body))


def _policy_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "context_key": DEPLOYMENT_FRONTIER_CONTEXT_KEY,
        "policies": {
            "research-read": {
                "actions": ["read"],
                "roles": ["reviewer"],
                "maximum_retention_days": 30,
                "network_access": False,
            }
        },
        "requests": [
            {
                "request_id": "policy-request-positive",
                "subject_id": "principal:research-reviewer",
                "action": "read",
                "roles": ["reviewer"],
                "data_scope": "public_reference",
                "retention_days": 7,
                "context_key": DEPLOYMENT_FRONTIER_CONTEXT_KEY,
            }
        ],
    }
    value.update(overrides)
    return value


def _bundle_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "bundle_id": "bundle-positive",
        "platform": "windows-x86_64",
        "runtime_version": "python3.11",
        "offline": True,
        "artifacts": [
            {
                "artifact_id": "runtime",
                "version": "0.1.0",
                "digest": "sha256:runtime-artifact",
                "size_bytes": 1024,
                "required_runtime": "python3.11",
                "local_only": True,
            },
            {
                "artifact_id": "schemas",
                "version": "2026.08",
                "digest": "sha256:schema-artifact",
                "size_bytes": 512,
                "required_runtime": "python3.11",
                "local_only": True,
            },
        ],
        "services": [
            {"service_id": "local-api", "port": 8010, "depends_on": []},
            {"service_id": "local-worker", "port": 8011, "depends_on": ["local-api"]},
        ],
        "environment_requirements": {"GLIO_DATA_MODE": "aggregate-only"},
    }
    value.update(overrides)
    return value


def _federated_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "plan_id": "federated-positive",
        "context_key": DEPLOYMENT_FRONTIER_CONTEXT_KEY,
        "privacy_budget": 5,
        "minimum_site_count": 1,
        "tasks": [
            {"task_id": "aggregate-summary", "privacy_cost": 2, "minimum_sample_count": 10}
        ],
        "sites": [
            {
                "site_id": "site-aggregate-a",
                "available": True,
                "sample_count": 24,
                "supported_contexts": [DEPLOYMENT_FRONTIER_CONTEXT_KEY],
            },
            {
                "site_id": "site-aggregate-b",
                "available": True,
                "sample_count": 18,
                "supported_contexts": [DEPLOYMENT_FRONTIER_CONTEXT_KEY],
            },
        ],
    }
    value.update(overrides)
    return value


def _release_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "release_id": "release-positive",
        "current_version": "0.9.0",
        "requested_version": "1.0.0",
        "action": "release",
        "previous_version": "0.9.0",
        "checks": {"tests": True, "integrity": True, "compatibility": True, "policy": True},
        "required_checks": ["tests", "integrity", "compatibility", "policy"],
    }
    value.update(overrides)
    return value


def default_deployment_frontier_fixture() -> DeploymentFrontierFixture:
    """Return the deterministic four-positive/twelve-control fixture."""

    sources = _source_receipts()
    records = (
        _record("C13-POS-001", DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, DeploymentFrontierRole.POSITIVE, _policy_payload(), DeploymentFrontierState.READY, (), "allow aggregate read under declared role and retention", ("gdc", "ga4gh")),
        _record("C13-CTRL-001", DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, DeploymentFrontierRole.CONTROL, _policy_payload(requests=[{**_policy_payload()["requests"][0], "roles": ["analyst"], "required_role": "reviewer"}]), DeploymentFrontierState.DENIED, ("role_not_allowed", "required_role_missing"), "role and required-role controls remain denied", ("gdc", "ga4gh")),
        _record("C13-CTRL-002", DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, DeploymentFrontierRole.CONTROL, _policy_payload(requests=[{**_policy_payload()["requests"][0], "context_key": "GRCh38|diffuse_glioma|adult|aggregate|platform|other"}]), DeploymentFrontierState.DENIED, ("context_mismatch",), "context mismatch cannot cross the policy boundary", ("gdc", "ga4gh")),
        _record("C13-CTRL-003", DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, DeploymentFrontierRole.CONTROL, _policy_payload(requests=[{**_policy_payload()["requests"][0], "sensitive": True}]), DeploymentFrontierState.DENIED, ("sensitive_access_denied",), "sensitive access remains denied by default", ("gdc", "ga4gh")),
        _record("C14-POS-001", DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, DeploymentFrontierRole.POSITIVE, _bundle_payload(), DeploymentFrontierState.READY, (), "digest-addressed offline bundle with dependency-declared services", ("encode", "ga4gh")),
        _record("C14-CTRL-001", DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, DeploymentFrontierRole.CONTROL, _bundle_payload(artifacts=[{**_bundle_payload()["artifacts"][0], "digest": "not-a-digest"}]), DeploymentFrontierState.HOLD, ("invalid_digest",), "malformed artifact digest holds release readiness", ("encode", "ga4gh")),
        _record("C14-CTRL-002", DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, DeploymentFrontierRole.CONTROL, _bundle_payload(services=[]), DeploymentFrontierState.HOLD, ("bundle_requirements_missing",), "missing service inventory cannot produce a bundle", ("encode", "ga4gh")),
        _record("C14-CTRL-003", DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, DeploymentFrontierRole.CONTROL, _bundle_payload(offline=False), DeploymentFrontierState.HOLD, ("offline_mode_required",), "online-only deployment is outside the local boundary", ("encode", "ga4gh")),
        _record("C15-POS-001", DeploymentFrontierOperation.FEDERATED_EXECUTION, DeploymentFrontierRole.POSITIVE, _federated_payload(), DeploymentFrontierState.READY, (), "two eligible sites retain only aggregate assignments", ("gdc", "depmap", "ga4gh")),
        _record("C15-CTRL-001", DeploymentFrontierOperation.FEDERATED_EXECUTION, DeploymentFrontierRole.CONTROL, _federated_payload(tasks=[{"task_id": "aggregate-summary", "site_ids": ["site-aggregate-a"], "privacy_cost": 2, "minimum_sample_count": 10}], sites=[{**_federated_payload()["sites"][0], "available": False}, _federated_payload()["sites"][1]]), DeploymentFrontierState.HOLD, ("site_unavailable",), "an unavailable required site leaves the task in review", ("gdc", "depmap", "ga4gh")),
        _record("C15-CTRL-002", DeploymentFrontierOperation.FEDERATED_EXECUTION, DeploymentFrontierRole.CONTROL, _federated_payload(privacy_budget=1), DeploymentFrontierState.HOLD, ("privacy_budget_exceeded",), "privacy cost above the declared budget is denied", ("gdc", "depmap", "ga4gh")),
        _record("C15-CTRL-003", DeploymentFrontierOperation.FEDERATED_EXECUTION, DeploymentFrontierRole.CONTROL, _federated_payload(sites=[{**_federated_payload()["sites"][0], "supported_contexts": ["other-context"]}]), DeploymentFrontierState.HOLD, ("context_not_supported",), "site context mismatch cannot receive a task", ("gdc", "depmap", "ga4gh")),
        _record("C16-POS-001", DeploymentFrontierOperation.RELEASE_ROLLBACK, DeploymentFrontierRole.POSITIVE, _release_payload(), DeploymentFrontierState.RELEASED, (), "release passes tests integrity compatibility and policy gates", ("encode", "ga4gh")),
        _record("C16-CTRL-001", DeploymentFrontierOperation.RELEASE_ROLLBACK, DeploymentFrontierRole.CONTROL, _release_payload(checks={"tests": True, "integrity": False, "compatibility": True, "policy": True}), DeploymentFrontierState.DENIED, ("failed_check:integrity",), "failed integrity gate denies release", ("encode", "ga4gh")),
        _record("C16-CTRL-002", DeploymentFrontierOperation.RELEASE_ROLLBACK, DeploymentFrontierRole.CONTROL, _release_payload(action="rollback", requested_version="0.8.0", previous_version=None), DeploymentFrontierState.DENIED, ("previous_version_missing",), "rollback requires a declared previous version", ("encode", "ga4gh")),
        _record("C16-CTRL-003", DeploymentFrontierOperation.RELEASE_ROLLBACK, DeploymentFrontierRole.CONTROL, _release_payload(requested_version="0.9.0"), DeploymentFrontierState.DENIED, ("version_already_current",), "releasing the current version is denied", ("encode", "ga4gh")),
    )
    body = {
        "fixture_id": "deployment-frontier-public-aggregate-001",
        "fixture_version": DEPLOYMENT_FRONTIER_VERSION,
        "context_key": DEPLOYMENT_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": DEPLOYMENT_FRONTIER_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return DeploymentFrontierFixture(**body, content_address=content_hash(body))


def audit_deployment_frontier_data(fixture: DeploymentFrontierFixture) -> DeploymentFrontierDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    record_ids = [item.record_id for item in fixture.records]
    operation_counts = Counter(item.operation.value for item in fixture.records)
    controls_with_sensitive_markers = tuple(
        item.record_id
        for item in fixture.records
        if any(marker in json.dumps(item.payload).lower() for marker in ("patient_id", "sample_id", "api_key", "password", "token"))
    )
    values = (
        ("source-count", len(fixture.sources), DEPLOYMENT_FRONTIER_SOURCE_COUNT, "public portal receipts"),
        ("record-count", len(fixture.records), DEPLOYMENT_FRONTIER_RECORD_COUNT, "four rows per operation"),
        ("positive-count", len(fixture.positive_records), DEPLOYMENT_FRONTIER_POSITIVE_COUNT, "one positive per capability"),
        ("control-count", len(fixture.control_records), DEPLOYMENT_FRONTIER_CONTROL_COUNT, "three controls per capability"),
        ("unique-record-ids", len(record_ids), len(set(record_ids)), "record identities are unique"),
        ("known-source-links", all(set(item.source_ids) <= source_ids for item in fixture.records), True, "every row links to a receipt"),
        ("https-receipts", all(item.uri.startswith("https://") for item in fixture.sources), True, "sources use HTTPS"),
        ("exact-context", all(item.context_key == fixture.context_key for item in fixture.records), True, "rows share one context"),
        ("no-sensitive-markers", controls_with_sensitive_markers, (), "fixture excludes secrets and patient markers"),
        ("balanced-operations", sorted(operation_counts.values()), [4, 4, 4, 4], "each operation has one positive and three controls"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(DeploymentFrontierDataCheck(**body, content_address=content_hash(body)))
    return DeploymentFrontierDataAudit(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


def load_deployment_frontier_fixture(path: str | Path) -> DeploymentFrontierFixture:
    fixture_path = Path(path)
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("deployment fixture must be an object")
    if raw.get("fixture_version") != DEPLOYMENT_FRONTIER_VERSION:
        raise ValueError("deployment fixture version mismatch")
    expected = default_deployment_frontier_fixture()
    if raw.get("fixture_id") != expected.fixture_id:
        raise ValueError("deployment fixture identity mismatch")
    if raw.get("content_address") != expected.content_address:
        raise ValueError("deployment fixture content address mismatch")
    return expected


def deployment_frontier_fixture_json(fixture: DeploymentFrontierFixture | None = None) -> str:
    return json.dumps(jsonable(fixture or default_deployment_frontier_fixture()), indent=2, sort_keys=True) + "\n"


__all__ = [
    "DEPLOYMENT_FRONTIER_CONTROL_COUNT",
    "DEPLOYMENT_FRONTIER_POSITIVE_COUNT",
    "DEPLOYMENT_FRONTIER_RECORD_COUNT",
    "DEPLOYMENT_FRONTIER_SOURCE_COUNT",
    "DeploymentFrontierDataAudit",
    "DeploymentFrontierDataCheck",
    "audit_deployment_frontier_data",
    "default_deployment_frontier_fixture",
    "deployment_frontier_fixture_json",
    "load_deployment_frontier_fixture",
]
