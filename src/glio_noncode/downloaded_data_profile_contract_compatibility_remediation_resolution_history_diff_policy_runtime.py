"""Exact-file runtime closure for policy-governed history-diff release review."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as diff_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_audit as diff_audit_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy as policy_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_audit as policy_audit_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_query as query_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_query_audit as query_audit_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-runtime-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_runtime"
RUNTIME_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
MANIFEST_ARTIFACT_FILES = ("diff.json", "policy.json", "evaluation.json", "audit.json", "query.json", "query-audit.json")
FILES = ("manifest.json",) + MANIFEST_ARTIFACT_FILES + ("runtime.json",)
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = ("runtime_id", "version", "boundary", "policy_id", "policy_address", "evaluation_id", "evaluation_address", "diff_address", "audit_address", "query_address", "query_audit_address", "direction", "state", "decision", "accepted", "release_ready", "passed_rule_count", "failed_rule_count", "manifest", "diff", "policy", "evaluation", "audit", "query", "query_audit", "content_address")
MAX_ARTIFACTS = len(MANIFEST_ARTIFACT_FILES)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history diff policy runtime manifest ID")
        self.files = tuple(_label(item, "history diff policy runtime manifest file") for item in _sequence(files, "history diff policy runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "history diff policy runtime artifact address") for item in _sequence(artifact_addresses, "history diff policy runtime artifact addresses", MAX_ARTIFACTS))
        self.content_address = _address(content_address, "history diff policy runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != MAX_ARTIFACTS or not _public(self.to_dict()):
            raise ValidationError("history diff policy runtime manifest is not canonical")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("history diff policy runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest:
        value = _mapping(value, "history diff policy runtime manifest")
        _strict(value, set(cls.FIELDS), "history diff policy runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest):
        raise ValidationError("history diff policy manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, policy_id: str, policy_address: str, evaluation_id: str, evaluation_address: str, diff_address: str, audit_address: str, query_address: str, query_audit_address: str, direction: str, state: str, decision: str, accepted: bool, release_ready: bool, passed_rule_count: int, failed_rule_count: int, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest | Mapping[str, Any], diff: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff | Mapping[str, Any], policy: policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy | Mapping[str, Any], evaluation: policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation | Mapping[str, Any], audit: diff_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit | Mapping[str, Any], query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history diff policy runtime ID")
        self.version = _text(version, "history diff policy runtime version")
        self.boundary = _text(boundary, "history diff policy runtime boundary", 512)
        self.policy_id = _label(policy_id, "history diff policy runtime policy ID")
        self.policy_address = _address(policy_address, "history diff policy runtime policy address", policy_model.POLICY_PREFIX)
        self.evaluation_id = _label(evaluation_id, "history diff policy runtime evaluation ID")
        self.evaluation_address = _address(evaluation_address, "history diff policy runtime evaluation address", policy_model.EVALUATION_PREFIX)
        self.diff_address = _address(diff_address, "history diff policy runtime diff address", diff_model.DIFF_PREFIX)
        self.audit_address = _address(audit_address, "history diff policy runtime audit address", diff_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "history diff policy runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "history diff policy runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.direction = _label(direction, "history diff policy runtime direction")
        if self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("history diff policy runtime direction is unsupported")
        self.state = _label(state, "history diff policy runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("history diff policy runtime state is unsupported")
        self.decision = _label(decision, "history diff policy runtime decision")
        if self.decision not in policy_model.DECISIONS:
            raise ValidationError("history diff policy runtime decision is unsupported")
        self.accepted = _bool(accepted, "history diff policy runtime acceptance")
        self.release_ready = _bool(release_ready, "history diff policy runtime release readiness")
        self.passed_rule_count = _count(passed_rule_count, "history diff policy runtime passed rule count", policy_model.MAX_RULES)
        self.failed_rule_count = _count(failed_rule_count, "history diff policy runtime failed rule count", policy_model.MAX_RULES)
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest.from_mapping(manifest)
        self.diff = diff if isinstance(diff, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) else diff_model.diff_from_mapping(diff)
        self.policy = policy if isinstance(policy, policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy) else policy_model.policy_from_mapping(policy)
        self.evaluation = evaluation if isinstance(evaluation, policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation) else policy_model.evaluation_from_mapping(evaluation)
        self.audit = audit if isinstance(audit, diff_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit) else diff_audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "history diff policy runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff policy runtime version or boundary is not current")
        if (self.policy_id, self.policy_address) != (self.policy.policy_id, self.policy.content_address):
            raise ValidationError("history diff policy runtime policy linkage does not replay")
        if (self.evaluation_id, self.evaluation_address) != (self.evaluation.evaluation_id, self.evaluation.content_address):
            raise ValidationError("history diff policy runtime evaluation linkage does not replay")
        if (self.evaluation.policy_id, self.evaluation.policy_address) != (self.policy_id, self.policy_address):
            raise ValidationError("history diff policy runtime evaluation policy link does not replay")
        policy_audit = policy_audit_model.audit_evaluation(self.evaluation)
        if not policy_audit.accepted:
            raise ValidationError("history diff policy runtime policy evaluation audit is not accepted")
        if (self.evaluation.diff_id, self.evaluation.diff_address) != (self.diff.diff_id, self.diff.content_address):
            raise ValidationError("history diff policy runtime evaluation diff link does not replay")
        if self.diff_address != self.diff.content_address or self.audit.diff_address != self.diff_address or self.query.evaluation_address != self.evaluation_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("history diff policy runtime component links do not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("history diff policy runtime artifact addresses do not replay")
        if (self.direction, self.decision) != (self.evaluation.direction, self.evaluation.decision):
            raise ValidationError("history diff policy runtime decision aggregates do not replay")
        if (self.passed_rule_count, self.failed_rule_count) != (self.evaluation.passed_rule_count, self.evaluation.failed_rule_count):
            raise ValidationError("history diff policy runtime rule aggregates do not replay")
        expected_accepted = self.evaluation.accepted and self.audit.accepted and self.query_audit.accepted
        expected_ready = expected_accepted and self.evaluation.release_ready
        if self.accepted != expected_accepted or self.release_ready != expected_ready or (self.state == "complete") != expected_accepted:
            raise ValidationError("history diff policy runtime readiness does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("history diff policy runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("history diff policy runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "policy_id": self.policy_id, "policy_address": self.policy_address, "evaluation_id": self.evaluation_id, "evaluation_address": self.evaluation_address, "diff_address": self.diff_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "direction": self.direction, "state": self.state, "decision": self.decision, "accepted": self.accepted, "release_ready": self.release_ready, "passed_rule_count": self.passed_rule_count, "failed_rule_count": self.failed_rule_count, "manifest": self.manifest.to_dict(), "diff": self.diff.to_dict(), "policy": self.policy.to_dict(), "evaluation": self.evaluation.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "diff", "policy", "evaluation", "audit", "query", "query_audit"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime:
        value = _mapping(value, "history diff policy runtime")
        _strict(value, set(cls.FIELDS), "history diff policy runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime):
        raise ValidationError("history diff policy runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(diff: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff, *, policy: policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy | None = None, runtime_id: str = DEFAULT_RUNTIME_ID, evaluation_id: str = policy_model.EVALUATION_PREFIX, resources: Sequence[str] = query_model.RESOURCES, resource: str = "", rule_id: str = "", passed: bool | None = None, text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime:
    if not isinstance(diff, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff):
        raise ValidationError("history diff policy runtime requires a typed diff")
    policy = policy_model.default_policy() if policy is None else policy
    if not isinstance(policy, policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy):
        raise ValidationError("history diff policy runtime policy must be typed")
    diff_audit = diff_audit_model.audit_diff(diff)
    evaluation = policy_model.evaluate(diff, policy=policy, evaluation_id=evaluation_id)
    policy_audit = policy_audit_model.audit_evaluation(evaluation)
    query = query_model.query_evaluation(evaluation, resources=resources, resource=resource, rule_id=rule_id, passed=passed, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (diff.content_address, policy.content_address, evaluation.content_address, diff_audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = evaluation.accepted and diff_audit.accepted and policy_audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "policy_id": policy.policy_id, "policy_address": policy.content_address, "evaluation_id": evaluation.evaluation_id, "evaluation_address": evaluation.content_address, "diff_address": diff.content_address, "audit_address": diff_audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "direction": evaluation.direction, "state": "complete" if accepted else "incomplete", "decision": evaluation.decision, "accepted": accepted, "release_ready": accepted and evaluation.release_ready, "passed_rule_count": evaluation.passed_rule_count, "failed_rule_count": evaluation.failed_rule_count, "manifest": manifest, "diff": diff, "policy": policy, "evaluation": evaluation, "audit": diff_audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime) -> str:
    return canonical_json(runtime_from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in RUNTIME_FIELDS if field not in {"manifest", "diff", "policy", "evaluation", "audit", "query", "query_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_runtime_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff Policy Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Policy: `{value.policy_address}`", f"- Decision: `{value.decision}`", f"- State: `{value.state}`", f"- Direction: `{value.direction}`", f"- Rules: `{value.passed_rule_count}/{value.passed_rule_count + value.failed_rule_count}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("diff", value.diff_address), ("policy", value.policy_address), ("evaluation", value.evaluation_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime):
        raise ValidationError("history diff policy runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("history diff policy runtime destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-resolution-history-diff-policy-runtime-", dir=str(parent)))
    try:
        documents = {"manifest.json": value.manifest.to_dict(), "diff.json": value.diff.to_dict(), "policy.json": value.policy.to_dict(), "evaluation.json": value.evaluation.to_dict(), "audit.json": value.audit.to_dict(), "query.json": value.query.to_dict(), "query-audit.json": value.query_audit.to_dict(), "runtime.json": value.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("history diff policy runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("history diff policy runtime artifact is not valid JSON") from error
    return _mapping(value, "history diff policy runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("history diff policy runtime destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("history diff policy runtime directory does not contain the exact file set")
    runtime = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("history diff policy runtime manifest differs from runtime.json")
    artifacts = {"diff.json": diff_model.diff_from_mapping(_read_json(destination / "diff.json")), "policy.json": policy_model.policy_from_mapping(_read_json(destination / "policy.json")), "evaluation.json": policy_model.evaluation_from_mapping(_read_json(destination / "evaluation.json")), "audit.json": diff_audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"diff.json": runtime.diff, "policy.json": runtime.policy, "evaluation.json": runtime.evaluation, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"history diff policy runtime artifact {name} differs from runtime.json")
    if tuple(runtime.manifest.artifact_addresses) != tuple(artifacts[name].content_address for name in MANIFEST_ARTIFACT_FILES):
        raise ValidationError("history diff policy runtime manifest artifact addresses do not replay")
    return runtime


def run_runtime(diff: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff, *, policy: policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy | None = None, runtime_id: str = DEFAULT_RUNTIME_ID, evaluation_id: str = policy_model.EVALUATION_PREFIX, resources: Sequence[str] = query_model.RESOURCES, resource: str = "", rule_id: str = "", passed: bool | None = None, text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime:
    value = build_runtime(diff, policy=policy, runtime_id=runtime_id, evaluation_id=evaluation_id, resources=resources, resource=resource, rule_id=rule_id, passed=passed, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": MAX_ARTIFACTS, "maxItems": MAX_ARTIFACTS}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "policy_id": {"type": "string"}, "policy_address": {"type": "string"}, "evaluation_id": {"type": "string"}, "evaluation_address": {"type": "string"}, "diff_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "direction": {"enum": list(diff_model.DIRECTIONS)}, "state": {"enum": ["complete", "incomplete"]}, "decision": {"enum": list(policy_model.DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "passed_rule_count": {"type": "integer", "minimum": 0, "maximum": policy_model.MAX_RULES}, "failed_rule_count": {"type": "integer", "minimum": 0, "maximum": policy_model.MAX_RULES}, "manifest": manifest_schema(), "diff": diff_model.diff_schema(), "policy": policy_model.policy_schema(), "evaluation": policy_model.evaluation_schema(), "audit": diff_audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"max_artifacts": MAX_ARTIFACTS}}


__all__ = ["BOUNDARY", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ARTIFACTS", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeManifest", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
