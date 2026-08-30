"""Portable exact-file package for policy-governed history-diff review."""

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
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy as policy_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_audit as policy_audit_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_runtime as runtime_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_runtime_audit as runtime_audit_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package"
PACKAGE_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package"
MANIFEST_PREFIX = PACKAGE_PREFIX + "-manifest"
SUMMARY_PREFIX = PACKAGE_PREFIX + "-summary"
DEFAULT_PACKAGE_ID = PACKAGE_PREFIX
MANIFEST_ARTIFACT_FILES = ("runtime.json", "policy-audit.json", "runtime-audit.json", "summary.json")
FILES = ("manifest.json",) + MANIFEST_ARTIFACT_FILES
MANIFEST_FIELDS = ("package_id", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("package_id", "runtime_address", "policy_audit_address", "runtime_audit_address", "policy_id", "evaluation_id", "direction", "state", "decision", "accepted", "release_ready", "policy_rule_count", "passed_rule_count", "failed_rule_count", "content_address")
PACKAGE_FIELDS = ("package_id", "version", "boundary", "runtime_address", "policy_audit_address", "runtime_audit_address", "policy_id", "evaluation_id", "direction", "state", "decision", "accepted", "release_ready", "policy_rule_count", "passed_rule_count", "failed_rule_count", "manifest", "summary", "runtime", "policy_audit", "runtime_audit", "content_address")
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, package_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.package_id = _label(package_id, "history diff policy package manifest ID")
        self.files = tuple(_label(item, "history diff policy package manifest file") for item in _sequence(files, "history diff policy package manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "history diff policy package artifact address") for item in _sequence(artifact_addresses, "history diff policy package artifact addresses", MAX_ARTIFACTS))
        self.content_address = _address(content_address, "history diff policy package manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != MAX_ARTIFACTS or not _public(self.to_dict()):
            raise ValidationError("history diff policy package manifest is not canonical")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("history diff policy package manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest:
        value = _mapping(value, "history diff policy package manifest")
        _strict(value, set(cls.FIELDS), "history diff policy package manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest):
        raise ValidationError("history diff policy package manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, package_id: str, runtime_address: str, policy_audit_address: str, runtime_audit_address: str, policy_id: str, evaluation_id: str, direction: str, state: str, decision: str, accepted: bool, release_ready: bool, policy_rule_count: int, passed_rule_count: int, failed_rule_count: int, content_address: str) -> None:
        self.package_id = _label(package_id, "history diff policy package summary ID")
        self.runtime_address = _address(runtime_address, "history diff policy package summary runtime address", runtime_model.RUNTIME_PREFIX)
        self.policy_audit_address = _address(policy_audit_address, "history diff policy package summary policy audit address", policy_audit_model.AUDIT_PREFIX)
        self.runtime_audit_address = _address(runtime_audit_address, "history diff policy package summary runtime audit address", runtime_audit_model.AUDIT_PREFIX)
        self.policy_id = _label(policy_id, "history diff policy package summary policy ID")
        self.evaluation_id = _label(evaluation_id, "history diff policy package summary evaluation ID")
        self.direction = _label(direction, "history diff policy package summary direction")
        self.state = _label(state, "history diff policy package summary state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("history diff policy package summary state is unsupported")
        self.decision = _label(decision, "history diff policy package summary decision")
        if self.decision not in policy_model.DECISIONS:
            raise ValidationError("history diff policy package summary decision is unsupported")
        self.accepted = _bool(accepted, "history diff policy package summary acceptance")
        self.release_ready = _bool(release_ready, "history diff policy package summary release readiness")
        self.policy_rule_count = _count(policy_rule_count, "history diff policy package summary rule count", policy_model.MAX_RULES)
        self.passed_rule_count = _count(passed_rule_count, "history diff policy package summary passed rule count", policy_model.MAX_RULES)
        self.failed_rule_count = _count(failed_rule_count, "history diff policy package summary failed rule count", policy_model.MAX_RULES)
        self.content_address = _address(content_address, "history diff policy package summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.passed_rule_count + self.failed_rule_count != self.policy_rule_count or not _public(self.to_dict()):
            raise ValidationError("history diff policy package summary counts do not replay")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("history diff policy package summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary:
        value = _mapping(value, "history diff policy package summary")
        _strict(value, set(cls.FIELDS), "history diff policy package summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary):
        raise ValidationError("history diff policy package summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage:
    FIELDS = PACKAGE_FIELDS

    def __init__(self, package_id: str, version: str, boundary: str, runtime_address: str, policy_audit_address: str, runtime_audit_address: str, policy_id: str, evaluation_id: str, direction: str, state: str, decision: str, accepted: bool, release_ready: bool, policy_rule_count: int, passed_rule_count: int, failed_rule_count: int, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest | Mapping[str, Any], summary: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary | Mapping[str, Any], runtime: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime | Mapping[str, Any], policy_audit: policy_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyAudit | Mapping[str, Any], runtime_audit: runtime_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeAudit | Mapping[str, Any], content_address: str) -> None:
        self.package_id = _label(package_id, "history diff policy package ID")
        self.version = _text(version, "history diff policy package version")
        self.boundary = _text(boundary, "history diff policy package boundary", 512)
        self.runtime_address = _address(runtime_address, "history diff policy package runtime address", runtime_model.RUNTIME_PREFIX)
        self.policy_audit_address = _address(policy_audit_address, "history diff policy package policy audit address", policy_audit_model.AUDIT_PREFIX)
        self.runtime_audit_address = _address(runtime_audit_address, "history diff policy package runtime audit address", runtime_audit_model.AUDIT_PREFIX)
        self.policy_id = _label(policy_id, "history diff policy package policy ID")
        self.evaluation_id = _label(evaluation_id, "history diff policy package evaluation ID")
        self.direction = _label(direction, "history diff policy package direction")
        if self.direction not in runtime_model.diff_model.DIRECTIONS:
            raise ValidationError("history diff policy package direction is unsupported")
        self.state = _label(state, "history diff policy package state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("history diff policy package state is unsupported")
        self.decision = _label(decision, "history diff policy package decision")
        if self.decision not in policy_model.DECISIONS:
            raise ValidationError("history diff policy package decision is unsupported")
        self.accepted = _bool(accepted, "history diff policy package acceptance")
        self.release_ready = _bool(release_ready, "history diff policy package release readiness")
        self.policy_rule_count = _count(policy_rule_count, "history diff policy package rule count", policy_model.MAX_RULES)
        self.passed_rule_count = _count(passed_rule_count, "history diff policy package passed rule count", policy_model.MAX_RULES)
        self.failed_rule_count = _count(failed_rule_count, "history diff policy package failed rule count", policy_model.MAX_RULES)
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary.from_mapping(summary)
        self.runtime = runtime if isinstance(runtime, runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime) else runtime_model.runtime_from_mapping(runtime)
        self.policy_audit = policy_audit if isinstance(policy_audit, policy_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyAudit) else policy_audit_model.audit_from_mapping(policy_audit)
        self.runtime_audit = runtime_audit if isinstance(runtime_audit, runtime_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntimeAudit) else runtime_audit_model.audit_from_mapping(runtime_audit)
        self.content_address = _address(content_address, "history diff policy package address", PACKAGE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff policy package version or boundary is not current")
        if self.runtime_address != self.runtime.content_address or self.runtime_audit_address != self.runtime_audit.content_address or self.policy_audit_address != self.policy_audit.content_address:
            raise ValidationError("history diff policy package artifact addresses do not replay")
        if self.runtime_audit.runtime_address != self.runtime_address or self.policy_audit.evaluation_address != self.runtime.evaluation_address:
            raise ValidationError("history diff policy package audit links do not replay")
        if (self.policy_id, self.evaluation_id, self.direction, self.decision) != (self.runtime.policy_id, self.runtime.evaluation_id, self.runtime.direction, self.runtime.decision):
            raise ValidationError("history diff policy package decision identity does not replay")
        if (self.policy_rule_count, self.passed_rule_count, self.failed_rule_count) != (self.runtime.passed_rule_count + self.runtime.failed_rule_count, self.runtime.passed_rule_count, self.runtime.failed_rule_count):
            raise ValidationError("history diff policy package rule counts do not replay")
        if (self.summary.package_id, self.summary.runtime_address, self.summary.policy_audit_address, self.summary.runtime_audit_address) != (self.package_id, self.runtime_address, self.policy_audit_address, self.runtime_audit_address):
            raise ValidationError("history diff policy package summary links do not replay")
        if (self.summary.policy_id, self.summary.evaluation_id, self.summary.direction, self.summary.state, self.summary.decision, self.summary.accepted, self.summary.release_ready, self.summary.policy_rule_count, self.summary.passed_rule_count, self.summary.failed_rule_count) != (self.policy_id, self.evaluation_id, self.direction, self.state, self.decision, self.accepted, self.release_ready, self.policy_rule_count, self.passed_rule_count, self.failed_rule_count):
            raise ValidationError("history diff policy package summary values do not replay")
        expected_accepted = self.runtime.accepted and self.policy_audit.accepted and self.runtime_audit.accepted
        if self.accepted != expected_accepted or self.release_ready != (expected_accepted and self.runtime.release_ready) or (self.state == "complete") != expected_accepted:
            raise ValidationError("history diff policy package acceptance does not replay")
        if self.manifest.package_id != self.package_id or self.manifest.files != FILES or tuple(self.manifest.artifact_addresses) != (self.runtime_address, self.policy_audit_address, self.runtime_audit_address, self.summary.content_address) or not _public(self.to_dict()):
            raise ValidationError("history diff policy package manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_package(self) != self.content_address:
            raise ValidationError("history diff policy package address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "version": self.version, "boundary": self.boundary, "runtime_address": self.runtime_address, "policy_audit_address": self.policy_audit_address, "runtime_audit_address": self.runtime_audit_address, "policy_id": self.policy_id, "evaluation_id": self.evaluation_id, "direction": self.direction, "state": self.state, "decision": self.decision, "accepted": self.accepted, "release_ready": self.release_ready, "policy_rule_count": self.policy_rule_count, "passed_rule_count": self.passed_rule_count, "failed_rule_count": self.failed_rule_count, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "runtime": self.runtime.to_dict(), "policy_audit": self.policy_audit.to_dict(), "runtime_audit": self.runtime_audit.to_dict(), "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "summary", "runtime", "policy_audit", "runtime_audit"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage:
        value = _mapping(value, "history diff policy package")
        _strict(value, set(cls.FIELDS), "history diff policy package")
        return cls(*(value[field] for field in cls.FIELDS))


def address_package(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage):
        raise ValidationError("history diff policy package address requires a typed package")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PACKAGE_PREFIX)


def build_package(runtime: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime, *, package_id: str = DEFAULT_PACKAGE_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage:
    if not isinstance(runtime, runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime):
        raise ValidationError("history diff policy package requires a typed runtime")
    policy_audit = policy_audit_model.audit_evaluation(runtime.evaluation)
    runtime_audit = runtime_audit_model.audit_runtime(runtime)
    accepted = runtime.accepted and policy_audit.accepted and runtime_audit.accepted
    state = "complete" if accepted else "incomplete"
    summary_body = {"package_id": package_id, "runtime_address": runtime.content_address, "policy_audit_address": policy_audit.content_address, "runtime_audit_address": runtime_audit.content_address, "policy_id": runtime.policy_id, "evaluation_id": runtime.evaluation_id, "direction": runtime.direction, "state": state, "decision": runtime.decision, "accepted": accepted, "release_ready": accepted and runtime.release_ready, "policy_rule_count": runtime.passed_rule_count + runtime.failed_rule_count, "passed_rule_count": runtime.passed_rule_count, "failed_rule_count": runtime.failed_rule_count, "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    manifest_body = {"package_id": package_id, "files": FILES, "artifact_addresses": (runtime.content_address, policy_audit.content_address, runtime_audit.content_address, summary.content_address)}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    body = {"package_id": package_id, "version": VERSION, "boundary": BOUNDARY, "runtime_address": runtime.content_address, "policy_audit_address": policy_audit.content_address, "runtime_audit_address": runtime_audit.content_address, "policy_id": runtime.policy_id, "evaluation_id": runtime.evaluation_id, "direction": runtime.direction, "state": state, "decision": runtime.decision, "accepted": accepted, "release_ready": accepted and runtime.release_ready, "policy_rule_count": runtime.passed_rule_count + runtime.failed_rule_count, "passed_rule_count": runtime.passed_rule_count, "failed_rule_count": runtime.failed_rule_count, "manifest": manifest, "summary": summary, "runtime": runtime, "policy_audit": policy_audit, "runtime_audit": runtime_audit}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage(**body, content_address=PACKAGE_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage(**body, content_address=address_package(provisional))


def package_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage.from_mapping(value)


def package_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage) -> str:
    return canonical_json(package_from_mapping(value.to_dict()).to_dict())


def package_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage) -> str:
    value = package_from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in PACKAGE_FIELDS if field not in {"manifest", "summary", "runtime", "policy_audit", "runtime_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_package_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage) -> str:
    value = package_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff Policy Package", "", f"- Package: `{value.package_id}`", f"- Decision: `{value.decision}`", f"- State: `{value.state}`", f"- Direction: `{value.direction}`", f"- Rules: `{value.passed_rule_count}/{value.policy_rule_count}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| artifact | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("runtime", value.runtime_address), ("policy-audit", value.policy_audit_address), ("runtime-audit", value.runtime_audit_address), ("summary", value.summary.content_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_package(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage):
        raise ValidationError("history diff policy package persistence requires a typed package")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("history diff policy package destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-resolution-history-diff-policy-package-", dir=str(parent)))
    try:
        documents = {"manifest.json": value.manifest.to_dict(), "runtime.json": value.runtime.to_dict(), "policy-audit.json": value.policy_audit.to_dict(), "runtime-audit.json": value.runtime_audit.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("history diff policy package destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("history diff policy package artifact is not valid JSON") from error
    return _mapping(value, "history diff policy package artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("history diff policy package artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("history diff policy package artifact is not canonical")


def load_package(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("history diff policy package destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("history diff policy package directory does not contain the exact file set")
    raw = {name: _read_json(destination / name) for name in FILES}
    for name, value in raw.items():
        _read_canonical(destination / name, value)
    package = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage(
        raw["summary.json"].get("package_id", ""),
        VERSION,
        BOUNDARY,
        raw["runtime.json"].get("content_address", ""),
        raw["policy-audit.json"].get("content_address", ""),
        raw["runtime-audit.json"].get("content_address", ""),
        raw["runtime.json"].get("policy_id", ""),
        raw["runtime.json"].get("evaluation_id", ""),
        raw["runtime.json"].get("direction", ""),
        raw["summary.json"].get("state", ""),
        raw["runtime.json"].get("decision", ""),
        raw["summary.json"].get("accepted", False),
        raw["summary.json"].get("release_ready", False),
        raw["summary.json"].get("policy_rule_count", 0),
        raw["summary.json"].get("passed_rule_count", 0),
        raw["summary.json"].get("failed_rule_count", 0),
        raw["manifest.json"],
        raw["summary.json"],
        raw["runtime.json"],
        raw["policy-audit.json"],
        raw["runtime-audit.json"],
        PACKAGE_PREFIX + ":pending",
    )
    package = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage(**(package.to_dict() | {"content_address": address_package(package)}))
    if package.manifest.to_dict() != DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest.from_mapping(raw["manifest.json"]).to_dict() or package.to_dict()["content_address"] != address_package(package):
        raise ValidationError("history diff policy package artifacts do not replay")
    return package


def run_package(runtime: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRuntime, *, package_id: str = DEFAULT_PACKAGE_ID, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage:
    value = build_package(runtime, package_id=package_id)
    if destination is not None:
        persist_package(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy package manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"package_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": MAX_ARTIFACTS, "maxItems": MAX_ARTIFACTS}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy package summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"package_id": {"type": "string"}, "runtime_address": {"type": "string"}, "policy_audit_address": {"type": "string"}, "runtime_audit_address": {"type": "string"}, "policy_id": {"type": "string"}, "evaluation_id": {"type": "string"}, "direction": {"type": "string"}, "state": {"enum": ["complete", "incomplete"]}, "decision": {"enum": list(policy_model.DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "policy_rule_count": {"type": "integer", "minimum": 0}, "passed_rule_count": {"type": "integer", "minimum": 0}, "failed_rule_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy package", "type": "object", "additionalProperties": False, "required": list(PACKAGE_FIELDS), "properties": {"package_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "runtime_address": {"type": "string"}, "policy_audit_address": {"type": "string"}, "runtime_audit_address": {"type": "string"}, "policy_id": {"type": "string"}, "evaluation_id": {"type": "string"}, "direction": {"type": "string"}, "state": {"enum": ["complete", "incomplete"]}, "decision": {"enum": list(policy_model.DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "policy_rule_count": {"type": "integer", "minimum": 0}, "passed_rule_count": {"type": "integer", "minimum": 0}, "failed_rule_count": {"type": "integer", "minimum": 0}, "manifest": manifest_schema(), "summary": summary_schema(), "runtime": runtime_model.runtime_schema(), "policy_audit": policy_audit_model.audit_schema(), "runtime_audit": runtime_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_package", "package_from_mapping", "package_json", "package_csv", "render_package_markdown", "persist_package", "load_package", "run_package"), "limits": {"max_artifacts": MAX_ARTIFACTS}}


__all__ = ["BOUNDARY", "DEFAULT_PACKAGE_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ARTIFACTS", "PACKAGE_FIELDS", "PACKAGE_PREFIX", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageSummary", "address_manifest", "address_package", "address_summary", "build_package", "capabilities", "load_package", "manifest_schema", "package_csv", "package_from_mapping", "package_json", "package_schema", "persist_package", "render_package_markdown", "run_package", "summary_schema"]
