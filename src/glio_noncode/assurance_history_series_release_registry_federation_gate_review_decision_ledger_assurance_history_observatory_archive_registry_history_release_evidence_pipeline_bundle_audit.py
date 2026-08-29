"""Independent audit report for durable release-evidence pipeline bundles.

The bundle loader is deliberately fail-fast: it is the right boundary for a
consumer that must refuse malformed input.  This companion audit reads the
same five-file directory with its own checks and returns a bounded report even
when one or more files are damaged.  Each assertion is public and addressed,
so reviewers can identify the failed evidence without receiving the source
directory, timestamps, or process metadata.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle as bundle_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query as query_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = bundle_model.VERSION + "-audit-v1"
BOUNDARY = bundle_model.BOUNDARY + "_audit"
AUDIT_PREFIX = bundle_model.BUNDLE_PREFIX + "-audit"
AUDIT_CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "exact-members",
    "canonical-json",
    "manifest-contract",
    "artifact-receipts",
    "pipeline-linkage",
    "query-linkage",
    "nested-query-results",
    "stage-projection",
    "decision-projection",
    "evidence-projection",
    "public-boundary",
    "content-address",
    "mapping-round-trip",
)
STATES = ("complete", "incomplete")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return pipeline_model._public(value)


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "release evidence bundle audit evidence address", prefix)
    except ValidationError:
        return fallback


class RegistryHistoryReleaseEvidencePipelineBundleAuditCheck:
    """One independent assertion over a durable five-file evidence bundle."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "release evidence bundle audit check ID", 128)
        self.passed = _bool(passed, "release evidence bundle audit check passed")
        self.detail = _text(detail, "release evidence bundle audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "release evidence bundle audit evidence address", 2048)
        self.content_address = content_hash(
            {
                "check_id": self.check_id,
                "passed": self.passed,
                "detail": self.detail,
                "evidence_address": self.evidence_address,
            },
            prefix=AUDIT_CHECK_PREFIX,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "detail": self.detail,
            "evidence_address": self.evidence_address,
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleAuditCheck:
        value = _mapping(value, "release evidence bundle audit check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "release evidence bundle audit check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if result.content_address != value["content_address"]:
            raise ValidationError("release evidence bundle audit check content address mismatch")
        return result


class RegistryHistoryReleaseEvidencePipelineBundleAudit:
    """Complete or incomplete, path-free audit report for one bundle."""

    def __init__(
        self,
        bundle_address: str,
        manifest_address: str,
        pipeline_address: str,
        pipeline_state: str,
        pipeline_accepted: bool,
        state: str,
        complete: bool,
        accepted: bool,
        checks: Sequence[RegistryHistoryReleaseEvidencePipelineBundleAuditCheck],
        content_address: str,
    ) -> None:
        self.bundle_address = bundle_address
        self.manifest_address = manifest_address
        self.pipeline_address = pipeline_address
        self.pipeline_state = pipeline_state
        self.pipeline_accepted = pipeline_accepted
        self.state = state
        self.complete = complete
        self.accepted = accepted
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.bundle_address, "release evidence bundle audit bundle address", bundle_model.BUNDLE_PREFIX)
        _address(self.manifest_address, "release evidence bundle audit manifest address", bundle_model.MANIFEST_PREFIX)
        _address(self.pipeline_address, "release evidence bundle audit pipeline address", pipeline_model.PIPELINE_PREFIX)
        _text(self.pipeline_state, "release evidence bundle audit pipeline state", 32)
        _bool(self.pipeline_accepted, "release evidence bundle audit pipeline acceptance")
        if self.state not in STATES or self.complete != (self.state == "complete"):
            raise ValidationError("release evidence bundle audit state does not match completion")
        _bool(self.complete, "release evidence bundle audit complete")
        _bool(self.accepted, "release evidence bundle audit accepted")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("release evidence bundle audit check set is invalid")
        if any(not isinstance(check, RegistryHistoryReleaseEvidencePipelineBundleAuditCheck) for check in self.checks):
            raise ValidationError("release evidence bundle audit checks must be typed")
        _count(self.passed_count, "release evidence bundle audit passed count", MAX_CHECKS)
        _count(self.failed_count, "release evidence bundle audit failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("release evidence bundle audit counts are not conserved")
        if self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("release evidence bundle audit acceptance does not match checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence bundle audit content address")
        else:
            _address(self.content_address, "release evidence bundle audit content address", AUDIT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("release evidence bundle audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_address": self.bundle_address,
            "manifest_address": self.manifest_address,
            "pipeline_address": self.pipeline_address,
            "pipeline_state": self.pipeline_state,
            "pipeline_accepted": self.pipeline_accepted,
            "state": self.state,
            "complete": self.complete,
            "accepted": self.accepted,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": tuple(check.to_dict() for check in self.checks),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("bundle_address", "manifest_address", "pipeline_address", "pipeline_state", "pipeline_accepted", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleAudit:
        value = _mapping(value, "release evidence bundle audit")
        fields = {"bundle_address", "manifest_address", "pipeline_address", "pipeline_state", "pipeline_accepted", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address"}
        _strict(value, fields, "release evidence bundle audit")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineBundleAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "release evidence bundle audit checks", MAX_CHECKS))
        result = cls(value["bundle_address"], value["manifest_address"], value["pipeline_address"], value["pipeline_state"], value["pipeline_accepted"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])
        if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
            raise ValidationError("release evidence bundle audit derived counts are not conserved")
        return result


def address_audit(value: RegistryHistoryReleaseEvidencePipelineBundleAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundleAudit):
        raise ValidationError("release evidence bundle audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> RegistryHistoryReleaseEvidencePipelineBundleAuditCheck:
    return RegistryHistoryReleaseEvidencePipelineBundleAuditCheck(check_id, passed, detail, evidence)


def _read_directory(source: str | Path) -> tuple[dict[str, bytes], set[str], bool]:
    try:
        directory = Path(source)
        if directory.is_symlink() or not directory.is_dir():
            return {}, set(), False
        members = tuple(directory.iterdir())
        names = {item.name for item in members}
        exact = names == set(bundle_model.FILES)
        payload: dict[str, bytes] = {}
        for item in members:
            if item.is_symlink() or not item.is_file():
                exact = False
                continue
            if item.name not in bundle_model.FILES:
                continue
            try:
                if item.stat().st_size <= bundle_model.MAX_ARTIFACT_BYTES:
                    payload[item.name] = item.read_bytes()
            except OSError:
                exact = False
        return payload, names, exact and set(payload) == set(bundle_model.FILES)
    except (OSError, ValueError):
        return {}, set(), False


def _decode_documents(payload: Mapping[str, bytes]) -> tuple[dict[str, Mapping[str, Any]], bool]:
    documents: dict[str, Mapping[str, Any]] = {}
    canonical = bool(payload) and set(payload) == set(bundle_model.FILES)
    for name in bundle_model.FILES:
        raw = payload.get(name)
        if raw is None:
            canonical = False
            continue
        try:
            document = json.loads(raw.decode("utf-8"))
            documents[name] = _mapping(document, f"release evidence bundle {name}")
            if canonical_bytes(document) != raw:
                canonical = False
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            canonical = False
    return documents, canonical


def _typed_pipeline(document: Mapping[str, Any]) -> pipeline_model.RegistryHistoryReleaseEvidencePipeline | None:
    try:
        return pipeline_model.pipeline_from_mapping(document)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


def _typed_query(document: Mapping[str, Any]) -> query_model.RegistryHistoryReleaseEvidencePipelineQueryResult | None:
    try:
        return query_model.query_result_from_mapping(document)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


def _manifest_contract(manifest: Mapping[str, Any]) -> bool:
    try:
        _strict(manifest, {"version", "boundary", "pipeline_address", "artifact_count", "files", "query_addresses", "artifacts", "manifest_address"}, "release evidence bundle manifest")
        expected = content_hash(dict(manifest) | {"manifest_address": None}, prefix=bundle_model.MANIFEST_PREFIX)
        return (
            manifest.get("version") == bundle_model.VERSION
            and manifest.get("boundary") == bundle_model.BOUNDARY
            and manifest.get("pipeline_address", "").startswith(pipeline_model.PIPELINE_PREFIX + ":")
            and manifest.get("artifact_count") == len(bundle_model.ARTIFACT_FILES)
            and manifest.get("files") == list(bundle_model.ARTIFACT_FILES)
            and isinstance(manifest.get("query_addresses"), list)
            and len(manifest["query_addresses"]) == len(bundle_model.QUERY_ARTIFACTS)
            and manifest.get("manifest_address") == expected
        )
    except (ValidationError, TypeError):
        return False


def _artifact_receipts(manifest: Mapping[str, Any], payload: Mapping[str, bytes]) -> bool:
    try:
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != len(bundle_model.ARTIFACT_FILES):
            return False
        observed: set[str] = set()
        for item in artifacts:
            item = _mapping(item, "release evidence bundle artifact receipt")
            _strict(item, {"name", "size", "hash"}, "release evidence bundle artifact receipt")
            name = item.get("name")
            if name not in bundle_model.ARTIFACT_FILES or name not in payload or dict(item) != {"name": name, "size": len(payload[name]), "hash": hash_bytes(payload[name], prefix=bundle_model.BUNDLE_PREFIX + "-artifact")}:
                return False
            observed.add(name)
        return observed == set(bundle_model.ARTIFACT_FILES)
    except (ValidationError, TypeError, KeyError):
        return False


def _expected_query(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline, resource: str) -> query_model.RegistryHistoryReleaseEvidencePipelineQueryResult:
    return query_model.query_pipeline(value, resource=resource, limit=query_model.MAX_QUERY_ITEMS)


def _audit_documents(payload: Mapping[str, bytes], documents: Mapping[str, Mapping[str, Any]], members_exact: bool) -> RegistryHistoryReleaseEvidencePipelineBundleAudit:
    manifest = documents.get(bundle_model.MANIFEST_NAME, {})
    pipeline_document = documents.get(bundle_model.PIPELINE_NAME, {})
    typed_pipeline = _typed_pipeline(pipeline_document)
    typed_queries = {name: _typed_query(documents[name]) for name in bundle_model.QUERY_ARTIFACTS if name in documents}
    fallback_bundle = bundle_model.BUNDLE_PREFIX + ":unresolved"
    fallback_manifest = bundle_model.MANIFEST_PREFIX + ":unresolved"
    fallback_pipeline = pipeline_model.PIPELINE_PREFIX + ":unresolved"
    bundle_address = _safe_address(manifest.get("bundle_address"), bundle_model.BUNDLE_PREFIX, fallback_bundle)
    manifest_address = _safe_address(manifest.get("manifest_address"), bundle_model.MANIFEST_PREFIX, fallback_manifest)
    pipeline_address = _safe_address(manifest.get("pipeline_address"), pipeline_model.PIPELINE_PREFIX, fallback_pipeline)
    pipeline_state = typed_pipeline.state if typed_pipeline is not None else "held"
    pipeline_accepted = typed_pipeline.accepted if typed_pipeline is not None else False
    if typed_pipeline is not None:
        pipeline_address = typed_pipeline.content_address

    canonical_ok = bool(payload) and set(payload) == set(bundle_model.FILES) and set(documents) == set(bundle_model.FILES) and all(canonical_bytes(documents[name]) == payload[name] for name in bundle_model.FILES)
    manifest_ok = _manifest_contract(manifest)
    receipt_ok = _artifact_receipts(manifest, payload)
    pipeline_linkage_ok = typed_pipeline is not None and manifest.get("pipeline_address") == typed_pipeline.content_address and pipeline_document.get("content_address") == typed_pipeline.content_address
    query_linkage_ok = typed_pipeline is not None and all(typed_queries.get(name) is not None for name in bundle_model.QUERY_ARTIFACTS) and manifest.get("query_addresses") == [typed_queries[name].content_address for name in bundle_model.QUERY_ARTIFACTS]
    nested_queries_ok = typed_pipeline is not None and all(query.pipeline_address == typed_pipeline.content_address and query_model.address_query(query) == query.content_address for query in typed_queries.values()) and set(typed_queries) == set(bundle_model.QUERY_ARTIFACTS)
    stage_projection_ok = typed_pipeline is not None and typed_queries.get(bundle_model.STAGES_NAME) is not None and typed_queries[bundle_model.STAGES_NAME].to_dict() == _expected_query(typed_pipeline, "stages").to_dict()
    decision_projection_ok = typed_pipeline is not None and typed_queries.get(bundle_model.DECISIONS_NAME) is not None and typed_queries[bundle_model.DECISIONS_NAME].to_dict() == _expected_query(typed_pipeline, "decisions").to_dict()
    evidence_projection_ok = typed_pipeline is not None and typed_queries.get(bundle_model.EVIDENCE_NAME) is not None and typed_queries[bundle_model.EVIDENCE_NAME].to_dict() == _expected_query(typed_pipeline, "evidence").to_dict()
    public_ok = all(_public(document) for document in documents.values())
    content_ok = False
    if typed_pipeline is not None and set(payload) == set(bundle_model.FILES):
        expected_payload = bundle_model.bundle_bytes(typed_pipeline)
        content_ok = all(expected_payload[name] == payload[name] for name in bundle_model.FILES)
        if content_ok:
            bundle_address = bundle_model.address_bundle(bundle_model.build_bundle(typed_pipeline))
            manifest_address = json.loads(expected_payload[bundle_model.MANIFEST_NAME].decode("utf-8"))["manifest_address"]
    mapping_round_trip_ok = typed_pipeline is not None and all(query is not None for query in typed_queries.values())
    if mapping_round_trip_ok:
        try:
            mapping_round_trip_ok = pipeline_model.pipeline_from_mapping(typed_pipeline.to_dict()).to_dict() == typed_pipeline.to_dict() and all(query_model.query_result_from_mapping(typed_queries[name].to_dict()).to_dict() == typed_queries[name].to_dict() for name in bundle_model.QUERY_ARTIFACTS)
        except (ValidationError, KeyError, TypeError, ValueError):
            mapping_round_trip_ok = False

    checks = (
        _check("exact-members", members_exact, "bundle contains exactly the five declared regular files", bundle_address),
        _check("canonical-json", canonical_ok, "every bundle artifact is canonical UTF-8 JSON within the byte limit", bundle_address),
        _check("manifest-contract", manifest_ok, "manifest version, boundary, file list, count, query list, and address reproduce", manifest_address),
        _check("artifact-receipts", receipt_ok, "manifest artifact byte receipts reproduce the stored artifacts", manifest_address),
        _check("pipeline-linkage", pipeline_linkage_ok, "manifest and pipeline documents agree on the pipeline identity", pipeline_address),
        _check("query-linkage", query_linkage_ok, "manifest query addresses link to the three declared query artifacts", pipeline_address),
        _check("nested-query-results", nested_queries_ok, "query pages are typed, public, pipeline-linked, and content-addressed", pipeline_address),
        _check("stage-projection", stage_projection_ok, "stages-query reproduces the pipeline stage projection", pipeline_address),
        _check("decision-projection", decision_projection_ok, "decisions-query reproduces the pipeline decision projection", pipeline_address),
        _check("evidence-projection", evidence_projection_ok, "evidence-query reproduces the pipeline evidence projection", pipeline_address),
        _check("public-boundary", public_ok, "all decoded bundle documents contain only public fields", bundle_address),
        _check("content-address", content_ok, "recomputed pipeline, query, manifest, and bundle bytes reproduce exactly", bundle_address),
        _check("mapping-round-trip", mapping_round_trip_ok, "pipeline and query documents rehydrate without projection drift", pipeline_address),
    )
    complete = all(check.passed for check in checks)
    body = {"bundle_address": bundle_address, "manifest_address": manifest_address, "pipeline_address": pipeline_address, "pipeline_state": pipeline_state, "pipeline_accepted": pipeline_accepted, "state": "complete" if complete else "incomplete", "complete": complete, "accepted": complete, "checks": checks}
    provisional = RegistryHistoryReleaseEvidencePipelineBundleAudit(**body, content_address="pending:audit")
    return RegistryHistoryReleaseEvidencePipelineBundleAudit(**body, content_address=address_audit(provisional))


def audit_bundle_directory(source: str | Path) -> RegistryHistoryReleaseEvidencePipelineBundleAudit:
    """Audit a raw bundle directory, preserving diagnostics for malformed input."""

    payload, names, members_exact = _read_directory(source)
    documents, _ = _decode_documents(payload)
    return _audit_documents(payload, documents, members_exact and names == set(bundle_model.FILES))


def audit_bundle(source: str | Path) -> RegistryHistoryReleaseEvidencePipelineBundleAudit:
    """Alias for the public directory audit boundary."""

    return audit_bundle_directory(source)


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleAudit:
    return RegistryHistoryReleaseEvidencePipelineBundleAudit.from_mapping(value)


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineBundleAudit) -> RegistryHistoryReleaseEvidencePipelineBundleAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundleAudit):
        raise ValidationError("release evidence bundle audit verification requires a typed audit")
    value._validate()
    return value


def audit_json(value: RegistryHistoryReleaseEvidencePipelineBundleAudit) -> str:
    verify_audit(value)
    return canonical_json(value.to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineBundleAudit) -> str:
    verify_audit(value)
    lines = [
        "# Assurance History Observatory Archive Registry History Release Evidence Pipeline Bundle Audit",
        "",
        f"- State: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Bundle: `{value.bundle_address}`",
        f"- Manifest: `{value.manifest_address}`",
        f"- Pipeline: `{value.pipeline_address}`",
        f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed",
        f"- Content address: `{value.content_address}`",
        "",
        "| Check | Passed | Detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "minLength": 1, "maxLength": 128}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_CHECK_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def audit_schema() -> dict[str, Any]:
    fields = {"bundle_address": {"type": "string", "pattern": "^" + bundle_model.BUNDLE_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + bundle_model.MANIFEST_PREFIX + ":"}, "pipeline_address": {"type": "string", "pattern": "^" + pipeline_model.PIPELINE_PREFIX + ":"}, "pipeline_state": {"type": "string"}, "pipeline_accepted": {"type": "boolean"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "checks": CHECK_IDS, "states": STATES, "limits": {"max_checks": MAX_CHECKS, "max_artifacts": len(bundle_model.FILES)}, "features": ("independent raw five-file audit", "malformed bundle diagnostics", "canonical JSON and byte receipt replay", "pipeline and query linkage audit", "stage decision and evidence projection replay", "public-boundary audit", "content-addressed report", "path-free JSON and Markdown projection"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_CHECK_PREFIX",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineBundleAudit",
    "RegistryHistoryReleaseEvidencePipelineBundleAuditCheck",
    "address_audit",
    "audit_bundle",
    "audit_bundle_directory",
    "audit_from_mapping",
    "audit_json",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
