"""Portable, independently verifiable releases for public mission plans.

The public mission planner produces a useful receipt, but a receipt alone is
not a durable handoff.  This module packages that receipt and its human and
tabular projections into an exact-byte directory with a closed manifest.  A
consumer can verify the directory on another machine, hydrate the typed
receipt without the planner, and refuse tampered or incomplete material.

Only the lossy public mission contract is accepted here.  Internal routing
identifiers, producer metadata, model metadata, programming-language
metadata, identity, and raw request payloads are never copied into release
artifacts or manifests.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_runtime_public import (
    MISSION_PLAN_PUBLIC_VERSION,
    MissionPlanPublicReceipt,
    mission_plan_public_csv,
    mission_plan_public_json,
    render_mission_plan_public_markdown,
)
from .module_fabric_support import contains_private_key
from .serialization import canonical_json, content_hash, hash_bytes, jsonable


MISSION_PLAN_RELEASE_VERSION = "mission-plan-release-v1"
MISSION_PLAN_RELEASE_MANIFEST_FILE = "manifest.json"
MISSION_PLAN_RELEASE_MANIFEST_PREFIX = "mission-plan-release-manifest"
MISSION_PLAN_RELEASE_ARTIFACT_PREFIX = "mission-plan-release-artifact"
MISSION_PLAN_RELEASE_CHECKS_VERSION = "mission-plan-release-checks-v1"
MISSION_PLAN_RELEASE_CHECKS_PREFIX = "mission-plan-release-checks"
MISSION_PLAN_RELEASE_SUMMARY_VERSION = "mission-plan-release-summary-v1"
MISSION_PLAN_RELEASE_SUMMARY_PREFIX = "mission-plan-release-summary"
MISSION_PLAN_RELEASE_SCHEMA_VERSION = "mission-plan-release-schema-v1"
MISSION_PLAN_RELEASE_CAPABILITIES_VERSION = "mission-plan-release-capabilities-v1"
MISSION_PLAN_RELEASE_MAX_ARTIFACTS = 32
MISSION_PLAN_RELEASE_MAX_CHECKS = 32

MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS = frozenset(
    {
        "mission-plan.json",
        "mission-plan.md",
        "mission-plan-steps.csv",
        "release-checks.json",
        "release-summary.json",
    }
)

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_ids",
        "assistant",
        "assistant_id",
        "author",
        "author_id",
        "contact",
        "credential",
        "email",
        "generated_by",
        "individual",
        "language",
        "model",
        "model_id",
        "model_version",
        "patient",
        "phone",
        "producer",
        "programming_language",
        "role_id",
        "sample",
        "secret",
        "selected_agent_ids",
        "selected_tool_ids",
        "subject",
        "token",
        "tool_id",
        "tool_ids",
    }
)


def _text(value: Any, field: str, *, maximum: int | None = None) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if maximum is not None and len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _private_key_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                paths.append(child)
            paths.extend(_private_key_paths(item, child))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, item in enumerate(value):
            paths.extend(_private_key_paths(item, f"{path}[{index}]"))
        return tuple(paths)
    return ()


def _safe_filename(value: Any) -> str:
    filename = str(value)
    path = Path(filename)
    if (
        not filename
        or path.name != filename
        or filename in {".", "..", MISSION_PLAN_RELEASE_MANIFEST_FILE}
    ):
        raise ValidationError(f"unsafe mission plan release filename: {filename!r}")
    return filename


def _media_type(filename: str) -> str:
    if filename.endswith(".json"):
        return "application/json"
    if filename.endswith(".csv"):
        return "text/csv"
    return "text/markdown"


def _artifact(artifact_id: str, filename: str, payload: bytes) -> "MissionPlanReleaseArtifact":
    _safe_filename(filename)
    try:
        line_count = len(payload.decode("utf-8").splitlines())
    except UnicodeDecodeError as exc:
        raise ValidationError(f"mission plan release artifact is not UTF-8: {filename}") from exc
    return MissionPlanReleaseArtifact(
        artifact_id=_text(artifact_id, "artifact_id"),
        filename=filename,
        media_type=_media_type(filename),
        byte_count=len(payload),
        line_count=line_count,
        content_address=hash_bytes(payload, prefix=MISSION_PLAN_RELEASE_ARTIFACT_PREFIX),
        payload=payload,
    )


def _address_without_content(
    value: Mapping[str, Any],
    *,
    prefix: str,
    field: str,
) -> str:
    address = _text(value.get("content_address"), f"{field}.content_address")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if content_hash(body, prefix=prefix) != address:
        raise ValidationError(f"{field} content address does not reconcile")
    return address


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCheck:
    """One deterministic release-integrity check."""

    check_id: str
    category: str
    accepted: bool
    expected: Any
    observed: Any
    message: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id")
        _text(self.category, "category")
        _text(self.message, "message")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCheck":
        body = _mapping(value, "release check")
        allowed = {
            "check_id",
            "category",
            "accepted",
            "expected",
            "observed",
            "message",
            "content_address",
        }
        unexpected = set(body) - allowed
        if unexpected:
            raise ValidationError(f"release check contains unsupported fields: {sorted(unexpected)}")
        check = cls(
            check_id=_text(body.get("check_id"), "check.check_id"),
            category=_text(body.get("category"), "check.category"),
            accepted=bool(body.get("accepted")),
            expected=body.get("expected"),
            observed=body.get("observed"),
            message=_text(body.get("message"), "check.message"),
            content_address=_text(body.get("content_address"), "check.content_address"),
        )
        expected_address = content_hash(
            {key: item for key, item in check.to_dict().items() if key != "content_address"},
            prefix="mission-plan-release-check",
        )
        if expected_address != check.content_address:
            raise ValidationError("release check content address does not reconcile")
        return check


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseArtifact:
    """One exact-byte artifact in a mission-plan release."""

    artifact_id: str
    filename: str
    media_type: str
    byte_count: int
    line_count: int
    content_address: str
    payload: bytes

    def __post_init__(self) -> None:
        _text(self.artifact_id, "artifact_id")
        _safe_filename(self.filename)
        if self.media_type != _media_type(self.filename):
            raise ValidationError("artifact media type does not match its filename")
        if self.byte_count != len(self.payload):
            raise ValidationError("artifact byte count does not reconcile")
        try:
            actual_lines = len(self.payload.decode("utf-8").splitlines())
        except UnicodeDecodeError as exc:
            raise ValidationError("artifact payload must be UTF-8") from exc
        if self.line_count != actual_lines:
            raise ValidationError("artifact line count does not reconcile")
        if hash_bytes(self.payload, prefix=MISSION_PLAN_RELEASE_ARTIFACT_PREFIX) != self.content_address:
            raise ValidationError("artifact content address does not reconcile")

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload:
            body["content"] = self.payload.decode("utf-8")
        return body


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseBundle:
    """Public mission receipt and closed exact-byte handoff."""

    release_id: str
    plan_id: str
    plan_address: str
    state: str
    accepted: bool
    receipt: MissionPlanPublicReceipt
    checks: tuple[MissionPlanReleaseCheck, ...]
    artifacts: tuple[MissionPlanReleaseArtifact, ...]
    manifest: Mapping[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        _text(self.release_id, "release_id")
        _text(self.plan_id, "plan_id")
        _text(self.plan_address, "plan_address")
        _text(self.state, "state")
        if self.receipt.plan_id != self.plan_id or self.receipt.content_address != self.plan_address:
            raise ValidationError("release receipt does not match its plan address")
        if len(self.artifacts) > MISSION_PLAN_RELEASE_MAX_ARTIFACTS:
            raise ValidationError("mission plan release artifact count exceeds the bound")
        if len(self.checks) > MISSION_PLAN_RELEASE_MAX_CHECKS:
            raise ValidationError("mission plan release check count exceeds the bound")
        filenames = [item.filename for item in self.artifacts]
        if len(filenames) != len(set(filenames)):
            raise ValidationError("mission plan release artifact filenames must be unique")

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "release_version": MISSION_PLAN_RELEASE_VERSION,
            "release_id": self.release_id,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "state": self.state,
            "accepted": self.accepted,
            "receipt": self.receipt.to_dict(),
            "checks": [item.to_dict() for item in self.checks],
            "artifacts": [item.to_dict(include_payload=include_payloads) for item in self.artifacts],
            "manifest": jsonable(self.manifest),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseVerification:
    """Independent filesystem verification receipt."""

    path: str
    release_id: str
    accepted: bool
    manifest_version_valid: bool
    manifest_address_valid: bool
    receipt_address_valid: bool
    checks_valid: bool
    summary_valid: bool
    artifact_set_valid: bool
    exact_bytes: bool
    public_boundary_valid: bool
    artifact_count: int
    verified_artifact_count: int
    missing_files: tuple[str, ...]
    unexpected_files: tuple[str, ...]
    unsafe_files: tuple[str, ...]
    tampered_files: tuple[str, ...]
    boundary_violations: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanOfflineRelease:
    """Verified release hydrated without a live planner."""

    path: str
    release_id: str
    plan_id: str
    plan_address: str
    receipt: MissionPlanPublicReceipt
    checks: tuple[MissionPlanReleaseCheck, ...]
    manifest: Mapping[str, Any]
    verification: MissionPlanReleaseVerification
    accepted: bool
    content_address: str

    def to_dict(self, *, include_receipt: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "release_version": MISSION_PLAN_RELEASE_VERSION,
            "path": self.path,
            "release_id": self.release_id,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "accepted": self.accepted,
            "check_count": len(self.checks),
            "manifest_address": self.manifest.get("manifest_address"),
            "verification": self.verification.to_dict(),
            "content_address": self.content_address,
        }
        if include_receipt:
            body["receipt"] = self.receipt.to_dict()
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def _check(
    check_id: str,
    category: str,
    accepted: bool,
    expected: Any,
    observed: Any,
    message: str,
) -> MissionPlanReleaseCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "accepted": accepted,
        "expected": expected,
        "observed": observed,
        "message": message,
    }
    return MissionPlanReleaseCheck(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-check"),
    )


def _workflow_order_valid(receipt: MissionPlanPublicReceipt) -> bool:
    seen: set[str] = set()
    for step in receipt.steps:
        if step.step_id in seen:
            return False
        if any(dependency not in seen for dependency in step.depends_on):
            return False
        seen.add(step.step_id)
    return True


def _release_checks(receipt: MissionPlanPublicReceipt) -> tuple[MissionPlanReleaseCheck, ...]:
    public_body = receipt.to_dict()
    expected_steps = receipt.step_count
    observed_steps = len(receipt.steps)
    resource_cpu = round(sum(float(item.resource.get("cpu", 0.0)) for item in receipt.steps), 6)
    resource_memory = round(
        max((float(item.resource.get("memory_gb", 0.0)) for item in receipt.steps), default=0.0),
        6,
    )
    resource_storage = round(
        sum(float(item.resource.get("storage_gb", 0.0)) for item in receipt.steps),
        6,
    )
    resource_seconds = sum(int(item.resource.get("max_seconds", 0)) for item in receipt.steps)
    return (
        _check(
            "public-boundary",
            "boundary",
            not _private_key_paths(public_body) and not contains_private_key(public_body),
            "no restricted metadata paths",
            list(_private_key_paths(public_body)),
            "The receipt remains inside the public contract boundary.",
        ),
        _check(
            "receipt-address",
            "address",
            MissionPlanPublicReceipt.from_mapping(public_body).content_address == receipt.content_address,
            receipt.content_address,
            receipt.content_address,
            "The receipt address reconstructs from its published fields.",
        ),
        _check(
            "workflow-order",
            "workflow",
            _workflow_order_valid(receipt),
            "dependencies precede dependants",
            [item.step_id for item in receipt.steps],
            "The published workflow is a dependency-safe ordered DAG.",
        ),
        _check(
            "step-count",
            "workflow",
            expected_steps == observed_steps,
            expected_steps,
            observed_steps,
            "The declared step count matches the published step rows.",
        ),
        _check(
            "resource-accounting",
            "resources",
            (
                resource_cpu == round(receipt.total_cpu, 6)
                and resource_memory == round(receipt.peak_memory_gb, 6)
                and resource_storage == round(receipt.total_storage_gb, 6)
                and resource_seconds == receipt.max_seconds
            ),
            {
                "total_cpu": receipt.total_cpu,
                "peak_memory_gb": receipt.peak_memory_gb,
                "total_storage_gb": receipt.total_storage_gb,
                "max_seconds": receipt.max_seconds,
            },
            {
                "total_cpu": resource_cpu,
                "peak_memory_gb": resource_memory,
                "total_storage_gb": resource_storage,
                "max_seconds": resource_seconds,
            },
            "Aggregate resource totals reconcile with the published steps.",
        ),
    )


def _checks_payload(
    receipt: MissionPlanPublicReceipt,
    checks: tuple[MissionPlanReleaseCheck, ...],
    release_id: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "checks_version": MISSION_PLAN_RELEASE_CHECKS_VERSION,
        "release_id": release_id,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "check_count": len(checks),
        "accepted": all(item.accepted for item in checks),
        "checks": [item.to_dict() for item in checks],
    }
    return body | {
        "content_address": content_hash(body, prefix=MISSION_PLAN_RELEASE_CHECKS_PREFIX)
    }


def _summary_payload(
    receipt: MissionPlanPublicReceipt,
    checks: tuple[MissionPlanReleaseCheck, ...],
    artifacts: tuple[MissionPlanReleaseArtifact, ...],
    release_id: str,
) -> dict[str, Any]:
    artifact_names = [item.filename for item in artifacts] + ["release-summary.json"]
    body: dict[str, Any] = {
        "summary_version": MISSION_PLAN_RELEASE_SUMMARY_VERSION,
        "release_id": release_id,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "state": receipt.state.value,
        "accepted": receipt.accepted and all(item.accepted for item in checks),
        "step_count": receipt.step_count,
        "check_count": len(checks),
        "failed_check_count": sum(not item.accepted for item in checks),
        "artifact_count": len(artifact_names),
        "artifact_names": sorted(artifact_names),
        "boundary_accepted": receipt.boundary_accepted,
    }
    return body | {
        "content_address": content_hash(body, prefix=MISSION_PLAN_RELEASE_SUMMARY_PREFIX)
    }


def _manifest_payload(
    receipt: MissionPlanPublicReceipt,
    checks: tuple[MissionPlanReleaseCheck, ...],
    artifacts: tuple[MissionPlanReleaseArtifact, ...],
    summary: Mapping[str, Any],
    checks_payload: Mapping[str, Any],
    release_id: str,
    accepted: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "release_version": MISSION_PLAN_RELEASE_VERSION,
        "public_plan_version": MISSION_PLAN_PUBLIC_VERSION,
        "release_id": release_id,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "state": receipt.state.value,
        "accepted": accepted,
        "step_count": receipt.step_count,
        "check_count": len(checks),
        "checks_address": checks_payload["content_address"],
        "summary_address": summary["content_address"],
        "artifact_count": len(artifacts),
        "artifacts": [item.to_dict() for item in artifacts],
        "public_boundary_valid": not _private_key_paths(receipt.to_dict())
        and not contains_private_key(receipt.to_dict()),
    }
    return body | {
        "manifest_address": content_hash(body, prefix=MISSION_PLAN_RELEASE_MANIFEST_PREFIX)
    }


def build_mission_plan_release(
    value: MissionPlanPublicReceipt | Mapping[str, Any],
    *,
    release_id: str | None = None,
) -> MissionPlanReleaseBundle:
    """Build a deterministic public release from a receipt or JSON mapping."""

    receipt = value if isinstance(value, MissionPlanPublicReceipt) else MissionPlanPublicReceipt.from_mapping(value)
    # Round-trip before packaging so a caller cannot smuggle an unaddressed
    # dataclass field into a release.
    receipt = MissionPlanPublicReceipt.from_mapping(receipt.to_dict())
    selected_release_id = release_id or (
        "mission-plan-release-" + receipt.content_address.split(":", 1)[-1][:24]
    )
    selected_release_id = _text(selected_release_id, "release_id", maximum=192)
    checks = _release_checks(receipt)
    checks_payload = _checks_payload(receipt, checks, selected_release_id)
    payloads: dict[str, bytes] = {
        "mission-plan.json": mission_plan_public_json(receipt).encode("utf-8"),
        "mission-plan.md": (render_mission_plan_public_markdown(receipt) + "\n").encode("utf-8"),
        "mission-plan-steps.csv": mission_plan_public_csv(receipt).encode("utf-8"),
        "release-checks.json": (canonical_json(checks_payload) + "\n").encode("utf-8"),
    }
    checks_artifacts = tuple(
        _artifact(filename.replace(".", "-"), filename, payload)
        for filename, payload in sorted(payloads.items())
    )
    summary_payload = _summary_payload(receipt, checks, checks_artifacts, selected_release_id)
    payloads["release-summary.json"] = (canonical_json(summary_payload) + "\n").encode("utf-8")
    artifacts = tuple(
        _artifact(filename.replace(".", "-"), filename, payload)
        for filename, payload in sorted(payloads.items())
    )
    accepted = receipt.accepted and all(item.accepted for item in checks) and set(payloads) == MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS
    manifest = _manifest_payload(
        receipt,
        checks,
        artifacts,
        summary_payload,
        checks_payload,
        selected_release_id,
        accepted,
    )
    body = {
        "release_id": selected_release_id,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "state": receipt.state.value,
        "accepted": accepted,
        "receipt": receipt,
        "checks": checks,
        "artifacts": [item.to_dict() for item in artifacts],
        "manifest": manifest,
    }
    return MissionPlanReleaseBundle(
        release_id=selected_release_id,
        plan_id=receipt.plan_id,
        plan_address=receipt.content_address,
        state=receipt.state.value,
        accepted=accepted,
        receipt=receipt,
        checks=checks,
        artifacts=artifacts,
        manifest=manifest,
        content_address=content_hash(body, prefix="mission-plan-release"),
    )


def write_mission_plan_release(
    bundle: MissionPlanReleaseBundle,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Materialize exact UTF-8 bytes without deleting existing files."""

    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("mission plan release destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValueError("mission plan release destination is not empty; pass allow_existing=True to overwrite")
    for artifact in bundle.artifacts:
        filename = _safe_filename(artifact.filename)
        target = root / filename
        if target.exists() and target.is_symlink():
            raise ValidationError(f"mission plan release artifact must not be a symlink: {filename}")
        target.write_bytes(artifact.payload)
    manifest_target = root / MISSION_PLAN_RELEASE_MANIFEST_FILE
    if manifest_target.exists() and manifest_target.is_symlink():
        raise ValidationError("mission plan release manifest must not be a symlink")
    manifest_target.write_bytes((canonical_json(bundle.manifest) + "\n").encode("utf-8"))
    return root


def _verification(
    *,
    root: Path,
    release_id: str,
    accepted: bool,
    manifest_version_valid: bool = False,
    manifest_address_valid: bool = False,
    receipt_address_valid: bool = False,
    checks_valid: bool = False,
    summary_valid: bool = False,
    artifact_set_valid: bool = False,
    exact_bytes: bool = False,
    public_boundary_valid: bool = False,
    artifact_count: int = 0,
    verified_artifact_count: int = 0,
    missing_files: Iterable[str] = (),
    unexpected_files: Iterable[str] = (),
    unsafe_files: Iterable[str] = (),
    tampered_files: Iterable[str] = (),
    boundary_violations: Iterable[str] = (),
    warnings: Iterable[str] = (),
) -> MissionPlanReleaseVerification:
    body = {
        "path": str(root),
        "release_id": release_id,
        "accepted": accepted,
        "manifest_version_valid": manifest_version_valid,
        "manifest_address_valid": manifest_address_valid,
        "receipt_address_valid": receipt_address_valid,
        "checks_valid": checks_valid,
        "summary_valid": summary_valid,
        "artifact_set_valid": artifact_set_valid,
        "exact_bytes": exact_bytes,
        "public_boundary_valid": public_boundary_valid,
        "artifact_count": artifact_count,
        "verified_artifact_count": verified_artifact_count,
        "missing_files": tuple(sorted(set(missing_files))),
        "unexpected_files": tuple(sorted(set(unexpected_files))),
        "unsafe_files": tuple(sorted(set(unsafe_files))),
        "tampered_files": tuple(sorted(set(tampered_files))),
        "boundary_violations": tuple(sorted(set(boundary_violations))),
        "warnings": tuple(dict.fromkeys(str(item) for item in warnings if str(item).strip())),
    }
    return MissionPlanReleaseVerification(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-verification"),
    )


def verify_mission_plan_release(destination: str | Path) -> MissionPlanReleaseVerification:
    """Verify manifest closure, exact bytes, receipt, checks, and boundary."""

    root = Path(destination)
    if not root.is_dir() or root.is_symlink():
        raise ValidationError("mission plan release directory is missing or is a symlink")
    manifest_path = root / MISSION_PLAN_RELEASE_MANIFEST_FILE
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return _verification(root=root, release_id="", missing_files=(MISSION_PLAN_RELEASE_MANIFEST_FILE,))
    missing: list[str] = []
    unexpected: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    boundary: list[str] = []
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _verification(root=root, release_id="", tampered_files=(MISSION_PLAN_RELEASE_MANIFEST_FILE,))
    if not isinstance(manifest, dict):
        return _verification(root=root, release_id="", tampered_files=(MISSION_PLAN_RELEASE_MANIFEST_FILE,))
    release_id = str(manifest.get("release_id", ""))
    version_valid = manifest.get("release_version") == MISSION_PLAN_RELEASE_VERSION
    listed_address = manifest.get("manifest_address")
    normalized_manifest = {key: item for key, item in manifest.items() if key != "manifest_address"}
    address_valid = listed_address == content_hash(
        normalized_manifest,
        prefix=MISSION_PLAN_RELEASE_MANIFEST_PREFIX,
    )
    exact_manifest = manifest_bytes == (canonical_json(manifest) + "\n").encode("utf-8")
    if not version_valid or not address_valid or not exact_manifest:
        tampered.append(MISSION_PLAN_RELEASE_MANIFEST_FILE)
    boundary.extend(f"manifest:{item}" for item in _private_key_paths(manifest))
    listed_artifacts = manifest.get("artifacts", ())
    if not isinstance(listed_artifacts, list):
        listed_artifacts = []
        tampered.append("manifest.artifacts")
    expected: list[str] = []
    artifact_rows: dict[str, Mapping[str, Any]] = {}
    for row in listed_artifacts:
        if not isinstance(row, Mapping):
            tampered.append("manifest.artifacts")
            continue
        try:
            filename = _safe_filename(row.get("filename"))
        except ValidationError:
            unsafe.append(str(row.get("filename", "")))
            continue
        if filename in expected:
            unsafe.append(filename)
        expected.append(filename)
        artifact_rows[filename] = row
    actual = sorted(
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() or item.is_symlink()
    )
    unexpected.extend(
        item for item in actual if item not in {*expected, MISSION_PLAN_RELEASE_MANIFEST_FILE}
    )
    missing.extend(item for item in MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS if item not in expected)
    unsafe.extend(item for item in expected if item not in MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS)
    artifact_set_valid = (
        set(expected) == MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS
        and len(expected) == len(MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS)
    )
    try:
        artifact_count_valid = int(manifest.get("artifact_count", -1)) == len(expected)
    except (TypeError, ValueError, OverflowError):
        artifact_count_valid = False
    if not artifact_count_valid:
        tampered.append("manifest.artifact_count")
    verified_count = 0
    payloads: dict[str, bytes] = {}
    exact_bytes = True
    for filename, row in artifact_rows.items():
        target = root / filename
        if not target.is_file() or target.is_symlink():
            missing.append(filename)
            exact_bytes = False
            continue
        try:
            payload = target.read_bytes()
            valid = (
                len(payload) == int(row.get("byte_count", -1))
                and len(payload.decode("utf-8").splitlines()) == int(row.get("line_count", -1))
                and hash_bytes(payload, prefix=MISSION_PLAN_RELEASE_ARTIFACT_PREFIX)
                == row.get("content_address")
                and row.get("media_type") == _media_type(filename)
            )
        except (OSError, UnicodeError, TypeError, ValueError):
            valid = False
            payload = b""
        if not valid:
            tampered.append(filename)
            exact_bytes = False
            continue
        verified_count += 1
        payloads[filename] = payload
        if filename.endswith(".json"):
            try:
                parsed = json.loads(payload.decode("utf-8"))
                boundary.extend(f"{filename}:{item}" for item in _private_key_paths(parsed))
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(filename)
    receipt: MissionPlanPublicReceipt | None = None
    receipt_address_valid = False
    checks_valid = False
    summary_valid = False
    loaded_checks: tuple[MissionPlanReleaseCheck, ...] = ()
    checks_body: Mapping[str, Any] | None = None
    summary_body: Mapping[str, Any] | None = None
    if "mission-plan.json" in payloads:
        try:
            raw_receipt = json.loads(payloads["mission-plan.json"].decode("utf-8"))
            receipt = MissionPlanPublicReceipt.from_mapping(raw_receipt)
            receipt_address_valid = (
                receipt.content_address == manifest.get("plan_address")
                and receipt.plan_id == manifest.get("plan_id")
                and receipt.state.value == manifest.get("state")
                and receipt.step_count == manifest.get("step_count")
            )
            if not receipt_address_valid:
                tampered.append("plan-address")
            if payloads["mission-plan.json"] != mission_plan_public_json(receipt).encode("utf-8"):
                tampered.append("mission-plan.json")
                exact_bytes = False
        except (UnicodeError, json.JSONDecodeError, ValidationError, TypeError):
            tampered.append("mission-plan.json")
    if "release-checks.json" in payloads:
        try:
            checks_body = json.loads(payloads["release-checks.json"].decode("utf-8"))
            if not isinstance(checks_body, Mapping):
                raise ValidationError("release checks must be an object")
            _address_without_content(
                checks_body,
                prefix=MISSION_PLAN_RELEASE_CHECKS_PREFIX,
                field="release-checks",
            )
            if payloads["release-checks.json"] != (canonical_json(checks_body) + "\n").encode("utf-8"):
                tampered.append("release-checks.json")
                exact_bytes = False
            raw_checks = checks_body.get("checks", ())
            if not isinstance(raw_checks, list):
                raise ValidationError("release checks must be an array")
            loaded_checks = tuple(MissionPlanReleaseCheck.from_mapping(item) for item in raw_checks)
            checks_valid = (
                receipt is not None
                and checks_body.get("release_id") == release_id
                and checks_body.get("plan_id") == manifest.get("plan_id")
                and checks_body.get("plan_address") == manifest.get("plan_address")
                and checks_body.get("checks_version") == MISSION_PLAN_RELEASE_CHECKS_VERSION
                and int(checks_body.get("check_count", -1)) == len(loaded_checks)
                and bool(checks_body.get("accepted")) == all(item.accepted for item in loaded_checks)
                and loaded_checks == _release_checks(receipt)
                and checks_body.get("content_address") == manifest.get("checks_address")
            )
        except (UnicodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            tampered.append("release-checks.json")
    if "release-summary.json" in payloads:
        try:
            summary_body = json.loads(payloads["release-summary.json"].decode("utf-8"))
            if not isinstance(summary_body, Mapping):
                raise ValidationError("release summary must be an object")
            _address_without_content(
                summary_body,
                prefix=MISSION_PLAN_RELEASE_SUMMARY_PREFIX,
                field="release-summary",
            )
            if payloads["release-summary.json"] != (canonical_json(summary_body) + "\n").encode("utf-8"):
                tampered.append("release-summary.json")
                exact_bytes = False
            summary_valid = (
                receipt is not None
                and tuple(summary_body.get("artifact_names", ()))
                == tuple(sorted(MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS))
                and summary_body.get("release_id") == release_id
                and summary_body.get("summary_version") == MISSION_PLAN_RELEASE_SUMMARY_VERSION
                and summary_body.get("artifact_count") == len(MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS)
                and summary_body.get("check_count") == len(loaded_checks)
                and summary_body.get("failed_check_count")
                == sum(not item.accepted for item in loaded_checks)
                and summary_body.get("plan_address") == manifest.get("plan_address")
                and summary_body.get("state") == manifest.get("state")
                and summary_body.get("accepted")
                == bool(receipt and receipt.accepted and all(item.accepted for item in loaded_checks))
                and summary_body.get("boundary_accepted") is True
                and summary_body.get("content_address") == manifest.get("summary_address")
            )
        except (UnicodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            tampered.append("release-summary.json")
    public_boundary_valid = not boundary and bool(manifest.get("public_boundary_valid", False))
    manifest_fields_valid = (
        manifest.get("public_plan_version") == MISSION_PLAN_PUBLIC_VERSION
        and manifest.get("step_count") == (receipt.step_count if receipt is not None else None)
        and manifest.get("check_count") == len(loaded_checks)
        and manifest.get("accepted")
        == bool(receipt and receipt.accepted and all(item.accepted for item in loaded_checks))
    )
    if not manifest_fields_valid:
        tampered.append("manifest.fields")
    accepted = bool(
        version_valid
        and address_valid
        and receipt_address_valid
        and checks_valid
        and summary_valid
        and artifact_set_valid
        and artifact_count_valid
        and manifest_fields_valid
        and exact_bytes
        and public_boundary_valid
        and not missing
        and not unexpected
        and not unsafe
        and not tampered
    )
    warnings: list[str] = []
    if not accepted and bool(manifest.get("accepted")):
        warnings.append("manifest declared acceptance but independent verification rejected the package")
    return _verification(
        root=root,
        release_id=release_id,
        accepted=accepted,
        manifest_version_valid=version_valid,
        manifest_address_valid=address_valid,
        receipt_address_valid=receipt_address_valid,
        checks_valid=checks_valid,
        summary_valid=summary_valid,
        artifact_set_valid=artifact_set_valid,
        exact_bytes=exact_bytes,
        public_boundary_valid=public_boundary_valid,
        artifact_count=len(expected),
        verified_artifact_count=verified_count,
        missing_files=missing,
        unexpected_files=unexpected,
        unsafe_files=unsafe,
        tampered_files=tampered,
        boundary_violations=boundary,
        warnings=warnings,
    )


def _load_manifest(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((root / MISSION_PLAN_RELEASE_MANIFEST_FILE).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load mission plan release manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError("mission plan release manifest must be an object")
    return value


def load_mission_plan_release(destination: str | Path) -> MissionPlanOfflineRelease:
    """Verify and hydrate a release for offline queries and diffs."""

    root = Path(destination)
    verification = verify_mission_plan_release(root)
    if not verification.accepted:
        raise ValidationError("mission plan release filesystem verification failed")
    manifest = _load_manifest(root)
    receipt = MissionPlanPublicReceipt.from_mapping(
        json.loads((root / "mission-plan.json").read_text(encoding="utf-8"))
    )
    checks_body = json.loads((root / "release-checks.json").read_text(encoding="utf-8"))
    checks = tuple(MissionPlanReleaseCheck.from_mapping(item) for item in checks_body["checks"])
    body = {
        "path": str(root),
        "release_id": manifest["release_id"],
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "receipt": receipt,
        "checks": checks,
        "manifest": manifest,
        "verification": verification,
        "accepted": True,
    }
    return MissionPlanOfflineRelease(
        path=str(root),
        release_id=_text(manifest.get("release_id"), "release_id"),
        plan_id=receipt.plan_id,
        plan_address=receipt.content_address,
        receipt=receipt,
        checks=checks,
        manifest=manifest,
        verification=verification,
        accepted=True,
        content_address=content_hash(body, prefix="mission-plan-offline-release"),
    )


def mission_plan_release_schema() -> dict[str, Any]:
    """Return the versioned release and verification contract."""

    return {
        "version": MISSION_PLAN_RELEASE_SCHEMA_VERSION,
        "release_version": MISSION_PLAN_RELEASE_VERSION,
        "public_plan_version": MISSION_PLAN_PUBLIC_VERSION,
        "type": "directory",
        "required_files": sorted((*MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS, MISSION_PLAN_RELEASE_MANIFEST_FILE)),
        "artifact_fields": [
            "artifact_id",
            "filename",
            "media_type",
            "byte_count",
            "line_count",
            "content_address",
        ],
        "verification": [
            "manifest_version_valid",
            "manifest_address_valid",
            "receipt_address_valid",
            "checks_valid",
            "summary_valid",
            "artifact_set_valid",
            "exact_bytes",
            "public_boundary_valid",
        ],
        "limits": {
            "max_artifacts": MISSION_PLAN_RELEASE_MAX_ARTIFACTS,
            "max_checks": MISSION_PLAN_RELEASE_MAX_CHECKS,
        },
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "private_identity": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_capabilities() -> dict[str, Any]:
    """Return operational capabilities for the release plane."""

    return {
        "version": MISSION_PLAN_RELEASE_CAPABILITIES_VERSION,
        "exact_byte_artifacts": True,
        "content_addressed_manifest": True,
        "independent_verification": True,
        "offline_hydration": True,
        "public_boundary_audit": True,
        "tamper_detection": True,
        "symlink_rejection": True,
        "deterministic_json": True,
        "deterministic_markdown": True,
        "deterministic_csv": True,
        "read_only_verification": True,
        "research_use_only": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_ARTIFACT_PREFIX",
    "MISSION_PLAN_RELEASE_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CHECKS_PREFIX",
    "MISSION_PLAN_RELEASE_CHECKS_VERSION",
    "MISSION_PLAN_RELEASE_MANIFEST_FILE",
    "MISSION_PLAN_RELEASE_MANIFEST_PREFIX",
    "MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS",
    "MISSION_PLAN_RELEASE_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_SUMMARY_PREFIX",
    "MISSION_PLAN_RELEASE_SUMMARY_VERSION",
    "MISSION_PLAN_RELEASE_VERSION",
    "MissionPlanOfflineRelease",
    "MissionPlanReleaseArtifact",
    "MissionPlanReleaseBundle",
    "MissionPlanReleaseCheck",
    "MissionPlanReleaseVerification",
    "build_mission_plan_release",
    "load_mission_plan_release",
    "mission_plan_release_capabilities",
    "mission_plan_release_schema",
    "verify_mission_plan_release",
    "write_mission_plan_release",
]
